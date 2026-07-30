"""Truth-blind policies for turning hypothesis flocks into an external output."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from .config import ExperimentConfig
from .robust import HypothesisFlock


FloatArray = NDArray[np.float64]
OUTPUT_POLICIES = ("largest", "temporal", "mixture", "defer", "active")


@dataclass(frozen=True, slots=True)
class OutputDecision:
    """One truth-blind output action and the state exposed to legacy consumers."""

    action: str
    state: FloatArray
    covariance: FloatArray
    selected_flock_id: int | None
    confidence: float


def moment_match(flocks: list[HypothesisFlock]) -> tuple[FloatArray, FloatArray]:
    """Moment-match a weighted hypothesis set without pretending it is unimodal."""
    weights = np.asarray([flock.weight for flock in flocks], dtype=float)
    total = float(np.sum(weights))
    if total <= 0.0:
        weights = np.full(len(flocks), 1.0 / len(flocks), dtype=float)
    else:
        weights /= total
    state = sum(
        (weight * flock.state for weight, flock in zip(weights, flocks)),
        start=np.zeros_like(flocks[0].state),
    )
    covariance = np.zeros_like(flocks[0].covariance)
    for weight, flock in zip(weights, flocks):
        delta = flock.state - state
        covariance += weight * (flock.covariance + np.outer(delta, delta))
    covariance = 0.5 * (covariance + covariance.T)
    return state, covariance


class HypothesisOutputController:
    """Stateful output policy that never receives truth or fault identities."""

    def __init__(self, config: ExperimentConfig, policy: str) -> None:
        if policy not in OUTPUT_POLICIES:
            raise ValueError(f"unknown output policy: {policy}")
        self.config = config
        self.policy = policy
        self._previous_state: FloatArray | None = None
        self._ambiguous_cycles = 0
        self._ambiguity_streak = 0
        self._resolution_streak = 0
        self._ambiguity_seen = False

    def _support_groups(self, flocks: list[HypothesisFlock]) -> list[list[int]]:
        remaining = set(range(len(flocks)))
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
                    if float(
                        np.linalg.norm(
                            flocks[current].state[:2] - flocks[index].state[:2]
                        )
                    )
                    <= self.config.output_mode_equivalence_distance
                ]
                for index in connected:
                    remaining.remove(index)
                    frontier.append(index)
                    group.append(index)
            groups.append(sorted(group))
        return sorted(
            groups,
            key=lambda group: (
                -sum(flocks[index].weight for index in group),
                min(flocks[index].flock_id for index in group),
            ),
        )

    def _confidence(
        self,
        flocks: list[HypothesisFlock],
        unknown_support: float = 0.0,
    ) -> float:
        groups = self._support_groups(flocks)
        if len(groups) == 1:
            leading = sum(flocks[index].weight for index in groups[0])
            if unknown_support <= 0.0:
                return 1.0
            return float(leading - unknown_support)
        weights = sorted(
            (sum(flocks[index].weight for index in group) for group in groups),
            reverse=True,
        )
        return float(weights[0] - weights[1] - unknown_support)

    def _supported_choice(self, flocks: list[HypothesisFlock]) -> HypothesisFlock:
        leading_group = self._support_groups(flocks)[0]
        candidates = [flocks[index] for index in leading_group]
        return self._temporal_choice(candidates)

    def _select(self, flock: HypothesisFlock, confidence: float) -> OutputDecision:
        self._previous_state = flock.state.copy()
        return OutputDecision(
            action="select",
            state=flock.state,
            covariance=flock.covariance,
            selected_flock_id=flock.flock_id,
            confidence=confidence,
        )

    def _temporal_choice(self, flocks: list[HypothesisFlock]) -> HypothesisFlock:
        if self._previous_state is None:
            return flocks[0]
        predicted = self._previous_state.copy()
        predicted[:2] += predicted[2:4] * self.config.dt
        return min(
            flocks,
            key=lambda flock: float(
                np.linalg.norm(flock.state[:2] - predicted[:2])
            ),
        )

    def decide(
        self,
        flocks: list[HypothesisFlock],
        *,
        unknown_support: float = 0.0,
        force_defer: bool = False,
    ) -> OutputDecision:
        if not flocks:
            raise ValueError("at least one hypothesis flock is required")
        confidence = self._confidence(flocks, unknown_support)

        if self.policy == "largest":
            return self._select(flocks[0], confidence)

        if self.policy == "temporal":
            return self._select(self._temporal_choice(flocks), confidence)

        mixture_state, mixture_covariance = moment_match(flocks)
        if force_defer:
            return OutputDecision(
                action="defer",
                state=mixture_state,
                covariance=mixture_covariance,
                selected_flock_id=None,
                confidence=confidence,
            )
        if self.policy == "mixture":
            self._previous_state = mixture_state.copy()
            return OutputDecision(
                action="mixture",
                state=mixture_state,
                covariance=mixture_covariance,
                selected_flock_id=None,
                confidence=confidence,
            )

        if self.policy == "defer":
            return OutputDecision(
                action="defer",
                state=mixture_state,
                covariance=mixture_covariance,
                selected_flock_id=None,
                confidence=confidence,
            )

        # Active policy: decisive evidence selects; symmetric ambiguity first
        # triggers bounded investigation and then an explicit deferral.
        conservative_ambiguity = (
            unknown_support > 0.0
            and confidence < self.config.output_confidence_margin
        )
        if len(flocks) > 1 or conservative_ambiguity:
            self._resolution_streak = 0
            if confidence >= self.config.output_confidence_margin:
                self._ambiguous_cycles = 0
                self._ambiguity_streak = 0
                return self._select(self._supported_choice(flocks), confidence)
            self._ambiguity_streak += 1
            if (
                not conservative_ambiguity
                and self._ambiguity_streak
                < self.config.output_ambiguity_persistence_steps
            ):
                return self._select(self._temporal_choice(flocks), confidence)
            self._ambiguity_seen = True
            self._ambiguous_cycles += 1
            action = (
                "investigate"
                if self._ambiguous_cycles <= self.config.output_investigation_horizon
                else "defer"
            )
            return OutputDecision(
                action=action,
                state=mixture_state,
                covariance=mixture_covariance,
                selected_flock_id=None,
                confidence=confidence,
            )

        self._ambiguity_streak = 0
        if self._ambiguity_seen:
            self._resolution_streak += 1
            if self._resolution_streak < self.config.output_resolution_persistence_steps:
                return OutputDecision(
                    action="investigate",
                    state=flocks[0].state,
                    covariance=flocks[0].covariance,
                    selected_flock_id=None,
                    confidence=confidence,
                )
            self._ambiguity_seen = False
            self._ambiguous_cycles = 0
            self._resolution_streak = 0
        return self._select(flocks[0], confidence)


def investigation_goals(
    flocks: list[HypothesisFlock],
    n_agents: int,
) -> FloatArray:
    """Allocate mobile sensors across surviving hypotheses without truth access."""
    goals = np.zeros((n_agents, 2), dtype=float)
    for index in range(n_agents):
        goals[index] = flocks[index % len(flocks)].state[:2]
    return goals
