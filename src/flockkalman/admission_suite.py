"""Preregistered M9A.7 split-admission evaluation and tail gates."""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import asdict, replace
import json
import hashlib
import math
import os
from pathlib import Path
import platform
from time import perf_counter

import numpy as np

from .admission_evidence import AdmissionAwareController
from .config import ExperimentConfig
from .experiment import run_trial
from .metrics import StepRecord, summarize_run
from .missing_evidence_suite import (
    M9A6_CHALLENGE_SCENARIOS,
    MissingEvidenceShadowCollector,
)
from .oracle_floor import OracleFloorCollector
from .provenance import (
    CURRENT_FINGERPRINT_ALGORITHM,
    ReplayVerification,
    environment_fingerprint,
    replay_verdict_suffix,
    verify_replay,
)
from .simulation import scenario_fingerprint
from .suite import ScenarioDefinition, _bootstrap_interval, _write_csv
from .topology import connected_components
from .topology_suite import M9A_FULL, M9A_SCENARIOS, _fit_timing


M9A7_POSITIVE_CONTROL = ScenarioDefinition(
    "admission_censoring_control",
    "Aggressive rejoin probation makes fresh operational measurements routinely belief-censored.",
    {
        "target_change_mode": "none",
        "secondary_mode_agent_count": 4,
        "secondary_mode_offset": (5.0, -4.0),
        "secondary_mode_start_step": 20,
        "secondary_mode_end_step": 140,
        "agent_failure_count": 3,
        "agent_failure_step": 30,
        "agent_recovery_step": 60,
        "topology_partition_step": 65,
        "topology_partition_duration": 4,
        "topology_partition_repeat_interval": 10,
        "topology_partition_repeat_count": 7,
        "topology_rejoin_probation_steps": 40,
        "topology_rejoin_component_stable_steps": 4,
    },
)

M9A7_ATTACK = ScenarioDefinition(
    "raw_channel_colluding_ramp",
    "Three rejoining colluders ramp a shared offset and understate covariance on the raw channel.",
    {
        "target_change_mode": "none",
        "secondary_mode_agent_count": 3,
        "secondary_mode_offset": (5.0, -4.0),
        "secondary_mode_start_step": 20,
        "secondary_mode_end_step": 130,
        "strategic_agent_count": 3,
        "strategic_offset_magnitude": 5.0,
        "strategic_offset_direction": (0.7, 1.0),
        "strategic_ramp_steps": 30,
        "strategic_covariance_scale": 0.05,
        "agent_failure_count": 3,
        "agent_failure_step": 32,
        "agent_recovery_step": 58,
        "agent_failure_fault_type": 4,
        "topology_rejoin_probation_steps": 35,
        "m9a6_override_declared_model": True,
        "m9a6_model_secondary_count": 3,
        "m9a6_model_secondary_offset": (5.0, -4.0),
        "m9a6_model_secondary_start_step": 20,
        "m9a6_model_secondary_end_step": 130,
    },
)

M9A7_EXACT_SCENARIOS = M9A_SCENARIOS + (M9A7_POSITIVE_CONTROL,)
M9A7_EXACT_NAMES = frozenset(item.name for item in M9A7_EXACT_SCENARIOS)
M9A7_SCENARIOS = (
    M9A7_EXACT_SCENARIOS
    + M9A6_CHALLENGE_SCENARIOS
    + (M9A7_ATTACK,)
)

M9A7_PREREGISTERED_THRESHOLDS = {
    "natural_loss_noninferiority_lcb_min": -0.02,
    "positive_control_improvement_lcb_min": 0.0,
    "observer_regret_mean_ucb_max": 0.10,
    "observer_regret_p95_bootstrap_ucb_max": 0.20,
    "observer_regret_per_seed_max": 0.75,
    "wrong_mode_action_rate_max": 0.01,
    "mean_nees_max": 6.0,
    "p95_nees_max": 20.0,
    "coverage95_min": 0.88,
    "positive_control_mean_censored_agents_min": 0.50,
    "positive_control_censoring_rate_min": 0.20,
    "off_model_residual_mass_min": 0.08,
    "off_model_any_abstention_rate_min": 0.25,
    "attack_covariance_floor_rate_min": 0.10,
    "motion_difference_tolerance": 1e-12,
    "tail_event_frequency": 0.02,
    "tail_detection_probability": 0.95,
}


def _artifact_hash(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


class AdmissionEvidenceShadowCollector:
    """Score M9A.7 without changing the frozen M9A physical trajectory."""

    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        self.controller = AdmissionAwareController(config)
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
        raw_trusted = np.asarray(payload["raw_measurement_trusted"], dtype=bool)
        source_quarantined = np.asarray(payload["source_quarantined"], dtype=bool)
        belief_share_eligible = np.asarray(
            payload["belief_share_eligible"], dtype=bool
        )
        neighbors = [
            list(peers) for peers in payload["neighbors"]  # type: ignore[union-attr]
        ]
        record = payload["record"]
        if not isinstance(record, StepRecord):
            raise TypeError("M9A.7 shadow received an invalid step record")

        components, labels = connected_components(neighbors, operational)
        observer_label = int(labels[0])
        if observer_label < 0 and components:
            observer_label = 0
        component_visible = np.zeros(self.config.n_agents, dtype=bool)
        if components and observer_label >= 0:
            component_visible[list(components[observer_label])] = True
        result = self.controller.update(
            step,
            observations,
            covariances,
            component_visible=component_visible,
            available=available,
            operational=operational,
            raw_trusted=raw_trusted,
            source_quarantined=source_quarantined,
            belief_share_eligible=belief_share_eligible,
            belief_admitted=admitted,
        )
        decision = result.posterior
        all_errors = np.asarray(
            [np.linalg.norm(mode.state[:2] - truth[:2]) for mode in decision.modes]
        )
        credible_errors = np.asarray(
            [
                np.linalg.norm(mode.state[:2] - truth[:2])
                for mode in decision.credible_modes
            ]
        )
        truth_mode = decision.credible_modes[int(np.argmin(credible_errors))]
        best_error = float(np.min(credible_errors))
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
            > float(np.min(all_errors)) + self.config.robust_bias_group_tolerance
        )
        self.rows.append(
            {
                "decision_loss": loss,
                "base_error": base_error,
                "team_error": team_error,
                "best_hypothesis_error": best_error,
                "action": decision.action,
                "wrong_mode": wrong,
                "nees": nees,
                "coverage95": nees <= 5.991,
                "residual_mass": decision.residual_mass,
                "model_residual_mass": decision.model_residual_mass,
                "admission_residual_mass": result.admission_residual_mass,
                "model_nis": decision.model_nis,
                "assignment_entropy": decision.assignment_entropy,
                "measurement_eligible_agents": result.measurement_eligible_agents,
                "belief_admitted_agents": result.belief_admitted_agents,
                "belief_censored_measurement_agents": (
                    result.belief_censored_measurement_agents
                ),
                "robust_excluded_measurement_agents": (
                    result.robust_excluded_measurement_agents
                ),
                "unreachable_measurement_agents": (
                    result.unreachable_measurement_agents
                ),
                "covariance_floored_agents": result.covariance_floored_agents,
                "model_rejected_measurement_agents": (
                    result.model_rejected_measurement_agents
                ),
                "excluded_secondary_probability": (
                    result.excluded_secondary_probability
                ),
                "unreachable_secondary_probability": (
                    result.unreachable_secondary_probability
                ),
                "quarantined_agents": record.quarantined_agents,
                "mean_sensor_speed": record.mean_sensor_speed,
            }
        )

    def summarize(self) -> dict[str, object]:
        if not self.rows:
            raise ValueError("cannot summarize an empty M9A.7 shadow")

        def mean(name: str) -> float:
            return float(np.mean([float(row[name]) for row in self.rows]))

        nees = np.asarray([float(row["nees"]) for row in self.rows])
        return {
            "decision_loss": mean("decision_loss"),
            "mean_base_error": mean("base_error"),
            "position_rmse": math.sqrt(mean_squared(self.rows, "team_error")),
            "best_hypothesis_rmse": math.sqrt(
                mean_squared(self.rows, "best_hypothesis_error")
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
            "coverage95_rate": mean("coverage95"),
            "mean_residual_mass": mean("residual_mass"),
            "max_residual_mass": float(
                np.max([float(row["residual_mass"]) for row in self.rows])
            ),
            "mean_model_residual_mass": mean("model_residual_mass"),
            "mean_admission_residual_mass": mean("admission_residual_mass"),
            "mean_model_nis": mean("model_nis"),
            "mean_assignment_entropy": mean("assignment_entropy"),
            "mean_measurement_eligible_agents": mean("measurement_eligible_agents"),
            "mean_belief_admitted_agents": mean("belief_admitted_agents"),
            "mean_belief_censored_measurement_agents": mean(
                "belief_censored_measurement_agents"
            ),
            "belief_censoring_rate": float(
                np.mean(
                    [
                        int(row["belief_censored_measurement_agents"]) > 0
                        for row in self.rows
                    ]
                )
            ),
            "mean_robust_excluded_measurement_agents": mean(
                "robust_excluded_measurement_agents"
            ),
            "mean_unreachable_measurement_agents": mean(
                "unreachable_measurement_agents"
            ),
            "mean_covariance_floored_agents": mean("covariance_floored_agents"),
            "mean_model_rejected_measurement_agents": mean(
                "model_rejected_measurement_agents"
            ),
            "covariance_floor_rate": float(
                np.mean(
                    [int(row["covariance_floored_agents"]) > 0 for row in self.rows]
                )
            ),
            "mean_excluded_secondary_probability": mean(
                "excluded_secondary_probability"
            ),
            "mean_unreachable_secondary_probability": mean(
                "unreachable_secondary_probability"
            ),
            "mean_quarantined_agents": mean("quarantined_agents"),
            "quarantine_rate": float(
                np.mean([int(row["quarantined_agents"]) > 0 for row in self.rows])
            ),
            "movement_distance": float(
                sum(
                    float(row["mean_sensor_speed"]) * self.config.dt
                    for row in self.rows
                )
            ),
        }


def mean_squared(rows: list[dict[str, object]], name: str) -> float:
    return float(np.mean([float(row[name]) ** 2 for row in rows]))


def _prefixed(prefix: str, values: dict[str, object]) -> dict[str, object]:
    return {f"{prefix}_{key}": value for key, value in values.items()}


def _worker(task: tuple[str, dict[str, object], int]) -> dict[str, object]:
    scenario_name, config_data, seed = task
    config = ExperimentConfig(**config_data)
    baseline = MissingEvidenceShadowCollector(config)
    candidate = AdmissionEvidenceShadowCollector(config)
    oracle = OracleFloorCollector(config) if scenario_name in M9A7_EXACT_NAMES else None

    def observe(payload: dict[str, object]) -> None:
        baseline(payload)
        candidate(payload)
        if oracle is not None:
            oracle(payload)

    started = perf_counter()
    records = run_trial(config, M9A_FULL, seed, step_observer=observe)
    runtime = perf_counter() - started
    physical = summarize_run(config, records)
    baseline_summary = baseline.summarize()
    candidate_summary = candidate.summarize()
    # Both shadows consume the same frozen robust tracker; expose the shared
    # quarantine trace under both prefixes so the non-increase gate is
    # explicit rather than merely assumed.
    baseline_summary["mean_quarantined_agents"] = physical[
        "mean_quarantined_agents"
    ]
    baseline_summary["quarantine_rate"] = physical["quarantine_rate"]
    row: dict[str, object] = {
        "scenario": scenario_name,
        "seed": seed,
        "runtime_seconds": runtime,
        "motion_distance_difference": (
            float(candidate_summary["movement_distance"])
            - float(physical["movement_distance"])
        ),
    }
    row.update(_prefixed("baseline", baseline_summary))
    row.update(_prefixed("candidate", candidate_summary))
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
            {"observer_loss": None, "global_loss": None, "hindsight_floor_loss": None}
        )
    return row


SUMMARY_METRICS = (
    "baseline_decision_loss",
    "baseline_abstention_rate",
    "baseline_wrong_mode_action_rate",
    "candidate_decision_loss",
    "candidate_position_rmse",
    "candidate_best_hypothesis_rmse",
    "candidate_selection_rate",
    "candidate_mixture_rate",
    "candidate_abstention_rate",
    "candidate_wrong_mode_action_rate",
    "candidate_mean_nees",
    "candidate_p95_nees",
    "candidate_coverage95_rate",
    "candidate_mean_residual_mass",
    "candidate_max_residual_mass",
    "candidate_mean_model_residual_mass",
    "candidate_mean_admission_residual_mass",
    "candidate_mean_model_nis",
    "candidate_mean_assignment_entropy",
    "candidate_mean_measurement_eligible_agents",
    "candidate_mean_belief_admitted_agents",
    "candidate_mean_belief_censored_measurement_agents",
    "candidate_belief_censoring_rate",
    "candidate_mean_robust_excluded_measurement_agents",
    "candidate_mean_unreachable_measurement_agents",
    "candidate_mean_covariance_floored_agents",
    "candidate_mean_model_rejected_measurement_agents",
    "candidate_covariance_floor_rate",
    "candidate_mean_excluded_secondary_probability",
    "candidate_mean_unreachable_secondary_probability",
    "baseline_mean_quarantined_agents",
    "candidate_mean_quarantined_agents",
    "baseline_quarantine_rate",
    "candidate_quarantine_rate",
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
        if scenario in M9A7_EXACT_NAMES:
            regret = np.asarray(
                [
                    float(row["candidate_decision_loss"])
                    - float(row["observer_loss"])
                    for row in group
                ]
            )
            item["observer_regret_p95"] = float(np.quantile(regret, 0.95))
            item["observer_regret_max"] = float(np.max(regret))
            item["observer_regret_over_0_20_rate"] = float(np.mean(regret > 0.20))
        result.append(item)
    return result


def _bootstrap_quantile_upper(
    values: np.ndarray,
    bootstrap_samples: int,
    rng: np.random.Generator,
    quantile: float = 0.95,
) -> float:
    sampled_quantiles = np.empty(bootstrap_samples, dtype=float)
    for index in range(bootstrap_samples):
        sample = values[rng.integers(0, len(values), size=len(values))]
        sampled_quantiles[index] = float(np.quantile(sample, quantile))
    return float(np.quantile(sampled_quantiles, 0.975))


def _paired_effects(
    rows: list[dict[str, object]],
    seeds: list[int],
    bootstrap_samples: int,
) -> list[dict[str, object]]:
    indexed = {(str(row["scenario"]), int(row["seed"])): row for row in rows}
    rng = np.random.default_rng(2026072223)
    effects: list[dict[str, object]] = []
    for scenario in M9A7_SCENARIOS:
        baseline = np.asarray(
            [
                float(indexed[(scenario.name, seed)]["baseline_decision_loss"])
                for seed in seeds
            ]
        )
        candidate = np.asarray(
            [
                float(indexed[(scenario.name, seed)]["candidate_decision_loss"])
                for seed in seeds
            ]
        )
        improvement = baseline - candidate
        lower, upper = _bootstrap_interval(improvement, bootstrap_samples, rng)
        effects.append(
            {
                "scenario": scenario.name,
                "comparison": "m9a6_minus_m9a7_loss",
                "pairs": len(seeds),
                "effect_mean": float(np.mean(improvement)),
                "ci95_lower": lower,
                "ci95_upper": upper,
            }
        )
        if scenario.name in M9A7_EXACT_NAMES:
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
                    "comparison": "m9a7_minus_observer_regret",
                    "pairs": len(seeds),
                    "effect_mean": float(np.mean(regret)),
                    "ci95_lower": lower,
                    "ci95_upper": upper,
                }
            )
            effects.append(
                {
                    "scenario": scenario.name,
                    "comparison": "m9a7_observer_regret_p95",
                    "pairs": len(seeds),
                    "effect_mean": float(np.quantile(regret, 0.95)),
                    "ci95_lower": None,
                    "ci95_upper": _bootstrap_quantile_upper(
                        regret, bootstrap_samples, rng
                    ),
                }
            )
    return effects


def required_seed_count(event_frequency: float, detection_probability: float) -> int:
    """Minimum independent seeds needed to observe at least one tail event."""
    if not 0.0 < event_frequency < 1.0:
        raise ValueError("event_frequency must be in (0, 1)")
    if not 0.0 < detection_probability < 1.0:
        raise ValueError("detection_probability must be in (0, 1)")
    return int(
        math.ceil(
            math.log(1.0 - detection_probability) / math.log(1.0 - event_frequency)
        )
    )


def _decision(
    scenario_rows: list[dict[str, object]],
    effects: list[dict[str, object]],
    replay: ReplayVerification,
    phase: str,
    seed_count: int,
) -> dict[str, object]:
    threshold = M9A7_PREREGISTERED_THRESHOLDS
    scenario = {str(row["scenario"]): row for row in scenario_rows}
    effect = {(str(row["scenario"]), str(row["comparison"])): row for row in effects}
    natural = [scenario[item.name] for item in M9A_SCENARIOS]
    exact = [scenario[item.name] for item in M9A7_EXACT_SCENARIOS]
    positive = scenario[M9A7_POSITIVE_CONTROL.name]
    attack = scenario[M9A7_ATTACK.name]
    power_required = required_seed_count(
        float(threshold["tail_event_frequency"]),
        float(threshold["tail_detection_probability"]),
    )
    gates = {
        "replay": replay.verified,
        # Training is a development split, not a promotion attempt.  The
        # preregistered minimum becomes binding only on the held-out verdict.
        "tail_event_power": phase == "training" or seed_count >= power_required,
        "positive_control_is_exercised": (
            float(positive["candidate_mean_belief_censored_measurement_agents_mean"])
            >= float(threshold["positive_control_mean_censored_agents_min"])
            and float(positive["candidate_belief_censoring_rate_mean"])
            >= float(threshold["positive_control_censoring_rate_min"])
        ),
        "positive_control_repairs_loss": float(
            effect[(M9A7_POSITIVE_CONTROL.name, "m9a6_minus_m9a7_loss")][
                "ci95_lower"
            ]
        )
        > float(threshold["positive_control_improvement_lcb_min"]),
        "natural_scenario_noninferiority": all(
            float(effect[(item.name, "m9a6_minus_m9a7_loss")]["ci95_lower"])
            > float(threshold["natural_loss_noninferiority_lcb_min"])
            for item in M9A_SCENARIOS
        ),
        "mean_observer_regret": all(
            float(effect[(item.name, "m9a7_minus_observer_regret")]["ci95_upper"])
            <= float(threshold["observer_regret_mean_ucb_max"])
            for item in M9A7_EXACT_SCENARIOS
        ),
        "p95_observer_regret": all(
            float(effect[(item.name, "m9a7_observer_regret_p95")]["ci95_upper"])
            <= float(threshold["observer_regret_p95_bootstrap_ucb_max"])
            for item in M9A_SCENARIOS
        ),
        "per_seed_observer_regret": all(
            float(row["observer_regret_max"])
            <= float(threshold["observer_regret_per_seed_max"])
            for row in natural
        ),
        "wrong_action_safety": all(
            float(row["candidate_wrong_mode_action_rate_mean"])
            <= float(threshold["wrong_mode_action_rate_max"])
            for row in scenario_rows
        ),
        "calibration": all(
            float(row["candidate_mean_nees_mean"])
            <= float(threshold["mean_nees_max"])
            and float(row["candidate_p95_nees_mean"])
            <= float(threshold["p95_nees_max"])
            and float(row["candidate_coverage95_rate_mean"])
            >= float(threshold["coverage95_min"])
            for row in exact
        ),
        "off_model_residual_response": (
            min(
                float(
                    scenario[item.name]["candidate_mean_residual_mass_mean"]
                )
                for item in M9A6_CHALLENGE_SCENARIOS
            )
            >= float(threshold["off_model_residual_mass_min"])
            and max(
                float(scenario[item.name]["candidate_abstention_rate_mean"])
                for item in M9A6_CHALLENGE_SCENARIOS
            )
            >= float(threshold["off_model_any_abstention_rate_min"])
        ),
        "raw_channel_attack_safety": (
            float(attack["candidate_wrong_mode_action_rate_mean"])
            <= float(attack["baseline_wrong_mode_action_rate_mean"]) + 1e-12
            and float(attack["candidate_quarantine_rate_mean"])
            <= float(attack["baseline_quarantine_rate_mean"]) + 1e-12
            and float(attack["candidate_covariance_floor_rate_mean"])
            >= float(threshold["attack_covariance_floor_rate_min"])
        ),
        "frozen_motion": all(
            abs(float(row["motion_distance_difference_mean"]))
            <= float(threshold["motion_difference_tolerance"])
            and float(row["motion_distance_difference_std"])
            <= float(threshold["motion_difference_tolerance"])
            for row in scenario_rows
        ),
    }
    # M14.3: replay adjudicated separately; only an unexplained mismatch blocks.
    passed = all(value for name, value in gates.items() if name != "replay")
    _suffix = replay_verdict_suffix(replay)
    verdict = (
        "INVALID-SUITE"
        if replay.blocks_promotion
        else (
            "M9A7-TRAINING-PASS" if phase == "training" and passed else
            "M9A7-TRAINING-FAIL" if phase == "training" else
            "M9A7-GO" if passed else "M9A7-NO-GO"
        )
    )
    return {
        "verdict": verdict,
        "phase": phase,
        "gates": gates,
        "thresholds": threshold,
        "power_calculation": {
            "event_frequency": threshold["tail_event_frequency"],
            "detection_probability": threshold["tail_detection_probability"],
            "minimum_seed_count": power_required,
            "actual_seed_count": seed_count,
            "actual_at_least_one_detection_probability": 1.0
            - (1.0 - float(threshold["tail_event_frequency"])) ** seed_count,
        },
        "m9b_integration_authorized": phase == "heldout" and passed,
        "original_m9a_and_m9a6_verdicts_unchanged": True,
        "trace_replay_verified": replay.verified,
        "replay_verification": replay.to_dict(),
        "environment": environment_fingerprint(),
    }


def _verify_trace_manifest(
    scenario_configs: dict[str, dict[str, object]],
    entries: list[dict[str, object]],
    *,
    recorded_environment: dict[str, object] | None = None,
    recorded_algorithm: str | None = None,
) -> ReplayVerification:
    """Verify the trace manifest, separating env churn and schema drift (M14.3)."""
    return verify_replay(
        [dict(entry) for entry in entries],
        expected=lambda entry, algorithm: scenario_fingerprint(
            ExperimentConfig(**scenario_configs[str(entry["scenario"])]),
            int(entry["seed"]),
            algorithm=algorithm,
        ),
        schema_expected=lambda entry, algorithm: scenario_fingerprint(
            ExperimentConfig(**scenario_configs[str(entry["scenario"])]),
            int(entry["seed"]),
            algorithm=algorithm,
            config_payload=dict(scenario_configs[str(entry["scenario"])]),
        ),
        recorded_environment=recorded_environment,
        recorded_algorithm=recorded_algorithm,
        fingerprint_key="fingerprint",
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
    effect = {(str(row["scenario"]), str(row["comparison"])): row for row in effects}
    lines = [
        "# M9A.7 split-admission and tail-safety report",
        "",
        f"**Verdict: `{decision['verdict']}`**",
        "",
        f"Phase: `{decision['phase']}`. Seeds: `{seed_start}`–`{seed_start + seed_count - 1}` ({seed_count} paired seeds per scenario).",
        "",
        "M9A.7 is an output-only overlay on the frozen M9A trajectory. Fresh raw measurements use source-local robust trust and a covariance floor; recursively fused beliefs retain lifecycle admission. The policy never sees truth, realized future noise, or seeded identities.",
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
            "## Exact-model scenarios",
            "",
            "| Scenario | M9A.6 | M9A.7 | Improvement LCB | Observer | Mean regret UCB | P95 regret | P95 UCB | Max regret | Censored | Censor rate | Wrong | NEES | Coverage |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in M9A7_EXACT_SCENARIOS:
        row = scenario[item.name]
        improvement = effect[(item.name, "m9a6_minus_m9a7_loss")]
        regret = effect[(item.name, "m9a7_minus_observer_regret")]
        tail = effect[(item.name, "m9a7_observer_regret_p95")]
        lines.append(
            f"| {item.name} | {float(row['baseline_decision_loss_mean']):.3f} | "
            f"{float(row['candidate_decision_loss_mean']):.3f} | {float(improvement['ci95_lower']):.3f} | "
            f"{float(row['observer_loss_mean']):.3f} | {float(regret['ci95_upper']):.3f} | "
            f"{float(row['observer_regret_p95']):.3f} | {float(tail['ci95_upper']):.3f} | "
            f"{float(row['observer_regret_max']):.3f} | "
            f"{float(row['candidate_mean_belief_censored_measurement_agents_mean']):.2f} | "
            f"{float(row['candidate_belief_censoring_rate_mean']):.3f} | "
            f"{float(row['candidate_wrong_mode_action_rate_mean']):.3f} | "
            f"{float(row['candidate_mean_nees_mean']):.2f} | "
            f"{float(row['candidate_coverage95_rate_mean']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Robustness challenges",
            "",
            "| Scenario | M9A.6 | M9A.7 | Residual | Defer | Wrong | Covariance-floor rate | Quarantine delta |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in M9A6_CHALLENGE_SCENARIOS + (M9A7_ATTACK,):
        row = scenario[item.name]
        lines.append(
            f"| {item.name} | {float(row['baseline_decision_loss_mean']):.3f} | "
            f"{float(row['candidate_decision_loss_mean']):.3f} | "
            f"{float(row['candidate_mean_residual_mass_mean']):.3f} | "
            f"{float(row['candidate_abstention_rate_mean']):.3f} | "
            f"{float(row['candidate_wrong_mode_action_rate_mean']):.3f} | "
            f"{float(row['candidate_covariance_floor_rate_mean']):.3f} | "
            f"{float(row['candidate_quarantine_rate_mean']) - float(row['baseline_quarantine_rate_mean']):.3f} |"
        )
    power = dict(decision["power_calculation"])
    lines.extend(
        [
            "",
            "## Power and boundary",
            "",
            f"The preregistered 2% tail calculation requires {power['minimum_seed_count']} independent seeds for a 95% chance of observing at least one event. This run used {power['actual_seed_count']} seeds, giving probability {float(power['actual_at_least_one_detection_probability']):.4f}.",
            "",
            "A held-out GO authorizes an M9A/M9B integration experiment, not production deployment. The original M9A and M9A.6 verdicts remain immutable.",
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
    replay = _verify_trace_manifest(
        dict(suite_config["scenario_configs"]),  # type: ignore[arg-type]
        list(trace_manifest["entries"]),  # type: ignore[arg-type]
        recorded_environment={
            key: suite_config[key]
            for key in ("python", "numpy", "platform", "machine")
            if key in suite_config
        }
        or None,
        recorded_algorithm=(
            str(suite_config["fingerprint_algorithm"])
            if suite_config.get("fingerprint_algorithm")
            else None
        ),
    )
    decision = _decision(
        scenario_rows,
        effects,
        replay,
        str(suite_config["phase"]),
        seed_count,
    )
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "run_summary.csv", run_rows)
    _write_csv(output / "scenario_summary.csv", scenario_rows)
    _write_csv(output / "paired_effects.csv", effects)
    trace_manifest["replay_verified"] = replay.verified
    trace_manifest["replay_verification"] = replay.to_dict()
    (output / "trace_manifest.json").write_text(
        json.dumps(trace_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    _write_report(
        output / "milestone9a7_report.md",
        decision,
        scenario_rows,
        effects,
        seed_start,
        seed_count,
    )
    return decision


def run_admission_evidence_suite(
    base_config: ExperimentConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 300,
    seed_start: int = 16000,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
    phase: str = "heldout",
    scenario_field_overrides: dict[str, dict[str, object]] | None = None,
) -> dict[str, object]:
    """Run the frozen, preregistered M9A.7 protocol.

    ``scenario_field_overrides`` maps a scenario name to fields that replace entries
    in that scenario's override dict, applied BEFORE ``_fit_timing`` so the timing
    fit sees the final values. Added for M17, whose dose axis is
    ``topology_rejoin_probation_steps`` -- a field the positive-control scenario sets
    itself, so it cannot be varied from ``base_config``.

    The alternative was for the caller to pre-fit the overrides and pass a finished
    config, which would mean the dose sweep and this suite's own frozen baseline were
    no longer built by the same code path; any divergence would then present as a
    dose effect on the gate that decides the research direction. Threading the
    override through here keeps one code path, and the applied values are recorded in
    ``suite_config.json`` so a reader can see which dose produced an artifact.

    Passing ``None`` reproduces the frozen protocol exactly.
    """
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
    applied_field_overrides: dict[str, dict[str, object]] = {}
    for scenario in M9A7_SCENARIOS:
        raw_overrides = dict(scenario.overrides)
        extra = (scenario_field_overrides or {}).get(scenario.name)
        if extra:
            unknown = set(extra) - set(ExperimentConfig.__dataclass_fields__)
            if unknown:
                raise ValueError(
                    f"scenario_field_overrides for {scenario.name!r} names fields "
                    f"that are not on ExperimentConfig: {sorted(unknown)}"
                )
            raw_overrides.update(extra)
            applied_field_overrides[scenario.name] = dict(extra)
        overrides = _fit_timing(raw_overrides, base_config.steps)
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
                    "fingerprint": scenario_fingerprint(
                        config, seed, algorithm=CURRENT_FINGERPRINT_ALGORITHM
                    ),
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
    order = {item.name: index for index, item in enumerate(M9A7_SCENARIOS)}
    run_rows.sort(key=lambda row: (order[str(row["scenario"])], int(row["seed"])))
    output = Path(output_directory)
    project_root = Path(__file__).resolve().parents[2]
    protocol_path = project_root / "M9A7_PROTOCOL.md"
    candidate_sources = (
        Path(__file__).resolve(),
        Path(__file__).with_name("admission_evidence.py").resolve(),
        Path(__file__).with_name("missing_evidence.py").resolve(),
        Path(__file__).with_name("oracle_floor.py").resolve(),
    )
    suite_config: dict[str, object] = {
        "phase": phase,
        "seed_start": seed_start,
        "seed_count": seed_count,
        "bootstrap_samples": bootstrap_samples,
        "workers": worker_count,
        "executor": executor_kind,
        "scenarios": [asdict(item) for item in M9A7_SCENARIOS],
        "scenario_configs": scenario_configs,
        "candidate_parameters": {
            key: value
            for key, value in base_config.to_dict().items()
            if key.startswith("m9a6_") or key.startswith("m9a7_")
        },
        "preregistered_thresholds": M9A7_PREREGISTERED_THRESHOLDS,
        "protocol_sha256": _artifact_hash((protocol_path,)),
        "candidate_source_sha256": _artifact_hash(candidate_sources),
        "frozen_physical_policy": M9A_FULL,
        "fingerprint_algorithm": CURRENT_FINGERPRINT_ALGORITHM,
        "scenario_field_overrides": applied_field_overrides,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "platform_version": "0.12.0",
    }
    trace_manifest: dict[str, object] = {
        "candidate_is_output_only_shadow": True,
        "baseline_is_m9a6_shadow": True,
        "replay_verified": False,
        "entries": trace_entries,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "suite_config.json").write_text(
        json.dumps(suite_config, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return _materialize(
        output,
        run_rows,
        suite_config,
        trace_manifest,
        bootstrap_samples=bootstrap_samples,
    )


def reanalyze_admission_evidence_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    """Rebuild M9A.7 statistics and verify every exogenous trace."""
    output = Path(output_directory)
    suite_config = json.loads((output / "suite_config.json").read_text(encoding="utf-8"))
    trace_manifest = json.loads((output / "trace_manifest.json").read_text(encoding="utf-8"))
    with (output / "run_summary.csv").open(encoding="utf-8", newline="") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    return _materialize(
        output,
        rows,
        suite_config,
        trace_manifest,
        bootstrap_samples=int(bootstrap_samples or suite_config["bootstrap_samples"]),
    )
