# Milestone 6: Robust Fusion and Multi-Flock Decision Report

**Verdict: GO**

**Research direction: ADVANCE_ROBUST_MULTIFLOCK_TO_END_TO_END_EVALUATION**

This evaluation uses 100 seeds (3000–3099), seven scenarios, common random numbers, and paired bootstrap 95% confidence intervals.

## Decision gates

| Gate | Result |
|---|---|
| overall set rmse significant vs fixed | PASS |
| bias rmse significant vs fixed | PASS |
| byzantine rmse significant vs fixed | PASS |
| multimodal set rmse significant vs fixed | PASS |
| nominal rmse noninferior within 0.02 | PASS |
| dropout rmse noninferior within 0.03 | PASS |
| delay rmse noninferior within 0.05 | PASS |
| biased outputs are calibrated | PASS |
| alternative mode survives | PASS |
| false quarantine is bounded | PASS |
| communication overhead under 2% | PASS |
| runtime overhead under 50% | PASS |

## Scenario results

| Scenario | Fixed RMSE | Robust primary RMSE | Robust set RMSE | Set improvement | Set 95% CI | Flocks | Alternative weight | Quarantined |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| abrupt_change | 0.6661 | 0.6641 | 0.6641 | 0.0020 | [-0.0045, 0.0084] | 1.00 | 0.000 | 0.00 |
| biased_agents | 1.2806 | 0.6674 | 0.6618 | 0.6188 | [0.5340, 0.7070] | 1.02 | 0.011 | 2.22 |
| byzantine_agent | 10.7300 | 0.6563 | 0.6563 | 10.0737 | [10.0535, 10.0934] | 1.00 | 0.000 | 0.99 |
| communication_delay | 2.5275 | 0.6847 | 0.6847 | 1.8427 | [1.7636, 1.9216] | 1.00 | 0.000 | 0.01 |
| mixed_dropout | 0.6808 | 0.6772 | 0.6770 | 0.0038 | [-0.0030, 0.0105] | 1.00 | 0.000 | 0.00 |
| multimodal_equal | 2.9178 | 3.8323 | 0.7225 | 2.1953 | [2.0007, 2.4003] | 1.99 | 0.491 | 0.00 |
| no_change | 0.6519 | 0.6516 | 0.6516 | 0.0003 | [-0.0068, 0.0072] | 1.00 | 0.000 | 0.00 |

## Overall paired effect

Robust multi-flock fusion changed hypothesis-set RMSE by 2.1052 versus fixed fusion, with 95% CI [2.0708, 2.1414].

## Interpretation

The M6 prototype passed every defined gate. Robust fusion may advance to end-to-end output-policy evaluation while fixed recurrence remains the motion controller.

In the symmetric multimodal scenario, the primary-flock tie is intentionally not scored as if the system knew the truth. The hypothesis-set RMSE measures whether at least one returned flock is truth-consistent. A downstream policy for choosing one primary output remains a separate milestone.
