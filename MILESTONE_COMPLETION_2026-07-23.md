# Remaining-milestone completion report

Date: 23 July 2026  
Platform version: 0.19.0

## Decisions

| Milestone | Result | Decisive evidence | Authorization |
|---|---|---|---|
| M10A.5 closed-loop trust | `M10A5-GO` | 16/16 held-out gates; canonical attack loss `0.434`; trust recovery ≤ 8 cycles; exact baseline compatibility | M10B research |
| M10B decentralized allocation | `M10B-GO` | 15/15 held-out gates; zero ownership/message-bound violations; worst natural noninferiority LCB `-0.0079`; attack loss `0.437` | External replay research |
| M11 original external replay | `M11-INVALID` | Frozen Dataset 9 parser rejected four negative initial odometry timestamp jumps before estimation | Transparent repair only |
| M11.1 repaired external replay | `M11.1-GO` | 15/15 combined gates; Dataset 6 bounded RMSE `0.514 m` vs odometry `2.163 m`; NEES `1.93`; coverage `0.899` | M12 development |
| M12 measured acceleration | `M12-DEVELOPMENT-FAIL` | RMSE `0.521 m` vs baseline `0.313 m`; improvement CI wholly negative; NEES `19.38`; outage ratio `2.00` | Stop estimator branch; do not open Dataset 7 |
| M12 behavioural jerk | Isolated assay pass | 90% peak-jerk reduction, acceleration bound respected, `0.045 m/s` added tracking RMSE | Future closed-loop behavioural ablation only |
| M13.0 validation boundary | Software complete | Canonical wire/ROS contracts, truth isolation, exact bytes, deterministic network/attack manifests, safety, sealed ledgers | M13.1 screen |
| M13.1 independent full loop | `M13.1-HIL-PILOT-READY` | 6,000 paired trials; 12/12 gates; decentralized-v-central loss `-0.00362`, CI `[-0.00447, -0.00279]`; zero wrong actions/collisions/e-stops/ownership violations | M13.2 instrumented pilot only |
| M13.2 physical pilot | Implemented, awaiting evidence | 320-run randomized plan; genuine-evidence check; independent raw scoring; covariance/power/source freeze | No decision until robot bundles exist |
| M13.3 physical holdout | Implemented, unopened | Pilot exclusion, source lock, ≥3 days, complete powered blocks, 13 integrity/scientific gates | No external claim yet |

## Reproducibility

- Frozen M10A.5 held-out artifacts:
  `results/milestone10a5_heldout/`
- Frozen M10B training and held-out artifacts:
  `results/milestone10b_training/`,
  `results/milestone10b_heldout/`
- Original invalid M11 record:
  `results/milestone11_heldout/`
- M11.1 repair development and replacement held-out artifacts:
  `results/milestone11_1_development/`,
  `results/milestone11_1_heldout/`
- M12 development-stop artifacts:
  `results/milestone12_development/`
- M13.1 powered screen:
  `results/milestone13_1_hil/`
- M13.2 randomized pilot plan:
  `physical/m13_pilot_plan/`
- Protocols:
  `M10A5_PROTOCOL.md`, `M10B_PROTOCOL.md`, `M11_PROTOCOL.md`,
  `M11_1_PROTOCOL.md`, `M12_PROTOCOL.md`, `M13_PROTOCOL.md`
- Regression suite: 59 tests, all passing.

## Research recommendation

Continue the trust-plus-decentralized-allocation architecture, but stop the
current kinematic expansion. M13.1 clears entry to the instrumented physical
pilot with an adaptive bounded attacker and independent fault process. Execute
the generated M13.2 plan next, qualify the site adapters, and freeze M13.3 only
from genuine external evidence while preserving the constant-velocity
estimator.

The known-map MR.CLAM result is a real external-validity step, but it does not
validate the simulator's adversarial assignment or active-allocation model.
The powered software result is not a physical result. Production remains
unauthorized.
