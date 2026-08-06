"""bench_physics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from physics import kinematic_distance, kinematic_velocity, kinetic_energy, potential_energy, momentum, gravitational_force, projectile_range, projectile_max_height, projectile_time, work, power, elastic_collision_v1
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_kinematic_distance: Float64 = 0.0
    var _t0_kinematic_distance = perf_counter_ns()
    for _ in range(N):
        _acc_kinematic_distance += kinematic_distance(0.5, 0.5, 0.5)
    var _t1_kinematic_distance = perf_counter_ns()
    var _ns_kinematic_distance = Float64(_t1_kinematic_distance - _t0_kinematic_distance) / Float64(N)
    print("MOJO_TIMING physics::kinematic_distance", _ns_kinematic_distance, _acc_kinematic_distance)
    var _result_kinematic_distance = kinematic_distance(0.5, 0.5, 0.5)
    var _summary_kinematic_distance = _summary_float64(_result_kinematic_distance)
    print("MOJO_RESULT physics::kinematic_distance", _summary_kinematic_distance)
    var _acc_kinematic_velocity: Float64 = 0.0
    var _t0_kinematic_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_kinematic_velocity += kinematic_velocity(0.5, 0.5, 0.5)
    var _t1_kinematic_velocity = perf_counter_ns()
    var _ns_kinematic_velocity = Float64(_t1_kinematic_velocity - _t0_kinematic_velocity) / Float64(N)
    print("MOJO_TIMING physics::kinematic_velocity", _ns_kinematic_velocity, _acc_kinematic_velocity)
    var _result_kinematic_velocity = kinematic_velocity(0.5, 0.5, 0.5)
    var _summary_kinematic_velocity = _summary_float64(_result_kinematic_velocity)
    print("MOJO_RESULT physics::kinematic_velocity", _summary_kinematic_velocity)
    var _acc_kinetic_energy: Float64 = 0.0
    var _t0_kinetic_energy = perf_counter_ns()
    for _ in range(N):
        _acc_kinetic_energy += kinetic_energy(0.5, 0.5)
    var _t1_kinetic_energy = perf_counter_ns()
    var _ns_kinetic_energy = Float64(_t1_kinetic_energy - _t0_kinetic_energy) / Float64(N)
    print("MOJO_TIMING physics::kinetic_energy", _ns_kinetic_energy, _acc_kinetic_energy)
    var _result_kinetic_energy = kinetic_energy(0.5, 0.5)
    var _summary_kinetic_energy = _summary_float64(_result_kinetic_energy)
    print("MOJO_RESULT physics::kinetic_energy", _summary_kinetic_energy)
    var _acc_potential_energy: Float64 = 0.0
    var _t0_potential_energy = perf_counter_ns()
    for _ in range(N):
        _acc_potential_energy += potential_energy(0.5, 0.5, 0.5)
    var _t1_potential_energy = perf_counter_ns()
    var _ns_potential_energy = Float64(_t1_potential_energy - _t0_potential_energy) / Float64(N)
    print("MOJO_TIMING physics::potential_energy", _ns_potential_energy, _acc_potential_energy)
    var _result_potential_energy = potential_energy(0.5, 0.5, 0.5)
    var _summary_potential_energy = _summary_float64(_result_potential_energy)
    print("MOJO_RESULT physics::potential_energy", _summary_potential_energy)
    var _acc_momentum: Float64 = 0.0
    var _t0_momentum = perf_counter_ns()
    for _ in range(N):
        _acc_momentum += momentum(0.5, 0.5)
    var _t1_momentum = perf_counter_ns()
    var _ns_momentum = Float64(_t1_momentum - _t0_momentum) / Float64(N)
    print("MOJO_TIMING physics::momentum", _ns_momentum, _acc_momentum)
    var _result_momentum = momentum(0.5, 0.5)
    var _summary_momentum = _summary_float64(_result_momentum)
    print("MOJO_RESULT physics::momentum", _summary_momentum)
    var _acc_gravitational_force: Float64 = 0.0
    var _t0_gravitational_force = perf_counter_ns()
    for _ in range(N):
        _acc_gravitational_force += gravitational_force(0.5, 0.5, 0.5)
    var _t1_gravitational_force = perf_counter_ns()
    var _ns_gravitational_force = Float64(_t1_gravitational_force - _t0_gravitational_force) / Float64(N)
    print("MOJO_TIMING physics::gravitational_force", _ns_gravitational_force, _acc_gravitational_force)
    var _result_gravitational_force = gravitational_force(0.5, 0.5, 0.5)
    var _summary_gravitational_force = _summary_float64(_result_gravitational_force)
    print("MOJO_RESULT physics::gravitational_force", _summary_gravitational_force)
    var _acc_projectile_range: Float64 = 0.0
    var _t0_projectile_range = perf_counter_ns()
    for _ in range(N):
        _acc_projectile_range += projectile_range(0.5, 0.5, 0.5)
    var _t1_projectile_range = perf_counter_ns()
    var _ns_projectile_range = Float64(_t1_projectile_range - _t0_projectile_range) / Float64(N)
    print("MOJO_TIMING physics::projectile_range", _ns_projectile_range, _acc_projectile_range)
    var _result_projectile_range = projectile_range(0.5, 0.5, 0.5)
    var _summary_projectile_range = _summary_float64(_result_projectile_range)
    print("MOJO_RESULT physics::projectile_range", _summary_projectile_range)
    var _acc_projectile_max_height: Float64 = 0.0
    var _t0_projectile_max_height = perf_counter_ns()
    for _ in range(N):
        _acc_projectile_max_height += projectile_max_height(0.5, 0.5, 0.5)
    var _t1_projectile_max_height = perf_counter_ns()
    var _ns_projectile_max_height = Float64(_t1_projectile_max_height - _t0_projectile_max_height) / Float64(N)
    print("MOJO_TIMING physics::projectile_max_height", _ns_projectile_max_height, _acc_projectile_max_height)
    var _result_projectile_max_height = projectile_max_height(0.5, 0.5, 0.5)
    var _summary_projectile_max_height = _summary_float64(_result_projectile_max_height)
    print("MOJO_RESULT physics::projectile_max_height", _summary_projectile_max_height)
    var _acc_projectile_time: Float64 = 0.0
    var _t0_projectile_time = perf_counter_ns()
    for _ in range(N):
        _acc_projectile_time += projectile_time(0.5, 0.5, 0.5)
    var _t1_projectile_time = perf_counter_ns()
    var _ns_projectile_time = Float64(_t1_projectile_time - _t0_projectile_time) / Float64(N)
    print("MOJO_TIMING physics::projectile_time", _ns_projectile_time, _acc_projectile_time)
    var _result_projectile_time = projectile_time(0.5, 0.5, 0.5)
    var _summary_projectile_time = _summary_float64(_result_projectile_time)
    print("MOJO_RESULT physics::projectile_time", _summary_projectile_time)
    var _acc_work: Float64 = 0.0
    var _t0_work = perf_counter_ns()
    for _ in range(N):
        _acc_work += work(0.5, 0.5, 0.5)
    var _t1_work = perf_counter_ns()
    var _ns_work = Float64(_t1_work - _t0_work) / Float64(N)
    print("MOJO_TIMING physics::work", _ns_work, _acc_work)
    var _result_work = work(0.5, 0.5, 0.5)
    var _summary_work = _summary_float64(_result_work)
    print("MOJO_RESULT physics::work", _summary_work)
    var _acc_power: Float64 = 0.0
    var _t0_power = perf_counter_ns()
    for _ in range(N):
        _acc_power += power(0.5, 0.5)
    var _t1_power = perf_counter_ns()
    var _ns_power = Float64(_t1_power - _t0_power) / Float64(N)
    print("MOJO_TIMING physics::power", _ns_power, _acc_power)
    var _result_power = power(0.5, 0.5)
    var _summary_power = _summary_float64(_result_power)
    print("MOJO_RESULT physics::power", _summary_power)
    var _acc_elastic_collision_v1: Float64 = 0.0
    var _t0_elastic_collision_v1 = perf_counter_ns()
    for _ in range(N):
        _acc_elastic_collision_v1 += elastic_collision_v1(0.5, 0.5, 0.5, 0.5)
    var _t1_elastic_collision_v1 = perf_counter_ns()
    var _ns_elastic_collision_v1 = Float64(_t1_elastic_collision_v1 - _t0_elastic_collision_v1) / Float64(N)
    print("MOJO_TIMING physics::elastic_collision_v1", _ns_elastic_collision_v1, _acc_elastic_collision_v1)
    var _result_elastic_collision_v1 = elastic_collision_v1(0.5, 0.5, 0.5, 0.5)
    var _summary_elastic_collision_v1 = _summary_float64(_result_elastic_collision_v1)
    print("MOJO_RESULT physics::elastic_collision_v1", _summary_elastic_collision_v1)
