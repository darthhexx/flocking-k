# M11.1 preregistered external-replay canonicalization repair

Status: Dataset 9 is a transparent repair/development set after the original
M11 held-out parser rejection. Dataset 6 is the untouched replacement
held-out set. The canonicalization rule, replay parameters, metrics, and gates
are frozen before Dataset 6 is extracted or parsed.

## Reason for the repair

Frozen M11 correctly failed closed when Dataset 9 contained one initial
negative timestamp jump in each of four odometry files. No estimates were
created and Dataset 9 is no longer treated as held out.

M11.1 adds one data-boundary operation: independently stable-sort every
Groundtruth, Odometry, and Measurement file by timestamp, preserve source
order for equal timestamps, and retain every numeric row. Barcode and landmark
tables retain their input order. The canonicalizer records source/canonical
hashes, inversions, duplicate times, moved-row counts, and maximum backward
jump for all 17 files. It never interpolates, imputes, deduplicates, or reads
ground truth for operational filtering.

## Archives and split

- Repair/development: Dataset 9,
  `013714987dc0f797853689a80146da1fee50478ad884491d0eeac5f6357602d4`.
- Replacement held-out: Dataset 6,
  `45295fec82cd1f60cd08ed661f7eacf4a08ae0d950a38f72feaf7fe0ab86368d`.

The official source and task boundary are unchanged from `M11_PROTOCOL.md`.

## Frozen replay

Dataset 9 development showed that Dataset 1's pose-process standard deviations
(`0.10 m`, `0.06 rad`) were badly overconfident under the occluded trace:
mean NEES `115.08` and 95% coverage `0.469`. A six-point development-only
grid selected the lowest-RMSE calibrated setting: position-process standard
deviation `0.30 m` and heading-process standard deviation `0.15 rad`.

The three M11 arms, causal half-open bins, known-map filter, two-update budget,
60-second windows, measurement noise, innovation gate, topology TTL, bootstrap
procedure, and eleven original M11 gates are unchanged. The two declared
process-noise values above are the only replay-model change.

Additional validity gates require:

1. the archive hash matches the declared split;
2. canonicalization is deterministic and all 17 output hashes verify;
3. input and output row counts are exactly equal;
4. every timed output is monotone nondecreasing;
5. the frozen M11 parser accepts the canonicalized output.

Original M11 failure remains recorded as `M11-INVALID`. M11.1 validity failure
yields `M11.1-INVALID`; a performance-gate failure yields `M11.1-NO-GO`; all
gates passing on Dataset 6 yields `M11.1-GO`. This authorizes only the
prospective acceleration ablation, never production.
