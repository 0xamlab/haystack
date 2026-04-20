"""bench_biomechanics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from biomechanics import joint_torque, angular_velocity, angular_acceleration, moment_of_inertia_limb, ground_reaction_force_ratio, stride_length, cadence_from_velocity, metabolic_cost_walking, joint_power, elastic_energy_tendon, center_of_mass_two_segments, muscle_force_hill
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_joint_torque: Float64 = 0.0
    var _t0_joint_torque = perf_counter_ns()
    for _ in range(N):
        _acc_joint_torque += joint_torque(0.5, 0.5)
    var _t1_joint_torque = perf_counter_ns()
    var _ns_joint_torque = Float64(_t1_joint_torque - _t0_joint_torque) / Float64(N)
    print("MOJO_TIMING biomechanics::joint_torque", _ns_joint_torque, _acc_joint_torque)
    var _acc_angular_velocity: Float64 = 0.0
    var _t0_angular_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_angular_velocity += angular_velocity(0.5, 0.5)
    var _t1_angular_velocity = perf_counter_ns()
    var _ns_angular_velocity = Float64(_t1_angular_velocity - _t0_angular_velocity) / Float64(N)
    print("MOJO_TIMING biomechanics::angular_velocity", _ns_angular_velocity, _acc_angular_velocity)
    var _acc_angular_acceleration: Float64 = 0.0
    var _t0_angular_acceleration = perf_counter_ns()
    for _ in range(N):
        _acc_angular_acceleration += angular_acceleration(0.5, 0.5)
    var _t1_angular_acceleration = perf_counter_ns()
    var _ns_angular_acceleration = Float64(_t1_angular_acceleration - _t0_angular_acceleration) / Float64(N)
    print("MOJO_TIMING biomechanics::angular_acceleration", _ns_angular_acceleration, _acc_angular_acceleration)
    var _acc_moment_of_inertia_limb: Float64 = 0.0
    var _t0_moment_of_inertia_limb = perf_counter_ns()
    for _ in range(N):
        _acc_moment_of_inertia_limb += moment_of_inertia_limb(0.5, 0.5)
    var _t1_moment_of_inertia_limb = perf_counter_ns()
    var _ns_moment_of_inertia_limb = Float64(_t1_moment_of_inertia_limb - _t0_moment_of_inertia_limb) / Float64(N)
    print("MOJO_TIMING biomechanics::moment_of_inertia_limb", _ns_moment_of_inertia_limb, _acc_moment_of_inertia_limb)
    var _acc_ground_reaction_force_ratio: Float64 = 0.0
    var _t0_ground_reaction_force_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_ground_reaction_force_ratio += ground_reaction_force_ratio(0.5, 0.5)
    var _t1_ground_reaction_force_ratio = perf_counter_ns()
    var _ns_ground_reaction_force_ratio = Float64(_t1_ground_reaction_force_ratio - _t0_ground_reaction_force_ratio) / Float64(N)
    print("MOJO_TIMING biomechanics::ground_reaction_force_ratio", _ns_ground_reaction_force_ratio, _acc_ground_reaction_force_ratio)
    var _acc_stride_length: Float64 = 0.0
    var _t0_stride_length = perf_counter_ns()
    for _ in range(N):
        _acc_stride_length += stride_length(0.5, 0.5)
    var _t1_stride_length = perf_counter_ns()
    var _ns_stride_length = Float64(_t1_stride_length - _t0_stride_length) / Float64(N)
    print("MOJO_TIMING biomechanics::stride_length", _ns_stride_length, _acc_stride_length)
    var _acc_cadence_from_velocity: Float64 = 0.0
    var _t0_cadence_from_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_cadence_from_velocity += cadence_from_velocity(0.5, 0.5)
    var _t1_cadence_from_velocity = perf_counter_ns()
    var _ns_cadence_from_velocity = Float64(_t1_cadence_from_velocity - _t0_cadence_from_velocity) / Float64(N)
    print("MOJO_TIMING biomechanics::cadence_from_velocity", _ns_cadence_from_velocity, _acc_cadence_from_velocity)
    var _acc_metabolic_cost_walking: Float64 = 0.0
    var _t0_metabolic_cost_walking = perf_counter_ns()
    for _ in range(N):
        _acc_metabolic_cost_walking += metabolic_cost_walking(0.5, 0.5)
    var _t1_metabolic_cost_walking = perf_counter_ns()
    var _ns_metabolic_cost_walking = Float64(_t1_metabolic_cost_walking - _t0_metabolic_cost_walking) / Float64(N)
    print("MOJO_TIMING biomechanics::metabolic_cost_walking", _ns_metabolic_cost_walking, _acc_metabolic_cost_walking)
    var _acc_joint_power: Float64 = 0.0
    var _t0_joint_power = perf_counter_ns()
    for _ in range(N):
        _acc_joint_power += joint_power(0.5, 0.5)
    var _t1_joint_power = perf_counter_ns()
    var _ns_joint_power = Float64(_t1_joint_power - _t0_joint_power) / Float64(N)
    print("MOJO_TIMING biomechanics::joint_power", _ns_joint_power, _acc_joint_power)
    var _acc_elastic_energy_tendon: Float64 = 0.0
    var _t0_elastic_energy_tendon = perf_counter_ns()
    for _ in range(N):
        _acc_elastic_energy_tendon += elastic_energy_tendon(0.5, 0.5)
    var _t1_elastic_energy_tendon = perf_counter_ns()
    var _ns_elastic_energy_tendon = Float64(_t1_elastic_energy_tendon - _t0_elastic_energy_tendon) / Float64(N)
    print("MOJO_TIMING biomechanics::elastic_energy_tendon", _ns_elastic_energy_tendon, _acc_elastic_energy_tendon)
    var _acc_center_of_mass_two_segments: Float64 = 0.0
    var _t0_center_of_mass_two_segments = perf_counter_ns()
    for _ in range(N):
        _acc_center_of_mass_two_segments += center_of_mass_two_segments(0.5, 0.5, 0.5, 0.5)
    var _t1_center_of_mass_two_segments = perf_counter_ns()
    var _ns_center_of_mass_two_segments = Float64(_t1_center_of_mass_two_segments - _t0_center_of_mass_two_segments) / Float64(N)
    print("MOJO_TIMING biomechanics::center_of_mass_two_segments", _ns_center_of_mass_two_segments, _acc_center_of_mass_two_segments)
    var _acc_muscle_force_hill: Float64 = 0.0
    var _t0_muscle_force_hill = perf_counter_ns()
    for _ in range(N):
        _acc_muscle_force_hill += muscle_force_hill(0.5, 0.5, 0.5, 0.5)
    var _t1_muscle_force_hill = perf_counter_ns()
    var _ns_muscle_force_hill = Float64(_t1_muscle_force_hill - _t0_muscle_force_hill) / Float64(N)
    print("MOJO_TIMING biomechanics::muscle_force_hill", _ns_muscle_force_hill, _acc_muscle_force_hill)
