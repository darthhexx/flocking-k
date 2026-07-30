"""Configuration model for reproducible experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ExperimentConfig:
    """All parameters required to replay an experiment."""

    steps: int = 160
    dt: float = 1.0
    n_agents: int = 8
    seeds: list[int] = field(default_factory=lambda: [0, 1, 2])
    algorithms: list[str] = field(
        default_factory=lambda: [
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
        ]
    )

    # Target and sensor model.
    target_initial_state: tuple[float, float, float, float] = (0.0, 0.0, 0.8, 0.15)
    target_velocity_change: tuple[float, float] = (-0.9, 1.25)
    change_step: int = 80
    target_change_mode: str = "abrupt"
    gradual_change_duration: int = 20
    repeated_change_interval: int = 30
    truth_process_std: float = 0.025
    filter_process_variance: float = 0.035
    measurement_base_std: float = 0.65
    measurement_distance_scale: float = 16.0
    initial_sensor_radius: float = 12.0
    initial_belief_position_std: float = 2.5
    initial_belief_velocity_std: float = 0.7
    measurement_dropout_rate: float = 0.0
    communication_dropout_rate: float = 0.0
    communication_delay_steps: int = 0
    communication_burst_entry_probability: float = 0.0
    communication_burst_recovery_probability: float = 1.0
    communication_delay_jitter_steps: int = 0
    agent_clock_offset_max_steps: int = 0
    measurement_model: str = "cartesian"
    bearing_base_std: float = 0.025
    sensor_noise_scale_min: float = 1.0
    sensor_noise_scale_max: float = 1.0
    biased_agent_count: int = 0
    measurement_bias: tuple[float, float] = (0.0, 0.0)
    measurement_bias_drift: tuple[float, float] = (0.0, 0.0)
    biased_agent_recovery_step: int = -1
    byzantine_agent_count: int = 0
    byzantine_offset: tuple[float, float] = (0.0, 0.0)
    byzantine_covariance_scale: float = 0.15
    secondary_mode_agent_count: int = 0
    secondary_mode_offset: tuple[float, float] = (0.0, 0.0)
    secondary_mode_start_step: int = 0
    secondary_mode_end_step: int = -1
    strategic_agent_count: int = 0
    strategic_offset_magnitude: float = 4.0
    strategic_offset_direction: tuple[float, float] = (1.0, -0.8)
    strategic_ramp_steps: int = 30
    strategic_covariance_scale: float = 0.40

    # Dynamic availability and topology (M8 realism ladder).
    agent_failure_count: int = 0
    agent_failure_step: int = -1
    agent_recovery_step: int = -1
    agent_recovery_stagger_steps: int = 0
    # -1 samples failures from the whole team.  Values 1--4 deliberately
    # target one of the simulated fault populations for adversarial tests.
    agent_failure_fault_type: int = -1
    topology_partition_step: int = -1
    topology_partition_duration: int = 0
    topology_partition_split_index: int = 0
    topology_partition_repeat_interval: int = 0
    topology_partition_repeat_count: int = 1

    # Topology-resilient evidence and lifecycle controls (M9A).
    topology_rejoin_probation_steps: int = 4
    topology_rejoin_nis_threshold: float = 9.21
    topology_rejoin_component_stable_steps: int = 2
    topology_rejoin_ramp_steps: int = 6
    topology_rejoin_covariance_inflation: float = 0.08
    topology_merge_grace_steps: int = 4
    topology_retained_support_decay: float = 0.92
    topology_hypothesis_match_distance: float = 3.0

    # Assignment-weighted missing-evidence output (M9A.6).
    m9a6_residual_base_mass: float = 0.01
    m9a6_residual_ema_alpha: float = 0.20
    m9a6_residual_nis_start: float = 3.5
    m9a6_residual_nis_full: float = 7.0
    m9a6_residual_loss: float = 6.5
    m9a6_wrong_risk_ceiling: float = 0.10
    m9a6_credible_mass: float = 0.95
    m9a6_override_declared_model: bool = False
    m9a6_model_secondary_count: int = 4
    m9a6_model_secondary_offset: tuple[float, float] = (5.0, -4.0)
    m9a6_model_secondary_start_step: int = 20
    m9a6_model_secondary_end_step: int = 90

    # Split raw-measurement/shared-belief trust and admission-aware unknown
    # support (M9A.7).  The covariance floor is relative to the median
    # per-cycle raw covariance eigenvalue, so understated reports cannot buy
    # disproportionate posterior weight.
    m9a7_covariance_floor_fraction: float = 0.25
    # Catastrophic-only predictive gate.  Ordinary contradictory rejoin
    # evidence must remain able to reopen an assignment rather than being
    # circularly rejected by the currently dominant mode.
    m9a7_raw_measurement_nis_ceiling: float = 100.0
    m9a7_admission_residual_ema_alpha: float = 0.25
    m9a7_excluded_secondary_mass_scale: float = 1.0

    # Bounded M9A.7/M9B integration (M9C).  The dynamic planner operates only
    # when the M9A.7 output defers, holds the current communication graph fixed
    # over its short rollout, and prices mean-agent displacement in the same
    # units as the declared output loss.
    m9c_probe_agent_count: int = 2
    m9c_planning_horizon: int = 2
    m9c_planning_samples: int = 9
    m9c_max_probe_modes: int = 3
    m9c_replan_interval: int = 3
    m9c_probe_goal_extrapolation: float = 2.0
    m9c_movement_cost_per_unit: float = 0.80
    m9c_action_change_cost: float = 0.02
    m9c_terminal_risk_max_cycles: int = 12
    m9c_min_mode_separation: float = 0.50
    m9c_activation_probability: float = 0.99
    m9c_exploration_residual_ceiling: float = 0.25

    # Topological flock and motion controller.
    neighbor_limit: int = 3
    sensor_max_speed: float = 2.2
    workspace_limit: float = 200.0
    goal_gain: float = 0.16
    alignment_gain: float = 0.34
    cohesion_gain: float = 0.025
    separation_gain: float = 1.1
    separation_radius: float = 4.0

    # Investigative momentum.
    fixed_momentum: float = 0.72
    adaptive_momentum_min: float = 0.12
    adaptive_momentum_max: float = 0.92
    adaptive_surprise_start: float = 1.0
    adaptive_surprise_full: float = 4.0

    # Guarded adaptive momentum (M5 research prototype).
    guarded_change_momentum: float = 0.58
    guarded_nis_threshold: float = 1.6
    guarded_center_threshold: float = 0.85
    guarded_alignment_threshold: float = 0.45
    guarded_corroboration_fraction: float = 0.50
    guarded_min_available_fraction: float = 0.50
    guarded_min_delivery_ratio: float = 0.65
    guarded_max_message_age: int = 1
    guarded_change_persistence_steps: int = 3
    guarded_hold_steps: int = 2
    guarded_cooldown_steps: int = 10
    guarded_bias_ema_alpha: float = 0.12
    guarded_bias_threshold: float = 1.25
    guarded_bias_persistence_steps: int = 8

    # Robust fusion and explicit hypothesis flocks (M6 research prototype).
    robust_bias_ema_alpha: float = 0.18
    robust_bias_threshold: float = 0.75
    robust_bias_group_tolerance: float = 0.90
    robust_bias_persistence_steps: int = 5
    robust_mode_min_fraction: float = 0.35
    robust_compatibility_threshold: float = 9.21

    # Truth-blind hypothesis-output policy (M7 research prototype).
    output_confidence_margin: float = 0.15
    output_mode_equivalence_distance: float = 2.0
    output_ambiguity_persistence_steps: int = 3
    output_investigation_horizon: int = 8
    output_resolution_persistence_steps: int = 3
    output_defer_cost: float = 0.75
    output_investigation_cost: float = 0.10

    # Evaluation and output.
    recovery_window: int = 5
    recovery_multiplier: float = 1.5
    recovery_error_floor: float = 1.5
    ci_grid_points: int = 21
    reference_position_variance: float = 25.0

    def validate(self) -> None:
        if self.steps < 10:
            raise ValueError("steps must be at least 10")
        if not 1 <= self.change_step < self.steps - 1:
            raise ValueError("change_step must fall inside the experiment")
        if self.target_change_mode not in {"none", "abrupt", "gradual", "repeated"}:
            raise ValueError("target_change_mode must be none, abrupt, gradual, or repeated")
        if self.gradual_change_duration < 1 or self.repeated_change_interval < 2:
            raise ValueError("change durations and intervals must be positive")
        if self.n_agents < 2:
            raise ValueError("n_agents must be at least 2")
        if not 1 <= self.neighbor_limit < self.n_agents:
            raise ValueError("neighbor_limit must be between 1 and n_agents - 1")
        if not 0.0 <= self.fixed_momentum < 1.0:
            raise ValueError("fixed_momentum must be in [0, 1)")
        if not 0.0 <= self.adaptive_momentum_min < self.adaptive_momentum_max < 1.0:
            raise ValueError("adaptive momentum bounds must satisfy 0 <= min < max < 1")
        if self.adaptive_surprise_full <= self.adaptive_surprise_start:
            raise ValueError("adaptive_surprise_full must exceed adaptive_surprise_start")
        if not 0.0 <= self.guarded_change_momentum <= self.fixed_momentum:
            raise ValueError("guarded_change_momentum must be between zero and fixed_momentum")
        if self.guarded_nis_threshold <= 0.0 or self.guarded_center_threshold <= 0.0:
            raise ValueError("guarded surprise thresholds must be positive")
        if not -1.0 <= self.guarded_alignment_threshold <= 1.0:
            raise ValueError("guarded_alignment_threshold must be in [-1, 1]")
        for name, value in (
            ("guarded_corroboration_fraction", self.guarded_corroboration_fraction),
            ("guarded_min_available_fraction", self.guarded_min_available_fraction),
            ("guarded_min_delivery_ratio", self.guarded_min_delivery_ratio),
            ("guarded_bias_ema_alpha", self.guarded_bias_ema_alpha),
        ):
            if not 0.0 < value <= 1.0:
                raise ValueError(f"{name} must be in (0, 1]")
        if self.guarded_max_message_age < 0:
            raise ValueError("guarded_max_message_age cannot be negative")
        if min(
            self.guarded_change_persistence_steps,
            self.guarded_hold_steps,
            self.guarded_bias_persistence_steps,
        ) < 1:
            raise ValueError("guarded persistence and hold durations must be positive")
        if self.guarded_cooldown_steps < 0 or self.guarded_bias_threshold <= 0.0:
            raise ValueError("guarded cooldown and bias threshold are invalid")
        if not 0.0 < self.robust_bias_ema_alpha <= 1.0:
            raise ValueError("robust_bias_ema_alpha must be in (0, 1]")
        if min(
            self.robust_bias_threshold,
            self.robust_bias_group_tolerance,
            self.robust_compatibility_threshold,
        ) <= 0.0:
            raise ValueError("robust fusion thresholds must be positive")
        if self.robust_bias_persistence_steps < 1:
            raise ValueError("robust_bias_persistence_steps must be positive")
        if not 0.0 < self.robust_mode_min_fraction <= 0.5:
            raise ValueError("robust_mode_min_fraction must be in (0, 0.5]")
        if not 0.0 <= self.output_confidence_margin <= 1.0:
            raise ValueError("output_confidence_margin must be in [0, 1]")
        if self.output_mode_equivalence_distance <= 0.0:
            raise ValueError("output_mode_equivalence_distance must be positive")
        if min(
            self.output_ambiguity_persistence_steps,
            self.output_investigation_horizon,
            self.output_resolution_persistence_steps,
        ) < 1:
            raise ValueError("output investigation and resolution durations must be positive")
        if min(self.output_defer_cost, self.output_investigation_cost) < 0.0:
            raise ValueError("output decision costs cannot be negative")
        if self.measurement_base_std <= 0 or self.measurement_distance_scale <= 0:
            raise ValueError("measurement noise parameters must be positive")
        if self.measurement_model not in {"cartesian", "range_bearing"}:
            raise ValueError("measurement_model must be cartesian or range_bearing")
        if self.bearing_base_std <= 0.0:
            raise ValueError("bearing_base_std must be positive")
        if not 0.0 < self.sensor_noise_scale_min <= self.sensor_noise_scale_max:
            raise ValueError("sensor noise scales must satisfy 0 < min <= max")
        if not 0.0 <= self.measurement_dropout_rate < 1.0:
            raise ValueError("measurement_dropout_rate must be in [0, 1)")
        if not 0.0 <= self.communication_dropout_rate < 1.0:
            raise ValueError("communication_dropout_rate must be in [0, 1)")
        for name, value in (
            ("communication_burst_entry_probability", self.communication_burst_entry_probability),
            ("communication_burst_recovery_probability", self.communication_burst_recovery_probability),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if min(
            self.communication_delay_steps,
            self.communication_delay_jitter_steps,
            self.agent_clock_offset_max_steps,
        ) < 0:
            raise ValueError("communication delays, jitter and clock offsets cannot be negative")
        if not 0 <= self.biased_agent_count <= self.n_agents:
            raise ValueError("biased_agent_count must be between 0 and n_agents")
        if min(
            self.byzantine_agent_count,
            self.secondary_mode_agent_count,
            self.strategic_agent_count,
        ) < 0:
            raise ValueError("fault and secondary-mode agent counts cannot be negative")
        if (
            self.biased_agent_count
            + self.byzantine_agent_count
            + self.secondary_mode_agent_count
            + self.strategic_agent_count
            > self.n_agents
        ):
            raise ValueError(
                "biased, Byzantine, secondary-mode and strategic groups must not overlap"
            )
        if self.biased_agent_recovery_step != -1 and not (
            0 < self.biased_agent_recovery_step <= self.steps
        ):
            raise ValueError("biased_agent_recovery_step must be -1 or inside the experiment")
        if not 0.0 < self.byzantine_covariance_scale <= 1.0:
            raise ValueError("byzantine_covariance_scale must be in (0, 1]")
        if not 0 <= self.secondary_mode_start_step < self.steps:
            raise ValueError("secondary_mode_start_step must fall inside the experiment")
        if self.secondary_mode_end_step != -1 and not (
            self.secondary_mode_start_step < self.secondary_mode_end_step <= self.steps
        ):
            raise ValueError(
                "secondary_mode_end_step must be -1 or later than its start and no greater than steps"
            )
        if self.strategic_offset_magnitude < 0.0 or self.strategic_ramp_steps < 1:
            raise ValueError("strategic offset and ramp parameters are invalid")
        if np_norm(self.strategic_offset_direction) <= 0.0:
            raise ValueError("strategic_offset_direction cannot be zero")
        if not 0.0 < self.strategic_covariance_scale <= 1.0:
            raise ValueError("strategic_covariance_scale must be in (0, 1]")
        if not 0 <= self.agent_failure_count < self.n_agents:
            raise ValueError("agent_failure_count must be in [0, n_agents)")
        if self.agent_failure_count:
            if not 0 <= self.agent_failure_step < self.steps:
                raise ValueError("agent_failure_step must be set inside the experiment")
            if self.agent_recovery_step != -1 and not (
                self.agent_failure_step < self.agent_recovery_step <= self.steps
            ):
                raise ValueError("agent_recovery_step must follow failure or be -1")
            if (
                self.agent_recovery_step != -1
                and self.agent_recovery_step
                + (self.agent_failure_count - 1) * self.agent_recovery_stagger_steps
                > self.steps
            ):
                raise ValueError("staggered agent recovery must fit inside the experiment")
        elif self.agent_failure_step != -1 or self.agent_recovery_step != -1:
            raise ValueError("failure timing requires agent_failure_count > 0")
        if self.agent_recovery_stagger_steps < 0:
            raise ValueError("agent_recovery_stagger_steps cannot be negative")
        if self.agent_failure_fault_type not in {-1, 1, 2, 3, 4}:
            raise ValueError("agent_failure_fault_type must be -1 or a fault type in 1..4")
        if self.agent_failure_count and self.agent_failure_fault_type != -1:
            fault_population = {
                1: self.biased_agent_count,
                2: self.byzantine_agent_count,
                3: self.secondary_mode_agent_count,
                4: self.strategic_agent_count,
            }[self.agent_failure_fault_type]
            if self.agent_failure_count > fault_population:
                raise ValueError(
                    "targeted failures cannot exceed the selected fault population"
                )
        if not 0 <= self.topology_partition_split_index < self.n_agents:
            raise ValueError("topology_partition_split_index must be in [0, n_agents)")
        if self.topology_partition_repeat_interval < 0:
            raise ValueError("topology_partition_repeat_interval cannot be negative")
        if self.topology_partition_repeat_count < 1:
            raise ValueError("topology_partition_repeat_count must be positive")
        if self.topology_partition_step == -1:
            if self.topology_partition_duration != 0:
                raise ValueError("partition duration requires topology_partition_step")
        elif not (
            0 <= self.topology_partition_step < self.steps
            and 1 <= self.topology_partition_duration
            and self.topology_partition_step + self.topology_partition_duration <= self.steps
        ):
            raise ValueError("topology partition must fit inside the experiment")
        if self.topology_partition_repeat_count > 1:
            if self.topology_partition_repeat_interval <= self.topology_partition_duration:
                raise ValueError("repeated partitions require a nonzero reconnect gap")
            final_partition_end = (
                self.topology_partition_step
                + (self.topology_partition_repeat_count - 1)
                * self.topology_partition_repeat_interval
                + self.topology_partition_duration
            )
            if self.topology_partition_step < 0 or final_partition_end > self.steps:
                raise ValueError("all repeated partitions must fit inside the experiment")
        if min(
            self.topology_rejoin_probation_steps,
            self.topology_rejoin_component_stable_steps,
            self.topology_rejoin_ramp_steps,
            self.topology_merge_grace_steps,
        ) < 1:
            raise ValueError("M9A lifecycle and merge durations must be positive")
        if self.topology_rejoin_nis_threshold <= 0.0:
            raise ValueError("topology_rejoin_nis_threshold must be positive")
        if self.topology_rejoin_covariance_inflation < 0.0:
            raise ValueError("topology_rejoin_covariance_inflation cannot be negative")
        if not 0.0 < self.topology_retained_support_decay <= 1.0:
            raise ValueError("topology_retained_support_decay must be in (0, 1]")
        if self.topology_hypothesis_match_distance <= 0.0:
            raise ValueError("topology_hypothesis_match_distance must be positive")
        for name, value in (
            ("m9a6_residual_base_mass", self.m9a6_residual_base_mass),
            ("m9a6_residual_ema_alpha", self.m9a6_residual_ema_alpha),
            ("m9a6_wrong_risk_ceiling", self.m9a6_wrong_risk_ceiling),
            ("m9a6_credible_mass", self.m9a6_credible_mass),
        ):
            if not 0.0 < value < 1.0:
                raise ValueError(f"{name} must be in (0, 1)")
        if not (
            0.0 < self.m9a6_residual_nis_start < self.m9a6_residual_nis_full
        ):
            raise ValueError("M9A.6 residual NIS thresholds must be positive and ordered")
        if self.m9a6_residual_loss <= 0.0:
            raise ValueError("m9a6_residual_loss must be positive")
        if not 0.0 < self.m9a7_covariance_floor_fraction <= 1.0:
            raise ValueError("m9a7_covariance_floor_fraction must be in (0, 1]")
        if self.m9a7_raw_measurement_nis_ceiling <= 0.0:
            raise ValueError("m9a7_raw_measurement_nis_ceiling must be positive")
        if not 0.0 < self.m9a7_admission_residual_ema_alpha <= 1.0:
            raise ValueError("m9a7_admission_residual_ema_alpha must be in (0, 1]")
        if not 0.0 <= self.m9a7_excluded_secondary_mass_scale <= 1.0:
            raise ValueError("m9a7_excluded_secondary_mass_scale must be in [0, 1]")
        if not 1 <= self.m9c_probe_agent_count < self.n_agents:
            raise ValueError("m9c_probe_agent_count must be in [1, n_agents)")
        if not 1 <= self.m9c_planning_horizon <= 3:
            raise ValueError("m9c_planning_horizon must be in [1, 3]")
        if self.m9c_planning_samples < 5 or self.m9c_planning_samples % 2 == 0:
            raise ValueError("m9c_planning_samples must be an odd integer of at least five")
        if not 1 <= self.m9c_max_probe_modes <= 4:
            raise ValueError("m9c_max_probe_modes must be in [1, 4]")
        if self.m9c_replan_interval < 1:
            raise ValueError("m9c_replan_interval must be positive")
        if self.m9c_probe_goal_extrapolation <= 1.0:
            raise ValueError("m9c_probe_goal_extrapolation must exceed one")
        if min(
            self.m9c_movement_cost_per_unit,
            self.m9c_action_change_cost,
        ) < 0.0:
            raise ValueError("M9C movement and action-change costs cannot be negative")
        if self.m9c_terminal_risk_max_cycles < self.m9c_planning_horizon:
            raise ValueError("m9c_terminal_risk_max_cycles must cover the planner horizon")
        if self.m9c_min_mode_separation <= 0.0:
            raise ValueError("m9c_min_mode_separation must be positive")
        if not 0.5 < self.m9c_activation_probability < 1.0:
            raise ValueError("m9c_activation_probability must be in (0.5, 1)")
        if not 0.0 <= self.m9c_exploration_residual_ceiling <= 1.0:
            raise ValueError("m9c_exploration_residual_ceiling must be in [0, 1]")
        if self.m9a6_override_declared_model:
            if not 0 <= self.m9a6_model_secondary_count <= self.n_agents:
                raise ValueError("M9A.6 model secondary count must fit the agent count")
            if not 0 <= self.m9a6_model_secondary_start_step < self.steps:
                raise ValueError("M9A.6 model start step must fall inside the experiment")
            if self.m9a6_model_secondary_end_step != -1 and not (
                self.m9a6_model_secondary_start_step
                < self.m9a6_model_secondary_end_step
                <= self.steps
            ):
                raise ValueError("M9A.6 model end step must follow its start")
        if self.sensor_max_speed <= 0 or self.workspace_limit <= 0:
            raise ValueError("motion limits must be positive")
        if self.ci_grid_points < 2:
            raise ValueError("ci_grid_points must be at least 2")
        if not 1 <= self.recovery_window < self.steps - self.change_step:
            raise ValueError("recovery_window must fit after change_step")
        if not self.seeds:
            raise ValueError("at least one seed is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, path: str | Path) -> "ExperimentConfig":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        config = cls(**data)
        config.validate()
        return config


def np_norm(vector: tuple[float, float]) -> float:
    """Small dependency-free norm used during configuration validation."""
    return float((vector[0] ** 2 + vector[1] ** 2) ** 0.5)
