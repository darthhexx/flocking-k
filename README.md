# Flocking–Kalman Research Platform

This package is a small but complete experimental platform for testing whether topological flocking rules, recurrent investigative velocity, robust multi-hypothesis fusion, value-of-information motion, and causal source trust improve distributed state estimation. Version 0.19 adds a hardware-facing full-loop validation layer, a powered independent HIL screen, and fail-closed physical pilot/holdout tooling while preserving the constant-velocity estimator.

The full engineering design and milestone record is in [`DESIGN_SPEC.md`](DESIGN_SPEC.md).

It addresses the first three research objectives:

1. A reproducible numerical benchmark: mobile sensing agents track a manoeuvring two-dimensional target. Observation noise grows with sensor-to-target distance, so agent movement changes the information available to the system.
2. Controlled ablations: independent and distributed filtering, flocking, recurrent motion, robust hypothesis flocks, and truth-blind output policies.
3. Comparable measurements: estimation error, covariance calibration, decision loss, abstention, mode safety, information, movement, runtime, and communication cost.

The platform requires Python 3.11 or newer and NumPy. Plotting uses dependency-free SVG generation.

## Quick start

From this directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
flockkalman run --config configs/default.json --output results/default
```

It can also run directly from a source checkout when NumPy is already installed:

```bash
PYTHONPATH=src python3 -m flockkalman run \
  --config configs/default.json \
  --output results/default
```

For a fast smoke experiment:

```bash
PYTHONPATH=src python3 -m flockkalman run \
  --steps 50 \
  --seeds 0 \
  --output results/smoke
```

List the stable algorithm identifiers with:

```bash
PYTHONPATH=src python3 -m flockkalman list-algorithms
```

## Experimental model

The hidden target state is

```text
x = [position_x, position_y, velocity_x, velocity_y]
```

The target follows a constant-velocity process and receives an abrupt velocity change halfway through the default trial. Every sensor receives a noisy position observation. Measurement variance increases with distance, giving the agents a reason to move intelligently rather than merely estimate passively.

Kalman variants use a linear constant-velocity filter. Distributed variants exchange beliefs with their nearest `k` neighbours and apply covariance intersection. This is conservative when cross-correlations produced by repeated exchange are unknown.

Flocking policies combine:

- goal seeking toward the agent's current target estimate;
- velocity alignment with topological neighbours;
- cohesion toward neighbour positions;
- short-range separation;
- recurrent velocity, where enabled.

The original adaptive policy maps normalized innovation squared (NIS) directly to recurrence and is retained as a negative control. The M5 guarded policy instead requires directionally coherent surprise from multiple independently observed agents. It tracks persistent agent-specific residual offsets, refuses adaptation under stale or degraded communication, and falls back exactly to fixed recurrence whenever a guard is active. Recurrence belongs to the behavioural controller, not the Kalman transition, which keeps the causal comparison interpretable.

## Algorithms

| Identifier | Estimation | Agent policy | Communication |
|---|---|---|---|
| `independent_kf` | Local Kalman filter | Direct tracking | None |
| `consensus_kf` | Local Kalman + covariance intersection | Direct tracking | Beliefs |
| `flocking_only` | Current observation only | Flocking, no recurrence | Motion and observation summaries |
| `flocking_kf_no_momentum` | Distributed Kalman | Flocking with zero recurrence | Bundled belief and motion state |
| `flocking_fixed_momentum` | Distributed Kalman | Flocking with fixed recurrence | Bundled belief and motion state |
| `flocking_adaptive_momentum` | Distributed Kalman | Rejected direct-NIS recurrence rule | Bundled belief and motion state |
| `flocking_guarded_momentum` | Distributed Kalman | Corroborated change response with fixed fallback | Bundled belief and motion state |
| `flocking_robust_multiflock` | Bias-aware distributed Kalman with explicit hypothesis flocks | Flocking with fixed recurrence | Bundled belief and motion state |
| `flocking_robust_temporal` | Same robust hypothesis set | Temporal-nearest selection | Same payload |
| `flocking_robust_mixture` | Same robust hypothesis set | Moment-matched mixture output | Same payload |
| `flocking_robust_defer` | Same robust hypothesis set | Always return the set | Same payload |
| `flocking_robust_active_no_investigation` | Same robust hypothesis set and active output actions | Ordinary flocking goals during investigation (causal control) | Same payload |
| `flocking_robust_active` | Same robust hypothesis set | Select, bounded investigation, or defer with mode-spreading motion | Same payload |
| `flocking_topology_resilient` | M9A lifecycle-, provenance-, and component-aware hypothesis flocks | Frozen topology-resilient physical controller | Component-local belief and motion state |
| `flocking_topology_posterior` | M9A.6 causal hidden-assignment posterior with residual unknown support | Frozen M9A motion; risk-priced select, mixture, or defer output | Same component-local payload |
| `flocking_topology_admission_posterior` | M9A.7 split raw/belief admission with covariance floor and admission diagnostics | Frozen M9A motion; M9A.6 risk-priced output | Same component-local payload plus distinct raw/belief eligibility |
| `flocking_topology_admission_round_robin` | Unchanged M9A.7 estimator and output | Broad all-visible-source investigation while assignment identity is uncertain | Same M9A.7 component-local payload |
| `flocking_topology_admission_receding_voi` | Unchanged M9A.7 estimator and output | Component-local two-step assignment-VOI motion with residual guard | Same M9A.7 component-local payload |

All algorithms receive the same target trajectory, initial conditions, and standard-normal noise draws for a given seed. Their measurement variances can differ because their sensor trajectories differ; that is the intended consequence of active sensing.

## Results

Each run directory contains:

- `config.json`: exact replay configuration;
- `environment.json`: Python, NumPy, platform, and package versions;
- `per_step_metrics.csv`: complete time series for subsequent analysis;
- `run_summary.csv`: one row per algorithm and random seed;
- `summary.csv` and `summary.json`: mean and standard deviation across seeds;
- `comparison.svg`: six-panel aggregate comparison;
- `error_timeseries.svg`: mean team error and the manoeuvre time.

Guarded runs also record the momentum classification, change score, corroborating-agent count, persistent-bias flags, fallback state, and exact change-event steps. Robust runs additionally record hypothesis-flock counts and weights, truth-consistent mode weight, bias-state magnitude, suspected and quarantined source counts, and best-hypothesis error for evaluation. M7 runs add output action, confidence, decision loss, abstention, investigation, material wrong-mode action, resolution, and movement diagnostics. M8 adds operational-agent count, delivered-edge ratio, message age, partition state, and cryptographic scenario replay manifests. M8.1 records Bayesian mode probability, resolution, decision and movement cost, geometric discriminability, dose response, and replay fingerprints. M9A.6 adds posterior assignment entropy, predictive-model NIS, residual unknown mass, predicted action and wrong-action risk, and credible-mode count. M9A.7 adds measurement eligibility, belief admission, admission censoring, reachability, covariance-floor, model-rejection, and secondary-source missingness diagnostics. M10A/M10A.5 add cross-channel disagreement, ramp-rate evidence, influence capping, raw-source trust, alert/recovery rates, bounded trust-residual support, and trust-driven verification motion. M10B adds per-agent ownership, proposal messages/bytes, conflict, planner-state age, and asynchronous action diagnostics. M11/M11.1 add archive/materialized hashes, timestamp-canonicalization manifests, real-log topology/outage metrics, and 60-second replay windows. M12 adds measured-acceleration diagnostics and a separate jerk-limiter assay. M13 adds exact wire bytes, transport events, truth-isolation audits, safety interventions, adaptive-attack alerts/recovery, sealed evidence hashes, and preregistered physical gates.

## Firm-decision suite

Version 0.2 adds a held-out, paired evaluation designed to decide whether investigative momentum merits another research phase:

```bash
PYTHONPATH=src python3 -m flockkalman decision-suite \
  --config configs/default.json \
  --seed-count 100 \
  --seed-start 1000 \
  --output results/decision_suite
```

The suite freezes the existing controller parameters and compares zero, fixed, and adaptive momentum using the same random draws for every paired trial. It covers seven scenarios:

- no deliberate regime change;
- one abrupt velocity change;
- a gradual velocity change;
- repeated target turns;
- combined observation and communication dropout;
- two-cycle communication delay;
- two persistently biased agents.

It writes per-run and per-scenario summaries, paired effect estimates, bootstrap 95% confidence intervals, and `decision_report.md`. Overall effects average scenarios within each held-out seed before bootstrapping, preserving 100 independent paired experimental units.

The automatic decision gate returns `GO` only when adaptive momentum:

- has a positive RMSE confidence interval against both zero and fixed momentum;
- remains calibrated;
- beats both controls in at least five of seven scenario means;
- adds less than 2% realized communication and less than 25% runtime overhead.

### Included held-out decision result

The packaged `results/decision_suite` contains 2,100 completed trials: three momentum conditions, seven scenarios, and 100 held-out seeds.

- Fixed momentum reduced overall RMSE by **19.60%** versus zero momentum. Its paired 95% confidence interval for absolute RMSE improvement was `[0.2305, 0.2565]`, and it won all 100 seed-level aggregates.
- Fixed momentum improved recovery by `1.0117` steps, with paired interval `[0.5367, 1.4733]`.
- The current adaptive rule was **2.41% worse** than fixed momentum. Its RMSE improvement interval was wholly negative: `[-0.0360, -0.0116]`.
- Adaptive momentum was worse than fixed momentum under persistent bias and two-cycle communication delay. Overall uncertainty calibration also failed when those deliberately unmodelled stresses were included.

The resulting decision is `NO-GO` for the current innovation-adaptive scheduler and `PIVOT_TO_FIXED_MOMENTUM_AND_REDESIGN_ADAPTATION` for the wider research direction. Fixed recurrence remains the supported baseline; future adaptation should distinguish genuine target change from stale or biased innovations.

## Milestone 5 guarded-momentum suite

Version 0.3 implements that redesign as a falsifiable prototype:

```bash
PYTHONPATH=src python3 -m flockkalman guarded-suite \
  --config configs/default.json \
  --seed-count 100 \
  --seed-start 2000 \
  --output results/milestone5_heldout
```

The controller uses robust cross-agent innovation direction, observation availability, message age, delivery ratio, and persistent residual-offset diagnostics. A change response requires three consecutive corroborated cycles. Any stale-message or bias guard restores fixed `rho=0.72`; accepted events briefly use `rho=0.58` for two cycles, followed by a ten-cycle cooldown.

The packaged M5 report contains 2,100 held-out trials on seeds 2000–2099. The frozen result is **NO-GO** for promotion:

- Guarded momentum was statistically indistinguishable from fixed recurrence on RMSE: improvement `-0.0012`, paired 95% CI `[-0.0048, 0.0021]`.
- Recovery improved by only `0.0400` steps, CI `[-0.0183, 0.1200]`.
- The guarded controller beat the rejected direct-NIS policy on RMSE by `0.0136`, CI `[0.0006, 0.0261]`, and on recovery by `1.0267` steps, CI `[0.6633, 1.3517]`.
- Stale-message fallback, persistent-bias detection, bounded false events, communication cost, and runtime gates passed.
- Delay and unmodelled persistent bias remained uncalibrated, demonstrating that motion-policy guards cannot repair a fusion/model-consistency failure.

The engineering decision is to keep fixed recurrence as the supported controller and move to M6: robust fusion, explicit bias state, and multi-flock hypotheses. Acceleration remains deferred.

## Milestone 6 robust multi-flock suite

Version 0.4 implements bias-state tracking, persistent-minority quarantine, randomized per-seed fault identities, time alignment of delayed beliefs, Byzantine-source stress, and explicit compatible hypothesis flocks:

```bash
PYTHONPATH=src python3 -m flockkalman robust-suite \
  --config configs/default.json \
  --seed-count 100 \
  --seed-start 3000 \
  --bootstrap-samples 5000 \
  --output results/milestone6_heldout
```

The frozen M6 result is a research **GO**. All 12 gates passed across 1,400 held-out trials:

- overall hypothesis-set RMSE improved by `2.1052`, paired 95% CI `[2.0708, 2.1414]`;
- persistent-bias RMSE improved by `0.6188`, CI `[0.5340, 0.7070]`;
- Byzantine-source RMSE improved by `10.0737`, CI `[10.0535, 10.0934]`;
- two-cycle-delay RMSE improved by `1.8427`, CI `[1.7636, 1.9216]`;
- the equal alternative mode survived on 98.96% of steps with mean alternative weight `0.491`;
- nominal, dropout, calibration, false-quarantine, communication, and runtime gates passed.

The multimodal result must be read carefully. Robust set RMSE was `0.7225`, but its arbitrarily ordered primary RMSE was `3.8323`, worse than fixed fusion at `2.9178`. With equal evidence, the system cannot know which mode is true. M6 therefore validates explicit hypothesis retention, not single-output selection; M7 below adds truth-blind selection and abstention.

## Milestone 7 truth-blind output-policy suite

Version 0.5 implements the downstream decision layer identified by M6:

```bash
PYTHONPATH=src python3 -m flockkalman output-suite \
  --config configs/default.json \
  --seed-count 100 \
  --seed-start 4000 \
  --bootstrap-samples 5000 \
  --output results/milestone7_heldout
```

The active policy groups nearby Gaussian fragments only for decision-level support counting; it does not merge their conservative M6 posteriors. It selects through temporal continuity when grouped support has a `0.15` margin, requires three ambiguous cycles before acting, investigates for at most eight cycles, and then explicitly defers. Neither truth nor fault identity is a policy input.

The frozen M7 result is a research **GO**. All 18 gates passed across 4,000 held-out trials:

- active decision loss was `0.7377`;
- improvement versus largest-flock selection was `0.3751`, 95% CI `[0.2681, 0.4867]`;
- improvement versus temporal selection was `0.1699`, CI `[0.0998, 0.2403]`;
- improvement versus moment matching was `0.5489`, CI `[0.5454, 0.5524]`;
- improvement versus always defer was `0.5892`, CI `[0.5870, 0.5913]`;
- persistent equal evidence produced 97.74% abstention and 0.67% material wrong-mode actions;
- five-versus-three evidence produced 97.54% selection;
- communication and runtime were unchanged within noise, while movement increased by 0.40%.

The result remains significant for counterfactual deferral costs from `0.25` through `1.00`. At cost `1.50`, the lower confidence bound crosses zero, so the promotion claim does not extend to applications where abstention is valued that harshly.

M7 validates the combined output controller, not a causal benefit from investigation motion by itself. The transient mode ends exogenously; M8 below supplies the otherwise-identical no-investigation ablation.

## Milestone 8 realism ladder

Version 0.6 adds burst-correlated links, per-sender delay jitter and clock skew, exact-moment range–bearing conversion, heterogeneous sensors, drifting/recovering bias, colluding ramp attacks, temporary agent outages, graph partitions, a composite stress case, and deterministic trace hashes:

```bash
PYTHONPATH=src python3 -m flockkalman realism-suite \
  --config configs/default.json \
  --seed-count 100 \
  --seed-start 5000 \
  --bootstrap-samples 5000 \
  --output results/milestone8_heldout
```

The no-investigation arm uses the same active output policy and action costs. Its only intervention is to keep ordinary flocking goals when the policy says `investigate`; this isolates the downstream effect of mode-spreading physical motion.

The frozen held-out verdict is **NO-GO** for full M8 promotion across 4,000 trials:

- overall active decision loss still beat temporal selection by `0.2082`, 95% CI `[0.1382, 0.2829]`;
- nine of ten ordered layers passed, including burst links, asynchronous messages, nonlinear/heterogeneous sensing, drifting bias, and colluding ramp attacks;
- dynamic topology was the first failure: active loss increased from the `0.9506` transient reference to `1.1698`, a transfer effect of `-0.2192`, CI `[-0.3308, -0.1151]`, beyond the declared `-0.10` margin;
- dynamic-topology NEES was `8.16` with 91.05% coverage; composite-stress NEES was `27.73`, exposing an important tail-consistency problem despite bounded wrong actions;
- investigative motion significantly increased information gain by `0.0030`, CI `[0.0015, 0.0045]`, but did not reduce decision loss: improvement `-0.0020`, CI `[-0.0052, 0.0011]`;
- all 1,000 scenario/seed fingerprints regenerated exactly, communication was effectively unchanged, and investigation added 1.40% movement.

The supported interpretation is precise: the geometry mechanism acquires information, but the current allocator/output coupling does not turn it into better decisions, and participation/topology changes damage uncertainty consistency. M9A remains the production-blocking topology redesign; M9B below evaluates expected-utility investigation separately. Acceleration remains deferred.

## Milestone 8.1 endogenous-ambiguity assay

Version 0.7 directly tests the identifiability concern exposed by the M8 review. Two equally likely target hypotheses at `(-5, 0)` and `(5, 0)` produce identical range distributions while all sensors remain on their initial `x=0` bisector. Lateral sensor motion makes the likelihoods distinguishable, and support is updated from the measurement likelihood rather than agent headcount. The suite includes passive sensing, the current round-robin allocator at five motion doses, an information oracle, and a one-step value-of-information policy:

```bash
PYTHONPATH=src python3 -m flockkalman ambiguity-assay \
  --config configs/ambiguity_assay.json \
  --seed-count 100 \
  --seed-start 7000 \
  --bootstrap-samples 5000 \
  --output results/milestone8_1_heldout
```

The frozen held-out positive control passed all six gates on seeds `7000–7099`:

- passive sensing remained unresolved in every run, with zero discriminability;
- every nonzero round-robin dose resolved all runs without a wrong selection;
- dose and mean discriminability had correlation `0.9994`;
- full-dose investigation reduced mean cumulative decision loss from `6.0000` to `0.1140`, an improvement of `5.8860`, 95% CI `[5.8652, 5.9067]`;
- all trace fingerprints replayed exactly.

This is evidence that motion can resolve ambiguity when viewpoint changes feed a Bayesian evidence update. It is not a rescue of the M8 allocator in the realism ladder. In this intentionally simple binary geometry, full-dose round-robin, oracle, and one-step value-of-information policies produce the same path and result. M9B below introduces competing views, asymmetric movement costs, and more than two hypotheses so policy quality—not merely nonzero motion—is identifiable.

Reanalyze the saved raw summaries and regenerate the decision without rerunning simulation:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-ambiguity-assay \
  --output results/milestone8_1_heldout \
  --bootstrap-samples 5000
```

## Fixed-recurrence mechanism diagnostic

Version 0.7 also sweeps fixed recurrence values and reports the equivalent time constant `tau = -dt/log(rho)` across no-change, abrupt, gradual, and repeated-turn scenarios. It tests whether RMSE improvements covary with sensor diversity, disagreement, or information; correlations are diagnostic and are not interpreted as mediation:

```bash
PYTHONPATH=src python3 -m flockkalman momentum-mechanism \
  --config configs/default.json \
  --seed-count 30 \
  --seed-start 8000 \
  --output results/momentum_mechanism_training
```

The 1,440-trial training diagnostic returned **MECHANISM-UNRESOLVED**. All eight scenarios preferred a nonzero recurrence value, but their best `rho` varied among `0.72`, `0.85`, and `0.93`. RMSE improvement versus spatial-diversity change had correlation `-0.295` between cells and `0.051` within cells; disagreement was likewise uninformative, while information change had a modest within-cell correlation of `0.345`. This does not support the proposed diversity mechanism or a simple recurrence-timescale rule. `rho=0.72` remains frozen for comparison with earlier milestones, but it should not be treated as a portable optimum.

## Milestone 9B decision-relevant active sensing

Version 0.8 introduces five static range-only tasks with three or four hypotheses, limited two-agent probes, skewed priors, competing views, and asymmetric movement costs. It compares passive sensing, current broad round-robin spreading, one-step VOI, two-step receding-horizon VOI, and a truth-blind exhaustive horizon-three comparator:

```bash
PYTHONPATH=src python3 -m flockkalman active-sensing-suite \
  --config configs/active_sensing.json \
  --seed-count 100 \
  --seed-start 10000 \
  --bootstrap-samples 5000 \
  --output results/milestone9b_heldout
```

The frozen held-out run contains 2,500 trials and passed all 12 gates:

- receding-horizon VOI reduced total movement-inclusive loss from `2.0124` to `1.4387` versus round-robin, an improvement of `0.5737`, 95% CI `[0.5293, 0.6196]`;
- it beat round-robin in all five task families, with every scenario-specific lower confidence bound above zero;
- it resolved every trial with zero wrong selections, matching round-robin safety;
- movement cost fell from `1.7244` to `1.0427`, improvement `0.6817`, CI `[0.6418, 0.7226]`;
- it used targeted probes for 33.7% and broad spreading for 41.3% of actions, versus 100% spreading for round-robin;
- all 500 scenario/seed fingerprints replayed exactly.

The result is an efficiency win, not an accuracy or speed win. Round-robin resolved in `2.15` cycles versus `2.58` for VOI, and VOI's decision-cost component was `0.1080` higher. Its lower total loss comes from using materially less costly motion. The static centralized assay is a research **M9B-GO**; M9A.7 now authorizes a bounded integration experiment, not production deployment.

Reanalyze without rerunning simulation:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-active-sensing-suite \
  --output results/milestone9b_heldout \
  --bootstrap-samples 5000
```

Version 0.12 reprices the immutable held-out actions across movement-cost scales `0–4`:

```bash
PYTHONPATH=src python3 -m flockkalman movement-cost-sweep \
  --output results/milestone9b_heldout \
  --bootstrap-samples 5000
```

The receding policy breaks even at scale `0.158` versus round-robin and `2.018` versus passive/myopic. Its 95% LCB is positive against round-robin at tested scales `0.20–4.0`, and against passive/myopic at `0–1.5`. The original `M9B-GO` remains unchanged and conditional on this cost envelope.

## Milestone 9A topology resilience

Version 0.9 implements all M9A sub-milestones:

- per-cycle connected components, stable topology epochs, provenance masks, visibility, support, merge, and selection-block diagnostics;
- separate live, decaying retained, and unreachable/withheld support, with retained hypotheses preserved as zero-vote modes;
- `OFFLINE → PROBATION → TRUSTED` recovery, stale bias reset, outage-length covariance inflation, bounded-NIS admission, and gradual support ramp;
- observer-component-local output, explicit unknown mass, common-time compatibility, conservative covariance intersection, stable hypothesis identity, merge grace, and merge-entry support ramp;
- four topology algorithms forming an ablation ladder and an eight-scenario suite covering stable control, failure, balanced/asymmetric partitions, combined failure/partition, staggered rejoin, flapping reconnect, and false splits from correlated dropout.

Run the frozen protocol with:

```bash
PYTHONPATH=src python3 -m flockkalman topology-suite \
  --config configs/default.json \
  --seed-count 100 \
  --seed-start 12000 \
  --bootstrap-samples 5000 \
  --output results/milestone9a_heldout
```

The held-out result is **M9A-PARTIAL-GO**. Replay, stable noninferiority, calibration/tails, wrong selection, rejoin shock, partition uncertainty, and support continuity all passed. Across the dynamic cases, mean NEES was `1.61–2.26`, p95 NEES was `4.12–6.74`, coverage was `0.964–0.973`, and wrong-mode actions were `0.3–0.6%`. Overall decision loss improved over the unchanged M8 active control by `0.0480`, 95% CI `[0.0079, 0.0890]`.

The strict transfer gate failed. Dynamic-vs-stable lower confidence bounds ranged from `-0.2724` to `-0.0331`; failure-only, balanced/asymmetric partition, combined failure/partition, and staggered rejoin breached the declared `-0.10` margin. The architecture repairs the M8 uncertainty pathology but remains unqualified for production because safe deferral under missing evidence is still too costly in several scenarios.

Reanalyze saved rows and all 800 trace fingerprints with:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-topology-suite \
  --output results/milestone9a_heldout \
  --bootstrap-samples 5000
```

## Milestone 9A.5 dynamic loss-floor diagnostic

Version 0.10 evaluates three nested references on the same frozen M9A trajectories:

- an observer-component Bayesian reference that marginalizes all 70 possible four-of-eight secondary-mode assignments using only currently available measurements inside the observer's delivered weak component;
- the same reference with all currently operational measurements supplied by an ideal out-of-band global collector;
- an evaluation-only lower bound that chooses the frozen M9A returned hypothesis nearest truth.

The two causal references know the declared assignment count, offset, and activation schedule. They do not see target truth, future noise, or the seeded fault identities before acting. The simulator passes truth only to the scoring function after each decision. A regression test also confirms that attaching the diagnostic observer leaves every frozen M9A step record unchanged.

Run the complete non-promotional diagnostic with:

```bash
PYTHONPATH=src python3 -m flockkalman oracle-floor-suite \
  --config configs/default.json \
  --seed-count 100 \
  --seed-start 12000 \
  --bootstrap-samples 5000 \
  --output results/milestone9a5_oracle_floor
```

The 800-trace held-out conclusion is **`INFORMATION-LIMITED`**, with an important qualification. The final run used M9A's original Python `3.11.11`/NumPy `2.4.6` runtime, and all 800 rerun frozen-M9A decision-loss rows exactly match the M9A.4 artifact. The observer reference clears the original transfer margin in six of seven dynamic scenarios and misses only asymmetric partition (`LCB -0.1053` versus the unchanged `-0.10` threshold). The ideal-global reference clears all seven. Thus a hard component-information boundary is real, but it is not the dominant explanation for current loss in most cases: frozen M9A is still `0.664–0.809` loss worse than the same-information observer reference across scenarios.

Failure+partition also makes the frozen returned-set floor miss the margin (`LCB -0.1337`) while the observer Bayesian representation passes (`LCB -0.0851`). The next implementation must therefore combine an assignment-weighted missing-evidence representation with risk-priced actions and a separate residual-unknown fallback. Simply lowering the fixed deferral cost would not repair the representation failure. M9A remains `PARTIAL-GO`; this diagnostic does not relax or replace its original gate.

Reanalyze saved rows and all fingerprints with:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-oracle-floor-suite \
  --output results/milestone9a5_oracle_floor \
  --bootstrap-samples 5000
```

## Milestone 9A.6 missing-evidence posterior

Version 0.11 implements M9A.6 as an output-only overlay on the frozen M9A physical trajectory. It enumerates the declared hidden secondary-source assignments, maintains a causal posterior from lifecycle-admitted observer-component measurements, preserves posterior-predictive mismatch as separate residual unknown mass, and prices select/mixture/defer actions with a hard predicted wrong-action ceiling. It does not receive truth or fault identity before acting.

The candidate and gates were developed on seeds `13000–13029`. After they passed, they were frozen and run once on seeds `14000–14099`:

```bash
PYTHONPATH=src python3 -m flockkalman missing-evidence-suite \
  --config configs/default.json \
  --phase heldout \
  --seed-count 100 \
  --seed-start 14000 \
  --bootstrap-samples 5000 \
  --output results/milestone9a6_heldout
```

The held-out verdict is **`M9A6-NO-GO`**: eight of nine gates pass, but the all-scenario observer-regret gate fails. M9A.6 improves decision loss in every exact-model topology scenario with improvement LCBs `0.6287–0.7093`, records zero material wrong point selections, and preserves exact M9A motion. Mean NEES is `1.70–1.77`, p95 NEES `5.03–5.18`, and coverage `0.967–0.970`. Seven observer-regret UCBs are at most `0.0471`; failure+partition reaches `0.1568` against the frozen `0.10` limit.

The residual fallback responds correctly to its two explicit misspecification challenges. Actual-three/assumed-four membership raises mean residual mass to `0.402` and abstention to `0.498`; a shifted offset raises them to `0.132` and `0.452`. Both make zero material wrong point selections, but neither is an accuracy win: M9A.6 loss is worse than M9A because safe abstention is costly.

Two failure+partition outliers explain the failed gate. Lifecycle admission leaves only about `3.5` visible sources although `5.31` fresh operational component measurements exist; the visible subset is internally model-consistent, so predictive NIS remains low. A post-hoc, non-promotional replay with a separate raw-measurement channel reduces the two losses from `2.100/2.284` to `0.347/0.464`. At the M9A.6 decision point, the next bounded repair was therefore admission-aware missingness with separate trust channels for fresh measurements and shared beliefs—not held-out retuning of M9A.6—and M9B integration remained unauthorized.

Reanalysis regenerates the decision and verifies all 1,000 fingerprints:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-missing-evidence-suite \
  --output results/milestone9a6_heldout \
  --bootstrap-samples 5000
```

## Milestone 9A.7 split-admission tail repair

Version 0.12 separates current raw measurements from recursive belief admission. A current sample may enter the observer-component assignment posterior even while its sender's fused belief remains suspected, quarantined, or on lifecycle probation. The raw path floors reported covariance against the contemporaneous team median, retains posterior-predictive mismatch mass and the hard wrong-risk ceiling, and is challenged by rejoining colluders that ramp a shared offset while reporting covariance at `0.05 ×` its physical value.

The positive control and candidate were developed on seeds `15000–15059`. The implementation, protocol, and thresholds were then frozen before the powered held-out split on seeds `16000–16299`:

```bash
PYTHONPATH=src python3 -m flockkalman admission-evidence-suite \
  --config configs/default.json \
  --phase heldout \
  --seed-count 300 \
  --seed-start 16000 \
  --bootstrap-samples 5000 \
  --output results/milestone9a7_heldout
```

The held-out verdict is **`M9A7-GO`**: all 13 gates pass across 3,600 paired trials and all fingerprints replay. Failure+partition loss falls from M9A.6 `0.419` to M9A.7 `0.371`; observer-regret mean UCB, P95 bootstrap UCB, and per-seed maximum are `0.023`, `0.070`, and `0.103`, all below `0.10`, `0.20`, and `0.75`. Wrong actions are zero and exact-model coverage remains `0.968–0.970`. The engineered positive control has 1.56 belief-censored raw sources on average, is censored on 63.2% of cycles, and improves from `0.405` to `0.339` loss.

The raw-channel attack passes its frozen safety criterion: zero wrong-action increase, zero quarantine increase, and covariance flooring on 83.4% of cycles. It is not a utility success—loss rises from `1.105` to `3.502` because M9A.7 abstains on 89.7% of cycles. That `GO` authorized only the M9C integration experiment reported below.

Reanalyze all saved rows and fingerprints with:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-admission-evidence-suite \
  --output results/milestone9a7_heldout \
  --bootstrap-samples 5000
```

## Milestone 9C bounded dynamic integration

Version 0.13 connects M9A.7's exact source-assignment posterior to two physical sensing allocators while leaving its estimator, split admission, residual fallback, covariance floor, and external risk-priced output unchanged. The broad arm closes every visible source while assignment identity is uncertain. The two-step VOI arm instead chooses ordinary tracking, a selective two-source probe, or broad motion within the current observer component and disables extra probing when residual unknown mass exceeds `0.25`.

The frozen V2 candidate was evaluated on 150 held-out seeds per scenario, enough to clear the preregistered 149-seed tail-power requirement:

```bash
PYTHONPATH=src python3 -m flockkalman integration-suite \
  --config configs/default.json \
  --phase heldout \
  --seed-count 150 \
  --seed-start 19000 \
  --workers 8 \
  --bootstrap-samples 5000 \
  --output results/milestone9c_heldout
```

The result is **`M9C-PARTIAL-GO`**. Twelve validity, efficacy, safety, calibration, topology, and attack-nonworsening gates pass. Aggregate broad-minus-VOI movement-inclusive improvement is `0.00293`, 95% CI `[0.00228, 0.00359]`; the source-competition positive control improves by `0.00749`, `[0.00444, 0.01059]`, while movement falls by `0.02028` per step. Wrong-mode actions remain zero, exact-scenario mean NEES is `1.57–1.71`, coverage is `0.969–0.978`, and the worst natural M9A.7 noninferiority LCB is positive at `0.00682`.

The sole failure is intentionally decisive: colluding-ramp decision loss is `3.507` against the absolute `1.50` ceiling. The allocator makes no extra probe under this off-model evidence and does not worsen integrated attack utility, but it does not repair the permissive raw channel. The result supports a decentralized allocator follow-up and a separate trust-channel repair, not production or acceleration work.

Reanalysis regenerates the verdict from 4,950 saved rows and verifies every fingerprint:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-integration-suite \
  --output results/milestone9c_heldout \
  --bootstrap-samples 5000
```

## Milestone 10A raw-channel adversarial trust

Version 0.14 evaluates a causal trust layer on frozen M9C receding-VOI trajectories. It combines assignment-corrected cross-channel disagreement, corroborated ramp-rate evidence, and an influence budget for suspicious raw-only sources. It does not receive truth, fault identity, future samples, or the seed before acting. The no-defense shadow must reproduce M9C output to `1e-12`, and all arms share identical physical motion.

The frozen held-out suite uses seven non-adversarial controls and four attack doses, with 150 fresh paired seeds per scenario:

```bash
PYTHONPATH=src python3 -m flockkalman adversarial-trust-suite \
  --phase heldout \
  --seed-count 150 \
  --seed-start 21000 \
  --workers 8 \
  --bootstrap-samples 5000 \
  --output results/milestone10a_heldout
```

The result is **`M10A-GO`**: all 16 preregistered gates pass. Canonical attack decision loss falls from `3.509` to `0.437`, an improvement of `3.0717`, 95% CI `[3.0634, 3.0795]`. Mild, moderate, and severe attack losses are `0.317`, `0.345`, and `0.339`, all below the independently derived `1.50` availability ceiling. Across all seven controls, decision loss is exactly unchanged, non-strategic alert and material wrong-action rates are zero, and mean NEES is `1.60–1.80`.

Reanalysis reproduces the verdict from 8,250 saved arm rows and verifies all 1,650 exogenous traces and frozen hashes:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-adversarial-trust-suite \
  --output results/milestone10a_heldout \
  --bootstrap-samples 5000
```

This `GO` authorizes a closed-loop research integration only. M10A is still a shadow assay against declared scripted attacks; it does not establish production security or robustness to adaptive adversaries.

## Milestone 10A.5 closed-loop trust integration

Version 0.15 injects frozen M10A trust into frozen M9C through a
dependency-isolated compatibility harness. Trust-adjusted assignment evidence
changes subsequent sensing geometry, and a bounded trusted-sensor verification
action exercises the feedback path. The no-defense arm reproduces historical
M9C exactly.

The powered held-out result is **`M10A5-GO`**: all 16 gates pass on seeds
`23000–23149`. Canonical attack decision loss is `0.434`, with improvement
`3.084`, 95% CI `[3.077, 3.091]`; maximum attack movement increase is `0.0278`
per step; trust recovers within eight cycles; and control noninferiority,
false-alert, calibration, wrong-action, quarantine, replay, and feedback gates
all pass.

```bash
PYTHONPATH=src python3 -m flockkalman closed-loop-trust-suite \
  --phase heldout --seed-count 150 --seed-start 23000 --workers 8 \
  --output results/milestone10a5_heldout
```

## Milestone 10B decentralized allocation

Version 0.16 gives each agent ownership of its own sensing goal. Replanning is
staggered, actions persist asynchronously, and each delivered neighbour sees
at most one deterministic four-scalar proposal. Local winner resolution
reduces conflict; trust verification outranks ordinary assignment probing.

The powered result is **`M10B-GO`** with all 15 gates passing on seeds
`25000–25149`. Centralized compatibility and ownership violations are exactly
zero, message bounds hold, worst natural noninferiority LCB is `-0.0079`
against `-0.05`, canonical attack loss is `0.437`, and topology, calibration,
honest recovery, asynchronous-path, negotiation, and runtime gates pass.

```bash
PYTHONPATH=src python3 -m flockkalman decentralized-suite \
  --phase heldout --seed-count 150 --seed-start 25000 --workers 8 \
  --output results/milestone10b_heldout
```

## Milestone 11 external MR.CLAM replay

Version 0.17 adds causal known-map localization on the official UTIAS MR.CLAM
logs. The filter predicts from recorded odometry, selects at most two current
landmark observations by expected covariance reduction, and uses Vicon truth
only for initialization and post-estimate scoring.

Dataset 1 development passed, but the frozen Dataset 9 parser rejected four
negative initial odometry timestamp jumps before estimation. That result
remains **`M11-INVALID`**. M11.1 adds an auditable stable timestamp sort that
preserves every row and records source/canonical hashes, then recalibrates
process uncertainty on Dataset 9. The repaired source was frozen before
Dataset 6 was extracted.

The replacement held-out result is **`M11.1-GO`**, all gates passing. Bounded
RMSE is `0.514 m` versus `2.163 m` odometry-only; mean NEES is `1.93`, coverage
`0.899`, and the exact two-update budget, outage, connected/disconnected
topology, malformed-input, hash, determinism, and runtime gates pass.

```bash
PYTHONPATH=src python3 -m flockkalman external-replay-repair-suite \
  --dataset external_data/MRCLAM_Dataset6 \
  --canonical external_data/MRCLAM_Dataset6_canonical \
  --archive external_data/MRCLAM6.zip \
  --phase heldout \
  --output results/milestone11_1_heldout
```

## Milestone 12 acceleration ablation

Version 0.18 separately tests a five-state measured-acceleration replay filter
and a behavioural jerk limiter. The estimator is a decisive development
**`NO-GO`**: RMSE worsens from `0.313` to `0.521 m`, mean NEES rises to
`19.38`, outage RMSE doubles, and the paired improvement interval is wholly
negative. Acceleration is exercised on 42.3% of cycles, so this is not a dead
code path. Dataset 7 remains unextracted and untested.

The isolated behavioural assay passes: peak jerk falls 90%, from `16.0` to
`1.6 m/s³`, within the `0.8 m/s²` acceleration limit and with `0.045 m/s`
added velocity RMSE. Keep the jerk limiter as a future controller ablation; do
not add the tested acceleration state to the replay filter.

```bash
PYTHONPATH=src python3 -m flockkalman acceleration-suite \
  --dataset external_data/MRCLAM_Dataset1 \
  --canonical external_data/MRCLAM_Dataset1_canonical \
  --archive external_data/MRCLAM1.zip \
  --phase development \
  --output results/milestone12_development
```

## Milestone 13 external full-loop validation

Version 0.19 implements M13.0–M13.3 without changing the frozen M9C, M10A.5,
or M10B candidates. It adds canonical wire messages, recursive truth-leak
checks, exact byte accounting, deterministic delay/loss/partition/outage,
bounded causal attack shims, a final command safety supervisor, hash-chained
operational/transport/safety/truth ledgers, a buildable ROS 2 message package,
and independent physical scoring.

The powered independent reference screen ran 6,000 trials—four arms, ten
scenarios, and 150 paired seeds—and returned
**`M13.1-HIL-PILOT-READY`** with all 12 entry gates passing. The decentralized
candidate's integrated-loss improvement over centralized was `-0.00362`, 95%
CI `[-0.00447, -0.00279]` (positive favours decentralized), above the frozen
`-0.05` noninferiority floor. Wrong actions, collisions, emergency stops,
ownership violations, and message-bound violations were all zero.

```bash
PYTHONPATH=src python3 -m flockkalman full-loop-hil-suite \
  --steps 120 --seed-count 150 --seed-start 27000 \
  --bootstrap-samples 2000 --workers 8 \
  --output results/milestone13_1_hil
```

M13.2/M13.3 are implemented but do not yet have physical results. A randomized
320-run pilot schedule is in `physical/m13_pilot_plan/`. The pilot command
rejects synthetic and loopback evidence; the holdout additionally rejects
pilot reuse, source drift, incomplete blocks, fewer than three days, and
underpowered scenarios. Start with `M13_PROTOCOL.md`, then use:

```bash
flockkalman seal-physical-bundle --bundle RUN_DIR
flockkalman score-physical-bundle --bundle RUN_DIR
flockkalman physical-pilot --bundles PILOT_RUN_DIRS... \
  --output results/milestone13_2_pilot
flockkalman physical-heldout \
  --freeze results/milestone13_2_pilot/power_freeze.json \
  --bundles HELDOUT_RUN_DIRS... \
  --output results/milestone13_3_heldout
```

M13.1 is authorization to begin the instrumented pilot, not external physical
validation and not deployment authorization.

Primary metrics are:

- **Position RMSE:** root mean squared error of the conservatively fused team position.
- **Best-hypothesis RMSE:** evaluation-only error of the returned hypothesis nearest truth; this measures mode retention and is not available to an operational selector.
- **Decision loss:** selected or mixed output error, or best retained-hypothesis error plus declared deferral/investigation costs.
- **Output safety:** action rates, confidence, material wrong-mode actions, and ambiguity-resolution delay.
- **NEES and 95% coverage:** whether each agent's covariance matches its observed error. For a calibrated two-dimensional position estimate, mean NEES should be near 2 and coverage near 0.95.
- **Information gain:** expected Gaussian information from the current range-dependent observation model against a fixed reference prior.
- **Spatial diversity:** mean pairwise sensor distance.
- **Estimate disagreement:** mean pairwise distance between agents' target estimates.
- **Recovery:** steps after the manoeuvre until error returns below an automatically derived threshold for a sustained window.
- **Communication:** directed messages and serialized float payload bytes. Protocol overhead is intentionally excluded.

## Tests

The tests use the standard library test runner:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The 59 tests cover all historical checks plus M13 wire serialization and byte accounting, covariance/truth rejection, deterministic partitions, bounded adaptive attacks, hash-chain domains, full-loop replay, complete HIL artifacts, randomized physical plans, independent scoring, and rejection of synthetic pilot evidence.

## Interpreting the first experiment

The platform is designed for falsification, not to make the adaptive method win. The useful first questions are:

1. Does adaptive momentum reduce recovery time relative to fixed momentum?
2. Does it improve information gain or RMSE without damaging NEES and coverage?
3. Does flocking preserve useful sensor diversity rather than collapsing the group?
4. Is any improvement large enough to justify its communication cost?

The flocking variants should not be promoted on RMSE alone. A gain that relies on overconfident covariance, mode collapse, or excessive communication is a negative result.

## Important limitations

- The platform now includes a moment-matched range–bearing research sensor, but the local estimator remains a linear Cartesian Kalman filter rather than a production nonlinear/non-Gaussian filter.
- Covariance intersection is safe but can be conservative and order-sensitive when applied repeatedly.
- The communication metric counts payload bytes, not packet framing, retries, latency, or energy.
- `flocking_only` has calibrated instantaneous measurement covariance but no temporal predictive belief.
- The benchmark represents physical investigative velocity. Moving into abstract hypothesis or language-agent spaces requires a validated state representation and observation-noise model.
- Best-hypothesis RMSE uses simulation truth only for evaluation; it does not solve operational primary selection.
- The current strategic stress follows a declared seeded ramp; it is not an adversary that adapts to the detector.
- M7's decision claim is conditional on its declared abstention-loss model and does not cover deferral cost `1.50`.
- Decision-equivalent support uses a fixed Euclidean distance; M8 exercised it under nonlinear and heterogeneous sensing but did not validate heterogeneous physical units.
- M9A repairs the prior covariance inconsistency and heavy topology tails, but its conservative missing-evidence policy still breaches the frozen transfer margin in five dynamic cases.
- M9A.5 uses a declared and unusually informative secondary-mode assignment model; its Bayesian references are diagnostic comparators, not distribution-free theoretical optima or production policies.
- The M9A.5 observer reference narrowly misses the original margin under asymmetric partition, while ideal global access passes. A disconnected local component cannot be expected to reproduce the global result without a separately evaluated communication mechanism.
- M9A.6's residual mass is a prospectively tuned posterior-predictive NIS surrogate, not a formal posterior spanning every possible unknown model.
- M9A.6 detects declared count and offset misspecification but misses admission-censored evidence when the observed subset remains internally model-consistent; its historical held-out verdict remains `NO-GO`.
- M9A.7 repairs the evaluated admission-censored topology tails, but its permissive raw path pays severe decision loss under the fixed colluding-ramp attack even though its wrong-action and quarantine gates pass.
- The causal ablation shows more information but no decision-loss benefit from the current investigative motion.
- M9B's mechanism transfers through the M9C outage/partition suite, but M9C still computes each observer component's actions from shared component state rather than through genuinely decentralized ownership, negotiation, and asynchronous replanning.
- M9C assumes the declared assignment mask, secondary offset, and Gaussian pose-conditioned likelihood; its small utility gain is tied to the registered movement price and does not establish robustness to arbitrary latent modes.
- M10A.5 places the declared trust repair into the physical sensing feedback loop, but it still does not model an attacker that adapts to detector state.
- The M10A attacker follows preregistered ramp families and does not adapt to detector state; the trust mechanism is not a general Byzantine-resilience or security proof.
- M10B decentralizes sensing-goal ownership and bounded proposal exchange, not every estimator/fusion operation or the simulator's exogenous network process.
- M11.1 validates causal bounded known-map localization on real MR.CLAM logs; it does not externally validate the simulator's adversarial assignment, trust, or active-allocation mechanisms.
- Original M11 remains `INVALID` because Dataset 9 violated the frozen timestamp-order assumption. M11.1's repair is transparent and prospectively retested, not a retroactive relabelling.
- M12's measured-acceleration filter is rejected: it worsens RMSE, outage error, and calibration. The passing jerk limiter is only an isolated deterministic behavioural assay.
- M13.1 uses an independent but deterministic software plant and packet scheduler. It is not measured Wi-Fi/DDS, a physical camera qualification, or an external robot result.
- The ROS 2 interface package is hardware-ready, but robot drivers, camera calibration, MCAP export, safety I/O, and truth capture remain site-specific adapters that must qualify in M13.2.

M10A.5, M10B, M11.1, and the M13.1 pilot-entry screen clear their powered gates. The next bounded action is to execute the generated M13.2 instrumented pilot and freeze M13.3 from those genuine external measurements. Do not include kinematic state expansion.
