"""Figure data sourced from ``results/`` (milestone M14.6).

``generate_paper_figures.py`` imported exactly ``math`` and ``pathlib``. Every
verdict, gate count and metric in the four paper figures was a hardcoded literal,
so the figures a referee looks at had no mechanical link to the artifacts they
claim to depict. They happened to match, but only because someone transcribed them
by hand -- and for a paper whose argument is that its artifacts bind it, that is
the wrong way round.

This module is the missing link. Everything a figure needs is derived from
``results/*/decision.json`` and the CSV summaries. Nothing is defaulted: a missing
value raises :class:`FigureDataError` rather than silently falling back, because a
figure that quietly renders a stale number is worse than one that fails to render.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

__all__ = [
    "FigureDataError",
    "MilestoneRecord",
    "load_milestone",
    "load_milestones",
    "metric_from_scenario_summary",
]


class FigureDataError(RuntimeError):
    """A figure asked for a value the artifacts do not contain."""


@dataclass(frozen=True)
class MilestoneRecord:
    """The figure-relevant facts about one milestone artifact."""

    artifact: str
    verdict: str
    gates_passed: int
    gates_total: int
    seed_start: int | None
    seed_count: int | None
    replay_status: str | None

    @property
    def gate_summary(self) -> str:
        """e.g. ``"12/12 gates passed"`` -- derived, never transcribed."""
        return f"{self.gates_passed}/{self.gates_total} gates passed"

    @property
    def all_gates_passed(self) -> bool:
        return self.gates_total > 0 and self.gates_passed == self.gates_total

    @property
    def verdict_class(self) -> str:
        """Coarse class driving figure colour, derived from the verdict string."""
        v = self.verdict.upper()
        if v.startswith("DIAGNOSTIC") or "UNRESOLVED" in v:
            return "diagnostic"
        if "INVALID" in v:
            return "invalid"
        if "PARTIAL" in v:
            return "partial"
        if "REPLAY-" in v:
            # A provenance-qualified verdict: substantive gates passed but the
            # replay was not bit-exactly certifiable. Its own class so a figure
            # cannot silently render it as a clean GO.
            return "qualified"
        if "NO-GO" in v or "FAIL" in v:
            return "rejected"
        if "GO" in v or "PASS" in v or "READY" in v:
            return "promoted"
        return "other"


def _results_root(project_root: str | Path) -> Path:
    root = Path(project_root) / "results"
    if not root.is_dir():
        raise FigureDataError(f"no results directory at {root}")
    return root


#: Artifacts whose verdict lives somewhere other than ``decision.json``. The
#: mechanism sweep (M8.2) writes ``mechanism.json`` because it is a training
#: diagnostic and produces no decision. Listed explicitly rather than discovered by
#: globbing, so a figure can never pick up an unintended file.
ALTERNATIVE_DECISION_FILES = {
    "momentum_mechanism_training": "mechanism.json",
}


def load_milestone(artifact: str, project_root: str | Path) -> MilestoneRecord:
    """Read one artifact's decision and suite config."""
    directory = _results_root(project_root) / artifact
    filename = ALTERNATIVE_DECISION_FILES.get(artifact, "decision.json")
    decision_path = directory / filename
    if not decision_path.is_file():
        raise FigureDataError(f"missing {decision_path}")
    decision = json.loads(decision_path.read_text(encoding="utf-8"))

    verdict = decision.get("verdict")
    if not isinstance(verdict, str):
        # Diagnostic suites deliberately record no verdict -- that is the point of
        # being non-promotional. They carry a diagnostic_conclusion instead, and it
        # is read here rather than being allowed to masquerade as a verdict.
        conclusion = decision.get("diagnostic_conclusion")
        if isinstance(conclusion, str):
            verdict = f"DIAGNOSTIC: {conclusion}"
        else:
            raise FigureDataError(
                f"{artifact}: decision.json has neither a verdict nor a "
                "diagnostic_conclusion string"
            )

    gates = decision.get("gates")
    if isinstance(gates, dict):
        total = len(gates)
        passed = sum(1 for value in gates.values() if value)
    elif str(verdict).startswith("DIAGNOSTIC") or "UNRESOLVED" in str(verdict).upper():
        # A diagnostic has no gates because it promotes nothing. Zero/zero is the
        # honest encoding, and `all_gates_passed` is False for it by construction
        # so no figure can render a diagnostic as having passed anything.
        total = passed = 0
    else:
        raise FigureDataError(f"{artifact}: decision.json has no gates mapping")

    suite: dict[str, Any] = {}
    suite_path = directory / "suite_config.json"
    if suite_path.is_file():
        suite = json.loads(suite_path.read_text(encoding="utf-8"))

    replay = decision.get("replay_verification")
    replay_status = (
        str(replay["status"]) if isinstance(replay, dict) and "status" in replay else None
    )

    return MilestoneRecord(
        artifact=artifact,
        verdict=verdict,
        gates_passed=passed,
        gates_total=total,
        seed_start=suite.get("seed_start"),
        seed_count=suite.get("seed_count"),
        replay_status=replay_status,
    )


def load_milestones(
    artifacts: Iterable[str], project_root: str | Path
) -> dict[str, MilestoneRecord]:
    """Load several artifacts, reporting *all* missing ones at once.

    Failing with the complete list matters: a figure typically depends on a dozen
    artifacts, and discovering them one exception at a time is how a partially
    wired figure ends up shipping with the rest still hardcoded.
    """
    records: dict[str, MilestoneRecord] = {}
    problems: list[str] = []
    for artifact in artifacts:
        try:
            records[artifact] = load_milestone(artifact, project_root)
        except FigureDataError as exc:
            problems.append(str(exc))
    if problems:
        raise FigureDataError(
            "could not source figure data:\n  " + "\n  ".join(problems)
        )
    return records


def metric_from_scenario_summary(
    artifact: str,
    project_root: str | Path,
    *,
    column: str,
    where: dict[str, str] | None = None,
    filename: str = "scenario_summary.csv",
) -> float:
    """Pull a single numeric cell from a summary CSV.

    ``where`` selects the row by exact column matches. Exactly one row must match:
    zero means the figure is asking for something absent, and more than one means
    the selector is ambiguous and could silently pick a different row after a
    re-run. Both raise.
    """
    path = _results_root(project_root) / artifact / filename
    if not path.is_file():
        raise FigureDataError(f"missing {path}")
    with path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise FigureDataError(f"{path} is empty")
    if column not in rows[0]:
        raise FigureDataError(
            f"{path} has no column {column!r}; available: {sorted(rows[0])[:12]}"
        )
    selected = [
        row
        for row in rows
        if all(str(row.get(key, "")) == str(value) for key, value in (where or {}).items())
    ]
    if len(selected) != 1:
        raise FigureDataError(
            f"{path}: selector {where!r} matched {len(selected)} rows; exactly one "
            "required so the figure cannot silently pick a different row later"
        )
    raw = selected[0][column]
    try:
        return float(raw)
    except (TypeError, ValueError) as exc:
        raise FigureDataError(f"{path}: {column}={raw!r} is not numeric") from exc
