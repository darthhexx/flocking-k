"""Selection-induced contraction under validation gating (milestones M15, M16).

Implements the exogenous-gate result this research direction builds on, and the
counterexample that bounds it.

The exogenous case (M15). Or, *The Illusion of Consistency: Selection-Induced Bias
in Gated Kalman Innovation Statistics* (arXiv:2512.18508), shows that hashing a
filter's innovations *after* validation gating measures gate-conditioned rather
than nominal quantities. For an ellipsoidal gate at threshold tau on the normalized
innovation squared, the innovation covariance contracts by a deterministic,
dimension-dependent factor gamma(tau, m) in (0, 1), and post-gate mean NIS is
m * gamma rather than m. A correction Z / gamma restores the nominal statistic.

Derivation, stated here because the correction's *availability* is the object of
study and the reader should be able to check it. Whiten the innovation:
z = S^{-1/2} nu ~ N(0, I_m), so the gate event A is ||z||^2 <= tau with
||z||^2 ~ chi2_m. Using the identity E[X 1{X <= tau}] = m F_{m+2}(tau) for
X ~ chi2_m,

    gamma(tau, m) = E[||z||^2 | A] / m = F_{m+2}(tau) / F_m(tau),

which is strictly below 1 for any finite tau because F_{m+2}(tau) < F_m(tau).

The crucial property for this research direction is not the value of gamma but
*why it exists*: the gate is a function of a statistic whose null distribution is
known in closed form, so the truncation is computable. The endogenous gate in
:func:`endogenous_disagreement_bias` breaks exactly that, and no closed-form gamma
follows.

Numpy-only by design -- the platform declares no scipy dependency, so the
regularized incomplete gamma function is implemented here rather than imported.
``_m15/check_gate_theory.py`` verifies it against scipy and against Monte Carlo.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

__all__ = [
    "GateContraction",
    "chi2_cdf",
    "chi2_quantile",
    "gate_contraction_factor",
    "gate_threshold_for_probability",
    "endogenous_disagreement_bias",
    "corrected_nis",
]


# --- regularized lower incomplete gamma, hence the chi-square CDF -----------

_MAX_ITERATIONS = 400
_EPSILON = 3.0e-16


def _gamma_p_series(a: float, x: float) -> float:
    """Regularized P(a, x) by series expansion; converges quickly for x < a + 1."""
    total = 1.0 / a
    term = total
    for n in range(1, _MAX_ITERATIONS):
        term *= x / (a + n)
        total += term
        if abs(term) < abs(total) * _EPSILON:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gamma_q_continued_fraction(a: float, x: float) -> float:
    """Regularized Q(a, x) = 1 - P(a, x) by continued fraction; for x >= a + 1."""
    tiny = 1.0e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, _MAX_ITERATIONS):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPSILON:
            break
    return h * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gamma_p(a: float, x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x < a + 1.0:
        return _gamma_p_series(a, x)
    return 1.0 - _gamma_q_continued_fraction(a, x)


def chi2_cdf(x: float, dof: int) -> float:
    """CDF of the chi-square distribution with ``dof`` degrees of freedom."""
    if dof < 1:
        raise ValueError("dof must be at least 1")
    if x <= 0.0:
        return 0.0
    return _gamma_p(dof / 2.0, x / 2.0)


def chi2_quantile(probability: float, dof: int) -> float:
    """Inverse chi-square CDF by bisection.

    Bisection rather than a Newton step: it needs no derivative, cannot overshoot,
    and the cost is irrelevant here (a handful of calls per suite). Correctness
    matters more than speed for a quantity that sets a gate threshold.
    """
    if not 0.0 < probability < 1.0:
        raise ValueError("probability must lie strictly inside (0, 1)")
    low, high = 0.0, float(dof)
    while chi2_cdf(high, dof) < probability:
        high *= 2.0
        if high > 1.0e12:
            raise RuntimeError("chi2_quantile failed to bracket the root")
    for _ in range(200):
        mid = 0.5 * (low + high)
        if chi2_cdf(mid, dof) < probability:
            low = mid
        else:
            high = mid
        if high - low < 1.0e-13 * max(1.0, high):
            break
    return 0.5 * (low + high)


# --- the exogenous gate: Or's contraction result ----------------------------

@dataclass(frozen=True)
class GateContraction:
    """The gate-conditioned innovation moments for an ellipsoidal gate."""

    dimension: int
    threshold: float
    gate_probability: float
    gamma: float

    @property
    def expected_gated_nis(self) -> float:
        """``m * gamma`` -- Or, Corollary 1."""
        return self.dimension * self.gamma

    @property
    def contraction_percent(self) -> float:
        return 100.0 * (1.0 - self.gamma)


def gate_contraction_factor(threshold: float, dimension: int) -> GateContraction:
    """Innovation-covariance contraction under an ellipsoidal validation gate.

    ``gamma = F_{m+2}(tau) / F_m(tau)``, strictly in (0, 1) for any finite
    threshold. Returns the whole record rather than a bare float because the gate
    probability is what a practitioner actually chose, and reporting gamma without
    it invites the two being confused.
    """
    if dimension < 1:
        raise ValueError("dimension must be at least 1")
    if threshold <= 0.0:
        raise ValueError("threshold must be positive")
    denominator = chi2_cdf(threshold, dimension)
    if denominator <= 0.0:
        raise ValueError("threshold admits no probability mass")
    gamma = chi2_cdf(threshold, dimension + 2) / denominator
    return GateContraction(
        dimension=dimension,
        threshold=threshold,
        gate_probability=denominator,
        gamma=gamma,
    )


def gate_threshold_for_probability(
    gate_probability: float, dimension: int
) -> float:
    """The threshold achieving a target gate acceptance probability."""
    return chi2_quantile(gate_probability, dimension)


def corrected_nis(nis: float, contraction: GateContraction) -> float:
    """Or's gate-aware normalization ``Z / gamma``, restoring ``E[Z | A] = m``."""
    return nis / contraction.gamma


# --- the endogenous gate: the counterexample (M16) --------------------------

def endogenous_disagreement_bias(
    *,
    seeds: "np.ndarray | list[int]",
    steps: int = 60,
    disagreement_threshold: float = 2.0,
    measurement_std: float = 1.0,
    peer_bias: float = 1.0,
    couple_peer: bool = True,
    adaptive_threshold: bool = False,
    history_dependent: bool = False,
) -> dict[str, float]:
    """Two agents, one shared target, admission by mutual disagreement (M16).

    The counterexample. Each agent measures the same scalar state and admits its own
    measurement only when it agrees with the peer's within a threshold. Unlike an
    innovation gate, the selection event depends on the *other* agent's measurement,
    which shares the estimand -- so the admission indicator is correlated with the
    error being estimated through a path the single-filter model has no term for.

    The three violations from the M16 protocol are individually switchable, so their
    contributions can be measured rather than asserted:

    ``couple_peer``
        Cross-source coupling. When False the peer measures an *independent* target,
        which severs the shared-estimand path while leaving the gate's shape intact.
    ``adaptive_threshold``
        Endogenous threshold. When True the effective threshold tracks the spread of
        recently admitted disagreements, so the boundary moves with what was
        admitted -- the self-reinforcing tightening Or warns about but does not
        analyse.
    ``history_dependent``
        Non-Markov selection. When True admission also requires an exponentially
        smoothed agreement statistic to stay below threshold, making the selection a
        stopping-time-like object rather than a per-step truncation.

    Reported paired against the ungated estimate on the same seeds, so common
    finite-sample seed noise cancels and the residual is attributable to selection.
    """
    seeds = np.asarray(list(seeds), dtype=np.int64)

    paired: list[float] = []
    gated: list[float] = []
    ungated: list[float] = []
    required: list[float] = []
    admit_rates: list[float] = []

    for seed in seeds:
        local = np.random.default_rng(int(seed))
        truth = 0.0
        own = truth + local.normal(0.0, measurement_std, size=steps)
        if couple_peer:
            peer = truth + peer_bias + local.normal(0.0, measurement_std, size=steps)
        else:
            # Independent target: the peer is equally noisy and equally biased, but
            # its value carries no information about `own`'s error.
            peer = (
                truth
                + peer_bias
                + local.normal(0.0, measurement_std, size=steps)
                + local.normal(0.0, 5.0 * measurement_std, size=steps)
            )

        disagreement = np.abs(own - peer)
        admit = np.zeros(steps, dtype=bool)
        threshold = disagreement_threshold
        smoothed = disagreement_threshold * 0.5
        recent: list[float] = []
        for k in range(steps):
            effective = threshold
            if adaptive_threshold and recent:
                # Tighten toward the spread of what has already been admitted.
                effective = min(
                    threshold, 1.5 * float(np.std(recent)) + 1e-6
                ) if len(recent) > 2 else threshold
            passes = disagreement[k] <= effective
            if history_dependent:
                smoothed = 0.7 * smoothed + 0.3 * disagreement[k]
                passes = passes and smoothed <= threshold
            admit[k] = passes
            if passes:
                recent.append(float(disagreement[k]))

        if not admit.any():
            continue
        gated_error = float(np.mean(own[admit] - truth))
        ungated_error = float(np.mean(own - truth))
        gated.append(gated_error)
        ungated.append(ungated_error)
        paired.append(gated_error - ungated_error)
        admit_rates.append(float(admit.mean()))

        gated_var = float(np.var(own[admit] - truth))
        full_var = float(np.var(own - truth))
        if gated_var > 0.0:
            required.append(full_var / gated_var)

    paired_arr = np.asarray(paired, dtype=float)
    required_arr = np.asarray(required, dtype=float)

    def sem(values: np.ndarray) -> float:
        if values.size < 2:
            return float("nan")
        return float(np.std(values, ddof=1) / math.sqrt(values.size))

    paired_sem = sem(paired_arr)
    paired_mean = float(np.mean(paired_arr))
    return {
        "seeds": float(paired_arr.size),
        "admit_rate_mean": float(np.mean(admit_rates)) if admit_rates else float("nan"),
        "ungated_mean_error": float(np.mean(ungated)),
        "gated_mean_error": float(np.mean(gated)),
        "paired_selection_bias": paired_mean,
        "paired_sem": paired_sem,
        "paired_ci_lower": paired_mean - 1.96 * paired_sem,
        "paired_ci_upper": paired_mean + 1.96 * paired_sem,
        "bias_excludes_zero": bool(
            (paired_mean - 1.96 * paired_sem) * (paired_mean + 1.96 * paired_sem) > 0
        ),
        "required_correction_mean": float(np.mean(required_arr)),
        "required_correction_std": float(np.std(required_arr, ddof=1)),
        "required_correction_min": float(np.min(required_arr)),
        "required_correction_max": float(np.max(required_arr)),
    }
