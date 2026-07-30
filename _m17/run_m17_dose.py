"""M17: censoring dose-response, the spine of the correctability paper.

The dose axis is `agent_failure_count`, chosen by measurement rather than by
argument. Three candidate knobs were probed on the M9A.7 positive control
(`_m17/DOSE_AXIS_SELECTION.md` records the run):

    knob                                  loss moved   NEES moved
    topology_rejoin_probation_steps       0.0028       0.0035     saturates
    m9a7_excluded_secondary_mass_scale    0.0000       0.0000     no effect at all
    m9a7_raw_measurement_nis_ceiling      0.1100       0.4037     NEES sees it
    agent_failure_count                   0.0861       0.0748     selected

The first attempt -- rejoin probation -- was abandoned after the smoke sweep returned
byte-identical metrics at doses 0.50, 0.70 and 1.00. With partitions repeating every
10 steps, a probation window beyond about 22 steps already spans several partition
cycles, so an agent never leaves PROBATION and further increases change nothing. The
axis was saturated across more than half its declared range while moving decision
loss by 0.4%.

That is the reason this runner was smoke-tested before the training band. A 300-seed
sweep on that axis would have cost roughly 15 hours and returned a flat line, which
is indistinguishable from M17 exit condition 4 -- "NEES sees the censoring, the
direction is dead" -- when in fact the knob simply was not moving.

`m9a7_raw_measurement_nis_ceiling` moves decision loss slightly more, but it also
moves mean NEES by 0.40, far outside the predeclared negligibility margin of 0.10.
That is a substantive finding rather than a disqualification: censoring produced by
*tightening a gate threshold* is visible to NEES, whereas censoring produced by
*losing contributors* is not. The silent failure mode this paper is about is the
second kind, so `agent_failure_count` is the correct axis -- and the contrast between
the two is worth reporting in its own right.

DEVIATION FROM THE PREDECLARED GRID, disclosed: the protocol declared doses
{0, 0.1, 0.2, 0.35, 0.5, 0.7, 1.0}. `agent_failure_count` is an integer, so only
multiples of 1/6 are reachable over 0..6 failures. The grid is therefore
{1, 2, 3, 4, 5, 6} censored agents. Zero is not reachable: the positive control sets
failure timing, and config validation rejects `agent_failure_count = 0` with
"failure timing requires agent_failure_count > 0", so the floor is one censored
agent. Six levels rather than seven, spanning the reachable range.

Predeclared gates (see MILESTONES_correctability_program.md M17). The blindness
signature is 17.1-17.3 passing WHILE 17.4-17.7 pass -- regret climbing while the
self-consistency diagnostics stay flat. Note that 17.4 and 17.6 are equivalence
tests against a predeclared negligibility margin, not failures to reject: flatness
cannot be established by a null result.

    python3 _m17/run_m17_dose.py --phase smoke     --seed-start 31900 --seed-count 4
    python3 _m17/run_m17_dose.py --phase training  --seed-start 31000 --seed-count 300
    python3 _m17/run_m17_dose.py --phase heldout   --seed-start 32000 --seed-count 300

RESOLVED: the dose knob collided with the scenario definition, because
`run_admission_evidence_suite` builds per-scenario configs as
`_fit_timing(scenario.overrides, base.steps)` and `M9A7_POSITIVE_CONTROL` pins
`topology_rejoin_probation_steps` itself. Rather than pre-fit the overrides here --
which would mean the sweep and the frozen M9A.7 baseline were no longer built by the
same code path, so any divergence would present as a dose effect -- the suite gained
an explicit `scenario_field_overrides` parameter applied before `_fit_timing`, and
records the applied values in `suite_config.json`.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from flockkalman.admission_suite import (  # noqa: E402
    M9A7_POSITIVE_CONTROL,
    run_admission_evidence_suite,
)
from flockkalman.config import ExperimentConfig  # noqa: E402
from flockkalman.firewall import (  # noqa: E402
    DiagnosticFirewallError,
    check_diagnostic_seeds,
)
from flockkalman.provenance import environment_fingerprint  # noqa: E402

DOSES = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)
FAILURES_MIN, FAILURES_MAX = 1, 6
DOSE_FIELD = "agent_failure_count"

#: Predeclared negligibility margins for the equivalence tests. A slope whose
#: upper confidence bound is below these is "flat" for the purpose of the claim.
#: Justification: NEES is nominally 1.0 and the platform's own calibration band is
#: [0.8, 1.5], a width of 0.7. A slope that could move NEES by more than 0.1 across
#: the full dose range (a seventh of the band) is not flat in any useful sense, so
#: 0.1 per unit dose is the margin. Coverage is nominally 0.95 within [0.93, 0.97],
#: a width of 0.04, so the same one-seventh reasoning gives 0.006 per unit dose.
DELTA_NEES_SLOPE = 0.10
DELTA_COVERAGE_SLOPE = 0.006


def censored_agents_for_dose(dose: float) -> int:
    """Number of agents whose evidence is censored at this dose."""
    return int(round(FAILURES_MIN + dose * (FAILURES_MAX - FAILURES_MIN)))


def _slope_ci(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    """OLS slope with a normal-theory 95% interval. Returns (slope, lo, hi)."""
    n = x.size
    if n < 3:
        return float("nan"), float("nan"), float("nan")
    xm, ym = x.mean(), y.mean()
    sxx = float(((x - xm) ** 2).sum())
    if sxx == 0.0:
        return float("nan"), float("nan"), float("nan")
    slope = float(((x - xm) * (y - ym)).sum() / sxx)
    intercept = float(ym - slope * xm)
    residual = y - (intercept + slope * x)
    sigma2 = float((residual**2).sum()) / (n - 2)
    se = math.sqrt(sigma2 / sxx) if sigma2 > 0 else 0.0
    return slope, slope - 1.96 * se, slope + 1.96 * se


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    def rank(v: np.ndarray) -> np.ndarray:
        order = v.argsort()
        ranks = np.empty_like(order, dtype=float)
        ranks[order] = np.arange(v.size, dtype=float)
        return ranks

    rx, ry = rank(x), rank(y)
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=("smoke", "training", "heldout"),
                        required=True)
    parser.add_argument("--seed-start", type=int, required=True)
    parser.add_argument("--seed-count", type=int, required=True)
    parser.add_argument("--bootstrap-samples", type=int, default=5000)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--workers", type=int, default=None)
    parser.add_argument("--doses", type=str, default=None,
                        help="comma-separated subset of the dose grid, for "
                             "splitting a long sweep across invocations")
    args = parser.parse_args()

    output = args.output or REPO / f"results/milestone17_{args.phase}"

    # The dose sweep is not a diagnostic, but it must not silently land on another
    # milestone's held-out band. Smoke and training runs are checked; a heldout run
    # is expected to occupy its own declared band.
    if args.phase != "heldout":
        report = check_diagnostic_seeds(args.seed_start, args.seed_count, REPO)
        if not report["clear"]:
            raise DiagnosticFirewallError(
                f"M17 {args.phase} range {args.seed_start}.."
                f"{args.seed_start + args.seed_count - 1} intersects a held-out "
                f"split: {report['overlaps']}"
            )

    selected = (
        tuple(float(x) for x in args.doses.split(","))
        if args.doses else DOSES
    )
    per_dose: list[dict[str, object]] = []
    for dose in selected:
        censored = censored_agents_for_dose(dose)
        dose_output = output / f"dose_{dose:.2f}"
        decision = run_admission_evidence_suite(
            ExperimentConfig(),
            dose_output,
            scenario_field_overrides={
                M9A7_POSITIVE_CONTROL.name: {DOSE_FIELD: censored}
            },
            seed_count=args.seed_count,
            seed_start=args.seed_start,
            bootstrap_samples=args.bootstrap_samples,
            workers=args.workers,
            phase="training" if args.phase != "heldout" else "heldout",
        )
        per_dose.append({
            "dose": dose,
            "censored_agents": censored,
            "verdict": decision.get("verdict"),
            "artifact": (
                str(dose_output.relative_to(REPO))
                if dose_output.is_relative_to(REPO)
                else str(dose_output)
            ),
        })
        print(f"  dose {dose:.2f} ({censored} censored agents) -> "
              f"{decision.get('verdict')}")

    record = {
        "milestone": "M17",
        "phase": args.phase,
        "seed_start": args.seed_start,
        "seed_count": args.seed_count,
        "dose_axis": {
            "parameter": DOSE_FIELD,
            "minimum": FAILURES_MIN,
            "maximum": FAILURES_MAX,
            "doses": list(selected),
            "rationale": (
                "Selected by measurement over three candidates; see the module "
                "docstring and _m17/DOSE_AXIS_SELECTION.md. Rejoin probation "
                "saturated across half its range and was abandoned."
            ),
        },
        "negligibility_margins": {
            "nees_slope": DELTA_NEES_SLOPE,
            "coverage_slope": DELTA_COVERAGE_SLOPE,
            "note": (
                "Predeclared for the equivalence tests in gates 17.4 and 17.6. "
                "Flatness is asserted only if the slope's confidence bound falls "
                "inside these; a failure to reject is not sufficient."
            ),
        },
        "per_dose": per_dose,
        "environment": environment_fingerprint(),
        "gates_evaluated": False,
        "note": (
            "This runner materialises the dose sweep. Gate evaluation (17.1-17.11) "
            "reads the per-dose artifacts and is deliberately a separate step, so "
            "the expensive sweep is not re-run when a threshold is refined."
        ),
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "sweep.json").write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"\nwritten: {output / 'sweep.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
