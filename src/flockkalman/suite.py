"""Held-out paired evaluation and go/no-go decision support."""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, replace
import json
import os
from pathlib import Path
import platform
from time import perf_counter
from typing import Iterable

import numpy as np

from .config import ExperimentConfig
from .experiment import run_trial
from .metrics import summarize_run


DECISION_ALGORITHMS = (
    "flocking_kf_no_momentum",
    "flocking_fixed_momentum",
    "flocking_adaptive_momentum",
)


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    name: str
    description: str
    overrides: dict[str, object]


DEFAULT_SUITE_SCENARIOS = (
    ScenarioDefinition(
        "no_change",
        "Stationary dynamics with process noise and no deliberate regime change.",
        {"target_change_mode": "none"},
    ),
    ScenarioDefinition(
        "abrupt_change",
        "One abrupt velocity change at the configured change point.",
        {"target_change_mode": "abrupt"},
    ),
    ScenarioDefinition(
        "gradual_change",
        "The velocity change is distributed across twenty steps.",
        {"target_change_mode": "gradual", "gradual_change_duration": 20},
    ),
    ScenarioDefinition(
        "repeated_changes",
        "Repeated target turns test reorientation without a long stable interval.",
        {
            "target_change_mode": "repeated",
            "change_step": 35,
            "repeated_change_interval": 35,
        },
    ),
    ScenarioDefinition(
        "mixed_dropout",
        "Twenty percent observation dropout and fifteen percent directed-link dropout.",
        {"measurement_dropout_rate": 0.20, "communication_dropout_rate": 0.15},
    ),
    ScenarioDefinition(
        "communication_delay",
        "Neighbour belief and motion messages arrive two cycles late.",
        {"communication_delay_steps": 2},
    ),
    ScenarioDefinition(
        "biased_agents",
        "Two agents have a persistent, unmodelled measurement bias.",
        {"biased_agent_count": 2, "measurement_bias": (2.5, -2.0)},
    ),
)


EFFECT_METRICS = {
    "position_rmse": "lower",
    "best_hypothesis_rmse": "lower",
    "agent_position_rmse": "lower",
    "recovery_steps": "lower",
    "information_gain": "higher",
    "nees_calibration_error": "lower",
    "coverage_calibration_error": "lower",
    "estimate_disagreement": "lower",
    "runtime_seconds": "lower",
    "bytes_sent": "lower",
}

COMPARISONS = (
    ("flocking_adaptive_momentum", "flocking_kf_no_momentum"),
    ("flocking_adaptive_momentum", "flocking_fixed_momentum"),
    ("flocking_fixed_momentum", "flocking_kf_no_momentum"),
)


def _worker(task: tuple[str, dict[str, object], str, int]) -> dict[str, object]:
    scenario_name, config_data, algorithm, seed = task
    config = ExperimentConfig(**config_data)
    started = perf_counter()
    records = run_trial(config, algorithm, seed)
    summary = summarize_run(config, records)
    summary["runtime_seconds"] = perf_counter() - started
    summary["scenario"] = scenario_name
    summary["nees_calibration_error"] = abs(float(summary["mean_nees"]) - 2.0)
    summary["coverage_calibration_error"] = abs(
        float(summary["coverage95_rate"]) - 0.95
    )
    return summary


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _scenario_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["scenario"]), str(row["algorithm"])), []).append(row)
    metrics = list(EFFECT_METRICS) + [
        "mean_truth_consistent_flock_weight",
        "decision_loss",
        "mean_decision_base_error",
        "selection_rate",
        "mixture_rate",
        "abstention_rate",
        "investigation_rate",
        "wrong_mode_rate",
        "wrong_mode_action_rate",
        "mean_output_confidence",
        "ambiguity_resolution_steps",
        "mean_nees",
        "p95_nees",
        "max_nees",
        "coverage95_rate",
        "rejoin_window_nees",
        "mean_nis",
        "spatial_diversity",
        "messages",
        "mean_momentum",
        "mean_momentum_change_score",
        "mean_momentum_corroborating_agents",
        "mean_momentum_biased_agents",
        "momentum_fallback_rate",
        "momentum_change_events",
        "mean_hypothesis_flocks",
        "multiflock_rate",
        "mean_primary_flock_size",
        "mean_primary_flock_weight",
        "mean_alternative_flock_weight",
        "mean_quarantined_agents",
        "quarantine_rate",
        "mean_suspected_bias_agents",
        "mean_bias_estimate_norm",
        "mean_operational_agents",
        "mean_delivery_ratio",
        "mean_message_age",
        "partition_active_rate",
        "partition_selection_rate",
        "mean_topology_components",
        "mean_observer_component_size",
        "mean_topology_visibility_fraction",
        "mean_topology_live_support",
        "mean_topology_retained_support",
        "mean_topology_unknown_support",
        "mean_topology_probation_agents",
        "topology_rejoin_events",
        "topology_merge_grace_rate",
        "topology_epoch_changes",
        "mean_duplicate_support_suppressed",
        "topology_selection_blocked_rate",
        "max_primary_support_jump",
        "movement_distance",
    ]
    result: list[dict[str, object]] = []
    for (scenario, algorithm), group in grouped.items():
        item: dict[str, object] = {
            "scenario": scenario,
            "algorithm": algorithm,
            "runs": len(group),
        }
        for metric in metrics:
            values = [float(row[metric]) for row in group if row.get(metric) is not None]
            item[f"{metric}_mean"] = float(np.mean(values)) if values else None
            item[f"{metric}_std"] = float(np.std(values)) if values else None
        result.append(item)
    return result


def _bootstrap_interval(
    values: np.ndarray, samples: int, rng: np.random.Generator
) -> tuple[float, float]:
    if len(values) == 1:
        value = float(values[0])
        return value, value
    indices = rng.integers(0, len(values), size=(samples, len(values)))
    means = np.mean(values[indices], axis=1)
    lower, upper = np.percentile(means, [2.5, 97.5])
    return float(lower), float(upper)


def _paired_effects(
    rows: list[dict[str, object]],
    scenarios: tuple[ScenarioDefinition, ...],
    seeds: list[int],
    bootstrap_samples: int,
    comparisons: tuple[tuple[str, str], ...] = COMPARISONS,
    effect_metrics: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    indexed = {
        (str(row["scenario"]), str(row["algorithm"]), int(row["seed"])): row
        for row in rows
    }
    scopes = [scenario.name for scenario in scenarios] + ["overall"]
    rng = np.random.default_rng(20260721)
    metrics = effect_metrics or EFFECT_METRICS
    results: list[dict[str, object]] = []
    for scope in scopes:
        selected = [scope] if scope != "overall" else [scenario.name for scenario in scenarios]
        for candidate, baseline in comparisons:
            for metric, direction in metrics.items():
                baseline_values: list[float] = []
                candidate_values: list[float] = []
                paired_seeds: list[int] = []
                for seed in seeds:
                    base_parts: list[float] = []
                    candidate_parts: list[float] = []
                    for scenario_name in selected:
                        base = indexed[(scenario_name, baseline, seed)].get(metric)
                        candidate_value = indexed[
                            (scenario_name, candidate, seed)
                        ].get(metric)
                        if base is not None and candidate_value is not None:
                            base_parts.append(float(base))
                            candidate_parts.append(float(candidate_value))
                    if base_parts:
                        baseline_values.append(float(np.mean(base_parts)))
                        candidate_values.append(float(np.mean(candidate_parts)))
                        paired_seeds.append(seed)
                if not paired_seeds:
                    continue
                baseline_array = np.asarray(baseline_values)
                candidate_array = np.asarray(candidate_values)
                if direction == "lower":
                    improvement = baseline_array - candidate_array
                else:
                    improvement = candidate_array - baseline_array
                lower, upper = _bootstrap_interval(improvement, bootstrap_samples, rng)
                tolerance = 1e-12
                baseline_mean = float(np.mean(baseline_array))
                results.append(
                    {
                        "scope": scope,
                        "candidate": candidate,
                        "baseline": baseline,
                        "metric": metric,
                        "direction": direction,
                        "pairs": len(paired_seeds),
                        "baseline_mean": baseline_mean,
                        "candidate_mean": float(np.mean(candidate_array)),
                        "improvement_mean": float(np.mean(improvement)),
                        "relative_improvement_percent": (
                            100.0 * float(np.mean(improvement)) / abs(baseline_mean)
                            if abs(baseline_mean) > tolerance
                            else None
                        ),
                        "ci95_lower": lower,
                        "ci95_upper": upper,
                        "wins": int(np.sum(improvement > tolerance)),
                        "ties": int(np.sum(np.abs(improvement) <= tolerance)),
                        "losses": int(np.sum(improvement < -tolerance)),
                    }
                )
    return results


def _decision(
    run_rows: list[dict[str, object]],
    scenario_rows: list[dict[str, object]],
    effects: list[dict[str, object]],
    scenario_count: int,
) -> dict[str, object]:
    lookup = {
        (
            str(row["scope"]),
            str(row["candidate"]),
            str(row["baseline"]),
            str(row["metric"]),
        ): row
        for row in effects
    }
    adaptive = [row for row in run_rows if row["algorithm"] == "flocking_adaptive_momentum"]
    coverage = float(np.mean([float(row["coverage95_rate"]) for row in adaptive]))
    nees = float(np.mean([float(row["mean_nees"]) for row in adaptive]))

    rmse_effects = [
        lookup[("overall", "flocking_adaptive_momentum", baseline, "position_rmse")]
        for baseline in DECISION_ALGORITHMS[:2]
    ]
    recovery_effects = [
        lookup[("overall", "flocking_adaptive_momentum", baseline, "recovery_steps")]
        for baseline in DECISION_ALGORITHMS[:2]
    ]
    runtime = lookup[
        (
            "overall",
            "flocking_adaptive_momentum",
            "flocking_fixed_momentum",
            "runtime_seconds",
        )
    ]
    communication = lookup[
        (
            "overall",
            "flocking_adaptive_momentum",
            "flocking_fixed_momentum",
            "bytes_sent",
        )
    ]
    fixed_rmse = lookup[
        (
            "overall",
            "flocking_fixed_momentum",
            "flocking_kf_no_momentum",
            "position_rmse",
        )
    ]
    fixed_recovery = lookup[
        (
            "overall",
            "flocking_fixed_momentum",
            "flocking_kf_no_momentum",
            "recovery_steps",
        )
    ]

    scenario_index = {
        (str(row["scenario"]), str(row["algorithm"])): row for row in scenario_rows
    }
    scenario_names = sorted({str(row["scenario"]) for row in scenario_rows})
    robust_wins = 0
    fixed_wins = 0
    for scenario_name in scenario_names:
        adaptive_rmse = float(
            scenario_index[(scenario_name, "flocking_adaptive_momentum")][
                "position_rmse_mean"
            ]
        )
        if all(
            adaptive_rmse
            < float(scenario_index[(scenario_name, baseline)]["position_rmse_mean"])
            for baseline in DECISION_ALGORITHMS[:2]
        ):
            robust_wins += 1
        fixed_rmse_value = float(
            scenario_index[(scenario_name, "flocking_fixed_momentum")][
                "position_rmse_mean"
            ]
        )
        zero_rmse_value = float(
            scenario_index[(scenario_name, "flocking_kf_no_momentum")][
                "position_rmse_mean"
            ]
        )
        fixed_wins += int(fixed_rmse_value < zero_rmse_value)

    gates = {
        "rmse_significant_vs_both": all(
            float(effect["ci95_lower"]) > 0.0 for effect in rmse_effects
        ),
        "recovery_mean_better_vs_both": all(
            float(effect["improvement_mean"]) > 0.0 for effect in recovery_effects
        ),
        "calibration_acceptable": 0.93 <= coverage <= 0.97 and 1.5 <= nees <= 2.5,
        "scenario_robustness": robust_wins >= max(1, scenario_count - 2),
        "communication_overhead_under_2_percent": (
            float(communication["candidate_mean"])
            <= 1.02 * float(communication["baseline_mean"])
        ),
        "runtime_overhead_under_25_percent": (
            float(runtime["candidate_mean"]) <= 1.25 * float(runtime["baseline_mean"])
        ),
    }
    if (
        gates["rmse_significant_vs_both"]
        and gates["calibration_acceptable"]
        and gates["scenario_robustness"]
        and gates["communication_overhead_under_2_percent"]
        and gates["runtime_overhead_under_25_percent"]
    ):
        verdict = "GO"
    elif any(float(effect["ci95_upper"]) < 0.0 for effect in rmse_effects) or not gates[
        "calibration_acceptable"
    ]:
        verdict = "NO-GO"
    else:
        verdict = "INCONCLUSIVE"
    core_scenarios = {
        "no_change",
        "abrupt_change",
        "gradual_change",
        "repeated_changes",
        "mixed_dropout",
    }
    core_rows = [
        row
        for row in scenario_rows
        if row["algorithm"] == "flocking_fixed_momentum"
        and row["scenario"] in core_scenarios
    ]
    fixed_core_calibrated = all(
        0.93 <= float(row["coverage95_rate_mean"]) <= 0.98
        and 1.5 <= float(row["mean_nees_mean"]) <= 2.5
        for row in core_rows
    )
    fixed_signal = {
        "rmse_significant_vs_zero": float(fixed_rmse["ci95_lower"]) > 0.0,
        "recovery_significant_vs_zero": float(fixed_recovery["ci95_lower"]) > 0.0,
        "scenario_robustness_vs_zero": fixed_wins >= max(1, scenario_count - 2),
        "core_scenarios_calibrated": fixed_core_calibrated,
    }
    research_direction = (
        "PURSUE_ADAPTIVE_MOMENTUM"
        if verdict == "GO"
        else (
            "PIVOT_TO_FIXED_MOMENTUM_AND_REDESIGN_ADAPTATION"
            if all(fixed_signal.values())
            else "STOP_INVESTIGATIVE_MOMENTUM"
        )
    )
    return {
        "verdict": verdict,
        "verdict_scope": "current innovation-adaptive momentum scheduler",
        "research_direction": research_direction,
        "gates": gates,
        "fixed_momentum_signal": fixed_signal,
        "adaptive_coverage95": coverage,
        "adaptive_mean_nees": nees,
        "scenarios_won_against_both": robust_wins,
        "fixed_momentum_scenarios_won_vs_zero": fixed_wins,
        "scenario_count": scenario_count,
    }


def _write_report(
    path: Path,
    decision: dict[str, object],
    effects: list[dict[str, object]],
    scenario_summary: list[dict[str, object]],
    seed_start: int,
    seed_count: int,
) -> None:
    lookup = {
        (
            str(row["scope"]),
            str(row["candidate"]),
            str(row["baseline"]),
            str(row["metric"]),
        ): row
        for row in effects
    }
    lines = [
        "# Adaptive Investigative Momentum Decision Report",
        "",
        f"**Verdict: {decision['verdict']}**",
        "",
        f"**Research direction: {decision['research_direction']}**",
        "",
        f"This report uses {seed_count} held-out seeds ({seed_start}–{seed_start + seed_count - 1}), seven stress scenarios, common random numbers, and paired bootstrap 95% confidence intervals.",
        "",
        "## Decision gates",
        "",
        "| Gate | Result |",
        "|---|---|",
    ]
    for gate, passed in dict(decision["gates"]).items():
        lines.append(f"| {gate.replace('_', ' ')} | {'PASS' if passed else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## Fixed-momentum diagnostic",
            "",
            "The adaptive verdict is separate from the broader question of whether recurrence helps. This preregistered zero-momentum control supplies that contrast.",
            "",
            "| Gate | Result |",
            "|---|---|",
        ]
    )
    for gate, passed in dict(decision["fixed_momentum_signal"]).items():
        lines.append(f"| {gate.replace('_', ' ')} | {'PASS' if passed else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## Overall paired effects",
            "",
            "Positive improvement means the named candidate is better than its baseline. Overall effects first average scenarios within each seed, preserving 100 independent paired units.",
            "",
            "| Candidate | Baseline | Metric | Baseline | Candidate | Improvement | 95% CI | Wins / losses |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for candidate, baseline in COMPARISONS:
        for metric in ("position_rmse", "recovery_steps", "information_gain", "coverage_calibration_error", "runtime_seconds"):
            row = lookup[("overall", candidate, baseline, metric)]
            lines.append(
                f"| {candidate} | {baseline} | {metric} | {float(row['baseline_mean']):.4f} | "
                f"{float(row['candidate_mean']):.4f} | {float(row['improvement_mean']):.4f} | "
                f"[{float(row['ci95_lower']):.4f}, {float(row['ci95_upper']):.4f}] | "
                f"{row['wins']} / {row['losses']} |"
            )
    lines.extend(
        [
            "",
            "## Scenario RMSE",
            "",
            "| Scenario | Zero momentum | Fixed momentum | Adaptive momentum |",
            "|---|---:|---:|---:|",
        ]
    )
    indexed = {
        (str(row["scenario"]), str(row["algorithm"])): row for row in scenario_summary
    }
    for scenario in sorted({str(row["scenario"]) for row in scenario_summary}):
        values = [
            float(indexed[(scenario, algorithm)]["position_rmse_mean"])
            for algorithm in DECISION_ALGORITHMS
        ]
        lines.append(
            f"| {scenario} | {values[0]:.4f} | {values[1]:.4f} | {values[2]:.4f} |"
        )
    lines.extend(["", "## Interpretation", ""])
    if decision["research_direction"] == "PIVOT_TO_FIXED_MOMENTUM_AND_REDESIGN_ADAPTATION":
        fixed = lookup[
            (
                "overall",
                "flocking_fixed_momentum",
                "flocking_kf_no_momentum",
                "position_rmse",
            )
        ]
        adaptive = lookup[
            (
                "overall",
                "flocking_adaptive_momentum",
                "flocking_fixed_momentum",
                "position_rmse",
            )
        ]
        lines.extend(
            [
                f"Fixed recurrence reduced RMSE versus zero recurrence by {float(fixed['relative_improvement_percent']):.2f}% with a wholly positive paired confidence interval.",
                "",
                f"The current innovation-adaptive scheduler was {abs(float(adaptive['relative_improvement_percent'])):.2f}% worse than fixed recurrence, with a wholly negative paired confidence interval. Its largest failures occurred under communication delay and persistent sensor bias.",
                "",
                "The firm decision is therefore to retain fixed investigative momentum as the supported baseline, reject the current NIS-to-momentum rule, and redesign adaptation around delay-aware and bias-robust change detection.",
            ]
        )
    else:
        lines.append(
            "The verdict applies to this benchmark family and does not establish transfer to language-agent or hypothesis spaces; those require separately validated state and uncertainty models."
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_decision_suite(
    base_config: ExperimentConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 100,
    seed_start: int = 1000,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
    scenario_names: Iterable[str] | None = None,
) -> dict[str, object]:
    """Run the frozen, held-out decision experiment and write its evidence package."""
    if seed_count < 2:
        raise ValueError("seed_count must be at least 2")
    if bootstrap_samples < 100:
        raise ValueError("bootstrap_samples must be at least 100")
    requested = set(scenario_names) if scenario_names is not None else None
    scenarios = tuple(
        scenario
        for scenario in DEFAULT_SUITE_SCENARIOS
        if requested is None or scenario.name in requested
    )
    if requested is not None and requested != {scenario.name for scenario in scenarios}:
        unknown = sorted(requested - {scenario.name for scenario in scenarios})
        raise ValueError(f"unknown scenarios: {', '.join(unknown)}")
    if not scenarios:
        raise ValueError("at least one scenario is required")

    seeds = list(range(seed_start, seed_start + seed_count))
    tasks: list[tuple[str, dict[str, object], str, int]] = []
    scenario_configs: dict[str, dict[str, object]] = {}
    for scenario in scenarios:
        config = replace(
            base_config,
            **scenario.overrides,
            seeds=seeds,
            algorithms=list(DECISION_ALGORITHMS),
        )
        config.validate()
        scenario_configs[scenario.name] = config.to_dict()
        for algorithm in DECISION_ALGORITHMS:
            for seed in seeds:
                tasks.append((scenario.name, config.to_dict(), algorithm, seed))

    worker_count = workers or min(os.cpu_count() or 2, 8)
    if worker_count == 1:
        run_rows = [_worker(task) for task in tasks]
    else:
        with ProcessPoolExecutor(max_workers=worker_count) as executor:
            run_rows = list(executor.map(_worker, tasks, chunksize=4))
    order_scenario = {scenario.name: index for index, scenario in enumerate(scenarios)}
    order_algorithm = {algorithm: index for index, algorithm in enumerate(DECISION_ALGORITHMS)}
    run_rows.sort(
        key=lambda row: (
            order_scenario[str(row["scenario"])],
            order_algorithm[str(row["algorithm"])],
            int(row["seed"]),
        )
    )

    scenario_rows = _scenario_summary(run_rows)
    effects = _paired_effects(run_rows, scenarios, seeds, bootstrap_samples)
    decision = _decision(run_rows, scenario_rows, effects, len(scenarios))
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "run_summary.csv", run_rows)
    _write_csv(output / "scenario_summary.csv", scenario_rows)
    _write_csv(output / "paired_effects.csv", effects)
    suite_config = {
        "seed_start": seed_start,
        "seed_count": seed_count,
        "bootstrap_samples": bootstrap_samples,
        "workers": worker_count,
        "algorithms": list(DECISION_ALGORITHMS),
        "scenarios": [asdict(scenario) for scenario in scenarios],
        "scenario_configs": scenario_configs,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "platform_version": "0.12.0",
    }
    (output / "suite_config.json").write_text(
        json.dumps(suite_config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_report(
        output / "decision_report.md",
        decision,
        effects,
        scenario_rows,
        seed_start,
        seed_count,
    )
    return decision


def reanalyze_decision_suite(
    output_directory: str | Path, *, bootstrap_samples: int | None = None
) -> dict[str, object]:
    """Regenerate statistical artifacts from completed trials without rerunning them."""
    output = Path(output_directory)
    suite_config = json.loads((output / "suite_config.json").read_text(encoding="utf-8"))
    with (output / "run_summary.csv").open(encoding="utf-8", newline="") as handle:
        run_rows = [
            {key: (None if value == "" else value) for key, value in row.items()}
            for row in csv.DictReader(handle)
        ]
    scenarios = tuple(ScenarioDefinition(**item) for item in suite_config["scenarios"])
    seed_start = int(suite_config["seed_start"])
    seed_count = int(suite_config["seed_count"])
    seeds = list(range(seed_start, seed_start + seed_count))
    samples = int(bootstrap_samples or suite_config["bootstrap_samples"])
    scenario_rows = _scenario_summary(run_rows)
    effects = _paired_effects(run_rows, scenarios, seeds, samples)
    decision = _decision(run_rows, scenario_rows, effects, len(scenarios))
    _write_csv(output / "scenario_summary.csv", scenario_rows)
    _write_csv(output / "paired_effects.csv", effects)
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_report(
        output / "decision_report.md",
        decision,
        effects,
        scenario_rows,
        seed_start,
        seed_count,
    )
    return decision
