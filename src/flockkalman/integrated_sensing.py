"""M9C topology-aware integration of M9A.7 evidence with M9B-style VOI motion.

M9A.7 usually collapses compatible assignment hypotheses to one external target
mode.  The useful active-sensing uncertainty therefore lives one layer below
that output: which reachable sources are producing the declared secondary
offset.  This module allocates closer views to those source identities while
leaving the validated M9A.7 output rule unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
import math

import numpy as np
from numpy.typing import NDArray

from .config import ExperimentConfig
from .missing_evidence import MissingEvidenceDecision
from .policies import advance_sensors, flocking_velocity
from .simulation import measurement_covariance


FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]

M9C_ROUND_ROBIN_ALGORITHM = "flocking_topology_admission_round_robin"
M9C_RECEDING_ALGORITHM = "flocking_topology_admission_receding_voi"
M9C_ALGORITHMS = (M9C_ROUND_ROBIN_ALGORITHM, M9C_RECEDING_ALGORITHM)


@dataclass(frozen=True, slots=True)
class AssignmentEvidence:
    """Causal assignment posterior exposed by the M9A.7 filter."""

    weights: FloatArray
    assignment_mask: BoolArray
    secondary_offset: FloatArray
    secondary_active: bool
    secondary_steps_remaining: int

    def validate(self, n_agents: int) -> None:
        if self.assignment_mask.ndim != 2 or self.assignment_mask.shape[1] != n_agents:
            raise ValueError("assignment_mask has the wrong shape")
        if self.weights.shape != (len(self.assignment_mask),):
            raise ValueError("assignment weights do not align with the mask")
        if self.secondary_offset.shape != (2,):
            raise ValueError("secondary_offset must be two-dimensional")
        if self.secondary_steps_remaining < 0:
            raise ValueError("secondary_steps_remaining cannot be negative")


@dataclass(frozen=True, slots=True)
class IntegratedMotionDecision:
    """One auditable component-local investigation action."""

    policy: str
    action: str
    goals: FloatArray
    requested: bool
    residual_guarded: bool
    replanned: bool
    planning_sequences_evaluated: int
    expected_risk: float
    predicted_movement_cost: float
    active_agents: int
    mode_count: int


def _normalize(values: FloatArray) -> FloatArray:
    total = float(np.sum(values))
    if total <= 0.0:
        return np.full(len(values), 1.0 / max(len(values), 1), dtype=float)
    return values / total


def assignment_marginals(evidence: AssignmentEvidence) -> FloatArray:
    """Return P(source is secondary) under the exact joint posterior."""
    weights = _normalize(np.asarray(evidence.weights, dtype=float))
    return np.einsum("h,ha->a", weights, evidence.assignment_mask.astype(float))


def _binary_entropy(probabilities: FloatArray) -> FloatArray:
    values = np.clip(probabilities, 1e-15, 1.0 - 1e-15)
    return -(values * np.log(values) + (1.0 - values) * np.log(1.0 - values))


def _expected_binary_error(
    probability_secondary: float,
    discriminability: float,
    quadrature_points: int,
) -> float:
    """Expected Bayes label error after a Gaussian offset observation."""
    probability = float(np.clip(probability_secondary, 1e-12, 1.0 - 1e-12))
    if discriminability <= 1e-14:
        return min(probability, 1.0 - probability)
    nodes, weights = np.polynomial.hermite.hermgauss(quadrature_points)
    log_odds = math.log(probability / (1.0 - probability))
    standard_deviation = math.sqrt(discriminability)
    expected = 0.0
    for secondary, prior in ((False, 1.0 - probability), (True, probability)):
        mean = log_odds + (0.5 if secondary else -0.5) * discriminability
        samples = mean + math.sqrt(2.0) * standard_deviation * nodes
        posterior = 1.0 / (1.0 + np.exp(-np.clip(samples, -60.0, 60.0)))
        errors = np.minimum(posterior, 1.0 - posterior)
        expected += prior * float(np.dot(weights, errors) / math.sqrt(math.pi))
    return expected


def _probe_agents(
    config: ExperimentConfig,
    action: str,
    visible: BoolArray,
    marginals: FloatArray,
) -> list[int]:
    if action == "track":
        return []
    if action == "spread":
        return [int(value) for value in np.flatnonzero(visible)]
    if not action.startswith("probe_"):
        raise ValueError(f"unknown M9C action: {action}")
    anchor = int(action.split("_", 1)[1])
    members = [int(value) for value in np.flatnonzero(visible)]
    if anchor not in members:
        raise ValueError(f"M9C probe source {anchor} is not visible")
    ranked = sorted(
        members,
        key=lambda agent: (
            0 if agent == anchor else 1,
            abs(float(marginals[agent]) - 0.5),
            agent,
        ),
    )
    return ranked[: min(config.m9c_probe_agent_count, len(ranked))]


def _action_goals(
    config: ExperimentConfig,
    action: str,
    positions: FloatArray,
    normal_goals: FloatArray,
    target_position: FloatArray,
    visible: BoolArray,
    marginals: FloatArray,
) -> tuple[FloatArray, int]:
    goals = normal_goals.copy()
    active = _probe_agents(config, action, visible, marginals)
    if active:
        # Ordinary flocking already tracks the target estimate.  Extrapolating
        # the selected goal creates the bounded extra closing speed that makes
        # this source's next measurement a distinct, more informative view.
        goals[active] = positions[active] + config.m9c_probe_goal_extrapolation * (
            target_position - positions[active]
        )
    return goals, len(active)


class IntegratedInvestigationController:
    """Choose component-local round-robin or receding-horizon source probes."""

    def __init__(self, config: ExperimentConfig, policy: str) -> None:
        if policy not in {"round_robin", "receding_horizon_voi"}:
            raise ValueError(f"unknown M9C policy: {policy}")
        self.config = config
        self.policy = policy
        self._last_action = "track"
        self._last_plan_step = -config.m9c_replan_interval
        self._last_expected_risk = 0.0
        self._round_robin_cursor = 0

    def _actions(
        self,
        visible: BoolArray,
        marginals: FloatArray,
    ) -> tuple[str, ...]:
        ranked = sorted(
            (int(agent) for agent in np.flatnonzero(visible)),
            key=lambda agent: (abs(float(marginals[agent]) - 0.5), agent),
        )
        anchors = ranked[: self.config.m9c_max_probe_modes]
        return ("track",) + tuple(f"probe_{agent}" for agent in anchors) + (
            "spread",
        )

    def _sequence_score(
        self,
        posterior: MissingEvidenceDecision,
        evidence: AssignmentEvidence,
        marginals: FloatArray,
        sequence: tuple[str, ...],
        sensor_positions: FloatArray,
        sensor_velocities: FloatArray,
        normal_goals: FloatArray,
        visible: BoolArray,
        operational: BoolArray,
        control_neighbors: list[list[int]],
        momenta: FloatArray,
    ) -> tuple[float, float]:
        positions = sensor_positions.copy()
        velocities = sensor_velocities.copy()
        cumulative_discriminability = np.zeros(self.config.n_agents, dtype=float)
        total_movement_cost = 0.0
        action_change_cost = 0.0
        previous_action = self._last_action
        member_indices = [int(value) for value in np.flatnonzero(visible)]
        for horizon_step, action in enumerate(sequence, start=1):
            predicted_target = posterior.state[:2] + (
                horizon_step * self.config.dt * posterior.state[2:4]
            )
            goals, _ = _action_goals(
                self.config,
                action,
                positions,
                normal_goals,
                predicted_target,
                visible,
                marginals,
            )
            velocities = flocking_velocity(
                self.config,
                positions,
                velocities,
                goals,
                control_neighbors,
                momenta,
                peer_positions=positions,
                peer_velocities=velocities,
            )
            velocities[~operational] = 0.0
            positions = advance_sensors(self.config, positions, velocities)
            movement = (
                float(np.mean(np.linalg.norm(velocities[member_indices], axis=1)))
                * self.config.dt
                if member_indices
                else 0.0
            )
            total_movement_cost += self.config.m9c_movement_cost_per_unit * movement
            if action != previous_action:
                action_change_cost += self.config.m9c_action_change_cost
            previous_action = action
            for agent in member_indices:
                covariance = measurement_covariance(
                    self.config,
                    positions[agent],
                    predicted_target,
                ) + posterior.covariance[:2, :2]
                offset = evidence.secondary_offset
                cumulative_discriminability[agent] += float(
                    offset @ np.linalg.solve(covariance, offset)
                )

        expected_errors = np.asarray(
            [
                _expected_binary_error(
                    float(marginals[agent]),
                    float(cumulative_discriminability[agent]),
                    self.config.m9c_planning_samples,
                )
                for agent in member_indices
            ],
            dtype=float,
        )
        offset_scale = float(np.linalg.norm(evidence.secondary_offset))
        assignment_risk = (
            offset_scale * float(np.mean(expected_errors)) if len(expected_errors) else 0.0
        )
        residual_risk = posterior.residual_mass * self.config.m9a6_residual_loss
        # Match M9B's truncated-horizon boundary: ambiguity that survives the
        # explicit action rollout is charged through the declared evidence
        # window rather than being treated as free after two steps.  This was
        # the specific V1 training defect; thresholds and evaluation loss are
        # unchanged.
        terminal_cycles = max(
            1,
            min(
                self.config.m9c_terminal_risk_max_cycles,
                evidence.secondary_steps_remaining - len(sequence) + 1,
            ),
        )
        expected_risk = (
            (1.0 - posterior.residual_mass) * assignment_risk * terminal_cycles
            + residual_risk
            + total_movement_cost
            + action_change_cost
        )
        return expected_risk, total_movement_cost

    def _choose_action(
        self,
        posterior: MissingEvidenceDecision,
        evidence: AssignmentEvidence,
        marginals: FloatArray,
        sensor_positions: FloatArray,
        sensor_velocities: FloatArray,
        normal_goals: FloatArray,
        visible: BoolArray,
        operational: BoolArray,
        control_neighbors: list[list[int]],
        momenta: FloatArray,
        remaining_steps: int,
    ) -> tuple[str, int, float, float]:
        actions = self._actions(visible, marginals)
        horizon = min(self.config.m9c_planning_horizon, remaining_steps)
        best: tuple[float, int, tuple[str, ...], float] | None = None
        evaluated = 0
        for order, sequence in enumerate(product(actions, repeat=horizon)):
            risk, movement_cost = self._sequence_score(
                posterior,
                evidence,
                marginals,
                sequence,
                sensor_positions,
                sensor_velocities,
                normal_goals,
                visible,
                operational,
                control_neighbors,
                momenta,
            )
            candidate = (risk, order, sequence, movement_cost)
            if best is None or candidate < best:
                best = candidate
            evaluated += 1
        assert best is not None
        return best[2][0], evaluated, best[0], best[3]

    def decide(
        self,
        step: int,
        posterior: MissingEvidenceDecision,
        evidence: AssignmentEvidence,
        sensor_positions: FloatArray,
        sensor_velocities: FloatArray,
        normal_goals: FloatArray,
        *,
        component_visible: BoolArray,
        operational: BoolArray,
        control_neighbors: list[list[int]],
        momenta: FloatArray,
        remaining_steps: int,
    ) -> IntegratedMotionDecision:
        evidence.validate(self.config.n_agents)
        visible = component_visible & operational
        marginals = assignment_marginals(evidence)
        uncertainties = np.minimum(marginals, 1.0 - marginals)
        visible_uncertainty = uncertainties[visible]
        requested = bool(
            evidence.secondary_active
            and len(visible_uncertainty)
            and float(np.max(visible_uncertainty))
            > 1.0 - self.config.m9c_activation_probability
        )
        residual_guarded = (
            requested
            and posterior.residual_mass
            > self.config.m9c_exploration_residual_ceiling
        )
        replanned = False
        evaluated = 0
        expected_risk = self._last_expected_risk
        predicted_movement_cost = 0.0
        actions = self._actions(visible, marginals) if np.any(visible) else ("track",)
        if not requested or residual_guarded or len(actions) == 1:
            action = "track"
        elif step - self._last_plan_step < self.config.m9c_replan_interval:
            action = self._last_action if self._last_action in actions else "track"
        elif self.policy == "round_robin":
            # M9B's comparator broadly spreads the whole team.  In the dynamic
            # integration this means giving every visible source the aggressive
            # close-view goal while uncertainty persists.
            action = "spread"
            self._last_plan_step = step
            replanned = True
        else:
            action, evaluated, expected_risk, predicted_movement_cost = (
                self._choose_action(
                    posterior,
                    evidence,
                    marginals,
                    sensor_positions,
                    sensor_velocities,
                    normal_goals,
                    visible,
                    operational,
                    control_neighbors,
                    momenta,
                    remaining_steps,
                )
            )
            self._last_plan_step = step
            self._last_expected_risk = expected_risk
            replanned = True
        target = posterior.state[:2]
        goals, active_agents = _action_goals(
            self.config,
            action,
            sensor_positions,
            normal_goals,
            target,
            visible,
            marginals,
        )
        self._last_action = action
        uncertain_count = int(
            np.sum(visible_uncertainty > 1.0 - self.config.m9c_activation_probability)
        )
        return IntegratedMotionDecision(
            policy=self.policy,
            action=action,
            goals=goals,
            requested=requested,
            residual_guarded=residual_guarded,
            replanned=replanned,
            planning_sequences_evaluated=evaluated,
            expected_risk=expected_risk,
            predicted_movement_cost=predicted_movement_cost,
            active_agents=active_agents,
            mode_count=uncertain_count,
        )
