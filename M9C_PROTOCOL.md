# M9C preregistered bounded M9A.7/M9B integration protocol

Status: gates were fixed before training. Candidate V1 training on seeds `18000–18039` diagnosed two integration defects: unlike M9B, V1 treated assignment ambiguity after its two-step rollout as free, and it incorrectly transferred M9B's dimensionless break-even scale (`0.158`) as a physical cost (`0.15`) instead of using M9B's registered `0.80` unit movement cost. V2 adds the bounded terminal ambiguity price and restores movement cost `0.80`. No gate, scenario, or data split changed; V1 artifacts remain historical in `results/milestone9c_training`, V2 is rerun on the training split in `results/milestone9c_training_v2`, and V2 receives a new source hash before the held-out split is opened. Development seeds below `18000` are excluded.

## Research question

Does two-step receding-horizon value-of-information motion improve movement-inclusive decision utility over broad investigation when driven by M9A.7's exact source-assignment posterior under dynamic topology, without weakening M9A.7 output safety or topology behaviour?

The external estimate, split raw/shared-belief admission, residual unknown support, covariance floor, and risk-priced output are unchanged M9A.7. Only physical investigation goals differ:

- `M9A.7`: frozen M9A physical allocator;
- `broad`: every visible source receives an aggressive close-view goal while source identity is uncertain;
- `VOI`: a component-local two-step planner chooses tracking, a two-source probe, or broad motion using expected primary-versus-secondary classification error plus movement and action-change cost.

The planner receives no truth, future random draw, fault identity, or seed. It consumes the current exact assignment weights, declared assignment mask and offset, M9A.7 residual mass, sensor state, and observer-component graph. It holds that graph fixed only inside its two-step counterfactual rollout. Actual graph evolution remains endogenous in the simulator.

Extra probing is disabled when residual unknown mass exceeds `0.25`. This prevents a declared-model VOI calculation from treating strong off-model evidence as a target for exploitation.

## Frozen parameters

- horizon: `2`;
- at most `3` competing probe anchors;
- `2` sources per selective probe;
- replan every `3` cycles;
- close-view goal extrapolation: `2.0×` normally and `4.0×` only in the positive control;
- movement cost: `0.80` per unit mean-agent displacement per cycle, the original registered M9B cost (scale `1.0` in its later sensitivity sweep);
- action-change cost: `0.02`;
- assignment activation: any visible source with posterior class confidence below `0.99`;
- residual exploration ceiling: `0.25`;
- expected-label-error quadrature: `9` points;
- terminal boundary: assignment error surviving the explicit two-step rollout is charged for up to `12` known remaining secondary-evidence cycles. This restores M9B's conservative truncated-planner convention while bounding the marginal-label approximation to the local replanning regime.

Movement-inclusive loss is mean M9A.7 decision loss plus `0.80 ×` mean-agent movement distance per cycle. This preserves M9B's original registered cost rather than confusing its later dimensionless sweep multiplier with a cost in loss units. It remains a dynamic integration operating point, not an inherited optimality guarantee.

## Scenarios and splits

The exact set contains the eight natural M9A scenarios, the M9A.7 admission-censoring control, and `source_assignment_competition`. The latter starts noisy, partially dropped secondary evidence early enough that source identity remains uncertain while close-view motion can change future measurement covariance.

The `raw_channel_colluding_ramp` is retained as an off-model safety and absolute-utility challenge.

- Training: seeds `18000–18039`, 40 paired seeds per scenario.
- Held-out: seeds `19000–19149`, 150 paired seeds per scenario.
- Bootstrap: 5,000 paired resamples with a fixed suite RNG.

For a 2% event, `ceil(log(0.05) / log(0.98)) = 149` seeds give at least 95% probability of observing one or more events. The held-out split uses 150.

## Frozen gates

All applicable gates are reported; none may be silently dropped.

1. Every exogenous trace fingerprint replays.
2. The exact frozen M9A.7 candidate source hash still matches its held-out `M9A7-GO`, whose replay flag remains true.
3. The held-out split contains at least 149 seeds per scenario.
4. In `source_assignment_competition`, broad investigation is active on at least 3% of cycles, the VOI planner evaluates actions, and VOI differs from broad on at least 2% of cycles.
5. Aggregate exact-scenario broad-minus-VOI movement-inclusive loss has a paired-bootstrap 95% LCB greater than zero.
6. The same loss effect in `source_assignment_competition` has a 95% LCB greater than zero.
7. Aggregate broad-minus-VOI movement per cycle has a 95% LCB greater than zero.
8. In every natural M9A scenario, M9A.7-minus-VOI movement-inclusive loss has LCB at least `-0.03`.
9. VOI material wrong-mode action rate is at most `0.01` in every scenario.
10. Every exact VOI scenario has mean NEES at most `6`, mean per-run P95 NEES at most `20`, and coverage at least `0.88`.
11. In every natural scenario, VOI-versus-M9A.7 delivery-ratio LCB is at least `-0.05`, and mean component count increases by at most `0.25`.
12. In the colluding-ramp attack, VOI-versus-M9A.7 loss LCB is at least `-0.10`, wrong actions do not increase, and active investigation occurs on at most 5% of cycles.
13. The colluding-ramp VOI decision loss is at most `1.50`. This deliberately demanding absolute-utility gate tests whether integration resolves, rather than merely avoids worsening, the known raw-channel weakness.

Replay/upstream/power/control failures make the assay invalid. Safety or efficacy failure yields `M9C-NO-GO`. If all validity, safety, and efficacy gates pass but absolute attack utility fails, the result is `M9C-PARTIAL-GO`. All gates passing yields `M9C-GO` for a decentralized research follow-up only. Production is never authorized, and prior M9A.7/M9B verdicts remain unchanged.
