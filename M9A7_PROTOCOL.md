# M9A.7 preregistered split-admission protocol

Status: candidate and gates frozen after positive-control development and the M9A.7 training run, before opening the held-out split. Development smoke seeds `15900–15901` are excluded from both formal splits.

## Research question

Can a split trust boundary repair admission-censored missingness without weakening M9A.6 calibration, wrong-action safety, model-mismatch response, or the M6 quarantine boundary?

The candidate is an output-only shadow on the unchanged `flocking_topology_resilient` physical trajectory. It receives no target truth, realized future noise, or seeded fault identity. Fresh measurements and recursively fused beliefs use separate eligibility channels:

- shared beliefs retain robust-source trust, lifecycle probation, component reachability, and merge handling;
- fresh measurements require current availability, operational status, and observer-component reachability, but do not inherit M6 belief suspicion/quarantine or lifecycle admission because a current sample has no recursive fusion lineage; the raw channel is instead bounded by covariance flooring, the declared assignment likelihood, posterior-predictive mismatch mass, the wrong-risk ceiling, and the preregistered colluding-ramp attack gate;
- covariance eigenvalues on the fresh channel are floored at `0.25 ×` the contemporaneous median reachable-source floor;
- catastrophic posterior-predictive incompatibility is gated only above NIS `100`, so contradictory but plausible rejoin evidence can reopen assignment support;
- admission-specific residual mass is reserved for the intersection of lifecycle censoring and source quarantine. Reachability, lifecycle censoring, source exclusion, covariance flooring, and inferred secondary-source probabilities remain separately observable.

The M9A.6 assignment family, model-mismatch residual, credible-set policy, wrong-risk ceiling, and decision loss are otherwise unchanged.

## Fixed scenarios

The exact-model set contains the eight M9A scenarios plus `admission_censoring_control`. The positive control fails three agents, recovers them into a 40-cycle probation window, and applies seven short partition/reconnect events; it must create common lifecycle censoring while valid raw measurements remain available.

Two existing off-model scenarios are retained unchanged:

- actual secondary-source count three versus assumed count four;
- actual secondary offset `(6.5, -2.0)` versus assumed `(5.0, -4.0)`.

The new `raw_channel_colluding_ramp` challenge has three declared secondary sources and three strategic sources. The strategic sources fail and rejoin together, ramp a shared offset, and report covariance at `0.05 ×` its physical value while belief admission remains under a 35-cycle probation. This scenario is a safety challenge, not an exact-model accuracy claim.

## Splits and power

- Training: seeds `15000–15059`, 60 paired seeds per scenario.
- Held-out: seeds `16000–16299`, 300 paired seeds per scenario.
- Bootstrap: 5,000 paired resamples with the suite's fixed RNG seed.

For a tail event with frequency `p = 0.02`, the minimum sample size giving at least 95% probability of observing one or more events is

`ceil(log(1 - 0.95) / log(1 - 0.02)) = 149`.

The 300-seed held-out set gives probability `1 - 0.98^300 = 0.99767` of observing at least one such event. Training is deliberately not promotion-powered.

## Frozen gates

All gates must pass. Thresholds may not be weakened after either run.

1. Every exogenous trace fingerprint replays.
2. Held-out seed count is at least 149.
3. Positive control has at least 0.50 mean belief-censored fresh sources and censoring on at least 20% of steps.
4. Positive-control M9A.6-minus-M9A.7 decision-loss improvement has 95% LCB greater than zero.
5. Each natural M9A scenario has M9A.6-minus-M9A.7 decision-loss LCB greater than `-0.02`.
6. Every exact scenario has mean observer-regret 95% UCB at most `0.10`.
7. Every natural M9A scenario has observer-regret P95 bootstrap UCB at most `0.20`.
8. Every natural M9A scenario has per-seed observer regret at most `0.75`.
9. Every scenario has material wrong-mode action rate at most `0.01`.
10. Every exact scenario has mean NEES at most `6.0`, mean per-run P95 NEES at most `20.0`, and 95% coverage at least `0.88`.
11. Both off-model challenges have mean residual mass at least `0.08`, and at least one has abstention rate at least `0.25`.
12. In the colluding-ramp challenge, M9A.7 does not increase wrong-action rate or quarantine rate relative to M9A.6, and covariance flooring activates on at least 10% of cycles.
13. Mean and standard deviation of candidate-minus-frozen movement distance are at most `1e-12` in magnitude.

Passing authorizes an M9A/M9B integration experiment. It does not revise the original M9A or M9A.6 verdict, relax an earlier gate, or authorize production use.

## Standing analysis

The M9B movement-cost counterfactual is analysis-only: saved action traces are repriced at scales `0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.50, 0.75, 1, 1.5, 2, 3, 4`. Counterfactual first-action planning is reported separately and cannot alter the fixed-action result or the original M9B verdict.
