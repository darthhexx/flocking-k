# M9A.5 dynamic-topology loss-floor diagnostic

**Diagnostic conclusion: `INFORMATION-LIMITED`**

This is a non-promotional diagnostic. It does not alter M9A's frozen parameters, original transfer gate, or `M9A-PARTIAL-GO` verdict.

Seeds: `12000`–`12099` (100 paired seeds per scenario). Every reference observed the same frozen M9A sensor trajectory.

## Nested references

- **Frozen M9A:** the operational output already evaluated in M9A.4.
- **Observer Bayes:** exact assignment marginalization under the declared four-of-eight secondary-mode model, using only raw measurements in the observer's current delivered weak component.
- **Global Bayes:** the same inference and action rule with every currently operational measurement delivered by an ideal out-of-band collector.
- **Hindsight set floor:** the closest frozen M9A hypothesis after truth is revealed. This is a genuine evaluation-only lower bound for that returned set, not an implementable policy.

Neither Bayesian arm sees target truth, future noise, or seeded fault identities before acting. They know the declared secondary-mode count, offset, and activation schedule. Their RMS-risk action rule is a model-informed reference rather than a proof of global Bayes optimality.

## Mean decision loss and original-margin transfer

| Scenario | M9A loss | Observer | Global | Set floor | Observer LCB | Global LCB | Floor LCB | Diagnosis |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| stable_control | 0.944 | 0.275 | 0.274 | 0.577 | — | — | — | `REFERENCE` |
| failure_only | 1.047 | 0.294 | 0.292 | 0.598 | -0.021 | -0.020 | -0.032 | `SAME_INFORMATION_POLICY_OR_REPRESENTATION_HEADROOM` |
| partition_only | 1.075 | 0.350 | 0.272 | 0.638 | -0.081 | 0.001 | -0.085 | `SAME_INFORMATION_POLICY_OR_REPRESENTATION_HEADROOM` |
| asymmetric_partition | 1.089 | 0.372 | 0.272 | 0.652 | -0.105 | 0.001 | -0.100 | `OBSERVER_COMPONENT_INFORMATION_LIMIT` |
| failure_partition | 1.162 | 0.354 | 0.292 | 0.665 | -0.085 | -0.020 | -0.134 | `SAME_INFORMATION_POLICY_OR_REPRESENTATION_HEADROOM` |
| staggered_rejoin | 1.009 | 0.310 | 0.309 | 0.595 | -0.038 | -0.037 | -0.059 | `SAME_INFORMATION_POLICY_OR_REPRESENTATION_HEADROOM` |
| flapping_reconnect | 0.967 | 0.303 | 0.273 | 0.591 | -0.031 | 0.000 | -0.023 | `CURRENT_POLICY_CLEARS_MARGIN` |
| false_split_dropout | 1.002 | 0.279 | 0.272 | 0.581 | -0.006 | 0.001 | -0.012 | `CURRENT_POLICY_CLEARS_MARGIN` |

The LCB columns are paired 95% bootstrap lower bounds for `stable loss − dynamic loss`; the unchanged M9A criterion passes only above `-0.10`.

## Decomposition gaps

Positive gaps mean the reference on the right has lower decision loss.

| Scenario | M9A − observer | Observer − global | M9A − global | M9A − set floor |
|---|---:|---:|---:|---:|
| stable_control | 0.669 | 0.001 | 0.670 | 0.366 |
| failure_only | 0.753 | 0.001 | 0.755 | 0.449 |
| partition_only | 0.725 | 0.077 | 0.803 | 0.436 |
| asymmetric_partition | 0.717 | 0.100 | 0.817 | 0.437 |
| failure_partition | 0.809 | 0.062 | 0.871 | 0.497 |
| staggered_rejoin | 0.699 | 0.002 | 0.701 | 0.415 |
| flapping_reconnect | 0.664 | 0.030 | 0.694 | 0.376 |
| false_split_dropout | 0.722 | 0.007 | 0.729 | 0.420 |

## Interpretation boundary

Observer-to-global differences isolate the value of ideal cross-component access under one shared inference model. Frozen-M9A-to-observer differences combine production representation, fusion, lifecycle, and action-rule costs while holding physical trajectories and the observer information boundary fixed. The hindsight-set floor tests only whether the frozen returned hypothesis set contains a low-error answer; it cannot prescribe a causal selector.

The diagnostic may justify a new, prospectively registered oracle-relative protocol. It cannot retroactively relax the failed M9A.4 gate or qualify M9B for integration.
