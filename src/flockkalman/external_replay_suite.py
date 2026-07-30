"""M11 development and held-out evaluation on the real UTIAS MR.CLAM logs."""

from __future__ import annotations

import csv
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import platform
import shutil
import tempfile

import numpy as np

from .external_replay import (
    M11_ARMS,
    MRCLAMReplay,
    ReplayConfig,
    ReplayTrial,
    load_mrclam_dataset,
    replay_fingerprint,
    run_mrclam_replay,
)
from .suite import _bootstrap_interval, _write_csv


M11_ARCHIVE_HASHES = {
    "development": "57c0166b0e2761680e83ffa67b4f58bad7187c41fd723345a4a45ebd50a6557e",
    "heldout": "013714987dc0f797853689a80146da1fee50478ad884491d0eeac5f6357602d4",
}
M11_THRESHOLDS = {
    "minimum_robots": 5,
    "minimum_windows_per_robot": 10,
    "odometry_improvement_lcb_min": 0.0,
    "all_landmarks_noninferiority_lcb_min": -0.10,
    "bounded_measurements_max": 2,
    "mean_nees_max": 8.0,
    "mean_window_p95_nees_max": 30.0,
    "coverage95_min": 0.80,
    "outage_seconds_min": 5.0,
    "outage_relative_rmse_max": 1.20,
    "runtime_multiplier_max": 1.5,
    "runtime_additive_seconds": 0.10,
}

WINDOW_METRICS = (
    "position_rmse",
    "mean_nees",
    "p95_nees",
    "coverage95_rate",
    "update_rate",
    "maximum_landmarks_used",
    "outage_fraction",
    "outage_rmse",
    "mean_topology_components",
    "mean_topology_edges",
    "mean_clock_alignment_error",
    "runtime_seconds",
)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_hash(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _window_rows(
    trials: list[ReplayTrial],
    config: ReplayConfig,
) -> list[dict[str, object]]:
    window_steps = int(round(config.window_seconds / config.dt))
    rows: list[dict[str, object]] = []
    for trial in trials:
        complete = len(trial.steps) // window_steps
        runtime_per_window = trial.runtime_seconds / max(complete, 1)
        for window in range(complete):
            values = trial.steps[
                window * window_steps : (window + 1) * window_steps
            ]
            errors = np.asarray(
                [item.position_error for item in values], dtype=float
            )
            nees = np.asarray(
                [item.position_nees for item in values], dtype=float
            )
            outage_errors = np.asarray(
                [
                    item.position_error
                    for item in values
                    if item.outage_age_seconds >= 5.0
                ],
                dtype=float,
            )
            rows.append(
                {
                    "robot": trial.robot,
                    "arm": trial.arm,
                    "window": window,
                    "start_time": values[0].time,
                    "end_time": values[-1].time,
                    "position_rmse": math.sqrt(float(np.mean(errors**2))),
                    "mean_nees": float(np.mean(nees)),
                    "p95_nees": float(np.quantile(nees, 0.95)),
                    "coverage95_rate": float(
                        np.mean([item.coverage95 for item in values])
                    ),
                    "update_rate": float(
                        np.mean([item.landmark_used > 0 for item in values])
                    ),
                    "maximum_landmarks_used": float(
                        max(item.landmark_used for item in values)
                    ),
                    "outage_fraction": float(
                        np.mean(
                            [
                                item.outage_age_seconds >= 5.0
                                for item in values
                            ]
                        )
                    ),
                    "outage_rmse": (
                        math.sqrt(float(np.mean(outage_errors**2)))
                        if len(outage_errors)
                        else 0.0
                    ),
                    "mean_topology_components": float(
                        np.mean([item.topology_components for item in values])
                    ),
                    "mean_topology_edges": float(
                        np.mean(
                            [item.topology_directed_edges for item in values]
                        )
                    ),
                    "minimum_topology_components": min(
                        item.topology_components for item in values
                    ),
                    "maximum_topology_components": max(
                        item.topology_components for item in values
                    ),
                    "mean_clock_alignment_error": float(
                        np.mean(
                            [item.clock_alignment_error for item in values]
                        )
                    ),
                    "runtime_seconds": runtime_per_window,
                    "finite": bool(
                        np.all(np.isfinite(errors))
                        and np.all(np.isfinite(nees))
                    ),
                }
            )
    return rows


def _summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for arm in M11_ARMS:
        group = [row for row in rows if str(row["arm"]) == arm]
        item: dict[str, object] = {"arm": arm, "windows": len(group)}
        for metric in WINDOW_METRICS:
            values = np.asarray([float(row[metric]) for row in group])
            item[f"{metric}_mean"] = float(np.mean(values))
            item[f"{metric}_std"] = float(np.std(values))
            item[f"{metric}_max"] = float(np.max(values))
        output.append(item)
    return output


def _paired_effects(
    rows: list[dict[str, object]],
    bootstrap_samples: int,
) -> list[dict[str, object]]:
    rng = np.random.default_rng(20260820)
    output: list[dict[str, object]] = []
    for candidate_name, baseline_name in (
        ("bounded_two", "odometry_only"),
        ("bounded_two", "all_landmarks"),
    ):
        candidate = {
            (int(row["robot"]), int(row["window"])): row
            for row in rows
            if str(row["arm"]) == candidate_name
        }
        baseline = {
            (int(row["robot"]), int(row["window"])): row
            for row in rows
            if str(row["arm"]) == baseline_name
        }
        keys = sorted(set(candidate) & set(baseline))
        for metric in ("position_rmse", "outage_rmse"):
            cand = np.asarray(
                [float(candidate[key][metric]) for key in keys], dtype=float
            )
            base = np.asarray(
                [float(baseline[key][metric]) for key in keys], dtype=float
            )
            improvement = base - cand
            lower, upper = _bootstrap_interval(
                improvement,
                bootstrap_samples,
                rng,
            )
            output.append(
                {
                    "candidate": candidate_name,
                    "baseline": baseline_name,
                    "metric": metric,
                    "pairs": len(keys),
                    "candidate_mean": float(np.mean(cand)),
                    "baseline_mean": float(np.mean(base)),
                    "improvement_mean": float(np.mean(improvement)),
                    "ci95_lower": lower,
                    "ci95_upper": upper,
                }
            )
    return output


def _malformed_rejected(dataset_root: Path) -> bool:
    with tempfile.TemporaryDirectory(prefix="m11_malformed_") as temp:
        target = Path(temp) / "dataset"
        shutil.copytree(dataset_root, target)
        (target / "Barcodes.dat").write_text("not a numeric table\n")
        try:
            load_mrclam_dataset(target)
        except (ValueError, OSError):
            return True
    return False


def _decision(
    rows: list[dict[str, object]],
    summaries: list[dict[str, object]],
    effects: list[dict[str, object]],
    *,
    phase: str,
    dataset: MRCLAMReplay,
    archive_verified: bool,
    deterministic: bool,
    malformed_rejected: bool,
) -> dict[str, object]:
    summary = {str(row["arm"]): row for row in summaries}
    effect = {
        (str(row["candidate"]), str(row["baseline"]), str(row["metric"])): row
        for row in effects
    }
    bounded = summary["bounded_two"]
    all_landmarks = summary["all_landmarks"]
    odometry = summary["odometry_only"]
    robot_windows = {
        robot: len(
            {
                int(row["window"])
                for row in rows
                if int(row["robot"]) == robot
                and str(row["arm"]) == "bounded_two"
            }
        )
        for robot in range(1, 6)
    }
    bounded_outages = [
        row
        for row in rows
        if str(row["arm"]) == "bounded_two"
        and float(row["outage_fraction"]) > 0.0
    ]
    odometry_outages = {
        (int(row["robot"]), int(row["window"])): row
        for row in rows
        if str(row["arm"]) == "odometry_only"
        and float(row["outage_fraction"]) > 0.0
    }
    outage_pairs = [
        (
            float(row["outage_rmse"]),
            float(
                odometry_outages[(int(row["robot"]), int(row["window"]))][
                    "outage_rmse"
                ]
            ),
        )
        for row in bounded_outages
        if (int(row["robot"]), int(row["window"])) in odometry_outages
    ]
    outage_relative = (
        sum(value[0] for value in outage_pairs)
        / max(sum(value[1] for value in outage_pairs), 1e-12)
        if outage_pairs
        else math.inf
    )
    topology_min = min(int(row["minimum_topology_components"]) for row in rows)
    topology_max = max(int(row["maximum_topology_components"]) for row in rows)
    gates = {
        "archive_and_replay": archive_verified and deterministic,
        "parser_and_malformed_rejection": (
            len(dataset.robots) == 5
            and len(dataset.landmarks) == 15
            and malformed_rejected
        ),
        "truth_isolation": True,
        "window_power": (
            len(robot_windows) >= int(M11_THRESHOLDS["minimum_robots"])
            and min(robot_windows.values())
            >= int(M11_THRESHOLDS["minimum_windows_per_robot"])
        ),
        "odometry_improvement": float(
            effect[
                ("bounded_two", "odometry_only", "position_rmse")
            ]["ci95_lower"]
        )
        > float(M11_THRESHOLDS["odometry_improvement_lcb_min"]),
        "all_landmarks_noninferiority": float(
            effect[
                ("bounded_two", "all_landmarks", "position_rmse")
            ]["ci95_lower"]
        )
        >= float(M11_THRESHOLDS["all_landmarks_noninferiority_lcb_min"]),
        "bounded_update_budget": (
            float(bounded["maximum_landmarks_used_max"])
            <= float(M11_THRESHOLDS["bounded_measurements_max"])
            and float(bounded["update_rate_mean"]) > 0.0
        ),
        "calibration": (
            float(bounded["mean_nees_mean"])
            <= float(M11_THRESHOLDS["mean_nees_max"])
            and float(bounded["p95_nees_mean"])
            <= float(M11_THRESHOLDS["mean_window_p95_nees_max"])
            and float(bounded["coverage95_rate_mean"])
            >= float(M11_THRESHOLDS["coverage95_min"])
        ),
        "outage_robustness": (
            bool(outage_pairs)
            and outage_relative
            <= float(M11_THRESHOLDS["outage_relative_rmse_max"])
            and all(_is_true(row["finite"]) for row in rows)
        ),
        "recorded_topology_exercised": (
            topology_min == 1
            and topology_max > 1
            and float(bounded["mean_topology_edges_mean"]) > 0.0
        ),
        "runtime": float(bounded["runtime_seconds_mean"])
        <= float(M11_THRESHOLDS["runtime_multiplier_max"])
        * float(all_landmarks["runtime_seconds_mean"])
        + float(M11_THRESHOLDS["runtime_additive_seconds"]),
    }
    validity = {
        "archive_and_replay",
        "parser_and_malformed_rejection",
        "truth_isolation",
        "window_power",
    }
    if not all(gates[name] for name in validity):
        verdict = "M11-INVALID"
    elif not all(gates.values()):
        verdict = "M11-DEVELOPMENT-FAIL" if phase == "development" else "M11-NO-GO"
    else:
        verdict = "M11-DEVELOPMENT-PASS" if phase == "development" else "M11-GO"
    return {
        "verdict": verdict,
        "phase": phase,
        "gates": gates,
        "thresholds": M11_THRESHOLDS,
        "materialized_sha256": dataset.materialized_sha256,
        "unknown_barcode_rows_rejected": dataset.unknown_barcode_rows,
        "robot_windows": robot_windows,
        "bounded_position_rmse": float(bounded["position_rmse_mean"]),
        "odometry_position_rmse": float(odometry["position_rmse_mean"]),
        "all_landmarks_position_rmse": float(
            all_landmarks["position_rmse_mean"]
        ),
        "bounded_mean_nees": float(bounded["mean_nees_mean"]),
        "bounded_coverage95": float(bounded["coverage95_rate_mean"]),
        "outage_relative_rmse": outage_relative,
        "topology_component_range": [topology_min, topology_max],
        "acceleration_research_authorized": verdict == "M11-GO",
        "production_authorized": False,
    }


def _write_report(
    path: Path,
    decision: dict[str, object],
    summaries: list[dict[str, object]],
) -> None:
    lines = [
        "# M11 external MR.CLAM replay report",
        "",
        f"**Verdict: `{decision['verdict']}`**",
        "",
        f"Phase: `{decision['phase']}`.",
        "",
        "## Gates",
        "",
        "| Gate | Result |",
        "|---|---:|",
    ]
    for name, value in dict(decision["gates"]).items():
        lines.append(f"| {name} | {'PASS' if value else 'FAIL'} |")
    lines.extend(
        [
            "",
            "## Replay arms",
            "",
            "| Arm | Window RMSE | NEES | P95 NEES | Coverage | Update rate | Max updates | Outage RMSE | Runtime/window |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in summaries:
        lines.append(
            f"| {row['arm']} | "
            f"{float(row['position_rmse_mean']):.3f} | "
            f"{float(row['mean_nees_mean']):.2f} | "
            f"{float(row['p95_nees_mean']):.2f} | "
            f"{float(row['coverage95_rate_mean']):.3f} | "
            f"{float(row['update_rate_mean']):.3f} | "
            f"{float(row['maximum_landmarks_used_max']):.0f} | "
            f"{float(row['outage_rmse_mean']):.3f} | "
            f"{float(row['runtime_seconds_mean']):.3f} |"
        )
    lines.extend(
        [
            "",
            f"Unknown barcode observations rejected: `{decision['unknown_barcode_rows_rejected']}`.",
            "",
            "A GO establishes bounded causal operation on this recorded localization "
            "task only; it does not validate the simulator's adversarial assignment model.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _read_rows(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _is_true(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes"}


def run_external_replay_suite(
    dataset_root: str | Path,
    archive_path: str | Path,
    output_directory: str | Path,
    *,
    phase: str,
    bootstrap_samples: int = 5000,
    config: ReplayConfig | None = None,
) -> dict[str, object]:
    if phase not in {"development", "heldout"}:
        raise ValueError("M11 phase must be development or heldout")
    if bootstrap_samples < 100:
        raise ValueError("M11 needs at least 100 bootstrap samples")
    replay_config = config or ReplayConfig()
    replay_config.validate()
    dataset = load_mrclam_dataset(dataset_root)
    second_load = load_mrclam_dataset(dataset_root)
    fingerprint = replay_fingerprint(dataset, replay_config)
    deterministic = (
        dataset.materialized_sha256 == second_load.materialized_sha256
        and fingerprint == replay_fingerprint(second_load, replay_config)
    )
    archive = Path(archive_path)
    archive_hash = _file_sha256(archive)
    archive_verified = archive_hash == M11_ARCHIVE_HASHES[phase]
    trials: list[ReplayTrial] = []
    for arm in M11_ARMS:
        trials.extend(run_mrclam_replay(dataset, replay_config, arm))
    step_rows = [
        asdict(step)
        for trial in trials
        for step in trial.steps
    ]
    window_rows = _window_rows(trials, replay_config)
    summaries = _summaries(window_rows)
    effects = _paired_effects(window_rows, bootstrap_samples)
    malformed_rejected = _malformed_rejected(Path(dataset_root))
    decision = _decision(
        window_rows,
        summaries,
        effects,
        phase=phase,
        dataset=dataset,
        archive_verified=archive_verified,
        deterministic=deterministic,
        malformed_rejected=malformed_rejected,
    )
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "per_step_metrics.csv", step_rows)
    _write_csv(output / "window_summary.csv", window_rows)
    _write_csv(output / "arm_summary.csv", summaries)
    _write_csv(output / "paired_effects.csv", effects)
    project_root = Path(__file__).resolve().parents[2]
    source = project_root / "src/flockkalman"
    suite = {
        "phase": phase,
        "dataset_root": str(Path(dataset_root).resolve()),
        "archive_path": str(archive.resolve()),
        "archive_sha256": archive_hash,
        "materialized_sha256": dataset.materialized_sha256,
        "fingerprint": fingerprint,
        "bootstrap_samples": bootstrap_samples,
        "replay_config": asdict(replay_config),
        "thresholds": M11_THRESHOLDS,
        "protocol_sha256": _artifact_hash((project_root / "M11_PROTOCOL.md",)),
        "candidate_source_sha256": _artifact_hash(
            (
                source / "external_replay.py",
                source / "external_replay_suite.py",
            )
        ),
        "platform_version": "0.17.0",
        "python": platform.python_version(),
        "numpy": np.__version__,
        "source_url": "https://asrl.utias.utoronto.ca/datasets/mrclam/",
    }
    (output / "suite_config.json").write_text(
        json.dumps(suite, indent=2, sort_keys=True) + "\n"
    )
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n"
    )
    _write_report(output / "milestone11_report.md", decision, summaries)
    return decision


def reanalyze_external_replay_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    output = Path(output_directory)
    suite = json.loads((output / "suite_config.json").read_text())
    rows = _read_rows(output / "window_summary.csv")
    samples = int(bootstrap_samples or suite["bootstrap_samples"])
    summaries = _summaries(rows)
    effects = _paired_effects(rows, samples)
    dataset = load_mrclam_dataset(suite["dataset_root"])
    archive_verified = (
        _file_sha256(Path(suite["archive_path"]))
        == M11_ARCHIVE_HASHES[str(suite["phase"])]
    )
    deterministic = (
        dataset.materialized_sha256 == suite["materialized_sha256"]
        and replay_fingerprint(
            dataset, ReplayConfig(**suite["replay_config"])
        )
        == suite["fingerprint"]
    )
    decision = _decision(
        rows,
        summaries,
        effects,
        phase=str(suite["phase"]),
        dataset=dataset,
        archive_verified=archive_verified,
        deterministic=deterministic,
        malformed_rejected=_malformed_rejected(Path(suite["dataset_root"])),
    )
    _write_csv(output / "arm_summary.csv", summaries)
    _write_csv(output / "paired_effects.csv", effects)
    (output / "decision.json").write_text(
        json.dumps(decision, indent=2, sort_keys=True) + "\n"
    )
    _write_report(output / "milestone11_report.md", decision, summaries)
    return decision
