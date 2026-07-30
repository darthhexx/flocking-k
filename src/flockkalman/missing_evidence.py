"""M9A.6 missing-evidence posterior and risk-priced output policy.

The controller treats declared missing evidence and model mismatch separately.
Assignment uncertainty is marginalized by the causal Bayesian filter.  A
posterior-predictive check maintains residual probability mass for effects
outside that model; the residual mass is never converted into positive support
for a returned target mode.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .config import ExperimentConfig
from .oracle_floor import AssignmentBayesFilter, BayesianMode, FloatArray, BoolArray


M9A6_ALGORITHM = "flocking_topology_posterior"


@dataclass(frozen=True, slots=True)
class MissingEvidenceDecision:
    """One causal, risk-priced M9A.6 output decision."""

    action: str
    state: FloatArray
    covariance: FloatArray
    modes: tuple[BayesianMode, ...]
    credible_modes: tuple[BayesianMode, ...]
    selected_mode_index: int | None
    predicted_risk: float
    predicted_wrong_risk: float
    confidence: float
    residual_mass: float
    model_residual_mass: float
    external_residual_mass: float
    model_nis: float
    assignment_entropy: float


def _moment_match(modes: tuple[BayesianMode, ...]) -> tuple[FloatArray, FloatArray]:
    state = sum(
        (mode.probability * mode.state for mode in modes),
        start=np.zeros(4, dtype=float),
    )
    covariance = np.zeros((4, 4), dtype=float)
    for mode in modes:
        difference = mode.state - state
        covariance += mode.probability * (
            mode.covariance + np.outer(difference, difference)
        )
    return state, 0.5 * (covariance + covariance.T)


def _candidate_risk(
    candidate: FloatArray,
    modes: tuple[BayesianMode, ...],
) -> float:
    return float(
        sum(
            mode.probability
            * math.sqrt(
                max(
                    0.0,
                    float(np.sum((candidate[:2] - mode.state[:2]) ** 2))
                    + float(np.trace(mode.covariance[:2, :2])),
                )
            )
            for mode in modes
        )
    )


class MissingEvidenceController:
    """Maintain the M9A.6 posterior and choose a bounded-risk output."""

    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        overrides = (
            {
                "secondary_count": config.m9a6_model_secondary_count,
                "secondary_offset": config.m9a6_model_secondary_offset,
                "secondary_start_step": config.m9a6_model_secondary_start_step,
                "secondary_end_step": config.m9a6_model_secondary_end_step,
            }
            if config.m9a6_override_declared_model
            else {}
        )
        self.filter = AssignmentBayesFilter(config, **overrides)
        self._residual_mass = config.m9a6_residual_base_mass

    @property
    def residual_mass(self) -> float:
        return self._residual_mass

    def _update_residual_mass(self) -> None:
        # No observation is not evidence that the declared model fits.  Keep
        # the previous residual probability through a complete local outage.
        if self.filter.last_measurement_count == 0:
            return
        span = (
            self.config.m9a6_residual_nis_full
            - self.config.m9a6_residual_nis_start
        )
        mismatch = np.clip(
            (self.filter.last_model_nis - self.config.m9a6_residual_nis_start)
            / span,
            0.0,
            1.0,
        )
        target = self.config.m9a6_residual_base_mass + (
            1.0 - self.config.m9a6_residual_base_mass
        ) * float(mismatch)
        alpha = self.config.m9a6_residual_ema_alpha
        self._residual_mass = max(
            self.config.m9a6_residual_base_mass,
            (1.0 - alpha) * self._residual_mass + alpha * target,
        )

    def _credible_modes(
        self, modes: tuple[BayesianMode, ...]
    ) -> tuple[BayesianMode, ...]:
        cumulative = 0.0
        credible: list[BayesianMode] = []
        for mode in modes:
            credible.append(mode)
            cumulative += mode.probability
            if cumulative >= self.config.m9a6_credible_mass:
                break
        return tuple(credible)

    def _wrong_risk(
        self,
        candidate: FloatArray,
        modes: tuple[BayesianMode, ...],
        residual_mass: float,
    ) -> float:
        model_wrong = sum(
            mode.probability
            for mode in modes
            if float(np.linalg.norm(candidate[:2] - mode.state[:2]))
            > self.config.robust_bias_group_tolerance
        )
        return residual_mass + (1.0 - residual_mass) * model_wrong

    def update(
        self,
        step: int,
        observations: FloatArray,
        measurement_covariances: tuple[FloatArray, ...],
        visible: BoolArray,
        *,
        force_defer: bool = False,
        external_residual_mass: float = 0.0,
        measurement_nis_ceiling: float | None = None,
    ) -> MissingEvidenceDecision:
        if not 0.0 <= external_residual_mass <= 1.0:
            raise ValueError("external_residual_mass must be in [0, 1]")
        self.filter.advance(
            step,
            observations,
            measurement_covariances,
            visible,
            measurement_nis_ceiling=measurement_nis_ceiling,
        )
        self._update_residual_mass()
        residual_mass = 1.0 - (
            (1.0 - self._residual_mass) * (1.0 - external_residual_mass)
        )
        modes = self.filter.modes()
        credible = self._credible_modes(modes)
        mixture_state, mixture_covariance = _moment_match(modes)

        candidates: list[
            tuple[str, FloatArray, FloatArray, int | None, float, float]
        ] = []
        for index, mode in enumerate(modes):
            model_risk = _candidate_risk(mode.state, modes)
            risk = (
                (1.0 - residual_mass) * model_risk
                + residual_mass * self.config.m9a6_residual_loss
            )
            wrong_risk = self._wrong_risk(mode.state, modes, residual_mass)
            candidates.append(
                (
                    "select",
                    mode.state.copy(),
                    mode.covariance.copy(),
                    index,
                    risk,
                    wrong_risk,
                )
            )
        if len(modes) > 1:
            model_risk = _candidate_risk(mixture_state, modes)
            candidates.append(
                (
                    "mixture",
                    mixture_state,
                    mixture_covariance,
                    None,
                    (1.0 - residual_mass) * model_risk
                    + residual_mass * self.config.m9a6_residual_loss,
                    self._wrong_risk(mixture_state, modes, residual_mass),
                )
            )

        allowed = [
            candidate
            for candidate in candidates
            if candidate[5] <= self.config.m9a6_wrong_risk_ceiling
        ]
        best_candidate = min(
            allowed or candidates,
            key=lambda item: (
                item[4],
                item[0],
                float(item[1][0]),
                float(item[1][1]),
            ),
        )

        known_set_risk = 0.0
        for mode in modes:
            nearest = min(
                math.sqrt(
                    max(
                        0.0,
                        float(np.sum((candidate.state[:2] - mode.state[:2]) ** 2))
                        + float(np.trace(mode.covariance[:2, :2])),
                    )
                )
                for candidate in credible
            )
            known_set_risk += mode.probability * nearest
        # Model mismatch is irreducible at decision time: abstaining avoids a
        # wrong point choice, but it does not make unknown evidence disappear.
        # Charge the same residual loss to every action, then add the explicit
        # defer cost.  The separate wrong-risk ceiling remains responsible for
        # forcing abstention when residual support is too large.
        defer_risk = (
            (1.0 - residual_mass) * known_set_risk
            + residual_mass * self.config.m9a6_residual_loss
            + self.config.output_defer_cost
        )
        selection_blocked = (
            not allowed
            or best_candidate[5] > self.config.m9a6_wrong_risk_ceiling
        )
        if force_defer or selection_blocked or defer_risk + 1e-12 < best_candidate[4]:
            action = "defer"
            state = mixture_state
            covariance = mixture_covariance
            selected_mode_index = None
            predicted_risk = defer_risk
            predicted_wrong_risk = residual_mass
        else:
            (
                action,
                state,
                covariance,
                selected_mode_index,
                predicted_risk,
                predicted_wrong_risk,
            ) = best_candidate

        runner_up = modes[1].probability if len(modes) > 1 else 0.0
        confidence = (
            (1.0 - residual_mass)
            * (modes[0].probability - runner_up)
            - residual_mass
        )
        return MissingEvidenceDecision(
            action=action,
            state=state.copy(),
            covariance=covariance.copy(),
            modes=modes,
            credible_modes=credible,
            selected_mode_index=selected_mode_index,
            predicted_risk=float(predicted_risk),
            predicted_wrong_risk=float(predicted_wrong_risk),
            confidence=float(confidence),
            residual_mass=residual_mass,
            model_residual_mass=self._residual_mass,
            external_residual_mass=external_residual_mass,
            model_nis=self.filter.last_model_nis,
            assignment_entropy=self.filter.normalized_assignment_entropy,
        )
