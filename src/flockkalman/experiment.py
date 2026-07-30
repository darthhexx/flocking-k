"""Experiment orchestration for all required algorithmic baselines."""

from __future__ import annotations

import csv
from functools import reduce
import json
import operator
import platform
from pathlib import Path
import sys
from time import perf_counter
from typing import Callable, Iterable

import numpy as np

from .admission_evidence import M9A7_ALGORITHM, AdmissionAwareController
from .config import ExperimentConfig
from .filters import (
    KalmanFilter,
    constant_velocity_matrices,
    fuse_neighbor_beliefs,
    fuse_team_belief,
    precision_fuse_positions,
)
from .integrated_sensing import (
    AssignmentEvidence,
    M9C_ALGORITHMS,
    M9C_RECEDING_ALGORITHM,
    M9C_ROUND_ROBIN_ALGORITHM,
    IntegratedInvestigationController,
)
from .metrics import (
    StepRecord,
    agent_calibration,
    aggregate_runs,
    expected_information_gain,
    mean_pairwise_distance,
    summarize_run,
)
from .missing_evidence import (
    M9A6_ALGORITHM,
    MissingEvidenceController,
)
from .output_policy import HypothesisOutputController, investigation_goals
from .policies import (
    GuardedMomentumController,
    adaptive_momentum,
    advance_sensors,
    direct_tracking_velocity,
    flocking_velocity,
    topological_neighbors,
)
from .reporting import write_comparison_svg, write_error_timeseries_svg
from .robust import BiasModeTracker, build_hypothesis_flocks, flock_membership
from .simulation import make_scenario, observe
from .topology import (
    AgentLifecycleManager,
    ComponentEpochTracker,
    HypothesisMemory,
    build_topology_flocks,
)


ALGORITHMS = (
    "independent_kf",
    "consensus_kf",
    "flocking_only",
    "flocking_kf_no_momentum",
    "flocking_fixed_momentum",
    "flocking_adaptive_momentum",
    "flocking_guarded_momentum",
    "flocking_robust_multiflock",
    "flocking_robust_temporal",
    "flocking_robust_mixture",
    "flocking_robust_defer",
    "flocking_robust_active_no_investigation",
    "flocking_robust_active",
    "flocking_topology_support",
    "flocking_topology_rejoin",
    "flocking_topology_partition",
    "flocking_topology_resilient",
    M9A6_ALGORITHM,
    M9A7_ALGORITHM,
    M9C_ROUND_ROBIN_ALGORITHM,
    M9C_RECEDING_ALGORITHM,
)

ROBUST_OUTPUT_POLICIES = {
    "flocking_robust_multiflock": "largest",
    "flocking_robust_temporal": "temporal",
    "flocking_robust_mixture": "mixture",
    "flocking_robust_defer": "defer",
    "flocking_robust_active_no_investigation": "active",
    "flocking_robust_active": "active",
    "flocking_topology_support": "active",
    "flocking_topology_rejoin": "active",
    "flocking_topology_partition": "active",
    "flocking_topology_resilient": "active",
    M9A6_ALGORITHM: "active",
    M9A7_ALGORITHM: "active",
    M9C_ROUND_ROBIN_ALGORITHM: "active",
    M9C_RECEDING_ALGORITHM: "active",
}
_ROBUST_ALGORITHMS = set(ROBUST_OUTPUT_POLICIES)
_TOPOLOGY_ALGORITHMS = {
    "flocking_topology_support",
    "flocking_topology_rejoin",
    "flocking_topology_partition",
    "flocking_topology_resilient",
    M9A6_ALGORITHM,
    M9A7_ALGORITHM,
    *M9C_ALGORITHMS,
}
_TOPOLOGY_LIFECYCLE_ALGORITHMS = {
    "flocking_topology_rejoin",
    "flocking_topology_partition",
    "flocking_topology_resilient",
    M9A6_ALGORITHM,
    M9A7_ALGORITHM,
    *M9C_ALGORITHMS,
}
_TOPOLOGY_COMPONENT_ALGORITHMS = {
    "flocking_topology_partition",
    "flocking_topology_resilient",
    M9A6_ALGORITHM,
    M9A7_ALGORITHM,
    *M9C_ALGORITHMS,
}

_KALMAN_ALGORITHMS = {
    "independent_kf",
    "consensus_kf",
    "flocking_kf_no_momentum",
    "flocking_fixed_momentum",
    "flocking_adaptive_momentum",
    "flocking_guarded_momentum",
} | _ROBUST_ALGORITHMS
_CONSENSUS_ALGORITHMS = {
    "consensus_kf",
    "flocking_kf_no_momentum",
    "flocking_fixed_momentum",
    "flocking_adaptive_momentum",
    "flocking_guarded_momentum",
} | _ROBUST_ALGORITHMS
_FLOCKING_ALGORITHMS = {
    "flocking_only",
    "flocking_kf_no_momentum",
    "flocking_fixed_momentum",
    "flocking_adaptive_momentum",
    "flocking_guarded_momentum",
} | _ROBUST_ALGORITHMS


def _validate_algorithms(algorithms: Iterable[str]) -> list[str]:
    requested = list(algorithms)
    unknown = sorted(set(requested) - set(ALGORITHMS))
    if unknown:
        raise ValueError(f"unknown algorithms: {', '.join(unknown)}")
    if not requested:
        raise ValueError("at least one algorithm is required")
    return requested


def _initial_filters(config: ExperimentConfig, truth: np.ndarray, offsets: np.ndarray) -> list[KalmanFilter]:
    filters: list[KalmanFilter] = []
    initial_covariance = np.diag(
        [
            config.initial_belief_position_std**2,
            config.initial_belief_position_std**2,
            config.initial_belief_velocity_std**2,
            config.initial_belief_velocity_std**2,
        ]
    )
    for offset in offsets:
        filters.append(
            KalmanFilter(
                state=truth.copy() + offset,
                covariance=initial_covariance.copy(),
                dt=config.dt,
                acceleration_variance=config.filter_process_variance,
            )
        )
    return filters


def _communication_cost(algorithm: str, edge_count: int) -> tuple[int, int]:
    if algorithm == "independent_kf":
        return 0, 0
    if algorithm == "consensus_kf":
        floats_per_message = 4 + 16
    elif algorithm == "flocking_only":
        floats_per_message = 2 + 2 + 2 + 2
    else:
        floats_per_message = 2 + 2 + 4 + 16
    return edge_count, edge_count * floats_per_message * 8


def _age_compensate_beliefs(
    config: ExperimentConfig,
    states: list[np.ndarray],
    covariances: list[np.ndarray],
    age: int,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Propagate delayed peer beliefs to the current cycle before fusion."""
    if age <= 0:
        return states, covariances
    transition, process = constant_velocity_matrices(
        config.dt,
        config.filter_process_variance,
    )
    propagated_states = [state.copy() for state in states]
    propagated_covariances = [covariance.copy() for covariance in covariances]
    for _ in range(age):
        propagated_states = [transition @ state for state in propagated_states]
        next_covariances: list[np.ndarray] = []
        for covariance in propagated_covariances:
            predicted = transition @ covariance @ transition.T + process
            next_covariances.append(0.5 * (predicted + predicted.T))
        propagated_covariances = next_covariances
    return propagated_states, propagated_covariances


def _partition_active(config: ExperimentConfig, step: int) -> bool:
    if config.topology_partition_step < 0 or step < config.topology_partition_step:
        return False
    offset = step - config.topology_partition_step
    if config.topology_partition_repeat_interval <= 0:
        return offset < config.topology_partition_duration
    event = offset // config.topology_partition_repeat_interval
    phase = offset % config.topology_partition_repeat_interval
    return (
        event < config.topology_partition_repeat_count
        and phase < config.topology_partition_duration
    )


def _same_partition(
    first: int,
    second: int,
    n_agents: int,
    split_index: int = 0,
) -> bool:
    split = split_index or n_agents // 2
    return (first < split) == (second < split)


def run_trial(
    config: ExperimentConfig,
    algorithm: str,
    seed: int,
    *,
    step_observer: Callable[[dict[str, object]], None] | None = None,
) -> list[StepRecord]:
    """Run one deterministic algorithm/seed pair and return every metric sample."""
    config.validate()
    _validate_algorithms([algorithm])
    scenario = make_scenario(config, seed)
    sensor_positions = scenario.initial_sensor_positions.copy()
    sensor_velocities = scenario.initial_sensor_velocities.copy()
    filters = (
        _initial_filters(config, scenario.truth[0], scenario.initial_belief_offsets)
        if algorithm in _KALMAN_ALGORITHMS
        else []
    )
    records: list[StepRecord] = []
    belief_state_history: list[list[np.ndarray]] = []
    belief_covariance_history: list[list[np.ndarray]] = []
    provenance_history: list[list[int]] = []
    provenance_masks = [1 << index for index in range(config.n_agents)]
    motion_position_history: list[np.ndarray] = []
    motion_velocity_history: list[np.ndarray] = []
    last_observations = np.zeros((config.n_agents, 2), dtype=float)
    last_observation_covariances = [np.eye(2, dtype=float) * 1e6 for _ in range(config.n_agents)]
    guarded_controller = (
        GuardedMomentumController(config)
        if algorithm == "flocking_guarded_momentum"
        else None
    )
    robust_tracker = (
        BiasModeTracker(config)
        if algorithm in _ROBUST_ALGORITHMS
        else None
    )
    output_controller = (
        HypothesisOutputController(config, ROBUST_OUTPUT_POLICIES[algorithm])
        if algorithm in _ROBUST_ALGORITHMS
        else None
    )
    component_tracker = (
        ComponentEpochTracker(config)
        if algorithm in _TOPOLOGY_ALGORITHMS
        else None
    )
    lifecycle_manager = (
        AgentLifecycleManager(config)
        if algorithm in _TOPOLOGY_LIFECYCLE_ALGORITHMS
        else None
    )
    hypothesis_memory = (
        HypothesisMemory(config)
        if algorithm in {
            "flocking_topology_resilient",
            M9A6_ALGORITHM,
            M9A7_ALGORITHM,
            *M9C_ALGORITHMS,
        }
        else None
    )
    missing_evidence_controller = (
        MissingEvidenceController(config)
        if algorithm == M9A6_ALGORITHM
        else None
    )
    admission_evidence_controller = (
        AdmissionAwareController(config)
        if algorithm == M9A7_ALGORITHM or algorithm in M9C_ALGORITHMS
        else None
    )
    integrated_motion_controller = (
        IntegratedInvestigationController(
            config,
            (
                "round_robin"
                if algorithm == M9C_ROUND_ROBIN_ALGORITHM
                else "receding_horizon_voi"
            ),
        )
        if algorithm in M9C_ALGORITHMS
        else None
    )
    previous_operational = np.ones(config.n_agents, dtype=bool)
    previous_observer_visible = np.ones(config.n_agents, dtype=bool)
    merge_admission_cycles = np.full(
        config.n_agents,
        config.topology_rejoin_ramp_steps,
        dtype=np.int64,
    )

    for step in range(config.steps):
        truth = scenario.truth[step]
        operational = scenario.agent_active[step]
        partition_active = _partition_active(config, step)
        topological = topological_neighbors(sensor_positions, config.neighbor_limit)
        operational_topological = [
            [
                peer
                for peer in peer_indices
                if operational[index]
                and operational[peer]
                and (
                    not partition_active
                    or _same_partition(
                        index,
                        peer,
                        config.n_agents,
                        config.topology_partition_split_index,
                    )
                )
            ]
            for index, peer_indices in enumerate(topological)
        ]
        neighbors = [
            [
                peer
                for peer in peer_indices
                if scenario.communication_available[step, index, peer]
            ]
            for index, peer_indices in enumerate(operational_topological)
        ]
        topological_edge_count = sum(
            len(peer_indices) for peer_indices in operational_topological
        )
        edge_count = sum(len(peer_indices) for peer_indices in neighbors)
        delivery_ratio = edge_count / max(topological_edge_count, 1)
        component_snapshot = (
            component_tracker.update(neighbors, operational)
            if component_tracker is not None
            else None
        )
        motion_position_history.append(sensor_positions.copy())
        motion_velocity_history.append(sensor_velocities.copy())
        effective_ages = np.minimum(step, scenario.message_ages[step]).astype(
            np.int64
        )
        delayed_indices = step - effective_ages
        delayed_sensor_positions = np.asarray(
            [
                motion_position_history[int(delayed_indices[index])][index]
                for index in range(config.n_agents)
            ]
        )
        delayed_sensor_velocities = np.asarray(
            [
                motion_velocity_history[int(delayed_indices[index])][index]
                for index in range(config.n_agents)
            ]
        )
        delivered_ages = [
            int(effective_ages[peer])
            for peer_indices in neighbors
            for peer in peer_indices
        ]
        mean_message_age = (
            float(np.mean(delivered_ages)) if delivered_ages else 0.0
        )
        max_message_age = max(delivered_ages, default=0)
        observations, measurement_covariances, available = observe(
            config,
            step,
            truth[:2],
            sensor_positions,
            scenario.measurement_normals[step],
            scenario.measurement_uniforms[step],
            scenario.agent_fault_types,
            scenario.sensor_noise_scales,
            operational,
        )
        robust_assessment = None
        filter_observations = observations
        trusted_for_information = available.copy()
        robust_trusted = operational.copy()
        raw_measurement_trusted = operational.copy()
        source_quarantined = np.zeros(config.n_agents, dtype=bool)
        diagnostic_admitted = operational.copy()
        belief_sharing_eligible = operational.copy()
        recovery_mask = operational & ~previous_operational
        if algorithm in _ROBUST_ALGORITHMS:
            assert robust_tracker is not None
            if algorithm in _TOPOLOGY_LIFECYCLE_ALGORITHMS and np.any(recovery_mask):
                robust_tracker.reset_agents(recovery_mask)
            robust_assessment = robust_tracker.update(observations, available)
            filter_observations = robust_assessment.corrected_observations
            robust_trusted = robust_assessment.trusted_agents & operational
            # A current raw sample carries no recursive fusion lineage.  Its
            # sender's M6 suspicion/quarantine state remains binding for belief
            # sharing, while the raw path is defended by covariance flooring,
            # the declared assignment model, posterior-predictive mismatch,
            # and the explicit wrong-risk ceiling.  M9A.7's colluding-ramp
            # challenge is the promotion test for this deliberately sharp
            # trust split.
            raw_measurement_trusted = operational.copy()
            source_quarantined = robust_assessment.quarantined_agents.copy()
            trusted_for_information = available & robust_trusted

        hypothesis_flock_count = 1
        primary_flock_size = config.n_agents
        primary_flock_weight = 1.0
        alternative_flock_weight = 0.0
        quarantined_agents = 0
        suspected_bias_agents = 0
        mean_bias_estimate_norm = 0.0
        metric_members = np.arange(config.n_agents, dtype=np.int64)
        control_neighbors = neighbors
        best_hypothesis_position_error: float | None = None
        truth_consistent_flock_weight = 1.0
        output_action = "select"
        output_confidence = 1.0
        output_selected_flock_id = -1
        output_wrong_mode = False
        robust_flocks = []
        output_policy_decision = None
        topology_component_count = (
            len(component_snapshot.components) if component_snapshot is not None else 1
        )
        topology_observer_component_size = int(np.sum(operational))
        topology_unknown_support = 0.0
        topology_live_support = float(np.sum(robust_trusted))
        topology_retained_support = 0.0
        topology_probation_agents = 0
        topology_rejoin_events = 0
        topology_merge_grace_active = False
        topology_component_epoch = (
            component_snapshot.epoch if component_snapshot is not None else 0
        )
        topology_duplicate_support_suppressed = 0.0
        topology_selection_blocked = False
        topology_visibility_fraction = 1.0
        topology_visible_members = tuple(range(config.n_agents))
        lifecycle_snapshot = None
        metric_virtual_estimate = None
        metric_virtual_covariance = None
        missing_evidence_residual_mass = 0.0
        missing_evidence_model_nis = 0.0
        missing_evidence_assignment_entropy = 0.0
        missing_evidence_predicted_risk = 0.0
        missing_evidence_predicted_wrong_risk = 0.0
        missing_evidence_credible_modes = 0
        measurement_eligible_agents = 0
        belief_admitted_agents = 0
        belief_censored_measurement_agents = 0
        robust_excluded_measurement_agents = 0
        unreachable_measurement_agents = 0
        measurement_covariance_floored_agents = 0
        model_rejected_measurement_agents = 0
        admission_missingness_mass = 0.0
        excluded_secondary_probability = 0.0
        unreachable_secondary_probability = 0.0
        integrated_posterior_decision = None
        investigation_allocator = "none"
        investigation_motion_action = "inactive"
        investigation_requested = False
        investigation_residual_guarded = False
        investigation_replanned = False
        investigation_planning_sequences = 0
        investigation_expected_risk = 0.0
        investigation_predicted_movement_cost = 0.0
        investigation_active_agents = 0
        investigation_mode_count = 0

        if algorithm in _KALMAN_ALGORITHMS:
            nis_values = np.full(config.n_agents, 2.0, dtype=float)
            standardized_innovations = np.full(
                (config.n_agents, 2),
                np.nan,
                dtype=float,
            )
            observed_nis: list[float] = []
            for index, kalman_filter in enumerate(filters):
                kalman_filter.predict()
                if available[index]:
                    innovation = filter_observations[index] - kalman_filter.state[:2]
                    innovation_covariance = (
                        kalman_filter.covariance[:2, :2]
                        + measurement_covariances[index]
                    )
                    standardized_innovations[index] = np.linalg.solve(
                        np.linalg.cholesky(innovation_covariance),
                        innovation,
                    )
                    nis_values[index] = kalman_filter.update(
                        filter_observations[index], measurement_covariances[index]
                    )
                    observed_nis.append(float(nis_values[index]))
            admission_weights = robust_trusted.astype(float)
            fusion_trusted = robust_trusted.copy()
            if lifecycle_manager is not None:
                assert component_snapshot is not None
                lifecycle_snapshot = lifecycle_manager.update(
                    operational,
                    available,
                    nis_values,
                    component_stable_cycles=component_snapshot.stable_cycles,
                )
                fusion_trusted = robust_trusted & lifecycle_snapshot.eligible
                belief_sharing_eligible = lifecycle_snapshot.eligible.copy()
                diagnostic_admitted = fusion_trusted.copy()
                admission_weights = (
                    lifecycle_snapshot.admission_weights
                    * robust_trusted.astype(float)
                )
                topology_probation_agents = lifecycle_snapshot.probation_count
                topology_rejoin_events = lifecycle_snapshot.rejoin_events
                if np.any(lifecycle_snapshot.recovery_mask):
                    additions = lifecycle_manager.recovery_covariance_inflation(
                        lifecycle_snapshot.recovery_mask
                    )
                    for index, addition in enumerate(additions):
                        if lifecycle_snapshot.recovery_mask[index]:
                            filters[index].covariance = (
                                filters[index].covariance + addition
                            )
            if algorithm in {
                "flocking_topology_resilient",
                M9A6_ALGORITHM,
                M9A7_ALGORITHM,
                *M9C_ALGORITHMS,
            }:
                assert component_snapshot is not None
                observer_label = int(component_snapshot.labels[0])
                if observer_label < 0:
                    observer_label = 0
                observer_visible = np.zeros(config.n_agents, dtype=bool)
                if component_snapshot.components:
                    observer_visible[
                        list(component_snapshot.components[observer_label])
                    ] = True
                entered = observer_visible & ~previous_observer_visible
                continuing_ramp = (
                    observer_visible
                    & ~entered
                    & (merge_admission_cycles < config.topology_rejoin_ramp_steps)
                )
                merge_admission_cycles[~observer_visible] = 0
                merge_admission_cycles[entered] = 1
                merge_admission_cycles[continuing_ramp] += 1
                merge_weights = np.minimum(
                    1.0,
                    merge_admission_cycles
                    / max(config.topology_rejoin_ramp_steps, 1),
                )
                admission_weights *= merge_weights
                previous_observer_visible = observer_visible
            states = [kalman_filter.state.copy() for kalman_filter in filters]
            covariances = [kalman_filter.covariance.copy() for kalman_filter in filters]
            belief_state_history.append([state.copy() for state in states])
            belief_covariance_history.append(
                [covariance.copy() for covariance in covariances]
            )
            provenance_history.append(provenance_masks.copy())
            if algorithm in _ROBUST_ALGORITHMS:
                assert robust_assessment is not None
                preliminary_flocks = build_hypothesis_flocks(
                    states,
                    covariances,
                    fusion_trusted,
                    compatibility_threshold=config.robust_compatibility_threshold,
                    grid_points=config.ci_grid_points,
                    mode_labels=robust_assessment.mode_labels,
                    fallback_if_empty=algorithm not in _TOPOLOGY_ALGORITHMS,
                )
                membership = flock_membership(preliminary_flocks, config.n_agents)
                control_neighbors = [
                    [
                        peer
                        for peer in peer_indices
                        if fusion_trusted[index]
                        and fusion_trusted[peer]
                        and membership[index] >= 0
                        and membership[index] == membership[peer]
                    ]
                    for index, peer_indices in enumerate(neighbors)
                ]
                fusion_neighbors = control_neighbors
            else:
                fusion_neighbors = neighbors
            if algorithm in _CONSENSUS_ALGORITHMS:
                peer_states = [
                    belief_state_history[int(delayed_indices[index])][index]
                    for index in range(config.n_agents)
                ]
                peer_covariances = [
                    belief_covariance_history[int(delayed_indices[index])][index]
                    for index in range(config.n_agents)
                ]
                if algorithm in _ROBUST_ALGORITHMS:
                    compensated_states: list[np.ndarray] = []
                    compensated_covariances: list[np.ndarray] = []
                    for state, covariance, age in zip(
                        peer_states, peer_covariances, effective_ages
                    ):
                        propagated_state, propagated_covariance = (
                            _age_compensate_beliefs(
                                config,
                                [state],
                                [covariance],
                                int(age),
                            )
                        )
                        compensated_states.append(propagated_state[0])
                        compensated_covariances.append(propagated_covariance[0])
                    peer_states = compensated_states
                    peer_covariances = compensated_covariances
                states, covariances = fuse_neighbor_beliefs(
                    states,
                    covariances,
                    fusion_neighbors,
                    config.ci_grid_points,
                    peer_states=peer_states,
                    peer_covariances=peer_covariances,
                )
                for kalman_filter, state, covariance in zip(filters, states, covariances):
                    kalman_filter.state = state
                    kalman_filter.covariance = covariance
                if algorithm in _TOPOLOGY_ALGORITHMS:
                    peer_provenance = [
                        provenance_history[int(delayed_indices[index])][index]
                        for index in range(config.n_agents)
                    ]
                    provenance_masks = [
                        provenance_masks[index]
                        | reduce(
                            operator.or_,
                            (peer_provenance[peer] for peer in peer_indices),
                            0,
                        )
                        for index, peer_indices in enumerate(fusion_neighbors)
                    ]
            position_estimates = np.asarray([state[:2] for state in states])
            position_covariances = [covariance[:2, :2] for covariance in covariances]
            if algorithm in _ROBUST_ALGORITHMS:
                assert robust_assessment is not None
                assert output_controller is not None
                if algorithm in _TOPOLOGY_ALGORITHMS:
                    assert component_snapshot is not None
                    topology_flock_set = build_topology_flocks(
                        states,
                        covariances,
                        fusion_trusted,
                        admission_weights,
                        provenance_masks,
                        component_snapshot,
                        config,
                        mode_labels=robust_assessment.mode_labels,
                        component_local=algorithm in _TOPOLOGY_COMPONENT_ALGORITHMS,
                    )
                    robust_flocks = topology_flock_set.flocks
                    if hypothesis_memory is not None:
                        robust_flocks, topology_retained_support = (
                            hypothesis_memory.stabilize(robust_flocks)
                        )
                    topology_live_support = topology_flock_set.live_support
                    topology_unknown_support = (
                        topology_flock_set.unknown_support / config.n_agents
                    )
                    topology_duplicate_support_suppressed = (
                        topology_flock_set.duplicate_support_suppressed
                    )
                    topology_observer_component_size = len(
                        topology_flock_set.visible_members
                    )
                    topology_visible_members = topology_flock_set.visible_members
                    topology_visibility_fraction = (
                        topology_observer_component_size / config.n_agents
                    )
                    topology_merge_grace_active = (
                        algorithm
                        in {
                            "flocking_topology_resilient",
                            M9A6_ALGORITHM,
                            M9A7_ALGORITHM,
                            *M9C_ALGORITHMS,
                        }
                        and component_snapshot.merge_grace_active
                    )
                    topology_selection_blocked = (
                        topology_merge_grace_active
                        or topology_live_support <= 0.0
                    )
                else:
                    robust_flocks = build_hypothesis_flocks(
                        states,
                        covariances,
                        robust_trusted,
                        compatibility_threshold=config.robust_compatibility_threshold,
                        grid_points=config.ci_grid_points,
                        mode_labels=robust_assessment.mode_labels,
                    )
                primary = robust_flocks[0]
                output_policy_decision = output_controller.decide(
                    robust_flocks,
                    unknown_support=topology_unknown_support,
                    force_defer=topology_selection_blocked,
                )
                team_state = output_policy_decision.state
                _team_covariance = output_policy_decision.covariance
                output_action = output_policy_decision.action
                output_confidence = output_policy_decision.confidence
                output_selected_flock_id = (
                    output_policy_decision.selected_flock_id
                    if output_policy_decision.selected_flock_id is not None
                    else -1
                )
                hypothesis_flock_count = len(robust_flocks)
                primary_flock_size = len(primary.members)
                primary_flock_weight = primary.weight
                alternative_flock_weight = (
                    max(flock.weight for flock in robust_flocks[1:])
                    if len(robust_flocks) > 1
                    else 0.0
                )
                truth_consistent_flock = min(
                    robust_flocks,
                    key=lambda flock: float(
                        np.linalg.norm(flock.state[:2] - truth[:2])
                    ),
                )
                best_hypothesis_position_error = float(
                    np.linalg.norm(truth_consistent_flock.state[:2] - truth[:2])
                )
                truth_consistent_flock_weight = truth_consistent_flock.weight
                selected_error = float(
                    np.linalg.norm(output_policy_decision.state[:2] - truth[:2])
                )
                output_wrong_mode = (
                    output_policy_decision.selected_flock_id is not None
                    and len(robust_flocks) > 1
                    and selected_error
                    > best_hypothesis_position_error
                    + config.robust_bias_group_tolerance
                )
                if output_policy_decision.selected_flock_id is not None:
                    selected_flock = next(
                        flock
                        for flock in robust_flocks
                        if flock.flock_id == output_policy_decision.selected_flock_id
                    )
                    metric_members = np.asarray(
                        selected_flock.members,
                        dtype=np.int64,
                    )
                else:
                    # Calibration of a returned set is evaluated on the
                    # truth-consistent member flock; the policy never sees it.
                    metric_members = np.asarray(
                        truth_consistent_flock.members,
                        dtype=np.int64,
                    )
                if metric_members.size == 0 and metric_virtual_estimate is None:
                    metric_virtual_estimate = truth_consistent_flock.state[:2].copy()
                    metric_virtual_covariance = (
                        truth_consistent_flock.covariance[:2, :2].copy()
                    )
                if (
                    missing_evidence_controller is not None
                    or admission_evidence_controller is not None
                ):
                    observer_visible = np.zeros(config.n_agents, dtype=bool)
                    observer_visible[list(topology_visible_members)] = True
                    if admission_evidence_controller is not None:
                        admission_decision = admission_evidence_controller.update(
                            step,
                            observations,
                            tuple(measurement_covariances),
                            component_visible=observer_visible,
                            available=available,
                            operational=operational,
                            raw_trusted=raw_measurement_trusted,
                            source_quarantined=source_quarantined,
                            belief_share_eligible=belief_sharing_eligible,
                            belief_admitted=diagnostic_admitted,
                        )
                        missing_decision = admission_decision.posterior
                        measurement_eligible_agents = (
                            admission_decision.measurement_eligible_agents
                        )
                        belief_admitted_agents = (
                            admission_decision.belief_admitted_agents
                        )
                        belief_censored_measurement_agents = (
                            admission_decision.belief_censored_measurement_agents
                        )
                        robust_excluded_measurement_agents = (
                            admission_decision.robust_excluded_measurement_agents
                        )
                        unreachable_measurement_agents = (
                            admission_decision.unreachable_measurement_agents
                        )
                        measurement_covariance_floored_agents = (
                            admission_decision.covariance_floored_agents
                        )
                        model_rejected_measurement_agents = (
                            admission_decision.model_rejected_measurement_agents
                        )
                        admission_missingness_mass = (
                            admission_decision.admission_residual_mass
                        )
                        excluded_secondary_probability = (
                            admission_decision.excluded_secondary_probability
                        )
                        unreachable_secondary_probability = (
                            admission_decision.unreachable_secondary_probability
                        )
                    else:
                        assert missing_evidence_controller is not None
                        observer_visible &= available & diagnostic_admitted
                        missing_decision = missing_evidence_controller.update(
                            step,
                            observations,
                            tuple(measurement_covariances),
                            observer_visible,
                        )
                    team_state = missing_decision.state
                    _team_covariance = missing_decision.covariance
                    output_action = missing_decision.action
                    output_confidence = missing_decision.confidence
                    output_selected_flock_id = (
                        missing_decision.selected_mode_index
                        if missing_decision.selected_mode_index is not None
                        else -1
                    )
                    hypothesis_flock_count = len(missing_decision.modes)
                    primary_flock_size = int(
                        round(
                            config.n_agents
                            * (1.0 - missing_decision.residual_mass)
                            * missing_decision.modes[0].probability
                        )
                    )
                    primary_flock_weight = (
                        (1.0 - missing_decision.residual_mass)
                        * missing_decision.modes[0].probability
                    )
                    alternative_flock_weight = (
                        (1.0 - missing_decision.residual_mass)
                        * max(
                            (
                                mode.probability
                                for mode in missing_decision.modes[1:]
                            ),
                            default=0.0,
                        )
                    )
                    truth_consistent_mode = min(
                        missing_decision.credible_modes,
                        key=lambda mode: float(
                            np.linalg.norm(mode.state[:2] - truth[:2])
                        ),
                    )
                    best_hypothesis_position_error = float(
                        np.linalg.norm(
                            truth_consistent_mode.state[:2] - truth[:2]
                        )
                    )
                    truth_consistent_flock_weight = (
                        (1.0 - missing_decision.residual_mass)
                        * truth_consistent_mode.probability
                    )
                    selected_error = float(
                        np.linalg.norm(missing_decision.state[:2] - truth[:2])
                    )
                    output_wrong_mode = (
                        missing_decision.action == "select"
                        and len(missing_decision.modes) > 1
                        and selected_error
                        > min(
                            float(np.linalg.norm(mode.state[:2] - truth[:2]))
                            for mode in missing_decision.modes
                        )
                        + config.robust_bias_group_tolerance
                    )
                    metric_members = np.asarray([], dtype=np.int64)
                    metric_virtual_estimate = truth_consistent_mode.state[:2].copy()
                    metric_virtual_covariance = (
                        truth_consistent_mode.covariance[:2, :2].copy()
                    )
                    missing_evidence_residual_mass = (
                        missing_decision.residual_mass
                    )
                    missing_evidence_model_nis = missing_decision.model_nis
                    missing_evidence_assignment_entropy = (
                        missing_decision.assignment_entropy
                    )
                    missing_evidence_predicted_risk = (
                        missing_decision.predicted_risk
                    )
                    missing_evidence_predicted_wrong_risk = (
                        missing_decision.predicted_wrong_risk
                    )
                    missing_evidence_credible_modes = len(
                        missing_decision.credible_modes
                    )
                    if algorithm in M9C_ALGORITHMS:
                        integrated_posterior_decision = missing_decision
                quarantined_agents = int(
                    np.sum(robust_assessment.quarantined_agents)
                )
                suspected_bias_agents = int(
                    np.sum(robust_assessment.suspected_bias_agents)
                )
                mean_bias_estimate_norm = float(
                    np.mean(np.linalg.norm(robust_assessment.bias_estimates, axis=1))
                )
            else:
                team_state, _team_covariance = fuse_team_belief(
                    states, covariances, config.ci_grid_points
                )
            team_position = team_state[:2]
            mean_nis: float | None = float(np.mean(observed_nis)) if observed_nis else None
        else:
            # This baseline deliberately has no dynamic estimator: current observations
            # are its beliefs, and only the behavioural flock supplies coordination.
            nis_values = np.full(config.n_agents, 2.0, dtype=float)
            for index in range(config.n_agents):
                if available[index]:
                    last_observations[index] = observations[index]
                    last_observation_covariances[index] = measurement_covariances[index].copy()
                else:
                    last_observation_covariances[index] = (
                        last_observation_covariances[index]
                        + np.eye(2, dtype=float) * config.filter_process_variance
                    )
            position_estimates = last_observations.copy()
            position_covariances = [item.copy() for item in last_observation_covariances]
            team_position, _team_covariance = precision_fuse_positions(
                position_estimates, position_covariances
            )
            mean_nis = None

        momentum_classification = "not_applicable"
        momentum_change_score = 0.0
        momentum_corroborating_agents = 0
        momentum_biased_agents = 0
        momentum_fallback_active = False
        momentum_change_event = False
        if algorithm == "flocking_guarded_momentum":
            assert guarded_controller is not None
            decision = guarded_controller.update(
                standardized_innovations,
                nis_values,
                available,
                delivery_ratio=delivery_ratio,
                message_age=max_message_age,
            )
            momenta = decision.momenta
            momentum_classification = decision.classification
            momentum_change_score = decision.change_score
            momentum_corroborating_agents = decision.corroborating_agents
            momentum_biased_agents = decision.biased_agents
            momentum_fallback_active = decision.fallback_active
            momentum_change_event = decision.change_event
        elif algorithm == "flocking_adaptive_momentum":
            momenta = adaptive_momentum(config, nis_values)
            momentum_classification = "direct_nis_adaptive"
        elif algorithm == "flocking_fixed_momentum" or algorithm in _ROBUST_ALGORITHMS:
            momenta = np.full(config.n_agents, config.fixed_momentum, dtype=float)
            momentum_classification = (
                f"fixed_robust_{ROBUST_OUTPUT_POLICIES[algorithm]}"
                if algorithm in _ROBUST_ALGORITHMS
                else "fixed"
            )
        else:
            momenta = np.zeros(config.n_agents, dtype=float)
            momentum_classification = "zero"

        integrated_motion_goals = None
        if integrated_motion_controller is not None:
            assert integrated_posterior_decision is not None
            assert admission_evidence_controller is not None
            assignment_filter = admission_evidence_controller.posterior.filter
            component_visible = np.zeros(config.n_agents, dtype=bool)
            component_visible[list(topology_visible_members)] = True
            integrated_motion = integrated_motion_controller.decide(
                step,
                integrated_posterior_decision,
                AssignmentEvidence(
                    weights=assignment_filter.weights.copy(),
                    assignment_mask=assignment_filter.assignment_mask.copy(),
                    secondary_offset=assignment_filter.secondary_offset.copy(),
                    secondary_active=(
                        step + config.m9c_planning_horizon
                        >= assignment_filter.secondary_start_step
                        and (
                            assignment_filter.secondary_end_step < 0
                            or step < assignment_filter.secondary_end_step
                        )
                    ),
                    secondary_steps_remaining=max(
                        0,
                        (
                            config.steps
                            if assignment_filter.secondary_end_step < 0
                            else assignment_filter.secondary_end_step
                        )
                        - max(step, assignment_filter.secondary_start_step),
                    ),
                ),
                sensor_positions,
                sensor_velocities,
                position_estimates,
                component_visible=component_visible,
                operational=operational,
                control_neighbors=control_neighbors,
                momenta=momenta,
                remaining_steps=config.steps - step,
            )
            integrated_motion_goals = integrated_motion.goals
            investigation_allocator = integrated_motion.policy
            investigation_motion_action = integrated_motion.action
            investigation_requested = integrated_motion.requested
            investigation_residual_guarded = integrated_motion.residual_guarded
            investigation_replanned = integrated_motion.replanned
            investigation_planning_sequences = (
                integrated_motion.planning_sequences_evaluated
            )
            investigation_expected_risk = (
                integrated_motion.expected_risk
                if np.isfinite(integrated_motion.expected_risk)
                else 0.0
            )
            investigation_predicted_movement_cost = (
                integrated_motion.predicted_movement_cost
            )
            investigation_active_agents = integrated_motion.active_agents
            investigation_mode_count = integrated_motion.mode_count

        team_error = float(np.linalg.norm(team_position - truth[:2]))
        if best_hypothesis_position_error is None:
            best_hypothesis_position_error = team_error
        output_decision_base_error = (
            best_hypothesis_position_error
            if output_action in {"defer", "investigate"}
            else team_error
        )
        output_decision_loss = output_decision_base_error
        if output_action in {"defer", "investigate"}:
            output_decision_loss += config.output_defer_cost
        if output_action == "investigate":
            output_decision_loss += config.output_investigation_cost
        if metric_virtual_estimate is not None:
            metric_position_estimates = np.asarray([metric_virtual_estimate])
            metric_position_covariances = [metric_virtual_covariance]
        else:
            metric_position_estimates = position_estimates[metric_members]
            metric_position_covariances = [
                position_covariances[int(index)] for index in metric_members
            ]
        agent_errors = metric_position_estimates - truth[:2]
        mean_agent_squared_error = float(np.mean(np.sum(agent_errors**2, axis=1)))
        mean_nees, coverage95 = agent_calibration(
            metric_position_estimates,
            metric_position_covariances,
            truth[:2],
        )
        messages, bytes_sent = _communication_cost(algorithm, edge_count)
        records.append(
            StepRecord(
                seed=seed,
                algorithm=algorithm,
                step=step,
                target_x=float(truth[0]),
                target_y=float(truth[1]),
                team_estimate_x=float(team_position[0]),
                team_estimate_y=float(team_position[1]),
                team_position_error=team_error,
                best_hypothesis_position_error=best_hypothesis_position_error,
                truth_consistent_flock_weight=truth_consistent_flock_weight,
                output_action=output_action,
                output_confidence=output_confidence,
                output_selected_flock_id=output_selected_flock_id,
                output_decision_base_error=output_decision_base_error,
                output_decision_loss=output_decision_loss,
                output_wrong_mode=output_wrong_mode,
                mean_agent_squared_error=mean_agent_squared_error,
                mean_nees=mean_nees,
                coverage95_rate=coverage95,
                mean_nis=mean_nis,
                information_gain=expected_information_gain(
                    [
                        covariance
                        for covariance, is_available in zip(
                            measurement_covariances, trusted_for_information
                        )
                        if is_available
                    ],
                    config.reference_position_variance,
                ),
                spatial_diversity=mean_pairwise_distance(sensor_positions),
                estimate_disagreement=mean_pairwise_distance(position_estimates),
                mean_momentum=float(np.mean(momenta)),
                momentum_classification=momentum_classification,
                momentum_change_score=momentum_change_score,
                momentum_corroborating_agents=momentum_corroborating_agents,
                momentum_biased_agents=momentum_biased_agents,
                momentum_fallback_active=momentum_fallback_active,
                momentum_change_event=momentum_change_event,
                hypothesis_flock_count=hypothesis_flock_count,
                primary_flock_size=primary_flock_size,
                primary_flock_weight=primary_flock_weight,
                alternative_flock_weight=alternative_flock_weight,
                quarantined_agents=quarantined_agents,
                suspected_bias_agents=suspected_bias_agents,
                mean_bias_estimate_norm=mean_bias_estimate_norm,
                mean_sensor_speed=float(
                    np.mean(np.linalg.norm(sensor_velocities, axis=1))
                ),
                operational_agents=int(np.sum(operational)),
                delivery_ratio=delivery_ratio,
                mean_message_age=mean_message_age,
                topology_partition_active=partition_active,
                topology_component_count=topology_component_count,
                topology_observer_component_size=topology_observer_component_size,
                topology_visibility_fraction=topology_visibility_fraction,
                topology_live_support=topology_live_support,
                topology_retained_support=topology_retained_support,
                topology_unknown_support=topology_unknown_support,
                topology_probation_agents=topology_probation_agents,
                topology_rejoin_events=topology_rejoin_events,
                topology_merge_grace_active=topology_merge_grace_active,
                topology_component_epoch=topology_component_epoch,
                topology_duplicate_support_suppressed=(
                    topology_duplicate_support_suppressed
                ),
                topology_selection_blocked=topology_selection_blocked,
                missing_evidence_residual_mass=(
                    missing_evidence_residual_mass
                ),
                missing_evidence_model_nis=missing_evidence_model_nis,
                missing_evidence_assignment_entropy=(
                    missing_evidence_assignment_entropy
                ),
                missing_evidence_predicted_risk=(
                    missing_evidence_predicted_risk
                ),
                missing_evidence_predicted_wrong_risk=(
                    missing_evidence_predicted_wrong_risk
                ),
                missing_evidence_credible_modes=(
                    missing_evidence_credible_modes
                ),
                measurement_eligible_agents=measurement_eligible_agents,
                belief_admitted_agents=belief_admitted_agents,
                belief_censored_measurement_agents=(
                    belief_censored_measurement_agents
                ),
                robust_excluded_measurement_agents=(
                    robust_excluded_measurement_agents
                ),
                unreachable_measurement_agents=unreachable_measurement_agents,
                measurement_covariance_floored_agents=(
                    measurement_covariance_floored_agents
                ),
                model_rejected_measurement_agents=(
                    model_rejected_measurement_agents
                ),
                admission_missingness_mass=admission_missingness_mass,
                excluded_secondary_probability=excluded_secondary_probability,
                unreachable_secondary_probability=(
                    unreachable_secondary_probability
                ),
                investigation_allocator=investigation_allocator,
                investigation_motion_action=investigation_motion_action,
                investigation_requested=investigation_requested,
                investigation_residual_guarded=investigation_residual_guarded,
                investigation_replanned=investigation_replanned,
                investigation_planning_sequences=(
                    investigation_planning_sequences
                ),
                investigation_expected_risk=investigation_expected_risk,
                investigation_predicted_movement_cost=(
                    investigation_predicted_movement_cost
                ),
                investigation_active_agents=investigation_active_agents,
                investigation_mode_count=investigation_mode_count,
                messages=messages,
                bytes_sent=bytes_sent,
            )
        )
        if step_observer is not None:
            # The observer is deliberately read-only and receives copies of
            # the causal information materialized on this cycle.  It is used
            # by diagnostic comparators without changing the frozen policy,
            # sensor motion, random stream, or recorded M9A output.
            step_observer(
                {
                    "step": step,
                    "truth": truth.copy(),
                    "observations": observations.copy(),
                    "measurement_covariances": tuple(
                        covariance.copy() for covariance in measurement_covariances
                    ),
                    "available": available.copy(),
                    "operational": operational.copy(),
                    "admitted": diagnostic_admitted.copy(),
                    "raw_measurement_trusted": raw_measurement_trusted.copy(),
                    "source_quarantined": source_quarantined.copy(),
                    "belief_share_eligible": belief_sharing_eligible.copy(),
                    "neighbors": tuple(tuple(peers) for peers in neighbors),
                    "record": records[-1],
                }
            )

        if algorithm in _FLOCKING_ALGORITHMS:
            motion_goal_estimates = position_estimates
            if integrated_motion_goals is not None:
                motion_goal_estimates = integrated_motion_goals
            elif (
                algorithm
                in {
                    "flocking_robust_active",
                    "flocking_topology_resilient",
                    M9A6_ALGORITHM,
                    M9A7_ALGORITHM,
                }
                and output_policy_decision is not None
                and output_policy_decision.action == "investigate"
                and robust_flocks
            ):
                motion_goal_estimates = investigation_goals(
                    robust_flocks,
                    config.n_agents,
                )
                if algorithm in _TOPOLOGY_COMPONENT_ALGORITHMS:
                    component_goals = position_estimates.copy()
                    component_goals[list(topology_visible_members)] = (
                        motion_goal_estimates[list(topology_visible_members)]
                    )
                    motion_goal_estimates = component_goals
            sensor_velocities = flocking_velocity(
                config,
                sensor_positions,
                sensor_velocities,
                motion_goal_estimates,
                control_neighbors,
                momenta,
                peer_positions=delayed_sensor_positions,
                peer_velocities=delayed_sensor_velocities,
            )
        else:
            sensor_velocities = direct_tracking_velocity(
                config, sensor_positions, position_estimates
            )
        sensor_velocities[~operational] = 0.0
        sensor_positions = advance_sensors(config, sensor_positions, sensor_velocities)
        previous_operational = operational.copy()

    return records


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run_experiment(config: ExperimentConfig, output_directory: str | Path) -> list[dict[str, object]]:
    """Run the experiment matrix and write machine- and human-readable artifacts."""
    config.validate()
    algorithms = _validate_algorithms(config.algorithms)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)

    all_records: list[StepRecord] = []
    run_summaries: list[dict[str, object]] = []
    for algorithm in algorithms:
        for seed in config.seeds:
            started = perf_counter()
            records = run_trial(config, algorithm, seed)
            all_records.extend(records)
            summary = summarize_run(config, records)
            summary["runtime_seconds"] = perf_counter() - started
            run_summaries.append(summary)

    aggregate_summary = aggregate_runs(run_summaries)
    _write_csv(output / "per_step_metrics.csv", [record.to_dict() for record in all_records])
    _write_csv(output / "run_summary.csv", run_summaries)
    _write_csv(output / "summary.csv", aggregate_summary)
    (output / "config.json").write_text(
        json.dumps(config.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "summary.json").write_text(
        json.dumps(aggregate_summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    environment = {
        "platform_version": "0.12.0",
        "python": platform.python_version(),
        "numpy": np.__version__,
        "operating_system": platform.platform(),
        "command_python": sys.executable,
    }
    (output / "environment.json").write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_comparison_svg(aggregate_summary, output / "comparison.svg")
    write_error_timeseries_svg(config, all_records, output / "error_timeseries.svg")
    return aggregate_summary
