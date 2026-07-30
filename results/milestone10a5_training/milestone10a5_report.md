# M10A.5 closed-loop trust integration report

**Verdict: `M10A5-TRAINING-PASS`**

Phase: `training`. Seeds: `22000`–`22039`.

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
| stable_control | 1.012 | 0.273 | 0.924 | 0.000 | 1.71 | 0.968 | 0.000 | 0.000 | 0.000 |
| failure_partition | 1.101 | 0.374 | 0.908 | 0.000 | 1.74 | 0.968 | 0.000 | 0.000 | 0.000 |
| flapping_reconnect | 1.069 | 0.315 | 0.941 | 0.000 | 1.73 | 0.969 | 0.000 | 0.000 | 0.000 |
| admission_censoring_control | 1.094 | 0.340 | 0.942 | 0.000 | 1.71 | 0.969 | 0.000 | 0.000 | 0.000 |
| source_assignment_competition | 1.792 | 1.032 | 0.950 | 0.000 | 1.60 | 0.976 | 0.000 | 0.000 | 0.000 |
| genuine_target_maneuver | 1.203 | 0.274 | 1.161 | 0.000 | 1.78 | 0.961 | 0.000 | 0.000 | 0.000 |
| legitimate_heterogeneous_precision | 0.908 | 0.184 | 0.906 | 0.000 | 1.77 | 0.963 | 0.000 | 0.000 | 0.000 |
| raw_attack_mild | 1.064 | 0.315 | 0.936 | 0.000 | 2.09 | 0.938 | 0.904 | 0.000 | 0.304 |
| raw_attack_moderate | 1.103 | 0.344 | 0.948 | 0.000 | 2.13 | 0.941 | 0.964 | 0.000 | 0.327 |
| raw_attack_severe | 1.139 | 0.330 | 1.012 | 0.000 | 1.78 | 0.961 | 0.994 | 0.000 | 0.331 |
| raw_channel_colluding_ramp | 1.209 | 0.429 | 0.975 | 0.000 | 3.17 | 0.947 | 0.985 | 0.000 | 0.275 |
| raw_attack_then_honest_recovery | 1.190 | 0.406 | 0.980 | 0.000 | 3.14 | 0.952 | 0.590 | 0.000 | 0.163 |

## Boundary

A GO authorizes the decentralized planner milestone only. It does not establish adaptive-adversary security or production readiness.
