"""Amendment 003 sec 6: identify what causes the repaired-arm residual asymmetry.

WHY THIS EXISTS
---------------
The four-scenario v2 sweep showed that the split-admission repair removes 90-93%
of the decision-regret slope in every scenario, but removes ~91% of the NEES
inversion on ``admission_censoring_control`` against only ~62% on the three
natural scenarios. That asymmetry is the M17 finding.

Its CAUSE is not identified by those four points. The control differs from the
naturals on at least five axes simultaneously:

    topology_rejoin_probation_steps      4 (default)      vs   40
    topology_rejoin_component_stable_steps   2 (default)  vs    4
    censoring duration                   65-75 steps      vs   30 steps
    partition structure                  none / one x 70  vs    7 x 4
    secondary_mode_end_step              90               vs  140

Four points cannot separate five confounded factors. An earlier reading of mine
attributed the split to an exogenous/endogenous gate distinction; that reading was
retracted in Amendment 003 sec 1, because ``AgentLifecycle.update`` gates
re-admission on ``nis_values <= topology_rejoin_nis_threshold`` in every scenario,
so all four are endogenous and the control in fact has the STRONGER gate.

This script runs the 2x2 that does identify a cause, over the two factors that are
knobs rather than structure, on the ``failure_only`` base with everything else held:

    cell   probation   recovery step   duration
    A          4            115           70      == failure_only, already run
    B         40            115           70
    C          4             75           30
    D         40             75           30

Read-out on the candidate-arm NEES residual fraction (candidate slope / baseline
slope):

    splits by probation (A,C high; B,D low)  -> gate selection depth is the cause
    splits by duration  (A,B high; C,D low)  -> accumulated exposure is the cause
    splits by neither                        -> cause is structural; redesign
    interaction                              -> report it, do not collapse

SEEDS
-----
Training band only (31000-31299 by default), firewall-checked by the runner. This
experiment does not touch held-out and is not a precondition for opening it; the
Amendment 003 sec 5 hypotheses are deliberately descriptive so that the held-out
run does not wait on this.

SMOKE FIRST -- THIS IS NOT OPTIONAL
-----------------------------------
``topology_rejoin_probation_steps`` was REJECTED as the M17 dose axis because it
saturated: a smoke sweep returned byte-identical metrics at three levels
(``_m17/DOSE_AXIS_SELECTION.md``). The 4 -> 40 contrast here is far wider than that
sweep covered, but if cells A and B come back byte-identical the factorial is dead
and must not consume a 300-seed run. ``--phase smoke`` runs 3 seeds x 2 doses and
asserts the cells are distinguishable before anything expensive happens.

COST
----
Each cell is a full suite run (the M9A.7 suite evaluates all 12 scenarios per dose
regardless of which are dosed), so a cell costs about what the v2 sweep cost.
Cell A is already on disk, so the full factorial is 3 new cells, roughly 4 hours at
16 workers. Use ``--cells B,C,D`` to skip A.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

BASE_SCENARIO = "failure_only"

#: cell -> (topology_rejoin_probation_steps, agent_recovery_step)
#: agent_failure_step is 45 in every cell, so recovery 115 -> 70 steps of censoring
#: and recovery 75 -> 30, matching the control's exposure while leaving the gate
#: mechanism and every other field alone.
CELLS: dict[str, tuple[int, int]] = {
    "A": (4, 115),
    "B": (40, 115),
    "C": (4, 75),
    "D": (40, 75),
}

FACTORS = {
    "A": {"probation": "low", "duration": "long"},
    "B": {"probation": "high", "duration": "long"},
    "C": {"probation": "low", "duration": "short"},
    "D": {"probation": "high", "duration": "short"},
}


def cell_overrides(cell: str) -> dict[str, dict[str, object]]:
    probation, recovery = CELLS[cell]
    return {BASE_SCENARIO: {"topology_rejoin_probation_steps": probation,
                            "agent_recovery_step": recovery}}


def run_cell(cell: str, args: argparse.Namespace) -> Path:
    output = args.output / f"cell_{cell}"
    cmd = [
        sys.executable, "-u", str(Path(__file__).parent / "run_m17_dose.py"),
        "--phase", args.phase,
        "--seed-start", str(args.seed_start),
        "--seed-count", str(args.seed_count),
        "--output", str(output),
        "--extra-overrides", json.dumps(cell_overrides(cell)),
    ]
    if args.workers:
        cmd += ["--workers", str(args.workers)]
    if args.doses:
        cmd += ["--doses", args.doses]
    if args.resume:
        cmd += ["--resume"]
    if args.bootstrap_samples:
        cmd += ["--bootstrap-samples", str(args.bootstrap_samples)]

    print("=" * 72, flush=True)
    print(f"CELL {cell}  probation={CELLS[cell][0]} recovery={CELLS[cell][1]} "
          f"({FACTORS[cell]['probation']} probation, "
          f"{FACTORS[cell]['duration']} duration)", flush=True)
    print("=" * 72, flush=True)
    subprocess.run(cmd, check=True)
    return output


def cell_metrics(output: Path) -> dict[float, dict[str, float]]:
    """Mean baseline/candidate metrics for BASE_SCENARIO at each dose.

    Read straight from run_summary.csv rather than through the evaluator, because
    the smoke check only needs to know whether two cells differ at all -- and at 3
    seeds the evaluator's bootstrap CIs would be meaningless anyway.
    """
    sweep = json.loads((output / "sweep.json").read_text(encoding="utf-8"))
    out: dict[float, dict[str, float]] = {}
    for entry in sorted(sweep["per_dose"], key=lambda e: e["dose"]):
        path = output / f"dose_{entry['dose']:.2f}" / "run_summary.csv"
        acc: dict[str, list[float]] = {}
        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["scenario"] != BASE_SCENARIO:
                    continue
                for arm in ("baseline", "candidate"):
                    for metric in ("decision_loss", "mean_nees",
                                   "coverage95_rate"):
                        col = f"{arm}_{metric}"
                        acc.setdefault(col, []).append(float(row[col]))
        out[entry["dose"]] = {k: sum(v) / len(v) for k, v in acc.items()}
    return out


def check_distinguishable(metrics: dict[str, dict]) -> tuple[bool, list[str]]:
    """Did varying the factors move anything at all?

    Compares every cell against cell A on the base scenario. Byte-identical means
    the knob did nothing -- the saturation failure that killed
    topology_rejoin_probation_steps as a dose axis. Returns (ok, notes).
    """
    notes: list[str] = []
    ok = True
    reference = metrics.get("A")
    if reference is None:
        return True, ["cell A not run in this invocation; no comparison made"]
    for cell, table in metrics.items():
        if cell == "A":
            continue
        biggest = 0.0
        for dose, row in table.items():
            for key, value in row.items():
                other = reference.get(dose, {}).get(key)
                if other is None:
                    continue
                biggest = max(biggest, abs(value - other))
        verdict = "distinct" if biggest > 0 else "IDENTICAL"
        notes.append(f"cell {cell} vs A: max |diff| = {biggest:.9f}  {verdict}")
        if biggest == 0.0:
            ok = False
    return ok, notes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=("smoke", "training"), default="smoke",
                    help="smoke runs 3 seeds x 2 doses and only checks that the "
                         "cells differ; training runs the real factorial. "
                         "'heldout' is deliberately not offered -- this is a "
                         "cause-finding experiment and Amendment 003 sec 5.3 "
                         "keeps it on the training band.")
    ap.add_argument("--cells", default="A,B,C,D",
                    help="comma-separated subset, e.g. B,C,D to reuse cell A")
    ap.add_argument("--seed-start", type=int, default=31000)
    ap.add_argument("--seed-count", type=int, default=None)
    ap.add_argument("--doses", type=str, default=None)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--bootstrap-samples", type=int, default=None)
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--output", type=Path,
                    default=REPO / "results/milestone17_factorial")
    args = ap.parse_args()

    if args.seed_count is None:
        args.seed_count = 3 if args.phase == "smoke" else 300
    if args.doses is None and args.phase == "smoke":
        args.doses = "0.0,1.0"
    if args.bootstrap_samples is None and args.phase == "smoke":
        args.bootstrap_samples = 100

    cells = [c.strip().upper() for c in args.cells.split(",") if c.strip()]
    unknown = [c for c in cells if c not in CELLS]
    if unknown:
        raise SystemExit(f"unknown cells: {unknown}; known: {sorted(CELLS)}")

    args.output.mkdir(parents=True, exist_ok=True)
    metrics: dict[str, dict] = {}
    for cell in cells:
        output = run_cell(cell, args)
        metrics[cell] = cell_metrics(output)

    ok, notes = check_distinguishable(metrics)
    print("\n" + "=" * 72)
    print(f"factorial {args.phase}: cells {', '.join(cells)} on {BASE_SCENARIO}")
    for note in notes:
        print(f"  {note}")

    record = {
        "milestone": "M17",
        "experiment": "amendment_003_section_6_factorial",
        "phase": args.phase,
        "base_scenario": BASE_SCENARIO,
        "cells": {c: {"probation_steps": CELLS[c][0],
                      "agent_recovery_step": CELLS[c][1],
                      "censoring_duration_steps": CELLS[c][1] - 45,
                      "factors": FACTORS[c]} for c in cells},
        "seed_start": args.seed_start,
        "seed_count": args.seed_count,
        "distinguishable": ok,
        "notes": notes,
    }
    out = args.output / f"factorial_{args.phase}.json"
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"\nwritten: {out}")

    if not ok:
        print("\nSTOP. At least one cell is byte-identical to cell A, so the "
              "factor it varies does nothing at these settings. This is the same "
              "saturation that disqualified topology_rejoin_probation_steps as a "
              "dose axis. Do NOT run the 300-seed factorial: it would spend four "
              "hours to produce a null that is a property of the knob, not of the "
              "system. Widen the contrast or pick a different factor first.")
        return 1

    if args.phase == "smoke":
        print("\nCells are distinguishable. The 300-seed factorial is worth "
              "running:\n"
              f"  python3 -u _m17/run_m17_factorial.py --phase training "
              f"--cells B,C,D --workers 16 --resume")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
