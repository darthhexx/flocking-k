"""Mechanical diagnostic firewall (milestone M14.5).

Before M14 the firewall between diagnosis and promotion was the string literal
``"non_promotional": True`` written into two dictionaries in
``oracle_floor_suite.py``. Nothing enforced it: no namespace separation, no gate
refusing to consume oracle output, and no check that a diagnostic had not been run
against the very seeds a held-out verdict depended on.

It was crossed. ``results/milestone9a5_oracle_floor/suite_config.json`` records
``seed_start: 12000, seed_count: 100`` -- byte-identical to M9A's held-out split --
and the repository's own README documents the finding from that diagnostic
selecting the next milestone's architecture ("*At the M9A.6 decision point, the
next bounded repair was therefore admission-aware missingness with separate trust
channels*"). The sequence was: open held-out, run a diagnostic on those same
traces, use the result to choose the next candidate, evaluate it.

This module makes the constraint mechanical. A diagnostic suite must declare its
seed range, and the range is checked against every held-out range recorded in the
results tree. Overlap raises :class:`DiagnosticFirewallError`.

The escape hatch is deliberately awkward. ``acknowledge_overlap`` requires a
non-empty written justification, which is returned for recording in the artifact,
so a violation becomes a declared and durable statement rather than a boolean
someone flipped. Reproducing the historical M9A.5 run is exactly this case: it
*did* use M9A's held-out seeds, and re-running it must say so out loud rather than
quietly succeed.

Only ``run_*`` entry points are guarded. Reanalysis of an existing artifact is not
blocked -- the run already happened, and refusing to recompute its statistics
would destroy the ability to audit it, which is the opposite of the intent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

__all__ = [
    "DiagnosticFirewallError",
    "SeedRange",
    "assert_diagnostic_seeds_clear",
    "check_diagnostic_seeds",
    "held_out_seed_ranges",
]


class DiagnosticFirewallError(RuntimeError):
    """A diagnostic suite was launched against held-out seeds."""


@dataclass(frozen=True)
class SeedRange:
    """A half-open seed interval ``[start, start + count)`` and its provenance."""

    artifact: str
    start: int
    count: int

    @property
    def stop(self) -> int:
        return self.start + self.count

    def overlaps(self, start: int, count: int) -> bool:
        return start < self.stop and self.start < start + count

    def intersection(self, start: int, count: int) -> tuple[int, int] | None:
        lo, hi = max(self.start, start), min(self.stop, start + count)
        return (lo, hi - 1) if lo < hi else None

    def describe(self) -> str:
        return f"{self.artifact} [{self.start}..{self.stop - 1}]"


#: Substrings in an artifact directory name that mark it as a held-out split.
#: Name-based rather than phase-based because ``phase`` is absent from many
#: pre-M14 artifacts, and a missing field must not silently disable the check.
HELD_OUT_MARKERS = ("heldout", "held_out", "held-out")


def _is_held_out(name: str, suite: dict[str, Any]) -> bool:
    lowered = name.lower()
    if any(marker in lowered for marker in HELD_OUT_MARKERS):
        return True
    phase = str(suite.get("phase", "")).lower()
    return phase in {"heldout", "held_out", "held-out", "confirmatory"}


def held_out_seed_ranges(project_root: str | Path) -> list[SeedRange]:
    """Every held-out seed range recorded in the results tree.

    Reads the artifacts rather than a hand-maintained list, so a newly opened
    held-out split is protected the moment it is written, with no second place to
    remember to update.
    """
    root = Path(project_root)
    ranges: list[SeedRange] = []
    for config_path in sorted((root / "results").glob("*/suite_config.json")):
        try:
            suite = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        name = config_path.parent.name
        if not _is_held_out(name, suite):
            continue
        start, count = suite.get("seed_start"), suite.get("seed_count")
        if start is None or count is None:
            continue
        ranges.append(SeedRange(artifact=name, start=int(start), count=int(count)))
    return ranges


def check_diagnostic_seeds(
    seed_start: int,
    seed_count: int,
    project_root: str | Path,
) -> dict[str, Any]:
    """Report, without raising, whether a diagnostic range touches held-out seeds."""
    ranges = held_out_seed_ranges(project_root)
    overlaps = [
        {
            "artifact": item.artifact,
            "held_out_range": [item.start, item.stop - 1],
            "intersection": list(item.intersection(seed_start, seed_count) or ()),
        }
        for item in ranges
        if item.overlaps(seed_start, seed_count)
    ]
    return {
        "requested_range": [seed_start, seed_start + seed_count - 1],
        "held_out_ranges_checked": len(ranges),
        "overlaps": overlaps,
        "clear": not overlaps,
    }


def assert_diagnostic_seeds_clear(
    seed_start: int,
    seed_count: int,
    project_root: str | Path,
    *,
    acknowledge_overlap: str | None = None,
) -> dict[str, Any]:
    """Raise unless a diagnostic's seed range is disjoint from every held-out split.

    Returns a record for embedding in the artifact, so the check is visible in the
    output whether or not it found anything -- a firewall that leaves no trace when
    it passes is indistinguishable from one that was never run.

    ``acknowledge_overlap`` must be a written justification of at least 20
    characters. A bare ``True`` is not accepted, and the text is copied into the
    returned record.
    """
    report = check_diagnostic_seeds(seed_start, seed_count, project_root)
    if report["clear"]:
        report["status"] = "FIREWALL-CLEAR"
        report["acknowledged_overlap"] = None
        return report

    detail = "; ".join(
        f"{item['artifact']} seeds {item['intersection'][0]}..{item['intersection'][1]}"
        for item in report["overlaps"]
    )
    if acknowledge_overlap is None:
        raise DiagnosticFirewallError(
            "diagnostic seed range "
            f"{seed_start}..{seed_start + seed_count - 1} intersects held-out "
            f"splits: {detail}. Running a diagnostic on opened held-out traces is "
            "a selection pathway: its finding can steer the design of the next "
            "candidate, which is then evaluated as though independent. Move the "
            "diagnostic to a dedicated seed band, or pass acknowledge_overlap="
            "'<written justification>' to declare the violation in the artifact."
        )
    if not isinstance(acknowledge_overlap, str) or len(acknowledge_overlap.strip()) < 20:
        raise DiagnosticFirewallError(
            "acknowledge_overlap must be a written justification of at least 20 "
            "characters; a bare flag is not sufficient to record a firewall "
            "violation."
        )
    report["status"] = "FIREWALL-OVERLAP-ACKNOWLEDGED"
    report["acknowledged_overlap"] = acknowledge_overlap.strip()
    report["warning"] = (
        "This diagnostic ran on opened held-out seeds. Any downstream candidate "
        "whose design was informed by it is not independent of those seeds, and "
        "that dependence must be disclosed wherever the downstream result is "
        f"reported. Overlap: {detail}."
    )
    return report
