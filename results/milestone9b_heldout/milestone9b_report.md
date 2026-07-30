# M9B Decision-Relevant Active-Sensing Report

**Verdict: M9B-GO**

**Research direction: ADVANCE_VOI_TO_PRODUCTION_STACK_INTEGRATION_AFTER_M9A**

The suite uses 100 paired seeds (10000–10099) per scenario. All policies receive the same truth draw and standardized range noise. The oracle is a truth-blind exhaustive finite-horizon action-sequence comparator, not a clairvoyant policy.

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
| passive | 0.000 | 0.000 | 10.00 | 2.5000 | 2.5000 | 0.0000 | 0.6333 | 0.000 | 0.000 | 0.0002 |
| round_robin | 1.000 | 0.000 | 2.15 | 2.0124 | 0.2880 | 1.7244 | 0.0000 | 0.000 | 1.000 | 0.0001 |
| myopic_voi | 0.000 | 0.000 | 10.00 | 2.5000 | 2.5000 | 0.0000 | 0.6333 | 0.000 | 0.000 | 0.0039 |
| receding_horizon_voi | 1.000 | 0.000 | 2.58 | 1.4387 | 0.3960 | 1.0427 | 0.0000 | 0.337 | 0.413 | 0.0094 |
| computational_oracle | 1.000 | 0.002 | 2.65 | 1.2753 | 0.4155 | 0.8598 | 0.0040 | 0.429 | 0.302 | 0.0749 |

## Receding-horizon effects

| Baseline | Scope | Movement-inclusive loss improvement | 95% CI |
|---|---|---:|---:|
| passive | overall | 1.0613 | [1.0322, 1.0911] |
| passive | asymmetric_transit | 1.3107 | [1.2588, 1.3596] |
| passive | four_mode_cross | 1.0725 | [1.0190, 1.1256] |
| passive | four_mode_skewed_cost | 0.9254 | [0.8660, 0.9822] |
| passive | near_pair_rare_distractor | 0.6783 | [0.5941, 0.7599] |
| passive | triad_uniform | 1.3197 | [1.2682, 1.3681] |
| round_robin | overall | 0.5737 | [0.5293, 0.6196] |
| round_robin | asymmetric_transit | 0.5911 | [0.5376, 0.6465] |
| round_robin | four_mode_cross | 0.5527 | [0.4495, 0.6545] |
| round_robin | four_mode_skewed_cost | 0.8205 | [0.6882, 0.9632] |
| round_robin | near_pair_rare_distractor | 0.4697 | [0.3601, 0.5854] |
| round_robin | triad_uniform | 0.4346 | [0.3788, 0.4897] |
| myopic_voi | overall | 1.0613 | [1.0312, 1.0899] |
| myopic_voi | asymmetric_transit | 1.3107 | [1.2589, 1.3609] |
| myopic_voi | four_mode_cross | 1.0725 | [1.0194, 1.1226] |
| myopic_voi | four_mode_skewed_cost | 0.9254 | [0.8665, 0.9836] |
| myopic_voi | near_pair_rare_distractor | 0.6783 | [0.5964, 0.7628] |
| myopic_voi | triad_uniform | 1.3197 | [1.2662, 1.3705] |

## Interpretation boundary

M9B tests decision-relevant view allocation in a static, centralized Bayesian mode-classification assay. It does not repair the M8 dynamic-topology failure, does not establish decentralized execution, and cannot enter the production stack until M9A qualifies outage/rejoin and partition uncertainty.
