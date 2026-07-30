"""Milestone 6 evaluation for robust fusion and explicit hypothesis flocks."""

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
    ScenarioDefinition,
    _paired_effects,
    _scenario_summary,
    _worker,
    _write_csv,
)


M6_ALGORITHMS = (
    "flocking_fixed_momentum",
    "flocking_robust_multiflock",
)

M6_COMPARISONS = (
    ("flocking_robust_multiflock", "flocking_fixed_momentum"),
)

M6_SCENARIOS = (
    ScenarioDefinition(
        "no_change",
        "Nominal stationary dynamics expose false quarantine and false mode splitting.",
        {"target_change_mode": "none"},
    ),
    ScenarioDefinition(
        "abrupt_change",
        "Nominal abrupt manoeuvre checks that robust fusion retains baseline utility.",
        {"target_change_mode": "abrupt"},
    ),
    ScenarioDefinition(
        "mixed_dropout",
        "Observation and directed-link dropout stress sparse compatible fusion.",
        {"measurement_dropout_rate": 0.20, "communication_dropout_rate": 0.15},
    ),
    ScenarioDefinition(
        "communication_delay",
        "Two-cycle peer delay tests compatibility gating with stale beliefs.",
        {"communication_delay_steps": 2},
    ),
    ScenarioDefinition(
        "biased_agents",
        "Two persistent minority offsets require bias-state estimation and quarantine.",
        {"biased_agent_count": 2, "measurement_bias": (2.5, -2.0)},
    ),
    ScenarioDefinition(
        "byzantine_agent",
        "One confidently false source reports a large offset and understated covariance.",
        {
            "byzantine_agent_count": 1,
            "byzantine_offset": (8.0, -7.0),
            "byzantine_covariance_scale": 0.10,
        },
    ),
    ScenarioDefinition(
        "multimodal_equal",
        "Four sources support a persistent alternative mode that must remain explicit.",
        {
            "secondary_mode_agent_count": 4,
            "secondary_mode_offset": (5.0, -4.0),
        },
    ),
)


def _lookup(
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


def _decision(
    scenario_rows: list[dict[str, object]],
    effects: list[dict[str, object]],
    scenario_count: int,
) -> dict[str, object]:
    effect = _lookup(effects)
    candidate = "flocking_robust_multiflock"
    baseline = "flocking_fixed_momentum"
    overall = effect[("overall", candidate, baseline, "best_hypothesis_rmse")]
    bias = effect.get(
        ("biased_agents", candidate, baseline, "position_rmse"),
        overall,
    )
    byzantine = effect.get(
        ("byzantine_agent", candidate, baseline, "position_rmse"),
        overall,
    )
    nominal = effect.get(
        ("no_change", candidate, baseline, "position_rmse"),
        overall,
    )
    delay = effect.get(
        ("communication_delay", candidate, baseline, "position_rmse"),
        overall,
    )
    dropout = effect.get(
        ("mixed_dropout", candidate, baseline, "position_rmse"),
        overall,
    )
    multimodal_effect = effect.get(
        ("multimodal_equal", candidate, baseline, "best_hypothesis_rmse"),
        overall,
    )
    runtime = effect[("overall", candidate, baseline, "runtime_seconds")]
    communication = effect[("overall", candidate, baseline, "bytes_sent")]
    indexed = {
        (str(row["scenario"]), str(row["algorithm"])): row
        for row in scenario_rows
    }
    robust_bias_rows = [
        indexed[(scenario, candidate)]
        for scenario in ("biased_agents", "byzantine_agent")
        if (scenario, candidate) in indexed
    ]
    calibrated = bool(robust_bias_rows) and all(
        0.90 <= float(row["coverage95_rate_mean"]) <= 0.98
        and 1.0 <= float(row["mean_nees_mean"]) <= 3.0
        for row in robust_bias_rows
    )
    multimodal = indexed.get(("multimodal_equal", candidate))
    nominal_row = indexed.get(("no_change", candidate))
    scenario_names = sorted({str(row["scenario"]) for row in scenario_rows})
    wins = sum(
        float(indexed[(scenario, candidate)]["best_hypothesis_rmse_mean"])
        < float(indexed[(scenario, baseline)]["best_hypothesis_rmse_mean"])
        for scenario in scenario_names
    )
    gates = {
        "overall_set_rmse_significant_vs_fixed": float(overall["ci95_lower"]) > 0.0,
        "bias_rmse_significant_vs_fixed": float(bias["ci95_lower"]) > 0.0,
        "byzantine_rmse_significant_vs_fixed": float(byzantine["ci95_lower"]) > 0.0,
        "multimodal_set_rmse_significant_vs_fixed": float(
            multimodal_effect["ci95_lower"]
        ) > 0.0,
        "nominal_rmse_noninferior_within_0_02": float(nominal["ci95_lower"]) > -0.02,
        "dropout_rmse_noninferior_within_0_03": float(dropout["ci95_lower"]) > -0.03,
        "delay_rmse_noninferior_within_0_05": float(delay["ci95_lower"]) > -0.05,
        "biased_outputs_are_calibrated": calibrated,
        "alternative_mode_survives": (
            multimodal is not None
            and float(multimodal["multiflock_rate_mean"]) >= 0.50
            and float(multimodal["mean_alternative_flock_weight_mean"]) >= 0.25
            and float(multimodal["mean_truth_consistent_flock_weight_mean"]) >= 0.25
        ),
        "false_quarantine_is_bounded": (
            nominal_row is not None
            and float(nominal_row["mean_quarantined_agents_mean"]) <= 0.25
        ),
        "communication_overhead_under_2_percent": (
            float(communication["candidate_mean"])
            <= 1.02 * float(communication["baseline_mean"])
        ),
        "runtime_overhead_under_50_percent": (
            float(runtime["candidate_mean"])
            <= 1.50 * float(runtime["baseline_mean"])
        ),
    }
    if all(gates.values()):
        verdict = "GO"
        research_direction = "ADVANCE_ROBUST_MULTIFLOCK_TO_END_TO_END_EVALUATION"
    elif (
        float(overall["ci95_upper"]) < 0.0
        or not gates["alternative_mode_survives"]
        or not gates["false_quarantine_is_bounded"]
    ):
        verdict = "NO-GO"
        research_direction = "RETAIN_FIXED_FUSION_AND_REDESIGN_M6"
    else:
        verdict = "INCONCLUSIVE"
        research_direction = "REFINE_M6_WITHOUT_PRODUCTION_PROMOTION"
    return {
        "verdict": verdict,
        "verdict_scope": "M6 robust fusion and explicit hypothesis flocks",
        "research_direction": research_direction,
        "gates": gates,
        "scenarios_won_vs_fixed": int(wins),
        "scenario_count": scenario_count,
        "overall_set_rmse_improvement": float(overall["improvement_mean"]),
        "overall_set_rmse_ci95": [
            float(overall["ci95_lower"]),
            float(overall["ci95_upper"]),
        ],
        "bias_rmse_improvement": float(bias["improvement_mean"]),
        "byzantine_rmse_improvement": float(byzantine["improvement_mean"]),
        "multimodal_flock_survival_rate": (
            float(multimodal["multiflock_rate_mean"]) if multimodal else None
        ),
        "multimodal_alternative_weight": (
            float(multimodal["mean_alternative_flock_weight_mean"])
            if multimodal
            else None
        ),
        "multimodal_truth_consistent_weight": (
            float(multimodal["mean_truth_consistent_flock_weight_mean"])
            if multimodal
            else None
        ),
    }


def _write_report(
    path: Path,
    decision: dict[str, object],
    effects: list[dict[str, object]],
    scenario_rows: list[dict[str, object]],
    seed_start: int,
    seed_count: int,
) -> None:
    effect = _lookup(effects)
    candidate = "flocking_robust_multiflock"
    baseline = "flocking_fixed_momentum"
    indexed = {
        (str(row["scenario"]), str(row["algorithm"])): row
        for row in scenario_rows
    }
    lines = [
        "# Milestone 6: Robust Fusion and Multi-Flock Decision Report",
        "",
        f"**Verdict: {decision['verdict']}**",
        "",
        f"**Research direction: {decision['research_direction']}**",
        "",
        (
            f"This evaluation uses {seed_count} seeds "
            f"({seed_start}–{seed_start + seed_count - 1}), seven scenarios, common "
            "random numbers, and paired bootstrap 95% confidence intervals."
        ),
        "",
        "## Decision gates",
        "",
        "| Gate | Result |",
        "|---|---|",
    ]
    for gate, passed in dict(decision["gates"]).items():
        label = gate.replace("_", " ")
        label = (
            label.replace("0 02", "0.02")
            .replace("0 03", "0.03")
            .replace("0 05", "0.05")
            .replace("2 percent", "2%")
            .replace("50 percent", "50%")
        )
        lines.append(f"| {label} | {'PASS' if passed else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## Scenario results",
            "",
            "| Scenario | Fixed RMSE | Robust primary RMSE | Robust set RMSE | Set improvement | Set 95% CI | Flocks | Alternative weight | Quarantined |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for scenario in sorted({str(row["scenario"]) for row in scenario_rows}):
        fixed = indexed[(scenario, baseline)]
        robust = indexed[(scenario, candidate)]
        paired = effect[(scenario, candidate, baseline, "best_hypothesis_rmse")]
        lines.append(
            f"| {scenario} | {float(fixed['position_rmse_mean']):.4f} | "
            f"{float(robust['position_rmse_mean']):.4f} | "
            f"{float(robust['best_hypothesis_rmse_mean']):.4f} | "
            f"{float(paired['improvement_mean']):.4f} | "
            f"[{float(paired['ci95_lower']):.4f}, {float(paired['ci95_upper']):.4f}] | "
            f"{float(robust['mean_hypothesis_flocks_mean']):.2f} | "
            f"{float(robust['mean_alternative_flock_weight_mean']):.3f} | "
            f"{float(robust['mean_quarantined_agents_mean']):.2f} |"
        )
    overall = effect[("overall", candidate, baseline, "best_hypothesis_rmse")]
    lines.extend(
        [
            "",
            "## Overall paired effect",
            "",
            (
                f"Robust multi-flock fusion changed hypothesis-set RMSE by "
                f"{float(overall['improvement_mean']):.4f} versus fixed fusion, with "
                f"95% CI [{float(overall['ci95_lower']):.4f}, "
                f"{float(overall['ci95_upper']):.4f}]."
            ),
            "",
            "## Interpretation",
            "",
        ]
    )
    if decision["verdict"] == "GO":
        lines.append(
            "The M6 prototype passed every defined gate. Robust fusion may advance to end-to-end output-policy evaluation while fixed recurrence remains the motion controller."
        )
    elif decision["verdict"] == "NO-GO":
        lines.append(
            "The M6 prototype failed a decisive robustness gate and must not replace the fixed-fusion baseline."
        )
    else:
        lines.append(
            "The M6 prototype is promising but not promotable. Refinement must use separate training seeds before another frozen evaluation."
        )
    lines.extend(
        [
            "",
            "In the symmetric multimodal scenario, the primary-flock tie is intentionally not scored as if the system knew the truth. The hypothesis-set RMSE measures whether at least one returned flock is truth-consistent. A downstream policy for choosing one primary output remains a separate milestone.",
        ]
    )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_robust_decision_suite(
    base_config: ExperimentConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 100,
    seed_start: int = 3000,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
    scenario_names: Iterable[str] | None = None,
) -> dict[str, object]:
    """Run the M6 fixed-versus-robust paired evaluation."""
    if seed_count < 2:
        raise ValueError("seed_count must be at least 2")
    if bootstrap_samples < 100:
        raise ValueError("bootstrap_samples must be at least 100")
    requested = set(scenario_names) if scenario_names is not None else None
    scenarios = tuple(
        scenario
        for scenario in M6_SCENARIOS
        if requested is None or scenario.name in requested
    )
    if requested is not None and requested != {scenario.name for scenario in scenarios}:
        unknown = sorted(requested - {scenario.name for scenario in scenarios})
        raise ValueError(f"unknown M6 scenarios: {', '.join(unknown)}")
    if not scenarios:
        raise ValueError("at least one M6 scenario is required")

    seeds = list(range(seed_start, seed_start + seed_count))
    tasks: list[tuple[str, dict[str, object], str, int]] = []
    scenario_configs: dict[str, dict[str, object]] = {}
    for scenario in scenarios:
        config = replace(
            base_config,
            **scenario.overrides,
            seeds=seeds,
            algorithms=list(M6_ALGORITHMS),
        )
        config.validate()
        scenario_configs[scenario.name] = config.to_dict()
        for algorithm in M6_ALGORITHMS:
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
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                run_rows = list(executor.map(_worker, tasks))
            executor_kind = "thread_fallback"
    order_scenario = {scenario.name: index for index, scenario in enumerate(scenarios)}
    order_algorithm = {algorithm: index for index, algorithm in enumerate(M6_ALGORITHMS)}
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
        M6_COMPARISONS,
    )
    decision = _decision(scenario_rows, effects, len(scenarios))
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
        "algorithms": list(M6_ALGORITHMS),
        "comparisons": [list(item) for item in M6_COMPARISONS],
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
    _write_report(
        output / "milestone6_report.md",
        decision,
        effects,
        scenario_rows,
        seed_start,
        seed_count,
    )
    return decision


def reanalyze_robust_decision_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    """Regenerate M6 statistical artifacts without rerunning trials."""
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
        M6_COMPARISONS,
    )
    decision = _decision(scenario_rows, effects, len(scenarios))
    _write_csv(output / "scenario_summary.csv", scenario_rows)
    _write_csv(output / "paired_effects.csv", effects)
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_report(
        output / "milestone6_report.md",
        decision,
        effects,
        scenario_rows,
        seed_start,
        seed_count,
    )
    return decision
