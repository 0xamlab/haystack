"""bench_wind_energy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from wind_energy import wind_power_available, betz_limit, power_coefficient, tip_speed_ratio, swept_area, annual_energy_production, capacity_factor, wind_shear_power_law, weibull_mean_wind_speed, energy_density, rotor_thrust, wake_velocity
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

    var _acc_wind_power_available: Float64 = 0.0
    var _t0_wind_power_available = perf_counter_ns()
    for _ in range(N):
        _acc_wind_power_available += wind_power_available(0.5, 0.5, 0.5)
    var _t1_wind_power_available = perf_counter_ns()
    var _ns_wind_power_available = Float64(_t1_wind_power_available - _t0_wind_power_available) / Float64(N)
    print("MOJO_TIMING wind_energy::wind_power_available", _ns_wind_power_available, _acc_wind_power_available)
    var _acc_betz_limit: Float64 = 0.0
    var _t0_betz_limit = perf_counter_ns()
    for _ in range(N):
        _acc_betz_limit += betz_limit()
    var _t1_betz_limit = perf_counter_ns()
    var _ns_betz_limit = Float64(_t1_betz_limit - _t0_betz_limit) / Float64(N)
    print("MOJO_TIMING wind_energy::betz_limit", _ns_betz_limit, _acc_betz_limit)
    var _acc_power_coefficient: Float64 = 0.0
    var _t0_power_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_power_coefficient += power_coefficient(0.5, 0.5)
    var _t1_power_coefficient = perf_counter_ns()
    var _ns_power_coefficient = Float64(_t1_power_coefficient - _t0_power_coefficient) / Float64(N)
    print("MOJO_TIMING wind_energy::power_coefficient", _ns_power_coefficient, _acc_power_coefficient)
    var _acc_tip_speed_ratio: Float64 = 0.0
    var _t0_tip_speed_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_tip_speed_ratio += tip_speed_ratio(0.5, 0.5, 0.5)
    var _t1_tip_speed_ratio = perf_counter_ns()
    var _ns_tip_speed_ratio = Float64(_t1_tip_speed_ratio - _t0_tip_speed_ratio) / Float64(N)
    print("MOJO_TIMING wind_energy::tip_speed_ratio", _ns_tip_speed_ratio, _acc_tip_speed_ratio)
    var _acc_swept_area: Float64 = 0.0
    var _t0_swept_area = perf_counter_ns()
    for _ in range(N):
        _acc_swept_area += swept_area(0.5)
    var _t1_swept_area = perf_counter_ns()
    var _ns_swept_area = Float64(_t1_swept_area - _t0_swept_area) / Float64(N)
    print("MOJO_TIMING wind_energy::swept_area", _ns_swept_area, _acc_swept_area)
    var _acc_annual_energy_production: Float64 = 0.0
    var _t0_annual_energy_production = perf_counter_ns()
    for _ in range(N):
        _acc_annual_energy_production += annual_energy_production(0.5, 0.5, 0.5)
    var _t1_annual_energy_production = perf_counter_ns()
    var _ns_annual_energy_production = Float64(_t1_annual_energy_production - _t0_annual_energy_production) / Float64(N)
    print("MOJO_TIMING wind_energy::annual_energy_production", _ns_annual_energy_production, _acc_annual_energy_production)
    var _acc_capacity_factor: Float64 = 0.0
    var _t0_capacity_factor = perf_counter_ns()
    for _ in range(N):
        _acc_capacity_factor += capacity_factor(0.5, 0.5, 0.5)
    var _t1_capacity_factor = perf_counter_ns()
    var _ns_capacity_factor = Float64(_t1_capacity_factor - _t0_capacity_factor) / Float64(N)
    print("MOJO_TIMING wind_energy::capacity_factor", _ns_capacity_factor, _acc_capacity_factor)
    var _acc_wind_shear_power_law: Float64 = 0.0
    var _t0_wind_shear_power_law = perf_counter_ns()
    for _ in range(N):
        _acc_wind_shear_power_law += wind_shear_power_law(0.5, 0.5, 0.5, 0.5)
    var _t1_wind_shear_power_law = perf_counter_ns()
    var _ns_wind_shear_power_law = Float64(_t1_wind_shear_power_law - _t0_wind_shear_power_law) / Float64(N)
    print("MOJO_TIMING wind_energy::wind_shear_power_law", _ns_wind_shear_power_law, _acc_wind_shear_power_law)
    var _acc_weibull_mean_wind_speed: Float64 = 0.0
    var _t0_weibull_mean_wind_speed = perf_counter_ns()
    for _ in range(N):
        _acc_weibull_mean_wind_speed += weibull_mean_wind_speed(0.5, 0.5)
    var _t1_weibull_mean_wind_speed = perf_counter_ns()
    var _ns_weibull_mean_wind_speed = Float64(_t1_weibull_mean_wind_speed - _t0_weibull_mean_wind_speed) / Float64(N)
    print("MOJO_TIMING wind_energy::weibull_mean_wind_speed", _ns_weibull_mean_wind_speed, _acc_weibull_mean_wind_speed)
    var _acc_energy_density: Float64 = 0.0
    var _t0_energy_density = perf_counter_ns()
    for _ in range(N):
        _acc_energy_density += energy_density(0.5, 0.5)
    var _t1_energy_density = perf_counter_ns()
    var _ns_energy_density = Float64(_t1_energy_density - _t0_energy_density) / Float64(N)
    print("MOJO_TIMING wind_energy::energy_density", _ns_energy_density, _acc_energy_density)
    var _acc_rotor_thrust: Float64 = 0.0
    var _t0_rotor_thrust = perf_counter_ns()
    for _ in range(N):
        _acc_rotor_thrust += rotor_thrust(0.5, 0.5, 0.5, 0.5)
    var _t1_rotor_thrust = perf_counter_ns()
    var _ns_rotor_thrust = Float64(_t1_rotor_thrust - _t0_rotor_thrust) / Float64(N)
    print("MOJO_TIMING wind_energy::rotor_thrust", _ns_rotor_thrust, _acc_rotor_thrust)
    var _acc_wake_velocity: Float64 = 0.0
    var _t0_wake_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_wake_velocity += wake_velocity(0.5, 0.5, 0.5, 0.5)
    var _t1_wake_velocity = perf_counter_ns()
    var _ns_wake_velocity = Float64(_t1_wake_velocity - _t0_wake_velocity) / Float64(N)
    print("MOJO_TIMING wind_energy::wake_velocity", _ns_wake_velocity, _acc_wake_velocity)
