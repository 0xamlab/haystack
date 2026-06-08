"""bench_astrobiology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from astrobiology import habitable_zone_inner, habitable_zone_outer, stellar_luminosity, planetary_equilibrium_temp, water_activity, radiation_dose_rate, metabolism_rate_q10, pressure_tolerance_depth, uv_penetration_depth, panspermia_survival_fraction
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

    var _acc_habitable_zone_inner: Float64 = 0.0
    var _t0_habitable_zone_inner = perf_counter_ns()
    for _ in range(N):
        _acc_habitable_zone_inner += habitable_zone_inner(0.5)
    var _t1_habitable_zone_inner = perf_counter_ns()
    var _ns_habitable_zone_inner = Float64(_t1_habitable_zone_inner - _t0_habitable_zone_inner) / Float64(N)
    print("MOJO_TIMING astrobiology::habitable_zone_inner", _ns_habitable_zone_inner, _acc_habitable_zone_inner)
    var _result_habitable_zone_inner = habitable_zone_inner(0.5)
    var _summary_habitable_zone_inner = _summary_float64(_result_habitable_zone_inner)
    print("MOJO_RESULT astrobiology::habitable_zone_inner", _summary_habitable_zone_inner)
    var _acc_habitable_zone_outer: Float64 = 0.0
    var _t0_habitable_zone_outer = perf_counter_ns()
    for _ in range(N):
        _acc_habitable_zone_outer += habitable_zone_outer(0.5)
    var _t1_habitable_zone_outer = perf_counter_ns()
    var _ns_habitable_zone_outer = Float64(_t1_habitable_zone_outer - _t0_habitable_zone_outer) / Float64(N)
    print("MOJO_TIMING astrobiology::habitable_zone_outer", _ns_habitable_zone_outer, _acc_habitable_zone_outer)
    var _result_habitable_zone_outer = habitable_zone_outer(0.5)
    var _summary_habitable_zone_outer = _summary_float64(_result_habitable_zone_outer)
    print("MOJO_RESULT astrobiology::habitable_zone_outer", _summary_habitable_zone_outer)
    var _acc_stellar_luminosity: Float64 = 0.0
    var _t0_stellar_luminosity = perf_counter_ns()
    for _ in range(N):
        _acc_stellar_luminosity += stellar_luminosity(0.5, 0.5)
    var _t1_stellar_luminosity = perf_counter_ns()
    var _ns_stellar_luminosity = Float64(_t1_stellar_luminosity - _t0_stellar_luminosity) / Float64(N)
    print("MOJO_TIMING astrobiology::stellar_luminosity", _ns_stellar_luminosity, _acc_stellar_luminosity)
    var _result_stellar_luminosity = stellar_luminosity(0.5, 0.5)
    var _summary_stellar_luminosity = _summary_float64(_result_stellar_luminosity)
    print("MOJO_RESULT astrobiology::stellar_luminosity", _summary_stellar_luminosity)
    var _acc_planetary_equilibrium_temp: Float64 = 0.0
    var _t0_planetary_equilibrium_temp = perf_counter_ns()
    for _ in range(N):
        _acc_planetary_equilibrium_temp += planetary_equilibrium_temp(0.5, 0.5)
    var _t1_planetary_equilibrium_temp = perf_counter_ns()
    var _ns_planetary_equilibrium_temp = Float64(_t1_planetary_equilibrium_temp - _t0_planetary_equilibrium_temp) / Float64(N)
    print("MOJO_TIMING astrobiology::planetary_equilibrium_temp", _ns_planetary_equilibrium_temp, _acc_planetary_equilibrium_temp)
    var _result_planetary_equilibrium_temp = planetary_equilibrium_temp(0.5, 0.5)
    var _summary_planetary_equilibrium_temp = _summary_float64(_result_planetary_equilibrium_temp)
    print("MOJO_RESULT astrobiology::planetary_equilibrium_temp", _summary_planetary_equilibrium_temp)
    var _acc_water_activity: Float64 = 0.0
    var _t0_water_activity = perf_counter_ns()
    for _ in range(N):
        _acc_water_activity += water_activity(0.5, 0.5)
    var _t1_water_activity = perf_counter_ns()
    var _ns_water_activity = Float64(_t1_water_activity - _t0_water_activity) / Float64(N)
    print("MOJO_TIMING astrobiology::water_activity", _ns_water_activity, _acc_water_activity)
    var _result_water_activity = water_activity(0.5, 0.5)
    var _summary_water_activity = _summary_float64(_result_water_activity)
    print("MOJO_RESULT astrobiology::water_activity", _summary_water_activity)
    var _acc_radiation_dose_rate: Float64 = 0.0
    var _t0_radiation_dose_rate = perf_counter_ns()
    for _ in range(N):
        _acc_radiation_dose_rate += radiation_dose_rate(0.5, 0.5, 0.5)
    var _t1_radiation_dose_rate = perf_counter_ns()
    var _ns_radiation_dose_rate = Float64(_t1_radiation_dose_rate - _t0_radiation_dose_rate) / Float64(N)
    print("MOJO_TIMING astrobiology::radiation_dose_rate", _ns_radiation_dose_rate, _acc_radiation_dose_rate)
    var _result_radiation_dose_rate = radiation_dose_rate(0.5, 0.5, 0.5)
    var _summary_radiation_dose_rate = _summary_float64(_result_radiation_dose_rate)
    print("MOJO_RESULT astrobiology::radiation_dose_rate", _summary_radiation_dose_rate)
    var _acc_metabolism_rate_q10: Float64 = 0.0
    var _t0_metabolism_rate_q10 = perf_counter_ns()
    for _ in range(N):
        _acc_metabolism_rate_q10 += metabolism_rate_q10(0.5, 0.5, 0.5, 0.5)
    var _t1_metabolism_rate_q10 = perf_counter_ns()
    var _ns_metabolism_rate_q10 = Float64(_t1_metabolism_rate_q10 - _t0_metabolism_rate_q10) / Float64(N)
    print("MOJO_TIMING astrobiology::metabolism_rate_q10", _ns_metabolism_rate_q10, _acc_metabolism_rate_q10)
    var _result_metabolism_rate_q10 = metabolism_rate_q10(0.5, 0.5, 0.5, 0.5)
    var _summary_metabolism_rate_q10 = _summary_float64(_result_metabolism_rate_q10)
    print("MOJO_RESULT astrobiology::metabolism_rate_q10", _summary_metabolism_rate_q10)
    var _acc_pressure_tolerance_depth: Float64 = 0.0
    var _t0_pressure_tolerance_depth = perf_counter_ns()
    for _ in range(N):
        _acc_pressure_tolerance_depth += pressure_tolerance_depth(0.5)
    var _t1_pressure_tolerance_depth = perf_counter_ns()
    var _ns_pressure_tolerance_depth = Float64(_t1_pressure_tolerance_depth - _t0_pressure_tolerance_depth) / Float64(N)
    print("MOJO_TIMING astrobiology::pressure_tolerance_depth", _ns_pressure_tolerance_depth, _acc_pressure_tolerance_depth)
    var _result_pressure_tolerance_depth = pressure_tolerance_depth(0.5)
    var _summary_pressure_tolerance_depth = _summary_float64(_result_pressure_tolerance_depth)
    print("MOJO_RESULT astrobiology::pressure_tolerance_depth", _summary_pressure_tolerance_depth)
    var _acc_uv_penetration_depth: Float64 = 0.0
    var _t0_uv_penetration_depth = perf_counter_ns()
    for _ in range(N):
        _acc_uv_penetration_depth += uv_penetration_depth(0.5, 0.5)
    var _t1_uv_penetration_depth = perf_counter_ns()
    var _ns_uv_penetration_depth = Float64(_t1_uv_penetration_depth - _t0_uv_penetration_depth) / Float64(N)
    print("MOJO_TIMING astrobiology::uv_penetration_depth", _ns_uv_penetration_depth, _acc_uv_penetration_depth)
    var _result_uv_penetration_depth = uv_penetration_depth(0.5, 0.5)
    var _summary_uv_penetration_depth = _summary_float64(_result_uv_penetration_depth)
    print("MOJO_RESULT astrobiology::uv_penetration_depth", _summary_uv_penetration_depth)
    var _acc_panspermia_survival_fraction: Float64 = 0.0
    var _t0_panspermia_survival_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_panspermia_survival_fraction += panspermia_survival_fraction(0.5, 0.5)
    var _t1_panspermia_survival_fraction = perf_counter_ns()
    var _ns_panspermia_survival_fraction = Float64(_t1_panspermia_survival_fraction - _t0_panspermia_survival_fraction) / Float64(N)
    print("MOJO_TIMING astrobiology::panspermia_survival_fraction", _ns_panspermia_survival_fraction, _acc_panspermia_survival_fraction)
    var _result_panspermia_survival_fraction = panspermia_survival_fraction(0.5, 0.5)
    var _summary_panspermia_survival_fraction = _summary_float64(_result_panspermia_survival_fraction)
    print("MOJO_RESULT astrobiology::panspermia_survival_fraction", _summary_panspermia_survival_fraction)
