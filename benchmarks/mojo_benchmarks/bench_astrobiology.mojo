"""bench_astrobiology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from astrobiology import habitable_zone_inner, habitable_zone_outer, stellar_luminosity, planetary_equilibrium_temp, water_activity, radiation_dose_rate, metabolism_rate_q10, pressure_tolerance_depth, uv_penetration_depth, panspermia_survival_fraction
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

    var _acc_habitable_zone_inner: Float64 = 0.0
    var _t0_habitable_zone_inner = perf_counter_ns()
    for _ in range(N):
        _acc_habitable_zone_inner += habitable_zone_inner(0.5)
    var _t1_habitable_zone_inner = perf_counter_ns()
    var _ns_habitable_zone_inner = Float64(_t1_habitable_zone_inner - _t0_habitable_zone_inner) / Float64(N)
    print("MOJO_TIMING astrobiology::habitable_zone_inner", _ns_habitable_zone_inner, _acc_habitable_zone_inner)
    var _acc_habitable_zone_outer: Float64 = 0.0
    var _t0_habitable_zone_outer = perf_counter_ns()
    for _ in range(N):
        _acc_habitable_zone_outer += habitable_zone_outer(0.5)
    var _t1_habitable_zone_outer = perf_counter_ns()
    var _ns_habitable_zone_outer = Float64(_t1_habitable_zone_outer - _t0_habitable_zone_outer) / Float64(N)
    print("MOJO_TIMING astrobiology::habitable_zone_outer", _ns_habitable_zone_outer, _acc_habitable_zone_outer)
    var _acc_stellar_luminosity: Float64 = 0.0
    var _t0_stellar_luminosity = perf_counter_ns()
    for _ in range(N):
        _acc_stellar_luminosity += stellar_luminosity(0.5, 0.5)
    var _t1_stellar_luminosity = perf_counter_ns()
    var _ns_stellar_luminosity = Float64(_t1_stellar_luminosity - _t0_stellar_luminosity) / Float64(N)
    print("MOJO_TIMING astrobiology::stellar_luminosity", _ns_stellar_luminosity, _acc_stellar_luminosity)
    var _acc_planetary_equilibrium_temp: Float64 = 0.0
    var _t0_planetary_equilibrium_temp = perf_counter_ns()
    for _ in range(N):
        _acc_planetary_equilibrium_temp += planetary_equilibrium_temp(0.5, 0.5)
    var _t1_planetary_equilibrium_temp = perf_counter_ns()
    var _ns_planetary_equilibrium_temp = Float64(_t1_planetary_equilibrium_temp - _t0_planetary_equilibrium_temp) / Float64(N)
    print("MOJO_TIMING astrobiology::planetary_equilibrium_temp", _ns_planetary_equilibrium_temp, _acc_planetary_equilibrium_temp)
    var _acc_water_activity: Float64 = 0.0
    var _t0_water_activity = perf_counter_ns()
    for _ in range(N):
        _acc_water_activity += water_activity(0.5, 0.5)
    var _t1_water_activity = perf_counter_ns()
    var _ns_water_activity = Float64(_t1_water_activity - _t0_water_activity) / Float64(N)
    print("MOJO_TIMING astrobiology::water_activity", _ns_water_activity, _acc_water_activity)
    var _acc_radiation_dose_rate: Float64 = 0.0
    var _t0_radiation_dose_rate = perf_counter_ns()
    for _ in range(N):
        _acc_radiation_dose_rate += radiation_dose_rate(0.5, 0.5, 0.5)
    var _t1_radiation_dose_rate = perf_counter_ns()
    var _ns_radiation_dose_rate = Float64(_t1_radiation_dose_rate - _t0_radiation_dose_rate) / Float64(N)
    print("MOJO_TIMING astrobiology::radiation_dose_rate", _ns_radiation_dose_rate, _acc_radiation_dose_rate)
    var _acc_metabolism_rate_q10: Float64 = 0.0
    var _t0_metabolism_rate_q10 = perf_counter_ns()
    for _ in range(N):
        _acc_metabolism_rate_q10 += metabolism_rate_q10(0.5, 0.5, 0.5, 0.5)
    var _t1_metabolism_rate_q10 = perf_counter_ns()
    var _ns_metabolism_rate_q10 = Float64(_t1_metabolism_rate_q10 - _t0_metabolism_rate_q10) / Float64(N)
    print("MOJO_TIMING astrobiology::metabolism_rate_q10", _ns_metabolism_rate_q10, _acc_metabolism_rate_q10)
    var _acc_pressure_tolerance_depth: Float64 = 0.0
    var _t0_pressure_tolerance_depth = perf_counter_ns()
    for _ in range(N):
        _acc_pressure_tolerance_depth += pressure_tolerance_depth(0.5)
    var _t1_pressure_tolerance_depth = perf_counter_ns()
    var _ns_pressure_tolerance_depth = Float64(_t1_pressure_tolerance_depth - _t0_pressure_tolerance_depth) / Float64(N)
    print("MOJO_TIMING astrobiology::pressure_tolerance_depth", _ns_pressure_tolerance_depth, _acc_pressure_tolerance_depth)
    var _acc_uv_penetration_depth: Float64 = 0.0
    var _t0_uv_penetration_depth = perf_counter_ns()
    for _ in range(N):
        _acc_uv_penetration_depth += uv_penetration_depth(0.5, 0.5)
    var _t1_uv_penetration_depth = perf_counter_ns()
    var _ns_uv_penetration_depth = Float64(_t1_uv_penetration_depth - _t0_uv_penetration_depth) / Float64(N)
    print("MOJO_TIMING astrobiology::uv_penetration_depth", _ns_uv_penetration_depth, _acc_uv_penetration_depth)
    var _acc_panspermia_survival_fraction: Float64 = 0.0
    var _t0_panspermia_survival_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_panspermia_survival_fraction += panspermia_survival_fraction(0.5, 0.5)
    var _t1_panspermia_survival_fraction = perf_counter_ns()
    var _ns_panspermia_survival_fraction = Float64(_t1_panspermia_survival_fraction - _t0_panspermia_survival_fraction) / Float64(N)
    print("MOJO_TIMING astrobiology::panspermia_survival_fraction", _ns_panspermia_survival_fraction, _acc_panspermia_survival_fraction)
