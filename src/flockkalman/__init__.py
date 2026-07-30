"""Flocking–Kalman research platform."""

from .ambiguity_assay import (
    AmbiguityAssayConfig,
    reanalyze_ambiguity_decision_suite,
    run_ambiguity_assay,
    run_ambiguity_decision_suite,
)
from .active_sensing_suite import (
    ActiveSensingConfig,
    ActiveSensingScenario,
    active_sensing_fingerprint,
    choose_active_sensing_action,
    reanalyze_active_sensing_decision_suite,
    run_active_sensing_decision_suite,
    run_active_sensing_trial,
)
from .admission_evidence import M9A7_ALGORITHM, AdmissionAwareController
from .admission_suite import (
    reanalyze_admission_evidence_suite,
    run_admission_evidence_suite,
)
from .adversarial_trust import (
    AdversarialTrustConfig,
    AdversarialTrustController,
)
from .adversarial_trust_suite import (
    reanalyze_adversarial_trust_suite,
    run_adversarial_trust_suite,
)
from .acceleration_replay import (
    AccelerationConfig,
    AccelerationLandmarkEKF,
    run_acceleration_replay,
    run_jerk_limiter_assay,
)
from .acceleration_suite import run_acceleration_suite
from .closed_loop_trust_suite import (
    reanalyze_closed_loop_trust_suite,
    run_closed_loop_trust_suite,
)
from .config import ExperimentConfig
from .decentralized_sensing import DecentralizedInvestigationController
from .decentralized_suite import (
    reanalyze_decentralized_suite,
    run_decentralized_suite,
)
from .experiment import ALGORITHMS, run_experiment, run_trial
from .external_replay import (
    LandmarkEKF,
    ReplayConfig,
    load_mrclam_dataset,
    run_mrclam_replay,
)
from .external_replay_repair import canonicalize_mrclam_dataset
from .external_replay_repair_suite import run_external_replay_repair_suite
from .external_replay_suite import (
    reanalyze_external_replay_suite,
    run_external_replay_suite,
)
from .guarded_suite import (
    reanalyze_guarded_decision_suite,
    run_guarded_decision_suite,
)
from .integrated_sensing import (
    M9C_RECEDING_ALGORITHM,
    M9C_ROUND_ROBIN_ALGORITHM,
    IntegratedInvestigationController,
)
from .integration_suite import (
    reanalyze_integration_suite,
    run_integration_suite,
)
from .full_loop_contracts import (
    AttackManifest,
    AttackShim,
    DeterministicNetwork,
    HashChainedLedger,
    NetworkFaultManifest,
    SafetyLimits,
    SafetySupervisor,
    TruthSample,
    WireMessage,
)
from .full_loop_hil import (
    DEFAULT_HIL_SCENARIOS,
    HILConfig,
    run_full_loop_hil_suite,
    run_hil_trial,
)
from .full_loop_physical import (
    audit_physical_bundle,
    create_physical_trial_plan,
    evaluate_physical_holdout,
    run_physical_pilot,
    score_physical_bundle,
    seal_physical_bundle,
)
from .momentum_mechanism import (
    recurrence_time_constant,
    run_momentum_mechanism_study,
)
from .missing_evidence import M9A6_ALGORITHM, MissingEvidenceController
from .missing_evidence_suite import (
    reanalyze_missing_evidence_suite,
    run_missing_evidence_suite,
)
from .movement_cost_sweep import analyze_movement_cost_sweep
from .output_suite import (
    reanalyze_output_decision_suite,
    run_output_decision_suite,
)
from .oracle_floor import run_oracle_floor_trial
from .oracle_floor_suite import (
    reanalyze_oracle_floor_suite,
    run_oracle_floor_suite,
)
from .suite import reanalyze_decision_suite, run_decision_suite
from .robust_suite import (
    reanalyze_robust_decision_suite,
    run_robust_decision_suite,
)
from .realism_suite import (
    reanalyze_realism_decision_suite,
    run_realism_decision_suite,
)
from .topology_suite import (
    reanalyze_topology_decision_suite,
    run_topology_decision_suite,
)

__all__ = [
    "ALGORITHMS",
    "ActiveSensingConfig",
    "ActiveSensingScenario",
    "AccelerationConfig",
    "AccelerationLandmarkEKF",
    "AmbiguityAssayConfig",
    "AdversarialTrustConfig",
    "AdversarialTrustController",
    "ExperimentConfig",
    "AttackManifest",
    "AttackShim",
    "DEFAULT_HIL_SCENARIOS",
    "DeterministicNetwork",
    "DecentralizedInvestigationController",
    "HILConfig",
    "HashChainedLedger",
    "LandmarkEKF",
    "M9A6_ALGORITHM",
    "M9A7_ALGORITHM",
    "M9C_RECEDING_ALGORITHM",
    "M9C_ROUND_ROBIN_ALGORITHM",
    "AdmissionAwareController",
    "IntegratedInvestigationController",
    "MissingEvidenceController",
    "NetworkFaultManifest",
    "ReplayConfig",
    "SafetyLimits",
    "SafetySupervisor",
    "TruthSample",
    "WireMessage",
    "active_sensing_fingerprint",
    "analyze_movement_cost_sweep",
    "audit_physical_bundle",
    "choose_active_sensing_action",
    "canonicalize_mrclam_dataset",
    "create_physical_trial_plan",
    "evaluate_physical_holdout",
    "load_mrclam_dataset",
    "reanalyze_active_sensing_decision_suite",
    "reanalyze_admission_evidence_suite",
    "reanalyze_adversarial_trust_suite",
    "reanalyze_closed_loop_trust_suite",
    "reanalyze_decentralized_suite",
    "reanalyze_external_replay_suite",
    "reanalyze_ambiguity_decision_suite",
    "reanalyze_decision_suite",
    "reanalyze_guarded_decision_suite",
    "reanalyze_integration_suite",
    "reanalyze_missing_evidence_suite",
    "reanalyze_output_decision_suite",
    "reanalyze_oracle_floor_suite",
    "reanalyze_realism_decision_suite",
    "reanalyze_robust_decision_suite",
    "reanalyze_topology_decision_suite",
    "recurrence_time_constant",
    "run_active_sensing_decision_suite",
    "run_admission_evidence_suite",
    "run_adversarial_trust_suite",
    "run_acceleration_replay",
    "run_acceleration_suite",
    "run_active_sensing_trial",
    "run_ambiguity_assay",
    "run_ambiguity_decision_suite",
    "run_closed_loop_trust_suite",
    "run_decentralized_suite",
    "run_decision_suite",
    "run_experiment",
    "run_external_replay_repair_suite",
    "run_external_replay_suite",
    "run_full_loop_hil_suite",
    "run_guarded_decision_suite",
    "run_integration_suite",
    "run_hil_trial",
    "run_jerk_limiter_assay",
    "run_mrclam_replay",
    "run_momentum_mechanism_study",
    "run_physical_pilot",
    "run_missing_evidence_suite",
    "run_output_decision_suite",
    "run_oracle_floor_suite",
    "run_oracle_floor_trial",
    "run_realism_decision_suite",
    "run_robust_decision_suite",
    "run_topology_decision_suite",
    "run_trial",
    "score_physical_bundle",
    "seal_physical_bundle",
]
__version__ = "0.19.0"
