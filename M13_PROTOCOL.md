# M13 external full-loop validation protocol

Status: implementation complete; external physical evidence not yet collected  
Protocol version: M13.0.0  
Platform version: 0.19.0

## 1. Question and claim boundary

M13 asks whether the frozen constant-velocity trust-plus-investigation system
survives a real distributed sensing, transport, planning, and motion loop. It
does not retune M9C, M10A.5, or M10B and it does not add an acceleration state.
The M12 jerk limiter remains a later, separately powered behavioural arm.

M13.1 can authorize entry to a physical pilot. Only M13.3 can support the
external full-loop research claim. No M13 result by itself authorizes
unattended or production deployment.

## 2. System under test

The intended rig has four or five observer robots and one independently
controlled target robot. Each observer obtains range and bearing from a
camera/AprilTag measurement and maintains a four-state constant-velocity
estimate. ROS 2/DDS transports estimates, trust diagnostics, locally owned
planner proposals, and commands over Wi-Fi. The target, network fault injector,
and attack shim are processes independent of the controller.

An overhead camera or motion-capture process records target state and robot
poses to the `independent_scorer` domain. Operational processes cannot subscribe
to scorer topics, share scorer credentials, or contain truth fields. A separate
hardware safety supervisor applies speed, acceleration, jerk, boundary, and
separation limits after the research controller.

## 3. Arms

All arms run in paired randomized blocks with the same path, layout, lighting,
fault manifest, and target program:

1. `m9c_no_trust`
2. `m10a5_centralized`
3. `m10b_decentralized_no_negotiation`
4. `m10b_decentralized`

The primary comparison is `m10b_decentralized` against
`m10a5_centralized`. Positive paired effects mean lower loss for the
decentralized candidate.

## 4. Scenarios

1. Stable network and smooth target.
2. Bounded target manoeuvre.
3. Physical camera occlusion.
4. Burst loss and variable latency.
5. Network partition and rejoin.
6. Observer outage and honest rejoin.
7. Legitimate high-precision minority sensor.
8. Covariance-understating colluding ramp.
9. Temporary attack and honest recovery.
10. Adaptive causal attacker within fixed bias and bias-rate bounds.

The adaptive attacker receives only its own outgoing message history. Neither
fault injection nor attack generation receives scorer truth.

## 5. M13.0 — interfaces, isolation, and evidence

`WireMessage` is the canonical operational envelope. Every estimate, proposal,
diagnostic, and command includes:

- schema and run identifiers;
- sender, sequence, monotonic timestamp, and local epoch;
- the sender's four-state estimate and 4 × 4 covariance;
- trust metadata and type-specific payload;
- an exact canonical-JSON byte count.

Covariances must be finite, symmetric, and positive semidefinite. Proposal
ownership must equal the sender. Recursive truth-key checks reject evaluator
fields in operational messages and ledgers.

Four hash-chained ledgers are mandatory per physical run:

- `operational.jsonl`;
- `transport.jsonl`;
- `safety.jsonl`;
- `truth.jsonl`, in the separate scorer domain.

`manifest.json` identifies processes, clocks, arm, block, day, path, layout,
lighting, and the causal fault/attack manifest. `artifact_hashes.json` seals
the closed recorders. It also lists every observer/planner/safety recorder
host and the relative paths of its raw files. Maximum absolute measured clock
offset is 5 ms.

One operational MCAP per declared recorder host, an independently hosted truth
MCAP, and a packet capture are mandatory source evidence and are included in
the bundle seal. The canonical scorer consumes exported ledgers so scoring is
deterministic and does not depend on a ROS installation. There must be exactly
one safety record per observer robot per operational estimate tick.

## 6. M13.1 — independent HIL screen

The independent reference environment in `full_loop_hil.py` does not call the
historical project simulator. It implements its own target plant, range-bearing
camera, network, distributed inboxes, causal trust monitor, planner, robot
kinematics, safety supervisor, and independent scorer.

Formal screening uses 150 paired seeds per scenario (6,000 trials). It writes
run and scenario summaries, paired effects, one audited operational/truth
trace, replay fingerprints, source hashes, a gate decision, and a report. A
deterministic replay mismatch or truth-isolation failure makes the HIL gate
fail. HIL output always records `external_physical_claim_authorized: false`.

## 7. M13.2 — physical development pilot and freeze

Pilot layouts, paths, lighting, clock synchronization, camera covariance, and
safety limits are development data. Genuine physical bundles must use one of
the declared ROS 2/physical adapters; loopback and synthetic evidence cannot
freeze the protocol.

Pilot scoring recomputes all metrics from raw ledgers. Paired pilot variance
sets the held-out sample size using two-sided α = 0.05, power = 0.80, a target
integrated-loss effect of 0.05, and a floor of 30 paired blocks per scenario.
At least one complete four-arm block from every scenario is required before a
freeze is allowed.
The freeze records:

- camera covariance scale and clock limit;
- required paired blocks and at least three trial days;
- arms, scenarios, gates, candidate source hashes, and protocol hashes;
- pilot run IDs and evidence hashes, which are forbidden in M13.3.

Once `power_freeze.json` exists, changes to any frozen candidate or protocol
file invalidate the held-out analysis.

## 8. M13.3 — preregistered physical holdout

Held-out paths, layouts, lighting conditions, fault manifests, and days must
not appear in the pilot. All four arms must be present in every complete paired
block. The evaluator requires the frozen number of complete blocks for every
scenario and evidence from at least three dates.

Integrity failures—hash mismatch, truth leakage, clock failure, incomplete
block, pilot reuse, synthetic adapter, source drift, or insufficient
power—return `M13.3-INVALID`, not a scientific result.

If integrity passes, `M13.3-PHYSICAL-GO` requires every gate below:

- truth isolation and replay completeness;
- zero collisions and emergency stops;
- safety-supervisor intervention rate below 1%;
- zero ownership violations and no planner-message-bound violation;
- decentralized-vs-central integrated-loss lower confidence bound ≥ −0.05;
- attack decision loss ≤ 1.50;
- wrong-action rate ≤ 0.01;
- mean NEES ≤ 6.0 and 95% coverage ≥ 0.88;
- attack alert rate ≥ 0.50 and nominal false-alert rate ≤ 0.05;
- attack recovery ≤ 30 steps;
- no material (>5%) delivery, topology, movement, or runtime regression;
- every leave-one-day-out lower bound ≥ −0.05.

Failure of any scientific gate returns `M13.3-PHYSICAL-NO-GO`.

## 9. Commands

Run the independent screen:

```bash
PYTHONPATH=src python3 -m flockkalman full-loop-hil-suite \
  --seed-count 150 \
  --seed-start 27000 \
  --output results/milestone13_1_hil
```

Create pilot or held-out schedules:

```bash
PYTHONPATH=src python3 -m flockkalman physical-trial-plan \
  --phase pilot \
  --blocks-per-scenario 8 \
  --trial-dates 2026-08-03,2026-08-04,2026-08-05 \
  --output physical/m13_pilot_plan
```

After all recorders close, seal and independently score each bundle:

```bash
PYTHONPATH=src python3 -m flockkalman seal-physical-bundle --bundle RUN_DIR
PYTHONPATH=src python3 -m flockkalman score-physical-bundle --bundle RUN_DIR
```

Freeze from genuine pilot evidence, then evaluate the new holdout:

```bash
PYTHONPATH=src python3 -m flockkalman physical-pilot \
  --bundles PILOT_RUN_DIRS... \
  --output results/milestone13_2_pilot

PYTHONPATH=src python3 -m flockkalman physical-heldout \
  --freeze results/milestone13_2_pilot/power_freeze.json \
  --bundles HELDOUT_RUN_DIRS... \
  --output results/milestone13_3_heldout
```

## 10. Stop rules

Stop a physical session immediately after any collision, emergency stop,
truth-domain access by an operational process, unlogged command path, clock
offset above 5 ms, missing recorder, or evidence-seal failure. Safety events
are never removed as outliers. A failed pilot does not open the holdout. A
failed or invalid holdout is reported as such; it is not repaired by
post-hoc threshold or sample changes.
