"""bench_geotechnical.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from geotechnical import bearing_capacity_terzaghi, effective_stress, overburden_pressure, coefficient_of_earth_pressure_at_rest, rankine_ka, rankine_kp, active_earth_pressure, settlement_elastic, factor_of_safety_slope, void_ratio, porosity_from_void_ratio, degree_of_saturation
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

    var _acc_bearing_capacity_terzaghi: Float64 = 0.0
    var _t0_bearing_capacity_terzaghi = perf_counter_ns()
    for _ in range(N):
        _acc_bearing_capacity_terzaghi += bearing_capacity_terzaghi(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_bearing_capacity_terzaghi = perf_counter_ns()
    var _ns_bearing_capacity_terzaghi = Float64(_t1_bearing_capacity_terzaghi - _t0_bearing_capacity_terzaghi) / Float64(N)
    print("MOJO_TIMING geotechnical::bearing_capacity_terzaghi", _ns_bearing_capacity_terzaghi, _acc_bearing_capacity_terzaghi)
    var _acc_effective_stress: Float64 = 0.0
    var _t0_effective_stress = perf_counter_ns()
    for _ in range(N):
        _acc_effective_stress += effective_stress(0.5, 0.5)
    var _t1_effective_stress = perf_counter_ns()
    var _ns_effective_stress = Float64(_t1_effective_stress - _t0_effective_stress) / Float64(N)
    print("MOJO_TIMING geotechnical::effective_stress", _ns_effective_stress, _acc_effective_stress)
    var _acc_overburden_pressure: Float64 = 0.0
    var _t0_overburden_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_overburden_pressure += overburden_pressure(0.5, 0.5)
    var _t1_overburden_pressure = perf_counter_ns()
    var _ns_overburden_pressure = Float64(_t1_overburden_pressure - _t0_overburden_pressure) / Float64(N)
    print("MOJO_TIMING geotechnical::overburden_pressure", _ns_overburden_pressure, _acc_overburden_pressure)
    var _acc_coefficient_of_earth_pressure_at_rest: Float64 = 0.0
    var _t0_coefficient_of_earth_pressure_at_rest = perf_counter_ns()
    for _ in range(N):
        _acc_coefficient_of_earth_pressure_at_rest += coefficient_of_earth_pressure_at_rest(0.5)
    var _t1_coefficient_of_earth_pressure_at_rest = perf_counter_ns()
    var _ns_coefficient_of_earth_pressure_at_rest = Float64(_t1_coefficient_of_earth_pressure_at_rest - _t0_coefficient_of_earth_pressure_at_rest) / Float64(N)
    print("MOJO_TIMING geotechnical::coefficient_of_earth_pressure_at_rest", _ns_coefficient_of_earth_pressure_at_rest, _acc_coefficient_of_earth_pressure_at_rest)
    var _acc_rankine_ka: Float64 = 0.0
    var _t0_rankine_ka = perf_counter_ns()
    for _ in range(N):
        _acc_rankine_ka += rankine_ka(0.5)
    var _t1_rankine_ka = perf_counter_ns()
    var _ns_rankine_ka = Float64(_t1_rankine_ka - _t0_rankine_ka) / Float64(N)
    print("MOJO_TIMING geotechnical::rankine_ka", _ns_rankine_ka, _acc_rankine_ka)
    var _acc_rankine_kp: Float64 = 0.0
    var _t0_rankine_kp = perf_counter_ns()
    for _ in range(N):
        _acc_rankine_kp += rankine_kp(0.5)
    var _t1_rankine_kp = perf_counter_ns()
    var _ns_rankine_kp = Float64(_t1_rankine_kp - _t0_rankine_kp) / Float64(N)
    print("MOJO_TIMING geotechnical::rankine_kp", _ns_rankine_kp, _acc_rankine_kp)
    var _acc_active_earth_pressure: Float64 = 0.0
    var _t0_active_earth_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_active_earth_pressure += active_earth_pressure(0.5, 0.5, 0.5)
    var _t1_active_earth_pressure = perf_counter_ns()
    var _ns_active_earth_pressure = Float64(_t1_active_earth_pressure - _t0_active_earth_pressure) / Float64(N)
    print("MOJO_TIMING geotechnical::active_earth_pressure", _ns_active_earth_pressure, _acc_active_earth_pressure)
    var _acc_settlement_elastic: Float64 = 0.0
    var _t0_settlement_elastic = perf_counter_ns()
    for _ in range(N):
        _acc_settlement_elastic += settlement_elastic(0.5, 0.5, 0.5, 0.5)
    var _t1_settlement_elastic = perf_counter_ns()
    var _ns_settlement_elastic = Float64(_t1_settlement_elastic - _t0_settlement_elastic) / Float64(N)
    print("MOJO_TIMING geotechnical::settlement_elastic", _ns_settlement_elastic, _acc_settlement_elastic)
    var _acc_factor_of_safety_slope: Float64 = 0.0
    var _t0_factor_of_safety_slope = perf_counter_ns()
    for _ in range(N):
        _acc_factor_of_safety_slope += factor_of_safety_slope(0.5, 0.5)
    var _t1_factor_of_safety_slope = perf_counter_ns()
    var _ns_factor_of_safety_slope = Float64(_t1_factor_of_safety_slope - _t0_factor_of_safety_slope) / Float64(N)
    print("MOJO_TIMING geotechnical::factor_of_safety_slope", _ns_factor_of_safety_slope, _acc_factor_of_safety_slope)
    var _acc_void_ratio: Float64 = 0.0
    var _t0_void_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_void_ratio += void_ratio(0.5)
    var _t1_void_ratio = perf_counter_ns()
    var _ns_void_ratio = Float64(_t1_void_ratio - _t0_void_ratio) / Float64(N)
    print("MOJO_TIMING geotechnical::void_ratio", _ns_void_ratio, _acc_void_ratio)
    var _acc_porosity_from_void_ratio: Float64 = 0.0
    var _t0_porosity_from_void_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_porosity_from_void_ratio += porosity_from_void_ratio(0.5)
    var _t1_porosity_from_void_ratio = perf_counter_ns()
    var _ns_porosity_from_void_ratio = Float64(_t1_porosity_from_void_ratio - _t0_porosity_from_void_ratio) / Float64(N)
    print("MOJO_TIMING geotechnical::porosity_from_void_ratio", _ns_porosity_from_void_ratio, _acc_porosity_from_void_ratio)
    var _acc_degree_of_saturation: Float64 = 0.0
    var _t0_degree_of_saturation = perf_counter_ns()
    for _ in range(N):
        _acc_degree_of_saturation += degree_of_saturation(0.5, 0.5, 0.5)
    var _t1_degree_of_saturation = perf_counter_ns()
    var _ns_degree_of_saturation = Float64(_t1_degree_of_saturation - _t0_degree_of_saturation) / Float64(N)
    print("MOJO_TIMING geotechnical::degree_of_saturation", _ns_degree_of_saturation, _acc_degree_of_saturation)
