"""Topological flocking and investigative-momentum policies."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from numpy.typing import NDArray

from .config import ExperimentConfig


FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class GuardedMomentumDecision:
    """Reason-coded output from the guarded momentum controller."""

    momenta: FloatArray
    classification: str
    change_score: float
    corroborating_agents: int
    biased_agents: int
    fallback_active: bool
    change_event: bool


class GuardedMomentumController:
    """Stateful change detector with a mandatory fixed-momentum fallback.

    The detector treats coherent, independently observed innovations as possible
    regime change.  It refuses to adapt when messages are stale, delivery is
    degraded, evidence is sparse, or surprise is not directionally corroborated.
    Persistent agent-specific residual offsets are tracked as bias candidates and
    excluded from the corroboration vote.
    """

    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        self._bias_ema = np.zeros((config.n_agents, 2), dtype=float)
        self._bias_streak = np.zeros(config.n_agents, dtype=np.int64)
        self._candidate_streak = 0
        self._hold_remaining = 0
        self._cooldown_remaining = 0

    def update(
        self,
        standardized_innovations: FloatArray,
        nis_values: FloatArray,
        available: NDArray[np.bool_],
        *,
        delivery_ratio: float,
        message_age: int,
    ) -> GuardedMomentumDecision:
        config = self.config
        fixed = np.full(config.n_agents, config.fixed_momentum, dtype=float)
        valid = available & np.all(np.isfinite(standardized_innovations), axis=1)
        valid_count = int(np.sum(valid))

        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1

        if valid_count:
            alpha = config.guarded_bias_ema_alpha
            self._bias_ema[valid] = (
                (1.0 - alpha) * self._bias_ema[valid]
                + alpha * standardized_innovations[valid]
            )
            robust_bias_center = np.median(self._bias_ema[valid], axis=0)
            bias_deviation = np.linalg.norm(
                self._bias_ema - robust_bias_center,
                axis=1,
            )
            bias_evidence = valid & (bias_deviation >= config.guarded_bias_threshold)
            self._bias_streak[bias_evidence] += 1
            self._bias_streak[valid & ~bias_evidence] = np.maximum(
                0,
                self._bias_streak[valid & ~bias_evidence] - 1,
            )
        biased = self._bias_streak >= config.guarded_bias_persistence_steps
        bias_guard_active = bool(np.any(biased))
        if valid_count:
            # Early bias suspicion is enough to disable a global turn; the
            # longer persistence threshold is retained for diagnostic labelling.
            bias_guard_active = bias_guard_active or bool(np.any(bias_evidence))
        eligible = valid & ~biased
        eligible_count = int(np.sum(eligible))
        minimum_available = max(
            2,
            math.ceil(config.guarded_min_available_fraction * config.n_agents),
        )

        reliable_delivery = (
            message_age <= config.guarded_max_message_age
            and delivery_ratio >= config.guarded_min_delivery_ratio
        )
        score = 0.0
        corroborating = 0
        coherent_candidate = False
        if eligible_count >= minimum_available:
            center = np.median(standardized_innovations[eligible], axis=0)
            center_norm = float(np.linalg.norm(center))
            eligible_vectors = standardized_innovations[eligible]
            vector_norms = np.linalg.norm(eligible_vectors, axis=1)
            if center_norm > 1e-12:
                alignment = (eligible_vectors @ center) / np.maximum(
                    vector_norms * center_norm,
                    1e-12,
                )
            else:
                alignment = np.zeros(eligible_count, dtype=float)
            eligible_nis = nis_values[eligible] / 2.0
            corroborating_mask = (
                (eligible_nis >= config.guarded_nis_threshold)
                & (alignment >= config.guarded_alignment_threshold)
            )
            corroborating = int(np.sum(corroborating_mask))
            required = max(
                2,
                math.ceil(config.guarded_corroboration_fraction * eligible_count),
            )
            corroboration_fraction = corroborating / max(eligible_count, 1)
            magnitude_score = min(
                1.0,
                center_norm / max(config.guarded_center_threshold, 1e-12),
            )
            score = corroboration_fraction * magnitude_score * min(
                1.0,
                max(0.0, delivery_ratio),
            )
            coherent_candidate = (
                reliable_delivery
                and not bias_guard_active
                and center_norm >= config.guarded_center_threshold
                and corroborating >= required
            )

        if coherent_candidate:
            self._candidate_streak += 1
        else:
            self._candidate_streak = max(0, self._candidate_streak - 1)

        change_event = False
        if (
            coherent_candidate
            and self._candidate_streak >= config.guarded_change_persistence_steps
            and self._cooldown_remaining == 0
        ):
            change_event = True
            self._hold_remaining = config.guarded_hold_steps
            self._cooldown_remaining = (
                config.guarded_hold_steps + config.guarded_cooldown_steps
            )
            self._candidate_streak = 0

        if bias_guard_active:
            self._hold_remaining = 0

        if self._hold_remaining > 0:
            self._hold_remaining -= 1
            momenta = np.full(
                config.n_agents,
                config.guarded_change_momentum,
                dtype=float,
            )
            # Suspected biased agents never receive a surprise-driven turn command.
            momenta[biased] = config.fixed_momentum
            classification = "corroborated_change"
            fallback = False
        else:
            momenta = fixed
            fallback = True
            if message_age > config.guarded_max_message_age:
                classification = "stale_message_fallback"
            elif delivery_ratio < config.guarded_min_delivery_ratio:
                classification = "delivery_degraded_fallback"
            elif valid_count < minimum_available:
                classification = "insufficient_evidence_fallback"
            elif bias_guard_active:
                classification = "persistent_bias_fallback"
            elif corroborating:
                classification = "uncorroborated_surprise_fallback"
            else:
                classification = "fixed_fallback"

        return GuardedMomentumDecision(
            momenta=momenta,
            classification=classification,
            change_score=score,
            corroborating_agents=corroborating,
            biased_agents=int(np.sum(biased)),
            fallback_active=fallback,
            change_event=change_event,
        )


def topological_neighbors(positions: FloatArray, limit: int) -> list[list[int]]:
    neighbors: list[list[int]] = []
    for index, position in enumerate(positions):
        distances = np.linalg.norm(positions - position, axis=1)
        ordering = np.argsort(distances)
        neighbors.append([int(peer) for peer in ordering if peer != index][:limit])
    return neighbors


def _clip_vectors(vectors: FloatArray, maximum_norm: float) -> FloatArray:
    result = vectors.copy()
    norms = np.linalg.norm(result, axis=1)
    mask = norms > maximum_norm
    result[mask] *= (maximum_norm / norms[mask])[:, None]
    return result


def direct_tracking_velocity(
    config: ExperimentConfig, positions: FloatArray, goal_positions: FloatArray
) -> FloatArray:
    desired = config.goal_gain * (goal_positions - positions)
    return _clip_vectors(desired, config.sensor_max_speed)


def adaptive_momentum(config: ExperimentConfig, nis_values: FloatArray) -> FloatArray:
    """Reduce recurrence when normalized innovation signals surprise."""
    normalized = nis_values / 2.0  # Expected NIS equals measurement dimension.
    denominator = config.adaptive_surprise_full - config.adaptive_surprise_start
    surprise = np.clip(
        (normalized - config.adaptive_surprise_start) / denominator,
        0.0,
        1.0,
    )
    return config.adaptive_momentum_max - surprise * (
        config.adaptive_momentum_max - config.adaptive_momentum_min
    )


def flocking_velocity(
    config: ExperimentConfig,
    positions: FloatArray,
    velocities: FloatArray,
    goals: FloatArray,
    neighbors: list[list[int]],
    momenta: FloatArray,
    peer_positions: FloatArray | None = None,
    peer_velocities: FloatArray | None = None,
) -> FloatArray:
    neighbor_positions = positions if peer_positions is None else peer_positions
    neighbor_velocities = velocities if peer_velocities is None else peer_velocities
    accelerations = np.zeros_like(velocities)
    for index, peer_indices in enumerate(neighbors):
        if not peer_indices:
            peer_alignment = np.zeros(2, dtype=float)
            peer_cohesion = np.zeros(2, dtype=float)
        else:
            peers_position = neighbor_positions[peer_indices]
            peers_velocity = neighbor_velocities[peer_indices]
            peer_alignment = np.mean(peers_velocity, axis=0) - velocities[index]
            peer_cohesion = np.mean(peers_position, axis=0) - positions[index]
        separation = np.zeros(2, dtype=float)
        for peer in peer_indices:
            displacement = positions[index] - neighbor_positions[peer]
            distance = max(float(np.linalg.norm(displacement)), 1e-6)
            if distance < config.separation_radius:
                separation += displacement / distance**2
        goal = goals[index] - positions[index]
        accelerations[index] = (
            config.goal_gain * goal
            + config.alignment_gain * peer_alignment
            + config.cohesion_gain * peer_cohesion
            + config.separation_gain * separation
        )
    proposed = momenta[:, None] * velocities + config.dt * accelerations
    return _clip_vectors(proposed, config.sensor_max_speed)


def advance_sensors(
    config: ExperimentConfig, positions: FloatArray, velocities: FloatArray
) -> FloatArray:
    next_positions = positions + velocities * config.dt
    return np.clip(next_positions, -config.workspace_limit, config.workspace_limit)
