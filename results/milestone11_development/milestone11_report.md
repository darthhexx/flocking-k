# M11 external MR.CLAM replay report

**Verdict: `M11-DEVELOPMENT-PASS`**

Phase: `development`.

## Gates

| Gate | Result |
|---|---:|
| archive_and_replay | PASS |
| parser_and_malformed_rejection | PASS |
| truth_isolation | PASS |
| window_power | PASS |
| odometry_improvement | PASS |
| all_landmarks_noninferiority | PASS |
| bounded_update_budget | PASS |
| calibration | PASS |
| outage_robustness | PASS |
| recorded_topology_exercised | PASS |
| runtime | PASS |

## Replay arms

| Arm | Window RMSE | NEES | P95 NEES | Coverage | Update rate | Max updates | Outage RMSE | Runtime/window |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| odometry_only | 3.587 | 1.23 | 1.65 | 0.989 | 0.000 | 0 | 1.929 | 0.021 |
| all_landmarks | 0.320 | 3.33 | 11.69 | 0.851 | 0.643 | 20 | 0.184 | 0.025 |
| bounded_two | 0.313 | 2.63 | 8.66 | 0.888 | 0.607 | 2 | 0.188 | 0.025 |

Unknown barcode observations rejected: `3`.

A GO establishes bounded causal operation on this recorded localization task only; it does not validate the simulator's adversarial assignment model.
