"""
biomechanics.mojo — Biomechanics Library. Zero Python imports.

Pure Mojo implementations of fundamental biomechanics equations including
joint torque, angular kinematics, moment of inertia, ground reaction force,
gait analysis, metabolic cost, joint power, tendon elasticity, centre of
mass, and Hill muscle model.

Public API:
  joint_torque                — τ = F·d
  angular_velocity            — ω = θ/t
  angular_acceleration        — α = Δω/t
  moment_of_inertia_limb     — I ≈ m·L²/3
  ground_reaction_force_ratio — GRF / BW
  stride_length               — SL from velocity & cadence
  cadence_from_velocity       — cadence from velocity & SL
  metabolic_cost_walking      — simplified walking cost (W)
  joint_power                 — P = τ·ω
  elastic_energy_tendon       — E = 0.5·k·x²
  center_of_mass_two_segments — CoM of two segments
  muscle_force_hill           — Hill muscle model force
"""
from std.math import sqrt, abs as fabs


# ── joint_torque ─────────────────────────────────────────────────────────────


fn joint_torque(force: Float64, moment_arm: Float64) -> Float64:
    """τ = F · d  (N·m)."""
    return force * moment_arm


# ── angular_velocity ─────────────────────────────────────────────────────────


fn angular_velocity(angular_displacement: Float64, time: Float64) -> Float64:
    """ω = θ / t  (rad/s)."""
    return angular_displacement / time


# ── angular_acceleration ─────────────────────────────────────────────────────


fn angular_acceleration(delta_omega: Float64, time: Float64) -> Float64:
    """α = Δω / t  (rad/s²)."""
    return delta_omega / time


# ── moment_of_inertia_limb ──────────────────────────────────────────────────


fn moment_of_inertia_limb(mass: Float64, length: Float64) -> Float64:
    """I ≈ m · L² / 3  (rod about end)."""
    return mass * length * length / 3.0


# ── ground_reaction_force_ratio ──────────────────────────────────────────────


fn ground_reaction_force_ratio(grf: Float64, body_weight: Float64) -> Float64:
    """Ratio = GRF / BW."""
    return grf / body_weight


# ── stride_length ────────────────────────────────────────────────────────────


fn stride_length(velocity: Float64, cadence_steps_per_min: Float64) -> Float64:
    """SL = v * 60 / (cadence / 2)  metres."""
    return velocity * 60.0 / (cadence_steps_per_min / 2.0)


# ── cadence_from_velocity ────────────────────────────────────────────────────


fn cadence_from_velocity(velocity: Float64, stride_len: Float64) -> Float64:
    """Cadence = (v / SL) * 2 * 60  steps/min."""
    return (velocity / stride_len) * 2.0 * 60.0


# ── metabolic_cost_walking ───────────────────────────────────────────────────


fn metabolic_cost_walking(mass: Float64, velocity: Float64) -> Float64:
    """E ≈ 2.5·mass + 3.0·mass·velocity²  (W, simplified)."""
    return 2.5 * mass + 3.0 * mass * velocity * velocity


# ── joint_power ──────────────────────────────────────────────────────────────


fn joint_power(torque: Float64, angular_vel: Float64) -> Float64:
    """P = τ · ω  (watts)."""
    return torque * angular_vel


# ── elastic_energy_tendon ────────────────────────────────────────────────────


fn elastic_energy_tendon(stiffness: Float64, deformation: Float64) -> Float64:
    """E = 0.5 · k · x²  (joules)."""
    return 0.5 * stiffness * deformation * deformation


# ── center_of_mass_two_segments ──────────────────────────────────────────────


fn center_of_mass_two_segments(m1: Float64, x1: Float64,
                                m2: Float64, x2: Float64) -> Float64:
    """CoM = (m1·x1 + m2·x2) / (m1 + m2)."""
    return (m1 * x1 + m2 * x2) / (m1 + m2)


# ── muscle_force_hill ────────────────────────────────────────────────────────


fn muscle_force_hill(fmax: Float64, velocity: Float64,
                     vmax: Float64, a_hill: Float64) -> Float64:
    """F = Fmax · (vmax - v) / (vmax + v / a_hill)  (simplified Hill model)."""
    return fmax * (vmax - velocity) / (vmax + velocity / a_hill)
