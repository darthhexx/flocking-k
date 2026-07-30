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
| support_continuity | FAIL |

## Full M9A algorithm by scenario

| Scenario | Loss | Transfer LCB | NEES | p95 NEES | Coverage | Wrong mode | Unknown | Rejoin NEES | Support jump |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stable_control | 0.989 | — | 1.57 | 4.27 | 0.976 | 0.046 | 0.017 | 0.00 | 0.000 |
| failure_only | 1.240 | -0.827 | 4.57 | 24.74 | 0.938 | 0.006 | 0.212 | 2.41 | 0.100 |
| partition_only | 1.470 | -1.134 | 7.73 | 29.39 | 0.921 | 0.032 | 0.306 | 0.00 | 0.500 |
| asymmetric_partition | 1.448 | -1.120 | 6.49 | 27.97 | 0.919 | 0.014 | 0.336 | 0.00 | 0.650 |
| failure_partition | 1.387 | -1.184 | 6.19 | 26.49 | 0.919 | 0.003 | 0.414 | 1.90 | 0.425 |
| staggered_rejoin | 0.950 | -0.002 | 1.44 | 4.19 | 0.984 | 0.017 | 0.259 | 0.92 | 0.142 |
| flapping_reconnect | 1.007 | -0.096 | 1.54 | 4.12 | 0.980 | 0.020 | 0.151 | 0.00 | 0.225 |
| false_split_dropout | 1.055 | -0.162 | 2.25 | 3.99 | 0.968 | 0.018 | 0.057 | 0.00 | 0.425 |

## Interpretation

M9A.0 records component epochs, lifecycle transitions, evidence provenance, unknown support, merge grace, and selection blocks on every cycle.

M9A.1 uses unique live contributors, decaying retained mode memory, and explicit unknown support. M9A.2 enforces OFFLINE → PROBATION → TRUSTED with covariance inflation and a support ramp. M9A.3 restricts the external output to the observer component and defers selection during reconnection grace. M9A.4 evaluates the frozen implementation against failure-only, partition-only, asymmetric, combined, staggered, flapping, and false-split traces.

A GO verdict is still simulator evidence rather than external validity. M9B remains a separate held-out claim until an integrated suite is explicitly run.
