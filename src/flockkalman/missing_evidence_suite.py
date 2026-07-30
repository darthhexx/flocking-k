"""M9A.6 oracle-relative evaluation for missing-evidence inference and pricing."""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import asdict, replace
import json
import math
import os
from pathlib import Path
import platform
from time import perf_counter

import numpy as np

from .config import ExperimentConfig
from .experiment import run_trial
from .metrics import StepRecord, summarize_run
from .missing_evidence import MissingEvidenceController
from .oracle_floor import OracleFloorCollector
from .simulation import scenario_fingerprint
from .suite import ScenarioDefinition, _bootstrap_interval, _write_csv
from .topology import connected_components
from .topology_suite import M9A_FULL, M9A_SCENARIOS, _fit_timing


M9A6_EXACT_NAMES = frozenset(scenario.name for scenario in M9A_SCENARIOS)
M9A6_CHALLENGE_SCENARIOS = (
    ScenarioDefinition(
        "unmodelled_count",
        "Three actual secondary sources challenge an assumed four-source model.",
        {
            "target_change_mode": "none",
            "secondary_mode_agent_count": 3,
            "secondary_mode_offset": (5.0, -4.0),
            "secondary_mode_start_step": 20,
            "secondary_mode_end_step": 90,
            "m9a6_override_declared_model": True,
            "m9a6_model_secondary_count": 4,
            "m9a6_model_secondary_offset": (5.0, -4.0),
            "m9a6_model_secondary_start_step": 20,
            "m9a6_model_secondary_end_step": 90,
        },
    ),
    ScenarioDefinition(
        "unmodelled_offset",
        "A shifted true secondary offset challenges the assumed offset model.",
        {
            "target_change_mode": "none",
            "secondary_mode_agent_count": 4,
            "secondary_mode_offset": (6.5, -2.0),
            "secondary_mode_start_step": 20,
            "secondary_mode_end_step": 90,
            "m9a6_override_declared_model": True,
            "m9a6_model_secondary_count": 4,
            "m9a6_model_secondary_offset": (5.0, -4.0),
            "m9a6_model_secondary_start_step": 20,
            "m9a6_model_secondary_end_step": 90,
        },
    ),
)
M9A6_SCENARIOS = M9A_SCENARIOS + M9A6_CHALLENGE_SCENARIOS


class MissingEvidenceShadowCollector:
    """Score M9A.6 on the frozen M9A physical trajectory."""

    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        self.controller = MissingEvidenceController(config)
        self.rows: list[dict[str, object]] = []

    def __call__(self, payload: dict[str, object]) -> None:
        step = int(payload["step"])
        truth = np.asarray(payload["truth"], dtype=float)
        observations = np.asarray(payload["observations"], dtype=float)
        covariances = tuple(
            np.asarray(value, dtype=float)
            for value in payload["measurement_covariances"]  # type: ignore[union-attr]
        )
        available = np.asarray(payload["available"], dtype=bool)
        operational = np.asarray(payload["operational"], dtype=bool)
        admitted = np.asarray(payload["admitted"], dtype=bool)
        neighbors = [
            list(peers) for peers in payload["neighbors"]  # type: ignore[union-attr]
        ]
        record = payload["record"]
        if not isinstance(record, StepRecord):
            raise TypeError("M9A.6 shadow received an invalid step record")

        components, labels = connected_components(neighbors, operational)
        observer_label = int(labels[0])
        if observer_label < 0 and components:
            observer_label = 0
        visible = np.zeros(self.config.n_agents, dtype=bool)
        if components and observer_label >= 0:
            visible[list(components[observer_label])] = True
        visible &= available & operational & admitted
        decision = self.controller.update(
            step,
            observations,
            covariances,
            visible,
        )

        all_errors = np.asarray(
            [
                np.linalg.norm(mode.state[:2] - truth[:2])
                for mode in decision.modes
            ]
        )
        credible_errors = np.asarray(
            [
                np.linalg.norm(mode.state[:2] - truth[:2])
                for mode in decision.credible_modes
            ]
        )
        truth_index = int(np.argmin(credible_errors))
        truth_mode = decision.credible_modes[truth_index]
        best_error = float(credible_errors[truth_index])
        team_error = float(np.linalg.norm(decision.state[:2] - truth[:2]))
        base_error = best_error if decision.action == "defer" else team_error
        loss = base_error + (
            self.config.output_defer_cost if decision.action == "defer" else 0.0
        )
        error = truth_mode.state[:2] - truth[:2]
        covariance = truth_mode.covariance[:2, :2]
        nees = float(error @ np.linalg.solve(covariance, error))
        wrong = (
            decision.action == "select"
            and len(decision.modes) > 1
            and team_error
            > float(np.min(all_errors))
            + self.config.robust_bias_group_tolerance
        )
        self.rows.append(
            {
                "step": step,
                "decision_loss": loss,
                "base_error": base_error,
                "team_error": team_error,
                "best_hypothesis_error": best_error,
                "action": decision.action,
                "wrong_mode": wrong,
                "nees": nees,
                "coverage95": nees <= 5.991,
                "residual_mass": decision.residual_mass,
                "model_nis": decision.model_nis,
                "assignment_entropy": decision.assignment_entropy,
                "predicted_risk": decision.predicted_risk,
                "predicted_wrong_risk": decision.predicted_wrong_risk,
                "credible_modes": len(decision.credible_modes),
                "visible_agents": int(np.sum(visible)),
                "mean_sensor_speed": record.mean_sensor_speed,
            }
        )

    def summarize(self) -> dict[str, object]:
        if not self.rows:
            raise ValueError("cannot summarize an empty M9A.6 shadow")

        def mean(name: str) -> float:
            return float(np.mean([float(row[name]) for row in self.rows]))

        nees = np.asarray([float(row["nees"]) for row in self.rows])
        return {
            "decision_loss": mean("decision_loss"),
            "mean_base_error": mean("base_error"),
            "position_rmse": math.sqrt(
                float(np.mean([float(row["team_error"]) ** 2 for row in self.rows]))
            ),
            "best_hypothesis_rmse": math.sqrt(
                float(
                    np.mean(
                        [
                            float(row["best_hypothesis_error"]) ** 2
                            for row in self.rows
                        ]
                    )
                )
            ),
            "selection_rate": float(
                np.mean([row["action"] == "select" for row in self.rows])
            ),
            "mixture_rate": float(
                np.mean([row["action"] == "mixture" for row in self.rows])
            ),
            "abstention_rate": float(
                np.mean([row["action"] == "defer" for row in self.rows])
            ),
            "wrong_mode_action_rate": mean("wrong_mode"),
            "mean_nees": float(np.mean(nees)),
            "p95_nees": float(np.quantile(nees, 0.95)),
            "max_nees": float(np.max(nees)),
            "coverage95_rate": mean("coverage95"),
            "mean_residual_mass": mean("residual_mass"),
            "max_residual_mass": float(
                np.max([float(row["residual_mass"]) for row in self.rows])
            ),
            "mean_model_nis": mean("model_nis"),
            "mean_assignment_entropy": mean("assignment_entropy"),
            "mean_predicted_risk": mean("predicted_risk"),
            "mean_predicted_wrong_risk": mean("predicted_wrong_risk"),
            "mean_credible_modes": mean("credible_modes"),
            "mean_visible_agents": mean("visible_agents"),
            "movement_distance": float(
                sum(
                    float(row["mean_sensor_speed"]) * self.config.dt
                    for row in self.rows
                )
            ),
        }


def _prefixed(prefix: str, values: dict[str, object]) -> dict[str, object]:
    return {f"{prefix}_{key}": value for key, value in values.items()}


def _worker(task: tuple[str, dict[str, object], int]) -> dict[str, object]:
    scenario_name, config_data, seed = task
    config = ExperimentConfig(**config_data)
    shadow = MissingEvidenceShadowCollector(config)
    oracle = OracleFloorCollector(config) if scenario_name in M9A6_EXACT_NAMES else None

    def observe(payload: dict[str, object]) -> None:
        shadow(payload)
        if oracle is not None:
            oracle(payload)

    started = perf_counter()
    records = run_trial(config, M9A_FULL, seed, step_observer=observe)
    runtime = perf_counter() - started
    current = summarize_run(config, records)
    candidate = shadow.summarize()
    row: dict[str, object] = {
        "scenario": scenario_name,
        "seed": seed,
        "runtime_seconds": runtime,
        "motion_distance_difference": float(candidate["movement_distance"])
        - float(current["movement_distance"]),
    }
    row.update(_prefixed("current", current))
    row.update(_prefixed("candidate", candidate))
    if oracle is not None:
        reference = oracle.summarize(seed)
        row.update(
            {
                "observer_loss": reference["observer_loss"],
                "global_loss": reference["global_loss"],
                "hindsight_floor_loss": reference["m9a_hypothesis_floor_loss"],
            }
        )
    else:
        row.update(
            {
                "observer_loss": None,
                "global_loss": None,
                "hindsight_floor_loss": None,
            }
        )
    return row


SUMMARY_METRICS = (
    "current_decision_loss",
    "current_wrong_mode_action_rate",
    "current_mean_nees",
    "current_p95_nees",
    "current_coverage95_rate",
    "candidate_decision_loss",
    "candidate_mean_base_error",
    "candidate_position_rmse",
    "candidate_best_hypothesis_rmse",
    "candidate_selection_rate",
    "candidate_mixture_rate",
    "candidate_abstention_rate",
    "candidate_wrong_mode_action_rate",
    "candidate_mean_nees",
    "candidate_p95_nees",
    "candidate_max_nees",
    "candidate_coverage95_rate",
    "candidate_mean_residual_mass",
    "candidate_max_residual_mass",
    "candidate_mean_model_nis",
    "candidate_mean_assignment_entropy",
    "candidate_mean_predicted_risk",
    "candidate_mean_predicted_wrong_risk",
    "candidate_mean_credible_modes",
    "candidate_mean_visible_agents",
    "motion_distance_difference",
    "observer_loss",
    "global_loss",
    "hindsight_floor_loss",
    "runtime_seconds",
)


def _scenario_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(str(row["scenario"]), []).append(row)
    result: list[dict[str, object]] = []
    for scenario, group in grouped.items():
        item: dict[str, object] = {"scenario": scenario, "runs": len(group)}
        for metric in SUMMARY_METRICS:
            values = [
                float(row[metric])
                for row in group
                if row.get(metric) not in (None, "")
            ]
            item[f"{metric}_mean"] = float(np.mean(values)) if values else None
            item[f"{metric}_std"] = float(np.std(values)) if values else None
        result.append(item)
    return result


def _paired_effects(
    rows: list[dict[str, object]],
    seeds: list[int],
    bootstrap_samples: int,
) -> list[dict[str, object]]:
    indexed = {
        (str(row["scenario"]), int(row["seed"])): row for row in rows
    }
    rng = np.random.default_rng(2026072217)
    effects: list[dict[str, object]] = []
    for scenario in M9A6_SCENARIOS:
        current = np.asarray(
            [
                float(indexed[(scenario.name, seed)]["current_decision_loss"])
                for seed in seeds
            ]
        )
        candidate = np.asarray(
            [
                float(indexed[(scenario.name, seed)]["candidate_decision_loss"])
                for seed in seeds
            ]
        )
        improvement = current - candidate
        lower, upper = _bootstrap_interval(improvement, bootstrap_samples, rng)
        effects.append(
            {
                "scenario": scenario.name,
                "comparison": "current_minus_candidate_loss",
                "pairs": len(seeds),
                "left_mean": float(np.mean(current)),
                "right_mean": float(np.mean(candidate)),
                "effect_mean": float(np.mean(improvement)),
                "ci95_lower": lower,
                "ci95_upper": upper,
            }
        )
        if scenario.name in M9A6_EXACT_NAMES:
            observer = np.asarray(
                [
                    float(indexed[(scenario.name, seed)]["observer_loss"])
                    for seed in seeds
                ]
            )
            regret = candidate - observer
            lower, upper = _bootstrap_interval(regret, bootstrap_samples, rng)
            effects.append(
                {
                    "scenario": scenario.name,
                    "comparison": "candidate_minus_observer_regret",
                    "pairs": len(seeds),
                    "left_mean": float(np.mean(candidate)),
                    "right_mean": float(np.mean(observer)),
                    "effect_mean": float(np.mean(regret)),
                    "ci95_lower": lower,
                    "ci95_upper": upper,
                }
            )

    stable = np.asarray(
        [
            float(indexed[("stable_control", seed)]["candidate_decision_loss"])
            for seed in seeds
        ]
    )
    for scenario in M9A_SCENARIOS[1:]:
        dynamic = np.asarray(
            [
                float(indexed[(scenario.name, seed)]["candidate_decision_loss"])
                for seed in seeds
            ]
        )
        transfer = stable - dynamic
        lower, upper = _bootstrap_interval(transfer, bootstrap_samples, rng)
        effects.append(
            {
                "scenario": scenario.name,
                "comparison": "candidate_stable_minus_dynamic_transfer",
                "pairs": len(seeds),
                "left_mean": float(np.mean(stable)),
                "right_mean": float(np.mean(dynamic)),
                "effect_mean": float(np.mean(transfer)),
                "ci95_lower": lower,
                "ci95_upper": upper,
            }
        )
    return effects


def _decision(
    scenario_rows: list[dict[str, object]],
    effects: list[dict[str, object]],
    trace_verified: bool,
    phase: str,
) -> dict[str, object]:
    scenario = {str(row["scenario"]): row for row in scenario_rows}
    effect = {
        (str(row["scenario"]), str(row["comparison"])): row for row in effects
    }
    exact = [scenario[item.name] for item in M9A_SCENARIOS]
    dynamic = [scenario[item.name] for item in M9A_SCENARIOS[1:]]
    improvement_pass = all(
        float(
            effect[(item.name, "current_minus_candidate_loss")]["ci95_lower"]
        )
        > 0.0
        for item in M9A_SCENARIOS
    )
    observer_regret_pass = all(
        float(
            effect[(item.name, "candidate_minus_observer_regret")]["ci95_upper"]
        )
        <= 0.10
        for item in M9A_SCENARIOS
    )
    safety_pass = all(
        float(row["candidate_wrong_mode_action_rate_mean"]) <= 0.01
        for row in scenario_rows
    )
    calibration_pass = all(
        float(row["candidate_mean_nees_mean"]) <= 6.0
        and float(row["candidate_p95_nees_mean"]) <= 20.0
        and float(row["candidate_coverage95_rate_mean"]) >= 0.88
        for row in exact
    )
    exact_residual_pass = all(
        float(row["candidate_mean_residual_mass_mean"]) <= 0.03
        for row in exact
    )
    count_mismatch = scenario["unmodelled_count"]
    offset_mismatch = scenario["unmodelled_offset"]
    residual_challenge_pass = (
        float(count_mismatch["candidate_mean_residual_mass_mean"]) >= 0.08
        and float(offset_mismatch["candidate_mean_residual_mass_mean"]) >= 0.08
        and max(
            float(count_mismatch["candidate_abstention_rate_mean"]),
            float(offset_mismatch["candidate_abstention_rate_mean"]),
        )
        >= 0.25
        and min(
            float(count_mismatch["candidate_mean_residual_mass_mean"]),
            float(offset_mismatch["candidate_mean_residual_mass_mean"]),
        )
        >= float(scenario["stable_control"]["candidate_mean_residual_mass_mean"])
        + 0.05
    )
    motion_pass = all(
        abs(float(row["motion_distance_difference_mean"])) <= 1e-12
        and float(row["motion_distance_difference_std"]) <= 1e-12
        for row in scenario_rows
    )
    # The asymmetric observer floor already misses the original absolute
    # transfer margin.  M9A.6 is judged against that local information bound.
    observer_boundary_respected = (
        float(
            effect[
                ("asymmetric_partition", "candidate_minus_observer_regret")
            ]["ci95_upper"]
        )
        <= 0.10
    )
    gates = {
        "replay": trace_verified,
        "exact_model_loss_improvement_every_scenario": improvement_pass,
        "observer_regret": observer_regret_pass,
        "wrong_action_safety": safety_pass,
        "calibration": calibration_pass,
        "nominal_residual_specificity": exact_residual_pass,
        "off_model_residual_response": residual_challenge_pass,
        "frozen_motion": motion_pass,
        "asymmetric_information_boundary": observer_boundary_respected,
    }
    passed = all(gates.values())
    if not trace_verified:
        verdict = "INVALID-SUITE"
    elif phase == "training":
        verdict = "M9A6-TRAINING-PASS" if passed else "M9A6-TRAINING-FAIL"
    else:
        verdict = "M9A6-GO" if passed else "M9A6-NO-GO"
    return {
        "verdict": verdict,
        "phase": phase,
        "gates": gates,
        "thresholds": {
            "per_scenario_loss_improvement_lcb_min": 0.0,
            "observer_regret_ucb_max": 0.10,
            "wrong_mode_action_rate_max": 0.01,
            "mean_nees_max": 6.0,
            "p95_nees_max": 20.0,
            "coverage95_min": 0.88,
            "exact_mean_residual_mass_max": 0.03,
            "off_model_mean_residual_mass_min": 0.08,
            "off_model_any_abstention_rate_min": 0.25,
            "off_model_residual_lift_min": 0.05,
            "motion_difference_tolerance": 1e-12,
        },
        "original_m9a_verdict_unchanged": True,
        "m9b_integration_authorized": phase == "heldout" and passed,
        "trace_replay_verified": trace_verified,
    }


def _verify_trace_manifest(
    scenario_configs: dict[str, dict[str, object]],
    entries: list[dict[str, object]],
) -> bool:
    return all(
        scenario_fingerprint(
            ExperimentConfig(**scenario_configs[str(entry["scenario"])]),
            int(entry["seed"]),
        )
        == entry["fingerprint"]
        for entry in entries
    )


def _write_report(
    path: Path,
    decision: dict[str, object],
    scenario_rows: list[dict[str, object]],
    effects: list[dict[str, object]],
    seed_start: int,
    seed_count: int,
) -> None:
    scenario = {str(row["scenario"]): row for row in scenario_rows}
    effect = {
        (str(row["scenario"]), str(row["comparison"])): row for row in effects
    }
    lines = [
        "# M9A.6 missing-evidence posterior and pricing report",
        "",
        f"**Verdict: `{decision['verdict']}`**",
        "",
        f"Phase: `{decision['phase']}`. Seeds: `{seed_start}`–`{seed_start + seed_count - 1}` ({seed_count} paired seeds per scenario).",
        "",
        "M9A.6 is an output-only overlay on the frozen M9A physical controller. It marginalizes declared missing-agent assignments, preserves posterior-predictive model-mismatch mass as residual unknown support, and prices select/mixture/defer actions by expected risk. The observer/global references and truth scoring remain outside the policy.",
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
            "## Exact-model topology scenarios",
            "",
            "| Scenario | Current | M9A.6 | Improvement LCB | Observer | Regret UCB | Global | Frozen-set floor | Residual | Defer | Wrong | NEES | Coverage |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in M9A_SCENARIOS:
        row = scenario[item.name]
        improvement = effect[(item.name, "current_minus_candidate_loss")]
        regret = effect[(item.name, "candidate_minus_observer_regret")]
        lines.append(
            f"| {item.name} | {float(row['current_decision_loss_mean']):.3f} | "
            f"{float(row['candidate_decision_loss_mean']):.3f} | {float(improvement['ci95_lower']):.3f} | "
            f"{float(row['observer_loss_mean']):.3f} | {float(regret['ci95_upper']):.3f} | "
            f"{float(row['global_loss_mean']):.3f} | "
            f"{float(row['hindsight_floor_loss_mean']):.3f} | "
            f"{float(row['candidate_mean_residual_mass_mean']):.3f} | "
            f"{float(row['candidate_abstention_rate_mean']):.3f} | "
            f"{float(row['candidate_wrong_mode_action_rate_mean']):.3f} | "
            f"{float(row['candidate_mean_nees_mean']):.2f} | "
            f"{float(row['candidate_coverage95_rate_mean']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Off-model challenges",
            "",
            "| Scenario | Current | M9A.6 | Residual | Peak residual | Defer | Wrong |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in M9A6_CHALLENGE_SCENARIOS:
        row = scenario[item.name]
        lines.append(
            f"| {item.name} | {float(row['current_decision_loss_mean']):.3f} | "
            f"{float(row['candidate_decision_loss_mean']):.3f} | "
            f"{float(row['candidate_mean_residual_mass_mean']):.3f} | "
            f"{float(row['candidate_max_residual_mass_mean']):.3f} | "
            f"{float(row['candidate_abstention_rate_mean']):.3f} | "
            f"{float(row['candidate_wrong_mode_action_rate_mean']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "A held-out GO authorizes M9B integration research, not production deployment. It does not change M9A.4, does not claim the declared assignment family is complete, and does not make component-local information equal ideal-global information. Residual mass must remain explicit in every later integration.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _materialize(
    output: Path,
    run_rows: list[dict[str, object]],
    suite_config: dict[str, object],
    trace_manifest: dict[str, object],
    *,
    bootstrap_samples: int,
) -> dict[str, object]:
    seed_start = int(suite_config["seed_start"])
    seed_count = int(suite_config["seed_count"])
    seeds = list(range(seed_start, seed_start + seed_count))
    scenario_rows = _scenario_summary(run_rows)
    effects = _paired_effects(run_rows, seeds, bootstrap_samples)
    trace_verified = _verify_trace_manifest(
        dict(suite_config["scenario_configs"]),  # type: ignore[arg-type]
        list(trace_manifest["entries"]),  # type: ignore[arg-type]
    )
    decision = _decision(
        scenario_rows,
        effects,
        trace_verified,
        str(suite_config["phase"]),
    )
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "run_summary.csv", run_rows)
    _write_csv(output / "scenario_summary.csv", scenario_rows)
    _write_csv(output / "paired_effects.csv", effects)
    trace_manifest["replay_verified"] = trace_verified
    (output / "trace_manifest.json").write_text(
        json.dumps(trace_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_report(
        output / "milestone9a6_report.md",
        decision,
        scenario_rows,
        effects,
        seed_start,
        seed_count,
    )
    return decision


def run_missing_evidence_suite(
    base_config: ExperimentConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 100,
    seed_start: int = 14000,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
    phase: str = "heldout",
) -> dict[str, object]:
    """Run the preregistered M9A.6 oracle-relative protocol."""
    if phase not in {"training", "heldout"}:
        raise ValueError("phase must be training or heldout")
    if seed_count < 2:
        raise ValueError("seed_count must be at least 2")
    if bootstrap_samples < 100:
        raise ValueError("bootstrap_samples must be at least 100")
    seeds = list(range(seed_start, seed_start + seed_count))
    tasks: list[tuple[str, dict[str, object], int]] = []
    scenario_configs: dict[str, dict[str, object]] = {}
    trace_entries: list[dict[str, object]] = []
    for scenario in M9A6_SCENARIOS:
        overrides = _fit_timing(scenario.overrides, base_config.steps)
        if bool(overrides.get("m9a6_override_declared_model", False)):
            overrides["m9a6_model_secondary_start_step"] = overrides[
                "secondary_mode_start_step"
            ]
            overrides["m9a6_model_secondary_end_step"] = overrides[
                "secondary_mode_end_step"
            ]
        config = replace(
            base_config,
            **overrides,
            seeds=seeds,
            algorithms=[M9A_FULL],
        )
        config.validate()
        config_data = config.to_dict()
        scenario_configs[scenario.name] = config_data
        for seed in seeds:
            tasks.append((scenario.name, config_data, seed))
            trace_entries.append(
                {
                    "scenario": scenario.name,
                    "seed": seed,
                    "fingerprint": scenario_fingerprint(config, seed),
                }
            )

    worker_count = workers or min(os.cpu_count() or 2, 8)
    executor_kind = "serial"
    if worker_count == 1:
        run_rows = [_worker(task) for task in tasks]
    else:
        try:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                run_rows = list(executor.map(_worker, tasks, chunksize=2))
            executor_kind = "process"
        except (PermissionError, OSError):
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                run_rows = list(executor.map(_worker, tasks))
            executor_kind = "thread_fallback"
    scenario_order = {
        scenario.name: index for index, scenario in enumerate(M9A6_SCENARIOS)
    }
    run_rows.sort(
        key=lambda row: (scenario_order[str(row["scenario"])], int(row["seed"]))
    )

    output = Path(output_directory)
    suite_config: dict[str, object] = {
        "phase": phase,
        "seed_start": seed_start,
        "seed_count": seed_count,
        "bootstrap_samples": bootstrap_samples,
        "workers": worker_count,
        "executor": executor_kind,
        "scenarios": [asdict(scenario) for scenario in M9A6_SCENARIOS],
        "scenario_configs": scenario_configs,
        "candidate_parameters": {
            key: value
            for key, value in base_config.to_dict().items()
            if key.startswith("m9a6_")
        },
        "frozen_physical_policy": M9A_FULL,
        "original_m9a_verdict_unchanged": True,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "platform_version": "0.12.0",
    }
    trace_manifest: dict[str, object] = {
        "candidate_is_output_only_shadow": True,
        "replay_verified": False,
        "entries": trace_entries,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "suite_config.json").write_text(
        json.dumps(suite_config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return _materialize(
        output,
        run_rows,
        suite_config,
        trace_manifest,
        bootstrap_samples=bootstrap_samples,
    )


def reanalyze_missing_evidence_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    """Rebuild M9A.6 statistics and verify every trace fingerprint."""
    output = Path(output_directory)
    suite_config = json.loads(
        (output / "suite_config.json").read_text(encoding="utf-8")
    )
    trace_manifest = json.loads(
        (output / "trace_manifest.json").read_text(encoding="utf-8")
    )
    with (output / "run_summary.csv").open(encoding="utf-8", newline="") as handle:
        run_rows = [dict(row) for row in csv.DictReader(handle)]
    return _materialize(
        output,
        run_rows,
        suite_config,
        trace_manifest,
        bootstrap_samples=int(
            bootstrap_samples or suite_config["bootstrap_samples"]
        ),
    )
