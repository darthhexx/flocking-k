"""Milestone 5 evaluation for guarded adaptive investigative momentum."""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import platform
from typing import Iterable

import numpy as np

from .config import ExperimentConfig
from .suite import (
    DEFAULT_SUITE_SCENARIOS,
    ScenarioDefinition,
    _paired_effects,
    _scenario_summary,
    _worker,
    _write_csv,
)


M5_ALGORITHMS = (
    "flocking_fixed_momentum",
    "flocking_guarded_momentum",
    "flocking_adaptive_momentum",
)

M5_COMPARISONS = (
    ("flocking_guarded_momentum", "flocking_fixed_momentum"),
    ("flocking_guarded_momentum", "flocking_adaptive_momentum"),
    ("flocking_adaptive_momentum", "flocking_fixed_momentum"),
)


def _effect_lookup(
    effects: list[dict[str, object]],
) -> dict[tuple[str, str, str, str], dict[str, object]]:
    return {
        (
            str(row["scope"]),
            str(row["candidate"]),
            str(row["baseline"]),
            str(row["metric"]),
        ): row
        for row in effects
    }


def _guarded_decision(
    run_rows: list[dict[str, object]],
    scenario_rows: list[dict[str, object]],
    effects: list[dict[str, object]],
    scenario_count: int,
) -> dict[str, object]:
    lookup = _effect_lookup(effects)
    rmse = lookup[
        (
            "overall",
            "flocking_guarded_momentum",
            "flocking_fixed_momentum",
            "position_rmse",
        )
    ]
    recovery = lookup[
        (
            "overall",
            "flocking_guarded_momentum",
            "flocking_fixed_momentum",
            "recovery_steps",
        )
    ]
    runtime = lookup[
        (
            "overall",
            "flocking_guarded_momentum",
            "flocking_fixed_momentum",
            "runtime_seconds",
        )
    ]
    communication = lookup[
        (
            "overall",
            "flocking_guarded_momentum",
            "flocking_fixed_momentum",
            "bytes_sent",
        )
    ]

    indexed = {
        (str(row["scenario"]), str(row["algorithm"])): row
        for row in scenario_rows
    }
    scenario_names = sorted({str(row["scenario"]) for row in scenario_rows})
    wins = sum(
        float(indexed[(scenario, "flocking_guarded_momentum")]["position_rmse_mean"])
        < float(indexed[(scenario, "flocking_fixed_momentum")]["position_rmse_mean"])
        for scenario in scenario_names
    )

    stress_rows = [
        indexed[(scenario, "flocking_guarded_momentum")]
        for scenario in ("communication_delay", "biased_agents")
        if (scenario, "flocking_guarded_momentum") in indexed
    ]
    stress_calibrated = bool(stress_rows) and all(
        0.93 <= float(row["coverage95_rate_mean"]) <= 0.97
        and 1.5 <= float(row["mean_nees_mean"]) <= 2.5
        for row in stress_rows
    )

    delay_row = indexed.get(("communication_delay", "flocking_guarded_momentum"))
    bias_row = indexed.get(("biased_agents", "flocking_guarded_momentum"))
    no_change_row = indexed.get(("no_change", "flocking_guarded_momentum"))
    stale_guard = delay_row is not None and float(
        delay_row["momentum_fallback_rate_mean"]
    ) >= 0.98
    bias_guard = bias_row is not None and float(
        bias_row["mean_momentum_biased_agents_mean"]
    ) >= 0.5
    false_event_guard = no_change_row is not None and float(
        no_change_row["momentum_change_events_mean"]
    ) <= 0.25

    gates = {
        "rmse_significant_vs_fixed": float(rmse["ci95_lower"]) > 0.0,
        "recovery_significant_vs_fixed": float(recovery["ci95_lower"]) > 0.0,
        "calibrated_under_delay_and_bias": stress_calibrated,
        "wins_at_least_five_of_seven_scenarios": wins >= max(1, scenario_count - 2),
        "stale_messages_force_fixed_fallback": stale_guard,
        "persistent_bias_is_detected": bias_guard,
        "false_change_events_are_bounded": false_event_guard,
        "communication_overhead_under_2_percent": (
            float(communication["candidate_mean"])
            <= 1.02 * float(communication["baseline_mean"])
        ),
        "runtime_overhead_under_25_percent": (
            float(runtime["candidate_mean"])
            <= 1.25 * float(runtime["baseline_mean"])
        ),
    }
    if all(gates.values()):
        verdict = "GO"
        research_direction = "ADVANCE_GUARDED_MOMENTUM"
    elif (
        float(rmse["ci95_upper"]) < 0.0
        or not stress_calibrated
        or not stale_guard
        or not bias_guard
    ):
        verdict = "NO-GO"
        research_direction = "RETAIN_FIXED_MOMENTUM_AND_MOVE_TO_M6"
    else:
        verdict = "INCONCLUSIVE"
        research_direction = "REFINE_GUARDED_CLASSIFIER_WITHOUT_PROMOTION"

    return {
        "verdict": verdict,
        "verdict_scope": "M5 guarded adaptive momentum prototype",
        "research_direction": research_direction,
        "gates": gates,
        "scenarios_won_vs_fixed": int(wins),
        "scenario_count": scenario_count,
        "guarded_rmse_improvement": float(rmse["improvement_mean"]),
        "guarded_rmse_ci95": [float(rmse["ci95_lower"]), float(rmse["ci95_upper"])],
        "guarded_recovery_improvement": float(recovery["improvement_mean"]),
        "guarded_recovery_ci95": [
            float(recovery["ci95_lower"]),
            float(recovery["ci95_upper"]),
        ],
    }


def _write_guarded_report(
    path: Path,
    decision: dict[str, object],
    effects: list[dict[str, object]],
    scenario_rows: list[dict[str, object]],
    seed_start: int,
    seed_count: int,
) -> None:
    lookup = _effect_lookup(effects)
    lines = [
        "# Milestone 5: Guarded Adaptive Momentum Decision Report",
        "",
        f"**Verdict: {decision['verdict']}**",
        "",
        f"**Research direction: {decision['research_direction']}**",
        "",
        (
            f"This frozen evaluation uses {seed_count} seeds "
            f"({seed_start}–{seed_start + seed_count - 1}), common random numbers, "
            "the seven preregistered stress scenarios, and paired bootstrap 95% "
            "confidence intervals."
        ),
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
            "## Overall paired effects",
            "",
            "Positive improvement means the candidate is better than its baseline.",
            "",
            "| Candidate | Baseline | Metric | Baseline | Candidate | Improvement | 95% CI | Wins / losses |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for candidate, baseline in M5_COMPARISONS:
        for metric in (
            "position_rmse",
            "recovery_steps",
            "information_gain",
            "coverage_calibration_error",
            "runtime_seconds",
        ):
            row = lookup[("overall", candidate, baseline, metric)]
            lines.append(
                f"| {candidate} | {baseline} | {metric} | "
                f"{float(row['baseline_mean']):.4f} | {float(row['candidate_mean']):.4f} | "
                f"{float(row['improvement_mean']):.4f} | "
                f"[{float(row['ci95_lower']):.4f}, {float(row['ci95_upper']):.4f}] | "
                f"{row['wins']} / {row['losses']} |"
            )

    indexed = {
        (str(row["scenario"]), str(row["algorithm"])): row
        for row in scenario_rows
    }
    lines.extend(
        [
            "",
            "## Scenario diagnostics",
            "",
            "| Scenario | Fixed RMSE | Guarded RMSE | Direct-NIS RMSE | Guarded events | Fallback rate | Bias flags |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for scenario in sorted({str(row["scenario"]) for row in scenario_rows}):
        fixed = indexed[(scenario, "flocking_fixed_momentum")]
        guarded = indexed[(scenario, "flocking_guarded_momentum")]
        adaptive = indexed[(scenario, "flocking_adaptive_momentum")]
        lines.append(
            f"| {scenario} | {float(fixed['position_rmse_mean']):.4f} | "
            f"{float(guarded['position_rmse_mean']):.4f} | "
            f"{float(adaptive['position_rmse_mean']):.4f} | "
            f"{float(guarded['momentum_change_events_mean']):.2f} | "
            f"{float(guarded['momentum_fallback_rate_mean']):.3f} | "
            f"{float(guarded['mean_momentum_biased_agents_mean']):.2f} |"
        )

    lines.extend(["", "## Interpretation", ""])
    if decision["verdict"] == "GO":
        lines.append(
            "The guarded controller cleared every preregistered gate and may advance as the experimental adaptive policy, while fixed recurrence remains the operational fallback."
        )
    elif decision["verdict"] == "NO-GO":
        lines.append(
            "The guarded controller did not clear the promotion gates. Fixed recurrence remains the supported controller; the next engineering investment should address robust fusion and explicit bias state in M6 rather than add acceleration."
        )
    else:
        lines.append(
            "The result is not strong enough for promotion or rejection. Any refinement must be trained on separate seeds and rerun against a new frozen held-out set."
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_guarded_decision_suite(
    base_config: ExperimentConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 100,
    seed_start: int = 2000,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
    scenario_names: Iterable[str] | None = None,
) -> dict[str, object]:
    """Run the frozen M5 comparison against fixed and rejected direct-NIS controls."""
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
            algorithms=list(M5_ALGORITHMS),
        )
        config.validate()
        scenario_configs[scenario.name] = config.to_dict()
        for algorithm in M5_ALGORITHMS:
            for seed in seeds:
                tasks.append((scenario.name, config.to_dict(), algorithm, seed))

    worker_count = workers or min(os.cpu_count() or 2, 8)
    executor_kind = "serial"
    if worker_count == 1:
        run_rows = [_worker(task) for task in tasks]
    else:
        try:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                run_rows = list(executor.map(_worker, tasks, chunksize=4))
            executor_kind = "process"
        except (PermissionError, OSError):
            # Restricted containers may prohibit POSIX semaphores. NumPy's
            # linear algebra releases the GIL, so a thread pool is still a
            # useful and deterministic fallback for this workload.
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                run_rows = list(executor.map(_worker, tasks))
            executor_kind = "thread_fallback"

    order_scenario = {scenario.name: index for index, scenario in enumerate(scenarios)}
    order_algorithm = {algorithm: index for index, algorithm in enumerate(M5_ALGORITHMS)}
    run_rows.sort(
        key=lambda row: (
            order_scenario[str(row["scenario"])],
            order_algorithm[str(row["algorithm"])],
            int(row["seed"]),
        )
    )
    scenario_rows = _scenario_summary(run_rows)
    effects = _paired_effects(
        run_rows,
        scenarios,
        seeds,
        bootstrap_samples,
        M5_COMPARISONS,
    )
    decision = _guarded_decision(run_rows, scenario_rows, effects, len(scenarios))

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
        "executor": executor_kind,
        "algorithms": list(M5_ALGORITHMS),
        "comparisons": [list(item) for item in M5_COMPARISONS],
        "scenarios": [asdict(scenario) for scenario in scenarios],
        "scenario_configs": scenario_configs,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "platform_version": "0.12.0",
    }
    (output / "suite_config.json").write_text(
        json.dumps(suite_config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_guarded_report(
        output / "milestone5_report.md",
        decision,
        effects,
        scenario_rows,
        seed_start,
        seed_count,
    )
    return decision


def reanalyze_guarded_decision_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    """Regenerate M5 statistical artifacts without rerunning trials."""
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
    effects = _paired_effects(
        run_rows,
        scenarios,
        seeds,
        samples,
        M5_COMPARISONS,
    )
    decision = _guarded_decision(run_rows, scenario_rows, effects, len(scenarios))
    _write_csv(output / "scenario_summary.csv", scenario_rows)
    _write_csv(output / "paired_effects.csv", effects)
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_guarded_report(
        output / "milestone5_report.md",
        decision,
        effects,
        scenario_rows,
        seed_start,
        seed_count,
    )
    return decision
