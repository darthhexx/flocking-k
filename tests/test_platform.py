from __future__ import annotations

import csv
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from flockkalman.active_sensing_suite import (
    ActiveSensingConfig,
    DEFAULT_ACTIVE_SENSING_SCENARIOS,
    active_sensing_fingerprint,
    choose_active_sensing_action,
    reanalyze_active_sensing_decision_suite,
    run_active_sensing_decision_suite,
    run_active_sensing_trial,
)
from flockkalman.admission_evidence import (
    M9A7_ALGORITHM,
    AdmissionAwareController,
    floor_reported_covariances,
)
from flockkalman.admission_suite import (
    AdmissionEvidenceShadowCollector,
    reanalyze_admission_evidence_suite,
    required_seed_count,
    run_admission_evidence_suite,
)
from flockkalman.adversarial_trust import (
    AdversarialTrustController,
)
from flockkalman.adversarial_trust_suite import (
    reanalyze_adversarial_trust_suite,
    run_adversarial_trust_suite,
)
from flockkalman.acceleration_replay import (
    AccelerationConfig,
    AccelerationLandmarkEKF,
    run_jerk_limiter_assay,
)
from flockkalman.ambiguity_assay import (
    AmbiguityAssayConfig,
    assay_fingerprint,
    reanalyze_ambiguity_decision_suite,
    run_ambiguity_assay,
    run_ambiguity_decision_suite,
)
from flockkalman.config import ExperimentConfig
from flockkalman.experiment import ALGORITHMS, run_experiment, run_trial
from flockkalman.external_replay import (
    load_mrclam_dataset,
)
from flockkalman.external_replay_repair import (
    canonicalize_mrclam_dataset,
    verify_canonicalization,
)
from flockkalman.filters import KalmanFilter, covariance_intersection
from flockkalman.guarded_suite import run_guarded_decision_suite
from flockkalman.integrated_sensing import (
    M9C_RECEDING_ALGORITHM,
    M9C_ROUND_ROBIN_ALGORITHM,
)
from flockkalman.integration_suite import (
    reanalyze_integration_suite,
    required_tail_seeds,
    run_integration_suite,
)
from flockkalman.full_loop_contracts import (
    AttackManifest,
    AttackShim,
    DeterministicNetwork,
    HashChainedLedger,
    NetworkFaultManifest,
    OPERATIONAL_DOMAIN,
    SCORER_DOMAIN,
    TruthSample,
    WireMessage,
    verify_ledger,
)
from flockkalman.full_loop_hil import (
    DEFAULT_HIL_SCENARIOS,
    HILConfig,
    run_full_loop_hil_suite,
    run_hil_trial,
)
from flockkalman.full_loop_physical import (
    create_physical_trial_plan,
    run_physical_pilot,
    score_physical_bundle,
    seal_physical_bundle,
)
from flockkalman.output_policy import HypothesisOutputController
from flockkalman.output_suite import run_output_decision_suite
from flockkalman.momentum_mechanism import (
    recurrence_time_constant,
    run_momentum_mechanism_study,
)
from flockkalman.missing_evidence import M9A6_ALGORITHM, MissingEvidenceController
from flockkalman.missing_evidence_suite import (
    MissingEvidenceShadowCollector,
    reanalyze_missing_evidence_suite,
    run_missing_evidence_suite,
)
from flockkalman.oracle_floor import AssignmentBayesFilter, run_oracle_floor_trial
from flockkalman.oracle_floor_suite import (
    reanalyze_oracle_floor_suite,
    run_oracle_floor_suite,
)
from flockkalman.realism_suite import run_realism_decision_suite
from flockkalman.policies import GuardedMomentumController, adaptive_momentum
from flockkalman.robust import BiasModeTracker, HypothesisFlock, build_hypothesis_flocks
from flockkalman.robust_suite import run_robust_decision_suite
from flockkalman.simulation import make_scenario, scenario_fingerprint
from flockkalman.suite import run_decision_suite
from flockkalman.topology import (
    AgentLifecycleManager,
    ComponentEpochTracker,
    LifecycleState,
    connected_components,
)
from flockkalman.topology_suite import (
    reanalyze_topology_decision_suite,
    run_topology_decision_suite,
)


class FilterTests(unittest.TestCase):
    def test_kalman_update_reduces_position_uncertainty(self) -> None:
        kalman_filter = KalmanFilter(
            state=np.zeros(4),
            covariance=np.eye(4) * 4.0,
            dt=1.0,
            acceleration_variance=0.05,
        )
        kalman_filter.predict()
        before = np.trace(kalman_filter.covariance[:2, :2])
        nis = kalman_filter.update(np.array([1.0, -0.5]), np.eye(2))
        self.assertLess(np.trace(kalman_filter.covariance[:2, :2]), before)
        self.assertGreaterEqual(nis, 0.0)
        self.assertTrue(np.all(np.linalg.eigvalsh(kalman_filter.covariance) > 0.0))

    def test_covariance_intersection_is_symmetric_for_equal_covariance(self) -> None:
        state, covariance = covariance_intersection(
            np.array([0.0, 0.0]),
            np.eye(2),
            np.array([2.0, 0.0]),
            np.eye(2),
            grid_points=21,
        )
        np.testing.assert_allclose(state, np.array([1.0, 0.0]))
        np.testing.assert_allclose(covariance, np.eye(2))


class PolicyTests(unittest.TestCase):
    def test_surprise_reduces_momentum(self) -> None:
        config = ExperimentConfig()
        values = adaptive_momentum(config, np.array([2.0, 8.0]))
        self.assertGreater(values[0], values[1])
        self.assertAlmostEqual(values[0], config.adaptive_momentum_max)
        self.assertAlmostEqual(values[1], config.adaptive_momentum_min)

    def test_recurrence_time_constant_round_trip(self) -> None:
        rho = 0.72
        tau = recurrence_time_constant(rho, 1.0)
        self.assertAlmostEqual(np.exp(-1.0 / tau), rho)
        self.assertEqual(recurrence_time_constant(0.0, 1.0), 0.0)

    def test_guarded_controller_requires_correlated_surprise(self) -> None:
        config = ExperimentConfig(n_agents=4, neighbor_limit=2)
        controller = GuardedMomentumController(config)
        available = np.ones(4, dtype=bool)
        coherent = np.tile(np.array([2.0, 0.2]), (4, 1))
        first = controller.update(
            coherent,
            np.full(4, 8.08),
            available,
            delivery_ratio=1.0,
            message_age=0,
        )
        second = controller.update(
            coherent,
            np.full(4, 8.08),
            available,
            delivery_ratio=1.0,
            message_age=0,
        )
        third = controller.update(
            coherent,
            np.full(4, 8.08),
            available,
            delivery_ratio=1.0,
            message_age=0,
        )
        self.assertTrue(first.fallback_active)
        self.assertTrue(second.fallback_active)
        self.assertTrue(third.change_event)
        self.assertEqual(third.classification, "corroborated_change")
        np.testing.assert_allclose(third.momenta, config.guarded_change_momentum)

        uncorroborated = GuardedMomentumController(config).update(
            np.array([[3.0, 0.0], [0.1, 0.0], [0.0, 0.1], [-0.1, 0.0]]),
            np.array([9.0, 0.01, 0.01, 0.01]),
            available,
            delivery_ratio=1.0,
            message_age=0,
        )
        self.assertTrue(uncorroborated.fallback_active)
        np.testing.assert_allclose(uncorroborated.momenta, config.fixed_momentum)

    def test_guarded_controller_rejects_stale_evidence_and_flags_bias(self) -> None:
        config = ExperimentConfig(
            n_agents=4,
            neighbor_limit=2,
            guarded_bias_persistence_steps=3,
            guarded_bias_ema_alpha=0.5,
            guarded_bias_threshold=0.8,
        )
        available = np.ones(4, dtype=bool)
        controller = GuardedMomentumController(config)
        stale = controller.update(
            np.tile(np.array([2.0, 0.0]), (4, 1)),
            np.full(4, 8.0),
            available,
            delivery_ratio=1.0,
            message_age=2,
        )
        self.assertEqual(stale.classification, "stale_message_fallback")
        for _ in range(5):
            biased = controller.update(
                np.array([[3.0, 0.0], [0.0, 0.0], [0.1, 0.0], [-0.1, 0.0]]),
                np.array([9.0, 0.0, 0.01, 0.01]),
                available,
                delivery_ratio=1.0,
                message_age=0,
            )
        self.assertGreaterEqual(biased.biased_agents, 1)
        self.assertTrue(biased.fallback_active)


class RobustFusionTests(unittest.TestCase):
    def test_bias_tracker_quarantines_minorities_but_preserves_large_modes(self) -> None:
        available = np.ones(8, dtype=bool)
        bias_config = ExperimentConfig(
            robust_bias_persistence_steps=3,
            robust_bias_ema_alpha=0.5,
        )
        bias_tracker = BiasModeTracker(bias_config)
        biased_observations = np.zeros((8, 2), dtype=float)
        biased_observations[:2] = np.array([3.0, -2.0])
        for _ in range(5):
            bias_assessment = bias_tracker.update(biased_observations, available)
        self.assertEqual(int(np.sum(bias_assessment.quarantined_agents)), 2)
        self.assertEqual(int(np.sum(bias_assessment.alternative_mode_agents)), 0)

        mode_tracker = BiasModeTracker(bias_config)
        multimodal_observations = np.zeros((8, 2), dtype=float)
        multimodal_observations[4:] = np.array([5.0, -4.0])
        for _ in range(5):
            mode_assessment = mode_tracker.update(multimodal_observations, available)
        self.assertEqual(int(np.sum(mode_assessment.quarantined_agents)), 0)
        self.assertEqual(int(np.sum(mode_assessment.alternative_mode_agents)), 8)
        self.assertEqual(len(set(mode_assessment.mode_labels.tolist())), 2)
        self.assertTrue(
            np.all(mode_assessment.mode_labels[:4] != mode_assessment.mode_labels[4])
        )
        self.assertTrue(
            np.all(mode_assessment.mode_labels[4:] == mode_assessment.mode_labels[4])
        )

    def test_hypothesis_manager_keeps_incompatible_modes_separate(self) -> None:
        states = [np.zeros(4) for _ in range(4)] + [
            np.array([5.0, -4.0, 0.0, 0.0]) for _ in range(4)
        ]
        covariances = [np.eye(4) * 0.2 for _ in range(8)]
        labels = np.array([0, 0, 0, 0, 1, 1, 1, 1])
        flocks = build_hypothesis_flocks(
            states,
            covariances,
            np.ones(8, dtype=bool),
            compatibility_threshold=9.21,
            grid_points=7,
            mode_labels=labels,
        )
        self.assertEqual(len(flocks), 2)
        self.assertEqual(flocks[0].members, (0, 1, 2, 3))
        self.assertAlmostEqual(flocks[0].weight, 0.5)
        self.assertAlmostEqual(flocks[1].weight, 0.5)


class TopologyResilienceTests(unittest.TestCase):
    def test_components_are_weak_deterministic_and_exclude_offline_agents(self) -> None:
        neighbors = [[1], [], [3], [2], []]
        operational = np.array([True, True, True, True, False])
        components, labels = connected_components(neighbors, operational)
        self.assertEqual(components, ((0, 1), (2, 3)))
        np.testing.assert_array_equal(labels, np.array([0, 0, 1, 1, -1]))

    def test_recovered_agent_must_complete_probation_and_support_ramp(self) -> None:
        config = ExperimentConfig(
            n_agents=4,
            neighbor_limit=2,
            topology_rejoin_probation_steps=2,
            topology_rejoin_component_stable_steps=1,
            topology_rejoin_ramp_steps=3,
        )
        manager = AgentLifecycleManager(config)
        available = np.ones(4, dtype=bool)
        nis = np.ones(4)
        operational = np.ones(4, dtype=bool)
        first = manager.update(
            operational, available, nis, component_stable_cycles=3
        )
        self.assertTrue(np.all(first.eligible))

        operational[3] = False
        offline = manager.update(
            operational, available, nis, component_stable_cycles=3
        )
        self.assertEqual(offline.states[3], int(LifecycleState.OFFLINE))
        operational[3] = True
        probation = manager.update(
            operational, available, nis, component_stable_cycles=3
        )
        self.assertEqual(probation.states[3], int(LifecycleState.PROBATION))
        self.assertFalse(probation.eligible[3])
        admitted = manager.update(
            operational, available, nis, component_stable_cycles=3
        )
        self.assertEqual(admitted.states[3], int(LifecycleState.TRUSTED))
        self.assertGreater(admitted.admission_weights[3], 0.0)
        self.assertLess(admitted.admission_weights[3], 1.0)

    def test_unknown_support_prevents_single_component_overclaim(self) -> None:
        config = ExperimentConfig(output_ambiguity_persistence_steps=3)
        controller = HypothesisOutputController(config, "active")
        flock = HypothesisFlock(
            0,
            (0, 1, 2),
            np.zeros(4),
            np.eye(4),
            3.0 / 8.0,
        )
        decision = controller.decide([flock], unknown_support=5.0 / 8.0)
        self.assertEqual(decision.action, "investigate")
        self.assertIsNone(decision.selected_flock_id)

    def test_partition_rejoin_trace_materializes_m9a_diagnostics(self) -> None:
        config = ExperimentConfig(
            steps=55,
            change_step=27,
            recovery_window=3,
            ci_grid_points=5,
            agent_failure_count=2,
            agent_failure_step=12,
            agent_recovery_step=36,
            topology_partition_step=10,
            topology_partition_duration=24,
            topology_partition_split_index=3,
        )
        records = run_trial(config, "flocking_topology_resilient", 91)
        self.assertGreater(sum(record.topology_rejoin_events for record in records), 0)
        self.assertTrue(any(record.topology_probation_agents > 0 for record in records))
        self.assertTrue(any(record.topology_component_count > 1 for record in records))
        self.assertTrue(any(record.topology_unknown_support > 0.0 for record in records))
        self.assertTrue(any(record.topology_merge_grace_active for record in records))
        self.assertTrue(
            any(record.topology_duplicate_support_suppressed > 0.0 for record in records)
        )

    def test_small_topology_suite_and_reanalysis(self) -> None:
        config = ExperimentConfig(
            steps=40,
            change_step=20,
            n_agents=8,
            neighbor_limit=3,
            recovery_window=3,
            ci_grid_points=5,
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            decision = run_topology_decision_suite(
                config,
                output,
                seed_count=2,
                seed_start=1290,
                workers=1,
                bootstrap_samples=100,
            )
            self.assertIn(
                decision["verdict"],
                {"INVALID-SUITE", "M9A-GO", "M9A-PARTIAL-GO", "M9A-NO-GO"},
            )
            self.assertEqual(
                {
                    "run_summary.csv",
                    "scenario_summary.csv",
                    "paired_effects.csv",
                    "suite_config.json",
                    "trace_manifest.json",
                    "decision.json",
                    "milestone9a_report.md",
                },
                {path.name for path in output.iterdir()},
            )
            repeated = reanalyze_topology_decision_suite(
                output, bootstrap_samples=100
            )
            self.assertEqual(repeated["verdict"], decision["verdict"])

    def test_m9a5_enumerates_hidden_assignments_without_fault_identity(self) -> None:
        config = ExperimentConfig(
            secondary_mode_agent_count=4,
            secondary_mode_offset=(5.0, -4.0),
            secondary_mode_start_step=5,
            secondary_mode_end_step=20,
        )
        reference = AssignmentBayesFilter(config)
        self.assertEqual(reference.assignment_mask.shape, (70, 8))
        np.testing.assert_array_equal(
            np.sum(reference.assignment_mask, axis=1), np.full(70, 4)
        )
        self.assertAlmostEqual(reference.normalized_assignment_entropy, 1.0)

    def test_m9a5_observer_does_not_change_frozen_trajectory(self) -> None:
        config = ExperimentConfig(
            steps=40,
            change_step=20,
            ci_grid_points=5,
            secondary_mode_agent_count=4,
            secondary_mode_offset=(5.0, -4.0),
            secondary_mode_start_step=5,
            secondary_mode_end_step=24,
            topology_partition_step=10,
            topology_partition_duration=18,
        )
        frozen = run_trial(config, "flocking_topology_resilient", 333)
        observed_steps: list[int] = []
        observed = run_trial(
            config,
            "flocking_topology_resilient",
            333,
            step_observer=lambda payload: observed_steps.append(int(payload["step"])),
        )
        self.assertEqual(observed_steps, list(range(config.steps)))
        self.assertEqual(
            [record.to_dict() for record in frozen],
            [record.to_dict() for record in observed],
        )
        summary, _ = run_oracle_floor_trial(config, 333)
        self.assertTrue(np.isfinite(float(summary["observer_loss"])))
        self.assertTrue(np.isfinite(float(summary["global_loss"])))

    def test_small_oracle_floor_suite_and_reanalysis(self) -> None:
        config = ExperimentConfig(
            steps=40,
            change_step=20,
            n_agents=8,
            neighbor_limit=3,
            recovery_window=3,
            ci_grid_points=5,
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            diagnosis = run_oracle_floor_suite(
                config,
                output,
                seed_count=2,
                seed_start=1390,
                workers=1,
                bootstrap_samples=100,
            )
            self.assertTrue(diagnosis["non_promotional"])
            self.assertTrue(diagnosis["original_m9a_verdict_unchanged"])
            self.assertEqual(
                {
                    "run_summary.csv",
                    "scenario_summary.csv",
                    "transfer_effects.csv",
                    "gap_effects.csv",
                    "suite_config.json",
                    "trace_manifest.json",
                    "decision.json",
                    "milestone9a5_report.md",
                },
                {path.name for path in output.iterdir()},
            )
            repeated = reanalyze_oracle_floor_suite(
                output, bootstrap_samples=100
            )
            self.assertEqual(
                repeated["diagnostic_conclusion"],
                diagnosis["diagnostic_conclusion"],
            )

    def test_m9a6_residual_mass_distinguishes_model_mismatch(self) -> None:
        config = ExperimentConfig(
            steps=25,
            change_step=12,
            recovery_window=3,
            n_agents=4,
            neighbor_limit=2,
            secondary_mode_agent_count=2,
            secondary_mode_offset=(5.0, -4.0),
            secondary_mode_start_step=4,
            secondary_mode_end_step=20,
        )
        mismatched_config = ExperimentConfig(
            **{
                **config.to_dict(),
                "m9a6_override_declared_model": True,
                "m9a6_model_secondary_count": 3,
                "m9a6_model_secondary_offset": (5.0, -4.0),
                "m9a6_model_secondary_start_step": 4,
                "m9a6_model_secondary_end_step": 20,
            }
        )
        exact = MissingEvidenceController(config)
        mismatched = MissingEvidenceController(mismatched_config)
        truth = np.asarray(config.target_initial_state, dtype=float)
        transition = np.asarray(
            [[1.0, 0.0, config.dt, 0.0], [0.0, 1.0, 0.0, config.dt],
             [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]],
            dtype=float,
        )
        covariance = tuple(np.eye(2, dtype=float) * 0.09 for _ in range(4))
        visible = np.ones(4, dtype=bool)
        exact_residuals: list[float] = []
        mismatch_residuals: list[float] = []
        for step in range(config.steps - 1):
            if step > 0:
                truth = transition @ truth
            observations = np.tile(truth[:2], (4, 1))
            if 4 <= step < 20:
                observations[:2] += np.asarray((5.0, -4.0))
            exact_residuals.append(
                exact.update(step, observations, covariance, visible).residual_mass
            )
            mismatch_residuals.append(
                mismatched.update(
                    step, observations, covariance, visible
                ).residual_mass
            )
        self.assertLess(float(np.mean(exact_residuals)), 0.03)
        self.assertGreater(float(np.mean(mismatch_residuals)), 0.20)
        self.assertGreater(max(mismatch_residuals), max(exact_residuals) + 0.50)
        before_outage = mismatched.residual_mass
        truth = transition @ truth
        mismatched.update(
            config.steps - 1,
            np.tile(truth[:2], (4, 1)),
            covariance,
            np.zeros(4, dtype=bool),
        )
        self.assertEqual(mismatched.residual_mass, before_outage)

    def test_m9a6_output_overlay_preserves_m9a_motion(self) -> None:
        config = ExperimentConfig(
            steps=40,
            change_step=20,
            recovery_window=3,
            ci_grid_points=5,
            secondary_mode_agent_count=4,
            secondary_mode_offset=(5.0, -4.0),
            secondary_mode_start_step=5,
            secondary_mode_end_step=24,
            topology_partition_step=10,
            topology_partition_duration=18,
        )
        shadow = MissingEvidenceShadowCollector(config)
        frozen = run_trial(
            config,
            "flocking_topology_resilient",
            341,
            step_observer=shadow,
        )
        candidate = run_trial(config, M9A6_ALGORITHM, 341)
        for left, right, shadow_row in zip(frozen, candidate, shadow.rows):
            self.assertEqual(left.target_x, right.target_x)
            self.assertEqual(left.target_y, right.target_y)
            self.assertEqual(left.mean_sensor_speed, right.mean_sensor_speed)
            self.assertEqual(left.spatial_diversity, right.spatial_diversity)
            self.assertEqual(left.messages, right.messages)
            self.assertEqual(left.topology_component_epoch, right.topology_component_epoch)
            self.assertEqual(
                right.output_decision_loss, shadow_row["decision_loss"]
            )
            self.assertEqual(
                right.missing_evidence_residual_mass,
                shadow_row["residual_mass"],
            )
        self.assertTrue(
            any(record.missing_evidence_residual_mass > 0.0 for record in candidate)
        )

    def test_small_missing_evidence_suite_and_reanalysis(self) -> None:
        config = ExperimentConfig(
            steps=40,
            change_step=20,
            n_agents=8,
            neighbor_limit=3,
            recovery_window=3,
            ci_grid_points=5,
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            decision = run_missing_evidence_suite(
                config,
                output,
                seed_count=2,
                seed_start=1395,
                workers=1,
                bootstrap_samples=100,
                phase="training",
            )
            self.assertIn(
                decision["verdict"],
                {"INVALID-SUITE", "M9A6-TRAINING-PASS", "M9A6-TRAINING-FAIL"},
            )
            self.assertTrue(decision["original_m9a_verdict_unchanged"])
            self.assertEqual(
                {
                    "run_summary.csv",
                    "scenario_summary.csv",
                    "paired_effects.csv",
                    "suite_config.json",
                    "trace_manifest.json",
                    "decision.json",
                    "milestone9a6_report.md",
                },
                {path.name for path in output.iterdir()},
            )
            repeated = reanalyze_missing_evidence_suite(
                output, bootstrap_samples=100
            )
            self.assertEqual(repeated["verdict"], decision["verdict"])

    def test_m9a7_separates_fresh_measurements_from_belief_admission(self) -> None:
        config = ExperimentConfig(
            steps=20,
            change_step=10,
            recovery_window=3,
            n_agents=4,
            neighbor_limit=2,
            secondary_mode_agent_count=2,
            secondary_mode_offset=(5.0, -4.0),
            secondary_mode_start_step=0,
            secondary_mode_end_step=15,
        )
        controller = AdmissionAwareController(config)
        observations = np.zeros((4, 2), dtype=float)
        observations[2:] += np.asarray((5.0, -4.0))
        result = controller.update(
            0,
            observations,
            tuple(np.eye(2, dtype=float) for _ in range(4)),
            component_visible=np.ones(4, dtype=bool),
            available=np.ones(4, dtype=bool),
            operational=np.ones(4, dtype=bool),
            raw_trusted=np.ones(4, dtype=bool),
            source_quarantined=np.zeros(4, dtype=bool),
            belief_share_eligible=np.asarray([True, True, False, False]),
            belief_admitted=np.asarray([True, True, False, False]),
        )
        self.assertEqual(result.measurement_eligible_agents, 4)
        self.assertEqual(result.belief_admitted_agents, 2)
        self.assertEqual(result.belief_censored_measurement_agents, 2)
        self.assertEqual(result.robust_excluded_measurement_agents, 0)

        excluded = controller.update(
            1,
            observations,
            tuple(np.eye(2, dtype=float) for _ in range(4)),
            component_visible=np.ones(4, dtype=bool),
            available=np.ones(4, dtype=bool),
            operational=np.ones(4, dtype=bool),
            raw_trusted=np.asarray([True, True, True, False]),
            source_quarantined=np.asarray([False, False, False, True]),
            belief_share_eligible=np.asarray([True, True, True, False]),
            belief_admitted=np.asarray([True, True, True, False]),
        )
        self.assertGreater(excluded.admission_residual_mass, 0.0)
        self.assertGreater(excluded.excluded_secondary_probability, 0.0)

    def test_m9a7_covariance_floor_blocks_understatement(self) -> None:
        config = ExperimentConfig(n_agents=4, neighbor_limit=2)
        repaired, changed, floor = floor_reported_covariances(
            config,
            (
                np.eye(2),
                np.eye(2),
                np.eye(2),
                np.eye(2) * 0.01,
            ),
            np.ones(4, dtype=bool),
        )
        self.assertEqual(changed, 1)
        self.assertAlmostEqual(floor, config.m9a7_covariance_floor_fraction)
        self.assertGreaterEqual(float(np.min(np.linalg.eigvalsh(repaired[3]))), floor)

    def test_targeted_failure_selects_declared_fault_population(self) -> None:
        config = ExperimentConfig(
            n_agents=6,
            neighbor_limit=2,
            strategic_agent_count=2,
            agent_failure_count=2,
            agent_failure_step=10,
            agent_recovery_step=20,
            agent_failure_fault_type=4,
        )
        scenario = make_scenario(config, 344)
        failed = np.flatnonzero(~scenario.agent_active[12])
        self.assertEqual(len(failed), 2)
        self.assertTrue(np.all(scenario.agent_fault_types[failed] == 4))

    def test_m9a7_overlay_matches_shadow_and_preserves_motion(self) -> None:
        config = ExperimentConfig(
            steps=40,
            change_step=20,
            recovery_window=3,
            ci_grid_points=5,
            secondary_mode_agent_count=4,
            secondary_mode_offset=(5.0, -4.0),
            secondary_mode_start_step=5,
            secondary_mode_end_step=24,
            agent_failure_count=2,
            agent_failure_step=10,
            agent_recovery_step=26,
        )
        shadow = AdmissionEvidenceShadowCollector(config)
        frozen = run_trial(config, "flocking_topology_resilient", 345, step_observer=shadow)
        candidate = run_trial(config, M9A7_ALGORITHM, 345)
        for left, right, shadow_row in zip(frozen, candidate, shadow.rows):
            self.assertEqual(left.mean_sensor_speed, right.mean_sensor_speed)
            self.assertEqual(left.spatial_diversity, right.spatial_diversity)
            self.assertEqual(right.output_decision_loss, shadow_row["decision_loss"])
        self.assertTrue(
            any(record.measurement_eligible_agents > 0 for record in candidate)
        )

    def test_small_admission_suite_and_power_calculation(self) -> None:
        self.assertEqual(required_seed_count(0.02, 0.95), 149)
        config = ExperimentConfig(
            steps=40,
            change_step=20,
            n_agents=8,
            neighbor_limit=3,
            recovery_window=3,
            ci_grid_points=5,
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            decision = run_admission_evidence_suite(
                config,
                output,
                seed_count=2,
                seed_start=1595,
                workers=1,
                bootstrap_samples=100,
                phase="training",
            )
            self.assertIn(
                decision["verdict"],
                {"INVALID-SUITE", "M9A7-TRAINING-PASS", "M9A7-TRAINING-FAIL"},
            )
            self.assertEqual(
                {
                    "run_summary.csv",
                    "scenario_summary.csv",
                    "paired_effects.csv",
                    "suite_config.json",
                    "trace_manifest.json",
                    "decision.json",
                    "milestone9a7_report.md",
                },
                {path.name for path in output.iterdir()},
            )
            repeated = reanalyze_admission_evidence_suite(
                output, bootstrap_samples=100
            )
            self.assertEqual(repeated["verdict"], decision["verdict"])

    def test_m9c_uses_assignment_uncertainty_for_physical_actions(self) -> None:
        config = ExperimentConfig(
            steps=30,
            change_step=15,
            recovery_window=3,
            ci_grid_points=5,
            target_change_mode="none",
            secondary_mode_agent_count=4,
            secondary_mode_offset=(5.0, -4.0),
            secondary_mode_start_step=5,
            secondary_mode_end_step=24,
        )
        broad = run_trial(config, M9C_ROUND_ROBIN_ALGORITHM, 346)
        receding = run_trial(config, M9C_RECEDING_ALGORITHM, 346)
        self.assertIn(M9C_ROUND_ROBIN_ALGORITHM, ALGORITHMS)
        self.assertIn(M9C_RECEDING_ALGORITHM, ALGORITHMS)
        self.assertTrue(any(row.investigation_requested for row in broad))
        self.assertTrue(
            any(row.investigation_motion_action == "spread" for row in broad)
        )
        self.assertGreater(
            sum(row.investigation_planning_sequences for row in receding), 0
        )
        self.assertEqual(len(broad), len(receding))

    def test_small_m9c_suite_and_reanalysis(self) -> None:
        self.assertEqual(required_tail_seeds(0.02, 0.95), 149)
        config = ExperimentConfig(
            steps=20,
            change_step=10,
            recovery_window=3,
            ci_grid_points=5,
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            decision = run_integration_suite(
                config,
                output,
                seed_count=2,
                seed_start=17980,
                workers=1,
                bootstrap_samples=100,
                phase="training",
            )
            self.assertIn(
                decision["verdict"],
                {
                    "M9C-INVALID",
                    "M9C-TRAINING-FAIL",
                    "M9C-TRAINING-PARTIAL",
                    "M9C-TRAINING-PASS",
                },
            )
            self.assertEqual(
                {
                    "run_summary.csv",
                    "scenario_summary.csv",
                    "paired_effects.csv",
                    "suite_config.json",
                    "trace_manifest.json",
                    "decision.json",
                    "milestone9c_report.md",
                },
                {path.name for path in output.iterdir()},
            )
            repeated = reanalyze_integration_suite(
                output, bootstrap_samples=100
            )
            self.assertEqual(repeated["verdict"], decision["verdict"])

    def test_m10a_trust_isolates_understated_colluders(self) -> None:
        config = ExperimentConfig(
            steps=20,
            change_step=10,
            target_initial_state=(0.0, 0.0, 0.0, 0.0),
            n_agents=8,
            neighbor_limit=3,
            secondary_mode_agent_count=3,
            secondary_mode_offset=(5.0, -4.0),
            secondary_mode_start_step=0,
            secondary_mode_end_step=15,
        )
        controller = AdversarialTrustController(config, "combined")
        masks = np.ones(config.n_agents, dtype=bool)
        quarantined = np.zeros(config.n_agents, dtype=bool)
        observations = np.zeros((config.n_agents, 2), dtype=float)
        observations[2:5] += np.asarray(config.secondary_mode_offset)
        observations[5:] += np.asarray((3.5, 5.0))
        covariances = tuple(
            np.eye(2, dtype=float) * (0.05 if index >= 5 else 1.0)
            for index in range(config.n_agents)
        )
        result = None
        for step in range(4):
            result = controller.update(
                step,
                observations,
                covariances,
                component_visible=masks,
                available=masks,
                operational=masks,
                raw_trusted=masks,
                source_quarantined=quarantined,
                belief_share_eligible=masks,
                belief_admitted=masks,
            )
        assert result is not None
        self.assertTrue(np.all(result.trust_scores[5:] < 0.50))
        self.assertTrue(np.all(result.trust_scores[:5] > 0.99))
        self.assertEqual(result.strong_floor_evidence_agents, 3)
        self.assertTrue(np.isfinite(result.posterior.predicted_risk))

    def test_small_m10a_suite_and_reanalysis(self) -> None:
        config = ExperimentConfig(
            steps=30,
            change_step=15,
            recovery_window=3,
            ci_grid_points=5,
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            decision = run_adversarial_trust_suite(
                config,
                output,
                seed_count=2,
                seed_start=19980,
                workers=1,
                bootstrap_samples=100,
                phase="training",
            )
            self.assertIn(
                decision["verdict"],
                {
                    "M10A-INVALID",
                    "M10A-TRAINING-FAIL",
                    "M10A-TRAINING-PASS",
                },
            )
            self.assertEqual(
                {
                    "run_summary.csv",
                    "scenario_summary.csv",
                    "paired_effects.csv",
                    "suite_config.json",
                    "trace_manifest.json",
                    "decision.json",
                    "milestone10a_report.md",
                },
                {path.name for path in output.iterdir()},
            )
            repeated = reanalyze_adversarial_trust_suite(
                output, bootstrap_samples=100
            )
            self.assertEqual(repeated["verdict"], decision["verdict"])


class OutputPolicyTests(unittest.TestCase):
    @staticmethod
    def flocks(first_weight: float = 0.5) -> list[HypothesisFlock]:
        return [
            HypothesisFlock(
                flock_id=0,
                members=(0, 1, 2, 3),
                state=np.array([0.0, 0.0, 0.2, 0.0]),
                covariance=np.eye(4),
                weight=first_weight,
            ),
            HypothesisFlock(
                flock_id=1,
                members=(4, 5, 6, 7),
                state=np.array([5.0, -4.0, 0.2, 0.0]),
                covariance=np.eye(4),
                weight=1.0 - first_weight,
            ),
        ]

    def test_active_policy_selects_decisive_mode_without_truth(self) -> None:
        controller = HypothesisOutputController(ExperimentConfig(), "active")
        decision = controller.decide(self.flocks(0.625))
        self.assertEqual(decision.action, "select")
        self.assertEqual(decision.selected_flock_id, 0)

    def test_active_policy_investigates_then_defers_on_equal_modes(self) -> None:
        config = ExperimentConfig(
            output_ambiguity_persistence_steps=1,
            output_investigation_horizon=2,
        )
        controller = HypothesisOutputController(config, "active")
        self.assertEqual(controller.decide(self.flocks()).action, "investigate")
        self.assertEqual(controller.decide(self.flocks()).action, "investigate")
        decision = controller.decide(self.flocks())
        self.assertEqual(decision.action, "defer")
        self.assertIsNone(decision.selected_flock_id)

    def test_active_policy_ignores_one_cycle_ambiguity(self) -> None:
        controller = HypothesisOutputController(ExperimentConfig(), "active")
        self.assertEqual(controller.decide(self.flocks()).action, "select")
        single = [self.flocks()[0]]
        self.assertEqual(controller.decide(single).action, "select")

    def test_active_policy_aggregates_nearby_support_fragments(self) -> None:
        flocks = [
            HypothesisFlock(0, (0, 1, 2), np.array([0.0, 0.0, 0.0, 0.0]), np.eye(4), 0.375),
            HypothesisFlock(1, (3, 4), np.array([1.0, 0.2, 0.0, 0.0]), np.eye(4), 0.25),
            HypothesisFlock(2, (5, 6, 7), np.array([5.0, -4.0, 0.0, 0.0]), np.eye(4), 0.375),
        ]
        controller = HypothesisOutputController(ExperimentConfig(), "active")
        decision = controller.decide(flocks)
        self.assertEqual(decision.action, "select")
        self.assertIn(decision.selected_flock_id, {0, 1})
        self.assertAlmostEqual(decision.confidence, 0.25)


class ExperimentTests(unittest.TestCase):
    @staticmethod
    def small_config() -> ExperimentConfig:
        return ExperimentConfig(
            steps=30,
            change_step=15,
            n_agents=4,
            neighbor_limit=2,
            seeds=[7],
            recovery_window=3,
            ci_grid_points=7,
        )

    def test_scenario_replay_is_deterministic(self) -> None:
        config = self.small_config()
        first = make_scenario(config, 11)
        second = make_scenario(config, 11)
        np.testing.assert_allclose(first.truth, second.truth)
        np.testing.assert_allclose(first.measurement_normals, second.measurement_normals)
        np.testing.assert_array_equal(first.agent_fault_types, second.agent_fault_types)
        np.testing.assert_array_equal(
            first.communication_available, second.communication_available
        )
        self.assertEqual(
            scenario_fingerprint(config, 11), scenario_fingerprint(config, 11)
        )

    def test_realism_trace_changes_with_seed_and_materializes_disturbances(self) -> None:
        config = self.small_config()
        config.communication_burst_entry_probability = 0.2
        config.communication_burst_recovery_probability = 0.3
        config.communication_delay_steps = 1
        config.communication_delay_jitter_steps = 2
        config.agent_clock_offset_max_steps = 1
        config.sensor_noise_scale_min = 0.6
        config.sensor_noise_scale_max = 1.8
        config.strategic_agent_count = 1
        config.agent_failure_count = 1
        config.agent_failure_step = 8
        config.agent_recovery_step = 20
        config.topology_partition_step = 5
        config.topology_partition_duration = 10
        config.validate()
        scenario = make_scenario(config, 17)
        self.assertTrue(np.any(~scenario.communication_available))
        self.assertGreater(int(np.max(scenario.message_ages)), 0)
        self.assertGreater(float(np.ptp(scenario.sensor_noise_scales)), 0.0)
        self.assertEqual(int(np.sum(scenario.agent_fault_types == 4)), 1)
        self.assertEqual(int(np.sum(~scenario.agent_active[10])), 1)
        self.assertTrue(np.all(scenario.agent_active[22]))
        self.assertNotEqual(
            scenario_fingerprint(config, 17), scenario_fingerprint(config, 18)
        )

    def test_nonlinear_range_bearing_trial_is_finite(self) -> None:
        config = self.small_config()
        config.measurement_model = "range_bearing"
        config.sensor_noise_scale_min = 0.7
        config.sensor_noise_scale_max = 1.5
        records = run_trial(config, "flocking_robust_active", 31)
        self.assertTrue(all(np.isfinite(record.team_position_error) for record in records))
        self.assertTrue(all(np.isfinite(record.mean_nees) for record in records))

    def test_fault_identity_is_seeded_and_count_preserving(self) -> None:
        config = self.small_config()
        config.biased_agent_count = 1
        config.byzantine_agent_count = 1
        config.secondary_mode_agent_count = 2
        first = make_scenario(config, 21)
        self.assertEqual(np.bincount(first.agent_fault_types, minlength=4).tolist(), [0, 1, 1, 2])
        assignments = {
            tuple(make_scenario(config, seed).agent_fault_types.tolist())
            for seed in range(21, 31)
        }
        self.assertGreater(len(assignments), 1)

    def test_all_algorithms_produce_complete_finite_trials(self) -> None:
        config = self.small_config()
        for algorithm in ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                records = run_trial(config, algorithm, 7)
                self.assertEqual(len(records), config.steps)
                self.assertTrue(all(np.isfinite(record.team_position_error) for record in records))
                self.assertTrue(all(0.0 <= record.coverage95_rate <= 1.0 for record in records))
                if algorithm == "independent_kf":
                    self.assertEqual(sum(record.messages for record in records), 0)
                else:
                    self.assertGreater(sum(record.messages for record in records), 0)

    def test_runner_writes_replayable_artifacts(self) -> None:
        config = self.small_config()
        config.algorithms = ["independent_kf", "flocking_adaptive_momentum"]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            summary = run_experiment(config, output)
            self.assertEqual(len(summary), 2)
            expected = {
                "config.json",
                "environment.json",
                "summary.json",
                "summary.csv",
                "run_summary.csv",
                "per_step_metrics.csv",
                "comparison.svg",
                "error_timeseries.svg",
            }
            self.assertEqual(expected, {path.name for path in output.iterdir()})
            saved_config = json.loads((output / "config.json").read_text(encoding="utf-8"))
            self.assertEqual(saved_config["seeds"], [7])
            environment = json.loads((output / "environment.json").read_text(encoding="utf-8"))
            self.assertEqual(environment["platform_version"], "0.12.0")
            with (output / "per_step_metrics.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2 * config.steps)

    def test_small_decision_suite_writes_paired_evidence(self) -> None:
        config = self.small_config()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            decision = run_decision_suite(
                config,
                output,
                seed_count=3,
                seed_start=100,
                workers=1,
                bootstrap_samples=100,
                scenario_names=["abrupt_change", "mixed_dropout"],
            )
            self.assertIn(decision["verdict"], {"GO", "NO-GO", "INCONCLUSIVE"})
            self.assertEqual(
                {
                    "run_summary.csv",
                    "scenario_summary.csv",
                    "paired_effects.csv",
                    "suite_config.json",
                    "decision.json",
                    "decision_report.md",
                },
                {path.name for path in output.iterdir()},
            )
            with (output / "run_summary.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2 * 3 * 3)

    def test_small_robust_suite_writes_milestone6_evidence(self) -> None:
        config = self.small_config()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            decision = run_robust_decision_suite(
                config,
                output,
                seed_count=2,
                seed_start=300,
                workers=1,
                bootstrap_samples=100,
            )
            self.assertIn(decision["verdict"], {"GO", "NO-GO", "INCONCLUSIVE"})
            self.assertEqual(
                {
                    "run_summary.csv",
                    "scenario_summary.csv",
                    "paired_effects.csv",
                    "suite_config.json",
                    "decision.json",
                    "milestone6_report.md",
                },
                {path.name for path in output.iterdir()},
            )
            with (output / "run_summary.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 7 * 2 * 2)

    def test_small_guarded_suite_writes_milestone5_evidence(self) -> None:
        config = self.small_config()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            decision = run_guarded_decision_suite(
                config,
                output,
                seed_count=3,
                seed_start=200,
                workers=1,
                bootstrap_samples=100,
                scenario_names=["abrupt_change", "mixed_dropout"],
            )
            self.assertIn(decision["verdict"], {"GO", "NO-GO", "INCONCLUSIVE"})
            self.assertEqual(
                {
                    "run_summary.csv",
                    "scenario_summary.csv",
                    "paired_effects.csv",
                    "suite_config.json",
                    "decision.json",
                    "milestone5_report.md",
                },
                {path.name for path in output.iterdir()},
            )
            with (output / "run_summary.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2 * 3 * 3)

    def test_small_output_suite_writes_milestone7_evidence(self) -> None:
        config = self.small_config()
        config.n_agents = 8
        config.neighbor_limit = 3
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            decision = run_output_decision_suite(
                config,
                output,
                seed_count=2,
                seed_start=400,
                workers=1,
                bootstrap_samples=100,
            )
            self.assertIn(decision["verdict"], {"GO", "NO-GO", "INCONCLUSIVE"})
            self.assertEqual(
                {
                    "run_summary.csv",
                    "scenario_summary.csv",
                    "paired_effects.csv",
                    "suite_config.json",
                    "decision.json",
                    "milestone7_report.md",
                },
                {path.name for path in output.iterdir()},
            )
            with (output / "run_summary.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 8 * 5 * 2)

    def test_small_realism_suite_writes_milestone8_evidence(self) -> None:
        config = self.small_config()
        config.n_agents = 8
        config.neighbor_limit = 3
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            decision = run_realism_decision_suite(
                config,
                output,
                seed_count=2,
                seed_start=500,
                workers=1,
                bootstrap_samples=100,
            )
            self.assertIn(decision["verdict"], {"GO", "PARTIAL-GO", "NO-GO"})
            self.assertIn("investigation_reduces_decision_loss", decision["causal_gates"])
            self.assertEqual(
                {
                    "run_summary.csv",
                    "scenario_summary.csv",
                    "paired_effects.csv",
                    "suite_config.json",
                    "trace_manifest.json",
                    "decision.json",
                    "milestone8_report.md",
                },
                {path.name for path in output.iterdir()},
            )
            manifest = json.loads(
                (output / "trace_manifest.json").read_text(encoding="utf-8")
            )
            self.assertTrue(manifest["replay_verified"])
            self.assertEqual(len(manifest["entries"]), 10 * 2)
            with (output / "run_summary.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 10 * 4 * 2)


class EndogenousAmbiguityTests(unittest.TestCase):
    def test_passive_is_unidentifiable_but_active_oracle_resolves(self) -> None:
        config = AmbiguityAssayConfig()
        passive = run_ambiguity_assay(config, "passive", 71, dose=0.0)
        oracle = run_ambiguity_assay(config, "information_oracle", 71, dose=1.0)
        self.assertFalse(passive.resolved)
        self.assertAlmostEqual(passive.final_truth_probability, 0.5)
        self.assertEqual(passive.mean_discriminability, 0.0)
        self.assertTrue(oracle.resolved)
        self.assertLess(oracle.resolution_steps, config.steps)
        self.assertGreater(oracle.mean_discriminability, 0.0)
        self.assertLess(oracle.total_decision_loss, passive.total_decision_loss)

    def test_assay_trace_and_run_are_deterministic(self) -> None:
        config = AmbiguityAssayConfig()
        first = run_ambiguity_assay(config, "round_robin", 73, dose=0.25)
        second = run_ambiguity_assay(config, "round_robin", 73, dose=0.25)
        self.assertEqual(first, second)
        self.assertEqual(
            assay_fingerprint(config, 73), assay_fingerprint(config, 73)
        )
        self.assertNotEqual(
            assay_fingerprint(config, 73), assay_fingerprint(config, 74)
        )

    def test_small_ambiguity_suite_and_reanalysis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            decision = run_ambiguity_decision_suite(
                AmbiguityAssayConfig(),
                output,
                seed_count=5,
                seed_start=900,
                workers=1,
                bootstrap_samples=100,
            )
            self.assertEqual(decision["verdict"], "POSITIVE-CONTROL-PASS")
            self.assertTrue(all(decision["gates"].values()))
            self.assertEqual(
                {
                    "run_summary.csv",
                    "policy_summary.csv",
                    "paired_effects.csv",
                    "suite_config.json",
                    "trace_manifest.json",
                    "decision.json",
                    "milestone8_1_report.md",
                },
                {path.name for path in output.iterdir()},
            )
            repeated = reanalyze_ambiguity_decision_suite(
                output, bootstrap_samples=100
            )
            self.assertEqual(repeated["verdict"], decision["verdict"])


class DecisionRelevantActiveSensingTests(unittest.TestCase):
    def test_passive_multi_hypothesis_task_is_unidentifiable(self) -> None:
        config = ActiveSensingConfig()
        scenario = DEFAULT_ACTIVE_SENSING_SCENARIOS[0]
        passive = run_active_sensing_trial(config, scenario, "passive", 1201)
        self.assertFalse(passive.resolved)
        self.assertEqual(passive.probe_actions, 0)
        self.assertEqual(passive.spread_actions, 0)
        self.assertAlmostEqual(
            passive.final_truth_probability,
            scenario.prior_probabilities[passive.truth_mode],
        )

    def test_planner_and_trace_are_deterministic(self) -> None:
        config = ActiveSensingConfig()
        scenario = DEFAULT_ACTIVE_SENSING_SCENARIOS[1]
        prior = np.asarray(scenario.prior_probabilities, dtype=float)
        positions = np.zeros((config.n_agents, 2), dtype=float)
        velocities = np.zeros_like(positions)
        first = choose_active_sensing_action(
            config, scenario, prior, positions, velocities, 2
        )
        second = choose_active_sensing_action(
            config, scenario, prior, positions, velocities, 2
        )
        self.assertEqual(first, second)
        self.assertEqual(first[1], (len(scenario.hypothesis_positions) + 2) ** 2)
        self.assertEqual(
            active_sensing_fingerprint(config, scenario, 1202),
            active_sensing_fingerprint(config, scenario, 1202),
        )
        self.assertNotEqual(
            active_sensing_fingerprint(config, scenario, 1202),
            active_sensing_fingerprint(config, scenario, 1203),
        )

    def test_small_m9b_suite_and_reanalysis(self) -> None:
        config = ActiveSensingConfig(
            steps=5,
            n_agents=4,
            probe_agent_count=1,
            planning_samples=3,
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            decision = run_active_sensing_decision_suite(
                config,
                output,
                seed_count=3,
                seed_start=1250,
                workers=1,
                bootstrap_samples=100,
                scenario_names=("triad_uniform",),
            )
            self.assertIn(
                decision["verdict"],
                {"INVALID-ASSAY", "M9B-GO", "M9B-PARTIAL-GO", "M9B-NO-GO"},
            )
            self.assertEqual(
                {
                    "run_summary.csv",
                    "scenario_summary.csv",
                    "policy_summary.csv",
                    "paired_effects.csv",
                    "suite_config.json",
                    "trace_manifest.json",
                    "decision.json",
                    "milestone9b_report.md",
                },
                {path.name for path in output.iterdir()},
            )
            repeated = reanalyze_active_sensing_decision_suite(
                output, bootstrap_samples=100
            )
            self.assertEqual(repeated["verdict"], decision["verdict"])


class MomentumMechanismTests(unittest.TestCase):
    def test_small_mechanism_study_writes_diagnostics(self) -> None:
        config = ExperimentConfig(
            steps=30,
            change_step=15,
            n_agents=4,
            neighbor_limit=2,
            recovery_window=3,
            ci_grid_points=7,
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            analysis = run_momentum_mechanism_study(
                config,
                output,
                seed_count=2,
                seed_start=950,
                rhos=(0.0, 0.72),
                scenario_names=("no_change", "abrupt_change"),
                workers=1,
            )
            self.assertIn(
                analysis["verdict"],
                {"GEOMETRY-MECHANISM-SUPPORTED", "MECHANISM-UNRESOLVED"},
            )
            self.assertEqual(
                {
                    "run_summary.csv",
                    "cell_summary.csv",
                    "paired_mechanism.csv",
                    "suite_config.json",
                    "mechanism.json",
                    "momentum_mechanism_report.md",
                },
                {path.name for path in output.iterdir()},
            )


class ExternalReplayBoundaryTests(unittest.TestCase):
    @staticmethod
    def _write_synthetic_dataset(root: Path) -> None:
        barcodes = np.asarray(
            [[subject, 100 + subject] for subject in range(1, 21)],
            dtype=float,
        )
        landmarks = np.asarray(
            [
                [subject, float(subject), 0.5 * subject, 0.01, 0.01]
                for subject in range(6, 21)
            ],
            dtype=float,
        )
        np.savetxt(root / "Barcodes.dat", barcodes)
        np.savetxt(root / "Landmark_Groundtruth.dat", landmarks)
        for robot in range(1, 6):
            groundtruth = np.asarray(
                [[0.0, 0.0, 0.0, 0.0], [1.0, 0.1, 0.0, 0.0]]
            )
            odometry = np.asarray(
                [[0.0, 0.1, 0.0], [1.0, 0.1, 0.0]]
            )
            if robot == 1:
                odometry = odometry[::-1]
            measurements = np.asarray(
                [[0.5, 106.0, 6.0, 0.0]]
            )
            np.savetxt(
                root / f"Robot{robot}_Groundtruth.dat",
                groundtruth,
            )
            np.savetxt(
                root / f"Robot{robot}_Odometry.dat",
                odometry,
            )
            np.savetxt(
                root / f"Robot{robot}_Measurement.dat",
                measurements,
            )

    def test_canonicalizer_stably_repairs_without_dropping_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            target = root / "canonical"
            source.mkdir()
            self._write_synthetic_dataset(source)
            manifest = canonicalize_mrclam_dataset(source, target)
            self.assertEqual(manifest.total_timestamp_inversions, 1)
            self.assertEqual(manifest.input_rows, manifest.output_rows)
            self.assertTrue(verify_canonicalization(manifest))
            replay = load_mrclam_dataset(target)
            self.assertEqual(len(replay.robots), 5)
            self.assertEqual(replay.unknown_barcode_rows, 0)


class AccelerationAblationTests(unittest.TestCase):
    def test_measured_acceleration_filter_is_finite_and_causal(self) -> None:
        config = AccelerationConfig()
        filter_ = AccelerationLandmarkEKF(
            np.zeros(3),
            initial_velocity=0.0,
            initial_angular_velocity=0.0,
            config=config,
        )
        filter_.predict(1.0, 0.2)
        self.assertAlmostEqual(filter_.last_linear_acceleration, 2.0)
        self.assertAlmostEqual(filter_.last_angular_acceleration, 0.4)
        accepted, nis = filter_.update(
            np.asarray([2.0, 0.0]),
            measured_range=1.75,
            measured_bearing=-0.05,
        )
        self.assertTrue(accepted)
        self.assertGreaterEqual(nis, 0.0)
        self.assertTrue(np.all(np.isfinite(filter_.state)))
        self.assertTrue(
            np.all(np.linalg.eigvalsh(filter_.covariance) > 0.0)
        )

    def test_jerk_limiter_meets_isolated_assay_contract(self) -> None:
        clipped, limited = run_jerk_limiter_assay()
        self.assertTrue(clipped.finite)
        self.assertTrue(limited.finite)
        self.assertLessEqual(limited.peak_acceleration, 0.8 + 1e-12)
        self.assertLess(limited.peak_jerk, 0.5 * clipped.peak_jerk)
        self.assertLessEqual(
            limited.velocity_rmse - clipped.velocity_rmse,
            0.10,
        )


class FullLoopContractTests(unittest.TestCase):
    @staticmethod
    def _message(sender: str = "agent0", seq: int = 1) -> WireMessage:
        return WireMessage(
            run_id="contract-test",
            sender_id=sender,
            seq=seq,
            monotonic_ns=100,
            local_epoch=2,
            message_type="estimate",
            estimate=(1.0, 2.0, 0.1, -0.2),
            covariance=tuple(float(value) for value in np.eye(4).ravel()),
            trust_metadata={"minimum_peer_trust": 0.9},
            payload={"source": "camera"},
        ).accounted()

    def test_wire_round_trip_accounts_bytes_and_rejects_truth(self) -> None:
        message = self._message()
        record = message.to_record()
        self.assertEqual(record["wire_bytes"], len(json.dumps(
            record, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")))
        self.assertEqual(WireMessage.from_record(record), message)
        contaminated = WireMessage(
            run_id="bad",
            sender_id="agent0",
            seq=0,
            monotonic_ns=0,
            local_epoch=0,
            message_type="estimate",
            estimate=(0.0, 0.0, 0.0, 0.0),
            covariance=tuple(float(value) for value in np.eye(4).ravel()),
            trust_metadata={},
            payload={"ground_truth": [0.0, 0.0]},
        )
        with self.assertRaises(ValueError):
            contaminated.validate()

    def test_network_partition_and_attack_are_bounded_and_deterministic(self) -> None:
        manifest = NetworkFaultManifest(
            partition_start=2,
            partition_stop=5,
            partition_a=("agent0",),
            partition_b=("agent1",),
        )
        networks = [DeterministicNetwork(manifest, 7) for _ in range(2)]
        for network in networks:
            network.send(self._message(), ("agent1",), 3)
            self.assertEqual(network.receive(3), [])
        self.assertEqual(networks[0].events, networks[1].events)
        attack = AttackShim(
            AttackManifest(
                kind="adaptive_bounded",
                attacker_ids=("agent0",),
                start_step=0,
                stop_step=100,
                maximum_bias=0.2,
                maximum_bias_step=0.03,
            )
        )
        original = self._message()
        current = original
        for step in range(30):
            current = attack.apply(original, step)
        self.assertLessEqual(
            np.linalg.norm(
                np.asarray(current.estimate[:2]) - np.asarray(original.estimate[:2])
            ),
            0.2 + 1e-12,
        )

    def test_hash_chained_ledgers_enforce_domains(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            operational = HashChainedLedger(
                root / "operational.jsonl", OPERATIONAL_DOMAIN
            )
            operational.append(
                {
                    "domain": OPERATIONAL_DOMAIN,
                    "event_type": "diagnostic",
                    "process_id": "agent0",
                }
            )
            self.assertEqual(
                verify_ledger(
                    root / "operational.jsonl", OPERATIONAL_DOMAIN
                )["records"],
                1,
            )
            with self.assertRaises(ValueError):
                operational.append(
                    {
                        "domain": OPERATIONAL_DOMAIN,
                        "truth_state": [0.0, 0.0],
                    }
                )


class FullLoopHILTests(unittest.TestCase):
    def test_reference_loop_is_replay_deterministic(self) -> None:
        config = HILConfig(
            steps=40,
            seed_count=1,
            seed_start=27000,
            bootstrap_samples=100,
        )
        first, operational, truth = run_hil_trial(
            config,
            DEFAULT_HIL_SCENARIOS[0],
            "m10b_decentralized",
            27000,
            capture_trace=True,
        )
        second, _, _ = run_hil_trial(
            config,
            DEFAULT_HIL_SCENARIOS[0],
            "m10b_decentralized",
            27000,
        )
        self.assertEqual(first.replay_fingerprint, second.replay_fingerprint)
        self.assertEqual(len(operational), config.steps)
        self.assertEqual(len(truth), config.steps)
        self.assertEqual(first.collisions, 0)
        self.assertEqual(first.ownership_violations, 0)
        self.assertLessEqual(
            first.planner_messages, first.maximum_allowed_planner_messages
        )

    def test_small_hil_suite_writes_complete_screen(self) -> None:
        config = HILConfig(
            steps=40,
            seed_count=2,
            seed_start=27010,
            bootstrap_samples=100,
        )
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = run_full_loop_hil_suite(
                config,
                output,
                scenario_names=("stable",),
            )
            self.assertIn(
                result["verdict"],
                {"M13.1-HIL-PILOT-READY", "M13.1-HIL-NO-GO"},
            )
            self.assertFalse(result["external_physical_claim_authorized"])
            self.assertEqual(
                {
                    "artifact_manifest.json",
                    "audit_operational.json",
                    "audit_truth.json",
                    "decision.json",
                    "m13_1_report.md",
                    "paired_effects.csv",
                    "run_summary.csv",
                    "scenario_summary.csv",
                    "suite_config.json",
                },
                {path.name for path in output.iterdir()},
            )


class PhysicalEvidenceBoundaryTests(unittest.TestCase):
    @staticmethod
    def _synthetic_bundle(root: Path) -> Path:
        bundle = root / "synthetic_bundle"
        bundle.mkdir()
        manifest = {
            "schema_version": "m13.0.0",
            "run_id": "synthetic-run",
            "phase": "pilot",
            "evidence_class": "synthetic",
            "adapter": "loopback",
            "scenario": "stable",
            "arm": "m10b_decentralized",
            "block_id": "block0",
            "trial_date": "2026-01-01",
            "operational_process_ids": ["agent0", "planner", "safety"],
            "observer_robot_ids": ["agent0"],
            "recorder_host_ids": ["host0"],
            "scorer_process_id": "independent_scorer",
            "source_files": [
                {
                    "path": "raw/host0.mcap",
                    "kind": "operational_mcap",
                    "host_id": "host0",
                },
                {
                    "path": "raw/truth.mcap",
                    "kind": "truth_mcap",
                    "host_id": "truth-host",
                },
                {
                    "path": "raw/network.pcapng",
                    "kind": "pcap",
                    "host_id": "network-tap",
                },
            ],
            "clock_offsets": [
                {"process_id": "agent0", "offset_ms": 0.2},
                {"process_id": "independent_scorer", "offset_ms": -0.1},
            ],
            "attack": {
                "kind": "none",
                "attacker_ids": [],
                "start_ns": 0,
                "stop_ns": 0,
            },
        }
        (bundle / "manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )
        (bundle / "raw").mkdir()
        (bundle / "raw/host0.mcap").write_bytes(b"synthetic operational bag")
        (bundle / "raw/truth.mcap").write_bytes(b"synthetic truth bag")
        (bundle / "raw/network.pcapng").write_bytes(b"synthetic packet capture")
        operational = HashChainedLedger(
            bundle / "operational.jsonl", OPERATIONAL_DOMAIN
        )
        transport = HashChainedLedger(
            bundle / "transport.jsonl", OPERATIONAL_DOMAIN
        )
        safety = HashChainedLedger(
            bundle / "safety.jsonl", OPERATIONAL_DOMAIN
        )
        truth = HashChainedLedger(bundle / "truth.jsonl", SCORER_DOMAIN)
        for step in range(3):
            timestamp = step * 100_000_000
            operational.append(
                {
                    "domain": OPERATIONAL_DOMAIN,
                    "event_type": "estimate",
                    "process_id": "planner",
                    "monotonic_ns": timestamp,
                    "team_state": [float(step), 0.0, 1.0, 0.0],
                    "team_covariance": [
                        float(value) for value in (np.eye(4) * 0.2).ravel()
                    ],
                    "output_action": "select",
                    "trust_alert_agents": 0,
                    "ownership_violations": 0,
                    "maximum_allowed_planner_messages": 3,
                    "movement": 0.1,
                    "runtime_ms": 1.0,
                    "component_count": 1,
                }
            )
            for event in ("send", "receive"):
                transport.append(
                    {
                        "domain": OPERATIONAL_DOMAIN,
                        "event_type": "transport",
                        "event": event,
                        "channel": "planner",
                        "wire_bytes": 100,
                    }
                )
            safety.append(
                {
                    "domain": OPERATIONAL_DOMAIN,
                    "event_type": "safety",
                    "intervened": False,
                    "emergency_stop": False,
                    "collision": False,
                }
            )
            truth.append(
                TruthSample(
                    run_id="synthetic-run",
                    scorer_process_id="independent_scorer",
                    monotonic_ns=timestamp,
                    target_state=(float(step), 0.0, 1.0, 0.0),
                    robot_poses={"agent0": (0.0, 0.0, 0.0)},
                ).to_record()
            )
        seal_physical_bundle(bundle)
        return bundle

    def test_plan_and_synthetic_evidence_cannot_freeze_pilot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = create_physical_trial_plan(
                root / "plan",
                phase="pilot",
                blocks_per_scenario=1,
                trial_dates=("2026-01-01",),
            )
            self.assertEqual(plan["milestone"], "M13.2")
            with (root / "plan/trial_schedule.csv").open(
                encoding="utf-8"
            ) as handle:
                planned_rows = list(csv.DictReader(handle))
            self.assertEqual(len(planned_rows), 10 * 4)
            bundle = self._synthetic_bundle(root)
            score = score_physical_bundle(bundle)
            self.assertEqual(score.evidence_class, "synthetic")
            with self.assertRaisesRegex(ValueError, "genuine external"):
                run_physical_pilot(
                    [bundle],
                    root / "pilot",
                    project_root=Path(__file__).resolve().parents[1],
                )


if __name__ == "__main__":
    unittest.main()
