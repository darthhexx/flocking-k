"""M10B powered decentralized sensing-allocation evaluation."""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import platform
from time import perf_counter

import numpy as np

from .admission_suite import M9A7_ATTACK
from .closed_loop_trust import (
    closed_loop_fingerprint,
    run_closed_loop_trust_trial,
)
from .closed_loop_trust_suite import (
    M10A5_RECOVERY,
    M10A5_SCENARIOS,
    ClosedLoopScenario,
    _scenario_config,
    _trust_rates,
)
from .config import ExperimentConfig
from .decentralized_sensing import (
    M10B_ARMS,
    M10B_CENTRALIZED,
    M10B_NEGOTIATED,
    M10B_UNNEGOTIATED,
    DecentralizedTrial,
    run_decentralized_trial,
)
from .metrics import StepRecord, summarize_run
from .suite import _bootstrap_interval, _write_csv


M10B_SCENARIO_NAMES = (
    "stable_control",
    "failure_partition",
    "flapping_reconnect",
    "admission_censoring_control",
    "source_assignment_competition",
    "genuine_target_maneuver",
    M9A7_ATTACK.name,
    M10A5_RECOVERY.name,
)
M10B_SCENARIOS = tuple(
    scenario
    for scenario in M10A5_SCENARIOS
    if scenario.name in M10B_SCENARIO_NAMES
)
M10B_NATURAL_NAMES = frozenset(M10B_SCENARIO_NAMES[:6])

M10B_THRESHOLDS = {
    "stable_noninferiority_lcb_min": -0.03,
    "natural_noninferiority_lcb_min": -0.05,
    "source_competition_noninferiority_lcb_min": -0.03,
    "source_competition_action_difference_min": 0.02,
    "wrong_mode_action_rate_max": 0.01,
    "mean_nees_max": 6.0,
    "p95_nees_max": 20.0,
    "coverage95_min": 0.88,
    "delivery_ratio_lcb_min": -0.05,
    "component_count_increase_max": 0.25,
    "attack_loss_max": 1.50,
    "attack_detection_rate_min": 0.50,
    "attack_movement_increase_max": 0.05,
    "recovery_cycles_max": 30,
    "post_recovery_loss_max": 1.50,
    "negotiation_noninferiority_lcb_min": -0.06,
    "asynchronous_action_difference_min": 0.02,
    "runtime_multiplier_max": 2.0,
    "runtime_additive_seconds": 0.10,
    "compatibility_tolerance": 1e-12,
    "tail_event_frequency": 0.02,
    "tail_detection_probability": 0.95,
}

SUMMARY_METRICS = (
    "integrated_loss",
    "decision_loss",
    "movement_per_step",
    "position_rmse",
    "wrong_mode_action_rate",
    "mean_nees",
    "p95_nees",
    "coverage95_rate",
    "mean_delivery_ratio",
    "mean_topology_components",
    "quarantine_rate",
    "strategic_alert_rate",
    "nonstrategic_alert_rate",
    "trust_recovery_cycles",
    "post_stop_decision_loss",
    "planner_messages_per_step",
    "planner_bytes_per_step",
    "message_bound_violations",
    "mean_planner_state_age",
    "planner_active_rate",
    "planner_conflict_rate",
    "ownership_violations",
    "action_difference_rate",
    "runtime_seconds",
)


def _artifact_hash(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def required_tail_seeds(event_frequency: float, detection_probability: float) -> int:
    return math.ceil(
        math.log(1.0 - detection_probability) / math.log(1.0 - event_frequency)
    )


def _centralized_row(
    config: ExperimentConfig,
    scenario: ClosedLoopScenario,
    seed: int,
    runtime: float,
    records: tuple[StepRecord, ...],
    trust_steps: tuple,
) -> dict[str, object]:
    summary = summarize_run(config, list(records))
    movement = float(summary["movement_distance"]) / config.steps
    rates = _trust_rates(
        trust_steps,
        attack_stop_step=scenario.attack_stop_step,
        recovery_threshold=0.80,
    )
    post_loss = (
        float(
            np.mean(
                [
                    item.output_decision_loss
                    for item in records[scenario.attack_stop_step :]
                ]
            )
        )
        if scenario.attack_stop_step is not None
        else 0.0
    )
    return {
        "scenario": scenario.name,
        "seed": seed,
        "arm": M10B_CENTRALIZED,
        "integrated_loss": float(summary["decision_loss"])
        + config.m9c_movement_cost_per_unit * movement,
        "movement_per_step": movement,
        "post_stop_decision_loss": post_loss,
        "action_trace": "|".join(
            item.investigation_motion_action for item in records
        ),
        "planner_messages_per_step": 0.0,
        "planner_bytes_per_step": 0.0,
        "message_bound_violations": 0.0,
        "mean_planner_state_age": 0.0,
        "planner_active_rate": float(
            np.mean(
                [
                    item.investigation_motion_action
                    not in {"inactive", "track"}
                    for item in records
                ]
            )
        ),
        "planner_conflict_rate": 0.0,
        "ownership_violations": 0.0,
        "action_difference_rate": 0.0,
        "runtime_seconds": runtime,
        "trace_fingerprint": closed_loop_fingerprint(
            config, seed, scenario.attack_stop_step
        ),
        **rates,
        **{
            name: summary[name]
            for name in (
                "decision_loss",
                "position_rmse",
                "wrong_mode_action_rate",
                "mean_nees",
                "p95_nees",
                "coverage95_rate",
                "mean_delivery_ratio",
                "mean_topology_components",
                "quarantine_rate",
            )
        },
    }


def _decentralized_row(
    config: ExperimentConfig,
    scenario: ClosedLoopScenario,
    seed: int,
    runtime: float,
    trial: DecentralizedTrial,
    central_actions: tuple[str, ...],
) -> dict[str, object]:
    summary = summarize_run(config, list(trial.records))
    movement = float(summary["movement_distance"]) / config.steps
    rates = _trust_rates(
        trial.trust_steps,
        attack_stop_step=scenario.attack_stop_step,
        recovery_threshold=0.80,
    )
    actions = tuple(
        item.investigation_motion_action for item in trial.records
    )
    post_loss = (
        float(
            np.mean(
                [
                    item.output_decision_loss
                    for item in trial.records[scenario.attack_stop_step :]
                ]
            )
        )
        if scenario.attack_stop_step is not None
        else 0.0
    )
    return {
        "scenario": scenario.name,
        "seed": seed,
        "arm": trial.arm,
        "integrated_loss": float(summary["decision_loss"])
        + config.m9c_movement_cost_per_unit * movement,
        "movement_per_step": movement,
        "post_stop_decision_loss": post_loss,
        "action_trace": "|".join(actions),
        "planner_messages_per_step": (
            sum(item.planner_messages for item in trial.planner_steps)
            / config.steps
        ),
        "planner_bytes_per_step": (
            sum(item.planner_bytes for item in trial.planner_steps)
            / config.steps
        ),
        "message_bound_violations": float(
            sum(
                item.planner_messages > item.maximum_allowed_messages
                for item in trial.planner_steps
            )
        ),
        "mean_planner_state_age": float(
            np.mean([item.mean_state_age for item in trial.planner_steps])
        ),
        "planner_active_rate": float(
            np.mean([item.active_agents > 0 for item in trial.planner_steps])
        ),
        "planner_conflict_rate": float(
            np.mean([item.conflict_rate for item in trial.planner_steps])
        ),
        "ownership_violations": float(
            sum(item.ownership_violations for item in trial.planner_steps)
        ),
        "action_difference_rate": float(
            np.mean(np.asarray(actions) != np.asarray(central_actions))
        ),
        "runtime_seconds": runtime,
        "trace_fingerprint": closed_loop_fingerprint(
            config, seed, scenario.attack_stop_step
        ),
        **rates,
        **{
            name: summary[name]
            for name in (
                "decision_loss",
                "position_rmse",
                "wrong_mode_action_rate",
                "mean_nees",
                "p95_nees",
                "coverage95_rate",
                "mean_delivery_ratio",
                "mean_topology_components",
                "quarantine_rate",
            )
        },
    }


def _worker(
    task: tuple[dict[str, object], dict[str, object], int, int | None],
) -> list[dict[str, object]]:
    scenario_data, config_data, seed, attack_stop_step = task
    scenario = ClosedLoopScenario(
        definition=type(M10B_SCENARIOS[0].definition)(**scenario_data),
        attack_stop_step=attack_stop_step,
    )
    config = ExperimentConfig(**config_data)
    started = perf_counter()
    central = run_closed_loop_trust_trial(
        config,
        seed,
        attack_stop_step=attack_stop_step,
    )
    central_runtime = perf_counter() - started
    central_actions = tuple(
        item.investigation_motion_action for item in central.records
    )
    started = perf_counter()
    unnegotiated = run_decentralized_trial(
        config,
        seed,
        negotiated=False,
        attack_stop_step=attack_stop_step,
    )
    unnegotiated_runtime = perf_counter() - started
    started = perf_counter()
    negotiated = run_decentralized_trial(
        config,
        seed,
        negotiated=True,
        attack_stop_step=attack_stop_step,
    )
    negotiated_runtime = perf_counter() - started
    return [
        _centralized_row(
            config,
            scenario,
            seed,
            central_runtime,
            central.records,
            central.trust_steps,
        ),
        _decentralized_row(
            config,
            scenario,
            seed,
            unnegotiated_runtime,
            unnegotiated,
            central_actions,
        ),
        _decentralized_row(
            config,
            scenario,
            seed,
            negotiated_runtime,
            negotiated,
            central_actions,
        ),
    ]


def _summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault((str(row["scenario"]), str(row["arm"])), []).append(row)
    output: list[dict[str, object]] = []
    for (scenario, arm), group in grouped.items():
        item: dict[str, object] = {
            "scenario": scenario,
            "arm": arm,
            "runs": len(group),
        }
        for metric in SUMMARY_METRICS:
            values = np.asarray([float(row[metric]) for row in group], dtype=float)
            item[f"{metric}_mean"] = float(np.mean(values))
            item[f"{metric}_std"] = float(np.std(values))
            item[f"{metric}_max"] = float(np.max(values))
        output.append(item)
    return output


def _effects(
    rows: list[dict[str, object]],
    bootstrap_samples: int,
) -> list[dict[str, object]]:
    rng = np.random.default_rng(20260810)
    output: list[dict[str, object]] = []
    comparisons = (
        (M10B_NEGOTIATED, M10B_CENTRALIZED),
        (M10B_NEGOTIATED, M10B_UNNEGOTIATED),
    )
    for scenario in M10B_SCENARIOS:
        scoped = [row for row in rows if str(row["scenario"]) == scenario.name]
        for candidate_name, baseline_name in comparisons:
            candidate = {
                int(row["seed"]): row
                for row in scoped
                if str(row["arm"]) == candidate_name
            }
            baseline = {
                int(row["seed"]): row
                for row in scoped
                if str(row["arm"]) == baseline_name
            }
            seeds = sorted(set(candidate) & set(baseline))
            for metric, direction in (
                ("integrated_loss", "lower"),
                ("movement_per_step", "lower"),
                ("planner_conflict_rate", "lower"),
                ("mean_delivery_ratio", "higher"),
            ):
                cand = np.asarray(
                    [float(candidate[seed][metric]) for seed in seeds]
                )
                base = np.asarray(
                    [float(baseline[seed][metric]) for seed in seeds]
                )
                improvement = (
                    base - cand if direction == "lower" else cand - base
                )
                lower, upper = _bootstrap_interval(
                    improvement,
                    bootstrap_samples,
                    rng,
                )
                output.append(
                    {
                        "scenario": scenario.name,
                        "candidate": candidate_name,
                        "baseline": baseline_name,
                        "metric": metric,
                        "direction": direction,
                        "pairs": len(seeds),
                        "baseline_mean": float(np.mean(base)),
                        "candidate_mean": float(np.mean(cand)),
                        "improvement_mean": float(np.mean(improvement)),
                        "ci95_lower": lower,
                        "ci95_upper": upper,
                    }
                )
    return output


def _verify_upstream(
    project_root: Path,
    phase: str,
) -> tuple[bool, dict[str, object]]:
    source = project_root / "src/flockkalman"
    heldout = project_root / "results/milestone10a5_heldout"
    training = project_root / "results/milestone10a5_training"
    selected = heldout if (heldout / "decision.json").exists() else training
    decision = json.loads((selected / "decision.json").read_text())
    suite = json.loads((selected / "suite_config.json").read_text())
    source_hash = _artifact_hash(
        (
            source / "closed_loop_trust.py",
            source / "closed_loop_trust_suite.py",
        )
    )
    protocol_hash = _artifact_hash((project_root / "M10A5_PROTOCOL.md",))
    allowed = (
        {"M10A5-TRAINING-PASS", "M10A5-GO"}
        if phase == "training"
        else {"M10A5-GO"}
    )
    verified = (
        decision.get("verdict") in allowed
        and source_hash == suite.get("candidate_source_sha256")
        and protocol_hash == suite.get("protocol_sha256")
        and bool(dict(decision.get("gates", {})).get("upstream_frozen"))
    )
    return verified, {
        "verified": verified,
        "artifact": str(selected),
        "verdict": decision.get("verdict"),
        "source_sha256": source_hash,
        "protocol_sha256": protocol_hash,
    }


def _compatibility_audit(
    config: ExperimentConfig,
    seed: int,
) -> tuple[bool, float]:
    before = run_closed_loop_trust_trial(config, seed)
    run_decentralized_trial(config, seed, negotiated=True)
    after = run_closed_loop_trust_trial(config, seed)
    maximum = 0.0
    compatible = True
    for expected, actual in zip(before.records, after.records):
        for name, expected_value in asdict(expected).items():
            actual_value = getattr(actual, name)
            if isinstance(expected_value, (bool, str)) or expected_value is None:
                compatible &= expected_value == actual_value
            else:
                difference = abs(float(expected_value) - float(actual_value))
                maximum = max(maximum, difference)
    compatible &= maximum <= float(
        M10B_THRESHOLDS["compatibility_tolerance"]
    )
    return bool(compatible), maximum


def _decision(
    summaries: list[dict[str, object]],
    effects: list[dict[str, object]],
    *,
    phase: str,
    seed_count: int,
    replay_verified: bool,
    upstream_verified: bool,
    compatibility_verified: bool,
    compatibility_maximum: float,
) -> dict[str, object]:
    summary = {
        (str(row["scenario"]), str(row["arm"])): row for row in summaries
    }
    effect = {
        (
            str(row["scenario"]),
            str(row["candidate"]),
            str(row["baseline"]),
            str(row["metric"]),
        ): row
        for row in effects
    }
    candidate = {
        name: summary[(name, M10B_NEGOTIATED)]
        for name in M10B_SCENARIO_NAMES
    }
    central = {
        name: summary[(name, M10B_CENTRALIZED)]
        for name in M10B_SCENARIO_NAMES
    }
    unnegotiated = {
        name: summary[(name, M10B_UNNEGOTIATED)]
        for name in M10B_SCENARIO_NAMES
    }
    natural_bounds = [
        float(
            effect[
                (
                    name,
                    M10B_NEGOTIATED,
                    M10B_CENTRALIZED,
                    "integrated_loss",
                )
            ]["ci95_lower"]
        )
        for name in M10B_NATURAL_NAMES
    ]
    delivery_bounds = [
        float(
            effect[
                (
                    name,
                    M10B_NEGOTIATED,
                    M10B_CENTRALIZED,
                    "mean_delivery_ratio",
                )
            ]["ci95_lower"]
        )
        for name in M10B_NATURAL_NAMES
    ]
    component_increases = [
        float(candidate[name]["mean_topology_components_mean"])
        - float(central[name]["mean_topology_components_mean"])
        for name in M10B_NATURAL_NAMES
    ]
    negotiation_bounds = [
        float(
            effect[
                (
                    name,
                    M10B_NEGOTIATED,
                    M10B_UNNEGOTIATED,
                    "integrated_loss",
                )
            ]["ci95_lower"]
        )
        for name in M10B_NATURAL_NAMES
    ]
    conflict_improvements = [
        float(
            effect[
                (
                    name,
                    M10B_NEGOTIATED,
                    M10B_UNNEGOTIATED,
                    "planner_conflict_rate",
                )
            ]["improvement_mean"]
        )
        for name in M10B_NATURAL_NAMES
    ]
    movement_improvements = [
        float(
            effect[
                (
                    name,
                    M10B_NEGOTIATED,
                    M10B_UNNEGOTIATED,
                    "movement_per_step",
                )
            ]["improvement_mean"]
        )
        for name in M10B_NATURAL_NAMES
    ]
    minimum_seeds = required_tail_seeds(
        float(M10B_THRESHOLDS["tail_event_frequency"]),
        float(M10B_THRESHOLDS["tail_detection_probability"]),
    )
    attack = candidate[M9A7_ATTACK.name]
    recovery = candidate[M10A5_RECOVERY.name]
    attack_move_increase = (
        float(attack["movement_per_step_mean"])
        - float(central[M9A7_ATTACK.name]["movement_per_step_mean"])
    )
    source = candidate["source_assignment_competition"]
    source_bound = float(
        effect[
            (
                "source_assignment_competition",
                M10B_NEGOTIATED,
                M10B_CENTRALIZED,
                "integrated_loss",
            )
        ]["ci95_lower"]
    )
    runtime_ok = all(
        float(candidate[name]["runtime_seconds_mean"])
        <= float(M10B_THRESHOLDS["runtime_multiplier_max"])
        * float(central[name]["runtime_seconds_mean"])
        + float(M10B_THRESHOLDS["runtime_additive_seconds"])
        for name in M10B_SCENARIO_NAMES
    )
    gates = {
        "replay_and_upstream": replay_verified and upstream_verified,
        "tail_event_power": phase == "training" or seed_count >= minimum_seeds,
        "centralized_compatibility": compatibility_verified,
        "ownership": all(
            float(row["ownership_violations_max"]) == 0.0
            for row in candidate.values()
        ),
        "bounded_messages": all(
            float(row["message_bound_violations_max"]) == 0.0
            for row in candidate.values()
        ),
        "stable_noninferiority": float(
            effect[
                (
                    "stable_control",
                    M10B_NEGOTIATED,
                    M10B_CENTRALIZED,
                    "integrated_loss",
                )
            ]["ci95_lower"]
        )
        >= float(M10B_THRESHOLDS["stable_noninferiority_lcb_min"]),
        "natural_noninferiority": min(natural_bounds)
        >= float(M10B_THRESHOLDS["natural_noninferiority_lcb_min"]),
        "source_competition": (
            source_bound
            >= float(
                M10B_THRESHOLDS[
                    "source_competition_noninferiority_lcb_min"
                ]
            )
            and float(source["planner_active_rate_mean"]) >= 0.02
        ),
        "calibration_and_safety": all(
            float(row["wrong_mode_action_rate_mean"])
            <= float(M10B_THRESHOLDS["wrong_mode_action_rate_max"])
            and float(row["mean_nees_mean"])
            <= float(M10B_THRESHOLDS["mean_nees_max"])
            and float(row["p95_nees_mean"])
            <= float(M10B_THRESHOLDS["p95_nees_max"])
            and float(row["coverage95_rate_mean"])
            >= float(M10B_THRESHOLDS["coverage95_min"])
            for row in candidate.values()
        ),
        "topology_noninterference": (
            min(delivery_bounds)
            >= float(M10B_THRESHOLDS["delivery_ratio_lcb_min"])
            and max(component_increases)
            <= float(M10B_THRESHOLDS["component_count_increase_max"])
        ),
        "attack_boundary": (
            float(attack["decision_loss_mean"])
            <= float(M10B_THRESHOLDS["attack_loss_max"])
            and float(attack["strategic_alert_rate_mean"])
            >= float(M10B_THRESHOLDS["attack_detection_rate_min"])
            and attack_move_increase
            <= float(M10B_THRESHOLDS["attack_movement_increase_max"])
        ),
        "honest_recovery": (
            float(recovery["trust_recovery_cycles_max"])
            <= float(M10B_THRESHOLDS["recovery_cycles_max"])
            and float(recovery["post_stop_decision_loss_mean"])
            <= float(M10B_THRESHOLDS["post_recovery_loss_max"])
        ),
        "negotiation_value": (
            min(negotiation_bounds)
            >= float(M10B_THRESHOLDS["negotiation_noninferiority_lcb_min"])
            and (
                max(conflict_improvements) > 0.0
                or max(movement_improvements) > 0.0
            )
        ),
        "asynchronous_path_exercised": (
            float(source["mean_planner_state_age_mean"]) > 0.0
            and float(source["action_difference_rate_mean"])
            >= float(
                M10B_THRESHOLDS["asynchronous_action_difference_min"]
            )
            and float(source["planner_messages_per_step_mean"]) > 0.0
        ),
        "runtime": runtime_ok,
    }
    validity = {
        "replay_and_upstream",
        "tail_event_power",
        "centralized_compatibility",
        "ownership",
        "bounded_messages",
    }
    if not all(gates[name] for name in validity):
        verdict = "M10B-INVALID"
    elif not all(gates.values()):
        verdict = "M10B-TRAINING-FAIL" if phase == "training" else "M10B-NO-GO"
    else:
        verdict = "M10B-TRAINING-PASS" if phase == "training" else "M10B-GO"
    return {
        "verdict": verdict,
        "phase": phase,
        "gates": gates,
        "thresholds": M10B_THRESHOLDS,
        "compatibility_maximum_difference": compatibility_maximum,
        "power_calculation": {
            "minimum_seed_count": minimum_seeds,
            "actual_seed_count": seed_count,
        },
        "worst_natural_noninferiority_lcb": min(natural_bounds),
        "worst_delivery_lcb": min(delivery_bounds),
        "maximum_component_increase": max(component_increases),
        "source_competition_lcb": source_bound,
        "attack_loss": float(attack["decision_loss_mean"]),
        "attack_movement_increase": attack_move_increase,
        "external_replay_authorized": verdict == "M10B-GO",
        "production_authorized": False,
    }


def _write_report(
    path: Path,
    decision: dict[str, object],
    summaries: list[dict[str, object]],
    seed_start: int,
    seed_count: int,
) -> None:
    index = {
        (str(row["scenario"]), str(row["arm"])): row for row in summaries
    }
    lines = [
        "# M10B decentralized allocation report",
        "",
        f"**Verdict: `{decision['verdict']}`**",
        "",
        f"Phase: `{decision['phase']}`. Seeds: `{seed_start}`–`{seed_start + seed_count - 1}`.",
        "",
        "## Gates",
        "",
        "| Gate | Result |",
        "|---|---:|",
    ]
    for name, value in dict(decision["gates"]).items():
        lines.append(f"| {name} | {'PASS' if value else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## Negotiated candidate",
            "",
            "| Scenario | Integrated | Decision | Move | Active | Conflict | Msg/step | Age | Wrong | NEES | Coverage |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for scenario in M10B_SCENARIOS:
        row = index[(scenario.name, M10B_NEGOTIATED)]
        lines.append(
            f"| {scenario.name} | "
            f"{float(row['integrated_loss_mean']):.3f} | "
            f"{float(row['decision_loss_mean']):.3f} | "
            f"{float(row['movement_per_step_mean']):.3f} | "
            f"{float(row['planner_active_rate_mean']):.3f} | "
            f"{float(row['planner_conflict_rate_mean']):.3f} | "
            f"{float(row['planner_messages_per_step_mean']):.2f} | "
            f"{float(row['mean_planner_state_age_mean']):.2f} | "
            f"{float(row['wrong_mode_action_rate_mean']):.3f} | "
            f"{float(row['mean_nees_mean']):.2f} | "
            f"{float(row['coverage95_rate_mean']):.3f} |"
        )
    lines.extend(
        [
            "",
            "A GO authorizes external replay only; it is not a deployment verdict.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _read_rows(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def run_decentralized_suite(
    base_config: ExperimentConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 150,
    seed_start: int = 25000,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
    phase: str = "heldout",
) -> dict[str, object]:
    """Run the prospective M10B protocol."""
    base_config.validate()
    if phase not in {"training", "heldout"}:
        raise ValueError("phase must be training or heldout")
    if seed_count < 2 or bootstrap_samples < 100:
        raise ValueError("M10B needs at least two seeds and 100 bootstraps")
    tasks: list[
        tuple[dict[str, object], dict[str, object], int, int | None]
    ] = []
    scenario_configs: dict[str, dict[str, object]] = {}
    manifest: list[dict[str, object]] = []
    for scenario in M10B_SCENARIOS:
        config = _scenario_config(base_config, scenario)
        config_data = config.to_dict()
        scenario_configs[scenario.name] = config_data
        for seed in range(seed_start, seed_start + seed_count):
            tasks.append(
                (
                    asdict(scenario.definition),
                    config_data,
                    seed,
                    scenario.attack_stop_step,
                )
            )
            manifest.append(
                {
                    "scenario": scenario.name,
                    "seed": seed,
                    "attack_stop_step": scenario.attack_stop_step,
                    "fingerprint": closed_loop_fingerprint(
                        config, seed, scenario.attack_stop_step
                    ),
                }
            )
    audit_config = _scenario_config(base_config, M10B_SCENARIOS[0])
    compatibility_verified, compatibility_maximum = _compatibility_audit(
        audit_config, seed_start
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
            groups = [_worker(task) for task in tasks]
            executor_kind = "serial_fallback"
    rows = [row for group in groups for row in group]
    scenario_order = {
        scenario.name: index for index, scenario in enumerate(M10B_SCENARIOS)
    }
    arm_order = {arm: index for index, arm in enumerate(M10B_ARMS)}
    rows.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            arm_order[str(row["arm"])],
            int(row["seed"]),
        )
    )
    summaries = _summaries(rows)
    summaries.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            arm_order[str(row["arm"])],
        )
    )
    effects = _effects(rows, bootstrap_samples)
    replay_verified = all(
        str(entry["fingerprint"])
        == closed_loop_fingerprint(
            ExperimentConfig(
                **scenario_configs[str(entry["scenario"])]
            ),
            int(entry["seed"]),
            entry["attack_stop_step"],
        )
        for entry in manifest
    )
    project_root = Path(__file__).resolve().parents[2]
    upstream_verified, upstream = _verify_upstream(project_root, phase)
    decision = _decision(
        summaries,
        effects,
        phase=phase,
        seed_count=seed_count,
        replay_verified=replay_verified,
        upstream_verified=upstream_verified,
        compatibility_verified=compatibility_verified,
        compatibility_maximum=compatibility_maximum,
    )
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "run_summary.csv", rows)
    _write_csv(output / "scenario_summary.csv", summaries)
    _write_csv(output / "paired_effects.csv", effects)
    (output / "trace_manifest.json").write_text(
        json.dumps(
            {"replay_verified": replay_verified, "entries": manifest},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    source = project_root / "src/flockkalman"
    suite_config = {
        "phase": phase,
        "seed_start": seed_start,
        "seed_count": seed_count,
        "bootstrap_samples": bootstrap_samples,
        "workers": worker_count,
        "executor": executor_kind,
        "base_config": base_config.to_dict(),
        "scenarios": [
            {
                **asdict(item.definition),
                "attack_stop_step": item.attack_stop_step,
            }
            for item in M10B_SCENARIOS
        ],
        "scenario_configs": scenario_configs,
        "thresholds": M10B_THRESHOLDS,
        "protocol_sha256": _artifact_hash(
            (project_root / "M10B_PROTOCOL.md",)
        ),
        "candidate_source_sha256": _artifact_hash(
            (
                source / "decentralized_sensing.py",
                source / "decentralized_suite.py",
            )
        ),
        "upstream": upstream,
        "platform_version": "0.16.0",
        "python": platform.python_version(),
        "numpy": np.__version__,
    }
    (output / "suite_config.json").write_text(
        json.dumps(suite_config, indent=2, sort_keys=True) + "\n"
    )
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n"
    )
    _write_report(
        output / "milestone10b_report.md",
        decision,
        summaries,
        seed_start,
        seed_count,
    )
    return decision


def reanalyze_decentralized_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    output = Path(output_directory)
    suite = json.loads((output / "suite_config.json").read_text())
    rows = _read_rows(output / "run_summary.csv")
    samples = int(bootstrap_samples or suite["bootstrap_samples"])
    summaries = _summaries(rows)
    scenario_order = {
        scenario.name: index for index, scenario in enumerate(M10B_SCENARIOS)
    }
    arm_order = {arm: index for index, arm in enumerate(M10B_ARMS)}
    summaries.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            arm_order[str(row["arm"])],
        )
    )
    effects = _effects(rows, samples)
    replay_verified = all(
        str(row["trace_fingerprint"])
        == closed_loop_fingerprint(
            ExperimentConfig(
                **suite["scenario_configs"][str(row["scenario"])]
            ),
            int(row["seed"]),
            next(
                (
                    item["attack_stop_step"]
                    for item in suite["scenarios"]
                    if item["name"] == str(row["scenario"])
                ),
                None,
            ),
        )
        for row in rows
    )
    project_root = Path(__file__).resolve().parents[2]
    upstream_verified, _ = _verify_upstream(project_root, str(suite["phase"]))
    audit_config = ExperimentConfig(
        **suite["scenario_configs"][M10B_SCENARIOS[0].name]
    )
    compatibility_verified, compatibility_maximum = _compatibility_audit(
        audit_config, int(suite["seed_start"])
    )
    decision = _decision(
        summaries,
        effects,
        phase=str(suite["phase"]),
        seed_count=int(suite["seed_count"]),
        replay_verified=replay_verified,
        upstream_verified=upstream_verified,
        compatibility_verified=compatibility_verified,
        compatibility_maximum=compatibility_maximum,
    )
    _write_csv(output / "scenario_summary.csv", summaries)
    _write_csv(output / "paired_effects.csv", effects)
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n"
    )
    _write_report(
        output / "milestone10b_report.md",
        decision,
        summaries,
        int(suite["seed_start"]),
        int(suite["seed_count"]),
    )
    return decision
