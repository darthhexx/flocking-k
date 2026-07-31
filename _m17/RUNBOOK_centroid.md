# centroid runbook

Everything analysis-side is already done on the Mac. What is left for `centroid` is
compute. Set `--workers` to the **physical** core count — the workload is pure NumPy
on CPU, there is no GPU path, and hyperthreads add little while raising memory
pressure.

---

## 0. Get the code

Push from the Mac first (three unpushed commits plus four dirty `_m17` files; the
`origin` remote is SSH so the push has to come from your machine), then:

```bash
cd ~/flocking_kalman_research_platform
git pull
```

Verify you have the new evaluator before anything else — this is the check that
would have caught last night's problem:

```bash
python3 _m17/evaluate_m17_gates.py --help | grep -- --all
```

Expect `--all  evaluate every dosable scenario and write an aggregate`. No output
means the pull did not land.

## 1. Rebuild the v2 records on centroid (~1 min)

`centroid` still has only `admission_censoring_control` in its
`gate_evaluation.json` — the other three were overwritten. The factorial in step 4
needs `gate_evaluation_failure_only.json` as its cell A reference, so regenerate
them here even though the Mac already has its own copies.

```bash
python3 _m17/evaluate_m17_gates.py --sweep results/milestone17_training_v2 --all
python3 _m17/record_m17_decision.py  --sweep results/milestone17_training_v2
```

No simulation re-runs — both read existing artifacts. Cross-check against the Mac:

| scenario | regret | NEES | coverage |
|---|---|---|---|
| `failure_only` | 0.090 | 0.408 | 0.659 |
| `failure_partition` | 0.070 | 0.373 | 0.655 |
| `staggered_rejoin` | 0.086 | 0.377 | 0.658 |
| `admission_censoring_control` | 0.098 | 0.086 | 0.189 |

If centroid disagrees with these, **stop** — the two machines are not running the
same code, and nothing downstream is trustworthy until that is resolved.

## 2. Factorial smoke (~2 min)

Cheap, and it gates a four-hour run.

```bash
python3 -u _m17/run_m17_factorial.py --phase smoke --workers 16
```

Expect all three cells distinct from A. For reference, from a 2-seed single-dose run
in the session container:

| cell | probation | duration | max abs diff vs A |
|---|---|---|---|
| B | 40 | 70 | 0.015740313 |
| C | 4 | 30 | 0.020148650 |
| D | 40 | 30 | 0.028789102 |

Your numbers will differ (different seeds and dose grid). What matters is that none
of them is `0.000000000`. An `IDENTICAL` verdict exits non-zero and prints a stop
notice — that is the saturation failure that disqualified
`topology_rejoin_probation_steps` as a dose axis, and it means the factorial cannot
work at these settings.

## 3. Held-out (~1 h 20 m at 16 workers)

**Band 32000–32299 is spent the moment this starts.** Hypotheses are fixed in
`PROTOCOL_AMENDMENT_003_m17.md` §5.1 — H1 anti-correlation, H2 decision repair, H3
asymmetric residual, all directional, no causal claim. Read §5 before launching; the
band cannot be reopened.

```bash
nohup python3 -u _m17/run_m17_dose.py \
    --phase heldout \
    --seed-start 32000 --seed-count 300 \
    --workers 16 \
    --resume \
    --progress-every 120 \
    > m17_heldout.log 2>&1 &

tail -f m17_heldout.log
```

`--progress-every 120` keeps an unattended log small. `--resume` skips any dose whose
`decision.json` already exists, so re-running the identical command after a crash
picks up where it stopped. It will not resume *within* a dose — a partial dose is
re-run from scratch, because the suite computes statistics over the whole seed set.

Then:

```bash
python3 _m17/evaluate_m17_gates.py --sweep results/milestone17_heldout --all
```

## 4. Factorial (~4 h at 16 workers)

Independent of step 3. Run it after, unless the box is large enough that they will
not contend — they are both CPU-saturating.

```bash
nohup python3 -u _m17/run_m17_factorial.py \
    --phase training --cells B,C,D \
    --workers 16 --resume \
    > m17_factorial.log 2>&1 &
```

Cell A is `failure_only` from the v2 sweep and is not re-run. Then evaluate each cell
on the base scenario:

```bash
for c in B C D; do
  python3 _m17/evaluate_m17_gates.py \
      --sweep results/milestone17_factorial/cell_$c \
      --scenario failure_only
done
```

Read-out is the **candidate-arm NEES residual fraction** in each cell, against cell A
at 0.408:

- splits by probation (A, C high; B, D low) → gate selection depth is the cause
- splits by duration (A, B high; C, D low) → accumulated exposure is the cause
- splits by neither → the cause is structural; the design needs rethinking
- interaction → report it as an interaction, do not collapse to a main effect

## What to send back

For step 3, the `--all` summary block — the residual-fraction table plus the per-
scenario gate lines. For step 4, the four `decision_loss / mean_nees / coverage95`
residual lines, one per cell.

## Notes

- `--phase heldout` deliberately skips the diagnostic-firewall seed check; the band
  is its own declared range. Steps 2 and 4 run on 31000–31299 and **are** checked.
- The factorial offers no `heldout` phase. It is a cause-finding experiment and
  Amendment 003 §5.3 keeps it on the training band.
- If a run dies, the log is the truth. Every line is flushed, so a stalled log means
  a stalled run rather than a buffered one.
