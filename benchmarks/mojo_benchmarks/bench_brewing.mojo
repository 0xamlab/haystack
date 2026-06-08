"""bench_brewing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from brewing import original_gravity_to_plato, plato_to_gravity, abv_from_og_fg, apparent_attenuation, real_attenuation, ibu_tinseth, utilization_tinseth, mash_water_volume, strike_water_temp, color_srm_from_mcu, calories_per_12oz, priming_sugar_g
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

    var _acc_original_gravity_to_plato: Float64 = 0.0
    var _t0_original_gravity_to_plato = perf_counter_ns()
    for _ in range(N):
        _acc_original_gravity_to_plato += original_gravity_to_plato(0.5)
    var _t1_original_gravity_to_plato = perf_counter_ns()
    var _ns_original_gravity_to_plato = Float64(_t1_original_gravity_to_plato - _t0_original_gravity_to_plato) / Float64(N)
    print("MOJO_TIMING brewing::original_gravity_to_plato", _ns_original_gravity_to_plato, _acc_original_gravity_to_plato)
    var _result_original_gravity_to_plato = original_gravity_to_plato(0.5)
    var _summary_original_gravity_to_plato = _summary_float64(_result_original_gravity_to_plato)
    print("MOJO_RESULT brewing::original_gravity_to_plato", _summary_original_gravity_to_plato)
    var _acc_plato_to_gravity: Float64 = 0.0
    var _t0_plato_to_gravity = perf_counter_ns()
    for _ in range(N):
        _acc_plato_to_gravity += plato_to_gravity(0.5)
    var _t1_plato_to_gravity = perf_counter_ns()
    var _ns_plato_to_gravity = Float64(_t1_plato_to_gravity - _t0_plato_to_gravity) / Float64(N)
    print("MOJO_TIMING brewing::plato_to_gravity", _ns_plato_to_gravity, _acc_plato_to_gravity)
    var _result_plato_to_gravity = plato_to_gravity(0.5)
    var _summary_plato_to_gravity = _summary_float64(_result_plato_to_gravity)
    print("MOJO_RESULT brewing::plato_to_gravity", _summary_plato_to_gravity)
    var _acc_abv_from_og_fg: Float64 = 0.0
    var _t0_abv_from_og_fg = perf_counter_ns()
    for _ in range(N):
        _acc_abv_from_og_fg += abv_from_og_fg(0.5, 0.5)
    var _t1_abv_from_og_fg = perf_counter_ns()
    var _ns_abv_from_og_fg = Float64(_t1_abv_from_og_fg - _t0_abv_from_og_fg) / Float64(N)
    print("MOJO_TIMING brewing::abv_from_og_fg", _ns_abv_from_og_fg, _acc_abv_from_og_fg)
    var _result_abv_from_og_fg = abv_from_og_fg(0.5, 0.5)
    var _summary_abv_from_og_fg = _summary_float64(_result_abv_from_og_fg)
    print("MOJO_RESULT brewing::abv_from_og_fg", _summary_abv_from_og_fg)
    var _acc_apparent_attenuation: Float64 = 0.0
    var _t0_apparent_attenuation = perf_counter_ns()
    for _ in range(N):
        _acc_apparent_attenuation += apparent_attenuation(0.5, 0.5)
    var _t1_apparent_attenuation = perf_counter_ns()
    var _ns_apparent_attenuation = Float64(_t1_apparent_attenuation - _t0_apparent_attenuation) / Float64(N)
    print("MOJO_TIMING brewing::apparent_attenuation", _ns_apparent_attenuation, _acc_apparent_attenuation)
    var _result_apparent_attenuation = apparent_attenuation(0.5, 0.5)
    var _summary_apparent_attenuation = _summary_float64(_result_apparent_attenuation)
    print("MOJO_RESULT brewing::apparent_attenuation", _summary_apparent_attenuation)
    var _acc_real_attenuation: Float64 = 0.0
    var _t0_real_attenuation = perf_counter_ns()
    for _ in range(N):
        _acc_real_attenuation += real_attenuation(0.5)
    var _t1_real_attenuation = perf_counter_ns()
    var _ns_real_attenuation = Float64(_t1_real_attenuation - _t0_real_attenuation) / Float64(N)
    print("MOJO_TIMING brewing::real_attenuation", _ns_real_attenuation, _acc_real_attenuation)
    var _result_real_attenuation = real_attenuation(0.5)
    var _summary_real_attenuation = _summary_float64(_result_real_attenuation)
    print("MOJO_RESULT brewing::real_attenuation", _summary_real_attenuation)
    var _acc_ibu_tinseth: Float64 = 0.0
    var _t0_ibu_tinseth = perf_counter_ns()
    for _ in range(N):
        _acc_ibu_tinseth += ibu_tinseth(0.5, 0.5, 0.5, 0.5)
    var _t1_ibu_tinseth = perf_counter_ns()
    var _ns_ibu_tinseth = Float64(_t1_ibu_tinseth - _t0_ibu_tinseth) / Float64(N)
    print("MOJO_TIMING brewing::ibu_tinseth", _ns_ibu_tinseth, _acc_ibu_tinseth)
    var _result_ibu_tinseth = ibu_tinseth(0.5, 0.5, 0.5, 0.5)
    var _summary_ibu_tinseth = _summary_float64(_result_ibu_tinseth)
    print("MOJO_RESULT brewing::ibu_tinseth", _summary_ibu_tinseth)
    var _acc_utilization_tinseth: Float64 = 0.0
    var _t0_utilization_tinseth = perf_counter_ns()
    for _ in range(N):
        _acc_utilization_tinseth += utilization_tinseth(0.5, 0.5)
    var _t1_utilization_tinseth = perf_counter_ns()
    var _ns_utilization_tinseth = Float64(_t1_utilization_tinseth - _t0_utilization_tinseth) / Float64(N)
    print("MOJO_TIMING brewing::utilization_tinseth", _ns_utilization_tinseth, _acc_utilization_tinseth)
    var _result_utilization_tinseth = utilization_tinseth(0.5, 0.5)
    var _summary_utilization_tinseth = _summary_float64(_result_utilization_tinseth)
    print("MOJO_RESULT brewing::utilization_tinseth", _summary_utilization_tinseth)
    var _acc_mash_water_volume: Float64 = 0.0
    var _t0_mash_water_volume = perf_counter_ns()
    for _ in range(N):
        _acc_mash_water_volume += mash_water_volume(0.5, 0.5)
    var _t1_mash_water_volume = perf_counter_ns()
    var _ns_mash_water_volume = Float64(_t1_mash_water_volume - _t0_mash_water_volume) / Float64(N)
    print("MOJO_TIMING brewing::mash_water_volume", _ns_mash_water_volume, _acc_mash_water_volume)
    var _result_mash_water_volume = mash_water_volume(0.5, 0.5)
    var _summary_mash_water_volume = _summary_float64(_result_mash_water_volume)
    print("MOJO_RESULT brewing::mash_water_volume", _summary_mash_water_volume)
    var _acc_strike_water_temp: Float64 = 0.0
    var _t0_strike_water_temp = perf_counter_ns()
    for _ in range(N):
        _acc_strike_water_temp += strike_water_temp(0.5, 0.5, 0.5)
    var _t1_strike_water_temp = perf_counter_ns()
    var _ns_strike_water_temp = Float64(_t1_strike_water_temp - _t0_strike_water_temp) / Float64(N)
    print("MOJO_TIMING brewing::strike_water_temp", _ns_strike_water_temp, _acc_strike_water_temp)
    var _result_strike_water_temp = strike_water_temp(0.5, 0.5, 0.5)
    var _summary_strike_water_temp = _summary_float64(_result_strike_water_temp)
    print("MOJO_RESULT brewing::strike_water_temp", _summary_strike_water_temp)
    var _acc_color_srm_from_mcu: Float64 = 0.0
    var _t0_color_srm_from_mcu = perf_counter_ns()
    for _ in range(N):
        _acc_color_srm_from_mcu += color_srm_from_mcu(0.5)
    var _t1_color_srm_from_mcu = perf_counter_ns()
    var _ns_color_srm_from_mcu = Float64(_t1_color_srm_from_mcu - _t0_color_srm_from_mcu) / Float64(N)
    print("MOJO_TIMING brewing::color_srm_from_mcu", _ns_color_srm_from_mcu, _acc_color_srm_from_mcu)
    var _result_color_srm_from_mcu = color_srm_from_mcu(0.5)
    var _summary_color_srm_from_mcu = _summary_float64(_result_color_srm_from_mcu)
    print("MOJO_RESULT brewing::color_srm_from_mcu", _summary_color_srm_from_mcu)
    var _acc_calories_per_12oz: Float64 = 0.0
    var _t0_calories_per_12oz = perf_counter_ns()
    for _ in range(N):
        _acc_calories_per_12oz += calories_per_12oz(0.5, 0.5)
    var _t1_calories_per_12oz = perf_counter_ns()
    var _ns_calories_per_12oz = Float64(_t1_calories_per_12oz - _t0_calories_per_12oz) / Float64(N)
    print("MOJO_TIMING brewing::calories_per_12oz", _ns_calories_per_12oz, _acc_calories_per_12oz)
    var _result_calories_per_12oz = calories_per_12oz(0.5, 0.5)
    var _summary_calories_per_12oz = _summary_float64(_result_calories_per_12oz)
    print("MOJO_RESULT brewing::calories_per_12oz", _summary_calories_per_12oz)
    var _acc_priming_sugar_g: Float64 = 0.0
    var _t0_priming_sugar_g = perf_counter_ns()
    for _ in range(N):
        _acc_priming_sugar_g += priming_sugar_g(0.5, 0.5, 0.5)
    var _t1_priming_sugar_g = perf_counter_ns()
    var _ns_priming_sugar_g = Float64(_t1_priming_sugar_g - _t0_priming_sugar_g) / Float64(N)
    print("MOJO_TIMING brewing::priming_sugar_g", _ns_priming_sugar_g, _acc_priming_sugar_g)
    var _result_priming_sugar_g = priming_sugar_g(0.5, 0.5, 0.5)
    var _summary_priming_sugar_g = _summary_float64(_result_priming_sugar_g)
    print("MOJO_RESULT brewing::priming_sugar_g", _summary_priming_sugar_g)
