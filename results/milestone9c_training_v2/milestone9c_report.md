# M9C bounded M9A.7/M9B integration report

**Verdict: `M9C-TRAINING-PARTIAL`**

Phase: `training`. Seeds: `18000`–`18039` (40 paired seeds per scenario).

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
| stable_control | M9A.7 | 1.047 | 0.279 | 0.961 | 0.000 | 0.000 | 1.80 | 0.963 | 1.000 | 1.00 |
| stable_control | broad | 1.040 | 0.279 | 0.950 | 0.013 | 0.000 | 1.80 | 0.965 | 1.000 | 1.01 |
| stable_control | VOI | 1.038 | 0.280 | 0.948 | 0.002 | 0.000 | 1.80 | 0.964 | 1.000 | 1.01 |
| failure_only | M9A.7 | 1.061 | 0.300 | 0.951 | 0.000 | 0.000 | 1.79 | 0.964 | 1.000 | 1.01 |
| failure_only | broad | 1.052 | 0.301 | 0.939 | 0.013 | 0.000 | 1.79 | 0.964 | 1.000 | 1.01 |
| failure_only | VOI | 1.052 | 0.301 | 0.938 | 0.002 | 0.000 | 1.79 | 0.964 | 1.000 | 1.01 |
| partition_only | M9A.7 | 1.156 | 0.381 | 0.969 | 0.000 | 0.000 | 1.76 | 0.965 | 1.000 | 2.14 |
| partition_only | broad | 1.143 | 0.379 | 0.955 | 0.013 | 0.000 | 1.77 | 0.964 | 1.000 | 2.10 |
| partition_only | VOI | 1.141 | 0.377 | 0.955 | 0.002 | 0.000 | 1.77 | 0.965 | 1.000 | 2.09 |
| asymmetric_partition | M9A.7 | 1.187 | 0.413 | 0.967 | 0.000 | 0.000 | 1.76 | 0.967 | 1.000 | 2.02 |
| asymmetric_partition | broad | 1.177 | 0.413 | 0.955 | 0.013 | 0.000 | 1.76 | 0.966 | 1.000 | 1.98 |
| asymmetric_partition | VOI | 1.176 | 0.414 | 0.953 | 0.002 | 0.000 | 1.76 | 0.966 | 1.000 | 2.00 |
| failure_partition | M9A.7 | 1.138 | 0.384 | 0.942 | 0.000 | 0.000 | 1.77 | 0.965 | 1.000 | 1.69 |
| failure_partition | broad | 1.129 | 0.385 | 0.931 | 0.013 | 0.000 | 1.76 | 0.965 | 1.000 | 1.68 |
| failure_partition | VOI | 1.126 | 0.382 | 0.930 | 0.002 | 0.000 | 1.76 | 0.965 | 1.000 | 1.68 |
| staggered_rejoin | M9A.7 | 1.061 | 0.314 | 0.933 | 0.000 | 0.000 | 1.76 | 0.964 | 1.000 | 1.01 |
| staggered_rejoin | broad | 1.054 | 0.316 | 0.922 | 0.013 | 0.000 | 1.77 | 0.967 | 1.000 | 1.02 |
| staggered_rejoin | VOI | 1.053 | 0.317 | 0.921 | 0.002 | 0.000 | 1.77 | 0.965 | 1.000 | 1.02 |
| flapping_reconnect | M9A.7 | 1.101 | 0.318 | 0.979 | 0.000 | 0.000 | 1.78 | 0.965 | 1.000 | 1.48 |
| flapping_reconnect | broad | 1.094 | 0.320 | 0.968 | 0.013 | 0.000 | 1.77 | 0.966 | 1.000 | 1.50 |
| flapping_reconnect | VOI | 1.096 | 0.321 | 0.970 | 0.002 | 0.000 | 1.78 | 0.965 | 1.000 | 1.49 |
| false_split_dropout | M9A.7 | 1.109 | 0.285 | 1.031 | 0.000 | 0.000 | 1.80 | 0.963 | 0.652 | 1.10 |
| false_split_dropout | broad | 1.099 | 0.286 | 1.016 | 0.013 | 0.000 | 1.80 | 0.966 | 0.652 | 1.10 |
| false_split_dropout | VOI | 1.096 | 0.286 | 1.012 | 0.000 | 0.000 | 1.79 | 0.965 | 0.652 | 1.11 |
| admission_censoring_control | M9A.7 | 1.126 | 0.344 | 0.977 | 0.000 | 0.000 | 1.75 | 0.965 | 1.000 | 1.60 |
| admission_censoring_control | broad | 1.123 | 0.347 | 0.970 | 0.013 | 0.000 | 1.75 | 0.965 | 1.000 | 1.61 |
| admission_censoring_control | VOI | 1.122 | 0.348 | 0.968 | 0.002 | 0.000 | 1.74 | 0.966 | 1.000 | 1.61 |
| source_assignment_competition | M9A.7 | 1.837 | 1.056 | 0.976 | 0.000 | 0.000 | 1.63 | 0.976 | 1.000 | 1.00 |
| source_assignment_competition | broad | 1.831 | 1.036 | 0.993 | 0.086 | 0.000 | 1.63 | 0.974 | 1.000 | 1.00 |
| source_assignment_competition | VOI | 1.825 | 1.048 | 0.971 | 0.025 | 0.000 | 1.63 | 0.975 | 1.000 | 1.00 |
| raw_channel_colluding_ramp | M9A.7 | 4.298 | 3.500 | 0.998 | 0.000 | 0.000 | 397.89 | 0.161 | 1.000 | 1.01 |
| raw_channel_colluding_ramp | broad | 4.290 | 3.508 | 0.978 | 0.000 | 0.000 | 402.53 | 0.160 | 1.000 | 1.00 |
| raw_channel_colluding_ramp | VOI | 4.290 | 3.508 | 0.978 | 0.000 | 0.000 | 402.53 | 0.160 | 1.000 | 1.00 |

## VOI effects versus broad investigation

| Scope | Integrated-loss improvement | 95% CI | Movement improvement | 95% CI |
|---|---:|---:|---:|---:|
| stable_control | 0.0022 | [0.0007, 0.0036] | 0.0028 | [0.0014, 0.0042] |
| failure_only | 0.0004 | [-0.0016, 0.0024] | 0.0009 | [-0.0011, 0.0029] |
| partition_only | 0.0023 | [-0.0026, 0.0069] | 0.0007 | [-0.0015, 0.0029] |
| asymmetric_partition | 0.0009 | [-0.0022, 0.0041] | 0.0024 | [0.0005, 0.0043] |
| failure_partition | 0.0034 | [0.0002, 0.0067] | 0.0006 | [-0.0012, 0.0022] |
| staggered_rejoin | 0.0005 | [-0.0016, 0.0024] | 0.0014 | [-0.0001, 0.0027] |
| flapping_reconnect | -0.0021 | [-0.0057, 0.0015] | -0.0016 | [-0.0045, 0.0016] |
| false_split_dropout | 0.0028 | [-0.0019, 0.0073] | 0.0036 | [-0.0002, 0.0074] |
| admission_censoring_control | 0.0006 | [-0.0030, 0.0042] | 0.0020 | [0.0001, 0.0040] |
| source_assignment_competition | 0.0060 | [0.0008, 0.0114] | 0.0223 | [0.0186, 0.0262] |
| raw_channel_colluding_ramp | 0.0000 | [0.0000, 0.0000] | 0.0000 | [0.0000, 0.0000] |
| __aggregate_exact__ | 0.0017 | [0.0006, 0.0029] | 0.0035 | [0.0025, 0.0045] |

## Boundary

This protocol cannot authorize production. A GO would only retain the integrated allocator for a decentralized follow-up. Failure of an efficacy gate archives the dynamic VOI integration at this representation; failure of attack absolute utility leaves the raw-channel risk explicitly unresolved.

