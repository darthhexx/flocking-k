# Milestone 9A topology resilience report

**Verdict: M9A-NO-GO**

Fresh seeds: `11990`–`11991` (2 paired seeds per cell).

## Preregistered gates

| Gate | Result |
|---|---:|
| replay | PASS |
| stable_noninferiority | FAIL |
| dynamic_transfer_lcb | FAIL |
| calibration_and_tail | FAIL |
| wrong_selection | PASS |
| rejoin_shock | FAIL |
| partition_uncertainty | PASS |
| support_continuity | FAIL |

## Full M9A algorithm by scenario

| Scenario | Loss | Transfer LCB | NEES | p95 NEES | Coverage | Wrong mode | Unknown | Rejoin NEES | Support jump |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stable_control | 3.510 | — | 49.15 | 167.27 | 0.517 | 0.013 | 0.400 | 0.00 | 0.333 |
| failure_only | 2.772 | -0.270 | 37.49 | 160.57 | 0.688 | 0.013 | 0.374 | 1.87 | 0.333 |
| partition_only | 3.380 | -0.022 | 43.31 | 152.99 | 0.492 | 0.013 | 0.556 | 0.00 | 0.417 |
| asymmetric_partition | 3.380 | -0.022 | 43.31 | 152.99 | 0.492 | 0.013 | 0.556 | 0.00 | 0.417 |
| failure_partition | 2.594 | 0.086 | 29.30 | 129.68 | 0.662 | 0.013 | 0.545 | 1.93 | 0.417 |
| staggered_rejoin | 3.858 | -0.357 | 56.09 | 172.54 | 0.522 | 0.013 | 0.595 | 1.78 | 0.347 |
| flapping_reconnect | 3.525 | -0.159 | 45.52 | 159.19 | 0.517 | 0.013 | 0.498 | 0.00 | 0.500 |
| false_split_dropout | 3.667 | -0.219 | 49.39 | 160.65 | 0.519 | 0.013 | 0.477 | 0.00 | 0.583 |

## Interpretation

M9A.0 records component epochs, lifecycle transitions, evidence provenance, unknown support, merge grace, and selection blocks on every cycle.

M9A.1 uses unique live contributors, decaying retained mode memory, and explicit unknown support. M9A.2 enforces OFFLINE → PROBATION → TRUSTED with covariance inflation and a support ramp. M9A.3 restricts the external output to the observer component and defers selection during reconnection grace. M9A.4 evaluates the frozen implementation against failure-only, partition-only, asymmetric, combined, staggered, flapping, and false-split traces.

A GO verdict is still simulator evidence rather than external validity. M9B remains a separate held-out claim until an integrated suite is explicitly run.
