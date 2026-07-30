"""Deterministic manoeuvring-target scenario and range-dependent observations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import numpy as np
from numpy.typing import NDArray

from .config import ExperimentConfig
from .provenance import (
    DEFAULT_FLOAT_TOLERANCE,
    FINGERPRINT_V1,
    FINGERPRINT_V2,
    ReplayVerification,
    digest_arrays,
    verify_replay,
)


FloatArray = NDArray[np.float64]


@dataclass(slots=True)
class Scenario:
    truth: FloatArray
    measurement_normals: FloatArray
    measurement_uniforms: FloatArray
    communication_uniforms: FloatArray
    communication_available: NDArray[np.bool_]
    message_ages: NDArray[np.int64]
    agent_clock_offsets: NDArray[np.int64]
    sensor_noise_scales: FloatArray
    agent_active: NDArray[np.bool_]
    initial_sensor_positions: FloatArray
    initial_sensor_velocities: FloatArray
    initial_belief_offsets: FloatArray
    agent_fault_types: NDArray[np.int64]


def make_scenario(config: ExperimentConfig, seed: int) -> Scenario:
    """Create common random numbers so every algorithm sees a fair trial."""
    rng = np.random.default_rng(seed)
    truth = np.zeros((config.steps, 4), dtype=float)
    truth[0] = np.asarray(config.target_initial_state, dtype=float)
    process_normals = rng.normal(size=(config.steps, 2))

    repeated_event = 0
    for step in range(1, config.steps):
        previous = truth[step - 1].copy()
        if config.target_change_mode == "abrupt" and step == config.change_step:
            previous[2:4] += np.asarray(config.target_velocity_change, dtype=float)
        elif (
            config.target_change_mode == "gradual"
            and config.change_step <= step < config.change_step + config.gradual_change_duration
        ):
            previous[2:4] += (
                np.asarray(config.target_velocity_change, dtype=float)
                / config.gradual_change_duration
            )
        elif (
            config.target_change_mode == "repeated"
            and step >= config.change_step
            and (step - config.change_step) % config.repeated_change_interval == 0
        ):
            angles = (70.0, -110.0, 95.0, -80.0)
            angle = np.deg2rad(angles[repeated_event % len(angles)])
            rotation = np.array(
                [[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]],
                dtype=float,
            )
            previous[2:4] = rotation @ previous[2:4]
            repeated_event += 1
        acceleration = config.truth_process_std * process_normals[step]
        truth[step, :2] = (
            previous[:2]
            + previous[2:4] * config.dt
            + 0.5 * acceleration * config.dt**2
        )
        truth[step, 2:4] = previous[2:4] + acceleration * config.dt

    angles = np.linspace(0.0, 2.0 * np.pi, config.n_agents, endpoint=False)
    sensor_positions = np.column_stack((np.cos(angles), np.sin(angles)))
    sensor_positions *= config.initial_sensor_radius
    sensor_positions += truth[0, :2]

    offsets = np.empty((config.n_agents, 4), dtype=float)
    offsets[:, :2] = rng.normal(
        scale=config.initial_belief_position_std, size=(config.n_agents, 2)
    )
    offsets[:, 2:4] = rng.normal(
        scale=config.initial_belief_velocity_std, size=(config.n_agents, 2)
    )
    measurement_uniforms = rng.uniform(size=(config.steps, config.n_agents))
    measurement_uniforms[0] = 1.0  # Every method starts from an observed state.
    # Fault identities are randomized per seed. This prevents deterministic
    # agent ordering from leaking the truth when equally supported modes tie.
    fault_types = np.zeros(config.n_agents, dtype=np.int64)
    permutation = rng.permutation(config.n_agents)
    cursor = 0
    fault_types[permutation[cursor : cursor + config.biased_agent_count]] = 1
    cursor += config.biased_agent_count
    fault_types[permutation[cursor : cursor + config.byzantine_agent_count]] = 2
    cursor += config.byzantine_agent_count
    fault_types[permutation[cursor : cursor + config.secondary_mode_agent_count]] = 3
    cursor += config.secondary_mode_agent_count
    fault_types[permutation[cursor : cursor + config.strategic_agent_count]] = 4

    # Preserve the original random stream for legacy scenarios. M8-only random
    # variables use a separate deterministic stream, so all-zero realism knobs
    # reproduce M7 exactly.
    measurement_normals = rng.normal(size=(config.steps, config.n_agents, 2))
    communication_uniforms = rng.uniform(
        size=(config.steps, config.n_agents, config.n_agents)
    )
    realism_rng = np.random.default_rng(np.random.SeedSequence([seed, 8, 2026]))

    burst_failed = np.zeros((config.n_agents, config.n_agents), dtype=bool)
    communication_available = np.zeros_like(communication_uniforms, dtype=bool)
    burst_entry = realism_rng.uniform(size=communication_uniforms.shape)
    burst_recovery = realism_rng.uniform(size=communication_uniforms.shape)
    for step in range(config.steps):
        recovered = burst_failed & (
            burst_recovery[step] < config.communication_burst_recovery_probability
        )
        entered = (~burst_failed) & (
            burst_entry[step] < config.communication_burst_entry_probability
        )
        burst_failed = (burst_failed & ~recovered) | entered
        np.fill_diagonal(burst_failed, False)
        communication_available[step] = (
            communication_uniforms[step] >= config.communication_dropout_rate
        ) & ~burst_failed
        np.fill_diagonal(communication_available[step], False)

    if config.agent_clock_offset_max_steps:
        agent_clock_offsets = realism_rng.integers(
            -config.agent_clock_offset_max_steps,
            config.agent_clock_offset_max_steps + 1,
            size=config.n_agents,
            dtype=np.int64,
        )
    else:
        agent_clock_offsets = np.zeros(config.n_agents, dtype=np.int64)
    if config.communication_delay_jitter_steps:
        delay_jitter = realism_rng.integers(
            0,
            config.communication_delay_jitter_steps + 1,
            size=(config.steps, config.n_agents),
            dtype=np.int64,
        )
    else:
        delay_jitter = np.zeros((config.steps, config.n_agents), dtype=np.int64)
    message_ages = np.maximum(
        0,
        config.communication_delay_steps
        + delay_jitter
        + agent_clock_offsets[np.newaxis, :],
    ).astype(np.int64)

    if config.sensor_noise_scale_min == config.sensor_noise_scale_max:
        sensor_noise_scales = np.full(
            config.n_agents, config.sensor_noise_scale_min, dtype=float
        )
    else:
        sensor_noise_scales = realism_rng.uniform(
            config.sensor_noise_scale_min,
            config.sensor_noise_scale_max,
            size=config.n_agents,
        )

    agent_active = np.ones((config.steps, config.n_agents), dtype=bool)
    if config.agent_failure_count:
        failure_candidates = (
            np.flatnonzero(fault_types == config.agent_failure_fault_type)
            if config.agent_failure_fault_type != -1
            else np.arange(config.n_agents, dtype=np.int64)
        )
        failure_agents = realism_rng.permutation(failure_candidates)[
            : config.agent_failure_count
        ]
        for order, agent in enumerate(failure_agents):
            failure_end = (
                config.steps
                if config.agent_recovery_step < 0
                else min(
                    config.steps,
                    config.agent_recovery_step
                    + order * config.agent_recovery_stagger_steps,
                )
            )
            agent_active[config.agent_failure_step : failure_end, agent] = False
    return Scenario(
        truth=truth,
        measurement_normals=measurement_normals,
        measurement_uniforms=measurement_uniforms,
        communication_uniforms=communication_uniforms,
        communication_available=communication_available,
        message_ages=message_ages,
        agent_clock_offsets=agent_clock_offsets,
        sensor_noise_scales=sensor_noise_scales,
        agent_active=agent_active,
        initial_sensor_positions=sensor_positions,
        initial_sensor_velocities=np.zeros((config.n_agents, 2), dtype=float),
        initial_belief_offsets=offsets,
        agent_fault_types=fault_types,
    )


def measurement_covariance(
    config: ExperimentConfig,
    sensor_position: FloatArray,
    target_position: FloatArray,
    sensor_noise_scale: float = 1.0,
) -> FloatArray:
    distance = float(np.linalg.norm(sensor_position - target_position))
    standard_deviation = config.measurement_base_std * sensor_noise_scale * (
        1.0 + distance / config.measurement_distance_scale
    )
    return np.eye(2, dtype=float) * standard_deviation**2


def observe(
    config: ExperimentConfig,
    step: int,
    target_position: FloatArray,
    sensor_positions: FloatArray,
    standard_normals: FloatArray,
    availability_uniforms: FloatArray,
    agent_fault_types: NDArray[np.int64],
    sensor_noise_scales: FloatArray | None = None,
    agent_active: NDArray[np.bool_] | None = None,
) -> tuple[FloatArray, list[FloatArray], NDArray[np.bool_]]:
    observations = np.zeros_like(sensor_positions)
    covariances: list[FloatArray] = []
    available = availability_uniforms >= config.measurement_dropout_rate
    if agent_active is not None:
        available &= agent_active
    if sensor_noise_scales is None:
        sensor_noise_scales = np.ones(len(sensor_positions), dtype=float)
    bias = np.asarray(config.measurement_bias, dtype=float)
    bias_drift = np.asarray(config.measurement_bias_drift, dtype=float)
    byzantine_offset = np.asarray(config.byzantine_offset, dtype=float)
    secondary_offset = np.asarray(config.secondary_mode_offset, dtype=float)
    strategic_direction = np.asarray(config.strategic_offset_direction, dtype=float)
    strategic_direction /= np.linalg.norm(strategic_direction)
    for index, position in enumerate(sensor_positions):
        distance = float(np.linalg.norm(position - target_position))
        noise_scale = float(sensor_noise_scales[index])
        physical_covariance = measurement_covariance(
            config, position, target_position, noise_scale
        )
        covariance = physical_covariance.copy()
        if config.measurement_model == "cartesian":
            observations[index] = (
                target_position
                + np.sqrt(physical_covariance[0, 0]) * standard_normals[index]
            )
        else:
            delta = target_position - position
            true_bearing = float(np.arctan2(delta[1], delta[0]))
            range_std = config.measurement_base_std * noise_scale * (
                1.0 + distance / config.measurement_distance_scale
            )
            bearing_std = config.bearing_base_std * noise_scale * np.sqrt(
                1.0 + distance / config.measurement_distance_scale
            )
            measured_range = max(
                0.01, distance + range_std * standard_normals[index, 0]
            )
            measured_bearing = (
                true_bearing + bearing_std * standard_normals[index, 1]
            )
            cosine = float(np.cos(measured_bearing))
            sine = float(np.sin(measured_bearing))
            # Exact first and second moments for independent Gaussian range
            # and bearing noise. Dividing by E[cos(noise)] removes the usual
            # inward conversion bias; the reported Cartesian covariance then
            # matches that unbiased converted measurement rather than relying
            # on a fragile first-order Jacobian.
            bearing_attenuation = float(np.exp(-0.5 * bearing_std**2))
            relative_observation = (
                measured_range
                * np.array([cosine, sine], dtype=float)
                / bearing_attenuation
            )
            observations[index] = position + relative_observation
            radial_second_moment = distance**2 + range_std**2
            double_bearing_attenuation = float(np.exp(-2.0 * bearing_std**2))
            cosine_two = float(np.cos(2.0 * true_bearing))
            sine_two = float(np.sin(2.0 * true_bearing))
            scale = radial_second_moment / (2.0 * bearing_attenuation**2)
            second_moment = scale * np.array(
                [
                    [
                        1.0 + double_bearing_attenuation * cosine_two,
                        double_bearing_attenuation * sine_two,
                    ],
                    [
                        double_bearing_attenuation * sine_two,
                        1.0 - double_bearing_attenuation * cosine_two,
                    ],
                ],
                dtype=float,
            )
            true_delta = target_position - position
            covariance = (
                second_moment
                - np.outer(true_delta, true_delta)
                + np.eye(2, dtype=float) * 1e-6
            )
            covariance = 0.5 * (covariance + covariance.T)
        if agent_fault_types[index] == 1 and (
            config.biased_agent_recovery_step < 0
            or step < config.biased_agent_recovery_step
        ):
            observations[index] += bias + step * bias_drift
        elif agent_fault_types[index] == 2:
            observations[index] += byzantine_offset
            covariance *= config.byzantine_covariance_scale
        elif (
            agent_fault_types[index] == 3
            and step >= config.secondary_mode_start_step
            and (
                config.secondary_mode_end_step < 0
                or step < config.secondary_mode_end_step
            )
        ):
            observations[index] += secondary_offset
        elif agent_fault_types[index] == 4:
            ramp = min(1.0, (step + 1) / config.strategic_ramp_steps)
            observations[index] += (
                strategic_direction * config.strategic_offset_magnitude * ramp
            )
            covariance *= config.strategic_covariance_scale
        covariances.append(covariance)
    return observations, covariances, available


def scenario_fingerprint(
    config: ExperimentConfig,
    seed: int,
    *,
    algorithm: str = FINGERPRINT_V1,
    tolerance: float = DEFAULT_FLOAT_TOLERANCE,
) -> str:
    """Hash a fully materialized scenario for deterministic trace replay.

    The default is deliberately :data:`~.provenance.FINGERPRINT_V1`, the legacy
    bit-exact algorithm, so that every historical artifact keeps verifying. New
    suites should pass ``algorithm=CURRENT_FINGERPRINT_ALGORITHM`` and record the
    choice alongside the fingerprint; see :mod:`flockkalman.provenance` for why
    the default is not simply flipped.
    """
    scenario = make_scenario(config, seed)
    digest = hashlib.sha256()
    digest.update(
        json.dumps(config.to_dict(), sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )
    digest.update(str(seed).encode("ascii"))
    if algorithm == FINGERPRINT_V2:
        # Bind the algorithm and quantum into the digest so a v2 fingerprint can
        # never be silently compared against a v1 one, or against a v2 computed
        # at a different tolerance.
        digest.update(FINGERPRINT_V2.encode("ascii"))
        digest.update(repr(float(tolerance)).encode("ascii"))
    digest_arrays(
        (
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
        ),
        algorithm=algorithm,
        tolerance=tolerance,
        digest=digest,
    )
    return digest.hexdigest()


def verify_scenario_replay(
    rows: "list[dict[str, object]]",
    suite: "dict[str, object]",
    *,
    fingerprint_key: str = "trace_fingerprint",
) -> ReplayVerification:
    """Verify recorded scenario fingerprints for a saved suite (M14.3).

    Shared by every suite that carries a ``replay`` validity gate, so the
    environment-mismatch distinction is implemented once rather than six times.
    The recorded environment and fingerprint algorithm are read from the
    artifact; a pre-M14 artifact declares no algorithm and is therefore treated
    as ``v1-raw-bytes``.
    """
    configs = dict(suite.get("scenario_configs", {}))  # type: ignore[arg-type]

    def expected(row: "dict[str, object]", algorithm: str) -> str:
        config = ExperimentConfig(**configs[str(row["scenario"])])
        return scenario_fingerprint(config, int(row["seed"]), algorithm=algorithm)

    recorded_environment = {
        key: suite[key]
        for key in ("python", "numpy", "platform", "machine")
        if key in suite
    }
    return verify_replay(
        rows,
        expected=expected,
        recorded_environment=recorded_environment or None,
        recorded_algorithm=str(suite["fingerprint_algorithm"])
        if suite.get("fingerprint_algorithm")
        else None,
        fingerprint_key=fingerprint_key,
    )
