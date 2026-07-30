"""Metric definitions and aggregation."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Iterable

import numpy as np
from numpy.typing import NDArray

from .config import ExperimentConfig


FloatArray = NDArray[np.float64]


@dataclass(slots=True)
class StepRecord:
    seed: int
    algorithm: str
    step: int
    target_x: float
    target_y: float
    team_estimate_x: float
    team_estimate_y: float
    team_position_error: float
    best_hypothesis_position_error: float
    truth_consistent_flock_weight: float
    output_action: str
    output_confidence: float
    output_selected_flock_id: int
    output_decision_base_error: float
    output_decision_loss: float
    output_wrong_mode: bool
    mean_agent_squared_error: float
    mean_nees: float
    coverage95_rate: float
    mean_nis: float | None
    information_gain: float
    spatial_diversity: float
    estimate_disagreement: float
    mean_momentum: float
    momentum_classification: str
    momentum_change_score: float
    momentum_corroborating_agents: int
    momentum_biased_agents: int
    momentum_fallback_active: bool
    momentum_change_event: bool
    hypothesis_flock_count: int
    primary_flock_size: int
    primary_flock_weight: float
    alternative_flock_weight: float
    quarantined_agents: int
    suspected_bias_agents: int
    mean_bias_estimate_norm: float
    mean_sensor_speed: float
    operational_agents: int
    delivery_ratio: float
    mean_message_age: float
    topology_partition_active: bool
    topology_component_count: int
    topology_observer_component_size: int
    topology_visibility_fraction: float
    topology_live_support: float
    topology_retained_support: float
    topology_unknown_support: float
    topology_probation_agents: int
    topology_rejoin_events: int
    topology_merge_grace_active: bool
    topology_component_epoch: int
    topology_duplicate_support_suppressed: float
    topology_selection_blocked: bool
    missing_evidence_residual_mass: float
    missing_evidence_model_nis: float
    missing_evidence_assignment_entropy: float
    missing_evidence_predicted_risk: float
    missing_evidence_predicted_wrong_risk: float
    missing_evidence_credible_modes: int
    measurement_eligible_agents: int
    belief_admitted_agents: int
    belief_censored_measurement_agents: int
    robust_excluded_measurement_agents: int
    unreachable_measurement_agents: int
    measurement_covariance_floored_agents: int
    model_rejected_measurement_agents: int
    admission_missingness_mass: float
    excluded_secondary_probability: float
    unreachable_secondary_probability: float
    investigation_allocator: str
    investigation_motion_action: str
    investigation_requested: bool
    investigation_residual_guarded: bool
    investigation_replanned: bool
    investigation_planning_sequences: int
    investigation_expected_risk: float
    investigation_predicted_movement_cost: float
    investigation_active_agents: int
    investigation_mode_count: int
    messages: int
    bytes_sent: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def mean_pairwise_distance(points: FloatArray) -> float:
    distances: list[float] = []
    for first in range(len(points)):
        for second in range(first + 1, len(points)):
            distances.append(float(np.linalg.norm(points[first] - points[second])))
    return float(np.mean(distances)) if distances else 0.0


def agent_calibration(
    estimates: FloatArray, covariances: list[FloatArray], truth_position: FloatArray
) -> tuple[float, float]:
    nees_values: list[float] = []
    covered = 0
    for estimate, covariance in zip(estimates, covariances):
        error = estimate - truth_position
        nees = float(error @ np.linalg.solve(covariance, error))
        nees_values.append(nees)
        covered += int(nees <= 5.991)  # 95% chi-square threshold with 2 degrees of freedom.
    return float(np.mean(nees_values)), covered / len(nees_values)


def expected_information_gain(
    measurement_covariances: list[FloatArray], reference_variance: float
) -> float:
    if not measurement_covariances:
        return 0.0
    reference = np.eye(2, dtype=float) * reference_variance
    gains = []
    for covariance in measurement_covariances:
        sign, log_determinant = np.linalg.slogdet(
            np.eye(2, dtype=float) + reference @ np.linalg.inv(covariance)
        )
        gains.append(0.5 * log_determinant if sign > 0 else 0.0)
    return float(np.mean(gains))


def recovery_delay(config: ExperimentConfig, records: list[StepRecord]) -> int | None:
    if config.target_change_mode == "none":
        return None
    errors = np.asarray([record.team_position_error for record in records], dtype=float)
    start = max(0, config.change_step - 12)
    baseline = float(np.median(errors[start : config.change_step]))
    threshold = max(config.recovery_error_floor, config.recovery_multiplier * baseline)
    post_change = errors[config.change_step :]
    if not np.any(post_change > threshold):
        return 0
    for offset in range(1, len(post_change) - config.recovery_window + 1):
        window = post_change[offset : offset + config.recovery_window]
        if len(window) == config.recovery_window and np.all(window <= threshold):
            return offset
    return len(post_change)


def ambiguity_resolution_delay(
    config: ExperimentConfig,
    records: list[StepRecord],
) -> int | None:
    ambiguous = [
        index for index, record in enumerate(records) if record.hypothesis_flock_count > 1
    ]
    if not ambiguous:
        return None
    start = ambiguous[0]
    persistence = config.output_resolution_persistence_steps
    for index in range(start + 1, len(records) - persistence + 1):
        if all(
            record.hypothesis_flock_count == 1
            for record in records[index : index + persistence]
        ):
            return index - start
    return len(records) - start


def summarize_run(config: ExperimentConfig, records: list[StepRecord]) -> dict[str, object]:
    if not records:
        raise ValueError("cannot summarize an empty run")
    nis_values = [record.mean_nis for record in records if record.mean_nis is not None]
    ambiguous_selections = [
        record
        for record in records
        if record.hypothesis_flock_count > 1 and record.output_action == "select"
    ]
    rejoin_records = [
        record
        for record in records
        if record.topology_probation_agents > 0 or record.topology_rejoin_events > 0
    ]
    primary_support_jumps = [
        abs(current.primary_flock_weight - previous.primary_flock_weight)
        for previous, current in zip(records, records[1:])
        if current.topology_rejoin_events > 0
        or current.topology_probation_agents > 0
        or current.topology_component_count < previous.topology_component_count
    ]
    partition_records = [record for record in records if record.topology_partition_active]
    return {
        "algorithm": records[0].algorithm,
        "seed": records[0].seed,
        "position_rmse": math.sqrt(
            float(np.mean([record.team_position_error**2 for record in records]))
        ),
        "best_hypothesis_rmse": math.sqrt(
            float(
                np.mean(
                    [record.best_hypothesis_position_error**2 for record in records]
                )
            )
        ),
        "mean_truth_consistent_flock_weight": float(
            np.mean([record.truth_consistent_flock_weight for record in records])
        ),
        "decision_loss": float(
            np.mean([record.output_decision_loss for record in records])
        ),
        "mean_decision_base_error": float(
            np.mean([record.output_decision_base_error for record in records])
        ),
        "selection_rate": float(
            np.mean([record.output_action == "select" for record in records])
        ),
        "mixture_rate": float(
            np.mean([record.output_action == "mixture" for record in records])
        ),
        "abstention_rate": float(
            np.mean(
                [record.output_action in {"defer", "investigate"} for record in records]
            )
        ),
        "investigation_rate": float(
            np.mean([record.output_action == "investigate" for record in records])
        ),
        "wrong_mode_rate": (
            float(np.mean([record.output_wrong_mode for record in ambiguous_selections]))
            if ambiguous_selections
            else 0.0
        ),
        "wrong_mode_action_rate": float(
            np.mean([record.output_wrong_mode for record in records])
        ),
        "mean_output_confidence": float(
            np.mean([record.output_confidence for record in records])
        ),
        "ambiguity_resolution_steps": ambiguity_resolution_delay(config, records),
        "agent_position_rmse": math.sqrt(
            float(np.mean([record.mean_agent_squared_error for record in records]))
        ),
        "mean_nees": float(np.mean([record.mean_nees for record in records])),
        "p95_nees": float(np.quantile([record.mean_nees for record in records], 0.95)),
        "max_nees": float(np.max([record.mean_nees for record in records])),
        "coverage95_rate": float(np.mean([record.coverage95_rate for record in records])),
        "rejoin_window_nees": (
            float(np.mean([record.mean_nees for record in rejoin_records]))
            if rejoin_records
            else 0.0
        ),
        "mean_nis": float(np.mean(nis_values)) if nis_values else None,
        "information_gain": float(np.mean([record.information_gain for record in records])),
        "spatial_diversity": float(np.mean([record.spatial_diversity for record in records])),
        "estimate_disagreement": float(
            np.mean([record.estimate_disagreement for record in records])
        ),
        "mean_operational_agents": float(
            np.mean([record.operational_agents for record in records])
        ),
        "mean_delivery_ratio": float(
            np.mean([record.delivery_ratio for record in records])
        ),
        "mean_message_age": float(
            np.mean([record.mean_message_age for record in records])
        ),
        "partition_active_rate": float(
            np.mean([record.topology_partition_active for record in records])
        ),
        "partition_selection_rate": (
            float(np.mean([record.output_action == "select" for record in partition_records]))
            if partition_records
            else 0.0
        ),
        "mean_topology_components": float(
            np.mean([record.topology_component_count for record in records])
        ),
        "mean_observer_component_size": float(
            np.mean([record.topology_observer_component_size for record in records])
        ),
        "mean_topology_visibility_fraction": float(
            np.mean([record.topology_visibility_fraction for record in records])
        ),
        "mean_topology_live_support": float(
            np.mean([record.topology_live_support for record in records])
        ),
        "mean_topology_retained_support": float(
            np.mean([record.topology_retained_support for record in records])
        ),
        "mean_topology_unknown_support": float(
            np.mean([record.topology_unknown_support for record in records])
        ),
        "mean_topology_probation_agents": float(
            np.mean([record.topology_probation_agents for record in records])
        ),
        "topology_rejoin_events": int(
            sum(record.topology_rejoin_events for record in records)
        ),
        "topology_merge_grace_rate": float(
            np.mean([record.topology_merge_grace_active for record in records])
        ),
        "topology_epoch_changes": int(
            max(record.topology_component_epoch for record in records)
        ),
        "mean_duplicate_support_suppressed": float(
            np.mean(
                [record.topology_duplicate_support_suppressed for record in records]
            )
        ),
        "topology_selection_blocked_rate": float(
            np.mean([record.topology_selection_blocked for record in records])
        ),
        "mean_missing_evidence_residual_mass": float(
            np.mean([record.missing_evidence_residual_mass for record in records])
        ),
        "mean_missing_evidence_model_nis": float(
            np.mean([record.missing_evidence_model_nis for record in records])
        ),
        "mean_missing_evidence_assignment_entropy": float(
            np.mean(
                [record.missing_evidence_assignment_entropy for record in records]
            )
        ),
        "mean_missing_evidence_predicted_risk": float(
            np.mean([record.missing_evidence_predicted_risk for record in records])
        ),
        "mean_missing_evidence_predicted_wrong_risk": float(
            np.mean(
                [record.missing_evidence_predicted_wrong_risk for record in records]
            )
        ),
        "mean_missing_evidence_credible_modes": float(
            np.mean([record.missing_evidence_credible_modes for record in records])
        ),
        "mean_measurement_eligible_agents": float(
            np.mean([record.measurement_eligible_agents for record in records])
        ),
        "mean_belief_admitted_agents": float(
            np.mean([record.belief_admitted_agents for record in records])
        ),
        "mean_belief_censored_measurement_agents": float(
            np.mean(
                [record.belief_censored_measurement_agents for record in records]
            )
        ),
        "belief_censoring_rate": float(
            np.mean(
                [record.belief_censored_measurement_agents > 0 for record in records]
            )
        ),
        "mean_robust_excluded_measurement_agents": float(
            np.mean(
                [record.robust_excluded_measurement_agents for record in records]
            )
        ),
        "mean_unreachable_measurement_agents": float(
            np.mean([record.unreachable_measurement_agents for record in records])
        ),
        "mean_measurement_covariance_floored_agents": float(
            np.mean(
                [record.measurement_covariance_floored_agents for record in records]
            )
        ),
        "mean_model_rejected_measurement_agents": float(
            np.mean(
                [record.model_rejected_measurement_agents for record in records]
            )
        ),
        "mean_admission_missingness_mass": float(
            np.mean([record.admission_missingness_mass for record in records])
        ),
        "mean_excluded_secondary_probability": float(
            np.mean([record.excluded_secondary_probability for record in records])
        ),
        "mean_unreachable_secondary_probability": float(
            np.mean([record.unreachable_secondary_probability for record in records])
        ),
        "investigation_request_rate": float(
            np.mean([record.investigation_requested for record in records])
        ),
        "investigation_residual_guard_rate": float(
            np.mean([record.investigation_residual_guarded for record in records])
        ),
        "investigation_replan_rate": float(
            np.mean([record.investigation_replanned for record in records])
        ),
        "investigation_active_motion_rate": float(
            np.mean(
                [
                    record.investigation_motion_action not in {"inactive", "track"}
                    for record in records
                ]
            )
        ),
        "investigation_spread_rate": float(
            np.mean(
                [record.investigation_motion_action == "spread" for record in records]
            )
        ),
        "investigation_probe_rate": float(
            np.mean(
                [record.investigation_motion_action.startswith("probe_") for record in records]
            )
        ),
        "mean_investigation_active_agents": float(
            np.mean([record.investigation_active_agents for record in records])
        ),
        "mean_investigation_mode_count": float(
            np.mean([record.investigation_mode_count for record in records])
        ),
        "investigation_planning_sequences": int(
            sum(record.investigation_planning_sequences for record in records)
        ),
        "mean_investigation_predicted_movement_cost": float(
            np.mean(
                [record.investigation_predicted_movement_cost for record in records]
            )
        ),
        "max_primary_support_jump": max(primary_support_jumps, default=0.0),
        "recovery_steps": recovery_delay(config, records),
        "messages": int(sum(record.messages for record in records)),
        "bytes_sent": int(sum(record.bytes_sent for record in records)),
        "mean_momentum": float(np.mean([record.mean_momentum for record in records])),
        "mean_momentum_change_score": float(
            np.mean([record.momentum_change_score for record in records])
        ),
        "mean_momentum_corroborating_agents": float(
            np.mean([record.momentum_corroborating_agents for record in records])
        ),
        "mean_momentum_biased_agents": float(
            np.mean([record.momentum_biased_agents for record in records])
        ),
        "momentum_fallback_rate": float(
            np.mean([record.momentum_fallback_active for record in records])
        ),
        "momentum_change_events": int(
            sum(record.momentum_change_event for record in records)
        ),
        "mean_hypothesis_flocks": float(
            np.mean([record.hypothesis_flock_count for record in records])
        ),
        "multiflock_rate": float(
            np.mean([record.hypothesis_flock_count > 1 for record in records])
        ),
        "mean_primary_flock_size": float(
            np.mean([record.primary_flock_size for record in records])
        ),
        "mean_primary_flock_weight": float(
            np.mean([record.primary_flock_weight for record in records])
        ),
        "mean_alternative_flock_weight": float(
            np.mean([record.alternative_flock_weight for record in records])
        ),
        "mean_quarantined_agents": float(
            np.mean([record.quarantined_agents for record in records])
        ),
        "quarantine_rate": float(
            np.mean([record.quarantined_agents > 0 for record in records])
        ),
        "mean_suspected_bias_agents": float(
            np.mean([record.suspected_bias_agents for record in records])
        ),
        "mean_bias_estimate_norm": float(
            np.mean([record.mean_bias_estimate_norm for record in records])
        ),
        "movement_distance": float(
            sum(record.mean_sensor_speed * config.dt for record in records)
        ),
    }


def aggregate_runs(run_summaries: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for summary in run_summaries:
        grouped.setdefault(str(summary["algorithm"]), []).append(summary)
    rows: list[dict[str, object]] = []
    metric_names = [
        "position_rmse",
        "best_hypothesis_rmse",
        "mean_truth_consistent_flock_weight",
        "decision_loss",
        "mean_decision_base_error",
        "selection_rate",
        "mixture_rate",
        "abstention_rate",
        "investigation_rate",
        "wrong_mode_rate",
        "wrong_mode_action_rate",
        "mean_output_confidence",
        "ambiguity_resolution_steps",
        "agent_position_rmse",
        "mean_nees",
        "p95_nees",
        "max_nees",
        "coverage95_rate",
        "rejoin_window_nees",
        "mean_nis",
        "information_gain",
        "spatial_diversity",
        "estimate_disagreement",
        "mean_operational_agents",
        "mean_delivery_ratio",
        "mean_message_age",
        "partition_active_rate",
        "partition_selection_rate",
        "mean_topology_components",
        "mean_observer_component_size",
        "mean_topology_visibility_fraction",
        "mean_topology_live_support",
        "mean_topology_retained_support",
        "mean_topology_unknown_support",
        "mean_topology_probation_agents",
        "topology_rejoin_events",
        "topology_merge_grace_rate",
        "topology_epoch_changes",
        "mean_duplicate_support_suppressed",
        "topology_selection_blocked_rate",
        "mean_missing_evidence_residual_mass",
        "mean_missing_evidence_model_nis",
        "mean_missing_evidence_assignment_entropy",
        "mean_missing_evidence_predicted_risk",
        "mean_missing_evidence_predicted_wrong_risk",
        "mean_missing_evidence_credible_modes",
        "mean_measurement_eligible_agents",
        "mean_belief_admitted_agents",
        "mean_belief_censored_measurement_agents",
        "belief_censoring_rate",
        "mean_robust_excluded_measurement_agents",
        "mean_unreachable_measurement_agents",
        "mean_measurement_covariance_floored_agents",
        "mean_model_rejected_measurement_agents",
        "mean_admission_missingness_mass",
        "mean_excluded_secondary_probability",
        "mean_unreachable_secondary_probability",
        "max_primary_support_jump",
        "recovery_steps",
        "messages",
        "bytes_sent",
        "mean_momentum",
        "mean_momentum_change_score",
        "mean_momentum_corroborating_agents",
        "mean_momentum_biased_agents",
        "momentum_fallback_rate",
        "momentum_change_events",
        "mean_hypothesis_flocks",
        "multiflock_rate",
        "mean_primary_flock_size",
        "mean_primary_flock_weight",
        "mean_alternative_flock_weight",
        "mean_quarantined_agents",
        "quarantine_rate",
        "mean_suspected_bias_agents",
        "mean_bias_estimate_norm",
        "movement_distance",
        "runtime_seconds",
    ]
    for algorithm, summaries in grouped.items():
        row: dict[str, object] = {"algorithm": algorithm, "runs": len(summaries)}
        for metric in metric_names:
            values = [float(item[metric]) for item in summaries if item[metric] is not None]
            row[f"{metric}_mean"] = float(np.mean(values)) if values else None
            row[f"{metric}_std"] = float(np.std(values)) if values else None
        rows.append(row)
    return rows
