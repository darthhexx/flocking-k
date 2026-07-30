"""Causal ingestion and localization replay for the real UTIAS MR.CLAM logs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path

import numpy as np


MRCLAM_ROBOTS = (1, 2, 3, 4, 5)
MRCLAM_LANDMARKS = tuple(range(6, 21))
M11_ARMS = ("odometry_only", "all_landmarks", "bounded_two")


@dataclass(frozen=True, slots=True)
class ReplayConfig:
    dt: float = 0.50
    process_position_std: float = 0.10
    process_heading_std: float = 0.06
    range_std: float = 0.18
    bearing_std: float = 0.10
    nis_gate: float = 25.0
    initialization_position_std: float = 0.05
    initialization_heading_std: float = 0.03
    window_seconds: float = 60.0
    topology_message_ttl: float = 5.0
    bounded_measurements: int = 2

    def validate(self) -> None:
        positive = (
            self.dt,
            self.process_position_std,
            self.process_heading_std,
            self.range_std,
            self.bearing_std,
            self.nis_gate,
            self.initialization_position_std,
            self.initialization_heading_std,
            self.window_seconds,
            self.topology_message_ttl,
        )
        if min(positive) <= 0.0:
            raise ValueError("replay parameters must be positive")
        if self.bounded_measurements < 1:
            raise ValueError("bounded_measurements must be positive")


@dataclass(frozen=True, slots=True)
class RobotLog:
    groundtruth: np.ndarray
    odometry: np.ndarray
    measurements: np.ndarray


@dataclass(frozen=True, slots=True)
class MRCLAMReplay:
    root: Path
    barcode_to_subject: dict[int, int]
    landmarks: dict[int, np.ndarray]
    robots: dict[int, RobotLog]
    materialized_sha256: str
    unknown_barcode_rows: int


@dataclass(frozen=True, slots=True)
class ReplayStep:
    robot: int
    arm: str
    step: int
    time: float
    estimate_x: float
    estimate_y: float
    truth_x: float
    truth_y: float
    position_error: float
    position_nees: float
    coverage95: bool
    landmark_available: int
    landmark_used: int
    rejected: int
    outage_age_seconds: float
    topology_components: int
    topology_directed_edges: int
    clock_alignment_error: float


@dataclass(frozen=True, slots=True)
class ReplayTrial:
    robot: int
    arm: str
    steps: tuple[ReplayStep, ...]
    runtime_seconds: float


def _load_table(path: Path, columns: int) -> np.ndarray:
    if not path.is_file():
        raise ValueError(f"missing MRCLAM file: {path.name}")
    values = np.loadtxt(path, comments="#", dtype=float)
    if values.ndim == 1:
        values = values[np.newaxis, :]
    if values.ndim != 2 or values.shape[1] != columns or len(values) == 0:
        raise ValueError(f"malformed MRCLAM file: {path.name}")
    if not np.all(np.isfinite(values)):
        raise ValueError(f"non-finite MRCLAM values: {path.name}")
    return values


def _hash_materialized(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.name):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def load_mrclam_dataset(root: str | Path) -> MRCLAMReplay:
    """Load and strictly validate all 17 MR.CLAM text files."""
    directory = Path(root)
    barcodes = _load_table(directory / "Barcodes.dat", 2)
    landmark_values = _load_table(directory / "Landmark_Groundtruth.dat", 5)
    subject_to_barcode = {
        int(subject): int(barcode) for subject, barcode in barcodes
    }
    if set(subject_to_barcode) != set(range(1, 21)):
        raise ValueError("MRCLAM barcode subjects must be exactly 1..20")
    barcode_to_subject = {
        barcode: subject for subject, barcode in subject_to_barcode.items()
    }
    if len(barcode_to_subject) != 20:
        raise ValueError("MRCLAM barcodes must be unique")
    landmarks = {
        int(row[0]): np.asarray(row[1:3], dtype=float)
        for row in landmark_values
    }
    if set(landmarks) != set(MRCLAM_LANDMARKS):
        raise ValueError("MRCLAM landmarks must be subjects 6..20")
    robots: dict[int, RobotLog] = {}
    unknown_barcode_rows = 0
    files = [directory / "Barcodes.dat", directory / "Landmark_Groundtruth.dat"]
    for robot in MRCLAM_ROBOTS:
        groundtruth_path = directory / f"Robot{robot}_Groundtruth.dat"
        odometry_path = directory / f"Robot{robot}_Odometry.dat"
        measurement_path = directory / f"Robot{robot}_Measurement.dat"
        groundtruth = _load_table(groundtruth_path, 4)
        groundtruth = groundtruth.copy()
        groundtruth[:, 3] = np.unwrap(groundtruth[:, 3])
        odometry = _load_table(odometry_path, 3)
        measurements = _load_table(measurement_path, 4)
        for name, values in (
            ("groundtruth", groundtruth),
            ("odometry", odometry),
            ("measurement", measurements),
        ):
            if np.any(np.diff(values[:, 0]) < 0.0):
                raise ValueError(
                    f"Robot {robot} {name} timestamps are not monotone"
                )
        measured_barcodes = {int(value) for value in measurements[:, 1]}
        unknown = measured_barcodes - set(barcode_to_subject)
        if unknown:
            known_mask = np.isin(
                measurements[:, 1].astype(np.int64),
                np.asarray(sorted(barcode_to_subject), dtype=np.int64),
            )
            unknown_barcode_rows += int(np.sum(~known_mask))
            measurements = measurements[known_mask]
        robots[robot] = RobotLog(groundtruth, odometry, measurements)
        files.extend([groundtruth_path, odometry_path, measurement_path])
    return MRCLAMReplay(
        root=directory,
        barcode_to_subject=barcode_to_subject,
        landmarks=landmarks,
        robots=robots,
        materialized_sha256=_hash_materialized(files),
        unknown_barcode_rows=unknown_barcode_rows,
    )


def replay_fingerprint(dataset: MRCLAMReplay, config: ReplayConfig) -> str:
    config.validate()
    digest = hashlib.sha256()
    digest.update(dataset.materialized_sha256.encode("ascii"))
    for value in (
        config.dt,
        config.process_position_std,
        config.process_heading_std,
        config.range_std,
        config.bearing_std,
        config.nis_gate,
        config.window_seconds,
        config.topology_message_ttl,
        float(config.bounded_measurements),
    ):
        digest.update(np.float64(value).tobytes())
    return digest.hexdigest()


def _wrap_angle(value: float) -> float:
    return float((value + math.pi) % (2.0 * math.pi) - math.pi)


class LandmarkEKF:
    """Truth-isolated planar pose EKF for recorded odometry and landmarks."""

    def __init__(self, initial_pose: np.ndarray, config: ReplayConfig) -> None:
        self.config = config
        self.state = np.asarray(initial_pose, dtype=float).copy()
        self.covariance = np.diag(
            [
                config.initialization_position_std**2,
                config.initialization_position_std**2,
                config.initialization_heading_std**2,
            ]
        )

    def predict(self, forward_velocity: float, angular_velocity: float) -> None:
        theta = float(self.state[2])
        dt = self.config.dt
        self.state[0] += forward_velocity * math.cos(theta) * dt
        self.state[1] += forward_velocity * math.sin(theta) * dt
        self.state[2] = _wrap_angle(
            self.state[2] + angular_velocity * dt
        )
        transition = np.eye(3, dtype=float)
        transition[0, 2] = -forward_velocity * math.sin(theta) * dt
        transition[1, 2] = forward_velocity * math.cos(theta) * dt
        process = np.diag(
            [
                (self.config.process_position_std * math.sqrt(dt)) ** 2,
                (self.config.process_position_std * math.sqrt(dt)) ** 2,
                (self.config.process_heading_std * math.sqrt(dt)) ** 2,
            ]
        )
        self.covariance = (
            transition @ self.covariance @ transition.T + process
        )

    def linearize(
        self,
        landmark: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        dx = float(landmark[0] - self.state[0])
        dy = float(landmark[1] - self.state[1])
        squared = max(dx * dx + dy * dy, 1e-12)
        distance = math.sqrt(squared)
        predicted = np.asarray(
            [distance, _wrap_angle(math.atan2(dy, dx) - self.state[2])],
            dtype=float,
        )
        jacobian = np.asarray(
            [
                [-dx / distance, -dy / distance, 0.0],
                [dy / squared, -dx / squared, -1.0],
            ],
            dtype=float,
        )
        return predicted, jacobian

    def expected_position_reduction(self, landmark: np.ndarray) -> float:
        _, jacobian = self.linearize(landmark)
        noise = np.diag(
            [self.config.range_std**2, self.config.bearing_std**2]
        )
        innovation = jacobian @ self.covariance @ jacobian.T + noise
        gain = self.covariance @ jacobian.T @ np.linalg.inv(innovation)
        posterior = (
            np.eye(3, dtype=float) - gain @ jacobian
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
        noise = np.diag(
            [self.config.range_std**2, self.config.bearing_std**2]
        )
        innovation = jacobian @ self.covariance @ jacobian.T + noise
        nis = float(residual @ np.linalg.solve(innovation, residual))
        if nis > self.config.nis_gate:
            return False, nis
        gain = self.covariance @ jacobian.T @ np.linalg.inv(innovation)
        self.state += gain @ residual
        self.state[2] = _wrap_angle(float(self.state[2]))
        identity = np.eye(3, dtype=float)
        update = identity - gain @ jacobian
        self.covariance = (
            update @ self.covariance @ update.T + gain @ noise @ gain.T
        )
        return True, nis


def _interpolate_pose(groundtruth: np.ndarray, time: float) -> np.ndarray:
    times = groundtruth[:, 0]
    x = float(np.interp(time, times, groundtruth[:, 1]))
    y = float(np.interp(time, times, groundtruth[:, 2]))
    theta = _wrap_angle(float(np.interp(time, times, groundtruth[:, 3])))
    return np.asarray([x, y, theta], dtype=float)


def _previous_row(values: np.ndarray, time: float) -> np.ndarray:
    index = int(np.searchsorted(values[:, 0], time, side="right") - 1)
    return values[max(index, 0)]


def replay_time_bounds(dataset: MRCLAMReplay) -> tuple[float, float]:
    start = max(
        max(log.groundtruth[0, 0], log.odometry[0, 0])
        for log in dataset.robots.values()
    )
    end = min(
        min(log.groundtruth[-1, 0], log.odometry[-1, 0])
        for log in dataset.robots.values()
    )
    if end <= start:
        raise ValueError("MRCLAM streams have no common replay interval")
    return float(start), float(end)


def _topology_series(
    dataset: MRCLAMReplay,
    times: np.ndarray,
    config: ReplayConfig,
) -> tuple[np.ndarray, np.ndarray]:
    last_seen = np.full((5, 5), -np.inf, dtype=float)
    components = np.full(len(times), 5, dtype=np.int64)
    edges = np.zeros(len(times), dtype=np.int64)
    cursors = {robot: 0 for robot in MRCLAM_ROBOTS}
    for step, time in enumerate(times):
        previous_time = times[step - 1] if step else time - config.dt
        for robot in MRCLAM_ROBOTS:
            measurements = dataset.robots[robot].measurements
            cursor = cursors[robot]
            while cursor < len(measurements) and measurements[cursor, 0] <= time:
                row = measurements[cursor]
                if row[0] > previous_time:
                    subject = dataset.barcode_to_subject[int(row[1])]
                    if subject in MRCLAM_ROBOTS and subject != robot:
                        last_seen[robot - 1, subject - 1] = float(row[0])
                cursor += 1
            cursors[robot] = cursor
        adjacency = time - last_seen <= config.topology_message_ttl
        np.fill_diagonal(adjacency, False)
        edges[step] = int(np.sum(adjacency))
        undirected = adjacency | adjacency.T
        visited: set[int] = set()
        count = 0
        for node in range(5):
            if node in visited:
                continue
            count += 1
            stack = [node]
            visited.add(node)
            while stack:
                current = stack.pop()
                for peer in np.flatnonzero(undirected[current]):
                    index = int(peer)
                    if index not in visited:
                        visited.add(index)
                        stack.append(index)
        components[step] = count
    return components, edges


def run_mrclam_replay(
    dataset: MRCLAMReplay,
    config: ReplayConfig,
    arm: str,
) -> list[ReplayTrial]:
    """Run one causal replay arm for all five robots."""
    import time as time_module

    config.validate()
    if arm not in M11_ARMS:
        raise ValueError(f"unknown replay arm: {arm}")
    start, end = replay_time_bounds(dataset)
    times = np.arange(start, end, config.dt, dtype=float)
    topology_components, topology_edges = _topology_series(
        dataset, times, config
    )
    trials: list[ReplayTrial] = []
    for robot in MRCLAM_ROBOTS:
        started = time_module.perf_counter()
        log = dataset.robots[robot]
        initial = _interpolate_pose(log.groundtruth, float(times[0]))
        filter_ = LandmarkEKF(initial, config)
        cursor = int(
            np.searchsorted(log.measurements[:, 0], times[0], side="right")
        )
        steps: list[ReplayStep] = []
        outage_age = 0.0
        for step, current_time in enumerate(times):
            if step:
                odometry = _previous_row(log.odometry, float(current_time))
                filter_.predict(float(odometry[1]), float(odometry[2]))
            previous_time = (
                times[step - 1] if step else current_time - config.dt
            )
            current_events: list[tuple[int, float, float, float]] = []
            while (
                cursor < len(log.measurements)
                and log.measurements[cursor, 0] <= current_time
            ):
                row = log.measurements[cursor]
                if row[0] > previous_time:
                    subject = dataset.barcode_to_subject[int(row[1])]
                    if subject in dataset.landmarks:
                        current_events.append(
                            (
                                subject,
                                float(row[2]),
                                float(row[3]),
                                float(row[0]),
                            )
                        )
                cursor += 1
            selected = current_events
            if arm == "odometry_only":
                selected = []
            elif arm == "bounded_two" and len(selected) > config.bounded_measurements:
                ranked = sorted(
                    selected,
                    key=lambda item: (
                        -filter_.expected_position_reduction(
                            dataset.landmarks[item[0]]
                        ),
                        item[0],
                        item[3],
                    ),
                )
                selected = ranked[: config.bounded_measurements]
            used = 0
            rejected = 0
            alignment_errors: list[float] = []
            for subject, measured_range, measured_bearing, event_time in selected:
                accepted, _ = filter_.update(
                    dataset.landmarks[subject],
                    measured_range,
                    measured_bearing,
                )
                used += int(accepted)
                rejected += int(not accepted)
                alignment_errors.append(current_time - event_time)
            outage_age = (
                0.0 if current_events else outage_age + config.dt
            )
            truth = _interpolate_pose(log.groundtruth, float(current_time))
            error = filter_.state[:2] - truth[:2]
            nees = float(
                error
                @ np.linalg.solve(filter_.covariance[:2, :2], error)
            )
            steps.append(
                ReplayStep(
                    robot=robot,
                    arm=arm,
                    step=step,
                    time=float(current_time),
                    estimate_x=float(filter_.state[0]),
                    estimate_y=float(filter_.state[1]),
                    truth_x=float(truth[0]),
                    truth_y=float(truth[1]),
                    position_error=float(np.linalg.norm(error)),
                    position_nees=nees,
                    coverage95=nees <= 5.991,
                    landmark_available=len(current_events),
                    landmark_used=used,
                    rejected=rejected,
                    outage_age_seconds=outage_age,
                    topology_components=int(topology_components[step]),
                    topology_directed_edges=int(topology_edges[step]),
                    clock_alignment_error=(
                        float(np.mean(alignment_errors))
                        if alignment_errors
                        else 0.0
                    ),
                )
            )
        trials.append(
            ReplayTrial(
                robot=robot,
                arm=arm,
                steps=tuple(steps),
                runtime_seconds=time_module.perf_counter() - started,
            )
        )
    return trials
