"""bench_marine.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from marine import seawater_density, wave_speed_deep, wave_speed_shallow, wave_period, significant_wave_height, tidal_range, mixed_layer_depth_estimate, ekman_depth, coriolis_parameter, buoyancy_frequency, salinity_from_conductivity, ocean_pressure_at_depth
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

    var _acc_seawater_density: Float64 = 0.0
    var _t0_seawater_density = perf_counter_ns()
    for _ in range(N):
        _acc_seawater_density += seawater_density(0.5, 0.5)
    var _t1_seawater_density = perf_counter_ns()
    var _ns_seawater_density = Float64(_t1_seawater_density - _t0_seawater_density) / Float64(N)
    print("MOJO_TIMING marine::seawater_density", _ns_seawater_density, _acc_seawater_density)
    var _acc_wave_speed_deep: Float64 = 0.0
    var _t0_wave_speed_deep = perf_counter_ns()
    for _ in range(N):
        _acc_wave_speed_deep += wave_speed_deep(0.5, 0.5)
    var _t1_wave_speed_deep = perf_counter_ns()
    var _ns_wave_speed_deep = Float64(_t1_wave_speed_deep - _t0_wave_speed_deep) / Float64(N)
    print("MOJO_TIMING marine::wave_speed_deep", _ns_wave_speed_deep, _acc_wave_speed_deep)
    var _acc_wave_speed_shallow: Float64 = 0.0
    var _t0_wave_speed_shallow = perf_counter_ns()
    for _ in range(N):
        _acc_wave_speed_shallow += wave_speed_shallow(0.5, 0.5)
    var _t1_wave_speed_shallow = perf_counter_ns()
    var _ns_wave_speed_shallow = Float64(_t1_wave_speed_shallow - _t0_wave_speed_shallow) / Float64(N)
    print("MOJO_TIMING marine::wave_speed_shallow", _ns_wave_speed_shallow, _acc_wave_speed_shallow)
    var _acc_wave_period: Float64 = 0.0
    var _t0_wave_period = perf_counter_ns()
    for _ in range(N):
        _acc_wave_period += wave_period(0.5, 0.5)
    var _t1_wave_period = perf_counter_ns()
    var _ns_wave_period = Float64(_t1_wave_period - _t0_wave_period) / Float64(N)
    print("MOJO_TIMING marine::wave_period", _ns_wave_period, _acc_wave_period)
    var _acc_significant_wave_height: Float64 = 0.0
    var _t0_significant_wave_height = perf_counter_ns()
    for _ in range(N):
        _acc_significant_wave_height += significant_wave_height(0.5)
    var _t1_significant_wave_height = perf_counter_ns()
    var _ns_significant_wave_height = Float64(_t1_significant_wave_height - _t0_significant_wave_height) / Float64(N)
    print("MOJO_TIMING marine::significant_wave_height", _ns_significant_wave_height, _acc_significant_wave_height)
    var _acc_tidal_range: Float64 = 0.0
    var _t0_tidal_range = perf_counter_ns()
    for _ in range(N):
        _acc_tidal_range += tidal_range(0.5, 0.5)
    var _t1_tidal_range = perf_counter_ns()
    var _ns_tidal_range = Float64(_t1_tidal_range - _t0_tidal_range) / Float64(N)
    print("MOJO_TIMING marine::tidal_range", _ns_tidal_range, _acc_tidal_range)
    var _acc_mixed_layer_depth_estimate: Float64 = 0.0
    var _t0_mixed_layer_depth_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_mixed_layer_depth_estimate += mixed_layer_depth_estimate(0.5, 0.5)
    var _t1_mixed_layer_depth_estimate = perf_counter_ns()
    var _ns_mixed_layer_depth_estimate = Float64(_t1_mixed_layer_depth_estimate - _t0_mixed_layer_depth_estimate) / Float64(N)
    print("MOJO_TIMING marine::mixed_layer_depth_estimate", _ns_mixed_layer_depth_estimate, _acc_mixed_layer_depth_estimate)
    var _acc_ekman_depth: Float64 = 0.0
    var _t0_ekman_depth = perf_counter_ns()
    for _ in range(N):
        _acc_ekman_depth += ekman_depth(0.5, 0.5, 0.5)
    var _t1_ekman_depth = perf_counter_ns()
    var _ns_ekman_depth = Float64(_t1_ekman_depth - _t0_ekman_depth) / Float64(N)
    print("MOJO_TIMING marine::ekman_depth", _ns_ekman_depth, _acc_ekman_depth)
    var _acc_coriolis_parameter: Float64 = 0.0
    var _t0_coriolis_parameter = perf_counter_ns()
    for _ in range(N):
        _acc_coriolis_parameter += coriolis_parameter(0.5)
    var _t1_coriolis_parameter = perf_counter_ns()
    var _ns_coriolis_parameter = Float64(_t1_coriolis_parameter - _t0_coriolis_parameter) / Float64(N)
    print("MOJO_TIMING marine::coriolis_parameter", _ns_coriolis_parameter, _acc_coriolis_parameter)
    var _acc_buoyancy_frequency: Float64 = 0.0
    var _t0_buoyancy_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_buoyancy_frequency += buoyancy_frequency(0.5, 0.5, 0.5)
    var _t1_buoyancy_frequency = perf_counter_ns()
    var _ns_buoyancy_frequency = Float64(_t1_buoyancy_frequency - _t0_buoyancy_frequency) / Float64(N)
    print("MOJO_TIMING marine::buoyancy_frequency", _ns_buoyancy_frequency, _acc_buoyancy_frequency)
    var _acc_salinity_from_conductivity: Float64 = 0.0
    var _t0_salinity_from_conductivity = perf_counter_ns()
    for _ in range(N):
        _acc_salinity_from_conductivity += salinity_from_conductivity(0.5, 0.5)
    var _t1_salinity_from_conductivity = perf_counter_ns()
    var _ns_salinity_from_conductivity = Float64(_t1_salinity_from_conductivity - _t0_salinity_from_conductivity) / Float64(N)
    print("MOJO_TIMING marine::salinity_from_conductivity", _ns_salinity_from_conductivity, _acc_salinity_from_conductivity)
    var _acc_ocean_pressure_at_depth: Float64 = 0.0
    var _t0_ocean_pressure_at_depth = perf_counter_ns()
    for _ in range(N):
        _acc_ocean_pressure_at_depth += ocean_pressure_at_depth(0.5, 0.5, 0.5)
    var _t1_ocean_pressure_at_depth = perf_counter_ns()
    var _ns_ocean_pressure_at_depth = Float64(_t1_ocean_pressure_at_depth - _t0_ocean_pressure_at_depth) / Float64(N)
    print("MOJO_TIMING marine::ocean_pressure_at_depth", _ns_ocean_pressure_at_depth, _acc_ocean_pressure_at_depth)
