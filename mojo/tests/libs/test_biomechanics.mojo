"""test_biomechanics.mojo — auto-generated tests for biomechanics library."""
from std.math import isnan, isinf
from biomechanics import joint_torque, angular_velocity, angular_acceleration, moment_of_inertia_limb, ground_reaction_force_ratio, stride_length, cadence_from_velocity, metabolic_cost_walking, joint_power, elastic_energy_tendon, center_of_mass_two_segments, muscle_force_hill

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_joint_torque = joint_torque(0.5, 0.5)
    if is_finite(_v_joint_torque): passed += 1; print("  ✅ biomechanics::joint_torque =", _v_joint_torque)
    else: failed += 1; print("  ❌ biomechanics::joint_torque → non-finite:", _v_joint_torque)
    var _v_angular_velocity = angular_velocity(0.5, 0.5)
    if is_finite(_v_angular_velocity): passed += 1; print("  ✅ biomechanics::angular_velocity =", _v_angular_velocity)
    else: failed += 1; print("  ❌ biomechanics::angular_velocity → non-finite:", _v_angular_velocity)
    var _v_angular_acceleration = angular_acceleration(0.5, 0.5)
    if is_finite(_v_angular_acceleration): passed += 1; print("  ✅ biomechanics::angular_acceleration =", _v_angular_acceleration)
    else: failed += 1; print("  ❌ biomechanics::angular_acceleration → non-finite:", _v_angular_acceleration)
    var _v_moment_of_inertia_limb = moment_of_inertia_limb(0.5, 0.5)
    if is_finite(_v_moment_of_inertia_limb): passed += 1; print("  ✅ biomechanics::moment_of_inertia_limb =", _v_moment_of_inertia_limb)
    else: failed += 1; print("  ❌ biomechanics::moment_of_inertia_limb → non-finite:", _v_moment_of_inertia_limb)
    var _v_ground_reaction_force_ratio = ground_reaction_force_ratio(0.5, 0.5)
    if is_finite(_v_ground_reaction_force_ratio): passed += 1; print("  ✅ biomechanics::ground_reaction_force_ratio =", _v_ground_reaction_force_ratio)
    else: failed += 1; print("  ❌ biomechanics::ground_reaction_force_ratio → non-finite:", _v_ground_reaction_force_ratio)
    var _v_stride_length = stride_length(0.5, 0.5)
    if is_finite(_v_stride_length): passed += 1; print("  ✅ biomechanics::stride_length =", _v_stride_length)
    else: failed += 1; print("  ❌ biomechanics::stride_length → non-finite:", _v_stride_length)
    var _v_cadence_from_velocity = cadence_from_velocity(0.5, 0.5)
    if is_finite(_v_cadence_from_velocity): passed += 1; print("  ✅ biomechanics::cadence_from_velocity =", _v_cadence_from_velocity)
    else: failed += 1; print("  ❌ biomechanics::cadence_from_velocity → non-finite:", _v_cadence_from_velocity)
    var _v_metabolic_cost_walking = metabolic_cost_walking(0.5, 0.5)
    if is_finite(_v_metabolic_cost_walking): passed += 1; print("  ✅ biomechanics::metabolic_cost_walking =", _v_metabolic_cost_walking)
    else: failed += 1; print("  ❌ biomechanics::metabolic_cost_walking → non-finite:", _v_metabolic_cost_walking)
    var _v_joint_power = joint_power(0.5, 0.5)
    if is_finite(_v_joint_power): passed += 1; print("  ✅ biomechanics::joint_power =", _v_joint_power)
    else: failed += 1; print("  ❌ biomechanics::joint_power → non-finite:", _v_joint_power)
    var _v_elastic_energy_tendon = elastic_energy_tendon(0.5, 0.5)
    if is_finite(_v_elastic_energy_tendon): passed += 1; print("  ✅ biomechanics::elastic_energy_tendon =", _v_elastic_energy_tendon)
    else: failed += 1; print("  ❌ biomechanics::elastic_energy_tendon → non-finite:", _v_elastic_energy_tendon)
    var _v_center_of_mass_two_segments = center_of_mass_two_segments(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_center_of_mass_two_segments): passed += 1; print("  ✅ biomechanics::center_of_mass_two_segments =", _v_center_of_mass_two_segments)
    else: failed += 1; print("  ❌ biomechanics::center_of_mass_two_segments → non-finite:", _v_center_of_mass_two_segments)
    var _v_muscle_force_hill = muscle_force_hill(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_muscle_force_hill): passed += 1; print("  ✅ biomechanics::muscle_force_hill =", _v_muscle_force_hill)
    else: failed += 1; print("  ❌ biomechanics::muscle_force_hill → non-finite:", _v_muscle_force_hill)

    print("  [biomechanics] Passed:", passed, "Failed:", failed)
