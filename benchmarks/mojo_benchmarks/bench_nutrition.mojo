"""bench_nutrition.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from nutrition import bmi, bmi_category, bmr_mifflin, tdee, caloric_deficit, macro_split, ideal_body_weight, body_fat_estimate, water_intake, heart_rate_max, target_heart_rate, vo2max_estimate
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

    var _acc_bmi: Float64 = 0.0
    var _t0_bmi = perf_counter_ns()
    for _ in range(N):
        _acc_bmi += bmi(0.5, 0.5)
    var _t1_bmi = perf_counter_ns()
    var _ns_bmi = Float64(_t1_bmi - _t0_bmi) / Float64(N)
    print("MOJO_TIMING nutrition::bmi", _ns_bmi, _acc_bmi)
    var _acc_bmi_category: Float64 = 0.0
    var _t0_bmi_category = perf_counter_ns()
    for _ in range(N):
        _acc_bmi_category += Float64(bmi_category(0.5))
    var _t1_bmi_category = perf_counter_ns()
    var _ns_bmi_category = Float64(_t1_bmi_category - _t0_bmi_category) / Float64(N)
    print("MOJO_TIMING nutrition::bmi_category", _ns_bmi_category, _acc_bmi_category)
    var _acc_bmr_mifflin: Float64 = 0.0
    var _t0_bmr_mifflin = perf_counter_ns()
    for _ in range(N):
        _acc_bmr_mifflin += bmr_mifflin(0.5, 0.5, 5, True)
    var _t1_bmr_mifflin = perf_counter_ns()
    var _ns_bmr_mifflin = Float64(_t1_bmr_mifflin - _t0_bmr_mifflin) / Float64(N)
    print("MOJO_TIMING nutrition::bmr_mifflin", _ns_bmr_mifflin, _acc_bmr_mifflin)
    var _acc_tdee: Float64 = 0.0
    var _t0_tdee = perf_counter_ns()
    for _ in range(N):
        _acc_tdee += tdee(0.5, 0.5)
    var _t1_tdee = perf_counter_ns()
    var _ns_tdee = Float64(_t1_tdee - _t0_tdee) / Float64(N)
    print("MOJO_TIMING nutrition::tdee", _ns_tdee, _acc_tdee)
    var _acc_caloric_deficit: Float64 = 0.0
    var _t0_caloric_deficit = perf_counter_ns()
    for _ in range(N):
        _acc_caloric_deficit += caloric_deficit(0.5, 0.5)
    var _t1_caloric_deficit = perf_counter_ns()
    var _ns_caloric_deficit = Float64(_t1_caloric_deficit - _t0_caloric_deficit) / Float64(N)
    print("MOJO_TIMING nutrition::caloric_deficit", _ns_caloric_deficit, _acc_caloric_deficit)
    var _acc_macro_split: Float64 = 0.0
    var _t0_macro_split = perf_counter_ns()
    for _ in range(N):
        var _r_macro_split = macro_split(0.5, 0.5, 0.5)
        _acc_macro_split += Float64(len(_r_macro_split))
    var _t1_macro_split = perf_counter_ns()
    var _ns_macro_split = Float64(_t1_macro_split - _t0_macro_split) / Float64(N)
    print("MOJO_TIMING nutrition::macro_split", _ns_macro_split, _acc_macro_split)
    var _acc_ideal_body_weight: Float64 = 0.0
    var _t0_ideal_body_weight = perf_counter_ns()
    for _ in range(N):
        _acc_ideal_body_weight += ideal_body_weight(0.5, True)
    var _t1_ideal_body_weight = perf_counter_ns()
    var _ns_ideal_body_weight = Float64(_t1_ideal_body_weight - _t0_ideal_body_weight) / Float64(N)
    print("MOJO_TIMING nutrition::ideal_body_weight", _ns_ideal_body_weight, _acc_ideal_body_weight)
    var _acc_body_fat_estimate: Float64 = 0.0
    var _t0_body_fat_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_body_fat_estimate += body_fat_estimate(0.5, 5, True)
    var _t1_body_fat_estimate = perf_counter_ns()
    var _ns_body_fat_estimate = Float64(_t1_body_fat_estimate - _t0_body_fat_estimate) / Float64(N)
    print("MOJO_TIMING nutrition::body_fat_estimate", _ns_body_fat_estimate, _acc_body_fat_estimate)
    var _acc_water_intake: Float64 = 0.0
    var _t0_water_intake = perf_counter_ns()
    for _ in range(N):
        _acc_water_intake += water_intake(0.5)
    var _t1_water_intake = perf_counter_ns()
    var _ns_water_intake = Float64(_t1_water_intake - _t0_water_intake) / Float64(N)
    print("MOJO_TIMING nutrition::water_intake", _ns_water_intake, _acc_water_intake)
    var _acc_heart_rate_max: Float64 = 0.0
    var _t0_heart_rate_max = perf_counter_ns()
    for _ in range(N):
        _acc_heart_rate_max += Float64(heart_rate_max(5))
    var _t1_heart_rate_max = perf_counter_ns()
    var _ns_heart_rate_max = Float64(_t1_heart_rate_max - _t0_heart_rate_max) / Float64(N)
    print("MOJO_TIMING nutrition::heart_rate_max", _ns_heart_rate_max, _acc_heart_rate_max)
    var _acc_target_heart_rate: Float64 = 0.0
    var _t0_target_heart_rate = perf_counter_ns()
    for _ in range(N):
        var _r_target_heart_rate = target_heart_rate(5, 0.5, 0.5)
        _acc_target_heart_rate += Float64(len(_r_target_heart_rate))
    var _t1_target_heart_rate = perf_counter_ns()
    var _ns_target_heart_rate = Float64(_t1_target_heart_rate - _t0_target_heart_rate) / Float64(N)
    print("MOJO_TIMING nutrition::target_heart_rate", _ns_target_heart_rate, _acc_target_heart_rate)
    var _acc_vo2max_estimate: Float64 = 0.0
    var _t0_vo2max_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_vo2max_estimate += vo2max_estimate(5, 5)
    var _t1_vo2max_estimate = perf_counter_ns()
    var _ns_vo2max_estimate = Float64(_t1_vo2max_estimate - _t0_vo2max_estimate) / Float64(N)
    print("MOJO_TIMING nutrition::vo2max_estimate", _ns_vo2max_estimate, _acc_vo2max_estimate)
