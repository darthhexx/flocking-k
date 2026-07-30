"""Analysis-only M9B movement-cost sensitivity over immutable saved actions."""

from __future__ import annotations

import csv
from dataclasses import replace
import json
from pathlib import Path

import numpy as np

from .active_sensing_suite import (
    ActiveSensingConfig,
    ActiveSensingScenario,
    choose_active_sensing_action,
)
from .suite import _bootstrap_interval, _write_csv


DEFAULT_MOVEMENT_COST_SCALES = (
    0.0,
    0.05,
    0.10,
    0.15,
    0.20,
    0.25,
    0.50,
    0.75,
    1.0,
    1.5,
    2.0,
    3.0,
    4.0,
)
BASELINES = ("passive", "round_robin", "myopic_voi")


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _break_even(
    candidate_decision: float,
    candidate_movement: float,
    baseline_decision: float,
    baseline_movement: float,
) -> float | None:
    denominator = candidate_movement - baseline_movement
    if abs(denominator) <= 1e-15:
        return None
    value = (baseline_decision - candidate_decision) / denominator
    return float(value) if value >= 0.0 else None


def analyze_movement_cost_sweep(
    output_directory: str | Path,
    *,
    scales: tuple[float, ...] = DEFAULT_MOVEMENT_COST_SCALES,
    bootstrap_samples: int = 5000,
) -> dict[str, object]:
    """Reprice saved M9B action traces; never regenerate or change an action."""
    if not scales or any(value < 0.0 for value in scales):
        raise ValueError("movement-cost scales must be nonempty and nonnegative")
    if bootstrap_samples < 100:
        raise ValueError("bootstrap_samples must be at least 100")
    output = Path(output_directory)
    rows = _read_rows(output / "run_summary.csv")
    suite_config = json.loads((output / "suite_config.json").read_text(encoding="utf-8"))
    scenarios = [str(item["name"]) for item in suite_config["scenarios"]]
    policies = [str(value) for value in suite_config["policies"]]
    seeds = sorted({int(row["seed"]) for row in rows})
    indexed = {
        (str(row["scenario"]), str(row["policy"]), int(row["seed"])): row
        for row in rows
    }

    sweep_rows: list[dict[str, object]] = []
    effect_rows: list[dict[str, object]] = []
    rng = np.random.default_rng(2026072229)
    for scale in scales:
        for policy in policies:
            decision = np.asarray(
                [
                    float(indexed[(scenario, policy, seed)]["decision_cost"])
                    for scenario in scenarios
                    for seed in seeds
                ]
            )
            movement = np.asarray(
                [
                    float(indexed[(scenario, policy, seed)]["movement_cost"])
                    for scenario in scenarios
                    for seed in seeds
                ]
            )
            sweep_rows.append(
                {
                    "movement_cost_scale": scale,
                    "policy": policy,
                    "runs": len(decision),
                    "decision_cost_mean": float(np.mean(decision)),
                    "scaled_movement_cost_mean": float(scale * np.mean(movement)),
                    "repriced_total_loss_mean": float(
                        np.mean(decision + scale * movement)
                    ),
                }
            )
        for baseline in BASELINES:
            paired: list[float] = []
            for seed in seeds:
                baseline_loss = np.mean(
                    [
                        float(indexed[(scenario, baseline, seed)]["decision_cost"])
                        + scale
                        * float(indexed[(scenario, baseline, seed)]["movement_cost"])
                        for scenario in scenarios
                    ]
                )
                candidate_loss = np.mean(
                    [
                        float(
                            indexed[(scenario, "receding_horizon_voi", seed)][
                                "decision_cost"
                            ]
                        )
                        + scale
                        * float(
                            indexed[(scenario, "receding_horizon_voi", seed)][
                                "movement_cost"
                            ]
                        )
                        for scenario in scenarios
                    ]
                )
                paired.append(float(baseline_loss - candidate_loss))
            values = np.asarray(paired)
            lower, upper = _bootstrap_interval(values, bootstrap_samples, rng)
            effect_rows.append(
                {
                    "movement_cost_scale": scale,
                    "candidate": "receding_horizon_voi",
                    "baseline": baseline,
                    "pairs": len(values),
                    "improvement_mean": float(np.mean(values)),
                    "ci95_lower": lower,
                    "ci95_upper": upper,
                }
            )

    means: dict[str, tuple[float, float]] = {}
    for policy in policies:
        policy_rows = [row for row in rows if row["policy"] == policy]
        means[policy] = (
            float(np.mean([float(row["decision_cost"]) for row in policy_rows])),
            float(np.mean([float(row["movement_cost"]) for row in policy_rows])),
        )
    break_even = {
        baseline: _break_even(*means["receding_horizon_voi"], *means[baseline])
        for baseline in BASELINES
    }
    supported = {
        baseline: [
            float(row["movement_cost_scale"])
            for row in effect_rows
            if row["baseline"] == baseline and float(row["ci95_lower"]) > 0.0
        ]
        for baseline in BASELINES
    }

    # This diagnostic asks when a freshly planned first action changes.  It is
    # reported separately and is never mixed into the fixed-action loss sweep.
    config = ActiveSensingConfig(**suite_config["active_sensing_config"])
    planning_threshold_rows: list[dict[str, object]] = []
    for scenario_data in suite_config["scenarios"]:
        scenario = ActiveSensingScenario(**scenario_data)
        prior = np.asarray(scenario.prior_probabilities, dtype=float)
        positions = np.zeros((config.n_agents, 2), dtype=float)
        velocities = np.zeros_like(positions)
        for scale in scales:
            scaled_config = replace(
                config, movement_cost_per_unit=config.movement_cost_per_unit * scale
            )
            for policy, horizon in (
                ("myopic_voi", config.myopic_horizon),
                ("receding_horizon_voi", config.receding_horizon),
            ):
                action, evaluated = choose_active_sensing_action(
                    scaled_config,
                    scenario,
                    prior,
                    positions,
                    velocities,
                    horizon,
                    remaining_steps=config.steps,
                )
                planning_threshold_rows.append(
                    {
                        "scenario": scenario.name,
                        "movement_cost_scale": scale,
                        "policy": policy,
                        "first_action": action,
                        "planning_sequences_evaluated": evaluated,
                    }
                )

    result: dict[str, object] = {
        "analysis": "fixed-action movement-cost repricing",
        "source": str(output / "run_summary.csv"),
        "saved_actions_modified": False,
        "original_m9b_verdict_unchanged": True,
        "scales": list(scales),
        "receding_break_even_scale": break_even,
        "scales_with_significant_receding_advantage": supported,
        "highest_grid_scale_with_active_first_action": {
            f"{scenario}:{policy}": max(
                (
                    float(row["movement_cost_scale"])
                    for row in planning_threshold_rows
                    if row["scenario"] == scenario
                    and row["policy"] == policy
                    and row["first_action"] != "hold"
                ),
                default=None,
            )
            for scenario in scenarios
            for policy in ("myopic_voi", "receding_horizon_voi")
        },
        "interpretation": (
            "The original GO is conditional on the declared movement-cost scale; "
            "this artifact maps, but does not redefine, that operating envelope."
        ),
    }
    _write_csv(output / "movement_cost_sweep.csv", sweep_rows)
    _write_csv(output / "movement_cost_effects.csv", effect_rows)
    _write_csv(output / "movement_cost_planning_thresholds.csv", planning_threshold_rows)
    (output / "movement_cost_sensitivity.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# M9B movement-cost sensitivity",
        "",
        "This is an analysis-only repricing of saved held-out actions. No action trace, posterior, or original M9B verdict was changed.",
        "",
        "| Baseline | Analytic break-even scale | Scales with positive 95% LCB |",
        "|---|---:|---|",
    ]
    for baseline in BASELINES:
        value = break_even[baseline]
        rendered = "none" if value is None else f"{value:.3f}"
        scale_text = ", ".join(f"{value:g}" for value in supported[baseline]) or "none"
        lines.append(f"| {baseline} | {rendered} | {scale_text} |")
    lines.extend(
        [
            "",
            "## Counterfactual first-action diagnostic",
            "",
            "| Scenario | Myopic highest active scale | Receding highest active scale |",
            "|---|---:|---:|",
        ]
    )
    active_thresholds = result["highest_grid_scale_with_active_first_action"]
    assert isinstance(active_thresholds, dict)
    for scenario in scenarios:
        myopic = active_thresholds[f"{scenario}:myopic_voi"]
        receding = active_thresholds[f"{scenario}:receding_horizon_voi"]
        lines.append(
            f"| {scenario} | {'none' if myopic is None else f'{float(myopic):g}'} | "
            f"{'none' if receding is None else f'{float(receding):g}'} |"
        )
    lines.extend(
        [
            "",
            "`movement_cost_planning_thresholds.csv` records every counterfactual first-action choice. These choices are diagnostic only and are not used in the fixed-action performance comparison.",
            "",
        ]
    )
    (output / "movement_cost_sensitivity.md").write_text(
        "\n".join(lines), encoding="utf-8"
    )
    return result
