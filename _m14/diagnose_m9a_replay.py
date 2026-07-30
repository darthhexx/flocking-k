"""Why do M9A / M9A.6 show ZERO exact fingerprint matches?

M10A showed 7740/8250 -- a subset, consistent with last-bit churn in one scenario.
M9A shows 0/800. A total miss is the signature of a *systematic* difference, and
if it is code drift rather than environment churn then REPLAY-ENV-MISMATCH is the
wrong status and M14.3 would be masking a real failure.
"""

import json
import sys
from dataclasses import fields
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from flockkalman.config import ExperimentConfig
from flockkalman.provenance import FINGERPRINT_V1
from flockkalman.simulation import scenario_fingerprint

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    for name in ("milestone9a_heldout", "milestone9a6_heldout", "milestone10a_heldout"):
        suite = json.loads((ROOT / "results" / name / "suite_config.json").read_text())
        configs = suite["scenario_configs"]
        first = next(iter(configs))
        recorded_keys = set(configs[first].keys())
        current_keys = {f.name for f in fields(ExperimentConfig)}

        missing = sorted(current_keys - recorded_keys)
        extra = sorted(recorded_keys - current_keys)

        print(f"══ {name} ══")
        print(f"  recorded config keys: {len(recorded_keys)}   "
              f"current dataclass fields: {len(current_keys)}")
        print(f"  fields ADDED to ExperimentConfig since this run: {len(missing)}")
        if missing:
            print(f"    {missing[:12]}{' ...' if len(missing) > 12 else ''}")
        print(f"  fields REMOVED since this run: {len(extra)}")
        if extra:
            print(f"    {extra}")

        # Does the reconstructed config's to_dict() match what was recorded?
        cfg = ExperimentConfig(**configs[first])
        rebuilt = cfg.to_dict()
        differing = {
            k: (configs[first].get(k, "<absent>"), rebuilt.get(k, "<absent>"))
            for k in set(rebuilt) | recorded_keys
            if configs[first].get(k, "<absent>") != rebuilt.get(k, "<absent>")
        }
        print(f"  to_dict() differs from recorded on {len(differing)} keys")
        for k, (was, now) in list(differing.items())[:8]:
            print(f"    {k}: recorded={was!r} rebuilt={now!r}")

        # The config dict is folded into the digest as JSON, so ANY added field
        # changes every fingerprint. Confirm that is the mechanism.
        print(f"  => config JSON identical: {json.dumps(configs[first], sort_keys=True) == json.dumps(rebuilt, sort_keys=True)}")
        print()


if __name__ == "__main__":
    main()
