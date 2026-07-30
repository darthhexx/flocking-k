"""M9A.5 nested-reference diagnostic for dynamic-topology decision loss."""

from __future__ import annotations

import csv
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import platform
from time import perf_counter

import numpy as np

from .config import ExperimentConfig
from .oracle_floor import run_oracle_floor_trial
from .simulation import scenario_fingerprint
from .suite import _bootstrap_interval, _write_csv
from .topology_suite import M9A_SCENARIOS, _fit_timing


M9A5_REFERENCES = (
    "frozen_m9a_loss",
    "observer_loss",
    "global_loss",
    "m9a_hypothesis_floor_loss",
)
M9A5_METRICS = (
    "frozen_m9a_loss",
    "frozen_m9a_base_error",
    "m9a_hypothesis_floor_loss",
    "observer_loss",
    "observer_base_error",
    "observer_selection_rate",
    "observer_mixture_rate",
    "observer_defer_rate",
    "observer_wrong_mode_action_rate",
    "observer_mean_mode_count",
    "observer_mean_credible_mode_count",
    "observer_mean_top_mode_probability",
    "observer_mean_confidence",
    "observer_mean_predicted_risk",
    "observer_mean_assignment_entropy",
    "observer_mean_visible_agents",
    "global_loss",
    "global_base_error",
    "global_selection_rate",
    "global_mixture_rate",
    "global_defer_rate",
    "global_wrong_mode_action_rate",
    "global_mean_mode_count",
    "global_mean_credible_mode_count",
    "global_mean_top_mode_probability",
    "global_mean_confidence",
    "global_mean_predicted_risk",
    "global_mean_assignment_entropy",
    "global_mean_visible_agents",
    "current_to_observer_gap",
    "observer_to_global_gap",
    "current_to_global_gap",
    "current_to_hypothesis_floor_gap",
    "runtime_seconds",
)


def _worker(task: tuple[str, dict[str, object], int]) -> dict[str, object]:
    scenario_name, config_data, seed = task
    config = ExperimentConfig(**config_data)
    started = perf_counter()
    summary, _ = run_oracle_floor_trial(config, seed)
    summary["runtime_seconds"] = perf_counter() - started
    summary["scenario"] = scenario_name
    return summary


def _scenario_summary(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(str(row["scenario"]), []).append(row)
    result: list[dict[str, object]] = []
    for scenario, group in grouped.items():
        item: dict[str, object] = {"scenario": scenario, "runs": len(group)}
        for metric in M9A5_METRICS:
            values = np.asarray([float(row[metric]) for row in group], dtype=float)
            item[f"{metric}_mean"] = float(np.mean(values))
            item[f"{metric}_std"] = float(np.std(values))
        result.append(item)
    return result


def _transfer_effects(
    rows: list[dict[str, object]],
    seeds: list[int],
    bootstrap_samples: int,
) -> list[dict[str, object]]:
    indexed = {
        (str(row["scenario"]), int(row["seed"])): row for row in rows
    }
    rng = np.random.default_rng(2026072215)
    effects: list[dict[str, object]] = []
    for reference in M9A5_REFERENCES:
        stable = np.asarray(
            [
                float(indexed[("stable_control", seed)][reference])
                for seed in seeds
            ],
            dtype=float,
        )
        for scenario in M9A_SCENARIOS[1:]:
            dynamic = np.asarray(
                [
                    float(indexed[(scenario.name, seed)][reference])
                    for seed in seeds
                ],
                dtype=float,
            )
            transfer = stable - dynamic
            lower, upper = _bootstrap_interval(transfer, bootstrap_samples, rng)
            effects.append(
                {
                    "scenario": scenario.name,
                    "reference": reference,
                    "pairs": len(seeds),
                    "stable_mean": float(np.mean(stable)),
                    "dynamic_mean": float(np.mean(dynamic)),
                    "transfer_mean": float(np.mean(transfer)),
                    "ci95_lower": lower,
                    "ci95_upper": upper,
                    "passes_original_margin": lower > -0.10,
                }
            )
    return effects


def _gap_effects(
    rows: list[dict[str, object]],
    seeds: list[int],
    bootstrap_samples: int,
) -> list[dict[str, object]]:
    indexed = {
        (str(row["scenario"]), int(row["seed"])): row for row in rows
    }
    comparisons = (
        ("frozen_m9a_loss", "observer_loss", "current_minus_observer"),
        ("observer_loss", "global_loss", "observer_minus_global"),
        ("frozen_m9a_loss", "global_loss", "current_minus_global"),
        (
            "frozen_m9a_loss",
            "m9a_hypothesis_floor_loss",
            "current_minus_hypothesis_floor",
        ),
    )
    rng = np.random.default_rng(2026072216)
    effects: list[dict[str, object]] = []
    for scenario in M9A_SCENARIOS:
        for left, right, comparison in comparisons:
            left_values = np.asarray(
                [float(indexed[(scenario.name, seed)][left]) for seed in seeds]
            )
            right_values = np.asarray(
                [float(indexed[(scenario.name, seed)][right]) for seed in seeds]
            )
            gap = left_values - right_values
            lower, upper = _bootstrap_interval(gap, bootstrap_samples, rng)
            effects.append(
                {
                    "scenario": scenario.name,
                    "comparison": comparison,
                    "pairs": len(seeds),
                    "left_mean": float(np.mean(left_values)),
                    "right_mean": float(np.mean(right_values)),
                    "gap_mean": float(np.mean(gap)),
                    "ci95_lower": lower,
                    "ci95_upper": upper,
                }
            )
    return effects


def _diagnosis(
    transfers: list[dict[str, object]], trace_verified: bool
) -> dict[str, object]:
    lookup = {
        (str(row["scenario"]), str(row["reference"])): row for row in transfers
    }
    scenario_diagnoses: dict[str, str] = {}
    for scenario in M9A_SCENARIOS[1:]:
        passes = {
            reference: bool(
                lookup[(scenario.name, reference)]["passes_original_margin"]
            )
            for reference in M9A5_REFERENCES
        }
        if passes["frozen_m9a_loss"]:
            diagnosis = "CURRENT_POLICY_CLEARS_MARGIN"
        elif passes["observer_loss"]:
            diagnosis = "SAME_INFORMATION_POLICY_OR_REPRESENTATION_HEADROOM"
        elif passes["global_loss"]:
            diagnosis = "OBSERVER_COMPONENT_INFORMATION_LIMIT"
        elif passes["m9a_hypothesis_floor_loss"]:
            diagnosis = "MODEL_REFERENCE_GAP_WITH_FROZEN_REPRESENTATION_HEADROOM"
        else:
            diagnosis = "FROZEN_REPRESENTATION_TRANSFER_LIMIT"
        scenario_diagnoses[scenario.name] = diagnosis

    all_pass = {
        reference: all(
            bool(lookup[(scenario.name, reference)]["passes_original_margin"])
            for scenario in M9A_SCENARIOS[1:]
        )
        for reference in M9A5_REFERENCES
    }
    if not trace_verified:
        conclusion = "INVALID-DIAGNOSTIC"
    elif all_pass["frozen_m9a_loss"]:
        conclusion = "CURRENT-MARGIN-CLEARS"
    elif all_pass["observer_loss"]:
        conclusion = "POLICY-HEADROOM"
    elif all_pass["global_loss"]:
        conclusion = "INFORMATION-LIMITED"
    elif all_pass["m9a_hypothesis_floor_loss"]:
        conclusion = "MIXED-HEADROOM"
    else:
        conclusion = "FROZEN-REPRESENTATION-LIMITED"
    return {
        "diagnostic_conclusion": conclusion,
        "non_promotional": True,
        "original_m9a_verdict_unchanged": True,
        "trace_replay_verified": trace_verified,
        "original_transfer_margin_lcb": -0.10,
        "all_dynamic_scenarios_pass": all_pass,
        "scenario_diagnoses": scenario_diagnoses,
        "reference_semantics": {
            "frozen_m9a_loss": "unchanged operational M9A output",
            "observer_loss": (
                "truth-blind model-informed Bayesian reference using raw observations "
                "inside the observer's delivered weak component"
            ),
            "global_loss": (
                "truth-blind model-informed Bayesian reference using all currently "
                "operational raw observations through an ideal out-of-band collector"
            ),
            "m9a_hypothesis_floor_loss": (
                "truth-using evaluation-only lower bound over the frozen M9A returned set"
            ),
        },
    }


def _verify_trace_manifest(
    scenario_configs: dict[str, dict[str, object]],
    entries: list[dict[str, object]],
) -> bool:
    return all(
        scenario_fingerprint(
            ExperimentConfig(**scenario_configs[str(entry["scenario"])]),
            int(entry["seed"]),
        )
        == entry["fingerprint"]
        for entry in entries
    )


def _write_report(
    path: Path,
    diagnosis: dict[str, object],
    scenario_rows: list[dict[str, object]],
    transfers: list[dict[str, object]],
    gaps: list[dict[str, object]],
    seed_start: int,
    seed_count: int,
) -> None:
    scenario_lookup = {str(row["scenario"]): row for row in scenario_rows}
    transfer_lookup = {
        (str(row["scenario"]), str(row["reference"])): row for row in transfers
    }
    gap_lookup = {
        (str(row["scenario"]), str(row["comparison"])): row for row in gaps
    }
    labels = {
        "frozen_m9a_loss": "M9A",
        "observer_loss": "Observer Bayes",
        "global_loss": "Global Bayes",
        "m9a_hypothesis_floor_loss": "Hindsight set floor",
    }
    lines = [
        "# M9A.5 dynamic-topology loss-floor diagnostic",
        "",
        f"**Diagnostic conclusion: `{diagnosis['diagnostic_conclusion']}`**",
        "",
        "This is a non-promotional diagnostic. It does not alter M9A's frozen parameters, original transfer gate, or `M9A-PARTIAL-GO` verdict.",
        "",
        f"Seeds: `{seed_start}`–`{seed_start + seed_count - 1}` ({seed_count} paired seeds per scenario). Every reference observed the same frozen M9A sensor trajectory.",
        "",
        "## Nested references",
        "",
        "- **Frozen M9A:** the operational output already evaluated in M9A.4.",
        "- **Observer Bayes:** exact assignment marginalization under the declared four-of-eight secondary-mode model, using only raw measurements in the observer's current delivered weak component.",
        "- **Global Bayes:** the same inference and action rule with every currently operational measurement delivered by an ideal out-of-band collector.",
        "- **Hindsight set floor:** the closest frozen M9A hypothesis after truth is revealed. This is a genuine evaluation-only lower bound for that returned set, not an implementable policy.",
        "",
        "Neither Bayesian arm sees target truth, future noise, or seeded fault identities before acting. They know the declared secondary-mode count, offset, and activation schedule. Their RMS-risk action rule is a model-informed reference rather than a proof of global Bayes optimality.",
        "",
        "## Mean decision loss and original-margin transfer",
        "",
        "| Scenario | M9A loss | Observer | Global | Set floor | Observer LCB | Global LCB | Floor LCB | Diagnosis |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    diagnoses = dict(diagnosis["scenario_diagnoses"])
    for scenario in M9A_SCENARIOS:
        row = scenario_lookup[scenario.name]
        if scenario.name == "stable_control":
            observer_lcb = global_lcb = floor_lcb = "—"
            scenario_diagnosis = "REFERENCE"
        else:
            observer_lcb = f"{float(transfer_lookup[(scenario.name, 'observer_loss')]['ci95_lower']):.3f}"
            global_lcb = f"{float(transfer_lookup[(scenario.name, 'global_loss')]['ci95_lower']):.3f}"
            floor_lcb = f"{float(transfer_lookup[(scenario.name, 'm9a_hypothesis_floor_loss')]['ci95_lower']):.3f}"
            scenario_diagnosis = diagnoses[scenario.name]
        lines.append(
            f"| {scenario.name} | {float(row['frozen_m9a_loss_mean']):.3f} | "
            f"{float(row['observer_loss_mean']):.3f} | {float(row['global_loss_mean']):.3f} | "
            f"{float(row['m9a_hypothesis_floor_loss_mean']):.3f} | {observer_lcb} | "
            f"{global_lcb} | {floor_lcb} | `{scenario_diagnosis}` |"
        )
    lines.extend(
        [
            "",
            "The LCB columns are paired 95% bootstrap lower bounds for `stable loss − dynamic loss`; the unchanged M9A criterion passes only above `-0.10`.",
            "",
            "## Decomposition gaps",
            "",
            "Positive gaps mean the reference on the right has lower decision loss.",
            "",
            "| Scenario | M9A − observer | Observer − global | M9A − global | M9A − set floor |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for scenario in M9A_SCENARIOS:
        values = [
            gap_lookup[(scenario.name, comparison)]["gap_mean"]
            for comparison in (
                "current_minus_observer",
                "observer_minus_global",
                "current_minus_global",
                "current_minus_hypothesis_floor",
            )
        ]
        lines.append(
            f"| {scenario.name} | " + " | ".join(f"{float(value):.3f}" for value in values) + " |"
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "Observer-to-global differences isolate the value of ideal cross-component access under one shared inference model. Frozen-M9A-to-observer differences combine production representation, fusion, lifecycle, and action-rule costs while holding physical trajectories and the observer information boundary fixed. The hindsight-set floor tests only whether the frozen returned hypothesis set contains a low-error answer; it cannot prescribe a causal selector.",
            "",
            "The diagnostic may justify a new, prospectively registered oracle-relative protocol. It cannot retroactively relax the failed M9A.4 gate or qualify M9B for integration.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _materialize(
    output: Path,
    run_rows: list[dict[str, object]],
    suite_config: dict[str, object],
    trace_manifest: dict[str, object],
    *,
    bootstrap_samples: int,
) -> dict[str, object]:
    seed_start = int(suite_config["seed_start"])
    seed_count = int(suite_config["seed_count"])
    seeds = list(range(seed_start, seed_start + seed_count))
    scenario_rows = _scenario_summary(run_rows)
    transfers = _transfer_effects(run_rows, seeds, bootstrap_samples)
    gaps = _gap_effects(run_rows, seeds, bootstrap_samples)
    trace_verified = _verify_trace_manifest(
        dict(suite_config["scenario_configs"]),  # type: ignore[arg-type]
        list(trace_manifest["entries"]),  # type: ignore[arg-type]
    )
    diagnosis = _diagnosis(transfers, trace_verified)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(output / "run_summary.csv", run_rows)
    _write_csv(output / "scenario_summary.csv", scenario_rows)
    _write_csv(output / "transfer_effects.csv", transfers)
    _write_csv(output / "gap_effects.csv", gaps)
    trace_manifest["replay_verified"] = trace_verified
    (output / "trace_manifest.json").write_text(
        json.dumps(trace_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "decision.json").write_text(
        json.dumps(diagnosis, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_report(
        output / "milestone9a5_report.md",
        diagnosis,
        scenario_rows,
        transfers,
        gaps,
        seed_start,
        seed_count,
    )
    return diagnosis


def run_oracle_floor_suite(
    base_config: ExperimentConfig,
    output_directory: str | Path,
    *,
    seed_count: int = 100,
    seed_start: int = 12000,
    workers: int | None = None,
    bootstrap_samples: int = 5000,
) -> dict[str, object]:
    """Run the complete non-promotional M9A.5 diagnostic."""
    if seed_count < 2:
        raise ValueError("seed_count must be at least 2")
    if bootstrap_samples < 100:
        raise ValueError("bootstrap_samples must be at least 100")
    seeds = list(range(seed_start, seed_start + seed_count))
    tasks: list[tuple[str, dict[str, object], int]] = []
    scenario_configs: dict[str, dict[str, object]] = {}
    trace_entries: list[dict[str, object]] = []
    for scenario in M9A_SCENARIOS:
        config = replace(
            base_config,
            **_fit_timing(scenario.overrides, base_config.steps),
            seeds=seeds,
            algorithms=["flocking_topology_resilient"],
        )
        config.validate()
        config_data = config.to_dict()
        scenario_configs[scenario.name] = config_data
        for seed in seeds:
            tasks.append((scenario.name, config_data, seed))
            trace_entries.append(
                {
                    "scenario": scenario.name,
                    "seed": seed,
                    "fingerprint": scenario_fingerprint(config, seed),
                }
            )

    worker_count = workers or min(os.cpu_count() or 2, 8)
    executor_kind = "serial"
    if worker_count == 1:
        run_rows = [_worker(task) for task in tasks]
    else:
        try:
            with ProcessPoolExecutor(max_workers=worker_count) as executor:
                run_rows = list(executor.map(_worker, tasks, chunksize=2))
            executor_kind = "process"
        except (PermissionError, OSError):
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                run_rows = list(executor.map(_worker, tasks))
            executor_kind = "thread_fallback"
    scenario_order = {
        scenario.name: index for index, scenario in enumerate(M9A_SCENARIOS)
    }
    run_rows.sort(
        key=lambda row: (scenario_order[str(row["scenario"])], int(row["seed"]))
    )

    output = Path(output_directory)
    suite_config: dict[str, object] = {
        "seed_start": seed_start,
        "seed_count": seed_count,
        "bootstrap_samples": bootstrap_samples,
        "workers": worker_count,
        "executor": executor_kind,
        "scenarios": [asdict(scenario) for scenario in M9A_SCENARIOS],
        "scenario_configs": scenario_configs,
        "trajectory_policy": "frozen_flocking_topology_resilient",
        "assignment_model": "uniform enumeration of declared secondary-mode membership",
        "credible_mass": 0.95,
        "original_m9a_parameters_frozen": True,
        "non_promotional": True,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "platform_version": "0.12.0",
    }
    trace_manifest: dict[str, object] = {
        "identical_frozen_trajectory_for_all_nested_references": True,
        "replay_verified": False,
        "entries": trace_entries,
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "suite_config.json").write_text(
        json.dumps(suite_config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return _materialize(
        output,
        run_rows,
        suite_config,
        trace_manifest,
        bootstrap_samples=bootstrap_samples,
    )


def reanalyze_oracle_floor_suite(
    output_directory: str | Path,
    *,
    bootstrap_samples: int | None = None,
) -> dict[str, object]:
    """Rebuild M9A.5 statistics and verify all materialized traces."""
    output = Path(output_directory)
    suite_config = json.loads(
        (output / "suite_config.json").read_text(encoding="utf-8")
    )
    trace_manifest = json.loads(
        (output / "trace_manifest.json").read_text(encoding="utf-8")
    )
    with (output / "run_summary.csv").open(encoding="utf-8", newline="") as handle:
        run_rows = [dict(row) for row in csv.DictReader(handle)]
    samples = int(bootstrap_samples or suite_config["bootstrap_samples"])
    return _materialize(
        output,
        run_rows,
        suite_config,
        trace_manifest,
        bootstrap_samples=samples,
    )
