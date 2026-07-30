"""M11.1 powered evaluation of the timestamp canonicalization repair."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import tempfile

import numpy as np

from .external_replay import (
    M11_ARMS,
    ReplayConfig,
    ReplayTrial,
    load_mrclam_dataset,
    replay_fingerprint,
    run_mrclam_replay,
)
from .external_replay_repair import (
    CanonicalizationManifest,
    canonicalize_mrclam_dataset,
    verify_canonicalization,
)
from .external_replay_suite import (
    _decision,
    _file_sha256,
    _malformed_rejected,
    _paired_effects,
    _summaries,
    _window_rows,
    _write_report,
)
from .suite import _write_csv


M11_1_ARCHIVE_HASHES = {
    "development": "013714987dc0f797853689a80146da1fee50478ad884491d0eeac5f6357602d4",
    "heldout": "45295fec82cd1f60cd08ed661f7eacf4a08ae0d950a38f72feaf7fe0ab86368d",
}
M11_1_REPLAY_CONFIG = ReplayConfig(
    process_position_std=0.30,
    process_heading_std=0.15,
)


def _artifact_hash(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _canonical_fingerprint(manifest: CanonicalizationManifest) -> str:
    digest = hashlib.sha256()
    for record in manifest.records:
        digest.update(record.filename.encode("utf-8"))
        digest.update(record.canonical_sha256.encode("ascii"))
    return digest.hexdigest()


def _normalization_decision(
    core: dict[str, object],
    manifest: CanonicalizationManifest,
    *,
    phase: str,
    archive_verified: bool,
    deterministic: bool,
) -> dict[str, object]:
    normalization_gates = {
        "repair_archive": archive_verified,
        "canonicalization_deterministic": deterministic,
        "all_rows_preserved": (
            manifest.input_rows == manifest.output_rows
            and manifest.input_rows > 0
        ),
        "canonical_hashes_and_order": verify_canonicalization(manifest),
    }
    gates = {
        **normalization_gates,
        **{
            f"m11_{name}": bool(value)
            for name, value in dict(core["gates"]).items()
        },
    }
    validity_names = {
        "repair_archive",
        "canonicalization_deterministic",
        "all_rows_preserved",
        "canonical_hashes_and_order",
        "m11_archive_and_replay",
        "m11_parser_and_malformed_rejection",
        "m11_truth_isolation",
        "m11_window_power",
    }
    if not all(gates[name] for name in validity_names):
        verdict = "M11.1-INVALID"
    elif not all(gates.values()):
        verdict = (
            "M11.1-DEVELOPMENT-FAIL"
            if phase == "development"
            else "M11.1-NO-GO"
        )
    else:
        verdict = (
            "M11.1-DEVELOPMENT-PASS"
            if phase == "development"
            else "M11.1-GO"
        )
    return {
        **core,
        "verdict": verdict,
        "gates": gates,
        "canonicalization": {
            "input_rows": manifest.input_rows,
            "output_rows": manifest.output_rows,
            "timestamp_inversions": manifest.total_timestamp_inversions,
            "reordered_rows": manifest.total_reordered_rows,
            "fingerprint": _canonical_fingerprint(manifest),
        },
        "acceleration_research_authorized": verdict == "M11.1-GO",
        "production_authorized": False,
    }


def _write_repair_report(
    path: Path,
    decision: dict[str, object],
    summaries: list[dict[str, object]],
) -> None:
    temporary = path.with_suffix(".m11.tmp")
    _write_report(temporary, decision, summaries)
    original = temporary.read_text(encoding="utf-8")
    temporary.unlink()
    normalization = dict(decision["canonicalization"])
    prefix = "\n".join(
        [
            "# M11.1 canonicalized external replay report",
            "",
            f"**Verdict: `{decision['verdict']}`**",
            "",
            "The original M11 Dataset 9 rejection remains `M11-INVALID`.",
            "",
            "## Canonicalization",
            "",
            f"- Rows retained: `{normalization['output_rows']}` / "
            f"`{normalization['input_rows']}`",
            f"- Timestamp inversions: `{normalization['timestamp_inversions']}`",
            f"- Reordered rows: `{normalization['reordered_rows']}`",
            f"- Fingerprint: `{normalization['fingerprint']}`",
            "",
        ]
    )
    body = original.split("## Gates", maxsplit=1)[-1]
    path.write_text(prefix + "\n## Gates" + body, encoding="utf-8")


def run_external_replay_repair_suite(
    source_root: str | Path,
    canonical_root: str | Path,
    archive_path: str | Path,
    output_directory: str | Path,
    *,
    phase: str,
    bootstrap_samples: int = 5000,
    config: ReplayConfig | None = None,
) -> dict[str, object]:
    if phase not in {"development", "heldout"}:
        raise ValueError("M11.1 phase must be development or heldout")
    if bootstrap_samples < 100:
        raise ValueError("M11.1 needs at least 100 bootstrap samples")
    replay_config = config or M11_1_REPLAY_CONFIG
    replay_config.validate()
    canonical_path = Path(canonical_root)
    manifest = canonicalize_mrclam_dataset(
        source_root,
        canonical_path,
        replace=canonical_path.exists(),
    )
    with tempfile.TemporaryDirectory(prefix="m11_1_repeat_") as temp:
        repeated = canonicalize_mrclam_dataset(
            source_root,
            Path(temp) / "canonical",
        )
        deterministic = (
            _canonical_fingerprint(manifest)
            == _canonical_fingerprint(repeated)
            and verify_canonicalization(repeated)
        )
    dataset = load_mrclam_dataset(canonical_path)
    fingerprint = replay_fingerprint(dataset, replay_config)
    archive = Path(archive_path)
    archive_hash = _file_sha256(archive)
    archive_verified = archive_hash == M11_1_ARCHIVE_HASHES[phase]
    trials: list[ReplayTrial] = []
    for arm in M11_ARMS:
        trials.extend(run_mrclam_replay(dataset, replay_config, arm))
    window_rows = _window_rows(trials, replay_config)
    summaries = _summaries(window_rows)
    effects = _paired_effects(window_rows, bootstrap_samples)
    core = _decision(
        window_rows,
        summaries,
        effects,
        phase=phase,
        dataset=dataset,
        archive_verified=archive_verified,
        deterministic=(
            deterministic
            and fingerprint == replay_fingerprint(dataset, replay_config)
        ),
        malformed_rejected=_malformed_rejected(canonical_path),
    )
    decision = _normalization_decision(
        core,
        manifest,
        phase=phase,
        archive_verified=archive_verified,
        deterministic=deterministic,
    )
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(
        output / "per_step_metrics.csv",
        [asdict(step) for trial in trials for step in trial.steps],
    )
    _write_csv(output / "window_summary.csv", window_rows)
    _write_csv(output / "arm_summary.csv", summaries)
    _write_csv(output / "paired_effects.csv", effects)
    project_root = Path(__file__).resolve().parents[2]
    source = project_root / "src/flockkalman"
    suite = {
        "phase": phase,
        "source_root": str(Path(source_root).resolve()),
        "canonical_root": str(canonical_path.resolve()),
        "archive_path": str(archive.resolve()),
        "archive_sha256": archive_hash,
        "bootstrap_samples": bootstrap_samples,
        "replay_config": asdict(replay_config),
        "replay_fingerprint": fingerprint,
        "canonical_fingerprint": _canonical_fingerprint(manifest),
        "protocol_sha256": _artifact_hash(
            (project_root / "M11_1_PROTOCOL.md",)
        ),
        "candidate_source_sha256": _artifact_hash(
            (
                source / "external_replay_repair.py",
                source / "external_replay_repair_suite.py",
            )
        ),
        "frozen_m11_source_sha256": _artifact_hash(
            (
                source / "external_replay.py",
                source / "external_replay_suite.py",
            )
        ),
        "platform_version": "0.18.0",
        "python": platform.python_version(),
        "numpy": np.__version__,
    }
    (output / "suite_config.json").write_text(
        json.dumps(suite, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_repair_report(
        output / "milestone11_1_report.md",
        decision,
        summaries,
    )
    return decision
