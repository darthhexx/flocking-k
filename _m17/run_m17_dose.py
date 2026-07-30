"""M17: censoring dose-response, the spine of the correctability paper.

The dose axis needs no new estimator code. The M9A.7 engineered positive control
(`admission_censoring_control`) induces censoring through aggressive rejoin
probation: `topology_rejoin_probation_steps` is 40 there against a platform default
of 4, so an agent that fails and rejoins spends most of its life in PROBATION and
its fresh operational measurements are routinely excluded from belief fusion. Longer
probation is therefore literally more censoring, on a knob that is already frozen
config rather than something invented for this run.

Dose 0.0 maps to the default (4 steps, near-nominal admission); dose 1.0 maps to the
engineered control (40 steps). The predeclared grid is
{0, 0.1, 0.2, 0.35, 0.5, 0.7, 1.0}.

Predeclared gates (see MILESTONES_correctability_program.md M17). The blindness
signature is 17.1-17.3 passing WHILE 17.4-17.7 pass -- regret climbing while the
self-consistency diagnostics stay flat. Note that 17.4 and 17.6 are equivalence
tests against a predeclared negligibility margin, not failures to reject: flatness
cannot be established by a null result.

    python3 _m17/run_m17_dose.py --phase smoke     --seed-start 31900 --seed-count 4
    python3 _m17/run_m17_dose.py --phase training  --seed-start 31000 --seed-count 300
    python3 _m17/run_m17_dose.py --phase heldout   --seed-start 32000 --seed-count 300

BLOCKER -- this runner does not yet execute. Recorded here rather than worked
around, because the workaround that suggests itself produces a wrong answer to the
gate that decides the direction.

The dose knob collides with the scenario definition. `run_admission_evidence_suite`
builds each per-scenario config as `_fit_timing(scenario.overrides,
base_config.steps)` applied over the base, and `M9A7_POSITIVE_CONTROL.overrides`
itself pins `topology_rejoin_probation_steps: 40`. So a dose set on the base config
is overwritten by the scenario, and pre-applying the overrides to the base (what
this file currently attempts) bypasses `_fit_timing` and fails validation with
"repeated partitions require a nonzero reconnect gap" -- the partition timings must
be fitted to the episode length.

The tempting workaround is to pre-fit the overrides by calling `_fit_timing`
directly here. Do not: it silently duplicates suite-internal logic, so the dose
sweep and the frozen M9A.7 artifact would no longer be built by the same code path,
and any divergence would appear as a dose effect. Gate 17.4 is the outcome that
kills the research direction, and it must not be answered by a harness that differs
from the one that produced the baseline.

The correct fix is a small, explicit addition to `run_admission_evidence_suite`: an
optional `scenario_field_overrides: dict[str, dict[str, object]]` mapping a scenario
name to fields that replace entries in its override dict *before* `_fit_timing`
runs. Roughly ten lines, applied at admission_suite.py:878, with the override
recorded in `suite_config.json` so a reader can see which dose produced an artifact.
That keeps one code path, keeps the dose visible in the provenance record, and does
not touch the frozen scenario definitions themselves.

Modifying admission_suite.py is now safe: M14.4's `verify_upstream_source` resolves
upstream drift against the pre-m14 tag, so the existing M9A.7 held-out artifact
continues to verify.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import replace
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

DOSES = (0.0, 0.1, 0.2, 0.35, 0.5, 0.7, 1.0)
PROBATION_MIN, PROBATION_MAX = 4, 40

#: Predeclared negligibility margins for the equivalence tests. A slope whose
#: upper confidence bound is below these is "flat" for the purpose of the claim.
#: Justification: NEES is nominally 1.0 and the platform's own calibration band is
#: [0.8, 1.5], a width of 0.7. A slope that could move NEES by more than 0.1 across
#: the full dose range (a seventh of the band) is not flat in any useful sense, so
#: 0.1 per unit dose is the margin. Coverage is nominally 0.95 within [0.93, 0.97],
#: a width of 0.04, so the same one-seventh reasoning gives 0.006 per unit dose.
DELTA_NEES_SLOPE = 0.10
DELTA_COVERAGE_SLOPE = 0.006


def probation_for_dose(dose: float) -> int:
    """Linear interpolation from the default to the engineered control."""
    return int(round(PROBATION_MIN + dose * (PROBATION_MAX - PROBATION_MIN)))


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

    per_dose: list[dict[str, object]] = []
    for dose in DOSES:
        probation = probation_for_dose(dose)
        overrides = dict(M9A7_POSITIVE_CONTROL.overrides)
        overrides["topology_rejoin_probation_steps"] = probation
        config = replace(ExperimentConfig(), **overrides)

        dose_output = output / f"dose_{dose:.2f}"
        decision = run_admission_evidence_suite(
            config,
            dose_output,
            seed_count=args.seed_count,
            seed_start=args.seed_start,
            bootstrap_samples=args.bootstrap_samples,
            phase="training" if args.phase != "heldout" else "heldout",
        )
        per_dose.append({
            "dose": dose,
            "probation_steps": probation,
            "verdict": decision.get("verdict"),
            "artifact": str(dose_output.relative_to(REPO)),
        })
        print(f"  dose {dose:.2f} (probation {probation:2d}) -> "
              f"{decision.get('verdict')}")

    record = {
        "milestone": "M17",
        "phase": args.phase,
        "seed_start": args.seed_start,
        "seed_count": args.seed_count,
        "dose_axis": {
            "parameter": "topology_rejoin_probation_steps",
            "minimum": PROBATION_MIN,
            "maximum": PROBATION_MAX,
            "doses": list(DOSES),
            "rationale": (
                "The M9A.7 positive control induces censoring through aggressive "
                "rejoin probation, so probation length IS the censoring intensity. "
                "Using an already-frozen config field avoids inventing a knob for "
                "this run."
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
