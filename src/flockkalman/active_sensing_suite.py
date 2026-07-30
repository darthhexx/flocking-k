"""M9B decision-relevant multi-hypothesis active-sensing research suite."""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import asdict, dataclass
from functools import lru_cache
import hashlib
from itertools import product
import json
import math
import os
from pathlib import Path
import platform
from time import perf_counter
from typing import Iterable, Sequence

import numpy as np
from numpy.typing import NDArray

from .suite import _bootstrap_interval, _write_csv


FloatArray = NDArray[np.float64]
POLICIES = (
    "passive",
    "round_robin",
    "myopic_voi",
    "receding_horizon_voi",
    "computational_oracle",
)


@dataclass(frozen=True, slots=True)
class ActiveSensingConfig:
    """Shared policy, sensing, motion, and loss parameters for M9B."""

    steps: int = 10
    dt: float = 1.0
    n_agents: int = 8
    probe_agent_count: int = 2
    measurement_std: float = 0.90
    sensor_max_speed: float = 1.80
    fixed_momentum: float = 0.72
    selection_probability: float = 0.99
    defer_cost: float = 0.25
    wrong_selection_cost: float = 2.0
    movement_cost_per_unit: float = 0.80
    planning_samples: int = 9
    myopic_horizon: int = 1
    receding_horizon: int = 2
    oracle_horizon: int = 3

    def validate(self) -> None:
        if self.steps < 3 or self.n_agents < 3:
            raise ValueError("M9B needs at least three steps and three agents")
        if not 1 <= self.probe_agent_count < self.n_agents:
            raise ValueError("probe_agent_count must be in [1, n_agents)")
        if self.dt <= 0.0 or self.measurement_std <= 0.0:
            raise ValueError("time and sensing scales must be positive")
        if self.sensor_max_speed <= 0.0:
            raise ValueError("sensor_max_speed must be positive")
        if not 0.0 <= self.fixed_momentum < 1.0:
            raise ValueError("fixed_momentum must be in [0, 1)")
        if not 0.5 < self.selection_probability < 1.0:
            raise ValueError("selection_probability must be in (0.5, 1)")
        if min(
            self.defer_cost,
            self.wrong_selection_cost,
            self.movement_cost_per_unit,
        ) < 0.0:
            raise ValueError("losses cannot be negative")
        if self.planning_samples < 3 or self.planning_samples % 2 == 0:
            raise ValueError("planning_samples must be an odd integer of at least three")
        if not (
            self.myopic_horizon == 1
            and self.receding_horizon >= 2
            and self.oracle_horizon > self.receding_horizon
        ):
            raise ValueError("planner horizons must satisfy 1 < receding < oracle")
        if self.oracle_horizon > min(self.steps, 16):
            raise ValueError("oracle_horizon cannot exceed steps or 16 rollout cycles")


@dataclass(frozen=True, slots=True)
class ActiveSensingScenario:
    """A static mode set whose candidate views have competing utility."""

    name: str
    description: str
    hypothesis_positions: tuple[tuple[float, float], ...]
    prior_probabilities: tuple[float, ...]
    probe_cost_multipliers: tuple[float, ...]
    spread_cost_multiplier: float = 1.25
    measurement_std_multiplier: float = 1.0

    def validate(self) -> None:
        hypotheses = np.asarray(self.hypothesis_positions, dtype=float)
        prior = np.asarray(self.prior_probabilities, dtype=float)
        costs = np.asarray(self.probe_cost_multipliers, dtype=float)
        if hypotheses.ndim != 2 or hypotheses.shape[0] < 3 or hypotheses.shape[1] != 2:
            raise ValueError(f"{self.name}: at least three 2D hypotheses are required")
        if len(prior) != len(hypotheses) or len(costs) != len(hypotheses):
            raise ValueError(f"{self.name}: hypotheses, priors, and costs must align")
        if np.any(prior <= 0.0) or not np.isclose(np.sum(prior), 1.0):
            raise ValueError(f"{self.name}: priors must be positive and sum to one")
        if np.any(costs <= 0.0) or self.spread_cost_multiplier <= 0.0:
            raise ValueError(f"{self.name}: action costs must be positive")
        if self.measurement_std_multiplier <= 0.0:
            raise ValueError(f"{self.name}: noise multiplier must be positive")
        radii = np.linalg.norm(hypotheses, axis=1)
        if float(np.max(radii) - np.min(radii)) > 1e-8:
            raise ValueError(
                f"{self.name}: hypotheses must be equidistant from the passive start"
            )


SQRT_THREE = math.sqrt(3.0)
DEFAULT_ACTIVE_SENSING_SCENARIOS = (
    ActiveSensingScenario(
        "triad_uniform",
        "Three equally likely modes on a circle; a probe resolves one-vs-rest before the remaining pair.",
        ((6.0, 0.0), (-3.0, 3.0 * SQRT_THREE), (-3.0, -3.0 * SQRT_THREE)),
        (1.0 / 3.0, 1.0 / 3.0, 1.0 / 3.0),
        (1.0, 1.0, 1.0),
    ),
    ActiveSensingScenario(
        "near_pair_rare_distractor",
        "Two probable nearby angular modes compete with a rare distant-direction distractor.",
        (
            (6.0 * math.cos(math.radians(35.0)), 6.0 * math.sin(math.radians(35.0))),
            (6.0 * math.cos(math.radians(-35.0)), 6.0 * math.sin(math.radians(-35.0))),
            (-6.0, 0.0),
        ),
        (0.45, 0.45, 0.10),
        (1.0, 1.0, 1.0),
        spread_cost_multiplier=1.35,
        measurement_std_multiplier=0.90,
    ),
    ActiveSensingScenario(
        "asymmetric_transit",
        "The most probable eastward probe has a high transit cost, making information and cost disagree.",
        ((6.0, 0.0), (-3.0, 3.0 * SQRT_THREE), (-3.0, -3.0 * SQRT_THREE)),
        (0.50, 0.35, 0.15),
        (2.60, 0.85, 1.10),
        spread_cost_multiplier=1.45,
    ),
    ActiveSensingScenario(
        "four_mode_cross",
        "Four equally likely cardinal modes require allocating limited probes among competing pairs.",
        ((6.0, 0.0), (0.0, 6.0), (-6.0, 0.0), (0.0, -6.0)),
        (0.25, 0.25, 0.25, 0.25),
        (1.0, 1.0, 1.0, 1.0),
        spread_cost_multiplier=1.35,
        measurement_std_multiplier=0.95,
    ),
    ActiveSensingScenario(
        "four_mode_skewed_cost",
        "Four modes combine skewed prior support with asymmetric probe and broad-spread costs.",
        ((6.0, 0.0), (0.0, 6.0), (-6.0, 0.0), (0.0, -6.0)),
        (0.42, 0.33, 0.15, 0.10),
        (2.20, 0.80, 1.35, 0.70),
        spread_cost_multiplier=1.55,
        measurement_std_multiplier=1.10,
    ),
)


@dataclass(frozen=True, slots=True)
class ActiveSensingRun:
    scenario: str
    seed: int
    policy: str
    truth_mode: int
    resolved: bool
    resolution_steps: int
    selected_mode: int
    wrong_selection: bool
    total_decision_loss: float
    decision_cost: float
    movement_cost: float
    movement_distance: float
    final_truth_probability: float
    final_entropy: float
    brier_score: float
    log_loss: float
    mean_confidence: float
    hold_actions: int
    spread_actions: int
    probe_actions: int
    unique_probe_actions: int
    first_action: str
    action_trace: str
    planner_horizon: int
    planning_sequences_evaluated: int
    runtime_seconds: float
    trace_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _scenario_trace(
    config: ActiveSensingConfig,
    scenario: ActiveSensingScenario,
    seed: int,
) -> tuple[int, FloatArray, str]:
    rng = np.random.default_rng(seed)
    truth_mode = int(rng.choice(len(scenario.hypothesis_positions), p=scenario.prior_probabilities))
    normals = rng.normal(size=(config.steps, config.n_agents))
    digest = hashlib.sha256()
    digest.update(
        json.dumps(
            {"config": asdict(config), "scenario": asdict(scenario)},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    digest.update(str(seed).encode("ascii"))
    digest.update(str(truth_mode).encode("ascii"))
    digest.update(np.ascontiguousarray(normals).tobytes())
    return truth_mode, normals, digest.hexdigest()


def active_sensing_fingerprint(
    config: ActiveSensingConfig,
    scenario: ActiveSensingScenario,
    seed: int,
) -> str:
    """Return the deterministic exogenous trace fingerprint."""
    config.validate()
    scenario.validate()
    return _scenario_trace(config, scenario, seed)[2]


def _normalize_log_probabilities(log_probabilities: FloatArray) -> FloatArray:
    shifted = log_probabilities - float(np.max(log_probabilities))
    probabilities = np.exp(np.clip(shifted, -700.0, 0.0))
    return probabilities / float(np.sum(probabilities))


def _entropy(probabilities: FloatArray) -> float:
    clipped = np.clip(probabilities, 1e-15, 1.0)
    return float(-np.sum(clipped * np.log(clipped)))


def _measurement_means(positions: FloatArray, hypotheses: FloatArray) -> FloatArray:
    return np.linalg.norm(
        positions[np.newaxis, :, :] - hypotheses[:, np.newaxis, :], axis=2
    )


def _update_posterior(
    prior: FloatArray,
    observations: FloatArray,
    means: FloatArray,
    measurement_std: float,
) -> FloatArray:
    log_probabilities = np.log(np.clip(prior, 1e-300, 1.0))
    log_probabilities -= np.sum(
        (observations[np.newaxis, :] - means) ** 2, axis=1
    ) / (2.0 * measurement_std**2)
    return _normalize_log_probabilities(log_probabilities)


def _actions(scenario: ActiveSensingScenario) -> tuple[str, ...]:
    return ("hold",) + tuple(
        f"probe_{index}" for index in range(len(scenario.hypothesis_positions))
    ) + ("spread",)


def _motion(
    config: ActiveSensingConfig,
    scenario: ActiveSensingScenario,
    positions: FloatArray,
    velocities: FloatArray,
    action: str,
) -> tuple[FloatArray, FloatArray, float, float]:
    hypotheses = np.asarray(scenario.hypothesis_positions, dtype=float)
    desired = np.zeros_like(positions)
    cost_multiplier = 1.0
    if action == "spread":
        for agent in range(config.n_agents):
            goal = hypotheses[agent % len(hypotheses)]
            direction = goal - positions[agent]
            norm = float(np.linalg.norm(direction))
            if norm > 1e-12:
                desired[agent] = direction / norm * config.sensor_max_speed
        cost_multiplier = scenario.spread_cost_multiplier
    elif action.startswith("probe_"):
        mode = int(action.split("_", 1)[1])
        if not 0 <= mode < len(hypotheses):
            raise ValueError(f"unknown probe action: {action}")
        start = (mode * config.probe_agent_count) % config.n_agents
        agents = [
            (start + offset) % config.n_agents
            for offset in range(config.probe_agent_count)
        ]
        for agent in agents:
            direction = hypotheses[mode] - positions[agent]
            norm = float(np.linalg.norm(direction))
            if norm > 1e-12:
                desired[agent] = direction / norm * config.sensor_max_speed
        cost_multiplier = float(scenario.probe_cost_multipliers[mode])
    elif action != "hold":
        raise ValueError(f"unknown M9B action: {action}")
    next_velocities = (
        config.fixed_momentum * velocities
        + (1.0 - config.fixed_momentum) * desired
    )
    speeds = np.linalg.norm(next_velocities, axis=1)
    next_velocities = np.divide(
        next_velocities,
        np.maximum(1.0, speeds / config.sensor_max_speed)[:, np.newaxis],
    )
    displacement = next_velocities * config.dt
    movement_distance = float(np.mean(np.linalg.norm(displacement, axis=1)))
    movement_cost = (
        config.movement_cost_per_unit * cost_multiplier * movement_distance
    )
    return positions + displacement, next_velocities, movement_distance, movement_cost


@lru_cache(maxsize=32)
def _planning_noise(samples: int, horizon: int, n_agents: int) -> FloatArray:
    half = (samples - 1) // 2
    rng = np.random.default_rng(20260725 + n_agents)
    # Generate a common long rollout and take a prefix so planner depth is the
    # only deliberate difference between myopic, receding, and oracle arms.
    draws = rng.normal(size=(half, 16, n_agents))[:, :horizon, :]
    return np.concatenate(
        (np.zeros((1, horizon, n_agents), dtype=float), draws, -draws), axis=0
    )


def _sequence_geometry(
    config: ActiveSensingConfig,
    scenario: ActiveSensingScenario,
    positions: FloatArray,
    velocities: FloatArray,
    sequence: Sequence[str],
) -> tuple[FloatArray, FloatArray]:
    hypotheses = np.asarray(scenario.hypothesis_positions, dtype=float)
    means: list[FloatArray] = []
    movement_costs: list[float] = []
    future_positions = positions.copy()
    future_velocities = velocities.copy()
    for action in sequence:
        future_positions, future_velocities, _, movement_cost = _motion(
            config,
            scenario,
            future_positions,
            future_velocities,
            action,
        )
        means.append(_measurement_means(future_positions, hypotheses))
        movement_costs.append(movement_cost)
    return np.asarray(means, dtype=float), np.asarray(movement_costs, dtype=float)


def _expected_sequence_loss(
    config: ActiveSensingConfig,
    scenario: ActiveSensingScenario,
    prior: FloatArray,
    means: FloatArray,
    movement_costs: FloatArray,
    remaining_steps: int,
) -> float:
    """Approximate Bayes risk for a deterministic open-loop action sequence."""
    horizon, mode_count, _ = means.shape
    noise = _planning_noise(config.planning_samples, horizon, config.n_agents)
    measurement_std = config.measurement_std * scenario.measurement_std_multiplier
    expected = 0.0
    for truth_mode in range(mode_count):
        log_probabilities = np.repeat(
            np.log(np.clip(prior, 1e-300, 1.0))[np.newaxis, :],
            config.planning_samples,
            axis=0,
        )
        alive = np.ones(config.planning_samples, dtype=bool)
        costs = np.zeros(config.planning_samples, dtype=float)
        for step in range(horizon):
            costs[alive] += float(movement_costs[step])
            observations = (
                means[step, truth_mode][np.newaxis, :]
                + measurement_std * noise[:, step, :]
            )
            log_probabilities -= np.sum(
                (
                    observations[:, np.newaxis, :]
                    - means[step][np.newaxis, :, :]
                )
                ** 2,
                axis=2,
            ) / (2.0 * measurement_std**2)
            row_maximum = np.max(log_probabilities, axis=1, keepdims=True)
            probabilities = np.exp(
                np.clip(log_probabilities - row_maximum, -700.0, 0.0)
            )
            probabilities /= np.sum(probabilities, axis=1, keepdims=True)
            confidence = np.max(probabilities, axis=1)
            selected = np.argmax(probabilities, axis=1)
            resolving = alive & (confidence >= config.selection_probability)
            costs[resolving] += (
                selected[resolving] != truth_mode
            ).astype(float) * config.wrong_selection_cost
            alive &= ~resolving
            costs[alive] += config.defer_cost
        # A truncated planner must price ambiguity left outside its explicit
        # action horizon. The conservative boundary assumes no later view
        # improvement and pays the declared deferral cost to the deadline.
        costs[alive] += config.defer_cost * max(remaining_steps - horizon, 0)
        expected += float(prior[truth_mode]) * float(np.mean(costs))
    return expected


def choose_active_sensing_action(
    config: ActiveSensingConfig,
    scenario: ActiveSensingScenario,
    prior: FloatArray,
    positions: FloatArray,
    velocities: FloatArray,
    horizon: int,
    remaining_steps: int | None = None,
) -> tuple[str, int]:
    """Choose the first action of the minimum sampled-risk action sequence."""
    config.validate()
    scenario.validate()
    actions = _actions(scenario)
    planning_horizon = min(horizon, remaining_steps or config.steps)
    best: tuple[float, int, tuple[str, ...]] | None = None
    evaluated = 0
    for order, sequence in enumerate(product(actions, repeat=planning_horizon)):
        means, movement_costs = _sequence_geometry(
            config, scenario, positions, velocities, sequence
        )
        score = _expected_sequence_loss(
            config,
            scenario,
            prior,
            means,
            movement_costs,
            remaining_steps or config.steps,
        )
        candidate = (score, order, sequence)
        if best is None or candidate < best:
            best = candidate
        evaluated += 1
    assert best is not None
    return best[2][0], evaluated


def run_active_sensing_trial(
    config: ActiveSensingConfig,
    scenario: ActiveSensingScenario,
    policy: str,
    seed: int,
) -> ActiveSensingRun:
    """Run one paired M9B multi-hypothesis active-sensing trial."""
    config.validate()
    scenario.validate()
    if policy not in POLICIES:
        raise ValueError(f"unknown M9B policy: {policy}")
    started = perf_counter()
    truth_mode, normals, fingerprint = _scenario_trace(config, scenario, seed)
    hypotheses = np.asarray(scenario.hypothesis_positions, dtype=float)
    posterior = np.asarray(scenario.prior_probabilities, dtype=float)
    positions = np.zeros((config.n_agents, 2), dtype=float)
    velocities = np.zeros_like(positions)
    measurement_std = config.measurement_std * scenario.measurement_std_multiplier
    decision_cost = 0.0
    movement_cost = 0.0
    movement_distance = 0.0
    resolved = False
    resolution_steps = config.steps
    selected_mode = -1
    confidences: list[float] = []
    action_trace: list[str] = []
    planning_sequences_evaluated = 0
    horizon_by_policy = {
        "passive": 0,
        "round_robin": 0,
        "myopic_voi": config.myopic_horizon,
        "receding_horizon_voi": config.receding_horizon,
        "computational_oracle": config.oracle_horizon,
    }

    for step in range(config.steps):
        if policy == "passive":
            action = "hold"
        elif policy == "round_robin":
            action = "spread"
        else:
            action, evaluated = choose_active_sensing_action(
                config,
                scenario,
                posterior,
                positions,
                velocities,
                horizon_by_policy[policy],
                config.steps - step,
            )
            planning_sequences_evaluated += evaluated
        action_trace.append(action)
        positions, velocities, distance, action_movement_cost = _motion(
            config, scenario, positions, velocities, action
        )
        movement_distance += distance
        movement_cost += action_movement_cost
        means = _measurement_means(positions, hypotheses)
        observations = means[truth_mode] + measurement_std * normals[step]
        posterior = _update_posterior(
            posterior, observations, means, measurement_std
        )
        confidence = float(np.max(posterior))
        confidences.append(confidence)
        if confidence >= config.selection_probability:
            selected_mode = int(np.argmax(posterior))
            decision_cost += (
                config.wrong_selection_cost if selected_mode != truth_mode else 0.0
            )
            resolved = True
            resolution_steps = step + 1
            break
        decision_cost += config.defer_cost

    truth_vector = np.zeros(len(hypotheses), dtype=float)
    truth_vector[truth_mode] = 1.0
    probe_labels = {action for action in action_trace if action.startswith("probe_")}
    return ActiveSensingRun(
        scenario=scenario.name,
        seed=seed,
        policy=policy,
        truth_mode=truth_mode,
        resolved=resolved,
        resolution_steps=resolution_steps,
        selected_mode=selected_mode,
        wrong_selection=resolved and selected_mode != truth_mode,
        total_decision_loss=decision_cost + movement_cost,
        decision_cost=decision_cost,
        movement_cost=movement_cost,
        movement_distance=movement_distance,
        final_truth_probability=float(posterior[truth_mode]),
        final_entropy=_entropy(posterior),
        brier_score=float(np.sum((posterior - truth_vector) ** 2)),
        log_loss=float(-math.log(max(float(posterior[truth_mode]), 1e-15))),
        mean_confidence=float(np.mean(confidences)),
        hold_actions=action_trace.count("hold"),
        spread_actions=action_trace.count("spread"),
        probe_actions=sum(action.startswith("probe_") for action in action_trace),
        unique_probe_actions=len(probe_labels),
        first_action=action_trace[0],
        action_trace="|".join(action_trace),
        planner_horizon=horizon_by_policy[policy],
        planning_sequences_evaluated=planning_sequences_evaluated,
        runtime_seconds=perf_counter() - started,
        trace_fingerprint=fingerprint,
    )


def _worker(
    task: tuple[
        dict[str, object], dict[str, object], str, int
    ]
) -> dict[str, object]:
    config_data, scenario_data, policy, seed = task
    config = ActiveSensingConfig(**config_data)
    scenario = ActiveSensingScenario(**scenario_data)
    return run_active_sensing_trial(config, scenario, policy, seed).to_dict()


def _numeric(value: object) -> float:
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return float(value.lower() == "true")
    return float(value)


SUMMARY_METRICS = (
    "resolved",
    "resolution_steps",
    "wrong_selection",
    "total_decision_loss",
    "decision_cost",
    "movement_cost",
    "movement_distance",
    "final_truth_probability",
    "final_entropy",
    "brier_score",
    "log_loss",
    "mean_confidence",
    "hold_actions",
    "spread_actions",
    "probe_actions",
    "unique_probe_actions",
    "planning_sequences_evaluated",
    "runtime_seconds",
)


def _summarize_group(group: list[dict[str, object]]) -> dict[str, object]:
    item: dict[str, object] = {"runs": len(group)}
    for metric in SUMMARY_METRICS:
        values = np.asarray([_numeric(row[metric]) for row in group], dtype=float)
        item[f"{metric}_mean"] = float(np.mean(values))
        item[f"{metric}_std"] = float(np.std(values))
    action_count = np.asarray(
        [
            _numeric(row["hold_actions"])
            + _numeric(row["spread_actions"])
            + _numeric(row["probe_actions"])
            for row in group
        ],
        dtype=float,
    )
    for action_kind in ("hold_actions", "spread_actions", "probe_actions"):
        values = np.asarray([_numeric(row[action_kind]) for row in group], dtype=float)
        item[f"{action_kind}_fraction"] = float(
            np.sum(values) / max(float(np.sum(action_count)), 1.0)
        )
    return item


def _summaries(
    rows: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    scenario_groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    policy_groups: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        scenario_groups.setdefault(
            (str(row["scenario"]), str(row["policy"])), []
        ).append(row)
        policy_groups.setdefault(str(row["policy"]), []).append(row)
    scenario_summaries: list[dict[str, object]] = []
    for (scenario, policy), group in scenario_groups.items():
        item = {"scenario": scenario, "policy": policy}
        item.update(_summarize_group(group))
        scenario_summaries.append(item)
    policy_summaries: list[dict[str, object]] = []
    for policy, group in policy_groups.items():
        item = {"policy": policy}
        item.update(_summarize_group(group))
        policy_summaries.append(item)
    return scenario_summaries, policy_summaries


EFFECT_METRICS = {
    "total_decision_loss": "lower",
    "decision_cost": "lower",
    "movement_cost": "lower",
    "resolution_steps": "lower",
    "wrong_selection": "lower",
    "brier_score": "lower",
    "log_loss": "lower",
    "final_truth_probability": "higher",
}


def _effects(
    rows: list[dict[str, object]],
    scenarios: Sequence[ActiveSensingScenario],
    seeds: list[int],
    bootstrap_samples: int,
) -> list[dict[str, object]]:
    indexed = {
        (str(row["scenario"]), str(row["policy"]), int(row["seed"])): row
        for row in rows
    }
    rng = np.random.default_rng(20260726)
    effects: list[dict[str, object]] = []
    comparisons = [
        (candidate, baseline)
        for baseline in ("passive", "round_robin", "myopic_voi")
        for candidate in POLICIES
        if candidate != baseline
    ]
    scopes: list[tuple[str, tuple[str, ...]]] = [
        (scenario.name, (scenario.name,)) for scenario in scenarios
    ] + [("overall", tuple(scenario.name for scenario in scenarios))]
    for scope, scenario_names in scopes:
        for candidate, baseline in comparisons:
            for metric, direction in EFFECT_METRICS.items():
                baseline_values: list[float] = []
                candidate_values: list[float] = []
                for seed in seeds:
                    baseline_values.append(
                        float(
                            np.mean(
                                [
                                    _numeric(indexed[(name, baseline, seed)][metric])
                                    for name in scenario_names
                                ]
                            )
                        )
                    )
                    candidate_values.append(
                        float(
                            np.mean(
                                [
                                    _numeric(indexed[(name, candidate, seed)][metric])
                                    for name in scenario_names
                                ]
                            )
                        )
                    )
                baseline_array = np.asarray(baseline_values, dtype=float)
                candidate_array = np.asarray(candidate_values, dtype=float)
                improvement = (
                    baseline_array - candidate_array
                    if direction == "lower"
                    else candidate_array - baseline_array
                )
                lower, upper = _bootstrap_interval(
                    improvement, bootstrap_samples, rng
                )
                effects.append(
                    {
                        "scope": scope,
                        "candidate": candidate,
                        "baseline": baseline,
                        "metric": metric,
                        "direction": direction,
                        "pairs": len(seeds),
                        "baseline_mean": float(np.mean(baseline_array)),
                        "candidate_mean": float(np.mean(candidate_array)),
                        "improvement_mean": float(np.mean(improvement)),
                        "ci95_lower": lower,
                        "ci95_upper": upper,
                        "wins": int(np.sum(improvement > 1e-12)),
                        "ties": int(np.sum(np.abs(improvement) <= 1e-12)),
                        "losses": int(np.sum(improvement < -1e-12)),
                    }
                )
    return effects


def _decision(
    scenario_summaries: list[dict[str, object]],
    policy_summaries: list[dict[str, object]],
    effects: list[dict[str, object]],
    replay_verified: bool,
) -> dict[str, object]:
    summary = {str(row["policy"]): row for row in policy_summaries}
    effect = {
        (
            str(row["scope"]),
            str(row["candidate"]),
            str(row["baseline"]),
            str(row["metric"]),
        ): row
        for row in effects
    }

    def overall(candidate: str, baseline: str, metric: str) -> dict[str, object]:
        return effect[("overall", candidate, baseline, metric)]

    receding_current = overall(
        "receding_horizon_voi", "round_robin", "total_decision_loss"
    )
    receding_passive = overall(
        "receding_horizon_voi", "passive", "total_decision_loss"
    )
    receding_myopic = overall(
        "receding_horizon_voi", "myopic_voi", "total_decision_loss"
    )
    oracle_passive = overall(
        "computational_oracle", "passive", "total_decision_loss"
    )
    receding_movement = overall(
        "receding_horizon_voi", "round_robin", "movement_cost"
    )
    receding = summary["receding_horizon_voi"]
    current = summary["round_robin"]
    oracle = summary["computational_oracle"]
    passive = summary["passive"]
    receding_scenarios = [
        row
        for row in scenario_summaries
        if str(row["policy"]) == "receding_horizon_voi"
    ]
    oracle_scenarios = [
        row
        for row in scenario_summaries
        if str(row["policy"]) == "computational_oracle"
    ]
    scenario_scopes = sorted(
        {
            str(row["scope"])
            for row in effects
            if str(row["scope"]) != "overall"
        }
    )
    current_scenario_wins = sum(
        float(
            effect[
                (
                    scope,
                    "receding_horizon_voi",
                    "round_robin",
                    "total_decision_loss",
                )
            ]["ci95_lower"]
        )
        > 0.0
        for scope in scenario_scopes
    )
    gates = {
        "passive_control_remains_ambiguous": (
            float(passive["resolved_mean"]) <= 0.05
            and float(passive["probe_actions_fraction"]) <= 1e-12
            and float(passive["spread_actions_fraction"]) <= 1e-12
        ),
        "finite_horizon_oracle_has_attainable_gain": (
            float(oracle_passive["ci95_lower"]) > 0.0
            and all(float(row["resolved_mean"]) >= 0.90 for row in oracle_scenarios)
            and all(
                float(row["wrong_selection_mean"]) <= 0.05
                for row in oracle_scenarios
            )
        ),
        "receding_voi_beats_current_allocator": float(
            receding_current["ci95_lower"]
        )
        > 0.0,
        "receding_voi_beats_passive": float(receding_passive["ci95_lower"]) > 0.0,
        "nonmyopic_planning_beats_myopic": float(receding_myopic["ci95_lower"]) > 0.0,
        "receding_voi_resolves_safely": (
            all(float(row["resolved_mean"]) >= 0.90 for row in receding_scenarios)
            and all(
                float(row["wrong_selection_mean"]) <= 0.05
                for row in receding_scenarios
            )
        ),
        "allocator_gain_generalizes_across_tasks": current_scenario_wins
        >= max(1, len(scenario_scopes) - 1),
        "receding_voi_is_calibrated_noninferior": (
            float(receding["brier_score_mean"])
            <= float(current["brier_score_mean"]) + 0.02
            and float(receding["log_loss_mean"])
            <= float(current["log_loss_mean"]) + 0.05
        ),
        "receding_voi_reduces_movement_cost": float(
            receding_movement["ci95_lower"]
        )
        >= 0.0,
        "competing_view_policy_is_identified": (
            float(receding["probe_actions_fraction"]) >= 0.20
            and float(receding["spread_actions_fraction"])
            <= float(current["spread_actions_fraction"]) - 0.20
        ),
        "runtime_is_bounded": float(receding["runtime_seconds_mean"]) <= 2.0,
        "trace_replay_verified": replay_verified,
    }
    validity_gates = (
        "passive_control_remains_ambiguous",
        "finite_horizon_oracle_has_attainable_gain",
        "trace_replay_verified",
    )
    promotion_gates = tuple(gate for gate in gates if gate not in validity_gates)
    if not all(gates[gate] for gate in validity_gates):
        verdict = "INVALID-ASSAY"
        direction = "REDESIGN_M9B_TASK_BEFORE_INTERPRETATION"
    elif all(gates[gate] for gate in promotion_gates):
        verdict = "M9B-GO"
        direction = "ADVANCE_VOI_TO_PRODUCTION_STACK_INTEGRATION_AFTER_M9A"
    elif gates["receding_voi_beats_current_allocator"] and gates[
        "receding_voi_resolves_safely"
    ]:
        verdict = "M9B-PARTIAL-GO"
        direction = "RETAIN_AS_BOUNDED_ASSAY_AND_FIX_FAILED_GATES"
    else:
        verdict = "M9B-NO-GO"
        direction = "DO_NOT_INTEGRATE_VOI_INTO_PRODUCTION_STACK"
    return {
        "verdict": verdict,
        "research_direction": direction,
        "gates": gates,
        "receding_vs_current_decision_loss_improvement": float(
            receding_current["improvement_mean"]
        ),
        "receding_vs_current_decision_loss_ci95": [
            float(receding_current["ci95_lower"]),
            float(receding_current["ci95_upper"]),
        ],
        "receding_vs_myopic_decision_loss_improvement": float(
            receding_myopic["improvement_mean"]
        ),
        "receding_vs_myopic_decision_loss_ci95": [
            float(receding_myopic["ci95_lower"]),
            float(receding_myopic["ci95_upper"]),
        ],
        "receding_vs_current_movement_cost_improvement": float(
            receding_movement["improvement_mean"]
        ),
        "receding_vs_current_movement_cost_ci95": [
            float(receding_movement["ci95_lower"]),
            float(receding_movement["ci95_upper"]),
        ],
        "oracle_decision_loss": float(oracle["total_decision_loss_mean"]),
        "receding_decision_loss": float(receding["total_decision_loss_mean"]),
        "current_decision_loss": float(current["total_decision_loss_mean"]),
        "passive_decision_loss": float(passive["total_decision_loss_mean"]),
        "current_allocator_scenario_wins": current_scenario_wins,
        "scenario_count": len(scenario_scopes),
    }


def _write_report(
    path: Path,
    decision: dict[str, object],
    scenario_summaries: list[dict[str, object]],
    policy_summaries: list[dict[str, object]],
    effects: list[dict[str, object]],
    seed_start: int,
    seed_count: int,
) -> None:
    effect = {
        (
            str(row["scope"]),
            str(row["candidate"]),
            str(row["baseline"]),
            str(row["metric"]),
        ): row
        for row in effects
    }
    lines = [
        "# M9B Decision-Relevant Active-Sensing Report",
        "",
        f"**Verdict: {decision['verdict']}**",
        "",
        f"**Research direction: {decision['research_direction']}**",
        "",
        (
            f"The suite uses {seed_count} paired seeds "
            f"({seed_start}–{seed_start + seed_count - 1}) per scenario. All policies "
            "receive the same truth draw and standardized range noise. The oracle is a "
            "truth-blind exhaustive finite-horizon action-sequence comparator, not a "
            "clairvoyant policy."
        ),
        "",
        "## Gates",
        "",
        "| Gate | Result |",
        "|---|---|",
    ]
    for gate, passed in dict(decision["gates"]).items():
        lines.append(f"| {gate.replace('_', ' ')} | {'PASS' if passed else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## Overall policy results",
            "",
            "| Policy | Resolved | Wrong | Resolution | Loss | Decision | Movement cost | Brier | Probe fraction | Spread fraction | Runtime |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    order = {policy: index for index, policy in enumerate(POLICIES)}
    for row in sorted(policy_summaries, key=lambda item: order[str(item["policy"])]):
        lines.append(
            f"| {row['policy']} | {float(row['resolved_mean']):.3f} | "
            f"{float(row['wrong_selection_mean']):.3f} | "
            f"{float(row['resolution_steps_mean']):.2f} | "
            f"{float(row['total_decision_loss_mean']):.4f} | "
            f"{float(row['decision_cost_mean']):.4f} | "
            f"{float(row['movement_cost_mean']):.4f} | "
            f"{float(row['brier_score_mean']):.4f} | "
            f"{float(row['probe_actions_fraction']):.3f} | "
            f"{float(row['spread_actions_fraction']):.3f} | "
            f"{float(row['runtime_seconds_mean']):.4f} |"
        )
    lines.extend(
        [
            "",
            "## Receding-horizon effects",
            "",
            "| Baseline | Scope | Movement-inclusive loss improvement | 95% CI |",
            "|---|---|---:|---:|",
        ]
    )
    scenario_names = sorted({str(row["scenario"]) for row in scenario_summaries})
    for baseline in ("passive", "round_robin", "myopic_voi"):
        for scope in ("overall", *scenario_names):
            row = effect[
                (scope, "receding_horizon_voi", baseline, "total_decision_loss")
            ]
            lines.append(
                f"| {baseline} | {scope} | {float(row['improvement_mean']):.4f} | "
                f"[{float(row['ci95_lower']):.4f}, {float(row['ci95_upper']):.4f}] |"
            )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "M9B tests decision-relevant view allocation in a static, centralized Bayesian "
            "mode-classification assay. It does not repair the M8 dynamic-topology failure, "
            "does not establish decentralized execution, and cannot enter the production "
            "stack until M9A qualifies outage/rejoin and partition uncertainty.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _select_scenarios(
    scenario_names: Iterable[str] | None,
) -> tuple[ActiveSensingScenario, ...]:
    requested = set(scenario_names) if scenario_names is not None else None
    known = {scenario.name for scenario in DEFAULT_ACTIVE_SENSING_SCENARIOS}
    if requested is not None and requested - known:
        raise ValueError(
            f"unknown M9B scenarios: {', '.join(sorted(requested - known))}"
        )
    scenarios = tuple(
        scenario
        for scenario in DEFAULT_ACTIVE_SENSING_SCENARIOS
        if requested is None or scenario.name in requested
    )
    if not scenarios:
        raise ValueError("at least one M9B scenario is required")
    return scenarios


def run_active_sensing_decision_suite(
    config: ActiveSensingConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 100,
    seed_start: int = 10000,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
    scenario_names: Iterable[str] | None = None,
) -> dict[str, object]:
    """Run the paired M9B competing-view decision suite."""
    config.validate()
    if seed_count < 2 or bootstrap_samples < 100:
        raise ValueError("M9B needs at least two seeds and 100 bootstrap samples")
    scenarios = _select_scenarios(scenario_names)
    for scenario in scenarios:
        scenario.validate()
    seeds = list(range(seed_start, seed_start + seed_count))
    config_data = asdict(config)
    tasks = [
        (config_data, asdict(scenario), policy, seed)
        for scenario in scenarios
        for policy in POLICIES
        for seed in seeds
    ]
    worker_count = workers or min(os.cpu_count() or 2, 8)
    executor_kind = "serial"
    if worker_count == 1:
        rows = [_worker(task) for task in tasks]
    else:
        try:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                rows = list(executor.map(_worker, tasks, chunksize=2))
            executor_kind = "process"
        except (PermissionError, OSError):
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                rows = list(executor.map(_worker, tasks))
            executor_kind = "thread_fallback"
    scenario_order = {scenario.name: index for index, scenario in enumerate(scenarios)}
    policy_order = {policy: index for index, policy in enumerate(POLICIES)}
    rows.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            policy_order[str(row["policy"])],
            int(row["seed"]),
        )
    )
    scenario_summaries, policy_summaries = _summaries(rows)
    scenario_summaries.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])], policy_order[str(row["policy"])]
        )
    )
    policy_summaries.sort(key=lambda row: policy_order[str(row["policy"])] )
    effects = _effects(rows, scenarios, seeds, bootstrap_samples)
    fingerprints = [
        {
            "scenario": scenario.name,
            "seed": seed,
            "fingerprint": active_sensing_fingerprint(config, scenario, seed),
        }
        for scenario in scenarios
        for seed in seeds
    ]
    replay_verified = all(
        entry["fingerprint"]
        == active_sensing_fingerprint(
            config,
            next(s for s in scenarios if s.name == entry["scenario"]),
            int(entry["seed"]),
        )
        for entry in fingerprints
    )
    decision = _decision(
        scenario_summaries, policy_summaries, effects, replay_verified
    )
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "run_summary.csv", rows)
    _write_csv(output / "scenario_summary.csv", scenario_summaries)
    _write_csv(output / "policy_summary.csv", policy_summaries)
    _write_csv(output / "paired_effects.csv", effects)
    (output / "trace_manifest.json").write_text(
        json.dumps(
            {"replay_verified": replay_verified, "entries": fingerprints},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    suite_config = {
        "active_sensing_config": config_data,
        "scenarios": [asdict(scenario) for scenario in scenarios],
        "policies": list(POLICIES),
        "seed_start": seed_start,
        "seed_count": seed_count,
        "bootstrap_samples": bootstrap_samples,
        "workers": worker_count,
        "executor": executor_kind,
        "platform_version": "0.12.0",
        "python": platform.python_version(),
        "numpy": np.__version__,
    }
    (output / "suite_config.json").write_text(
        json.dumps(suite_config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_report(
        output / "milestone9b_report.md",
        decision,
        scenario_summaries,
        policy_summaries,
        effects,
        seed_start,
        seed_count,
    )
    return decision


def reanalyze_active_sensing_decision_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    """Recompute M9B statistics, gates, report, and deterministic replay."""
    output = Path(output_directory)
    suite_config = json.loads((output / "suite_config.json").read_text(encoding="utf-8"))
    config = ActiveSensingConfig(**suite_config["active_sensing_config"])
    scenarios = tuple(
        ActiveSensingScenario(**scenario) for scenario in suite_config["scenarios"]
    )
    with (output / "run_summary.csv").open(encoding="utf-8", newline="") as handle:
        rows = [
            {key: (None if value == "" else value) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]
    seed_start = int(suite_config["seed_start"])
    seed_count = int(suite_config["seed_count"])
    seeds = list(range(seed_start, seed_start + seed_count))
    samples = int(bootstrap_samples or suite_config["bootstrap_samples"])
    scenario_summaries, policy_summaries = _summaries(rows)
    scenario_order = {scenario.name: index for index, scenario in enumerate(scenarios)}
    policy_order = {policy: index for index, policy in enumerate(POLICIES)}
    scenario_summaries.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])], policy_order[str(row["policy"])]
        )
    )
    policy_summaries.sort(key=lambda row: policy_order[str(row["policy"])] )
    effects = _effects(rows, scenarios, seeds, samples)
    scenario_by_name = {scenario.name: scenario for scenario in scenarios}
    replay_verified = all(
        str(row["trace_fingerprint"])
        == active_sensing_fingerprint(
            config, scenario_by_name[str(row["scenario"])], int(row["seed"])
        )
        for row in rows
    )
    decision = _decision(
        scenario_summaries, policy_summaries, effects, replay_verified
    )
    _write_csv(output / "scenario_summary.csv", scenario_summaries)
    _write_csv(output / "policy_summary.csv", policy_summaries)
    _write_csv(output / "paired_effects.csv", effects)
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_report(
        output / "milestone9b_report.md",
        decision,
        scenario_summaries,
        policy_summaries,
        effects,
        seed_start,
        seed_count,
    )
    return decision
