"""M14.4 companion: verify historical certification against the pre-M14 commit.

Widening the frozen source sets (M14.4) means the current tree no longer matches
the ``candidate_source_sha256`` recorded in pre-M14 artifacts. That is the chain
of custody working, not breaking -- but it leaves a question a referee will ask:
*can the historical certification still be checked at all?*

It can, and this script is the check. Git history preserves the exact tree that
produced each artifact, so every recorded hash is recomputable from the pre-M14
commit. Git history therefore serves as the legacy hash manifest; no separate
``legacy_source_sha256`` field is needed.

Usage:
    python3 _m14/verify_legacy_certification.py [PRE_M14_COMMIT]

Exit status is 0 when every determinable artifact verifies against history.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Which source files each suite folds into candidate_source_sha256. This mapping
# is hardcoded in the suite modules rather than recorded in the artifacts, which
# is itself a gap -- see the FINDING printed at the end.
SOURCE_SETS: dict[str, list[str]] = {
    "milestone9c_heldout": [
        "integrated_sensing.py", "integration_suite.py",
        "experiment.py", "config.py", "metrics.py",
    ],
    "milestone9a7_heldout": [
        "admission_suite.py", "admission_evidence.py",
        "missing_evidence.py", "oracle_floor.py",
    ],
    "milestone10a_heldout": ["adversarial_trust.py", "adversarial_trust_suite.py"],
    "milestone10a5_heldout": ["closed_loop_trust.py", "closed_loop_trust_suite.py"],
    "milestone10b_heldout": ["decentralized_sensing.py", "decentralized_suite.py"],
    "milestone11_heldout": ["external_replay.py", "external_replay_suite.py"],
    "milestone11_1_heldout": [
        "external_replay_repair.py", "external_replay_repair_suite.py",
    ],
    "milestone12_development": ["acceleration_replay.py", "acceleration_suite.py"],
}


def blob(commit: str, path: str) -> bytes:
    out = subprocess.run(
        ["git", "-C", str(REPO), "show", f"{commit}:{path}"],
        capture_output=True,
    )
    if out.returncode != 0:
        raise FileNotFoundError(f"{path} not in {commit}")
    return out.stdout


def artifact_hash(names_and_bytes: list[tuple[str, bytes]]) -> str:
    """Replicate _artifact_hash: file *name* bytes then content bytes, in order."""
    digest = hashlib.sha256()
    for name, payload in names_and_bytes:
        digest.update(name.encode("utf-8"))
        digest.update(payload)
    return digest.hexdigest()


def main(commit: str) -> int:
    results_dir = REPO / "results"
    verified: list[str] = []
    failed: list[str] = []
    no_hash: list[str] = []
    unmapped: list[str] = []

    for path in sorted(results_dir.glob("*/suite_config.json")):
        name = path.parent.name
        suite = json.loads(path.read_text())
        recorded = suite.get("candidate_source_sha256")
        if not recorded:
            no_hash.append(name)
            continue
        files = SOURCE_SETS.get(name)
        if not files:
            unmapped.append(name)
            continue
        try:
            payload = [
                (f, blob(commit, f"src/flockkalman/{f}")) for f in files
            ]
        except FileNotFoundError as exc:
            print(f"  {name}: cannot read from history -- {exc}")
            failed.append(name)
            continue
        got = artifact_hash(payload)
        current = artifact_hash(
            [(f, (REPO / "src/flockkalman" / f).read_bytes()) for f in files]
        )
        if got == recorded:
            drifted = " (current tree differs, as expected after M14)" if current != recorded else ""
            print(f"  PASS  {name}{drifted}")
            verified.append(name)
        else:
            print(f"  FAIL  {name}")
            print(f"        recorded    {recorded}")
            print(f"        history     {got}")
            failed.append(name)

    print()
    print(f"verified against {commit}: {len(verified)}")
    print(f"failed:                   {len(failed)}")
    print(f"artifact records no source hash: {len(no_hash)}")
    for n in no_hash:
        print(f"    {n}")
    if unmapped:
        print(f"hash recorded but source set unknown to this script: {len(unmapped)}")
        for n in unmapped:
            print(f"    {n}")

    print()
    print("FINDING (for the paper's methods section, not a defect of this script):")
    print("  Only the artifacts listed as verified/failed record a candidate source")
    print("  hash at all. The freeze-and-hash discipline covers a minority of the")
    print("  program. Notably M9A (topology_suite) and M9A.6 (missing_evidence_suite)")
    print("  record none -- and M9A.6 is the motivating finding of P1. Any claim that")
    print("  'implementations and protocols are frozen and hashed' must be scoped to")
    print("  the suites that actually do it.")
    print()
    print("  Second gap: the file *list* behind each hash lives in the suite module,")
    print("  not in the artifact, so verification requires reading the code that")
    print("  produced it. Future suites should record the list alongside the digest.")

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "568fbfa"))
