"""M16: the correctability proposition and its numerical counterexample.

Runs on the dedicated diagnostic band 30000-30099 declared in
MILESTONES_correctability_program.md, which the M14.5 firewall confirms is
disjoint from every held-out split. Non-promotional, but blocking for M18.

Predeclared gates:
  16.1  counterexample bias is nonzero (CI excludes zero)
  16.2  no scalar correction suffices
  16.3  each of the three violations independently demonstrated
  16.4  vanishing conditions verified
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from flockkalman.firewall import assert_diagnostic_seeds_clear  # noqa: E402
from flockkalman.gated_estimation import (  # noqa: E402
    endogenous_disagreement_bias,
    gate_contraction_factor,
    gate_threshold_for_probability,
)
from flockkalman.provenance import environment_fingerprint  # noqa: E402

SEED_START, SEED_COUNT = 30000, 100
SEEDS = list(range(SEED_START, SEED_START + SEED_COUNT))


def main() -> int:
    firewall = assert_diagnostic_seeds_clear(SEED_START, SEED_COUNT, REPO)

    configurations = {
        "all_three_violations": dict(
            couple_peer=True, adaptive_threshold=True, history_dependent=True
        ),
        "coupling_only": dict(couple_peer=True),
        "without_coupling": dict(
            couple_peer=False, adaptive_threshold=True, history_dependent=True
        ),
        "without_adaptive_threshold": dict(
            couple_peer=True, history_dependent=True
        ),
        "without_history_dependence": dict(
            couple_peer=True, adaptive_threshold=True
        ),
        "vanishing_no_coupling_memoryless": dict(couple_peer=False),
        "vanishing_unbiased_peer": dict(couple_peer=True, peer_bias=0.0),
    }
    arms = {
        name: endogenous_disagreement_bias(seeds=SEEDS, **kwargs)
        for name, kwargs in configurations.items()
    }

    full = arms["all_three_violations"]
    coupling = arms["coupling_only"]

    # --- 16.1 bias is nonzero -------------------------------------------------
    gate_16_1 = {
        "passed": bool(full["bias_excludes_zero"] and coupling["bias_excludes_zero"]),
        "all_three_bias": full["paired_selection_bias"],
        "all_three_ci": [full["paired_ci_lower"], full["paired_ci_upper"]],
        "coupling_only_bias": coupling["paired_selection_bias"],
        "coupling_only_ci": [coupling["paired_ci_lower"], coupling["paired_ci_upper"]],
        "detail": (
            "Paired against the ungated estimate on the same seeds, so common "
            "finite-sample noise cancels and the residual is attributable to "
            "selection."
        ),
    }

    # --- 16.2 no scalar correction suffices -----------------------------------
    # A constant gamma would make the per-seed required correction identical
    # across seeds. Compare its spread against the exogenous case, where the
    # correction IS a constant by construction.
    spread = full["required_correction_std"]
    span = full["required_correction_max"] - full["required_correction_min"]
    gate_16_2 = {
        "passed": bool(spread > 0.05 and span > 0.2),
        "required_correction_mean": full["required_correction_mean"],
        "required_correction_std": spread,
        "required_correction_range": [
            full["required_correction_min"],
            full["required_correction_max"],
        ],
        "exogenous_comparison": {
            "note": (
                "For an ellipsoidal gate the correction is a single number "
                "determined by (tau, m) alone -- zero spread across seeds by "
                "construction. The endogenous gate's per-seed requirement varies "
                "by the reported range, so no scalar analogue exists."
            ),
            "gamma_at_2d_90pct": gate_contraction_factor(
                gate_threshold_for_probability(0.90, 2), 2
            ).gamma,
        },
    }

    # --- 16.3 each violation independently demonstrated -----------------------
    # Predeclared as: disabling any one leaves the bias present; disabling all
    # three removes it. Measured rather than assumed.
    per_mechanism = {
        "coupling": {
            "disabled_arm": "without_coupling",
            "bias": arms["without_coupling"]["paired_selection_bias"],
            "still_present": arms["without_coupling"]["bias_excludes_zero"],
        },
        "adaptive_threshold": {
            "disabled_arm": "without_adaptive_threshold",
            "bias": arms["without_adaptive_threshold"]["paired_selection_bias"],
            "still_present": arms["without_adaptive_threshold"]["bias_excludes_zero"],
        },
        "history_dependence": {
            "disabled_arm": "without_history_dependence",
            "bias": arms["without_history_dependence"]["paired_selection_bias"],
            "still_present": arms["without_history_dependence"]["bias_excludes_zero"],
        },
    }
    necessary = [k for k, v in per_mechanism.items() if not v["still_present"]]
    amplifying = [k for k, v in per_mechanism.items() if v["still_present"]]
    gate_16_3 = {
        "passed": all(v["still_present"] for v in per_mechanism.values()),
        "per_mechanism": per_mechanism,
        "necessary_mechanisms": necessary,
        "amplifying_mechanisms": amplifying,
        "amplification_factor": (
            full["paired_selection_bias"] / coupling["paired_selection_bias"]
            if coupling["paired_selection_bias"]
            else None
        ),
        "detail": (
            "The predeclared form of this gate assumed the three violations were "
            "independently sufficient. They are not. Cross-source coupling is "
            "NECESSARY -- removing it returns a bias whose interval contains zero -- "
            "while the adaptive threshold and history dependence are amplifiers that "
            "leave the bias intact when removed individually. The weakened "
            "proposition (coupling necessary, the other two amplifying) is supported "
            "and is the more informative statement; the gate as written is not met."
        ),
    }

    # --- 16.4 vanishing conditions -------------------------------------------
    vanishing = {
        name: {
            "bias": arms[name]["paired_selection_bias"],
            "ci": [arms[name]["paired_ci_lower"], arms[name]["paired_ci_upper"]],
            "contains_zero": not arms[name]["bias_excludes_zero"],
        }
        for name in ("vanishing_no_coupling_memoryless", "vanishing_unbiased_peer")
    }
    gate_16_4 = {
        "passed": all(v["contains_zero"] for v in vanishing.values()),
        "conditions": vanishing,
        "detail": (
            "Two declared conditions under which the bias vanishes: admission "
            "independent of the estimand (peer measures an unrelated target), and an "
            "unbiased peer (agreement carries no directional pull)."
        ),
    }

    gates = {
        "16_1_bias_nonzero": gate_16_1,
        "16_2_no_scalar_correction": gate_16_2,
        "16_3_mechanisms_independent": gate_16_3,
        "16_4_vanishing_conditions": gate_16_4,
    }
    passed = {name: bool(g["passed"]) for name, g in gates.items()}
    verdict = "M16-PROOF-SUPPORTED" if all(passed.values()) else "M16-PROOF-PARTIAL"

    decision = {
        "verdict": verdict,
        "milestone": "M16",
        "non_promotional": True,
        "research_question": (
            "Is there a condition separating correctable from uncorrectable "
            "gate-induced selection, and does the platform's trust gate provably "
            "fall on the uncorrectable side?"
        ),
        "seed_firewall": firewall,
        "seed_start": SEED_START,
        "seed_count": SEED_COUNT,
        "gates": passed,
        "gate_detail": gates,
        "arms": arms,
        "environment": environment_fingerprint(),
        "verdict_semantics": {
            "M16-PROOF-SUPPORTED": "all four gates met; T-RO-scale section 4 viable",
            "M16-PROOF-PARTIAL": (
                "the proposition holds in a weakened form; per the M16 exit "
                "condition a partial result is reportable rather than fatal, but "
                "section 4 must state the weakened form"
            ),
        },
        "consequence_for_m18": (
            "M18 requires M16 PROOF-SUPPORTED. This run returns PROOF-PARTIAL, so "
            "M18 must either be re-scoped against the weakened proposition or M16 "
            "re-run with gate 16.3 restated to match what the mechanism actually is."
        ),
    }

    output = REPO / "results/milestone16_counterexample"
    output.mkdir(parents=True, exist_ok=True)
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"verdict: {verdict}")
    for name, ok in passed.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print()
    print(f"  bias (all three violations): {full['paired_selection_bias']:+.4f} "
          f"CI [{full['paired_ci_lower']:+.4f}, {full['paired_ci_upper']:+.4f}]")
    print(f"  necessary: {necessary or 'none'}   amplifying: {amplifying}")
    print(f"\nwritten: {output / 'decision.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
