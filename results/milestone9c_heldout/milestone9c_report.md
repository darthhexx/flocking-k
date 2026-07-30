# M9C bounded M9A.7/M9B integration report

**Verdict: `M9C-PARTIAL-GO`**

Phase: `heldout`. Seeds: `19000`–`19149` (150 paired seeds per scenario).

The external estimator and risk-priced output are unchanged M9A.7. The two integration arms use the exact assignment posterior for physical motion: broad all-source investigation versus a component-local two-step VOI allocator. Unknown residual mass above the frozen ceiling disables extra probing.

## Gates

| Gate | Result |
|---|---:|
| replay | PASS |
| upstream_m9a7_frozen_go | PASS |
| tail_event_power | PASS |
| positive_control_exercised | PASS |
| aggregate_voi_utility | PASS |
| positive_control_voi_utility | PASS |
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
| stable_control | M9A.7 | 1.048 | 0.272 | 0.970 | 0.000 | 0.000 | 1.71 | 0.970 | 1.000 | 1.01 |
| stable_control | broad | 1.038 | 0.273 | 0.957 | 0.012 | 0.000 | 1.71 | 0.970 | 1.000 | 1.01 |
| stable_control | VOI | 1.036 | 0.272 | 0.955 | 0.001 | 0.000 | 1.71 | 0.970 | 1.000 | 1.01 |
| failure_only | M9A.7 | 1.056 | 0.291 | 0.956 | 0.000 | 0.000 | 1.70 | 0.970 | 1.000 | 1.01 |
| failure_only | broad | 1.046 | 0.292 | 0.943 | 0.012 | 0.000 | 1.70 | 0.970 | 1.000 | 1.02 |
| failure_only | VOI | 1.044 | 0.292 | 0.941 | 0.001 | 0.000 | 1.70 | 0.970 | 1.000 | 1.01 |
| partition_only | M9A.7 | 1.153 | 0.372 | 0.975 | 0.000 | 0.000 | 1.68 | 0.971 | 1.000 | 2.12 |
| partition_only | broad | 1.140 | 0.370 | 0.963 | 0.012 | 0.000 | 1.68 | 0.972 | 1.000 | 2.10 |
| partition_only | VOI | 1.137 | 0.369 | 0.961 | 0.001 | 0.000 | 1.68 | 0.972 | 1.000 | 2.09 |
| asymmetric_partition | M9A.7 | 1.189 | 0.410 | 0.974 | 0.000 | 0.000 | 1.68 | 0.972 | 1.000 | 2.04 |
| asymmetric_partition | broad | 1.179 | 0.409 | 0.963 | 0.012 | 0.000 | 1.67 | 0.973 | 1.000 | 2.04 |
| asymmetric_partition | VOI | 1.178 | 0.409 | 0.960 | 0.001 | 0.000 | 1.67 | 0.973 | 1.000 | 2.03 |
| failure_partition | M9A.7 | 1.126 | 0.369 | 0.946 | 0.000 | 0.000 | 1.69 | 0.971 | 1.000 | 1.68 |
| failure_partition | broad | 1.117 | 0.369 | 0.934 | 0.012 | 0.000 | 1.69 | 0.971 | 1.000 | 1.67 |
| failure_partition | VOI | 1.114 | 0.369 | 0.932 | 0.001 | 0.000 | 1.69 | 0.971 | 1.000 | 1.68 |
| staggered_rejoin | M9A.7 | 1.061 | 0.308 | 0.941 | 0.000 | 0.000 | 1.70 | 0.970 | 1.000 | 1.01 |
| staggered_rejoin | broad | 1.050 | 0.309 | 0.927 | 0.012 | 0.000 | 1.70 | 0.970 | 1.000 | 1.02 |
| staggered_rejoin | VOI | 1.048 | 0.308 | 0.925 | 0.001 | 0.000 | 1.70 | 0.971 | 1.000 | 1.02 |
| flapping_reconnect | M9A.7 | 1.101 | 0.312 | 0.986 | 0.000 | 0.000 | 1.70 | 0.971 | 1.000 | 1.48 |
| flapping_reconnect | broad | 1.096 | 0.314 | 0.977 | 0.012 | 0.000 | 1.70 | 0.971 | 1.000 | 1.50 |
| flapping_reconnect | VOI | 1.091 | 0.313 | 0.973 | 0.001 | 0.000 | 1.69 | 0.971 | 1.000 | 1.49 |
| false_split_dropout | M9A.7 | 1.108 | 0.279 | 1.036 | 0.000 | 0.000 | 1.71 | 0.970 | 0.653 | 1.10 |
| false_split_dropout | broad | 1.097 | 0.279 | 1.022 | 0.012 | 0.000 | 1.71 | 0.971 | 0.653 | 1.11 |
| false_split_dropout | VOI | 1.095 | 0.279 | 1.019 | 0.000 | 0.000 | 1.71 | 0.969 | 0.654 | 1.11 |
| admission_censoring_control | M9A.7 | 1.124 | 0.334 | 0.987 | 0.000 | 0.000 | 1.68 | 0.972 | 1.000 | 1.59 |
| admission_censoring_control | broad | 1.119 | 0.336 | 0.979 | 0.012 | 0.000 | 1.68 | 0.971 | 1.000 | 1.61 |
| admission_censoring_control | VOI | 1.117 | 0.336 | 0.977 | 0.001 | 0.000 | 1.68 | 0.972 | 1.000 | 1.61 |
| source_assignment_competition | M9A.7 | 1.823 | 1.038 | 0.982 | 0.000 | 0.000 | 1.57 | 0.978 | 1.000 | 1.00 |
| source_assignment_competition | broad | 1.823 | 1.023 | 1.000 | 0.084 | 0.000 | 1.58 | 0.978 | 1.000 | 1.00 |
| source_assignment_competition | VOI | 1.816 | 1.031 | 0.980 | 0.024 | 0.000 | 1.57 | 0.978 | 1.000 | 1.00 |
| raw_channel_colluding_ramp | M9A.7 | 4.304 | 3.499 | 1.007 | 0.000 | 0.000 | 398.38 | 0.162 | 1.000 | 1.01 |
| raw_channel_colluding_ramp | broad | 4.296 | 3.507 | 0.987 | 0.000 | 0.000 | 402.72 | 0.161 | 1.000 | 1.01 |
| raw_channel_colluding_ramp | VOI | 4.296 | 3.507 | 0.987 | 0.000 | 0.000 | 402.72 | 0.161 | 1.000 | 1.01 |

## VOI effects versus broad investigation

| Scope | Integrated-loss improvement | 95% CI | Movement improvement | 95% CI |
|---|---:|---:|---:|---:|
| stable_control | 0.0020 | [0.0011, 0.0030] | 0.0019 | [0.0009, 0.0030] |
| failure_only | 0.0018 | [0.0010, 0.0028] | 0.0019 | [0.0010, 0.0029] |
| partition_only | 0.0030 | [0.0008, 0.0054] | 0.0024 | [0.0014, 0.0035] |
| asymmetric_partition | 0.0015 | [-0.0005, 0.0035] | 0.0023 | [0.0012, 0.0033] |
| failure_partition | 0.0023 | [-0.0003, 0.0048] | 0.0021 | [0.0011, 0.0032] |
| staggered_rejoin | 0.0021 | [0.0013, 0.0029] | 0.0021 | [0.0014, 0.0029] |
| flapping_reconnect | 0.0043 | [0.0023, 0.0063] | 0.0036 | [0.0022, 0.0050] |
| false_split_dropout | 0.0027 | [0.0003, 0.0051] | 0.0028 | [0.0006, 0.0051] |
| admission_censoring_control | 0.0022 | [0.0003, 0.0039] | 0.0017 | [0.0007, 0.0029] |
| source_assignment_competition | 0.0075 | [0.0044, 0.0106] | 0.0203 | [0.0179, 0.0227] |
| raw_channel_colluding_ramp | 0.0000 | [0.0000, 0.0000] | 0.0000 | [0.0000, 0.0000] |
| __aggregate_exact__ | 0.0029 | [0.0023, 0.0036] | 0.0041 | [0.0036, 0.0047] |

## Boundary

This protocol cannot authorize production. A GO would only retain the integrated allocator for a decentralized follow-up. Failure of an efficacy gate archives the dynamic VOI integration at this representation; failure of attack absolute utility leaves the raw-channel risk explicitly unresolved.

