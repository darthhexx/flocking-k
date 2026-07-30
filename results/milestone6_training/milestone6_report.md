# Milestone 6: Robust Fusion and Multi-Flock Decision Report

**Verdict: GO**

**Research direction: ADVANCE_ROBUST_MULTIFLOCK_TO_END_TO_END_EVALUATION**

This evaluation uses 30 seeds (0–29), seven scenarios, common random numbers, and paired bootstrap 95% confidence intervals.

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
| abrupt_change | 0.6789 | 0.6676 | 0.6675 | 0.0114 | [-0.0001, 0.0238] | 1.00 | 0.000 | 0.00 |
| biased_agents | 1.3144 | 0.6692 | 0.6633 | 0.6512 | [0.4786, 0.8340] | 1.03 | 0.013 | 2.23 |
| byzantine_agent | 10.7004 | 0.6749 | 0.6749 | 10.0256 | [9.9836, 10.0694] | 1.00 | 0.000 | 0.99 |
| communication_delay | 2.4865 | 0.6987 | 0.6987 | 1.7878 | [1.6620, 1.9160] | 1.00 | 0.000 | 0.01 |
| mixed_dropout | 0.6831 | 0.6720 | 0.6720 | 0.0111 | [0.0021, 0.0196] | 1.00 | 0.000 | 0.00 |
| multimodal_equal | 2.7214 | 3.4564 | 0.7305 | 1.9909 | [1.7362, 2.2391] | 2.00 | 0.492 | 0.00 |
| no_change | 0.6501 | 0.6429 | 0.6429 | 0.0073 | [-0.0038, 0.0185] | 1.00 | 0.000 | 0.00 |

## Overall paired effect

Robust multi-flock fusion changed hypothesis-set RMSE by 2.0693 versus fixed fusion, with 95% CI [2.0116, 2.1293].

## Interpretation

The M6 prototype passed every defined gate. Robust fusion may advance to end-to-end output-policy evaluation while fixed recurrence remains the motion controller.

In the symmetric multimodal scenario, the primary-flock tie is intentionally not scored as if the system knew the truth. The hypothesis-set RMSE measures whether at least one returned flock is truth-consistent. A downstream policy for choosing one primary output remains a separate milestone.
