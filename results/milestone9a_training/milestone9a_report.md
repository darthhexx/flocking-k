# Milestone 9A topology resilience report

**Verdict: M9A-NO-GO**

Fresh seeds: `11000`–`11029` (30 paired seeds per cell).

## Preregistered gates

| Gate | Result |
|---|---:|
| replay | PASS |
| stable_noninferiority | PASS |
| dynamic_transfer_lcb | FAIL |
| calibration_and_tail | FAIL |
| wrong_selection | PASS |
| rejoin_shock | PASS |
| partition_uncertainty | PASS |
| support_continuity | FAIL |

## Full M9A algorithm by scenario

| Scenario | Loss | Transfer LCB | NEES | p95 NEES | Coverage | Wrong mode | Unknown | Rejoin NEES | Support jump |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stable_control | 0.954 | — | 2.22 | 4.44 | 0.969 | 0.004 | 0.020 | 0.00 | 0.533 |
| failure_only | 1.386 | -0.683 | 8.95 | 29.88 | 0.904 | 0.003 | 0.235 | 1.76 | 0.529 |
| partition_only | 2.156 | -1.530 | 25.23 | 86.51 | 0.780 | 0.002 | 0.312 | 0.00 | 0.596 |
| asymmetric_partition | 2.216 | -1.603 | 25.62 | 84.59 | 0.769 | 0.002 | 0.347 | 0.00 | 0.688 |
| failure_partition | 1.874 | -1.188 | 17.47 | 85.34 | 0.827 | 0.002 | 0.414 | 1.80 | 0.537 |
| staggered_rejoin | 1.228 | -0.507 | 6.94 | 19.40 | 0.929 | 0.003 | 0.272 | 1.45 | 0.529 |
| flapping_reconnect | 1.481 | -0.679 | 12.73 | 76.68 | 0.881 | 0.002 | 0.151 | 0.00 | 0.537 |
| false_split_dropout | 1.230 | -0.385 | 6.64 | 46.93 | 0.931 | 0.003 | 0.059 | 0.00 | 0.633 |

## Interpretation

M9A.0 records component epochs, lifecycle transitions, evidence provenance, unknown support, merge grace, and selection blocks on every cycle.

M9A.1 uses unique live contributors, decaying retained mode memory, and explicit unknown support. M9A.2 enforces OFFLINE → PROBATION → TRUSTED with covariance inflation and a support ramp. M9A.3 restricts the external output to the observer component and defers selection during reconnection grace. M9A.4 evaluates the frozen implementation against failure-only, partition-only, asymmetric, combined, staggered, flapping, and false-split traces.

A GO verdict is still simulator evidence rather than external validity. M9B remains a separate held-out claim until an integrated suite is explicitly run.
