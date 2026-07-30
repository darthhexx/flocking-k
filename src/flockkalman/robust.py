"""Bias-state tracking and explicit multi-flock hypothesis management."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from numpy.typing import NDArray

from .config import ExperimentConfig
from .filters import covariance_intersection


FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class EvidenceAssessment:
    """Per-cycle robust evidence decision before local filter updates."""

    corrected_observations: FloatArray
    trusted_agents: NDArray[np.bool_]
    quarantined_agents: NDArray[np.bool_]
    suspected_bias_agents: NDArray[np.bool_]
    alternative_mode_agents: NDArray[np.bool_]
    mode_labels: NDArray[np.int64]
    bias_estimates: FloatArray


class BiasModeTracker:
    """Estimate persistent source offsets without erasing supported modes.

    Residuals are measured relative to the coordinate-wise median observation.
    Small, persistently displaced source groups are treated as bias candidates;
    sufficiently large coherent groups remain trusted as alternative modes.
    """

    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        self._bias_ema = np.zeros((config.n_agents, 2), dtype=float)
        self._bias_streak = np.zeros(config.n_agents, dtype=np.int64)

    @staticmethod
    def _groups(
        vectors: FloatArray,
        indices: list[int],
        tolerance: float,
    ) -> list[list[int]]:
        remaining = set(indices)
        groups: list[list[int]] = []
        while remaining:
            root = min(remaining)
            remaining.remove(root)
            group = [root]
            frontier = [root]
            while frontier:
                current = frontier.pop()
                connected = [
                    index
                    for index in sorted(remaining)
                    if float(np.linalg.norm(vectors[current] - vectors[index]))
                    <= tolerance
                ]
                for index in connected:
                    remaining.remove(index)
                    frontier.append(index)
                    group.append(index)
            groups.append(sorted(group))
        return groups

    def update(
        self,
        observations: FloatArray,
        available: NDArray[np.bool_],
    ) -> EvidenceAssessment:
        config = self.config
        valid_indices = [int(index) for index in np.flatnonzero(available)]
        corrected = observations.copy()
        suspected = np.zeros(config.n_agents, dtype=bool)
        alternative = np.zeros(config.n_agents, dtype=bool)
        mode_labels = np.zeros(config.n_agents, dtype=np.int64)

        if valid_indices:
            center = np.median(observations[valid_indices], axis=0)
            residuals = observations - center
            alpha = config.robust_bias_ema_alpha
            self._bias_ema[available] = (
                (1.0 - alpha) * self._bias_ema[available]
                + alpha * residuals[available]
            )
            candidate_indices = [
                index
                for index in valid_indices
                if float(np.linalg.norm(self._bias_ema[index]))
                >= config.robust_bias_threshold
            ]
            minimum_mode_size = max(
                2,
                math.ceil(config.robust_mode_min_fraction * len(valid_indices)),
            )
            alternative_label = 1
            for group in self._groups(
                self._bias_ema,
                candidate_indices,
                config.robust_bias_group_tolerance,
            ):
                if len(group) >= minimum_mode_size:
                    alternative[group] = True
                    mode_labels[group] = alternative_label
                    alternative_label += 1
                else:
                    suspected[group] = True

        self._bias_streak[suspected] += 1
        self._bias_streak[available & ~suspected] = np.maximum(
            0,
            self._bias_streak[available & ~suspected] - 1,
        )
        quarantined = (
            self._bias_streak >= config.robust_bias_persistence_steps
        ) & ~alternative
        trusted = ~suspected & ~quarantined

        # A suspected minority offset is an explicit measurement-bias state.
        # Large coherent groups are not corrected because they represent a
        # supported alternative hypothesis rather than an isolated bad source.
        corrected[suspected] -= self._bias_ema[suspected]
        return EvidenceAssessment(
            corrected_observations=corrected,
            trusted_agents=trusted,
            quarantined_agents=quarantined,
            suspected_bias_agents=suspected,
            alternative_mode_agents=alternative,
            mode_labels=mode_labels,
            bias_estimates=self._bias_ema.copy(),
        )

    def reset_agents(self, agents: NDArray[np.bool_]) -> None:
        """Discard stale bias persistence when agents start a new evidence epoch."""
        self._bias_ema[agents] = 0.0
        self._bias_streak[agents] = 0


@dataclass(frozen=True, slots=True)
class HypothesisFlock:
    """A compatible set of agent beliefs and its conservative fused state."""

    flock_id: int
    members: tuple[int, ...]
    state: FloatArray
    covariance: FloatArray
    weight: float
    live_support: float = 0.0
    retained_support: float = 0.0
    unknown_support: float = 0.0
    contributors: tuple[int, ...] = ()
    component_id: int = -1
    component_epoch: int = 0


def build_hypothesis_flocks(
    states: list[FloatArray],
    covariances: list[FloatArray],
    trusted_agents: NDArray[np.bool_],
    *,
    compatibility_threshold: float,
    grid_points: int,
    mode_labels: NDArray[np.int64] | None = None,
    fallback_if_empty: bool = True,
) -> list[HypothesisFlock]:
    """Cluster compatible posteriors and fuse only within each cluster."""
    indices = [int(index) for index in np.flatnonzero(trusted_agents)]
    if not indices and fallback_if_empty:
        indices = list(range(len(states)))
    if not indices:
        return []
    parent = {index: index for index in indices}

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        root_first = find(first)
        root_second = find(second)
        if root_first != root_second:
            parent[max(root_first, root_second)] = min(root_first, root_second)

    for offset, first in enumerate(indices):
        for second in indices[offset + 1 :]:
            if mode_labels is not None and mode_labels[first] != mode_labels[second]:
                continue
            delta = states[first][:2] - states[second][:2]
            joint_covariance = (
                covariances[first][:2, :2] + covariances[second][:2, :2]
            )
            disagreement = float(
                delta @ np.linalg.solve(joint_covariance, delta)
            )
            if disagreement <= compatibility_threshold:
                union(first, second)

    grouped: dict[int, list[int]] = {}
    for index in indices:
        grouped.setdefault(find(index), []).append(index)
    ordered_groups = sorted(
        (sorted(group) for group in grouped.values()),
        key=lambda group: (-len(group), group[0]),
    )
    total = sum(len(group) for group in ordered_groups)
    flocks: list[HypothesisFlock] = []
    for flock_id, group in enumerate(ordered_groups):
        state = states[group[0]].copy()
        covariance = covariances[group[0]].copy()
        for index in group[1:]:
            state, covariance = covariance_intersection(
                state,
                covariance,
                states[index],
                covariances[index],
                grid_points,
            )
        flocks.append(
            HypothesisFlock(
                flock_id=flock_id,
                members=tuple(group),
                state=state,
                covariance=covariance,
                weight=len(group) / max(total, 1),
            )
        )
    return flocks


def flock_membership(
    flocks: list[HypothesisFlock],
    n_agents: int,
) -> NDArray[np.int64]:
    membership = np.full(n_agents, -1, dtype=np.int64)
    for flock in flocks:
        membership[list(flock.members)] = flock.flock_id
    return membership
