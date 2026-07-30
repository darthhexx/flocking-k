"""Diagnostic rho/tau mechanism study for fixed behavioural recurrence."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import asdict, replace
import json
import math
import os
from pathlib import Path
import platform
from time import perf_counter
from typing import Iterable

import numpy as np

from .config import ExperimentConfig
from .experiment import run_trial
from .metrics import summarize_run
from .suite import ScenarioDefinition, _write_csv


DEFAULT_RHOS = (0.0, 0.25, 0.50, 0.72, 0.85, 0.93)
MECHANISM_SCENARIOS = (
    ScenarioDefinition(
        "no_change",
        "No target regime change; exposes pure trajectory smoothing.",
        {"target_change_mode": "none"},
    ),
    ScenarioDefinition(
        "abrupt_change",
        "One abrupt target velocity change.",
        {"target_change_mode": "abrupt"},
    ),
    ScenarioDefinition(
        "gradual_10",
        "Velocity change distributed over ten cycles.",
        {"target_change_mode": "gradual", "gradual_change_duration": 10},
    ),
    ScenarioDefinition(
        "gradual_20",
        "Velocity change distributed over twenty cycles.",
        {"target_change_mode": "gradual", "gradual_change_duration": 20},
    ),
    ScenarioDefinition(
        "gradual_40",
        "Velocity change distributed over forty cycles.",
        {"target_change_mode": "gradual", "gradual_change_duration": 40},
    ),
    ScenarioDefinition(
        "repeated_20",
        "Repeated turns every twenty cycles.",
        {"target_change_mode": "repeated", "repeated_change_interval": 20},
    ),
    ScenarioDefinition(
        "repeated_35",
        "Repeated turns every thirty-five cycles.",
        {"target_change_mode": "repeated", "repeated_change_interval": 35},
    ),
    ScenarioDefinition(
        "repeated_50",
        "Repeated turns every fifty cycles.",
        {"target_change_mode": "repeated", "repeated_change_interval": 50},
    ),
)


def recurrence_time_constant(rho: float, dt: float) -> float:
    """Return tau from rho = exp(-dt/tau), with zero as the no-memory limit."""
    if not 0.0 <= rho < 1.0:
        raise ValueError("rho must be in [0, 1)")
    if dt <= 0.0:
        raise ValueError("dt must be positive")
    return 0.0 if rho == 0.0 else -dt / math.log(rho)


def _rho_label(rho: float) -> str:
    return f"rho_{rho:.2f}".replace(".", "_")


def _scenario_timescale(config: ExperimentConfig) -> float:
    if config.target_change_mode == "gradual":
        return float(config.gradual_change_duration)
    if config.target_change_mode == "repeated":
        return float(config.repeated_change_interval)
    if config.target_change_mode == "abrupt":
        return float(config.change_step)
    return float(config.steps)


def _worker(task: tuple[str, dict[str, object], float, int]) -> dict[str, object]:
    scenario, config_data, rho, seed = task
    config = ExperimentConfig(**config_data)
    started = perf_counter()
    records = run_trial(config, "flocking_fixed_momentum", seed)
    summary = summarize_run(config, records)
    summary.update(
        {
            "scenario": scenario,
            "rho": rho,
            "rho_label": _rho_label(rho),
            "tau": recurrence_time_constant(rho, config.dt),
            "scenario_timescale": _scenario_timescale(config),
            "runtime_seconds": perf_counter() - started,
        }
    )
    summary["tau_to_timescale"] = float(summary["tau"]) / float(
        summary["scenario_timescale"]
    )
    return summary


def _cell_summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, float], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["scenario"]), float(row["rho"])), []).append(row)
    metrics = (
        "position_rmse",
        "agent_position_rmse",
        "information_gain",
        "spatial_diversity",
        "estimate_disagreement",
        "movement_distance",
        "coverage95_rate",
        "mean_nees",
        "runtime_seconds",
    )
    result: list[dict[str, object]] = []
    for (scenario, rho), group in grouped.items():
        item: dict[str, object] = {
            "scenario": scenario,
            "rho": rho,
            "rho_label": _rho_label(rho),
            "tau": float(group[0]["tau"]),
            "scenario_timescale": float(group[0]["scenario_timescale"]),
            "tau_to_timescale": float(group[0]["tau_to_timescale"]),
            "runs": len(group),
        }
        for metric in metrics:
            values = np.asarray([float(row[metric]) for row in group], dtype=float)
            item[f"{metric}_mean"] = float(np.mean(values))
            item[f"{metric}_std"] = float(np.std(values))
        result.append(item)
    return result


def _paired_mechanism(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    indexed = {
        (str(row["scenario"]), float(row["rho"]), int(row["seed"])): row
        for row in rows
    }
    scenarios = sorted({str(row["scenario"]) for row in rows})
    rhos = sorted({float(row["rho"]) for row in rows})
    seeds = sorted({int(row["seed"]) for row in rows})
    paired: list[dict[str, object]] = []
    for scenario in scenarios:
        for rho in rhos:
            if rho == 0.0:
                continue
            for seed in seeds:
                baseline = indexed[(scenario, 0.0, seed)]
                candidate = indexed[(scenario, rho, seed)]
                paired.append(
                    {
                        "scenario": scenario,
                        "rho": rho,
                        "rho_label": _rho_label(rho),
                        "seed": seed,
                        "rmse_improvement": float(baseline["position_rmse"])
                        - float(candidate["position_rmse"]),
                        "diversity_change": float(candidate["spatial_diversity"])
                        - float(baseline["spatial_diversity"]),
                        "disagreement_change": float(candidate["estimate_disagreement"])
                        - float(baseline["estimate_disagreement"]),
                        "information_change": float(candidate["information_gain"])
                        - float(baseline["information_gain"]),
                        "movement_change": float(candidate["movement_distance"])
                        - float(baseline["movement_distance"]),
                    }
                )
    return paired


def _correlation(first: np.ndarray, second: np.ndarray) -> float | None:
    if len(first) < 3 or np.std(first) <= 1e-12 or np.std(second) <= 1e-12:
        return None
    return float(np.corrcoef(first, second)[0, 1])


def _center_within_cells(
    rows: list[dict[str, object]], metric: str
) -> np.ndarray:
    grouped: dict[tuple[str, float], list[int]] = {}
    for index, row in enumerate(rows):
        grouped.setdefault((str(row["scenario"]), float(row["rho"])), []).append(index)
    values = np.asarray([float(row[metric]) for row in rows], dtype=float)
    centered = values.copy()
    for indices in grouped.values():
        centered[indices] -= float(np.mean(values[indices]))
    return centered


def _analysis(
    cells: list[dict[str, object]], paired: list[dict[str, object]]
) -> dict[str, object]:
    nonzero_cells = [row for row in cells if float(row["rho"]) > 0.0]
    grouped_paired: dict[tuple[str, float], list[dict[str, object]]] = {}
    for row in paired:
        grouped_paired.setdefault((str(row["scenario"]), float(row["rho"])), []).append(row)
    cell_effects: list[dict[str, object]] = []
    for key, group in grouped_paired.items():
        item = {
            "scenario": key[0],
            "rho": key[1],
            "rmse_improvement": float(
                np.mean([float(row["rmse_improvement"]) for row in group])
            ),
            "diversity_change": float(
                np.mean([float(row["diversity_change"]) for row in group])
            ),
            "disagreement_change": float(
                np.mean([float(row["disagreement_change"]) for row in group])
            ),
            "information_change": float(
                np.mean([float(row["information_change"]) for row in group])
            ),
            "movement_change": float(
                np.mean([float(row["movement_change"]) for row in group])
            ),
        }
        cell_effects.append(item)
    cell_improvement = np.asarray(
        [float(row["rmse_improvement"]) for row in cell_effects], dtype=float
    )
    best_by_scenario: list[dict[str, object]] = []
    for scenario in sorted({str(row["scenario"]) for row in cells}):
        choices = [row for row in cells if row["scenario"] == scenario]
        best = min(choices, key=lambda row: float(row["position_rmse_mean"]))
        best_by_scenario.append(
            {
                "scenario": scenario,
                "best_rho": float(best["rho"]),
                "best_tau": float(best["tau"]),
                "timescale": float(best["scenario_timescale"]),
                "tau_to_timescale": float(best["tau_to_timescale"]),
                "position_rmse": float(best["position_rmse_mean"]),
            }
        )
    centered_improvement = _center_within_cells(paired, "rmse_improvement")
    centered_diversity = _center_within_cells(paired, "diversity_change")
    centered_disagreement = _center_within_cells(paired, "disagreement_change")
    centered_information = _center_within_cells(paired, "information_change")
    between_diversity = _correlation(
        cell_improvement,
        np.asarray([float(row["diversity_change"]) for row in cell_effects]),
    )
    within_diversity = _correlation(centered_improvement, centered_diversity)
    within_disagreement = _correlation(centered_improvement, centered_disagreement)
    within_information = _correlation(centered_improvement, centered_information)
    best_nonzero_fraction = float(
        np.mean([float(row["best_rho"]) > 0.0 for row in best_by_scenario])
    )
    geometry_supported = (
        between_diversity is not None
        and between_diversity >= 0.40
        and within_diversity is not None
        and within_diversity >= 0.15
    )
    verdict = "GEOMETRY-MECHANISM-SUPPORTED" if geometry_supported else "MECHANISM-UNRESOLVED"
    return {
        "verdict": verdict,
        "geometry_mechanism_supported": geometry_supported,
        "best_nonzero_rho_fraction": best_nonzero_fraction,
        "between_cell_rmse_improvement_vs_diversity_change_correlation": between_diversity,
        "within_cell_rmse_improvement_vs_diversity_change_correlation": within_diversity,
        "within_cell_rmse_improvement_vs_disagreement_change_correlation": within_disagreement,
        "within_cell_rmse_improvement_vs_information_change_correlation": within_information,
        "best_by_scenario": best_by_scenario,
        "cell_effects": cell_effects,
        "nonzero_cells": len(nonzero_cells),
    }


def _write_report(
    path: Path,
    analysis: dict[str, object],
    cells: list[dict[str, object]],
    seed_start: int,
    seed_count: int,
) -> None:
    best = {str(row["scenario"]): row for row in analysis["best_by_scenario"]}
    lines = [
        "# Fixed-Recurrence Mechanism Study",
        "",
        f"**Diagnostic verdict: {analysis['verdict']}**",
        "",
        (
            f"This training-only study uses {seed_count} seeds "
            f"({seed_start}–{seed_start + seed_count - 1}). It sweeps rho and reports "
            "tau = -dt/log(rho) across target-change timescales. It is a mechanism "
            "diagnostic, not a new promotion test."
        ),
        "",
        "## Correlations",
        "",
        f"- Between-cell RMSE improvement vs diversity change: `{analysis['between_cell_rmse_improvement_vs_diversity_change_correlation']}`",
        f"- Within-cell paired RMSE improvement vs diversity change: `{analysis['within_cell_rmse_improvement_vs_diversity_change_correlation']}`",
        f"- Within-cell paired RMSE improvement vs disagreement change: `{analysis['within_cell_rmse_improvement_vs_disagreement_change_correlation']}`",
        f"- Within-cell paired RMSE improvement vs information change: `{analysis['within_cell_rmse_improvement_vs_information_change_correlation']}`",
        "",
        "## Best recurrence by scenario",
        "",
        "| Scenario | Best rho | Tau | Scenario timescale | Tau/timescale | RMSE |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for scenario in sorted(best):
        row = best[scenario]
        lines.append(
            f"| {scenario} | {float(row['best_rho']):.2f} | {float(row['best_tau']):.3f} | "
            f"{float(row['timescale']):.1f} | {float(row['tau_to_timescale']):.4f} | "
            f"{float(row['position_rmse']):.4f} |"
        )
    lines.extend(
        [
            "",
            "## Full cell means",
            "",
            "| Scenario | Rho | Tau | RMSE | Diversity | Disagreement | Information |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in cells:
        lines.append(
            f"| {row['scenario']} | {float(row['rho']):.2f} | {float(row['tau']):.3f} | "
            f"{float(row['position_rmse_mean']):.4f} | "
            f"{float(row['spatial_diversity_mean']):.3f} | "
            f"{float(row['estimate_disagreement_mean']):.3f} | "
            f"{float(row['information_gain_mean']):.3f} |"
        )
    lines.extend(
        [
            "",
            "Correlation is not mediation. A supported geometry signature motivates a causal geometry ablation; an unresolved signature means rho remains an empirical scenario-family setting.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_momentum_mechanism_study(
    base_config: ExperimentConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 30,
    seed_start: int = 8000,
    rhos: Iterable[float] = DEFAULT_RHOS,
    scenario_names: Iterable[str] | None = None,
    workers: int | None = None,
) -> dict[str, object]:
    """Run the training-only rho/tau and sensor-geometry diagnostic."""
    if seed_count < 2:
        raise ValueError("seed_count must be at least two")
    rho_tuple = tuple(float(value) for value in rhos)
    if not rho_tuple or rho_tuple[0] != 0.0 or any(
        second <= first for first, second in zip(rho_tuple, rho_tuple[1:])
    ):
        raise ValueError("rhos must be strictly increasing and start at zero")
    for rho in rho_tuple:
        recurrence_time_constant(rho, base_config.dt)
    requested = set(scenario_names) if scenario_names is not None else None
    scenarios = tuple(
        scenario
        for scenario in MECHANISM_SCENARIOS
        if requested is None or scenario.name in requested
    )
    known = {scenario.name for scenario in MECHANISM_SCENARIOS}
    if requested is not None and requested - known:
        raise ValueError(
            f"unknown mechanism scenarios: {', '.join(sorted(requested - known))}"
        )
    if not scenarios:
        raise ValueError("at least one mechanism scenario is required")
    seeds = list(range(seed_start, seed_start + seed_count))
    tasks: list[tuple[str, dict[str, object], float, int]] = []
    scenario_configs: dict[str, dict[str, object]] = {}
    for scenario in scenarios:
        overrides = dict(scenario.overrides)
        if base_config.steps < 60:
            if "gradual_change_duration" in overrides:
                overrides["gradual_change_duration"] = min(
                    int(overrides["gradual_change_duration"]), max(2, base_config.steps // 3)
                )
            if "repeated_change_interval" in overrides:
                overrides["repeated_change_interval"] = min(
                    int(overrides["repeated_change_interval"]), max(3, base_config.steps // 3)
                )
        scenario_config = replace(
            base_config,
            **overrides,
            seeds=seeds,
            algorithms=["flocking_fixed_momentum"],
        )
        scenario_config.validate()
        scenario_configs[scenario.name] = scenario_config.to_dict()
        for rho in rho_tuple:
            config = replace(
                scenario_config,
                fixed_momentum=rho,
                # The guarded controller is not run here, but the shared
                # configuration invariant requires its change value not to
                # exceed the fixed recurrence setting.
                guarded_change_momentum=min(
                    scenario_config.guarded_change_momentum, rho
                ),
            )
            for seed in seeds:
                tasks.append((scenario.name, config.to_dict(), rho, seed))
    worker_count = workers or min(os.cpu_count() or 2, 8)
    executor_kind = "serial"
    if worker_count == 1:
        rows = [_worker(task) for task in tasks]
    else:
        try:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                rows = list(executor.map(_worker, tasks, chunksize=4))
            executor_kind = "process"
        except (PermissionError, OSError):
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                rows = list(executor.map(_worker, tasks))
            executor_kind = "thread_fallback"
    scenario_order = {scenario.name: index for index, scenario in enumerate(scenarios)}
    rows.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            rho_tuple.index(float(row["rho"])),
            int(row["seed"]),
        )
    )
    cells = _cell_summaries(rows)
    cells.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])], rho_tuple.index(float(row["rho"]))
        )
    )
    paired = _paired_mechanism(rows)
    analysis = _analysis(cells, paired)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "run_summary.csv", rows)
    _write_csv(output / "cell_summary.csv", cells)
    _write_csv(output / "paired_mechanism.csv", paired)
    suite_config = {
        "seed_start": seed_start,
        "seed_count": seed_count,
        "rhos": list(rho_tuple),
        "scenarios": [asdict(scenario) for scenario in scenarios],
        "scenario_configs": scenario_configs,
        "workers": worker_count,
        "executor": executor_kind,
        "platform_version": "0.11.0",
        "python": platform.python_version(),
        "numpy": np.__version__,
    }
    (output / "suite_config.json").write_text(
        json.dumps(suite_config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "mechanism.json").write_text(
        json.dumps(analysis, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_report(
        output / "momentum_mechanism_report.md",
        analysis,
        cells,
        seed_start,
        seed_count,
    )
    return analysis
