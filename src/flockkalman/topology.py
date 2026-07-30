"""Topology-resilient evidence accounting for the M9A research milestone.

The primitives in this module deliberately separate four concepts that were
conflated by the M8 prototype: graph reachability, agent lifecycle, hypothesis
compatibility, and evidential support.  None of the classes receive truth or
fault identities.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

import numpy as np
from numpy.typing import NDArray

from .config import ExperimentConfig
from .filters import constant_velocity_matrices
from .robust import HypothesisFlock, build_hypothesis_flocks


FloatArray = NDArray[np.float64]


class LifecycleState(IntEnum):
    """The sharing lifecycle of one agent belief."""

    OFFLINE = 0
    PROBATION = 1
    TRUSTED = 2


@dataclass(frozen=True, slots=True)
class ComponentSnapshot:
    """Connected-component state for one delivered communication graph."""

    components: tuple[tuple[int, ...], ...]
    labels: NDArray[np.int64]
    epoch: int
    stable_cycles: int
    merge_event: bool
    merge_grace_active: bool


@dataclass(frozen=True, slots=True)
class LifecycleSnapshot:
    """Lifecycle admission state after one local measurement cycle."""

    states: NDArray[np.int64]
    eligible: NDArray[np.bool_]
    admission_weights: FloatArray
    offline_ages: NDArray[np.int64]
    recovery_mask: NDArray[np.bool_]
    probation_count: int
    rejoin_events: int


@dataclass(frozen=True, slots=True)
class TopologyFlockSet:
    """A component-local hypothesis set and its evidence ledger."""

    flocks: list[HypothesisFlock]
    visible_members: tuple[int, ...]
    observer_component_id: int
    live_support: float
    retained_support: float
    unknown_support: float
    duplicate_support_suppressed: float


def connected_components(
    neighbors: list[list[int]],
    operational: NDArray[np.bool_],
) -> tuple[tuple[tuple[int, ...], ...], NDArray[np.int64]]:
    """Return deterministic weak components of the delivered directed graph."""
    count = len(neighbors)
    adjacency = [set() for _ in range(count)]
    for source, peers in enumerate(neighbors):
        if not operational[source]:
            continue
        for peer in peers:
            if operational[peer]:
                adjacency[source].add(int(peer))
                adjacency[int(peer)].add(source)

    remaining = {int(index) for index in np.flatnonzero(operational)}
    components: list[tuple[int, ...]] = []
    while remaining:
        root = min(remaining)
        remaining.remove(root)
        members = [root]
        frontier = [root]
        while frontier:
            current = frontier.pop()
            for peer in sorted(adjacency[current]):
                if peer in remaining:
                    remaining.remove(peer)
                    frontier.append(peer)
                    members.append(peer)
        components.append(tuple(sorted(members)))
    components.sort(key=lambda item: item[0])
    labels = np.full(count, -1, dtype=np.int64)
    for component_id, members in enumerate(components):
        labels[list(members)] = component_id
    return tuple(components), labels


class ComponentEpochTracker:
    """Assign epochs to topology changes and bound post-merge decisions."""

    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        self._signature: tuple[tuple[int, ...], ...] | None = None
        self._epoch = 0
        self._stable_cycles = 0
        self._merge_grace_remaining = 0

    def update(
        self,
        neighbors: list[list[int]],
        operational: NDArray[np.bool_],
    ) -> ComponentSnapshot:
        components, labels = connected_components(neighbors, operational)
        signature = components
        changed = signature != self._signature
        merge_event = False
        if changed:
            if self._signature is not None:
                previous_sets = [set(item) for item in self._signature]
                merge_event = any(
                    sum(bool(set(component) & previous) for previous in previous_sets) > 1
                    for component in components
                )
                self._epoch += 1
            self._signature = signature
            self._stable_cycles = 1
            if merge_event:
                self._merge_grace_remaining = self.config.topology_merge_grace_steps
        else:
            self._stable_cycles += 1

        grace_active = self._merge_grace_remaining > 0
        if self._merge_grace_remaining > 0:
            self._merge_grace_remaining -= 1
        return ComponentSnapshot(
            components=components,
            labels=labels,
            epoch=self._epoch,
            stable_cycles=self._stable_cycles,
            merge_event=merge_event,
            merge_grace_active=grace_active,
        )


class AgentLifecycleManager:
    """Enforce OFFLINE -> PROBATION -> TRUSTED before belief sharing."""

    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        self._states = np.full(
            config.n_agents, int(LifecycleState.TRUSTED), dtype=np.int64
        )
        self._previous_operational = np.ones(config.n_agents, dtype=bool)
        self._offline_ages = np.zeros(config.n_agents, dtype=np.int64)
        self._consistent_cycles = np.zeros(config.n_agents, dtype=np.int64)
        self._ramp_cycles = np.full(
            config.n_agents, config.topology_rejoin_ramp_steps, dtype=np.int64
        )

    def update(
        self,
        operational: NDArray[np.bool_],
        available: NDArray[np.bool_],
        nis_values: FloatArray,
        *,
        component_stable_cycles: int,
    ) -> LifecycleSnapshot:
        recovery_mask = operational & ~self._previous_operational
        failure_mask = ~operational & self._previous_operational

        self._states[failure_mask] = int(LifecycleState.OFFLINE)
        self._consistent_cycles[failure_mask] = 0
        self._ramp_cycles[failure_mask] = 0
        self._offline_ages[~operational] += 1

        self._states[recovery_mask] = int(LifecycleState.PROBATION)
        self._consistent_cycles[recovery_mask] = 0
        self._ramp_cycles[recovery_mask] = 0

        probation = self._states == int(LifecycleState.PROBATION)
        consistent = (
            probation
            & operational
            & available
            & np.isfinite(nis_values)
            & (nis_values <= self.config.topology_rejoin_nis_threshold)
            & (
                component_stable_cycles
                >= self.config.topology_rejoin_component_stable_steps
            )
        )
        self._consistent_cycles[consistent] += 1
        self._consistent_cycles[probation & ~consistent] = 0
        admitted = probation & (
            self._consistent_cycles >= self.config.topology_rejoin_probation_steps
        )
        self._states[admitted] = int(LifecycleState.TRUSTED)
        self._ramp_cycles[admitted] = 1

        trusted = operational & (self._states == int(LifecycleState.TRUSTED))
        ramping = trusted & (
            self._ramp_cycles < self.config.topology_rejoin_ramp_steps
        )
        self._ramp_cycles[ramping] += (~admitted[ramping]).astype(np.int64)
        weights = np.zeros(self.config.n_agents, dtype=float)
        weights[trusted] = np.minimum(
            1.0,
            self._ramp_cycles[trusted]
            / max(self.config.topology_rejoin_ramp_steps, 1),
        )
        # Agents that never left start at full support.
        weights[trusted & (self._offline_ages == 0)] = 1.0
        self._previous_operational = operational.copy()
        return LifecycleSnapshot(
            states=self._states.copy(),
            eligible=trusted,
            admission_weights=weights,
            offline_ages=self._offline_ages.copy(),
            recovery_mask=recovery_mask.copy(),
            probation_count=int(np.sum(self._states == int(LifecycleState.PROBATION))),
            rejoin_events=int(np.sum(recovery_mask)),
        )

    def recovery_covariance_inflation(
        self,
        recovery_mask: NDArray[np.bool_],
    ) -> list[FloatArray]:
        """Return additive admission covariance for newly recovered agents."""
        additions: list[FloatArray] = []
        for index in range(self.config.n_agents):
            age = int(self._offline_ages[index]) if recovery_mask[index] else 0
            position = self.config.topology_rejoin_covariance_inflation * age
            velocity = 0.25 * position
            additions.append(np.diag([position, position, velocity, velocity]))
        return additions


class HypothesisMemory:
    """Retain disappeared mode identities without treating memory as a vote."""

    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        self._records: dict[int, HypothesisFlock] = {}
        self._next_id = 0

    @staticmethod
    def _distance(first: HypothesisFlock, second: HypothesisFlock) -> float:
        delta = first.state[:2] - second.state[:2]
        covariance = first.covariance[:2, :2] + second.covariance[:2, :2]
        return float(delta @ np.linalg.solve(covariance, delta))

    @staticmethod
    def _overlap(first: HypothesisFlock, second: HypothesisFlock) -> int:
        return len(set(first.contributors) & set(second.contributors))

    @staticmethod
    def _euclidean(first: HypothesisFlock, second: HypothesisFlock) -> float:
        return float(np.linalg.norm(first.state[:2] - second.state[:2]))

    def stabilize(
        self,
        flocks: list[HypothesisFlock],
    ) -> tuple[list[HypothesisFlock], float]:
        unmatched = set(self._records)
        stabilized: list[HypothesisFlock] = []
        next_records: dict[int, HypothesisFlock] = {}
        for flock in sorted(flocks, key=lambda item: (-item.live_support, item.flock_id)):
            candidates = [
                record_id
                for record_id in unmatched
                if self._distance(flock, self._records[record_id])
                <= self.config.robust_compatibility_threshold
                and self._euclidean(flock, self._records[record_id])
                <= self.config.topology_hypothesis_match_distance
            ]
            if candidates:
                record_id = min(
                    candidates,
                    key=lambda item: (
                        -self._overlap(flock, self._records[item]),
                        self._distance(flock, self._records[item]),
                    ),
                )
                unmatched.remove(record_id)
            else:
                record_id = self._next_id
                self._next_id += 1
            stable = HypothesisFlock(
                flock_id=record_id,
                members=flock.members,
                state=flock.state,
                covariance=flock.covariance,
                weight=flock.weight,
                live_support=flock.live_support,
                retained_support=flock.retained_support,
                unknown_support=flock.unknown_support,
                contributors=flock.contributors,
                component_id=flock.component_id,
                component_epoch=flock.component_epoch,
            )
            stabilized.append(stable)
            next_records[record_id] = stable

        retained = 0.0
        retained_flocks: list[HypothesisFlock] = []
        transition, process = constant_velocity_matrices(
            self.config.dt,
            self.config.filter_process_variance,
        )
        live_mass = sum(max(flock.live_support, 0.0) for flock in stabilized)
        reference_velocity = (
            sum(
                (
                    flock.live_support * flock.state[2:4]
                    for flock in stabilized
                ),
                start=np.zeros(2, dtype=float),
            )
            / live_mass
            if live_mass > 0.0
            else None
        )
        for record_id in unmatched:
            old = self._records[record_id]
            if any(
                self._euclidean(old, live)
                <= self.config.output_mode_equivalence_distance
                for live in stabilized
            ):
                continue
            historical = max(old.live_support, old.retained_support)
            historical *= self.config.topology_retained_support_decay
            if historical < 1e-3:
                continue
            retained += historical
            predicted_state = transition @ old.state
            if reference_velocity is not None:
                predicted_state[:2] = (
                    old.state[:2] + reference_velocity * self.config.dt
                )
                predicted_state[2:4] = reference_velocity
            predicted_covariance = (
                transition @ old.covariance @ transition.T + process
            )
            predicted_covariance = 0.5 * (
                predicted_covariance + predicted_covariance.T
            )
            retained_flock = HypothesisFlock(
                flock_id=record_id,
                members=(),
                state=predicted_state,
                covariance=predicted_covariance,
                weight=0.0,
                live_support=0.0,
                retained_support=historical,
                unknown_support=old.unknown_support,
                contributors=old.contributors,
                component_id=old.component_id,
                component_epoch=old.component_epoch,
            )
            next_records[record_id] = retained_flock
            retained_flocks.append(retained_flock)
        # A contributor epoch may be copied into several beliefs.  Keep only
        # the strongest representative of equivalent retained modes.
        retained_flocks.sort(key=lambda item: -item.retained_support)
        unique_retained: list[HypothesisFlock] = []
        for flock in retained_flocks:
            if any(
                self._euclidean(flock, other)
                <= self.config.output_mode_equivalence_distance
                and set(flock.contributors) == set(other.contributors)
                for other in unique_retained
            ):
                next_records.pop(flock.flock_id, None)
                retained -= flock.retained_support
                continue
            unique_retained.append(flock)
        retained_flocks = unique_retained
        self._records = next_records
        stabilized.extend(retained_flocks)
        stabilized.sort(
            key=lambda item: (
                item.live_support <= 0.0,
                -item.live_support,
                -item.retained_support,
                item.flock_id,
            )
        )
        return stabilized, retained


def _mask_members(mask: int, count: int) -> tuple[int, ...]:
    return tuple(index for index in range(count) if mask & (1 << index))


def build_topology_flocks(
    states: list[FloatArray],
    covariances: list[FloatArray],
    trusted_agents: NDArray[np.bool_],
    admission_weights: FloatArray,
    provenance_masks: list[int],
    component_snapshot: ComponentSnapshot,
    config: ExperimentConfig,
    *,
    mode_labels: NDArray[np.int64] | None,
    component_local: bool,
    observer_anchor: int = 0,
) -> TopologyFlockSet:
    """Build component-local flocks with live/retained/unknown accounting."""
    if component_local and component_snapshot.components:
        label = int(component_snapshot.labels[observer_anchor])
        if label < 0:
            label = 0
        visible = component_snapshot.components[label]
        component_id = label
    else:
        visible = tuple(
            int(index)
            for index in np.flatnonzero(component_snapshot.labels >= 0)
        )
        component_id = -1

    visible_mask = np.zeros(config.n_agents, dtype=bool)
    visible_mask[list(visible)] = True
    eligible = trusted_agents & visible_mask & (admission_weights > 0.0)
    base_flocks = build_hypothesis_flocks(
        states,
        covariances,
        eligible,
        compatibility_threshold=config.robust_compatibility_threshold,
        grid_points=config.ci_grid_points,
        mode_labels=mode_labels,
        fallback_if_empty=False,
    )

    live_total = float(np.sum(admission_weights[eligible]))
    unknown = max(0.0, float(config.n_agents) - live_total)
    duplicate_suppressed = 0.0
    flocks: list[HypothesisFlock] = []
    for flock in base_flocks:
        live = float(np.sum(admission_weights[list(flock.members)]))
        contributor_mask = 0
        raw_contributors = 0
        for member in flock.members:
            contributor_mask |= provenance_masks[member]
            raw_contributors += provenance_masks[member].bit_count()
        unique_contributors = contributor_mask.bit_count()
        duplicate_suppressed += max(0, raw_contributors - unique_contributors)
        flocks.append(
            HypothesisFlock(
                flock_id=flock.flock_id,
                members=flock.members,
                state=flock.state,
                covariance=flock.covariance,
                weight=live / config.n_agents,
                live_support=live,
                retained_support=0.0,
                unknown_support=unknown,
                contributors=_mask_members(contributor_mask, config.n_agents),
                component_id=component_id,
                component_epoch=component_snapshot.epoch,
            )
        )

    if not flocks:
        fallback = next(iter(visible), observer_anchor)
        flocks = [
            HypothesisFlock(
                flock_id=0,
                members=(fallback,),
                state=states[fallback].copy(),
                covariance=covariances[fallback].copy(),
                weight=1e-12,
                live_support=0.0,
                retained_support=0.0,
                unknown_support=float(config.n_agents),
                contributors=(),
                component_id=component_id,
                component_epoch=component_snapshot.epoch,
            )
        ]
        unknown = float(config.n_agents)

    flocks.sort(key=lambda item: (-item.live_support, item.flock_id))
    return TopologyFlockSet(
        flocks=flocks,
        visible_members=visible,
        observer_component_id=component_id,
        live_support=live_total,
        retained_support=0.0,
        unknown_support=unknown,
        duplicate_support_suppressed=duplicate_suppressed,
    )
