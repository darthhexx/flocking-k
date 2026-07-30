# M9A.6 missing-evidence posterior and pricing report

**Verdict: `M9A6-TRAINING-PASS`**

Phase: `training`. Seeds: `13000`–`13029` (30 paired seeds per scenario).

M9A.6 is an output-only overlay on the frozen M9A physical controller. It marginalizes declared missing-agent assignments, preserves posterior-predictive model-mismatch mass as residual unknown support, and prices select/mixture/defer actions by expected risk. The observer/global references and truth scoring remain outside the policy.

## Gates

| Gate | Result |
|---|---:|
| replay | PASS |
| exact_model_loss_improvement_every_scenario | PASS |
| observer_regret | PASS |
| wrong_action_safety | PASS |
| calibration | PASS |
| nominal_residual_specificity | PASS |
| off_model_residual_response | PASS |
| frozen_motion | PASS |
| asymmetric_information_boundary | PASS |

## Exact-model topology scenarios

| Scenario | Current | M9A.6 | Improvement LCB | Observer | Regret UCB | Global | Frozen-set floor | Residual | Defer | Wrong | NEES | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stable_control | 0.943 | 0.281 | 0.647 | 0.278 | 0.005 | 0.278 | 0.585 | 0.013 | 0.000 | 0.000 | 1.79 | 0.968 |
| failure_only | 1.116 | 0.322 | 0.709 | 0.293 | 0.039 | 0.292 | 0.651 | 0.017 | 0.005 | 0.000 | 1.70 | 0.971 |
| partition_only | 1.061 | 0.388 | 0.644 | 0.359 | 0.038 | 0.276 | 0.629 | 0.024 | 0.035 | 0.000 | 1.76 | 0.970 |
| asymmetric_partition | 1.063 | 0.416 | 0.615 | 0.378 | 0.048 | 0.276 | 0.631 | 0.026 | 0.046 | 0.000 | 1.75 | 0.970 |
| failure_partition | 1.167 | 0.444 | 0.676 | 0.369 | 0.096 | 0.292 | 0.657 | 0.029 | 0.056 | 0.000 | 1.70 | 0.972 |
| staggered_rejoin | 0.995 | 0.322 | 0.642 | 0.311 | 0.016 | 0.309 | 0.594 | 0.015 | 0.004 | 0.000 | 1.74 | 0.971 |
| flapping_reconnect | 0.968 | 0.322 | 0.631 | 0.309 | 0.018 | 0.277 | 0.598 | 0.018 | 0.014 | 0.000 | 1.76 | 0.971 |
| false_split_dropout | 1.007 | 0.287 | 0.702 | 0.284 | 0.006 | 0.276 | 0.593 | 0.013 | 0.001 | 0.000 | 1.79 | 0.968 |

## Off-model challenges

| Scenario | Current | M9A.6 | Residual | Peak residual | Defer | Wrong |
|---|---:|---:|---:|---:|---:|---:|
| unmodelled_count | 0.644 | 0.895 | 0.398 | 0.996 | 0.499 | 0.000 |
| unmodelled_offset | 0.947 | 0.993 | 0.133 | 0.484 | 0.457 | 0.000 |

## Boundary

A held-out GO authorizes M9B integration research, not production deployment. It does not change M9A.4, does not claim the declared assignment family is complete, and does not make component-local information equal ideal-global information. Residual mass must remain explicit in every later integration.
