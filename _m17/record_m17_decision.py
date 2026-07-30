"""Record the M17 training-phase decision from the evaluated gates."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from flockkalman.provenance import environment_fingerprint  # noqa: E402

SWEEP = REPO / "results/milestone17_training"


def main() -> int:
    ev = json.loads((SWEEP / "gate_evaluation.json").read_text(encoding="utf-8"))
    sweep = json.loads((SWEEP / "sweep.json").read_text(encoding="utf-8"))
    gates = ev["gates"]

    # Gates the protocol declares but this evaluation does not yet implement.
    unevaluated = {
        "17_8_posterior_predictive_blind": "PPC p-value uniformity not implemented",
        "17_9_repaired_arm_holds": "split-admission arm not run as a separate arm",
        "17_10_crn_integrity": "trace fingerprint arm-disagreement not checked here",
        "17_11_validity": "hashes/environment/power record not asserted here",
    }

    decision = {
        "verdict": "M17-TRAINING-SIGNATURE-PRESENT",
        "milestone": "M17",
        "phase": "training",
        "promotion": False,
        "research_question": (
            "As censoring intensity rises, does decision regret rise monotonically "
            "while NEES, coverage and posterior-predictive checks remain flat?"
        ),
        "headline": (
            "The blindness signature is present, and in its strong form. Across the "
            "censoring dose range decision regret rises 25% (0.3169 -> 0.3961, "
            "slope +0.0819, CI [+0.0785, +0.0855], Spearman +1.00) while mean NEES "
            "FALLS slightly (slope -0.0255, CI [-0.0416, -0.0094]) and coverage "
            "RISES slightly (slope +0.0018, CI [+0.0001, +0.0036]). Both diagnostic "
            "slopes lie entirely inside their predeclared negligibility margins, so "
            "the equivalence tests pass rather than merely failing to reject. The "
            "self-consistency diagnostics do not just miss the degradation -- they "
            "move in the reassuring direction while decisions get worse."
        ),
        "exit_condition_4": {
            "fired": False,
            "statement": (
                "Exit condition 4 -- 'gates 17.4-17.7 fail, NEES does see the "
                "censoring, the blindness claim collapses' -- has NOT fired. The two "
                "flatness gates the claim turns on both pass."
            ),
        },
        "smoke_signal_reversed": {
            "note": (
                "The 3-seed smoke run reported a NEES slope of +0.142, outside the "
                "margin, which taken at face value would have been exit condition 4. "
                "At 300 seeds the slope is -0.0255: the sign flips and the magnitude "
                "falls fivefold. The smoke estimate was noise, as its own caveat "
                "predicted, and is left in the record rather than deleted."
            ),
            "smoke_nees_slope": 0.1420,
            "training_nees_slope": ev["slopes"]["mean_nees"]["slope"],
        },
        "gates": gates,
        "gates_unevaluated": unevaluated,
        "failed_gates_analysis": {
            "17_5_nees_in_band": (
                "FAILED as predeclared, on a band this author specified badly. The "
                "declared band [0.8, 1.5] was invented for the margin justification; "
                "the platform's own recorded threshold for these suites is "
                "mean_nees_max = 6.0. Observed 1.706-1.734 is comfortably inside the "
                "platform's gate and is consistent with M9A/M9A.6's own operating "
                "range. Critically the failure is present at EVERY dose including the "
                "lowest, so it is a level offset of the scenario, not an effect of "
                "censoring, and it does not bear on flatness. The gate is left "
                "FAILED; the band is not retroactively widened."
            ),
            "17_7_coverage_in_band": (
                "FAILED at the top dose only, 0.9701 against a declared ceiling of "
                "0.97 -- a breach of 0.0001, on the conservative side (better "
                "coverage). The platform's own threshold is coverage95_min = 0.88. "
                "Same treatment: recorded as failed, not rewritten."
            ),
        },
        "scope_limitation": {
            "scenarios_dosed": 1,
            "scenario": "admission_censoring_control",
            "declared_matrix": [
                "failure_partition", "asymmetric_partition", "composite stress",
            ],
            "note": (
                "The dose override touches only the engineered positive control, so "
                "the other eleven scenarios are byte-identical across doses "
                "(max |diff| = 0.000000 over 300 seeds -- a clean negative control "
                "confirming the knob touches only what it should, but also meaning "
                "this result covers one scenario rather than the three the protocol "
                "declared). Extending the dose to the natural scenarios is required "
                "before the held-out band is opened."
            ),
        },
        "sweep": {
            "seed_start": sweep["seed_start"],
            "seed_count": sweep["seed_count"],
            "doses": ev["doses"],
            "dose_axis": sweep["dose_axis"]["parameter"],
            "per_dose_means": ev["per_dose_means"],
        },
        "statistics": ev["statistics"],
        "verdict_semantics": {
            "M17-TRAINING-SIGNATURE-PRESENT": (
                "The training band shows the predicted signature. This is NOT a "
                "promotion: the held-out band 32000-32299 is unopened, four declared "
                "gates are unevaluated, two failed, and the dose covers one scenario."
            ),
        },
        "required_before_heldout": [
            "implement gates 17.8-17.11",
            "extend the dose to the declared natural scenarios",
            "decide whether 17.5/17.7 bands are respecified (with disclosure) or "
            "dropped in favour of the platform's own thresholds",
        ],
        "environment": environment_fingerprint(),
    }
    out = SWEEP / "decision.json"
    out.write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(f"verdict: {decision['verdict']}")
    print(f"exit condition 4 fired: {decision['exit_condition_4']['fired']}")
    print(f"written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
