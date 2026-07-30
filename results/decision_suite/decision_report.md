# Adaptive Investigative Momentum Decision Report

**Verdict: NO-GO**

**Research direction: PIVOT_TO_FIXED_MOMENTUM_AND_REDESIGN_ADAPTATION**

This report uses 100 held-out seeds (1000–1099), seven stress scenarios, common random numbers, and paired bootstrap 95% confidence intervals.

## Decision gates

| Gate | Result |
|---|---|
| rmse significant vs both | FAIL |
| recovery mean better vs both | FAIL |
| calibration acceptable | FAIL |
| scenario robustness | FAIL |
| communication overhead under 2 percent | PASS |
| runtime overhead under 25 percent | PASS |

## Fixed-momentum diagnostic

The adaptive verdict is separate from the broader question of whether recurrence helps. This preregistered zero-momentum control supplies that contrast.

| Gate | Result |
|---|---|
| rmse significant vs zero | PASS |
| recovery significant vs zero | PASS |
| scenario robustness vs zero | PASS |
| core scenarios calibrated | PASS |

## Overall paired effects

Positive improvement means the named candidate is better than its baseline. Overall effects first average scenarios within each seed, preserving 100 independent paired units.

| Candidate | Baseline | Metric | Baseline | Candidate | Improvement | 95% CI | Wins / losses |
|---|---|---:|---:|---:|---:|---:|---:|
| flocking_adaptive_momentum | flocking_kf_no_momentum | position_rmse | 1.2413 | 1.0221 | 0.2192 | [0.2071, 0.2314] | 100 / 0 |
| flocking_adaptive_momentum | flocking_kf_no_momentum | recovery_steps | 4.5033 | 4.8067 | -0.3033 | [-0.8500, 0.1984] | 53 / 43 |
| flocking_adaptive_momentum | flocking_kf_no_momentum | information_gain | 3.4111 | 3.6899 | 0.2788 | [0.2695, 0.2882] | 100 / 0 |
| flocking_adaptive_momentum | flocking_kf_no_momentum | coverage_calibration_error | 0.1649 | 0.1357 | 0.0292 | [0.0266, 0.0317] | 97 / 3 |
| flocking_adaptive_momentum | flocking_kf_no_momentum | runtime_seconds | 0.9091 | 0.9125 | -0.0034 | [-0.0050, -0.0017] | 30 / 70 |
| flocking_adaptive_momentum | flocking_fixed_momentum | position_rmse | 0.9980 | 1.0221 | -0.0241 | [-0.0360, -0.0116] | 30 / 70 |
| flocking_adaptive_momentum | flocking_fixed_momentum | recovery_steps | 3.4917 | 4.8067 | -1.3150 | [-1.7317, -0.8933] | 21 / 78 |
| flocking_adaptive_momentum | flocking_fixed_momentum | information_gain | 3.6918 | 3.6899 | -0.0019 | [-0.0035, -0.0003] | 46 / 54 |
| flocking_adaptive_momentum | flocking_fixed_momentum | coverage_calibration_error | 0.1391 | 0.1357 | 0.0034 | [-0.0011, 0.0081] | 52 / 48 |
| flocking_adaptive_momentum | flocking_fixed_momentum | runtime_seconds | 0.9129 | 0.9125 | 0.0004 | [-0.0017, 0.0026] | 52 / 48 |
| flocking_fixed_momentum | flocking_kf_no_momentum | position_rmse | 1.2413 | 0.9980 | 0.2433 | [0.2305, 0.2565] | 100 / 0 |
| flocking_fixed_momentum | flocking_kf_no_momentum | recovery_steps | 4.5033 | 3.4917 | 1.0117 | [0.5367, 1.4733] | 72 / 28 |
| flocking_fixed_momentum | flocking_kf_no_momentum | information_gain | 3.4111 | 3.6918 | 0.2807 | [0.2708, 0.2907] | 100 / 0 |
| flocking_fixed_momentum | flocking_kf_no_momentum | coverage_calibration_error | 0.1649 | 0.1391 | 0.0258 | [0.0214, 0.0300] | 87 / 13 |
| flocking_fixed_momentum | flocking_kf_no_momentum | runtime_seconds | 0.9091 | 0.9129 | -0.0038 | [-0.0055, -0.0020] | 35 / 65 |

## Scenario RMSE

| Scenario | Zero momentum | Fixed momentum | Adaptive momentum |
|---|---:|---:|---:|
| abrupt_change | 0.7545 | 0.6696 | 0.6697 |
| biased_agents | 2.2261 | 1.2403 | 1.3080 |
| communication_delay | 2.7948 | 2.4046 | 2.5009 |
| gradual_change | 0.7314 | 0.6616 | 0.6584 |
| mixed_dropout | 0.7620 | 0.6716 | 0.6801 |
| no_change | 0.6979 | 0.6510 | 0.6528 |
| repeated_changes | 0.7226 | 0.6876 | 0.6850 |

## Interpretation

Fixed recurrence reduced RMSE versus zero recurrence by 19.60% with a wholly positive paired confidence interval.

The current innovation-adaptive scheduler was 2.41% worse than fixed recurrence, with a wholly negative paired confidence interval. Its largest failures occurred under communication delay and persistent sensor bias.

The firm decision is therefore to retain fixed investigative momentum as the supported baseline, reject the current NIS-to-momentum rule, and redesign adaptation around delay-aware and bias-robust change detection.
