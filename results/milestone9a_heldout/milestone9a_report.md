# Milestone 9A topology resilience report

**Verdict: M9A-PARTIAL-GO**

Fresh seeds: `12000`–`12099` (100 paired seeds per cell).

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
| stable_control | 0.944 | — | 1.88 | 4.53 | 0.967 | 0.007 | 0.021 | 0.00 | 0.005 |
| failure_only | 1.047 | -0.130 | 1.79 | 4.48 | 0.971 | 0.004 | 0.253 | 1.58 | 0.024 |
| partition_only | 1.075 | -0.155 | 1.61 | 4.12 | 0.973 | 0.004 | 0.323 | 0.00 | 0.130 |
| asymmetric_partition | 1.089 | -0.171 | 1.62 | 4.16 | 0.973 | 0.003 | 0.354 | 0.00 | 0.137 |
| failure_partition | 1.162 | -0.272 | 2.26 | 6.74 | 0.964 | 0.004 | 0.432 | 1.67 | 0.112 |
| staggered_rejoin | 1.009 | -0.114 | 2.19 | 5.94 | 0.964 | 0.006 | 0.272 | 1.64 | 0.123 |
| flapping_reconnect | 0.967 | -0.033 | 1.75 | 4.26 | 0.972 | 0.005 | 0.202 | 0.00 | 0.056 |
| false_split_dropout | 1.002 | -0.070 | 1.90 | 4.10 | 0.968 | 0.006 | 0.099 | 0.00 | 0.113 |

## Interpretation

M9A.0 records component epochs, lifecycle transitions, evidence provenance, unknown support, merge grace, and selection blocks on every cycle.

M9A.1 uses unique live contributors, decaying retained mode memory, and explicit unknown support. M9A.2 enforces OFFLINE → PROBATION → TRUSTED with covariance inflation and a support ramp. M9A.3 restricts the external output to the observer component and defers selection during reconnection grace. M9A.4 evaluates the frozen implementation against failure-only, partition-only, asymmetric, combined, staggered, flapping, and false-split traces.

A GO verdict is still simulator evidence rather than external validity. M9B remains a separate held-out claim until an integrated suite is explicitly run.
