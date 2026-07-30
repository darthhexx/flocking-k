"""Preregistered M10A raw-channel adversarial-trust evaluation."""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import asdict, replace
import hashlib
import json
import math
import os
from pathlib import Path
import platform
from time import perf_counter

import numpy as np

from .adversarial_trust import (
    M10A_DEFENSE_MODES,
    AdversarialTrustConfig,
    AdversarialTrustController,
)
from .admission_suite import M9A7_ATTACK, M9A7_POSITIVE_CONTROL
from .config import ExperimentConfig
from .experiment import run_trial
from .integrated_sensing import M9C_RECEDING_ALGORITHM
from .integration_suite import M9C_SOURCE_COMPETITION
from .metrics import StepRecord
from .provenance import (
    CURRENT_FINGERPRINT_ALGORITHM,
    ReplayVerification,
    environment_fingerprint,
    verify_replay,
)
from .simulation import (
    make_scenario,
    scenario_fingerprint,
    verify_scenario_replay,
)
from .suite import ScenarioDefinition, _bootstrap_interval, _write_csv
from .topology import connected_components
from .topology_suite import M9A_SCENARIOS, _fit_timing


M10A_BASELINE = "m9c_baseline"
M10A_CROSS = "cross_channel"
M10A_RAMP = "ramp_rate"
M10A_INFLUENCE = "influence_budget"
M10A_COMBINED = "combined"
M10A_ARMS = (
    M10A_BASELINE,
    M10A_CROSS,
    M10A_RAMP,
    M10A_INFLUENCE,
    M10A_COMBINED,
)


def _named_m9a(name: str) -> ScenarioDefinition:
    return next(item for item in M9A_SCENARIOS if item.name == name)


M10A_GENUINE_MANEUVER = ScenarioDefinition(
    "genuine_target_maneuver",
    "Abrupt shared target manoeuvre without a strategic source.",
    {
        "target_change_mode": "abrupt",
        "secondary_mode_agent_count": 0,
        "secondary_mode_start_step": 0,
        "secondary_mode_end_step": -1,
    },
)

M10A_HETEROGENEOUS_PRECISION = ScenarioDefinition(
    "legitimate_heterogeneous_precision",
    "Accurately reported high-quality sources must not be mistaken for covariance understatement.",
    {
        "target_change_mode": "none",
        "secondary_mode_agent_count": 4,
        "secondary_mode_offset": (5.0, -4.0),
        "secondary_mode_start_step": 20,
        "secondary_mode_end_step": 90,
        "sensor_noise_scale_min": 0.40,
        "sensor_noise_scale_max": 1.0,
    },
)


def _attack(
    name: str,
    description: str,
    colluders: int,
    ramp_steps: int,
    covariance_scale: float,
) -> ScenarioDefinition:
    return ScenarioDefinition(
        name,
        description,
        {
            "target_change_mode": "none",
            "secondary_mode_agent_count": 3,
            "secondary_mode_offset": (5.0, -4.0),
            "secondary_mode_start_step": 20,
            "secondary_mode_end_step": 130,
            "strategic_agent_count": colluders,
            "strategic_offset_magnitude": 5.0,
            "strategic_offset_direction": (0.7, 1.0),
            "strategic_ramp_steps": ramp_steps,
            "strategic_covariance_scale": covariance_scale,
            "m9a6_override_declared_model": True,
            "m9a6_model_secondary_count": 3,
            "m9a6_model_secondary_offset": (5.0, -4.0),
            "m9a6_model_secondary_start_step": 20,
            "m9a6_model_secondary_end_step": 130,
        },
    )


M10A_ATTACK_MILD = _attack(
    "raw_attack_mild",
    "One colluder uses a slow ramp and modest covariance understatement.",
    1,
    60,
    0.20,
)
M10A_ATTACK_MODERATE = _attack(
    "raw_attack_moderate",
    "Two colluders use the registered ramp and stronger covariance understatement.",
    2,
    30,
    0.10,
)
M10A_ATTACK_SEVERE = _attack(
    "raw_attack_severe",
    "Three colluders use a fast ramp and severe covariance understatement.",
    3,
    15,
    0.05,
)

M10A_CONTROL_SCENARIOS = (
    _named_m9a("stable_control"),
    _named_m9a("failure_partition"),
    _named_m9a("flapping_reconnect"),
    M9A7_POSITIVE_CONTROL,
    M9C_SOURCE_COMPETITION,
    M10A_GENUINE_MANEUVER,
    M10A_HETEROGENEOUS_PRECISION,
)
M10A_ATTACK_SCENARIOS = (
    M10A_ATTACK_MILD,
    M10A_ATTACK_MODERATE,
    M10A_ATTACK_SEVERE,
    M9A7_ATTACK,
)
M10A_SCENARIOS = M10A_CONTROL_SCENARIOS + M10A_ATTACK_SCENARIOS

M10A_THRESHOLDS = {
    "availability_loss_multiplier": 2.0,
    "control_noninferiority_lcb_min": -0.02,
    "control_false_alert_rate_max": 0.05,
    "wrong_mode_action_rate_max": 0.01,
    "mean_nees_max": 6.0,
    "p95_nees_max": 20.0,
    "coverage95_min": 0.88,
    "canonical_improvement_lcb_min": 0.0,
    "attack_detection_rate_mild_min": 0.25,
    "attack_detection_rate_other_min": 0.50,
    "dose_adjacent_loss_increase_max": 0.35,
    "shadow_tolerance": 1e-12,
    "motion_tolerance": 1e-12,
    "tail_event_frequency": 0.02,
    "tail_detection_probability": 0.95,
}


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


class TrustAssayCollector:
    """Evaluate every trust ablation on one frozen M9C physical trajectory."""

    def __init__(
        self,
        config: ExperimentConfig,
        strategic_sources: np.ndarray,
        trust_config: AdversarialTrustConfig,
    ) -> None:
        self.config = config
        self.strategic_sources = np.asarray(strategic_sources, dtype=bool)
        self.controllers = {
            M10A_BASELINE: AdversarialTrustController(config, "none", trust_config),
            **{
                mode: AdversarialTrustController(config, mode, trust_config)
                for mode in M10A_DEFENSE_MODES
            },
        }
        self.rows = {arm: [] for arm in M10A_ARMS}

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
        quarantined = np.asarray(payload["source_quarantined"], dtype=bool)
        belief_share_eligible = np.asarray(
            payload["belief_share_eligible"], dtype=bool
        )
        neighbors = [
            list(peers) for peers in payload["neighbors"]  # type: ignore[union-attr]
        ]
        record = payload["record"]
        if not isinstance(record, StepRecord):
            raise TypeError("M10A collector received an invalid step record")

        components, labels = connected_components(neighbors, operational)
        observer_label = int(labels[0])
        if observer_label < 0 and components:
            observer_label = 0
        component_visible = np.zeros(self.config.n_agents, dtype=bool)
        if components and observer_label >= 0:
            component_visible[list(components[observer_label])] = True
        source_visible = component_visible & available & operational

        for arm, controller in self.controllers.items():
            result = controller.update(
                step,
                observations,
                covariances,
                component_visible=component_visible,
                available=available,
                operational=operational,
                raw_trusted=raw_trusted,
                source_quarantined=quarantined,
                belief_share_eligible=belief_share_eligible,
                belief_admitted=admitted,
            )
            decision = result.posterior
            all_errors = np.asarray(
                [
                    float(np.linalg.norm(mode.state[:2] - truth[:2]))
                    for mode in decision.modes
                ],
                dtype=float,
            )
            credible_errors = np.asarray(
                [
                    float(np.linalg.norm(mode.state[:2] - truth[:2]))
                    for mode in decision.credible_modes
                ],
                dtype=float,
            )
            truth_mode = decision.credible_modes[int(np.argmin(credible_errors))]
            best_error = float(np.min(credible_errors))
            team_error = float(np.linalg.norm(decision.state[:2] - truth[:2]))
            base_error = best_error if decision.action == "defer" else team_error
            loss = base_error + (
                self.config.output_defer_cost
                if decision.action == "defer"
                else 0.0
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
            alerts = (
                result.trust_scores
                < controller.trust_config.trust_alert_threshold
            )
            strategic_visible = source_visible & self.strategic_sources
            nonstrategic_visible = source_visible & ~self.strategic_sources
            self.rows[arm].append(
                {
                    "decision_loss": loss,
                    "team_error": team_error,
                    "best_error": best_error,
                    "action": decision.action,
                    "wrong": wrong,
                    "nees": nees,
                    "coverage95": nees <= 5.991,
                    "residual_mass": decision.residual_mass,
                    "cross_agents": result.cross_channel_disagreement_agents,
                    "strong_floor_agents": result.strong_floor_evidence_agents,
                    "ramp_agents": result.ramp_alert_agents,
                    "capped_agents": result.influence_capped_agents,
                    "trust_alert_agents": result.trust_alert_agents,
                    "mean_trust": result.mean_raw_trust,
                    "minimum_trust": result.minimum_raw_trust,
                    "raw_precision_fraction": result.raw_only_precision_fraction,
                    "trust_residual_mass": result.trust_residual_mass,
                    "strategic_alerted": int(np.sum(alerts & strategic_visible)),
                    "strategic_visible": int(np.sum(strategic_visible)),
                    "nonstrategic_alerted": int(
                        np.sum(alerts & nonstrategic_visible)
                    ),
                    "nonstrategic_visible": int(np.sum(nonstrategic_visible)),
                    "quarantined_agents": record.quarantined_agents,
                    "mean_sensor_speed": record.mean_sensor_speed,
                    "shadow_loss_difference": (
                        abs(loss - record.output_decision_loss)
                        if arm == M10A_BASELINE
                        else 0.0
                    ),
                    "shadow_action_difference": (
                        int(decision.action != record.output_action)
                        if arm == M10A_BASELINE
                        else 0
                    ),
                }
            )

    def summaries(self) -> dict[str, dict[str, float]]:
        summaries: dict[str, dict[str, float]] = {}
        for arm, rows in self.rows.items():
            if not rows:
                raise ValueError("cannot summarize an empty M10A trace")

            def mean(name: str) -> float:
                return float(np.mean([float(row[name]) for row in rows]))

            strategic_visible = sum(int(row["strategic_visible"]) for row in rows)
            nonstrategic_visible = sum(
                int(row["nonstrategic_visible"]) for row in rows
            )
            nees = np.asarray([float(row["nees"]) for row in rows], dtype=float)
            summaries[arm] = {
                "decision_loss": mean("decision_loss"),
                "position_rmse": math.sqrt(
                    float(np.mean([float(row["team_error"]) ** 2 for row in rows]))
                ),
                "best_hypothesis_rmse": math.sqrt(
                    float(np.mean([float(row["best_error"]) ** 2 for row in rows]))
                ),
                "selection_rate": float(
                    np.mean([row["action"] == "select" for row in rows])
                ),
                "mixture_rate": float(
                    np.mean([row["action"] == "mixture" for row in rows])
                ),
                "abstention_rate": float(
                    np.mean([row["action"] == "defer" for row in rows])
                ),
                "wrong_mode_action_rate": mean("wrong"),
                "mean_nees": float(np.mean(nees)),
                "p95_nees": float(np.quantile(nees, 0.95)),
                "coverage95_rate": mean("coverage95"),
                "mean_residual_mass": mean("residual_mass"),
                "cross_diagnostic_rate": float(
                    np.mean([int(row["cross_agents"]) > 0 for row in rows])
                ),
                "strong_floor_rate": float(
                    np.mean([int(row["strong_floor_agents"]) > 0 for row in rows])
                ),
                "ramp_diagnostic_rate": float(
                    np.mean([int(row["ramp_agents"]) > 0 for row in rows])
                ),
                "influence_cap_rate": float(
                    np.mean([int(row["capped_agents"]) > 0 for row in rows])
                ),
                "trust_alert_rate": float(
                    np.mean([int(row["trust_alert_agents"]) > 0 for row in rows])
                ),
                "mean_raw_trust": mean("mean_trust"),
                "minimum_raw_trust": float(
                    np.min([float(row["minimum_trust"]) for row in rows])
                ),
                "mean_raw_only_precision_fraction": mean(
                    "raw_precision_fraction"
                ),
                "mean_trust_residual_mass": mean("trust_residual_mass"),
                "strategic_alert_rate": (
                    sum(int(row["strategic_alerted"]) for row in rows)
                    / strategic_visible
                    if strategic_visible
                    else 0.0
                ),
                "nonstrategic_alert_rate": (
                    sum(int(row["nonstrategic_alerted"]) for row in rows)
                    / nonstrategic_visible
                    if nonstrategic_visible
                    else 0.0
                ),
                "quarantine_rate": float(
                    np.mean([int(row["quarantined_agents"]) > 0 for row in rows])
                ),
                "mean_sensor_speed": mean("mean_sensor_speed"),
                "shadow_max_decision_loss_difference": float(
                    np.max(
                        [float(row["shadow_loss_difference"]) for row in rows]
                    )
                ),
                "shadow_action_difference_rate": mean(
                    "shadow_action_difference"
                ),
            }
        return summaries


def _scenario_config(
    base_config: ExperimentConfig,
    scenario: ScenarioDefinition,
) -> ExperimentConfig:
    overrides = _fit_timing(scenario.overrides, base_config.steps)
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


def _worker(
    task: tuple[str, dict[str, object], int, dict[str, object]],
) -> list[dict[str, object]]:
    scenario_name, config_data, seed, trust_data = task
    config = ExperimentConfig(**config_data)
    scenario = make_scenario(config, seed)
    trust_config = AdversarialTrustConfig(**trust_data)
    collector = TrustAssayCollector(
        config,
        scenario.agent_fault_types == 4,
        trust_config,
    )
    started = perf_counter()
    run_trial(
        config,
        M9C_RECEDING_ALGORITHM,
        seed,
        step_observer=collector,
    )
    runtime = perf_counter() - started
    # M14.3: rows and the trace manifest must agree on the algorithm, otherwise
    # a fresh run's own reanalysis compares v1 against v2 and self-invalidates.
    fingerprint = scenario_fingerprint(
        config, seed, algorithm=CURRENT_FINGERPRINT_ALGORITHM
    )
    rows: list[dict[str, object]] = []
    for arm, summary in collector.summaries().items():
        rows.append(
            {
                "scenario": scenario_name,
                "seed": seed,
                "arm": arm,
                **summary,
                "runtime_seconds": runtime,
                "trace_fingerprint": fingerprint,
            }
        )
    return rows


SUMMARY_METRICS = (
    "decision_loss",
    "position_rmse",
    "best_hypothesis_rmse",
    "selection_rate",
    "mixture_rate",
    "abstention_rate",
    "wrong_mode_action_rate",
    "mean_nees",
    "p95_nees",
    "coverage95_rate",
    "mean_residual_mass",
    "cross_diagnostic_rate",
    "strong_floor_rate",
    "ramp_diagnostic_rate",
    "influence_cap_rate",
    "trust_alert_rate",
    "mean_raw_trust",
    "minimum_raw_trust",
    "mean_raw_only_precision_fraction",
    "mean_trust_residual_mass",
    "strategic_alert_rate",
    "nonstrategic_alert_rate",
    "quarantine_rate",
    "mean_sensor_speed",
    "shadow_max_decision_loss_difference",
    "shadow_action_difference_rate",
    "runtime_seconds",
)


def _scenario_summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, object]]] = {}
    for row in rows:
        groups.setdefault((str(row["scenario"]), str(row["arm"])), []).append(row)
    output: list[dict[str, object]] = []
    for (scenario, arm), group in groups.items():
        item: dict[str, object] = {
            "scenario": scenario,
            "arm": arm,
            "runs": len(group),
        }
        for metric in SUMMARY_METRICS:
            values = np.asarray([float(row[metric]) for row in group], dtype=float)
            item[f"{metric}_mean"] = float(np.mean(values))
            item[f"{metric}_std"] = float(np.std(values))
        output.append(item)
    return output


def _effects(
    rows: list[dict[str, object]],
    bootstrap_samples: int,
) -> list[dict[str, object]]:
    rng = np.random.default_rng(20260801)
    output: list[dict[str, object]] = []
    comparisons = (
        (M10A_COMBINED, M10A_BASELINE),
        (M10A_COMBINED, M10A_CROSS),
        (M10A_COMBINED, M10A_RAMP),
        (M10A_COMBINED, M10A_INFLUENCE),
    )
    for scenario in M10A_SCENARIOS:
        scoped = [
            row for row in rows if str(row["scenario"]) == scenario.name
        ]
        for candidate, baseline in comparisons:
            candidate_rows = {
                int(row["seed"]): row
                for row in scoped
                if str(row["arm"]) == candidate
            }
            baseline_rows = {
                int(row["seed"]): row
                for row in scoped
                if str(row["arm"]) == baseline
            }
            seeds = sorted(set(candidate_rows) & set(baseline_rows))
            baseline_values = np.asarray(
                [float(baseline_rows[seed]["decision_loss"]) for seed in seeds]
            )
            candidate_values = np.asarray(
                [float(candidate_rows[seed]["decision_loss"]) for seed in seeds]
            )
            improvement = baseline_values - candidate_values
            lower, upper = _bootstrap_interval(
                improvement, bootstrap_samples, rng
            )
            output.append(
                {
                    "scenario": scenario.name,
                    "candidate": candidate,
                    "baseline": baseline,
                    "metric": "decision_loss",
                    "pairs": len(seeds),
                    "baseline_mean": float(np.mean(baseline_values)),
                    "candidate_mean": float(np.mean(candidate_values)),
                    "improvement_mean": float(np.mean(improvement)),
                    "ci95_lower": lower,
                    "ci95_upper": upper,
                }
            )
    return output


def _verify_upstream(project_root: Path) -> tuple[bool, dict[str, object]]:
    output = project_root / "results/milestone9c_heldout"
    decision = json.loads((output / "decision.json").read_text(encoding="utf-8"))
    suite = json.loads((output / "suite_config.json").read_text(encoding="utf-8"))
    source = project_root / "src/flockkalman"
    current_source = _artifact_hash(
        (
            source / "integrated_sensing.py",
            source / "integration_suite.py",
            source / "experiment.py",
            source / "config.py",
            source / "metrics.py",
        )
    )
    current_protocol = _artifact_hash((project_root / "M9C_PROTOCOL.md",))
    verified = (
        decision.get("verdict") == "M9C-PARTIAL-GO"
        and bool(dict(decision.get("gates", {})).get("replay"))
        and current_source == suite.get("candidate_source_sha256")
        and current_protocol == suite.get("protocol_sha256")
    )
    return verified, {
        "verdict": decision.get("verdict"),
        "replay": dict(decision.get("gates", {})).get("replay"),
        "recorded_source_sha256": suite.get("candidate_source_sha256"),
        "current_source_sha256": current_source,
        "recorded_protocol_sha256": suite.get("protocol_sha256"),
        "current_protocol_sha256": current_protocol,
    }


def _decision(
    rows: list[dict[str, object]],
    summaries: list[dict[str, object]],
    effects: list[dict[str, object]],
    *,
    base_config: ExperimentConfig,
    phase: str,
    seed_count: int,
    replay: ReplayVerification,
    upstream_verified: bool,
) -> dict[str, object]:
    threshold = M10A_THRESHOLDS
    summary = {
        (str(row["scenario"]), str(row["arm"])): row for row in summaries
    }
    effect = {
        (str(row["scenario"]), str(row["candidate"]), str(row["baseline"])): row
        for row in effects
    }
    controls = [
        summary[(scenario.name, M10A_COMBINED)]
        for scenario in M10A_CONTROL_SCENARIOS
    ]
    attacks = [
        summary[(scenario.name, M10A_COMBINED)]
        for scenario in M10A_ATTACK_SCENARIOS
    ]
    availability_limit = (
        float(threshold["availability_loss_multiplier"])
        * base_config.output_defer_cost
    )
    minimum_powered_seeds = required_tail_seeds(
        float(threshold["tail_event_frequency"]),
        float(threshold["tail_detection_probability"]),
    )
    shadow_loss_difference = max(
        float(
            summary[(scenario.name, M10A_BASELINE)][
                "shadow_max_decision_loss_difference_mean"
            ]
        )
        for scenario in M10A_SCENARIOS
    )
    shadow_action_difference = max(
        float(
            summary[(scenario.name, M10A_BASELINE)][
                "shadow_action_difference_rate_mean"
            ]
        )
        for scenario in M10A_SCENARIOS
    )
    motion_spreads = []
    for scenario in M10A_SCENARIOS:
        values = [
            float(summary[(scenario.name, arm)]["mean_sensor_speed_mean"])
            for arm in M10A_ARMS
        ]
        motion_spreads.append(max(values) - min(values))
    natural_bounds = [
        float(
            effect[(scenario.name, M10A_COMBINED, M10A_BASELINE)][
                "ci95_lower"
            ]
        )
        for scenario in M10A_CONTROL_SCENARIOS
    ]
    canonical_effect = effect[
        (M9A7_ATTACK.name, M10A_COMBINED, M10A_BASELINE)
    ]
    detection_rates = {
        scenario.name: float(
            summary[(scenario.name, M10A_COMBINED)][
                "strategic_alert_rate_mean"
            ]
        )
        for scenario in M10A_ATTACK_SCENARIOS
    }
    dose_losses = [
        float(summary[(scenario.name, M10A_COMBINED)]["decision_loss_mean"])
        for scenario in (
            M10A_ATTACK_MILD,
            M10A_ATTACK_MODERATE,
            M10A_ATTACK_SEVERE,
        )
    ]
    gates = {
        "replay": replay.verified,
        "upstream_m9c_frozen": upstream_verified,
        "shadow_equivalence": (
            shadow_loss_difference <= float(threshold["shadow_tolerance"])
            and shadow_action_difference <= float(threshold["shadow_tolerance"])
        ),
        "frozen_motion": max(motion_spreads) <= float(
            threshold["motion_tolerance"]
        ),
        "tail_event_power": phase == "training" or seed_count >= minimum_powered_seeds,
        "diagnostics_exercised": all(
            detection_rates[scenario.name] >= 0.25
            for scenario in (
                M10A_ATTACK_MODERATE,
                M10A_ATTACK_SEVERE,
                M9A7_ATTACK,
            )
        ),
        "control_noninferiority": min(natural_bounds)
        >= float(threshold["control_noninferiority_lcb_min"]),
        "control_false_alerts": all(
            float(row["nonstrategic_alert_rate_mean"])
            <= float(threshold["control_false_alert_rate_max"])
            for row in controls
        ),
        "control_calibration_and_safety": all(
            float(row["wrong_mode_action_rate_mean"])
            <= float(threshold["wrong_mode_action_rate_max"])
            and float(row["mean_nees_mean"]) <= float(threshold["mean_nees_max"])
            and float(row["p95_nees_mean"]) <= float(threshold["p95_nees_max"])
            and float(row["coverage95_rate_mean"])
            >= float(threshold["coverage95_min"])
            for row in controls
        ),
        "legitimate_mode_and_precision": all(
            float(
                effect[(name, M10A_COMBINED, M10A_BASELINE)]["ci95_lower"]
            )
            >= float(threshold["control_noninferiority_lcb_min"])
            for name in (
                M9A7_POSITIVE_CONTROL.name,
                M9C_SOURCE_COMPETITION.name,
                M10A_HETEROGENEOUS_PRECISION.name,
            )
        ),
        "attack_absolute_availability": all(
            float(row["decision_loss_mean"]) <= availability_limit
            for row in attacks
        ),
        "canonical_attack_improvement": float(canonical_effect["ci95_lower"])
        > float(threshold["canonical_improvement_lcb_min"]),
        "attack_calibration_and_safety": all(
            float(row["wrong_mode_action_rate_mean"])
            <= float(threshold["wrong_mode_action_rate_max"])
            and float(row["mean_nees_mean"]) <= float(threshold["mean_nees_max"])
            and float(row["p95_nees_mean"]) <= float(threshold["p95_nees_max"])
            and float(row["coverage95_rate_mean"])
            >= float(threshold["coverage95_min"])
            for row in attacks
        ),
        "quarantine_noninterference": all(
            abs(
                float(
                    summary[(scenario.name, M10A_COMBINED)][
                        "quarantine_rate_mean"
                    ]
                )
                - float(
                    summary[(scenario.name, M10A_BASELINE)][
                        "quarantine_rate_mean"
                    ]
                )
            )
            <= 1e-12
            for scenario in M10A_SCENARIOS
        ),
        "attack_detection": (
            detection_rates[M10A_ATTACK_MILD.name]
            >= float(threshold["attack_detection_rate_mild_min"])
            and all(
                detection_rates[scenario.name]
                >= float(threshold["attack_detection_rate_other_min"])
                for scenario in (
                    M10A_ATTACK_MODERATE,
                    M10A_ATTACK_SEVERE,
                    M9A7_ATTACK,
                )
            )
        ),
        "dose_response_graceful": (
            max(
                dose_losses[index + 1] - dose_losses[index]
                for index in range(len(dose_losses) - 1)
            )
            <= float(threshold["dose_adjacent_loss_increase_max"])
            and max(dose_losses) <= availability_limit
        ),
    }
    validity = {
        "replay",
        "upstream_m9c_frozen",
        "shadow_equivalence",
        "frozen_motion",
        "tail_event_power",
        "diagnostics_exercised",
    }
    # M14.3: the `replay` gate is adjudicated separately from the other validity
    # gates. An unexplained fingerprint mismatch still invalidates; a mismatch
    # that the recorded environment accounts for is reported as its own verdict
    # class rather than being collapsed into INVALID (which is what made two
    # held-out GOs read as integrity failures under a referee's NumPy) or
    # silently promoted to GO (which would overclaim bit-exact verification).
    other_validity = validity - {"replay"}
    substantive = {name: value for name, value in gates.items() if name != "replay"}
    if replay.blocks_promotion or not all(gates[name] for name in other_validity):
        verdict = "M10A-INVALID"
    elif not all(substantive.values()):
        verdict = "M10A-TRAINING-FAIL" if phase == "training" else "M10A-NO-GO"
    elif not replay.verified:
        verdict = "M10A-REPLAY-ENV-MISMATCH"
    else:
        verdict = "M10A-TRAINING-PASS" if phase == "training" else "M10A-GO"
    return {
        "verdict": verdict,
        "phase": phase,
        "gates": gates,
        "replay_verification": replay.to_dict(),
        "environment": environment_fingerprint(),
        "thresholds": threshold,
        "availability_loss_derivation": {
            "formula": "2 * output_defer_cost",
            "output_defer_cost": base_config.output_defer_cost,
            "absolute_limit": availability_limit,
        },
        "power_calculation": {
            "event_frequency": threshold["tail_event_frequency"],
            "detection_probability": threshold["tail_detection_probability"],
            "minimum_seed_count": minimum_powered_seeds,
            "actual_seed_count": seed_count,
        },
        "worst_control_noninferiority_lcb": min(natural_bounds),
        "maximum_control_false_alert_rate": max(
            float(row["nonstrategic_alert_rate_mean"]) for row in controls
        ),
        "canonical_attack_improvement": float(
            canonical_effect["improvement_mean"]
        ),
        "canonical_attack_ci95": [
            float(canonical_effect["ci95_lower"]),
            float(canonical_effect["ci95_upper"]),
        ],
        "attack_decision_losses": {
            scenario.name: float(
                summary[(scenario.name, M10A_COMBINED)]["decision_loss_mean"]
            )
            for scenario in M10A_ATTACK_SCENARIOS
        },
        "attack_detection_rates": detection_rates,
        "shadow_max_decision_loss_difference": shadow_loss_difference,
        "shadow_action_difference_rate": shadow_action_difference,
        "maximum_motion_difference": max(motion_spreads),
        "production_authorized": False,
        "closed_loop_integration_authorized": verdict == "M10A-GO",
        "m9_verdicts_unchanged": True,
    }


def _write_report(
    path: Path,
    decision: dict[str, object],
    summaries: list[dict[str, object]],
    effects: list[dict[str, object]],
    seed_start: int,
    seed_count: int,
) -> None:
    summary = {
        (str(row["scenario"]), str(row["arm"])): row for row in summaries
    }
    effect = {
        (str(row["scenario"]), str(row["candidate"]), str(row["baseline"])): row
        for row in effects
    }
    lines = [
        "# M10A raw-channel adversarial-trust report",
        "",
        f"**Verdict: `{decision['verdict']}`**",
        "",
        f"Phase: `{decision['phase']}`. Seeds: `{seed_start}`–`{seed_start + seed_count - 1}` ({seed_count} paired seeds per scenario).",
        "",
        "Every arm is an output-layer shadow on the same frozen M9C physical trajectory. Fault identity and truth are used only after each causal decision for scoring.",
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
            "## Combined candidate",
            "",
            "| Scenario | Loss | Abstain | Wrong | NEES | P95 NEES | Coverage | Strategic alert | False alert |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for scenario in M10A_SCENARIOS:
        row = summary[(scenario.name, M10A_COMBINED)]
        lines.append(
            f"| {scenario.name} | {float(row['decision_loss_mean']):.3f} | "
            f"{float(row['abstention_rate_mean']):.3f} | "
            f"{float(row['wrong_mode_action_rate_mean']):.3f} | "
            f"{float(row['mean_nees_mean']):.2f} | "
            f"{float(row['p95_nees_mean']):.2f} | "
            f"{float(row['coverage95_rate_mean']):.3f} | "
            f"{float(row['strategic_alert_rate_mean']):.3f} | "
            f"{float(row['nonstrategic_alert_rate_mean']):.3f} |"
        )
    lines.extend(
        [
            "",
            "## Decision-loss effects versus frozen M9C",
            "",
            "| Scenario | Improvement | 95% CI |",
            "|---|---:|---:|",
        ]
    )
    for scenario in M10A_SCENARIOS:
        row = effect[(scenario.name, M10A_COMBINED, M10A_BASELINE)]
        lines.append(
            f"| {scenario.name} | {float(row['improvement_mean']):.4f} | "
            f"[{float(row['ci95_lower']):.4f}, {float(row['ci95_upper']):.4f}] |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "A GO authorizes closed-loop research integration only. The assay does not establish robustness to adaptive attacks, production security, or external validity.",
            "",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_rows(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def run_adversarial_trust_suite(
    base_config: ExperimentConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 40,
    seed_start: int = 20000,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
    phase: str = "training",
    trust_config: AdversarialTrustConfig | None = None,
) -> dict[str, object]:
    """Run the frozen M10A paired trust-layer protocol."""
    base_config.validate()
    if phase not in {"training", "heldout"}:
        raise ValueError("phase must be training or heldout")
    if seed_count < 2 or bootstrap_samples < 100:
        raise ValueError("M10A needs at least two seeds and 100 bootstrap samples")
    trust = trust_config or AdversarialTrustConfig()
    trust.validate()
    trust_data = asdict(trust)
    tasks: list[tuple[str, dict[str, object], int, dict[str, object]]] = []
    scenario_configs: dict[str, dict[str, object]] = {}
    manifest: list[dict[str, object]] = []
    for scenario in M10A_SCENARIOS:
        config = _scenario_config(base_config, scenario)
        config.validate()
        config_data = config.to_dict()
        scenario_configs[scenario.name] = config_data
        for seed in range(seed_start, seed_start + seed_count):
            tasks.append((scenario.name, config_data, seed, trust_data))
            manifest.append(
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
        groups = [_worker(task) for task in tasks]
    else:
        try:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                groups = list(executor.map(_worker, tasks, chunksize=2))
            executor_kind = "process"
        except (PermissionError, OSError):
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                groups = list(executor.map(_worker, tasks))
            executor_kind = "thread_fallback"
    rows = [row for group in groups for row in group]
    scenario_order = {item.name: index for index, item in enumerate(M10A_SCENARIOS)}
    arm_order = {item: index for index, item in enumerate(M10A_ARMS)}
    rows.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            arm_order[str(row["arm"])],
            int(row["seed"]),
        )
    )
    summaries = _scenario_summaries(rows)
    summaries.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            arm_order[str(row["arm"])],
        )
    )
    effects = _effects(rows, bootstrap_samples)
    # A fresh run is by construction in its own environment, so the manifest is
    # checked bit-exactly under the algorithm this run records.
    replay = verify_replay(
        [dict(entry) for entry in manifest],
        expected=lambda entry, algorithm: scenario_fingerprint(
            ExperimentConfig(**scenario_configs[str(entry["scenario"])]),
            int(entry["seed"]),
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
        base_config=base_config,
        phase=phase,
        seed_count=seed_count,
        replay=replay,
        upstream_verified=upstream_verified,
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
        + "\n",
        encoding="utf-8",
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
        "trust_config": trust_data,
        "scenarios": [asdict(item) for item in M10A_SCENARIOS],
        "scenario_configs": scenario_configs,
        "thresholds": M10A_THRESHOLDS,
        "protocol_sha256": _artifact_hash((project_root / "M10A_PROTOCOL.md",)),
        "candidate_source_sha256": _artifact_hash(
            (
                source / "adversarial_trust.py",
                source / "adversarial_trust_suite.py",
                # M14.4: the replay validity gate is derived from these modules,
                # so drift in them must invalidate the frozen set. Omitting
                # simulation.py is what let a fingerprint-affecting code path sit
                # outside the chain of custody it was supposed to be inside.
                source / "simulation.py",
                source / "config.py",
                source / "provenance.py",
            )
        ),
        "fingerprint_algorithm": CURRENT_FINGERPRINT_ALGORITHM,
        "upstream_m9c": upstream,
        "platform_version": "0.14.0",
        "python": platform.python_version(),
        "numpy": np.__version__,
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
        output / "milestone10a_report.md",
        decision,
        summaries,
        effects,
        seed_start,
        seed_count,
    )
    return decision


def reanalyze_adversarial_trust_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    """Regenerate M10A gates and trace verification from saved rows."""
    output = Path(output_directory)
    suite = json.loads((output / "suite_config.json").read_text(encoding="utf-8"))
    rows = _read_rows(output / "run_summary.csv")
    samples = int(bootstrap_samples or suite["bootstrap_samples"])
    summaries = _scenario_summaries(rows)
    scenario_order = {item.name: index for index, item in enumerate(M10A_SCENARIOS)}
    arm_order = {item: index for index, item in enumerate(M10A_ARMS)}
    summaries.sort(
        key=lambda row: (
            scenario_order[str(row["scenario"])],
            arm_order[str(row["arm"])],
        )
    )
    effects = _effects(rows, samples)
    replay = verify_scenario_replay(rows, suite)
    project_root = Path(__file__).resolve().parents[2]
    upstream_verified, _ = _verify_upstream(project_root)
    base_config = ExperimentConfig(**suite["base_config"])
    decision = _decision(
        rows,
        summaries,
        effects,
        base_config=base_config,
        phase=str(suite["phase"]),
        seed_count=int(suite["seed_count"]),
        replay=replay,
        upstream_verified=upstream_verified,
    )
    _write_csv(output / "scenario_summary.csv", summaries)
    _write_csv(output / "paired_effects.csv", effects)
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_report(
        output / "milestone10a_report.md",
        decision,
        summaries,
        effects,
        int(suite["seed_start"]),
        int(suite["seed_count"]),
    )
    return decision
