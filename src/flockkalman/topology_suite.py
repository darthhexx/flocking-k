"""Milestone 9A topology, outage/rejoin, and partition decision suite."""

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


M9A_BASELINE = "flocking_robust_active"
M9A_SUPPORT = "flocking_topology_support"
M9A_REJOIN = "flocking_topology_rejoin"
M9A_PARTITION = "flocking_topology_partition"
M9A_FULL = "flocking_topology_resilient"
M9A_ALGORITHMS = (
    M9A_BASELINE,
    M9A_SUPPORT,
    M9A_REJOIN,
    M9A_PARTITION,
    M9A_FULL,
)
M9A_COMPARISONS = (
    (M9A_FULL, M9A_BASELINE),
    (M9A_FULL, M9A_SUPPORT),
    (M9A_FULL, M9A_REJOIN),
    (M9A_FULL, M9A_PARTITION),
)
M9A_EFFECT_METRICS = {
    "decision_loss": "lower",
    "position_rmse": "lower",
    "wrong_mode_action_rate": "lower",
    "mean_nees": "lower",
    "coverage95_rate": "higher",
    "max_primary_support_jump": "lower",
    "rejoin_window_nees": "lower",
    "runtime_seconds": "lower",
    "bytes_sent": "lower",
}


_COMMON_MODE = {
    "target_change_mode": "none",
    "secondary_mode_agent_count": 4,
    "secondary_mode_offset": (5.0, -4.0),
    "secondary_mode_start_step": 20,
    "secondary_mode_end_step": 90,
}


M9A_SCENARIOS = (
    ScenarioDefinition(
        "stable_control",
        "Connected, fully available control with transient competing evidence.",
        dict(_COMMON_MODE),
    ),
    ScenarioDefinition(
        "failure_only",
        "Two agents disappear and later recover without a graph partition.",
        {
            **_COMMON_MODE,
            "agent_failure_count": 2,
            "agent_failure_step": 45,
            "agent_recovery_step": 115,
        },
    ),
    ScenarioDefinition(
        "partition_only",
        "A balanced hard partition isolates the observer component.",
        {
            **_COMMON_MODE,
            "topology_partition_step": 35,
            "topology_partition_duration": 70,
        },
    ),
    ScenarioDefinition(
        "asymmetric_partition",
        "A 3/5 hard partition tests conservative unknown-support bounds.",
        {
            **_COMMON_MODE,
            "topology_partition_step": 35,
            "topology_partition_duration": 70,
            "topology_partition_split_index": 3,
        },
    ),
    ScenarioDefinition(
        "failure_partition",
        "Failure overlaps a balanced partition and common recovery epoch.",
        {
            **_COMMON_MODE,
            "agent_failure_count": 2,
            "agent_failure_step": 45,
            "agent_recovery_step": 120,
            "topology_partition_step": 35,
            "topology_partition_duration": 70,
        },
    ),
    ScenarioDefinition(
        "staggered_rejoin",
        "Three failed agents rejoin six cycles apart.",
        {
            **_COMMON_MODE,
            "agent_failure_count": 3,
            "agent_failure_step": 40,
            "agent_recovery_step": 105,
            "agent_recovery_stagger_steps": 6,
        },
    ),
    ScenarioDefinition(
        "flapping_reconnect",
        "Five short partition/reconnect cycles stress epoch and merge grace logic.",
        {
            **_COMMON_MODE,
            "topology_partition_step": 30,
            "topology_partition_duration": 6,
            "topology_partition_repeat_interval": 14,
            "topology_partition_repeat_count": 5,
        },
    ),
    ScenarioDefinition(
        "false_split_dropout",
        "Correlated directed-link dropouts create transient components without a declared partition.",
        {
            **_COMMON_MODE,
            "communication_dropout_rate": 0.10,
            "communication_burst_entry_probability": 0.08,
            "communication_burst_recovery_probability": 0.22,
        },
    ),
)


def _fit_timing(overrides: dict[str, object], steps: int) -> dict[str, object]:
    """Scale event schedules only for short smoke-test configurations."""
    result = dict(overrides)
    if int(result.get("secondary_mode_end_step", -1)) > steps:
        start = max(1, steps // 8)
        result["secondary_mode_start_step"] = start
        result["secondary_mode_end_step"] = min(
            steps, max(start + 2, 9 * steps // 16)
        )
    if int(result.get("agent_failure_step", -1)) >= steps:
        result["agent_failure_step"] = max(1, steps // 4)
    if int(result.get("agent_recovery_step", -1)) > steps:
        failure = int(result["agent_failure_step"])
        stagger = int(result.get("agent_recovery_stagger_steps", 0))
        failed = int(result.get("agent_failure_count", 0))
        reserve = max(1, stagger * max(failed - 1, 0))
        result["agent_recovery_step"] = max(
            failure + 1, min(steps - reserve, 3 * steps // 4)
        )
    start = int(result.get("topology_partition_step", -1))
    duration = int(result.get("topology_partition_duration", 0))
    repeat = int(result.get("topology_partition_repeat_interval", 0))
    count = int(result.get("topology_partition_repeat_count", 1))
    final_end = start + duration if repeat <= 0 else start + repeat * (count - 1) + duration
    if start >= steps or final_end > steps:
        if repeat > 0:
            count = min(count, 3)
            duration = max(2, steps // 12)
            repeat = max(duration + 2, steps // max(count + 1, 4))
            start = max(1, steps // 6)
            while count > 1 and start + repeat * (count - 1) + duration > steps:
                count -= 1
            result["topology_partition_repeat_count"] = count
            result["topology_partition_repeat_interval"] = repeat
        else:
            start = max(1, steps // 5)
            duration = max(1, min(steps - start, 7 * steps // 16))
        result["topology_partition_step"] = start
        result["topology_partition_duration"] = duration
    return result


def _transfer_effects(
    rows: list[dict[str, object]],
    seeds: list[int],
    bootstrap_samples: int,
) -> list[dict[str, object]]:
    indexed = {
        (str(row["scenario"]), str(row["algorithm"]), int(row["seed"])): row
        for row in rows
    }
    rng = np.random.default_rng(2026072209)
    results: list[dict[str, object]] = []
    stable = np.asarray(
        [
            float(indexed[("stable_control", M9A_FULL, seed)]["decision_loss"])
            for seed in seeds
        ]
    )
    for scenario in M9A_SCENARIOS[1:]:
        candidate = np.asarray(
            [
                float(indexed[(scenario.name, M9A_FULL, seed)]["decision_loss"])
                for seed in seeds
            ]
        )
        improvement = stable - candidate
        lower, upper = _bootstrap_interval(improvement, bootstrap_samples, rng)
        results.append(
            {
                "scope": scenario.name,
                "candidate": M9A_FULL,
                "baseline": f"stable_control:{M9A_FULL}",
                "metric": "decision_loss_transfer",
                "direction": "lower",
                "pairs": len(seeds),
                "baseline_mean": float(np.mean(stable)),
                "candidate_mean": float(np.mean(candidate)),
                "improvement_mean": float(np.mean(improvement)),
                "relative_improvement_percent": (
                    100.0 * float(np.mean(improvement)) / abs(float(np.mean(stable)))
                    if abs(float(np.mean(stable))) > 1e-12
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


def _lookup_rows(
    rows: list[dict[str, object]],
) -> dict[tuple[str, str], dict[str, object]]:
    return {(str(row["scenario"]), str(row["algorithm"])): row for row in rows}


def _decision(
    scenario_rows: list[dict[str, object]],
    effects: list[dict[str, object]],
    trace_verified: bool,
) -> dict[str, object]:
    scenario = _lookup_rows(scenario_rows)
    effect = {
        (
            str(row["scope"]),
            str(row["candidate"]),
            str(row["baseline"]),
            str(row["metric"]),
        ): row
        for row in effects
    }
    full_rows = [scenario[(item.name, M9A_FULL)] for item in M9A_SCENARIOS]
    dynamic_rows = full_rows[1:]

    stable_effect = effect[("stable_control", M9A_FULL, M9A_BASELINE, "decision_loss")]
    transfer_rows = [
        effect[
            (
                item.name,
                M9A_FULL,
                f"stable_control:{M9A_FULL}",
                "decision_loss_transfer",
            )
        ]
        for item in M9A_SCENARIOS[1:]
    ]
    calibration_pass = all(
        float(row["mean_nees_mean"]) <= 6.0
        and float(row["p95_nees_mean"]) <= 20.0
        and float(row["coverage95_rate_mean"]) >= 0.88
        for row in dynamic_rows
    )
    wrong_selection_pass = all(
        float(row["wrong_mode_action_rate_mean"]) <= 0.05
        for row in dynamic_rows
    )
    transfer_pass = all(float(row["ci95_lower"]) > -0.10 for row in transfer_rows)
    stable_pass = float(stable_effect["ci95_lower"]) > -0.05
    rejoin_pass = (
        float(scenario[("failure_only", M9A_FULL)]["topology_rejoin_events_mean"])
        >= 2.0
        and float(scenario[("staggered_rejoin", M9A_FULL)]["topology_rejoin_events_mean"])
        >= 3.0
        and max(
            float(scenario[(name, M9A_FULL)]["rejoin_window_nees_mean"])
            for name in ("failure_only", "failure_partition", "staggered_rejoin")
        )
        <= 10.0
    )
    partition_pass = (
        float(scenario[("partition_only", M9A_FULL)]["mean_topology_unknown_support_mean"])
        > 0.10
        and float(scenario[("asymmetric_partition", M9A_FULL)]["mean_topology_unknown_support_mean"])
        > 0.20
        and float(scenario[("flapping_reconnect", M9A_FULL)]["topology_merge_grace_rate_mean"])
        > 0.0
    )
    support_pass = (
        all(
            float(row["max_primary_support_jump_mean"]) <= 0.50
            for row in dynamic_rows
        )
        and float(
            scenario[("failure_partition", M9A_FULL)][
                "mean_duplicate_support_suppressed_mean"
            ]
        )
        > 0.0
    )
    gates = {
        "replay": trace_verified,
        "stable_noninferiority": stable_pass,
        "dynamic_transfer_lcb": transfer_pass,
        "calibration_and_tail": calibration_pass,
        "wrong_selection": wrong_selection_pass,
        "rejoin_shock": rejoin_pass,
        "partition_uncertainty": partition_pass,
        "support_continuity": support_pass,
    }
    if not trace_verified:
        verdict = "INVALID-SUITE"
    elif all(gates.values()):
        verdict = "M9A-GO"
    elif all(
        gates[name]
        for name in (
            "stable_noninferiority",
            "calibration_and_tail",
            "wrong_selection",
            "rejoin_shock",
            "partition_uncertainty",
            "support_continuity",
        )
    ):
        verdict = "M9A-PARTIAL-GO"
    else:
        verdict = "M9A-NO-GO"
    return {
        "verdict": verdict,
        "gates": gates,
        "thresholds": {
            "stable_decision_loss_improvement_lcb": -0.05,
            "dynamic_transfer_lcb": -0.10,
            "mean_nees_max": 6.0,
            "p95_nees_max": 20.0,
            "coverage95_min": 0.88,
            "wrong_mode_action_rate_max": 0.05,
            "rejoin_window_nees_max": 10.0,
            "max_primary_support_jump": 0.50,
        },
        "minimum_transfer_lcb": min(float(row["ci95_lower"]) for row in transfer_rows),
        "stable_noninferiority_lcb": float(stable_effect["ci95_lower"]),
        "trace_replay_verified": trace_verified,
    }


def _write_report(
    path: Path,
    decision: dict[str, object],
    scenario_rows: list[dict[str, object]],
    effects: list[dict[str, object]],
    seed_start: int,
    seed_count: int,
) -> None:
    scenario = _lookup_rows(scenario_rows)
    transfers = {
        str(row["scope"]): row
        for row in effects
        if row["metric"] == "decision_loss_transfer"
    }
    lines = [
        "# Milestone 9A topology resilience report",
        "",
        f"**Verdict: {decision['verdict']}**",
        "",
        f"Fresh seeds: `{seed_start}`–`{seed_start + seed_count - 1}` ({seed_count} paired seeds per cell).",
        "",
        "## Preregistered gates",
        "",
        "| Gate | Result |",
        "|---|---:|",
    ]
    for name, passed in dict(decision["gates"]).items():
        lines.append(f"| {name} | {'PASS' if passed else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## Full M9A algorithm by scenario",
            "",
            "| Scenario | Loss | Transfer LCB | NEES | p95 NEES | Coverage | Wrong mode | Unknown | Rejoin NEES | Support jump |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in M9A_SCENARIOS:
        row = scenario[(item.name, M9A_FULL)]
        transfer = "—" if item.name == "stable_control" else f"{float(transfers[item.name]['ci95_lower']):.3f}"
        lines.append(
            f"| {item.name} | {float(row['decision_loss_mean']):.3f} | {transfer} | "
            f"{float(row['mean_nees_mean']):.2f} | {float(row['p95_nees_mean']):.2f} | "
            f"{float(row['coverage95_rate_mean']):.3f} | "
            f"{float(row['wrong_mode_action_rate_mean']):.3f} | "
            f"{float(row['mean_topology_unknown_support_mean']):.3f} | "
            f"{float(row['rejoin_window_nees_mean']):.2f} | "
            f"{float(row['max_primary_support_jump_mean']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "M9A.0 records component epochs, lifecycle transitions, evidence provenance, unknown support, merge grace, and selection blocks on every cycle.",
            "",
            "M9A.1 uses unique live contributors, decaying retained mode memory, and explicit unknown support. M9A.2 enforces OFFLINE → PROBATION → TRUSTED with covariance inflation and a support ramp. M9A.3 restricts the external output to the observer component and defers selection during reconnection grace. M9A.4 evaluates the frozen implementation against failure-only, partition-only, asymmetric, combined, staggered, flapping, and false-split traces.",
            "",
            "A GO verdict is still simulator evidence rather than external validity. M9B remains a separate held-out claim until an integrated suite is explicitly run.",
            "",
        ]
    )
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


def run_topology_decision_suite(
    base_config: ExperimentConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 100,
    seed_start: int = 12000,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
    scenario_names: Iterable[str] | None = None,
) -> dict[str, object]:
    """Run the complete M9A ablation and held-out decision protocol."""
    if seed_count < 2:
        raise ValueError("seed_count must be at least 2")
    if bootstrap_samples < 100:
        raise ValueError("bootstrap_samples must be at least 100")
    requested = set(scenario_names) if scenario_names is not None else None
    known = {scenario.name for scenario in M9A_SCENARIOS}
    if requested is not None and requested - known:
        raise ValueError(f"unknown M9A scenarios: {', '.join(sorted(requested - known))}")
    scenarios = tuple(
        scenario
        for scenario in M9A_SCENARIOS
        if requested is None or scenario.name in requested
    )
    if len(scenarios) != len(M9A_SCENARIOS):
        raise ValueError("the automatic M9A decision requires all eight scenarios")

    seeds = list(range(seed_start, seed_start + seed_count))
    tasks: list[tuple[str, dict[str, object], str, int]] = []
    scenario_configs: dict[str, dict[str, object]] = {}
    trace_entries: list[dict[str, object]] = []
    for scenario in scenarios:
        config = replace(
            base_config,
            **_fit_timing(scenario.overrides, base_config.steps),
            seeds=seeds,
            algorithms=list(M9A_ALGORITHMS),
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
        for algorithm in M9A_ALGORITHMS:
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
    algorithm_order = {algorithm: index for index, algorithm in enumerate(M9A_ALGORITHMS)}
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
        M9A_COMPARISONS,
        M9A_EFFECT_METRICS,
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
        "algorithms": list(M9A_ALGORITHMS),
        "comparisons": [list(item) for item in M9A_COMPARISONS],
        "scenarios": [asdict(scenario) for scenario in scenarios],
        "scenario_configs": scenario_configs,
        "m9a_parameters_frozen": True,
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
        output / "milestone9a_report.md",
        decision,
        scenario_rows,
        effects,
        seed_start,
        seed_count,
    )
    return decision


def reanalyze_topology_decision_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    """Rebuild all M9A statistics and verify materialized scenario replay."""
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
        M9A_COMPARISONS,
        M9A_EFFECT_METRICS,
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
        output / "milestone9a_report.md",
        decision,
        scenario_rows,
        effects,
        seed_start,
        seed_count,
    )
    return decision
