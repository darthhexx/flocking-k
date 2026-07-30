"""Milestone 7 evaluation for truth-blind hypothesis-output policies."""

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


M7_ACTIVE = "flocking_robust_active"
M7_BASELINES = (
    "flocking_robust_multiflock",
    "flocking_robust_temporal",
    "flocking_robust_mixture",
    "flocking_robust_defer",
)
M7_ALGORITHMS = M7_BASELINES + (M7_ACTIVE,)
M7_COMPARISONS = tuple((M7_ACTIVE, baseline) for baseline in M7_BASELINES)

SENSITIVITY_COSTS = (0.25, 0.50, 1.00, 1.50)


def _cost_metric(cost: float) -> str:
    return f"decision_loss_defer_{cost:.2f}".replace(".", "_")


M7_EFFECT_METRICS = {
    "decision_loss": "lower",
    "best_hypothesis_rmse": "lower",
    "wrong_mode_action_rate": "lower",
    "movement_distance": "lower",
    "runtime_seconds": "lower",
    "bytes_sent": "lower",
    **{_cost_metric(cost): "lower" for cost in SENSITIVITY_COSTS},
}

M7_SCENARIOS = (
    ScenarioDefinition(
        "no_change",
        "Nominal dynamics test unnecessary abstention and false ambiguity.",
        {"target_change_mode": "none"},
    ),
    ScenarioDefinition(
        "mixed_dropout",
        "Observation and communication dropout test output stability.",
        {"measurement_dropout_rate": 0.20, "communication_dropout_rate": 0.15},
    ),
    ScenarioDefinition(
        "communication_delay",
        "Two-cycle delay verifies the M6 age-alignment protection remains intact.",
        {"communication_delay_steps": 2},
    ),
    ScenarioDefinition(
        "biased_agents",
        "Two biased sources verify that output logic preserves quarantine behaviour.",
        {"biased_agent_count": 2, "measurement_bias": (2.5, -2.0)},
    ),
    ScenarioDefinition(
        "byzantine_agent",
        "One confidently false source verifies robust primary output after quarantine.",
        {
            "byzantine_agent_count": 1,
            "byzantine_offset": (8.0, -7.0),
            "byzantine_covariance_scale": 0.10,
        },
    ),
    ScenarioDefinition(
        "multimodal_unequal",
        "A supported three-agent alternative should yield to the five-agent mode.",
        {
            "target_change_mode": "none",
            "secondary_mode_agent_count": 3,
            "secondary_mode_offset": (5.0, -4.0),
        },
    ),
    ScenarioDefinition(
        "multimodal_equal",
        "Persistent four-versus-four evidence should produce explicit abstention.",
        {
            "target_change_mode": "none",
            "secondary_mode_agent_count": 4,
            "secondary_mode_offset": (5.0, -4.0),
        },
    ),
    ScenarioDefinition(
        "multimodal_transient",
        "Equal ambiguity from steps 20–89 should be detected and later resolved.",
        {
            "target_change_mode": "none",
            "secondary_mode_agent_count": 4,
            "secondary_mode_offset": (5.0, -4.0),
            "secondary_mode_start_step": 20,
            "secondary_mode_end_step": 90,
        },
    ),
)


def _m7_worker(task: tuple[str, dict[str, object], str, int]) -> dict[str, object]:
    row = _worker(task)
    config = ExperimentConfig(**task[1])
    base_error = float(row["mean_decision_base_error"])
    abstention_rate = float(row["abstention_rate"])
    investigation_rate = float(row["investigation_rate"])
    for cost in SENSITIVITY_COSTS:
        row[_cost_metric(cost)] = (
            base_error
            + cost * abstention_rate
            + config.output_investigation_cost * investigation_rate
        )
    return row


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
) -> dict[str, object]:
    effect = _lookup(effects)
    indexed = {
        (str(row["scenario"]), str(row["algorithm"])): row
        for row in scenario_rows
    }
    largest = "flocking_robust_multiflock"
    always_defer = "flocking_robust_defer"
    mixture = "flocking_robust_mixture"

    overall_effects = [
        effect[("overall", M7_ACTIVE, baseline, "decision_loss")]
        for baseline in M7_BASELINES
    ]
    nominal = effect[("no_change", M7_ACTIVE, largest, "decision_loss")]
    dropout = effect[("mixed_dropout", M7_ACTIVE, largest, "decision_loss")]
    delay = effect[("communication_delay", M7_ACTIVE, largest, "decision_loss")]
    bias = effect[("biased_agents", M7_ACTIVE, largest, "decision_loss")]
    byzantine = effect[("byzantine_agent", M7_ACTIVE, largest, "decision_loss")]
    equal_vs_defer = effect[
        ("multimodal_equal", M7_ACTIVE, always_defer, "decision_loss")
    ]
    equal_vs_mixture = effect[
        ("multimodal_equal", M7_ACTIVE, mixture, "decision_loss")
    ]
    runtime = effect[("overall", M7_ACTIVE, largest, "runtime_seconds")]
    communication = effect[("overall", M7_ACTIVE, largest, "bytes_sent")]
    movement = effect[("overall", M7_ACTIVE, largest, "movement_distance")]

    active_nominal = indexed[("no_change", M7_ACTIVE)]
    active_bias = indexed[("biased_agents", M7_ACTIVE)]
    active_byzantine = indexed[("byzantine_agent", M7_ACTIVE)]
    active_equal = indexed[("multimodal_equal", M7_ACTIVE)]
    active_unequal = indexed[("multimodal_unequal", M7_ACTIVE)]
    active_transient = indexed[("multimodal_transient", M7_ACTIVE)]

    sensitivity_passes: dict[str, bool] = {}
    for cost in SENSITIVITY_COSTS:
        metric = _cost_metric(cost)
        sensitivity_passes[f"defer_cost_{cost:.2f}"] = all(
            float(effect[("overall", M7_ACTIVE, baseline, metric)]["ci95_lower"])
            > 0.0
            for baseline in M7_BASELINES
        )

    calibrated = all(
        0.90 <= float(row["coverage95_rate_mean"]) <= 0.98
        and 1.0 <= float(row["mean_nees_mean"]) <= 3.0
        for row in (active_bias, active_byzantine)
    )
    gates = {
        "overall_decision_loss_beats_all_baselines": all(
            float(row["ci95_lower"]) > 0.0 for row in overall_effects
        ),
        "decision_survives_defer_cost_range_0_25_to_1_00": all(
            passed
            for label, passed in sensitivity_passes.items()
            if label != "defer_cost_1.50"
        ),
        "nominal_noninferior_within_0_02": float(nominal["ci95_lower"]) > -0.02,
        "dropout_noninferior_within_0_03": float(dropout["ci95_lower"]) > -0.03,
        "delay_noninferior_within_0_03": float(delay["ci95_lower"]) > -0.03,
        "bias_noninferior_within_0_03": float(bias["ci95_lower"]) > -0.03,
        "byzantine_noninferior_within_0_03": float(byzantine["ci95_lower"]) > -0.03,
        "equal_mode_beats_mixture": float(equal_vs_mixture["ci95_lower"]) > 0.0,
        "equal_mode_noninferior_to_defer_within_0_10": float(
            equal_vs_defer["ci95_lower"]
        ) > -0.10,
        "equal_mode_abstains_without_wrong_selection": (
            float(active_equal["abstention_rate_mean"]) >= 0.80
            and float(active_equal["wrong_mode_action_rate_mean"]) <= 0.02
        ),
        "unequal_mode_selects_without_wrong_mode": (
            float(active_unequal["selection_rate_mean"]) >= 0.90
            and float(active_unequal["wrong_mode_action_rate_mean"]) <= 0.02
        ),
        "transient_mode_resolves": (
            0.20 <= float(active_transient["abstention_rate_mean"]) <= 0.70
            and float(active_transient["ambiguity_resolution_steps_mean"]) <= 100.0
        ),
        "m6_mode_survival_preserved": (
            float(active_equal["multiflock_rate_mean"]) >= 0.90
            and float(active_equal["mean_alternative_flock_weight_mean"]) >= 0.25
        ),
        "m6_bias_calibration_preserved": calibrated,
        "false_quarantine_is_bounded": float(
            active_nominal["mean_quarantined_agents_mean"]
        ) <= 0.25,
        "communication_overhead_under_2_percent": (
            float(communication["candidate_mean"])
            <= 1.02 * float(communication["baseline_mean"])
        ),
        "runtime_overhead_under_50_percent": (
            float(runtime["candidate_mean"])
            <= 1.50 * float(runtime["baseline_mean"])
        ),
        "movement_overhead_under_15_percent": (
            float(movement["candidate_mean"])
            <= 1.15 * float(movement["baseline_mean"])
        ),
    }

    if all(gates.values()):
        verdict = "GO"
        research_direction = "ADVANCE_OUTPUT_POLICY_TO_REALISM_LADDER"
    elif (
        any(float(row["ci95_upper"]) < 0.0 for row in overall_effects)
        or not gates["equal_mode_abstains_without_wrong_selection"]
        or not gates["m6_mode_survival_preserved"]
    ):
        verdict = "NO-GO"
        research_direction = "RETAIN_EXPLICIT_SET_OUTPUT_AND_REDESIGN_M7"
    else:
        verdict = "INCONCLUSIVE"
        research_direction = "REFINE_M7_ON_TRAINING_SEEDS_ONLY"

    return {
        "verdict": verdict,
        "verdict_scope": "M7 truth-blind hypothesis-output policy",
        "research_direction": research_direction,
        "gates": gates,
        "sensitivity_gates": sensitivity_passes,
        "overall_decision_loss_improvements": {
            baseline: float(
                effect[("overall", M7_ACTIVE, baseline, "decision_loss")][
                    "improvement_mean"
                ]
            )
            for baseline in M7_BASELINES
        },
        "equal_mode_abstention_rate": float(active_equal["abstention_rate_mean"]),
        "equal_mode_wrong_selection_rate": float(
            active_equal["wrong_mode_action_rate_mean"]
        ),
        "unequal_mode_selection_rate": float(active_unequal["selection_rate_mean"]),
        "transient_mode_resolution_steps": float(
            active_transient["ambiguity_resolution_steps_mean"]
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
    indexed = {
        (str(row["scenario"]), str(row["algorithm"])): row
        for row in scenario_rows
    }
    lines = [
        "# Milestone 7: Hypothesis-Output Policy Decision Report",
        "",
        f"**Verdict: {decision['verdict']}**",
        "",
        f"**Research direction: {decision['research_direction']}**",
        "",
        (
            f"This evaluation uses {seed_count} seeds "
            f"({seed_start}–{seed_start + seed_count - 1}), eight scenarios, five "
            "truth-blind output policies, common random numbers, and paired bootstrap "
            "95% confidence intervals. The declared deferral cost is 0.75 position-error units per cycle."
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
            label.replace("0 25", "0.25")
            .replace("1 00", "1.00")
            .replace("0 02", "0.02")
            .replace("0 03", "0.03")
            .replace("0 10", "0.10")
            .replace("2 percent", "2%")
            .replace("15 percent", "15%")
            .replace("50 percent", "50%")
        )
        lines.append(f"| {label} | {'PASS' if passed else 'FAIL'} |")

    lines.extend(
        [
            "",
            "## Overall policy comparison",
            "",
            "| Baseline | Baseline loss | Active loss | Improvement | 95% CI |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for baseline in M7_BASELINES:
        paired = effect[("overall", M7_ACTIVE, baseline, "decision_loss")]
        lines.append(
            f"| {baseline} | {float(paired['baseline_mean']):.4f} | "
            f"{float(paired['candidate_mean']):.4f} | "
            f"{float(paired['improvement_mean']):.4f} | "
            f"[{float(paired['ci95_lower']):.4f}, {float(paired['ci95_upper']):.4f}] |"
        )

    lines.extend(
        [
            "",
            "## Active-policy scenario behaviour",
            "",
            "| Scenario | Decision loss | Abstain | Investigate | Material wrong-mode action | Flocks | Resolution steps |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for scenario in [item.name for item in M7_SCENARIOS]:
        row = indexed[(scenario, M7_ACTIVE)]
        resolution = row.get("ambiguity_resolution_steps_mean")
        resolution_text = "—" if resolution is None else f"{float(resolution):.1f}"
        lines.append(
            f"| {scenario} | {float(row['decision_loss_mean']):.4f} | "
            f"{float(row['abstention_rate_mean']):.3f} | "
            f"{float(row['investigation_rate_mean']):.3f} | "
            f"{float(row['wrong_mode_action_rate_mean']):.3f} | "
            f"{float(row['mean_hypothesis_flocks_mean']):.2f} | {resolution_text} |"
        )

    lines.extend(
        [
            "",
            "## Deferral-cost sensitivity",
            "",
            "The table reports the smallest active-policy improvement against any baseline at each counterfactual deferral cost.",
            "",
            "| Deferral cost | Smallest improvement | Smallest lower 95% bound |",
            "|---:|---:|---:|",
        ]
    )
    for cost in SENSITIVITY_COSTS:
        metric = _cost_metric(cost)
        rows = [effect[("overall", M7_ACTIVE, baseline, metric)] for baseline in M7_BASELINES]
        lines.append(
            f"| {cost:.2f} | {min(float(row['improvement_mean']) for row in rows):.4f} | "
            f"{min(float(row['ci95_lower']) for row in rows):.4f} |"
        )

    lines.extend(["", "## Interpretation", ""])
    if decision["verdict"] == "GO":
        lines.append(
            "The active policy passed every gate. It may advance to the realism ladder while retaining explicit set output as its ambiguity fallback."
        )
    elif decision["verdict"] == "NO-GO":
        lines.append(
            "The policy failed a decisive output-safety or mode-preservation gate. M6 set output remains the supported result."
        )
    else:
        lines.append(
            "The policy is not yet promotable. Refinement must use disjoint training seeds before another held-out evaluation."
        )
    lines.extend(
        [
            "",
            "The selector receives flock states, covariances, weights, and its own history only. Fault identities and truth are used solely after each action to score evaluation metrics. Persistent equal evidence is expected to remain deferred; forced resolution would be scientifically invalid.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_output_decision_suite(
    base_config: ExperimentConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 100,
    seed_start: int = 4000,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
    scenario_names: Iterable[str] | None = None,
) -> dict[str, object]:
    """Run the M7 five-policy paired evaluation."""
    if seed_count < 2:
        raise ValueError("seed_count must be at least 2")
    if bootstrap_samples < 100:
        raise ValueError("bootstrap_samples must be at least 100")
    requested = set(scenario_names) if scenario_names is not None else None
    scenarios = tuple(
        scenario
        for scenario in M7_SCENARIOS
        if requested is None or scenario.name in requested
    )
    if requested is not None and requested != {scenario.name for scenario in scenarios}:
        unknown = sorted(requested - {scenario.name for scenario in scenarios})
        raise ValueError(f"unknown M7 scenarios: {', '.join(unknown)}")
    if len(scenarios) != len(M7_SCENARIOS):
        raise ValueError("the automatic M7 decision requires all eight scenarios")

    seeds = list(range(seed_start, seed_start + seed_count))
    tasks: list[tuple[str, dict[str, object], str, int]] = []
    scenario_configs: dict[str, dict[str, object]] = {}
    for scenario in scenarios:
        overrides = dict(scenario.overrides)
        if (
            scenario.name == "multimodal_transient"
            and int(overrides["secondary_mode_end_step"]) > base_config.steps
        ):
            start = max(2, base_config.steps // 4)
            overrides["secondary_mode_start_step"] = start
            overrides["secondary_mode_end_step"] = max(
                start + 1,
                3 * base_config.steps // 4,
            )
        config = replace(
            base_config,
            **overrides,
            seeds=seeds,
            algorithms=list(M7_ALGORITHMS),
        )
        config.validate()
        scenario_configs[scenario.name] = config.to_dict()
        for algorithm in M7_ALGORITHMS:
            for seed in seeds:
                tasks.append((scenario.name, config.to_dict(), algorithm, seed))

    worker_count = workers or min(os.cpu_count() or 2, 8)
    executor_kind = "serial"
    if worker_count == 1:
        run_rows = [_m7_worker(task) for task in tasks]
    else:
        try:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                run_rows = list(executor.map(_m7_worker, tasks, chunksize=4))
            executor_kind = "process"
        except (PermissionError, OSError):
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                run_rows = list(executor.map(_m7_worker, tasks))
            executor_kind = "thread_fallback"

    scenario_order = {scenario.name: index for index, scenario in enumerate(scenarios)}
    algorithm_order = {algorithm: index for index, algorithm in enumerate(M7_ALGORITHMS)}
    run_rows.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            algorithm_order[str(row["algorithm"])],
            int(row["seed"]),
        )
    )
    scenario_rows = _scenario_summary(run_rows)
    # Dynamic sensitivity metrics are added here because the shared scenario
    # aggregator intentionally knows only stable platform metrics.
    scenario_index = {
        (str(row["scenario"]), str(row["algorithm"])): row
        for row in scenario_rows
    }
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in run_rows:
        grouped.setdefault((str(row["scenario"]), str(row["algorithm"])), []).append(row)
    for key, group in grouped.items():
        target = scenario_index[key]
        for cost in SENSITIVITY_COSTS:
            metric = _cost_metric(cost)
            values = [float(row[metric]) for row in group]
            target[f"{metric}_mean"] = float(np.mean(values))
            target[f"{metric}_std"] = float(np.std(values))

    effects = _paired_effects(
        run_rows,
        scenarios,
        seeds,
        bootstrap_samples,
        M7_COMPARISONS,
        M7_EFFECT_METRICS,
    )
    decision = _decision(scenario_rows, effects)
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
        "algorithms": list(M7_ALGORITHMS),
        "comparisons": [list(item) for item in M7_COMPARISONS],
        "sensitivity_costs": list(SENSITIVITY_COSTS),
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
        output / "milestone7_report.md",
        decision,
        effects,
        scenario_rows,
        seed_start,
        seed_count,
    )
    return decision


def reanalyze_output_decision_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    """Regenerate M7 statistics without rerunning trials."""
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
    scenario_index = {
        (str(row["scenario"]), str(row["algorithm"])): row
        for row in scenario_rows
    }
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in run_rows:
        grouped.setdefault((str(row["scenario"]), str(row["algorithm"])), []).append(row)
    for key, group in grouped.items():
        target = scenario_index[key]
        for cost in SENSITIVITY_COSTS:
            metric = _cost_metric(cost)
            values = [float(row[metric]) for row in group]
            target[f"{metric}_mean"] = float(np.mean(values))
            target[f"{metric}_std"] = float(np.std(values))
    effects = _paired_effects(
        run_rows,
        scenarios,
        seeds,
        samples,
        M7_COMPARISONS,
        M7_EFFECT_METRICS,
    )
    decision = _decision(scenario_rows, effects)
    _write_csv(output / "scenario_summary.csv", scenario_rows)
    _write_csv(output / "paired_effects.csv", effects)
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_report(
        output / "milestone7_report.md",
        decision,
        effects,
        scenario_rows,
        seed_start,
        seed_count,
    )
    return decision
