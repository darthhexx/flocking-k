"""M10A.5 powered closed-loop trust integration and saved-row reanalysis."""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
import os
from pathlib import Path
import platform
from time import perf_counter

import numpy as np

from .admission_suite import M9A7_ATTACK
from .adversarial_trust import AdversarialTrustConfig
from .adversarial_trust_suite import (
    M10A_ATTACK_SCENARIOS,
    M10A_CONTROL_SCENARIOS,
    M10A_SCENARIOS,
)
from .closed_loop_trust import (
    M10A5_ARMS,
    M10A5_BASELINE,
    M10A5_CANDIDATE,
    closed_loop_fingerprint,
    run_closed_loop_trust_trial,
)
from .config import ExperimentConfig
from .experiment import run_trial
from .integrated_sensing import M9C_RECEDING_ALGORITHM
from .metrics import StepRecord, summarize_run
from .provenance import (
    resolve_pre_m14_commit,
    CURRENT_FINGERPRINT_ALGORITHM,
    ReplayVerification,
    environment_fingerprint,
    replay_verdict_suffix,
    verdict_accepted,
    verify_upstream_source,
    verify_replay,
)
from .simulation import make_scenario
from .suite import ScenarioDefinition, _bootstrap_interval, _write_csv
from .topology_suite import _fit_timing


@dataclass(frozen=True, slots=True)
class ClosedLoopScenario:
    definition: ScenarioDefinition
    attack_stop_step: int | None = None

    @property
    def name(self) -> str:
        return self.definition.name


M10A5_RECOVERY = ClosedLoopScenario(
    ScenarioDefinition(
        "raw_attack_then_honest_recovery",
        "Canonical rejoining colluders become honest while trust state persists.",
        dict(M9A7_ATTACK.overrides),
    ),
    attack_stop_step=105,
)
M10A5_SCENARIOS = tuple(
    ClosedLoopScenario(item) for item in M10A_SCENARIOS
) + (M10A5_RECOVERY,)
M10A5_CONTROL_NAMES = frozenset(item.name for item in M10A_CONTROL_SCENARIOS)
M10A5_ATTACK_NAMES = frozenset(item.name for item in M10A_ATTACK_SCENARIOS)

M10A5_THRESHOLDS = {
    "control_integrated_noninferiority_lcb_min": -0.03,
    "control_false_alert_rate_max": 0.05,
    "wrong_mode_action_rate_max": 0.01,
    "mean_nees_max": 6.0,
    "p95_nees_max": 20.0,
    "coverage95_min": 0.88,
    "availability_loss_max": 1.50,
    "canonical_improvement_lcb_min": 0.0,
    "attack_detection_rate_mild_min": 0.25,
    "attack_detection_rate_other_min": 0.50,
    "quarantine_difference_max": 0.02,
    "attack_movement_increase_max": 0.05,
    "trust_recovery_threshold": 0.80,
    "trust_recovery_cycles_max": 30,
    "post_recovery_false_alert_rate_max": 0.10,
    "post_recovery_loss_max": 1.50,
    "compatibility_tolerance": 1e-12,
    "tail_event_frequency": 0.02,
    "tail_detection_probability": 0.95,
}

SUMMARY_METRICS = (
    "integrated_loss",
    "decision_loss",
    "movement_per_step",
    "position_rmse",
    "abstention_rate",
    "wrong_mode_action_rate",
    "mean_nees",
    "p95_nees",
    "coverage95_rate",
    "mean_delivery_ratio",
    "mean_topology_components",
    "quarantine_rate",
    "strategic_alert_rate",
    "nonstrategic_alert_rate",
    "mean_raw_trust",
    "minimum_raw_trust",
    "trust_recovery_cycles",
    "post_stop_false_alert_rate",
    "post_stop_decision_loss",
    "trust_verification_rate",
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


def _scenario_config(
    base_config: ExperimentConfig,
    scenario: ClosedLoopScenario,
) -> ExperimentConfig:
    overrides = _fit_timing(scenario.definition.overrides, base_config.steps)
    if bool(overrides.get("m9a6_override_declared_model", False)):
        overrides["m9a6_model_secondary_start_step"] = overrides[
            "secondary_mode_start_step"
        ]
        overrides["m9a6_model_secondary_end_step"] = overrides[
            "secondary_mode_end_step"
        ]
    return replace(
        base_config,
        algorithms=[M9C_RECEDING_ALGORITHM],
        **overrides,
    )


def _trust_rates(
    trial_steps: tuple,
    *,
    attack_stop_step: int | None,
    recovery_threshold: float,
) -> dict[str, float]:
    strategic_visible = sum(item.strategic_visible for item in trial_steps)
    nonstrategic_visible = sum(item.nonstrategic_visible for item in trial_steps)
    recovery = 0.0
    post_false = 0.0
    if attack_stop_step is not None:
        recovery = float(len(trial_steps) - attack_stop_step)
        for item in trial_steps[attack_stop_step:]:
            if item.strategic_mean_trust >= recovery_threshold:
                recovery = float(item.step - attack_stop_step)
                break
        post_visible = sum(
            item.strategic_visible for item in trial_steps[attack_stop_step:]
        )
        post_alerted = sum(
            item.strategic_alerted for item in trial_steps[attack_stop_step:]
        )
        post_false = post_alerted / post_visible if post_visible else 0.0
    return {
        "strategic_alert_rate": (
            sum(item.strategic_alerted for item in trial_steps)
            / strategic_visible
            if strategic_visible
            else 0.0
        ),
        "nonstrategic_alert_rate": (
            sum(item.nonstrategic_alerted for item in trial_steps)
            / nonstrategic_visible
            if nonstrategic_visible
            else 0.0
        ),
        "mean_raw_trust": float(
            np.mean([item.mean_raw_trust for item in trial_steps])
        ),
        "minimum_raw_trust": float(
            np.min([item.minimum_raw_trust for item in trial_steps])
        ),
        "trust_recovery_cycles": recovery,
        "post_stop_false_alert_rate": post_false,
    }


def _row(
    config: ExperimentConfig,
    scenario: ClosedLoopScenario,
    seed: int,
    arm: str,
    records: tuple[StepRecord, ...],
    trust_steps: tuple,
    runtime: float,
    baseline_actions: tuple[str, ...],
) -> dict[str, object]:
    summary = summarize_run(config, list(records))
    movement = float(summary["movement_distance"]) / config.steps
    actions = tuple(record.investigation_motion_action for record in records)
    rates = _trust_rates(
        trust_steps,
        attack_stop_step=scenario.attack_stop_step,
        recovery_threshold=float(M10A5_THRESHOLDS["trust_recovery_threshold"]),
    )
    post_loss = 0.0
    if scenario.attack_stop_step is not None:
        post_loss = float(
            np.mean(
                [
                    record.output_decision_loss
                    for record in records[scenario.attack_stop_step :]
                ]
            )
        )
    return {
        "scenario": scenario.name,
        "seed": seed,
        "arm": arm,
        "integrated_loss": (
            float(summary["decision_loss"])
            + config.m9c_movement_cost_per_unit * movement
        ),
        "movement_per_step": movement,
        "runtime_seconds": runtime,
        "trace_fingerprint": closed_loop_fingerprint(
            config,
            seed,
            scenario.attack_stop_step,
            algorithm=CURRENT_FINGERPRINT_ALGORITHM,
        ),
        "action_trace": "|".join(actions),
        "action_difference_rate": float(
            np.mean(np.asarray(actions) != np.asarray(baseline_actions))
        ),
        "trust_verification_rate": float(
            np.mean(
                [
                    action == "trust_verify"
                    for action in actions
                ]
            )
        ),
        "post_stop_decision_loss": post_loss,
        **rates,
        **{
            metric: summary[metric]
            for metric in (
                "decision_loss",
                "position_rmse",
                "abstention_rate",
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
    definition_data, config_data, seed, attack_stop_step = task
    definition = ScenarioDefinition(**definition_data)
    scenario = ClosedLoopScenario(definition, attack_stop_step)
    config = ExperimentConfig(**config_data)
    started = perf_counter()
    baseline = run_closed_loop_trust_trial(
        config,
        seed,
        defense_mode="none",
        attack_stop_step=attack_stop_step,
    )
    baseline_runtime = perf_counter() - started
    baseline_actions = tuple(
        item.investigation_motion_action for item in baseline.records
    )
    started = perf_counter()
    candidate = run_closed_loop_trust_trial(
        config,
        seed,
        defense_mode="combined",
        attack_stop_step=attack_stop_step,
    )
    candidate_runtime = perf_counter() - started
    return [
        _row(
            config,
            scenario,
            seed,
            M10A5_BASELINE,
            baseline.records,
            baseline.trust_steps,
            baseline_runtime,
            baseline_actions,
        ),
        _row(
            config,
            scenario,
            seed,
            M10A5_CANDIDATE,
            candidate.records,
            candidate.trust_steps,
            candidate_runtime,
            baseline_actions,
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
    rng = np.random.default_rng(20260805)
    output: list[dict[str, object]] = []
    for scenario in M10A5_SCENARIOS:
        scoped = [row for row in rows if str(row["scenario"]) == scenario.name]
        baseline = {
            int(row["seed"]): row
            for row in scoped
            if str(row["arm"]) == M10A5_BASELINE
        }
        candidate = {
            int(row["seed"]): row
            for row in scoped
            if str(row["arm"]) == M10A5_CANDIDATE
        }
        seeds = sorted(set(baseline) & set(candidate))
        for metric in ("integrated_loss", "decision_loss", "movement_per_step"):
            base = np.asarray([float(baseline[seed][metric]) for seed in seeds])
            cand = np.asarray([float(candidate[seed][metric]) for seed in seeds])
            improvement = base - cand
            lower, upper = _bootstrap_interval(
                improvement,
                bootstrap_samples,
                rng,
            )
            output.append(
                {
                    "scenario": scenario.name,
                    "candidate": M10A5_CANDIDATE,
                    "baseline": M10A5_BASELINE,
                    "metric": metric,
                    "pairs": len(seeds),
                    "baseline_mean": float(np.mean(base)),
                    "candidate_mean": float(np.mean(cand)),
                    "improvement_mean": float(np.mean(improvement)),
                    "ci95_lower": lower,
                    "ci95_upper": upper,
                }
            )
    return output


def _verify_upstream(project_root: Path) -> tuple[bool, dict[str, object]]:
    source = project_root / "src/flockkalman"
    m9_output = project_root / "results/milestone9c_heldout"
    m10_output = project_root / "results/milestone10a_heldout"
    m9_suite = json.loads((m9_output / "suite_config.json").read_text())
    m9_decision = json.loads((m9_output / "decision.json").read_text())
    m10_suite = json.loads((m10_output / "suite_config.json").read_text())
    m10_decision = json.loads((m10_output / "decision.json").read_text())
    _m9_files = (
        (
            source / "integrated_sensing.py",
            source / "integration_suite.py",
            source / "experiment.py",
            source / "config.py",
            source / "metrics.py",
        )
    )
    _m10_files = (
        source / "adversarial_trust.py",
        source / "adversarial_trust_suite.py",
    )
    m9_verification = verify_upstream_source(
        m9_suite.get("candidate_source_sha256"),
        _m9_files,
        reference_commit=resolve_pre_m14_commit(project_root),
        repo_root=project_root,
    )
    m10_verification = verify_upstream_source(
        m10_suite.get("candidate_source_sha256"),
        _m10_files,
        reference_commit=resolve_pre_m14_commit(project_root),
        repo_root=project_root,
    )
    m9_source = m9_verification["current_sha256"]
    m10_source = m10_verification["current_sha256"]
    m9_protocol = _artifact_hash((project_root / "M9C_PROTOCOL.md",))
    m10_protocol = _artifact_hash((project_root / "M10A_PROTOCOL.md",))
    verified = (
        verdict_accepted(str(m9_decision.get("verdict", "")), {"M9C-PARTIAL-GO"})
        and verdict_accepted(str(m10_decision.get("verdict", "")), {"M10A-GO"})
        and not m9_verification["blocks_promotion"]
        and not m10_verification["blocks_promotion"]
        and m9_protocol == m9_suite.get("protocol_sha256")
        and m10_protocol == m10_suite.get("protocol_sha256")
    )
    return verified, {
        "verified": verified,
        "m9c_verdict": m9_decision.get("verdict"),
        "m10a_verdict": m10_decision.get("verdict"),
        "m9c_source_sha256": m9_source,
        "m10a_source_sha256": m10_source,
    }


def _compatibility_audit(
    config: ExperimentConfig,
    seed: int,
) -> tuple[bool, float]:
    direct = run_trial(config, M9C_RECEDING_ALGORITHM, seed)
    injected = run_closed_loop_trust_trial(config, seed, defense_mode="none")
    maximum = 0.0
    compatible = len(direct) == len(injected.records)
    for expected, actual in zip(direct, injected.records):
        expected_data = asdict(expected)
        actual_data = asdict(actual)
        expected_data.pop("algorithm")
        actual_data.pop("algorithm")
        for name, expected_value in expected_data.items():
            actual_value = actual_data[name]
            if isinstance(expected_value, (bool, str)) or expected_value is None:
                compatible &= expected_value == actual_value
            else:
                difference = abs(float(expected_value) - float(actual_value))
                maximum = max(maximum, difference)
    compatible &= maximum <= float(
        M10A5_THRESHOLDS["compatibility_tolerance"]
    )
    return bool(compatible), maximum


def _decision(
    rows: list[dict[str, object]],
    summaries: list[dict[str, object]],
    effects: list[dict[str, object]],
    *,
    phase: str,
    seed_count: int,
    replay: ReplayVerification,
    upstream_verified: bool,
    compatibility_verified: bool,
    compatibility_maximum: float,
) -> dict[str, object]:
    summary = {
        (str(row["scenario"]), str(row["arm"])): row for row in summaries
    }
    effect = {
        (str(row["scenario"]), str(row["metric"])): row for row in effects
    }
    candidate = {
        scenario.name: summary[(scenario.name, M10A5_CANDIDATE)]
        for scenario in M10A5_SCENARIOS
    }
    baseline = {
        scenario.name: summary[(scenario.name, M10A5_BASELINE)]
        for scenario in M10A5_SCENARIOS
    }
    controls = [candidate[name] for name in M10A5_CONTROL_NAMES]
    attacks = [candidate[name] for name in M10A5_ATTACK_NAMES]
    control_bounds = [
        float(effect[(name, "integrated_loss")]["ci95_lower"])
        for name in M10A5_CONTROL_NAMES
    ]
    recovery = candidate[M10A5_RECOVERY.name]
    canonical = effect[(M9A7_ATTACK.name, "decision_loss")]
    minimum_seeds = required_tail_seeds(
        float(M10A5_THRESHOLDS["tail_event_frequency"]),
        float(M10A5_THRESHOLDS["tail_detection_probability"]),
    )
    attack_movement_increases = [
        float(candidate[name]["movement_per_step_mean"])
        - float(baseline[name]["movement_per_step_mean"])
        for name in M10A5_ATTACK_NAMES
    ]
    gates = {
        "replay": replay.verified,
        "upstream_frozen": upstream_verified,
        "tail_event_power": phase == "training" or seed_count >= minimum_seeds,
        "baseline_compatibility": compatibility_verified,
        "control_noninferiority": min(control_bounds)
        >= float(
            M10A5_THRESHOLDS[
                "control_integrated_noninferiority_lcb_min"
            ]
        ),
        "control_false_alerts": all(
            float(row["nonstrategic_alert_rate_mean"])
            <= float(M10A5_THRESHOLDS["control_false_alert_rate_max"])
            for row in controls
        ),
        "control_calibration_and_safety": all(
            float(row["wrong_mode_action_rate_mean"])
            <= float(M10A5_THRESHOLDS["wrong_mode_action_rate_max"])
            and float(row["mean_nees_mean"])
            <= float(M10A5_THRESHOLDS["mean_nees_max"])
            and float(row["p95_nees_mean"])
            <= float(M10A5_THRESHOLDS["p95_nees_max"])
            and float(row["coverage95_rate_mean"])
            >= float(M10A5_THRESHOLDS["coverage95_min"])
            for row in controls
        ),
        "legitimate_evidence_noninferiority": all(
            float(effect[(name, "integrated_loss")]["ci95_lower"])
            >= float(
                M10A5_THRESHOLDS[
                    "control_integrated_noninferiority_lcb_min"
                ]
            )
            for name in (
                "admission_censoring_control",
                "source_assignment_competition",
                "genuine_target_maneuver",
                "legitimate_heterogeneous_precision",
            )
        ),
        "attack_absolute_availability": all(
            float(row["decision_loss_mean"])
            <= float(M10A5_THRESHOLDS["availability_loss_max"])
            for row in attacks
        ),
        "canonical_attack_improvement": float(canonical["ci95_lower"])
        > float(M10A5_THRESHOLDS["canonical_improvement_lcb_min"]),
        "attack_calibration_and_safety": all(
            float(row["wrong_mode_action_rate_mean"])
            <= float(M10A5_THRESHOLDS["wrong_mode_action_rate_max"])
            and float(row["mean_nees_mean"])
            <= float(M10A5_THRESHOLDS["mean_nees_max"])
            and float(row["p95_nees_mean"])
            <= float(M10A5_THRESHOLDS["p95_nees_max"])
            and float(row["coverage95_rate_mean"])
            >= float(M10A5_THRESHOLDS["coverage95_min"])
            for row in attacks
        ),
        "attack_detection": (
            float(
                candidate["raw_attack_mild"]["strategic_alert_rate_mean"]
            )
            >= float(M10A5_THRESHOLDS["attack_detection_rate_mild_min"])
            and all(
                float(candidate[name]["strategic_alert_rate_mean"])
                >= float(
                    M10A5_THRESHOLDS["attack_detection_rate_other_min"]
                )
                for name in (
                    "raw_attack_moderate",
                    "raw_attack_severe",
                    M9A7_ATTACK.name,
                )
            )
        ),
        "quarantine_noninterference": all(
            abs(
                float(candidate[scenario.name]["quarantine_rate_mean"])
                - float(baseline[scenario.name]["quarantine_rate_mean"])
            )
            <= float(M10A5_THRESHOLDS["quarantine_difference_max"])
            for scenario in M10A5_SCENARIOS
        ),
        "attack_movement_bounded": max(attack_movement_increases)
        <= float(M10A5_THRESHOLDS["attack_movement_increase_max"]),
        "honest_recovery": (
            float(recovery["trust_recovery_cycles_max"])
            <= float(M10A5_THRESHOLDS["trust_recovery_cycles_max"])
            and float(recovery["post_stop_false_alert_rate_mean"])
            <= float(
                M10A5_THRESHOLDS["post_recovery_false_alert_rate_max"]
            )
            and float(recovery["post_stop_decision_loss_mean"])
            <= float(M10A5_THRESHOLDS["post_recovery_loss_max"])
        ),
        "feedback_exercised": any(
            float(candidate[name]["action_difference_rate_mean"]) > 0.0
            for name in M10A5_ATTACK_NAMES
        ),
    }
    validity = {
        "replay",
        "upstream_frozen",
        "tail_event_power",
        "baseline_compatibility",
    }
    # M14.3: see adversarial_trust_suite for the rationale. An unexplained
    # mismatch invalidates; an environment-explained one gets its own class.
    other_validity = validity - {"replay"}
    substantive = {name: value for name, value in gates.items() if name != "replay"}
    if replay.blocks_promotion or not all(gates[name] for name in other_validity):
        verdict = "M10A5-INVALID"
    elif not all(substantive.values()):
        verdict = (
            "M10A5-TRAINING-FAIL"
            if phase == "training"
            else "M10A5-NO-GO"
        )
    elif not replay.verified:
        # Substantive gates passed but the replay is not bit-exactly certifiable;
        # qualify the verdict rather than reporting a clean GO (M14.3).
        verdict = f"M10A5-{replay_verdict_suffix(replay)}"
    else:
        verdict = (
            "M10A5-TRAINING-PASS"
            if phase == "training"
            else "M10A5-GO"
        )
    return {
        "verdict": verdict,
        "replay_verification": replay.to_dict(),
        "environment": environment_fingerprint(),
        "phase": phase,
        "gates": gates,
        "thresholds": M10A5_THRESHOLDS,
        "power_calculation": {
            "minimum_seed_count": minimum_seeds,
            "actual_seed_count": seed_count,
        },
        "compatibility_maximum_difference": compatibility_maximum,
        "canonical_attack_improvement": float(canonical["improvement_mean"]),
        "canonical_attack_ci95": [
            float(canonical["ci95_lower"]),
            float(canonical["ci95_upper"]),
        ],
        "attack_decision_losses": {
            name: float(candidate[name]["decision_loss_mean"])
            for name in M10A5_ATTACK_NAMES
        },
        "maximum_attack_movement_increase": max(attack_movement_increases),
        "recovery_max_cycles": float(recovery["trust_recovery_cycles_max"]),
        "recovery_post_stop_false_alert_rate": float(
            recovery["post_stop_false_alert_rate_mean"]
        ),
        "decentralized_research_authorized": verdict == "M10A5-GO",
        "production_authorized": False,
        "historical_verdicts_unchanged": True,
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
        "# M10A.5 closed-loop trust integration report",
        "",
        f"**Verdict: `{decision['verdict']}`**",
        "",
        f"Phase: `{decision['phase']}`. Seeds: `{seed_start}`–`{seed_start + seed_count - 1}`.",
        "",
        "The frozen M10A trust posterior feeds the frozen M9C receding planner. "
        "A bounded trusted-sensor verification action makes the feedback path explicit.",
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
            "## Candidate results",
            "",
            "| Scenario | Integrated loss | Decision loss | Move/step | Wrong | NEES | Coverage | Alert | False alert | Verify |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for scenario in M10A5_SCENARIOS:
        row = index[(scenario.name, M10A5_CANDIDATE)]
        lines.append(
            f"| {scenario.name} | "
            f"{float(row['integrated_loss_mean']):.3f} | "
            f"{float(row['decision_loss_mean']):.3f} | "
            f"{float(row['movement_per_step_mean']):.3f} | "
            f"{float(row['wrong_mode_action_rate_mean']):.3f} | "
            f"{float(row['mean_nees_mean']):.2f} | "
            f"{float(row['coverage95_rate_mean']):.3f} | "
            f"{float(row['strategic_alert_rate_mean']):.3f} | "
            f"{float(row['nonstrategic_alert_rate_mean']):.3f} | "
            f"{float(row['trust_verification_rate_mean']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "A GO authorizes the decentralized planner milestone only. It does "
            "not establish adaptive-adversary security or production readiness.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _read_rows(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def run_closed_loop_trust_suite(
    base_config: ExperimentConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 150,
    seed_start: int = 23000,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
    phase: str = "heldout",
) -> dict[str, object]:
    """Run the prospective M10A.5 closed-loop protocol."""
    base_config.validate()
    if phase not in {"training", "heldout"}:
        raise ValueError("phase must be training or heldout")
    if seed_count < 2 or bootstrap_samples < 100:
        raise ValueError("M10A.5 needs at least two seeds and 100 bootstraps")
    tasks: list[
        tuple[dict[str, object], dict[str, object], int, int | None]
    ] = []
    scenario_configs: dict[str, dict[str, object]] = {}
    manifest: list[dict[str, object]] = []
    for scenario in M10A5_SCENARIOS:
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
                        config,
                        seed,
                        scenario.attack_stop_step,
                        algorithm=CURRENT_FINGERPRINT_ALGORITHM,
                    ),
                }
            )
    audit_config = _scenario_config(base_config, M10A5_SCENARIOS[0])
    compatibility_verified, compatibility_maximum = _compatibility_audit(
        audit_config,
        seed_start,
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
        scenario.name: index for index, scenario in enumerate(M10A5_SCENARIOS)
    }
    arm_order = {arm: index for index, arm in enumerate(M10A5_ARMS)}
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
    replay = verify_replay(
        [dict(entry) for entry in manifest],
        expected=lambda entry, algorithm: closed_loop_fingerprint(
            ExperimentConfig(**scenario_configs[str(entry["scenario"])]),
            int(entry["seed"]),
            (
                None
                if entry["attack_stop_step"] is None
                else int(entry["attack_stop_step"])
            ),
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
            {
                "replay_verified": replay.verified,
                "replay_verification": replay.to_dict(),
                "fingerprint_algorithm": CURRENT_FINGERPRINT_ALGORITHM,
                "entries": manifest,
            },
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
        "trust_config": asdict(AdversarialTrustConfig()),
        "scenarios": [
            {
                **asdict(item.definition),
                "attack_stop_step": item.attack_stop_step,
            }
            for item in M10A5_SCENARIOS
        ],
        "scenario_configs": scenario_configs,
        "thresholds": M10A5_THRESHOLDS,
        "protocol_sha256": _artifact_hash(
            (project_root / "M10A5_PROTOCOL.md",)
        ),
        "candidate_source_sha256": _artifact_hash(
            (
                source / "closed_loop_trust.py",
                source / "closed_loop_trust_suite.py",
                # M14.4: modules the replay gate depends on.
                source / "simulation.py",
                source / "config.py",
                source / "provenance.py",
            )
        ),
        "fingerprint_algorithm": CURRENT_FINGERPRINT_ALGORITHM,
        "upstream": upstream,
        "platform_version": "0.15.0",
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
        output / "milestone10a5_report.md",
        decision,
        summaries,
        seed_start,
        seed_count,
    )
    return decision


def reanalyze_closed_loop_trust_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    """Regenerate M10A.5 gates from saved rows."""
    output = Path(output_directory)
    suite = json.loads((output / "suite_config.json").read_text())
    rows = _read_rows(output / "run_summary.csv")
    samples = int(bootstrap_samples or suite["bootstrap_samples"])
    summaries = _summaries(rows)
    scenario_order = {
        scenario.name: index for index, scenario in enumerate(M10A5_SCENARIOS)
    }
    arm_order = {arm: index for index, arm in enumerate(M10A5_ARMS)}
    summaries.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            arm_order[str(row["arm"])],
        )
    )
    effects = _effects(rows, samples)
    _recorded_env = {
        key: suite[key]
        for key in ("python", "numpy", "platform", "machine")
        if key in suite
    }
    replay = verify_replay(
        rows,
        expected=lambda row, algorithm: closed_loop_fingerprint(
            ExperimentConfig(**suite["scenario_configs"][str(row["scenario"])]),
            int(row["seed"]),
            next(
                (
                    item["attack_stop_step"]
                    for item in suite["scenarios"]
                    if item["name"] == str(row["scenario"])
                ),
                None,
            ),
            algorithm=algorithm,
        ),
        recorded_environment=_recorded_env or None,
        recorded_algorithm=(
            str(suite["fingerprint_algorithm"])
            if suite.get("fingerprint_algorithm")
            else None
        ),
    )
    project_root = Path(__file__).resolve().parents[2]
    upstream_verified, _ = _verify_upstream(project_root)
    audit_config = ExperimentConfig(
        **suite["scenario_configs"][M10A5_SCENARIOS[0].name]
    )
    compatibility_verified, compatibility_maximum = _compatibility_audit(
        audit_config,
        int(suite["seed_start"]),
    )
    decision = _decision(
        rows,
        summaries,
        effects,
        phase=str(suite["phase"]),
        seed_count=int(suite["seed_count"]),
        replay=replay,
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
        output / "milestone10a5_report.md",
        decision,
        summaries,
        int(suite["seed_start"]),
        int(suite["seed_count"]),
    )
    return decision
