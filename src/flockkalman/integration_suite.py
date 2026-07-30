"""Preregistered M9C dynamic-topology M9A.7/M9B integration experiment."""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import asdict, replace
import hashlib
import json
import math
import os
from pathlib import Path
import platform
from time import perf_counter

import numpy as np

from .admission_evidence import M9A7_ALGORITHM
from .admission_suite import M9A7_ATTACK, M9A7_POSITIVE_CONTROL
from .config import ExperimentConfig
from .experiment import run_trial
from .integrated_sensing import (
    M9C_RECEDING_ALGORITHM,
    M9C_ROUND_ROBIN_ALGORITHM,
)
from .metrics import summarize_run
from .provenance import (
    PRE_M14_COMMIT,
    CURRENT_FINGERPRINT_ALGORITHM,
    ReplayVerification,
    environment_fingerprint,
    replay_verdict_suffix,
    upstream_replay_acceptable,
    verdict_accepted,
    verify_upstream_source,
    verify_replay,
)
from .simulation import scenario_fingerprint
from .suite import ScenarioDefinition, _bootstrap_interval, _write_csv
from .topology_suite import M9A_SCENARIOS, _fit_timing


M9C_ALGORITHMS = (
    M9A7_ALGORITHM,
    M9C_ROUND_ROBIN_ALGORITHM,
    M9C_RECEDING_ALGORITHM,
)

M9C_SOURCE_COMPETITION = ScenarioDefinition(
    "source_assignment_competition",
    "Early, noisy secondary evidence keeps source identity uncertain long enough for allocated close views.",
    {
        "target_change_mode": "none",
        "secondary_mode_agent_count": 4,
        "secondary_mode_offset": (3.0, -2.4),
        "secondary_mode_start_step": 3,
        "secondary_mode_end_step": 80,
        "m9a6_override_declared_model": True,
        "m9a6_model_secondary_count": 4,
        "m9a6_model_secondary_offset": (3.0, -2.4),
        "m9a6_model_secondary_start_step": 3,
        "m9a6_model_secondary_end_step": 80,
        "measurement_base_std": 2.2,
        "measurement_distance_scale": 6.0,
        "measurement_dropout_rate": 0.30,
        "goal_gain": 0.08,
        "m9c_probe_goal_extrapolation": 4.0,
    },
)

M9C_NATURAL_SCENARIOS = M9A_SCENARIOS
M9C_EXACT_SCENARIOS = M9C_NATURAL_SCENARIOS + (
    M9A7_POSITIVE_CONTROL,
    M9C_SOURCE_COMPETITION,
)
M9C_SCENARIOS = M9C_EXACT_SCENARIOS + (M9A7_ATTACK,)

M9C_THRESHOLDS = {
    "tail_event_frequency": 0.02,
    "tail_detection_probability": 0.95,
    "positive_control_round_robin_active_rate_min": 0.03,
    "positive_control_action_difference_rate_min": 0.02,
    "aggregate_voi_improvement_lcb_min": 0.0,
    "positive_control_voi_improvement_lcb_min": 0.0,
    "movement_efficiency_lcb_min": 0.0,
    "natural_noninferiority_lcb_min": -0.03,
    "wrong_mode_action_rate_max": 0.01,
    "mean_nees_max": 6.0,
    "p95_nees_max": 20.0,
    "coverage95_min": 0.88,
    "delivery_ratio_degradation_lcb_min": -0.05,
    "topology_component_increase_max": 0.25,
    "attack_noninferiority_lcb_min": -0.10,
    "attack_active_motion_rate_max": 0.05,
    "attack_absolute_loss_max": 1.50,
}

SUMMARY_METRICS = (
    "integrated_loss",
    "decision_loss",
    "position_rmse",
    "movement_distance",
    "movement_per_step",
    "wrong_mode_action_rate",
    "mean_nees",
    "p95_nees",
    "coverage95_rate",
    "mean_delivery_ratio",
    "mean_topology_components",
    "mean_missing_evidence_residual_mass",
    "investigation_request_rate",
    "investigation_residual_guard_rate",
    "investigation_replan_rate",
    "investigation_active_motion_rate",
    "investigation_probe_rate",
    "mean_investigation_active_agents",
    "mean_investigation_mode_count",
    "investigation_planning_sequences",
    "runtime_seconds",
)

EFFECT_METRICS = {
    "integrated_loss": "lower",
    "decision_loss": "lower",
    "movement_per_step": "lower",
    "wrong_mode_action_rate": "lower",
    "mean_nees": "lower",
    "coverage95_rate": "higher",
    "mean_delivery_ratio": "higher",
    "mean_topology_components": "lower",
}


def _artifact_hash(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def required_tail_seeds(event_frequency: float, detection_probability: float) -> int:
    """Minimum independent trials needed to observe at least one tail event."""
    return math.ceil(
        math.log(1.0 - detection_probability) / math.log(1.0 - event_frequency)
    )


def _scenario_config(
    base_config: ExperimentConfig,
    scenario: ScenarioDefinition,
) -> ExperimentConfig:
    overrides = _fit_timing(scenario.overrides, base_config.steps)
    if bool(overrides.get("m9a6_override_declared_model", False)):
        overrides["m9a6_model_secondary_start_step"] = overrides[
            "secondary_mode_start_step"
        ]
        overrides["m9a6_model_secondary_end_step"] = overrides[
            "secondary_mode_end_step"
        ]
    return replace(base_config, algorithms=list(M9C_ALGORITHMS), **overrides)


def _worker(task: tuple[str, dict[str, object], int]) -> list[dict[str, object]]:
    scenario_name, config_data, seed = task
    config = ExperimentConfig(**config_data)
    fingerprint = scenario_fingerprint(
        config, seed, algorithm=CURRENT_FINGERPRINT_ALGORITHM
    )
    rows: list[dict[str, object]] = []
    for algorithm in M9C_ALGORITHMS:
        started = perf_counter()
        records = run_trial(config, algorithm, seed)
        summary = summarize_run(config, records)
        movement_per_step = float(summary["movement_distance"]) / config.steps
        row: dict[str, object] = {
            "scenario": scenario_name,
            "seed": seed,
            "algorithm": algorithm,
            "integrated_loss": (
                float(summary["decision_loss"])
                + config.m9c_movement_cost_per_unit * movement_per_step
            ),
            "movement_per_step": movement_per_step,
            "runtime_seconds": perf_counter() - started,
            "trace_fingerprint": fingerprint,
            "investigation_action_trace": "|".join(
                record.investigation_motion_action for record in records
            ),
        }
        for metric in SUMMARY_METRICS:
            if metric not in row and metric in summary:
                row[metric] = summary[metric]
        rows.append(row)
    return rows


def _scenario_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(
            (str(row["scenario"]), str(row["algorithm"])), []
        ).append(row)
    result: list[dict[str, object]] = []
    for (scenario, algorithm), group in grouped.items():
        item: dict[str, object] = {
            "scenario": scenario,
            "algorithm": algorithm,
            "runs": len(group),
        }
        for metric in SUMMARY_METRICS:
            values = np.asarray([float(row[metric]) for row in group], dtype=float)
            item[f"{metric}_mean"] = float(np.mean(values))
            item[f"{metric}_std"] = float(np.std(values))
        result.append(item)
    return result


def _paired_effect(
    candidate_rows: list[dict[str, object]],
    baseline_rows: list[dict[str, object]],
    metric: str,
    direction: str,
    bootstrap_samples: int,
    rng: np.random.Generator,
) -> dict[str, object]:
    candidate_index = {
        (str(row["scenario"]), int(row["seed"])): float(row[metric])
        for row in candidate_rows
    }
    baseline_index = {
        (str(row["scenario"]), int(row["seed"])): float(row[metric])
        for row in baseline_rows
    }
    keys = sorted(set(candidate_index) & set(baseline_index))
    candidate = np.asarray([candidate_index[key] for key in keys], dtype=float)
    baseline = np.asarray([baseline_index[key] for key in keys], dtype=float)
    improvement = baseline - candidate if direction == "lower" else candidate - baseline
    lower, upper = _bootstrap_interval(improvement, bootstrap_samples, rng)
    return {
        "metric": metric,
        "direction": direction,
        "pairs": len(keys),
        "baseline_mean": float(np.mean(baseline)),
        "candidate_mean": float(np.mean(candidate)),
        "improvement_mean": float(np.mean(improvement)),
        "ci95_lower": lower,
        "ci95_upper": upper,
        "wins": int(np.sum(improvement > 1e-12)),
        "ties": int(np.sum(np.abs(improvement) <= 1e-12)),
        "losses": int(np.sum(improvement < -1e-12)),
    }


def _effects(
    rows: list[dict[str, object]],
    bootstrap_samples: int,
) -> list[dict[str, object]]:
    rng = np.random.default_rng(20260730)
    comparisons = (
        (M9C_RECEDING_ALGORITHM, M9C_ROUND_ROBIN_ALGORITHM),
        (M9C_RECEDING_ALGORITHM, M9A7_ALGORITHM),
        (M9C_ROUND_ROBIN_ALGORITHM, M9A7_ALGORITHM),
    )
    effects: list[dict[str, object]] = []
    scopes = [scenario.name for scenario in M9C_SCENARIOS] + [
        "__aggregate_exact__"
    ]
    exact_names = {scenario.name for scenario in M9C_EXACT_SCENARIOS}
    for scope in scopes:
        scoped = (
            [row for row in rows if str(row["scenario"]) in exact_names]
            if scope == "__aggregate_exact__"
            else [row for row in rows if str(row["scenario"]) == scope]
        )
        for candidate, baseline in comparisons:
            candidate_rows = [
                row for row in scoped if str(row["algorithm"]) == candidate
            ]
            baseline_rows = [
                row for row in scoped if str(row["algorithm"]) == baseline
            ]
            for metric, direction in EFFECT_METRICS.items():
                effect = _paired_effect(
                    candidate_rows,
                    baseline_rows,
                    metric,
                    direction,
                    bootstrap_samples,
                    rng,
                )
                effect.update(
                    {"scope": scope, "candidate": candidate, "baseline": baseline}
                )
                effects.append(effect)
    return effects


def _action_difference_rate(
    rows: list[dict[str, object]], scenario_name: str
) -> float:
    indexed = {
        (str(row["algorithm"]), int(row["seed"])): str(
            row["investigation_action_trace"]
        ).split("|")
        for row in rows
        if str(row["scenario"]) == scenario_name
    }
    rates: list[float] = []
    seeds = sorted(
        seed
        for algorithm, seed in indexed
        if algorithm == M9C_RECEDING_ALGORITHM
    )
    for seed in seeds:
        candidate = indexed[(M9C_RECEDING_ALGORITHM, seed)]
        baseline = indexed[(M9C_ROUND_ROBIN_ALGORITHM, seed)]
        rates.append(float(np.mean(np.asarray(candidate) != np.asarray(baseline))))
    return float(np.mean(rates)) if rates else 0.0


def _decision(
    rows: list[dict[str, object]],
    summaries: list[dict[str, object]],
    effects: list[dict[str, object]],
    *,
    phase: str,
    seed_count: int,
    replay: ReplayVerification,
    upstream_verified: bool,
) -> dict[str, object]:
    threshold = M9C_THRESHOLDS
    summary = {
        (str(row["scenario"]), str(row["algorithm"])): row for row in summaries
    }
    effect = {
        (
            str(row["scope"]),
            str(row["candidate"]),
            str(row["baseline"]),
            str(row["metric"]),
        ): row
        for row in effects
    }
    positive = summary[
        (M9C_SOURCE_COMPETITION.name, M9C_ROUND_ROBIN_ALGORITHM)
    ]
    candidate_positive = summary[
        (M9C_SOURCE_COMPETITION.name, M9C_RECEDING_ALGORITHM)
    ]
    action_difference = _action_difference_rate(
        rows, M9C_SOURCE_COMPETITION.name
    )
    exact = [
        summary[(scenario.name, M9C_RECEDING_ALGORITHM)]
        for scenario in M9C_EXACT_SCENARIOS
    ]
    natural_noninferiority = [
        float(
            effect[
                (
                    scenario.name,
                    M9C_RECEDING_ALGORITHM,
                    M9A7_ALGORITHM,
                    "integrated_loss",
                )
            ]["ci95_lower"]
        )
        for scenario in M9C_NATURAL_SCENARIOS
    ]
    delivery_bounds = [
        float(
            effect[
                (
                    scenario.name,
                    M9C_RECEDING_ALGORITHM,
                    M9A7_ALGORITHM,
                    "mean_delivery_ratio",
                )
            ]["ci95_lower"]
        )
        for scenario in M9C_NATURAL_SCENARIOS
    ]
    component_increases = [
        float(summary[(scenario.name, M9C_RECEDING_ALGORITHM)]["mean_topology_components_mean"])
        - float(summary[(scenario.name, M9A7_ALGORITHM)]["mean_topology_components_mean"])
        for scenario in M9C_NATURAL_SCENARIOS
    ]
    aggregate_utility = effect[
        (
            "__aggregate_exact__",
            M9C_RECEDING_ALGORITHM,
            M9C_ROUND_ROBIN_ALGORITHM,
            "integrated_loss",
        )
    ]
    positive_utility = effect[
        (
            M9C_SOURCE_COMPETITION.name,
            M9C_RECEDING_ALGORITHM,
            M9C_ROUND_ROBIN_ALGORITHM,
            "integrated_loss",
        )
    ]
    movement = effect[
        (
            "__aggregate_exact__",
            M9C_RECEDING_ALGORITHM,
            M9C_ROUND_ROBIN_ALGORITHM,
            "movement_per_step",
        )
    ]
    attack_candidate = summary[(M9A7_ATTACK.name, M9C_RECEDING_ALGORITHM)]
    attack_baseline = summary[(M9A7_ATTACK.name, M9A7_ALGORITHM)]
    attack_effect = effect[
        (
            M9A7_ATTACK.name,
            M9C_RECEDING_ALGORITHM,
            M9A7_ALGORITHM,
            "integrated_loss",
        )
    ]
    minimum_powered_seeds = required_tail_seeds(
        float(threshold["tail_event_frequency"]),
        float(threshold["tail_detection_probability"]),
    )
    gates = {
        "replay": replay.verified,
        "upstream_m9a7_frozen_go": upstream_verified,
        "tail_event_power": phase == "training" or seed_count >= minimum_powered_seeds,
        "positive_control_exercised": (
            float(positive["investigation_active_motion_rate_mean"])
            >= float(threshold["positive_control_round_robin_active_rate_min"])
            and float(candidate_positive["investigation_planning_sequences_mean"]) > 0.0
            and action_difference
            >= float(threshold["positive_control_action_difference_rate_min"])
        ),
        "aggregate_voi_utility": float(aggregate_utility["ci95_lower"])
        > float(threshold["aggregate_voi_improvement_lcb_min"]),
        "positive_control_voi_utility": float(positive_utility["ci95_lower"])
        > float(threshold["positive_control_voi_improvement_lcb_min"]),
        "movement_efficiency": float(movement["ci95_lower"])
        > float(threshold["movement_efficiency_lcb_min"]),
        "natural_m9a7_noninferiority": min(natural_noninferiority)
        >= float(threshold["natural_noninferiority_lcb_min"]),
        "wrong_action_safety": all(
            float(row["wrong_mode_action_rate_mean"])
            <= float(threshold["wrong_mode_action_rate_max"])
            for row in exact + [attack_candidate]
        ),
        "calibration": all(
            float(row["mean_nees_mean"]) <= float(threshold["mean_nees_max"])
            and float(row["p95_nees_mean"]) <= float(threshold["p95_nees_max"])
            and float(row["coverage95_rate_mean"])
            >= float(threshold["coverage95_min"])
            for row in exact
        ),
        "topology_noninterference": (
            min(delivery_bounds)
            >= float(threshold["delivery_ratio_degradation_lcb_min"])
            and max(component_increases)
            <= float(threshold["topology_component_increase_max"])
        ),
        "attack_nonworsening": (
            float(attack_effect["ci95_lower"])
            >= float(threshold["attack_noninferiority_lcb_min"])
            and float(attack_candidate["wrong_mode_action_rate_mean"])
            <= float(attack_baseline["wrong_mode_action_rate_mean"]) + 1e-12
            and float(attack_candidate["investigation_active_motion_rate_mean"])
            <= float(threshold["attack_active_motion_rate_max"])
        ),
        "attack_absolute_utility": float(attack_candidate["decision_loss_mean"])
        <= float(threshold["attack_absolute_loss_max"]),
    }
    validity_names = {
        "replay",
        "upstream_m9a7_frozen_go",
        "tail_event_power",
        "positive_control_exercised",
    }
    safety_names = {
        "natural_m9a7_noninferiority",
        "wrong_action_safety",
        "calibration",
        "topology_noninterference",
        "attack_nonworsening",
    }
    efficacy_names = {
        "aggregate_voi_utility",
        "positive_control_voi_utility",
        "movement_efficiency",
    }
    # M14.3: replay is adjudicated separately from the other validity gates.
    _other_validity = validity_names - {"replay"}
    if replay.blocks_promotion or not all(gates[name] for name in _other_validity):
        verdict = "M9C-INVALID"
    elif not all(gates[name] for name in safety_names):
        verdict = "M9C-TRAINING-FAIL" if phase == "training" else "M9C-NO-GO"
    elif not all(gates[name] for name in efficacy_names):
        verdict = "M9C-TRAINING-FAIL" if phase == "training" else "M9C-NO-GO"
    elif not gates["attack_absolute_utility"]:
        verdict = (
            "M9C-TRAINING-PARTIAL"
            if phase == "training"
            else "M9C-PARTIAL-GO"
        )
    else:
        verdict = "M9C-TRAINING-PASS" if phase == "training" else "M9C-GO"
    return {
        "verdict": verdict,
        "phase": phase,
        "gates": gates,
        "thresholds": threshold,
        "positive_control_action_difference_rate": action_difference,
        "aggregate_voi_improvement": float(aggregate_utility["improvement_mean"]),
        "aggregate_voi_ci95": [
            float(aggregate_utility["ci95_lower"]),
            float(aggregate_utility["ci95_upper"]),
        ],
        "positive_control_voi_improvement": float(
            positive_utility["improvement_mean"]
        ),
        "movement_efficiency_improvement": float(movement["improvement_mean"]),
        "worst_natural_noninferiority_lcb": min(natural_noninferiority),
        "worst_delivery_ratio_lcb": min(delivery_bounds),
        "maximum_component_increase": max(component_increases),
        "attack_candidate_loss": float(attack_candidate["decision_loss_mean"]),
        "power_calculation": {
            "event_frequency": threshold["tail_event_frequency"],
            "detection_probability": threshold["tail_detection_probability"],
            "minimum_seed_count": minimum_powered_seeds,
            "actual_seed_count": seed_count,
        },
        "production_authorized": False,
        "original_m9a7_and_m9b_verdicts_unchanged": True,
    }


def _write_report(
    path: Path,
    decision: dict[str, object],
    summaries: list[dict[str, object]],
    effects: list[dict[str, object]],
    seed_start: int,
    seed_count: int,
) -> None:
    summary = {
        (str(row["scenario"]), str(row["algorithm"])): row for row in summaries
    }
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
        "# M9C bounded M9A.7/M9B integration report",
        "",
        f"**Verdict: `{decision['verdict']}`**",
        "",
        f"Phase: `{decision['phase']}`. Seeds: `{seed_start}`–`{seed_start + seed_count - 1}` ({seed_count} paired seeds per scenario).",
        "",
        "The external estimator and risk-priced output are unchanged M9A.7. The two integration arms use the exact assignment posterior for physical motion: broad all-source investigation versus a component-local two-step VOI allocator. Unknown residual mass above the frozen ceiling disables extra probing.",
        "",
        "## Gates",
        "",
        "| Gate | Result |",
        "|---|---:|",
    ]
    for name, passed in dict(decision["gates"]).items():
        lines.append(f"| {name} | {'PASS' if passed else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## Scenario results",
            "",
            "| Scenario | Arm | Integrated loss | Decision loss | Move/step | Active | Wrong | NEES | Coverage | Delivery | Components |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    labels = {
        M9A7_ALGORITHM: "M9A.7",
        M9C_ROUND_ROBIN_ALGORITHM: "broad",
        M9C_RECEDING_ALGORITHM: "VOI",
    }
    for scenario in M9C_SCENARIOS:
        for algorithm in M9C_ALGORITHMS:
            row = summary[(scenario.name, algorithm)]
            lines.append(
                f"| {scenario.name} | {labels[algorithm]} | "
                f"{float(row['integrated_loss_mean']):.3f} | "
                f"{float(row['decision_loss_mean']):.3f} | "
                f"{float(row['movement_per_step_mean']):.3f} | "
                f"{float(row['investigation_active_motion_rate_mean']):.3f} | "
                f"{float(row['wrong_mode_action_rate_mean']):.3f} | "
                f"{float(row['mean_nees_mean']):.2f} | "
                f"{float(row['coverage95_rate_mean']):.3f} | "
                f"{float(row['mean_delivery_ratio_mean']):.3f} | "
                f"{float(row['mean_topology_components_mean']):.2f} |"
            )
    lines.extend(
        [
            "",
            "## VOI effects versus broad investigation",
            "",
            "| Scope | Integrated-loss improvement | 95% CI | Movement improvement | 95% CI |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for scope in [scenario.name for scenario in M9C_SCENARIOS] + [
        "__aggregate_exact__"
    ]:
        utility = effect[
            (
                scope,
                M9C_RECEDING_ALGORITHM,
                M9C_ROUND_ROBIN_ALGORITHM,
                "integrated_loss",
            )
        ]
        movement = effect[
            (
                scope,
                M9C_RECEDING_ALGORITHM,
                M9C_ROUND_ROBIN_ALGORITHM,
                "movement_per_step",
            )
        ]
        lines.append(
            f"| {scope} | {float(utility['improvement_mean']):.4f} | "
            f"[{float(utility['ci95_lower']):.4f}, {float(utility['ci95_upper']):.4f}] | "
            f"{float(movement['improvement_mean']):.4f} | "
            f"[{float(movement['ci95_lower']):.4f}, {float(movement['ci95_upper']):.4f}] |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "This protocol cannot authorize production. A GO would only retain the integrated allocator for a decentralized follow-up. Failure of an efficacy gate archives the dynamic VOI integration at this representation; failure of attack absolute utility leaves the raw-channel risk explicitly unresolved.",
            "",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_rows(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _verify_upstream(project_root: Path) -> tuple[bool, dict[str, object]]:
    upstream = project_root / "results/milestone9a7_heldout"
    decision = json.loads((upstream / "decision.json").read_text(encoding="utf-8"))
    suite_config = json.loads(
        (upstream / "suite_config.json").read_text(encoding="utf-8")
    )
    source = project_root / "src/flockkalman"
    _m9a7_files = (
        source / "admission_suite.py",
        source / "admission_evidence.py",
        source / "missing_evidence.py",
        source / "oracle_floor.py",
    )
    upstream_source = verify_upstream_source(
        suite_config.get("candidate_source_sha256"),
        _m9a7_files,
        reference_commit=PRE_M14_COMMIT,
        repo_root=project_root,
    )
    current_hash = upstream_source["current_sha256"]
    verified = (
        verdict_accepted(str(decision.get("verdict", "")), {"M9A7-GO"})
        and not upstream_source["blocks_promotion"]
        and upstream_replay_acceptable(decision)
    )
    return verified, {
        "verdict": decision.get("verdict"),
        "candidate_source_sha256": suite_config.get("candidate_source_sha256"),
        "current_source_sha256": current_hash,
        "source_verification": upstream_source,
        "trace_replay_verified": decision.get("trace_replay_verified"),
    }


def run_integration_suite(
    base_config: ExperimentConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 150,
    seed_start: int = 19000,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
    phase: str = "heldout",
) -> dict[str, object]:
    """Run the frozen M9C paired dynamic-topology integration protocol."""
    base_config.validate()
    if phase not in {"training", "heldout"}:
        raise ValueError("phase must be training or heldout")
    if seed_count < 2 or bootstrap_samples < 100:
        raise ValueError("M9C needs at least two seeds and 100 bootstrap samples")
    tasks: list[tuple[str, dict[str, object], int]] = []
    scenario_configs: dict[str, dict[str, object]] = {}
    manifest_entries: list[dict[str, object]] = []
    for scenario in M9C_SCENARIOS:
        config = _scenario_config(base_config, scenario)
        config.validate()
        config_data = config.to_dict()
        scenario_configs[scenario.name] = config_data
        for seed in range(seed_start, seed_start + seed_count):
            tasks.append((scenario.name, config_data, seed))
            manifest_entries.append(
                {
                    "scenario": scenario.name,
                    "seed": seed,
                    "fingerprint": scenario_fingerprint(
                        config, seed, algorithm=CURRENT_FINGERPRINT_ALGORITHM
                    ),
                }
            )
    worker_count = workers or min(os.cpu_count() or 2, 8)
    executor_kind = "serial"
    if worker_count == 1:
        groups = [_worker(task) for task in tasks]
    else:
        try:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                groups = list(executor.map(_worker, tasks, chunksize=2))
            executor_kind = "process"
        except (PermissionError, OSError):
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                groups = list(executor.map(_worker, tasks))
            executor_kind = "thread_fallback"
    rows = [row for group in groups for row in group]
    scenario_order = {item.name: index for index, item in enumerate(M9C_SCENARIOS)}
    algorithm_order = {item: index for index, item in enumerate(M9C_ALGORITHMS)}
    rows.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            algorithm_order[str(row["algorithm"])],
            int(row["seed"]),
        )
    )
    summaries = _scenario_summary(rows)
    summaries.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            algorithm_order[str(row["algorithm"])],
        )
    )
    effects = _effects(rows, bootstrap_samples)
    replay = verify_replay(
        [dict(entry) for entry in manifest_entries],
        expected=lambda entry, algorithm: scenario_fingerprint(
            ExperimentConfig(**scenario_configs[str(entry["scenario"])]),
            int(entry["seed"]),
            algorithm=algorithm,
        ),
        recorded_environment=environment_fingerprint(),
        recorded_algorithm=CURRENT_FINGERPRINT_ALGORITHM,
        fingerprint_key="fingerprint",
    )
    project_root = Path(__file__).resolve().parents[2]
    upstream_verified, upstream = _verify_upstream(project_root)
    decision = _decision(
        rows,
        summaries,
        effects,
        phase=phase,
        seed_count=seed_count,
        replay=replay,
        upstream_verified=upstream_verified,
    )
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "run_summary.csv", rows)
    _write_csv(output / "scenario_summary.csv", summaries)
    _write_csv(output / "paired_effects.csv", effects)
    (output / "trace_manifest.json").write_text(
        json.dumps(
            {
                "replay_verified": replay.verified,
                "replay_verification": replay.to_dict(),
                "fingerprint_algorithm": CURRENT_FINGERPRINT_ALGORITHM,
                "entries": manifest_entries,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    protocol_path = project_root / "M9C_PROTOCOL.md"
    source = project_root / "src/flockkalman"
    suite_config = {
        "phase": phase,
        "seed_start": seed_start,
        "seed_count": seed_count,
        "bootstrap_samples": bootstrap_samples,
        "workers": worker_count,
        "executor": executor_kind,
        "scenarios": [asdict(item) for item in M9C_SCENARIOS],
        "scenario_configs": scenario_configs,
        "thresholds": M9C_THRESHOLDS,
        "protocol_sha256": _artifact_hash((protocol_path,)),
        "candidate_source_sha256": _artifact_hash(
            (
                source / "integrated_sensing.py",
                source / "integration_suite.py",
                source / "experiment.py",
                source / "config.py",
                source / "metrics.py",
                # M14.4: the replay gate depends on these too.
                source / "simulation.py",
                source / "provenance.py",
            )
        ),
        "upstream_m9a7": upstream,
        "platform_version": "0.13.0",
        "fingerprint_algorithm": CURRENT_FINGERPRINT_ALGORITHM,
        "python": platform.python_version(),
        "numpy": np.__version__,
    }
    (output / "suite_config.json").write_text(
        json.dumps(suite_config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_report(
        output / "milestone9c_report.md",
        decision,
        summaries,
        effects,
        seed_start,
        seed_count,
    )
    return decision


def reanalyze_integration_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    """Recompute M9C gates and replay verification from saved rows."""
    output = Path(output_directory)
    suite_config = json.loads(
        (output / "suite_config.json").read_text(encoding="utf-8")
    )
    rows = _read_rows(output / "run_summary.csv")
    samples = int(bootstrap_samples or suite_config["bootstrap_samples"])
    summaries = _scenario_summary(rows)
    scenario_order = {item.name: index for index, item in enumerate(M9C_SCENARIOS)}
    algorithm_order = {item: index for index, item in enumerate(M9C_ALGORITHMS)}
    summaries.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            algorithm_order[str(row["algorithm"])],
        )
    )
    effects = _effects(rows, samples)
    _cfgs = suite_config["scenario_configs"]
    replay = verify_replay(
        rows,
        expected=lambda row, algorithm: scenario_fingerprint(
            ExperimentConfig(**_cfgs[str(row["scenario"])]),
            int(row["seed"]),
            algorithm=algorithm,
        ),
        schema_expected=lambda row, algorithm: scenario_fingerprint(
            ExperimentConfig(**_cfgs[str(row["scenario"])]),
            int(row["seed"]),
            algorithm=algorithm,
            config_payload=dict(_cfgs[str(row["scenario"])]),
        ),
        recorded_environment={
            key: suite_config[key]
            for key in ("python", "numpy", "platform", "machine")
            if key in suite_config
        }
        or None,
        recorded_algorithm=(
            str(suite_config["fingerprint_algorithm"])
            if suite_config.get("fingerprint_algorithm")
            else None
        ),
    )
    project_root = Path(__file__).resolve().parents[2]
    upstream_verified, _ = _verify_upstream(project_root)
    decision = _decision(
        rows,
        summaries,
        effects,
        phase=str(suite_config["phase"]),
        seed_count=int(suite_config["seed_count"]),
        replay=replay,
        upstream_verified=upstream_verified,
    )
    _write_csv(output / "scenario_summary.csv", summaries)
    _write_csv(output / "paired_effects.csv", effects)
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_report(
        output / "milestone9c_report.md",
        decision,
        summaries,
        effects,
        int(suite_config["seed_start"]),
        int(suite_config["seed_count"]),
    )
    return decision
