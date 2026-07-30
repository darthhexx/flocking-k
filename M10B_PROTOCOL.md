# M10B preregistered decentralized allocation protocol

Status: protocol, ownership rules, scenarios, splits, and gates are frozen
before formal training. M10B may train while M10A.5 held-out is running, but
held-out is invalid unless the frozen M10A.5 result is `M10A5-GO`.

## Research question

Can per-agent sensing-action ownership with bounded local planner messages and
asynchronous replanning match the component-centralized M10A.5 planner under
partitions, outage/rejoin, source competition, and raw-channel attack?

## Planner

Each operational agent owns only its own extra sensing goal. It may use:

- the current component assignment posterior already available to M9C;
- its own assignment marginal and source-trust value;
- proposal tuples received from current topological neighbours;
- its own retained action and message age.

It may not read truth, seeded fault identity, future observations, or a
component-wide action list. A proposal contains four scalar fields:
`priority`, `agent_id`, `proposal_kind`, and `local_epoch`. On its asynchronous
replan phase, an agent activates only if its proposal is among the locally
allowed winners in its closed neighbourhood. Ties use stable agent identity.
The action persists until that agent's next phase. Partitioned edges carry no
planner messages.

Trusted-sensor verification has priority over ordinary assignment probing while
a local trust alert exists. Alerted sensors cannot win verification ownership.

## Arms

1. `centralized_trust`: frozen M10A.5 closed-loop controller.
2. `decentralized_no_negotiation`: per-agent asynchronous proposals without
   local winner resolution.
3. `decentralized_negotiated`: the full local negotiation protocol.

## Scenarios and splits

1. stable control;
2. failure plus partition;
3. flapping reconnect;
4. admission-censoring control;
5. source-assignment competition;
6. genuine target manoeuvre;
7. canonical raw-channel rejoin/ramp attack;
8. temporary attack followed by honest recovery.

- Training: seeds `24000`–`24039`, 40 per scenario.
- Held-out: seeds `25000`–`25149`, 150 per scenario.
- Bootstrap: 5,000 paired resamples.

## Frozen gates

1. Every exogenous trace replays and frozen M9C/M10A/M10A.5 hashes match.
2. Held-out contains at least 149 paired seeds per scenario.
3. Centralized compatibility reproduces frozen M10A.5 on an audit subset.
4. Negotiated ownership violations are zero.
5. Planner messages never exceed one four-scalar proposal per delivered
   directed neighbour edge on a sender's replan phase.
6. Stable-control centralized-minus-negotiated integrated-loss LCB is at least
   `-0.03`.
7. Every natural topology control has integrated-loss LCB at least `-0.05`.
8. Source-competition integrated-loss LCB is at least `-0.03`, and the
   decentralized action path is exercised on at least 2% of cycles.
9. All scenarios have wrong-action rate at most `0.01`, mean NEES at most `6`,
   mean run-level P95 NEES at most `20`, and coverage at least `0.88`.
10. Relative to centralized trust, delivery-ratio LCB is at least `-0.05` and
    mean component-count increase is at most `0.25`.
11. Canonical attack decision loss is at most `1.50`, strategic alert rate is
    at least `0.50`, and mean movement increase is at most `0.05` per step.
12. Temporary-attack trust recovery is at most 30 cycles and post-cessation
    decision loss is at most `1.50`.
13. Negotiation reduces either active-agent conflict rate or movement versus
    no negotiation without integrated-loss LCB below `-0.06`. This is an
    ablation-only margin; the stricter centralized-transfer gates remain
    unchanged.
14. Mean planner-state age is positive, action traces differ from centralized
    on at least 2% of source-competition cycles, and planner messages are
    nonzero.
15. Negotiated mean runtime is at most twice centralized runtime plus `0.10`
    seconds per trial.

Validity failure yields `M10B-INVALID`. Other failure yields `M10B-NO-GO`.
All gates passing yields `M10B-GO` for external replay research. Production is
never authorized.
