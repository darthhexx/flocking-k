# M8.1 Endogenous-Ambiguity Positive-Control Report

**Verdict: POSITIVE-CONTROL-PASS**

**Research direction: ALLOW_BOUNDED_M9B_VALUE_OF_INFORMATION_RESEARCH**

The assay uses 100 paired seeds (7000–7099). Two target hypotheses generate identical range distributions on the initial sensor bisector, but become distinguishable after lateral sensor motion. Mode support is a Bayesian likelihood posterior rather than agent headcount.

## Gates

| Gate | Result |
|---|---|
| passive control remains ambiguous | PASS |
| information oracle resolves safely | PASS |
| dose materially changes discriminability | PASS |
| current allocator has a positive dose | PASS |
| value of information reduces decision loss | PASS |
| trace replay verified | PASS |

## Policy and dose results

| Arm | Dose | Resolved | Wrong | Resolution | Decision loss | Movement | Discriminability |
|---|---:|---:|---:|---:|---:|---:|---:|
| passive | 0.00 | 0.000 | 0.000 | 30.00 | 6.0000 | 0.000 | 0.000 |
| round_robin_dose_0_00 | 0.00 | 0.000 | 0.000 | 30.00 | 6.0000 | 0.000 | 0.000 |
| round_robin_dose_0_10 | 0.10 | 1.000 | 0.000 | 4.73 | 0.7501 | 0.409 | 1.139 |
| round_robin_dose_0_25 | 0.25 | 1.000 | 0.000 | 2.98 | 0.4012 | 0.521 | 2.198 |
| round_robin_dose_0_50 | 0.50 | 1.000 | 0.000 | 2.18 | 0.2426 | 0.658 | 4.240 |
| round_robin_dose_1_00 | 1.00 | 1.000 | 0.000 | 1.53 | 0.1140 | 0.803 | 8.411 |
| information_oracle | 1.00 | 1.000 | 0.000 | 1.53 | 0.1140 | 0.803 | 8.411 |
| value_of_information | 1.00 | 1.000 | 0.000 | 1.53 | 0.1140 | 0.803 | 8.411 |

## Decision-loss effects versus passive

| Candidate | Improvement | 95% CI |
|---|---:|---:|
| information_oracle | 5.8860 | [5.8652, 5.9067] |
| round_robin_dose_0_00 | 0.0000 | [0.0000, 0.0000] |
| round_robin_dose_0_10 | 5.2499 | [5.2137, 5.2881] |
| round_robin_dose_0_25 | 5.5988 | [5.5785, 5.6190] |
| round_robin_dose_0_50 | 5.7574 | [5.7390, 5.7738] |
| round_robin_dose_1_00 | 5.8860 | [5.8652, 5.9067] |
| value_of_information | 5.8860 | [5.8652, 5.9067] |

This is a proof-of-identifiability assay, not evidence that the M8 production allocator works under the realism ladder. Passing permits a bounded value-of-information research track; it does not reverse the M8 dynamic-topology NO-GO.
