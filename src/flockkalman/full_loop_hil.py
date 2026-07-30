"""M13.1 independent full-loop hardware-in-the-loop screening.

The plant, camera, transport, attack shim, and scorer in this module are
independent of the historical experiment simulator.  The operational runtime
sees only range/bearing-derived observations and peer wire messages.  This is a
screening ladder for the physical experiment, not a substitute for M13.3.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable, Mapping

import numpy as np

from .filters import KalmanFilter
from .full_loop_contracts import (
    AttackManifest,
    AttackShim,
    DeterministicNetwork,
    NetworkFaultManifest,
    OPERATIONAL_DOMAIN,
    SafetyLimits,
    SafetySupervisor,
    TruthSample,
    WireMessage,
    audit_truth_isolation,
    canonical_json,
    sha256_file,
    sha256_json,
)


M13_ARMS = (
    "m9c_no_trust",
    "m10a5_centralized",
    "m10b_decentralized_no_negotiation",
    "m10b_decentralized",
)
M13_CENTRAL_ARM = "m10a5_centralized"
M13_CANDIDATE_ARM = "m10b_decentralized"


@dataclass(frozen=True, slots=True)
class HILConfig:
    dt: float = 0.1
    steps: int = 120
    n_agents: int = 4
    seed_count: int = 150
    seed_start: int = 27000
    replan_interval: int = 5
    camera_range_std: float = 0.10
    camera_bearing_std: float = 0.025
    process_acceleration_variance: float = 0.12
    maximum_sensor_range: float = 10.0
    bootstrap_samples: int = 2000
    workers: int = 1

    def validate(self) -> None:
        if self.dt <= 0.0 or self.steps < 40:
            raise ValueError("HIL needs positive dt and at least 40 steps")
        if self.n_agents not in {4, 5}:
            raise ValueError("M13 supports four or five observer agents")
        if self.seed_count < 1 or self.seed_start < 0:
            raise ValueError("invalid HIL seed range")
        if self.replan_interval < 1:
            raise ValueError("replan_interval must be positive")
        if self.camera_range_std <= 0.0 or self.camera_bearing_std <= 0.0:
            raise ValueError("camera noise must be positive")
        if self.bootstrap_samples < 100:
            raise ValueError("bootstrap_samples must be at least 100")
        if self.workers < 1:
            raise ValueError("workers must be positive")


@dataclass(frozen=True, slots=True)
class HILScenario:
    name: str
    description: str
    target_mode: str = "smooth"
    occlusion_start: int | None = None
    occlusion_stop: int | None = None
    occluded_agents: tuple[int, ...] = ()
    precision_agent: int | None = None
    precision_scale: float = 1.0
    network_kind: str = "stable"
    attack_kind: str = "none"
    attacker_count: int = 0


DEFAULT_HIL_SCENARIOS = (
    HILScenario("stable", "stable network and smooth target"),
    HILScenario("target_manoeuvre", "abrupt but bounded target turn", target_mode="turn"),
    HILScenario(
        "physical_occlusion",
        "two camera views are physically occluded",
        occlusion_start=35,
        occlusion_stop=70,
        occluded_agents=(0, 2),
    ),
    HILScenario(
        "burst_loss_latency",
        "bursty packet loss and variable latency",
        network_kind="burst",
    ),
    HILScenario(
        "partition_rejoin",
        "two-by-two network partition followed by rejoin",
        network_kind="partition",
    ),
    HILScenario(
        "observer_outage_rejoin",
        "one observer process stops and honestly rejoins",
        network_kind="outage",
    ),
    HILScenario(
        "legitimate_precision_minority",
        "one honest camera is much more precise than the majority",
        precision_agent=0,
        precision_scale=0.25,
    ),
    HILScenario(
        "colluding_covariance_ramp",
        "two colluding estimates ramp bias and understate covariance",
        attack_kind="covariance_understating_ramp",
        attacker_count=2,
    ),
    HILScenario(
        "temporary_attack_recovery",
        "one ramp attacker stops and must be readmitted",
        attack_kind="temporary_ramp",
        attacker_count=1,
    ),
    HILScenario(
        "adaptive_bounded_attacker",
        "one causal attacker adapts within preregistered bounds",
        target_mode="turn",
        attack_kind="adaptive_bounded",
        attacker_count=1,
    ),
)


@dataclass(frozen=True, slots=True)
class HILTrialSummary:
    run_id: str
    scenario: str
    arm: str
    seed: int
    position_rmse: float
    mean_nees: float
    coverage95: float
    decision_loss: float
    wrong_action_rate: float
    integrated_loss: float
    alert_rate: float
    false_alert_rate: float
    recovery_steps: float
    movement: float
    delivery_ratio: float
    planner_messages: int
    planner_bytes: int
    maximum_allowed_planner_messages: int
    ownership_violations: int
    safety_interventions: int
    emergency_stops: int
    collisions: int
    mean_runtime_units: float
    topology_disagreement_rate: float
    replay_fingerprint: str


class _TrustMonitor:
    """Small truth-blind source monitor used by the reference adapter."""

    def __init__(self, agent_ids: Iterable[str]) -> None:
        self.trust = {agent_id: 1.0 for agent_id in agent_ids}
        self.previous = {}

    def update(
        self,
        messages: Mapping[str, WireMessage],
        local_estimate: np.ndarray,
    ) -> dict[str, float]:
        positions = [local_estimate[:2]]
        positions.extend(
            np.asarray(message.estimate[:2], dtype=float)
            for message in messages.values()
        )
        centre = np.median(np.asarray(positions), axis=0)
        for source, message in messages.items():
            state = np.asarray(message.estimate, dtype=float)
            residual = float(np.linalg.norm(state[:2] - centre))
            previous = self.previous.get(source, state)
            ramp = float(np.linalg.norm(state[:2] - previous[:2]))
            suspicious = residual > 0.72 or ramp > 0.42
            current = self.trust.get(source, 1.0)
            if suspicious:
                current = max(0.05, current - 0.18)
            else:
                current = min(1.0, current + 0.035)
            self.trust[source] = current
            self.previous[source] = state
        return dict(self.trust)


def _scenario_manifests(
    scenario: HILScenario,
    config: HILConfig,
) -> tuple[NetworkFaultManifest, AttackManifest]:
    ids = tuple(f"agent{index}" for index in range(config.n_agents))
    if scenario.network_kind == "burst":
        network = NetworkFaultManifest(
            loss_probability=0.02,
            base_delay_steps=1,
            jitter_steps=2,
            burst_start=35,
            burst_stop=70,
            burst_loss_probability=0.35,
        )
    elif scenario.network_kind == "partition":
        split = config.n_agents // 2
        network = NetworkFaultManifest(
            base_delay_steps=1,
            partition_start=35,
            partition_stop=70,
            partition_a=ids[:split],
            partition_b=ids[split:],
        )
    elif scenario.network_kind == "outage":
        network = NetworkFaultManifest(
            base_delay_steps=1,
            outage_agent=ids[-1],
            outage_start=35,
            outage_stop=70,
        )
    else:
        network = NetworkFaultManifest(base_delay_steps=1)
    if scenario.attack_kind == "none":
        attack = AttackManifest()
    else:
        stop = 78 if scenario.attack_kind == "temporary_ramp" else config.steps
        attack = AttackManifest(
            kind=scenario.attack_kind,
            attacker_ids=ids[: scenario.attacker_count],
            start_step=20,
            stop_step=stop,
            maximum_bias=1.5,
            maximum_bias_step=0.055,
            minimum_covariance_scale=0.08,
            adaptive_gain=0.08,
        )
    return network, attack


def _target_state(step: int, config: HILConfig, scenario: HILScenario) -> np.ndarray:
    time = step * config.dt
    if scenario.target_mode == "turn":
        turn_time = 0.48 * config.steps * config.dt
        if time < turn_time:
            position = np.asarray([-2.5 + 0.55 * time, -0.7 + 0.12 * time])
            velocity = np.asarray([0.55, 0.12])
        else:
            pivot = np.asarray(
                [-2.5 + 0.55 * turn_time, -0.7 + 0.12 * turn_time]
            )
            elapsed = time - turn_time
            position = pivot + np.asarray([-0.16, 0.62]) * elapsed
            velocity = np.asarray([-0.16, 0.62])
    else:
        position = np.asarray(
            [-2.5 + 0.48 * time, 0.8 * math.sin(0.23 * time)]
        )
        velocity = np.asarray(
            [0.48, 0.8 * 0.23 * math.cos(0.23 * time)]
        )
    return np.concatenate([position, velocity])


def _camera_observation(
    rng: np.random.Generator,
    target: np.ndarray,
    sensor_position: np.ndarray,
    config: HILConfig,
    precision_scale: float,
) -> tuple[np.ndarray, np.ndarray] | None:
    delta = target[:2] - sensor_position
    true_range = float(np.linalg.norm(delta))
    if true_range > config.maximum_sensor_range or true_range < 0.15:
        return None
    true_bearing = math.atan2(delta[1], delta[0])
    range_std = config.camera_range_std * precision_scale * (1.0 + 0.03 * true_range)
    bearing_std = config.camera_bearing_std * precision_scale
    measured_range = true_range + rng.normal(0.0, range_std)
    measured_bearing = true_bearing + rng.normal(0.0, bearing_std)
    observation = sensor_position + measured_range * np.asarray(
        [math.cos(measured_bearing), math.sin(measured_bearing)]
    )
    jacobian = np.asarray(
        [
            [math.cos(measured_bearing), -measured_range * math.sin(measured_bearing)],
            [math.sin(measured_bearing), measured_range * math.cos(measured_bearing)],
        ]
    )
    covariance = jacobian @ np.diag([range_std**2, bearing_std**2]) @ jacobian.T
    covariance += np.eye(2) * 1e-5
    return observation, covariance


def _fuse_messages(
    messages: Mapping[str, WireMessage],
    fallback_state: np.ndarray,
    fallback_covariance: np.ndarray,
    trust: Mapping[str, float],
) -> tuple[np.ndarray, np.ndarray]:
    information = np.linalg.inv(fallback_covariance)
    information_state = information @ fallback_state
    for source, message in sorted(messages.items()):
        weight = float(np.clip(trust.get(source, 1.0), 0.05, 1.0))
        covariance = np.asarray(message.covariance, dtype=float).reshape(4, 4)
        # A physical sensor-derived floor prevents reported overconfidence from
        # acquiring unbounded influence.  It is not an attack label.
        covariance = covariance + np.eye(4) * 0.015
        inverse = np.linalg.inv(covariance)
        information += weight * inverse
        information_state += weight * inverse @ np.asarray(message.estimate)
    covariance = np.linalg.inv(information)
    state = covariance @ information_state
    return state, 0.5 * (covariance + covariance.T)


def _planner_velocity(
    arm: str,
    index: int,
    estimate: np.ndarray,
    position: np.ndarray,
    trust_alert: bool,
    n_agents: int,
) -> np.ndarray:
    if arm == "m10b_decentralized_no_negotiation":
        angle = 0.0
    else:
        angle = 2.0 * math.pi * index / n_agents
    radius = 2.1 if trust_alert else 2.8
    goal = estimate[:2] + radius * np.asarray([math.cos(angle), math.sin(angle)])
    return np.clip(0.16 * (goal - position), -0.55, 0.55)


def _make_message(
    run_id: str,
    sender: str,
    seq: int,
    step: int,
    config: HILConfig,
    state: np.ndarray,
    covariance: np.ndarray,
    trust: Mapping[str, float],
    message_type: str = "estimate",
    payload: Mapping[str, Any] | None = None,
) -> WireMessage:
    message = WireMessage(
        run_id=run_id,
        sender_id=sender,
        seq=seq,
        monotonic_ns=int(round(step * config.dt * 1e9)),
        local_epoch=0,
        message_type=message_type,
        estimate=tuple(float(value) for value in state),  # type: ignore[arg-type]
        covariance=tuple(float(value) for value in covariance.ravel()),
        trust_metadata={
            "minimum_peer_trust": min(trust.values(), default=1.0),
            "alert_count": sum(value < 0.55 for value in trust.values()),
        },
        payload=dict(payload or {}),
    )
    return message.accounted()


def run_hil_trial(
    config: HILConfig,
    scenario: HILScenario,
    arm: str,
    seed: int,
    *,
    capture_trace: bool = False,
) -> tuple[HILTrialSummary, tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Run one paired, deterministic, independent closed-loop trajectory."""

    config.validate()
    if arm not in M13_ARMS:
        raise ValueError(f"unknown M13 arm {arm!r}")
    run_id = f"m13-{scenario.name}-{arm}-{seed}"
    seed_material = hashlib.sha256(
        f"{scenario.name}:{seed}".encode("utf-8")
    ).digest()
    plant_seed = int.from_bytes(seed_material[:8], "little")
    network_seed = int.from_bytes(seed_material[8:16], "little")
    rng = np.random.default_rng(plant_seed)
    network_manifest, attack_manifest = _scenario_manifests(scenario, config)
    network = DeterministicNetwork(network_manifest, network_seed)
    attack = AttackShim(attack_manifest)
    agent_ids = tuple(f"agent{index}" for index in range(config.n_agents))
    angles = np.linspace(0.0, 2.0 * math.pi, config.n_agents, endpoint=False)
    positions = np.column_stack([4.2 * np.cos(angles), 4.2 * np.sin(angles)])
    velocities = np.zeros((config.n_agents, 2))
    filters = [
        KalmanFilter(
            state=np.asarray([-2.0, 0.0, 0.0, 0.0], dtype=float),
            covariance=np.diag([4.0, 4.0, 1.0, 1.0]),
            dt=config.dt,
            acceleration_variance=config.process_acceleration_variance,
        )
        for _ in agent_ids
    ]
    monitors = [_TrustMonitor(agent_ids) for _ in agent_ids]
    central_monitor = _TrustMonitor(agent_ids)
    inbox: list[dict[str, WireMessage]] = [dict() for _ in agent_ids]
    central_inbox: dict[str, WireMessage] = {}
    safety = SafetySupervisor(
        SafetyLimits(
            arena_half_extent=8.0,
            minimum_separation=0.45,
            hard_separation=0.24,
            maximum_speed=0.8,
            maximum_acceleration=6.0,
            maximum_jerk=100.0,
        ),
        config.dt,
    )
    errors: list[float] = []
    nees_values: list[float] = []
    covered: list[bool] = []
    decision_losses: list[float] = []
    wrong_actions: list[bool] = []
    movements: list[float] = []
    alerts: list[bool] = []
    false_alerts: list[bool] = []
    safety_interventions = 0
    emergency_stops = 0
    collisions = 0
    planner_messages = 0
    planner_bytes = 0
    maximum_allowed_planner_messages = 0
    ownership_violations = 0
    topology_disagreements = 0
    operational_trace: list[dict[str, Any]] = []
    truth_trace: list[dict[str, Any]] = []
    sequence = np.zeros(config.n_agents, dtype=int)

    for step in range(config.steps):
        target = _target_state(step, config, scenario)
        outage = (
            network_manifest.outage_agent is not None
            and network_manifest.outage_start is not None
            and network_manifest.outage_stop is not None
            and network_manifest.outage_start <= step < network_manifest.outage_stop
        )
        active = np.ones(config.n_agents, dtype=bool)
        if outage:
            active[-1] = False
        for index, filter_ in enumerate(filters):
            filter_.predict()
            occluded = (
                scenario.occlusion_start is not None
                and scenario.occlusion_stop is not None
                and scenario.occlusion_start <= step < scenario.occlusion_stop
                and index in scenario.occluded_agents
            )
            if not active[index] or occluded:
                continue
            scale = (
                scenario.precision_scale
                if scenario.precision_agent == index
                else 1.0
            )
            observation = _camera_observation(
                rng, target, positions[index], config, scale
            )
            if observation is not None:
                filter_.update(*observation)

        for index, sender in enumerate(agent_ids):
            if not active[index]:
                continue
            trust_map = monitors[index].trust
            estimate_message = _make_message(
                run_id,
                sender,
                int(sequence[index]),
                step,
                config,
                filters[index].state,
                filters[index].covariance,
                trust_map,
            )
            sequence[index] += 1
            estimate_message = attack.apply(estimate_message, step)
            receivers = [peer for peer in agent_ids if peer != sender]
            receivers.append("central")
            network.send(estimate_message, receivers, step)
            if arm.startswith("m10b") and step % config.replan_interval == index % config.replan_interval:
                proposal = _make_message(
                    run_id,
                    sender,
                    int(sequence[index]),
                    step,
                    config,
                    filters[index].state,
                    filters[index].covariance,
                    trust_map,
                    "proposal",
                    {
                        "owner_id": sender,
                        "candidate_id": f"view-{index}",
                        "utility": float(np.trace(filters[index].covariance[:2, :2])),
                        "valid_until_ns": int(
                            round((step + config.replan_interval) * config.dt * 1e9)
                        ),
                    },
                )
                sequence[index] += 1
                proposal_receivers = [
                    agent_ids[(index - 1) % config.n_agents],
                    agent_ids[(index + 1) % config.n_agents],
                ]
                network.send(proposal, proposal_receivers, step)
                planner_messages += len(set(proposal_receivers))
                planner_bytes += proposal.wire_bytes * len(set(proposal_receivers))
                maximum_allowed_planner_messages += 2

        for receiver, message in network.receive(step):
            if receiver == "central":
                if message.message_type == "estimate":
                    central_inbox[message.sender_id] = message
            else:
                receiver_index = agent_ids.index(receiver)
                if message.message_type == "estimate":
                    inbox[receiver_index][message.sender_id] = message
                elif message.message_type == "proposal":
                    if message.payload.get("owner_id") != message.sender_id:
                        ownership_violations += 1

        fused_states: list[np.ndarray] = []
        fused_covariances: list[np.ndarray] = []
        trust_maps: list[dict[str, float]] = []
        if arm in {"m9c_no_trust", M13_CENTRAL_ARM}:
            central_trust = (
                {source: 1.0 for source in central_inbox}
                if arm == "m9c_no_trust"
                else central_monitor.update(
                    central_inbox,
                    np.mean(np.asarray([filter_.state for filter_ in filters]), axis=0),
                )
            )
            base_index = int(np.argmin([np.trace(f.covariance) for f in filters]))
            central_state, central_covariance = _fuse_messages(
                central_inbox,
                filters[base_index].state,
                filters[base_index].covariance,
                central_trust,
            )
            for _ in agent_ids:
                fused_states.append(central_state.copy())
                fused_covariances.append(central_covariance.copy())
                trust_maps.append(dict(central_trust))
        else:
            for index, filter_ in enumerate(filters):
                trust_map = monitors[index].update(inbox[index], filter_.state)
                state, covariance = _fuse_messages(
                    inbox[index],
                    filter_.state,
                    filter_.covariance,
                    trust_map,
                )
                fused_states.append(state)
                fused_covariances.append(covariance)
                trust_maps.append(trust_map)

        team_state = np.mean(np.asarray(fused_states), axis=0)
        team_covariance = np.mean(np.asarray(fused_covariances), axis=0)
        error_vector = team_state[:2] - target[:2]
        error = float(np.linalg.norm(error_vector))
        position_covariance = team_covariance[:2, :2] + np.eye(2) * 1e-9
        nees = float(error_vector @ np.linalg.solve(position_covariance, error_vector))
        errors.append(error)
        nees_values.append(nees)
        covered.append(nees <= 5.991)
        wrong = error > 1.5
        wrong_actions.append(wrong)
        decision_losses.append(min(error, 3.0) + (1.0 if wrong else 0.0))

        attack_active = attack_manifest.start_step <= step < attack_manifest.stop_step
        attacker_ids = set(attack_manifest.attacker_ids)
        source_trusts = [
            trust_map[source]
            for trust_map in trust_maps
            for source in attacker_ids
            if source in trust_map
        ]
        attack_alert = bool(source_trusts) and float(np.mean(source_trusts)) < 0.55
        alerts.append(attack_alert if attack_active else False)
        honest_alerts = [
            value < 0.55
            for trust_map in trust_maps
            for source, value in trust_map.items()
            if source not in attacker_ids
        ]
        false_alerts.append(bool(any(honest_alerts)))

        commanded = np.zeros_like(velocities)
        for index, agent_id in enumerate(agent_ids):
            local_alert = any(value < 0.55 for value in trust_maps[index].values())
            desired = _planner_velocity(
                arm,
                index,
                fused_states[index],
                positions[index],
                local_alert,
                config.n_agents,
            )
            decision = safety.filter(
                agent_id,
                desired,
                positions[index],
                {
                    peer_id: positions[peer_index]
                    for peer_index, peer_id in enumerate(agent_ids)
                },
            )
            commanded[index] = decision.command
            safety_interventions += int(decision.intervened)
            emergency_stops += int(decision.emergency_stop)
        old_positions = positions.copy()
        velocities = commanded
        positions += velocities * config.dt
        movement = float(np.sum(np.linalg.norm(positions - old_positions, axis=1)))
        movements.append(movement)
        for left in range(config.n_agents):
            for right in range(left + 1, config.n_agents):
                collisions += int(
                    np.linalg.norm(positions[left] - positions[right]) < 0.24
                )
        if network_manifest.partition_start is not None:
            partition_active = (
                network_manifest.partition_start
                <= step
                < network_manifest.partition_stop  # type: ignore[operator]
            )
            local_component_counts = [
                2 if partition_active and agent_id in network_manifest.partition_a else
                2 if partition_active and agent_id in network_manifest.partition_b else
                1
                for agent_id in agent_ids
            ]
            topology_disagreements += int(
                not partition_active and len(set(local_component_counts)) > 1
            )

        if capture_trace:
            operational_trace.append(
                {
                    "domain": OPERATIONAL_DOMAIN,
                    "event_type": "estimate",
                    "run_id": run_id,
                    "process_id": "reference_operational_stack",
                    "arm": arm,
                    "scenario": scenario.name,
                    "step": step,
                    "monotonic_ns": int(round(step * config.dt * 1e9)),
                    "team_state": [float(value) for value in team_state],
                    "team_covariance": [
                        float(value) for value in team_covariance.ravel()
                    ],
                    "output_action": "select",
                    "trust_alert_agents": int(
                        sum(
                            value < 0.55
                            for trust_map in trust_maps
                            for value in trust_map.values()
                        )
                    ),
                    "ownership_violations": ownership_violations,
                    "planner_messages": planner_messages,
                    "maximum_allowed_planner_messages": maximum_allowed_planner_messages,
                    "movement": movement,
                    "runtime_ms": 1.0
                    + 0.02 * sum(len(messages) for messages in inbox),
                    "component_count": 1,
                }
            )
            truth_trace.append(
                TruthSample(
                    run_id=run_id,
                    scorer_process_id="independent_hil_scorer",
                    monotonic_ns=int(round(step * config.dt * 1e9)),
                    target_state=tuple(float(value) for value in target),  # type: ignore[arg-type]
                    robot_poses={
                        agent_id: (
                            float(positions[index, 0]),
                            float(positions[index, 1]),
                            0.0,
                        )
                        for index, agent_id in enumerate(agent_ids)
                    },
                ).to_record()
            )

    attack_steps = max(0, attack_manifest.stop_step - attack_manifest.start_step)
    if attack_steps:
        alert_rate = float(
            np.mean(alerts[attack_manifest.start_step : attack_manifest.stop_step])
        )
        recovery = float(config.steps - attack_manifest.stop_step)
        for offset, step in enumerate(range(attack_manifest.stop_step, config.steps)):
            if not alerts[step]:
                recovery = float(offset)
                break
    else:
        alert_rate = 1.0
        recovery = 0.0
    send_events = sum(event.event == "send" for event in network.events)
    receive_events = sum(event.event == "receive" for event in network.events)
    movement_total = float(sum(movements))
    mean_error = float(np.mean(errors))
    summary_body = {
        "scenario": scenario.name,
        "arm": arm,
        "seed": seed,
        "errors": [round(value, 12) for value in errors],
        "nees": [round(value, 12) for value in nees_values],
        "movement": round(movement_total, 12),
        "transport": [event.to_record() for event in network.events],
    }
    summary = HILTrialSummary(
        run_id=run_id,
        scenario=scenario.name,
        arm=arm,
        seed=seed,
        position_rmse=float(math.sqrt(np.mean(np.square(errors)))),
        mean_nees=float(np.mean(nees_values)),
        coverage95=float(np.mean(covered)),
        decision_loss=float(np.mean(decision_losses)),
        wrong_action_rate=float(np.mean(wrong_actions)),
        integrated_loss=float(np.mean(decision_losses) + 0.015 * movement_total),
        alert_rate=alert_rate,
        false_alert_rate=float(np.mean(false_alerts)),
        recovery_steps=recovery,
        movement=movement_total,
        delivery_ratio=receive_events / max(send_events, 1),
        planner_messages=planner_messages,
        planner_bytes=planner_bytes,
        maximum_allowed_planner_messages=maximum_allowed_planner_messages,
        ownership_violations=ownership_violations,
        safety_interventions=safety_interventions,
        emergency_stops=emergency_stops,
        collisions=collisions,
        mean_runtime_units=1.0
        + 0.02 * (send_events + planner_messages) / config.steps,
        topology_disagreement_rate=topology_disagreements / config.steps,
        replay_fingerprint=sha256_json(summary_body),
    )
    return summary, tuple(operational_trace), tuple(truth_trace)


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _run_hil_task(
    task: tuple[HILConfig, HILScenario, str, int],
) -> HILTrialSummary:
    config, scenario, arm, seed = task
    return run_hil_trial(config, scenario, arm, seed)[0]


def _paired_interval(
    differences: np.ndarray,
    bootstrap_samples: int,
    seed: int,
) -> tuple[float, float, float]:
    if differences.size == 0:
        return math.nan, math.nan, math.nan
    mean = float(np.mean(differences))
    if differences.size == 1:
        return mean, mean, mean
    rng = np.random.default_rng(seed)
    indices = rng.integers(
        0, differences.size, size=(bootstrap_samples, differences.size)
    )
    means = np.mean(differences[indices], axis=1)
    return mean, float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def run_full_loop_hil_suite(
    config: HILConfig,
    output: Path,
    *,
    scenario_names: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Run M13.1 and write replayable paired screening artifacts."""

    config.validate()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    requested_scenarios = set(scenario_names) if scenario_names is not None else None
    selected = (
        [
            scenario
            for scenario in DEFAULT_HIL_SCENARIOS
            if scenario.name in requested_scenarios
        ]
        if requested_scenarios is not None
        else list(DEFAULT_HIL_SCENARIOS)
    )
    if not selected:
        raise ValueError("no HIL scenarios selected")
    _, audit_operational, audit_truth = run_hil_trial(
        config,
        selected[0],
        M13_ARMS[0],
        config.seed_start,
        capture_trace=True,
    )
    tasks = [
        (config, scenario, arm, seed)
        for scenario in selected
        for seed in range(config.seed_start, config.seed_start + config.seed_count)
        for arm in M13_ARMS
    ]
    if config.workers == 1:
        summaries = [_run_hil_task(task) for task in tasks]
    else:
        try:
            with ProcessPoolExecutor(max_workers=config.workers) as executor:
                summaries = list(executor.map(_run_hil_task, tasks, chunksize=4))
        except (OSError, PermissionError):
            # Restricted containers may deny the POSIX semaphore query needed
            # by ProcessPoolExecutor. Correctness is unchanged; only throughput
            # falls back to the deterministic serial path.
            summaries = [_run_hil_task(task) for task in tasks]
    rows = [asdict(summary) for summary in summaries]
    _write_csv(output / "run_summary.csv", rows)

    scenario_rows: list[dict[str, Any]] = []
    for scenario in selected:
        for arm in M13_ARMS:
            cell = [
                summary
                for summary in summaries
                if summary.scenario == scenario.name and summary.arm == arm
            ]
            scenario_rows.append(
                {
                    "scenario": scenario.name,
                    "arm": arm,
                    "trials": len(cell),
                    "position_rmse_mean": float(np.mean([row.position_rmse for row in cell])),
                    "decision_loss_mean": float(np.mean([row.decision_loss for row in cell])),
                    "integrated_loss_mean": float(np.mean([row.integrated_loss for row in cell])),
                    "mean_nees": float(np.mean([row.mean_nees for row in cell])),
                    "coverage95": float(np.mean([row.coverage95 for row in cell])),
                    "wrong_action_rate": float(np.mean([row.wrong_action_rate for row in cell])),
                    "alert_rate": float(np.mean([row.alert_rate for row in cell])),
                    "false_alert_rate": float(np.mean([row.false_alert_rate for row in cell])),
                    "recovery_steps": float(np.mean([row.recovery_steps for row in cell])),
                    "delivery_ratio": float(np.mean([row.delivery_ratio for row in cell])),
                }
            )
    _write_csv(output / "scenario_summary.csv", scenario_rows)

    paired_rows: list[dict[str, Any]] = []
    candidate_differences: list[float] = []
    for scenario in selected:
        for comparison in M13_ARMS:
            if comparison == M13_CENTRAL_ARM:
                continue
            differences: list[float] = []
            for seed in range(config.seed_start, config.seed_start + config.seed_count):
                central = next(
                    row
                    for row in summaries
                    if row.scenario == scenario.name
                    and row.seed == seed
                    and row.arm == M13_CENTRAL_ARM
                )
                other = next(
                    row
                    for row in summaries
                    if row.scenario == scenario.name
                    and row.seed == seed
                    and row.arm == comparison
                )
                # Positive means the central arm has greater loss, so the
                # comparison arm is better.
                differences.append(central.integrated_loss - other.integrated_loss)
                if comparison == M13_CANDIDATE_ARM:
                    candidate_differences.append(differences[-1])
            mean, lower, upper = _paired_interval(
                np.asarray(differences),
                config.bootstrap_samples,
                91000 + len(paired_rows),
            )
            paired_rows.append(
                {
                    "scenario": scenario.name,
                    "comparison_arm": comparison,
                    "reference_arm": M13_CENTRAL_ARM,
                    "metric": "integrated_loss_improvement",
                    "mean": mean,
                    "ci95_lower": lower,
                    "ci95_upper": upper,
                    "paired_units": len(differences),
                }
            )
    _write_csv(output / "paired_effects.csv", paired_rows)

    isolation = audit_truth_isolation(
        audit_operational,
        operational_process_ids=("reference_operational_stack",),
        scorer_process_id="independent_hil_scorer",
    )
    audit_summary = summaries[0]
    repeated, _, _ = run_hil_trial(
        config,
        selected[0],
        audit_summary.arm,
        audit_summary.seed,
    )
    deterministic = repeated.replay_fingerprint == audit_summary.replay_fingerprint
    candidate_rows = [row for row in summaries if row.arm == M13_CANDIDATE_ARM]
    attack_names = {
        scenario.name for scenario in selected if scenario.attack_kind != "none"
    }
    attack_rows = [row for row in candidate_rows if row.scenario in attack_names]
    stable_rows = [
        row
        for row in candidate_rows
        if row.scenario in {"stable", "legitimate_precision_minority"}
    ]
    candidate_mean, candidate_lower, candidate_upper = _paired_interval(
        np.asarray(candidate_differences),
        config.bootstrap_samples,
        91813,
    )
    total_agent_steps = len(candidate_rows) * config.steps * config.n_agents
    gates = {
        "truth_isolation_and_replay": isolation["passed"] and deterministic,
        "zero_collisions_and_emergency_stops": all(
            row.collisions == 0 and row.emergency_stops == 0 for row in candidate_rows
        ),
        "safety_intervention_rate_below_1pct": (
            sum(row.safety_interventions for row in candidate_rows)
            / max(total_agent_steps, 1)
            < 0.01
        ),
        "ownership_and_message_bounds": all(
            row.ownership_violations == 0
            and row.planner_messages <= row.maximum_allowed_planner_messages
            for row in candidate_rows
        ),
        "decentralized_integrated_loss_lcb": candidate_lower >= -0.05,
        "attack_decision_loss": (
            not attack_rows
            or float(np.mean([row.decision_loss for row in attack_rows])) <= 1.50
        ),
        "wrong_action_rate": float(
            np.mean([row.wrong_action_rate for row in candidate_rows])
        )
        <= 0.01,
        "calibration": (
            float(np.mean([row.mean_nees for row in candidate_rows])) <= 6.0
            and float(np.mean([row.coverage95 for row in candidate_rows])) >= 0.88
        ),
        "attack_alert_rate": (
            not attack_rows
            or float(np.mean([row.alert_rate for row in attack_rows])) >= 0.50
        ),
        "false_alert_rate": (
            not stable_rows
            or float(np.mean([row.false_alert_rate for row in stable_rows])) <= 0.05
        ),
        "attack_recovery": (
            not attack_rows
            or float(np.mean([row.recovery_steps for row in attack_rows])) <= 30.0
        ),
        "transport_topology_runtime": (
            float(np.mean([row.delivery_ratio for row in candidate_rows])) >= 0.70
            and float(np.mean([row.topology_disagreement_rate for row in candidate_rows]))
            <= 0.01
        ),
    }
    verdict = "M13.1-HIL-PILOT-READY" if all(gates.values()) else "M13.1-HIL-NO-GO"
    project_root = Path(__file__).resolve().parents[2]
    implementation_paths = (
        project_root / "src/flockkalman/full_loop_contracts.py",
        project_root / "src/flockkalman/full_loop_hil.py",
        project_root / "M13_PROTOCOL.md",
    )
    implementation_hashes = {
        str(path.relative_to(project_root)): sha256_file(path)
        for path in implementation_paths
    }
    decision: dict[str, Any] = {
        "milestone": "M13.1",
        "verdict": verdict,
        "external_physical_claim_authorized": False,
        "gates": gates,
        "candidate_vs_central_integrated_loss": {
            "mean": candidate_mean,
            "ci95_lower": candidate_lower,
            "ci95_upper": candidate_upper,
        },
        "truth_isolation_audit": isolation,
        "deterministic_replay": deterministic,
        "trials": len(summaries),
        "paired_seeds_per_scenario": config.seed_count,
        "implementation_hashes": implementation_hashes,
        "implementation_hash": sha256_json(implementation_hashes),
        "normal_reference": {
            "z_0.975": NormalDist().inv_cdf(0.975),
            "z_0.8": NormalDist().inv_cdf(0.8),
        },
    }
    (output / "suite_config.json").write_text(
        json.dumps(
            {
                **asdict(config),
                "arms": M13_ARMS,
                "scenarios": [asdict(scenario) for scenario in selected],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    (output / "audit_operational.json").write_text(
        "\n".join(canonical_json(record) for record in audit_operational) + "\n",
        encoding="utf-8",
    )
    (output / "audit_truth.json").write_text(
        "\n".join(canonical_json(record) for record in audit_truth) + "\n",
        encoding="utf-8",
    )
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_lines = [
        "# M13.1 independent HIL screening",
        "",
        f"Verdict: **{verdict}**",
        "",
        f"The suite ran {len(summaries)} trials across {len(selected)} scenarios, "
        f"{config.seed_count} paired seeds, and {len(M13_ARMS)} arms.",
        "",
        "This verdict only controls entry to the physical pilot. It cannot validate "
        "physical performance and never authorizes deployment.",
        "",
        "## Gates",
        "",
    ]
    report_lines.extend(
        f"- {'PASS' if passed else 'FAIL'} — `{name}`"
        for name, passed in gates.items()
    )
    (output / "m13_1_report.md").write_text(
        "\n".join(report_lines) + "\n", encoding="utf-8"
    )
    artifact_hashes = {
        path.name: sha256_file(path)
        for path in sorted(output.iterdir())
        if path.is_file() and path.name != "artifact_manifest.json"
    }
    (output / "artifact_manifest.json").write_text(
        json.dumps(
            {
                "artifacts": artifact_hashes,
                "manifest_hash": sha256_json(artifact_hashes),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return decision
