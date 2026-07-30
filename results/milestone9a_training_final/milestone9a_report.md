# Milestone 9A topology resilience report

**Verdict: M9A-PARTIAL-GO**

Fresh seeds: `11000`–`11029` (30 paired seeds per cell).

## Preregistered gates

| Gate | Result |
|---|---:|
| replay | PASS |
| stable_noninferiority | PASS |
| dynamic_transfer_lcb | FAIL |
| calibration_and_tail | PASS |
| wrong_selection | PASS |
| rejoin_shock | PASS |
| partition_uncertainty | PASS |
| support_continuity | PASS |

## Full M9A algorithm by scenario

| Scenario | Loss | Transfer LCB | NEES | p95 NEES | Coverage | Wrong mode | Unknown | Rejoin NEES | Support jump |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stable_control | 0.939 | — | 1.76 | 4.39 | 0.971 | 0.006 | 0.023 | 0.00 | 0.007 |
| failure_only | 1.038 | -0.148 | 1.68 | 4.48 | 0.970 | 0.003 | 0.238 | 1.67 | 0.022 |
| partition_only | 1.069 | -0.163 | 1.44 | 3.98 | 0.978 | 0.001 | 0.329 | 0.00 | 0.127 |
| asymmetric_partition | 1.094 | -0.211 | 1.56 | 4.18 | 0.977 | 0.002 | 0.363 | 0.00 | 0.138 |
| failure_partition | 1.129 | -0.262 | 1.60 | 4.42 | 0.972 | 0.001 | 0.429 | 1.62 | 0.112 |
| staggered_rejoin | 1.032 | -0.233 | 2.91 | 9.06 | 0.963 | 0.002 | 0.277 | 1.59 | 0.097 |
| flapping_reconnect | 0.967 | -0.041 | 1.60 | 4.21 | 0.973 | 0.003 | 0.209 | 0.00 | 0.056 |
| false_split_dropout | 0.992 | -0.072 | 1.80 | 3.89 | 0.973 | 0.005 | 0.098 | 0.00 | 0.110 |

## Interpretation

M9A.0 records component epochs, lifecycle transitions, evidence provenance, unknown support, merge grace, and selection blocks on every cycle.

M9A.1 uses unique live contributors, decaying retained mode memory, and explicit unknown support. M9A.2 enforces OFFLINE → PROBATION → TRUSTED with covariance inflation and a support ramp. M9A.3 restricts the external output to the observer component and defers selection during reconnection grace. M9A.4 evaluates the frozen implementation against failure-only, partition-only, asymmetric, combined, staggered, flapping, and false-split traces.

A GO verdict is still simulator evidence rather than external validity. M9B remains a separate held-out claim until an integrated suite is explicitly run.
