# Milestone 7: Hypothesis-Output Policy Decision Report

**Verdict: INCONCLUSIVE**

**Research direction: REFINE_M7_ON_TRAINING_SEEDS_ONLY**

This evaluation uses 10 seeds (0–9), eight scenarios, five truth-blind output policies, common random numbers, and paired bootstrap 95% confidence intervals. The declared deferral cost is 0.75 position-error units per cycle.

## Decision gates

| Gate | Result |
|---|---|
| overall decision loss beats all baselines | FAIL |
| decision survives defer cost range 0.25 to 1.00 | FAIL |
| nominal noninferior within 0.02 | PASS |
| dropout noninferior within 0.03 | PASS |
| delay noninferior within 0.03 | PASS |
| bias noninferior within 0.03 | PASS |
| byzantine noninferior within 0.03 | PASS |
| equal mode beats mixture | PASS |
| equal mode noninferior to defer within 0.10 | PASS |
| equal mode abstains without wrong selection | PASS |
| unequal mode selects without wrong mode | PASS |
| transient mode resolves | PASS |
| m6 mode survival preserved | PASS |
| m6 bias calibration preserved | PASS |
| false quarantine is bounded | PASS |
| communication overhead under 2% | PASS |
| runtime overhead under 50% | PASS |
| movement overhead under 15% | PASS |

## Overall policy comparison

| Baseline | Baseline loss | Active loss | Improvement | 95% CI |
|---|---:|---:|---:|---:|
| flocking_robust_multiflock | 1.1512 | 0.7400 | 0.4112 | [0.0463, 0.7941] |
| flocking_robust_temporal | 0.9562 | 0.7400 | 0.2162 | [-0.0089, 0.4559] |
| flocking_robust_mixture | 1.2843 | 0.7400 | 0.5443 | [0.5294, 0.5594] |
| flocking_robust_defer | 1.3289 | 0.7400 | 0.5889 | [0.5838, 0.5947] |

## Active-policy scenario behaviour

| Scenario | Decision loss | Abstain | Investigate | Wrong-mode selection | Flocks | Resolution steps |
|---|---:|---:|---:|---:|---:|---:|
| no_change | 0.5606 | 0.000 | 0.000 | 0.000 | 1.00 | — |
| mixed_dropout | 0.6036 | 0.000 | 0.000 | 0.000 | 1.00 | — |
| communication_delay | 0.6123 | 0.000 | 0.000 | 0.000 | 1.00 | — |
| biased_agents | 0.5871 | 0.000 | 0.000 | 0.001 | 1.02 | 1.1 |
| byzantine_agent | 0.6006 | 0.000 | 0.000 | 0.000 | 1.00 | — |
| multimodal_unequal | 0.6062 | 0.024 | 0.024 | 0.015 | 2.67 | 155.5 |
| multimodal_equal | 1.3835 | 0.976 | 0.053 | 0.010 | 2.00 | 159.4 |
| multimodal_transient | 0.9663 | 0.439 | 0.066 | 0.010 | 1.49 | 76.8 |

## Deferral-cost sensitivity

The table reports the smallest active-policy improvement against any baseline at each counterfactual deferral cost.

| Deferral cost | Smallest improvement | Smallest lower 95% bound |
|---:|---:|---:|
| 0.25 | 0.1789 | 0.0899 |
| 0.50 | 0.2612 | 0.0404 |
| 1.00 | 0.1713 | -0.0461 |
| 1.50 | 0.0813 | -0.1310 |

## Interpretation

The policy is not yet promotable. Refinement must use disjoint training seeds before another held-out evaluation.

The selector receives flock states, covariances, weights, and its own history only. Fault identities and truth are used solely after each action to score evaluation metrics. Persistent equal evidence is expected to remain deferred; forced resolution would be scientifically invalid.
