# Milestone 5: Guarded Adaptive Momentum Decision Report

**Verdict: NO-GO**

**Research direction: RETAIN_FIXED_MOMENTUM_AND_MOVE_TO_M6**

This frozen evaluation uses 10 seeds (0–9), common random numbers, the seven preregistered stress scenarios, and paired bootstrap 95% confidence intervals.

## Decision gates

| Gate | Result |
|---|---|
| rmse significant vs fixed | FAIL |
| recovery significant vs fixed | FAIL |
| calibrated under delay and bias | FAIL |
| wins at least five of seven scenarios | FAIL |
| stale messages force fixed fallback | PASS |
| persistent bias is detected | PASS |
| false change events are bounded | PASS |
| communication overhead under 2 percent | PASS |
| runtime overhead under 25 percent | PASS |

## Overall paired effects

Positive improvement means the candidate is better than its baseline.

| Candidate | Baseline | Metric | Baseline | Candidate | Improvement | 95% CI | Wins / losses |
|---|---|---:|---:|---:|---:|---:|---:|
| flocking_guarded_momentum | flocking_fixed_momentum | position_rmse | 1.0229 | 1.0193 | 0.0036 | [-0.0007, 0.0087] | 4 / 5 |
| flocking_guarded_momentum | flocking_fixed_momentum | recovery_steps | 4.1833 | 4.1833 | 0.0000 | [-0.0667, 0.1000] | 1 / 2 |
| flocking_guarded_momentum | flocking_fixed_momentum | information_gain | 3.6891 | 3.6889 | -0.0002 | [-0.0005, -0.0000] | 2 / 7 |
| flocking_guarded_momentum | flocking_fixed_momentum | coverage_calibration_error | 0.1404 | 0.1401 | 0.0003 | [-0.0017, 0.0022] | 5 / 4 |
| flocking_guarded_momentum | flocking_fixed_momentum | runtime_seconds | 0.7750 | 0.7801 | -0.0051 | [-0.0068, -0.0034] | 0 / 10 |
| flocking_guarded_momentum | flocking_adaptive_momentum | position_rmse | 1.0094 | 1.0193 | -0.0099 | [-0.0477, 0.0248] | 4 / 6 |
| flocking_guarded_momentum | flocking_adaptive_momentum | recovery_steps | 4.8333 | 4.1833 | 0.6500 | [-0.3000, 1.4842] | 7 / 2 |
| flocking_guarded_momentum | flocking_adaptive_momentum | information_gain | 3.6867 | 3.6889 | 0.0023 | [-0.0018, 0.0070] | 4 / 6 |
| flocking_guarded_momentum | flocking_adaptive_momentum | coverage_calibration_error | 0.1286 | 0.1401 | -0.0115 | [-0.0196, -0.0031] | 2 / 8 |
| flocking_guarded_momentum | flocking_adaptive_momentum | runtime_seconds | 0.7762 | 0.7801 | -0.0039 | [-0.0052, -0.0025] | 1 / 9 |
| flocking_adaptive_momentum | flocking_fixed_momentum | position_rmse | 1.0229 | 1.0094 | 0.0135 | [-0.0246, 0.0535] | 7 / 3 |
| flocking_adaptive_momentum | flocking_fixed_momentum | recovery_steps | 4.1833 | 4.8333 | -0.6500 | [-1.4333, 0.4500] | 2 / 7 |
| flocking_adaptive_momentum | flocking_fixed_momentum | information_gain | 3.6891 | 3.6867 | -0.0025 | [-0.0078, 0.0017] | 6 / 4 |
| flocking_adaptive_momentum | flocking_fixed_momentum | coverage_calibration_error | 0.1404 | 0.1286 | 0.0118 | [0.0028, 0.0212] | 8 / 2 |
| flocking_adaptive_momentum | flocking_fixed_momentum | runtime_seconds | 0.7750 | 0.7762 | -0.0012 | [-0.0033, 0.0009] | 4 / 6 |

## Scenario diagnostics

| Scenario | Fixed RMSE | Guarded RMSE | Direct-NIS RMSE | Guarded events | Fallback rate | Bias flags |
|---|---:|---:|---:|---:|---:|---:|
| abrupt_change | 0.6570 | 0.6586 | 0.6659 | 0.40 | 0.995 | 0.00 |
| biased_agents | 1.2487 | 1.2180 | 1.1935 | 0.50 | 0.994 | 2.31 |
| communication_delay | 2.6461 | 2.6461 | 2.5520 | 0.00 | 1.000 | 0.30 |
| gradual_change | 0.6437 | 0.6361 | 0.6636 | 0.10 | 0.999 | 0.00 |
| mixed_dropout | 0.6602 | 0.6625 | 0.6741 | 0.40 | 0.995 | 0.00 |
| no_change | 0.6412 | 0.6462 | 0.6558 | 0.10 | 0.999 | 0.00 |
| repeated_changes | 0.6636 | 0.6677 | 0.6612 | 0.40 | 0.995 | 0.00 |

## Interpretation

The guarded controller did not clear the promotion gates. Fixed recurrence remains the supported controller; the next engineering investment should address robust fusion and explicit bias state in M6 rather than add acceleration.
