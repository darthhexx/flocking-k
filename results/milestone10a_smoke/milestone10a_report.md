# M10A raw-channel adversarial-trust report

**Verdict: `M10A-TRAINING-PASS`**

Phase: `training`. Seeds: `19900`–`19904` (5 paired seeds per scenario).

Every arm is an output-layer shadow on the same frozen M9C physical trajectory. Fault identity and truth are used only after each causal decision for scoring.

## Gates

| Gate | Result |
|---|---:|
| replay | PASS |
| upstream_m9c_frozen | PASS |
| shadow_equivalence | PASS |
| frozen_motion | PASS |
| tail_event_power | PASS |
| diagnostics_exercised | PASS |
| control_noninferiority | PASS |
| control_false_alerts | PASS |
| control_calibration_and_safety | PASS |
| legitimate_mode_and_precision | PASS |
| attack_absolute_availability | PASS |
| canonical_attack_improvement | PASS |
| attack_calibration_and_safety | PASS |
| quarantine_noninterference | PASS |
| attack_detection | PASS |
| dose_response_graceful | PASS |

## Combined candidate

| Scenario | Loss | Abstain | Wrong | NEES | P95 NEES | Coverage | Strategic alert | False alert |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| stable_control | 0.286 | 0.000 | 0.000 | 1.85 | 5.29 | 0.966 | 0.000 | 0.000 |
| failure_partition | 0.360 | 0.020 | 0.000 | 1.82 | 5.13 | 0.964 | 0.000 | 0.000 |
| flapping_reconnect | 0.330 | 0.015 | 0.000 | 1.82 | 5.35 | 0.968 | 0.000 | 0.000 |
| admission_censoring_control | 0.347 | 0.025 | 0.000 | 1.80 | 5.53 | 0.959 | 0.000 | 0.000 |
| source_assignment_competition | 1.091 | 0.011 | 0.000 | 1.75 | 4.91 | 0.975 | 0.000 | 0.000 |
| genuine_target_maneuver | 0.286 | 0.000 | 0.000 | 1.89 | 5.60 | 0.958 | 0.000 | 0.000 |
| legitimate_heterogeneous_precision | 0.177 | 0.000 | 0.000 | 1.89 | 5.76 | 0.956 | 0.000 | 0.000 |
| raw_attack_mild | 0.321 | 0.011 | 0.000 | 2.16 | 6.46 | 0.938 | 0.903 | 0.000 |
| raw_attack_moderate | 0.347 | 0.016 | 0.000 | 2.26 | 6.63 | 0.935 | 0.961 | 0.000 |
| raw_attack_severe | 0.362 | 0.016 | 0.000 | 1.96 | 5.71 | 0.959 | 0.994 | 0.000 |
| raw_channel_colluding_ramp | 0.453 | 0.109 | 0.000 | 2.98 | 6.65 | 0.937 | 0.984 | 0.000 |

## Decision-loss effects versus frozen M9C

| Scenario | Improvement | 95% CI |
|---|---:|---:|
| stable_control | 0.0000 | [0.0000, 0.0000] |
| failure_partition | 0.0000 | [0.0000, 0.0000] |
| flapping_reconnect | 0.0000 | [0.0000, 0.0000] |
| admission_censoring_control | 0.0000 | [0.0000, 0.0000] |
| source_assignment_competition | 0.0000 | [0.0000, 0.0000] |
| genuine_target_maneuver | 0.0000 | [0.0000, 0.0000] |
| legitimate_heterogeneous_precision | 0.0000 | [0.0000, 0.0000] |
| raw_attack_mild | 1.6590 | [1.4313, 1.8868] |
| raw_attack_moderate | 2.9410 | [2.7457, 3.0777] |
| raw_attack_severe | 3.8718 | [3.7509, 3.9734] |
| raw_channel_colluding_ramp | 2.9744 | [2.8196, 3.0851] |

## Boundary

A GO authorizes closed-loop research integration only. The assay does not establish robustness to adaptive attacks, production security, or external validity.

