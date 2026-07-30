# M9C bounded M9A.7/M9B integration report

**Verdict: `M9C-TRAINING-FAIL`**

Phase: `training`. Seeds: `18000`–`18039` (40 paired seeds per scenario).

The external estimator and risk-priced output are unchanged M9A.7. The two integration arms use the exact assignment posterior for physical motion: broad all-source investigation versus a component-local two-step VOI allocator. Unknown residual mass above the frozen ceiling disables extra probing.

## Gates

| Gate | Result |
|---|---:|
| replay | PASS |
| upstream_m9a7_frozen_go | PASS |
| tail_event_power | PASS |
| positive_control_exercised | PASS |
| aggregate_voi_utility | FAIL |
| positive_control_voi_utility | FAIL |
| movement_efficiency | PASS |
| natural_m9a7_noninferiority | PASS |
| wrong_action_safety | PASS |
| calibration | PASS |
| topology_noninterference | PASS |
| attack_nonworsening | PASS |
| attack_absolute_utility | FAIL |

## Scenario results

| Scenario | Arm | Integrated loss | Decision loss | Move/step | Active | Wrong | NEES | Coverage | Delivery | Components |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stable_control | M9A.7 | 0.423 | 0.279 | 0.961 | 0.000 | 0.000 | 1.80 | 0.963 | 1.000 | 1.00 |
| stable_control | broad | 0.422 | 0.279 | 0.950 | 0.013 | 0.000 | 1.80 | 0.965 | 1.000 | 1.01 |
| stable_control | VOI | 0.422 | 0.280 | 0.947 | 0.000 | 0.000 | 1.80 | 0.964 | 1.000 | 1.01 |
| failure_only | M9A.7 | 0.443 | 0.300 | 0.951 | 0.000 | 0.000 | 1.79 | 0.964 | 1.000 | 1.01 |
| failure_only | broad | 0.442 | 0.301 | 0.939 | 0.013 | 0.000 | 1.79 | 0.964 | 1.000 | 1.01 |
| failure_only | VOI | 0.442 | 0.301 | 0.939 | 0.000 | 0.000 | 1.79 | 0.963 | 1.000 | 1.02 |
| partition_only | M9A.7 | 0.526 | 0.381 | 0.969 | 0.000 | 0.000 | 1.76 | 0.965 | 1.000 | 2.14 |
| partition_only | broad | 0.522 | 0.379 | 0.955 | 0.013 | 0.000 | 1.77 | 0.964 | 1.000 | 2.10 |
| partition_only | VOI | 0.521 | 0.377 | 0.954 | 0.000 | 0.000 | 1.77 | 0.965 | 1.000 | 2.09 |
| asymmetric_partition | M9A.7 | 0.558 | 0.413 | 0.967 | 0.000 | 0.000 | 1.76 | 0.967 | 1.000 | 2.02 |
| asymmetric_partition | broad | 0.556 | 0.413 | 0.955 | 0.013 | 0.000 | 1.76 | 0.966 | 1.000 | 1.98 |
| asymmetric_partition | VOI | 0.557 | 0.414 | 0.953 | 0.000 | 0.000 | 1.76 | 0.965 | 1.000 | 2.00 |
| failure_partition | M9A.7 | 0.526 | 0.384 | 0.942 | 0.000 | 0.000 | 1.77 | 0.965 | 1.000 | 1.69 |
| failure_partition | broad | 0.525 | 0.385 | 0.931 | 0.013 | 0.000 | 1.76 | 0.965 | 1.000 | 1.68 |
| failure_partition | VOI | 0.522 | 0.383 | 0.930 | 0.000 | 0.000 | 1.76 | 0.965 | 1.000 | 1.68 |
| staggered_rejoin | M9A.7 | 0.454 | 0.314 | 0.933 | 0.000 | 0.000 | 1.76 | 0.964 | 1.000 | 1.01 |
| staggered_rejoin | broad | 0.455 | 0.316 | 0.922 | 0.013 | 0.000 | 1.77 | 0.967 | 1.000 | 1.02 |
| staggered_rejoin | VOI | 0.455 | 0.317 | 0.921 | 0.000 | 0.000 | 1.77 | 0.965 | 1.000 | 1.02 |
| flapping_reconnect | M9A.7 | 0.465 | 0.318 | 0.979 | 0.000 | 0.000 | 1.78 | 0.965 | 1.000 | 1.48 |
| flapping_reconnect | broad | 0.465 | 0.320 | 0.968 | 0.013 | 0.000 | 1.77 | 0.966 | 1.000 | 1.50 |
| flapping_reconnect | VOI | 0.466 | 0.320 | 0.970 | 0.000 | 0.000 | 1.78 | 0.964 | 1.000 | 1.50 |
| false_split_dropout | M9A.7 | 0.439 | 0.285 | 1.031 | 0.000 | 0.000 | 1.80 | 0.963 | 0.652 | 1.10 |
| false_split_dropout | broad | 0.439 | 0.286 | 1.016 | 0.013 | 0.000 | 1.80 | 0.966 | 0.652 | 1.10 |
| false_split_dropout | VOI | 0.438 | 0.286 | 1.012 | 0.000 | 0.000 | 1.80 | 0.965 | 0.652 | 1.11 |
| admission_censoring_control | M9A.7 | 0.491 | 0.344 | 0.977 | 0.000 | 0.000 | 1.75 | 0.965 | 1.000 | 1.60 |
| admission_censoring_control | broad | 0.492 | 0.347 | 0.970 | 0.013 | 0.000 | 1.75 | 0.965 | 1.000 | 1.61 |
| admission_censoring_control | VOI | 0.493 | 0.348 | 0.968 | 0.000 | 0.000 | 1.74 | 0.966 | 1.000 | 1.61 |
| source_assignment_competition | M9A.7 | 1.202 | 1.056 | 0.976 | 0.000 | 0.000 | 1.63 | 0.976 | 1.000 | 1.00 |
| source_assignment_competition | broad | 1.185 | 1.036 | 0.993 | 0.086 | 0.000 | 1.63 | 0.974 | 1.000 | 1.00 |
| source_assignment_competition | VOI | 1.196 | 1.051 | 0.970 | 0.002 | 0.000 | 1.62 | 0.975 | 1.000 | 1.00 |
| raw_channel_colluding_ramp | M9A.7 | 3.649 | 3.500 | 0.998 | 0.000 | 0.000 | 397.89 | 0.161 | 1.000 | 1.01 |
| raw_channel_colluding_ramp | broad | 3.654 | 3.508 | 0.978 | 0.000 | 0.000 | 402.53 | 0.160 | 1.000 | 1.00 |
| raw_channel_colluding_ramp | VOI | 3.654 | 3.508 | 0.978 | 0.000 | 0.000 | 402.53 | 0.160 | 1.000 | 1.00 |

## VOI effects versus broad investigation

| Scope | Integrated-loss improvement | 95% CI | Movement improvement | 95% CI |
|---|---:|---:|---:|---:|
| stable_control | 0.0002 | [-0.0008, 0.0012] | 0.0030 | [0.0016, 0.0045] |
| failure_only | -0.0005 | [-0.0016, 0.0006] | 0.0006 | [-0.0013, 0.0027] |
| partition_only | 0.0016 | [-0.0031, 0.0061] | 0.0013 | [-0.0009, 0.0036] |
| asymmetric_partition | -0.0006 | [-0.0035, 0.0025] | 0.0019 | [-0.0002, 0.0040] |
| failure_partition | 0.0026 | [-0.0007, 0.0062] | 0.0005 | [-0.0014, 0.0022] |
| staggered_rejoin | -0.0005 | [-0.0020, 0.0008] | 0.0012 | [-0.0002, 0.0026] |
| flapping_reconnect | -0.0009 | [-0.0032, 0.0016] | -0.0015 | [-0.0046, 0.0018] |
| false_split_dropout | 0.0003 | [-0.0026, 0.0032] | 0.0033 | [-0.0008, 0.0071] |
| admission_censoring_control | -0.0007 | [-0.0040, 0.0024] | 0.0024 | [0.0005, 0.0044] |
| source_assignment_competition | -0.0112 | [-0.0160, -0.0064] | 0.0230 | [0.0189, 0.0271] |
| raw_channel_colluding_ramp | 0.0000 | [0.0000, 0.0000] | 0.0000 | [0.0000, 0.0000] |
| __aggregate_exact__ | -0.0010 | [-0.0020, 0.0001] | 0.0036 | [0.0026, 0.0046] |

## Boundary

This protocol cannot authorize production. A GO would only retain the integrated allocator for a decentralized follow-up. Failure of an efficacy gate archives the dynamic VOI integration at this representation; failure of attack absolute utility leaves the raw-channel risk explicitly unresolved.

