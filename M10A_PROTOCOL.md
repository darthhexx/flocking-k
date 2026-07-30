# M10A preregistered raw-channel adversarial-trust protocol

Status: protocol, parameters, scenarios, splits, and gates are frozen before the
training split is evaluated. M9A.7 and M9C artifacts, gates, and verdicts remain
historical and unchanged.

## Research question

Can a causal trust layer prevent coherent raw-channel colluders from denying
decision service while retaining M9A.7's legitimate alternative modes and
M9C's natural-scenario calibration?

M10A is an output-layer security assay on the frozen M9C receding-VOI physical
trajectory. Every arm receives the same observations, admission masks,
topology, motion, and random trace. The candidate may change only the
measurement covariance and residual support supplied to a fresh
assignment-posterior replica. It receives no truth, fault identity, future
sample, or seed. A GO authorizes later closed-loop integration; it does not
authorize production.

## Threat and service model

The adversary controls a declared subset of raw sources, supplies a coherent
time-varying offset, and understates covariance. It does not alter the
communication graph, other agents, or evaluation truth. Integrity, calibration,
availability, and false exclusion are separate outcomes:

- material wrong point selections measure output integrity;
- NEES and coverage measure estimator consistency;
- decision loss and abstention measure service availability;
- trust alerts on non-strategic sources measure false exclusion;
- precision share measures raw-only posterior influence.

The absolute availability ceiling is derived from the existing decision-cost
model rather than fitted to the attack:

```text
availability_loss_max = 2 × output_defer_cost = 2 × 0.75 = 1.50
```

One defer-cost unit prices the missing point decision; at most one additional
equivalent unit is allowed for residual state error. Above this boundary the
system consumes more than its declared conservative service budget each cycle.

## Frozen defenses and ablations

All arms retain M9A.7 covariance flooring and assignment marginalization.

1. `m9c_baseline`: the frozen M9C output.
2. `cross_channel`: assignment-corrected raw evidence is compared with a robust
   reference built from currently belief-admitted sources. A global median
   innovation is removed so a genuine target manoeuvre does not look like a
   source attack. Strong covariance understatement is independent evidence.
3. `ramp_rate`: an exponentially smoothed per-source relative offset is tested
   for causal drift.
4. `influence_budget`: aggregate precision from raw-visible but
   belief-inadmissible sources that also carry causal attack evidence is capped
   relative to admitted-source precision. Belief censoring alone is not an
   attack signal.
5. `combined`: cross-channel, ramp-rate, and influence-budget defenses together.

Frozen parameters:

- cross-channel NIS signal: starts at the 99% two-dimensional chi-square
  boundary `9.21`, saturates at `25`;
- strong covariance-understatement signal: reported minimum eigenvalue below
  `0.10 ×` the contemporaneous reachable-source median;
- trust attack EMA: `0.45`; recovery EMA: `0.20`; alert below trust `0.50`;
- minimum retained trust: `0.05`;
- covariance discount and trust residual support activate only after trust crosses
  the declared alert threshold; sub-threshold evidence remains diagnostic;
- relative-offset EMA: `0.15`;
- ramp-rate signal: starts at `0.12` units/cycle and saturates at `0.40`, and
  is actionable only while the same source exceeds the saturated
  cross-channel boundary;
- raw-only aggregate precision cap: `0.35 ×` admitted-source precision;
- trust residual EMA: `0.25`, capped at `0.08`, below the unchanged M9A.6
  wrong-risk ceiling of `0.10`.

The trust residual represents uncertainty while influence is being isolated.
It may not be removed merely to make the candidate select.

## Scenarios and splits

Controls:

1. stable M9A control;
2. failure plus partition;
3. flapping reconnect;
4. M9A.7 admission-censoring control;
5. M9C source-assignment competition;
6. genuine abrupt target manoeuvre without a strategic source;
7. legitimate heterogeneous precision, including accurately reported
   high-quality sources.

Attack dose response:

1. mild: one colluder, 60-cycle ramp, covariance scale `0.20`;
2. moderate: two colluders, 30-cycle ramp, covariance scale `0.10`;
3. severe: three colluders, 15-cycle ramp, covariance scale `0.05`;
4. canonical rejoin: the frozen M9A.7 three-colluder rejoin/ramp attack.

All attack cases retain three legitimate secondary-mode sources, so the
candidate must distinguish an adversarial coherent group from a valid minority.

- Training: seeds `20000`–`20039`, 40 paired seeds per scenario.
- Held-out: seeds `21000`–`21149`, 150 paired seeds per scenario.
- Bootstrap: 5,000 paired resamples with fixed suite RNG.

For a 2% event, 149 independent seeds give at least 95% probability of seeing
one or more events. Held-out uses 150. Development seeds below 20000 and every
M9 held-out row are excluded from tuning.

## Frozen gates

All gates are reported; none may be silently dropped.

### Validity

1. Every exogenous trace fingerprint replays.
2. The frozen M9C artifact remains `M9C-PARTIAL-GO`, its replay flag is true,
   and its recorded source and protocol hashes still match.
3. A no-defense shadow reproduces every frozen M9C output action and
   decision-loss sample within `1e-12`.
4. All arms have identical physical motion within `1e-12`.
5. Held-out contains at least 149 seeds per scenario.
6. Moderate, severe, and canonical attacks activate a trust diagnostic on at
   least 25% of operational strategic-source cycles.

### Control safety

7. In every control, the M9C-minus-combined decision-loss improvement LCB is at
   least `-0.02`.
8. In every control, non-strategic source-alert rate is at most `0.05`.
9. Every control has material wrong-action rate at most `0.01`, mean NEES at
   most `6`, mean run-level P95 NEES at most `20`, and coverage at least `0.88`.
10. The admission-censoring and legitimate-minority controls retain M9C
    noninferiority; accurately reported high-quality sources are not
    systematically discounted.

### Attack efficacy and safety

11. Combined decision loss is at most the derived `1.50` ceiling in every
    attack dose.
12. Canonical-attack M9C-minus-combined decision-loss improvement has a paired
    95% LCB greater than zero.
13. Every attack has material wrong-action rate at most `0.01`, mean NEES at
    most `6`, mean run-level P95 NEES at most `20`, and coverage at least
    `0.88`.
14. The combined defense does not increase M6 quarantine rate; trust discount
    remains a separate, auditable channel.
15. Moderate, severe, and canonical true-strategic alert rate is at least
    `0.50`; mild alert rate is at least `0.25`.
16. Adjacent dose levels may increase mean decision loss by at most `0.35`, and
    all levels must remain below the absolute ceiling.

Replay, upstream, shadow-equivalence, motion, power, or diagnostic-exercise
failure makes the assay invalid. A control-safety or attack gate failure yields
`M10A-NO-GO`. All gates passing yields `M10A-GO` for closed-loop research
integration only. Production is never authorized.
