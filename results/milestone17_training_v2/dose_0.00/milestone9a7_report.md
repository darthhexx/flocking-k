# M9A.7 split-admission and tail-safety report

**Verdict: `M9A7-TRAINING-PASS`**

Phase: `training`. Seeds: `31000`–`31299` (300 paired seeds per scenario).

M9A.7 is an output-only overlay on the frozen M9A trajectory. Fresh raw measurements use source-local robust trust and a covariance floor; recursively fused beliefs retain lifecycle admission. The policy never sees truth, realized future noise, or seeded identities.

## Gates

| Gate | Result |
|---|---:|
| replay | PASS |
| tail_event_power | PASS |
| positive_control_is_exercised | PASS |
| positive_control_repairs_loss | PASS |
| natural_scenario_noninferiority | PASS |
| mean_observer_regret | PASS |
| p95_observer_regret | PASS |
| per_seed_observer_regret | PASS |
| wrong_action_safety | PASS |
| calibration | PASS |
| off_model_residual_response | PASS |
| raw_channel_attack_safety | PASS |
| frozen_motion | PASS |

## Exact-model scenarios

| Scenario | M9A.6 | M9A.7 | Improvement LCB | Observer | Mean regret UCB | P95 regret | P95 UCB | Max regret | Censored | Censor rate | Wrong | NEES | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stable_control | 0.279 | 0.275 | 0.003 | 0.275 | 0.001 | 0.005 | 0.009 | 0.019 | 0.12 | 0.084 | 0.000 | 1.76 | 0.966 |
| failure_only | 0.289 | 0.284 | 0.005 | 0.283 | 0.002 | 0.009 | 0.014 | 0.023 | 0.31 | 0.250 | 0.000 | 1.75 | 0.967 |
| partition_only | 0.378 | 0.375 | 0.002 | 0.351 | 0.026 | 0.066 | 0.084 | 0.103 | 0.08 | 0.065 | 0.000 | 1.73 | 0.967 |
| asymmetric_partition | 0.412 | 0.410 | 0.001 | 0.376 | 0.037 | 0.089 | 0.098 | 0.145 | 0.07 | 0.061 | 0.000 | 1.74 | 0.967 |
| failure_partition | 0.378 | 0.373 | 0.004 | 0.351 | 0.024 | 0.070 | 0.080 | 0.112 | 0.26 | 0.228 | 0.000 | 1.73 | 0.969 |
| staggered_rejoin | 0.289 | 0.284 | 0.005 | 0.283 | 0.002 | 0.009 | 0.014 | 0.023 | 0.31 | 0.250 | 0.000 | 1.75 | 0.967 |
| flapping_reconnect | 0.317 | 0.313 | 0.003 | 0.305 | 0.010 | 0.037 | 0.042 | 0.070 | 0.12 | 0.081 | 0.000 | 1.74 | 0.967 |
| false_split_dropout | 0.285 | 0.281 | 0.003 | 0.279 | 0.003 | 0.014 | 0.019 | 0.061 | 0.11 | 0.079 | 0.000 | 1.75 | 0.967 |
| admission_censoring_control | 0.333 | 0.317 | 0.014 | 0.309 | 0.009 | 0.033 | 0.037 | 0.061 | 0.60 | 0.520 | 0.000 | 1.73 | 0.968 |

## Robustness challenges

| Scenario | M9A.6 | M9A.7 | Residual | Defer | Wrong | Covariance-floor rate | Quarantine delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| unmodelled_count | 0.893 | 0.901 | 0.427 | 0.501 | 0.000 | 0.000 | 0.000 |
| unmodelled_offset | 0.989 | 0.989 | 0.134 | 0.456 | 0.000 | 0.000 | 0.000 |
| raw_channel_colluding_ramp | 1.111 | 3.510 | 0.783 | 0.897 | 0.000 | 0.835 | 0.000 |

## Power and boundary

The preregistered 2% tail calculation requires 149 independent seeds for a 95% chance of observing at least one event. This run used 300 seeds, giving probability 0.9977.

A held-out GO authorizes an M9A/M9B integration experiment, not production deployment. The original M9A and M9A.6 verdicts remain immutable.
