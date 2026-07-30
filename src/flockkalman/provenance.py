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
    "artifact_hash",
    "compare_environment",
    "digest_arrays",
    "environment_fingerprint",
    "frozen_source_record",
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

SCHEMA_DRIFT = "REPLAY-CONFIG-SCHEMA-DRIFT"
"""Fingerprints differ **only** because ExperimentConfig gained fields.

This is a *positive* adjudication and is strictly stronger than
:data:`ENV_MISMATCH`. The config dict is folded into the digest as a JSON header,
so a single added dataclass field changes every fingerprint in an artifact while
leaving the exogenous arrays untouched. That is why M9A shows 0/800 exact matches
where M10A shows 7740/8250: M9A predates 29 added fields, M10A predates none.

Crucially this is *provable*, not asserted. Re-hashing with the config dict
exactly as recorded -- rather than as ExperimentConfig would serialise it today --
reproduces the recorded digest if and only if every array is bit-identical. So
this status means "the scenario is verified; only its representation grew", and
the arrays have been checked rather than excused. It does not block promotion."""

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
    schema_drift_matches: int
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
        """False only when a v1 digest mismatch cannot be resolved either way.

        SCHEMA_DRIFT *is* adjudicable: the arrays were re-checked against the
        recorded config payload and found identical.
        """
        return self.status != ENV_MISMATCH

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "verified": self.verified,
            "blocks_promotion": self.blocks_promotion,
            "adjudicable": self.adjudicable,
            "exact_matches": self.exact_matches,
            "schema_drift_matches": self.schema_drift_matches,
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
    schema_expected: Callable[[Mapping[str, Any], str], str] | None = None,
    fingerprint_key: str = "trace_fingerprint",
    max_examples: int = 3,
) -> ReplayVerification:
    """Verify recorded fingerprints, distinguishing env churn from drift.

    ``expected(row, algorithm)`` recomputes the fingerprint for one row under a
    given algorithm. It is injected rather than imported so that each suite keeps
    ownership of how its configs are reconstructed.

    The decision rule, stated plainly because it is the whole point of M14:

    ``schema_expected(row, algorithm)``, when supplied, recomputes the fingerprint
    using the config dict **exactly as recorded** instead of as ExperimentConfig
    would serialise it today. It is the probe that separates schema growth from
    genuine drift; see :data:`SCHEMA_DRIFT`.

    The decision rule, in priority order, because the whole point of M14 is that
    these three causes stop being collapsed into one another:

    * every row reproduces under the artifact's own algorithm -> ``VERIFIED``;
    * every remaining row reproduces once the *recorded* config header is used
      -> ``REPLAY-CONFIG-SCHEMA-DRIFT``. Positively adjudicated: arrays identical,
      representation grew. Does not block;
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
    schema_drift = 0
    differing: list[dict[str, Any]] = []

    for row in rows:
        recorded_value = str(row[fingerprint_key])
        recomputed = expected(row, algorithm)
        if recorded_value == recomputed:
            exact += 1
            continue
        # Second chance: re-hash using the config dict exactly as recorded. A
        # match proves every exogenous array is bit-identical and the only
        # difference was the serialised config header.
        drifted = None
        if schema_expected is not None:
            try:
                drifted = schema_expected(row, algorithm)
            except Exception:  # noqa: BLE001 -- a failed probe must not mask the result
                drifted = None
        if drifted is not None and recorded_value == drifted:
            schema_drift += 1
            continue
        if len(differing) < max_examples:
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
    elif schema_drift and exact + schema_drift == total:
        status = SCHEMA_DRIFT
    elif algorithm == FINGERPRINT_V1 and not env["match"]:
        status = ENV_MISMATCH
    else:
        status = MISMATCH

    return ReplayVerification(
        status=status,
        exact_matches=exact,
        schema_drift_matches=schema_drift,
        total=total,
        algorithm=algorithm,
        environment=env,
        examples=tuple(differing),
    )


# --- frozen source records --------------------------------------------------

def artifact_hash(paths: "Sequence[Any]") -> str:
    """Hash an ordered set of files as ``name || contents`` per file.

    Identical semantics to the ``_artifact_hash`` helper duplicated across the
    suite modules, so digests recorded by either implementation are comparable.
    Centralised here because M14 needs it in suites that never had it.
    """
    digest = hashlib.sha256()
    for path in paths:
        from pathlib import Path as _Path

        p = _Path(path)
        digest.update(p.name.encode("utf-8"))
        digest.update(p.read_bytes())
    return digest.hexdigest()


def frozen_source_record(
    paths: "Sequence[Any]",
    *,
    project_root: Any = None,
) -> dict[str, Any]:
    """Describe a frozen source set: the digest **and** the file list.

    The second half is the point. Before M14 the digest was recorded but the list
    of files behind it lived only in the suite module that computed it, so
    verifying a historical artifact required reading the code that produced it --
    and if that code was later edited, working out what the digest had covered
    became guesswork. Recording the list makes an artifact self-describing.

    ``verify_legacy_certification.py`` exists precisely because the pre-M14
    artifacts lack this field and their file lists had to be reconstructed by
    hand from the source.
    """
    from pathlib import Path as _Path

    resolved = [_Path(p) for p in paths]
    root = _Path(project_root) if project_root is not None else None

    def label(p: "_Path") -> str:
        if root is not None:
            try:
                return str(p.relative_to(root))
            except ValueError:
                pass
        return p.name

    return {
        "sha256": artifact_hash(resolved),
        "files": [label(p) for p in resolved],
        "algorithm": "sha256(name||bytes) per file, in listed order",
    }


def replay_verdict_suffix(replay: ReplayVerification) -> str | None:
    """The verdict suffix a non-bit-exact but non-blocking replay should carry.

    Returns ``None`` when the replay verified exactly, otherwise the status
    itself, so a verdict reads ``M9A6-REPLAY-CONFIG-SCHEMA-DRIFT`` rather than a
    generic label that hides which of the three causes actually applied.

    A caller must apply this *after* checking substantive gates: a provenance
    caveat is strictly weaker news than a substantive NO-GO and must never
    displace it in the verdict string.
    """
    return None if replay.verified else replay.status


def upstream_replay_acceptable(decision: Mapping[str, Any]) -> bool:
    """Whether an upstream milestone's replay state permits building on it.

    Downstream suites verify their frozen upstream by, among other things,
    requiring that its ``replay`` gate passed. After M14 that boolean is False
    whenever the replay was merely non-bit-exact -- environment churn or config
    schema growth -- neither of which is an integrity failure. Requiring the raw
    boolean would therefore break every downstream chain the moment a referee
    reanalysed an upstream artifact on their own machine, which is the exact class
    of spurious failure M14 exists to remove.

    Prefers the structured ``replay_verification.blocks_promotion`` and falls back
    to the legacy boolean for artifacts written before M14.
    """
    verification = decision.get("replay_verification")
    if isinstance(verification, Mapping) and "blocks_promotion" in verification:
        return not bool(verification["blocks_promotion"])
    gates = decision.get("gates")
    if isinstance(gates, Mapping) and "replay" in gates:
        return bool(gates["replay"])
    return bool(decision.get("trace_replay_verified"))


REPLAY_VERDICT_SUFFIXES = (ENV_MISMATCH, SCHEMA_DRIFT)
"""Suffixes a verdict may carry purely as a provenance qualifier."""


def base_verdict(verdict: str) -> str:
    """Strip a trailing replay-provenance qualifier from a verdict string.

    ``"M10A-REPLAY-ENV-MISMATCH"`` -> ``"M10A-GO"``? No: deliberately NOT that.
    It returns ``"M10A"`` plus nothing, because the qualifier *replaced* the
    outcome token rather than being appended to it. Callers should therefore use
    :func:`verdict_accepted`, which compares on the milestone prefix, rather than
    trying to reconstruct the original outcome -- which is unknowable from the
    string alone and must not be guessed.
    """
    for suffix in REPLAY_VERDICT_SUFFIXES:
        marker = f"-{suffix}"
        if verdict.endswith(marker):
            return verdict[: -len(marker)]
    return verdict


def verdict_accepted(verdict: str, accepted: "Iterable[str]") -> bool:
    """Whether ``verdict`` satisfies ``accepted``, tolerating a provenance suffix.

    A verdict qualified by a non-blocking replay status (environment churn or
    config schema growth) is treated as satisfying the accepted set, because those
    statuses are explicitly not integrity failures. A ``MISMATCH`` never produces
    such a suffix -- it produces ``INVALID`` -- so this cannot launder a real
    failure into an accepted one.

    The comparison is on the milestone prefix: ``"M10A-REPLAY-ENV-MISMATCH"``
    satisfies ``{"M10A-GO"}`` because both share the ``M10A`` prefix and the
    qualifier is known-benign. Substantive outcomes such as ``M10A-NO-GO`` carry no
    qualifier and so are compared exactly, as before.
    """
    accepted = set(accepted)
    if verdict in accepted:
        return True
    stripped = base_verdict(verdict)
    if stripped == verdict:
        return False  # no benign qualifier was present; exact match was required
    return any(item.startswith(f"{stripped}-") for item in accepted)


# --- upstream source verification -------------------------------------------

UPSTREAM_VERIFIED = "UPSTREAM-VERIFIED"
UPSTREAM_HISTORICAL = "UPSTREAM-SOURCE-DRIFT-HISTORICALLY-VERIFIED"
UPSTREAM_DRIFT = "UPSTREAM-SOURCE-DRIFT"


def verify_upstream_source(
    recorded_sha256: str | None,
    files: "Sequence[Any]",
    *,
    reference_commit: str | None = None,
    repo_root: Any = None,
) -> dict[str, Any]:
    """Verify a frozen upstream source set, tolerating infrastructure drift.

    The problem this solves is the mirror image of the replay-gate one, and it
    bites for the same reason. M14 had to edit modules that sit inside *other*
    milestones' frozen sets (``simulation.py``, ``config.py``, and the suite
    modules themselves). A plain byte comparison against the working tree
    therefore reports drift for every downstream milestone, and three held-out
    artifacts re-analyse to INVALID -- swapping one spurious INVALID for another,
    which would defeat the point of M14.

    So the check gets a second chance, exactly as the replay gate did: if the
    current tree disagrees, recompute the digest from ``reference_commit`` in git
    history. A match there proves the recorded certification was valid against the
    tree that produced it, and the disagreement is attributable to later edits
    rather than to an algorithm change. That is reported as
    ``UPSTREAM-SOURCE-DRIFT-HISTORICALLY-VERIFIED`` and does not block.

    Only an upstream digest that matches *neither* the working tree nor history is
    ``UPSTREAM-SOURCE-DRIFT``, which blocks. Git being unavailable also blocks --
    an unverifiable upstream must never pass by default.
    """
    from pathlib import Path as _Path

    resolved = [_Path(f) for f in files]
    current = artifact_hash(resolved)
    out: dict[str, Any] = {
        "recorded_sha256": recorded_sha256,
        "current_sha256": current,
        "files": [p.name for p in resolved],
        "reference_commit": reference_commit,
    }
    if not recorded_sha256:
        out["status"] = UPSTREAM_DRIFT
        out["blocks_promotion"] = True
        out["detail"] = "upstream artifact records no candidate source hash"
        return out
    if current == recorded_sha256:
        out["status"] = UPSTREAM_VERIFIED
        out["blocks_promotion"] = False
        return out
    if not reference_commit:
        out["status"] = UPSTREAM_DRIFT
        out["blocks_promotion"] = True
        out["detail"] = "current tree differs and no reference commit was supplied"
        return out

    import subprocess

    root = _Path(repo_root) if repo_root is not None else resolved[0].parents[2]
    digest = hashlib.sha256()
    try:
        for path in resolved:
            rel = path.relative_to(root)
            proc = subprocess.run(
                ["git", "-C", str(root), "show", f"{reference_commit}:{rel.as_posix()}"],
                capture_output=True,
                check=True,
            )
            digest.update(path.name.encode("utf-8"))
            digest.update(proc.stdout)
    except Exception as exc:  # noqa: BLE001 - unverifiable must not silently pass
        out["status"] = UPSTREAM_DRIFT
        out["blocks_promotion"] = True
        out["detail"] = f"could not read reference commit: {exc}"
        return out

    out["historical_sha256"] = digest.hexdigest()
    if digest.hexdigest() == recorded_sha256:
        out["status"] = UPSTREAM_HISTORICAL
        out["blocks_promotion"] = False
        out["detail"] = (
            "recorded certification verified against history; the working tree "
            "differs due to later edits to shared modules"
        )
    else:
        out["status"] = UPSTREAM_DRIFT
        out["blocks_promotion"] = True
        out["detail"] = "digest matches neither the working tree nor history"
    return out


PRE_M14_TAG = "pre-m14"
PRE_M14_COMMIT_HINT = "568fbfa"
PRE_M14_COMMIT = PRE_M14_COMMIT_HINT  # backwards-compatible alias

def resolve_pre_m14_commit(repo_root: Any) -> str | None:
    """Resolve the commit holding the tree that produced every pre-M14 artifact.

    Resolution order, most to least durable:

    1. the ``pre-m14`` tag, which survives rebases and re-clones;
    2. :data:`PRE_M14_COMMIT_HINT`, the abbreviated hash as first created;
    3. the repository's root commit, which is what the pre-M14 import *is*.

    A bare hash was the first implementation and it is fragile: squashing on first
    push, or any history rewrite, silently breaks historical verification while
    every check still reports success right up to the moment it starts blocking.
    The tag is the intended handle; the root-commit fallback means the mechanism
    keeps working even if nobody creates it.
    """
    import subprocess
    from pathlib import Path as _Path

    root = str(_Path(repo_root))

    def rev_parse(ref: str) -> str | None:
        proc = subprocess.run(
            ["git", "-C", root, "rev-parse", "--verify", "--quiet", ref],
            capture_output=True, text=True,
        )
        out = proc.stdout.strip()
        return out or None

    for ref in (f"refs/tags/{PRE_M14_TAG}", PRE_M14_COMMIT_HINT):
        resolved = rev_parse(ref)
        if resolved:
            return resolved

    proc = subprocess.run(
        ["git", "-C", root, "rev-list", "--max-parents=0", "HEAD"],
        capture_output=True, text=True,
    )
    roots = [line for line in proc.stdout.split() if line]
    return roots[-1] if roots else None
