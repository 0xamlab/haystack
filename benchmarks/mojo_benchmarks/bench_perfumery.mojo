"""bench_perfumery.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from perfumery import concentration_parfum, dilution_ratio, evaporation_rate_relative, top_note_duration, middle_note_duration, base_note_duration, triangle_accord_balance, tenacity_hours, sillage_distance, cost_per_ml, fragrance_strength_scale, ingredient_proportion
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

    var _acc_concentration_parfum: Float64 = 0.0
    var _t0_concentration_parfum = perf_counter_ns()
    for _ in range(N):
        _acc_concentration_parfum += concentration_parfum(0.5, 0.5)
    var _t1_concentration_parfum = perf_counter_ns()
    var _ns_concentration_parfum = Float64(_t1_concentration_parfum - _t0_concentration_parfum) / Float64(N)
    print("MOJO_TIMING perfumery::concentration_parfum", _ns_concentration_parfum, _acc_concentration_parfum)
    var _acc_dilution_ratio: Float64 = 0.0
    var _t0_dilution_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_dilution_ratio += dilution_ratio(0.5, 0.5)
    var _t1_dilution_ratio = perf_counter_ns()
    var _ns_dilution_ratio = Float64(_t1_dilution_ratio - _t0_dilution_ratio) / Float64(N)
    print("MOJO_TIMING perfumery::dilution_ratio", _ns_dilution_ratio, _acc_dilution_ratio)
    var _acc_evaporation_rate_relative: Float64 = 0.0
    var _t0_evaporation_rate_relative = perf_counter_ns()
    for _ in range(N):
        _acc_evaporation_rate_relative += evaporation_rate_relative(0.5, 0.5)
    var _t1_evaporation_rate_relative = perf_counter_ns()
    var _ns_evaporation_rate_relative = Float64(_t1_evaporation_rate_relative - _t0_evaporation_rate_relative) / Float64(N)
    print("MOJO_TIMING perfumery::evaporation_rate_relative", _ns_evaporation_rate_relative, _acc_evaporation_rate_relative)
    var _acc_top_note_duration: Float64 = 0.0
    var _t0_top_note_duration = perf_counter_ns()
    for _ in range(N):
        _acc_top_note_duration += top_note_duration()
    var _t1_top_note_duration = perf_counter_ns()
    var _ns_top_note_duration = Float64(_t1_top_note_duration - _t0_top_note_duration) / Float64(N)
    print("MOJO_TIMING perfumery::top_note_duration", _ns_top_note_duration, _acc_top_note_duration)
    var _acc_middle_note_duration: Float64 = 0.0
    var _t0_middle_note_duration = perf_counter_ns()
    for _ in range(N):
        _acc_middle_note_duration += middle_note_duration()
    var _t1_middle_note_duration = perf_counter_ns()
    var _ns_middle_note_duration = Float64(_t1_middle_note_duration - _t0_middle_note_duration) / Float64(N)
    print("MOJO_TIMING perfumery::middle_note_duration", _ns_middle_note_duration, _acc_middle_note_duration)
    var _acc_base_note_duration: Float64 = 0.0
    var _t0_base_note_duration = perf_counter_ns()
    for _ in range(N):
        _acc_base_note_duration += base_note_duration()
    var _t1_base_note_duration = perf_counter_ns()
    var _ns_base_note_duration = Float64(_t1_base_note_duration - _t0_base_note_duration) / Float64(N)
    print("MOJO_TIMING perfumery::base_note_duration", _ns_base_note_duration, _acc_base_note_duration)
    var _acc_triangle_accord_balance: Float64 = 0.0
    var _t0_triangle_accord_balance = perf_counter_ns()
    for _ in range(N):
        _acc_triangle_accord_balance += triangle_accord_balance(0.5, 0.5, 0.5)
    var _t1_triangle_accord_balance = perf_counter_ns()
    var _ns_triangle_accord_balance = Float64(_t1_triangle_accord_balance - _t0_triangle_accord_balance) / Float64(N)
    print("MOJO_TIMING perfumery::triangle_accord_balance", _ns_triangle_accord_balance, _acc_triangle_accord_balance)
    var _acc_tenacity_hours: Float64 = 0.0
    var _t0_tenacity_hours = perf_counter_ns()
    for _ in range(N):
        _acc_tenacity_hours += tenacity_hours(0.5, 0.5, 0.5)
    var _t1_tenacity_hours = perf_counter_ns()
    var _ns_tenacity_hours = Float64(_t1_tenacity_hours - _t0_tenacity_hours) / Float64(N)
    print("MOJO_TIMING perfumery::tenacity_hours", _ns_tenacity_hours, _acc_tenacity_hours)
    var _acc_sillage_distance: Float64 = 0.0
    var _t0_sillage_distance = perf_counter_ns()
    for _ in range(N):
        _acc_sillage_distance += sillage_distance(0.5, 0.5)
    var _t1_sillage_distance = perf_counter_ns()
    var _ns_sillage_distance = Float64(_t1_sillage_distance - _t0_sillage_distance) / Float64(N)
    print("MOJO_TIMING perfumery::sillage_distance", _ns_sillage_distance, _acc_sillage_distance)
    var _acc_cost_per_ml: Float64 = 0.0
    var _t0_cost_per_ml = perf_counter_ns()
    for _ in range(N):
        _acc_cost_per_ml += cost_per_ml(0.5, 0.5)
    var _t1_cost_per_ml = perf_counter_ns()
    var _ns_cost_per_ml = Float64(_t1_cost_per_ml - _t0_cost_per_ml) / Float64(N)
    print("MOJO_TIMING perfumery::cost_per_ml", _ns_cost_per_ml, _acc_cost_per_ml)
    var _acc_fragrance_strength_scale: Float64 = 0.0
    var _t0_fragrance_strength_scale = perf_counter_ns()
    for _ in range(N):
        _acc_fragrance_strength_scale += Float64(fragrance_strength_scale(0.5))
    var _t1_fragrance_strength_scale = perf_counter_ns()
    var _ns_fragrance_strength_scale = Float64(_t1_fragrance_strength_scale - _t0_fragrance_strength_scale) / Float64(N)
    print("MOJO_TIMING perfumery::fragrance_strength_scale", _ns_fragrance_strength_scale, _acc_fragrance_strength_scale)
    var _acc_ingredient_proportion: Float64 = 0.0
    var _t0_ingredient_proportion = perf_counter_ns()
    for _ in range(N):
        _acc_ingredient_proportion += ingredient_proportion(0.5, 0.5)
    var _t1_ingredient_proportion = perf_counter_ns()
    var _ns_ingredient_proportion = Float64(_t1_ingredient_proportion - _t0_ingredient_proportion) / Float64(N)
    print("MOJO_TIMING perfumery::ingredient_proportion", _ns_ingredient_proportion, _acc_ingredient_proportion)
