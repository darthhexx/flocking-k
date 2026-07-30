# M9A.7 split-admission and tail-safety report

**Verdict: `M9A7-GO`**

Phase: `heldout`. Seeds: `16000`–`16299` (300 paired seeds per scenario).

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
| stable_control | 0.277 | 0.274 | 0.003 | 0.273 | 0.001 | 0.005 | 0.005 | 0.019 | 0.12 | 0.081 | 0.000 | 1.74 | 0.968 |
| failure_only | 0.323 | 0.294 | 0.026 | 0.292 | 0.002 | 0.009 | 0.014 | 0.028 | 1.04 | 0.444 | 0.000 | 1.73 | 0.969 |
| partition_only | 0.378 | 0.375 | 0.002 | 0.351 | 0.027 | 0.071 | 0.080 | 0.117 | 0.08 | 0.062 | 0.000 | 1.72 | 0.970 |
| asymmetric_partition | 0.408 | 0.405 | 0.002 | 0.371 | 0.037 | 0.084 | 0.098 | 0.127 | 0.07 | 0.058 | 0.000 | 1.72 | 0.969 |
| failure_partition | 0.419 | 0.371 | 0.039 | 0.350 | 0.023 | 0.061 | 0.070 | 0.103 | 0.81 | 0.409 | 0.000 | 1.71 | 0.969 |
| staggered_rejoin | 0.323 | 0.310 | 0.011 | 0.307 | 0.004 | 0.014 | 0.019 | 0.037 | 0.75 | 0.413 | 0.000 | 1.73 | 0.969 |
| flapping_reconnect | 0.315 | 0.313 | 0.002 | 0.304 | 0.010 | 0.033 | 0.038 | 0.066 | 0.11 | 0.078 | 0.000 | 1.74 | 0.968 |
| false_split_dropout | 0.283 | 0.280 | 0.003 | 0.279 | 0.002 | 0.014 | 0.014 | 0.042 | 0.11 | 0.077 | 0.000 | 1.74 | 0.968 |
| admission_censoring_control | 0.405 | 0.339 | 0.062 | 0.325 | 0.015 | 0.042 | 0.052 | 0.084 | 1.56 | 0.632 | 0.000 | 1.71 | 0.969 |

## Robustness challenges

| Scenario | M9A.6 | M9A.7 | Residual | Defer | Wrong | Covariance-floor rate | Quarantine delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| unmodelled_count | 0.892 | 0.899 | 0.428 | 0.501 | 0.000 | 0.000 | 0.000 |
| unmodelled_offset | 0.987 | 0.986 | 0.132 | 0.454 | 0.000 | 0.000 | 0.000 |
| raw_channel_colluding_ramp | 1.105 | 3.502 | 0.781 | 0.897 | 0.000 | 0.834 | 0.000 |

## Power and boundary

The preregistered 2% tail calculation requires 149 independent seeds for a 95% chance of observing at least one event. This run used 300 seeds, giving probability 0.9977.

A held-out GO authorizes an M9A/M9B integration experiment, not production deployment. The original M9A and M9A.6 verdicts remain immutable.
