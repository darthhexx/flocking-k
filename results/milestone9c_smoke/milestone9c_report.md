# M9C bounded M9A.7/M9B integration report

**Verdict: `M9C-TRAINING-FAIL`**

Phase: `training`. Seeds: `17990`–`17991` (2 paired seeds per scenario).

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
| movement_efficiency | FAIL |
| natural_m9a7_noninferiority | FAIL |
| wrong_action_safety | PASS |
| calibration | PASS |
| topology_noninterference | PASS |
| attack_nonworsening | PASS |
| attack_absolute_utility | FAIL |

## Scenario results

| Scenario | Arm | Integrated loss | Decision loss | Move/step | Active | Wrong | NEES | Coverage | Delivery | Components |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stable_control | M9A.7 | 0.417 | 0.284 | 0.890 | 0.000 | 0.000 | 1.90 | 0.963 | 1.000 | 1.01 |
| stable_control | broad | 0.413 | 0.286 | 0.850 | 0.013 | 0.000 | 1.94 | 0.950 | 1.000 | 1.01 |
| stable_control | VOI | 0.416 | 0.287 | 0.861 | 0.000 | 0.000 | 1.95 | 0.956 | 1.000 | 1.02 |
| failure_only | M9A.7 | 0.434 | 0.300 | 0.895 | 0.000 | 0.000 | 1.90 | 0.950 | 1.000 | 1.01 |
| failure_only | broad | 0.433 | 0.303 | 0.869 | 0.013 | 0.000 | 1.94 | 0.950 | 1.000 | 1.01 |
| failure_only | VOI | 0.433 | 0.302 | 0.874 | 0.000 | 0.000 | 1.92 | 0.947 | 1.000 | 1.02 |
| partition_only | M9A.7 | 0.529 | 0.396 | 0.881 | 0.000 | 0.000 | 1.76 | 0.966 | 1.000 | 2.13 |
| partition_only | broad | 0.516 | 0.389 | 0.850 | 0.013 | 0.000 | 1.76 | 0.969 | 1.000 | 2.01 |
| partition_only | VOI | 0.538 | 0.410 | 0.858 | 0.000 | 0.000 | 1.84 | 0.956 | 1.000 | 2.14 |
| asymmetric_partition | M9A.7 | 0.636 | 0.502 | 0.888 | 0.000 | 0.000 | 1.81 | 0.972 | 1.000 | 2.08 |
| asymmetric_partition | broad | 0.611 | 0.482 | 0.857 | 0.013 | 0.000 | 1.84 | 0.966 | 1.000 | 2.07 |
| asymmetric_partition | VOI | 0.628 | 0.499 | 0.855 | 0.000 | 0.000 | 1.84 | 0.963 | 1.000 | 2.11 |
| failure_partition | M9A.7 | 0.549 | 0.417 | 0.879 | 0.000 | 0.000 | 1.84 | 0.966 | 1.000 | 1.64 |
| failure_partition | broad | 0.579 | 0.451 | 0.853 | 0.013 | 0.000 | 1.88 | 0.959 | 1.000 | 1.67 |
| failure_partition | VOI | 0.555 | 0.428 | 0.849 | 0.000 | 0.000 | 1.82 | 0.966 | 1.000 | 1.67 |
| staggered_rejoin | M9A.7 | 0.445 | 0.315 | 0.868 | 0.000 | 0.000 | 1.83 | 0.966 | 1.000 | 1.02 |
| staggered_rejoin | broad | 0.443 | 0.317 | 0.840 | 0.013 | 0.000 | 1.86 | 0.956 | 1.000 | 1.02 |
| staggered_rejoin | VOI | 0.442 | 0.317 | 0.830 | 0.000 | 0.000 | 1.86 | 0.956 | 1.000 | 1.02 |
| flapping_reconnect | M9A.7 | 0.462 | 0.326 | 0.905 | 0.000 | 0.000 | 1.86 | 0.959 | 1.000 | 1.47 |
| flapping_reconnect | broad | 0.455 | 0.323 | 0.874 | 0.013 | 0.000 | 1.83 | 0.963 | 1.000 | 1.49 |
| flapping_reconnect | VOI | 0.468 | 0.338 | 0.871 | 0.000 | 0.000 | 1.87 | 0.963 | 1.000 | 1.52 |
| false_split_dropout | M9A.7 | 0.425 | 0.284 | 0.940 | 0.000 | 0.000 | 1.85 | 0.956 | 0.639 | 1.07 |
| false_split_dropout | broad | 0.432 | 0.293 | 0.924 | 0.013 | 0.000 | 1.91 | 0.959 | 0.644 | 1.12 |
| false_split_dropout | VOI | 0.434 | 0.294 | 0.930 | 0.000 | 0.000 | 1.94 | 0.956 | 0.639 | 1.11 |
| admission_censoring_control | M9A.7 | 0.473 | 0.337 | 0.904 | 0.000 | 0.000 | 1.78 | 0.966 | 1.000 | 1.54 |
| admission_censoring_control | broad | 0.477 | 0.342 | 0.898 | 0.013 | 0.000 | 1.73 | 0.966 | 1.000 | 1.61 |
| admission_censoring_control | VOI | 0.482 | 0.348 | 0.893 | 0.000 | 0.000 | 1.80 | 0.963 | 1.000 | 1.59 |
| source_assignment_competition | M9A.7 | 1.165 | 1.031 | 0.890 | 0.000 | 0.000 | 1.62 | 0.981 | 1.000 | 1.00 |
| source_assignment_competition | broad | 1.141 | 1.003 | 0.916 | 0.100 | 0.000 | 1.60 | 0.981 | 1.000 | 1.00 |
| source_assignment_competition | VOI | 1.141 | 1.008 | 0.885 | 0.000 | 0.000 | 1.60 | 0.981 | 1.000 | 1.00 |
| raw_channel_colluding_ramp | M9A.7 | 3.648 | 3.512 | 0.900 | 0.000 | 0.000 | 400.93 | 0.159 | 1.000 | 1.01 |
| raw_channel_colluding_ramp | broad | 3.650 | 3.515 | 0.897 | 0.000 | 0.000 | 404.57 | 0.159 | 1.000 | 1.00 |
| raw_channel_colluding_ramp | VOI | 3.650 | 3.515 | 0.897 | 0.000 | 0.000 | 404.57 | 0.159 | 1.000 | 1.00 |

## VOI effects versus broad investigation

| Scope | Integrated-loss improvement | 95% CI | Movement improvement | 95% CI |
|---|---:|---:|---:|---:|
| stable_control | -0.0025 | [-0.0026, -0.0024] | -0.0107 | [-0.0129, -0.0084] |
| failure_only | 0.0002 | [-0.0028, 0.0032] | -0.0050 | [-0.0146, 0.0045] |
| partition_only | -0.0219 | [-0.0253, -0.0185] | -0.0075 | [-0.0096, -0.0054] |
| asymmetric_partition | -0.0170 | [-0.0441, 0.0102] | 0.0017 | [-0.0087, 0.0121] |
| failure_partition | 0.0235 | [0.0151, 0.0320] | 0.0034 | [0.0006, 0.0062] |
| staggered_rejoin | 0.0009 | [0.0007, 0.0011] | 0.0094 | [0.0092, 0.0096] |
| flapping_reconnect | -0.0137 | [-0.0208, -0.0066] | 0.0030 | [0.0029, 0.0030] |
| false_split_dropout | -0.0018 | [-0.0067, 0.0032] | -0.0062 | [-0.0083, -0.0041] |
| admission_censoring_control | -0.0056 | [-0.0104, -0.0008] | 0.0045 | [0.0044, 0.0046] |
| source_assignment_competition | -0.0001 | [-0.0048, 0.0046] | 0.0306 | [0.0195, 0.0416] |
| raw_channel_colluding_ramp | 0.0000 | [0.0000, 0.0000] | 0.0000 | [0.0000, 0.0000] |
| __aggregate_exact__ | -0.0038 | [-0.0103, 0.0039] | 0.0023 | [-0.0026, 0.0081] |

## Boundary

This protocol cannot authorize production. A GO would only retain the integrated allocator for a decentralized follow-up. Failure of an efficacy gate archives the dynamic VOI integration at this representation; failure of attack absolute utility leaves the raw-channel risk explicitly unresolved.

