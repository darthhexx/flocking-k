# M9B Decision-Relevant Active-Sensing Report

**Verdict: M9B-GO**

**Research direction: ADVANCE_VOI_TO_PRODUCTION_STACK_INTEGRATION_AFTER_M9A**

The suite uses 10 paired seeds (9000–9009) per scenario. All policies receive the same truth draw and standardized range noise. The oracle is a truth-blind exhaustive finite-horizon action-sequence comparator, not a clairvoyant policy.

## Gates

| Gate | Result |
|---|---|
| passive control remains ambiguous | PASS |
| finite horizon oracle has attainable gain | PASS |
| receding voi beats current allocator | PASS |
| receding voi beats passive | PASS |
| nonmyopic planning beats myopic | PASS |
| receding voi resolves safely | PASS |
| receding voi is calibrated noninferior | PASS |
| receding voi reduces movement cost | PASS |
| competing view policy is identified | PASS |
| runtime is bounded | PASS |
| trace replay verified | PASS |

## Overall policy results

| Policy | Resolved | Wrong | Resolution | Loss | Decision | Movement cost | Brier | Probe fraction | Spread fraction | Runtime |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| passive | 0.000 | 0.000 | 10.00 | 2.5000 | 2.5000 | 0.0000 | 0.6581 | 0.000 | 0.000 | 0.0005 |
| round_robin | 1.000 | 0.000 | 2.20 | 2.0860 | 0.3000 | 1.7860 | 0.0000 | 0.000 | 1.000 | 0.0001 |
| myopic_voi | 0.000 | 0.000 | 10.00 | 2.5000 | 2.5000 | 0.0000 | 0.6581 | 0.000 | 0.000 | 0.0042 |
| receding_horizon_voi | 1.000 | 0.000 | 2.78 | 1.5105 | 0.4450 | 1.0655 | 0.0000 | 0.331 | 0.374 | 0.0102 |
| computational_oracle | 1.000 | 0.000 | 2.86 | 1.3621 | 0.4650 | 0.8971 | 0.0000 | 0.392 | 0.280 | 0.0807 |

## Receding-horizon effects

| Baseline | Scope | Decision-loss improvement | 95% CI |
|---|---|---:|---:|
| passive | overall | 0.9895 | [0.8517, 1.1079] |
| passive | asymmetric_transit | 1.0809 | [0.8663, 1.2613] |
| passive | four_mode_cross | 1.0934 | [0.8390, 1.2740] |
| passive | four_mode_skewed_cost | 0.8388 | [0.6505, 1.0266] |
| passive | near_pair_rare_distractor | 0.6571 | [0.3845, 0.9460] |
| passive | triad_uniform | 1.2775 | [1.0572, 1.5473] |
| round_robin | overall | 0.5755 | [0.4829, 0.6732] |
| round_robin | asymmetric_transit | 0.5770 | [0.3322, 0.8043] |
| round_robin | four_mode_cross | 0.4708 | [0.3225, 0.6093] |
| round_robin | four_mode_skewed_cost | 0.7833 | [0.3193, 1.2927] |
| round_robin | near_pair_rare_distractor | 0.6218 | [0.3584, 0.8870] |
| round_robin | triad_uniform | 0.4245 | [0.2259, 0.6289] |
| myopic_voi | overall | 0.9895 | [0.8553, 1.1031] |
| myopic_voi | asymmetric_transit | 1.0809 | [0.9021, 1.2945] |
| myopic_voi | four_mode_cross | 1.0934 | [0.8476, 1.3006] |
| myopic_voi | four_mode_skewed_cost | 0.8388 | [0.6509, 1.0297] |
| myopic_voi | near_pair_rare_distractor | 0.6571 | [0.3603, 0.9387] |
| myopic_voi | triad_uniform | 1.2775 | [1.0129, 1.5023] |

## Interpretation boundary

M9B tests decision-relevant view allocation in a static, centralized Bayesian mode-classification assay. It does not repair the M8 dynamic-topology failure, does not establish decentralized execution, and cannot enter the production stack until M9A qualifies outage/rejoin and partition uncertainty.
