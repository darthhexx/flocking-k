# Milestone 8: Realism Ladder Decision Report

**Verdict: NO-GO**

**Research direction: STOP_AT_FIRST_FAILED_REALISM_LAYER_AND_REDESIGN**

The held-out matrix uses 100 common-random-number seeds (5000–5099), ten ordered scenarios, four frozen M7 policies, and paired bootstrap 95% intervals. No M7 policy threshold is retuned in this milestone.

## Core transfer gates

| Gate | Result |
|---|---|
| m7 equal reference safety preserved | PASS |
| m7 transient reference resolves | PASS |
| all realism layers noninferior and safe | FAIL |
| overall decision loss beats temporal | PASS |
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
| investigation increases information gain | PASS |

The no-investigation arm makes exactly the same truth-blind output decisions and pays the same decision costs; only investigative motion is disabled. Therefore its paired difference isolates the downstream effect of that motion within this simulator.

## Realism ladder

| Scenario | Layer | Active loss | Temporal loss | Transfer vs active reference (95% CI) | Wrong action | Coverage | Delivery | Age |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| persistent_equal_reference | PASS | 1.3740 | 3.3315 | reference | 0.008 | 0.962 | 1.000 | 0.00 |
| transient_reference | PASS | 0.9506 | 0.8952 | reference | 0.008 | 0.963 | 1.000 | 0.00 |
| bursty_links | PASS | 0.9566 | 0.9085 | -0.0059 ([-0.0189, 0.0063]) | 0.009 | 0.961 | 0.787 | 0.00 |
| asynchronous_delay | PASS | 0.9499 | 1.0465 | 0.0007 ([-0.0112, 0.0122]) | 0.008 | 0.964 | 1.000 | 2.59 |
| nonlinear_range_bearing | PASS | 0.3924 | 0.0648 | 0.5582 ([0.5478, 0.5687]) | 0.004 | 0.985 | 1.000 | 0.00 |
| heterogeneous_sensors | PASS | 0.8798 | 1.0169 | 0.0708 ([0.0446, 0.0960]) | 0.009 | 0.955 | 1.000 | 0.00 |
| drifting_bias_recovery | PASS | 0.5678 | 0.5678 | 0.3829 ([0.3709, 0.3954]) | 0.001 | 0.977 | 1.000 | 0.00 |
| colluding_ramp_attack | PASS | 0.6657 | 1.1684 | 0.2849 ([0.2702, 0.2991]) | 0.024 | 0.914 | 1.000 | 0.00 |
| dynamic_topology | FAIL | 1.1698 | 1.2090 | -0.2192 ([-0.3308, -0.1151]) | 0.012 | 0.910 | 1.000 | 0.00 |
| composite_stress | PASS | 0.5071 | 0.2871 | 0.4435 ([0.3881, 0.4960]) | 0.027 | 0.921 | 0.794 | 1.98 |

## Causal investigation result

| Outcome | No-investigation | Active | Improvement | 95% CI |
|---|---:|---:|---:|---:|
| Decision loss | 0.8394 | 0.8414 | -0.0020 | [-0.0052, 0.0011] |
| Information gain | 4.1379 | 4.1409 | 0.0030 | [0.0015, 0.0045] |

## Interpretation

The frozen system fails at dynamic_topology. Later layers are diagnostic only; redesign must begin there before promotion.

This suite is a simulator result, not external validity. Strategic behaviour follows declared attack schedules rather than an adaptive adversary, and the range–bearing conversion uses an exact moment match only for its declared independent Gaussian sensor noise.
