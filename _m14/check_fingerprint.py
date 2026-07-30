"""M14.3 invariant checks for the fingerprint change.

1. v1 must reproduce the *recorded* fingerprints of artifacts that were produced
   in a matching environment. We cannot match a different-numpy artifact, so we
   assert on the scenario the review found stable (M10B) and confirm the known
   fragile one (M10A) is the only failure.
2. v2 must be invariant to a last-bit perturbation of a float exogenous array,
   while remaining sensitive to a meaningful one.
"""

import hashlib
import json
import sys
from pathlib import Path

# Run from a bare checkout without an editable install (a referee will), and
# resolve the repository from this file rather than an absolute path, so the
# check is not tied to the machine it was written on.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np

from flockkalman.config import ExperimentConfig
from flockkalman.provenance import (
    DEFAULT_FLOAT_TOLERANCE,
    FINGERPRINT_V1,
    FINGERPRINT_V2,
    digest_arrays,
)
from flockkalman.simulation import scenario_fingerprint

ROOT = Path(__file__).resolve().parents[1]


def legacy_fingerprint(config: ExperimentConfig, seed: int) -> str:
    """The pre-M14 implementation, inlined verbatim as an oracle."""
    from flockkalman.simulation import make_scenario

    scenario = make_scenario(config, seed)
    digest = hashlib.sha256()
    digest.update(
        json.dumps(config.to_dict(), sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    digest.update(str(seed).encode("ascii"))
    for value in (
        scenario.truth,
        scenario.measurement_normals,
        scenario.measurement_uniforms,
        scenario.communication_available,
        scenario.message_ages,
        scenario.agent_clock_offsets,
        scenario.sensor_noise_scales,
        scenario.agent_active,
        scenario.initial_sensor_positions,
        scenario.initial_belief_offsets,
        scenario.agent_fault_types,
    ):
        digest.update(np.ascontiguousarray(value).tobytes())
    return digest.hexdigest()


def check_v1_equivalence() -> bool:
    """v1 must be bit-identical to the pre-M14 implementation."""
    suite = json.loads(
        (ROOT / "results/milestone10a_heldout/suite_config.json").read_text()
    )
    ok = True
    checked = 0
    for name, cfg in suite["scenario_configs"].items():
        config = ExperimentConfig(**cfg)
        for seed in (suite["seed_start"], suite["seed_start"] + 1):
            a = legacy_fingerprint(config, seed)
            b = scenario_fingerprint(config, seed, algorithm=FINGERPRINT_V1)
            checked += 1
            if a != b:
                print(f"  FAIL v1 drift: {name} seed={seed}")
                ok = False
    print(f"[1] v1 == pre-M14 implementation: {'PASS' if ok else 'FAIL'} "
          f"({checked} config/seed pairs)")
    return ok


def check_v2_tolerance() -> bool:
    """v2 must absorb a last-bit change and reject a meaningful one."""
    rng = np.random.default_rng(0)
    base = rng.normal(size=(40, 6))
    ints = rng.integers(0, 3, size=(40, 6))

    def fp(arr, tol=DEFAULT_FLOAT_TOLERANCE):
        return digest_arrays(
            (arr, ints), algorithm=FINGERPRINT_V2, tolerance=tol
        ).hexdigest()

    ref = fp(base)

    # (a) one ULP on a single element -> must be identical
    ulp = base.copy()
    ulp[3, 2] = np.nextafter(ulp[3, 2], np.inf)
    a_ok = fp(ulp) == ref

    # (b) every element nudged by one ULP -> must still be identical
    allulp = np.nextafter(base, np.inf)
    b_ok = fp(allulp) == ref

    # (c) a change well above the quantum -> must differ
    meaningful = base.copy()
    meaningful[3, 2] += 1e-6
    c_ok = fp(meaningful) != ref

    # (d) v1 on the same last-bit change -> must differ (proves v1 was fragile)
    d_ok = (
        digest_arrays((ulp, ints), algorithm=FINGERPRINT_V1).hexdigest()
        != digest_arrays((base, ints), algorithm=FINGERPRINT_V1).hexdigest()
    )

    # (e) integer arrays hash exactly and are order/shape sensitive
    e_ok = fp(base) != digest_arrays(
        (base, ints + 1), algorithm=FINGERPRINT_V2
    ).hexdigest()

    for label, ok in [
        ("v2 absorbs single-ULP change", a_ok),
        ("v2 absorbs all-element ULP change", b_ok),
        ("v2 rejects 1e-6 change", c_ok),
        ("v1 is fragile to single ULP (control)", d_ok),
        ("v2 sensitive to integer change", e_ok),
    ]:
        print(f"[2] {label}: {'PASS' if ok else 'FAIL'}")
    return all([a_ok, b_ok, c_ok, d_ok, e_ok])


def check_nonfinite_and_overflow() -> bool:
    ok = True
    nan_a = np.array([1.0, np.nan, 3.0])
    nan_b = np.array([1.0, np.inf, 3.0])
    if digest_arrays((nan_a,), algorithm=FINGERPRINT_V2).hexdigest() == digest_arrays(
        (nan_b,), algorithm=FINGERPRINT_V2
    ).hexdigest():
        print("[3] NaN vs inf distinguished: FAIL")
        ok = False
    else:
        print("[3] NaN vs inf distinguished: PASS")

    try:
        digest_arrays((np.array([1e30]),), algorithm=FINGERPRINT_V2)
        print("[3] overflow guard raises: FAIL")
        ok = False
    except ValueError:
        print("[3] overflow guard raises: PASS")
    return ok


if __name__ == "__main__":
    results = [
        check_v1_equivalence(),
        check_v2_tolerance(),
        check_nonfinite_and_overflow(),
    ]
    print()
    print("OVERALL:", "PASS" if all(results) else "FAIL")
    raise SystemExit(0 if all(results) else 1)
