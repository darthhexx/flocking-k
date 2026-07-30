# M17 dose-axis selection — a smoke-stage diagnostic

**Date:** 30 July 2026
**Type:** non-promotional harness diagnostic. Ran on smoke seeds 31900–31952,
outside every training and held-out band, firewall-checked.
**Outcome:** the predeclared dose axis was rejected and replaced. Disclosed here
rather than substituted silently.

---

## What the protocol assumed

`MILESTONES_correctability_program.md` M17 declared a "censoring dose sweep on the
M9A.7 engineered positive control, dose ∈ {0, 0.1, 0.2, 0.35, 0.5, 0.7, 1.0} of the
constructed censoring rate" without naming the parameter. The obvious candidate was
`topology_rejoin_probation_steps`: the positive control sets it to 40 against a
platform default of 4, and its own description is *"aggressive rejoin probation makes
fresh operational measurements routinely belief-censored"*. Longer probation, more
censoring.

## What the smoke sweep found

Seven doses, 3 seeds, 8.5 minutes:

| dose | probation steps | candidate decision loss | candidate mean NEES |
|---|---|---|---|
| 0.00 | 4 | 0.3288 | 1.7259 |
| 0.10 | 8 | 0.3297 | 1.7230 |
| 0.20 | 11 | 0.3308 | 1.7293 |
| 0.35 | 17 | 0.3302 | 1.7297 |
| 0.50 | 22 | 0.3302 | 1.7294 |
| 0.70 | 29 | **0.3302** | **1.7294** |
| 1.00 | 40 | **0.3302** | **1.7294** |

The last three rows are byte-identical. The axis is saturated across more than half
its declared range, and total movement over the whole range is 0.4% of decision loss.

**Mechanism.** The positive control repeats partitions every 10 steps
(`topology_partition_repeat_interval: 10`, `repeat_count: 7`). Once the probation
window exceeds roughly two partition cycles, a rejoining agent is re-partitioned
before probation ever completes, so it never reaches TRUSTED and further increases in
probation length change nothing at all.

## Why this matters more than a wasted afternoon

A 300-seed sweep on this axis costs about 15 hours at the observed rate and would
have returned an almost flat line in both regret *and* NEES.

That is indistinguishable from **M17 exit condition 4** — *"gates 17.4–17.7 fail, NEES
does see the failure, the blindness claim collapses"* — which the program identifies
as the outcome that kills the research direction. The correct reading would have been
"the knob never moved"; the available reading would have been "the direction is
dead". Nothing in the artifact would have distinguished them.

This is the entire reason the program's suggested sequencing puts a smoke and
training check before any held-out run.

## Candidate comparison

Two-point probes, 2 seeds each, on the positive control:

| knob | decision loss moved | mean NEES moved | verdict |
|---|---|---|---|
| `topology_rejoin_probation_steps` | 0.0028 | 0.0035 | saturates; rejected |
| `m9a7_excluded_secondary_mass_scale` | **0.0000** | **0.0000** | no effect; see below |
| `m9a7_raw_measurement_nis_ceiling` | 0.1100 | 0.4037 | NEES sees it; rejected as the axis |
| `agent_failure_count` | 0.0861 | 0.0748 | **selected** (but see below: 0.166 at 3 seeds) |

### Two findings worth keeping

**`m9a7_excluded_secondary_mass_scale` has literally no effect on this scenario.**
Setting it from 1.0 to 0.0 changes decision loss and NEES by exactly zero. That is
the M9A.7 repair's *own* parameter — the one that scales how much excluded secondary
mass the assignment posterior carries. Either it is inert on this scenario or it is
mis-wired. It should be checked before any claim rests on it, and M9A.7's own
sensitivity to it should be established rather than assumed.

**Threshold tightening moves NEES much harder than contributor loss — at these
sample sizes, provisionally.** `m9a7_raw_measurement_nis_ceiling` 100 → 3 moves NEES
by 0.40, four times the predeclared margin. `agent_failure_count` 1 → 6 moved it by
0.075 at 2 seeds — but by 0.166 at 3 seeds (see the preliminary section below), so
the number is unstable and the *ordering* is the only part worth provisionally
keeping.

The tempting reading is that censoring by threshold tightening is visible to
self-consistency checks while censoring by contributor loss is not, which would make
the blindness claim conditional and mechanistic rather than blanket. **That reading is
not supported at this sample size and must not be carried into §6 until the powered
run says so.** It is recorded as a hypothesis the training run can test, not a
finding. `agent_failure_count` was selected because it produces a genuine monotone
dose response, not because it was shown to be NEES-invisible.

## The replacement axis

`agent_failure_count` on the positive control, over 1–6 censored agents
(8 agents total, so dose 1.0 censors six of eight).

**Deviation from the predeclared grid, disclosed:** the protocol declared seven doses
{0, 0.1, 0.2, 0.35, 0.5, 0.7, 1.0}. The realised grid is six levels,
{1, 2, 3, 4, 5, 6} censored agents → doses {0, 0.2, 0.4, 0.6, 0.8, 1.0}. Two reasons,
both forced: the quantity is a discrete count, and zero is unreachable because the
positive control sets failure timing and config validation rejects
`agent_failure_count = 0` with "failure timing requires agent_failure_count > 0". Six
equally spaced levels over the reachable range rather than seven over an unreachable
one.

## Preliminary smoke response on the selected axis — READ THE CAVEAT

Six doses, 3 seeds, positive-control scenario:

| dose | censored agents | decision loss | mean NEES | coverage95 |
|---|---|---|---|---|
| 0.00 | 1 | 0.2920 | 1.5633 | 0.9771 |
| 0.20 | 2 | 0.3073 | 1.6174 | 0.9729 |
| 0.40 | 3 | 0.3302 | 1.7294 | 0.9604 |
| 0.60 | 4 | 0.3687 | 1.6876 | 0.9688 |
| 0.80 | 5 | 0.3795 | 1.6961 | 0.9604 |
| 1.00 | 6 | 0.3941 | 1.7232 | 0.9583 |

| quantity | slope/unit dose | range | Spearman | vs. margin |
|---|---|---|---|---|
| decision loss | +0.1093 | 0.1021 | **+1.00** | — |
| mean NEES | +0.1420 | 0.1661 | +0.66 | margin 0.10 → **outside** |
| coverage95 | −0.0176 | 0.0187 | −0.83 | margin 0.006 → **outside** |

**The good part.** Decision loss rises perfectly monotonically with censoring dose
(Spearman +1.00). Gates 17.1–17.3 look reachable, and the axis is a real dose axis
rather than a saturated one.

**The bad part, stated plainly.** Mean NEES also rises, at a slope (+0.142) *larger*
than the regret slope, and coverage falls monotonically. Both sit outside their
predeclared negligibility margins. Taken at face value that is **M17 exit
condition 4** — *"NEES does see the censoring, the blindness claim collapses"* — the
outcome the program identifies as fatal to the research direction.

**Why it is not yet evidence of anything.** Three seeds. Candidate mean-NEES standard
deviation on these runs is around 0.29, so the standard error on a per-dose mean is
roughly 0.17 — larger than the entire fitted slope. The slope estimate of 0.142 is not
statistically distinguishable from zero, nor from 0.30. Six points at this noise level
cannot separate "NEES is flat" from "NEES tracks regret", which is precisely the
distinction the milestone turns on.

The honest summary: **the preliminary signal is unfavourable and does not rule out
exit condition 4; it does not establish it either.** The 300-seed training run is what
decides, and it should be read with the equivalence tests of gates 17.4 and 17.6, not
by eyeballing this table.

It also weakens the two-point claim above. The contributor-loss axis moved NEES by
0.075 over 1→6 agents at 2 seeds, but 0.166 at 3 seeds over the same range. The
"contributor loss is invisible to NEES" reading is not supported at this sample size
and should not be carried into §6 until the powered run says so.

## Status

The axis is selected and the harness runs end-to-end, but **M17 has not been run on
the training band.** At the observed rate (76 s per dose per 3 seeds on 2 cores) a
300-seed sweep is roughly 15 hours, which exceeds a single working session. It should
be run as a background job, training band 31000–31299 only, before the held-out band
32000–32299 is opened.
