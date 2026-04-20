"""bench_plasma_physics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from plasma_physics import debye_length, plasma_frequency, thermal_velocity, larmor_radius, coulomb_logarithm, spitzer_resistivity, alfven_speed, mhd_beta, fusion_lawson_criterion, bremsstrahlung_power
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

    var _acc_debye_length: Float64 = 0.0
    var _t0_debye_length = perf_counter_ns()
    for _ in range(N):
        _acc_debye_length += debye_length(0.5, 0.5)
    var _t1_debye_length = perf_counter_ns()
    var _ns_debye_length = Float64(_t1_debye_length - _t0_debye_length) / Float64(N)
    print("MOJO_TIMING plasma_physics::debye_length", _ns_debye_length, _acc_debye_length)
    var _acc_plasma_frequency: Float64 = 0.0
    var _t0_plasma_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_plasma_frequency += plasma_frequency(0.5)
    var _t1_plasma_frequency = perf_counter_ns()
    var _ns_plasma_frequency = Float64(_t1_plasma_frequency - _t0_plasma_frequency) / Float64(N)
    print("MOJO_TIMING plasma_physics::plasma_frequency", _ns_plasma_frequency, _acc_plasma_frequency)
    var _acc_thermal_velocity: Float64 = 0.0
    var _t0_thermal_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_velocity += thermal_velocity(0.5, 0.5)
    var _t1_thermal_velocity = perf_counter_ns()
    var _ns_thermal_velocity = Float64(_t1_thermal_velocity - _t0_thermal_velocity) / Float64(N)
    print("MOJO_TIMING plasma_physics::thermal_velocity", _ns_thermal_velocity, _acc_thermal_velocity)
    var _acc_larmor_radius: Float64 = 0.0
    var _t0_larmor_radius = perf_counter_ns()
    for _ in range(N):
        _acc_larmor_radius += larmor_radius(0.5, 0.5, 0.5, 0.5)
    var _t1_larmor_radius = perf_counter_ns()
    var _ns_larmor_radius = Float64(_t1_larmor_radius - _t0_larmor_radius) / Float64(N)
    print("MOJO_TIMING plasma_physics::larmor_radius", _ns_larmor_radius, _acc_larmor_radius)
    var _acc_coulomb_logarithm: Float64 = 0.0
    var _t0_coulomb_logarithm = perf_counter_ns()
    for _ in range(N):
        _acc_coulomb_logarithm += coulomb_logarithm(0.5, 0.5)
    var _t1_coulomb_logarithm = perf_counter_ns()
    var _ns_coulomb_logarithm = Float64(_t1_coulomb_logarithm - _t0_coulomb_logarithm) / Float64(N)
    print("MOJO_TIMING plasma_physics::coulomb_logarithm", _ns_coulomb_logarithm, _acc_coulomb_logarithm)
    var _acc_spitzer_resistivity: Float64 = 0.0
    var _t0_spitzer_resistivity = perf_counter_ns()
    for _ in range(N):
        _acc_spitzer_resistivity += spitzer_resistivity(0.5, 0.5)
    var _t1_spitzer_resistivity = perf_counter_ns()
    var _ns_spitzer_resistivity = Float64(_t1_spitzer_resistivity - _t0_spitzer_resistivity) / Float64(N)
    print("MOJO_TIMING plasma_physics::spitzer_resistivity", _ns_spitzer_resistivity, _acc_spitzer_resistivity)
    var _acc_alfven_speed: Float64 = 0.0
    var _t0_alfven_speed = perf_counter_ns()
    for _ in range(N):
        _acc_alfven_speed += alfven_speed(0.5, 0.5)
    var _t1_alfven_speed = perf_counter_ns()
    var _ns_alfven_speed = Float64(_t1_alfven_speed - _t0_alfven_speed) / Float64(N)
    print("MOJO_TIMING plasma_physics::alfven_speed", _ns_alfven_speed, _acc_alfven_speed)
    var _acc_mhd_beta: Float64 = 0.0
    var _t0_mhd_beta = perf_counter_ns()
    for _ in range(N):
        _acc_mhd_beta += mhd_beta(0.5, 0.5, 0.5)
    var _t1_mhd_beta = perf_counter_ns()
    var _ns_mhd_beta = Float64(_t1_mhd_beta - _t0_mhd_beta) / Float64(N)
    print("MOJO_TIMING plasma_physics::mhd_beta", _ns_mhd_beta, _acc_mhd_beta)
    var _acc_fusion_lawson_criterion: Float64 = 0.0
    var _t0_fusion_lawson_criterion = perf_counter_ns()
    for _ in range(N):
        _acc_fusion_lawson_criterion += fusion_lawson_criterion(0.5, 0.5)
    var _t1_fusion_lawson_criterion = perf_counter_ns()
    var _ns_fusion_lawson_criterion = Float64(_t1_fusion_lawson_criterion - _t0_fusion_lawson_criterion) / Float64(N)
    print("MOJO_TIMING plasma_physics::fusion_lawson_criterion", _ns_fusion_lawson_criterion, _acc_fusion_lawson_criterion)
    var _acc_bremsstrahlung_power: Float64 = 0.0
    var _t0_bremsstrahlung_power = perf_counter_ns()
    for _ in range(N):
        _acc_bremsstrahlung_power += bremsstrahlung_power(0.5, 0.5, 0.5, 0.5)
    var _t1_bremsstrahlung_power = perf_counter_ns()
    var _ns_bremsstrahlung_power = Float64(_t1_bremsstrahlung_power - _t0_bremsstrahlung_power) / Float64(N)
    print("MOJO_TIMING plasma_physics::bremsstrahlung_power", _ns_bremsstrahlung_power, _acc_bremsstrahlung_power)
