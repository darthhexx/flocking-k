# Milestone 7: Hypothesis-Output Policy Decision Report

**Verdict: GO**

**Research direction: ADVANCE_OUTPUT_POLICY_TO_REALISM_LADDER**

This evaluation uses 100 seeds (4000–4099), eight scenarios, five truth-blind output policies, common random numbers, and paired bootstrap 95% confidence intervals. The declared deferral cost is 0.75 position-error units per cycle.

## Decision gates

| Gate | Result |
|---|---|
| overall decision loss beats all baselines | PASS |
| decision survives defer cost range 0.25 to 1.00 | PASS |
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
| flocking_robust_multiflock | 1.1128 | 0.7377 | 0.3751 | [0.2681, 0.4867] |
| flocking_robust_temporal | 0.9076 | 0.7377 | 0.1699 | [0.0998, 0.2403] |
| flocking_robust_mixture | 1.2865 | 0.7377 | 0.5489 | [0.5454, 0.5524] |
| flocking_robust_defer | 1.3269 | 0.7377 | 0.5892 | [0.5870, 0.5913] |

## Active-policy scenario behaviour

| Scenario | Decision loss | Abstain | Investigate | Material wrong-mode action | Flocks | Resolution steps |
|---|---:|---:|---:|---:|---:|---:|
| no_change | 0.5793 | 0.000 | 0.000 | 0.000 | 1.00 | 1.0 |
| mixed_dropout | 0.5976 | 0.000 | 0.000 | 0.000 | 1.00 | 1.0 |
| communication_delay | 0.6095 | 0.000 | 0.000 | 0.000 | 1.00 | — |
| biased_agents | 0.5856 | 0.000 | 0.000 | 0.001 | 1.02 | 1.7 |
| byzantine_agent | 0.5894 | 0.000 | 0.000 | 0.000 | 1.00 | 1.0 |
| multimodal_unequal | 0.6113 | 0.025 | 0.025 | 0.013 | 2.69 | 158.0 |
| multimodal_equal | 1.3729 | 0.977 | 0.053 | 0.007 | 2.00 | 159.2 |
| multimodal_transient | 0.9555 | 0.438 | 0.064 | 0.009 | 1.49 | 76.8 |

## Deferral-cost sensitivity

The table reports the smallest active-policy improvement against any baseline at each counterfactual deferral cost.

| Deferral cost | Smallest improvement | Smallest lower 95% bound |
|---:|---:|---:|
| 0.25 | 0.1792 | 0.1769 |
| 0.50 | 0.2149 | 0.1469 |
| 1.00 | 0.1249 | 0.0575 |
| 1.50 | 0.0349 | -0.0327 |

## Interpretation

The active policy passed every gate. It may advance to the realism ladder while retaining explicit set output as its ambiguity fallback.

The selector receives flock states, covariances, weights, and its own history only. Fault identities and truth are used solely after each action to score evaluation metrics. Persistent equal evidence is expected to remain deferred; forced resolution would be scientifically invalid.
