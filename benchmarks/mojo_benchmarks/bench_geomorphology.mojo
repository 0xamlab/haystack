"""bench_geomorphology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from geomorphology import stream_power, shear_stress_flow, shields_parameter, settling_velocity_stokes, erosion_rate_spl, hillslope_diffusion, drainage_density, relief_ratio, sinuosity, hack_law_length, ruggedness_number, hypsometric_integral
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

    var _acc_stream_power: Float64 = 0.0
    var _t0_stream_power = perf_counter_ns()
    for _ in range(N):
        _acc_stream_power += stream_power(0.5, 0.5, 0.5, 0.5)
    var _t1_stream_power = perf_counter_ns()
    var _ns_stream_power = Float64(_t1_stream_power - _t0_stream_power) / Float64(N)
    print("MOJO_TIMING geomorphology::stream_power", _ns_stream_power, _acc_stream_power)
    var _acc_shear_stress_flow: Float64 = 0.0
    var _t0_shear_stress_flow = perf_counter_ns()
    for _ in range(N):
        _acc_shear_stress_flow += shear_stress_flow(0.5, 0.5, 0.5, 0.5)
    var _t1_shear_stress_flow = perf_counter_ns()
    var _ns_shear_stress_flow = Float64(_t1_shear_stress_flow - _t0_shear_stress_flow) / Float64(N)
    print("MOJO_TIMING geomorphology::shear_stress_flow", _ns_shear_stress_flow, _acc_shear_stress_flow)
    var _acc_shields_parameter: Float64 = 0.0
    var _t0_shields_parameter = perf_counter_ns()
    for _ in range(N):
        _acc_shields_parameter += shields_parameter(5.0, 2650.0, 1000.0, 9.81, 0.01)
    var _t1_shields_parameter = perf_counter_ns()
    var _ns_shields_parameter = Float64(_t1_shields_parameter - _t0_shields_parameter) / Float64(N)
    print("MOJO_TIMING geomorphology::shields_parameter", _ns_shields_parameter, _acc_shields_parameter)
    var _acc_settling_velocity_stokes: Float64 = 0.0
    var _t0_settling_velocity_stokes = perf_counter_ns()
    for _ in range(N):
        _acc_settling_velocity_stokes += settling_velocity_stokes(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_settling_velocity_stokes = perf_counter_ns()
    var _ns_settling_velocity_stokes = Float64(_t1_settling_velocity_stokes - _t0_settling_velocity_stokes) / Float64(N)
    print("MOJO_TIMING geomorphology::settling_velocity_stokes", _ns_settling_velocity_stokes, _acc_settling_velocity_stokes)
    var _acc_erosion_rate_spl: Float64 = 0.0
    var _t0_erosion_rate_spl = perf_counter_ns()
    for _ in range(N):
        _acc_erosion_rate_spl += erosion_rate_spl(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_erosion_rate_spl = perf_counter_ns()
    var _ns_erosion_rate_spl = Float64(_t1_erosion_rate_spl - _t0_erosion_rate_spl) / Float64(N)
    print("MOJO_TIMING geomorphology::erosion_rate_spl", _ns_erosion_rate_spl, _acc_erosion_rate_spl)
    var _acc_hillslope_diffusion: Float64 = 0.0
    var _t0_hillslope_diffusion = perf_counter_ns()
    for _ in range(N):
        _acc_hillslope_diffusion += hillslope_diffusion(0.5, 0.5)
    var _t1_hillslope_diffusion = perf_counter_ns()
    var _ns_hillslope_diffusion = Float64(_t1_hillslope_diffusion - _t0_hillslope_diffusion) / Float64(N)
    print("MOJO_TIMING geomorphology::hillslope_diffusion", _ns_hillslope_diffusion, _acc_hillslope_diffusion)
    var _acc_drainage_density: Float64 = 0.0
    var _t0_drainage_density = perf_counter_ns()
    for _ in range(N):
        _acc_drainage_density += drainage_density(0.5, 0.5)
    var _t1_drainage_density = perf_counter_ns()
    var _ns_drainage_density = Float64(_t1_drainage_density - _t0_drainage_density) / Float64(N)
    print("MOJO_TIMING geomorphology::drainage_density", _ns_drainage_density, _acc_drainage_density)
    var _acc_relief_ratio: Float64 = 0.0
    var _t0_relief_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_relief_ratio += relief_ratio(0.5, 0.5)
    var _t1_relief_ratio = perf_counter_ns()
    var _ns_relief_ratio = Float64(_t1_relief_ratio - _t0_relief_ratio) / Float64(N)
    print("MOJO_TIMING geomorphology::relief_ratio", _ns_relief_ratio, _acc_relief_ratio)
    var _acc_sinuosity: Float64 = 0.0
    var _t0_sinuosity = perf_counter_ns()
    for _ in range(N):
        _acc_sinuosity += sinuosity(0.5, 0.5)
    var _t1_sinuosity = perf_counter_ns()
    var _ns_sinuosity = Float64(_t1_sinuosity - _t0_sinuosity) / Float64(N)
    print("MOJO_TIMING geomorphology::sinuosity", _ns_sinuosity, _acc_sinuosity)
    var _acc_hack_law_length: Float64 = 0.0
    var _t0_hack_law_length = perf_counter_ns()
    for _ in range(N):
        _acc_hack_law_length += hack_law_length(0.5, 0.5, 0.5)
    var _t1_hack_law_length = perf_counter_ns()
    var _ns_hack_law_length = Float64(_t1_hack_law_length - _t0_hack_law_length) / Float64(N)
    print("MOJO_TIMING geomorphology::hack_law_length", _ns_hack_law_length, _acc_hack_law_length)
    var _acc_ruggedness_number: Float64 = 0.0
    var _t0_ruggedness_number = perf_counter_ns()
    for _ in range(N):
        _acc_ruggedness_number += ruggedness_number(0.5, 0.5)
    var _t1_ruggedness_number = perf_counter_ns()
    var _ns_ruggedness_number = Float64(_t1_ruggedness_number - _t0_ruggedness_number) / Float64(N)
    print("MOJO_TIMING geomorphology::ruggedness_number", _ns_ruggedness_number, _acc_ruggedness_number)
    var _acc_hypsometric_integral: Float64 = 0.0
    var _t0_hypsometric_integral = perf_counter_ns()
    for _ in range(N):
        _acc_hypsometric_integral += hypsometric_integral(500.0, 100.0, 1000.0)
    var _t1_hypsometric_integral = perf_counter_ns()
    var _ns_hypsometric_integral = Float64(_t1_hypsometric_integral - _t0_hypsometric_integral) / Float64(N)
    print("MOJO_TIMING geomorphology::hypsometric_integral", _ns_hypsometric_integral, _acc_hypsometric_integral)
