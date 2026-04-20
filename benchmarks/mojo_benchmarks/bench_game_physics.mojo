"""bench_game_physics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from game_physics import position_update, velocity_update, verlet_position, elastic_collision_1d, coefficient_of_restitution, kinetic_energy, gravitational_force, projectile_range, drag_force_quadratic, spring_force, angular_velocity_from_linear, moment_of_inertia_sphere
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

    var _acc_position_update: Float64 = 0.0
    var _t0_position_update = perf_counter_ns()
    for _ in range(N):
        _acc_position_update += position_update(0.5, 0.5, 0.5, 0.5)
    var _t1_position_update = perf_counter_ns()
    var _ns_position_update = Float64(_t1_position_update - _t0_position_update) / Float64(N)
    print("MOJO_TIMING game_physics::position_update", _ns_position_update, _acc_position_update)
    var _acc_velocity_update: Float64 = 0.0
    var _t0_velocity_update = perf_counter_ns()
    for _ in range(N):
        _acc_velocity_update += velocity_update(0.5, 0.5, 0.5)
    var _t1_velocity_update = perf_counter_ns()
    var _ns_velocity_update = Float64(_t1_velocity_update - _t0_velocity_update) / Float64(N)
    print("MOJO_TIMING game_physics::velocity_update", _ns_velocity_update, _acc_velocity_update)
    var _acc_verlet_position: Float64 = 0.0
    var _t0_verlet_position = perf_counter_ns()
    for _ in range(N):
        _acc_verlet_position += verlet_position(0.5, 0.5, 0.5, 0.5)
    var _t1_verlet_position = perf_counter_ns()
    var _ns_verlet_position = Float64(_t1_verlet_position - _t0_verlet_position) / Float64(N)
    print("MOJO_TIMING game_physics::verlet_position", _ns_verlet_position, _acc_verlet_position)
    var _acc_elastic_collision_1d: Float64 = 0.0
    var _t0_elastic_collision_1d = perf_counter_ns()
    for _ in range(N):
        _acc_elastic_collision_1d += elastic_collision_1d(0.5, 0.5, 0.5, 0.5)
    var _t1_elastic_collision_1d = perf_counter_ns()
    var _ns_elastic_collision_1d = Float64(_t1_elastic_collision_1d - _t0_elastic_collision_1d) / Float64(N)
    print("MOJO_TIMING game_physics::elastic_collision_1d", _ns_elastic_collision_1d, _acc_elastic_collision_1d)
    var _acc_coefficient_of_restitution: Float64 = 0.0
    var _t0_coefficient_of_restitution = perf_counter_ns()
    for _ in range(N):
        _acc_coefficient_of_restitution += coefficient_of_restitution(0.5, 0.5)
    var _t1_coefficient_of_restitution = perf_counter_ns()
    var _ns_coefficient_of_restitution = Float64(_t1_coefficient_of_restitution - _t0_coefficient_of_restitution) / Float64(N)
    print("MOJO_TIMING game_physics::coefficient_of_restitution", _ns_coefficient_of_restitution, _acc_coefficient_of_restitution)
    var _acc_kinetic_energy: Float64 = 0.0
    var _t0_kinetic_energy = perf_counter_ns()
    for _ in range(N):
        _acc_kinetic_energy += kinetic_energy(0.5, 0.5)
    var _t1_kinetic_energy = perf_counter_ns()
    var _ns_kinetic_energy = Float64(_t1_kinetic_energy - _t0_kinetic_energy) / Float64(N)
    print("MOJO_TIMING game_physics::kinetic_energy", _ns_kinetic_energy, _acc_kinetic_energy)
    var _acc_gravitational_force: Float64 = 0.0
    var _t0_gravitational_force = perf_counter_ns()
    for _ in range(N):
        _acc_gravitational_force += gravitational_force(0.5, 0.5, 0.5, 0.5)
    var _t1_gravitational_force = perf_counter_ns()
    var _ns_gravitational_force = Float64(_t1_gravitational_force - _t0_gravitational_force) / Float64(N)
    print("MOJO_TIMING game_physics::gravitational_force", _ns_gravitational_force, _acc_gravitational_force)
    var _acc_projectile_range: Float64 = 0.0
    var _t0_projectile_range = perf_counter_ns()
    for _ in range(N):
        _acc_projectile_range += projectile_range(0.5, 0.5, 0.5)
    var _t1_projectile_range = perf_counter_ns()
    var _ns_projectile_range = Float64(_t1_projectile_range - _t0_projectile_range) / Float64(N)
    print("MOJO_TIMING game_physics::projectile_range", _ns_projectile_range, _acc_projectile_range)
    var _acc_drag_force_quadratic: Float64 = 0.0
    var _t0_drag_force_quadratic = perf_counter_ns()
    for _ in range(N):
        _acc_drag_force_quadratic += drag_force_quadratic(0.5, 0.5, 0.5, 0.5)
    var _t1_drag_force_quadratic = perf_counter_ns()
    var _ns_drag_force_quadratic = Float64(_t1_drag_force_quadratic - _t0_drag_force_quadratic) / Float64(N)
    print("MOJO_TIMING game_physics::drag_force_quadratic", _ns_drag_force_quadratic, _acc_drag_force_quadratic)
    var _acc_spring_force: Float64 = 0.0
    var _t0_spring_force = perf_counter_ns()
    for _ in range(N):
        _acc_spring_force += spring_force(0.5, 0.5)
    var _t1_spring_force = perf_counter_ns()
    var _ns_spring_force = Float64(_t1_spring_force - _t0_spring_force) / Float64(N)
    print("MOJO_TIMING game_physics::spring_force", _ns_spring_force, _acc_spring_force)
    var _acc_angular_velocity_from_linear: Float64 = 0.0
    var _t0_angular_velocity_from_linear = perf_counter_ns()
    for _ in range(N):
        _acc_angular_velocity_from_linear += angular_velocity_from_linear(0.5, 0.5)
    var _t1_angular_velocity_from_linear = perf_counter_ns()
    var _ns_angular_velocity_from_linear = Float64(_t1_angular_velocity_from_linear - _t0_angular_velocity_from_linear) / Float64(N)
    print("MOJO_TIMING game_physics::angular_velocity_from_linear", _ns_angular_velocity_from_linear, _acc_angular_velocity_from_linear)
    var _acc_moment_of_inertia_sphere: Float64 = 0.0
    var _t0_moment_of_inertia_sphere = perf_counter_ns()
    for _ in range(N):
        _acc_moment_of_inertia_sphere += moment_of_inertia_sphere(0.5, 0.5)
    var _t1_moment_of_inertia_sphere = perf_counter_ns()
    var _ns_moment_of_inertia_sphere = Float64(_t1_moment_of_inertia_sphere - _t0_moment_of_inertia_sphere) / Float64(N)
    print("MOJO_TIMING game_physics::moment_of_inertia_sphere", _ns_moment_of_inertia_sphere, _acc_moment_of_inertia_sphere)
