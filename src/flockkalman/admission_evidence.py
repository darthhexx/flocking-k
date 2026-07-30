"""M9A.7 split-trust measurement admission and missingness accounting.

Belief sharing and fresh measurements have deliberately different trust
boundaries.  A rejoining agent's recursively fused belief remains subject to
lifecycle probation, while its current sensor sample may enter the assignment
posterior if the source is operational, reachable, and passes the source-local
robust screen.  Reported covariance is floored against the contemporaneous
team median before that bypass is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import ExperimentConfig
from .missing_evidence import MissingEvidenceController, MissingEvidenceDecision
from .oracle_floor import BoolArray, FloatArray


M9A7_ALGORITHM = "flocking_topology_admission_posterior"


@dataclass(frozen=True, slots=True)
class AdmissionEvidenceDecision:
    """Posterior decision plus auditable evidence-channel diagnostics."""

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


def _secondary_probability(
    controller: MissingEvidenceController,
    agents: BoolArray,
) -> float:
    """Exact posterior probability that at least one selected source is secondary."""
    if not np.any(agents):
        return 0.0
    assignments = controller.filter.assignment_mask[:, agents]
    contains_secondary = np.any(assignments, axis=1)
    return float(np.sum(controller.filter.weights[contains_secondary]))


def floor_reported_covariances(
    config: ExperimentConfig,
    covariances: tuple[FloatArray, ...],
    reference_agents: BoolArray,
) -> tuple[tuple[FloatArray, ...], int, float]:
    """Clamp reported 2-D covariance eigenvalues to a robust live-team floor."""
    reference_eigenvalues = [
        float(np.min(np.linalg.eigvalsh(covariances[index])))
        for index in np.flatnonzero(reference_agents)
    ]
    if not reference_eigenvalues:
        return tuple(value.copy() for value in covariances), 0, 0.0
    floor = config.m9a7_covariance_floor_fraction * float(
        np.median(reference_eigenvalues)
    )
    sanitized: list[FloatArray] = []
    changed = 0
    for index, covariance in enumerate(covariances):
        symmetric = 0.5 * (covariance + covariance.T)
        eigenvalues, eigenvectors = np.linalg.eigh(symmetric)
        clipped = np.maximum(eigenvalues, floor)
        changed += int(
            reference_agents[index]
            and np.any(clipped > eigenvalues + 1e-12)
        )
        repaired = (eigenvectors * clipped) @ eigenvectors.T
        sanitized.append(0.5 * (repaired + repaired.T))
    return tuple(sanitized), changed, floor


class AdmissionAwareController:
    """Run M9A.6 over fresh raw evidence with explicit censoring uncertainty."""

    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        self.posterior = MissingEvidenceController(config)
        self._admission_residual_mass = 0.0

    @property
    def admission_residual_mass(self) -> float:
        return self._admission_residual_mass

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
    ) -> AdmissionEvidenceDecision:
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

        fresh_reachable = component_visible & available & operational
        measurement_visible = fresh_reachable & raw_trusted
        belief_visible = fresh_reachable & belief_admitted
        belief_censored = measurement_visible & ~belief_visible
        robust_excluded = fresh_reachable & ~raw_trusted
        unreachable = available & operational & ~component_visible

        # Use the prior assignment distribution so missingness pricing cannot
        # inspect a measurement that the source-local trust screen rejected.
        # Only the intersection is admission-censored missing evidence: a
        # current raw sample that cannot pass source-local trust *and* whose
        # sender's belief is still in lifecycle probation.  A quarantine after
        # normal admission belongs to the already-validated M6 source screen,
        # not to the M9A.7 missingness repair.
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
        target_mass = (
            self.config.m9a7_excluded_secondary_mass_scale
            * excluded_secondary_probability
        )
        alpha = self.config.m9a7_admission_residual_ema_alpha
        self._admission_residual_mass = (
            (1.0 - alpha) * self._admission_residual_mass + alpha * target_mass
        )

        sanitized, floored, _ = floor_reported_covariances(
            self.config,
            measurement_covariances,
            fresh_reachable,
        )
        posterior = self.posterior.update(
            step,
            observations,
            sanitized,
            measurement_visible,
            force_defer=force_defer,
            external_residual_mass=self._admission_residual_mass,
            measurement_nis_ceiling=self.config.m9a7_raw_measurement_nis_ceiling,
        )
        return AdmissionEvidenceDecision(
            posterior=posterior,
            measurement_eligible_agents=int(np.sum(measurement_visible)),
            belief_admitted_agents=int(np.sum(belief_visible)),
            belief_censored_measurement_agents=int(np.sum(belief_censored)),
            robust_excluded_measurement_agents=int(np.sum(robust_excluded)),
            unreachable_measurement_agents=int(np.sum(unreachable)),
            covariance_floored_agents=floored,
            model_rejected_measurement_agents=int(
                np.sum(self.posterior.filter.last_rejected_agents)
            ),
            admission_residual_mass=float(self._admission_residual_mass),
            excluded_secondary_probability=excluded_secondary_probability,
            unreachable_secondary_probability=unreachable_secondary_probability,
        )
