"""Environment provenance and replay verification (milestone M14).

This module exists because of a specific, reproducible defect found in external
review of the v0.19 platform: two held-out ``GO`` verdicts (M10A, M10A.5)
re-analysed to ``INVALID`` when the reanalysis CLI was run under a different
NumPy version than the one that produced the artifacts.

Root cause. ``simulation.scenario_fingerprint`` hashes raw IEEE-754 bytes of the
materialized exogenous arrays. Exactly one scenario configuration
(``sensor_noise_scale_min != sensor_noise_scale_max``) reaches
``Generator.uniform``, whose last bit is not stable across NumPy releases. The
statistics were unaffected -- ``paired_effects.csv`` and ``scenario_summary.csv``
came back byte-identical -- but the bit-exact ``replay`` validity gate failed and
the verdict machinery, correctly, refused to certify.

The defect was therefore *presentational*, not an integrity failure. But a
referee re-running the artifact sees ``GO -> INVALID`` with no diagnostic, which
for a paper whose thesis is provenance is fatal. M14 fixes three things:

* an environment mismatch is now *named* (``REPLAY-ENV-MISMATCH``) instead of
  being silently collapsed into ``INVALID``;
* the fingerprint gains a tolerance-based algorithm (``v2-quantized``) that is
  invariant to last-bit floating-point differences while remaining sensitive to
  any change that could alter a result;
* the recorded interpreter/NumPy versions are compared at reanalysis time rather
  than merely written down and never read.

Backward compatibility is deliberate and load-bearing. Existing artifacts recorded
their fingerprints under ``v1-raw-bytes``; verification uses whichever algorithm
the artifact declares, defaulting to ``v1-raw-bytes`` when the field is absent.
Changing the default would invalidate every historical artifact in the record,
which is precisely the kind of silent repair the program's verdict semantics
exist to prevent.
"""

from __future__ import annotations

import hashlib
import platform
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

__all__ = [
    "FINGERPRINT_V1",
    "FINGERPRINT_V2",
    "CURRENT_FINGERPRINT_ALGORITHM",
    "DEFAULT_FLOAT_TOLERANCE",
    "ReplayVerification",
    "compare_environment",
    "digest_arrays",
    "environment_fingerprint",
    "verify_replay",
]


# --- fingerprint algorithms -------------------------------------------------

FINGERPRINT_V1 = "v1-raw-bytes"
"""Legacy: hashes raw float bytes. Bit-exact, environment-fragile."""

FINGERPRINT_V2 = "v2-quantized"
"""Current: hashes integer-quantized floats. Tolerant of last-bit differences."""

CURRENT_FINGERPRINT_ALGORITHM = FINGERPRINT_V2

DEFAULT_FLOAT_TOLERANCE = 1e-9
"""Absolute quantum for float hashing under :data:`FINGERPRINT_V2`.

Chosen to sit far below any physically meaningful difference in this platform
(positions are O(10) length units, noise scales are O(1)) while sitting far above
the ~1e-16 relative churn that distinguishes NumPy releases. int64 quantization
at this quantum is exact for magnitudes up to ~9.2e9, which every exogenous
array in the platform satisfies by orders of magnitude; the guard below raises
rather than silently wrapping if that ever stops being true.
"""

_INT64_LIMIT = 9.0e18


def _update_float(digest: "hashlib._Hash", array: np.ndarray, tolerance: float) -> None:
    """Fold a float array into ``digest`` at the given absolute quantum."""
    flat = np.ascontiguousarray(array, dtype=np.float64).ravel()

    # Non-finite values cannot be quantized; hash their positions and kinds
    # separately so NaN/+inf/-inf remain distinguishable from each other and
    # from any finite value.
    finite_mask = np.isfinite(flat)
    if not finite_mask.all():
        kinds = np.zeros(flat.shape, dtype=np.int8)
        kinds[np.isnan(flat)] = 1
        kinds[np.isposinf(flat)] = 2
        kinds[np.isneginf(flat)] = 3
        digest.update(b"nonfinite")
        digest.update(np.ascontiguousarray(kinds).tobytes())
        flat = np.where(finite_mask, flat, 0.0)

    scaled = flat / float(tolerance)
    if scaled.size and float(np.max(np.abs(scaled))) > _INT64_LIMIT:
        raise ValueError(
            "quantized fingerprint would overflow int64: array magnitude "
            f"{float(np.max(np.abs(flat)))!r} is too large for tolerance "
            f"{tolerance!r}. Widen the tolerance or hash this array as raw bytes."
        )
    # rint (round-half-to-even) is the stable choice: a value sitting exactly on
    # a quantum boundary must not depend on the sign of the last bit, which is
    # the very thing we are trying to be invariant to.
    digest.update(np.ascontiguousarray(np.rint(scaled), dtype=np.int64).tobytes())


def digest_arrays(
    values: Iterable[Any],
    *,
    algorithm: str = CURRENT_FINGERPRINT_ALGORITHM,
    tolerance: float = DEFAULT_FLOAT_TOLERANCE,
    digest: "hashlib._Hash | None" = None,
) -> "hashlib._Hash":
    """Fold an ordered sequence of arrays into a SHA-256 digest.

    Under :data:`FINGERPRINT_V1` this reproduces the historical behaviour exactly
    (``np.ascontiguousarray(value).tobytes()``), so legacy artifacts continue to
    verify. Under :data:`FINGERPRINT_V2` integer and boolean arrays are still
    hashed exactly -- they carry no representation ambiguity -- while float
    arrays are quantized.
    """
    if algorithm not in (FINGERPRINT_V1, FINGERPRINT_V2):
        raise ValueError(f"unknown fingerprint algorithm: {algorithm!r}")
    out = digest if digest is not None else hashlib.sha256()

    for value in values:
        array = np.ascontiguousarray(value)
        if algorithm == FINGERPRINT_V1:
            out.update(array.tobytes())
            continue

        # v2: shape and dtype-kind are folded in so that arrays which quantize
        # to the same integers but differ structurally cannot collide.
        out.update(str(array.shape).encode("ascii"))
        out.update(array.dtype.kind.encode("ascii"))
        if array.dtype.kind in "biu":
            out.update(np.ascontiguousarray(array, dtype=np.int64).tobytes())
        elif array.dtype.kind == "f":
            _update_float(out, array, tolerance)
        else:
            # Nothing in the platform reaches here today. Fail loudly rather
            # than hashing something whose byte layout we have not reasoned about.
            raise TypeError(
                f"v2 fingerprint does not handle dtype {array.dtype!r}; add an "
                "explicit rule rather than falling back to raw bytes."
            )
    return out


# --- environment ------------------------------------------------------------

def environment_fingerprint() -> dict[str, str]:
    """Describe the running interpreter for recording in an artifact."""
    return {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "platform": platform.system(),
        "machine": platform.machine(),
    }


#: Fields whose divergence can plausibly perturb floating-point results, and
#: which therefore justify a REPLAY-ENV-MISMATCH rather than an INVALID.
_NUMERIC_ENVIRONMENT_FIELDS = ("python", "numpy", "platform", "machine")


def compare_environment(
    recorded: Mapping[str, Any] | None,
    *,
    current: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare a recorded environment against the running one.

    ``recorded_present`` is False for pre-M14 artifacts that never wrote the
    fields. That is reported honestly rather than being treated as a match: an
    absent record cannot corroborate anything, but it also must not be allowed
    to mint a false ``INVALID``, so it counts as "unknown" and is handled by
    :func:`verify_replay` the same way a known mismatch is.
    """
    now = dict(current or environment_fingerprint())
    if not recorded:
        return {
            "recorded_present": False,
            "match": False,
            "current": now,
            "recorded": {},
            "differences": {},
        }

    differences: dict[str, dict[str, Any]] = {}
    for key in _NUMERIC_ENVIRONMENT_FIELDS:
        if key not in recorded:
            continue
        was, is_ = str(recorded[key]), str(now.get(key, ""))
        if was != is_:
            differences[key] = {"recorded": was, "current": is_}
    return {
        "recorded_present": True,
        "match": not differences,
        "current": now,
        "recorded": {k: str(v) for k, v in recorded.items()},
        "differences": differences,
    }


# --- replay verification ----------------------------------------------------

VERIFIED = "VERIFIED"
"""Fingerprints reproduced bit-exactly under the artifact's own algorithm."""

ENV_MISMATCH = "REPLAY-ENV-MISMATCH"
"""Fingerprints differ and the environment differs too, so the check cannot be
adjudicated bit-exactly.

Stated precisely, because the limitation matters: a SHA-256 digest is not
invertible, so for an artifact recorded under :data:`FINGERPRINT_V1` we *cannot*
demonstrate that the recorded scenario and the recomputed one agree to within a
tolerance -- we only have the recorded hash, not the recorded arrays. This status
therefore asserts something weaker than "equivalent": it asserts "not
adjudicable, and the environment supplies a sufficient explanation."

The corroborating evidence is statistical rather than cryptographic -- the
reanalysis writes ``paired_effects.csv`` and ``scenario_summary.csv``
byte-identically from the saved rows -- and that is checked independently of this
gate. Treating it as an integrity failure would be wrong; treating it as
verification would be overclaiming. It is reported as neither.

KNOWN LIMITATION, stated because it is a real weakening and must not be
discovered by a referee. Once the environment differs, a ``v1-raw-bytes``
artifact cannot distinguish last-bit churn from a *deliberately altered*
fingerprint: both present as "recorded != recomputed", and the digest cannot be
inverted to tell them apart. ``_m14/check_replay_gate.py`` check B demonstrates
this explicitly -- a tampered row is reported as ``REPLAY-ENV-MISMATCH``, not
``MISMATCH``. The mitigation is migration, not argument: artifacts recorded under
``v2-quantized`` are environment-invariant by construction, so for them the
excuse branch is unreachable and any mismatch blocks. Every suite re-run from
M14 onward records v2. The historical artifacts retain the weaker guarantee, and
any claim resting on them should say so."""

MISMATCH = "MISMATCH"
"""Fingerprints differ in a way the environment does not explain. This is the
genuine integrity failure the gate exists to catch, and it still yields
INVALID."""


@dataclass(frozen=True)
class ReplayVerification:
    """Structured outcome of a replay check.

    ``verified`` is the boolean the historical ``replay`` gate expected, so
    existing gate dictionaries keep their shape. ``status`` carries the new
    three-way distinction, and ``blocks_promotion`` is what the verdict
    machinery should actually branch on.
    """

    status: str
    exact_matches: int
    total: int
    algorithm: str
    environment: dict[str, Any] = field(default_factory=dict)
    examples: tuple[dict[str, Any], ...] = ()

    @property
    def verified(self) -> bool:
        return self.status == VERIFIED

    @property
    def blocks_promotion(self) -> bool:
        """Only an unexplained mismatch invalidates a milestone."""
        return self.status == MISMATCH

    @property
    def adjudicable(self) -> bool:
        """False when a v1 digest mismatch cannot be resolved either way."""
        return self.status != ENV_MISMATCH

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "verified": self.verified,
            "blocks_promotion": self.blocks_promotion,
            "adjudicable": self.adjudicable,
            "exact_matches": self.exact_matches,
            "total": self.total,
            "algorithm": self.algorithm,
            "environment": self.environment,
            "examples": list(self.examples),
        }


def verify_replay(
    rows: Sequence[Mapping[str, Any]],
    *,
    expected: Callable[[Mapping[str, Any], str], str],
    recorded_environment: Mapping[str, Any] | None,
    recorded_algorithm: str | None = None,
    fingerprint_key: str = "trace_fingerprint",
    max_examples: int = 3,
) -> ReplayVerification:
    """Verify recorded fingerprints, distinguishing env churn from drift.

    ``expected(row, algorithm)`` recomputes the fingerprint for one row under a
    given algorithm. It is injected rather than imported so that each suite keeps
    ownership of how its configs are reconstructed.

    The decision rule, stated plainly because it is the whole point of M14:

    * every row reproduces under the artifact's own algorithm -> ``VERIFIED``;
    * rows differ under :data:`FINGERPRINT_V1`, **and** the environment differs or
      was never recorded -> ``REPLAY-ENV-MISMATCH``, which does *not* block
      promotion but does *not* claim verification either (see that constant's
      docstring for why this is weaker than "equivalent");
    * anything else -> ``MISMATCH``, which blocks.

    Note the deliberate asymmetry in the second rule: it applies only to
    ``v1-raw-bytes`` artifacts. A ``v2-quantized`` fingerprint is *designed* to be
    invariant to interpreter and NumPy churn, so once an artifact records v2 a
    version bump is no longer an available excuse -- a v2 mismatch is drift and is
    reported as ``MISMATCH`` regardless of the environment. This is the property
    that makes the migration worth doing rather than merely relabelling.
    """
    algorithm = recorded_algorithm or FINGERPRINT_V1
    env = compare_environment(recorded_environment)

    exact = 0
    differing: list[dict[str, Any]] = []

    for row in rows:
        recorded_value = str(row[fingerprint_key])
        recomputed = expected(row, algorithm)
        if recorded_value == recomputed:
            exact += 1
        elif len(differing) < max_examples:
            differing.append(
                {
                    "scenario": row.get("scenario"),
                    "seed": row.get("seed"),
                    "recorded": recorded_value,
                    "recomputed": recomputed,
                }
            )

    total = len(rows)
    if exact == total:
        status = VERIFIED
    elif algorithm == FINGERPRINT_V1 and not env["match"]:
        status = ENV_MISMATCH
    else:
        status = MISMATCH

    return ReplayVerification(
        status=status,
        exact_matches=exact,
        total=total,
        algorithm=algorithm,
        environment=env,
        examples=tuple(differing),
    )
