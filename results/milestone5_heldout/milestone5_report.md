# Milestone 5: Guarded Adaptive Momentum Decision Report

**Verdict: NO-GO**

**Research direction: RETAIN_FIXED_MOMENTUM_AND_MOVE_TO_M6**

This frozen evaluation uses 100 seeds (2000–2099), common random numbers, the seven preregistered stress scenarios, and paired bootstrap 95% confidence intervals.

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
| flocking_guarded_momentum | flocking_fixed_momentum | position_rmse | 0.9966 | 0.9978 | -0.0012 | [-0.0048, 0.0021] | 48 / 47 |
| flocking_guarded_momentum | flocking_fixed_momentum | recovery_steps | 3.7300 | 3.6900 | 0.0400 | [-0.0183, 0.1200] | 21 / 14 |
| flocking_guarded_momentum | flocking_fixed_momentum | information_gain | 3.6903 | 3.6901 | -0.0002 | [-0.0003, -0.0001] | 34 / 61 |
| flocking_guarded_momentum | flocking_fixed_momentum | coverage_calibration_error | 0.1351 | 0.1357 | -0.0005 | [-0.0019, 0.0006] | 44 / 48 |
| flocking_guarded_momentum | flocking_fixed_momentum | runtime_seconds | 0.9729 | 0.9862 | -0.0133 | [-0.0156, -0.0110] | 15 / 85 |
| flocking_guarded_momentum | flocking_adaptive_momentum | position_rmse | 1.0113 | 0.9978 | 0.0136 | [0.0006, 0.0261] | 59 / 41 |
| flocking_guarded_momentum | flocking_adaptive_momentum | recovery_steps | 4.7167 | 3.6900 | 1.0267 | [0.6633, 1.3517] | 81 / 13 |
| flocking_guarded_momentum | flocking_adaptive_momentum | information_gain | 3.6880 | 3.6901 | 0.0021 | [0.0003, 0.0040] | 58 / 42 |
| flocking_guarded_momentum | flocking_adaptive_momentum | coverage_calibration_error | 0.1339 | 0.1357 | -0.0018 | [-0.0061, 0.0024] | 52 / 48 |
| flocking_guarded_momentum | flocking_adaptive_momentum | runtime_seconds | 0.9736 | 0.9862 | -0.0125 | [-0.0148, -0.0102] | 15 / 85 |
| flocking_adaptive_momentum | flocking_fixed_momentum | position_rmse | 0.9966 | 1.0113 | -0.0148 | [-0.0276, -0.0015] | 36 / 64 |
| flocking_adaptive_momentum | flocking_fixed_momentum | recovery_steps | 3.7300 | 4.7167 | -0.9867 | [-1.3183, -0.6300] | 15 / 81 |
| flocking_adaptive_momentum | flocking_fixed_momentum | information_gain | 3.6903 | 3.6880 | -0.0023 | [-0.0042, -0.0004] | 41 / 59 |
| flocking_adaptive_momentum | flocking_fixed_momentum | coverage_calibration_error | 0.1351 | 0.1339 | 0.0012 | [-0.0029, 0.0053] | 46 / 54 |
| flocking_adaptive_momentum | flocking_fixed_momentum | runtime_seconds | 0.9729 | 0.9736 | -0.0007 | [-0.0036, 0.0022] | 52 / 48 |

## Scenario diagnostics

| Scenario | Fixed RMSE | Guarded RMSE | Direct-NIS RMSE | Guarded events | Fallback rate | Bias flags |
|---|---:|---:|---:|---:|---:|---:|
| abrupt_change | 0.6683 | 0.6668 | 0.6636 | 0.59 | 0.993 | 0.00 |
| biased_agents | 1.1851 | 1.1942 | 1.2351 | 0.58 | 0.994 | 2.07 |
| communication_delay | 2.4351 | 2.4351 | 2.5075 | 0.00 | 1.000 | 0.16 |
| gradual_change | 0.6558 | 0.6568 | 0.6598 | 0.07 | 0.999 | 0.00 |
| mixed_dropout | 0.6844 | 0.6823 | 0.6750 | 0.41 | 0.995 | 0.00 |
| no_change | 0.6567 | 0.6562 | 0.6499 | 0.06 | 0.999 | 0.00 |
| repeated_changes | 0.6904 | 0.6929 | 0.6884 | 0.97 | 0.988 | 0.00 |

## Interpretation

The guarded controller did not clear the promotion gates. Fixed recurrence remains the supported controller; the next engineering investment should address robust fusion and explicit bias state in M6 rather than add acceleration.
