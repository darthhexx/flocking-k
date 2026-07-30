"""Produce the M14 decision record by executing its gates (milestone M14).

Written in the program's own idiom: the verdict is computed from evidence gathered
here, not asserted. Each gate reports what it checked and why it passed or failed,
and 14.1 deliberately cannot be satisfied from this session -- the repository must
be observable on a third-party host, which needs credentials this environment does
not have.

Usage:  python3 _m14/record_m14_decision.py [--output results/milestone14_remediation]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from flockkalman.provenance import environment_fingerprint  # noqa: E402


def _run(script: str) -> tuple[bool, str]:
    # Explicit PYTHONPATH so the gate checks work in a bare checkout with no
    # editable install. Without it these gates fail for an environmental reason
    # that has nothing to do with what they are meant to test.
    import os

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT / "src"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "_m14" / script)],
        cwd=ROOT, capture_output=True, text=True, env=env,
    )
    return proc.returncode == 0, (proc.stdout + proc.stderr)[-2000:]


def gate_14_1() -> dict[str, object]:
    """Version control, pushed to a third-party host with observable dates."""
    def git(*args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(ROOT), *args], capture_output=True, text=True
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""

    has_git = (ROOT / ".git").is_dir()
    commits = git("rev-list", "--count", "HEAD")
    remotes = git("remote", "-v")
    tracked = git("ls-files")
    pushed = bool(remotes.strip())
    return {
        "passed": bool(has_git and commits and pushed),
        "repository_initialised": has_git,
        "commit_count": int(commits) if commits.isdigit() else 0,
        "tracked_files": len(tracked.splitlines()) if tracked else 0,
        "remote_configured": pushed,
        "detail": (
            "Repository exists with history, but no remote is configured. The gate "
            "requires a third-party host so a third party can observe the dates; a "
            "hash in a local repository demonstrates internal consistency and "
            "nothing about when. Push, then re-run this script."
            if not pushed else
            "Repository initialised, committed, and pushed to a remote."
        ),
    }


def gate_14_2_3() -> dict[str, object]:
    """Environment pinned and compared; replay gate hardened."""
    fingerprint_ok, fingerprint_log = _run("check_fingerprint.py")
    replay_ok, replay_log = _run("check_replay_gate.py")
    return {
        "passed": fingerprint_ok and replay_ok,
        "fingerprint_invariants": fingerprint_ok,
        "replay_gate_regressions": replay_ok,
        "evidence": {
            "check_fingerprint": fingerprint_log[-700:],
            "check_replay_gate": replay_log[-700:],
        },
    }


def gate_14_4() -> dict[str, object]:
    """Frozen sets complete; historical certification verifiable."""
    legacy_ok, legacy_log = _run("verify_legacy_certification.py")
    src = ROOT / "src/flockkalman"
    wired = []
    for name in (
        "topology_suite.py", "missing_evidence_suite.py", "admission_suite.py",
        "integration_suite.py", "adversarial_trust_suite.py",
        "closed_loop_trust_suite.py",
    ):
        text = (src / name).read_text(encoding="utf-8")
        wired.append(name if "ReplayVerification" in text else None)
    all_wired = all(wired)
    return {
        "passed": legacy_ok and all_wired,
        "legacy_certification_verifies": legacy_ok,
        "replay_gated_suites_wired": [n for n in wired if n],
        "suites_expected": 6,
        "evidence": legacy_log[-700:],
    }


def gate_14_5() -> dict[str, object]:
    """Diagnostic firewall is mechanical."""
    from flockkalman.firewall import (
        DiagnosticFirewallError,
        check_diagnostic_seeds,
        held_out_seed_ranges,
    )

    ranges = held_out_seed_ranges(ROOT)
    historical = check_diagnostic_seeds(12000, 100, ROOT)
    clean = check_diagnostic_seeds(30000, 100, ROOT)

    blocked = False
    try:
        from flockkalman.config import ExperimentConfig
        from flockkalman.oracle_floor_suite import run_oracle_floor_suite

        run_oracle_floor_suite(
            ExperimentConfig(), ROOT / "_m14/_firewall_probe",
            seed_count=100, seed_start=12000,
        )
    except DiagnosticFirewallError:
        blocked = True
    except Exception:  # noqa: BLE001
        blocked = False

    bare_flag_rejected = False
    try:
        from flockkalman.firewall import assert_diagnostic_seeds_clear

        assert_diagnostic_seeds_clear(12000, 100, ROOT, acknowledge_overlap=True)  # type: ignore[arg-type]
    except DiagnosticFirewallError:
        bare_flag_rejected = True

    return {
        "passed": bool(
            ranges and not historical["clear"] and clean["clear"]
            and blocked and bare_flag_rejected
        ),
        "held_out_ranges_discovered": len(ranges),
        "historical_m9a5_overlap_detected": not historical["clear"],
        "historical_overlap": historical["overlaps"],
        "m16_planned_band_clear": clean["clear"],
        "oracle_floor_run_blocked_by_default": blocked,
        "bare_acknowledgement_flag_rejected": bare_flag_rejected,
    }


def gate_14_6() -> dict[str, object]:
    """Figures read results/."""
    ok, log = _run("check_figure_data.py")
    return {"passed": ok, "evidence": log[-900:]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path,
                        default=ROOT / "results/milestone14_remediation")
    args = parser.parse_args()

    gates = {
        "14_1_version_control": gate_14_1(),
        "14_2_3_environment_and_replay": gate_14_2_3(),
        "14_4_frozen_sets": gate_14_4(),
        "14_5_mechanical_firewall": gate_14_5(),
        "14_6_figures_from_results": gate_14_6(),
    }
    passed = {name: bool(g["passed"]) for name, g in gates.items()}
    verdict = "M14-GO" if all(passed.values()) else "M14-BLOCKED"

    decision = {
        "verdict": verdict,
        "milestone": "M14",
        "research_question": (
            "Can the platform support confirmatory claims that survive an "
            "independent referee re-running the artifact?"
        ),
        "gates": passed,
        "gate_detail": gates,
        "environment": environment_fingerprint(),
        "verdict_semantics": {
            "M14-GO": "all gates passed; M15 may run",
            "M14-BLOCKED": "a prerequisite is unmet; downstream milestones must not run",
        },
        "notes": [
            "M14 gates every downstream milestone. A BLOCKED verdict means M15 "
            "onward must not run, regardless of how the other gates read.",
            "Gate 14.1 cannot be satisfied from an environment without repository "
            "credentials. This is a real unmet prerequisite, not a technicality: "
            "predeclaration requires a third party to be able to observe the dates.",
        ],
    }

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"verdict: {verdict}")
    for name, ok in passed.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"\nwritten: {args.output / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
