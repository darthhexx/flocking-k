# Milestone 8: Realism Ladder Decision Report

**Verdict: NO-GO**

**Research direction: STOP_AT_FIRST_FAILED_REALISM_LAYER_AND_REDESIGN**

The held-out matrix uses 12 common-random-number seeds (4500–4511), ten ordered scenarios, four frozen M7 policies, and paired bootstrap 95% intervals. No M7 policy threshold is retuned in this milestone.

## Core transfer gates

| Gate | Result |
|---|---|
| m7 equal reference safety preserved | PASS |
| m7 transient reference resolves | PASS |
| all realism layers noninferior and safe | FAIL |
| overall decision loss beats temporal | FAIL |
| bursty delivery is material but connected | PASS |
| asynchronous messages are materially stale | PASS |
| nonlinear measurement calibration is credible | PASS |
| strategic alternative is represented | PASS |
| dynamic outage is exercised | PASS |
| composite stress retains bounded wrong actions | PASS |
| deterministic trace replay verified | PASS |
| communication overhead under 2 percent | PASS |
| runtime overhead under 50 percent | PASS |
| movement overhead under 30 percent | PASS |

## Investigation ablation gates

| Gate | Result |
|---|---|
| investigation reduces decision loss | FAIL |
| investigation increases information gain | FAIL |

The no-investigation arm makes exactly the same truth-blind output decisions and pays the same decision costs; only investigative motion is disabled. Therefore its paired difference isolates the downstream effect of that motion within this simulator.

## Realism ladder

| Scenario | Layer | Active loss | Temporal loss | Transfer vs active reference (95% CI) | Wrong action | Coverage | Delivery | Age |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| persistent_equal_reference | PASS | 1.3715 | 3.2923 | reference | 0.009 | 0.958 | 1.000 | 0.00 |
| transient_reference | PASS | 0.9523 | 0.7151 | reference | 0.008 | 0.964 | 1.000 | 0.00 |
| bursty_links | PASS | 0.9405 | 0.7931 | 0.0118 ([-0.0283, 0.0470]) | 0.007 | 0.965 | 0.785 | 0.00 |
| asynchronous_delay | PASS | 0.9393 | 0.9376 | 0.0130 ([-0.0222, 0.0485]) | 0.006 | 0.962 | 1.000 | 2.67 |
| nonlinear_range_bearing | PASS | 0.4019 | 0.0702 | 0.5503 ([0.5157, 0.5879]) | 0.005 | 0.981 | 1.000 | 0.00 |
| heterogeneous_sensors | PASS | 0.8862 | 0.7094 | 0.0661 ([-0.0363, 0.1563]) | 0.009 | 0.955 | 1.000 | 0.00 |
| drifting_bias_recovery | PASS | 0.5802 | 0.5802 | 0.3721 ([0.3437, 0.4071]) | 0.001 | 0.974 | 1.000 | 0.00 |
| colluding_ramp_attack | PASS | 0.6764 | 0.8282 | 0.2759 ([0.2376, 0.3187]) | 0.024 | 0.915 | 1.000 | 0.00 |
| dynamic_topology | FAIL | 0.9885 | 0.8132 | -0.0362 ([-0.3112, 0.1392]) | 0.010 | 0.942 | 1.000 | 0.00 |
| composite_stress | PASS | 0.4465 | 0.3483 | 0.5058 ([0.4013, 0.5940]) | 0.018 | 0.925 | 0.790 | 2.04 |

## Causal investigation result

| Outcome | No-investigation | Active | Improvement | 95% CI |
|---|---:|---:|---:|---:|
| Decision loss | 0.8231 | 0.8183 | 0.0048 | [-0.0032, 0.0135] |
| Information gain | 4.1471 | 4.1492 | 0.0021 | [-0.0008, 0.0051] |

## Interpretation

The frozen system fails at dynamic_topology. Later layers are diagnostic only; redesign must begin there before promotion.

This suite is a simulator result, not external validity. Strategic behaviour follows declared attack schedules rather than an adaptive adversary, and the range–bearing conversion is a local Gaussian approximation.
