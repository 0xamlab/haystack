"""bench_watchmaking.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from watchmaking import gear_ratio, gear_train_ratio, beats_per_hour, frequency_from_bph, mainspring_torque, power_reserve_hours, balance_wheel_period, escapement_error_spd, jewel_count_minimum, water_resistance_atm, case_diameter_mm, crown_winding_turns
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

    var _acc_gear_ratio: Float64 = 0.0
    var _t0_gear_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_gear_ratio += gear_ratio(0.5, 0.5)
    var _t1_gear_ratio = perf_counter_ns()
    var _ns_gear_ratio = Float64(_t1_gear_ratio - _t0_gear_ratio) / Float64(N)
    print("MOJO_TIMING watchmaking::gear_ratio", _ns_gear_ratio, _acc_gear_ratio)
    var _acc_gear_train_ratio: Float64 = 0.0
    var _t0_gear_train_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_gear_train_ratio += gear_train_ratio(0.5)
    var _t1_gear_train_ratio = perf_counter_ns()
    var _ns_gear_train_ratio = Float64(_t1_gear_train_ratio - _t0_gear_train_ratio) / Float64(N)
    print("MOJO_TIMING watchmaking::gear_train_ratio", _ns_gear_train_ratio, _acc_gear_train_ratio)
    var _acc_beats_per_hour: Float64 = 0.0
    var _t0_beats_per_hour = perf_counter_ns()
    for _ in range(N):
        _acc_beats_per_hour += beats_per_hour(0.5)
    var _t1_beats_per_hour = perf_counter_ns()
    var _ns_beats_per_hour = Float64(_t1_beats_per_hour - _t0_beats_per_hour) / Float64(N)
    print("MOJO_TIMING watchmaking::beats_per_hour", _ns_beats_per_hour, _acc_beats_per_hour)
    var _acc_frequency_from_bph: Float64 = 0.0
    var _t0_frequency_from_bph = perf_counter_ns()
    for _ in range(N):
        _acc_frequency_from_bph += frequency_from_bph(0.5)
    var _t1_frequency_from_bph = perf_counter_ns()
    var _ns_frequency_from_bph = Float64(_t1_frequency_from_bph - _t0_frequency_from_bph) / Float64(N)
    print("MOJO_TIMING watchmaking::frequency_from_bph", _ns_frequency_from_bph, _acc_frequency_from_bph)
    var _acc_mainspring_torque: Float64 = 0.0
    var _t0_mainspring_torque = perf_counter_ns()
    for _ in range(N):
        _acc_mainspring_torque += mainspring_torque(0.5, 0.5)
    var _t1_mainspring_torque = perf_counter_ns()
    var _ns_mainspring_torque = Float64(_t1_mainspring_torque - _t0_mainspring_torque) / Float64(N)
    print("MOJO_TIMING watchmaking::mainspring_torque", _ns_mainspring_torque, _acc_mainspring_torque)
    var _acc_power_reserve_hours: Float64 = 0.0
    var _t0_power_reserve_hours = perf_counter_ns()
    for _ in range(N):
        _acc_power_reserve_hours += power_reserve_hours(0.5, 0.5)
    var _t1_power_reserve_hours = perf_counter_ns()
    var _ns_power_reserve_hours = Float64(_t1_power_reserve_hours - _t0_power_reserve_hours) / Float64(N)
    print("MOJO_TIMING watchmaking::power_reserve_hours", _ns_power_reserve_hours, _acc_power_reserve_hours)
    var _acc_balance_wheel_period: Float64 = 0.0
    var _t0_balance_wheel_period = perf_counter_ns()
    for _ in range(N):
        _acc_balance_wheel_period += balance_wheel_period(0.5, 0.5)
    var _t1_balance_wheel_period = perf_counter_ns()
    var _ns_balance_wheel_period = Float64(_t1_balance_wheel_period - _t0_balance_wheel_period) / Float64(N)
    print("MOJO_TIMING watchmaking::balance_wheel_period", _ns_balance_wheel_period, _acc_balance_wheel_period)
    var _acc_escapement_error_spd: Float64 = 0.0
    var _t0_escapement_error_spd = perf_counter_ns()
    for _ in range(N):
        _acc_escapement_error_spd += escapement_error_spd(0.5, 0.5)
    var _t1_escapement_error_spd = perf_counter_ns()
    var _ns_escapement_error_spd = Float64(_t1_escapement_error_spd - _t0_escapement_error_spd) / Float64(N)
    print("MOJO_TIMING watchmaking::escapement_error_spd", _ns_escapement_error_spd, _acc_escapement_error_spd)
    var _acc_jewel_count_minimum: Float64 = 0.0
    var _t0_jewel_count_minimum = perf_counter_ns()
    for _ in range(N):
        _acc_jewel_count_minimum += Float64(jewel_count_minimum(5))
    var _t1_jewel_count_minimum = perf_counter_ns()
    var _ns_jewel_count_minimum = Float64(_t1_jewel_count_minimum - _t0_jewel_count_minimum) / Float64(N)
    print("MOJO_TIMING watchmaking::jewel_count_minimum", _ns_jewel_count_minimum, _acc_jewel_count_minimum)
    var _acc_water_resistance_atm: Float64 = 0.0
    var _t0_water_resistance_atm = perf_counter_ns()
    for _ in range(N):
        _acc_water_resistance_atm += water_resistance_atm(0.5)
    var _t1_water_resistance_atm = perf_counter_ns()
    var _ns_water_resistance_atm = Float64(_t1_water_resistance_atm - _t0_water_resistance_atm) / Float64(N)
    print("MOJO_TIMING watchmaking::water_resistance_atm", _ns_water_resistance_atm, _acc_water_resistance_atm)
    var _acc_case_diameter_mm: Float64 = 0.0
    var _t0_case_diameter_mm = perf_counter_ns()
    for _ in range(N):
        _acc_case_diameter_mm += case_diameter_mm(0.5)
    var _t1_case_diameter_mm = perf_counter_ns()
    var _ns_case_diameter_mm = Float64(_t1_case_diameter_mm - _t0_case_diameter_mm) / Float64(N)
    print("MOJO_TIMING watchmaking::case_diameter_mm", _ns_case_diameter_mm, _acc_case_diameter_mm)
    var _acc_crown_winding_turns: Float64 = 0.0
    var _t0_crown_winding_turns = perf_counter_ns()
    for _ in range(N):
        _acc_crown_winding_turns += crown_winding_turns(0.5, 0.5)
    var _t1_crown_winding_turns = perf_counter_ns()
    var _ns_crown_winding_turns = Float64(_t1_crown_winding_turns - _t0_crown_winding_turns) / Float64(N)
    print("MOJO_TIMING watchmaking::crown_winding_turns", _ns_crown_winding_turns, _acc_crown_winding_turns)
