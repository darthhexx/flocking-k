# M9B movement-cost sensitivity

This is an analysis-only repricing of saved held-out actions. No action trace, posterior, or original M9B verdict was changed.

| Baseline | Analytic break-even scale | Scales with positive 95% LCB |
|---|---:|---|
| passive | 2.018 | 0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.5, 0.75, 1, 1.5 |
| round_robin | 0.158 | 0.2, 0.25, 0.5, 0.75, 1, 1.5, 2, 3, 4 |
| myopic_voi | 2.018 | 0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.5, 0.75, 1, 1.5 |

## Counterfactual first-action diagnostic

| Scenario | Myopic highest active scale | Receding highest active scale |
|---|---:|---:|
| triad_uniform | none | 2 |
| near_pair_rare_distractor | 0.05 | 1 |
| asymmetric_transit | none | 2 |
| four_mode_cross | none | 1.5 |
| four_mode_skewed_cost | none | 1 |

`movement_cost_planning_thresholds.csv` records every counterfactual first-action choice. These choices are diagnostic only and are not used in the fixed-action performance comparison.
