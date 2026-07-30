"""M10A causal defenses for the permissive M9A.7 raw-measurement channel.

The controller is deliberately an output-layer overlay.  It consumes the same
causal masks and observations as M9A.7, but it never receives simulation truth
or fault identity.  Trust affects measurement covariance and bounded residual
support; it does not alter the M6 quarantine channel.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .admission_evidence import (
    AdmissionAwareController,
    floor_reported_covariances,
)
from .config import ExperimentConfig
from .missing_evidence import MissingEvidenceController, MissingEvidenceDecision
from .oracle_floor import BoolArray, FloatArray


M10A_DEFENSE_MODES = (
    "cross_channel",
    "ramp_rate",
    "influence_budget",
    "combined",
)


@dataclass(frozen=True, slots=True)
class AdversarialTrustConfig:
    """Frozen M10A parameters, separate from the historical M9 config."""

    cross_nis_start: float = 9.21
    cross_nis_full: float = 25.0
    strong_floor_ratio: float = 0.10
    trust_attack_alpha: float = 0.45
    trust_recovery_alpha: float = 0.20
    trust_alert_threshold: float = 0.50
    minimum_trust: float = 0.05
    offset_ema_alpha: float = 0.15
    ramp_rate_start: float = 0.12
    ramp_rate_full: float = 0.40
    raw_only_precision_fraction: float = 0.35
    trust_residual_alpha: float = 0.25
    trust_residual_cap: float = 0.08

    def validate(self) -> None:
        if not 0.0 < self.cross_nis_start < self.cross_nis_full:
            raise ValueError("cross-channel NIS thresholds must be ordered")
        if not 0.0 < self.strong_floor_ratio < 1.0:
            raise ValueError("strong_floor_ratio must be in (0, 1)")
        for name, value in (
            ("trust_attack_alpha", self.trust_attack_alpha),
            ("trust_recovery_alpha", self.trust_recovery_alpha),
            ("minimum_trust", self.minimum_trust),
            ("offset_ema_alpha", self.offset_ema_alpha),
            ("raw_only_precision_fraction", self.raw_only_precision_fraction),
            ("trust_residual_alpha", self.trust_residual_alpha),
            ("trust_residual_cap", self.trust_residual_cap),
        ):
            if not 0.0 < value < 1.0:
                raise ValueError(f"{name} must be in (0, 1)")
        if not self.minimum_trust < self.trust_alert_threshold < 1.0:
            raise ValueError("trust alert threshold must exceed minimum trust")
        if not 0.0 < self.ramp_rate_start < self.ramp_rate_full:
            raise ValueError("ramp-rate thresholds must be ordered")


@dataclass(frozen=True, slots=True)
class AdversarialTrustDecision:
    """One posterior decision plus auditable M10A trust diagnostics."""

    posterior: MissingEvidenceDecision
    measurement_eligible_agents: int
    belief_admitted_agents: int
    belief_censored_measurement_agents: int
    robust_excluded_measurement_agents: int
    unreachable_measurement_agents: int
    covariance_floored_agents: int
    model_rejected_measurement_agents: int
    admission_residual_mass: float
    excluded_secondary_probability: float
    unreachable_secondary_probability: float
    cross_channel_disagreement_agents: int
    strong_floor_evidence_agents: int
    ramp_alert_agents: int
    influence_capped_agents: int
    trust_alert_agents: int
    mean_raw_trust: float
    minimum_raw_trust: float
    raw_only_precision_fraction: float
    trust_residual_mass: float
    trust_scores: FloatArray


def _linear_signal(value: FloatArray, start: float, full: float) -> FloatArray:
    return np.clip((value - start) / (full - start), 0.0, 1.0)


def _secondary_probability(
    controller: MissingEvidenceController,
    agents: BoolArray,
) -> float:
    if not np.any(agents):
        return 0.0
    assignments = controller.filter.assignment_mask[:, agents]
    contains_secondary = np.any(assignments, axis=1)
    return float(np.sum(controller.filter.weights[contains_secondary]))


def _precision(covariance: FloatArray) -> float:
    return float(np.trace(np.linalg.inv(covariance)))


class AdversarialTrustController:
    """Discount coherent raw-channel influence without erasing valid modes."""

    def __init__(
        self,
        config: ExperimentConfig,
        defense_mode: str,
        trust_config: AdversarialTrustConfig | None = None,
    ) -> None:
        if defense_mode not in {"none", *M10A_DEFENSE_MODES}:
            raise ValueError(f"unknown M10A defense mode: {defense_mode}")
        self.config = config
        self.defense_mode = defense_mode
        self.trust_config = trust_config or AdversarialTrustConfig()
        self.trust_config.validate()
        self._baseline = (
            AdmissionAwareController(config) if defense_mode == "none" else None
        )
        self.posterior = (
            self._baseline.posterior
            if self._baseline is not None
            else MissingEvidenceController(config)
        )
        self._admission_residual_mass = 0.0
        self._trust_residual_mass = 0.0
        self._trust = np.ones(config.n_agents, dtype=float)
        self._offset_ema = np.zeros((config.n_agents, 2), dtype=float)
        self._offset_seen = np.zeros(config.n_agents, dtype=bool)

    def _baseline_decision(
        self,
        step: int,
        observations: FloatArray,
        measurement_covariances: tuple[FloatArray, ...],
        *,
        component_visible: BoolArray,
        available: BoolArray,
        operational: BoolArray,
        raw_trusted: BoolArray,
        source_quarantined: BoolArray,
        belief_share_eligible: BoolArray,
        belief_admitted: BoolArray,
        force_defer: bool,
    ) -> AdversarialTrustDecision:
        assert self._baseline is not None
        result = self._baseline.update(
            step,
            observations,
            measurement_covariances,
            component_visible=component_visible,
            available=available,
            operational=operational,
            raw_trusted=raw_trusted,
            source_quarantined=source_quarantined,
            belief_share_eligible=belief_share_eligible,
            belief_admitted=belief_admitted,
            force_defer=force_defer,
        )
        return AdversarialTrustDecision(
            posterior=result.posterior,
            measurement_eligible_agents=result.measurement_eligible_agents,
            belief_admitted_agents=result.belief_admitted_agents,
            belief_censored_measurement_agents=(
                result.belief_censored_measurement_agents
            ),
            robust_excluded_measurement_agents=(
                result.robust_excluded_measurement_agents
            ),
            unreachable_measurement_agents=result.unreachable_measurement_agents,
            covariance_floored_agents=result.covariance_floored_agents,
            model_rejected_measurement_agents=(
                result.model_rejected_measurement_agents
            ),
            admission_residual_mass=result.admission_residual_mass,
            excluded_secondary_probability=result.excluded_secondary_probability,
            unreachable_secondary_probability=(
                result.unreachable_secondary_probability
            ),
            cross_channel_disagreement_agents=0,
            strong_floor_evidence_agents=0,
            ramp_alert_agents=0,
            influence_capped_agents=0,
            trust_alert_agents=0,
            mean_raw_trust=1.0,
            minimum_raw_trust=1.0,
            raw_only_precision_fraction=0.0,
            trust_residual_mass=0.0,
            trust_scores=np.ones(self.config.n_agents, dtype=float),
        )

    def _assignment_corrected_reference(
        self,
        step: int,
        observations: FloatArray,
        sanitized_covariances: tuple[FloatArray, ...],
        measurement_visible: BoolArray,
        belief_visible: BoolArray,
    ) -> tuple[FloatArray, FloatArray, FloatArray, FloatArray]:
        weights = self.posterior.filter.weights
        predicted_target = np.einsum(
            "h,hi->i", weights, self.posterior.filter.states[:, :2]
        )
        secondary_active = (
            step >= self.posterior.filter.secondary_start_step
            and (
                self.posterior.filter.secondary_end_step < 0
                or step < self.posterior.filter.secondary_end_step
            )
        )
        offset = (
            self.posterior.filter.secondary_offset
            if secondary_active
            else np.zeros(2, dtype=float)
        )
        reference_members = np.flatnonzero(belief_visible)
        if len(reference_members) < 2:
            reference_members = np.flatnonzero(measurement_visible)
        corrected: list[FloatArray] = []
        for agent in reference_members:
            observation = observations[int(agent)]
            primary = observation
            secondary = observation - offset
            corrected.append(
                secondary
                if np.linalg.norm(secondary - predicted_target)
                < np.linalg.norm(primary - predicted_target)
                else primary
            )
        reference = (
            np.median(np.asarray(corrected), axis=0)
            if corrected
            else predicted_target
        )

        residuals = np.zeros_like(observations)
        raw_nis = np.zeros(self.config.n_agents, dtype=float)
        for agent in np.flatnonzero(measurement_visible):
            index = int(agent)
            primary_residual = observations[index] - reference
            secondary_residual = observations[index] - (reference + offset)
            inverse = np.linalg.inv(sanitized_covariances[index])
            primary_nis = float(primary_residual @ inverse @ primary_residual)
            secondary_nis = float(secondary_residual @ inverse @ secondary_residual)
            residuals[index] = (
                secondary_residual
                if secondary_nis < primary_nis
                else primary_residual
            )
        visible_residuals = residuals[measurement_visible]
        common = (
            np.median(visible_residuals, axis=0)
            if len(visible_residuals)
            else np.zeros(2, dtype=float)
        )
        residuals[measurement_visible] -= common
        for agent in np.flatnonzero(measurement_visible):
            index = int(agent)
            inverse = np.linalg.inv(sanitized_covariances[index])
            raw_nis[index] = float(
                residuals[index] @ inverse @ residuals[index]
            )
        return reference, residuals, raw_nis, offset

    def update(
        self,
        step: int,
        observations: FloatArray,
        measurement_covariances: tuple[FloatArray, ...],
        *,
        component_visible: BoolArray,
        available: BoolArray,
        operational: BoolArray,
        raw_trusted: BoolArray,
        source_quarantined: BoolArray,
        belief_share_eligible: BoolArray,
        belief_admitted: BoolArray,
        force_defer: bool = False,
    ) -> AdversarialTrustDecision:
        for name, mask in (
            ("component_visible", component_visible),
            ("available", available),
            ("operational", operational),
            ("raw_trusted", raw_trusted),
            ("source_quarantined", source_quarantined),
            ("belief_share_eligible", belief_share_eligible),
            ("belief_admitted", belief_admitted),
        ):
            if mask.shape != (self.config.n_agents,):
                raise ValueError(f"{name} has the wrong shape")
        if self._baseline is not None:
            return self._baseline_decision(
                step,
                observations,
                measurement_covariances,
                component_visible=component_visible,
                available=available,
                operational=operational,
                raw_trusted=raw_trusted,
                source_quarantined=source_quarantined,
                belief_share_eligible=belief_share_eligible,
                belief_admitted=belief_admitted,
                force_defer=force_defer,
            )

        fresh_reachable = component_visible & available & operational
        measurement_visible = fresh_reachable & raw_trusted
        belief_visible = fresh_reachable & belief_admitted
        belief_censored = measurement_visible & ~belief_visible
        robust_excluded = fresh_reachable & ~raw_trusted
        unreachable = available & operational & ~component_visible

        quarantine_missing = (
            fresh_reachable
            & source_quarantined
            & ~raw_trusted
            & ~belief_share_eligible
        )
        excluded_secondary_probability = _secondary_probability(
            self.posterior, quarantine_missing
        )
        unreachable_secondary_probability = _secondary_probability(
            self.posterior, unreachable
        )
        target_admission_mass = (
            self.config.m9a7_excluded_secondary_mass_scale
            * excluded_secondary_probability
        )
        admission_alpha = self.config.m9a7_admission_residual_ema_alpha
        self._admission_residual_mass = (
            (1.0 - admission_alpha) * self._admission_residual_mass
            + admission_alpha * target_admission_mass
        )

        sanitized, floored_count, covariance_floor = floor_reported_covariances(
            self.config,
            measurement_covariances,
            fresh_reachable,
        )
        reference_eigenvalues = np.asarray(
            [
                float(np.min(np.linalg.eigvalsh(measurement_covariances[index])))
                for index in np.flatnonzero(fresh_reachable)
            ],
            dtype=float,
        )
        median_eigenvalue = (
            float(np.median(reference_eigenvalues))
            if len(reference_eigenvalues)
            else 0.0
        )
        strong_floor = np.zeros(self.config.n_agents, dtype=bool)
        if median_eigenvalue > 0.0:
            for agent in np.flatnonzero(fresh_reachable):
                index = int(agent)
                reported = float(
                    np.min(np.linalg.eigvalsh(measurement_covariances[index]))
                )
                strong_floor[index] = (
                    reported
                    < self.trust_config.strong_floor_ratio * median_eigenvalue
                )

        _, residuals, cross_nis, _ = self._assignment_corrected_reference(
            step,
            observations,
            sanitized,
            measurement_visible,
            belief_visible,
        )
        cross_signal = _linear_signal(
            cross_nis,
            self.trust_config.cross_nis_start,
            self.trust_config.cross_nis_full,
        )
        cross_signal[strong_floor] = 1.0

        previous_offset = self._offset_ema.copy()
        alpha = self.trust_config.offset_ema_alpha
        self._offset_ema[measurement_visible] = (
            (1.0 - alpha) * self._offset_ema[measurement_visible]
            + alpha * residuals[measurement_visible]
        )
        ramp_rate = np.linalg.norm(
            self._offset_ema - previous_offset, axis=1
        ) / self.config.dt
        ramp_signal = _linear_signal(
            ramp_rate,
            self.trust_config.ramp_rate_start,
            self.trust_config.ramp_rate_full,
        )
        ramp_signal[cross_nis <= self.trust_config.cross_nis_full] = 0.0
        ramp_signal[~self._offset_seen] = 0.0
        self._offset_seen |= measurement_visible

        signal = np.zeros(self.config.n_agents, dtype=float)
        if self.defense_mode in {"cross_channel", "combined"}:
            signal = np.maximum(signal, cross_signal)
        if self.defense_mode in {"ramp_rate", "combined"}:
            signal = np.maximum(signal, ramp_signal)
        targets = 1.0 - signal
        for index in range(self.config.n_agents):
            if not measurement_visible[index]:
                targets[index] = 1.0
            update_alpha = (
                self.trust_config.trust_attack_alpha
                if targets[index] < self._trust[index]
                else self.trust_config.trust_recovery_alpha
            )
            self._trust[index] = (
                (1.0 - update_alpha) * self._trust[index]
                + update_alpha * targets[index]
            )
        self._trust = np.clip(
            self._trust, self.trust_config.minimum_trust, 1.0
        )

        defended = [value.copy() for value in sanitized]
        if self.defense_mode in {"cross_channel", "ramp_rate", "combined"}:
            for agent in np.flatnonzero(measurement_visible):
                index = int(agent)
                if self._trust[index] < self.trust_config.trust_alert_threshold:
                    defended[index] /= max(
                        self._trust[index] ** 2,
                        self.trust_config.minimum_trust**2,
                    )

        raw_only = measurement_visible & ~belief_visible
        diagnostic_suspicion = (
            strong_floor
            | (cross_nis > self.trust_config.cross_nis_start)
            | (ramp_rate > self.trust_config.ramp_rate_start)
        )
        budget_sources = raw_only & diagnostic_suspicion
        if self.defense_mode == "combined":
            budget_sources = raw_only & (
                self._trust < self.trust_config.trust_alert_threshold
            )
        influence_capped = np.zeros(self.config.n_agents, dtype=bool)
        raw_fraction = 0.0
        if self.defense_mode in {"influence_budget", "combined"}:
            raw_precision = float(
                sum(
                    _precision(defended[int(index)])
                    for index in np.flatnonzero(budget_sources)
                )
            )
            admitted_precision = float(
                sum(
                    _precision(defended[int(index)])
                    for index in np.flatnonzero(belief_visible)
                )
            )
            total_precision = raw_precision + admitted_precision
            raw_fraction = raw_precision / total_precision if total_precision > 0.0 else 0.0
            cap = self.trust_config.raw_only_precision_fraction * admitted_precision
            if raw_precision > cap > 0.0:
                scale = raw_precision / cap
                for agent in np.flatnonzero(budget_sources):
                    defended[int(agent)] *= scale
                    influence_capped[int(agent)] = True
                raw_precision = float(
                    sum(
                        _precision(defended[int(index)])
                        for index in np.flatnonzero(budget_sources)
                    )
                )
                total_precision = raw_precision + admitted_precision
                raw_fraction = (
                    raw_precision / total_precision if total_precision > 0.0 else 0.0
                )

        trust_target = 0.0
        if self.defense_mode in {"cross_channel", "ramp_rate", "combined"}:
            alert_deficit = np.clip(
                (
                    self.trust_config.trust_alert_threshold
                    - self._trust
                )
                / self.trust_config.trust_alert_threshold,
                0.0,
                1.0,
            )
            trust_target = self.trust_config.trust_residual_cap * float(
                np.max(alert_deficit[measurement_visible], initial=0.0)
            )
        residual_alpha = self.trust_config.trust_residual_alpha
        self._trust_residual_mass = (
            (1.0 - residual_alpha) * self._trust_residual_mass
            + residual_alpha * trust_target
        )
        external_residual = 1.0 - (
            (1.0 - self._admission_residual_mass)
            * (1.0 - self._trust_residual_mass)
        )
        posterior = self.posterior.update(
            step,
            observations,
            tuple(defended),
            measurement_visible,
            force_defer=force_defer,
            external_residual_mass=external_residual,
            measurement_nis_ceiling=self.config.m9a7_raw_measurement_nis_ceiling,
        )
        visible_trust = self._trust[measurement_visible]
        return AdversarialTrustDecision(
            posterior=posterior,
            measurement_eligible_agents=int(np.sum(measurement_visible)),
            belief_admitted_agents=int(np.sum(belief_visible)),
            belief_censored_measurement_agents=int(np.sum(belief_censored)),
            robust_excluded_measurement_agents=int(np.sum(robust_excluded)),
            unreachable_measurement_agents=int(np.sum(unreachable)),
            covariance_floored_agents=floored_count,
            model_rejected_measurement_agents=int(
                np.sum(self.posterior.filter.last_rejected_agents)
            ),
            admission_residual_mass=float(self._admission_residual_mass),
            excluded_secondary_probability=excluded_secondary_probability,
            unreachable_secondary_probability=unreachable_secondary_probability,
            cross_channel_disagreement_agents=int(
                np.sum(
                    measurement_visible
                    & (cross_nis > self.trust_config.cross_nis_start)
                )
            ),
            strong_floor_evidence_agents=int(np.sum(strong_floor)),
            ramp_alert_agents=int(
                np.sum(
                    measurement_visible
                    & (ramp_rate > self.trust_config.ramp_rate_start)
                )
            ),
            influence_capped_agents=int(np.sum(influence_capped)),
            trust_alert_agents=int(
                np.sum(
                    measurement_visible
                    & (self._trust < self.trust_config.trust_alert_threshold)
                )
            ),
            mean_raw_trust=(
                float(np.mean(visible_trust)) if len(visible_trust) else 1.0
            ),
            minimum_raw_trust=(
                float(np.min(visible_trust)) if len(visible_trust) else 1.0
            ),
            raw_only_precision_fraction=raw_fraction,
            trust_residual_mass=float(self._trust_residual_mass),
            trust_scores=self._trust.copy(),
        )
