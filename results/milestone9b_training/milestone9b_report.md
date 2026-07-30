# M9B Decision-Relevant Active-Sensing Report

**Verdict: M9B-GO**

**Research direction: ADVANCE_VOI_TO_PRODUCTION_STACK_INTEGRATION_AFTER_M9A**

The suite uses 30 paired seeds (9000–9029) per scenario. All policies receive the same truth draw and standardized range noise. The oracle is a truth-blind exhaustive finite-horizon action-sequence comparator, not a clairvoyant policy.

## Gates

| Gate | Result |
|---|---|
| passive control remains ambiguous | PASS |
| finite horizon oracle has attainable gain | PASS |
| receding voi beats current allocator | PASS |
| receding voi beats passive | PASS |
| nonmyopic planning beats myopic | PASS |
| receding voi resolves safely | PASS |
| allocator gain generalizes across tasks | PASS |
| receding voi is calibrated noninferior | PASS |
| receding voi reduces movement cost | PASS |
| competing view policy is identified | PASS |
| runtime is bounded | PASS |
| trace replay verified | PASS |

## Overall policy results

| Policy | Resolved | Wrong | Resolution | Loss | Decision | Movement cost | Brier | Probe fraction | Spread fraction | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| passive | 0.000 | 0.000 | 10.00 | 2.5000 | 2.5000 | 0.0000 | 0.6896 | 0.000 | 0.000 | 0.0002 |
| round_robin | 1.000 | 0.000 | 2.19 | 2.0623 | 0.2967 | 1.7656 | 0.0000 | 0.000 | 1.000 | 0.0001 |
| myopic_voi | 0.000 | 0.000 | 10.00 | 2.5000 | 2.5000 | 0.0000 | 0.6896 | 0.000 | 0.000 | 0.0038 |
| receding_horizon_voi | 1.000 | 0.000 | 2.62 | 1.4501 | 0.4050 | 1.0451 | 0.0000 | 0.338 | 0.405 | 0.0094 |
| computational_oracle | 1.000 | 0.000 | 2.77 | 1.3278 | 0.4433 | 0.8845 | 0.0000 | 0.425 | 0.288 | 0.0769 |

## Receding-horizon effects

| Baseline | Scope | Movement-inclusive loss improvement | 95% CI |
|---|---|---:|---:|
| passive | overall | 1.0499 | [0.9826, 1.1163] |
| passive | asymmetric_transit | 1.1823 | [1.0793, 1.2759] |
| passive | four_mode_cross | 1.0780 | [0.9698, 1.1819] |
| passive | four_mode_skewed_cost | 0.8961 | [0.7847, 1.0088] |
| passive | near_pair_rare_distractor | 0.7841 | [0.6359, 0.9367] |
| passive | triad_uniform | 1.3091 | [1.2092, 1.4053] |
| round_robin | overall | 0.6122 | [0.5447, 0.6827] |
| round_robin | asymmetric_transit | 0.6783 | [0.5347, 0.8344] |
| round_robin | four_mode_cross | 0.5044 | [0.3521, 0.6675] |
| round_robin | four_mode_skewed_cost | 0.8407 | [0.5838, 1.1042] |
| round_robin | near_pair_rare_distractor | 0.5531 | [0.3739, 0.7433] |
| round_robin | triad_uniform | 0.4846 | [0.3832, 0.5905] |
| myopic_voi | overall | 1.0499 | [0.9805, 1.1165] |
| myopic_voi | asymmetric_transit | 1.1823 | [1.0768, 1.2772] |
| myopic_voi | four_mode_cross | 1.0780 | [0.9669, 1.1850] |
| myopic_voi | four_mode_skewed_cost | 0.8961 | [0.7847, 1.0140] |
| myopic_voi | near_pair_rare_distractor | 0.7841 | [0.6320, 0.9272] |
| myopic_voi | triad_uniform | 1.3091 | [1.2042, 1.4075] |

## Interpretation boundary

M9B tests decision-relevant view allocation in a static, centralized Bayesian mode-classification assay. It does not repair the M8 dynamic-topology failure, does not establish decentralized execution, and cannot enter the production stack until M9A qualifies outage/rejoin and partition uncertainty.
