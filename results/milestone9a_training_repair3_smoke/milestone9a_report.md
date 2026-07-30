# Milestone 9A topology resilience report

**Verdict: M9A-NO-GO**

Fresh seeds: `11000`–`11004` (5 paired seeds per cell).

## Preregistered gates

| Gate | Result |
|---|---:|
| replay | PASS |
| stable_noninferiority | FAIL |
| dynamic_transfer_lcb | FAIL |
| calibration_and_tail | FAIL |
| wrong_selection | PASS |
| rejoin_shock | PASS |
| partition_uncertainty | PASS |
| support_continuity | PASS |

## Full M9A algorithm by scenario

| Scenario | Loss | Transfer LCB | NEES | p95 NEES | Coverage | Wrong mode | Unknown | Rejoin NEES | Support jump |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stable_control | 0.964 | — | 1.81 | 4.48 | 0.974 | 0.006 | 0.026 | 0.00 | 0.004 |
| failure_only | 1.140 | -0.482 | 3.69 | 23.17 | 0.940 | 0.000 | 0.216 | 2.25 | 0.054 |
| partition_only | 1.033 | -0.102 | 1.60 | 4.37 | 0.974 | 0.000 | 0.324 | 0.00 | 0.196 |
| asymmetric_partition | 1.047 | -0.104 | 1.61 | 4.22 | 0.970 | 0.000 | 0.352 | 0.00 | 0.171 |
| failure_partition | 1.071 | -0.225 | 1.66 | 4.76 | 0.961 | 0.000 | 0.432 | 1.74 | 0.112 |
| staggered_rejoin | 0.930 | 0.013 | 1.57 | 4.33 | 0.973 | 0.000 | 0.265 | 1.67 | 0.050 |
| flapping_reconnect | 0.986 | -0.057 | 1.73 | 4.76 | 0.964 | 0.003 | 0.207 | 0.00 | 0.046 |
| false_split_dropout | 1.012 | -0.093 | 2.21 | 4.13 | 0.963 | 0.009 | 0.121 | 0.00 | 0.129 |

## Interpretation

M9A.0 records component epochs, lifecycle transitions, evidence provenance, unknown support, merge grace, and selection blocks on every cycle.

M9A.1 uses unique live contributors, decaying retained mode memory, and explicit unknown support. M9A.2 enforces OFFLINE → PROBATION → TRUSTED with covariance inflation and a support ramp. M9A.3 restricts the external output to the observer component and defers selection during reconnection grace. M9A.4 evaluates the frozen implementation against failure-only, partition-only, asymmetric, combined, staggered, flapping, and false-split traces.

A GO verdict is still simulator evidence rather than external validity. M9B remains a separate held-out claim until an integrated suite is explicitly run.
