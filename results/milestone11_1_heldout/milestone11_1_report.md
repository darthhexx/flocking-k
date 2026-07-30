# M11.1 canonicalized external replay report

**Verdict: `M11.1-GO`**

The original M11 Dataset 9 rejection remains `M11-INVALID`.

## Canonicalization

- Rows retained: `605947` / `605947`
- Timestamp inversions: `0`
- Reordered rows: `0`
- Fingerprint: `fb40370e7a4996d5aa7966909ab4c7fd01fbcfc098a37a8be0f82ed06c5323a5`

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
| odometry_only | 2.163 | 0.11 | 0.17 | 1.000 | 0.000 | 0 | 2.023 | 0.015 |
| all_landmarks | 0.541 | 2.84 | 10.30 | 0.862 | 0.543 | 21 | 0.390 | 0.018 |
| bounded_two | 0.514 | 1.93 | 6.56 | 0.899 | 0.543 | 2 | 0.369 | 0.018 |

Unknown barcode observations rejected: `6`.

A GO establishes bounded causal operation on this recorded localization task only; it does not validate the simulator's adversarial assignment model.
