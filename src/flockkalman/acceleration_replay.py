"""M12 measured-acceleration pose filter and separate jerk-limiter assay."""

from __future__ import annotations

from dataclasses import dataclass
import math
import time as time_module

import numpy as np

from .external_replay import (
    MRCLAMReplay,
    MRCLAM_ROBOTS,
    ReplayConfig,
    ReplayStep,
    ReplayTrial,
    _interpolate_pose,
    _previous_row,
    _topology_series,
    _wrap_angle,
    replay_time_bounds,
)


M12_BASELINE_ARM = "bounded_constant_velocity"
M12_ACCELERATION_ARM = "bounded_measured_acceleration"
M12_ARMS = (M12_BASELINE_ARM, M12_ACCELERATION_ARM)


@dataclass(frozen=True, slots=True)
class AccelerationConfig:
    replay: ReplayConfig = ReplayConfig()
    initial_velocity_std: float = 0.08
    initial_angular_velocity_std: float = 0.12
    linear_acceleration_std: float = 0.35
    angular_acceleration_std: float = 0.50
    acceleration_exercised_threshold: float = 0.10
    angular_acceleration_exercised_threshold: float = 0.15

    def validate(self) -> None:
        self.replay.validate()
        values = (
            self.initial_velocity_std,
            self.initial_angular_velocity_std,
            self.linear_acceleration_std,
            self.angular_acceleration_std,
            self.acceleration_exercised_threshold,
            self.angular_acceleration_exercised_threshold,
        )
        if min(values) <= 0.0:
            raise ValueError("acceleration parameters must be positive")


@dataclass(frozen=True, slots=True)
class AccelerationReplayTrial:
    trial: ReplayTrial
    mean_absolute_acceleration: float
    p95_absolute_acceleration: float
    mean_absolute_angular_acceleration: float
    acceleration_exercised_rate: float


@dataclass(frozen=True, slots=True)
class JerkAssayResult:
    controller: str
    velocity_rmse: float
    peak_acceleration: float
    peak_jerk: float
    distance: float
    finite: bool


class AccelerationLandmarkEKF:
    """Five-state pose/velocity EKF driven by causal measured acceleration."""

    def __init__(
        self,
        initial_pose: np.ndarray,
        initial_velocity: float,
        initial_angular_velocity: float,
        config: AccelerationConfig,
    ) -> None:
        self.config = config
        replay = config.replay
        self.state = np.asarray(
            [
                initial_pose[0],
                initial_pose[1],
                initial_pose[2],
                initial_velocity,
                initial_angular_velocity,
            ],
            dtype=float,
        )
        self.covariance = np.diag(
            [
                replay.initialization_position_std**2,
                replay.initialization_position_std**2,
                replay.initialization_heading_std**2,
                config.initial_velocity_std**2,
                config.initial_angular_velocity_std**2,
            ]
        )
        self.last_linear_acceleration = 0.0
        self.last_angular_acceleration = 0.0

    def predict(
        self,
        measured_velocity: float,
        measured_angular_velocity: float,
    ) -> None:
        dt = self.config.replay.dt
        prior_velocity = float(self.state[3])
        prior_angular = float(self.state[4])
        acceleration = (measured_velocity - prior_velocity) / dt
        angular_acceleration = (
            measured_angular_velocity - prior_angular
        ) / dt
        mid_velocity = prior_velocity + 0.5 * acceleration * dt
        mid_angular = prior_angular + 0.5 * angular_acceleration * dt
        theta = float(self.state[2])
        mid_theta = theta + 0.5 * mid_angular * dt
        self.state[0] += mid_velocity * math.cos(mid_theta) * dt
        self.state[1] += mid_velocity * math.sin(mid_theta) * dt
        self.state[2] = _wrap_angle(theta + mid_angular * dt)
        self.state[3] = measured_velocity
        self.state[4] = measured_angular_velocity
        transition = np.zeros((5, 5), dtype=float)
        transition[0, 0] = 1.0
        transition[1, 1] = 1.0
        transition[2, 2] = 1.0
        transition[0, 2] = -mid_velocity * math.sin(mid_theta) * dt
        transition[1, 2] = mid_velocity * math.cos(mid_theta) * dt
        transition[0, 3] = 0.5 * math.cos(mid_theta) * dt
        transition[1, 3] = 0.5 * math.sin(mid_theta) * dt
        transition[2, 4] = 0.5 * dt
        replay = self.config.replay
        process = np.diag(
            [
                (replay.process_position_std * math.sqrt(dt)) ** 2,
                (replay.process_position_std * math.sqrt(dt)) ** 2,
                (replay.process_heading_std * math.sqrt(dt)) ** 2,
                (self.config.linear_acceleration_std * dt) ** 2,
                (self.config.angular_acceleration_std * dt) ** 2,
            ]
        )
        self.covariance = (
            transition @ self.covariance @ transition.T + process
        )
        self.last_linear_acceleration = acceleration
        self.last_angular_acceleration = angular_acceleration

    def linearize(
        self,
        landmark: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        dx = float(landmark[0] - self.state[0])
        dy = float(landmark[1] - self.state[1])
        squared = max(dx * dx + dy * dy, 1e-12)
        distance = math.sqrt(squared)
        predicted = np.asarray(
            [
                distance,
                _wrap_angle(math.atan2(dy, dx) - self.state[2]),
            ],
            dtype=float,
        )
        jacobian = np.zeros((2, 5), dtype=float)
        jacobian[0, :3] = (-dx / distance, -dy / distance, 0.0)
        jacobian[1, :3] = (dy / squared, -dx / squared, -1.0)
        return predicted, jacobian

    def expected_position_reduction(self, landmark: np.ndarray) -> float:
        _, jacobian = self.linearize(landmark)
        replay = self.config.replay
        noise = np.diag([replay.range_std**2, replay.bearing_std**2])
        innovation = jacobian @ self.covariance @ jacobian.T + noise
        gain = self.covariance @ jacobian.T @ np.linalg.inv(innovation)
        posterior = (
            np.eye(5, dtype=float) - gain @ jacobian
        ) @ self.covariance
        return float(
            np.trace(self.covariance[:2, :2])
            - np.trace(posterior[:2, :2])
        )

    def update(
        self,
        landmark: np.ndarray,
        measured_range: float,
        measured_bearing: float,
    ) -> tuple[bool, float]:
        predicted, jacobian = self.linearize(landmark)
        residual = np.asarray(
            [
                measured_range - predicted[0],
                _wrap_angle(measured_bearing - predicted[1]),
            ],
            dtype=float,
        )
        replay = self.config.replay
        noise = np.diag([replay.range_std**2, replay.bearing_std**2])
        innovation = jacobian @ self.covariance @ jacobian.T + noise
        nis = float(residual @ np.linalg.solve(innovation, residual))
        if nis > replay.nis_gate:
            return False, nis
        gain = self.covariance @ jacobian.T @ np.linalg.inv(innovation)
        self.state += gain @ residual
        self.state[2] = _wrap_angle(float(self.state[2]))
        identity = np.eye(5, dtype=float)
        correction = identity - gain @ jacobian
        self.covariance = (
            correction @ self.covariance @ correction.T
            + gain @ noise @ gain.T
        )
        return True, nis


def run_acceleration_replay(
    dataset: MRCLAMReplay,
    config: AccelerationConfig,
) -> list[AccelerationReplayTrial]:
    """Run the bounded two-landmark arm with a measured-acceleration model."""
    config.validate()
    replay = config.replay
    start, end = replay_time_bounds(dataset)
    times = np.arange(start, end, replay.dt, dtype=float)
    topology_components, topology_edges = _topology_series(
        dataset,
        times,
        replay,
    )
    trials: list[AccelerationReplayTrial] = []
    for robot in MRCLAM_ROBOTS:
        started = time_module.perf_counter()
        log = dataset.robots[robot]
        initial = _interpolate_pose(log.groundtruth, float(times[0]))
        initial_odometry = _previous_row(log.odometry, float(times[0]))
        filter_ = AccelerationLandmarkEKF(
            initial,
            float(initial_odometry[1]),
            float(initial_odometry[2]),
            config,
        )
        cursor = int(
            np.searchsorted(log.measurements[:, 0], times[0], side="right")
        )
        outage_age = 0.0
        steps: list[ReplayStep] = []
        linear_accelerations: list[float] = []
        angular_accelerations: list[float] = []
        for step, current_time in enumerate(times):
            if step:
                odometry = _previous_row(log.odometry, float(current_time))
                filter_.predict(float(odometry[1]), float(odometry[2]))
                linear_accelerations.append(
                    abs(filter_.last_linear_acceleration)
                )
                angular_accelerations.append(
                    abs(filter_.last_angular_acceleration)
                )
            previous_time = (
                times[step - 1] if step else current_time - replay.dt
            )
            events: list[tuple[int, float, float, float]] = []
            while (
                cursor < len(log.measurements)
                and log.measurements[cursor, 0] <= current_time
            ):
                row = log.measurements[cursor]
                if row[0] > previous_time:
                    subject = dataset.barcode_to_subject[int(row[1])]
                    if subject in dataset.landmarks:
                        events.append(
                            (
                                subject,
                                float(row[2]),
                                float(row[3]),
                                float(row[0]),
                            )
                        )
                cursor += 1
            ranked = sorted(
                events,
                key=lambda item: (
                    -filter_.expected_position_reduction(
                        dataset.landmarks[item[0]]
                    ),
                    item[0],
                    item[3],
                ),
            )
            selected = ranked[: replay.bounded_measurements]
            used = 0
            rejected = 0
            alignments: list[float] = []
            for subject, measured_range, measured_bearing, event_time in selected:
                accepted, _ = filter_.update(
                    dataset.landmarks[subject],
                    measured_range,
                    measured_bearing,
                )
                used += int(accepted)
                rejected += int(not accepted)
                alignments.append(float(current_time - event_time))
            outage_age = 0.0 if events else outage_age + replay.dt
            truth = _interpolate_pose(log.groundtruth, float(current_time))
            error = filter_.state[:2] - truth[:2]
            nees = float(
                error
                @ np.linalg.solve(filter_.covariance[:2, :2], error)
            )
            steps.append(
                ReplayStep(
                    robot=robot,
                    arm=M12_ACCELERATION_ARM,
                    step=step,
                    time=float(current_time),
                    estimate_x=float(filter_.state[0]),
                    estimate_y=float(filter_.state[1]),
                    truth_x=float(truth[0]),
                    truth_y=float(truth[1]),
                    position_error=float(np.linalg.norm(error)),
                    position_nees=nees,
                    coverage95=nees <= 5.991,
                    landmark_available=len(events),
                    landmark_used=used,
                    rejected=rejected,
                    outage_age_seconds=outage_age,
                    topology_components=int(topology_components[step]),
                    topology_directed_edges=int(topology_edges[step]),
                    clock_alignment_error=(
                        float(np.mean(alignments)) if alignments else 0.0
                    ),
                )
            )
        linear = np.asarray(linear_accelerations, dtype=float)
        angular = np.asarray(angular_accelerations, dtype=float)
        exercised = (
            (linear >= config.acceleration_exercised_threshold)
            | (
                angular
                >= config.angular_acceleration_exercised_threshold
            )
        )
        trials.append(
            AccelerationReplayTrial(
                trial=ReplayTrial(
                    robot=robot,
                    arm=M12_ACCELERATION_ARM,
                    steps=tuple(steps),
                    runtime_seconds=time_module.perf_counter() - started,
                ),
                mean_absolute_acceleration=float(np.mean(linear)),
                p95_absolute_acceleration=float(np.quantile(linear, 0.95)),
                mean_absolute_angular_acceleration=float(np.mean(angular)),
                acceleration_exercised_rate=float(np.mean(exercised)),
            )
        )
    return trials


def run_jerk_limiter_assay(
    *,
    dt: float = 0.05,
    steps: int = 800,
    acceleration_limit: float = 0.8,
    jerk_limit: float = 1.6,
) -> tuple[JerkAssayResult, JerkAssayResult]:
    """Compare an acceleration-clipped response with a jerk-limited response."""
    if min(dt, steps, acceleration_limit, jerk_limit) <= 0:
        raise ValueError("jerk assay parameters must be positive")
    target = np.zeros(steps, dtype=float)
    target[80:240] = 1.0
    target[240:360] = -0.5
    target[360:560] = 0.7
    target[560:680] = 0.2

    def simulate(jerk_limited: bool) -> JerkAssayResult:
        velocity = np.zeros(steps, dtype=float)
        acceleration = np.zeros(steps, dtype=float)
        for step in range(1, steps):
            desired_acceleration = np.clip(
                (target[step] - velocity[step - 1]) / dt,
                -acceleration_limit,
                acceleration_limit,
            )
            if jerk_limited:
                delta = np.clip(
                    desired_acceleration - acceleration[step - 1],
                    -jerk_limit * dt,
                    jerk_limit * dt,
                )
                acceleration[step] = acceleration[step - 1] + delta
            else:
                acceleration[step] = desired_acceleration
            velocity[step] = (
                velocity[step - 1] + acceleration[step] * dt
            )
        jerk = np.diff(acceleration) / dt
        return JerkAssayResult(
            controller=(
                "jerk_limited" if jerk_limited else "acceleration_clipped"
            ),
            velocity_rmse=math.sqrt(
                float(np.mean((velocity - target) ** 2))
            ),
            peak_acceleration=float(np.max(np.abs(acceleration))),
            peak_jerk=float(np.max(np.abs(jerk))),
            distance=float(np.sum(np.abs(velocity)) * dt),
            finite=bool(
                np.all(np.isfinite(velocity))
                and np.all(np.isfinite(acceleration))
            ),
        )

    return simulate(False), simulate(True)
