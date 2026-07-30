"""M17 gate evaluation, read from the dose-sweep artifacts.

Deliberately separate from the sweep runner so a threshold can be refined without
re-running hours of simulation.

Statistical treatment follows the program standard (MILESTONES section 0.3): the
unit of analysis is the seed, and every interval is a paired bootstrap over
seed-level aggregates. The design is paired by construction -- the same seed range
runs at every dose -- so each seed contributes one slope across the dose grid, and
the bootstrap resamples seeds rather than seed-dose cells. Treating the 6 dose means
as 6 independent points would ignore that pairing and badly understate precision.

Gates 17.4 and 17.6 are EQUIVALENCE tests. Flatness is asserted only when the
two-sided 95% interval for the slope lies entirely inside the predeclared
negligibility margin. A slope whose interval merely contains zero is not flat; it
is unresolved, and is reported as such.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from flockkalman.provenance import environment_fingerprint  # noqa: E402

SCENARIO = "admission_censoring_control"
DELTA_NEES_SLOPE = 0.10
DELTA_COVERAGE_SLOPE = 0.006
NEES_BAND = (0.8, 1.5)
COVERAGE_BAND = (0.93, 0.97)
REGRET_UCB_LIMIT = 0.10
BOOTSTRAP = 5000
RNG_SEED = 20260730


def load(sweep_dir: Path, scenario: str) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    """Return (doses, {metric: matrix[seed, dose]}) for one scenario."""
    sweep = json.loads((sweep_dir / "sweep.json").read_text(encoding="utf-8"))
    entries = sorted(sweep["per_dose"], key=lambda e: e["dose"])
    doses = np.array([e["dose"] for e in entries], dtype=float)

    columns = {
        "decision_loss": "candidate_decision_loss",
        "mean_nees": "candidate_mean_nees",
        "p95_nees": "candidate_p95_nees",
        "coverage95": "candidate_coverage95_rate",
        "baseline_loss": "baseline_decision_loss",
        "baseline_nees": "baseline_mean_nees",
    }
    per_dose: list[dict[int, dict[str, float]]] = []
    for entry in entries:
        path = sweep_dir / f"dose_{entry['dose']:.2f}" / "run_summary.csv"
        table: dict[int, dict[str, float]] = {}
        with path.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                if row["scenario"] != scenario:
                    continue
                table[int(row["seed"])] = {
                    key: float(row[col]) for key, col in columns.items()
                }
        per_dose.append(table)

    seeds = sorted(set.intersection(*(set(t) for t in per_dose)))
    if len(seeds) != len(per_dose[0]):
        print(f"  note: {len(per_dose[0]) - len(seeds)} seeds absent from some dose")
    matrices = {
        key: np.array([[per_dose[d][s][key] for d in range(len(entries))]
                       for s in seeds], dtype=float)
        for key in columns
    }
    return doses, matrices, np.array(seeds)


def seed_slopes(doses: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """One OLS slope per seed across the dose grid."""
    centred = doses - doses.mean()
    sxx = float((centred**2).sum())
    return (matrix - matrix.mean(axis=1, keepdims=True)) @ centred / sxx


def bootstrap_ci(values: np.ndarray, rng: np.random.Generator,
                 samples: int = BOOTSTRAP) -> tuple[float, float, float]:
    """Percentile bootstrap over seed-level aggregates."""
    n = values.size
    draws = rng.integers(0, n, size=(samples, n))
    means = values[draws].mean(axis=1)
    return (float(values.mean()),
            float(np.percentile(means, 2.5)),
            float(np.percentile(means, 97.5)))


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    def rank(v):
        o = v.argsort(); r = np.empty_like(o, dtype=float); r[o] = np.arange(v.size)
        return r
    rx, ry = rank(x), rank(y)
    return float(np.corrcoef(rx, ry)[0, 1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", type=Path,
                    default=REPO / "results/milestone17_training")
    ap.add_argument("--scenario", default=SCENARIO)
    args = ap.parse_args()

    rng = np.random.default_rng(RNG_SEED)
    doses, m, seeds = load(args.sweep, args.scenario)
    n = seeds.size
    print(f"scenario {args.scenario} | {n} seeds x {doses.size} doses\n")

    print(f"{'dose':>5} {'loss':>9} {'meanNEES':>9} {'p95NEES':>9} {'cov95':>8}")
    for i, d in enumerate(doses):
        print(f"{d:5.2f} {m['decision_loss'][:, i].mean():9.4f} "
              f"{m['mean_nees'][:, i].mean():9.4f} "
              f"{m['p95_nees'][:, i].mean():9.4f} "
              f"{m['coverage95'][:, i].mean():8.4f}")
    print()

    results: dict[str, object] = {}
    for key, label in (("decision_loss", "decision loss"),
                       ("mean_nees", "mean NEES"),
                       ("coverage95", "coverage95")):
        slopes = seed_slopes(doses, m[key])
        mean, lo, hi = bootstrap_ci(slopes, rng)
        results[key] = {"slope": mean, "ci": [lo, hi],
                        "spearman_of_means": spearman(doses, m[key].mean(axis=0))}
        print(f"{label:14s} slope {mean:+.5f}  95% CI [{lo:+.5f}, {hi:+.5f}]  "
              f"spearman(means) {results[key]['spearman_of_means']:+.2f}")
    print()

    # --- gates ------------------------------------------------------------
    loss = results["decision_loss"]
    nees = results["mean_nees"]
    cov = results["coverage95"]

    top_loss = m["decision_loss"][:, -1]
    top_mean, _, top_hi = bootstrap_ci(top_loss, rng)

    nees_in_band = [
        bool(NEES_BAND[0] <= m["mean_nees"][:, i].mean() <= NEES_BAND[1])
        for i in range(doses.size)
    ]
    cov_in_band = [
        bool(COVERAGE_BAND[0] <= m["coverage95"][:, i].mean() <= COVERAGE_BAND[1])
        for i in range(doses.size)
    ]

    gates = {
        "17_1_regret_rises": {
            "passed": bool(results["decision_loss"]["spearman_of_means"] >= 0.80
                           and loss["ci"][0] > 0),
            "spearman": results["decision_loss"]["spearman_of_means"],
            "slope_lcb": loss["ci"][0],
        },
        "17_2_regret_slope_positive": {
            "passed": bool(loss["ci"][0] > 0),
            "slope": loss["slope"], "ci": loss["ci"],
        },
        "17_3_reaches_failure_regime": {
            "passed": bool(top_hi > REGRET_UCB_LIMIT),
            "top_dose_mean": top_mean, "top_dose_ucb": top_hi,
            "limit": REGRET_UCB_LIMIT,
        },
        "17_4_nees_flat_equivalence": {
            "passed": bool(abs(nees["ci"][0]) < DELTA_NEES_SLOPE
                           and abs(nees["ci"][1]) < DELTA_NEES_SLOPE),
            "slope": nees["slope"], "ci": nees["ci"],
            "margin": DELTA_NEES_SLOPE,
            "test": "two-sided 95% CI must lie entirely inside +/- margin",
        },
        "17_5_nees_in_band": {
            "passed": all(nees_in_band),
            "per_dose_in_band": nees_in_band, "band": list(NEES_BAND),
            "per_dose_mean": [float(m["mean_nees"][:, i].mean())
                              for i in range(doses.size)],
        },
        "17_6_coverage_flat_equivalence": {
            "passed": bool(abs(cov["ci"][0]) < DELTA_COVERAGE_SLOPE
                           and abs(cov["ci"][1]) < DELTA_COVERAGE_SLOPE),
            "slope": cov["slope"], "ci": cov["ci"],
            "margin": DELTA_COVERAGE_SLOPE,
        },
        "17_7_coverage_in_band": {
            "passed": all(cov_in_band),
            "per_dose_in_band": cov_in_band, "band": list(COVERAGE_BAND),
            "per_dose_mean": [float(m["coverage95"][:, i].mean())
                              for i in range(doses.size)],
        },
    }

    print(f"{'gate':34s} {'result':8s} detail")
    for name, g in gates.items():
        print(f"{name:34s} {'PASS' if g['passed'] else 'FAIL':8s} "
              f"{ {k: (round(v, 5) if isinstance(v, float) else v) for k, v in g.items() if k not in ('passed','test')} }"[:140])

    signature = (gates["17_1_regret_rises"]["passed"]
                 and gates["17_2_regret_slope_positive"]["passed"]
                 and gates["17_4_nees_flat_equivalence"]["passed"]
                 and gates["17_6_coverage_flat_equivalence"]["passed"])
    print()
    print(f"BLINDNESS SIGNATURE (regret rises AND diagnostics flat): "
          f"{'PRESENT' if signature else 'ABSENT'}")

    record = {
        "milestone": "M17",
        "scenario": args.scenario,
        "sweep": str(args.sweep),
        "seeds": int(n),
        "doses": doses.tolist(),
        "statistics": {
            "unit_of_analysis": "seed",
            "method": "per-seed OLS slope across doses; percentile bootstrap over "
                      "seed-level slopes",
            "bootstrap_samples": BOOTSTRAP,
            "rng_seed": RNG_SEED,
        },
        "per_dose_means": {
            k: [float(m[k][:, i].mean()) for i in range(doses.size)]
            for k in ("decision_loss", "mean_nees", "p95_nees", "coverage95")
        },
        "slopes": results,
        "gates": {k: bool(v["passed"]) for k, v in gates.items()},
        "gate_detail": gates,
        "blindness_signature_present": bool(signature),
        "environment": environment_fingerprint(),
    }
    out = args.sweep / "gate_evaluation.json"
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
