# M9A.7 split-admission and tail-safety report

**Verdict: `M9A7-TRAINING-PASS`**

Phase: `training`. Seeds: `15000`–`15059` (60 paired seeds per scenario).

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
| stable_control | 0.278 | 0.275 | 0.002 | 0.275 | 0.001 | 0.005 | 0.010 | 0.019 | 0.11 | 0.080 | 0.000 | 1.75 | 0.968 |
| failure_only | 0.326 | 0.296 | 0.022 | 0.295 | 0.003 | 0.005 | 0.019 | 0.028 | 1.10 | 0.459 | 0.000 | 1.75 | 0.969 |
| partition_only | 0.380 | 0.378 | 0.000 | 0.353 | 0.032 | 0.075 | 0.095 | 0.122 | 0.07 | 0.060 | 0.000 | 1.71 | 0.969 |
| asymmetric_partition | 0.424 | 0.422 | -0.001 | 0.382 | 0.048 | 0.094 | 0.131 | 0.131 | 0.07 | 0.057 | 0.000 | 1.73 | 0.969 |
| failure_partition | 0.429 | 0.372 | 0.030 | 0.353 | 0.024 | 0.070 | 0.071 | 0.084 | 0.85 | 0.420 | 0.000 | 1.72 | 0.970 |
| staggered_rejoin | 0.323 | 0.310 | 0.009 | 0.308 | 0.004 | 0.014 | 0.019 | 0.028 | 0.77 | 0.416 | 0.000 | 1.73 | 0.970 |
| flapping_reconnect | 0.314 | 0.312 | 0.001 | 0.302 | 0.013 | 0.028 | 0.038 | 0.042 | 0.11 | 0.077 | 0.000 | 1.71 | 0.968 |
| false_split_dropout | 0.283 | 0.280 | 0.002 | 0.278 | 0.003 | 0.010 | 0.019 | 0.023 | 0.11 | 0.074 | 0.000 | 1.74 | 0.969 |
| admission_censoring_control | 0.403 | 0.342 | 0.051 | 0.330 | 0.015 | 0.033 | 0.057 | 0.070 | 1.54 | 0.629 | 0.000 | 1.72 | 0.971 |

## Robustness challenges

| Scenario | M9A.6 | M9A.7 | Residual | Defer | Wrong | Covariance-floor rate | Quarantine delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| unmodelled_count | 0.894 | 0.903 | 0.427 | 0.501 | 0.000 | 0.000 | 0.000 |
| unmodelled_offset | 0.989 | 0.989 | 0.131 | 0.455 | 0.000 | 0.000 | 0.000 |
| raw_channel_colluding_ramp | 1.102 | 3.509 | 0.783 | 0.899 | 0.000 | 0.834 | 0.000 |

## Power and boundary

The preregistered 2% tail calculation requires 149 independent seeds for a 95% chance of observing at least one event. This run used 60 seeds, giving probability 0.7024.

A held-out GO authorizes an M9A/M9B integration experiment, not production deployment. The original M9A and M9A.6 verdicts remain immutable.
