# M12 preregistered acceleration ablation protocol

Status: Dataset 1 is development. Dataset 7 is the untouched held-out replay.
The estimator, behavioural assay, thresholds, and gates are frozen before
Dataset 7 is extracted or parsed. A held-out verdict is invalid unless M11.1
first returns `M11.1-GO`.

## Research questions

1. Does a causal measured-acceleration pose model improve the replay-qualified
   bounded landmark filter beyond its constant-velocity propagation?
2. Separately, can a jerk-limited velocity response bound discontinuous
   acceleration without an unacceptable command-tracking penalty?

These are separate claims. Recorded trajectories cannot validate behavioural
closed-loop motion, so the jerk limiter is tested only in a deterministic
command-profile assay and is not used to alter replayed robot motion.

## Estimator arms

1. `bounded_constant_velocity`: the frozen M11 bounded-two filter.
2. `bounded_measured_acceleration`: state
   `[x, y, heading, forward velocity, angular velocity]`; current and previous
   causal odometry commands define constant linear/angular acceleration over
   each 0.5-second bin. Pose integrates the midpoint velocity and angular
   rate. Landmark selection, robust gate, measurement noise, process pose
   noise, two-update budget, topology diagnostics, and scoring remain
   unchanged.

Additional frozen parameters:

- initial forward/angular velocity standard deviations: `0.08`, `0.12`;
- linear/angular acceleration process standard deviations: `0.35`, `0.50`;
- exercised acceleration: `|a| >= 0.10 m/s²` or
  `|angular a| >= 0.15 rad/s²`.

## Behavioural assay

A fixed 800-step, 0.05-second piecewise velocity command is followed by:

- acceleration clipping at `0.8 m/s²`;
- the same clipping plus a `1.6 m/s³` jerk limit.

## Split and bootstrap

- Development: canonical Dataset 1.
- Held-out: canonical Dataset 7 archive
  `483b37724cfb8d95f71e8b3b7db55a21d30bf86311a71d2b3611071d94db9eb9`.
- Paired bootstrap: 5,000 resamples over robot/60-second-window pairs.

## Frozen gates

1. M11.1 is `GO`; archive and canonical materialization verify.
2. All five robots contribute at least ten complete held-out windows.
3. Acceleration is exercised on at least 10% of replay cycles.
4. Acceleration-minus-baseline position-RMSE improvement has a paired 95% LCB
   greater than zero.
5. Acceleration outage RMSE is no more than 20% worse than baseline.
6. Mean position NEES is at most 8, mean window P95 NEES at most 30, and 95%
   coverage is at least 0.80.
7. Every output remains finite and at most two landmarks update per bin.
8. Acceleration runtime is no more than 1.5 times baseline plus 0.10 seconds
   per robot.
9. The jerk limiter reduces peak jerk by at least 50%, respects the acceleration
   bound, remains finite, and adds no more than `0.10 m/s` velocity RMSE.

Validity failure yields `M12-INVALID`. Other failure yields `M12-NO-GO`.
All gates passing yields `M12-GO` for further research only. Production and
behavioural integration remain unauthorized.
