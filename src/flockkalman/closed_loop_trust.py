"""M10A.5 closed-loop integration of frozen M10A trust with frozen M9C.

The historical M9C engine is intentionally not edited.  A per-trial dependency
injection replaces its admission controller with the API-compatible M10A
controller, then restores the original dependency in ``finally``.  The
trust-adjusted assignment posterior is therefore consumed by the unchanged
M9C planner and changes subsequent geometry and observations.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Any

import numpy as np

from . import experiment as experiment_module
from .adversarial_trust import (
    AdversarialTrustConfig,
    AdversarialTrustController,
    AdversarialTrustDecision,
)
from .config import ExperimentConfig
from .integrated_sensing import (
    M9C_RECEDING_ALGORITHM,
    IntegratedInvestigationController,
    IntegratedMotionDecision,
)
from .metrics import StepRecord
from .provenance import FINGERPRINT_V1
from .simulation import scenario_fingerprint


M10A5_BASELINE = "m9c_receding"
M10A5_CANDIDATE = "closed_loop_trust"
M10A5_ARMS = (M10A5_BASELINE, M10A5_CANDIDATE)


@dataclass(frozen=True, slots=True)
class ClosedLoopTrustStep:
    """Causal trust diagnostics captured while the M9C loop is running."""

    step: int
    strategic_visible: int
    strategic_alerted: int
    nonstrategic_visible: int
    nonstrategic_alerted: int
    strategic_mean_trust: float
    mean_raw_trust: float
    minimum_raw_trust: float
    trust_alert_agents: int
    cross_channel_disagreement_agents: int
    ramp_alert_agents: int
    influence_capped_agents: int
    trust_residual_mass: float


@dataclass(frozen=True, slots=True)
class ClosedLoopTrustTrial:
    """One closed-loop trajectory plus its source-trust diagnostics."""

    arm: str
    records: tuple[StepRecord, ...]
    trust_steps: tuple[ClosedLoopTrustStep, ...]


def closed_loop_fingerprint(
    config: ExperimentConfig,
    seed: int,
    attack_stop_step: int | None,
    *,
    algorithm: str = FINGERPRINT_V1,
) -> str:
    """Fingerprint the exogenous trace and the optional attack-cessation rule.

    The algorithm default matches :func:`~.simulation.scenario_fingerprint`: v1,
    so historical M10A.5 artifacts keep verifying bit-exactly.
    """
    digest = hashlib.sha256()
    digest.update(
        scenario_fingerprint(config, seed, algorithm=algorithm).encode("ascii")
    )
    digest.update(
        ("none" if attack_stop_step is None else str(attack_stop_step)).encode(
            "ascii"
        )
    )
    return digest.hexdigest()


def _switching_observer(
    original_observe: Any,
    attack_stop_step: int | None,
) -> Any:
    if attack_stop_step is None:
        return original_observe

    def observe_with_recovery(
        config: ExperimentConfig,
        step: int,
        target_position: np.ndarray,
        sensor_positions: np.ndarray,
        standard_normals: np.ndarray,
        availability_uniforms: np.ndarray,
        agent_fault_types: np.ndarray,
        sensor_noise_scales: np.ndarray | None = None,
        agent_active: np.ndarray | None = None,
    ) -> tuple[np.ndarray, list[np.ndarray], np.ndarray]:
        effective_faults = np.asarray(agent_fault_types, dtype=np.int64).copy()
        if step >= attack_stop_step:
            effective_faults[effective_faults == 4] = 0
        return original_observe(
            config,
            step,
            target_position,
            sensor_positions,
            standard_normals,
            availability_uniforms,
            effective_faults,
            sensor_noise_scales,
            agent_active,
        )

    return observe_with_recovery


def run_closed_loop_trust_trial(
    config: ExperimentConfig,
    seed: int,
    *,
    defense_mode: str = "combined",
    trust_config: AdversarialTrustConfig | None = None,
    attack_stop_step: int | None = None,
) -> ClosedLoopTrustTrial:
    """Run one dependency-isolated M9C trajectory with causal trust feedback."""
    if defense_mode not in {"none", "combined"}:
        raise ValueError("closed-loop integration supports none or combined")
    if attack_stop_step is not None and not 1 <= attack_stop_step < config.steps:
        raise ValueError("attack_stop_step must fall inside the trial")
    frozen_trust = trust_config or AdversarialTrustConfig()
    frozen_trust.validate()
    scenario = experiment_module.make_scenario(config, seed)
    strategic = scenario.agent_fault_types == 4
    diagnostics: list[ClosedLoopTrustStep] = []
    shared: dict[str, Any] = {
        "trust_scores": np.ones(config.n_agents, dtype=float),
        "alert_active": False,
    }

    class RecordingTrustController:
        def __init__(self, run_config: ExperimentConfig) -> None:
            self.delegate = AdversarialTrustController(
                run_config,
                defense_mode,
                frozen_trust,
            )

        @property
        def posterior(self):  # type: ignore[no-untyped-def]
            return self.delegate.posterior

        def update(self, *args: Any, **kwargs: Any) -> AdversarialTrustDecision:
            result = self.delegate.update(*args, **kwargs)
            component = np.asarray(kwargs["component_visible"], dtype=bool)
            available = np.asarray(kwargs["available"], dtype=bool)
            operational = np.asarray(kwargs["operational"], dtype=bool)
            visible = component & available & operational
            strategic_visible = visible & strategic
            nonstrategic_visible = visible & ~strategic
            alerts = (
                result.trust_scores
                < self.delegate.trust_config.trust_alert_threshold
            )
            diagnostics.append(
                ClosedLoopTrustStep(
                    step=int(args[0]),
                    strategic_visible=int(np.sum(strategic_visible)),
                    strategic_alerted=int(np.sum(strategic_visible & alerts)),
                    nonstrategic_visible=int(np.sum(nonstrategic_visible)),
                    nonstrategic_alerted=int(np.sum(nonstrategic_visible & alerts)),
                    strategic_mean_trust=(
                        float(np.mean(result.trust_scores[strategic]))
                        if np.any(strategic)
                        else 1.0
                    ),
                    mean_raw_trust=result.mean_raw_trust,
                    minimum_raw_trust=result.minimum_raw_trust,
                    trust_alert_agents=result.trust_alert_agents,
                    cross_channel_disagreement_agents=(
                        result.cross_channel_disagreement_agents
                    ),
                    ramp_alert_agents=result.ramp_alert_agents,
                    influence_capped_agents=result.influence_capped_agents,
                    trust_residual_mass=result.trust_residual_mass,
                )
            )
            shared["trust_scores"] = result.trust_scores.copy()
            shared["alert_active"] = bool(
                result.trust_alert_agents > 0
            )
            return result

    class RecordingIntegratedController:
        def __init__(self, run_config: ExperimentConfig, policy: str) -> None:
            self.config = run_config
            self.delegate = IntegratedInvestigationController(run_config, policy)

        def decide(self, *args: Any, **kwargs: Any) -> IntegratedMotionDecision:
            decision = self.delegate.decide(*args, **kwargs)
            step = int(args[0])
            if (
                defense_mode == "none"
                or not bool(shared["alert_active"])
                or step % self.config.m9c_replan_interval != 0
            ):
                return decision
            posterior = args[1]
            sensor_positions = np.asarray(args[3], dtype=float)
            component_visible = np.asarray(
                kwargs["component_visible"],
                dtype=bool,
            )
            operational = np.asarray(kwargs["operational"], dtype=bool)
            trust_scores = np.asarray(shared["trust_scores"], dtype=float)
            eligible = np.flatnonzero(
                component_visible
                & operational
                & (
                    trust_scores
                    >= frozen_trust.trust_alert_threshold
                )
            )
            ranked = sorted(
                (int(index) for index in eligible),
                key=lambda index: (-float(trust_scores[index]), index),
            )
            selected = ranked[: self.config.m9c_probe_agent_count]
            if not selected:
                return decision
            goals = decision.goals.copy()
            target = posterior.state[:2]
            goals[selected] = sensor_positions[selected] + (
                self.config.m9c_probe_goal_extrapolation
                * (target - sensor_positions[selected])
            )
            return IntegratedMotionDecision(
                policy=decision.policy,
                action="trust_verify",
                goals=goals,
                requested=True,
                residual_guarded=decision.residual_guarded,
                replanned=True,
                planning_sequences_evaluated=(
                    decision.planning_sequences_evaluated
                ),
                expected_risk=decision.expected_risk,
                predicted_movement_cost=decision.predicted_movement_cost,
                active_agents=len(selected),
                mode_count=decision.mode_count,
            )

    original_controller = experiment_module.AdmissionAwareController
    original_motion_controller = experiment_module.IntegratedInvestigationController
    original_observe = experiment_module.observe
    experiment_module.AdmissionAwareController = RecordingTrustController
    experiment_module.IntegratedInvestigationController = (
        RecordingIntegratedController
    )
    experiment_module.observe = _switching_observer(
        original_observe,
        attack_stop_step,
    )
    try:
        records = experiment_module.run_trial(
            config,
            M9C_RECEDING_ALGORITHM,
            seed,
        )
    finally:
        experiment_module.AdmissionAwareController = original_controller
        experiment_module.IntegratedInvestigationController = (
            original_motion_controller
        )
        experiment_module.observe = original_observe

    if len(diagnostics) != config.steps:
        raise RuntimeError("closed-loop trust diagnostics do not align with steps")
    arm = M10A5_BASELINE if defense_mode == "none" else M10A5_CANDIDATE
    for record in records:
        record.algorithm = arm
    return ClosedLoopTrustTrial(
        arm=arm,
        records=tuple(records),
        trust_steps=tuple(diagnostics),
    )
