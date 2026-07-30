"""M13.2/M13.3 physical evidence planning, scoring, and held-out decision.

The evaluator is fail closed: loopback/synthetic bundles can exercise all code
paths but can never produce a physical GO.  Raw operational, transport, safety,
and independent-truth ledgers are hash chained and rescored here; submitted
summary numbers are not trusted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import csv
import json
import math
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from .full_loop_contracts import (
    OPERATIONAL_DOMAIN,
    SCHEMA_VERSION,
    SCORER_DOMAIN,
    audit_clock_offsets,
    audit_truth_isolation,
    canonical_json,
    sha256_file,
    sha256_json,
    verify_ledger,
)
from .full_loop_hil import (
    DEFAULT_HIL_SCENARIOS,
    M13_ARMS,
    M13_CANDIDATE_ARM,
    M13_CENTRAL_ARM,
)


REQUIRED_LEDGER_FILES = {
    "operational.jsonl": OPERATIONAL_DOMAIN,
    "transport.jsonl": OPERATIONAL_DOMAIN,
    "safety.jsonl": OPERATIONAL_DOMAIN,
    "truth.jsonl": SCORER_DOMAIN,
}
PHYSICAL_ADAPTERS = frozenset({"ros2_mcap", "ros2_dds", "physical_jsonl_bridge"})
ATTACK_SCENARIOS = frozenset(
    {
        "colluding_covariance_ramp",
        "temporary_attack_recovery",
        "adaptive_bounded_attacker",
    }
)


@dataclass(frozen=True, slots=True)
class PhysicalRunScore:
    run_id: str
    evidence_hash: str
    phase: str
    evidence_class: str
    adapter: str
    scenario: str
    arm: str
    block_id: str
    trial_date: str
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
    safety_events: int
    emergency_stops: int
    collisions: int
    mean_runtime_ms: float
    topology_disagreement_rate: float
    clock_maximum_offset_ms: float
    audit_passed: bool


def _load_ledger(path: Path, domain: str) -> list[dict[str, Any]]:
    verify_ledger(path, domain)
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(dict(json.loads(line)["record"]))
    return records


def _write_csv(path: Path, rows: list[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"cannot write empty CSV {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _candidate_paths(project_root: Path) -> tuple[Path, ...]:
    return (
        project_root / "src/flockkalman/closed_loop_trust.py",
        project_root / "src/flockkalman/decentralized_sensing.py",
        project_root / "src/flockkalman/full_loop_contracts.py",
        project_root / "src/flockkalman/full_loop_hil.py",
        project_root / "src/flockkalman/full_loop_physical.py",
        project_root / "M10A5_PROTOCOL.md",
        project_root / "M10B_PROTOCOL.md",
        project_root / "M13_PROTOCOL.md",
    )


def current_candidate_hashes(project_root: Path) -> dict[str, str]:
    paths = _candidate_paths(Path(project_root))
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"candidate freeze inputs missing: {missing}")
    return {
        str(path.relative_to(project_root)): sha256_file(path)
        for path in paths
    }


def _trial_manifest_template(phase: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": "REPLACE_ME",
        "phase": phase,
        "evidence_class": "external_physical",
        "adapter": "ros2_mcap",
        "scenario": "stable",
        "arm": M13_CANDIDATE_ARM,
        "block_id": "REPLACE_ME",
        "trial_date": "YYYY-MM-DD",
        "site_id": "REPLACE_ME",
        "operational_process_ids": [
            "agent0",
            "agent1",
            "agent2",
            "agent3",
            "planner",
            "safety_supervisor",
        ],
        "observer_robot_ids": ["agent0", "agent1", "agent2", "agent3"],
        "recorder_host_ids": [
            "observer-host-0",
            "observer-host-1",
            "observer-host-2",
            "observer-host-3",
            "planner-host",
            "safety-host",
        ],
        "scorer_process_id": "independent_truth_recorder",
        "source_files": [
            {
                "path": "raw/observer-host-0.mcap",
                "kind": "operational_mcap",
                "host_id": "observer-host-0"
            },
            {
                "path": "raw/observer-host-1.mcap",
                "kind": "operational_mcap",
                "host_id": "observer-host-1"
            },
            {
                "path": "raw/observer-host-2.mcap",
                "kind": "operational_mcap",
                "host_id": "observer-host-2"
            },
            {
                "path": "raw/observer-host-3.mcap",
                "kind": "operational_mcap",
                "host_id": "observer-host-3"
            },
            {
                "path": "raw/planner-host.mcap",
                "kind": "operational_mcap",
                "host_id": "planner-host"
            },
            {
                "path": "raw/safety-host.mcap",
                "kind": "operational_mcap",
                "host_id": "safety-host"
            },
            {
                "path": "raw/truth.mcap",
                "kind": "truth_mcap",
                "host_id": "independent-truth-host"
            },
            {
                "path": "raw/network.pcapng",
                "kind": "pcap",
                "host_id": "network-tap"
            }
        ],
        "clock_offsets": [
            {"process_id": "agent0", "offset_ms": 0.0},
            {"process_id": "agent1", "offset_ms": 0.0},
            {"process_id": "agent2", "offset_ms": 0.0},
            {"process_id": "agent3", "offset_ms": 0.0},
            {"process_id": "independent_truth_recorder", "offset_ms": 0.0},
        ],
        "attack": {
            "kind": "none",
            "attacker_ids": [],
            "start_ns": 0,
            "stop_ns": 0,
        },
        "fault_manifest_id": "REPLACE_ME",
        "layout_id": "REPLACE_ME",
        "path_id": "REPLACE_ME",
        "lighting_id": "REPLACE_ME",
        "operator_blinded_to_arm": True,
    }


def create_physical_trial_plan(
    output: Path,
    *,
    phase: str,
    blocks_per_scenario: int = 30,
    trial_dates: Sequence[str] = ("day-1", "day-2", "day-3"),
) -> dict[str, Any]:
    """Create a randomized schedule and evidence-bundle template."""

    if phase not in {"pilot", "heldout"}:
        raise ValueError("phase must be pilot or heldout")
    if blocks_per_scenario < 1:
        raise ValueError("blocks_per_scenario must be positive")
    if not trial_dates:
        raise ValueError("at least one trial date is required")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    template = output / "bundle_template"
    template.mkdir(exist_ok=True)
    (template / "manifest.json").write_text(
        json.dumps(_trial_manifest_template(phase), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for filename in REQUIRED_LEDGER_FILES:
        (template / filename).write_text("", encoding="utf-8")
    (template / "artifact_hashes.json").write_text(
        json.dumps(
            {
                "instructions": "Run seal_physical_bundle after all recorders close.",
                "files": {},
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    rows: list[dict[str, Any]] = []
    for scenario in DEFAULT_HIL_SCENARIOS:
        for block in range(blocks_per_scenario):
            date = trial_dates[block % len(trial_dates)]
            arm_order = sorted(
                M13_ARMS,
                key=lambda arm: sha256_json(
                    {
                        "phase": phase,
                        "scenario": scenario.name,
                        "block": block,
                        "arm": arm,
                    }
                ),
            )
            for order, arm in enumerate(arm_order):
                block_id = f"{phase}-{scenario.name}-{block:03d}"
                rows.append(
                    {
                        "phase": phase,
                        "scenario": scenario.name,
                        "block_id": block_id,
                        "trial_date": date,
                        "within_block_order": order,
                        "arm": arm,
                        "run_id": f"m13-{block_id}-{arm}",
                        "layout_class": "development"
                        if phase == "pilot"
                        else "heldout_unseen",
                        "status": "planned",
                    }
                )
    _write_csv(output / "trial_schedule.csv", rows)
    protocol = {
        "milestone": "M13.2" if phase == "pilot" else "M13.3",
        "phase": phase,
        "blocks_per_scenario": blocks_per_scenario,
        "trial_dates": list(trial_dates),
        "scenarios": [scenario.name for scenario in DEFAULT_HIL_SCENARIOS],
        "arms": list(M13_ARMS),
        "paired_blocking": ["scenario", "block_id"],
        "randomization": "SHA-256 deterministic arm order; operator blinded",
        "truth_isolation": "independent scorer process and ledger",
        "external_evidence_required": True,
        "schedule_hash": sha256_json(rows),
    }
    (output / "plan.json").write_text(
        json.dumps(protocol, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return protocol


def seal_physical_bundle(bundle: Path) -> dict[str, Any]:
    """Seal closed recorders without modifying their evidence."""

    bundle = Path(bundle)
    required = {"manifest.json", *REQUIRED_LEDGER_FILES}
    missing = sorted(name for name in required if not (bundle / name).is_file())
    if missing:
        raise FileNotFoundError(f"cannot seal incomplete bundle: {missing}")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    source_files = manifest.get("source_files", [])
    if not isinstance(source_files, list) or not source_files:
        raise ValueError("manifest must list raw MCAP and packet-capture source files")
    source_names: set[str] = set()
    for item in source_files:
        relative = Path(str(item["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe source file path {relative}")
        if not (bundle / relative).is_file():
            raise FileNotFoundError(f"raw source file missing: {relative}")
        source_names.add(relative.as_posix())
    kinds = {str(item.get("kind")) for item in source_files}
    if not {"operational_mcap", "truth_mcap", "pcap"}.issubset(kinds):
        raise ValueError("source files must include operational/truth MCAP and PCAP")
    all_files = required | source_names
    hashes = {name: sha256_file(bundle / name) for name in sorted(all_files)}
    value = {
        "schema_version": SCHEMA_VERSION,
        "files": hashes,
        "bundle_hash": sha256_json(hashes),
        "sealed_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    (bundle / "artifact_hashes.json").write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return value


def audit_physical_bundle(bundle: Path) -> dict[str, Any]:
    bundle = Path(bundle)
    required = {"manifest.json", "artifact_hashes.json", *REQUIRED_LEDGER_FILES}
    missing = sorted(name for name in required if not (bundle / name).is_file())
    if missing:
        raise FileNotFoundError(f"physical bundle missing {missing}")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    required_manifest = {
        "schema_version",
        "run_id",
        "phase",
        "evidence_class",
        "adapter",
        "scenario",
        "arm",
        "block_id",
        "trial_date",
        "operational_process_ids",
        "scorer_process_id",
        "clock_offsets",
        "attack",
        "observer_robot_ids",
        "recorder_host_ids",
        "source_files",
    }
    missing_manifest = sorted(required_manifest.difference(manifest))
    if missing_manifest:
        raise ValueError(f"physical manifest missing {missing_manifest}")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("physical manifest schema version mismatch")
    seal = json.loads((bundle / "artifact_hashes.json").read_text(encoding="utf-8"))
    if seal.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("evidence seal schema version mismatch")
    source_files = manifest["source_files"]
    if not isinstance(source_files, list) or not source_files:
        raise ValueError("physical manifest has no raw source files")
    source_names: set[str] = set()
    source_kinds: set[str] = set()
    operational_hosts: set[str] = set()
    for item in source_files:
        relative = Path(str(item["path"]))
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"unsafe source file path {relative}")
        if not (bundle / relative).is_file():
            raise FileNotFoundError(f"raw source file missing: {relative}")
        source_names.add(relative.as_posix())
        kind = str(item.get("kind"))
        source_kinds.add(kind)
        if kind == "operational_mcap":
            operational_hosts.add(str(item.get("host_id")))
    if not {"operational_mcap", "truth_mcap", "pcap"}.issubset(source_kinds):
        raise ValueError("missing operational/truth MCAP or PCAP source")
    if operational_hosts != set(manifest["recorder_host_ids"]):
        raise ValueError("per-host operational MCAP coverage is incomplete")
    actual_hashes = {
        name: sha256_file(bundle / name)
        for name in sorted(
            {"manifest.json", *REQUIRED_LEDGER_FILES, *source_names}
        )
    }
    if seal.get("files") != actual_hashes:
        raise ValueError("physical evidence hashes do not match the seal")
    if seal.get("bundle_hash") != sha256_json(actual_hashes):
        raise ValueError("physical bundle hash is invalid")
    records: dict[str, list[dict[str, Any]]] = {}
    ledger_audits: dict[str, Any] = {}
    for filename, domain in REQUIRED_LEDGER_FILES.items():
        ledger_audits[filename] = verify_ledger(bundle / filename, domain)
        records[filename] = _load_ledger(bundle / filename, domain)
    isolation = audit_truth_isolation(
        [
            *records["operational.jsonl"],
            *records["transport.jsonl"],
            *records["safety.jsonl"],
        ],
        operational_process_ids=manifest.get("operational_process_ids", []),
        scorer_process_id=str(manifest.get("scorer_process_id", "")),
    )
    clock = audit_clock_offsets(manifest.get("clock_offsets", []))
    truth_process_violations = [
        index
        for index, record in enumerate(records["truth.jsonl"])
        if record.get("scorer_process_id") != manifest["scorer_process_id"]
    ]
    estimate_records = [
        record
        for record in records["operational.jsonl"]
        if record.get("event_type") == "estimate"
    ]
    expected_safety_records = len(estimate_records) * len(
        manifest["observer_robot_ids"]
    )
    safety_complete = (
        expected_safety_records > 0
        and len(records["safety.jsonl"]) == expected_safety_records
    )
    passed = (
        isolation["passed"]
        and clock["passed"]
        and not truth_process_violations
        and safety_complete
        and all(audit["records"] > 0 for audit in ledger_audits.values())
    )
    return {
        "passed": passed,
        "bundle_hash": seal["bundle_hash"],
        "manifest": manifest,
        "records": records,
        "truth_isolation": isolation,
        "clock": clock,
        "truth_process_violations": truth_process_violations,
        "expected_safety_records": expected_safety_records,
        "safety_complete": safety_complete,
        "ledgers": ledger_audits,
    }


def _nearest_truth(
    timestamp_ns: int,
    truth_records: Sequence[Mapping[str, Any]],
    maximum_delta_ns: int = 10_000_000,
) -> Mapping[str, Any]:
    nearest = min(
        truth_records,
        key=lambda record: abs(int(record["monotonic_ns"]) - timestamp_ns),
    )
    if abs(int(nearest["monotonic_ns"]) - timestamp_ns) > maximum_delta_ns:
        raise ValueError("operational estimate has no clock-aligned truth sample")
    return nearest


def score_physical_bundle(bundle: Path) -> PhysicalRunScore:
    """Recompute a run score exclusively from sealed raw ledgers."""

    audit = audit_physical_bundle(bundle)
    if not audit["passed"]:
        raise ValueError("physical bundle failed audit")
    manifest = audit["manifest"]
    operational = [
        record
        for record in audit["records"]["operational.jsonl"]
        if record.get("event_type") == "estimate"
    ]
    truth = audit["records"]["truth.jsonl"]
    if not operational or not truth:
        raise ValueError("bundle needs estimate and truth records")
    errors: list[float] = []
    nees_values: list[float] = []
    coverage: list[bool] = []
    losses: list[float] = []
    wrong_actions: list[bool] = []
    movements: list[float] = []
    runtimes: list[float] = []
    topology_disagreements: list[bool] = []
    alerts: list[bool] = []
    attack = dict(manifest.get("attack", {}))
    attack_start = int(attack.get("start_ns", 0))
    attack_stop = int(attack.get("stop_ns", 0))
    attack_kind = str(attack.get("kind", "none"))
    recovery_step = math.inf
    nominal_step_ns = math.inf
    for index, record in enumerate(operational):
        timestamp = int(record["monotonic_ns"])
        aligned = _nearest_truth(timestamp, truth)
        estimate = np.asarray(record["team_state"], dtype=float)
        covariance = np.asarray(record["team_covariance"], dtype=float).reshape(4, 4)
        target = np.asarray(aligned["target_state"], dtype=float)
        if estimate.shape != (4,) or target.shape != (4,):
            raise ValueError("team and truth states must contain four scalars")
        if float(np.min(np.linalg.eigvalsh(covariance))) < -1e-9:
            raise ValueError("submitted operational covariance is not PSD")
        difference = estimate[:2] - target[:2]
        error = float(np.linalg.norm(difference))
        position_covariance = covariance[:2, :2] + np.eye(2) * 1e-9
        nees = float(difference @ np.linalg.solve(position_covariance, difference))
        action = str(record.get("output_action", "defer"))
        wrong = action == "select" and error > 1.5
        loss = (
            min(error, 3.0) + (1.0 if wrong else 0.0)
            if action == "select"
            else 0.75
        )
        alert = int(record.get("trust_alert_agents", 0)) > 0
        if attack_kind != "none" and attack_start <= timestamp < attack_stop:
            alerts.append(alert)
        if attack_kind != "none" and timestamp >= attack_stop and not alert:
            if math.isinf(recovery_step):
                recovery_step = float(index)
        if index:
            nominal_step_ns = min(
                nominal_step_ns,
                timestamp - int(operational[index - 1]["monotonic_ns"]),
            )
        errors.append(error)
        nees_values.append(nees)
        coverage.append(nees <= 5.991)
        losses.append(loss)
        wrong_actions.append(wrong)
        movements.append(float(record.get("movement", 0.0)))
        runtimes.append(float(record.get("runtime_ms", 0.0)))
        topology_disagreements.append(
            int(record.get("component_count", 1))
            != int(record.get("expected_component_count", record.get("component_count", 1)))
        )
    false_alerts = [
        int(record.get("trust_alert_agents", 0)) > 0
        for record in operational
        if not (
            attack_kind != "none"
            and attack_start <= int(record["monotonic_ns"]) < attack_stop
        )
    ]
    if math.isinf(recovery_step) or not math.isfinite(nominal_step_ns):
        recovery_steps = 0.0 if attack_kind == "none" else float(len(operational))
    else:
        attack_stop_index = next(
            (
                index
                for index, record in enumerate(operational)
                if int(record["monotonic_ns"]) >= attack_stop
            ),
            len(operational),
        )
        recovery_steps = max(0.0, recovery_step - attack_stop_index)
    transport = audit["records"]["transport.jsonl"]
    sends = sum(record.get("event") == "send" for record in transport)
    receives = sum(record.get("event") == "receive" for record in transport)
    planner_transport = [
        record for record in transport if record.get("channel") == "planner"
    ]
    planner_messages = sum(record.get("event") == "send" for record in planner_transport)
    planner_bytes = sum(
        int(record.get("wire_bytes", 0))
        for record in planner_transport
        if record.get("event") == "send"
    )
    safety = audit["records"]["safety.jsonl"]
    safety_interventions = sum(bool(record.get("intervened", False)) for record in safety)
    emergency_stops = sum(bool(record.get("emergency_stop", False)) for record in safety)
    collisions = sum(bool(record.get("collision", False)) for record in safety)
    ownership_violations = sum(
        int(record.get("ownership_violations", 0)) for record in operational
    )
    maximum_allowed = max(
        (
            int(record.get("maximum_allowed_planner_messages", 0))
            for record in operational
        ),
        default=0,
    )
    decision_loss = float(np.mean(losses))
    movement = float(sum(movements))
    return PhysicalRunScore(
        run_id=str(manifest["run_id"]),
        evidence_hash=str(audit["bundle_hash"]),
        phase=str(manifest["phase"]),
        evidence_class=str(manifest["evidence_class"]),
        adapter=str(manifest["adapter"]),
        scenario=str(manifest["scenario"]),
        arm=str(manifest["arm"]),
        block_id=str(manifest["block_id"]),
        trial_date=str(manifest["trial_date"]),
        position_rmse=float(math.sqrt(np.mean(np.square(errors)))),
        mean_nees=float(np.mean(nees_values)),
        coverage95=float(np.mean(coverage)),
        decision_loss=decision_loss,
        wrong_action_rate=float(np.mean(wrong_actions)),
        integrated_loss=decision_loss + 0.015 * movement,
        alert_rate=float(np.mean(alerts)) if alerts else 1.0,
        false_alert_rate=float(np.mean(false_alerts)) if false_alerts else 0.0,
        recovery_steps=recovery_steps,
        movement=movement,
        delivery_ratio=receives / max(sends, 1),
        planner_messages=planner_messages,
        planner_bytes=planner_bytes,
        maximum_allowed_planner_messages=maximum_allowed,
        ownership_violations=ownership_violations,
        safety_interventions=safety_interventions,
        safety_events=len(safety),
        emergency_stops=emergency_stops,
        collisions=collisions,
        mean_runtime_ms=float(np.mean(runtimes)),
        topology_disagreement_rate=float(np.mean(topology_disagreements)),
        clock_maximum_offset_ms=float(audit["clock"]["maximum_absolute_offset_ms"]),
        audit_passed=True,
    )


def _paired_differences(
    scores: Sequence[PhysicalRunScore],
    metric: str,
) -> dict[str, list[tuple[str, float]]]:
    grouped: dict[tuple[str, str], dict[str, PhysicalRunScore]] = {}
    for score in scores:
        grouped.setdefault((score.scenario, score.block_id), {})[score.arm] = score
    result: dict[str, list[tuple[str, float]]] = {}
    for (scenario, _), arms in grouped.items():
        if M13_CENTRAL_ARM not in arms or M13_CANDIDATE_ARM not in arms:
            continue
        central = float(getattr(arms[M13_CENTRAL_ARM], metric))
        candidate = float(getattr(arms[M13_CANDIDATE_ARM], metric))
        date = arms[M13_CANDIDATE_ARM].trial_date
        result.setdefault(scenario, []).append((date, central - candidate))
    return result


def _mean_interval(values: Sequence[float]) -> tuple[float, float, float]:
    array = np.asarray(values, dtype=float)
    mean = float(np.mean(array))
    if array.size < 2:
        return mean, mean, mean
    standard_error = float(np.std(array, ddof=1) / math.sqrt(array.size))
    margin = NormalDist().inv_cdf(0.975) * standard_error
    return mean, mean - margin, mean + margin


def run_physical_pilot(
    bundles: Sequence[Path],
    output: Path,
    *,
    project_root: Path,
    target_effect: float = 0.05,
    minimum_blocks: int = 30,
    maximum_blocks: int = 500,
) -> dict[str, Any]:
    """Score genuine development bundles and freeze the physical holdout."""

    if not bundles:
        raise ValueError("pilot requires external bundle paths")
    scores = [score_physical_bundle(path) for path in bundles]
    invalid = [
        score.run_id
        for score in scores
        if score.phase != "pilot"
        or score.evidence_class != "external_physical"
        or score.adapter not in PHYSICAL_ADAPTERS
    ]
    if invalid:
        raise ValueError(
            "pilot freeze requires genuine external physical evidence: "
            + ", ".join(invalid)
        )
    grouped: dict[tuple[str, str], dict[str, PhysicalRunScore]] = {}
    for score in scores:
        key = (score.scenario, score.block_id)
        if score.arm in grouped.setdefault(key, {}):
            raise ValueError(f"duplicate pilot arm in block {key}: {score.arm}")
        grouped[key][score.arm] = score
    incomplete_scenarios = [
        scenario.name
        for scenario in DEFAULT_HIL_SCENARIOS
        if not any(
            name == scenario.name and set(arms) == set(M13_ARMS)
            for (name, _), arms in grouped.items()
        )
    ]
    if incomplete_scenarios:
        raise ValueError(
            "pilot needs at least one complete four-arm block per scenario: "
            + ", ".join(incomplete_scenarios)
        )
    paired = _paired_differences(scores, "integrated_loss")
    differences = [value for rows in paired.values() for _, value in rows]
    if len(differences) < 2:
        raise ValueError("pilot requires at least two paired candidate/central blocks")
    standard_deviation = float(np.std(differences, ddof=1))
    z_sum = NormalDist().inv_cdf(0.975) + NormalDist().inv_cdf(0.8)
    estimated = math.ceil(2.0 * (z_sum * standard_deviation / target_effect) ** 2)
    required = int(np.clip(estimated, minimum_blocks, maximum_blocks))
    covariance_scale = float(
        np.clip(np.mean([score.mean_nees for score in scores]) / 2.0, 0.5, 4.0)
    )
    project_root = Path(project_root)
    candidate_hashes = current_candidate_hashes(project_root)
    pilot_hashes = sorted(score.evidence_hash for score in scores)
    freeze = {
        "milestone": "M13.2",
        "status": "FROZEN_FROM_EXTERNAL_PILOT",
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_hashes": candidate_hashes,
        "pilot_evidence_hashes": pilot_hashes,
        "pilot_run_ids": sorted(score.run_id for score in scores),
        "calibration": {
            "camera_covariance_scale": covariance_scale,
            "clock_offset_limit_ms": 5.0,
        },
        "power": {
            "paired_effect_standard_deviation": standard_deviation,
            "target_integrated_loss_effect": target_effect,
            "alpha_two_sided": 0.05,
            "power": 0.8,
            "minimum_paired_blocks_per_scenario": required,
            "minimum_days": 3,
        },
        "heldout_scenarios": [
            scenario.name for scenario in DEFAULT_HIL_SCENARIOS
        ],
        "heldout_arms": list(M13_ARMS),
        "external_physical_adapters": sorted(PHYSICAL_ADAPTERS),
        "gates": {
            "truth_and_replay": True,
            "collisions_and_emergency_stops": 0,
            "safety_intervention_rate_max": 0.01,
            "ownership_violations": 0,
            "planner_message_bound": True,
            "candidate_vs_central_integrated_loss_lcb_min": -0.05,
            "attack_decision_loss_max": 1.50,
            "wrong_action_rate_max": 0.01,
            "mean_nees_max": 6.0,
            "coverage95_min": 0.88,
            "attack_alert_rate_min": 0.50,
            "false_alert_rate_max": 0.05,
            "recovery_steps_max": 30.0,
            "maximum_material_regression": 0.05,
            "leave_one_day_out_lcb_min": -0.05,
        },
    }
    freeze["freeze_hash"] = sha256_json(freeze)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "pilot_run_scores.csv", [asdict(score) for score in scores])
    (output / "power_freeze.json").write_text(
        json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = [
        "# M13.2 physical development pilot",
        "",
        "**Status: holdout protocol frozen from genuine external evidence.**",
        "",
        f"- Scored physical runs: {len(scores)}",
        f"- Paired candidate/central blocks: {len(differences)}",
        f"- Frozen blocks per held-out scenario: {required}",
        f"- Camera covariance scale: {covariance_scale:.4f}",
        f"- Candidate/protocol files frozen: {len(candidate_hashes)}",
        "",
        "Pilot run IDs and evidence hashes are excluded from M13.3.",
    ]
    (output / "pilot_report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    return freeze


def evaluate_physical_holdout(
    bundles: Sequence[Path],
    freeze_path: Path,
    output: Path,
    *,
    project_root: Path,
) -> dict[str, Any]:
    """Evaluate preregistered external physical holdout evidence once."""

    freeze = json.loads(Path(freeze_path).read_text(encoding="utf-8"))
    supplied_hash = freeze.pop("freeze_hash", None)
    if supplied_hash != sha256_json(freeze):
        raise ValueError("power freeze hash is invalid")
    freeze["freeze_hash"] = supplied_hash
    current_hashes = current_candidate_hashes(Path(project_root))
    integrity_reasons: list[str] = []
    if freeze.get("status") != "FROZEN_FROM_EXTERNAL_PILOT":
        integrity_reasons.append("freeze was not produced by an external pilot")
    if freeze.get("candidate_hashes") != current_hashes:
        integrity_reasons.append("candidate or protocol changed after pilot freeze")
    scores: list[PhysicalRunScore] = []
    for bundle in bundles:
        try:
            scores.append(score_physical_bundle(bundle))
        except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
            integrity_reasons.append(f"{bundle}: {error}")
    pilot_hashes = set(freeze.get("pilot_evidence_hashes", []))
    for score in scores:
        if score.phase != "heldout":
            integrity_reasons.append(f"{score.run_id}: not a heldout run")
        if score.evidence_hash in pilot_hashes:
            integrity_reasons.append(f"{score.run_id}: reused pilot evidence")
        if (
            score.evidence_class != "external_physical"
            or score.adapter not in set(freeze.get("external_physical_adapters", []))
        ):
            integrity_reasons.append(
                f"{score.run_id}: not genuine external physical evidence"
            )
    expected_scenarios = set(freeze.get("heldout_scenarios", []))
    expected_arms = set(freeze.get("heldout_arms", []))
    grouped: dict[tuple[str, str], dict[str, PhysicalRunScore]] = {}
    seen_run_ids: set[str] = set()
    seen_evidence_hashes: set[str] = set()
    for score in scores:
        if score.run_id in seen_run_ids:
            integrity_reasons.append(f"{score.run_id}: duplicate run ID")
        if score.evidence_hash in seen_evidence_hashes:
            integrity_reasons.append(f"{score.run_id}: duplicate evidence bundle")
        seen_run_ids.add(score.run_id)
        seen_evidence_hashes.add(score.evidence_hash)
        arms = grouped.setdefault((score.scenario, score.block_id), {})
        if score.arm in arms:
            integrity_reasons.append(
                f"{score.scenario}/{score.block_id}: duplicate arm {score.arm}"
            )
        arms[score.arm] = score
    required_blocks = int(
        freeze.get("power", {}).get("minimum_paired_blocks_per_scenario", 30)
    )
    for scenario in expected_scenarios:
        complete = [
            arms
            for (name, _), arms in grouped.items()
            if name == scenario and set(arms) == expected_arms
        ]
        if len(complete) < required_blocks:
            integrity_reasons.append(
                f"{scenario}: {len(complete)} complete blocks, {required_blocks} required"
            )
    dates = {score.trial_date for score in scores}
    if len(dates) < int(freeze.get("power", {}).get("minimum_days", 3)):
        integrity_reasons.append("fewer than three physical trial days")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if integrity_reasons:
        decision = {
            "milestone": "M13.3",
            "verdict": "M13.3-INVALID",
            "deployment_authorized": False,
            "integrity_reasons": integrity_reasons,
            "scored_runs": len(scores),
        }
        (output / "decision.json").write_text(
            json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (output / "m13_3_report.md").write_text(
            "# M13.3 physical holdout\n\n"
            "**Verdict: M13.3-INVALID.**\n\n"
            + "\n".join(f"- {reason}" for reason in integrity_reasons)
            + "\n",
            encoding="utf-8",
        )
        return decision

    _write_csv(output / "heldout_run_scores.csv", [asdict(score) for score in scores])
    paired = _paired_differences(scores, "integrated_loss")
    all_differences = [value for rows in paired.values() for _, value in rows]
    mean, lower, upper = _mean_interval(all_differences)
    candidate = [score for score in scores if score.arm == M13_CANDIDATE_ARM]
    central = [score for score in scores if score.arm == M13_CENTRAL_ARM]
    attacks = [score for score in candidate if score.scenario in ATTACK_SCENARIOS]
    nominal = [
        score
        for score in candidate
        if score.scenario in {"stable", "legitimate_precision_minority"}
    ]
    total_safety_events = sum(score.safety_events for score in candidate)

    def relative_regression(metric: str, *, larger_is_better: bool = False) -> float:
        candidate_mean = float(np.mean([getattr(score, metric) for score in candidate]))
        central_mean = float(np.mean([getattr(score, metric) for score in central]))
        denominator = max(abs(central_mean), 1e-9)
        return (
            (central_mean - candidate_mean) / denominator
            if larger_is_better
            else (candidate_mean - central_mean) / denominator
        )

    leave_day_lowers: dict[str, float] = {}
    for date in sorted(dates):
        values = [
            difference
            for rows in paired.values()
            for row_date, difference in rows
            if row_date != date
        ]
        leave_day_lowers[date] = _mean_interval(values)[1]
    gate_spec = freeze["gates"]
    gates = {
        "truth_isolation_and_replay_completeness": all(
            score.audit_passed for score in scores
        ),
        "zero_collisions_and_emergency_stops": all(
            score.collisions == 0 and score.emergency_stops == 0
            for score in candidate
        ),
        "safety_intervention_rate": (
            sum(score.safety_interventions for score in candidate)
            / max(total_safety_events, 1)
            < float(gate_spec["safety_intervention_rate_max"])
        ),
        "ownership_and_message_bounds": all(
            score.ownership_violations == 0
            and score.planner_messages <= score.maximum_allowed_planner_messages
            for score in candidate
        ),
        "decentralized_integrated_loss_lcb": lower
        >= float(gate_spec["candidate_vs_central_integrated_loss_lcb_min"]),
        "attack_decision_loss": float(
            np.mean([score.decision_loss for score in attacks])
        )
        <= float(gate_spec["attack_decision_loss_max"]),
        "wrong_action_rate": float(
            np.mean([score.wrong_action_rate for score in candidate])
        )
        <= float(gate_spec["wrong_action_rate_max"]),
        "calibration": (
            float(np.mean([score.mean_nees for score in candidate]))
            <= float(gate_spec["mean_nees_max"])
            and float(np.mean([score.coverage95 for score in candidate]))
            >= float(gate_spec["coverage95_min"])
        ),
        "attack_alert_rate": float(
            np.mean([score.alert_rate for score in attacks])
        )
        >= float(gate_spec["attack_alert_rate_min"]),
        "false_alert_rate": float(
            np.mean([score.false_alert_rate for score in nominal])
        )
        <= float(gate_spec["false_alert_rate_max"]),
        "attack_recovery": float(
            np.mean([score.recovery_steps for score in attacks])
        )
        <= float(gate_spec["recovery_steps_max"]),
        "delivery_topology_movement_runtime": all(
            regression <= float(gate_spec["maximum_material_regression"])
            for regression in (
                relative_regression("delivery_ratio", larger_is_better=True),
                relative_regression("topology_disagreement_rate"),
                relative_regression("movement"),
                relative_regression("mean_runtime_ms"),
            )
        ),
        "not_one_day_driven": all(
            value >= float(gate_spec["leave_one_day_out_lcb_min"])
            for value in leave_day_lowers.values()
        ),
    }
    verdict = "M13.3-PHYSICAL-GO" if all(gates.values()) else "M13.3-PHYSICAL-NO-GO"
    decision = {
        "milestone": "M13.3",
        "verdict": verdict,
        "deployment_authorized": False,
        "gates": gates,
        "candidate_vs_central_integrated_loss": {
            "mean": mean,
            "ci95_lower": lower,
            "ci95_upper": upper,
        },
        "leave_one_day_out_lowers": leave_day_lowers,
        "run_count": len(scores),
        "complete_block_count": len(grouped),
        "trial_dates": sorted(dates),
        "freeze_hash": supplied_hash,
    }
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report = [
        "# M13.3 preregistered physical holdout",
        "",
        f"**Verdict: {verdict}.**",
        "",
        "A physical GO supports the research claim under the tested envelope; it "
        "does not itself authorize unattended or production deployment.",
        "",
        "## Gates",
        "",
    ]
    report.extend(
        f"- {'PASS' if passed else 'FAIL'} — `{name}`"
        for name, passed in gates.items()
    )
    (output / "m13_3_report.md").write_text(
        "\n".join(report) + "\n", encoding="utf-8"
    )
    return decision
