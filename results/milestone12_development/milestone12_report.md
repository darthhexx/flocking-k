# M12 acceleration report

**Verdict: `M12-DEVELOPMENT-FAIL`**

## Gates

| Gate | Result |
|---|---:|
| upstream_m11_1_go | PASS |
| archive_and_canonicalization | PASS |
| window_power | PASS |
| acceleration_exercised | PASS |
| rmse_improvement | FAIL |
| outage_nonregression | FAIL |
| calibration | FAIL |
| finite_and_bounded | PASS |
| runtime | PASS |
| behavioural_jerk | PASS |

## Estimator arms

| Arm | Window RMSE | NEES | Coverage | Runtime/window |
|---|---:|---:|---:|---:|
| bounded_constant_velocity | 0.313 | 2.63 | 0.888 | 0.024 |
| bounded_measured_acceleration | 0.521 | 19.38 | 0.853 | 0.026 |

Acceleration exercise rate: `0.423`.
Jerk reduction: `0.900`.

Replay evidence concerns estimator propagation only. The behavioural assay is isolated and does not authorize closed-loop integration.
