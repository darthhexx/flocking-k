# M10A raw-channel adversarial-trust report

**Verdict: `M10A-TRAINING-PASS`**

Phase: `training`. Seeds: `20000`–`20039` (40 paired seeds per scenario).

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
| stable_control | 0.274 | 0.001 | 0.000 | 1.73 | 5.09 | 0.968 | 0.000 | 0.000 |
| failure_partition | 0.366 | 0.024 | 0.000 | 1.67 | 4.86 | 0.974 | 0.000 | 0.000 |
| flapping_reconnect | 0.305 | 0.008 | 0.000 | 1.71 | 5.07 | 0.969 | 0.000 | 0.000 |
| admission_censoring_control | 0.335 | 0.014 | 0.000 | 1.70 | 4.99 | 0.971 | 0.000 | 0.000 |
| source_assignment_competition | 1.045 | 0.010 | 0.000 | 1.63 | 4.83 | 0.975 | 0.000 | 0.000 |
| genuine_target_maneuver | 0.277 | 0.003 | 0.000 | 1.80 | 5.35 | 0.961 | 0.000 | 0.000 |
| legitimate_heterogeneous_precision | 0.184 | 0.001 | 0.000 | 1.76 | 5.11 | 0.968 | 0.000 | 0.000 |
| raw_attack_mild | 0.317 | 0.021 | 0.000 | 2.07 | 6.52 | 0.941 | 0.908 | 0.000 |
| raw_attack_moderate | 0.341 | 0.030 | 0.000 | 2.01 | 5.83 | 0.952 | 0.968 | 0.000 |
| raw_attack_severe | 0.341 | 0.009 | 0.000 | 1.77 | 5.07 | 0.968 | 0.994 | 0.000 |
| raw_channel_colluding_ramp | 0.436 | 0.098 | 0.000 | 3.36 | 5.81 | 0.952 | 0.985 | 0.000 |

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
| raw_attack_mild | 1.6191 | [1.5502, 1.6854] |
| raw_attack_moderate | 3.0259 | [2.9894, 3.0577] |
| raw_attack_severe | 3.9426 | [3.9213, 3.9601] |
| raw_channel_colluding_ramp | 3.0607 | [3.0401, 3.0779] |

## Boundary

A GO authorizes closed-loop research integration only. The assay does not establish robustness to adaptive attacks, production security, or external validity.

