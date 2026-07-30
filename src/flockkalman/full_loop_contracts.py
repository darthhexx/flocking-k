"""M13 wire, fault, safety, and audit contracts.

This module deliberately has no ROS dependency.  The same canonical envelopes
are used by the deterministic HIL transport, JSONL evidence bundles, and the
ROS 2 bridge documented in ``ros2/``.  Ground truth has a different type and
domain so it cannot accidentally enter an operational controller.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np


SCHEMA_VERSION = "m13.0.0"
OPERATIONAL_DOMAIN = "operational"
SCORER_DOMAIN = "independent_scorer"
MESSAGE_TYPES = frozenset({"estimate", "proposal", "diagnostic", "command"})
FORBIDDEN_OPERATIONAL_KEYS = frozenset(
    {
        "truth",
        "ground_truth",
        "target_truth",
        "truth_state",
        "fault_identity",
        "scorer",
        "mocap_truth",
    }
)


def canonical_json(value: Any) -> str:
    """Return deterministic, finite JSON suitable for hashing and transport."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check_finite(name: str, values: Iterable[float]) -> None:
    array = np.asarray(tuple(values), dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")


def _contains_forbidden_key(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).lower()
            if normalized in FORBIDDEN_OPERATIONAL_KEYS or "groundtruth" in normalized:
                found.add(str(key))
            found.update(_contains_forbidden_key(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            found.update(_contains_forbidden_key(child))
    return found


@dataclass(frozen=True, slots=True)
class WireMessage:
    """Canonical envelope shared by all operational message types.

    Every message carries the sender's current estimate, covariance, trust
    metadata, monotonic time, epoch, sequence, and accounted byte count.  The
    payload changes by type but may never contain evaluator-only truth.
    """

    run_id: str
    sender_id: str
    seq: int
    monotonic_ns: int
    local_epoch: int
    message_type: str
    estimate: tuple[float, float, float, float]
    covariance: tuple[float, ...]
    trust_metadata: Mapping[str, float | int | bool | str]
    payload: Mapping[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
    wire_bytes: int = 0

    def validate(self) -> None:
        if not self.run_id or not self.sender_id:
            raise ValueError("run_id and sender_id are required")
        if self.seq < 0 or self.monotonic_ns < 0 or self.local_epoch < 0:
            raise ValueError("sequence, timestamp, and epoch must be non-negative")
        if self.message_type not in MESSAGE_TYPES:
            raise ValueError(f"unsupported message_type {self.message_type!r}")
        if len(self.estimate) != 4 or len(self.covariance) != 16:
            raise ValueError("estimate must have 4 and covariance 16 scalars")
        _check_finite("estimate", self.estimate)
        _check_finite("covariance", self.covariance)
        matrix = np.asarray(self.covariance, dtype=float).reshape(4, 4)
        if not np.allclose(matrix, matrix.T, atol=1e-9):
            raise ValueError("covariance must be symmetric")
        if float(np.min(np.linalg.eigvalsh(matrix))) < -1e-9:
            raise ValueError("covariance must be positive semidefinite")
        forbidden = _contains_forbidden_key(
            {"trust_metadata": self.trust_metadata, "payload": self.payload}
        )
        if forbidden:
            raise ValueError(
                "operational message contains evaluator-only keys: "
                + ", ".join(sorted(forbidden))
            )
        if self.message_type == "proposal":
            required = {"owner_id", "candidate_id", "utility", "valid_until_ns"}
            missing = required.difference(self.payload)
            if missing:
                raise ValueError(f"proposal missing fields: {sorted(missing)}")
            if self.payload["owner_id"] != self.sender_id:
                raise ValueError("proposal ownership must equal sender_id")
        computed = self.compute_wire_bytes()
        if self.wire_bytes not in {0, computed}:
            raise ValueError(
                f"wire_bytes mismatch: recorded {self.wire_bytes}, computed {computed}"
            )

    def _without_byte_count(self) -> dict[str, Any]:
        value = asdict(self)
        value["domain"] = OPERATIONAL_DOMAIN
        value["wire_bytes"] = 0
        return value

    def compute_wire_bytes(self) -> int:
        # Iterate because changing the integer digit count can change JSON size.
        value = self._without_byte_count()
        size = 0
        for _ in range(4):
            value["wire_bytes"] = size
            updated = len(canonical_json(value).encode("utf-8"))
            if updated == size:
                break
            size = updated
        return size

    def to_record(self) -> dict[str, Any]:
        self.validate()
        value = self._without_byte_count()
        value["wire_bytes"] = self.compute_wire_bytes()
        return value

    def accounted(self) -> "WireMessage":
        return replace(self, wire_bytes=self.compute_wire_bytes())

    @classmethod
    def from_record(cls, value: Mapping[str, Any]) -> "WireMessage":
        if value.get("domain") != OPERATIONAL_DOMAIN:
            raise ValueError("wire message must be in the operational domain")
        message = cls(
            run_id=str(value["run_id"]),
            sender_id=str(value["sender_id"]),
            seq=int(value["seq"]),
            monotonic_ns=int(value["monotonic_ns"]),
            local_epoch=int(value["local_epoch"]),
            message_type=str(value["message_type"]),
            estimate=tuple(float(item) for item in value["estimate"]),  # type: ignore[arg-type]
            covariance=tuple(float(item) for item in value["covariance"]),
            trust_metadata=dict(value["trust_metadata"]),
            payload=dict(value.get("payload", {})),
            schema_version=str(value["schema_version"]),
            wire_bytes=int(value["wire_bytes"]),
        )
        message.validate()
        return message


@dataclass(frozen=True, slots=True)
class TruthSample:
    """Evaluator-only state emitted by an independent truth process."""

    run_id: str
    scorer_process_id: str
    monotonic_ns: int
    target_state: tuple[float, float, float, float]
    robot_poses: Mapping[str, tuple[float, float, float]]
    schema_version: str = SCHEMA_VERSION

    def to_record(self) -> dict[str, Any]:
        if not self.run_id or not self.scorer_process_id:
            raise ValueError("truth sample identifiers are required")
        if self.monotonic_ns < 0:
            raise ValueError("truth timestamp must be non-negative")
        _check_finite("target_state", self.target_state)
        for pose in self.robot_poses.values():
            if len(pose) != 3:
                raise ValueError("robot poses must be x, y, heading")
            _check_finite("robot_pose", pose)
        value = asdict(self)
        value["domain"] = SCORER_DOMAIN
        return value


@dataclass(frozen=True, slots=True)
class NetworkFaultManifest:
    """Causal transport fault schedule, independent of target truth."""

    loss_probability: float = 0.0
    base_delay_steps: int = 0
    jitter_steps: int = 0
    burst_start: int | None = None
    burst_stop: int | None = None
    burst_loss_probability: float = 0.0
    partition_start: int | None = None
    partition_stop: int | None = None
    partition_a: tuple[str, ...] = ()
    partition_b: tuple[str, ...] = ()
    outage_agent: str | None = None
    outage_start: int | None = None
    outage_stop: int | None = None

    def validate(self) -> None:
        for name in (
            "loss_probability",
            "burst_loss_probability",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.base_delay_steps < 0 or self.jitter_steps < 0:
            raise ValueError("network delays must be non-negative")
        for start_name, stop_name in (
            ("burst_start", "burst_stop"),
            ("partition_start", "partition_stop"),
            ("outage_start", "outage_stop"),
        ):
            start = getattr(self, start_name)
            stop = getattr(self, stop_name)
            if (start is None) != (stop is None):
                raise ValueError(f"{start_name} and {stop_name} must be paired")
            if start is not None and (start < 0 or stop <= start):
                raise ValueError(f"invalid interval {start_name}/{stop_name}")
        if (self.partition_a or self.partition_b) and (
            set(self.partition_a) & set(self.partition_b)
        ):
            raise ValueError("partition sets must be disjoint")

    @staticmethod
    def _active(step: int, start: int | None, stop: int | None) -> bool:
        return start is not None and stop is not None and start <= step < stop

    def permits(self, sender: str, receiver: str, step: int) -> bool:
        if self._active(step, self.outage_start, self.outage_stop):
            if sender == self.outage_agent or receiver == self.outage_agent:
                return False
        if self._active(step, self.partition_start, self.partition_stop):
            cross = (
                sender in self.partition_a
                and receiver in self.partition_b
            ) or (
                sender in self.partition_b
                and receiver in self.partition_a
            )
            if cross:
                return False
        return True

    def loss_at(self, step: int) -> float:
        if self._active(step, self.burst_start, self.burst_stop):
            return self.burst_loss_probability
        return self.loss_probability


@dataclass(frozen=True, slots=True)
class AttackManifest:
    """Bounded, causal outgoing-message attack."""

    kind: str = "none"
    attacker_ids: tuple[str, ...] = ()
    start_step: int = 0
    stop_step: int = 0
    maximum_bias: float = 1.5
    maximum_bias_step: float = 0.04
    minimum_covariance_scale: float = 0.08
    adaptive_gain: float = 0.12

    def validate(self) -> None:
        if self.kind not in {
            "none",
            "covariance_understating_ramp",
            "temporary_ramp",
            "adaptive_bounded",
        }:
            raise ValueError(f"unsupported attack kind {self.kind!r}")
        if self.start_step < 0 or self.stop_step < self.start_step:
            raise ValueError("invalid attack interval")
        if self.maximum_bias < 0.0 or self.maximum_bias_step <= 0.0:
            raise ValueError("attack bias bounds must be positive")
        if not 0.0 < self.minimum_covariance_scale <= 1.0:
            raise ValueError("minimum_covariance_scale must be in (0, 1]")

    def active(self, sender: str, step: int) -> bool:
        return (
            self.kind != "none"
            and sender in self.attacker_ids
            and self.start_step <= step < self.stop_step
        )


class AttackShim:
    """Apply a manifest using outgoing history only.

    The method signature intentionally contains no truth or fault-identity
    argument.  The adaptive arm reacts only to its own successive estimates.
    """

    def __init__(self, manifest: AttackManifest) -> None:
        manifest.validate()
        self.manifest = manifest
        self._bias: dict[str, np.ndarray] = {}
        self._previous_estimate: dict[str, np.ndarray] = {}

    def apply(self, message: WireMessage, step: int) -> WireMessage:
        if not self.manifest.active(message.sender_id, step):
            self._previous_estimate[message.sender_id] = np.asarray(
                message.estimate, dtype=float
            )
            return message
        state = np.asarray(message.estimate, dtype=float)
        previous = self._previous_estimate.get(message.sender_id, state)
        motion = state[:2] - previous[:2]
        if float(np.linalg.norm(motion)) < 1e-12:
            direction = np.asarray([1.0, 0.0])
        else:
            direction = np.asarray([-motion[1], motion[0]], dtype=float)
            direction /= max(float(np.linalg.norm(direction)), 1e-12)
        current = self._bias.get(message.sender_id, np.zeros(2))
        if self.manifest.kind == "adaptive_bounded":
            desired = current + self.manifest.adaptive_gain * direction
        else:
            desired = current + self.manifest.maximum_bias_step * direction
        delta = desired - current
        delta_norm = float(np.linalg.norm(delta))
        if delta_norm > self.manifest.maximum_bias_step:
            delta *= self.manifest.maximum_bias_step / delta_norm
        updated = current + delta
        norm = float(np.linalg.norm(updated))
        if norm > self.manifest.maximum_bias:
            updated *= self.manifest.maximum_bias / norm
        attacked_state = state.copy()
        attacked_state[:2] += updated
        covariance = np.asarray(message.covariance, dtype=float).reshape(4, 4)
        covariance *= self.manifest.minimum_covariance_scale
        metadata = dict(message.trust_metadata)
        metadata["attack_shim_applied"] = True
        self._bias[message.sender_id] = updated
        self._previous_estimate[message.sender_id] = state
        return replace(
            message,
            estimate=tuple(float(value) for value in attacked_state),
            covariance=tuple(float(value) for value in covariance.ravel()),
            trust_metadata=metadata,
            wire_bytes=0,
        ).accounted()


@dataclass(frozen=True, slots=True)
class TransportEvent:
    run_id: str
    step: int
    sender_id: str
    receiver_id: str
    seq: int
    event: str
    scheduled_delivery_step: int | None
    wire_bytes: int
    reason: str = ""

    def to_record(self) -> dict[str, Any]:
        value = asdict(self)
        value["domain"] = OPERATIONAL_DOMAIN
        value["event_type"] = "transport"
        return value


class DeterministicNetwork:
    """Seeded packet transport with delay, loss, partition, and outage."""

    def __init__(self, manifest: NetworkFaultManifest, seed: int) -> None:
        manifest.validate()
        self.manifest = manifest
        self._rng = np.random.default_rng(seed)
        self._pending: list[tuple[int, str, WireMessage]] = []
        self.events: list[TransportEvent] = []

    def send(
        self,
        message: WireMessage,
        receivers: Iterable[str],
        step: int,
    ) -> None:
        message = message.accounted()
        for receiver in sorted(set(receivers)):
            reason = ""
            if not self.manifest.permits(message.sender_id, receiver, step):
                reason = "partition_or_outage"
            elif self._rng.random() < self.manifest.loss_at(step):
                reason = "stochastic_loss"
            if reason:
                self.events.append(
                    TransportEvent(
                        message.run_id,
                        step,
                        message.sender_id,
                        receiver,
                        message.seq,
                        "drop",
                        None,
                        message.wire_bytes,
                        reason,
                    )
                )
                continue
            jitter = (
                int(self._rng.integers(0, self.manifest.jitter_steps + 1))
                if self.manifest.jitter_steps
                else 0
            )
            delivery = step + self.manifest.base_delay_steps + jitter
            self._pending.append((delivery, receiver, message))
            self.events.append(
                TransportEvent(
                    message.run_id,
                    step,
                    message.sender_id,
                    receiver,
                    message.seq,
                    "send",
                    delivery,
                    message.wire_bytes,
                )
            )

    def receive(self, step: int) -> list[tuple[str, WireMessage]]:
        ready = [item for item in self._pending if item[0] <= step]
        self._pending = [item for item in self._pending if item[0] > step]
        delivered: list[tuple[str, WireMessage]] = []
        for _, receiver, message in sorted(
            ready, key=lambda item: (item[0], item[1], item[2].sender_id, item[2].seq)
        ):
            if not self.manifest.permits(message.sender_id, receiver, step):
                self.events.append(
                    TransportEvent(
                        message.run_id,
                        step,
                        message.sender_id,
                        receiver,
                        message.seq,
                        "drop",
                        None,
                        message.wire_bytes,
                        "state_changed_before_delivery",
                    )
                )
                continue
            delivered.append((receiver, message))
            self.events.append(
                TransportEvent(
                    message.run_id,
                    step,
                    message.sender_id,
                    receiver,
                    message.seq,
                    "receive",
                    step,
                    message.wire_bytes,
                )
            )
        return delivered


@dataclass(frozen=True, slots=True)
class SafetyLimits:
    arena_half_extent: float = 8.0
    hard_boundary_margin: float = 0.05
    minimum_separation: float = 0.45
    hard_separation: float = 0.25
    maximum_speed: float = 1.2
    maximum_acceleration: float = 1.0
    maximum_jerk: float = 3.0


@dataclass(frozen=True, slots=True)
class SafetyDecision:
    command: tuple[float, float]
    intervened: bool
    emergency_stop: bool
    reasons: tuple[str, ...]


class SafetySupervisor:
    """Final command limiter isolated from estimator and policy decisions."""

    def __init__(self, limits: SafetyLimits, dt: float) -> None:
        if dt <= 0.0:
            raise ValueError("dt must be positive")
        self.limits = limits
        self.dt = dt
        self._previous_velocity: dict[str, np.ndarray] = {}
        self._previous_acceleration: dict[str, np.ndarray] = {}

    @staticmethod
    def _clip_norm(value: np.ndarray, maximum: float) -> tuple[np.ndarray, bool]:
        norm = float(np.linalg.norm(value))
        if norm <= maximum or norm <= 1e-15:
            return value, False
        return value * (maximum / norm), True

    def filter(
        self,
        robot_id: str,
        command: Iterable[float],
        position: Iterable[float],
        peer_positions: Mapping[str, Iterable[float]],
    ) -> SafetyDecision:
        desired = np.asarray(tuple(command), dtype=float)
        location = np.asarray(tuple(position), dtype=float)
        if desired.shape != (2,) or location.shape != (2,):
            raise ValueError("command and position must be two dimensional")
        previous = self._previous_velocity.get(robot_id, np.zeros(2))
        previous_acceleration = self._previous_acceleration.get(robot_id, np.zeros(2))
        reasons: list[str] = []
        emergency = bool(
            np.any(
                np.abs(location)
                >= self.limits.arena_half_extent
                + self.limits.hard_boundary_margin
            )
        )
        for peer_id, peer_position in peer_positions.items():
            if peer_id == robot_id:
                continue
            distance = float(
                np.linalg.norm(location - np.asarray(tuple(peer_position), dtype=float))
            )
            if distance < self.limits.hard_separation:
                emergency = True
                reasons.append("hard_separation")
        if emergency:
            desired = np.zeros(2)
            reasons.append("emergency_stop")
        desired, clipped = self._clip_norm(desired, self.limits.maximum_speed)
        if clipped:
            reasons.append("speed")
        acceleration = (desired - previous) / self.dt
        acceleration, clipped = self._clip_norm(
            acceleration, self.limits.maximum_acceleration
        )
        if clipped:
            reasons.append("acceleration")
        jerk = (acceleration - previous_acceleration) / self.dt
        jerk, clipped = self._clip_norm(jerk, self.limits.maximum_jerk)
        if clipped:
            reasons.append("jerk")
            acceleration = previous_acceleration + jerk * self.dt
        limited = previous + acceleration * self.dt
        predicted = location + limited * self.dt
        boundary = self.limits.arena_half_extent
        for axis in range(2):
            if predicted[axis] > boundary and limited[axis] > 0.0:
                limited[axis] = 0.0
                reasons.append("boundary")
            elif predicted[axis] < -boundary and limited[axis] < 0.0:
                limited[axis] = 0.0
                reasons.append("boundary")
        for peer_id, peer_position in peer_positions.items():
            if peer_id == robot_id:
                continue
            delta = location - np.asarray(tuple(peer_position), dtype=float)
            distance = float(np.linalg.norm(delta))
            if distance < self.limits.minimum_separation:
                outward = delta / max(distance, 1e-12)
                limited += outward * min(
                    self.limits.maximum_speed,
                    (self.limits.minimum_separation - distance) / self.dt,
                )
                limited, _ = self._clip_norm(limited, self.limits.maximum_speed)
                reasons.append("separation")
        acceleration = (limited - previous) / self.dt
        self._previous_velocity[robot_id] = limited.copy()
        self._previous_acceleration[robot_id] = acceleration
        return SafetyDecision(
            tuple(float(value) for value in limited),
            bool(reasons),
            emergency,
            tuple(sorted(set(reasons))),
        )


class HashChainedLedger:
    """Append-only JSONL ledger with a deterministic record hash chain."""

    def __init__(self, path: Path, domain: str) -> None:
        if domain not in {OPERATIONAL_DOMAIN, SCORER_DOMAIN}:
            raise ValueError("invalid ledger domain")
        self.path = Path(path)
        self.domain = domain
        self._previous = "0" * 64
        self._count = 0

    def append(self, record: Mapping[str, Any]) -> str:
        value = dict(record)
        actual_domain = value.get("domain")
        if actual_domain != self.domain:
            raise ValueError(
                f"ledger domain {self.domain!r} does not accept {actual_domain!r}"
            )
        if self.domain == OPERATIONAL_DOMAIN:
            forbidden = _contains_forbidden_key(value)
            if forbidden:
                raise ValueError(
                    "truth leakage into operational ledger: "
                    + ", ".join(sorted(forbidden))
                )
        body = {
            "record_index": self._count,
            "previous_hash": self._previous,
            "record": value,
        }
        entry_hash = sha256_json(body)
        envelope = {**body, "entry_hash": entry_hash}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical_json(envelope) + "\n")
        self._previous = entry_hash
        self._count += 1
        return entry_hash


def verify_ledger(path: Path, expected_domain: str) -> dict[str, Any]:
    previous = "0" * 64
    count = 0
    final_hash = previous
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            envelope = json.loads(line)
            if envelope.get("record_index") != count:
                raise ValueError(f"{path}:{line_number}: non-contiguous record index")
            if envelope.get("previous_hash") != previous:
                raise ValueError(f"{path}:{line_number}: broken hash chain")
            record = envelope.get("record")
            if not isinstance(record, dict) or record.get("domain") != expected_domain:
                raise ValueError(f"{path}:{line_number}: wrong ledger domain")
            if expected_domain == OPERATIONAL_DOMAIN:
                forbidden = _contains_forbidden_key(record)
                if forbidden:
                    raise ValueError(
                        f"{path}:{line_number}: operational truth leakage {sorted(forbidden)}"
                    )
            body = {
                "record_index": envelope["record_index"],
                "previous_hash": envelope["previous_hash"],
                "record": record,
            }
            expected = sha256_json(body)
            if envelope.get("entry_hash") != expected:
                raise ValueError(f"{path}:{line_number}: invalid entry hash")
            previous = expected
            final_hash = expected
            count += 1
    return {"records": count, "final_hash": final_hash, "file_sha256": sha256_file(path)}


def audit_clock_offsets(
    samples: Iterable[Mapping[str, Any]],
    maximum_absolute_offset_ms: float = 5.0,
) -> dict[str, Any]:
    offsets = [abs(float(sample["offset_ms"])) for sample in samples]
    maximum = max(offsets, default=math.inf)
    return {
        "sample_count": len(offsets),
        "maximum_absolute_offset_ms": maximum,
        "limit_ms": maximum_absolute_offset_ms,
        "passed": bool(offsets) and maximum <= maximum_absolute_offset_ms,
    }


def audit_truth_isolation(
    operational_records: Iterable[Mapping[str, Any]],
    *,
    operational_process_ids: Iterable[str],
    scorer_process_id: str,
) -> dict[str, Any]:
    process_ids = {str(value) for value in operational_process_ids}
    leaks: list[str] = []
    for index, record in enumerate(operational_records):
        forbidden = _contains_forbidden_key(record)
        if forbidden:
            leaks.append(f"record {index}: forbidden keys {sorted(forbidden)}")
        if record.get("domain") != OPERATIONAL_DOMAIN:
            leaks.append(f"record {index}: wrong domain")
        if record.get("process_id") == scorer_process_id:
            leaks.append(f"record {index}: scorer process emitted operational data")
    if not scorer_process_id or scorer_process_id in process_ids:
        leaks.append("scorer process is not distinct from operational processes")
    return {
        "passed": not leaks,
        "scorer_process_id": scorer_process_id,
        "operational_process_ids": sorted(process_ids),
        "violations": leaks,
    }

