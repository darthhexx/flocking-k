# M10A raw-channel adversarial-trust report

**Verdict: `M10A-GO`**

Phase: `heldout`. Seeds: `21000`–`21149` (150 paired seeds per scenario).

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
| stable_control | 0.274 | 0.001 | 0.000 | 1.72 | 5.09 | 0.969 | 0.000 | 0.000 |
| failure_partition | 0.370 | 0.025 | 0.000 | 1.70 | 4.99 | 0.971 | 0.000 | 0.000 |
| flapping_reconnect | 0.313 | 0.013 | 0.000 | 1.71 | 5.07 | 0.970 | 0.000 | 0.000 |
| admission_censoring_control | 0.339 | 0.018 | 0.000 | 1.71 | 4.98 | 0.972 | 0.000 | 0.000 |
| source_assignment_competition | 1.043 | 0.009 | 0.000 | 1.60 | 4.67 | 0.976 | 0.000 | 0.000 |
| genuine_target_maneuver | 0.277 | 0.002 | 0.000 | 1.80 | 5.35 | 0.962 | 0.000 | 0.000 |
| legitimate_heterogeneous_precision | 0.188 | 0.001 | 0.000 | 1.76 | 5.19 | 0.968 | 0.000 | 0.000 |
| raw_attack_mild | 0.317 | 0.022 | 0.000 | 2.08 | 6.51 | 0.940 | 0.908 | 0.000 |
| raw_attack_moderate | 0.345 | 0.036 | 0.000 | 2.05 | 6.18 | 0.945 | 0.965 | 0.000 |
| raw_attack_severe | 0.339 | 0.009 | 0.000 | 1.75 | 5.14 | 0.967 | 0.994 | 0.000 |
| raw_channel_colluding_ramp | 0.437 | 0.103 | 0.000 | 3.36 | 5.80 | 0.951 | 0.985 | 0.000 |

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
| raw_attack_mild | 1.5906 | [1.5541, 1.6253] |
| raw_attack_moderate | 3.0109 | [2.9907, 3.0298] |
| raw_attack_severe | 3.9555 | [3.9479, 3.9627] |
| raw_channel_colluding_ramp | 3.0717 | [3.0634, 3.0795] |

## Boundary

A GO authorizes closed-loop research integration only. The assay does not establish robustness to adaptive attacks, production security, or external validity.

