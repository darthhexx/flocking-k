# M9A.7 split-admission and tail-safety report

**Verdict: `M9A7-TRAINING-FAIL`**

Phase: `training`. Seeds: `15900`–`15901` (2 paired seeds per scenario).

M9A.7 is an output-only overlay on the frozen M9A trajectory. Fresh raw measurements use source-local robust trust and a covariance floor; recursively fused beliefs retain lifecycle admission. The policy never sees truth, realized future noise, or seeded identities.

## Gates

| Gate | Result |
|---|---:|
| replay | PASS |
| tail_event_power | FAIL |
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
| stable_control | 0.272 | 0.268 | 0.000 | 0.268 | 0.000 | 0.000 | 0.000 | 0.000 | 0.12 | 0.091 | 0.000 | 1.65 | 0.984 |
| failure_only | 0.316 | 0.289 | 0.004 | 0.289 | 0.000 | 0.000 | 0.000 | 0.000 | 1.32 | 0.547 | 0.000 | 1.62 | 0.978 |
| partition_only | 0.406 | 0.405 | -0.007 | 0.380 | 0.052 | 0.049 | 0.052 | 0.052 | 0.09 | 0.075 | 0.000 | 1.79 | 0.972 |
| asymmetric_partition | 0.468 | 0.469 | -0.007 | 0.422 | 0.094 | 0.089 | 0.094 | 0.094 | 0.09 | 0.078 | 0.000 | 1.76 | 0.972 |
| failure_partition | 0.416 | 0.366 | 0.002 | 0.348 | 0.037 | 0.036 | 0.037 | 0.037 | 1.04 | 0.503 | 0.000 | 1.62 | 0.978 |
| staggered_rejoin | 0.304 | 0.299 | 0.002 | 0.299 | 0.000 | 0.000 | 0.000 | 0.000 | 0.83 | 0.419 | 0.000 | 1.61 | 0.978 |
| flapping_reconnect | 0.310 | 0.306 | 0.000 | 0.306 | 0.000 | 0.000 | 0.000 | 0.000 | 0.13 | 0.100 | 0.000 | 1.68 | 0.978 |
| false_split_dropout | 0.282 | 0.276 | 0.004 | 0.276 | 0.000 | 0.000 | 0.000 | 0.000 | 0.11 | 0.084 | 0.000 | 1.69 | 0.981 |
| admission_censoring_control | 0.397 | 0.344 | 0.034 | 0.332 | 0.023 | 0.022 | 0.023 | 0.023 | 1.48 | 0.597 | 0.000 | 1.71 | 0.975 |

## Robustness challenges

| Scenario | M9A.6 | M9A.7 | Residual | Defer | Wrong | Covariance-floor rate | Quarantine delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| unmodelled_count | 0.881 | 0.889 | 0.421 | 0.500 | 0.000 | 0.000 | 0.000 |
| unmodelled_offset | 1.007 | 1.008 | 0.124 | 0.459 | 0.000 | 0.000 | 0.000 |
| raw_channel_colluding_ramp | 1.117 | 3.527 | 0.782 | 0.906 | 0.000 | 0.838 | 0.000 |

## Power and boundary

The preregistered 2% tail calculation requires 149 independent seeds for a 95% chance of observing at least one event. This run used 2 seeds, giving probability 0.0396.

A held-out GO authorizes an M9A/M9B integration experiment, not production deployment. The original M9A and M9A.6 verdicts remain immutable.
