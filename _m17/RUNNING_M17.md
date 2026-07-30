# Running the M17 training sweep unattended

## The command

```bash
cd /path/to/flocking_kalman_research_platform

nohup python3 -u _m17/run_m17_dose.py \
    --phase training \
    --seed-start 31000 --seed-count 300 \
    --workers 16 \
    --resume \
    > m17_training.log 2>&1 &

tail -f m17_training.log                            # human view
tail -f results/milestone17_training/progress.jsonl # machine view
```

Set `--workers` to your physical core count. `-u` on the interpreter is belt and
braces — the script already flushes every line itself.

## Read this first: the GPU will not be used

The platform is pure NumPy on CPU. There is no CUDA path, no torch, no array
library that would dispatch to a device. **A GPU machine helps only through its
core count.** If the box has 32 cores it will be roughly 16× faster than the 2-core
environment the estimate below came from; if it has 8, roughly 4×.

Observed rate: ~0.6 trials/s on 2 workers. One dose at 300 seeds is 3,600 trials
(12 scenarios × 300 seeds), so:

| workers | per dose | full 6-dose sweep |
|---|---|---|
| 2 | ~1h 40m | ~10h |
| 8 | ~25m | ~2h 30m |
| 16 | ~13m | ~1h 20m |
| 32 | ~7m | ~40m |

Scaling is near-linear because each trial is independent and the pool is a
`ProcessPoolExecutor`. Do not set `--workers` above the physical core count; these
are CPU-bound, so hyperthreads add little and memory pressure grows.

## What you will see

```
========================================================================
M17 dose sweep | phase=training seeds=31000..31299 (300)
  doses     : 0.00, 0.20, 0.40, 0.60, 0.80, 1.00 (6 levels of agent_failure_count)
  workers   : 16 of 16 cpus  |  python 3.11.15  numpy 2.4.4
  output    : results/milestone17_training
  progress  : results/milestone17_training/progress.jsonl
========================================================================
[1/6] dose 0.00 (1 censored) starting
  [1/6] dose 0.00 (1 censored) 512/3600 trials ( 14.2%)   4.83 trial/s  dose ETA 0:10:39  sweep ETA 1:12:22 (~09:41 UTC)
  ...
[1/6] dose 0.00 (1 censored) DONE in 0:12:26 -> M9A7-TRAINING-PASS
```

A progress line lands at most every `--progress-every` seconds (default 30) plus
one at 100%. On a long run consider `--progress-every 120` to keep the log small.

## Why the flushing matters

The reason you saw no output is almost certainly not granularity — it is that
Python block-buffers stdout whenever it is not attached to a terminal. Redirected
to a file, the old script's per-dose prints would have sat in a 4–8 KB buffer for
hours. Every line now goes through a `flush=True` wrapper, so a redirected run is
live. This also means **a stalled log genuinely means a stalled run**, which is the
property you want at hour nine of an unattended job.

## Resuming

`--resume` skips any dose whose `decision.json` already exists. If the machine dies
at dose 4 of 6, re-run the identical command and it picks up at dose 4.

Two things it deliberately does not do. It will not resume *within* a dose — a
partially completed dose is re-run from scratch, because the suite computes its
statistics over the whole seed set and a half-finished artifact would silently be
underpowered. And it does not verify that a skipped artifact used the same
`--seed-count`; if you change the seed count, use a fresh `--output` directory
rather than resuming into the old one.

## Splitting across sessions

`--doses 0.0,0.2` runs a subset, so a sweep can be split across machines or
windows. All invocations must share `--output` for `sweep.json` to describe the
whole sweep; the last one to finish writes it, and it records only the doses that
invocation ran. `progress.jsonl` is append-only and safe to share.

## When it finishes

Gate evaluation is deliberately a separate step, so refining a threshold does not
mean re-running ten hours of simulation. `sweep.json` lists the per-dose artifacts;
gates 17.1–17.11 read those.

The thing to look at first is the **equivalence tests**, gates 17.4 and 17.6 —
whether the NEES and coverage slopes fall inside the predeclared negligibility
margins (0.10 and 0.006 per unit dose). The 3-seed smoke run put both *outside*
their margins, which taken at face value is M17 exit condition 4 and would kill the
direction. At 3 seeds the standard error exceeded the entire fitted slope, so that
signal means very little — but it is the reason this run matters, and it is why the
result should be read through the equivalence tests rather than by eyeballing the
dose table.

`_m17/DOSE_AXIS_SELECTION.md` has the full caveat.
