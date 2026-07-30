# M11 held-out external replay report

**Verdict: `M11-INVALID`**

The verified official Dataset 9 archive was opened once after the M11 source
and protocol were frozen. The strict parser stopped before estimation because
the first two rows of four robot odometry files are in descending timestamp
order by approximately 0.10 seconds.

No held-out estimates, metrics, or performance comparisons were produced. The
frozen M11 result remains invalid; it was not retroactively repaired or
relabelled. M11.1 transparently treats Dataset 9 as development data, adds a
row-preserving stable timestamp canonicalizer, and reserves Dataset 6 as a new
untouched hold-out.
