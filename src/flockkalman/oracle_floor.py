"""Causal Bayesian references for the M9A.5 topology-loss diagnostic.

These references are deliberately stronger than the production policy but do
not receive target truth, realized future noise, or seeded fault identities.
They enumerate the declared secondary-mode membership model and update its
posterior from the same measurements generated along the frozen M9A sensor
trajectory.  Truth enters only after an action has been chosen, for scoring.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

from .config import ExperimentConfig
from .filters import constant_velocity_matrices
from .metrics import StepRecord
from .topology import connected_components


M9A_FULL = "flocking_topology_resilient"


FloatArray = NDArray[np.float64]
BoolArray = NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class BayesianMode:
    """One posterior state mode formed from compatible assignments."""

    probability: float
    state: FloatArray
    covariance: FloatArray


@dataclass(frozen=True, slots=True)
class BayesianDecision:
    """A truth-blind action under the declared M9A decision loss."""

    action: str
    state: FloatArray
    modes: tuple[BayesianMode, ...]
    credible_modes: tuple[BayesianMode, ...]
    predicted_risk: float
    confidence: float


def _validate_reference_scope(config: ExperimentConfig) -> None:
    if config.measurement_model != "cartesian":
        raise ValueError("M9A.5 Bayesian references currently require Cartesian sensing")
    if config.secondary_mode_agent_count < 0:
        raise ValueError("secondary-mode population cannot be negative")
    if config.secondary_mode_agent_count > config.n_agents:
        raise ValueError("secondary-mode population exceeds agent count")


def _validate_oracle_scope(config: ExperimentConfig) -> None:
    _validate_reference_scope(config)
    if config.secondary_mode_agent_count <= 0:
        raise ValueError("M9A.5 requires a declared secondary-mode population")
    if any(
        count
        for count in (
            config.biased_agent_count,
            config.byzantine_agent_count,
            config.strategic_agent_count,
        )
    ):
        raise ValueError(
            "M9A.5 assignment model is scoped to the M9A secondary-mode scenarios"
        )


class AssignmentBayesFilter:
    """Vectorized bank of KFs over every declared fault-membership assignment."""

    def __init__(
        self,
        config: ExperimentConfig,
        *,
        secondary_count: int | None = None,
        secondary_offset: tuple[float, float] | None = None,
        secondary_start_step: int | None = None,
        secondary_end_step: int | None = None,
    ) -> None:
        _validate_reference_scope(config)
        self.secondary_count = (
            config.secondary_mode_agent_count
            if secondary_count is None
            else secondary_count
        )
        if not 0 <= self.secondary_count <= config.n_agents:
            raise ValueError("assumed secondary population must fit the agent count")
        self.secondary_offset = np.asarray(
            config.secondary_mode_offset
            if secondary_offset is None
            else secondary_offset,
            dtype=float,
        )
        self.secondary_start_step = (
            config.secondary_mode_start_step
            if secondary_start_step is None
            else secondary_start_step
        )
        self.secondary_end_step = (
            config.secondary_mode_end_step
            if secondary_end_step is None
            else secondary_end_step
        )
        self.config = config
        assignments = list(
            combinations(range(config.n_agents), self.secondary_count)
        )
        self.assignment_mask = np.zeros(
            (len(assignments), config.n_agents), dtype=bool
        )
        for index, members in enumerate(assignments):
            self.assignment_mask[index, list(members)] = True
        self.states = np.tile(
            np.asarray(config.target_initial_state, dtype=float),
            (len(assignments), 1),
        )
        initial_covariance = np.diag(
            [
                config.initial_belief_position_std**2,
                config.initial_belief_position_std**2,
                config.initial_belief_velocity_std**2,
                config.initial_belief_velocity_std**2,
            ]
        )
        self.covariances = np.tile(
            initial_covariance[np.newaxis, :, :], (len(assignments), 1, 1)
        )
        self.log_weights = np.full(
            len(assignments), -math.log(len(assignments)), dtype=float
        )
        self._last_step = -1
        self.last_model_nis = 0.0
        self.last_measurement_count = 0
        self.last_rejected_agents = np.zeros(config.n_agents, dtype=bool)

    @property
    def weights(self) -> FloatArray:
        weights = np.exp(self.log_weights)
        return weights / float(np.sum(weights))

    @property
    def normalized_assignment_entropy(self) -> float:
        weights = self.weights
        positive = weights > 0.0
        entropy = -float(np.sum(weights[positive] * np.log(weights[positive])))
        maximum = math.log(len(weights))
        return entropy / maximum if maximum > 0.0 else 0.0

    def _predict(self) -> None:
        transition, process = constant_velocity_matrices(
            self.config.dt, self.config.filter_process_variance
        )
        self.states = self.states @ transition.T
        self.covariances = np.einsum(
            "ij,hjk,lk->hil", transition, self.covariances, transition
        )
        self.covariances += process[np.newaxis, :, :]
        self.covariances = 0.5 * (
            self.covariances + np.swapaxes(self.covariances, 1, 2)
        )

    def _measurement_update(
        self,
        agent: int,
        observation: FloatArray,
        measurement_covariance: FloatArray,
        secondary_active: bool,
    ) -> float:
        adjusted = np.tile(observation, (len(self.states), 1))
        if secondary_active:
            adjusted -= (
                self.assignment_mask[:, agent, np.newaxis]
                * self.secondary_offset
            )
        innovation = adjusted - self.states[:, :2]
        innovation_covariance = (
            self.covariances[:, :2, :2]
            + measurement_covariance[np.newaxis, :, :]
        )

        # Closed-form batched inverse for the symmetric 2x2 innovation matrix.
        first = innovation_covariance[:, 0, 0]
        cross = 0.5 * (
            innovation_covariance[:, 0, 1]
            + innovation_covariance[:, 1, 0]
        )
        second = innovation_covariance[:, 1, 1]
        determinant = np.maximum(first * second - cross * cross, 1e-15)
        inverse = np.empty_like(innovation_covariance)
        inverse[:, 0, 0] = second / determinant
        inverse[:, 0, 1] = -cross / determinant
        inverse[:, 1, 0] = -cross / determinant
        inverse[:, 1, 1] = first / determinant
        quadratic = np.einsum("hi,hij,hj->h", innovation, inverse, innovation)
        log_likelihood = -0.5 * (
            2.0 * math.log(2.0 * math.pi) + np.log(determinant) + quadratic
        )
        prior = self.log_weights.copy()
        weighted = prior + log_likelihood
        maximum = float(np.max(weighted))
        predictive_log_likelihood = maximum + math.log(
            float(np.sum(np.exp(weighted - maximum)))
        )
        normalized_only = prior - 0.5 * (
            2.0 * math.log(2.0 * math.pi) + np.log(determinant)
        )
        normal_maximum = float(np.max(normalized_only))
        predictive_log_normalizer = normal_maximum + math.log(
            float(np.sum(np.exp(normalized_only - normal_maximum)))
        )
        model_nis = max(
            0.0,
            -2.0 * (predictive_log_likelihood - predictive_log_normalizer),
        )
        self.log_weights = weighted

        gain = np.einsum("hij,hjk->hik", self.covariances[:, :, :2], inverse)
        self.states += np.einsum("hij,hj->hi", gain, innovation)
        observation_matrix = np.zeros((2, 4), dtype=float)
        observation_matrix[:, :2] = np.eye(2, dtype=float)
        residual = np.eye(4, dtype=float)[np.newaxis, :, :] - np.einsum(
            "hij,jk->hik", gain, observation_matrix
        )
        joseph_left = np.einsum(
            "hij,hjk,hkl->hil",
            residual,
            self.covariances,
            np.swapaxes(residual, 1, 2),
        )
        joseph_noise = np.einsum(
            "hij,jk,hkl->hil",
            gain,
            measurement_covariance,
            np.swapaxes(gain, 1, 2),
        )
        self.covariances = joseph_left + joseph_noise
        self.covariances = 0.5 * (
            self.covariances + np.swapaxes(self.covariances, 1, 2)
        )
        return model_nis

    def advance(
        self,
        step: int,
        observations: FloatArray,
        measurement_covariances: tuple[FloatArray, ...],
        visible: BoolArray,
        *,
        measurement_nis_ceiling: float | None = None,
    ) -> None:
        if step != self._last_step + 1:
            raise ValueError("Bayesian reference steps must be consecutive")
        if step > 0:
            self._predict()
        secondary_active = step >= self.secondary_start_step and (
            self.secondary_end_step < 0
            or step < self.secondary_end_step
        )
        model_nis: list[float] = []
        rejected = np.zeros(self.config.n_agents, dtype=bool)
        for agent in np.flatnonzero(visible):
            index = int(agent)
            if measurement_nis_ceiling is None:
                model_nis.append(
                    self._measurement_update(
                        index,
                        observations[index],
                        measurement_covariances[index],
                        secondary_active,
                    )
                )
            else:
                # The causal predictive gate must be able to decline a raw
                # sample without letting that sample alter any hypothesis.
                saved_states = self.states.copy()
                saved_covariances = self.covariances.copy()
                saved_log_weights = self.log_weights.copy()
                nis = self._measurement_update(
                    index,
                    observations[index],
                    measurement_covariances[index],
                    secondary_active,
                )
                model_nis.append(nis)
                if nis > measurement_nis_ceiling:
                    self.states = saved_states
                    self.covariances = saved_covariances
                    self.log_weights = saved_log_weights
                    rejected[index] = True
        maximum = float(np.max(self.log_weights))
        normalizer = maximum + math.log(
            float(np.sum(np.exp(self.log_weights - maximum)))
        )
        self.log_weights -= normalizer
        self.last_measurement_count = len(model_nis)
        self.last_model_nis = float(np.mean(model_nis)) if model_nis else 0.0
        self.last_rejected_agents = rejected
        self._last_step = step

    def modes(self) -> tuple[BayesianMode, ...]:
        weights = self.weights
        retained = np.flatnonzero(weights > 1e-12)
        if retained.size == 0:
            retained = np.asarray([int(np.argmax(weights))])
        positions = self.states[retained, :2]
        parent = np.arange(len(retained), dtype=np.int64)

        def root(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[int(parent[index])]
                index = int(parent[index])
            return index

        for first in range(len(retained)):
            for second in range(first + 1, len(retained)):
                if (
                    np.linalg.norm(positions[first] - positions[second])
                    <= self.config.output_mode_equivalence_distance
                ):
                    first_root = root(first)
                    second_root = root(second)
                    if first_root != second_root:
                        parent[second_root] = first_root

        groups: dict[int, list[int]] = {}
        for local_index, hypothesis_index in enumerate(retained):
            groups.setdefault(root(local_index), []).append(int(hypothesis_index))

        modes: list[BayesianMode] = []
        retained_mass = float(np.sum(weights[retained]))
        for members in groups.values():
            member_weights = weights[members]
            probability = float(np.sum(member_weights)) / retained_mass
            normalized = member_weights / float(np.sum(member_weights))
            state = np.einsum("h,hi->i", normalized, self.states[members])
            covariance = np.zeros((4, 4), dtype=float)
            for weight, member in zip(normalized, members):
                difference = self.states[member] - state
                covariance += float(weight) * (
                    self.covariances[member] + np.outer(difference, difference)
                )
            modes.append(BayesianMode(probability, state, covariance))
        modes.sort(
            key=lambda mode: (
                -mode.probability,
                float(mode.state[0]),
                float(mode.state[1]),
            )
        )
        return tuple(modes)

    @staticmethod
    def _candidate_risk(candidate: FloatArray, modes: tuple[BayesianMode, ...]) -> float:
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

    def decide(self) -> BayesianDecision:
        modes = self.modes()
        cumulative = 0.0
        credible: list[BayesianMode] = []
        for mode in modes:
            credible.append(mode)
            cumulative += mode.probability
            if cumulative >= 0.95:
                break

        candidates: list[tuple[str, FloatArray, float]] = []
        for mode in modes:
            candidates.append(
                ("select", mode.state.copy(), self._candidate_risk(mode.state, modes))
            )
        if len(modes) > 1:
            mixture_state = sum(
                (mode.probability * mode.state for mode in modes),
                start=np.zeros(4, dtype=float),
            )
            candidates.append(
                (
                    "mixture",
                    mixture_state,
                    self._candidate_risk(mixture_state, modes),
                )
            )
        best_action, best_state, best_risk = min(
            candidates,
            key=lambda item: (item[2], item[0], float(item[1][0]), float(item[1][1])),
        )
        defer_risk = self.config.output_defer_cost
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
            defer_risk += mode.probability * nearest
        if defer_risk + 1e-12 < best_risk:
            action = "defer"
            state = credible[0].state.copy()
            predicted_risk = defer_risk
        else:
            action = best_action
            state = best_state
            predicted_risk = best_risk
        runner_up = modes[1].probability if len(modes) > 1 else 0.0
        return BayesianDecision(
            action=action,
            state=state,
            modes=modes,
            credible_modes=tuple(credible),
            predicted_risk=predicted_risk,
            confidence=modes[0].probability - runner_up,
        )


def _score_decision(
    config: ExperimentConfig,
    decision: BayesianDecision,
    truth_position: FloatArray,
) -> dict[str, object]:
    all_errors = np.asarray(
        [
            np.linalg.norm(mode.state[:2] - truth_position)
            for mode in decision.modes
        ],
        dtype=float,
    )
    if decision.action == "defer":
        credible_errors = [
            float(np.linalg.norm(mode.state[:2] - truth_position))
            for mode in decision.credible_modes
        ]
        base_error = min(credible_errors)
        loss = base_error + config.output_defer_cost
    else:
        base_error = float(np.linalg.norm(decision.state[:2] - truth_position))
        loss = base_error
    wrong_mode = (
        decision.action == "select"
        and len(decision.modes) > 1
        and base_error
        > float(np.min(all_errors)) + config.robust_bias_group_tolerance
    )
    return {
        "loss": loss,
        "base_error": base_error,
        "action": decision.action,
        "wrong_mode": wrong_mode,
        "mode_count": len(decision.modes),
        "credible_mode_count": len(decision.credible_modes),
        "top_mode_probability": decision.modes[0].probability,
        "confidence": decision.confidence,
        "predicted_risk": decision.predicted_risk,
    }


class OracleFloorCollector:
    """Evaluate observer-component and ideal-global references on one M9A run."""

    def __init__(self, config: ExperimentConfig) -> None:
        _validate_oracle_scope(config)
        self.config = config
        self.observer_reference = AssignmentBayesFilter(config)
        self.global_reference = AssignmentBayesFilter(config)
        self.rows: list[dict[str, object]] = []

    def __call__(self, payload: dict[str, object]) -> None:
        step = int(payload["step"])
        truth = np.asarray(payload["truth"], dtype=float)
        observations = np.asarray(payload["observations"], dtype=float)
        covariances = tuple(
            np.asarray(value, dtype=float)
            for value in payload["measurement_covariances"]  # type: ignore[union-attr]
        )
        available = np.asarray(payload["available"], dtype=bool)
        operational = np.asarray(payload["operational"], dtype=bool)
        neighbors = [
            list(peers) for peers in payload["neighbors"]  # type: ignore[union-attr]
        ]
        record = payload["record"]
        if not isinstance(record, StepRecord):
            raise TypeError("diagnostic observer received an invalid step record")

        components, labels = connected_components(neighbors, operational)
        observer_label = int(labels[0])
        if observer_label < 0 and components:
            observer_label = 0
        observer_visible = np.zeros(self.config.n_agents, dtype=bool)
        if components and observer_label >= 0:
            observer_visible[list(components[observer_label])] = True
        observer_visible &= available & operational
        global_visible = available & operational

        self.observer_reference.advance(
            step, observations, covariances, observer_visible
        )
        self.global_reference.advance(step, observations, covariances, global_visible)
        # Both actions are completed before truth is passed to the scoring helper.
        observer_decision = self.observer_reference.decide()
        global_decision = self.global_reference.decide()
        observer_score = _score_decision(
            self.config, observer_decision, truth[:2]
        )
        global_score = _score_decision(self.config, global_decision, truth[:2])

        row: dict[str, object] = {
            "step": step,
            "frozen_m9a_loss": record.output_decision_loss,
            "frozen_m9a_base_error": record.output_decision_base_error,
            "frozen_m9a_action": record.output_action,
            "m9a_hypothesis_floor_loss": record.best_hypothesis_position_error,
            "observer_visible_agents": int(np.sum(observer_visible)),
            "global_visible_agents": int(np.sum(global_visible)),
            "observer_assignment_entropy": (
                self.observer_reference.normalized_assignment_entropy
            ),
            "global_assignment_entropy": (
                self.global_reference.normalized_assignment_entropy
            ),
        }
        for prefix, score in (
            ("observer", observer_score),
            ("global", global_score),
        ):
            row.update({f"{prefix}_{key}": value for key, value in score.items()})
        self.rows.append(row)

    def summarize(self, seed: int) -> dict[str, object]:
        if not self.rows:
            raise ValueError("cannot summarize an empty M9A.5 run")

        def mean(name: str) -> float:
            return float(np.mean([float(row[name]) for row in self.rows]))

        summary: dict[str, object] = {
            "algorithm": M9A_FULL,
            "seed": seed,
            "frozen_m9a_loss": mean("frozen_m9a_loss"),
            "frozen_m9a_base_error": mean("frozen_m9a_base_error"),
            "m9a_hypothesis_floor_loss": mean("m9a_hypothesis_floor_loss"),
        }
        for prefix in ("observer", "global"):
            summary.update(
                {
                    f"{prefix}_loss": mean(f"{prefix}_loss"),
                    f"{prefix}_base_error": mean(f"{prefix}_base_error"),
                    f"{prefix}_selection_rate": mean_from_predicate(
                        self.rows, f"{prefix}_action", "select"
                    ),
                    f"{prefix}_mixture_rate": mean_from_predicate(
                        self.rows, f"{prefix}_action", "mixture"
                    ),
                    f"{prefix}_defer_rate": mean_from_predicate(
                        self.rows, f"{prefix}_action", "defer"
                    ),
                    f"{prefix}_wrong_mode_action_rate": mean(
                        f"{prefix}_wrong_mode"
                    ),
                    f"{prefix}_mean_mode_count": mean(f"{prefix}_mode_count"),
                    f"{prefix}_mean_credible_mode_count": mean(
                        f"{prefix}_credible_mode_count"
                    ),
                    f"{prefix}_mean_top_mode_probability": mean(
                        f"{prefix}_top_mode_probability"
                    ),
                    f"{prefix}_mean_confidence": mean(f"{prefix}_confidence"),
                    f"{prefix}_mean_predicted_risk": mean(
                        f"{prefix}_predicted_risk"
                    ),
                    f"{prefix}_mean_assignment_entropy": mean(
                        f"{prefix}_assignment_entropy"
                    ),
                    f"{prefix}_mean_visible_agents": mean(
                        f"{prefix}_visible_agents"
                    ),
                }
            )
        summary.update(
            {
                "current_to_observer_gap": float(summary["frozen_m9a_loss"])
                - float(summary["observer_loss"]),
                "observer_to_global_gap": float(summary["observer_loss"])
                - float(summary["global_loss"]),
                "current_to_global_gap": float(summary["frozen_m9a_loss"])
                - float(summary["global_loss"]),
                "current_to_hypothesis_floor_gap": float(summary["frozen_m9a_loss"])
                - float(summary["m9a_hypothesis_floor_loss"]),
            }
        )
        return summary


def mean_from_predicate(
    rows: list[Mapping[str, object]], name: str, expected: object
) -> float:
    return float(np.mean([row[name] == expected for row in rows]))


def run_oracle_floor_trial(
    config: ExperimentConfig,
    seed: int,
    *,
    include_step_rows: bool = False,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Run frozen M9A once while scoring both causal Bayesian references."""
    # Local import keeps the causal filter reusable by the integrated M9A.6
    # output policy without introducing an experiment/oracle import cycle.
    from .experiment import run_trial

    collector = OracleFloorCollector(config)
    run_trial(
        config,
        M9A_FULL,
        seed,
        step_observer=collector,
    )
    return collector.summarize(seed), collector.rows if include_step_rows else []
