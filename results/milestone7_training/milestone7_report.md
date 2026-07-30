# Milestone 7: Hypothesis-Output Policy Decision Report

**Verdict: GO**

**Research direction: ADVANCE_OUTPUT_POLICY_TO_REALISM_LADDER**

This evaluation uses 30 seeds (0–29), eight scenarios, five truth-blind output policies, common random numbers, and paired bootstrap 95% confidence intervals. The declared deferral cost is 0.75 position-error units per cycle.

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
| flocking_robust_multiflock | 1.1842 | 0.7377 | 0.4465 | [0.2402, 0.6667] |
| flocking_robust_temporal | 0.9377 | 0.7377 | 0.2000 | [0.0752, 0.3252] |
| flocking_robust_mixture | 1.2872 | 0.7377 | 0.5495 | [0.5412, 0.5572] |
| flocking_robust_defer | 1.3268 | 0.7377 | 0.5891 | [0.5855, 0.5927] |

## Active-policy scenario behaviour

| Scenario | Decision loss | Abstain | Investigate | Material wrong-mode action | Flocks | Resolution steps |
|---|---:|---:|---:|---:|---:|---:|
| no_change | 0.5675 | 0.000 | 0.000 | 0.000 | 1.00 | 1.0 |
| mixed_dropout | 0.5924 | 0.000 | 0.000 | 0.000 | 1.00 | — |
| communication_delay | 0.6167 | 0.000 | 0.000 | 0.000 | 1.00 | — |
| biased_agents | 0.5874 | 0.000 | 0.000 | 0.001 | 1.03 | 1.4 |
| byzantine_agent | 0.5940 | 0.000 | 0.000 | 0.000 | 1.00 | — |
| multimodal_unequal | 0.6050 | 0.024 | 0.024 | 0.013 | 2.68 | 158.2 |
| multimodal_equal | 1.3772 | 0.977 | 0.053 | 0.009 | 2.00 | 159.4 |
| multimodal_transient | 0.9613 | 0.438 | 0.066 | 0.011 | 1.49 | 76.6 |

## Deferral-cost sensitivity

The table reports the smallest active-policy improvement against any baseline at each counterfactual deferral cost.

| Deferral cost | Smallest improvement | Smallest lower 95% bound |
|---:|---:|---:|
| 0.25 | 0.1790 | 0.1695 |
| 0.50 | 0.2450 | 0.1210 |
| 1.00 | 0.1551 | 0.0310 |
| 1.50 | 0.0651 | -0.0550 |

## Interpretation

The active policy passed every gate. It may advance to the realism ladder while retaining explicit set output as its ambiguity fallback.

The selector receives flock states, covariances, weights, and its own history only. Fault identities and truth are used solely after each action to score evaluation metrics. Persistent equal evidence is expected to remain deferred; forced resolution would be scientifically invalid.
