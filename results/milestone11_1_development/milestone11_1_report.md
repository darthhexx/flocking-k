# M11.1 canonicalized external replay report

**Verdict: `M11.1-DEVELOPMENT-PASS`**

The original M11 Dataset 9 rejection remains `M11-INVALID`.

## Canonicalization

- Rows retained: `1116726` / `1116726`
- Timestamp inversions: `4`
- Reordered rows: `8`
- Fingerprint: `6c856105db5050edb20fa5606880ca858eae9b7e98a72c4bf0a0b752d77dc7b0`

## Gates

| Gate | Result |
|---|---:|
| repair_archive | PASS |
| canonicalization_deterministic | PASS |
| all_rows_preserved | PASS |
| canonical_hashes_and_order | PASS |
| m11_archive_and_replay | PASS |
| m11_parser_and_malformed_rejection | PASS |
| m11_truth_isolation | PASS |
| m11_window_power | PASS |
| m11_odometry_improvement | PASS |
| m11_all_landmarks_noninferiority | PASS |
| m11_bounded_update_budget | PASS |
| m11_calibration | PASS |
| m11_outage_robustness | PASS |
| m11_recorded_topology_exercised | PASS |
| m11_runtime | PASS |

## Replay arms

| Arm | Window RMSE | NEES | P95 NEES | Coverage | Update rate | Max updates | Outage RMSE | Runtime/window |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| odometry_only | 9.123 | 0.58 | 0.86 | 0.996 | 0.000 | 0 | 2.459 | 0.042 |
| all_landmarks | 0.407 | 2.73 | 10.17 | 0.902 | 0.779 | 11 | 0.102 | 0.047 |
| bounded_two | 0.411 | 2.50 | 9.25 | 0.919 | 0.778 | 2 | 0.107 | 0.048 |

Unknown barcode observations rejected: `2`.

A GO establishes bounded causal operation on this recorded localization task only; it does not validate the simulator's adversarial assignment model.
