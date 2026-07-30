# M9A.6 missing-evidence posterior and pricing report

**Verdict: `M9A6-NO-GO`**

Phase: `heldout`. Seeds: `14000`–`14099` (100 paired seeds per scenario).

M9A.6 is an output-only overlay on the frozen M9A physical controller. It marginalizes declared missing-agent assignments, preserves posterior-predictive model-mismatch mass as residual unknown support, and prices select/mixture/defer actions by expected risk. The observer/global references and truth scoring remain outside the policy.

## Gates

| Gate | Result |
|---|---:|
| replay | PASS |
| exact_model_loss_improvement_every_scenario | PASS |
| observer_regret | FAIL |
| wrong_action_safety | PASS |
| calibration | PASS |
| nominal_residual_specificity | PASS |
| off_model_residual_response | PASS |
| frozen_motion | PASS |
| asymmetric_information_boundary | PASS |

## Exact-model topology scenarios

| Scenario | Current | M9A.6 | Improvement LCB | Observer | Regret UCB | Global | Frozen-set floor | Residual | Defer | Wrong | NEES | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| stable_control | 0.939 | 0.276 | 0.655 | 0.273 | 0.005 | 0.273 | 0.577 | 0.013 | 0.001 | 0.000 | 1.75 | 0.968 |
| failure_only | 1.062 | 0.329 | 0.709 | 0.293 | 0.043 | 0.292 | 0.609 | 0.017 | 0.009 | 0.000 | 1.76 | 0.968 |
| partition_only | 1.046 | 0.372 | 0.653 | 0.347 | 0.031 | 0.271 | 0.615 | 0.023 | 0.031 | 0.000 | 1.74 | 0.967 |
| asymmetric_partition | 1.061 | 0.409 | 0.629 | 0.370 | 0.047 | 0.271 | 0.629 | 0.026 | 0.050 | 0.000 | 1.73 | 0.967 |
| failure_partition | 1.192 | 0.451 | 0.681 | 0.351 | 0.157 | 0.292 | 0.696 | 0.025 | 0.040 | 0.000 | 1.70 | 0.970 |
| staggered_rejoin | 1.029 | 0.325 | 0.669 | 0.308 | 0.020 | 0.307 | 0.610 | 0.016 | 0.005 | 0.000 | 1.77 | 0.967 |
| flapping_reconnect | 0.954 | 0.313 | 0.631 | 0.301 | 0.014 | 0.272 | 0.582 | 0.017 | 0.012 | 0.000 | 1.74 | 0.968 |
| false_split_dropout | 0.998 | 0.282 | 0.705 | 0.278 | 0.005 | 0.271 | 0.576 | 0.014 | 0.002 | 0.000 | 1.75 | 0.968 |

## Off-model challenges

| Scenario | Current | M9A.6 | Residual | Peak residual | Defer | Wrong |
|---|---:|---:|---:|---:|---:|---:|
| unmodelled_count | 0.639 | 0.895 | 0.402 | 0.996 | 0.498 | 0.000 |
| unmodelled_offset | 0.937 | 0.984 | 0.132 | 0.490 | 0.452 | 0.000 |

## Boundary

A held-out GO authorizes M9B integration research, not production deployment. It does not change M9A.4, does not claim the declared assignment family is complete, and does not make component-local information equal ideal-global information. Residual mass must remain explicit in every later integration.
