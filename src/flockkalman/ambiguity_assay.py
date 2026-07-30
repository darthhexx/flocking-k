"""Endogenous-ambiguity positive control for active sensing (M8.1)."""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import asdict, dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import platform
from typing import Iterable

import numpy as np
from numpy.typing import NDArray

from .suite import _bootstrap_interval, _write_csv


FloatArray = NDArray[np.float64]
POLICIES = ("passive", "round_robin", "information_oracle", "value_of_information")
DEFAULT_DOSES = (0.0, 0.10, 0.25, 0.50, 1.0)


@dataclass(frozen=True, slots=True)
class AmbiguityAssayConfig:
    """Parameters for a binary, geometry-identifiable sensing problem."""

    steps: int = 30
    dt: float = 1.0
    n_agents: int = 8
    hypothesis_positions: tuple[tuple[float, float], tuple[float, float]] = (
        (-5.0, 0.0),
        (5.0, 0.0),
    )
    initial_sensor_y_span: float = 8.0
    measurement_std: float = 0.80
    sensor_max_speed: float = 1.50
    fixed_momentum: float = 0.72
    selection_probability: float = 0.95
    defer_cost: float = 0.20
    wrong_selection_cost: float = 1.0
    movement_cost_per_unit: float = 0.01
    quadrature_points: int = 25

    def validate(self) -> None:
        if self.steps < 3 or self.n_agents < 2:
            raise ValueError("the assay needs at least three steps and two agents")
        if self.dt <= 0.0 or self.initial_sensor_y_span <= 0.0:
            raise ValueError("time and initial geometry scales must be positive")
        if self.measurement_std <= 0.0 or self.sensor_max_speed <= 0.0:
            raise ValueError("sensor noise and speed must be positive")
        if not 0.0 <= self.fixed_momentum < 1.0:
            raise ValueError("fixed_momentum must be in [0, 1)")
        if not 0.5 < self.selection_probability < 1.0:
            raise ValueError("selection_probability must be in (0.5, 1)")
        if min(
            self.defer_cost,
            self.wrong_selection_cost,
            self.movement_cost_per_unit,
        ) < 0.0:
            raise ValueError("decision and movement costs cannot be negative")
        hypotheses = np.asarray(self.hypothesis_positions, dtype=float)
        if hypotheses.shape != (2, 2) or np.allclose(hypotheses[0], hypotheses[1]):
            raise ValueError("exactly two distinct two-dimensional hypotheses are required")
        if self.quadrature_points < 5:
            raise ValueError("quadrature_points must be at least five")


@dataclass(frozen=True, slots=True)
class AssayRun:
    seed: int
    policy: str
    dose: float
    truth_mode: int
    resolved: bool
    resolution_steps: int
    selected_mode: int
    wrong_selection: bool
    total_decision_loss: float
    decision_cost: float
    movement_cost: float
    movement_distance: float
    mean_discriminability: float
    maximum_discriminability: float
    final_truth_probability: float
    final_entropy: float
    trace_fingerprint: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _scenario(config: AmbiguityAssayConfig, seed: int) -> tuple[int, FloatArray, str]:
    rng = np.random.default_rng(seed)
    truth_mode = int(rng.integers(0, 2))
    normals = rng.normal(size=(config.steps, config.n_agents))
    digest = hashlib.sha256()
    digest.update(
        json.dumps(asdict(config), sort_keys=True, separators=(",", ":")).encode("utf-8")
    )
    digest.update(str(seed).encode("ascii"))
    digest.update(str(truth_mode).encode("ascii"))
    digest.update(np.ascontiguousarray(normals).tobytes())
    return truth_mode, normals, digest.hexdigest()


def assay_fingerprint(config: AmbiguityAssayConfig, seed: int) -> str:
    """Return the deterministic exogenous-trace fingerprint."""
    config.validate()
    return _scenario(config, seed)[2]


def _initial_positions(config: AmbiguityAssayConfig) -> FloatArray:
    # Both hypotheses have identical range from every point on x=0.
    y_positions = np.linspace(
        -0.5 * config.initial_sensor_y_span,
        0.5 * config.initial_sensor_y_span,
        config.n_agents,
    )
    return np.column_stack((np.zeros(config.n_agents), y_positions))


def _posterior_one(log_odds: float) -> float:
    clipped = float(np.clip(log_odds, -60.0, 60.0))
    return 1.0 / (1.0 + math.exp(-clipped))


def _entropy(probability_one: float) -> float:
    probability_one = float(np.clip(probability_one, 1e-15, 1.0 - 1e-15))
    return -(
        probability_one * math.log(probability_one)
        + (1.0 - probability_one) * math.log(1.0 - probability_one)
    )


def _measurement_means(positions: FloatArray, hypotheses: FloatArray) -> FloatArray:
    return np.asarray(
        [np.linalg.norm(positions - hypothesis, axis=1) for hypothesis in hypotheses],
        dtype=float,
    )


def _discriminability(
    positions: FloatArray,
    hypotheses: FloatArray,
    measurement_std: float,
) -> float:
    means = _measurement_means(positions, hypotheses)
    return float(np.sum((means[1] - means[0]) ** 2) / (2.0 * measurement_std**2))


def _desired_velocity(
    config: AmbiguityAssayConfig,
    positions: FloatArray,
    hypotheses: FloatArray,
    pattern: str,
    dose: float,
) -> FloatArray:
    if pattern == "hold" or dose <= 0.0:
        return np.zeros_like(positions)
    if pattern == "positive":
        goals = np.repeat(hypotheses[1][np.newaxis, :], config.n_agents, axis=0)
    elif pattern == "negative":
        goals = np.repeat(hypotheses[0][np.newaxis, :], config.n_agents, axis=0)
    elif pattern == "split":
        goals = np.asarray(
            [hypotheses[index % 2] for index in range(config.n_agents)], dtype=float
        )
    else:
        raise ValueError(f"unknown motion pattern: {pattern}")
    delta = goals - positions
    norms = np.linalg.norm(delta, axis=1)
    directions = np.divide(
        delta,
        norms[:, np.newaxis],
        out=np.zeros_like(delta),
        where=norms[:, np.newaxis] > 1e-12,
    )
    return directions * (dose * config.sensor_max_speed)


def _candidate_motion(
    config: AmbiguityAssayConfig,
    positions: FloatArray,
    velocities: FloatArray,
    hypotheses: FloatArray,
    pattern: str,
    dose: float,
) -> tuple[FloatArray, FloatArray, float]:
    desired = _desired_velocity(config, positions, hypotheses, pattern, dose)
    next_velocities = (
        config.fixed_momentum * velocities
        + (1.0 - config.fixed_momentum) * desired
    )
    maximum = max(dose * config.sensor_max_speed, 1e-12)
    speeds = np.linalg.norm(next_velocities, axis=1)
    next_velocities = np.divide(
        next_velocities,
        np.maximum(1.0, speeds / maximum)[:, np.newaxis],
    )
    displacement = next_velocities * config.dt
    return positions + displacement, next_velocities, float(
        np.mean(np.linalg.norm(displacement, axis=1))
    )


def _instantaneous_risk(
    config: AmbiguityAssayConfig,
    log_odds: FloatArray | float,
    truth_mode: int,
) -> FloatArray:
    values = np.asarray(log_odds, dtype=float)
    probability_one = 1.0 / (1.0 + np.exp(-np.clip(values, -60.0, 60.0)))
    confidence = np.maximum(probability_one, 1.0 - probability_one)
    selected = (probability_one >= 0.5).astype(np.int64)
    return np.where(
        confidence >= config.selection_probability,
        (selected != truth_mode).astype(float) * config.wrong_selection_cost,
        config.defer_cost,
    )


def _expected_next_risk(
    config: AmbiguityAssayConfig,
    log_odds: float,
    discriminability: float,
) -> float:
    """Integrate one-step Bayes decision risk over the binary Gaussian model."""
    probability_one = _posterior_one(log_odds)
    if discriminability <= 1e-14:
        return float(
            (1.0 - probability_one) * _instantaneous_risk(config, log_odds, 0)
            + probability_one * _instantaneous_risk(config, log_odds, 1)
        )
    nodes, weights = np.polynomial.hermite.hermgauss(config.quadrature_points)
    standard_deviation = math.sqrt(2.0 * discriminability)
    total = 0.0
    for truth_mode, prior in ((0, 1.0 - probability_one), (1, probability_one)):
        mean = log_odds + (-discriminability if truth_mode == 0 else discriminability)
        samples = mean + math.sqrt(2.0) * standard_deviation * nodes
        losses = _instantaneous_risk(config, samples, truth_mode)
        total += prior * float(np.dot(weights, losses) / math.sqrt(math.pi))
    return total


def _choose_pattern(
    config: AmbiguityAssayConfig,
    policy: str,
    dose: float,
    positions: FloatArray,
    velocities: FloatArray,
    hypotheses: FloatArray,
    log_odds: float,
) -> str:
    if policy == "passive":
        return "hold"
    if policy == "round_robin":
        return "split"
    candidates = ("split", "positive", "negative", "hold")
    scored: list[tuple[float, int, str]] = []
    for order, pattern in enumerate(candidates):
        next_positions, _, movement = _candidate_motion(
            config, positions, velocities, hypotheses, pattern, dose
        )
        discriminability = _discriminability(
            next_positions, hypotheses, config.measurement_std
        )
        if policy == "information_oracle":
            score = -discriminability
        elif policy == "value_of_information":
            score = _expected_next_risk(config, log_odds, discriminability)
            score += config.movement_cost_per_unit * movement
        else:
            raise ValueError(f"unknown policy: {policy}")
        scored.append((score, order, pattern))
    return min(scored)[2]


def run_ambiguity_assay(
    config: AmbiguityAssayConfig,
    policy: str,
    seed: int,
    *,
    dose: float = 1.0,
) -> AssayRun:
    """Run one deterministic binary active-sensing assay."""
    config.validate()
    if policy not in POLICIES:
        raise ValueError(f"unknown ambiguity-assay policy: {policy}")
    if not 0.0 <= dose <= 2.0:
        raise ValueError("dose must be in [0, 2]")
    truth_mode, normals, fingerprint = _scenario(config, seed)
    hypotheses = np.asarray(config.hypothesis_positions, dtype=float)
    positions = _initial_positions(config)
    velocities = np.zeros_like(positions)
    log_odds = 0.0
    decision_cost = 0.0
    movement_distance = 0.0
    discriminabilities: list[float] = []
    selected_mode = -1
    resolved = False
    resolution_steps = config.steps

    for step in range(config.steps):
        pattern = _choose_pattern(
            config,
            policy,
            dose,
            positions,
            velocities,
            hypotheses,
            log_odds,
        )
        positions, velocities, movement = _candidate_motion(
            config, positions, velocities, hypotheses, pattern, dose
        )
        movement_distance += movement
        means = _measurement_means(positions, hypotheses)
        discriminability = float(
            np.sum((means[1] - means[0]) ** 2)
            / (2.0 * config.measurement_std**2)
        )
        discriminabilities.append(discriminability)
        observations = means[truth_mode] + config.measurement_std * normals[step]
        log_odds += float(
            np.sum((observations - means[0]) ** 2 - (observations - means[1]) ** 2)
            / (2.0 * config.measurement_std**2)
        )
        probability_one = _posterior_one(log_odds)
        confidence = max(probability_one, 1.0 - probability_one)
        if confidence >= config.selection_probability:
            selected_mode = int(probability_one >= 0.5)
            decision_cost += (
                config.wrong_selection_cost if selected_mode != truth_mode else 0.0
            )
            resolved = True
            resolution_steps = step + 1
            break
        decision_cost += config.defer_cost

    final_probability_one = _posterior_one(log_odds)
    movement_cost = config.movement_cost_per_unit * movement_distance
    return AssayRun(
        seed=seed,
        policy=policy,
        dose=dose,
        truth_mode=truth_mode,
        resolved=resolved,
        resolution_steps=resolution_steps,
        selected_mode=selected_mode,
        wrong_selection=resolved and selected_mode != truth_mode,
        total_decision_loss=decision_cost + movement_cost,
        decision_cost=decision_cost,
        movement_cost=movement_cost,
        movement_distance=movement_distance,
        mean_discriminability=float(np.mean(discriminabilities)),
        maximum_discriminability=float(np.max(discriminabilities)),
        final_truth_probability=(
            final_probability_one if truth_mode == 1 else 1.0 - final_probability_one
        ),
        final_entropy=_entropy(final_probability_one),
        trace_fingerprint=fingerprint,
    )


def _arm_name(policy: str, dose: float) -> str:
    if policy == "round_robin":
        return f"round_robin_dose_{dose:.2f}".replace(".", "_")
    return policy


def _worker(task: tuple[dict[str, object], str, float, int]) -> dict[str, object]:
    config_data, policy, dose, seed = task
    config = AmbiguityAssayConfig(**config_data)
    row = run_ambiguity_assay(config, policy, seed, dose=dose).to_dict()
    row["arm"] = _arm_name(policy, dose)
    return row


def _numeric(value: object) -> float:
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return float(value.lower() == "true")
    return float(value)


def _summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(str(row["arm"]), []).append(row)
    metrics = (
        "resolved",
        "resolution_steps",
        "wrong_selection",
        "total_decision_loss",
        "decision_cost",
        "movement_cost",
        "movement_distance",
        "mean_discriminability",
        "maximum_discriminability",
        "final_truth_probability",
        "final_entropy",
    )
    summaries: list[dict[str, object]] = []
    for arm, group in grouped.items():
        item: dict[str, object] = {
            "arm": arm,
            "policy": str(group[0]["policy"]),
            "dose": float(group[0]["dose"]),
            "runs": len(group),
        }
        for metric in metrics:
            values = np.asarray([_numeric(row[metric]) for row in group], dtype=float)
            item[f"{metric}_mean"] = float(np.mean(values))
            item[f"{metric}_std"] = float(np.std(values))
        summaries.append(item)
    return summaries


def _effects(
    rows: list[dict[str, object]],
    seeds: list[int],
    bootstrap_samples: int,
) -> list[dict[str, object]]:
    indexed = {(str(row["arm"]), int(row["seed"])): row for row in rows}
    arms = sorted({str(row["arm"]) for row in rows if row["arm"] != "passive"})
    metrics = {
        "total_decision_loss": "lower",
        "resolution_steps": "lower",
        "mean_discriminability": "higher",
        "final_truth_probability": "higher",
    }
    rng = np.random.default_rng(20260723)
    effects: list[dict[str, object]] = []
    for arm in arms:
        for metric, direction in metrics.items():
            baseline = np.asarray(
                [float(indexed[("passive", seed)][metric]) for seed in seeds]
            )
            candidate = np.asarray(
                [float(indexed[(arm, seed)][metric]) for seed in seeds]
            )
            improvement = baseline - candidate if direction == "lower" else candidate - baseline
            lower, upper = _bootstrap_interval(improvement, bootstrap_samples, rng)
            effects.append(
                {
                    "candidate": arm,
                    "baseline": "passive",
                    "metric": metric,
                    "direction": direction,
                    "pairs": len(seeds),
                    "baseline_mean": float(np.mean(baseline)),
                    "candidate_mean": float(np.mean(candidate)),
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
    summaries: list[dict[str, object]],
    effects: list[dict[str, object]],
    doses: tuple[float, ...],
    replay_verified: bool,
) -> dict[str, object]:
    summary = {str(row["arm"]): row for row in summaries}
    effect = {
        (str(row["candidate"]), str(row["metric"])): row for row in effects
    }
    oracle_loss = effect[("information_oracle", "total_decision_loss")]
    oracle_resolution = effect[("information_oracle", "resolution_steps")]
    voi_loss = effect[("value_of_information", "total_decision_loss")]
    dose_arms = [_arm_name("round_robin", dose) for dose in doses]
    active_loss_passes = [
        float(effect[(arm, "total_decision_loss")]["ci95_lower"]) > 0.0
        for arm in dose_arms
        if float(summary[arm]["dose"]) > 0.0
    ]
    dose_values = np.asarray([float(summary[arm]["dose"]) for arm in dose_arms])
    discrimination_values = np.asarray(
        [float(summary[arm]["mean_discriminability_mean"]) for arm in dose_arms]
    )
    dose_correlation = float(np.corrcoef(dose_values, discrimination_values)[0, 1])
    gates = {
        "passive_control_remains_ambiguous": (
            float(summary["passive"]["resolved_mean"]) <= 0.05
            and float(summary["passive"]["mean_discriminability_mean"]) <= 1e-10
        ),
        "information_oracle_resolves_safely": (
            float(oracle_loss["ci95_lower"]) > 0.0
            and float(oracle_resolution["ci95_lower"]) > 0.0
            and float(summary["information_oracle"]["resolved_mean"]) >= 0.95
            and float(summary["information_oracle"]["wrong_selection_mean"]) <= 0.02
        ),
        "dose_materially_changes_discriminability": (
            dose_correlation >= 0.80
            and float(discrimination_values[-1]) > float(discrimination_values[0]) + 0.25
        ),
        "current_allocator_has_a_positive_dose": any(active_loss_passes),
        "value_of_information_reduces_decision_loss": float(voi_loss["ci95_lower"]) > 0.0,
        "trace_replay_verified": replay_verified,
    }
    if not gates["passive_control_remains_ambiguous"] or not gates[
        "information_oracle_resolves_safely"
    ]:
        verdict = "INVALID-POSITIVE-CONTROL"
        direction = "REDESIGN_ASSAY_BEFORE_INTERPRETING_ACTIVE_SENSING"
    elif not gates["dose_materially_changes_discriminability"]:
        verdict = "INVALID-MANIPULATION"
        direction = "INCREASE_OR_REDESIGN_INVESTIGATION_DOSE"
    elif not gates["current_allocator_has_a_positive_dose"] and not gates[
        "value_of_information_reduces_decision_loss"
    ]:
        verdict = "ACTIVE-BRANCH-NO-GO"
        direction = "ARCHIVE_ACTIVE_FLOCKING_BRANCH"
    elif gates["value_of_information_reduces_decision_loss"]:
        verdict = "POSITIVE-CONTROL-PASS"
        direction = "ALLOW_BOUNDED_M9B_VALUE_OF_INFORMATION_RESEARCH"
    else:
        verdict = "ALLOCATOR-ONLY-PASS"
        direction = "CHARACTERIZE_DOSE_BEFORE_VALUE_OF_INFORMATION_REDESIGN"
    return {
        "verdict": verdict,
        "research_direction": direction,
        "gates": gates,
        "dose_correlation_with_discriminability": dose_correlation,
        "oracle_decision_loss_improvement": float(oracle_loss["improvement_mean"]),
        "oracle_decision_loss_ci95": [
            float(oracle_loss["ci95_lower"]),
            float(oracle_loss["ci95_upper"]),
        ],
        "value_of_information_decision_loss_improvement": float(
            voi_loss["improvement_mean"]
        ),
        "value_of_information_decision_loss_ci95": [
            float(voi_loss["ci95_lower"]),
            float(voi_loss["ci95_upper"]),
        ],
    }


def _write_report(
    path: Path,
    decision: dict[str, object],
    summaries: list[dict[str, object]],
    effects: list[dict[str, object]],
    seed_start: int,
    seed_count: int,
) -> None:
    effect = {
        (str(row["candidate"]), str(row["metric"])): row for row in effects
    }
    lines = [
        "# M8.1 Endogenous-Ambiguity Positive-Control Report",
        "",
        f"**Verdict: {decision['verdict']}**",
        "",
        f"**Research direction: {decision['research_direction']}**",
        "",
        (
            f"The assay uses {seed_count} paired seeds ({seed_start}–{seed_start + seed_count - 1}). "
            "Two target hypotheses generate identical range distributions on the initial sensor "
            "bisector, but become distinguishable after lateral sensor motion. Mode support is a "
            "Bayesian likelihood posterior rather than agent headcount."
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
            "## Policy and dose results",
            "",
            "| Arm | Dose | Resolved | Wrong | Resolution | Decision loss | Movement | Discriminability |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summaries:
        lines.append(
            f"| {row['arm']} | {float(row['dose']):.2f} | "
            f"{float(row['resolved_mean']):.3f} | {float(row['wrong_selection_mean']):.3f} | "
            f"{float(row['resolution_steps_mean']):.2f} | "
            f"{float(row['total_decision_loss_mean']):.4f} | "
            f"{float(row['movement_distance_mean']):.3f} | "
            f"{float(row['mean_discriminability_mean']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Decision-loss effects versus passive",
            "",
            "| Candidate | Improvement | 95% CI |",
            "|---|---:|---:|",
        ]
    )
    for arm in sorted({str(row["arm"]) for row in summaries if row["arm"] != "passive"}):
        row = effect[(arm, "total_decision_loss")]
        lines.append(
            f"| {arm} | {float(row['improvement_mean']):.4f} | "
            f"[{float(row['ci95_lower']):.4f}, {float(row['ci95_upper']):.4f}] |"
        )
    lines.extend(
        [
            "",
            "This is a proof-of-identifiability assay, not evidence that the M8 production allocator "
            "works under the realism ladder. Passing permits a bounded value-of-information research "
            "track; it does not reverse the M8 dynamic-topology NO-GO.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_ambiguity_decision_suite(
    config: AmbiguityAssayConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 100,
    seed_start: int = 7000,
    doses: Iterable[float] = DEFAULT_DOSES,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
) -> dict[str, object]:
    """Run the paired M8.1 positive control and dose-response evaluation."""
    config.validate()
    if seed_count < 2 or bootstrap_samples < 100:
        raise ValueError("the suite needs at least two seeds and 100 bootstrap samples")
    dose_tuple = tuple(float(value) for value in doses)
    if not dose_tuple or dose_tuple[0] != 0.0 or any(
        second <= first for first, second in zip(dose_tuple, dose_tuple[1:])
    ):
        raise ValueError("doses must be strictly increasing and start at zero")
    seeds = list(range(seed_start, seed_start + seed_count))
    config_data = asdict(config)
    tasks: list[tuple[dict[str, object], str, float, int]] = []
    for seed in seeds:
        tasks.append((config_data, "passive", 0.0, seed))
        for dose in dose_tuple:
            tasks.append((config_data, "round_robin", dose, seed))
        tasks.append((config_data, "information_oracle", 1.0, seed))
        tasks.append((config_data, "value_of_information", 1.0, seed))
    worker_count = workers or min(os.cpu_count() or 2, 8)
    executor_kind = "serial"
    if worker_count == 1:
        rows = [_worker(task) for task in tasks]
    else:
        try:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                rows = list(executor.map(_worker, tasks, chunksize=8))
            executor_kind = "process"
        except (PermissionError, OSError):
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                rows = list(executor.map(_worker, tasks))
            executor_kind = "thread_fallback"
    arm_order = ["passive"] + [_arm_name("round_robin", dose) for dose in dose_tuple] + [
        "information_oracle",
        "value_of_information",
    ]
    rows.sort(key=lambda row: (arm_order.index(str(row["arm"])), int(row["seed"])))
    summaries = _summaries(rows)
    summaries.sort(key=lambda row: arm_order.index(str(row["arm"])))
    effects = _effects(rows, seeds, bootstrap_samples)
    fingerprints = [
        {"seed": seed, "fingerprint": assay_fingerprint(config, seed)} for seed in seeds
    ]
    replay_verified = all(
        entry["fingerprint"] == assay_fingerprint(config, int(entry["seed"]))
        for entry in fingerprints
    )
    decision = _decision(summaries, effects, dose_tuple, replay_verified)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "run_summary.csv", rows)
    _write_csv(output / "policy_summary.csv", summaries)
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
        "assay_config": config_data,
        "seed_start": seed_start,
        "seed_count": seed_count,
        "doses": list(dose_tuple),
        "bootstrap_samples": bootstrap_samples,
        "workers": worker_count,
        "executor": executor_kind,
        "platform_version": "0.11.0",
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
        output / "milestone8_1_report.md",
        decision,
        summaries,
        effects,
        seed_start,
        seed_count,
    )
    return decision


def reanalyze_ambiguity_decision_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    """Recompute M8.1 evidence and deterministic replay from saved run rows."""
    output = Path(output_directory)
    suite_config = json.loads((output / "suite_config.json").read_text(encoding="utf-8"))
    config = AmbiguityAssayConfig(**suite_config["assay_config"])
    with (output / "run_summary.csv").open(encoding="utf-8", newline="") as handle:
        rows = [
            {key: (None if value == "" else value) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]
    seed_start = int(suite_config["seed_start"])
    seed_count = int(suite_config["seed_count"])
    seeds = list(range(seed_start, seed_start + seed_count))
    doses = tuple(float(value) for value in suite_config["doses"])
    samples = int(bootstrap_samples or suite_config["bootstrap_samples"])
    summaries = _summaries(rows)
    arm_order = ["passive"] + [_arm_name("round_robin", dose) for dose in doses] + [
        "information_oracle",
        "value_of_information",
    ]
    summaries.sort(key=lambda row: arm_order.index(str(row["arm"])))
    effects = _effects(rows, seeds, samples)
    replay_verified = all(
        str(row["trace_fingerprint"]) == assay_fingerprint(config, int(row["seed"]))
        for row in rows
    )
    decision = _decision(summaries, effects, doses, replay_verified)
    _write_csv(output / "policy_summary.csv", summaries)
    _write_csv(output / "paired_effects.csv", effects)
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_report(
        output / "milestone8_1_report.md",
        decision,
        summaries,
        effects,
        seed_start,
        seed_count,
    )
    return decision
