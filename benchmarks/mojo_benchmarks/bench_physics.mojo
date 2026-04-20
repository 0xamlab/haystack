"""bench_physics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from physics import kinematic_distance, kinematic_velocity, kinetic_energy, potential_energy, momentum, gravitational_force, projectile_range, projectile_max_height, projectile_time, work, power, elastic_collision_v1
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

    var _acc_kinematic_distance: Float64 = 0.0
    var _t0_kinematic_distance = perf_counter_ns()
    for _ in range(N):
        _acc_kinematic_distance += kinematic_distance(0.5, 0.5, 0.5)
    var _t1_kinematic_distance = perf_counter_ns()
    var _ns_kinematic_distance = Float64(_t1_kinematic_distance - _t0_kinematic_distance) / Float64(N)
    print("MOJO_TIMING physics::kinematic_distance", _ns_kinematic_distance, _acc_kinematic_distance)
    var _acc_kinematic_velocity: Float64 = 0.0
    var _t0_kinematic_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_kinematic_velocity += kinematic_velocity(0.5, 0.5, 0.5)
    var _t1_kinematic_velocity = perf_counter_ns()
    var _ns_kinematic_velocity = Float64(_t1_kinematic_velocity - _t0_kinematic_velocity) / Float64(N)
    print("MOJO_TIMING physics::kinematic_velocity", _ns_kinematic_velocity, _acc_kinematic_velocity)
    var _acc_kinetic_energy: Float64 = 0.0
    var _t0_kinetic_energy = perf_counter_ns()
    for _ in range(N):
        _acc_kinetic_energy += kinetic_energy(0.5, 0.5)
    var _t1_kinetic_energy = perf_counter_ns()
    var _ns_kinetic_energy = Float64(_t1_kinetic_energy - _t0_kinetic_energy) / Float64(N)
    print("MOJO_TIMING physics::kinetic_energy", _ns_kinetic_energy, _acc_kinetic_energy)
    var _acc_potential_energy: Float64 = 0.0
    var _t0_potential_energy = perf_counter_ns()
    for _ in range(N):
        _acc_potential_energy += potential_energy(0.5, 0.5, 0.5)
    var _t1_potential_energy = perf_counter_ns()
    var _ns_potential_energy = Float64(_t1_potential_energy - _t0_potential_energy) / Float64(N)
    print("MOJO_TIMING physics::potential_energy", _ns_potential_energy, _acc_potential_energy)
    var _acc_momentum: Float64 = 0.0
    var _t0_momentum = perf_counter_ns()
    for _ in range(N):
        _acc_momentum += momentum(0.5, 0.5)
    var _t1_momentum = perf_counter_ns()
    var _ns_momentum = Float64(_t1_momentum - _t0_momentum) / Float64(N)
    print("MOJO_TIMING physics::momentum", _ns_momentum, _acc_momentum)
    var _acc_gravitational_force: Float64 = 0.0
    var _t0_gravitational_force = perf_counter_ns()
    for _ in range(N):
        _acc_gravitational_force += gravitational_force(0.5, 0.5, 0.5)
    var _t1_gravitational_force = perf_counter_ns()
    var _ns_gravitational_force = Float64(_t1_gravitational_force - _t0_gravitational_force) / Float64(N)
    print("MOJO_TIMING physics::gravitational_force", _ns_gravitational_force, _acc_gravitational_force)
    var _acc_projectile_range: Float64 = 0.0
    var _t0_projectile_range = perf_counter_ns()
    for _ in range(N):
        _acc_projectile_range += projectile_range(0.5, 0.5, 0.5)
    var _t1_projectile_range = perf_counter_ns()
    var _ns_projectile_range = Float64(_t1_projectile_range - _t0_projectile_range) / Float64(N)
    print("MOJO_TIMING physics::projectile_range", _ns_projectile_range, _acc_projectile_range)
    var _acc_projectile_max_height: Float64 = 0.0
    var _t0_projectile_max_height = perf_counter_ns()
    for _ in range(N):
        _acc_projectile_max_height += projectile_max_height(0.5, 0.5, 0.5)
    var _t1_projectile_max_height = perf_counter_ns()
    var _ns_projectile_max_height = Float64(_t1_projectile_max_height - _t0_projectile_max_height) / Float64(N)
    print("MOJO_TIMING physics::projectile_max_height", _ns_projectile_max_height, _acc_projectile_max_height)
    var _acc_projectile_time: Float64 = 0.0
    var _t0_projectile_time = perf_counter_ns()
    for _ in range(N):
        _acc_projectile_time += projectile_time(0.5, 0.5, 0.5)
    var _t1_projectile_time = perf_counter_ns()
    var _ns_projectile_time = Float64(_t1_projectile_time - _t0_projectile_time) / Float64(N)
    print("MOJO_TIMING physics::projectile_time", _ns_projectile_time, _acc_projectile_time)
    var _acc_work: Float64 = 0.0
    var _t0_work = perf_counter_ns()
    for _ in range(N):
        _acc_work += work(0.5, 0.5, 0.5)
    var _t1_work = perf_counter_ns()
    var _ns_work = Float64(_t1_work - _t0_work) / Float64(N)
    print("MOJO_TIMING physics::work", _ns_work, _acc_work)
    var _acc_power: Float64 = 0.0
    var _t0_power = perf_counter_ns()
    for _ in range(N):
        _acc_power += power(0.5, 0.5)
    var _t1_power = perf_counter_ns()
    var _ns_power = Float64(_t1_power - _t0_power) / Float64(N)
    print("MOJO_TIMING physics::power", _ns_power, _acc_power)
    var _acc_elastic_collision_v1: Float64 = 0.0
    var _t0_elastic_collision_v1 = perf_counter_ns()
    for _ in range(N):
        _acc_elastic_collision_v1 += elastic_collision_v1(0.5, 0.5, 0.5, 0.5)
    var _t1_elastic_collision_v1 = perf_counter_ns()
    var _ns_elastic_collision_v1 = Float64(_t1_elastic_collision_v1 - _t0_elastic_collision_v1) / Float64(N)
    print("MOJO_TIMING physics::elastic_collision_v1", _ns_elastic_collision_v1, _acc_elastic_collision_v1)
