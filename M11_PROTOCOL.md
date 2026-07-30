# M11 preregistered external MR.CLAM replay protocol

Status: Dataset 1 is the development replay and Dataset 9 is the untouched
occlusion-held-out replay. Parser, filter parameters, windowing, metrics, and
gates are frozen before Dataset 9 is evaluated.

## Source and claim boundary

The University of Toronto Institute for Aerospace Studies MR.CLAM collection
contains timestamped odometry and camera-derived range–bearing observations
from five physical iRobot Create robots, plus Vicon ground truth. Dataset 9
contains physical barriers that reduce measurement availability.

Official source:
`https://asrl.utias.utoronto.ca/datasets/mrclam/`

Citation: K. Y. K. Leung, Y. Halpern, T. D. Barfoot, and H. H. T. Liu,
“The UTIAS multi-robot cooperative localization and mapping dataset,” IJRR
30(8):969–974, 2011.

Archive hashes:

- `MRCLAM1.zip`:
  `57c0166b0e2761680e83ffa67b4f58bad7187c41fd723345a4a45ebd50a6557e`
- `MRCLAM9.zip`:
  `013714987dc0f797853689a80146da1fee50478ad884491d0eeac5f6357602d4`

M11 tests replay ingestion and causal localization on real asynchronous logs.
It does not claim that a known-landmark localization task validates M10's
adversarial target-tracking model.

## Operational path

For each robot:

1. initialize pose and covariance from the first Vicon record;
2. predict with recorded forward and angular odometry;
3. assimilate recorded range–bearing observations to mapped landmarks;
4. use Vicon only after each estimate is fixed, for scoring.

Barcode identity maps observations to robot or landmark subjects. Inter-robot
observations generate a recorded directed visibility graph and topology/outage
diagnostics; only known-landmark observations update the localization filter.
All streams are resampled causally with previous-sample odometry and
measurements inside the current half-open replay bin.

## Arms

1. `odometry_only`: prediction without landmark updates.
2. `all_landmarks`: assimilate every causally available landmark observation.
3. `bounded_two`: each robot owns its update and selects at most two current
   landmark observations by predicted covariance reduction, with deterministic
   subject-ID tie breaking.

Frozen replay parameters:

- grid interval: `0.50 s`;
- process standard deviations: position `0.10 m`, heading `0.06 rad`;
- measurement standard deviations: range `0.18 m`, bearing `0.10 rad`;
- robust innovation gate: two-dimensional NIS `25`;
- initialization covariance: diagonal `[0.05², 0.05², 0.03²]`;
- evaluation windows: 60 seconds, excluding incomplete final windows.

## Splits

- Development: MR.CLAM Dataset 1.
- Held-out: MR.CLAM Dataset 9, whose physical occlusions are not used for
  tuning.
- Paired bootstrap: 5,000 resamples over robot/window pairs.

## Frozen gates

1. Archive and materialized-file hashes verify; replay is deterministic.
2. All 17 required files parse, timestamps are monotone, unknown observation
   barcodes are rejected and counted, and malformed structural files fail
   closed.
3. The operational filter never reads post-initialization Vicon truth.
4. All five robots contribute at least ten complete held-out windows.
5. `bounded_two` position-RMSE improvement over odometry has paired 95% LCB
   greater than zero.
6. `bounded_two` RMSE is noninferior to `all_landmarks`: all-minus-bounded
   improvement LCB is at least `-0.10 m`.
7. `bounded_two` uses at most two landmark updates per robot per replay bin and
   has a positive update rate.
8. Held-out mean position NEES is at most `8`, mean window P95 NEES at most
   `30`, and 95% coverage at least `0.80`.
9. At least one measurement-outage run of 5 seconds is present, every arm
   remains finite through it, and bounded-filter outage RMSE is no more than
   20% worse than odometry.
10. Recorded inter-robot topology includes both connected and disconnected
    bins, and all graph/message diagnostics are finite.
11. Bounded replay runtime is no more than `1.5 ×` all-landmarks runtime plus
    `0.10 s` per robot.

Validity failure yields `M11-INVALID`. Other failure yields `M11-NO-GO`. All
gates passing yields `M11-GO` for acceleration ablation on external replay.
Production is never authorized.
