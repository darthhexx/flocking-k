# Flocking–Kalman Multi-Agent Research System

**Engineering design specification — version 0.19**  
**Status:** M13.0–M13.3 validation software is implemented; the 6,000-trial independent M13.1 screen is `HIL-PILOT-READY`; M13.2/M13.3 remain awaiting genuine external physical evidence; production is not authorized  
**Date:** 23 July 2026

This Markdown file is the canonical engineering and research specification. Earlier Word documents are historical motivation only; where they differ, this file and the executable configuration take precedence.

## 1. Purpose

This platform tests a specific connection between flocking and state estimation: a group of mobile agents can use local Kalman beliefs to decide how to move, while their movement changes the quality and diversity of the evidence available to the group.

The system is deliberately a research platform rather than a production autonomy stack. It addresses three initial objectives:

1. provide a reproducible numerical benchmark for active multi-agent sensing;
2. compare independent estimation, conservative distributed fusion, flocking, and recurrent investigative motion through controlled ablations;
3. produce decision-grade evidence using calibration, fault, communication, and held-out statistical tests—not RMSE alone.

The current research claim remains bounded: the system can select when aggregated support is decisive and safely defer under symmetric ambiguity in this simulation family. M8 showed that agent failure plus graph partition broke calibrated transfer. M9A repairs uncertainty bookkeeping, rejoin shock, partition-local output, and covariance tails, but its original stable-transfer gate remains a `PARTIAL-GO`. M9A.5 found substantial same-information policy headroom plus one narrow component-information boundary. M9A.6 closed most of that headroom but exposed a rare admission-censored failure+partition tail. M9A.7 structurally separates current raw measurements from recursively fused belief admission and passes all 13 powered held-out gates on 300 seeds per scenario. M9B separately shows that two-step receding-horizon value of information reduces movement-inclusive loss when candidate views genuinely compete. M9C transfers that mechanism into dynamic topology: its component-local allocator improves held-out movement-inclusive loss over broad investigation by `0.00293`, 95% CI `[0.00228, 0.00359]`, while preserving measured topology safety, but the historical verdict is `PARTIAL-GO` because its colluding-ramp decision loss is `3.507` against the frozen `1.50` ceiling.

M10A repairs that declared availability failure as an output-layer trust assay
on the frozen M9C trajectory. M10A.5 then closes the feedback loop and passes
all 16 powered held-out gates; M10B replaces component-centralized action
selection with per-agent asynchronous ownership and passes all 15 powered
gates. External replay initially fails closed because official MR.CLAM Dataset
9 contains four negative initial odometry timestamp jumps. The failure remains
`M11-INVALID`; a transparent M11.1 stable-sort repair, development recalibration,
and untouched Dataset 6 hold-out then pass all gates. Finally, M12's causal
five-state measured-acceleration filter is decisively worse than the replay
baseline (`0.521` versus `0.313 m` RMSE), so Dataset 7 stays unopened and that
estimator branch stops. The separately tested jerk limiter reduces peak jerk
by 90% and remains a future behavioural component. These are research results,
not evidence of production security.

M13 now implements the full external-validation boundary: operational wire
contracts, truth-domain isolation, exact byte accounting, deterministic
network faults, bounded causal attackers, command safety, sealed raw evidence,
independent rescoring, pilot power freeze, and a preregistered physical
holdout. Its independent reference screen passes all 12 entry gates across
6,000 paired trials. The decentralized candidate is slightly worse than the
centralized arm on integrated loss (`-0.00362`, 95% CI
`[-0.00447, -0.00279]`, positive favouring decentralized) but comfortably
inside the frozen `-0.05` noninferiority margin. This authorizes only the M13.2
pilot. No physical bundle has been collected, so no external full-loop claim
has been made.

## 2. Research questions and current answers

| Question | Current answer |
|---|---|
| Can flocking and Kalman estimation be usefully coupled? | Yes. The estimator supplies local beliefs to the motion policy; motion changes future observation quality. |
| Should velocity be recurrent? | Yes within the evaluated family: held-out M4 and the M8.2 training sweep favour nonzero recurrence. The best value varies by scenario, however, and the tested geometry signature does not explain the gain. |
| Can guarded adaptive recurrence beat fixed recurrence? | Not yet. M5 was a held-out `NO-GO`; guards were safer than direct adaptation but did not improve fixed recurrence. |
| Can robust fusion repair bias, stale-belief, and incompatible-mode failures? | Yes at hypothesis-set level. M6 passed all 12 frozen held-out gates. |
| Can the platform safely handle a perfectly symmetric two-mode case? | Yes by deferring, not by pretending to know. M7 abstained on 97.74% of held-out equal-mode cycles and materially selected the wrong mode on 0.67%. |
| Can it select when support is unequal? | Yes in the tested five-versus-three case: M7 selected on 97.54% of cycles with a 1.3% material wrong-action rate. |
| Does the M7 system transfer through the realism ladder? | Mostly, but not fully. Nine of ten ordered M8 layers passed; temporary agent failure plus graph partition breached the transfer margin and degraded calibration. |
| Does investigative motion itself help? | It significantly increased information gain, but did not reduce decision loss versus an otherwise-identical no-investigation controller. |
| Was M8 capable of identifying a useful active-sensing effect? | No. Most ambiguity ended exogenously and hypothesis weights were based on agent membership, not viewpoint evidence. M8.1 corrects this with an endogenous Bayesian range-only assay. |
| Can viewpoint motion resolve endogenous ambiguity? | Yes in the M8.1 binary positive control. Passive sensing remained unresolved; every nonzero tested dose resolved all 100 held-out runs safely. |
| Is the M8 production allocator thereby validated? | No. Full-dose round-robin, information-oracle, and one-step VOI policies tie in the simple positive control, so policy quality is not yet identified. |
| Can a nonmyopic VOI allocator beat round-robin when views and costs compete? | Yes in the M9B static assay. It reduced held-out movement-inclusive loss by `0.5737`, 95% CI `[0.5293, 0.6196]`, with zero wrong selections and gains in all five task families. |
| Did M9B improve raw decision accuracy or speed? | No. Both policies made zero held-out wrong selections, and round-robin resolved about `0.43` cycles faster. M9B won by using substantially less costly motion. |
| Can M9B enter the production stack now? | Not as production. M9A.7 now authorizes a bounded integration experiment, but M9B remains centralized, static, and dependent on a known pose-conditioned likelihood and declared movement cost. |
| Did M9A repair topology uncertainty? | Yes at the safety and calibration layers. All held-out replay, calibration/tail, wrong-selection, rejoin-shock, partition-accounting, support-continuity, and stable-noninferiority gates passed. |
| Did M9A qualify production transfer? | No. The held-out verdict is `M9A-PARTIAL-GO`; dynamic-transfer LCBs ranged from `-0.2724` to `-0.0331`, and five of seven dynamic cases breached the declared `-0.10` margin. |
| Is M9A's remaining transfer cost irreducible? | Mixed. The M9A.5 observer-component Bayesian reference clears six of seven cases and misses asymmetric partition narrowly (`LCB -0.1053`); the ideal-global reference clears all seven. Thus one strict boundary is information-limited, but current M9A also has large same-information policy/representation headroom. |
| Can unknown-support repricing alone repair M9A? | Not every case. The truth-using floor over the frozen returned set still fails failure+partition (`LCB -0.1337`), so the next milestone must improve the missing-evidence hypothesis representation as well as the action price. |
| Did M9A.6 close the same-information policy gap? | Mostly, but not completely. It improved held-out loss in every exact-model scenario with zero material wrong point selections, yet failure+partition observer regret had UCB `0.1568` against the frozen `0.10` limit. |
| Did residual model-mismatch support work? | In the declared count/offset challenges, yes: mean residual mass rose to `0.402/0.132` and abstention to `0.498/0.452`. It did not detect admission-censored missingness when the smaller visible subset remained internally model-consistent. |
| Did M9A.7 repair admission-censored topology tails? | Yes in the powered held-out protocol. All 13 gates pass; failure+partition observer-regret mean/P95/max bounds are `0.023/0.070/0.103`, versus frozen limits `0.10/0.20/0.75`. |
| Is the permissive raw channel production-safe? | Not established. The colluding understated-covariance ramp caused zero wrong actions and no quarantine increase, satisfying the frozen safety gate, but candidate loss rose from `1.105` to `3.502` through conservative deferral. |
| Does M9B-style VOI transfer into the dynamic M9A.7 stack? | Yes, narrowly, at the registered movement price. On 150 held-out seeds per scenario, VOI beat broad investigation in aggregate by `0.00293`, 95% CI `[0.00228, 0.00359]`, and in the source-competition positive control by `0.00749`, `[0.00444, 0.01059]`. |
| Did integration preserve topology and output safety? | Yes in the declared suite. Wrong actions remained zero, the worst natural M9A.7 noninferiority LCB was `0.00682`, the worst delivery LCB was `-0.00112`, and maximum mean component-count increase was `0.0106`. |
| Did M9C repair the raw-channel attack? | No. It did not worsen the attack under the integrated-loss gate and disabled extra probing, but absolute decision loss was `3.507` against the frozen `1.50` ceiling; the verdict is `M9C-PARTIAL-GO`. |
| Can a causal raw-channel trust layer repair that failure? | Yes in the declared M10A output-layer assay. All 16 held-out gates pass; attack losses are `0.317–0.437`, every control is exactly noninferior, false-alert and material-wrong-action rates are zero, and calibration remains inside the frozen limits. |
| Is trust now part of the closed-loop stack? | Yes in M10A.5's declared simulator envelope. All 16 held-out gates pass, canonical attack loss is `0.434`, controls remain noninferior, and trust recovers within eight cycles. This is not a general security result. |
| Is sensing allocation genuinely decentralized? | Yes at the planner boundary tested by M10B. Per-agent asynchronous ownership, bounded four-scalar neighbour proposals, conflict resolution, and partition-aware persistence pass all 15 held-out gates. The estimator and environment remain simulator-specific. |
| Does the system transfer to recorded data? | Yes for a bounded known-map localization claim after an explicitly recorded repair. Original M11 is `INVALID` on Dataset 9 timestamp ordering; M11.1 preserves every row, recalibrates on Dataset 9, and passes untouched Dataset 6 with `0.514 m` bounded RMSE, NEES `1.93`, and coverage `0.899`. |
| Should estimator acceleration be added now? | No for the implemented M12 formulation. The measured-acceleration filter worsens development RMSE from `0.313` to `0.521 m`, has NEES `19.38`, and doubles outage RMSE; Dataset 7 remains sealed. Retain the separately passing jerk limiter only as a future behavioural ablation. |
| Is the full-loop external-validation harness ready? | Yes for entry to a physical development pilot. M13.1 ran 6,000 independent reference-HIL trials, passed all 12 frozen entry gates, reproduced exactly, and kept scorer truth outside operational records. |
| Has the trust-plus-allocation stack passed external physical validation? | Not yet. M13.2 and M13.3 are implemented but intentionally refuse synthetic, loopback, unsealed, underpowered, or source-drifted evidence. Genuine instrumented robot runs are still required. |

### 2.1 Related work and claim positioning

The broad combination of flocking, distributed estimation, and information-improving mobility is established prior art. Olfati-Saber formalized Reynolds-style distributed flocking and later applied distributed Kalman filtering with information-driven flocking mobility to mobile target tracking. Consensus-based distributed filtering and switching-topology analysis are likewise established. Covariance intersection is the standard conservative response to unknown cross-correlation. Information-driven mobile sensing commonly optimizes entropy or mutual information, while decision-directed active perception and value-of-information methods instead optimize task consequences such as classification error, decision loss, and motion cost.

Core references:

- Reza Olfati-Saber, [“Flocking for Multi-Agent Dynamic Systems: Algorithms and Theory”](https://authors.library.caltech.edu/records/srjr9-h3r57), 2004/2006.
- Reza Olfati-Saber, [“Distributed Tracking for Mobile Sensor Networks with Information-Driven Mobility”](https://tr.engineering.dartmouth.edu/reports/tr06-002.pdf), 2006.
- Reza Olfati-Saber, J. A. Fax, and R. M. Murray, [“Consensus and Cooperation in Networked Multi-Agent Systems”](https://murray.cds.caltech.edu/index.php/Consensus_and_Cooperation_in_Networked_Multi-Agent_Systems), 2007.
- S. J. Julier and J. K. Uhlmann, “A Non-divergent Estimation Algorithm in the Presence of Unknown Correlations,” ACC 1997, DOI `10.1109/ACC.1997.609105`.
- G. M. Hoffmann and C. J. Tomlin, [“Mobile Sensor Network Control Using Mutual Information Methods and Particle Filters”](https://ai.stanford.edu/~gabeh/papers/infoControl.pdf), IEEE TAC 2010.
- N. Atanasov et al., [“Nonmyopic View Planning for Active Object Classification and Pose Estimation”](https://erl.ucsd.edu/ref/Atanasov_ActiveObjectRecognition_TRO14.pdf), IEEE TRO 2014.
- A. Krause and C. Guestrin, [“Optimal Value of Information in Graphical Models”](https://arxiv.org/abs/1401.3474), JAIR 2009.
- H. Chernoff, [“Sequential Design of Experiments”](https://doi.org/10.1214/aoms/1177706205), Annals of Mathematical Statistics 1959.
- M. Naghshvar and T. Javidi, [“Active Sequential Hypothesis Testing”](https://arxiv.org/abs/1203.4626), Annals of Statistics 2013.
- M. Naghshvar and T. Javidi, [“Sequentiality and Adaptivity Gains in Active Hypothesis Testing”](https://arxiv.org/abs/1211.2291), IEEE JSTSP 2013.
- S. Nitinawarat, G. K. Atia, and V. V. Veeravalli, [“Controlled Sensing for Multihypothesis Testing”](https://arxiv.org/abs/1205.0858), IEEE TAC 2013.
- S. Nitinawarat and V. V. Veeravalli, [“Controlled Sensing for Sequential Multihypothesis Testing with Controlled Markovian Observations and Non-Uniform Control Cost”](https://arxiv.org/abs/1310.1844), 2013.

| Platform finding | Position against prior work | Permitted claim |
|---|---|---|
| Flocking coupled to distributed Kalman tracking | Direct confirmation/replication of an established connection, especially Olfati-Saber. | The platform independently reproduces and stress-tests the connection; it does not originate it. |
| Fixed velocity recurrence improves RMSE | Platform-specific empirical result; the M8.2 sweep found no supporting sensor-diversity mechanism and no single best timescale across scenarios. | `rho = 0.72` remains a frozen supported baseline for prior comparisons, not a portable optimum or mechanistic law. |
| Covariance-intersection fusion under repeated exchange | Application of established conservative fusion. | Novelty is not claimed for CI; the contribution is its controlled use inside explicit incompatible hypothesis flocks. |
| Explicit mode retention plus truth-blind, costed deferral | Chernoff-style sequential experiment design and the Naghshvar–Javidi/Nitinawarat–Veeravalli active-testing literature already establish adaptive action choice under observation, delay/control cost, and wrong-declaration risk. | Novelty is not claimed for costed active hypothesis testing. The contribution is the topology-aware engineering synthesis, split evidence admission, and preregistered simulator evidence. |
| Two-step M9B VOI allocation | Closely aligned with active sequential multihypothesis testing; finite-horizon sampled Bayes risk is an engineering approximation, not a new optimality result. | Claim only a held-out efficiency gain in the five declared static tasks and within the measured movement-cost envelope. |
| Split raw-measurement/shared-belief admission | A system-specific response to recursive fusion lineage and missing-not-at-random admission; the current literature pass does not establish this exact architecture as novel. | Claim a causally validated repair within the simulator, not a general theorem or distribution-free trust solution. |
| M8 information gain without decision-loss gain | Consistent with the known distinction between generic uncertainty reduction and decision-relevant value of information. | The current low-dose allocator failed; the broader active-sensing hypothesis was not identified because M8 lacked endogenous, viewpoint-resolvable ambiguity. |
| Dynamic-topology covariance inconsistency | Expected failure mode under stale/rejoining information and changing participation. | M8 quantifies the boundary; it does not establish a new theoretical failure. |

The reasoning-agent analogy remains quarantined. None of these physical-space results validates Euclidean, Gaussian, or kinematic structure for language-model hypothesis spaces.

## 3. Scope

### 3.1 In scope

- two-dimensional manoeuvring-target simulation;
- range-dependent Cartesian or nonlinear range–bearing observations with heterogeneous sensor quality;
- topological neighbour graphs, independent or burst-correlated directed dropout, per-sender delay, and clock skew;
- linear constant-velocity Kalman filters;
- conservative belief exchange through covariance intersection;
- Reynolds-style goal, alignment, cohesion, and separation motion;
- zero, fixed, direct-adaptive, and guarded recurrent velocity policies;
- source-bias tracking, drift and recovery, Byzantine and colluding-ramp stress, and explicit multi-flock hypotheses;
- temporary agent outages, graph partitions, and deterministic scenario fingerprints;
- truth-blind selection, moment matching, bounded investigation, and explicit deferral;
- a binary range-only endogenous-ambiguity assay with Bayesian mode updates, investigation dose, an information oracle, and one-step value of information;
- three- and four-mode competing-view assays with skewed priors, asymmetric movement costs, limited probes, and exhaustive horizons one through three;
- replayable trials, paired bootstrap confidence intervals, and automatic decision gates;
- causal observer-component and ideal-global Bayesian references that marginalize hidden secondary-mode assignments on frozen M9A trajectories;
- an output-only missing-evidence posterior with explicit residual model-mismatch support and risk-priced actions;
- separate current-measurement and recursive-belief admission with covariance flooring;
- component-local two-step value-of-information motion on dynamic topology;
- output-layer and closed-loop cross-channel trust, ramp-rate evidence, suspicious-source influence budgeting, and trusted-sensor verification;
- per-agent asynchronous sensing-goal ownership with bounded neighbour proposals and local conflict resolution;
- causal known-map replay on real MR.CLAM odometry, range-bearing, topology, outage, and truth logs with auditable timestamp canonicalization;
- a measured-acceleration estimator ablation and a separate behavioural jerk-limiter assay.
- canonical full-loop wire messages, ROS 2 interface definitions, network and attack manifests, hash-chained evidence, clock/truth audits, and command safety;
- an independent range-bearing HIL plant with four registered arms and ten physical/fault scenarios;
- physical pilot scoring, variance-based power, candidate/protocol freeze, and a fail-closed held-out evaluator.

### 3.2 Out of scope for version 0.19

- collision-certified trajectory planning;
- a claim that the M13.1 reference process is physical evidence;
- M13.2 calibration or M13.3 scientific verdict before genuine robot bundles;
- cryptographic identity or security proof against unrestricted attackers;
- nonlinear or non-Gaussian production filtering beyond the declared moment-matched research sensor;
- semantic-agent state representations;
- a learned or externally informed hypothesis selector;
- fully decentralized fusion/state estimation beyond M10B planner ownership;
- acceleration-state production models or promotion of the rejected M12 estimator.

## 4. System model

### 4.1 Target and local filter

Each local filter uses the state

```text
x = [p_x, p_y, v_x, v_y]^T
```

with constant-velocity transition

```text
x(t+1) = F x(t) + w(t)
z_i(t) = H x(t) + b_i(t) + n_i(t)
```

where `w` is process noise, `n_i` is sensor noise, and `b_i` is an optional persistent source offset. Measurement variance grows with sensor-to-target distance, making agent movement causally relevant to future information.

Delayed peer beliefs are propagated to the current cycle before compatibility testing or fusion. Their covariance receives the corresponding process-noise growth. Comparing unaligned timestamps is forbidden because it can manufacture false disagreement.

### 4.2 Conservative distributed fusion

Agents exchange posterior means and covariances with up to `k` topological neighbours. Because repeated exchange creates unknown cross-correlation, compatible beliefs are combined using covariance intersection:

```text
P_CI^-1 = omega P_a^-1 + (1 - omega) P_b^-1
x_CI    = P_CI [omega P_a^-1 x_a + (1 - omega) P_b^-1 x_b]
```

`omega` is selected by a deterministic grid search. Fusion must never occur across incompatible hypothesis flocks.

### 4.3 Flocking and investigative momentum

The non-recurrent desired velocity combines local terms:

```text
u_i = goal_i + alignment_i + cohesion_i + separation_i
```

The executed command is

```text
v_i(t+1) = clip[rho_i(t) v_i(t) + (1 - rho_i(t)) u_i(t)]
```

`rho` is investigative momentum. It belongs to the behavioural motion controller, not the Kalman transition. The supported setting remains fixed `rho = 0.72`. Direct NIS adaptation is retained as a negative control; the guarded M5 variant is retained as a research artifact.

### 4.4 Robust source assessment

The M6 tracker computes a coordinate-wise median observation centre and an exponentially smoothed source residual:

```text
c(t)       = median_i z_i(t)
b_hat_i(t) = (1 - alpha) b_hat_i(t-1) + alpha [z_i(t) - c(t)]
```

Persistent displaced minorities become suspected bias sources and then quarantined sources. Their local measurement is bias-corrected, but their belief is excluded from team fusion while suspected. Large coherent displaced groups are not erased: they are labelled as supported alternative modes.

Current defaults are `alpha = 0.18`, bias norm threshold `0.75`, group tolerance `0.90`, and quarantine persistence `5` cycles.

### 4.5 Explicit hypothesis flocks

Trusted posterior pairs are compatible when

```text
d^2_ij = (x_i - x_j)^T (P_i + P_j)^-1 (x_i - x_j) <= 9.21
```

using the position subspace. Connected compatible components form hypothesis flocks. Covariance intersection occurs only within a component. Each flock exposes:

- member identities;
- fused state and covariance;
- evidence weight equal to its fraction of trusted members;
- stable deterministic ordering for replay.

Explicit mode labels override accidental Gaussian overlap, preventing a supported alternative from being fused away.

### 4.6 Truth-blind hypothesis-output policy

M7 maps the retained hypothesis set to one of four externally visible actions: `select`, `mixture`, `investigate`, or `defer`. The promoted active policy uses only flock states, covariances, weights, and its own output history.

Nearby Gaussian fragments within `2.0` position units are grouped for decision-level support accounting, but remain separate M6 flocks for conservative estimation. A mode is decisive when the leading grouped support exceeds the runner-up by at least `0.15`. Ambiguity must persist for three cycles before intervention; investigation lasts at most eight cycles, after which unresolved evidence is explicitly deferred. Resolution must persist for three cycles before selection resumes.

The evaluation loss is

```text
L(select or mixture) = output position error
L(defer)             = best retained-hypothesis error + C_defer
L(investigate)       = best retained-hypothesis error + C_defer + C_investigate
```

with declared costs `C_defer = 0.75` and `C_investigate = 0.10`. Truth is used only to score this loss after an action. Counterfactual analysis tests deferral costs from `0.25` to `1.50` without changing actions.

### 4.7 M8 realism and causal ablation model

The M8 scenario layer adds opt-in deterministic disturbances while leaving every M7 default and original random-number stream unchanged:

- directed link outages follow a two-state entry/recovery process on top of independent dropout;
- message age is generated per sender from fixed delay, bounded jitter, and a seeded clock offset;
- range–bearing samples are converted to unbiased Cartesian pseudo-measurements using exact first and second moments for independent Gaussian range and bearing noise;
- each sensor has a seeded fixed noise multiplier;
- persistent biases may drift and recover, while colluding sources can ramp a shared offset while reporting understated covariance;
- seeded agents may become inactive and later recover;
- a time-bounded index partition removes cross-partition communication edges.

Inactive agents neither sense, communicate, nor move. Delayed beliefs are selected per sender and propagated to the current cycle before compatibility or covariance intersection. Every materialized scenario is hashed with SHA-256 over its full configuration and exogenous arrays; M8 regenerates and verifies all hashes after the trial matrix.

The causal control is `flocking_robust_active_no_investigation`. It uses the same M7 active output controller, actions, action costs, estimator, and fixed recurrence. The sole intervention is that an `investigate` action retains ordinary flocking goals instead of allocating agents across candidate modes. Downstream trajectories may then diverge, as required for a physical-motion ablation.

### 4.8 M8.1 endogenous-ambiguity positive control

M8.1 isolates the information-to-decision path from the production realism ladder. The hidden target is one of two equally likely stationary modes at `(-5, 0)` and `(5, 0)`. Eight range-only sensors begin on the perpendicular bisector `x=0`, where both modes generate identical range distributions. A sensor that remains on the bisector is therefore uninformative by construction; lateral movement makes the likelihoods separable.

For sensor positions `s_i`, mode positions `h_k`, and range noise standard deviation `sigma`, the mode likelihood is

```text
p(z | h_k, s) = product_i Normal(z_i; ||s_i - h_k||, sigma^2)
```

Bayesian log odds update from these pose-conditioned likelihoods. The policy selects only from posterior mode probability, predicted likelihood, and declared decision/movement cost; truth is used solely to generate measurements and score wrong selection. Resolution occurs when either posterior mode probability reaches `0.95`. The per-view discriminability diagnostic is

```text
D(s) = sum_i (mu_i,1(s) - mu_i,0(s))^2 / (2 sigma^2)
```

The assay compares passive motion, the existing round-robin pattern over a frozen dose sweep, a one-step discriminability oracle, and a one-step expected-decision-risk-plus-motion-cost policy. Its purpose is to prove that useful active sensing is identifiable in the platform. It is intentionally not a model of the full M8 fusion/topology stack.

### 4.9 M9B competing-view value of information

M9B generalizes the positive control to three or four stationary modes on a common-radius circle. Co-located sensors at the circle centre initially receive identical range likelihoods under every mode. Each action is one of:

- `hold`: no commanded motion;
- `probe_k`: allocate two of eight sensors toward mode `k` while other commands decay through fixed recurrence;
- `spread`: allocate every sensor round-robin across all modes.

Scenarios vary prior probability, angular mode separation, observation noise, broad-spread cost, and per-probe transit cost. At every cycle, the categorical posterior is updated from the full pose-conditioned range likelihood. The operational selection threshold is frozen at `0.99`.

The planner minimizes sampled expected cumulative loss over deterministic action sequences:

```text
J = expected[sum unresolved C_defer + wrong-selection C_wrong
             + sum action movement cost]
```

The boundary of a truncated action horizon prices unresolved ambiguity through the remaining trial deadline. Nine fixed antithetic Gaussian planning samples are common across policy horizons and independent of the realized trial noise. The policies are passive, current round-robin, myopic VOI at horizon one, receding-horizon VOI at horizon two, and a truth-blind exhaustive horizon-three comparator. Every optimized policy replans after each observation; the horizon-three comparator is computational, not clairvoyant.

The reported `total_decision_loss` includes movement cost. `decision_cost` and `movement_cost` remain separate artifacts so an efficiency win cannot be misreported as an accuracy or latency win.

### 4.10 M9A topology-resilient evidence model

M9A separates graph reachability, lifecycle admission, hypothesis compatibility, and evidential support. The delivered directed graph is converted into deterministic weak components each cycle. A predeclared observer component—normally the component containing agent `0`—is the only component visible to the external output. Evidence outside that component is `unknown`; it is not silently removed from the denominator.

Each returned flock carries `live_support`, `retained_support`, `unknown_support`, unique contributor identities, component identity, and component epoch. Live support comes only from admitted, reachable contributors. Retained hypotheses are propagated with current live target kinematics and decaying historical support, but their output weight is zero: they preserve a possible mode and justify deferral without becoming a vote. Provenance masks are unioned across fusion, so copied beliefs are diagnosed and cannot multiply support.

The conservative confidence margin is

```text
leading_live - runner_up_live - unknown
```

after normalization by the fixed roster capacity. An unreachable set can therefore overturn a selection unless the reachable leader still dominates it.

Agent sharing follows `OFFLINE → PROBATION → TRUSTED`. A recovered agent may update locally, but cannot contribute support or enter fusion until it has several stable-graph, bounded-NIS cycles. Its stale bias state is reset, its covariance receives outage-length admission inflation, and its support ramps from zero. A component merge starts a separate evidence ramp and a bounded merge-grace deferral. Incompatible post-merge beliefs remain separate; covariance intersection is applied only inside compatible groups, and mode identity matching requires both bounded Mahalanobis and positional distance.

### 4.11 M9A.6 missing-evidence posterior and action risk

M9A.6 adds a causal output overlay while leaving the complete M9A physical controller frozen. For the declared secondary-mode family, a vectorized bank of Kalman filters enumerates every hidden source assignment and updates its probability from lifecycle-admitted raw measurements in the observer's delivered weak component. Missing agents are marginalized rather than counted as negative evidence. Compatible assignment states are clustered into output modes and moment matched with within- and between-assignment covariance.

The declared family is not treated as exhaustive. A posterior-predictive effective NIS is mapped through a prospectively trained `3.5–7.0` ramp and a `0.20` exponential update to residual unknown mass with a `0.01` floor. A cycle with no local observation preserves the previous mass; absence is not evidence of fit. The residual remains separate from the known assignment probabilities and is exercised by count- and offset-misspecification challenges.

Select and mixture candidates are priced by posterior expected RMS position risk, including covariance, plus the declared residual loss. Deferral is priced by the closest member of the 95% credible set, the same irreducible residual loss, and the fixed defer cost. A point action is prohibited when residual mass plus posterior mass on materially different known modes exceeds `0.10`. Charging model-mismatch loss symmetrically is essential: deferral avoids a wrong point claim but cannot erase unknown evidence.

M9A's lifecycle, component, provenance, merge, and motion mechanisms remain active and instrumented. The legacy merge-grace selection block is not reapplied inside the M9A.6 raw-measurement filter because it merges no previously shared belief histories; doing so caused repeated range-graph merges to create artificial abstention. The original M9A output still controls every movement decision, so M9A.6 cannot improve its own evidence trajectory during this milestone.

### 4.12 M9A.7 split evidence admission

M9A.7 preserves the M9A.6 assignment posterior and risk policy but separates two information types that do not share the same contamination boundary:

- a recursively fused belief carries unknown lineage and remains subject to M6 source trust, `OFFLINE → PROBATION → TRUSTED` lifecycle admission, component reachability, and merge rules;
- a current raw sample carries no recursive fusion lineage and is eligible when its sender is operational, its measurement is available, and it is reachable from the observer component.

The raw path is deliberately permissive because the M9A.6 failure was caused by using the belief gate to censor the very current observation needed to contradict a collapsed assignment family. It is bounded in four independent ways: every reported covariance eigenvalue is floored at `0.25` times the median contemporaneous reachable-source eigenvalue; the declared assignment likelihood remains explicit; posterior-predictive mismatch continues to create residual unknown mass; and the `0.10` predicted wrong-risk ceiling still blocks a point decision. A catastrophic-only predictive NIS gate at `100` can reject a sample without letting it update any hypothesis, but ordinary contradictory rejoin evidence must remain able to reopen support.

Missingness diagnostics distinguish reachability, operational status, belief-lifecycle eligibility, belief admission, raw eligibility, model rejection, covariance flooring, and the posterior probability that an excluded source belongs to the secondary population. Admission-specific residual mass can grow only when a current sample is both unavailable to the raw path and lifecycle-censored; an observed raw sample is not priced as missing merely because its belief remains on probation.

The attack boundary is explicit. Three rejoining colluders ramp a shared offset and report covariance at `0.05` of its physical value while the raw path is available. The frozen success criterion is no increase in material wrong-action or quarantine rate relative to M9A.6, plus exercised covariance flooring. It is a safety gate, not a utility gate: held-out candidate loss is materially higher under this attack because the controller defers.

## 5. Processing cycle

For each timestep the platform:

1. advances the hidden target and samples common random numbers;
2. applies operational-agent and partition masks to each topological communication neighbourhood;
3. applies burst availability, per-sender age, and obtains noisy observations and availability flags;
4. assesses source bias and coherent alternative modes;
5. predicts and locally updates each Kalman filter;
6. selects and propagates each sender's delayed posterior to the current time;
7. constructs compatibility flocks and fuses only within them;
8. assigns component epochs and lifecycle state, then builds component-local live/retained/unknown evidence ledgers;
9. aggregates decision-equivalent support without merging Gaussian posteriors and blocks selection during unsafe merge/rejoin states;
10. for M9A.6/M9A.7, updates the causal assignment posterior, predictive mismatch residual, credible modes, and risk-priced output action; M9A.7 first applies split raw/belief admission and covariance flooring;
11. allocates investigation goals across surviving modes when requested;
12. computes flocking motion with fixed or experimental recurrence;
13. records estimation, calibration, output action, fault, mode, motion, operational count, delivery, message age, communication, and runtime diagnostics.

## 6. Software architecture

| Module | Responsibility |
|---|---|
| `config.py` | Validated, replayable experiment, robust-fusion, and realism parameters. |
| `simulation.py` | Truth, randomized faults, burst links, asynchronous ages, outages, heterogeneous/nonlinear observations, and trace hashes. |
| `filters.py` | Kalman prediction/update and covariance-intersection primitives. |
| `policies.py` | Flocking, recurrence, guarded adaptation, and sensor motion. |
| `robust.py` | Bias/mode tracking, quarantine, compatibility graphs, and hypothesis flocks. |
| `output_policy.py` | Truth-blind largest, temporal, mixture, defer, and active output policies. |
| `experiment.py` | Per-cycle orchestration, delay compensation, metrics, and standard artifacts. |
| `metrics.py` | RMSE, calibration, information, mode, quarantine, motion, and resource metrics. |
| `suite.py` | Shared paired evaluation and bootstrap machinery. |
| `guarded_suite.py` | M5 guarded-momentum protocol. |
| `robust_suite.py` | M6 fixed-versus-robust protocol and automatic decision. |
| `output_suite.py` | M7 five-policy protocol, decision-loss sensitivity, and automatic decision. |
| `realism_suite.py` | M8 ten-layer protocol, active/no-investigation ablation, trace verification, and automatic decision. |
| `ambiguity_assay.py` | M8.1 endogenous range-only ambiguity, Bayesian evidence, dose/oracle/VOI policies, replay, and gates. |
| `active_sensing_suite.py` | M9B multi-hypothesis tasks, recurrent probe motion, sampled finite-horizon Bayes-risk planners, replay, statistics, and gates. |
| `topology.py` | Connected components, topology epochs, lifecycle probation, merge grace, provenance-aware support, and retained hypothesis memory. |
| `topology_suite.py` | M9A four-stage ablation, eight-scenario paired protocol, replay verification, tail gates, and automatic decision. |
| `oracle_floor.py` | Vectorized hidden-assignment Bayesian filter, causal observer/global decisions, and frozen-trajectory diagnostic hook. |
| `oracle_floor_suite.py` | M9A.5 nested-reference protocol, transfer/gap decomposition, replay, reanalysis, and non-promotional diagnosis. |
| `missing_evidence.py` | M9A.6 assignment posterior, predictive mismatch residual, credible modes, and risk-priced output decision. |
| `missing_evidence_suite.py` | Training/held-out observer-relative protocol, misspecification challenges, frozen-motion audit, replay, gates, and report. |
| `admission_evidence.py` | M9A.7 split raw/belief trust, covariance flooring, admission-aware missingness diagnostics, and causal output controller. |
| `admission_suite.py` | Positive control, colluding raw-channel attack, powered mean/P95/max regret gates, replay, reanalysis, and report. |
| `integrated_sensing.py` | M9C broad and two-step component-local assignment-VOI physical motion. |
| `integration_suite.py` | M9C dynamic topology transfer, movement-inclusive gates, source-competition control, replay, reanalysis, and report. |
| `adversarial_trust.py` | M10A cross-channel, ramp-rate, and suspicious raw-only influence defenses with sticky source trust. |
| `adversarial_trust_suite.py` | M10A frozen-motion shadows, control and attack-dose protocols, ablations, replay, reanalysis, and 16-gate report. |
| `closed_loop_trust.py` | M10A.5 dependency-isolated trust feedback, trusted-sensor verification, recovery switching, and M9C compatibility. |
| `closed_loop_trust_suite.py` | M10A.5 powered controls, attacks, honest recovery, replay, reanalysis, and 16-gate report. |
| `decentralized_sensing.py` | M10B asynchronous per-agent action ownership, local proposals, deterministic conflict resolution, and planner diagnostics. |
| `decentralized_suite.py` | M10B centralized/negotiated/unnegotiated comparison, powered topology/attack gates, replay, reanalysis, and report. |
| `external_replay.py` | M11 strict MR.CLAM ingestion, causal known-map EKF, bounded landmark selection, topology/outage reconstruction, and truth-isolated scoring. |
| `external_replay_suite.py` | M11 archive verification, replay windows, calibration/outage/topology gates, paired effects, and report. |
| `external_replay_repair.py` | M11.1 deterministic row-preserving timestamp canonicalization and per-file hash manifest. |
| `external_replay_repair_suite.py` | M11.1 repair development and replacement held-out protocol. |
| `acceleration_replay.py` | M12 five-state measured-acceleration EKF and separate deterministic jerk-limiter assay. |
| `acceleration_suite.py` | M12 paired replay windows, acceleration/calibration/outage gates, jerk gates, and stop decision. |
| `full_loop_contracts.py` | M13 canonical envelopes, byte accounting, truth rejection, deterministic faults, causal attack shim, command safety, and hash-chained ledgers. |
| `full_loop_hil.py` | M13.1 independent plant/camera/network/runtime/scorer, four-arm paired suite, replay audit, gates, and report. |
| `full_loop_physical.py` | M13.2/M13.3 randomized plans, sealing, raw-ledger scoring, power freeze, source lock, and fail-closed holdout decision. |
| `ros2/flockkalman_msgs/` | Buildable ROS 2 interface package for operational, safety, and separately restricted truth messages. |
| `movement_cost_sweep.py` | Analysis-only M9B saved-action repricing and separate first-action planning thresholds. |
| `momentum_mechanism.py` | Fixed-`rho`/`tau` sweep and geometry/disagreement/information mechanism diagnostics. |
| `cli.py` | Reproducible command-line entry points. |

## 7. Requirements and invariants

### 7.1 Functional requirements

- A seed must reproduce truth, initial beliefs, agent fault identities, sensor quality, dropout bursts, clock offsets, message ages, outages, and observation draws.
- All algorithms in a paired trial must receive the same exogenous random draws.
- Fault groups must be randomized per seed so agent ordering cannot reveal the true mode.
- Unknown cross-correlations must use covariance intersection, not naïve precision fusion.
- Suspected or quarantined sources must not influence the team fusion result.
- A coherent alternative group above the configured evidence fraction must remain explicit.
- Delayed peer beliefs must be time-aligned before fusion.
- Inactive agents must not sense, communicate, or move; partitioned agents must not exchange cross-partition messages.
- Decision-equivalent support grouping must not alter or fuse M6 posterior flocks.
- Output-policy decisions must not receive truth, source faults, or evaluation labels.
- Every decision suite must save raw run summaries, scenario aggregates, paired effects, its complete configuration, and the automatic verdict.
- M8 must save and independently regenerate a cryptographic fingerprint for every scenario/seed pair.
- M8.1 must save and independently regenerate the truth-mode/noise fingerprint for every seed, and reanalysis must reproduce its gates from saved run summaries.
- M9B must keep realized noise hidden from every planner, use common planning samples across horizons, preserve separate decision and movement costs, and replay every scenario/seed trace.
- M9A must never turn loss of reachability into positive mode evidence; unreachable or unadmitted capacity remains explicit `unknown_support`.
- Recovered agents and newly merged component evidence must ramp from zero support, and selection must remain blocked during merge grace.
- Retained hypotheses may preserve a mode but must carry zero live output weight until compatible current evidence re-admits them.
- M9A reanalysis must regenerate all paired effects and verify every materialized scenario fingerprint.
- M9A.5 references must use the frozen M9A physical trajectory, must not receive target truth, future noise, or seeded fault identities before acting, and must keep the original M9A verdict and gate unchanged.
- M9A.6 must normalize known assignments independently of residual model-mismatch mass; missing observations cannot become positive support for any known assignment.
- M9A.6 truth may choose an evaluation mode only after the operational action is fixed, and the integrated algorithm must reproduce its frozen-M9A shadow output exactly.
- M9A.6 must leave target, sensor-motion, communication, and topology trajectories bit-identical to M9A for each seed and scenario.
- M9A.7 raw eligibility must not authorize recursive belief fusion; belief admission remains independently instrumented and binding.
- M9A.7 must floor understated raw covariance, preserve posterior-predictive residual support, and expose every raw/belief censoring count in saved artifacts.
- M9A.7 training and held-out seeds must exclude M9A.6 and development-smoke seeds; the held-out tail gate requires at least 149 seeds for 95% detection probability at a 2% event frequency.
- M9A.7 must remain an output-only shadow of frozen M9A motion, and every one of its scenario fingerprints must replay.
- M9C allocator arms must change only physical sensing goals; estimator, admission, output policy, exogenous traces, and declared movement price remain paired.
- M10A must preserve frozen M9C actions and decision loss in its no-defense shadow, keep every arm on identical physical motion, and isolate truth and seeded fault identity in scoring.
- M10A may discount a raw-only source only after causal attack evidence; belief censoring alone cannot be an attack signal.
- M10A training and held-out splits, protocol, candidate hash, all 16 gates, and the availability limit derived from deferral cost must be fixed before held-out evaluation.
- M10A.5 must reproduce frozen M9C exactly in no-defense mode, forbid alerted sensors from verification ownership, and restore every injected dependency after each trial.
- M10B agents may own only their own goal; proposals are bounded to four scalars per delivered directed neighbour on a sender's replan phase, and partitioned edges carry no planner messages.
- M11/M11.1 operational filters may read Vicon truth only for initialization; every later truth access occurs after the estimate is fixed for scoring.
- M11.1 canonicalization must use a stable timestamp sort, preserve equal-time input order and every numeric row, and materialize source/canonical hashes before replay.
- M12 estimator and behavioural acceleration claims must remain separate; a development estimator failure forbids opening the held-out Dataset 7 split.

### 7.2 Safety and scientific invariants

- No algorithm is promoted on RMSE alone; calibration, mode survival, false quarantine, and costs are gates.
- Training and held-out seed ranges must not overlap.
- Symmetric multimodal evaluation must not treat an arbitrary primary tie-break as truth knowledge.
- Hypothesis-set RMSE is an evaluation-only oracle metric: it measures whether any returned mode is truth-consistent. It is not available to an operational selector.
- A `GO` for M6 means “advance the hypothesis-set system,” not “deploy a single-output controller.”
- A `GO` for M7 permits selection only when its evidence rule fires; explicit deferral remains the required symmetric-ambiguity behavior.
- Information-gain improvement is not evidence of decision benefit unless the paired no-investigation ablation also improves declared decision loss.
- A positive-control pass establishes identifiability only. It must not be reported as validation of a production allocator unless competing policies produce separable held-out outcomes in the production-relevant task.
- An M9B utility gain caused by lower movement cost must be described as an efficiency gain. It is not an accuracy or resolution-speed gain unless the separate components support that claim.
- M9B is not production-qualified until the same policy survives M9A topology, calibration, and decentralization gates.
- A later composite layer cannot erase an earlier ordered-layer failure; diagnosis begins at the first failed layer.
- Promotion claims must state the assumed deferral cost and its sensitivity range.
- M9A.6 thresholds may be developed only on seeds `13000–13029`; seeds `14000–14099` are a single untouched confirmation split and cannot trigger retuning.
- An M9A.6 held-out `GO` authorizes M9B integration research only. It does not promote M9A.4, validate an exhaustive fault model, or remove the observer/global information boundary.
- An M9A.7 held-out `GO` authorizes only a bounded M9A/M9B integration experiment. It does not alter the historical M9A/M9A.6 verdicts, validate arbitrary adversaries, or qualify the raw channel for production.
- The M9B movement-cost sweep must reprice saved actions without regenerating them; counterfactual planner actions are a separate diagnostic and cannot change the original M9B verdict.
- An M9C `PARTIAL-GO` does not become a full M9C promotion when a later output overlay repairs its attack failure; every historical verdict remains immutable.
- An M10A `GO` authorizes only closed-loop integration research. It does not establish production security, adaptive-adversary robustness, or external validity.

## 8. Metrics

- **Primary position RMSE:** error of the operationally ordered primary flock.
- **Best-hypothesis RMSE:** evaluation-only error of the returned flock nearest to truth.
- **NEES and 95% coverage:** consistency between reported covariance and observed error.
- **Mode survival:** fraction of steps with multiple flocks, alternative weight, and truth-consistent-flock weight.
- **Bias diagnostics:** suspected count, quarantined count, quarantine rate, and mean bias-state norm.
- **Decision loss:** action-dependent position error plus declared deferral and investigation costs.
- **M9B total loss:** cumulative deferral/wrong-selection cost plus scenario-weighted movement cost; components are always reported separately.
- **Categorical calibration:** final truth-mode probability, Brier score, and log loss for the pose-conditioned multi-hypothesis posterior.
- **View allocation:** hold/spread/probe fractions, distinct probe count, planning horizon, and sequences evaluated.
- **Output behavior:** selection, mixture, abstention, investigation, confidence, material wrong-mode action, and ambiguity-resolution rates.
- **Missing-evidence diagnostics:** assignment entropy, posterior-predictive effective NIS, residual unknown mass, credible-mode count, and predicted action/wrong-action risk.
- **Trust diagnostics:** cross-channel disagreement, covariance-understatement and ramp-rate evidence, influence-cap activation, raw-source trust, strategic and non-strategic alert rates, and trust-residual mass.
- **Information gain:** expected Gaussian information from range-dependent observations.
- **Geometric discriminability:** expected binary log-likelihood separation induced by sensor pose in the M8.1 range-only assay.
- **Spatial diversity and disagreement:** sensor dispersion and belief separation.
- **Recovery:** sustained return below a pre-change-derived error threshold.
- **Communication:** directed messages and serialized float payload bytes.
- **Realism diagnostics:** operational-agent count, delivered-edge ratio, per-message age, partition-active rate, and scenario replay hash.
- **Runtime:** per-trial wall-clock time, used only as an engineering guard.

## 9. Engineering milestones

| Milestone | Deliverable | Exit criterion | Status |
|---|---|---|---|
| M0 — Formalization | State, observation, graph, fusion, flocking, and recurrence definitions. | Every symbol maps to an implementation parameter. | Complete |
| M1 — Reproducible simulator | Truth, sensing geometry, common random numbers, replayable seeds. | Identical seed produces identical scenario. | Complete |
| M2 — Baselines | Independent KF, consensus KF, flocking-only, and distributed flocking–KF ablations. | Finite complete trials and comparable artifacts. | Complete |
| M3 — Investigative momentum | Zero, fixed, and direct innovation-adaptive recurrence. | Controlled evaluation of error, recovery, calibration, and cost. | Complete |
| M4 — Firm momentum decision | Seven scenarios × 100 held-out seeds × three algorithms. | Frozen paired decision. | Complete: fixed recurrence retained; direct adaptation rejected |
| M5 — Guarded adaptation | Corroborated change detector, stale/bias guards, exact fixed fallback. | Beat fixed recurrence on held-out RMSE and recovery without calibration loss. | Complete: `NO-GO` |
| M6 — Robust multi-flock fusion | Bias state, quarantine, Byzantine stress, delay alignment, explicit alternatives. | Pass all 12 held-out robustness, non-inferiority, calibration, mode, and cost gates. | Complete: `GO` |
| M7 — Output-policy evaluation | Select, defer, or request information when several flocks survive. | Beat mixture/primary/abstention baselines using decision loss without truth-oracle access. | Complete: `GO` |
| M8 — Realism ladder | Asynchronous clocks, burst loss, nonlinear sensing, heterogeneous sensors, drifting/strategic faults, outages, partitions, trace replay, and no-investigation ablation. | M6/M7 findings survive successively harder held-out tests and investigation lowers decision loss. | Complete: `NO-GO` at dynamic topology; information gain did not become decision gain |
| M8.1 — Identifiable active-sensing control | Endogenous binary range-only ambiguity, Bayesian mode evidence, dose sweep, information oracle, one-step VOI, replay, and frozen gates. | Passive remains ambiguous while motion safely resolves it; discriminability responds to dose; held-out decision loss improves. | Complete: `POSITIVE-CONTROL-PASS`; bounded M9B allowed |
| M8.2 — Recurrence mechanism diagnostic | Sweep fixed `rho`, map it to `tau`, and test whether RMSE benefit covaries with diversity, disagreement, or information across change timescales. | Produce a reproducible diagnostic and explicitly separate correlation from causal mediation. | Complete: training-only diagnostic; see Section 10.7 |
| M9A — Topology resilience | Live/retained/unknown evidence, lifecycle probation, component-local output, merge grace, provenance, tail gates, and replay. | Dynamic-topology transfer lower confidence bound exceeds `-0.10`, with credible calibration, bounded wrong actions, and no rejoin support shock. | Complete: held-out `M9A-PARTIAL-GO`; seven of eight gates pass, transfer still blocks promotion |
| M9A.5 — Dynamic loss-floor diagnosis | Frozen-trajectory observer/global Bayesian references, hidden-assignment marginalization, truth-only scoring, hindsight set floor, and paired transfer decomposition. | Determine whether each failed transfer is dominated by production policy/representation, component-local information, or the frozen returned-set floor without changing M9A.4. | Complete: `INFORMATION-LIMITED` at the strict aggregate boundary, with material same-information headroom |
| M9A.6 — Missing-evidence posterior and pricing | Assignment-weighted missing-evidence hypotheses, residual unmodelled mass, risk-priced select/mixture/defer actions, and oracle-relative evaluation. | On a newly preregistered held-out protocol, materially close observer-reference regret without increasing wrong actions or weakening unknown-support and calibration invariants. | Complete: held-out `M9A6-NO-GO`; eight of nine gates pass, failure+partition observer regret blocks integration |
| M9A.7 — Split evidence admission | Separate current raw samples from recursive belief admission, add covariance flooring, admission-censoring positive control, colluding raw-channel attack, and powered mean/P95/max tail gates. | Repair failure+partition observer regret without wrong-action, quarantine, calibration, model-mismatch, replay, or frozen-motion regression. | Complete: powered held-out `M9A7-GO`; all 13 gates pass; bounded M9A/M9B integration research authorized |
| M9B — Decision-relevant active sensing | Pose-conditioned hypothesis evidence, competing-view tasks, asymmetric costs, multi-step VOI, unchanged controls, and saved-action movement-cost sensitivity. | VOI significantly lowers held-out movement-inclusive loss versus both current allocator and passive control, without unsafe selection, and its cost envelope is reported. | Complete: `M9B-GO` in static centralized assay; integration experiment now authorized by M9A.7 |
| M9C — Dynamic active-sensing integration | M9A.7 estimator/output with broad and two-step component-local VOI physical motion under the full dynamic topology suite. | Powered utility gain over broad motion with frozen M9A.7 noninferiority, calibration, topology, attack, replay, and motion-mechanism gates. | Complete: `M9C-PARTIAL-GO`; 12 of 13 gates pass, raw-channel absolute utility blocks promotion |
| M10A — Raw-channel adversarial trust | Cross-channel disagreement, ramp-rate evidence, suspicious raw-only influence budgeting, ablations, control challenges, attack dose response, replay, and frozen-motion shadows. | Restore attack availability below `1.50` without control loss, false exclusion, wrong action, calibration, quarantine, or M9C equivalence regression. | Complete: powered held-out `M10A-GO`; all 16 gates pass; closed-loop integration research authorized |
| M10A.5 — Closed-loop trust integration | Feed trust-adjusted evidence into output and sensing while retaining frozen M9C/no-trust controls and measuring recovery and feedback effects. | Preserve M10A attack repair and natural-scenario safety while retaining the M9C movement-inclusive gain under causal feedback. | Complete: powered held-out `M10A5-GO`; all 16 gates pass |
| M10B — Decentralized allocation | Per-agent action ownership, bounded planner messages, conflict resolution, asynchronous replanning, and partition-aware recovery. | Noninferiority to the component-local planner with bounded communication and no topology/calibration regression. | Complete: powered held-out `M10B-GO`; all 15 gates pass |
| M11 — External replay | Recorded or hardware-in-the-loop trajectories and communication traces. | Deterministic ingestion, declared ground-truth limits, and transfer beyond synthetic data. | Complete with transparent repair: original `M11-INVALID`; replacement held-out `M11.1-GO` |
| M12 — Acceleration ablation | Constant-acceleration or IMM local filters followed separately by acceleration-aware motion. | Held-out gain beyond the replay-qualified system with calibrated uncertainty and justified complexity. | Complete: development `M12-DEVELOPMENT-FAIL`; held-out not opened; isolated jerk assay passes |
| M13.0 — Full-loop interfaces | Wire/QoS contracts, exact byte accounting, per-host evidence, clock/truth isolation, fault/attack shims, and safety supervisor. | Reject truth leakage and malformed evidence; replay and source hashes must verify. | Complete in software |
| M13.1 — Independent HIL | Four arms × ten scenarios × 150 paired seeds against an independent plant, camera, network, attack process, and scorer. | Pass all entry gates before physical calibration. | Complete: `M13.1-HIL-PILOT-READY`; 12/12 gates pass |
| M13.2 — Physical development pilot | Instrumented robot blocks calibrate camera covariance, clocks, safety, variance, and held-out sample size. | Genuine external evidence freezes power and candidate/protocol hashes. | Implemented; 320-run randomized pilot plan generated; external collection pending |
| M13.3 — Preregistered physical holdout | New layouts, paths, lighting, faults, and at least three days; all four arms in every paired block. | Pass all integrity and scientific gates without one-day dependence. | Implemented but unopened; requires M13.2 freeze and genuine held-out bundles |

## 10. Experimental findings

### 10.1 M4: direct adaptive recurrence

Across 2,100 held-out trials on seeds `1000–1099`, fixed recurrence improved overall RMSE by 19.60% versus zero recurrence. Direct NIS adaptation was 2.41% worse than fixed, with its RMSE improvement confidence interval wholly below zero. Decision: retain fixed recurrence and redesign adaptation.

### 10.2 M5: guarded recurrence

Across 2,100 held-out trials on seeds `2000–2099`, guarded momentum was statistically indistinguishable from fixed recurrence: RMSE improvement `-0.0012`, 95% CI `[-0.0048, 0.0021]`. It safely beat the rejected direct policy, but did not justify promotion. Bias and delay failures pointed to the estimator/fusion layer rather than the motion recurrence rule.

### 10.3 M6: robust fusion and hypothesis flocks

Parameters and gates were developed on seeds `0–29`, then frozen. The held-out run used seeds `3000–3099`, seven scenarios, two algorithms, 1,400 trials, common random numbers, and 5,000-sample paired bootstrap intervals.

All 12 decision gates passed.

| Scenario | Fixed RMSE | Robust primary RMSE | Robust set RMSE | Set improvement, 95% CI |
|---|---:|---:|---:|---:|
| No change | 0.6519 | 0.6516 | 0.6516 | 0.0003 `[-0.0068, 0.0072]` |
| Abrupt change | 0.6661 | 0.6641 | 0.6641 | 0.0020 `[-0.0045, 0.0084]` |
| Mixed dropout | 0.6808 | 0.6772 | 0.6770 | 0.0038 `[-0.0030, 0.0105]` |
| Two-cycle delay | 2.5275 | 0.6847 | 0.6847 | 1.8427 `[1.7636, 1.9216]` |
| Two biased agents | 1.2806 | 0.6674 | 0.6618 | 0.6188 `[0.5340, 0.7070]` |
| One Byzantine agent | 10.7300 | 0.6563 | 0.6563 | 10.0737 `[10.0535, 10.0934]` |
| Equal two-mode evidence | 2.9178 | 3.8323 | 0.7225 | 2.1953 `[2.0007, 2.4003]` |

Overall hypothesis-set RMSE improved by `2.1052`, 95% CI `[2.0708, 2.1414]`, and won all 100 held-out seed aggregates. Runtime overhead was 5.94%; serialized payload overhead was 0.0045%. Nominal false quarantine averaged `0.0011` agents. The two-mode alternative survived on 98.96% of steps with mean alternative weight `0.491`.

Bias and Byzantine outputs remained calibrated: mean NEES was `1.663`/`1.669`, and 95% coverage was `0.970`/`0.970` respectively.

The symmetric-mode primary RMSE was worse than fixed fusion (`3.8323` versus `2.9178`) because no available evidence identifies which equal mode is true. This valid limitation motivated M7 selection and abstention without simulation-truth access.

### 10.4 M7: truth-blind output policy

Parameters and gates were developed on seeds `0–29`, then frozen. The held-out run used seeds `4000–4099`, eight scenarios, five policies, 4,000 trials, and 5,000-sample paired bootstrap intervals. All 18 decision gates passed.

| Baseline | Baseline loss | Active loss | Improvement, 95% CI |
|---|---:|---:|---:|
| Largest flock | 1.1128 | 0.7377 | 0.3751 `[0.2681, 0.4867]` |
| Temporal continuity | 0.9076 | 0.7377 | 0.1699 `[0.0998, 0.2403]` |
| Moment-matched mixture | 1.2865 | 0.7377 | 0.5489 `[0.5454, 0.5524]` |
| Always defer | 1.3269 | 0.7377 | 0.5892 `[0.5870, 0.5913]` |

Persistent equal evidence produced 97.74% abstention and a 0.67% material wrong-mode action rate. Five-versus-three evidence produced 97.54% selection. Transient equal ambiguity resolved in `76.76` steps on average. M6 calibration, mode survival, false-quarantine, and fault gates remained intact. Communication was unchanged, runtime was statistically unchanged, and movement increased by 0.40%.

The conclusion was significant for counterfactual deferral costs `0.25`, `0.50`, and `1.00`. At cost `1.50`, the smallest improvement was `0.0349` but its lower confidence bound was `-0.0327`; promotion is therefore not claimed when abstention is valued that harshly.

M7 validates the combined select/investigate/defer policy, but it does not establish that investigation motion caused ambiguity resolution. The transient alternative ends exogenously. M8 therefore adds an otherwise-identical no-investigation controller.

### 10.5 M8: realism ladder and investigation ablation

The engineering protocol was checked on disjoint seeds `4500–4511`; no M7 policy parameter was changed. The final held-out run used seeds `5000–5099`, ten scenarios, four policies, 4,000 trials, 5,000-sample paired bootstrap intervals, and 1,000 scenario fingerprints that all regenerated exactly.

The overall active policy still beat temporal continuity on declared decision loss by `0.2082`, 95% CI `[0.1382, 0.2829]`. Its M7 reference behaviour also survived: persistent equal evidence produced 97.60% abstention and 0.80% material wrong actions; transient ambiguity produced 43.71% abstention and resolved in `76.07` steps.

Nine of ten ordered layers met their layer-specific transfer and safety criteria. Burst links delivered 78.7% of eligible edges; asynchronous messages averaged `2.59` cycles old; exact-moment range–bearing conversion achieved mean NEES `1.01` and 98.54% coverage; heterogeneous sensing, drifting/recovering bias, and colluding ramp attacks also passed.

The first failure was **dynamic topology**. Against the frozen active transient reference, decision loss degraded by `0.2192`; expressed as reference-minus-layer transfer, the estimate was `-0.2192`, 95% CI `[-0.3308, -0.1151]`, breaching the predeclared `-0.10` margin. Dynamic-topology mean NEES rose to `8.16` and coverage fell to 91.05%, despite a low 1.19% material wrong-action rate. The layer had 7.0625 operational agents on average and an active partition during 43.75% of cycles, confirming the disturbance was exercised rather than silently bypassed.

The composite layer retained bounded wrong actions (2.68%) and low decision loss (`0.5071`), but mean NEES `27.73` reveals severe tail inconsistency. Because composite calibration was diagnostic rather than a declared decision gate, it does not alter the automatic first-failure location; it strengthens the case for topology/outage uncertainty redesign.

The causal motion ablation produced a sharp boundary:

| Outcome | No investigation | Active investigation | Improvement, 95% CI | Decision |
|---|---:|---:|---:|---|
| Decision loss | 0.8394 | 0.8414 | `-0.0020` `[-0.0052, 0.0011]` | Fail |
| Information gain | 4.1379 | 4.1409 | `0.0030` `[0.0015, 0.0045]` | Pass |

Investigative motion therefore changes geometry in the intended direction, but the current allocation and output policy do not use the additional information effectively enough to improve decisions. Movement rose by 1.40%; communication was effectively unchanged.

The automatic M8 verdict is **`NO-GO`** for promoting the full frozen active system. This does not overturn the narrower M6 hypothesis-retention or M7 symmetric-ambiguity findings under their evaluated conditions. It rejects the broader claim that they already transfer through changing participation/topology, and it rejects a causal decision-benefit claim for the current investigative motion.

### 10.6 M8.1: endogenous-ambiguity positive control

The assay and gates were checked on training seeds `6000–6029`, then frozen. The held-out run used 100 paired seeds `7000–7099`, five round-robin doses plus passive, information-oracle, and one-step VOI arms, 5,000-sample paired bootstrap intervals, and deterministic trace replay. All six gates passed.

Passive sensing and the zero-dose allocator remained unresolved in every run, with mean discriminability `0.000` and cumulative decision loss `6.0000`. Every nonzero tested round-robin dose resolved every run without a wrong selection. Resolution accelerated from `4.73` cycles at dose `0.10` to `1.53` cycles at dose `1.00`; dose and mean discriminability had correlation `0.9994`.

| Arm | Resolution rate | Mean resolution cycles | Decision loss | Movement | Discriminability |
|---|---:|---:|---:|---:|---:|
| Passive | 0.000 | 30.00 | 6.0000 | 0.000 | 0.000 |
| Round-robin, dose 0.10 | 1.000 | 4.73 | 0.7501 | 0.409 | 1.139 |
| Round-robin, dose 0.25 | 1.000 | 2.98 | 0.4012 | 0.521 | 2.198 |
| Round-robin, dose 0.50 | 1.000 | 2.18 | 0.2426 | 0.658 | 4.240 |
| Round-robin, dose 1.00 | 1.000 | 1.53 | 0.1140 | 0.803 | 8.411 |
| Information oracle | 1.000 | 1.53 | 0.1140 | 0.803 | 8.411 |
| One-step VOI | 1.000 | 1.53 | 0.1140 | 0.803 | 8.411 |

Full-dose motion improved cumulative decision loss over passive sensing by `5.8860`, 95% CI `[5.8652, 5.9067]`. The automatic verdict is **`POSITIVE-CONTROL-PASS`**, with research direction **`ALLOW_BOUNDED_M9B_VALUE_OF_INFORMATION_RESEARCH`**.

The limitation is as important as the pass: in this binary symmetric geometry, round-robin, oracle, and one-step VOI select the same full-dose path. M8.1 therefore proves that the simulator can expose a viewpoint-mediated information-to-decision benefit, but it does not rank allocation policies and does not validate the M8 production allocator. M9B must create competing views and costs before an allocator claim is identifiable.

### 10.7 M8.2: fixed-recurrence mechanism diagnostic

This training-only diagnostic used seeds `8000–8029`, eight target-change patterns, and fixed recurrence values `0.00`, `0.25`, `0.50`, `0.72`, `0.85`, and `0.93`, for 1,440 trials. Each nonzero recurrence maps to the interpretable time constant `tau = -dt/log(rho)`, ranging from `0.721` cycles at `rho=0.25` to `13.780` at `rho=0.93`.

Every scenario's lowest mean RMSE occurred at nonzero recurrence, consistent with the earlier M4 held-out result that recurrence is useful in this simulator family. The optimum was not stable: `rho=0.72` was best for gradual-10 and repeated-20; `rho=0.85` for no-change, gradual-40, repeated-35, and repeated-50; and `rho=0.93` for abrupt and gradual-20. Averaged equally across the eight scenario cells, mean RMSE decreased from `0.7065` at `rho=0` to `0.6540`, `0.6513`, and `0.6500` at `rho=0.72`, `0.85`, and `0.93`, respectively. These are exploratory means, not held-out pairwise promotion intervals.

The proposed sensor-geometry mechanism was not supported. RMSE improvement versus diversity change had correlation `-0.295` between scenario/`rho` cells and `0.051` after within-cell centering. Within-cell correlations with disagreement and information change were `-0.063` and `0.345`. The automatic diagnostic is **`MECHANISM-UNRESOLVED`**.

Accordingly, nonzero recurrence remains empirically useful, but no result here supports the claim that it works by preserving spatial diversity, nor that its time constant should simply scale with the target-change interval. `rho=0.72` remains frozen for comparability with M4–M8; retuning it is not part of M9A or M9B and should not be promoted without a new causal ablation and held-out test.

### 10.8 M9B: decision-relevant competing-view allocation

The planner boundary, task geometry, costs, threshold, policy horizons, and gates were developed on seeds `9000–9029` and then frozen. The held-out run used seeds `10000–10099`, five task families, five policies, 2,500 trials, 5,000-sample paired bootstrap intervals, and 500 scenario fingerprints. Reanalysis from saved rows regenerated the same verdict. All 12 gates passed.

| Policy | Resolved | Wrong | Resolution cycles | Total loss | Decision cost | Movement cost | Probe fraction | Spread fraction |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Passive | 0.000 | 0.000 | 10.00 | 2.5000 | 2.5000 | 0.0000 | 0.000 | 0.000 |
| Round-robin | 1.000 | 0.000 | 2.15 | 2.0124 | 0.2880 | 1.7244 | 0.000 | 1.000 |
| Myopic VOI | 0.000 | 0.000 | 10.00 | 2.5000 | 2.5000 | 0.0000 | 0.000 | 0.000 |
| Receding-horizon VOI | 1.000 | 0.000 | 2.58 | 1.4387 | 0.3960 | 1.0427 | 0.337 | 0.413 |
| Horizon-three comparator | 1.000 | 0.002 | 2.65 | 1.2753 | 0.4155 | 0.8598 | 0.429 | 0.302 |

Receding-horizon VOI improved total loss over round-robin by `0.5737`, 95% CI `[0.5293, 0.6196]`. It also improved over passive by `1.0613`, CI `[1.0322, 1.0911]`, and over the one-step policy by `1.0613`, CI `[1.0312, 1.0899]`. Against round-robin, every scenario-specific lower confidence bound was positive; the smallest was `0.3601` in the near-pair task.

The mechanism of the gain is efficiency. Receding-horizon VOI reduced movement cost by `0.6817`, CI `[0.6418, 0.7226]`, while its decision-cost component was `0.1080` higher and it resolved `0.43` cycles more slowly than round-robin. Both made zero wrong held-out selections and had effectively zero Brier error at their stopping threshold. The one-step policy held because no single limited probe could justify its movement cost and reach the `0.99` threshold; two-step planning exposed the value of committing to and then replanning across competing views.

The automatic verdict is **`M9B-GO`**, with direction **`ADVANCE_VOI_TO_PRODUCTION_STACK_INTEGRATION_AFTER_M9A`**. This supports a cost-aware allocator, not a raw-accuracy claim. The horizon-three comparator's lower total loss shows remaining planning headroom, but its nonzero wrong rate and higher compute do not justify replacing the two-step candidate.

The v0.12 analysis-only movement-cost sweep reprices the immutable 2,500 held-out action traces from scale `0` through `4`. The receding policy's analytic break-even scale is `0.158` against round-robin and `2.018` against passive/myopic. Its paired 95% LCB is positive against round-robin at every tested scale `0.20–4.0`, and positive against passive/myopic at every tested scale `0–1.5`; at sufficiently high cost, doing nothing becomes preferable. A separate first-action diagnostic confirms why myopic ties passive at the declared scale: myopic acts only in the near-pair task and only at tested scales `0–0.05`, while the receding policy remains active through scale `1.0–2.0` depending on task. This maps the operating envelope without changing any saved action or the original `M9B-GO`.

### 10.9 M9A: topology resilience

M9A was developed on seeds `11000–11029`, frozen, and confirmed on fresh seeds `12000–12099`. The held-out matrix contains eight scenarios, five algorithms, 4,000 paired trials, 800 verified scenario fingerprints, and 5,000-sample bootstrap intervals. Saved-row reanalysis reproduced the verdict exactly.

The automatic result is **`M9A-PARTIAL-GO`**. Seven gates passed: replay, stable noninferiority, calibration and tails, wrong selection, rejoin shock, partition uncertainty, and support continuity. The full algorithm also improved overall held-out decision loss over the unchanged M8 active baseline by `0.0480`, 95% CI `[0.0079, 0.0890]`, and improved over the component-local/no-memory ablation by `0.4468`, CI `[0.3666, 0.5229]`.

| Scenario | Loss | Transfer LCB | Mean NEES | p95 NEES | Coverage | Wrong action | Support jump |
|---|---:|---:|---:|---:|---:|---:|---:|
| Stable control | 0.944 | — | 1.88 | 4.53 | 0.967 | 0.007 | 0.005 |
| Failure only | 1.047 | -0.130 | 1.79 | 4.48 | 0.971 | 0.004 | 0.024 |
| Partition only | 1.075 | -0.155 | 1.61 | 4.12 | 0.973 | 0.004 | 0.130 |
| Asymmetric partition | 1.089 | -0.171 | 1.62 | 4.16 | 0.973 | 0.003 | 0.137 |
| Failure + partition | 1.162 | -0.272 | 2.26 | 6.74 | 0.964 | 0.004 | 0.112 |
| Staggered rejoin | 1.009 | -0.114 | 2.19 | 5.94 | 0.964 | 0.006 | 0.123 |
| Flapping reconnect | 0.967 | -0.033 | 1.75 | 4.26 | 0.972 | 0.005 | 0.056 |
| False-split dropout | 1.002 | -0.070 | 1.90 | 4.10 | 0.968 | 0.006 | 0.113 |

The repair target is therefore met at the uncertainty and safety layers: the M8 dynamic-topology NEES of `8.16` and composite tail failure no longer reproduce, material wrong actions remain bounded, and rejoin support does not jump. The promotion target is not met. Failure-only, balanced partition, asymmetric partition, combined failure/partition, and staggered rejoin have transfer lower bounds below `-0.10`; the combined case is worst at `-0.2724`. This is primarily the declared cost of conservative deferral when unreachable evidence could overturn the visible component, not a renewed covariance pathology. The gate must not be relaxed after seeing the result.

### 10.10 M9A.5: dynamic-topology loss-floor diagnosis

M9A.5 is a diagnostic, not a promotion attempt. It reran the unchanged `flocking_topology_resilient` policy on the original 100 held-out seeds `12000–12099` in all eight M9A scenarios. A read-only cycle observer evaluated two nested causal Bayesian references on each identical physical trajectory:

1. the **observer reference** received raw available observations only inside the observer's current delivered weak component;
2. the **global reference** received all currently operational and available observations through an ideal out-of-band collector.

Both references enumerated all `C(8,4) = 70` assignments allowed by the declared four-of-eight secondary-mode model. They knew the declared count, offset, and activation schedule, but never received the seeded assignment, target truth, or future realized noise before choosing an action. Truth was supplied only to a separate scoring function. A third, noncausal **hindsight set floor** selected the frozen M9A returned hypothesis nearest truth; this is a mathematical lower bound only for that returned set. The Bayesian RMS-risk rule is a strong model-informed comparator, not a proof of globally optimal control.

All 800 fingerprints replayed. The final diagnostic used the original M9A runtime (Python `3.11.11`, NumPy `2.4.6`); all 800 rerun frozen-M9A decision-loss rows exactly matched the M9A.4 artifact (`max |difference| = 0.0`). Reanalysis from the saved rows reproduced the same result.

| Scenario | M9A loss | Observer Bayes | Global Bayes | Frozen-set floor | Observer transfer LCB | Global transfer LCB |
|---|---:|---:|---:|---:|---:|---:|
| Stable control | 0.944 | 0.275 | 0.274 | 0.577 | — | — |
| Failure only | 1.047 | 0.294 | 0.292 | 0.598 | -0.021 | -0.020 |
| Partition only | 1.075 | 0.350 | 0.272 | 0.638 | -0.081 | 0.001 |
| Asymmetric partition | 1.089 | 0.372 | 0.272 | 0.652 | -0.105 | 0.001 |
| Failure + partition | 1.162 | 0.354 | 0.292 | 0.665 | -0.085 | -0.020 |
| Staggered rejoin | 1.009 | 0.310 | 0.309 | 0.595 | -0.038 | -0.037 |
| Flapping reconnect | 0.967 | 0.303 | 0.273 | 0.591 | -0.031 | 0.000 |
| False-split dropout | 1.002 | 0.279 | 0.272 | 0.581 | -0.006 | 0.001 |

The strict aggregate diagnosis is **`INFORMATION-LIMITED`**: the observer reference misses the unchanged `-0.10` transfer margin only in asymmetric partition, with LCB `-0.1053`, while the ideal-global reference clears every dynamic scenario. This establishes a real component-information boundary but not a general impossibility result. The miss is narrow and conditional on the declared simulator, prior, fault family, and decision loss.

The equally important result is the scale of production headroom. Frozen M9A decision loss exceeds the observer reference by `0.664–0.809` across the eight scenarios, even though both operate behind the same component boundary and on the same trajectory. Failure+partition also makes the frozen-set hindsight floor miss the original margin (`LCB -0.1337`) while the observer Bayesian representation passes (`LCB -0.0851`). The next repair therefore cannot be a cheaper deferral constant alone. It needs a causal, assignment-weighted representation of what missing evidence could imply, plus a risk-priced action rule. Any probability mass left outside the declared model must remain explicit residual unknown support and retain a conservative fallback.

This result leaves the original M9A.4 `PARTIAL-GO` and all its gates unchanged. A new oracle-relative gate, if used, must be specified prospectively on new training seeds and confirmed on fresh held-out seeds.

### 10.11 M9A.6: assignment-weighted missing evidence and risk pricing

M9A.6 was developed on new seeds `13000–13029`, where all nine gates passed, then frozen and run once on seeds `14000–14099`. The held-out matrix contains ten scenarios, 1,000 paired frozen-trajectory trials, 1,000 verified fingerprints, and 5,000-sample paired bootstrap intervals. Saved-row reanalysis reproduced the verdict. Every target, sensor-motion, communication, and topology trajectory was exactly unchanged from its M9A control (`max |movement-distance difference| = 0.0`).

The held-out verdict is **`M9A6-NO-GO`**. Eight gates pass: replay, exact-model improvement in every scenario, material wrong-action safety, calibration, nominal residual specificity, off-model residual response, frozen motion, and the asymmetric observer-information boundary. The aggregate observer-regret gate fails because failure+partition has UCB `0.1568` against the prospectively frozen `0.10` limit.

| Scenario | M9A | M9A.6 | Improvement LCB | Observer | Regret UCB | Residual | Defer | Wrong | Mean NEES | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Stable control | 0.939 | 0.276 | 0.655 | 0.273 | 0.005 | 0.013 | 0.001 | 0.000 | 1.75 | 0.968 |
| Failure only | 1.062 | 0.329 | 0.709 | 0.293 | 0.043 | 0.017 | 0.009 | 0.000 | 1.76 | 0.968 |
| Partition only | 1.046 | 0.373 | 0.653 | 0.347 | 0.031 | 0.023 | 0.031 | 0.000 | 1.74 | 0.967 |
| Asymmetric partition | 1.061 | 0.409 | 0.629 | 0.370 | 0.047 | 0.026 | 0.050 | 0.000 | 1.74 | 0.967 |
| Failure + partition | 1.192 | 0.451 | 0.681 | 0.351 | **0.157** | 0.025 | 0.040 | 0.000 | 1.70 | 0.970 |
| Staggered rejoin | 1.029 | 0.325 | 0.669 | 0.308 | 0.021 | 0.016 | 0.005 | 0.000 | 1.77 | 0.967 |
| Flapping reconnect | 0.954 | 0.313 | 0.631 | 0.301 | 0.014 | 0.017 | 0.012 | 0.000 | 1.74 | 0.968 |
| False-split dropout | 0.998 | 0.282 | 0.705 | 0.278 | 0.005 | 0.014 | 0.002 | 0.000 | 1.75 | 0.968 |

The representation repair is nevertheless material. Every exact-model improvement lower bound is strongly positive (`0.6287–0.7093`), all material wrong-point-action rates are zero, mean NEES is `1.70–1.77`, p95 NEES is `5.03–5.18`, and coverage is `0.967–0.970`. M9A.6 also clears the former asymmetric-partition observer boundary with regret UCB `0.0471`. This is evidence that assignment-weighted hypotheses and coherent action pricing remove most of M9A's conservative-policy loss; it is not permission to ignore the remaining tail.

The two misspecified-model challenges behave as safety tests rather than accuracy wins:

| Challenge | M9A loss | M9A.6 loss | Mean residual | Mean peak residual | Defer | Wrong |
|---|---:|---:|---:|---:|---:|---:|
| Assumed four sources, actual three | 0.639 | 0.895 | 0.402 | 0.996 | 0.498 | 0.000 |
| Assumed offset `(5,-4)`, actual `(6.5,-2)` | 0.937 | 0.984 | 0.132 | 0.490 | 0.452 | 0.000 |

The failure+partition regret distribution is heavy-tailed. Its mean is `0.1007`, median `0.0443`, and 95th percentile `0.2492`; two seeds dominate the confidence bound. Seeds `14032` and `14084` have M9A.6/observer losses `2.100/0.347` and `2.284/0.394`. In both, only about `3.5` lifecycle-admitted sources remain visible even though `5.31` fresh operational component measurements are available. The retained assignment family collapses around an internally consistent but displaced target, with mean residual only `0.019/0.025`; predictive checks on observed data cannot discover evidence censored by admission.

A post-hoc diagnostic replay, excluded from the promotion decision, supplied those fresh operational measurements to the same unchanged posterior. Loss fell to `0.347` for seed `14032` and `0.464` for seed `14084`. This localizes the next repair to the admission boundary: belief-sharing eligibility for stale/rejoining posteriors and measurement eligibility for fresh raw observations need separate trust channels, and the missingness/admission mechanism itself must contribute uncertainty. The result must not be used to retune M9A.6 on the held-out split.

At the M9A.6 decision point, M9A.4 remained `PARTIAL-GO`, M9A.6 remained `NO-GO`, and `m9b_integration_authorized` was false. That historical verdict triggered the prospective M9A.7 milestone below; it was not retrospectively weakened.

### 10.12 M9A.7: split admission and powered tail repair

M9A.7 was developed on the admission-censoring positive control and formal training seeds `15000–15059`, then its implementation, thresholds, and protocol were frozen and hashed before opening held-out seeds `16000–16299`. The held-out matrix contains 12 scenarios, 3,600 paired frozen-trajectory trials, 3,600 replayed fingerprints, and 5,000-sample paired bootstrap intervals. The 300 seeds give probability `0.9977` of seeing at least one event occurring at the observed 2% frequency; the preregistered minimum for 95% detection probability was 149.

The automatic verdict is **`M9A7-GO`**: all 13 gates pass. The positive control is strongly exercised—mean 1.56 raw-visible but belief-censored sources and censoring on 63.2% of cycles—and M9A.7 reduces its loss from `0.405` to `0.339`, improvement LCB `0.062`. Every natural topology scenario is noninferior to M9A.6, and failure-bearing scenarios improve materially.

| Scenario | M9A.6 | M9A.7 | Improvement LCB | Observer | Regret mean UCB | Regret P95 UCB | Max regret | Wrong | Mean NEES | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Stable control | 0.277 | 0.274 | 0.003 | 0.273 | 0.001 | 0.005 | 0.019 | 0.000 | 1.74 | 0.968 |
| Failure only | 0.323 | 0.294 | 0.026 | 0.292 | 0.002 | 0.014 | 0.028 | 0.000 | 1.73 | 0.969 |
| Partition only | 0.378 | 0.375 | 0.002 | 0.351 | 0.027 | 0.080 | 0.117 | 0.000 | 1.72 | 0.970 |
| Asymmetric partition | 0.408 | 0.405 | 0.002 | 0.371 | 0.037 | 0.098 | 0.127 | 0.000 | 1.72 | 0.969 |
| Failure + partition | 0.419 | 0.371 | 0.039 | 0.350 | 0.023 | 0.070 | 0.103 | 0.000 | 1.71 | 0.969 |
| Staggered rejoin | 0.323 | 0.310 | 0.011 | 0.307 | 0.004 | 0.019 | 0.037 | 0.000 | 1.73 | 0.969 |
| Flapping reconnect | 0.315 | 0.313 | 0.002 | 0.304 | 0.010 | 0.038 | 0.066 | 0.000 | 1.74 | 0.968 |
| False-split dropout | 0.283 | 0.280 | 0.003 | 0.279 | 0.002 | 0.014 | 0.042 | 0.000 | 1.74 | 0.968 |

The two off-model challenges retain the intended response: residual mass is `0.428/0.132`, abstention is `0.501/0.454`, and wrong actions remain zero. In the colluding raw-channel challenge, covariance flooring activates on 83.4% of cycles, with zero wrong actions and zero quarantine delta relative to M9A.6. That safety pass is costly: M9A.7 loss is `3.502` versus M9A.6 `1.105`, driven by 89.7% abstention. The permitted conclusion is therefore “safe enough for an integration experiment,” not “robust or efficient against adaptive adversaries.”

The historical M9A `PARTIAL-GO` and M9A.6 `NO-GO` remain unchanged. M9A.7's `GO` sets `m9b_integration_authorized = true` for research only. The next milestone is the combined, decentralized topology-stressed M9A/M9B experiment with unchanged passive, round-robin, no-investigation, and M9A.7 controls.

## 11. Split M9 program

M8 exposed two independent blockers, and M8.1 clears only the identifiability question for active sensing. They must therefore be implemented and promoted as separate tracks.

### 11.1 M9A: topology resilience

All planned M9A sub-milestones are implemented:

1. **M9A.0 instrumentation:** component/epoch, lifecycle, provenance, visibility, merge, support, and selection-block diagnostics;
2. **M9A.1 evidence ledger:** unique live support, decaying zero-vote retained hypotheses, explicit unknown support, and a conservative confidence bound;
3. **M9A.2 rejoin lifecycle:** `OFFLINE → PROBATION → TRUSTED`, bias reset, outage covariance inflation, NIS/graph admission, and support ramp;
4. **M9A.3 partition protocol:** delivered-graph components, observer-local output, common-time compatibility, stable hypothesis identity, contributor union, merge grace, and merge-entry ramp;
5. **M9A.4 decision suite:** stable, failure, balanced/asymmetric partition, combined, staggered, flapping, and false-split cases with ablations, tail gates, replay, training, and held-out confirmation;
6. **M9A.5 loss-floor diagnosis:** causal hidden-assignment Bayesian references at observer-component and ideal-global information levels, plus the frozen returned-set hindsight floor;
7. **M9A.6 missing-evidence posterior:** assignment marginalization, residual mismatch support, risk-priced actions, exact/off-model challenges, frozen-motion audit, and prospective observer-relative gates.
8. **M9A.7 split evidence admission:** current raw measurements separated from recursive belief admission, robust covariance floor, explicit missingness diagnostics, engineered admission-censoring positive control, colluding raw-channel attack, and powered mean/P95/max tail gates.

M9A.7 is complete and its powered held-out verdict is `GO`. The implementation satisfies the six previously declared requirements:

1. separate fresh-measurement eligibility from stale/shared-belief fusion eligibility instead of applying one lifecycle mask to both information types;
2. condition missing-evidence uncertainty on reachability, operational state, lifecycle admission, and the probability that admission censors a secondary-mode source;
3. preserve the M9A.6 known-assignment posterior and residual mismatch support, but add an explicit admission/missingness alternative that can grow without a contradictory observed innovation;
4. stress the new measurement channel with a targeted rejoining colluding ramp and understated covariance before allowing it to bypass any belief-sharing gate;
5. retain unchanged M9A, observer/global references, frozen motion, exact/off-model challenges, and add a preregistered regret-tail gate so rare failures cannot hide behind mean calibration;
6. use entirely new training and held-out seeds; neither the M9A.6 held-out rows nor its two diagnostic replays may tune or promote the successor.

The old M9A.4 and M9A.6 gates were not retrospectively weakened. M9A.7 answered its narrower admission-aware question in a new prospective protocol. Its result authorizes integration research but does not promote the historical M9A stack, erase the observer/global information boundary, or establish production security for the raw channel.

### 11.2 M9B: decision-relevant active sensing

M9B completed the bounded assay stage:

1. connect each candidate sensor pose to an explicit predictive likelihood for every retained hypothesis;
2. replace agent-headcount support with pose-conditioned Bayesian evidence where the observation model supports it;
3. introduce tasks with at least three hypotheses or geometries in which candidate views trade discrimination between different mode pairs;
4. include asymmetric movement cost, finite ambiguity horizon, and optional risk constraints in the expected-utility calculation;
5. compare passive, current round-robin, myopic VOI, a small receding-horizon VOI policy, and a computational oracle on identical traces;
6. retain the M8 no-investigation control when reintegrating with the production stack.

Items 1–5 are implemented and passed their frozen static-assay gates. The movement-cost counterfactual shows that the receding policy beats round-robin only above scale `0.158` and beats passive/myopic only below scale `2.018`; the original scale `1.0` is inside both intervals. M9C completes the bounded item-6 integration using unchanged M9A.7, broad investigation, and two-step VOI arms under the full dynamic stack. It preserves separate decision and movement costs and reports topology, component-boundary, and decentralization limits explicitly.

### 11.3 M9C: bounded dynamic integration

M9C integrates the exact M9A.7 source-assignment posterior with physical investigation motion while leaving M9A.7 estimation, split admission, residual support, covariance flooring, and risk-priced external output unchanged. The paired arms are:

1. unchanged M9A.7, including its historical physical investigation allocator;
2. broad investigation, which gives every visible source an aggressive close-view goal while assignment identity is uncertain;
3. component-local two-step VOI, which chooses ordinary tracking, a selective two-source probe, or broad motion and replans every three cycles.

“Tracking” is the candidate allocator's no-extra-probe action. It intentionally replaces, rather than reproduces, M9A.7's older investigation motion; the unchanged M9A.7 arm is the physical baseline. The candidates receive identical exogenous traces and the same estimator/output logic, so their only intervention is the physical sensing goal.

The first development candidate failed for two instructive reasons. It treated ambiguity beyond its two-step rollout as free, and it confused M9B's dimensionless `0.158` break-even multiplier with a movement cost in loss units. V2 restores the registered cost `0.80` and charges surviving assignment risk for at most 12 known remaining evidence cycles. The V1 artifacts remain in `results/milestone9c_training`; V2 passed every training efficacy and safety gate, with only absolute attack utility failing, in `results/milestone9c_training_v2`.

V2 was then frozen and evaluated once on seeds `19000–19149`, 150 per scenario. This exceeds the preregistered 149-seed requirement for a 95% chance of seeing at least one event with 2% frequency. The 4,950 saved run rows and all 1,650 exogenous trace fingerprints reanalyze to the same **`M9C-PARTIAL-GO`**:

- aggregate broad-minus-VOI movement-inclusive improvement is `0.00293`, 95% CI `[0.00228, 0.00359]`;
- source-assignment-competition improvement is `0.00749`, `[0.00444, 0.01059]`, and movement falls by `0.02028` per step, `[0.01792, 0.02267]`;
- aggregate movement improvement is `0.00412` per step, `[0.00360, 0.00465]`;
- broad and VOI actions differ on `8.44%` of positive-control cycles; broad extra motion is active on `8.40%`, versus `2.41%` for VOI;
- material wrong-mode actions remain zero; exact-scenario mean NEES is `1.57–1.71` and coverage is `0.969–0.978`;
- the worst natural M9A.7 noninferiority LCB is `0.00682`, the worst delivery-ratio LCB is `-0.00112`, and maximum mean component increase is `0.0106`;
- the colluding raw-channel arm performs no extra investigation and passes attack nonworsening, but decision loss is `3.507`, so the absolute `1.50` utility gate fails.

This is positive evidence for decision-relevant source allocation, but the magnitude is small and mainly reflects lower physical cost with equal safety rather than improved estimator accuracy. M9C authorizes a decentralized allocator follow-up only if raw-channel trust repair remains a separate, explicit workstream. It does not authorize deployment or acceleration-state expansion.

### 11.4 M10A: raw-channel adversarial trust

M10A is the prospectively frozen security and availability assay requested by the M9 review. It does not rerun or alter M9C motion. Each defense receives the same M9C receding-VOI trajectory, observations, topology, raw-admission mask, and belief-admission mask, then changes only the measurement covariance and residual uncertainty presented to a fresh assignment-posterior replica. Truth and seeded fault identity are isolated in the scorer.

The threat model separates five properties that the earlier raw-channel gate conflated:

1. **integrity:** material wrong point selection;
2. **calibration:** NEES, P95 NEES, and 95% coverage;
3. **availability:** decision loss and abstention under attack;
4. **false exclusion:** trust alerts on non-strategic sources and retention of legitimate minority/high-precision evidence;
5. **influence:** precision contributed by raw-visible but belief-inadmissible sources.

The combined candidate composes three causal defenses:

- assignment-corrected cross-channel disagreement against a robust reference of currently belief-admitted sources, after removing the global median innovation so a genuine manoeuvre is not treated as an attack;
- a per-source ramp-rate signal that becomes actionable only alongside saturated cross-channel disagreement;
- a precision budget for suspicious raw-only evidence, capped at `0.35 ×` admitted-source precision.

Trust is sticky, recovers more slowly than it falls, and never goes below `0.05`. Covariance discount and bounded trust-residual support activate only after trust crosses the `0.50` alert threshold. Belief censoring by itself is explicitly insufficient attack evidence. The registered ablations are frozen M9C, cross-channel only, ramp-rate only, influence-budget only, and the combined candidate.

Training used seeds `20000–20039`. After the training pass, candidate source hash `ec882ea680954ccd5cb6c02f1b65def725b17e33af5d4adc2928960f1fbb1ae3` and protocol hash `e4b2da1a5da556a48a6cd2d6fcd5d530211a039e65971426e652ccbaef18247c` were frozen. Held-out then used seeds `21000–21149`, 150 per scenario, across seven controls and four attack doses. The result contains 8,250 arm-level run rows and 1,650 replayed exogenous traces. Saved-row reanalysis reproduces **`M10A-GO`**, with all 16 gates passing and both hashes unchanged.

| Scenario | Combined loss | Abstain | Wrong | Mean NEES | Coverage | Strategic alert | False alert | M9C-minus-combined improvement |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Stable control | `0.274` | `0.001` | `0.000` | `1.72` | `0.969` | — | `0.000` | `0.0000` |
| Failure + partition | `0.370` | `0.025` | `0.000` | `1.70` | `0.971` | — | `0.000` | `0.0000` |
| Flapping reconnect | `0.313` | `0.013` | `0.000` | `1.71` | `0.970` | — | `0.000` | `0.0000` |
| Admission censoring | `0.339` | `0.018` | `0.000` | `1.71` | `0.972` | — | `0.000` | `0.0000` |
| Source competition | `1.043` | `0.009` | `0.000` | `1.60` | `0.976` | — | `0.000` | `0.0000` |
| Genuine manoeuvre | `0.277` | `0.002` | `0.000` | `1.80` | `0.962` | — | `0.000` | `0.0000` |
| Legitimate heterogeneous precision | `0.188` | `0.001` | `0.000` | `1.76` | `0.968` | — | `0.000` | `0.0000` |
| Mild attack | `0.317` | `0.022` | `0.000` | `2.08` | `0.940` | `0.908` | `0.000` | `1.5906` `[1.5541, 1.6253]` |
| Moderate attack | `0.345` | `0.036` | `0.000` | `2.05` | `0.945` | `0.965` | `0.000` | `3.0109` `[2.9907, 3.0298]` |
| Severe attack | `0.339` | `0.009` | `0.000` | `1.75` | `0.967` | `0.994` | `0.000` | `3.9555` `[3.9479, 3.9627]` |
| Canonical rejoin/ramp | `0.437` | `0.103` | `0.000` | `3.36` | `0.951` | `0.985` | `0.000` | `3.0717` `[3.0634, 3.0795]` |

The availability ceiling is not fitted to the observed attack. It is `2 × output_defer_cost = 1.50`: one defer-cost unit for the unavailable point decision and at most one further equivalent unit for residual state error. Every attack remains far below that limit. Control effects are exactly zero because the causal evidence never crosses the intervention boundary in the seven declared controls.

The ablations support a restrained mechanism claim: covariance flooring alone is insufficient; coherent raw evidence needs comparison with an independently admitted channel, temporal rate evidence, and an aggregate influence bound. Conversely, a blanket penalty on every raw-only source is unsafe because it damages legitimate source competition. This is why censoring is not itself an attack signal.

M10A remains simulation-bound and its attacker follows declared ramp families
rather than adapting to the defense. Its historical `GO` authorized M10A.5
only; the completed follow-on results are recorded below.

### 11.5 M10A.5: closed-loop trust integration

M10A.5 injects the frozen M10A combined-trust controller into the frozen M9C
engine without editing either historical implementation. Trust-adjusted
assignment evidence therefore changes subsequent sensing geometry and
observations. While an alert is active, up to the existing M9C probe budget of
currently trusted sensors performs a bounded `trust_verify` action; alerted
sensors can never receive that role. A no-defense dependency-injection audit
reproduces M9C exactly.

Training used seeds `22000–22039`; held-out used `23000–23149`, 150 seeds per
scenario across seven controls, four attacks, and a temporary attack followed
by honest recovery. Saved-row reanalysis reproduces **`M10A5-GO`**, with all 16
gates passing:

- canonical attack decision loss is `0.4335`, with improvement `3.0844`, 95%
  CI `[3.0772, 3.0914]`;
- mild, moderate, severe, and canonical attack losses are
  `0.3174/0.3449/0.3302/0.4335`, all below `1.50`;
- maximum attack movement increase is `0.0278` per step against the `0.05`
  limit;
- trust recovers above the declared threshold within eight cycles, and the
  post-stop false-alert rate is `0.0369`;
- compatibility difference is exactly zero, controls remain noninferior, and
  calibration, wrong-action, quarantine, false-alert, and feedback-exercise
  gates pass.

The result authorizes decentralized-planner research only. The trust mechanism
is still evaluated against scripted attacks and is not a Byzantine-resilience
proof.

### 11.6 M10B: decentralized sensing allocation

M10B replaces component-wide action assignment with per-agent ownership.
Agents replan on staggered phases, retain their own action asynchronously, and
send at most one four-scalar proposal to each currently delivered directed
neighbour. A deterministic closed-neighbourhood winner resolves conflicts.
Trusted-sensor verification outranks assignment probing, and alerted sources
cannot win verification ownership.

Training used seeds `24000–24039`; held-out used `25000–25149`, 150 per
scenario. The negotiated candidate is compared with frozen centralized M10A.5
and a decentralized no-negotiation ablation. Reanalysis returns
**`M10B-GO`**, with all 15 gates passing:

- centralized compatibility difference and ownership violations are zero;
- message-bound violations are zero and mean planner-state age is positive;
- the worst natural integrated-loss noninferiority LCB is `-0.00786` against
  `-0.05`; source-competition LCB is also `-0.00786` against `-0.03`;
- maximum mean component-count increase is `0.00442`, and worst delivery LCB
  is `0.0`;
- canonical attack loss is `0.4374`, attack movement change is `-0.0159`, and
  honest recovery passes;
- wrong-action, calibration, asynchronous-path, negotiation-value, and runtime
  gates pass.

This validates decentralized planner ownership inside the declared simulator.
It does not decentralize every estimator operation or establish arbitrary
network-fault tolerance.

### 11.7 M11 and M11.1: external MR.CLAM replay

M11 uses the real UTIAS MR.CLAM logs for a causal known-map localization task.
Each of five robots predicts from recorded odometry and may assimilate at most
two current landmark range-bearing observations selected by expected position
covariance reduction. Vicon initializes the pose and is then isolated until
post-estimate scoring. Recorded inter-robot observations generate topology and
outage diagnostics but do not become landmark updates.

Dataset 1 development passed all gates at `0.313 m` bounded-filter RMSE versus
`3.587 m` odometry-only. The frozen Dataset 9 held-out run then failed closed
before estimation: the first two odometry rows are in descending timestamp
order for robots 1–4. That original verdict remains **`M11-INVALID`**.

M11.1 transparently treats Dataset 9 as repair/development data. It stable-sorts
each timed file by timestamp, preserves equal-time order, records source and
canonical hashes, and drops no rows. Dataset 9 contains 1,116,726 rows, four
timestamp inversions, and eight moved rows. It also exposed severe covariance
overconfidence under occlusion; a six-point development-only grid selected
process standard deviations `0.30 m` and `0.15 rad`.

The repaired source/protocol were frozen before Dataset 6 was extracted.
Dataset 6 contributes 605,947 rows with no reorder needed and 12 complete
windows per robot. The replacement held-out verdict is **`M11.1-GO`**, all 15
combined gates passing:

- bounded-two RMSE is `0.514 m`, versus `2.163 m` odometry-only and `0.541 m`
  all-landmarks;
- mean position NEES is `1.93`, mean-window P95 NEES `6.56`, and 95% coverage
  `0.899`;
- update rate is `0.543` with an exact maximum of two, outage RMSE is
  `0.369 m`, and connected/disconnected recorded topology is exercised;
- six unknown-barcode observations are rejected and counted; all structural,
  hash, determinism, runtime, and malformed-input gates pass.

This is external validity for the bounded known-map replay task only. It does
not externally validate M10's adversarial source-assignment model.

### 11.8 M12: measured acceleration and behavioural jerk

M12 tests estimator and behavioural acceleration separately. The estimator
augments pose with forward/angular velocity and integrates causal measured
linear/angular acceleration across each replay bin. The comparison retains the
frozen landmark selector, two-update budget, robust gate, and scoring. A
separate fixed command-profile assay compares acceleration clipping with the
same clipping plus a jerk limit.

Dataset 1 development decisively rejects the estimator:

- constant-velocity RMSE is `0.313 m`; measured-acceleration RMSE is `0.521 m`,
  with baseline-minus-candidate improvement `-0.208 m`, 95% CI
  `[-0.386, -0.062]`;
- mean NEES rises from `2.63` to `19.38`, coverage falls to `0.853`, and outage
  RMSE becomes `2.00 ×` baseline;
- acceleration is genuinely exercised on `42.3%` of cycles, and finite,
  bounded-update, and runtime gates pass, so the failure is not an inactive
  implementation.

The result is **`M12-DEVELOPMENT-FAIL`** and the untouched Dataset 7 archive is
not extracted or evaluated. The behavioural assay separately passes: peak
jerk falls from `16.0` to `1.6 m/s³` with the `0.8 m/s²` acceleration bound and
only `0.045 m/s` added velocity RMSE. Retain that limiter as an isolated future
controller candidate; do not add the tested acceleration state to the replay
filter.

### 11.9 M13: external full-loop validation

M13.0 adds a hardware-facing boundary without changing any frozen M9–M12
candidate. Every operational message carries run/sender/sequence/monotonic
time/epoch, a four-state estimate, 4 × 4 covariance, trust metadata, payload,
and exact canonical byte count. Recursive checks prohibit truth fields.
Operational, transport, and safety evidence is hash chained separately from an
independent scorer ledger. The ROS 2 package provides estimate, proposal,
diagnostic, command, safety, and restricted truth interfaces.

M13.1 then tests four arms over ten scenarios: stable motion, manoeuvre,
physical occlusion, burst loss/latency, partition/rejoin, outage/rejoin,
legitimate high precision, colluding covariance ramp, temporary attack, and an
adaptive bounded attacker. The plant, range-bearing camera, transport, attack
shim, operational inboxes, planner, safety supervisor, and scorer do not call
the historical simulator.

The formal result is **`M13.1-HIL-PILOT-READY`**:

- 6,000 trials = four arms × ten scenarios × 150 paired seeds;
- all 12 truth/replay, collision/e-stop, intervention, ownership/message,
  noninferiority, attack-loss, wrong-action, calibration, alert, recovery, and
  transport/topology/runtime entry gates pass;
- candidate-versus-central integrated-loss improvement is `-0.00362`, 95% CI
  `[-0.00447, -0.00279]`, above the `-0.05` lower-bound gate;
- material wrong-action, collision, emergency-stop, ownership-violation, and
  message-bound-violation counts are zero;
- replay fingerprints match and the scorer process is absent from operational
  records.

This is deliberately not called external physical validation. M13.2 has a
generated 320-run development plan: eight paired blocks per scenario, four
arms, and three day labels. Genuine sealed bundles are needed to estimate
variance, calibrate camera covariance, and freeze the M13.3 block count.
Synthetic or loopback evidence is rejected. M13.3 is implemented but remains
unopened; it also rejects pilot reuse, candidate/protocol source drift, fewer
than three days, incomplete blocks, and any underpowered scenario.

## 12. Acceleration outcome and physical transition

The completed M12 result closes the straightforward measured-acceleration
branch. A future estimator proposal must be materially different and
prospectively justified—for example an interacting multiple-model filter with
an explicit manoeuvre mode, higher-rate propagation between odometry samples,
or a task where acceleration is actually latent rather than reconstructed from
already high-rate commands. It must use a new development set and a fresh
held-out archive.

Behavioural acceleration remains separate. The passing jerk limiter may enter
a future closed-loop simulator ablation with unchanged estimation, fixed
velocity recurrence, explicit path/energy cost, and safety constraints.
Promotion still requires held-out decision or recovery benefit, calibrated
uncertainty, and a complexity/runtime case.

The immediate path is now operational rather than algorithmic: qualify the
camera, ROS 2/MCAP exporter, clock synchronization, safety I/O, and independent
truth recorder on the M13.2 plan. Do not tune the trust or allocation
candidate from pilot outcomes; only the declared covariance scale, safety
limits, and powered M13.3 sample size may be frozen there.

## 13. Reproducibility and commands

Run the M8 protocol with:

```bash
PYTHONPATH=src python3 -m flockkalman realism-suite \
  --config configs/default.json \
  --seed-count 100 \
  --seed-start 5000 \
  --bootstrap-samples 5000 \
  --output results/milestone8_heldout
```

Run the frozen M8.1 positive control with:

```bash
PYTHONPATH=src python3 -m flockkalman ambiguity-assay \
  --config configs/ambiguity_assay.json \
  --seed-count 100 \
  --seed-start 7000 \
  --bootstrap-samples 5000 \
  --output results/milestone8_1_heldout
```

Run the training-only fixed-recurrence mechanism diagnostic with:

```bash
PYTHONPATH=src python3 -m flockkalman momentum-mechanism \
  --config configs/default.json \
  --seed-count 30 \
  --seed-start 8000 \
  --output results/momentum_mechanism_training
```

Run the frozen M9B held-out suite with:

```bash
PYTHONPATH=src python3 -m flockkalman active-sensing-suite \
  --config configs/active_sensing.json \
  --seed-count 100 \
  --seed-start 10000 \
  --bootstrap-samples 5000 \
  --output results/milestone9b_heldout
```

Reanalyze its saved paired rows and fingerprints with:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-active-sensing-suite \
  --output results/milestone9b_heldout \
  --bootstrap-samples 5000
```

Reprice the immutable M9B held-out actions across the declared movement-cost grid:

```bash
PYTHONPATH=src python3 -m flockkalman movement-cost-sweep \
  --output results/milestone9b_heldout \
  --bootstrap-samples 5000
```

Run the frozen M9A held-out suite with:

```bash
PYTHONPATH=src python3 -m flockkalman topology-suite \
  --config configs/default.json \
  --seed-count 100 \
  --seed-start 12000 \
  --bootstrap-samples 5000 \
  --output results/milestone9a_heldout
```

Reanalyze its saved paired rows and verify all fingerprints with:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-topology-suite \
  --output results/milestone9a_heldout \
  --bootstrap-samples 5000
```

Run the non-promotional M9A.5 nested-reference diagnostic on those same held-out traces with:

```bash
PYTHONPATH=src python3 -m flockkalman oracle-floor-suite \
  --config configs/default.json \
  --seed-count 100 \
  --seed-start 12000 \
  --bootstrap-samples 5000 \
  --output results/milestone9a5_oracle_floor
```

Reanalyze its saved rows and verify all 800 fingerprints with:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-oracle-floor-suite \
  --output results/milestone9a5_oracle_floor \
  --bootstrap-samples 5000
```

Run the M9A.6 development split without authorizing integration:

```bash
PYTHONPATH=src python3 -m flockkalman missing-evidence-suite \
  --config configs/default.json \
  --phase training \
  --seed-count 30 \
  --seed-start 13000 \
  --bootstrap-samples 5000 \
  --output results/milestone9a6_training
```

After freezing the candidate and gates, run the one-shot held-out confirmation:

```bash
PYTHONPATH=src python3 -m flockkalman missing-evidence-suite \
  --config configs/default.json \
  --phase heldout \
  --seed-count 100 \
  --seed-start 14000 \
  --bootstrap-samples 5000 \
  --output results/milestone9a6_heldout
```

Reanalyze the saved 1,000 rows and verify every fingerprint with:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-missing-evidence-suite \
  --output results/milestone9a6_heldout \
  --bootstrap-samples 5000
```

Run the M9A.7 development split and powered held-out confirmation defined in [`M9A7_PROTOCOL.md`](M9A7_PROTOCOL.md):

```bash
PYTHONPATH=src python3 -m flockkalman admission-evidence-suite \
  --config configs/default.json \
  --phase training \
  --seed-count 60 \
  --seed-start 15000 \
  --bootstrap-samples 5000 \
  --output results/milestone9a7_training

PYTHONPATH=src python3 -m flockkalman admission-evidence-suite \
  --config configs/default.json \
  --phase heldout \
  --seed-count 300 \
  --seed-start 16000 \
  --bootstrap-samples 5000 \
  --output results/milestone9a7_heldout
```

Reanalysis verifies all 3,600 held-out fingerprints and regenerates the powered verdict:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-admission-evidence-suite \
  --output results/milestone9a7_heldout \
  --bootstrap-samples 5000
```

Run the frozen M9C integration protocol defined in [`M9C_PROTOCOL.md`](M9C_PROTOCOL.md):

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

Reanalysis recomputes every gate from the 4,950 saved rows and verifies their trace fingerprints:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-integration-suite \
  --output results/milestone9c_heldout \
  --bootstrap-samples 5000
```

Run the M10A adversarial-trust protocol defined in [`M10A_PROTOCOL.md`](M10A_PROTOCOL.md):

```bash
PYTHONPATH=src python3 -m flockkalman adversarial-trust-suite \
  --phase heldout \
  --seed-count 150 \
  --seed-start 21000 \
  --workers 8 \
  --bootstrap-samples 5000 \
  --output results/milestone10a_heldout
```

Reanalysis recomputes all 16 gates from the 8,250 saved arm rows and verifies every exogenous fingerprint:

```bash
PYTHONPATH=src python3 -m flockkalman reanalyze-adversarial-trust-suite \
  --output results/milestone10a_heldout \
  --bootstrap-samples 5000
```

Run the frozen M10A.5 closed-loop protocol:

```bash
PYTHONPATH=src python3 -m flockkalman closed-loop-trust-suite \
  --phase heldout \
  --seed-count 150 \
  --seed-start 23000 \
  --workers 8 \
  --bootstrap-samples 5000 \
  --output results/milestone10a5_heldout
```

Run and reanalyze the frozen M10B decentralized protocol:

```bash
PYTHONPATH=src python3 -m flockkalman decentralized-suite \
  --phase heldout \
  --seed-count 150 \
  --seed-start 25000 \
  --workers 8 \
  --bootstrap-samples 5000 \
  --output results/milestone10b_heldout

PYTHONPATH=src python3 -m flockkalman reanalyze-decentralized-suite \
  --output results/milestone10b_heldout \
  --bootstrap-samples 5000
```

Run the M11.1 canonicalized external replay against an already extracted
official archive:

```bash
PYTHONPATH=src python3 -m flockkalman external-replay-repair-suite \
  --dataset external_data/MRCLAM_Dataset6 \
  --canonical external_data/MRCLAM_Dataset6_canonical \
  --archive external_data/MRCLAM6.zip \
  --phase heldout \
  --bootstrap-samples 5000 \
  --output results/milestone11_1_heldout
```

Reproduce the M12 development stop without opening Dataset 7:

```bash
PYTHONPATH=src python3 -m flockkalman acceleration-suite \
  --dataset external_data/MRCLAM_Dataset1 \
  --canonical external_data/MRCLAM_Dataset1_canonical \
  --archive external_data/MRCLAM1.zip \
  --phase development \
  --bootstrap-samples 5000 \
  --output results/milestone12_development
```

Run the powered M13.1 independent reference screen:

```bash
PYTHONPATH=src python3 -m flockkalman full-loop-hil-suite \
  --steps 120 \
  --seed-count 150 \
  --seed-start 27000 \
  --bootstrap-samples 2000 \
  --workers 8 \
  --output results/milestone13_1_hil
```

Generate the M13.2 randomized pilot plan:

```bash
PYTHONPATH=src python3 -m flockkalman physical-trial-plan \
  --phase pilot \
  --blocks-per-scenario 8 \
  --trial-dates pilot-day-1,pilot-day-2,pilot-day-3 \
  --output physical/m13_pilot_plan
```

The physical workflow then uses `seal-physical-bundle`,
`score-physical-bundle`, `physical-pilot`, and—only after the resulting
`power_freeze.json` exists—`physical-heldout`. `M13_PROTOCOL.md` is the
canonical lab and stop-rule specification.

Run the tests with:

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The M8 held-out directory contains the complete suite configuration, 4,000 per-run summaries, scenario aggregates, paired effects, 1,000 verified trace hashes, the machine-readable verdict, and the Markdown report. The M8.1 directory separately contains its run and policy/dose summaries, paired effects, verified fingerprints, verdict, and report. M9B adds 2,500 run rows, scenario/policy summaries, component-level effects, 500 verified fingerprints, its frozen decision, and v0.12 fixed-action movement-cost sensitivity artifacts. M9A adds 4,000 run rows, scenario summaries, ablation/transfer effects, 800 verified fingerprints, and a replay-stable partial verdict. M9A.5 adds 800 paired frozen-trajectory rows, observer/global transfer effects, within-scenario decomposition gaps, 800 replayed fingerprints, and a non-promotional diagnosis. M9A.6 adds 300 training and 1,000 held-out paired rows. M9A.7 adds 720 formal training rows and 3,600 powered held-out rows. M9C adds 4,950 powered held-out rows, broad/VOI/M9A.7 effects, 1,650 replayed exogenous traces, frozen protocol/source hashes, a machine-readable decision, and a generated report. M10A adds 8,250 arm-level held-out rows, 1,650 replayed exogenous traces, ablation effects, frozen candidate/protocol hashes, a 16-gate decision, and a generated report. M10A.5 adds 3,600 held-out arm rows across 1,800 exogenous traces. M10B adds 3,600 held-out arm rows across 1,200 traces plus ownership, message, conflict, and state-age diagnostics. M11/M11.1 add archive/materialized hashes, canonicalization manifests, 60-second replay windows, paired effects, and per-step real-log estimates. M12 adds paired constant-velocity/acceleration windows and an isolated jerk-assay artifact. M13.1 adds 6,000 run rows, ten-scenario aggregates, 30 paired-effect rows, independent operational/truth audit traces, replay and source hashes, 12 gates, and a report. M13.2 adds the randomized 320-run pilot schedule and an empty evidence template; it does not yet contain physical measurements.

## 14. Research decision

This remains a sound but narrowed research direction:

- retain flocking as a candidate information-acquisition policy coupled to conservative local state estimation;
- retain fixed velocity recurrence as the supported motion baseline;
- advance robust bias-aware, multi-hypothesis fusion;
- make ambiguity an explicit output rather than forcing premature consensus;
- do not promote the current investigation allocator merely because it increases information gain;
- treat the M8.1 pass as proof that viewpoint-mediated Bayesian evidence is testable, not as a reversal of M8;
- retain the completed M9A architecture because it repairs calibration, mode retention, rejoin shock, and partition accounting, but do not promote it past its held-out `PARTIAL-GO`;
- treat M9A.5 as a mixed localization result: asymmetric partition contains a real observer-information boundary, while large frozen-M9A-to-observer gaps show substantial policy and hypothesis-representation headroom elsewhere;
- retain M9A.6 as evidence that assignment weighting and risk pricing remove most exact-model policy loss, while preserving its historical held-out `NO-GO`;
- advance M9A.7 as the admission-aware output baseline because all powered held-out repair, calibration, wrong-action, attack, replay, and frozen-motion gates pass;
- retain M9C as a `PARTIAL-GO`: bounded component-local VOI transfers to dynamic topology with a small but powered movement-inclusive gain and no measured topology or output-safety regression;
- retain M10A as the frozen output-layer defense and advance M10A.5 as the closed-loop research baseline because all 16 powered feedback, recovery, safety, and compatibility gates pass;
- retain cross-channel disagreement, ramp-rate evidence, and suspicious-source influence budgeting as a composed defense; none alone should be described as a general trust solution;
- retain M10B's per-agent ownership, message-limited planner state, local conflict resolution, and asynchronous replanning because all 15 powered held-out gates pass;
- retain the M9B two-step VOI allocator because it beat passive, myopic, and current round-robin controls at the declared cost scale, while constraining the claim to the measured break-even envelope;
- describe the M9B result as movement efficiency with equal safety, not better accuracy or faster resolution;
- retain M11.1 as external evidence for bounded known-map localization while preserving the original M11 `INVALID` result and its exact timestamp diagnosis;
- require future external work to test cooperative fusion, adversarial trust, and action allocation directly rather than extrapolating from known-map replay;
- reject M12's measured-acceleration estimator and keep Dataset 7 sealed; do not tune that formulation further;
- retain only the isolated jerk limiter for a future behavioural closed-loop ablation with explicit path, energy, and safety costs;
- accept M13.1 as authorization to enter the instrumented development pilot, not as external physical validation;
- freeze M13.3 only from genuine M13.2 robot evidence and report any integrity failure as `INVALID`, never as a repaired scientific result;
- do not revisit adaptive recurrence without a new mechanism or task that differs materially from the rejected M5/M8.2 formulations.

The research direction remains sound, but its profitable branch is now clearer.
M10A.5 shows that the trust repair survives causal sensing feedback; M10B shows
that planner ownership can be decentralized without losing the declared
utility, topology, or calibration properties; and M11.1 establishes that the
bounded filtering core survives a real asynchronous log after transparent data
canonicalization and development-only recalibration. M12 is equally useful as
a negative result: simply adding measured acceleration to an already
high-rate-odometry filter makes estimation materially worse. M13.1 now shows
that the complete reference loop remains safe and noninferior under an
independent plant, packet schedule, physical occlusion, outage/rejoin, and a
causal adaptive attacker. Its small but powered loss disadvantage against the
central arm is acceptable for pilot entry, not evidence that decentralization
improves estimation.

The platform is still insufficient for deployment. The assignment, residual,
and trust models remain unqualified on physical cameras; the formal M13.1
transport is deterministic software rather than measured Wi-Fi/DDS; and M10B
still decentralizes planner actions rather than every fusion computation.
The next action is to execute the generated M13.2 instrumented pilot, qualify
the site adapters, and freeze the powered M13.3 holdout. Kinematic state
expansion must not be added to that protocol.
