# M10A.5 preregistered closed-loop trust integration protocol

Status: protocol, intervention, scenarios, splits, and gates are frozen before
formal training. Historical M9C and M10A sources, artifacts, hashes, and verdicts
remain unchanged.

## Research question

Does the M10A combined trust defense retain its availability and calibration
benefits when its posterior changes M9C sensing motion and therefore changes
future observations?

M10A.5 uses the unchanged M9C receding-VOI experiment engine. A compatibility
harness replaces the per-run admission controller with the frozen M10A
combined controller. The trust-adjusted posterior is consumed by the unchanged
M9C planner. When a source is below the frozen trust-alert threshold, a bounded
verification override moves at most the existing `m9c_probe_agent_count`
currently trusted sensors toward the posterior target on the existing M9C
replan cadence. It never moves an alerted sensor for verification. Output,
motion, geometry, and later measurements therefore form a real causal feedback
loop. No controller receives truth, seeded fault identity, or future samples.

## Frozen arms

1. `m9c_receding`: unchanged M9C receding-VOI baseline.
2. `closed_loop_trust`: frozen M10A combined trust controller feeding the
   unchanged M9C receding-VOI planner plus the bounded trusted-sensor
   verification override.

The compatibility harness must restore every injected dependency after each
trial. An upstream audit must reproduce the recorded M9C and M10A source and
protocol hashes before either split is valid.

## Scenarios and splits

The seven M10A controls and four registered attack doses are retained. One
additional recovery challenge uses the canonical rejoin/ramp attack until step
`105`, after which all strategic sources become honest while retaining their
identities, topology history, and trust state.

- Training: seeds `22000`–`22039`, 40 paired seeds per scenario.
- Held-out: seeds `23000`–`23149`, 150 paired seeds per scenario.
- Bootstrap: 5,000 paired resamples with fixed suite RNG.

The 150-seed held-out split exceeds the 149-seed requirement for at least 95%
probability of observing an event with 2% frequency.

## Metrics

- decision loss and movement-inclusive loss;
- abstention and material wrong-action rate;
- mean and run-level P95 NEES and 95% coverage;
- M9C probe/spread/track actions and mean movement per step;
- strategic and non-strategic trust-alert rates;
- minimum and mean raw trust;
- trust recovery delay after the temporary attack ceases;
- delivery ratio, component count, and quarantine rate.

Movement-inclusive loss remains:

```text
integrated_loss = decision_loss
                + m9c_movement_cost_per_unit × movement_per_step
```

The availability ceiling remains independently derived as
`2 × output_defer_cost = 1.50`.

## Frozen gates

1. Every exogenous trace fingerprint replays.
2. Recorded M9C and M10A hashes, replay flags, and historical verdicts match.
3. Held-out contains at least 149 paired seeds per scenario.
4. The unchanged baseline compatibility run reproduces direct M9C output,
   movement, and action traces within `1e-12` on an audit subset.
5. In every control, baseline-minus-candidate integrated-loss LCB is at least
   `-0.03`.
6. In every control, non-strategic alert rate is at most `0.05`.
7. Every control has wrong-action rate at most `0.01`, mean NEES at most `6`,
   mean run-level P95 NEES at most `20`, and coverage at least `0.88`.
8. Admission-censoring, source-competition, genuine-manoeuvre, and legitimate
   heterogeneous-precision controls each retain noninferiority.
9. Every attack has decision loss at most `1.50`.
10. Canonical-attack baseline-minus-candidate decision-loss LCB is positive.
11. Every attack has wrong-action rate at most `0.01`, mean NEES at most `6`,
    mean run-level P95 NEES at most `20`, and coverage at least `0.88`.
12. Moderate, severe, and canonical strategic alert rate is at least `0.50`;
    mild alert rate is at least `0.25`.
13. M10A trust remains structurally separate from M6 quarantine, and the
    indirect quarantine-rate change caused by altered sensing geometry is at
    most `0.02`.
14. Attack feedback does not increase mean movement per step by more than
    `0.05`.
15. In the temporary-attack challenge, strategic trust recovers to at least
    `0.80` within 30 cycles of honest evidence, post-cessation false alert rate
    is at most `0.10`, and post-cessation loss is at most `1.50`.
16. The candidate retains a nonzero probe/spread action difference from the
    baseline in at least one attack scenario, establishing that the feedback
    path is exercised.

Validity failure yields `M10A5-INVALID`. Any other failure yields
`M10A5-NO-GO`. All gates passing yields `M10A5-GO` for decentralized research
only. Production is never authorized.
