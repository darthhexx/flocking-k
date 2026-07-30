# M10A.5 closed-loop trust integration report

**Verdict: `M10A5-TRAINING-PASS`**

Phase: `training`. Seeds: `21990`–`21991`.

The frozen M10A trust posterior feeds the frozen M9C receding planner. A bounded trusted-sensor verification action makes the feedback path explicit.

## Gates

| Gate | Result |
|---|---:|
| replay | PASS |
| upstream_frozen | PASS |
| tail_event_power | PASS |
| baseline_compatibility | PASS |
| control_noninferiority | PASS |
| control_false_alerts | PASS |
| control_calibration_and_safety | PASS |
| legitimate_evidence_noninferiority | PASS |
| attack_absolute_availability | PASS |
| canonical_attack_improvement | PASS |
| attack_calibration_and_safety | PASS |
| attack_detection | PASS |
| quarantine_noninterference | PASS |
| attack_movement_bounded | PASS |
| honest_recovery | PASS |
| feedback_exercised | PASS |

## Candidate results

| Scenario | Integrated loss | Decision loss | Move/step | Wrong | NEES | Coverage | Alert | False alert | Verify |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stable_control | 1.069 | 0.265 | 1.005 | 0.000 | 1.63 | 0.975 | 0.000 | 0.000 | 0.000 |
| failure_partition | 1.119 | 0.332 | 0.983 | 0.000 | 1.56 | 0.969 | 0.000 | 0.000 | 0.000 |
| flapping_reconnect | 1.113 | 0.305 | 1.010 | 0.000 | 1.63 | 0.969 | 0.000 | 0.000 | 0.000 |
| admission_censoring_control | 1.128 | 0.310 | 1.023 | 0.000 | 1.61 | 0.978 | 0.000 | 0.000 | 0.000 |
| source_assignment_competition | 1.893 | 1.077 | 1.020 | 0.000 | 1.62 | 0.975 | 0.000 | 0.000 | 0.000 |
| genuine_target_maneuver | 1.367 | 0.272 | 1.369 | 0.000 | 1.76 | 0.969 | 0.000 | 0.000 | 0.000 |
| legitimate_heterogeneous_precision | 0.971 | 0.177 | 0.993 | 0.000 | 1.64 | 0.975 | 0.000 | 0.000 | 0.000 |
| raw_attack_mild | 1.097 | 0.286 | 1.013 | 0.000 | 1.88 | 0.953 | 0.916 | 0.000 | 0.306 |
| raw_attack_moderate | 1.110 | 0.291 | 1.024 | 0.000 | 1.57 | 0.978 | 0.988 | 0.000 | 0.331 |
| raw_attack_severe | 1.187 | 0.312 | 1.093 | 0.000 | 1.59 | 0.975 | 0.994 | 0.000 | 0.331 |
| raw_channel_colluding_ramp | 1.238 | 0.391 | 1.059 | 0.000 | 1.86 | 0.966 | 0.985 | 0.000 | 0.275 |
| raw_attack_then_honest_recovery | 1.226 | 0.371 | 1.068 | 0.000 | 1.84 | 0.963 | 0.590 | 0.000 | 0.163 |

## Boundary

A GO authorizes the decentralized planner milestone only. It does not establish adaptive-adversary security or production readiness.
