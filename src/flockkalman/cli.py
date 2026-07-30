"""Command-line interface."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .ambiguity_assay import (
    AmbiguityAssayConfig,
    reanalyze_ambiguity_decision_suite,
    run_ambiguity_decision_suite,
)
from .active_sensing_suite import (
    ActiveSensingConfig,
    reanalyze_active_sensing_decision_suite,
    run_active_sensing_decision_suite,
)
from .admission_suite import (
    reanalyze_admission_evidence_suite,
    run_admission_evidence_suite,
)
from .adversarial_trust_suite import (
    reanalyze_adversarial_trust_suite,
    run_adversarial_trust_suite,
)
from .acceleration_suite import run_acceleration_suite
from .closed_loop_trust_suite import (
    reanalyze_closed_loop_trust_suite,
    run_closed_loop_trust_suite,
)
from .config import ExperimentConfig
from .decentralized_suite import (
    reanalyze_decentralized_suite,
    run_decentralized_suite,
)
from .experiment import ALGORITHMS, run_experiment
from .external_replay_repair_suite import (
    run_external_replay_repair_suite,
)
from .external_replay_suite import (
    reanalyze_external_replay_suite,
    run_external_replay_suite,
)
from .guarded_suite import (
    reanalyze_guarded_decision_suite,
    run_guarded_decision_suite,
)
from .integration_suite import (
    reanalyze_integration_suite,
    run_integration_suite,
)
from .full_loop_hil import HILConfig, run_full_loop_hil_suite
from .full_loop_physical import (
    create_physical_trial_plan,
    evaluate_physical_holdout,
    run_physical_pilot,
    score_physical_bundle,
    seal_physical_bundle,
)
from .momentum_mechanism import run_momentum_mechanism_study
from .missing_evidence_suite import (
    reanalyze_missing_evidence_suite,
    run_missing_evidence_suite,
)
from .movement_cost_sweep import analyze_movement_cost_sweep
from .oracle_floor_suite import (
    reanalyze_oracle_floor_suite,
    run_oracle_floor_suite,
)
from .output_suite import (
    reanalyze_output_decision_suite,
    run_output_decision_suite,
)
from .realism_suite import (
    reanalyze_realism_decision_suite,
    run_realism_decision_suite,
)
from .robust_suite import (
    reanalyze_robust_decision_suite,
    run_robust_decision_suite,
)
from .suite import (
    DEFAULT_SUITE_SCENARIOS,
    reanalyze_decision_suite,
    run_decision_suite,
)
from .topology_suite import (
    reanalyze_topology_decision_suite,
    run_topology_decision_suite,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="flockkalman",
        description="Run reproducible flocking–Kalman research experiments.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run", help="run an experiment matrix")
    run.add_argument("--config", type=Path, help="JSON configuration file")
    run.add_argument("--output", type=Path, default=Path("results/latest"))
    run.add_argument("--steps", type=int, help="override the number of simulation steps")
    run.add_argument("--seeds", help="comma-separated integer seeds")
    run.add_argument("--algorithms", help="comma-separated algorithm names")
    decision = subparsers.add_parser(
        "decision-suite", help="run the held-out paired momentum evaluation"
    )
    decision.add_argument("--config", type=Path, help="base JSON configuration file")
    decision.add_argument("--output", type=Path, default=Path("results/decision_suite"))
    decision.add_argument("--seed-count", type=int, default=100)
    decision.add_argument("--seed-start", type=int, default=1000)
    decision.add_argument("--workers", type=int)
    decision.add_argument("--bootstrap-samples", type=int, default=5000)
    decision.add_argument(
        "--scenarios",
        help="comma-separated scenario names; defaults to all seven",
    )
    reanalyze = subparsers.add_parser(
        "reanalyze-suite", help="regenerate a completed suite's statistical report"
    )
    reanalyze.add_argument("--output", type=Path, required=True)
    reanalyze.add_argument("--bootstrap-samples", type=int)
    guarded = subparsers.add_parser(
        "guarded-suite", help="run the M5 guarded-momentum decision experiment"
    )
    guarded.add_argument("--config", type=Path, help="base JSON configuration file")
    guarded.add_argument("--output", type=Path, default=Path("results/milestone5_suite"))
    guarded.add_argument("--seed-count", type=int, default=100)
    guarded.add_argument("--seed-start", type=int, default=2000)
    guarded.add_argument("--workers", type=int)
    guarded.add_argument("--bootstrap-samples", type=int, default=5000)
    guarded.add_argument(
        "--scenarios",
        help="comma-separated scenario names; defaults to all seven",
    )
    reanalyze_guarded = subparsers.add_parser(
        "reanalyze-guarded-suite",
        help="regenerate an M5 suite's statistical report",
    )
    reanalyze_guarded.add_argument("--output", type=Path, required=True)
    reanalyze_guarded.add_argument("--bootstrap-samples", type=int)
    robust = subparsers.add_parser(
        "robust-suite", help="run the M6 robust-fusion and multi-flock experiment"
    )
    robust.add_argument("--config", type=Path, help="base JSON configuration file")
    robust.add_argument("--output", type=Path, default=Path("results/milestone6_suite"))
    robust.add_argument("--seed-count", type=int, default=100)
    robust.add_argument("--seed-start", type=int, default=3000)
    robust.add_argument("--workers", type=int)
    robust.add_argument("--bootstrap-samples", type=int, default=5000)
    robust.add_argument(
        "--scenarios",
        help="comma-separated M6 scenario names; defaults to all seven",
    )
    reanalyze_robust = subparsers.add_parser(
        "reanalyze-robust-suite",
        help="regenerate an M6 suite's statistical report",
    )
    reanalyze_robust.add_argument("--output", type=Path, required=True)
    reanalyze_robust.add_argument("--bootstrap-samples", type=int)
    output_policy = subparsers.add_parser(
        "output-suite", help="run the M7 truth-blind hypothesis-output experiment"
    )
    output_policy.add_argument("--config", type=Path, help="base JSON configuration file")
    output_policy.add_argument(
        "--output", type=Path, default=Path("results/milestone7_suite")
    )
    output_policy.add_argument("--seed-count", type=int, default=100)
    output_policy.add_argument("--seed-start", type=int, default=4000)
    output_policy.add_argument("--workers", type=int)
    output_policy.add_argument("--bootstrap-samples", type=int, default=5000)
    reanalyze_output = subparsers.add_parser(
        "reanalyze-output-suite",
        help="regenerate an M7 suite's statistical report",
    )
    reanalyze_output.add_argument("--output", type=Path, required=True)
    reanalyze_output.add_argument("--bootstrap-samples", type=int)
    realism = subparsers.add_parser(
        "realism-suite", help="run the M8 frozen-policy realism ladder"
    )
    realism.add_argument("--config", type=Path, help="base JSON configuration file")
    realism.add_argument(
        "--output", type=Path, default=Path("results/milestone8_suite")
    )
    realism.add_argument("--seed-count", type=int, default=100)
    realism.add_argument("--seed-start", type=int, default=5000)
    realism.add_argument("--workers", type=int)
    realism.add_argument("--bootstrap-samples", type=int, default=5000)
    reanalyze_realism = subparsers.add_parser(
        "reanalyze-realism-suite",
        help="regenerate an M8 suite's statistics and trace verification",
    )
    reanalyze_realism.add_argument("--output", type=Path, required=True)
    reanalyze_realism.add_argument("--bootstrap-samples", type=int)
    ambiguity = subparsers.add_parser(
        "ambiguity-assay",
        help="run the M8.1 endogenous-ambiguity positive control",
    )
    ambiguity.add_argument("--config", type=Path, help="optional assay JSON configuration")
    ambiguity.add_argument(
        "--output", type=Path, default=Path("results/milestone8_1_assay")
    )
    ambiguity.add_argument("--seed-count", type=int, default=100)
    ambiguity.add_argument("--seed-start", type=int, default=7000)
    ambiguity.add_argument("--doses", default="0,0.10,0.25,0.50,1.0")
    ambiguity.add_argument("--workers", type=int)
    ambiguity.add_argument("--bootstrap-samples", type=int, default=5000)
    reanalyze_ambiguity = subparsers.add_parser(
        "reanalyze-ambiguity-assay",
        help="regenerate an M8.1 assay's statistics and replay verification",
    )
    reanalyze_ambiguity.add_argument("--output", type=Path, required=True)
    reanalyze_ambiguity.add_argument("--bootstrap-samples", type=int)
    mechanism = subparsers.add_parser(
        "momentum-mechanism",
        help="run the training-only fixed-rho/tau mechanism study",
    )
    mechanism.add_argument("--config", type=Path, help="base JSON configuration file")
    mechanism.add_argument(
        "--output", type=Path, default=Path("results/momentum_mechanism")
    )
    mechanism.add_argument("--seed-count", type=int, default=30)
    mechanism.add_argument("--seed-start", type=int, default=8000)
    mechanism.add_argument("--rhos", default="0,0.25,0.50,0.72,0.85,0.93")
    mechanism.add_argument("--scenarios", help="comma-separated diagnostic scenarios")
    mechanism.add_argument("--workers", type=int)
    active_sensing = subparsers.add_parser(
        "active-sensing-suite",
        help="run the M9B competing-view value-of-information evaluation",
    )
    active_sensing.add_argument(
        "--config", type=Path, help="optional M9B JSON configuration"
    )
    active_sensing.add_argument(
        "--output", type=Path, default=Path("results/milestone9b_suite")
    )
    active_sensing.add_argument("--seed-count", type=int, default=100)
    active_sensing.add_argument("--seed-start", type=int, default=10000)
    active_sensing.add_argument("--workers", type=int)
    active_sensing.add_argument("--bootstrap-samples", type=int, default=5000)
    active_sensing.add_argument(
        "--scenarios", help="comma-separated M9B scenario names"
    )
    reanalyze_active_sensing = subparsers.add_parser(
        "reanalyze-active-sensing-suite",
        help="regenerate an M9B suite's statistics and replay verification",
    )
    reanalyze_active_sensing.add_argument("--output", type=Path, required=True)
    reanalyze_active_sensing.add_argument("--bootstrap-samples", type=int)
    topology = subparsers.add_parser(
        "topology-suite",
        help="run the M9A topology/outage/rejoin evaluation",
    )
    topology.add_argument("--config", type=Path, help="base JSON configuration file")
    topology.add_argument(
        "--output", type=Path, default=Path("results/milestone9a_suite")
    )
    topology.add_argument("--seed-count", type=int, default=100)
    topology.add_argument("--seed-start", type=int, default=12000)
    topology.add_argument("--workers", type=int)
    topology.add_argument("--bootstrap-samples", type=int, default=5000)
    reanalyze_topology = subparsers.add_parser(
        "reanalyze-topology-suite",
        help="regenerate M9A statistics and replay verification",
    )
    reanalyze_topology.add_argument("--output", type=Path, required=True)
    reanalyze_topology.add_argument("--bootstrap-samples", type=int)
    oracle_floor = subparsers.add_parser(
        "oracle-floor-suite",
        help="run the non-promotional M9A.5 nested-reference diagnostic",
    )
    oracle_floor.add_argument("--config", type=Path, help="base JSON configuration file")
    oracle_floor.add_argument(
        "--output", type=Path, default=Path("results/milestone9a5_oracle_floor")
    )
    oracle_floor.add_argument("--seed-count", type=int, default=100)
    oracle_floor.add_argument("--seed-start", type=int, default=12000)
    oracle_floor.add_argument("--workers", type=int)
    oracle_floor.add_argument("--bootstrap-samples", type=int, default=5000)
    reanalyze_oracle_floor = subparsers.add_parser(
        "reanalyze-oracle-floor-suite",
        help="regenerate M9A.5 statistics and replay verification",
    )
    reanalyze_oracle_floor.add_argument("--output", type=Path, required=True)
    reanalyze_oracle_floor.add_argument("--bootstrap-samples", type=int)
    missing_evidence = subparsers.add_parser(
        "missing-evidence-suite",
        help="run the M9A.6 missing-evidence posterior evaluation",
    )
    missing_evidence.add_argument(
        "--config", type=Path, help="base JSON configuration file"
    )
    missing_evidence.add_argument(
        "--output", type=Path, default=Path("results/milestone9a6_heldout")
    )
    missing_evidence.add_argument("--seed-count", type=int, default=100)
    missing_evidence.add_argument("--seed-start", type=int, default=14000)
    missing_evidence.add_argument("--workers", type=int)
    missing_evidence.add_argument("--bootstrap-samples", type=int, default=5000)
    missing_evidence.add_argument(
        "--phase", choices=("training", "heldout"), default="heldout"
    )
    reanalyze_missing_evidence = subparsers.add_parser(
        "reanalyze-missing-evidence-suite",
        help="regenerate M9A.6 statistics and replay verification",
    )
    reanalyze_missing_evidence.add_argument("--output", type=Path, required=True)
    reanalyze_missing_evidence.add_argument("--bootstrap-samples", type=int)
    admission = subparsers.add_parser(
        "admission-evidence-suite",
        help="run the M9A.7 split-admission and tail-safety evaluation",
    )
    admission.add_argument("--config", type=Path, help="base JSON configuration file")
    admission.add_argument(
        "--output", type=Path, default=Path("results/milestone9a7_heldout")
    )
    admission.add_argument("--seed-count", type=int, default=300)
    admission.add_argument("--seed-start", type=int, default=16000)
    admission.add_argument("--workers", type=int)
    admission.add_argument("--bootstrap-samples", type=int, default=5000)
    admission.add_argument(
        "--phase", choices=("training", "heldout"), default="heldout"
    )
    reanalyze_admission = subparsers.add_parser(
        "reanalyze-admission-evidence-suite",
        help="regenerate M9A.7 statistics and replay verification",
    )
    reanalyze_admission.add_argument("--output", type=Path, required=True)
    reanalyze_admission.add_argument("--bootstrap-samples", type=int)
    movement_sweep = subparsers.add_parser(
        "movement-cost-sweep",
        help="reprice immutable saved M9B actions across movement-cost scales",
    )
    movement_sweep.add_argument("--output", type=Path, required=True)
    movement_sweep.add_argument(
        "--scales", default="0,0.05,0.1,0.15,0.2,0.25,0.5,0.75,1,1.5,2,3,4"
    )
    movement_sweep.add_argument("--bootstrap-samples", type=int, default=5000)
    integration = subparsers.add_parser(
        "integration-suite",
        help="run the M9C bounded M9A.7/M9B dynamic-topology integration",
    )
    integration.add_argument("--config", type=Path, help="base JSON configuration file")
    integration.add_argument(
        "--output", type=Path, default=Path("results/milestone9c_heldout")
    )
    integration.add_argument("--seed-count", type=int, default=150)
    integration.add_argument("--seed-start", type=int, default=19000)
    integration.add_argument("--workers", type=int)
    integration.add_argument("--bootstrap-samples", type=int, default=5000)
    integration.add_argument(
        "--phase", choices=("training", "heldout"), default="heldout"
    )
    reanalyze_integration = subparsers.add_parser(
        "reanalyze-integration-suite",
        help="regenerate M9C statistics and trace verification",
    )
    reanalyze_integration.add_argument("--output", type=Path, required=True)
    reanalyze_integration.add_argument("--bootstrap-samples", type=int)
    adversarial_trust = subparsers.add_parser(
        "adversarial-trust-suite",
        help="run the M10A raw-channel trust and availability evaluation",
    )
    adversarial_trust.add_argument(
        "--config", type=Path, help="base JSON configuration file"
    )
    adversarial_trust.add_argument(
        "--output", type=Path, default=Path("results/milestone10a_training")
    )
    adversarial_trust.add_argument("--seed-count", type=int, default=40)
    adversarial_trust.add_argument("--seed-start", type=int, default=20000)
    adversarial_trust.add_argument("--workers", type=int)
    adversarial_trust.add_argument(
        "--bootstrap-samples", type=int, default=5000
    )
    adversarial_trust.add_argument(
        "--phase", choices=("training", "heldout"), default="training"
    )
    reanalyze_adversarial_trust = subparsers.add_parser(
        "reanalyze-adversarial-trust-suite",
        help="regenerate M10A statistics and trace verification",
    )
    reanalyze_adversarial_trust.add_argument(
        "--output", type=Path, required=True
    )
    reanalyze_adversarial_trust.add_argument("--bootstrap-samples", type=int)
    closed_loop_trust = subparsers.add_parser(
        "closed-loop-trust-suite",
        help="run the M10A.5 closed-loop trust integration",
    )
    closed_loop_trust.add_argument("--config", type=Path)
    closed_loop_trust.add_argument(
        "--output", type=Path, default=Path("results/milestone10a5_heldout")
    )
    closed_loop_trust.add_argument("--seed-count", type=int, default=150)
    closed_loop_trust.add_argument("--seed-start", type=int, default=23000)
    closed_loop_trust.add_argument("--workers", type=int)
    closed_loop_trust.add_argument("--bootstrap-samples", type=int, default=5000)
    closed_loop_trust.add_argument(
        "--phase", choices=("training", "heldout"), default="heldout"
    )
    reanalyze_closed_loop = subparsers.add_parser(
        "reanalyze-closed-loop-trust-suite"
    )
    reanalyze_closed_loop.add_argument("--output", type=Path, required=True)
    reanalyze_closed_loop.add_argument("--bootstrap-samples", type=int)
    decentralized = subparsers.add_parser(
        "decentralized-suite",
        help="run the M10B decentralized allocation evaluation",
    )
    decentralized.add_argument("--config", type=Path)
    decentralized.add_argument(
        "--output", type=Path, default=Path("results/milestone10b_heldout")
    )
    decentralized.add_argument("--seed-count", type=int, default=150)
    decentralized.add_argument("--seed-start", type=int, default=25000)
    decentralized.add_argument("--workers", type=int)
    decentralized.add_argument("--bootstrap-samples", type=int, default=5000)
    decentralized.add_argument(
        "--phase", choices=("training", "heldout"), default="heldout"
    )
    reanalyze_decentralized = subparsers.add_parser(
        "reanalyze-decentralized-suite"
    )
    reanalyze_decentralized.add_argument("--output", type=Path, required=True)
    reanalyze_decentralized.add_argument("--bootstrap-samples", type=int)
    external_replay = subparsers.add_parser(
        "external-replay-suite",
        help="run the M11 real MR.CLAM replay",
    )
    external_replay.add_argument("--dataset", type=Path, required=True)
    external_replay.add_argument("--archive", type=Path, required=True)
    external_replay.add_argument("--output", type=Path, required=True)
    external_replay.add_argument(
        "--phase", choices=("development", "heldout"), required=True
    )
    external_replay.add_argument("--bootstrap-samples", type=int, default=5000)
    reanalyze_external = subparsers.add_parser(
        "reanalyze-external-replay-suite"
    )
    reanalyze_external.add_argument("--output", type=Path, required=True)
    reanalyze_external.add_argument("--bootstrap-samples", type=int)
    repair_replay = subparsers.add_parser(
        "external-replay-repair-suite",
        help="run the M11.1 canonicalized MR.CLAM replay",
    )
    repair_replay.add_argument("--dataset", type=Path, required=True)
    repair_replay.add_argument("--canonical", type=Path, required=True)
    repair_replay.add_argument("--archive", type=Path, required=True)
    repair_replay.add_argument("--output", type=Path, required=True)
    repair_replay.add_argument(
        "--phase", choices=("development", "heldout"), required=True
    )
    repair_replay.add_argument("--bootstrap-samples", type=int, default=5000)
    acceleration = subparsers.add_parser(
        "acceleration-suite",
        help="run the M12 estimator/jerk acceleration ablation",
    )
    acceleration.add_argument("--dataset", type=Path, required=True)
    acceleration.add_argument("--canonical", type=Path, required=True)
    acceleration.add_argument("--archive", type=Path, required=True)
    acceleration.add_argument("--output", type=Path, required=True)
    acceleration.add_argument(
        "--phase", choices=("development", "heldout"), required=True
    )
    acceleration.add_argument("--bootstrap-samples", type=int, default=5000)
    full_loop_hil = subparsers.add_parser(
        "full-loop-hil-suite",
        help="run the M13.1 independent distributed full-loop HIL screen",
    )
    full_loop_hil.add_argument(
        "--output", type=Path, default=Path("results/milestone13_1_hil")
    )
    full_loop_hil.add_argument("--seed-count", type=int, default=150)
    full_loop_hil.add_argument("--seed-start", type=int, default=27000)
    full_loop_hil.add_argument("--steps", type=int, default=120)
    full_loop_hil.add_argument("--bootstrap-samples", type=int, default=2000)
    full_loop_hil.add_argument("--workers", type=int, default=1)
    full_loop_hil.add_argument("--scenarios", help="comma-separated M13 scenarios")
    physical_plan = subparsers.add_parser(
        "physical-trial-plan",
        help="create an M13.2 or M13.3 randomized physical trial schedule",
    )
    physical_plan.add_argument("--output", type=Path, required=True)
    physical_plan.add_argument("--phase", choices=("pilot", "heldout"), required=True)
    physical_plan.add_argument("--blocks-per-scenario", type=int, default=30)
    physical_plan.add_argument(
        "--trial-dates",
        default="day-1,day-2,day-3",
        help="comma-separated ISO dates or preregistered day labels",
    )
    physical_seal = subparsers.add_parser(
        "seal-physical-bundle",
        help="hash-seal a closed M13 physical evidence bundle",
    )
    physical_seal.add_argument("--bundle", type=Path, required=True)
    physical_score = subparsers.add_parser(
        "score-physical-bundle",
        help="audit and independently rescore one M13 physical evidence bundle",
    )
    physical_score.add_argument("--bundle", type=Path, required=True)
    physical_pilot = subparsers.add_parser(
        "physical-pilot",
        help="run M13.2 on genuine pilot bundles and freeze holdout power",
    )
    physical_pilot.add_argument("--bundles", type=Path, nargs="+", required=True)
    physical_pilot.add_argument("--output", type=Path, required=True)
    physical_pilot.add_argument("--project-root", type=Path, default=Path("."))
    physical_pilot.add_argument("--target-effect", type=float, default=0.05)
    physical_pilot.add_argument("--minimum-blocks", type=int, default=30)
    physical_pilot.add_argument("--maximum-blocks", type=int, default=500)
    physical_holdout = subparsers.add_parser(
        "physical-heldout",
        help="evaluate the frozen M13.3 external physical holdout",
    )
    physical_holdout.add_argument("--bundles", type=Path, nargs="+", required=True)
    physical_holdout.add_argument("--freeze", type=Path, required=True)
    physical_holdout.add_argument("--output", type=Path, required=True)
    physical_holdout.add_argument("--project-root", type=Path, default=Path("."))
    subparsers.add_parser("list-algorithms", help="show available algorithms")
    subparsers.add_parser("list-scenarios", help="show decision-suite scenarios")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    if arguments.command == "list-algorithms":
        for algorithm in ALGORITHMS:
            print(algorithm)
        return 0
    if arguments.command == "list-scenarios":
        for scenario in DEFAULT_SUITE_SCENARIOS:
            print(f"{scenario.name}: {scenario.description}")
        return 0

    if arguments.command == "decision-suite":
        config = (
            ExperimentConfig.from_json(arguments.config)
            if arguments.config
            else ExperimentConfig()
        )
        scenario_names = (
            [value.strip() for value in arguments.scenarios.split(",") if value.strip()]
            if arguments.scenarios
            else None
        )
        result = run_decision_suite(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
            scenario_names=scenario_names,
        )
        print(f"Decision suite completed in {arguments.output}")
        print(f"Verdict: {result['verdict']}")
        for gate, passed in dict(result["gates"]).items():
            print(f"  {'PASS' if passed else 'FAIL':4}  {gate}")
        return 0
    if arguments.command == "reanalyze-suite":
        result = reanalyze_decision_suite(
            arguments.output, bootstrap_samples=arguments.bootstrap_samples
        )
        print(f"Reanalyzed {arguments.output}")
        print(f"Adaptive scheduler verdict: {result['verdict']}")
        print(f"Research direction: {result['research_direction']}")
        return 0
    if arguments.command == "guarded-suite":
        config = (
            ExperimentConfig.from_json(arguments.config)
            if arguments.config
            else ExperimentConfig()
        )
        scenario_names = (
            [value.strip() for value in arguments.scenarios.split(",") if value.strip()]
            if arguments.scenarios
            else None
        )
        result = run_guarded_decision_suite(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
            scenario_names=scenario_names,
        )
        print(f"M5 guarded suite completed in {arguments.output}")
        print(f"Verdict: {result['verdict']}")
        for gate, passed in dict(result["gates"]).items():
            print(f"  {'PASS' if passed else 'FAIL':4}  {gate}")
        return 0
    if arguments.command == "reanalyze-guarded-suite":
        result = reanalyze_guarded_decision_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"Reanalyzed {arguments.output}")
        print(f"Guarded-controller verdict: {result['verdict']}")
        print(f"Research direction: {result['research_direction']}")
        return 0
    if arguments.command == "robust-suite":
        config = (
            ExperimentConfig.from_json(arguments.config)
            if arguments.config
            else ExperimentConfig()
        )
        scenario_names = (
            [value.strip() for value in arguments.scenarios.split(",") if value.strip()]
            if arguments.scenarios
            else None
        )
        result = run_robust_decision_suite(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
            scenario_names=scenario_names,
        )
        print(f"M6 robust suite completed in {arguments.output}")
        print(f"Verdict: {result['verdict']}")
        for gate, passed in dict(result["gates"]).items():
            print(f"  {'PASS' if passed else 'FAIL':4}  {gate}")
        return 0
    if arguments.command == "reanalyze-robust-suite":
        result = reanalyze_robust_decision_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"Reanalyzed {arguments.output}")
        print(f"Robust-fusion verdict: {result['verdict']}")
        print(f"Research direction: {result['research_direction']}")
        return 0
    if arguments.command == "output-suite":
        config = (
            ExperimentConfig.from_json(arguments.config)
            if arguments.config
            else ExperimentConfig()
        )
        result = run_output_decision_suite(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"M7 output-policy suite completed in {arguments.output}")
        print(f"Verdict: {result['verdict']}")
        for gate, passed in dict(result["gates"]).items():
            print(f"  {'PASS' if passed else 'FAIL':4}  {gate}")
        return 0
    if arguments.command == "reanalyze-output-suite":
        result = reanalyze_output_decision_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"Reanalyzed {arguments.output}")
        print(f"Output-policy verdict: {result['verdict']}")
        print(f"Research direction: {result['research_direction']}")
        return 0
    if arguments.command == "realism-suite":
        config = (
            ExperimentConfig.from_json(arguments.config)
            if arguments.config
            else ExperimentConfig()
        )
        result = run_realism_decision_suite(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"M8 realism suite completed in {arguments.output}")
        print(f"Verdict: {result['verdict']}")
        for gate, passed in dict(result["gates"]).items():
            print(f"  {'PASS' if passed else 'FAIL':4}  {gate}")
        return 0
    if arguments.command == "reanalyze-realism-suite":
        result = reanalyze_realism_decision_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"Reanalyzed {arguments.output}")
        print(f"M8 realism verdict: {result['verdict']}")
        print(f"Research direction: {result['research_direction']}")
        return 0
    if arguments.command == "ambiguity-assay":
        assay_config = (
            AmbiguityAssayConfig(
                **json.loads(arguments.config.read_text(encoding="utf-8"))
            )
            if arguments.config
            else AmbiguityAssayConfig()
        )
        doses = tuple(
            float(value.strip())
            for value in arguments.doses.split(",")
            if value.strip()
        )
        result = run_ambiguity_decision_suite(
            assay_config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            doses=doses,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"M8.1 ambiguity assay completed in {arguments.output}")
        print(f"Verdict: {result['verdict']}")
        for gate, passed in dict(result["gates"]).items():
            print(f"  {'PASS' if passed else 'FAIL':4}  {gate}")
        return 0
    if arguments.command == "reanalyze-ambiguity-assay":
        result = reanalyze_ambiguity_decision_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"Reanalyzed {arguments.output}")
        print(f"M8.1 ambiguity verdict: {result['verdict']}")
        print(f"Research direction: {result['research_direction']}")
        return 0
    if arguments.command == "momentum-mechanism":
        config = (
            ExperimentConfig.from_json(arguments.config)
            if arguments.config
            else ExperimentConfig()
        )
        rhos = tuple(
            float(value.strip())
            for value in arguments.rhos.split(",")
            if value.strip()
        )
        scenarios = (
            [value.strip() for value in arguments.scenarios.split(",") if value.strip()]
            if arguments.scenarios
            else None
        )
        result = run_momentum_mechanism_study(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            rhos=rhos,
            scenario_names=scenarios,
            workers=arguments.workers,
        )
        print(f"Momentum mechanism study completed in {arguments.output}")
        print(f"Diagnostic verdict: {result['verdict']}")
        return 0
    if arguments.command == "active-sensing-suite":
        config = (
            ActiveSensingConfig(
                **json.loads(arguments.config.read_text(encoding="utf-8"))
            )
            if arguments.config
            else ActiveSensingConfig()
        )
        scenarios = (
            [value.strip() for value in arguments.scenarios.split(",") if value.strip()]
            if arguments.scenarios
            else None
        )
        result = run_active_sensing_decision_suite(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
            scenario_names=scenarios,
        )
        print(f"M9B active-sensing suite completed in {arguments.output}")
        print(f"Verdict: {result['verdict']}")
        for gate, passed in dict(result["gates"]).items():
            print(f"  {'PASS' if passed else 'FAIL':4}  {gate}")
        return 0
    if arguments.command == "reanalyze-active-sensing-suite":
        result = reanalyze_active_sensing_decision_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"Reanalyzed {arguments.output}")
        print(f"M9B verdict: {result['verdict']}")
        print(f"Research direction: {result['research_direction']}")
        return 0
    if arguments.command == "topology-suite":
        config = (
            ExperimentConfig.from_json(arguments.config)
            if arguments.config
            else ExperimentConfig()
        )
        result = run_topology_decision_suite(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"M9A topology suite completed in {arguments.output}")
        print(f"Verdict: {result['verdict']}")
        for gate, passed in dict(result["gates"]).items():
            print(f"  {'PASS' if passed else 'FAIL':4}  {gate}")
        return 0
    if arguments.command == "reanalyze-topology-suite":
        result = reanalyze_topology_decision_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"Reanalyzed {arguments.output}")
        print(f"M9A verdict: {result['verdict']}")
        return 0
    if arguments.command == "oracle-floor-suite":
        config = (
            ExperimentConfig.from_json(arguments.config)
            if arguments.config
            else ExperimentConfig()
        )
        result = run_oracle_floor_suite(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"M9A.5 diagnostic completed in {arguments.output}")
        print(f"Conclusion: {result['diagnostic_conclusion']}")
        print("Original M9A verdict: unchanged")
        return 0
    if arguments.command == "reanalyze-oracle-floor-suite":
        result = reanalyze_oracle_floor_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"Reanalyzed {arguments.output}")
        print(f"M9A.5 conclusion: {result['diagnostic_conclusion']}")
        return 0
    if arguments.command == "missing-evidence-suite":
        config = (
            ExperimentConfig.from_json(arguments.config)
            if arguments.config
            else ExperimentConfig()
        )
        result = run_missing_evidence_suite(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
            phase=arguments.phase,
        )
        print(f"M9A.6 missing-evidence suite completed in {arguments.output}")
        print(f"Verdict: {result['verdict']}")
        print("Original M9A verdict: unchanged")
        for gate, passed in dict(result["gates"]).items():
            print(f"  {'PASS' if passed else 'FAIL':4}  {gate}")
        return 0
    if arguments.command == "reanalyze-missing-evidence-suite":
        result = reanalyze_missing_evidence_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"Reanalyzed {arguments.output}")
        print(f"M9A.6 verdict: {result['verdict']}")
        return 0
    if arguments.command == "admission-evidence-suite":
        config = (
            ExperimentConfig.from_json(arguments.config)
            if arguments.config
            else ExperimentConfig()
        )
        result = run_admission_evidence_suite(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
            phase=arguments.phase,
        )
        print(f"M9A.7 admission-evidence suite completed in {arguments.output}")
        print(f"Verdict: {result['verdict']}")
        for gate, passed in dict(result["gates"]).items():
            print(f"  {'PASS' if passed else 'FAIL':4}  {gate}")
        return 0
    if arguments.command == "reanalyze-admission-evidence-suite":
        result = reanalyze_admission_evidence_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"Reanalyzed {arguments.output}")
        print(f"M9A.7 verdict: {result['verdict']}")
        return 0
    if arguments.command == "movement-cost-sweep":
        scales = tuple(
            float(value.strip())
            for value in arguments.scales.split(",")
            if value.strip()
        )
        result = analyze_movement_cost_sweep(
            arguments.output,
            scales=scales,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"M9B movement-cost sensitivity written to {arguments.output}")
        print("Original M9B verdict: unchanged")
        print(json.dumps(result["receding_break_even_scale"], sort_keys=True))
        return 0
    if arguments.command == "integration-suite":
        config = (
            ExperimentConfig.from_json(arguments.config)
            if arguments.config
            else ExperimentConfig()
        )
        result = run_integration_suite(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
            phase=arguments.phase,
        )
        print(f"M9C integration suite completed in {arguments.output}")
        print(f"Verdict: {result['verdict']}")
        for gate, passed in dict(result["gates"]).items():
            print(f"  {'PASS' if passed else 'FAIL':4}  {gate}")
        return 0
    if arguments.command == "reanalyze-integration-suite":
        result = reanalyze_integration_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"Reanalyzed {arguments.output}")
        print(f"M9C verdict: {result['verdict']}")
        return 0
    if arguments.command == "adversarial-trust-suite":
        config = (
            ExperimentConfig.from_json(arguments.config)
            if arguments.config
            else ExperimentConfig()
        )
        result = run_adversarial_trust_suite(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
            phase=arguments.phase,
        )
        print(f"M10A adversarial-trust suite completed in {arguments.output}")
        print(f"Verdict: {result['verdict']}")
        for gate, passed in dict(result["gates"]).items():
            print(f"  {'PASS' if passed else 'FAIL':4}  {gate}")
        return 0
    if arguments.command == "reanalyze-adversarial-trust-suite":
        result = reanalyze_adversarial_trust_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"Reanalyzed {arguments.output}")
        print(f"M10A verdict: {result['verdict']}")
        return 0
    if arguments.command == "closed-loop-trust-suite":
        config = (
            ExperimentConfig.from_json(arguments.config)
            if arguments.config
            else ExperimentConfig()
        )
        result = run_closed_loop_trust_suite(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
            phase=arguments.phase,
        )
        print(f"M10A.5 closed-loop suite completed in {arguments.output}")
        print(f"Verdict: {result['verdict']}")
        return 0
    if arguments.command == "reanalyze-closed-loop-trust-suite":
        result = reanalyze_closed_loop_trust_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"M10A.5 verdict: {result['verdict']}")
        return 0
    if arguments.command == "decentralized-suite":
        config = (
            ExperimentConfig.from_json(arguments.config)
            if arguments.config
            else ExperimentConfig()
        )
        result = run_decentralized_suite(
            config,
            arguments.output,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            workers=arguments.workers,
            bootstrap_samples=arguments.bootstrap_samples,
            phase=arguments.phase,
        )
        print(f"M10B decentralized suite completed in {arguments.output}")
        print(f"Verdict: {result['verdict']}")
        return 0
    if arguments.command == "reanalyze-decentralized-suite":
        result = reanalyze_decentralized_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"M10B verdict: {result['verdict']}")
        return 0
    if arguments.command == "external-replay-suite":
        result = run_external_replay_suite(
            arguments.dataset,
            arguments.archive,
            arguments.output,
            phase=arguments.phase,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"M11 verdict: {result['verdict']}")
        return 0
    if arguments.command == "reanalyze-external-replay-suite":
        result = reanalyze_external_replay_suite(
            arguments.output,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"M11 verdict: {result['verdict']}")
        return 0
    if arguments.command == "external-replay-repair-suite":
        result = run_external_replay_repair_suite(
            arguments.dataset,
            arguments.canonical,
            arguments.archive,
            arguments.output,
            phase=arguments.phase,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"M11.1 verdict: {result['verdict']}")
        return 0
    if arguments.command == "acceleration-suite":
        result = run_acceleration_suite(
            arguments.dataset,
            arguments.canonical,
            arguments.archive,
            arguments.output,
            phase=arguments.phase,
            bootstrap_samples=arguments.bootstrap_samples,
        )
        print(f"M12 verdict: {result['verdict']}")
        return 0
    if arguments.command == "full-loop-hil-suite":
        config = HILConfig(
            steps=arguments.steps,
            seed_count=arguments.seed_count,
            seed_start=arguments.seed_start,
            bootstrap_samples=arguments.bootstrap_samples,
            workers=arguments.workers,
        )
        scenario_names = (
            tuple(
                value.strip()
                for value in arguments.scenarios.split(",")
                if value.strip()
            )
            if arguments.scenarios
            else None
        )
        result = run_full_loop_hil_suite(
            config,
            arguments.output,
            scenario_names=scenario_names,
        )
        print(f"M13.1 verdict: {result['verdict']}")
        print("External physical claim authorized: no")
        return 0
    if arguments.command == "physical-trial-plan":
        dates = tuple(
            value.strip()
            for value in arguments.trial_dates.split(",")
            if value.strip()
        )
        result = create_physical_trial_plan(
            arguments.output,
            phase=arguments.phase,
            blocks_per_scenario=arguments.blocks_per_scenario,
            trial_dates=dates,
        )
        print(
            f"{result['milestone']} {arguments.phase} schedule written to "
            f"{arguments.output}"
        )
        return 0
    if arguments.command == "seal-physical-bundle":
        result = seal_physical_bundle(arguments.bundle)
        print(f"Sealed {arguments.bundle}")
        print(f"Bundle SHA-256: {result['bundle_hash']}")
        return 0
    if arguments.command == "score-physical-bundle":
        result = score_physical_bundle(arguments.bundle)
        print(json.dumps(asdict(result), indent=2, sort_keys=True))
        return 0
    if arguments.command == "physical-pilot":
        result = run_physical_pilot(
            arguments.bundles,
            arguments.output,
            project_root=arguments.project_root,
            target_effect=arguments.target_effect,
            minimum_blocks=arguments.minimum_blocks,
            maximum_blocks=arguments.maximum_blocks,
        )
        print(f"M13.2 status: {result['status']}")
        print(
            "Required held-out blocks per scenario: "
            f"{result['power']['minimum_paired_blocks_per_scenario']}"
        )
        return 0
    if arguments.command == "physical-heldout":
        result = evaluate_physical_holdout(
            arguments.bundles,
            arguments.freeze,
            arguments.output,
            project_root=arguments.project_root,
        )
        print(f"M13.3 verdict: {result['verdict']}")
        return 0

    config = ExperimentConfig.from_json(arguments.config) if arguments.config else ExperimentConfig()
    if arguments.steps is not None:
        config.steps = arguments.steps
        if config.change_step >= config.steps - 1:
            config.change_step = config.steps // 2
    if arguments.seeds:
        config.seeds = [int(value.strip()) for value in arguments.seeds.split(",") if value.strip()]
    if arguments.algorithms:
        config.algorithms = [
            value.strip() for value in arguments.algorithms.split(",") if value.strip()
        ]
    config.validate()
    summary = run_experiment(config, arguments.output)
    print(f"Completed {len(config.algorithms) * len(config.seeds)} runs in {arguments.output}")
    print("Algorithm                         RMSE    Coverage  Recovery  Messages")
    for row in summary:
        print(
            f"{str(row['algorithm']):32} "
            f"{float(row['position_rmse_mean']):7.3f} "
            f"{float(row['coverage95_rate_mean']):9.3f} "
            f"{float(row['recovery_steps_mean']):9.1f} "
            f"{float(row['messages_mean']):9.0f}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
