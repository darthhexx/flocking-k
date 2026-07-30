# M8.1 Endogenous-Ambiguity Positive-Control Report

**Verdict: POSITIVE-CONTROL-PASS**

**Research direction: ALLOW_BOUNDED_M9B_VALUE_OF_INFORMATION_RESEARCH**

The assay uses 30 paired seeds (6000–6029). Two target hypotheses generate identical range distributions on the initial sensor bisector, but become distinguishable after lateral sensor motion. Mode support is a Bayesian likelihood posterior rather than agent headcount.

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
| round_robin_dose_0_10 | 0.10 | 1.000 | 0.000 | 4.77 | 0.7575 | 0.414 | 1.179 |
| round_robin_dose_0_25 | 0.25 | 1.000 | 0.000 | 2.90 | 0.3850 | 0.502 | 2.096 |
| round_robin_dose_0_50 | 0.50 | 1.000 | 0.000 | 2.10 | 0.2263 | 0.633 | 4.139 |
| round_robin_dose_1_00 | 1.00 | 1.000 | 0.000 | 1.37 | 0.0802 | 0.685 | 6.760 |
| information_oracle | 1.00 | 1.000 | 0.000 | 1.37 | 0.0802 | 0.685 | 6.760 |
| value_of_information | 1.00 | 1.000 | 0.000 | 1.37 | 0.0802 | 0.685 | 6.760 |

## Decision-loss effects versus passive

| Candidate | Improvement | 95% CI |
|---|---:|---:|
| information_oracle | 5.9198 | [5.8853, 5.9544] |
| round_robin_dose_0_00 | 0.0000 | [0.0000, 0.0000] |
| round_robin_dose_0_10 | 5.2425 | [5.1687, 5.3163] |
| round_robin_dose_0_25 | 5.6150 | [5.5745, 5.6555] |
| round_robin_dose_0_50 | 5.7737 | [5.7327, 5.8145] |
| round_robin_dose_1_00 | 5.9198 | [5.8853, 5.9544] |
| value_of_information | 5.9198 | [5.8851, 5.9544] |

This is a proof-of-identifiability assay, not evidence that the M8 production allocator works under the realism ladder. Passing permits a bounded value-of-information research track; it does not reverse the M8 dynamic-topology NO-GO.
