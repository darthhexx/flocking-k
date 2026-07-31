"""M17 gate evaluation, read from the dose-sweep artifacts.

Separate from the sweep runner so a threshold can be refined without re-running
hours of simulation.

ARM ASSIGNMENT -- read this first, because an earlier version of this file got it
wrong. In the M9A.7 suite the ``candidate`` arm IS the split-admission repair
(M9A7_PROTOCOL: "The candidate is an output-only shadow ... Fresh measurements and
recursively fused beliefs use separate eligibility channels"), and ``baseline`` is
the unrepaired M9A.6 assignment posterior. The gates therefore address different
arms and cannot both be run against ``candidate``:

    17.1-17.3   BASELINE   -- does the unrepaired estimator degrade with censoring?
    17.4-17.7   BASELINE   -- are its self-consistency diagnostics blind to that?
    17.9        CANDIDATE  -- does the repair hold?

The first evaluation ran every gate against ``candidate`` without establishing which
arm that was, which silently measured the blindness signature on the *repaired*
system. Both arms are reported here.

Statistical treatment follows the program standard (MILESTONES 0.3): the unit of
analysis is the seed. The design is paired by construction -- the same seed range
runs at every dose -- so each seed contributes one OLS slope across the dose grid and
the bootstrap resamples seeds. Treating the six dose means as independent points
would badly understate precision.

Gates 17.4 and 17.6 are EQUIVALENCE tests: flatness is asserted only when the
two-sided 95% interval lies entirely inside the predeclared negligibility margin. A
slope whose interval merely contains zero is unresolved, not flat.
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
REGRET_UCB_LIMIT = 0.10
BOOTSTRAP = 5000
RNG_SEED = 20260730

# Platform's own recorded thresholds, for the level checks. See Amendment 002:
# the bands used in the first evaluation ([0.8, 1.5] NEES, [0.93, 0.97] coverage)
# were invented for the margin justification and are far tighter than anything the
# platform gates on.
PLATFORM_MEAN_NEES_MAX = 6.0
PLATFORM_COVERAGE_MIN = 0.88

METRICS = {
    "decision_loss": "{arm}_decision_loss",
    "mean_nees": "{arm}_mean_nees",
    "p95_nees": "{arm}_p95_nees",
    "coverage95": "{arm}_coverage95_rate",
}


def load(sweep_dir: Path, scenario: str, arm: str):
    sweep = json.loads((sweep_dir / "sweep.json").read_text(encoding="utf-8"))
    entries = sorted(sweep["per_dose"], key=lambda e: e["dose"])
    doses = np.array([e["dose"] for e in entries], dtype=float)
    cols = {k: v.format(arm=arm) for k, v in METRICS.items()}

    per_dose = []
    for entry in entries:
        path = sweep_dir / f"dose_{entry['dose']:.2f}" / "run_summary.csv"
        table = {}
        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                if row["scenario"] != scenario:
                    continue
                table[int(row["seed"])] = {k: float(row[c]) for k, c in cols.items()}
        per_dose.append(table)

    seeds = sorted(set.intersection(*(set(t) for t in per_dose)))
    mats = {
        k: np.array([[per_dose[i][s][k] for i in range(len(entries))] for s in seeds])
        for k in cols
    }
    return doses, mats, np.array(seeds)


def slope_ci(doses, matrix, rng):
    c = doses - doses.mean()
    sxx = float((c**2).sum())
    slopes = (matrix - matrix.mean(axis=1, keepdims=True)) @ c / sxx
    draws = rng.integers(0, slopes.size, size=(BOOTSTRAP, slopes.size))
    boot = slopes[draws].mean(axis=1)
    return (float(slopes.mean()), float(np.percentile(boot, 2.5)),
            float(np.percentile(boot, 97.5)))


def mean_ucb(values, rng):
    draws = rng.integers(0, values.size, size=(BOOTSTRAP, values.size))
    boot = values[draws].mean(axis=1)
    return float(values.mean()), float(np.percentile(boot, 97.5))


def spearman(x, y):
    def rank(v):
        o = v.argsort(); r = np.empty_like(o, dtype=float); r[o] = np.arange(v.size)
        return r
    return float(np.corrcoef(rank(x), rank(y))[0, 1])


def ppc_uniformity(mats, doses, dof: int = 4):
    """Gate 17.8: are posterior-predictive p-values blind to the censoring?

    A calibrated filter's NEES is chi-square with `dof` degrees of freedom, so
    p = P(chi2_dof > NEES) is uniform under correct calibration. If censoring were
    visible to a posterior-predictive check, the p-value distribution would drift
    with dose. Implemented with the platform's own chi-square CDF rather than scipy.
    """
    from flockkalman.gated_estimation import chi2_cdf

    out = []
    for i in range(doses.size):
        nees = mats["mean_nees"][:, i]
        p = np.array([1.0 - chi2_cdf(float(v) * dof, dof) for v in nees])
        # KS distance from uniform
        srt = np.sort(p)
        n = srt.size
        d = float(np.max(np.abs(srt - (np.arange(1, n + 1) - 0.5) / n)))
        out.append({"dose": float(doses[i]), "mean_p": float(p.mean()),
                    "ks_distance_from_uniform": d})
    drift = abs(out[-1]["mean_p"] - out[0]["mean_p"])
    return out, drift


def crn_and_validity(sweep_dir: Path) -> tuple[dict, dict]:
    """Gates 17.10 and 17.11.

    17.10 CRN integrity. Every arm within a dose must observe the same exogenous
    trace, so `trace_fingerprint` must be constant across arms for a given
    (scenario, seed). The M9A.7 suite emits one row per (scenario, seed) with both
    arms' metrics on it, so arm-disagreement is structurally impossible *within* a
    row; what can still be checked, and is the thing that actually matters for a
    dose sweep, is that the un-dosed scenarios carry an identical fingerprint at
    every dose. If the dose leaked into a scenario it was not applied to, that
    fingerprint would move.

    17.11 Validity. The environment and the fingerprint algorithm must be recorded
    in every per-dose artifact, and the recorded scenario_field_overrides must match
    the dose the sweep claims to have applied.
    """
    sweep = json.loads((sweep_dir / "sweep.json").read_text(encoding="utf-8"))
    entries = sorted(sweep["per_dose"], key=lambda e: e["dose"])
    dosed = set(sweep["dose_axis"].get("dosed_scenarios")
                or [SCENARIO])

    # Fingerprints live in trace_manifest.json, not run_summary.csv: the M9A.7
    # suite writes one manifest entry per (scenario, seed) rather than a column.
    fingerprints: dict[str, set[str]] = {}
    for entry in entries:
        manifest = json.loads(
            (sweep_dir / f"dose_{entry['dose']:.2f}" / "trace_manifest.json")
            .read_text(encoding="utf-8")
        )
        for item in manifest["entries"]:
            key = f"{item['scenario']}|{item['seed']}"
            fingerprints.setdefault(key, set()).add(str(item["fingerprint"]))

    leaked = sorted({
        k.split("|")[0] for k, v in fingerprints.items()
        if len(v) > 1 and k.split("|")[0] not in dosed
    })
    moved_as_expected = sorted({
        k.split("|")[0] for k, v in fingerprints.items()
        if len(v) > 1 and k.split("|")[0] in dosed
    })
    gate_17_10 = {
        "arm": "all",
        "passed": not leaked,
        "undosed_scenarios_with_moving_fingerprints": leaked,
        "dosed_scenarios_with_moving_fingerprints": moved_as_expected,
        "note": ("An un-dosed scenario whose fingerprint moves across doses would "
                 "mean the dose leaked; a dosed scenario whose fingerprint does NOT "
                 "move would mean it never applied."),
        "dosed_scenarios_declared": sorted(dosed),
    }

    problems = []
    for entry in entries:
        cfg_path = sweep_dir / f"dose_{entry['dose']:.2f}" / "suite_config.json"
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        for field in ("python", "numpy", "fingerprint_algorithm"):
            if not cfg.get(field):
                problems.append(f"dose {entry['dose']:.2f}: missing {field}")
        applied = cfg.get("scenario_field_overrides") or {}
        for name in dosed:
            got = (applied.get(name) or {}).get("agent_failure_count")
            if got != entry.get("censored_agents"):
                problems.append(
                    f"dose {entry['dose']:.2f}: {name} recorded "
                    f"agent_failure_count={got}, sweep claims "
                    f"{entry.get('censored_agents')}")
    gate_17_11 = {
        "arm": "all", "passed": not problems, "problems": problems,
        "note": "environment, fingerprint algorithm and applied dose recorded and "
                "internally consistent in every per-dose artifact",
    }
    return gate_17_10, gate_17_11


def evaluate(sweep_dir: Path, scenario: str) -> dict:
    rng = np.random.default_rng(RNG_SEED)
    arms = {}
    for arm in ("baseline", "candidate"):
        doses, mats, seeds = load(sweep_dir, scenario, arm)
        stats = {}
        for key in ("decision_loss", "mean_nees", "coverage95"):
            s, lo, hi = slope_ci(doses, mats[key], rng)
            stats[key] = {"slope": s, "ci": [lo, hi],
                          "spearman_of_means": spearman(doses, mats[key].mean(axis=0)),
                          "level_first": float(mats[key][:, 0].mean()),
                          "level_last": float(mats[key][:, -1].mean())}
        top_mean, top_ucb = mean_ucb(mats["decision_loss"][:, -1], rng)
        stats["_top_dose_regret"] = {"mean": top_mean, "ucb": top_ucb}
        stats["_per_dose_nees"] = [float(mats["mean_nees"][:, i].mean())
                                   for i in range(doses.size)]
        stats["_per_dose_cov"] = [float(mats["coverage95"][:, i].mean())
                                  for i in range(doses.size)]
        stats["_per_dose_loss"] = [float(mats["decision_loss"][:, i].mean())
                                   for i in range(doses.size)]
        arms[arm] = stats
        if arm == "baseline":
            ppc, ppc_drift = ppc_uniformity(mats, doses)

    b, c = arms["baseline"], arms["candidate"]
    gates = {
        "17_1_regret_rises_baseline": {
            "arm": "baseline", "passed": bool(
                b["decision_loss"]["spearman_of_means"] >= 0.80
                and b["decision_loss"]["ci"][0] > 0),
            "spearman": b["decision_loss"]["spearman_of_means"],
            "slope_lcb": b["decision_loss"]["ci"][0]},
        "17_2_regret_slope_positive_baseline": {
            "arm": "baseline", "passed": bool(b["decision_loss"]["ci"][0] > 0),
            "slope": b["decision_loss"]["slope"], "ci": b["decision_loss"]["ci"]},
        "17_3_reaches_failure_regime_baseline": {
            "arm": "baseline",
            "passed": bool(b["_top_dose_regret"]["ucb"] > REGRET_UCB_LIMIT),
            "top_dose_mean": b["_top_dose_regret"]["mean"],
            "top_dose_ucb": b["_top_dose_regret"]["ucb"], "limit": REGRET_UCB_LIMIT},
        "17_4_nees_flat_equivalence_baseline": {
            "arm": "baseline", "passed": bool(
                abs(b["mean_nees"]["ci"][0]) < DELTA_NEES_SLOPE
                and abs(b["mean_nees"]["ci"][1]) < DELTA_NEES_SLOPE),
            "slope": b["mean_nees"]["slope"], "ci": b["mean_nees"]["ci"],
            "margin": DELTA_NEES_SLOPE},
        "17_5_nees_within_platform_threshold_baseline": {
            "arm": "baseline",
            "passed": all(v <= PLATFORM_MEAN_NEES_MAX for v in b["_per_dose_nees"]),
            "per_dose": b["_per_dose_nees"], "threshold": PLATFORM_MEAN_NEES_MAX,
            "note": "respecified per Amendment 002 against the platform's own "
                    "mean_nees_max; the original [0.8, 1.5] band was invented"},
        "17_6_coverage_flat_equivalence_baseline": {
            "arm": "baseline", "passed": bool(
                abs(b["coverage95"]["ci"][0]) < DELTA_COVERAGE_SLOPE
                and abs(b["coverage95"]["ci"][1]) < DELTA_COVERAGE_SLOPE),
            "slope": b["coverage95"]["slope"], "ci": b["coverage95"]["ci"],
            "margin": DELTA_COVERAGE_SLOPE},
        "17_7_coverage_within_platform_threshold_baseline": {
            "arm": "baseline",
            "passed": all(v >= PLATFORM_COVERAGE_MIN for v in b["_per_dose_cov"]),
            "per_dose": b["_per_dose_cov"], "threshold": PLATFORM_COVERAGE_MIN,
            "note": "respecified per Amendment 002 against coverage95_min"},
        "17_8_posterior_predictive_blind_baseline": {
            "arm": "baseline", "passed": bool(ppc_drift < 0.05),
            "mean_p_drift_across_doses": ppc_drift, "limit": 0.05,
            "per_dose": ppc},
        "17_9_repair_reduces_degradation": {
            "arm": "candidate vs baseline",
            "passed": bool(c["decision_loss"]["slope"] < 0.5 * b["decision_loss"]["slope"]),
            "baseline_slope": b["decision_loss"]["slope"],
            "candidate_slope": c["decision_loss"]["slope"],
            "reduction_factor": (b["decision_loss"]["slope"]
                                 / c["decision_loss"]["slope"]),
            "note": "respecified per Amendment 002. The original form -- repaired "
                    "regret UCB <= 0.10 at every dose -- used M9A.7's limit for the "
                    "NATURAL scenarios, but this is the engineered positive control "
                    "where even the lowest dose sits at 0.317. The limit was "
                    "unreachable by construction and tested nothing."},
    }
    gates["17_10_crn_integrity"], gates["17_11_validity"] = crn_and_validity(sweep_dir)
    return {"arms": arms, "gates": gates, "doses": load(sweep_dir, scenario,
                                                        "baseline")[0].tolist()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", type=Path,
                    default=REPO / "results/milestone17_training")
    ap.add_argument("--scenario", default=SCENARIO)
    args = ap.parse_args()

    ev = evaluate(args.sweep, args.scenario)
    doses = ev["doses"]
    print(f"scenario {args.scenario}\n")
    for arm in ("baseline", "candidate"):
        a = ev["arms"][arm]
        tag = "UNREPAIRED (M9A.6)" if arm == "baseline" else "REPAIRED (M9A.7 split)"
        print(f"-- {arm}: {tag} --")
        for k in ("decision_loss", "mean_nees", "coverage95"):
            s = a[k]
            print(f"   {k:14s} {s['level_first']:.4f} -> {s['level_last']:.4f}   "
                  f"slope {s['slope']:+.5f}  CI [{s['ci'][0]:+.5f}, {s['ci'][1]:+.5f}]")
        print()

    print(f"{'gate':46s} {'arm':20s} result")
    for name, g in ev["gates"].items():
        print(f"{name:46s} {g['arm']:20s} {'PASS' if g['passed'] else 'FAIL'}")

    b = ev["arms"]["baseline"]
    signature = (ev["gates"]["17_1_regret_rises_baseline"]["passed"]
                 and ev["gates"]["17_4_nees_flat_equivalence_baseline"]["passed"]
                 and ev["gates"]["17_6_coverage_flat_equivalence_baseline"]["passed"])
    print(f"\nBLINDNESS SIGNATURE on the UNREPAIRED arm: "
          f"{'PRESENT' if signature else 'ABSENT'}")

    record = {"milestone": "M17", "scenario": args.scenario,
              "sweep": str(args.sweep), "doses": doses,
              "arm_semantics": {
                  "baseline": "unrepaired M9A.6 assignment posterior",
                  "candidate": "M9A.7 split-admission repair"},
              "statistics": {"unit_of_analysis": "seed",
                             "method": "per-seed OLS slope; percentile bootstrap "
                                       "over seed-level slopes",
                             "bootstrap_samples": BOOTSTRAP, "rng_seed": RNG_SEED},
              "arms": ev["arms"],
              "gates": {k: bool(v["passed"]) for k, v in ev["gates"].items()},
              "gate_detail": ev["gates"],
              "blindness_signature_unrepaired": bool(signature),
              "environment": environment_fingerprint()}
    out = args.sweep / "gate_evaluation.json"
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"\nwritten: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
