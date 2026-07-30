"""Linear Kalman filtering and conservative distributed belief fusion."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from numpy.typing import NDArray


FloatArray = NDArray[np.float64]


def _symmetrize(matrix: FloatArray) -> FloatArray:
    return 0.5 * (matrix + matrix.T)


def constant_velocity_matrices(dt: float, acceleration_variance: float) -> tuple[FloatArray, FloatArray]:
    identity = np.eye(2, dtype=float)
    transition = np.block([[identity, dt * identity], [np.zeros((2, 2)), identity]])
    process = acceleration_variance * np.block(
        [
            [(dt**4 / 4.0) * identity, (dt**3 / 2.0) * identity],
            [(dt**3 / 2.0) * identity, (dt**2) * identity],
        ]
    )
    return transition, process


@dataclass(slots=True)
class KalmanFilter:
    state: FloatArray
    covariance: FloatArray
    dt: float
    acceleration_variance: float

    def predict(self) -> None:
        transition, process = constant_velocity_matrices(self.dt, self.acceleration_variance)
        self.state = transition @ self.state
        self.covariance = _symmetrize(transition @ self.covariance @ transition.T + process)

    def update(self, observation: FloatArray, measurement_covariance: FloatArray) -> float:
        observation_matrix = np.block([np.eye(2, dtype=float), np.zeros((2, 2), dtype=float)])
        innovation = observation - observation_matrix @ self.state
        innovation_covariance = (
            observation_matrix @ self.covariance @ observation_matrix.T + measurement_covariance
        )
        gain = np.linalg.solve(
            innovation_covariance,
            observation_matrix @ self.covariance,
        ).T
        self.state = self.state + gain @ innovation
        # Joseph form retains positive semidefiniteness under finite precision.
        identity = np.eye(4, dtype=float)
        residual = identity - gain @ observation_matrix
        self.covariance = _symmetrize(
            residual @ self.covariance @ residual.T
            + gain @ measurement_covariance @ gain.T
        )
        return float(innovation @ np.linalg.solve(innovation_covariance, innovation))


def covariance_intersection(
    state_a: FloatArray,
    covariance_a: FloatArray,
    state_b: FloatArray,
    covariance_b: FloatArray,
    grid_points: int = 21,
) -> tuple[FloatArray, FloatArray]:
    """Fuse beliefs without assuming their cross-correlation is known."""
    if grid_points < 2:
        raise ValueError("grid_points must be at least 2")
    information_a = np.linalg.inv(covariance_a)
    information_b = np.linalg.inv(covariance_b)
    best: tuple[float, FloatArray, FloatArray] | None = None
    weights = sorted(np.linspace(0.0, 1.0, grid_points), key=lambda value: abs(value - 0.5))
    for weight in weights:
        information = weight * information_a + (1.0 - weight) * information_b
        covariance = _symmetrize(np.linalg.inv(information))
        sign, log_determinant = np.linalg.slogdet(covariance)
        if sign <= 0:
            continue
        state = covariance @ (
            weight * information_a @ state_a + (1.0 - weight) * information_b @ state_b
        )
        if best is None or log_determinant < best[0]:
            best = (float(log_determinant), state, covariance)
    if best is None:
        raise np.linalg.LinAlgError("covariance intersection could not find an SPD result")
    return best[1], best[2]


def fuse_neighbor_beliefs(
    states: list[FloatArray],
    covariances: list[FloatArray],
    neighbors: list[list[int]],
    grid_points: int,
    peer_states: list[FloatArray] | None = None,
    peer_covariances: list[FloatArray] | None = None,
) -> tuple[list[FloatArray], list[FloatArray]]:
    """Apply one synchronous, topological fusion round."""
    source_states = states if peer_states is None else peer_states
    source_covariances = covariances if peer_covariances is None else peer_covariances
    fused_states: list[FloatArray] = []
    fused_covariances: list[FloatArray] = []
    for index, peer_indices in enumerate(neighbors):
        state = states[index].copy()
        covariance = covariances[index].copy()
        for peer in peer_indices:
            state, covariance = covariance_intersection(
                state,
                covariance,
                source_states[peer],
                source_covariances[peer],
                grid_points,
            )
        fused_states.append(state)
        fused_covariances.append(covariance)
    return fused_states, fused_covariances


def fuse_team_belief(
    states: list[FloatArray], covariances: list[FloatArray], grid_points: int
) -> tuple[FloatArray, FloatArray]:
    state = states[0].copy()
    covariance = covariances[0].copy()
    for peer_state, peer_covariance in zip(states[1:], covariances[1:]):
        state, covariance = covariance_intersection(
            state, covariance, peer_state, peer_covariance, grid_points
        )
    return state, covariance


def precision_fuse_positions(
    positions: FloatArray, covariances: list[FloatArray]
) -> tuple[FloatArray, FloatArray]:
    information = np.zeros((2, 2), dtype=float)
    information_state = np.zeros(2, dtype=float)
    for position, covariance in zip(positions, covariances):
        inverse = np.linalg.inv(covariance)
        information += inverse
        information_state += inverse @ position
    covariance = np.linalg.inv(information)
    return covariance @ information_state, _symmetrize(covariance)
