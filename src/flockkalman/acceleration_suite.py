"""M12 powered estimator-acceleration and behavioural-jerk evaluation."""

from __future__ import annotations

import csv
from dataclasses import asdict, replace
import hashlib
import json
import math
from pathlib import Path
import platform

import numpy as np

from .acceleration_replay import (
    M12_ACCELERATION_ARM,
    M12_ARMS,
    M12_BASELINE_ARM,
    AccelerationConfig,
    run_acceleration_replay,
    run_jerk_limiter_assay,
)
from .external_replay import (
    ReplayStep,
    ReplayTrial,
    load_mrclam_dataset,
    replay_fingerprint,
    run_mrclam_replay,
)
from .external_replay_repair import (
    canonicalize_mrclam_dataset,
    verify_canonicalization,
)
from .external_replay_suite import (
    WINDOW_METRICS,
    _file_sha256,
    _window_rows,
)
from .suite import _bootstrap_interval, _write_csv


M12_ARCHIVE_HASHES = {
    "development": "57c0166b0e2761680e83ffa67b4f58bad7187c41fd723345a4a45ebd50a6557e",
    "heldout": "483b37724cfb8d95f71e8b3b7db55a21d30bf86311a71d2b3611071d94db9eb9",
}
M12_THRESHOLDS = {
    "minimum_robots": 5,
    "minimum_windows_per_robot": 10,
    "acceleration_exercised_rate_min": 0.10,
    "rmse_improvement_lcb_min": 0.0,
    "outage_relative_rmse_max": 1.20,
    "mean_nees_max": 8.0,
    "mean_window_p95_nees_max": 30.0,
    "coverage95_min": 0.80,
    "maximum_landmarks_used": 2,
    "runtime_multiplier_max": 1.5,
    "runtime_additive_seconds": 0.10,
    "jerk_reduction_min": 0.50,
    "jerk_velocity_rmse_additive_max": 0.10,
    "acceleration_limit": 0.8,
}


def _artifact_hash(paths: tuple[Path, ...]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _baseline_trials(dataset, config: AccelerationConfig) -> list[ReplayTrial]:
    original = run_mrclam_replay(dataset, config.replay, "bounded_two")
    output: list[ReplayTrial] = []
    for trial in original:
        output.append(
            ReplayTrial(
                robot=trial.robot,
                arm=M12_BASELINE_ARM,
                steps=tuple(
                    replace(step, arm=M12_BASELINE_ARM)
                    for step in trial.steps
                ),
                runtime_seconds=trial.runtime_seconds,
            )
        )
    return output


def _summaries(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for arm in M12_ARMS:
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
    rng = np.random.default_rng(20260830)
    candidate = {
        (int(row["robot"]), int(row["window"])): row
        for row in rows
        if str(row["arm"]) == M12_ACCELERATION_ARM
    }
    baseline = {
        (int(row["robot"]), int(row["window"])): row
        for row in rows
        if str(row["arm"]) == M12_BASELINE_ARM
    }
    keys = sorted(set(candidate) & set(baseline))
    output: list[dict[str, object]] = []
    for metric in ("position_rmse", "outage_rmse"):
        candidate_values = np.asarray(
            [float(candidate[key][metric]) for key in keys],
            dtype=float,
        )
        baseline_values = np.asarray(
            [float(baseline[key][metric]) for key in keys],
            dtype=float,
        )
        improvement = baseline_values - candidate_values
        lower, upper = _bootstrap_interval(
            improvement,
            bootstrap_samples,
            rng,
        )
        output.append(
            {
                "candidate": M12_ACCELERATION_ARM,
                "baseline": M12_BASELINE_ARM,
                "metric": metric,
                "pairs": len(keys),
                "candidate_mean": float(np.mean(candidate_values)),
                "baseline_mean": float(np.mean(baseline_values)),
                "improvement_mean": float(np.mean(improvement)),
                "ci95_lower": lower,
                "ci95_upper": upper,
            }
        )
    return output


def _decision(
    rows: list[dict[str, object]],
    summaries: list[dict[str, object]],
    effects: list[dict[str, object]],
    acceleration_diagnostics: list[dict[str, object]],
    jerk_rows: list[dict[str, object]],
    *,
    phase: str,
    archive_verified: bool,
    canonical_verified: bool,
    upstream_go: bool,
) -> dict[str, object]:
    summary = {str(row["arm"]): row for row in summaries}
    effect = {
        str(row["metric"]): row
        for row in effects
    }
    baseline = summary[M12_BASELINE_ARM]
    acceleration = summary[M12_ACCELERATION_ARM]
    robot_windows = {
        robot: len(
            {
                int(row["window"])
                for row in rows
                if int(row["robot"]) == robot
                and str(row["arm"]) == M12_ACCELERATION_ARM
            }
        )
        for robot in range(1, 6)
    }
    baseline_outage = {
        (int(row["robot"]), int(row["window"])): float(row["outage_rmse"])
        for row in rows
        if str(row["arm"]) == M12_BASELINE_ARM
        and float(row["outage_fraction"]) > 0.0
    }
    acceleration_outage = {
        (int(row["robot"]), int(row["window"])): float(row["outage_rmse"])
        for row in rows
        if str(row["arm"]) == M12_ACCELERATION_ARM
        and float(row["outage_fraction"]) > 0.0
    }
    outage_keys = sorted(set(baseline_outage) & set(acceleration_outage))
    outage_relative = (
        sum(acceleration_outage[key] for key in outage_keys)
        / max(sum(baseline_outage[key] for key in outage_keys), 1e-12)
        if outage_keys
        else math.inf
    )
    exercised_rate = float(
        np.mean(
            [
                float(row["acceleration_exercised_rate"])
                for row in acceleration_diagnostics
            ]
        )
    )
    jerk = {str(row["controller"]): row for row in jerk_rows}
    clipped = jerk["acceleration_clipped"]
    limited = jerk["jerk_limited"]
    jerk_reduction = 1.0 - float(limited["peak_jerk"]) / max(
        float(clipped["peak_jerk"]),
        1e-12,
    )
    gates = {
        "upstream_m11_1_go": upstream_go if phase == "heldout" else True,
        "archive_and_canonicalization": (
            archive_verified and canonical_verified
        ),
        "window_power": (
            len(robot_windows) >= int(M12_THRESHOLDS["minimum_robots"])
            and min(robot_windows.values())
            >= int(M12_THRESHOLDS["minimum_windows_per_robot"])
        ),
        "acceleration_exercised": exercised_rate
        >= float(M12_THRESHOLDS["acceleration_exercised_rate_min"]),
        "rmse_improvement": float(effect["position_rmse"]["ci95_lower"])
        > float(M12_THRESHOLDS["rmse_improvement_lcb_min"]),
        "outage_nonregression": (
            bool(outage_keys)
            and outage_relative
            <= float(M12_THRESHOLDS["outage_relative_rmse_max"])
        ),
        "calibration": (
            float(acceleration["mean_nees_mean"])
            <= float(M12_THRESHOLDS["mean_nees_max"])
            and float(acceleration["p95_nees_mean"])
            <= float(M12_THRESHOLDS["mean_window_p95_nees_max"])
            and float(acceleration["coverage95_rate_mean"])
            >= float(M12_THRESHOLDS["coverage95_min"])
        ),
        "finite_and_bounded": (
            all(str(row["finite"]).lower() in {"true", "1"} for row in rows)
            and float(acceleration["maximum_landmarks_used_max"])
            <= float(M12_THRESHOLDS["maximum_landmarks_used"])
        ),
        "runtime": float(acceleration["runtime_seconds_mean"])
        <= float(M12_THRESHOLDS["runtime_multiplier_max"])
        * float(baseline["runtime_seconds_mean"])
        + float(M12_THRESHOLDS["runtime_additive_seconds"]),
        "behavioural_jerk": (
            jerk_reduction >= float(M12_THRESHOLDS["jerk_reduction_min"])
            and float(limited["peak_acceleration"])
            <= float(M12_THRESHOLDS["acceleration_limit"]) + 1e-12
            and bool(limited["finite"])
            and float(limited["velocity_rmse"])
            - float(clipped["velocity_rmse"])
            <= float(
                M12_THRESHOLDS["jerk_velocity_rmse_additive_max"]
            )
        ),
    }
    validity = {
        "upstream_m11_1_go",
        "archive_and_canonicalization",
        "window_power",
    }
    if not all(gates[name] for name in validity):
        verdict = "M12-INVALID"
    elif not all(gates.values()):
        verdict = (
            "M12-DEVELOPMENT-FAIL"
            if phase == "development"
            else "M12-NO-GO"
        )
    else:
        verdict = (
            "M12-DEVELOPMENT-PASS"
            if phase == "development"
            else "M12-GO"
        )
    return {
        "verdict": verdict,
        "phase": phase,
        "gates": gates,
        "thresholds": M12_THRESHOLDS,
        "robot_windows": robot_windows,
        "baseline_position_rmse": float(baseline["position_rmse_mean"]),
        "acceleration_position_rmse": float(
            acceleration["position_rmse_mean"]
        ),
        "rmse_improvement_mean": float(
            effect["position_rmse"]["improvement_mean"]
        ),
        "rmse_improvement_ci95": [
            float(effect["position_rmse"]["ci95_lower"]),
            float(effect["position_rmse"]["ci95_upper"]),
        ],
        "acceleration_mean_nees": float(acceleration["mean_nees_mean"]),
        "acceleration_coverage95": float(
            acceleration["coverage95_rate_mean"]
        ),
        "acceleration_exercised_rate": exercised_rate,
        "outage_relative_rmse": outage_relative,
        "jerk_reduction": jerk_reduction,
        "production_authorized": False,
        "behavioural_integration_authorized": False,
    }


def _write_report(
    path: Path,
    decision: dict[str, object],
    summaries: list[dict[str, object]],
) -> None:
    lines = [
        "# M12 acceleration report",
        "",
        f"**Verdict: `{decision['verdict']}`**",
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
            "## Estimator arms",
            "",
            "| Arm | Window RMSE | NEES | Coverage | Runtime/window |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in summaries:
        lines.append(
            f"| {row['arm']} | "
            f"{float(row['position_rmse_mean']):.3f} | "
            f"{float(row['mean_nees_mean']):.2f} | "
            f"{float(row['coverage95_rate_mean']):.3f} | "
            f"{float(row['runtime_seconds_mean']):.3f} |"
        )
    lines.extend(
        [
            "",
            f"Acceleration exercise rate: `{decision['acceleration_exercised_rate']:.3f}`.",
            f"Jerk reduction: `{decision['jerk_reduction']:.3f}`.",
            "",
            "Replay evidence concerns estimator propagation only. The behavioural "
            "assay is isolated and does not authorize closed-loop integration.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _upstream_go(path: Path) -> bool:
    if not path.is_file():
        return False
    return json.loads(path.read_text()).get("verdict") == "M11.1-GO"


def run_acceleration_suite(
    source_root: str | Path,
    canonical_root: str | Path,
    archive_path: str | Path,
    output_directory: str | Path,
    *,
    phase: str,
    bootstrap_samples: int = 5000,
    config: AccelerationConfig | None = None,
    upstream_decision: str | Path = "results/milestone11_1_heldout/decision.json",
) -> dict[str, object]:
    if phase not in {"development", "heldout"}:
        raise ValueError("M12 phase must be development or heldout")
    if bootstrap_samples < 100:
        raise ValueError("M12 needs at least 100 bootstrap samples")
    acceleration_config = config or AccelerationConfig()
    acceleration_config.validate()
    canonical_path = Path(canonical_root)
    manifest = canonicalize_mrclam_dataset(
        source_root,
        canonical_path,
        replace=canonical_path.exists(),
    )
    canonical_verified = verify_canonicalization(manifest)
    dataset = load_mrclam_dataset(canonical_path)
    archive = Path(archive_path)
    archive_hash = _file_sha256(archive)
    archive_verified = archive_hash == M12_ARCHIVE_HASHES[phase]
    baseline = _baseline_trials(dataset, acceleration_config)
    acceleration_wrappers = run_acceleration_replay(
        dataset,
        acceleration_config,
    )
    acceleration = [item.trial for item in acceleration_wrappers]
    trials = baseline + acceleration
    rows = _window_rows(trials, acceleration_config.replay)
    summaries = _summaries(rows)
    effects = _paired_effects(rows, bootstrap_samples)
    acceleration_diagnostics = [
        {
            "robot": item.trial.robot,
            "mean_absolute_acceleration": item.mean_absolute_acceleration,
            "p95_absolute_acceleration": item.p95_absolute_acceleration,
            "mean_absolute_angular_acceleration": (
                item.mean_absolute_angular_acceleration
            ),
            "acceleration_exercised_rate": (
                item.acceleration_exercised_rate
            ),
        }
        for item in acceleration_wrappers
    ]
    jerk_rows = [asdict(item) for item in run_jerk_limiter_assay()]
    decision = _decision(
        rows,
        summaries,
        effects,
        acceleration_diagnostics,
        jerk_rows,
        phase=phase,
        archive_verified=archive_verified,
        canonical_verified=canonical_verified,
        upstream_go=_upstream_go(Path(upstream_decision)),
    )
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(
        output / "per_step_metrics.csv",
        [asdict(step) for trial in trials for step in trial.steps],
    )
    _write_csv(output / "window_summary.csv", rows)
    _write_csv(output / "arm_summary.csv", summaries)
    _write_csv(output / "paired_effects.csv", effects)
    _write_csv(
        output / "acceleration_diagnostics.csv",
        acceleration_diagnostics,
    )
    _write_csv(output / "jerk_assay.csv", jerk_rows)
    project_root = Path(__file__).resolve().parents[2]
    source = project_root / "src/flockkalman"
    suite = {
        "phase": phase,
        "source_root": str(Path(source_root).resolve()),
        "canonical_root": str(canonical_path.resolve()),
        "archive_path": str(archive.resolve()),
        "archive_sha256": archive_hash,
        "materialized_sha256": dataset.materialized_sha256,
        "replay_fingerprint": replay_fingerprint(
            dataset,
            acceleration_config.replay,
        ),
        "bootstrap_samples": bootstrap_samples,
        "acceleration_config": {
            **asdict(acceleration_config),
            "replay": asdict(acceleration_config.replay),
        },
        "protocol_sha256": _artifact_hash((project_root / "M12_PROTOCOL.md",)),
        "candidate_source_sha256": _artifact_hash(
            (
                source / "acceleration_replay.py",
                source / "acceleration_suite.py",
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
    _write_report(output / "milestone12_report.md", decision, summaries)
    return decision
