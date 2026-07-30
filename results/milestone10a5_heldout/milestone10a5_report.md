# M10A.5 closed-loop trust integration report

**Verdict: `M10A5-GO`**

Phase: `heldout`. Seeds: `23000`–`23149`.

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
| stable_control | 1.029 | 0.277 | 0.940 | 0.000 | 1.77 | 0.965 | 0.000 | 0.000 | 0.000 |
| failure_partition | 1.107 | 0.371 | 0.921 | 0.000 | 1.74 | 0.968 | 0.000 | 0.000 | 0.000 |
| flapping_reconnect | 1.083 | 0.315 | 0.960 | 0.000 | 1.75 | 0.967 | 0.000 | 0.000 | 0.000 |
| admission_censoring_control | 1.111 | 0.340 | 0.964 | 0.000 | 1.75 | 0.968 | 0.000 | 0.000 | 0.000 |
| source_assignment_competition | 1.819 | 1.045 | 0.967 | 0.000 | 1.63 | 0.975 | 0.000 | 0.000 | 0.000 |
| genuine_target_maneuver | 1.235 | 0.280 | 1.194 | 0.000 | 1.84 | 0.958 | 0.000 | 0.000 | 0.000 |
| legitimate_heterogeneous_precision | 0.929 | 0.189 | 0.925 | 0.000 | 1.81 | 0.964 | 0.000 | 0.000 | 0.000 |
| raw_attack_mild | 1.081 | 0.317 | 0.955 | 0.000 | 2.11 | 0.938 | 0.910 | 0.000 | 0.306 |
| raw_attack_moderate | 1.120 | 0.345 | 0.969 | 0.000 | 2.08 | 0.945 | 0.967 | 0.000 | 0.329 |
| raw_attack_severe | 1.154 | 0.330 | 1.029 | 0.000 | 1.79 | 0.965 | 0.994 | 0.000 | 0.331 |
| raw_channel_colluding_ramp | 1.228 | 0.434 | 0.993 | 0.000 | 3.58 | 0.949 | 0.985 | 0.000 | 0.275 |
| raw_attack_then_honest_recovery | 1.213 | 0.414 | 0.999 | 0.000 | 3.58 | 0.949 | 0.589 | 0.000 | 0.163 |

## Boundary

A GO authorizes the decentralized planner milestone only. It does not establish adaptive-adversary security or production readiness.
