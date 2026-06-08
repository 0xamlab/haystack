"""bench_biomechanics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from biomechanics import joint_torque, angular_velocity, angular_acceleration, moment_of_inertia_limb, ground_reaction_force_ratio, stride_length, cadence_from_velocity, metabolic_cost_walking, joint_power, elastic_energy_tendon, center_of_mass_two_segments, muscle_force_hill
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_joint_torque = joint_torque(0.5, 0.5)
    var _summary_joint_torque = _summary_float64(_result_joint_torque)
    print("MOJO_RESULT biomechanics::joint_torque", _summary_joint_torque)
    var _acc_angular_velocity: Float64 = 0.0
    var _t0_angular_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_angular_velocity += angular_velocity(0.5, 0.5)
    var _t1_angular_velocity = perf_counter_ns()
    var _ns_angular_velocity = Float64(_t1_angular_velocity - _t0_angular_velocity) / Float64(N)
    print("MOJO_TIMING biomechanics::angular_velocity", _ns_angular_velocity, _acc_angular_velocity)
    var _result_angular_velocity = angular_velocity(0.5, 0.5)
    var _summary_angular_velocity = _summary_float64(_result_angular_velocity)
    print("MOJO_RESULT biomechanics::angular_velocity", _summary_angular_velocity)
    var _acc_angular_acceleration: Float64 = 0.0
    var _t0_angular_acceleration = perf_counter_ns()
    for _ in range(N):
        _acc_angular_acceleration += angular_acceleration(0.5, 0.5)
    var _t1_angular_acceleration = perf_counter_ns()
    var _ns_angular_acceleration = Float64(_t1_angular_acceleration - _t0_angular_acceleration) / Float64(N)
    print("MOJO_TIMING biomechanics::angular_acceleration", _ns_angular_acceleration, _acc_angular_acceleration)
    var _result_angular_acceleration = angular_acceleration(0.5, 0.5)
    var _summary_angular_acceleration = _summary_float64(_result_angular_acceleration)
    print("MOJO_RESULT biomechanics::angular_acceleration", _summary_angular_acceleration)
    var _acc_moment_of_inertia_limb: Float64 = 0.0
    var _t0_moment_of_inertia_limb = perf_counter_ns()
    for _ in range(N):
        _acc_moment_of_inertia_limb += moment_of_inertia_limb(0.5, 0.5)
    var _t1_moment_of_inertia_limb = perf_counter_ns()
    var _ns_moment_of_inertia_limb = Float64(_t1_moment_of_inertia_limb - _t0_moment_of_inertia_limb) / Float64(N)
    print("MOJO_TIMING biomechanics::moment_of_inertia_limb", _ns_moment_of_inertia_limb, _acc_moment_of_inertia_limb)
    var _result_moment_of_inertia_limb = moment_of_inertia_limb(0.5, 0.5)
    var _summary_moment_of_inertia_limb = _summary_float64(_result_moment_of_inertia_limb)
    print("MOJO_RESULT biomechanics::moment_of_inertia_limb", _summary_moment_of_inertia_limb)
    var _acc_ground_reaction_force_ratio: Float64 = 0.0
    var _t0_ground_reaction_force_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_ground_reaction_force_ratio += ground_reaction_force_ratio(0.5, 0.5)
    var _t1_ground_reaction_force_ratio = perf_counter_ns()
    var _ns_ground_reaction_force_ratio = Float64(_t1_ground_reaction_force_ratio - _t0_ground_reaction_force_ratio) / Float64(N)
    print("MOJO_TIMING biomechanics::ground_reaction_force_ratio", _ns_ground_reaction_force_ratio, _acc_ground_reaction_force_ratio)
    var _result_ground_reaction_force_ratio = ground_reaction_force_ratio(0.5, 0.5)
    var _summary_ground_reaction_force_ratio = _summary_float64(_result_ground_reaction_force_ratio)
    print("MOJO_RESULT biomechanics::ground_reaction_force_ratio", _summary_ground_reaction_force_ratio)
    var _acc_stride_length: Float64 = 0.0
    var _t0_stride_length = perf_counter_ns()
    for _ in range(N):
        _acc_stride_length += stride_length(0.5, 0.5)
    var _t1_stride_length = perf_counter_ns()
    var _ns_stride_length = Float64(_t1_stride_length - _t0_stride_length) / Float64(N)
    print("MOJO_TIMING biomechanics::stride_length", _ns_stride_length, _acc_stride_length)
    var _result_stride_length = stride_length(0.5, 0.5)
    var _summary_stride_length = _summary_float64(_result_stride_length)
    print("MOJO_RESULT biomechanics::stride_length", _summary_stride_length)
    var _acc_cadence_from_velocity: Float64 = 0.0
    var _t0_cadence_from_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_cadence_from_velocity += cadence_from_velocity(0.5, 0.5)
    var _t1_cadence_from_velocity = perf_counter_ns()
    var _ns_cadence_from_velocity = Float64(_t1_cadence_from_velocity - _t0_cadence_from_velocity) / Float64(N)
    print("MOJO_TIMING biomechanics::cadence_from_velocity", _ns_cadence_from_velocity, _acc_cadence_from_velocity)
    var _result_cadence_from_velocity = cadence_from_velocity(0.5, 0.5)
    var _summary_cadence_from_velocity = _summary_float64(_result_cadence_from_velocity)
    print("MOJO_RESULT biomechanics::cadence_from_velocity", _summary_cadence_from_velocity)
    var _acc_metabolic_cost_walking: Float64 = 0.0
    var _t0_metabolic_cost_walking = perf_counter_ns()
    for _ in range(N):
        _acc_metabolic_cost_walking += metabolic_cost_walking(0.5, 0.5)
    var _t1_metabolic_cost_walking = perf_counter_ns()
    var _ns_metabolic_cost_walking = Float64(_t1_metabolic_cost_walking - _t0_metabolic_cost_walking) / Float64(N)
    print("MOJO_TIMING biomechanics::metabolic_cost_walking", _ns_metabolic_cost_walking, _acc_metabolic_cost_walking)
    var _result_metabolic_cost_walking = metabolic_cost_walking(0.5, 0.5)
    var _summary_metabolic_cost_walking = _summary_float64(_result_metabolic_cost_walking)
    print("MOJO_RESULT biomechanics::metabolic_cost_walking", _summary_metabolic_cost_walking)
    var _acc_joint_power: Float64 = 0.0
    var _t0_joint_power = perf_counter_ns()
    for _ in range(N):
        _acc_joint_power += joint_power(0.5, 0.5)
    var _t1_joint_power = perf_counter_ns()
    var _ns_joint_power = Float64(_t1_joint_power - _t0_joint_power) / Float64(N)
    print("MOJO_TIMING biomechanics::joint_power", _ns_joint_power, _acc_joint_power)
    var _result_joint_power = joint_power(0.5, 0.5)
    var _summary_joint_power = _summary_float64(_result_joint_power)
    print("MOJO_RESULT biomechanics::joint_power", _summary_joint_power)
    var _acc_elastic_energy_tendon: Float64 = 0.0
    var _t0_elastic_energy_tendon = perf_counter_ns()
    for _ in range(N):
        _acc_elastic_energy_tendon += elastic_energy_tendon(0.5, 0.5)
    var _t1_elastic_energy_tendon = perf_counter_ns()
    var _ns_elastic_energy_tendon = Float64(_t1_elastic_energy_tendon - _t0_elastic_energy_tendon) / Float64(N)
    print("MOJO_TIMING biomechanics::elastic_energy_tendon", _ns_elastic_energy_tendon, _acc_elastic_energy_tendon)
    var _result_elastic_energy_tendon = elastic_energy_tendon(0.5, 0.5)
    var _summary_elastic_energy_tendon = _summary_float64(_result_elastic_energy_tendon)
    print("MOJO_RESULT biomechanics::elastic_energy_tendon", _summary_elastic_energy_tendon)
    var _acc_center_of_mass_two_segments: Float64 = 0.0
    var _t0_center_of_mass_two_segments = perf_counter_ns()
    for _ in range(N):
        _acc_center_of_mass_two_segments += center_of_mass_two_segments(0.5, 0.5, 0.5, 0.5)
    var _t1_center_of_mass_two_segments = perf_counter_ns()
    var _ns_center_of_mass_two_segments = Float64(_t1_center_of_mass_two_segments - _t0_center_of_mass_two_segments) / Float64(N)
    print("MOJO_TIMING biomechanics::center_of_mass_two_segments", _ns_center_of_mass_two_segments, _acc_center_of_mass_two_segments)
    var _result_center_of_mass_two_segments = center_of_mass_two_segments(0.5, 0.5, 0.5, 0.5)
    var _summary_center_of_mass_two_segments = _summary_float64(_result_center_of_mass_two_segments)
    print("MOJO_RESULT biomechanics::center_of_mass_two_segments", _summary_center_of_mass_two_segments)
    var _acc_muscle_force_hill: Float64 = 0.0
    var _t0_muscle_force_hill = perf_counter_ns()
    for _ in range(N):
        _acc_muscle_force_hill += muscle_force_hill(0.5, 0.5, 0.5, 0.5)
    var _t1_muscle_force_hill = perf_counter_ns()
    var _ns_muscle_force_hill = Float64(_t1_muscle_force_hill - _t0_muscle_force_hill) / Float64(N)
    print("MOJO_TIMING biomechanics::muscle_force_hill", _ns_muscle_force_hill, _acc_muscle_force_hill)
    var _result_muscle_force_hill = muscle_force_hill(0.5, 0.5, 0.5, 0.5)
    var _summary_muscle_force_hill = _summary_float64(_result_muscle_force_hill)
    print("MOJO_RESULT biomechanics::muscle_force_hill", _summary_muscle_force_hill)
