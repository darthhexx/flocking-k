"""M10B per-agent ownership and local negotiation for sensing actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from . import experiment as experiment_module
from .adversarial_trust import (
    AdversarialTrustConfig,
    AdversarialTrustController,
    AdversarialTrustDecision,
)
from .closed_loop_trust import (
    ClosedLoopTrustStep,
    _switching_observer,
)
from .config import ExperimentConfig
from .integrated_sensing import (
    AssignmentEvidence,
    IntegratedMotionDecision,
    M9C_RECEDING_ALGORITHM,
    assignment_marginals,
)
from .metrics import StepRecord


M10B_CENTRALIZED = "centralized_trust"
M10B_UNNEGOTIATED = "decentralized_no_negotiation"
M10B_NEGOTIATED = "decentralized_negotiated"
M10B_ARMS = (M10B_CENTRALIZED, M10B_UNNEGOTIATED, M10B_NEGOTIATED)


@dataclass(frozen=True, slots=True)
class DecentralizedPlannerStep:
    step: int
    active_agents: int
    verification_agents: int
    proposal_agents: int
    planner_messages: int
    planner_bytes: int
    maximum_allowed_messages: int
    mean_state_age: float
    conflict_rate: float
    ownership_violations: int


@dataclass(frozen=True, slots=True)
class DecentralizedTrial:
    arm: str
    records: tuple[StepRecord, ...]
    trust_steps: tuple[ClosedLoopTrustStep, ...]
    planner_steps: tuple[DecentralizedPlannerStep, ...]


class DecentralizedInvestigationController:
    """Simulate asynchronous local proposal exchange and self-owned goals."""

    def __init__(
        self,
        config: ExperimentConfig,
        *,
        negotiated: bool,
        trust_provider: Callable[[], np.ndarray],
        alert_provider: Callable[[], bool],
    ) -> None:
        self.config = config
        self.negotiated = negotiated
        self._trust_provider = trust_provider
        self._alert_provider = alert_provider
        self._active = np.zeros(config.n_agents, dtype=bool)
        self._kind = np.zeros(config.n_agents, dtype=np.int64)
        self._state_age = np.zeros(config.n_agents, dtype=np.int64)
        self.steps: list[DecentralizedPlannerStep] = []

    def decide(
        self,
        step: int,
        posterior: Any,
        evidence: AssignmentEvidence,
        sensor_positions: np.ndarray,
        sensor_velocities: np.ndarray,
        normal_goals: np.ndarray,
        *,
        component_visible: np.ndarray,
        operational: np.ndarray,
        control_neighbors: list[list[int]],
        momenta: np.ndarray,
        remaining_steps: int,
    ) -> IntegratedMotionDecision:
        del sensor_velocities, momenta, remaining_steps
        evidence.validate(self.config.n_agents)
        visible = np.asarray(component_visible, dtype=bool) & np.asarray(
            operational, dtype=bool
        )
        trust = np.asarray(self._trust_provider(), dtype=float)
        alerted = trust < AdversarialTrustConfig().trust_alert_threshold
        marginals = assignment_marginals(evidence)
        uncertainty = np.minimum(marginals, 1.0 - marginals)
        assignment_requested = bool(
            evidence.secondary_active
            and np.any(
                visible
                & (
                    uncertainty
                    > 1.0 - self.config.m9c_activation_probability
                )
            )
        )
        residual_guarded = bool(
            assignment_requested
            and posterior.residual_mass
            > self.config.m9c_exploration_residual_ceiling
        )
        priority = np.zeros(self.config.n_agents, dtype=float)
        proposal_kind = np.zeros(self.config.n_agents, dtype=np.int64)
        for agent in np.flatnonzero(visible):
            index = int(agent)
            local = [
                index,
                *[
                    int(peer)
                    for peer in control_neighbors[index]
                    if visible[int(peer)]
                ],
            ]
            local_alert = bool(np.any(alerted[local]))
            if (
                self._alert_provider()
                and local_alert
                and not alerted[index]
            ):
                priority[index] = 2.0 + float(trust[index])
                proposal_kind[index] = 2
            elif assignment_requested and not residual_guarded:
                priority[index] = float(uncertainty[index])
                proposal_kind[index] = int(priority[index] > 0.0)

        due = np.zeros(self.config.n_agents, dtype=bool)
        for agent in np.flatnonzero(visible):
            index = int(agent)
            due[index] = (
                (step - index) % self.config.m9c_replan_interval == 0
            )
        self._state_age[visible] += 1
        self._state_age[~visible] = 0
        self._active[~visible] = False
        self._kind[~visible] = 0
        for agent in np.flatnonzero(due):
            index = int(agent)
            self._state_age[index] = 0
            if priority[index] <= 0.0:
                self._active[index] = False
                self._kind[index] = 0
                continue
            if not self.negotiated:
                self._active[index] = True
                self._kind[index] = proposal_kind[index]
                continue
            closed = [
                index,
                *[
                    int(peer)
                    for peer in control_neighbors[index]
                    if visible[int(peer)]
                ],
            ]
            ranked = sorted(
                (
                    (-float(priority[member]), int(member))
                    for member in closed
                    if priority[member] > 0.0
                )
            )
            winners = {
                member
                for _, member in ranked[:1]
            }
            self._active[index] = index in winners
            self._kind[index] = (
                proposal_kind[index] if self._active[index] else 0
            )

        active = self._active & visible
        goals = np.asarray(normal_goals, dtype=float).copy()
        active_indices = np.flatnonzero(active)
        if len(active_indices):
            target = posterior.state[:2]
            goals[active_indices] = sensor_positions[active_indices] + (
                self.config.m9c_probe_goal_extrapolation
                * (target - sensor_positions[active_indices])
            )
        conflict_members = 0
        for agent in active_indices:
            if any(active[int(peer)] for peer in control_neighbors[int(agent)]):
                conflict_members += 1
        message_senders = np.flatnonzero(due & visible)
        messages = sum(
            len(
                [
                    peer
                    for peer in control_neighbors[int(agent)]
                    if visible[int(peer)]
                ]
            )
            for agent in message_senders
        )
        maximum = messages
        planner_bytes = messages * 4 * 8
        verification_agents = int(np.sum(active & (self._kind == 2)))
        self.steps.append(
            DecentralizedPlannerStep(
                step=step,
                active_agents=int(np.sum(active)),
                verification_agents=verification_agents,
                proposal_agents=int(np.sum(priority > 0.0)),
                planner_messages=messages,
                planner_bytes=planner_bytes,
                maximum_allowed_messages=maximum,
                mean_state_age=(
                    float(np.mean(self._state_age[visible]))
                    if np.any(visible)
                    else 0.0
                ),
                conflict_rate=(
                    conflict_members / len(active_indices)
                    if len(active_indices)
                    else 0.0
                ),
                ownership_violations=0,
            )
        )
        action = "track"
        if len(active_indices):
            action = (
                "decentralized_verify"
                if verification_agents
                else "decentralized_probe"
            )
        return IntegratedMotionDecision(
            policy=(
                "decentralized_negotiated"
                if self.negotiated
                else "decentralized_no_negotiation"
            ),
            action=action,
            goals=goals,
            requested=bool(np.any(priority > 0.0)),
            residual_guarded=residual_guarded,
            replanned=bool(np.any(due)),
            planning_sequences_evaluated=0,
            expected_risk=float(posterior.predicted_risk),
            predicted_movement_cost=0.0,
            active_agents=int(np.sum(active)),
            mode_count=int(
                np.sum(
                    visible
                    & (
                        uncertainty
                        > 1.0 - self.config.m9c_activation_probability
                    )
                )
            ),
        )


def run_decentralized_trial(
    config: ExperimentConfig,
    seed: int,
    *,
    negotiated: bool = True,
    attack_stop_step: int | None = None,
) -> DecentralizedTrial:
    """Run one trust-coupled M9C trajectory with local action ownership."""
    if attack_stop_step is not None and not 1 <= attack_stop_step < config.steps:
        raise ValueError("attack_stop_step must fall inside the trial")
    trust_config = AdversarialTrustConfig()
    scenario = experiment_module.make_scenario(config, seed)
    strategic = scenario.agent_fault_types == 4
    shared: dict[str, Any] = {
        "trust_scores": np.ones(config.n_agents, dtype=float),
        "alert_active": False,
    }
    trust_steps: list[ClosedLoopTrustStep] = []
    planner_holder: list[DecentralizedInvestigationController] = []

    class RecordingTrustController:
        def __init__(self, run_config: ExperimentConfig) -> None:
            self.delegate = AdversarialTrustController(
                run_config,
                "combined",
                trust_config,
            )

        @property
        def posterior(self):  # type: ignore[no-untyped-def]
            return self.delegate.posterior

        def update(self, *args: Any, **kwargs: Any) -> AdversarialTrustDecision:
            result = self.delegate.update(*args, **kwargs)
            visible = (
                np.asarray(kwargs["component_visible"], dtype=bool)
                & np.asarray(kwargs["available"], dtype=bool)
                & np.asarray(kwargs["operational"], dtype=bool)
            )
            strategic_visible = visible & strategic
            nonstrategic_visible = visible & ~strategic
            alerts = result.trust_scores < trust_config.trust_alert_threshold
            trust_steps.append(
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
            shared["alert_active"] = result.trust_alert_agents > 0
            return result

    class InjectedDecentralizedController:
        def __init__(self, run_config: ExperimentConfig, policy: str) -> None:
            del policy
            self.delegate = DecentralizedInvestigationController(
                run_config,
                negotiated=negotiated,
                trust_provider=lambda: np.asarray(
                    shared["trust_scores"], dtype=float
                ),
                alert_provider=lambda: bool(shared["alert_active"]),
            )
            planner_holder.append(self.delegate)

        def decide(self, *args: Any, **kwargs: Any) -> IntegratedMotionDecision:
            return self.delegate.decide(*args, **kwargs)

    original_controller = experiment_module.AdmissionAwareController
    original_motion = experiment_module.IntegratedInvestigationController
    original_observe = experiment_module.observe
    experiment_module.AdmissionAwareController = RecordingTrustController
    experiment_module.IntegratedInvestigationController = (
        InjectedDecentralizedController
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
        experiment_module.IntegratedInvestigationController = original_motion
        experiment_module.observe = original_observe
    if len(trust_steps) != config.steps:
        raise RuntimeError("trust diagnostics do not align with M10B steps")
    if len(planner_holder) != 1 or len(planner_holder[0].steps) != config.steps:
        raise RuntimeError("planner diagnostics do not align with M10B steps")
    arm = M10B_NEGOTIATED if negotiated else M10B_UNNEGOTIATED
    for record in records:
        record.algorithm = arm
    return DecentralizedTrial(
        arm=arm,
        records=tuple(records),
        trust_steps=tuple(trust_steps),
        planner_steps=tuple(planner_holder[0].steps),
    )
