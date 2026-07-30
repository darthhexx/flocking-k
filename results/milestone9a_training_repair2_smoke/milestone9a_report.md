# Milestone 9A topology resilience report

**Verdict: M9A-NO-GO**

Fresh seeds: `11000`–`11004` (5 paired seeds per cell).

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
| stable_control | 0.947 | — | 1.77 | 5.01 | 0.972 | 0.006 | 0.020 | 0.00 | 0.025 |
| failure_only | 1.269 | -0.907 | 5.35 | 27.78 | 0.921 | 0.000 | 0.212 | 1.81 | 0.075 |
| partition_only | 1.608 | -1.254 | 10.39 | 54.87 | 0.895 | 0.000 | 0.302 | 0.00 | 0.550 |
| asymmetric_partition | 1.671 | -1.399 | 13.46 | 57.56 | 0.878 | 0.000 | 0.333 | 0.00 | 0.625 |
| failure_partition | 1.419 | -1.205 | 6.45 | 29.39 | 0.921 | 0.000 | 0.415 | 2.04 | 0.450 |
| staggered_rejoin | 0.933 | -0.017 | 1.58 | 5.01 | 0.977 | 0.000 | 0.260 | 1.73 | 0.062 |
| flapping_reconnect | 0.984 | -0.095 | 1.58 | 4.69 | 0.974 | 0.000 | 0.150 | 0.00 | 0.200 |
| false_split_dropout | 1.011 | -0.112 | 2.39 | 5.04 | 0.972 | 0.006 | 0.052 | 0.00 | 0.350 |

## Interpretation

M9A.0 records component epochs, lifecycle transitions, evidence provenance, unknown support, merge grace, and selection blocks on every cycle.

M9A.1 uses unique live contributors, decaying retained mode memory, and explicit unknown support. M9A.2 enforces OFFLINE → PROBATION → TRUSTED with covariance inflation and a support ramp. M9A.3 restricts the external output to the observer component and defers selection during reconnection grace. M9A.4 evaluates the frozen implementation against failure-only, partition-only, asymmetric, combined, staggered, flapping, and false-split traces.

A GO verdict is still simulator evidence rather than external validity. M9B remains a separate held-out claim until an integrated suite is explicitly run.
