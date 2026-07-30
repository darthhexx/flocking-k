"""M15.0 gates: verify the exogenous-gate contraction result.

Gate 15.1 as predeclared reads "gamma(tau, m) matches Or's Table I to a relative
error below 1e-6". That comparison CANNOT be made here: the tabulated values were
not retrievable, only the paper's abstract and prose. Claiming the gate passed
would be fabrication, so it is recorded as PENDING and the substitute checks below
are what this run actually establishes.

What is verified instead is stronger in one respect and weaker in another. Stronger:
the closed form is checked against an independent numerical route (scipy) and
against Monte Carlo sampling of the gate event, so the implementation is confirmed
correct on its own terms. Weaker: agreement with Or's published numbers remains
unconfirmed, so a transcription or convention mismatch between his tau and ours
would not be caught.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from flockkalman.gated_estimation import (  # noqa: E402
    chi2_cdf,
    chi2_quantile,
    corrected_nis,
    gate_contraction_factor,
    gate_threshold_for_probability,
)

GATE_PROBABILITIES = (0.90, 0.95, 0.99)
DIMENSIONS = (1, 2, 3, 4, 6)


def check_cdf_against_scipy() -> bool:
    """The hand-rolled chi-square CDF must match an independent implementation."""
    try:
        from scipy.stats import chi2 as scipy_chi2
    except ImportError:
        print("[1] scipy unavailable -- CDF cross-check SKIPPED (not a pass)")
        return False

    worst = 0.0
    for dof in range(1, 13):
        for x in np.linspace(0.01, 40.0, 250):
            mine = chi2_cdf(float(x), dof)
            theirs = float(scipy_chi2.cdf(x, dof))
            worst = max(worst, abs(mine - theirs))
    ok = worst < 1e-12
    print(f"[1] chi2_cdf vs scipy, max abs error {worst:.3e}: "
          f"{'PASS' if ok else 'FAIL'}")

    worst_q = 0.0
    for dof in DIMENSIONS:
        for p in (0.5, 0.9, 0.95, 0.99, 0.999):
            mine = chi2_quantile(p, dof)
            theirs = float(scipy_chi2.ppf(p, dof))
            worst_q = max(worst_q, abs(mine - theirs))
    ok_q = worst_q < 1e-8
    print(f"[1] chi2_quantile vs scipy, max abs error {worst_q:.3e}: "
          f"{'PASS' if ok_q else 'FAIL'}")
    return ok and ok_q


def check_gamma_bounds_and_monotonicity() -> bool:
    """gamma must lie strictly in (0,1) and rise toward 1 as the gate opens."""
    ok = True
    for dof in DIMENSIONS:
        previous = -1.0
        for p in (0.50, 0.75, 0.90, 0.95, 0.99, 0.999):
            tau = gate_threshold_for_probability(p, dof)
            c = gate_contraction_factor(tau, dof)
            if not 0.0 < c.gamma < 1.0:
                print(f"    FAIL gamma out of range: m={dof} p={p} gamma={c.gamma}")
                ok = False
            if c.gamma <= previous:
                print(f"    FAIL gamma not increasing: m={dof} p={p}")
                ok = False
            previous = c.gamma
    print(f"[2] gamma in (0,1) and increasing with gate probability: "
          f"{'PASS' if ok else 'FAIL'}")
    return ok


def check_gamma_against_monte_carlo() -> bool:
    """Sample the gate event directly and compare E[||z||^2 | A] / m to gamma."""
    rng = np.random.default_rng(20260730)
    samples = 4_000_000
    ok = True
    print("[3] gamma vs Monte Carlo:")
    for dof in (1, 2, 4):
        z = rng.normal(size=(samples, dof))
        norm_sq = np.einsum("ij,ij->i", z, z)
        for p in GATE_PROBABILITIES:
            tau = gate_threshold_for_probability(p, dof)
            inside = norm_sq[norm_sq <= tau]
            empirical = float(inside.mean()) / dof
            predicted = gate_contraction_factor(tau, dof).gamma
            # Monte Carlo standard error on the conditional mean.
            sem = float(inside.std(ddof=1)) / np.sqrt(inside.size) / dof
            within = abs(empirical - predicted) < 5.0 * sem + 1e-6
            ok &= within
            print(f"    m={dof} P_G={p:.2f}  gamma={predicted:.6f}  "
                  f"MC={empirical:.6f}  |diff|={abs(empirical-predicted):.2e}  "
                  f"5*sem={5*sem:.2e}  {'ok' if within else 'FAIL'}")
    return ok


def check_correction_restores_nominal() -> bool:
    """Z / gamma must restore E[Z | A] = m -- Or's proposed correction."""
    rng = np.random.default_rng(11)
    ok = True
    print("[4] correction restores nominal NIS:")
    for dof in (2, 4):
        z = rng.normal(size=(2_000_000, dof))
        norm_sq = np.einsum("ij,ij->i", z, z)
        for p in GATE_PROBABILITIES:
            tau = gate_threshold_for_probability(p, dof)
            c = gate_contraction_factor(tau, dof)
            inside = norm_sq[norm_sq <= tau]
            raw = float(inside.mean())
            fixed = float(np.mean([corrected_nis(v, c) for v in inside[:200000]]))
            # Compare the corrected mean of the same subsample against m.
            sub = inside[:200000]
            fixed = float((sub / c.gamma).mean())
            close = abs(fixed - dof) < 0.02 * dof
            ok &= close
            print(f"    m={dof} P_G={p:.2f}  gated mean NIS={raw:.4f} "
                  f"(nominal {dof})  corrected={fixed:.4f}  "
                  f"{'ok' if close else 'FAIL'}")
    return ok


def report_table() -> None:
    """The contraction table this platform derives, for comparison with Table I."""
    print()
    print("[5] Derived contraction table (compare against Or Table I when available):")
    print(f"    {'m':>3} {'P_G':>6} {'tau':>10} {'gamma':>10} {'m*gamma':>10} "
          f"{'contraction':>12}")
    for dof in (2,):
        for p in GATE_PROBABILITIES:
            tau = gate_threshold_for_probability(p, dof)
            c = gate_contraction_factor(tau, dof)
            print(f"    {dof:>3} {p:>6.2f} {tau:>10.4f} {c.gamma:>10.6f} "
                  f"{c.expected_gated_nis:>10.6f} {c.contraction_percent:>11.2f}%")


if __name__ == "__main__":
    results = [
        check_cdf_against_scipy(),
        check_gamma_bounds_and_monotonicity(),
        check_gamma_against_monte_carlo(),
        check_correction_restores_nominal(),
    ]
    report_table()
    print()
    print("GATE 15.1 (match Or Table I to <1e-6): PENDING -- tabulated values not "
          "retrievable; not claimable from this run.")
    print(f"OVERALL (substitute checks): {'PASS' if all(results) else 'FAIL'}")
    raise SystemExit(0 if all(results) else 1)
