"""bench_perfumery.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from perfumery import concentration_parfum, dilution_ratio, evaporation_rate_relative, top_note_duration, middle_note_duration, base_note_duration, triangle_accord_balance, tenacity_hours, sillage_distance, cost_per_ml, fragrance_strength_scale, ingredient_proportion
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

    var _acc_concentration_parfum: Float64 = 0.0
    var _t0_concentration_parfum = perf_counter_ns()
    for _ in range(N):
        _acc_concentration_parfum += concentration_parfum(0.5, 0.5)
    var _t1_concentration_parfum = perf_counter_ns()
    var _ns_concentration_parfum = Float64(_t1_concentration_parfum - _t0_concentration_parfum) / Float64(N)
    print("MOJO_TIMING perfumery::concentration_parfum", _ns_concentration_parfum, _acc_concentration_parfum)
    var _result_concentration_parfum = concentration_parfum(0.5, 0.5)
    var _summary_concentration_parfum = _summary_float64(_result_concentration_parfum)
    print("MOJO_RESULT perfumery::concentration_parfum", _summary_concentration_parfum)
    var _acc_dilution_ratio: Float64 = 0.0
    var _t0_dilution_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_dilution_ratio += dilution_ratio(0.5, 0.5)
    var _t1_dilution_ratio = perf_counter_ns()
    var _ns_dilution_ratio = Float64(_t1_dilution_ratio - _t0_dilution_ratio) / Float64(N)
    print("MOJO_TIMING perfumery::dilution_ratio", _ns_dilution_ratio, _acc_dilution_ratio)
    var _result_dilution_ratio = dilution_ratio(0.5, 0.5)
    var _summary_dilution_ratio = _summary_float64(_result_dilution_ratio)
    print("MOJO_RESULT perfumery::dilution_ratio", _summary_dilution_ratio)
    var _acc_evaporation_rate_relative: Float64 = 0.0
    var _t0_evaporation_rate_relative = perf_counter_ns()
    for _ in range(N):
        _acc_evaporation_rate_relative += evaporation_rate_relative(0.5, 0.5)
    var _t1_evaporation_rate_relative = perf_counter_ns()
    var _ns_evaporation_rate_relative = Float64(_t1_evaporation_rate_relative - _t0_evaporation_rate_relative) / Float64(N)
    print("MOJO_TIMING perfumery::evaporation_rate_relative", _ns_evaporation_rate_relative, _acc_evaporation_rate_relative)
    var _result_evaporation_rate_relative = evaporation_rate_relative(0.5, 0.5)
    var _summary_evaporation_rate_relative = _summary_float64(_result_evaporation_rate_relative)
    print("MOJO_RESULT perfumery::evaporation_rate_relative", _summary_evaporation_rate_relative)
    var _acc_top_note_duration: Float64 = 0.0
    var _t0_top_note_duration = perf_counter_ns()
    for _ in range(N):
        _acc_top_note_duration += top_note_duration()
    var _t1_top_note_duration = perf_counter_ns()
    var _ns_top_note_duration = Float64(_t1_top_note_duration - _t0_top_note_duration) / Float64(N)
    print("MOJO_TIMING perfumery::top_note_duration", _ns_top_note_duration, _acc_top_note_duration)
    var _result_top_note_duration = top_note_duration()
    var _summary_top_note_duration = _summary_float64(_result_top_note_duration)
    print("MOJO_RESULT perfumery::top_note_duration", _summary_top_note_duration)
    var _acc_middle_note_duration: Float64 = 0.0
    var _t0_middle_note_duration = perf_counter_ns()
    for _ in range(N):
        _acc_middle_note_duration += middle_note_duration()
    var _t1_middle_note_duration = perf_counter_ns()
    var _ns_middle_note_duration = Float64(_t1_middle_note_duration - _t0_middle_note_duration) / Float64(N)
    print("MOJO_TIMING perfumery::middle_note_duration", _ns_middle_note_duration, _acc_middle_note_duration)
    var _result_middle_note_duration = middle_note_duration()
    var _summary_middle_note_duration = _summary_float64(_result_middle_note_duration)
    print("MOJO_RESULT perfumery::middle_note_duration", _summary_middle_note_duration)
    var _acc_base_note_duration: Float64 = 0.0
    var _t0_base_note_duration = perf_counter_ns()
    for _ in range(N):
        _acc_base_note_duration += base_note_duration()
    var _t1_base_note_duration = perf_counter_ns()
    var _ns_base_note_duration = Float64(_t1_base_note_duration - _t0_base_note_duration) / Float64(N)
    print("MOJO_TIMING perfumery::base_note_duration", _ns_base_note_duration, _acc_base_note_duration)
    var _result_base_note_duration = base_note_duration()
    var _summary_base_note_duration = _summary_float64(_result_base_note_duration)
    print("MOJO_RESULT perfumery::base_note_duration", _summary_base_note_duration)
    var _acc_triangle_accord_balance: Float64 = 0.0
    var _t0_triangle_accord_balance = perf_counter_ns()
    for _ in range(N):
        _acc_triangle_accord_balance += triangle_accord_balance(0.5, 0.5, 0.5)
    var _t1_triangle_accord_balance = perf_counter_ns()
    var _ns_triangle_accord_balance = Float64(_t1_triangle_accord_balance - _t0_triangle_accord_balance) / Float64(N)
    print("MOJO_TIMING perfumery::triangle_accord_balance", _ns_triangle_accord_balance, _acc_triangle_accord_balance)
    var _result_triangle_accord_balance = triangle_accord_balance(0.5, 0.5, 0.5)
    var _summary_triangle_accord_balance = _summary_float64(_result_triangle_accord_balance)
    print("MOJO_RESULT perfumery::triangle_accord_balance", _summary_triangle_accord_balance)
    var _acc_tenacity_hours: Float64 = 0.0
    var _t0_tenacity_hours = perf_counter_ns()
    for _ in range(N):
        _acc_tenacity_hours += tenacity_hours(0.5, 0.5, 0.5)
    var _t1_tenacity_hours = perf_counter_ns()
    var _ns_tenacity_hours = Float64(_t1_tenacity_hours - _t0_tenacity_hours) / Float64(N)
    print("MOJO_TIMING perfumery::tenacity_hours", _ns_tenacity_hours, _acc_tenacity_hours)
    var _result_tenacity_hours = tenacity_hours(0.5, 0.5, 0.5)
    var _summary_tenacity_hours = _summary_float64(_result_tenacity_hours)
    print("MOJO_RESULT perfumery::tenacity_hours", _summary_tenacity_hours)
    var _acc_sillage_distance: Float64 = 0.0
    var _t0_sillage_distance = perf_counter_ns()
    for _ in range(N):
        _acc_sillage_distance += sillage_distance(0.5, 0.5)
    var _t1_sillage_distance = perf_counter_ns()
    var _ns_sillage_distance = Float64(_t1_sillage_distance - _t0_sillage_distance) / Float64(N)
    print("MOJO_TIMING perfumery::sillage_distance", _ns_sillage_distance, _acc_sillage_distance)
    var _result_sillage_distance = sillage_distance(0.5, 0.5)
    var _summary_sillage_distance = _summary_float64(_result_sillage_distance)
    print("MOJO_RESULT perfumery::sillage_distance", _summary_sillage_distance)
    var _acc_cost_per_ml: Float64 = 0.0
    var _t0_cost_per_ml = perf_counter_ns()
    for _ in range(N):
        _acc_cost_per_ml += cost_per_ml(0.5, 0.5)
    var _t1_cost_per_ml = perf_counter_ns()
    var _ns_cost_per_ml = Float64(_t1_cost_per_ml - _t0_cost_per_ml) / Float64(N)
    print("MOJO_TIMING perfumery::cost_per_ml", _ns_cost_per_ml, _acc_cost_per_ml)
    var _result_cost_per_ml = cost_per_ml(0.5, 0.5)
    var _summary_cost_per_ml = _summary_float64(_result_cost_per_ml)
    print("MOJO_RESULT perfumery::cost_per_ml", _summary_cost_per_ml)
    var _acc_fragrance_strength_scale: Float64 = 0.0
    var _t0_fragrance_strength_scale = perf_counter_ns()
    for _ in range(N):
        _acc_fragrance_strength_scale += Float64(fragrance_strength_scale(0.5))
    var _t1_fragrance_strength_scale = perf_counter_ns()
    var _ns_fragrance_strength_scale = Float64(_t1_fragrance_strength_scale - _t0_fragrance_strength_scale) / Float64(N)
    print("MOJO_TIMING perfumery::fragrance_strength_scale", _ns_fragrance_strength_scale, _acc_fragrance_strength_scale)
    var _result_fragrance_strength_scale = fragrance_strength_scale(0.5)
    var _summary_fragrance_strength_scale = _summary_int(_result_fragrance_strength_scale)
    print("MOJO_RESULT perfumery::fragrance_strength_scale", _summary_fragrance_strength_scale)
    var _acc_ingredient_proportion: Float64 = 0.0
    var _t0_ingredient_proportion = perf_counter_ns()
    for _ in range(N):
        _acc_ingredient_proportion += ingredient_proportion(0.5, 0.5)
    var _t1_ingredient_proportion = perf_counter_ns()
    var _ns_ingredient_proportion = Float64(_t1_ingredient_proportion - _t0_ingredient_proportion) / Float64(N)
    print("MOJO_TIMING perfumery::ingredient_proportion", _ns_ingredient_proportion, _acc_ingredient_proportion)
    var _result_ingredient_proportion = ingredient_proportion(0.5, 0.5)
    var _summary_ingredient_proportion = _summary_float64(_result_ingredient_proportion)
    print("MOJO_RESULT perfumery::ingredient_proportion", _summary_ingredient_proportion)
