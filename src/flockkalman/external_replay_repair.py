"""Deterministic, auditable timestamp canonicalization for MR.CLAM logs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np


_STATIC_FILES = {
    "Barcodes.dat": 2,
    "Landmark_Groundtruth.dat": 5,
}
_STREAM_COLUMNS = {
    "Groundtruth": 4,
    "Odometry": 3,
    "Measurement": 4,
}


@dataclass(frozen=True, slots=True)
class CanonicalizationRecord:
    filename: str
    rows: int
    timestamp_inversions: int
    duplicate_timestamps: int
    reordered_rows: int
    maximum_backward_jump: float
    source_sha256: str
    canonical_sha256: str


@dataclass(frozen=True, slots=True)
class CanonicalizationManifest:
    source_root: str
    canonical_root: str
    records: tuple[CanonicalizationRecord, ...]
    input_rows: int
    output_rows: int
    total_timestamp_inversions: int
    total_reordered_rows: int
    deterministic_rule: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_numeric(path: Path, columns: int) -> np.ndarray:
    if not path.is_file():
        raise ValueError(f"missing MRCLAM file: {path.name}")
    values = np.loadtxt(path, comments="#", dtype=float)
    if values.ndim == 1:
        values = values[np.newaxis, :]
    if (
        values.ndim != 2
        or values.shape[1] != columns
        or len(values) == 0
        or not np.all(np.isfinite(values))
    ):
        raise ValueError(f"malformed MRCLAM file: {path.name}")
    return values


def _required_files() -> tuple[tuple[str, int, bool], ...]:
    files: list[tuple[str, int, bool]] = [
        (name, columns, False) for name, columns in _STATIC_FILES.items()
    ]
    for robot in range(1, 6):
        files.extend(
            (
                (
                    f"Robot{robot}_{stream}.dat",
                    columns,
                    True,
                )
                for stream, columns in _STREAM_COLUMNS.items()
            )
        )
    return tuple(files)


def canonicalize_mrclam_dataset(
    source_root: str | Path,
    canonical_root: str | Path,
    *,
    replace: bool = False,
) -> CanonicalizationManifest:
    """Stable-sort stream rows by timestamp without dropping or altering rows."""
    source = Path(source_root)
    target = Path(canonical_root)
    if target.exists():
        if not replace:
            raise FileExistsError(f"canonical target already exists: {target}")
        shutil.rmtree(target)
    target.mkdir(parents=True)
    records: list[CanonicalizationRecord] = []
    for filename, columns, timed in _required_files():
        source_path = source / filename
        values = _load_numeric(source_path, columns)
        inversions = (
            int(np.sum(np.diff(values[:, 0]) < 0.0)) if timed else 0
        )
        duplicates = (
            int(np.sum(np.diff(np.sort(values[:, 0])) == 0.0))
            if timed
            else 0
        )
        maximum_backward = (
            max(0.0, float(-np.min(np.diff(values[:, 0]))))
            if timed and len(values) > 1
            else 0.0
        )
        order = (
            np.argsort(values[:, 0], kind="stable")
            if timed
            else np.arange(len(values))
        )
        reordered = int(np.sum(order != np.arange(len(values))))
        canonical = values[order]
        target_path = target / filename
        np.savetxt(target_path, canonical, fmt="%.17g")
        records.append(
            CanonicalizationRecord(
                filename=filename,
                rows=len(values),
                timestamp_inversions=inversions,
                duplicate_timestamps=duplicates,
                reordered_rows=reordered,
                maximum_backward_jump=maximum_backward,
                source_sha256=_sha256(source_path),
                canonical_sha256=_sha256(target_path),
            )
        )
    manifest = CanonicalizationManifest(
        source_root=str(source.resolve()),
        canonical_root=str(target.resolve()),
        records=tuple(records),
        input_rows=sum(item.rows for item in records),
        output_rows=sum(item.rows for item in records),
        total_timestamp_inversions=sum(
            item.timestamp_inversions for item in records
        ),
        total_reordered_rows=sum(item.reordered_rows for item in records),
        deterministic_rule=(
            "stable ascending timestamp sort per Groundtruth, Odometry, and "
            "Measurement file; preserve equal-time input order; no row drop"
        ),
    )
    (target / "canonicalization_manifest.json").write_text(
        json.dumps(
            {
                **asdict(manifest),
                "records": [asdict(item) for item in manifest.records],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest


def verify_canonicalization(
    manifest: CanonicalizationManifest,
) -> bool:
    """Verify row preservation, hashes, and timestamp order in derived files."""
    if manifest.input_rows != manifest.output_rows:
        return False
    target = Path(manifest.canonical_root)
    expected = {name: (columns, timed) for name, columns, timed in _required_files()}
    for record in manifest.records:
        columns, timed = expected[record.filename]
        path = target / record.filename
        if _sha256(path) != record.canonical_sha256:
            return False
        values = _load_numeric(path, columns)
        if len(values) != record.rows:
            return False
        if timed and np.any(np.diff(values[:, 0]) < 0.0):
            return False
    return True
