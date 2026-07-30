# M10B decentralized allocation report

**Verdict: `M10B-TRAINING-PASS`**

Phase: `training`. Seeds: `24000`–`24039`.

## Gates

| Gate | Result |
|---|---:|
| replay_and_upstream | PASS |
| tail_event_power | PASS |
| centralized_compatibility | PASS |
| ownership | PASS |
| bounded_messages | PASS |
| stable_noninferiority | PASS |
| natural_noninferiority | PASS |
| source_competition | PASS |
| calibration_and_safety | PASS |
| topology_noninterference | PASS |
| attack_boundary | PASS |
| honest_recovery | PASS |
| negotiation_value | PASS |
| asynchronous_path_exercised | PASS |
| runtime | PASS |

## Negotiated candidate

| Scenario | Integrated | Decision | Move | Active | Conflict | Msg/step | Age | Wrong | NEES | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stable_control | 1.018 | 0.275 | 0.930 | 0.019 | 0.000 | 6.90 | 1.00 | 0.000 | 1.75 | 0.968 |
| failure_partition | 1.101 | 0.374 | 0.909 | 0.019 | 0.000 | 3.44 | 0.99 | 0.000 | 1.73 | 0.967 |
| flapping_reconnect | 1.068 | 0.311 | 0.945 | 0.019 | 0.000 | 5.94 | 0.99 | 0.000 | 1.75 | 0.968 |
| admission_censoring_control | 1.109 | 0.345 | 0.955 | 0.019 | 0.000 | 2.59 | 0.98 | 0.000 | 1.73 | 0.970 |
| source_assignment_competition | 1.814 | 1.034 | 0.976 | 0.103 | 0.013 | 0.27 | 1.00 | 0.000 | 1.61 | 0.978 |
| genuine_target_maneuver | 1.212 | 0.276 | 1.170 | 0.000 | 0.000 | 7.86 | 1.00 | 0.000 | 1.80 | 0.964 |
| raw_channel_colluding_ramp | 1.212 | 0.437 | 0.968 | 0.084 | 0.010 | 2.21 | 1.00 | 0.000 | 3.27 | 0.948 |
| raw_attack_then_honest_recovery | 1.197 | 0.415 | 0.977 | 0.084 | 0.010 | 2.14 | 1.00 | 0.000 | 3.27 | 0.949 |

A GO authorizes external replay only; it is not a deployment verdict.
