"""Milestone 8 realism ladder and active-investigation ablation."""

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
from .simulation import scenario_fingerprint
from .suite import (
    ScenarioDefinition,
    _bootstrap_interval,
    _paired_effects,
    _scenario_summary,
    _worker,
    _write_csv,
)


M8_ACTIVE = "flocking_robust_active"
M8_NO_INVESTIGATION = "flocking_robust_active_no_investigation"
M8_TEMPORAL = "flocking_robust_temporal"
M8_LARGEST = "flocking_robust_multiflock"
M8_ALGORITHMS = (M8_LARGEST, M8_TEMPORAL, M8_NO_INVESTIGATION, M8_ACTIVE)
M8_COMPARISONS = (
    (M8_ACTIVE, M8_TEMPORAL),
    (M8_ACTIVE, M8_LARGEST),
    (M8_ACTIVE, M8_NO_INVESTIGATION),
)
M8_EFFECT_METRICS = {
    "decision_loss": "lower",
    "position_rmse": "lower",
    "best_hypothesis_rmse": "lower",
    "wrong_mode_action_rate": "lower",
    "information_gain": "higher",
    "movement_distance": "lower",
    "runtime_seconds": "lower",
    "bytes_sent": "lower",
}


M8_SCENARIOS = (
    ScenarioDefinition(
        "persistent_equal_reference",
        "M7 equal-support reference checks that explicit abstention survives unchanged.",
        {
            "target_change_mode": "none",
            "secondary_mode_agent_count": 4,
            "secondary_mode_offset": (5.0, -4.0),
        },
    ),
    ScenarioDefinition(
        "transient_reference",
        "M7 transient ambiguity reference checks resolution after evidence reconverges.",
        {
            "target_change_mode": "none",
            "secondary_mode_agent_count": 4,
            "secondary_mode_offset": (5.0, -4.0),
            "secondary_mode_start_step": 20,
            "secondary_mode_end_step": 90,
        },
    ),
    ScenarioDefinition(
        "bursty_links",
        "Directed links enter and recover from correlated outage bursts.",
        {
            "target_change_mode": "none",
            "secondary_mode_agent_count": 4,
            "secondary_mode_offset": (5.0, -4.0),
            "secondary_mode_start_step": 20,
            "secondary_mode_end_step": 90,
            "communication_dropout_rate": 0.05,
            "communication_burst_entry_probability": 0.05,
            "communication_burst_recovery_probability": 0.25,
        },
    ),
    ScenarioDefinition(
        "asynchronous_delay",
        "Per-sender delay jitter and fixed clock offsets replace a global message age.",
        {
            "target_change_mode": "none",
            "secondary_mode_agent_count": 4,
            "secondary_mode_offset": (5.0, -4.0),
            "secondary_mode_start_step": 20,
            "secondary_mode_end_step": 90,
            "communication_delay_steps": 1,
            "communication_delay_jitter_steps": 3,
            "agent_clock_offset_max_steps": 2,
        },
    ),
    ScenarioDefinition(
        "nonlinear_range_bearing",
        "Sensors observe noisy range and bearing, converted by exact Gaussian moment matching.",
        {
            "target_change_mode": "none",
            "secondary_mode_agent_count": 4,
            "secondary_mode_offset": (5.0, -4.0),
            "secondary_mode_start_step": 20,
            "secondary_mode_end_step": 90,
            "measurement_model": "range_bearing",
            "bearing_base_std": 0.025,
        },
    ),
    ScenarioDefinition(
        "heterogeneous_sensors",
        "Each sensor receives a fixed seeded noise scale spanning low- and high-quality devices.",
        {
            "target_change_mode": "none",
            "secondary_mode_agent_count": 4,
            "secondary_mode_offset": (5.0, -4.0),
            "secondary_mode_start_step": 20,
            "secondary_mode_end_step": 90,
            "sensor_noise_scale_min": 0.55,
            "sensor_noise_scale_max": 1.80,
        },
    ),
    ScenarioDefinition(
        "drifting_bias_recovery",
        "Two source biases drift before a late recovery rather than remaining stationary.",
        {
            "target_change_mode": "none",
            "biased_agent_count": 2,
            "measurement_bias": (1.5, -1.0),
            "measurement_bias_drift": (0.018, -0.012),
            "biased_agent_recovery_step": 110,
        },
    ),
    ScenarioDefinition(
        "colluding_ramp_attack",
        "Three coordinated sources gradually construct a confident alternative mode.",
        {
            "target_change_mode": "none",
            "strategic_agent_count": 3,
            "strategic_offset_magnitude": 5.0,
            "strategic_offset_direction": (1.0, -0.8),
            "strategic_ramp_steps": 30,
            "strategic_covariance_scale": 0.25,
        },
    ),
    ScenarioDefinition(
        "dynamic_topology",
        "Two agents fail temporarily while the communication graph is partitioned.",
        {
            "target_change_mode": "none",
            "secondary_mode_agent_count": 4,
            "secondary_mode_offset": (5.0, -4.0),
            "secondary_mode_start_step": 20,
            "secondary_mode_end_step": 90,
            "agent_failure_count": 2,
            "agent_failure_step": 45,
            "agent_recovery_step": 120,
            "topology_partition_step": 35,
            "topology_partition_duration": 70,
        },
    ),
    ScenarioDefinition(
        "composite_stress",
        "Nonlinear heterogeneous sensing, attacks, burst links, asynchrony, failure and partition occur together.",
        {
            "target_change_mode": "abrupt",
            "secondary_mode_agent_count": 3,
            "secondary_mode_offset": (5.0, -4.0),
            "secondary_mode_start_step": 20,
            "secondary_mode_end_step": 90,
            "strategic_agent_count": 1,
            "strategic_offset_magnitude": 4.0,
            "strategic_ramp_steps": 30,
            "strategic_covariance_scale": 0.30,
            "communication_dropout_rate": 0.08,
            "communication_burst_entry_probability": 0.04,
            "communication_burst_recovery_probability": 0.25,
            "communication_delay_steps": 1,
            "communication_delay_jitter_steps": 2,
            "agent_clock_offset_max_steps": 1,
            "measurement_model": "range_bearing",
            "bearing_base_std": 0.03,
            "sensor_noise_scale_min": 0.65,
            "sensor_noise_scale_max": 1.65,
            "agent_failure_count": 1,
            "agent_failure_step": 45,
            "agent_recovery_step": 120,
            "topology_partition_step": 35,
            "topology_partition_duration": 70,
        },
    ),
)


def _fit_timing(overrides: dict[str, object], steps: int) -> dict[str, object]:
    """Scale M8 event timing only for deliberately short smoke-test runs."""
    result = dict(overrides)
    if int(result.get("secondary_mode_end_step", -1)) > steps:
        start = max(1, steps // 8)
        result["secondary_mode_start_step"] = start
        result["secondary_mode_end_step"] = min(steps, max(start + 2, 9 * steps // 16))
    if int(result.get("biased_agent_recovery_step", -1)) > steps:
        result["biased_agent_recovery_step"] = max(2, 11 * steps // 16)
    if int(result.get("agent_failure_step", -1)) >= steps:
        result["agent_failure_step"] = max(1, 9 * steps // 32)
    if int(result.get("agent_recovery_step", -1)) > steps:
        failure = int(result["agent_failure_step"])
        result["agent_recovery_step"] = min(steps, max(failure + 1, 3 * steps // 4))
    partition_start = int(result.get("topology_partition_step", -1))
    partition_duration = int(result.get("topology_partition_duration", 0))
    if partition_start >= steps or partition_start + partition_duration > steps:
        partition_start = max(1, 7 * steps // 32)
        result["topology_partition_step"] = partition_start
        result["topology_partition_duration"] = max(
            1, min(steps - partition_start, 7 * steps // 16)
        )
    return result


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


def _transfer_effects(
    rows: list[dict[str, object]],
    seeds: list[int],
    bootstrap_samples: int,
) -> list[dict[str, object]]:
    """Pair each stress layer with the frozen active transient reference."""
    indexed = {
        (str(row["scenario"]), str(row["algorithm"]), int(row["seed"])): row
        for row in rows
    }
    rng = np.random.default_rng(20260722)
    results: list[dict[str, object]] = []
    baseline_name = f"transient_reference:{M8_ACTIVE}"
    for scenario in M8_SCENARIOS[2:]:
        baseline_values = np.asarray(
            [
                float(indexed[("transient_reference", M8_ACTIVE, seed)]["decision_loss"])
                for seed in seeds
            ]
        )
        candidate_values = np.asarray(
            [
                float(indexed[(scenario.name, M8_ACTIVE, seed)]["decision_loss"])
                for seed in seeds
            ]
        )
        improvement = baseline_values - candidate_values
        lower, upper = _bootstrap_interval(improvement, bootstrap_samples, rng)
        results.append(
            {
                "scope": scenario.name,
                "candidate": M8_ACTIVE,
                "baseline": baseline_name,
                "metric": "decision_loss_transfer",
                "direction": "lower",
                "pairs": len(seeds),
                "baseline_mean": float(np.mean(baseline_values)),
                "candidate_mean": float(np.mean(candidate_values)),
                "improvement_mean": float(np.mean(improvement)),
                "relative_improvement_percent": (
                    100.0 * float(np.mean(improvement)) / abs(float(np.mean(baseline_values)))
                    if abs(float(np.mean(baseline_values))) > 1e-12
                    else None
                ),
                "ci95_lower": lower,
                "ci95_upper": upper,
                "wins": int(np.sum(improvement > 1e-12)),
                "ties": int(np.sum(np.abs(improvement) <= 1e-12)),
                "losses": int(np.sum(improvement < -1e-12)),
            }
        )
    return results


def _decision(
    scenario_rows: list[dict[str, object]],
    effects: list[dict[str, object]],
    trace_replay_verified: bool,
) -> dict[str, object]:
    effect = _lookup(effects)
    indexed = {
        (str(row["scenario"]), str(row["algorithm"])): row
        for row in scenario_rows
    }
    equal = indexed[("persistent_equal_reference", M8_ACTIVE)]
    transient = indexed[("transient_reference", M8_ACTIVE)]
    burst = indexed[("bursty_links", M8_ACTIVE)]
    asynchronous = indexed[("asynchronous_delay", M8_ACTIVE)]
    nonlinear = indexed[("nonlinear_range_bearing", M8_ACTIVE)]
    strategic = indexed[("colluding_ramp_attack", M8_ACTIVE)]
    dynamic = indexed[("dynamic_topology", M8_ACTIVE)]
    composite = indexed[("composite_stress", M8_ACTIVE)]
    overall_temporal = effect[("overall", M8_ACTIVE, M8_TEMPORAL, "decision_loss")]
    causal_loss = effect[
        ("overall", M8_ACTIVE, M8_NO_INVESTIGATION, "decision_loss")
    ]
    causal_information = effect[
        ("overall", M8_ACTIVE, M8_NO_INVESTIGATION, "information_gain")
    ]
    runtime = effect[
        ("overall", M8_ACTIVE, M8_NO_INVESTIGATION, "runtime_seconds")
    ]
    communication = effect[
        ("overall", M8_ACTIVE, M8_NO_INVESTIGATION, "bytes_sent")
    ]
    movement = effect[
        ("overall", M8_ACTIVE, M8_NO_INVESTIGATION, "movement_distance")
    ]

    equal_safe = (
        float(equal["abstention_rate_mean"]) >= 0.80
        and float(equal["wrong_mode_action_rate_mean"]) <= 0.02
    )
    transient_resolves = (
        0.20 <= float(transient["abstention_rate_mean"]) <= 0.70
        and float(transient["ambiguity_resolution_steps_mean"]) <= 100.0
    )
    transfer_baseline = f"transient_reference:{M8_ACTIVE}"
    layer_results: dict[str, bool] = {
        "persistent_equal_reference": equal_safe,
        "transient_reference": transient_resolves,
    }
    for scenario in M8_SCENARIOS[2:]:
        row = indexed[(scenario.name, M8_ACTIVE)]
        transfer = effect[
            (scenario.name, M8_ACTIVE, transfer_baseline, "decision_loss_transfer")
        ]
        layer_results[scenario.name] = (
            float(transfer["ci95_lower"]) > -0.10
            and float(row["wrong_mode_action_rate_mean"]) <= 0.05
        )

    core_gates = {
        "m7_equal_reference_safety_preserved": equal_safe,
        "m7_transient_reference_resolves": transient_resolves,
        "all_realism_layers_noninferior_and_safe": all(layer_results.values()),
        "overall_decision_loss_beats_temporal": float(overall_temporal["ci95_lower"]) > 0.0,
        "bursty_delivery_is_material_but_connected": (
            0.25 <= float(burst["mean_delivery_ratio_mean"]) <= 0.90
        ),
        "asynchronous_messages_are_materially_stale": (
            float(asynchronous["mean_message_age_mean"]) >= 0.75
        ),
        "nonlinear_measurement_calibration_is_credible": (
            0.50 <= float(nonlinear["mean_nees_mean"]) <= 6.0
            and 0.75 <= float(nonlinear["coverage95_rate_mean"]) <= 0.995
        ),
        "strategic_alternative_is_represented": (
            float(strategic["multiflock_rate_mean"]) >= 0.20
        ),
        "dynamic_outage_is_exercised": (
            6.0 <= float(dynamic["mean_operational_agents_mean"]) < 7.8
            and float(dynamic["partition_active_rate_mean"]) >= 0.30
        ),
        "composite_stress_retains_bounded_wrong_actions": (
            float(composite["wrong_mode_action_rate_mean"]) <= 0.05
        ),
        "deterministic_trace_replay_verified": trace_replay_verified,
        "communication_overhead_under_2_percent": (
            float(communication["candidate_mean"])
            <= 1.02 * max(float(communication["baseline_mean"]), 1.0)
        ),
        "runtime_overhead_under_50_percent": (
            float(runtime["candidate_mean"])
            <= 1.50 * max(float(runtime["baseline_mean"]), 1e-12)
        ),
        "movement_overhead_under_30_percent": (
            float(movement["candidate_mean"])
            <= 1.30 * max(float(movement["baseline_mean"]), 1e-12)
        ),
    }
    causal_gates = {
        "investigation_reduces_decision_loss": float(causal_loss["ci95_lower"]) > 0.0,
        "investigation_increases_information_gain": float(causal_information["ci95_lower"]) > 0.0,
    }
    failed_layers = [name for name, passed in layer_results.items() if not passed]
    if all(core_gates.values()) and all(causal_gates.values()):
        verdict = "GO"
        direction = "ADVANCE_ACTIVE_INVESTIGATION_TO_EXTERNAL_BENCHMARKS"
    elif all(core_gates.values()):
        verdict = "PARTIAL-GO"
        direction = "ADVANCE_REALISM_CORE_WITHOUT_CLAIMING_INVESTIGATION_BENEFIT"
    else:
        verdict = "NO-GO"
        direction = "STOP_AT_FIRST_FAILED_REALISM_LAYER_AND_REDESIGN"
    return {
        "verdict": verdict,
        "verdict_scope": "M8 frozen-policy realism ladder and causal investigation ablation",
        "research_direction": direction,
        "core_gates": core_gates,
        "causal_gates": causal_gates,
        "gates": {**core_gates, **causal_gates},
        "layer_results": layer_results,
        "first_failed_layer": failed_layers[0] if failed_layers else None,
        "active_vs_temporal_decision_improvement": float(overall_temporal["improvement_mean"]),
        "active_vs_temporal_ci95": [
            float(overall_temporal["ci95_lower"]),
            float(overall_temporal["ci95_upper"]),
        ],
        "investigation_decision_improvement": float(causal_loss["improvement_mean"]),
        "investigation_decision_ci95": [
            float(causal_loss["ci95_lower"]),
            float(causal_loss["ci95_upper"]),
        ],
        "investigation_information_improvement": float(causal_information["improvement_mean"]),
        "investigation_information_ci95": [
            float(causal_information["ci95_lower"]),
            float(causal_information["ci95_upper"]),
        ],
        "trace_replay_verified": trace_replay_verified,
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
        "# Milestone 8: Realism Ladder Decision Report",
        "",
        f"**Verdict: {decision['verdict']}**",
        "",
        f"**Research direction: {decision['research_direction']}**",
        "",
        (
            f"The held-out matrix uses {seed_count} common-random-number seeds "
            f"({seed_start}–{seed_start + seed_count - 1}), ten ordered scenarios, "
            "four frozen M7 policies, and paired bootstrap 95% intervals. No M7 "
            "policy threshold is retuned in this milestone."
        ),
        "",
        "## Core transfer gates",
        "",
        "| Gate | Result |",
        "|---|---|",
    ]
    for gate, passed in dict(decision["core_gates"]).items():
        lines.append(f"| {gate.replace('_', ' ')} | {'PASS' if passed else 'FAIL'} |")
    lines.extend([
        "",
        "## Investigation ablation gates",
        "",
        "| Gate | Result |",
        "|---|---|",
    ])
    for gate, passed in dict(decision["causal_gates"]).items():
        lines.append(f"| {gate.replace('_', ' ')} | {'PASS' if passed else 'FAIL'} |")
    lines.extend([
        "",
        "The no-investigation arm makes exactly the same truth-blind output decisions and pays the same decision costs; only investigative motion is disabled. Therefore its paired difference isolates the downstream effect of that motion within this simulator.",
        "",
        "## Realism ladder",
        "",
        "| Scenario | Layer | Active loss | Temporal loss | Transfer vs active reference (95% CI) | Wrong action | Coverage | Delivery | Age |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for scenario in M8_SCENARIOS:
        row = indexed[(scenario.name, M8_ACTIVE)]
        paired = effect[(scenario.name, M8_ACTIVE, M8_TEMPORAL, "decision_loss")]
        if scenario.name in {"persistent_equal_reference", "transient_reference"}:
            transfer_text = "reference"
        else:
            transfer = effect[
                (
                    scenario.name,
                    M8_ACTIVE,
                    f"transient_reference:{M8_ACTIVE}",
                    "decision_loss_transfer",
                )
            ]
            transfer_text = (
                f"{float(transfer['improvement_mean']):.4f} "
                f"([{float(transfer['ci95_lower']):.4f}, {float(transfer['ci95_upper']):.4f}])"
            )
        lines.append(
            f"| {scenario.name} | {'PASS' if decision['layer_results'][scenario.name] else 'FAIL'} | "
            f"{float(paired['candidate_mean']):.4f} | {float(paired['baseline_mean']):.4f} | "
            f"{transfer_text} | "
            f"{float(row['wrong_mode_action_rate_mean']):.3f} | "
            f"{float(row['coverage95_rate_mean']):.3f} | "
            f"{float(row['mean_delivery_ratio_mean']):.3f} | "
            f"{float(row['mean_message_age_mean']):.2f} |"
        )
    causal_loss = effect[("overall", M8_ACTIVE, M8_NO_INVESTIGATION, "decision_loss")]
    causal_info = effect[("overall", M8_ACTIVE, M8_NO_INVESTIGATION, "information_gain")]
    lines.extend([
        "",
        "## Causal investigation result",
        "",
        "| Outcome | No-investigation | Active | Improvement | 95% CI |",
        "|---|---:|---:|---:|---:|",
        (
            f"| Decision loss | {float(causal_loss['baseline_mean']):.4f} | "
            f"{float(causal_loss['candidate_mean']):.4f} | "
            f"{float(causal_loss['improvement_mean']):.4f} | "
            f"[{float(causal_loss['ci95_lower']):.4f}, {float(causal_loss['ci95_upper']):.4f}] |"
        ),
        (
            f"| Information gain | {float(causal_info['baseline_mean']):.4f} | "
            f"{float(causal_info['candidate_mean']):.4f} | "
            f"{float(causal_info['improvement_mean']):.4f} | "
            f"[{float(causal_info['ci95_lower']):.4f}, {float(causal_info['ci95_upper']):.4f}] |"
        ),
        "",
        "## Interpretation",
        "",
    ])
    if decision["verdict"] == "GO":
        lines.append("Both frozen-policy transfer and the investigative-motion mechanism are supported.")
    elif decision["verdict"] == "PARTIAL-GO":
        lines.append("The estimator/output core transfers, but investigative motion has not earned a causal performance claim. Continue with the no-investigation policy as the supported control arm.")
    else:
        first = decision.get("first_failed_layer") or "a cross-layer gate"
        lines.append(f"The frozen system fails at {first}. Later layers are diagnostic only; redesign must begin there before promotion.")
    lines.extend([
        "",
        "This suite is a simulator result, not external validity. Strategic behaviour follows declared attack schedules rather than an adaptive adversary, and the range–bearing conversion uses an exact moment match only for its declared independent Gaussian sensor noise.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def _verify_trace_manifest(
    scenario_configs: dict[str, dict[str, object]],
    entries: list[dict[str, object]],
) -> bool:
    for entry in entries:
        config = ExperimentConfig(**scenario_configs[str(entry["scenario"])])
        if scenario_fingerprint(config, int(entry["seed"])) != entry["fingerprint"]:
            return False
    return True


def run_realism_decision_suite(
    base_config: ExperimentConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 100,
    seed_start: int = 5000,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
    scenario_names: Iterable[str] | None = None,
) -> dict[str, object]:
    """Run the M8 frozen-policy realism ladder and causal ablation."""
    if seed_count < 2:
        raise ValueError("seed_count must be at least 2")
    if bootstrap_samples < 100:
        raise ValueError("bootstrap_samples must be at least 100")
    requested = set(scenario_names) if scenario_names is not None else None
    scenarios = tuple(
        scenario
        for scenario in M8_SCENARIOS
        if requested is None or scenario.name in requested
    )
    known = {scenario.name for scenario in M8_SCENARIOS}
    if requested is not None and requested - known:
        raise ValueError(f"unknown M8 scenarios: {', '.join(sorted(requested - known))}")
    if len(scenarios) != len(M8_SCENARIOS):
        raise ValueError("the automatic M8 decision requires all ten scenarios")

    seeds = list(range(seed_start, seed_start + seed_count))
    tasks: list[tuple[str, dict[str, object], str, int]] = []
    scenario_configs: dict[str, dict[str, object]] = {}
    trace_entries: list[dict[str, object]] = []
    for scenario in scenarios:
        config = replace(
            base_config,
            **_fit_timing(scenario.overrides, base_config.steps),
            seeds=seeds,
            algorithms=list(M8_ALGORITHMS),
        )
        config.validate()
        config_data = config.to_dict()
        scenario_configs[scenario.name] = config_data
        for seed in seeds:
            trace_entries.append(
                {
                    "scenario": scenario.name,
                    "seed": seed,
                    "fingerprint": scenario_fingerprint(config, seed),
                }
            )
        for algorithm in M8_ALGORITHMS:
            for seed in seeds:
                tasks.append((scenario.name, config_data, algorithm, seed))

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

    scenario_order = {scenario.name: index for index, scenario in enumerate(scenarios)}
    algorithm_order = {algorithm: index for index, algorithm in enumerate(M8_ALGORITHMS)}
    run_rows.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            algorithm_order[str(row["algorithm"])],
            int(row["seed"]),
        )
    )
    scenario_rows = _scenario_summary(run_rows)
    effects = _paired_effects(
        run_rows,
        scenarios,
        seeds,
        bootstrap_samples,
        M8_COMPARISONS,
        M8_EFFECT_METRICS,
    )
    effects.extend(_transfer_effects(run_rows, seeds, bootstrap_samples))
    trace_verified = _verify_trace_manifest(scenario_configs, trace_entries)
    decision = _decision(scenario_rows, effects, trace_verified)

    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "run_summary.csv", run_rows)
    _write_csv(output / "scenario_summary.csv", scenario_rows)
    _write_csv(output / "paired_effects.csv", effects)
    trace_manifest = {
        "algorithm_independent_common_random_numbers": True,
        "replay_verified": trace_verified,
        "entries": trace_entries,
    }
    (output / "trace_manifest.json").write_text(
        json.dumps(trace_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    suite_config = {
        "seed_start": seed_start,
        "seed_count": seed_count,
        "bootstrap_samples": bootstrap_samples,
        "workers": worker_count,
        "executor": executor_kind,
        "algorithms": list(M8_ALGORITHMS),
        "comparisons": [list(item) for item in M8_COMPARISONS],
        "scenarios": [asdict(scenario) for scenario in scenarios],
        "scenario_configs": scenario_configs,
        "policy_parameters_frozen_from_m7": True,
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
        output / "milestone8_report.md",
        decision,
        effects,
        scenario_rows,
        seed_start,
        seed_count,
    )
    return decision


def reanalyze_realism_decision_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    """Regenerate the M8 evidence and replay verification without rerunning trials."""
    output = Path(output_directory)
    suite_config = json.loads((output / "suite_config.json").read_text(encoding="utf-8"))
    trace_manifest = json.loads((output / "trace_manifest.json").read_text(encoding="utf-8"))
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
        M8_COMPARISONS,
        M8_EFFECT_METRICS,
    )
    effects.extend(_transfer_effects(run_rows, seeds, samples))
    trace_verified = _verify_trace_manifest(
        suite_config["scenario_configs"], trace_manifest["entries"]
    )
    decision = _decision(scenario_rows, effects, trace_verified)
    _write_csv(output / "scenario_summary.csv", scenario_rows)
    _write_csv(output / "paired_effects.csv", effects)
    trace_manifest["replay_verified"] = trace_verified
    (output / "trace_manifest.json").write_text(
        json.dumps(trace_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_report(
        output / "milestone8_report.md",
        decision,
        effects,
        scenario_rows,
        seed_start,
        seed_count,
    )
    return decision
