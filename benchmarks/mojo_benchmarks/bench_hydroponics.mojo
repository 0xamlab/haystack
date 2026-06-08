"""bench_hydroponics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hydroponics import ec_from_tds, tds_from_ec, nutrient_concentration, ph_adjustment_acid, light_daily_integral, vpd, water_consumption_rate, nutrient_uptake_rate, grow_light_efficiency, reservoir_dilution, yield_per_area, crop_cycle_roi
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

    var _acc_ec_from_tds: Float64 = 0.0
    var _t0_ec_from_tds = perf_counter_ns()
    for _ in range(N):
        _acc_ec_from_tds += ec_from_tds(0.5, 0.5)
    var _t1_ec_from_tds = perf_counter_ns()
    var _ns_ec_from_tds = Float64(_t1_ec_from_tds - _t0_ec_from_tds) / Float64(N)
    print("MOJO_TIMING hydroponics::ec_from_tds", _ns_ec_from_tds, _acc_ec_from_tds)
    var _result_ec_from_tds = ec_from_tds(0.5, 0.5)
    var _summary_ec_from_tds = _summary_float64(_result_ec_from_tds)
    print("MOJO_RESULT hydroponics::ec_from_tds", _summary_ec_from_tds)
    var _acc_tds_from_ec: Float64 = 0.0
    var _t0_tds_from_ec = perf_counter_ns()
    for _ in range(N):
        _acc_tds_from_ec += tds_from_ec(0.5, 0.5)
    var _t1_tds_from_ec = perf_counter_ns()
    var _ns_tds_from_ec = Float64(_t1_tds_from_ec - _t0_tds_from_ec) / Float64(N)
    print("MOJO_TIMING hydroponics::tds_from_ec", _ns_tds_from_ec, _acc_tds_from_ec)
    var _result_tds_from_ec = tds_from_ec(0.5, 0.5)
    var _summary_tds_from_ec = _summary_float64(_result_tds_from_ec)
    print("MOJO_RESULT hydroponics::tds_from_ec", _summary_tds_from_ec)
    var _acc_nutrient_concentration: Float64 = 0.0
    var _t0_nutrient_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_nutrient_concentration += nutrient_concentration(0.5, 0.5)
    var _t1_nutrient_concentration = perf_counter_ns()
    var _ns_nutrient_concentration = Float64(_t1_nutrient_concentration - _t0_nutrient_concentration) / Float64(N)
    print("MOJO_TIMING hydroponics::nutrient_concentration", _ns_nutrient_concentration, _acc_nutrient_concentration)
    var _result_nutrient_concentration = nutrient_concentration(0.5, 0.5)
    var _summary_nutrient_concentration = _summary_float64(_result_nutrient_concentration)
    print("MOJO_RESULT hydroponics::nutrient_concentration", _summary_nutrient_concentration)
    var _acc_ph_adjustment_acid: Float64 = 0.0
    var _t0_ph_adjustment_acid = perf_counter_ns()
    for _ in range(N):
        _acc_ph_adjustment_acid += ph_adjustment_acid(0.5, 0.5, 0.5)
    var _t1_ph_adjustment_acid = perf_counter_ns()
    var _ns_ph_adjustment_acid = Float64(_t1_ph_adjustment_acid - _t0_ph_adjustment_acid) / Float64(N)
    print("MOJO_TIMING hydroponics::ph_adjustment_acid", _ns_ph_adjustment_acid, _acc_ph_adjustment_acid)
    var _result_ph_adjustment_acid = ph_adjustment_acid(0.5, 0.5, 0.5)
    var _summary_ph_adjustment_acid = _summary_float64(_result_ph_adjustment_acid)
    print("MOJO_RESULT hydroponics::ph_adjustment_acid", _summary_ph_adjustment_acid)
    var _acc_light_daily_integral: Float64 = 0.0
    var _t0_light_daily_integral = perf_counter_ns()
    for _ in range(N):
        _acc_light_daily_integral += light_daily_integral(0.5, 0.5)
    var _t1_light_daily_integral = perf_counter_ns()
    var _ns_light_daily_integral = Float64(_t1_light_daily_integral - _t0_light_daily_integral) / Float64(N)
    print("MOJO_TIMING hydroponics::light_daily_integral", _ns_light_daily_integral, _acc_light_daily_integral)
    var _result_light_daily_integral = light_daily_integral(0.5, 0.5)
    var _summary_light_daily_integral = _summary_float64(_result_light_daily_integral)
    print("MOJO_RESULT hydroponics::light_daily_integral", _summary_light_daily_integral)
    var _acc_vpd: Float64 = 0.0
    var _t0_vpd = perf_counter_ns()
    for _ in range(N):
        _acc_vpd += vpd(0.5, 0.5)
    var _t1_vpd = perf_counter_ns()
    var _ns_vpd = Float64(_t1_vpd - _t0_vpd) / Float64(N)
    print("MOJO_TIMING hydroponics::vpd", _ns_vpd, _acc_vpd)
    var _result_vpd = vpd(0.5, 0.5)
    var _summary_vpd = _summary_float64(_result_vpd)
    print("MOJO_RESULT hydroponics::vpd", _summary_vpd)
    var _acc_water_consumption_rate: Float64 = 0.0
    var _t0_water_consumption_rate = perf_counter_ns()
    for _ in range(N):
        _acc_water_consumption_rate += water_consumption_rate(0.5, 0.5)
    var _t1_water_consumption_rate = perf_counter_ns()
    var _ns_water_consumption_rate = Float64(_t1_water_consumption_rate - _t0_water_consumption_rate) / Float64(N)
    print("MOJO_TIMING hydroponics::water_consumption_rate", _ns_water_consumption_rate, _acc_water_consumption_rate)
    var _result_water_consumption_rate = water_consumption_rate(0.5, 0.5)
    var _summary_water_consumption_rate = _summary_float64(_result_water_consumption_rate)
    print("MOJO_RESULT hydroponics::water_consumption_rate", _summary_water_consumption_rate)
    var _acc_nutrient_uptake_rate: Float64 = 0.0
    var _t0_nutrient_uptake_rate = perf_counter_ns()
    for _ in range(N):
        _acc_nutrient_uptake_rate += nutrient_uptake_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_nutrient_uptake_rate = perf_counter_ns()
    var _ns_nutrient_uptake_rate = Float64(_t1_nutrient_uptake_rate - _t0_nutrient_uptake_rate) / Float64(N)
    print("MOJO_TIMING hydroponics::nutrient_uptake_rate", _ns_nutrient_uptake_rate, _acc_nutrient_uptake_rate)
    var _result_nutrient_uptake_rate = nutrient_uptake_rate(0.5, 0.5, 0.5, 0.5)
    var _summary_nutrient_uptake_rate = _summary_float64(_result_nutrient_uptake_rate)
    print("MOJO_RESULT hydroponics::nutrient_uptake_rate", _summary_nutrient_uptake_rate)
    var _acc_grow_light_efficiency: Float64 = 0.0
    var _t0_grow_light_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_grow_light_efficiency += grow_light_efficiency(0.5, 0.5)
    var _t1_grow_light_efficiency = perf_counter_ns()
    var _ns_grow_light_efficiency = Float64(_t1_grow_light_efficiency - _t0_grow_light_efficiency) / Float64(N)
    print("MOJO_TIMING hydroponics::grow_light_efficiency", _ns_grow_light_efficiency, _acc_grow_light_efficiency)
    var _result_grow_light_efficiency = grow_light_efficiency(0.5, 0.5)
    var _summary_grow_light_efficiency = _summary_float64(_result_grow_light_efficiency)
    print("MOJO_RESULT hydroponics::grow_light_efficiency", _summary_grow_light_efficiency)
    var _acc_reservoir_dilution: Float64 = 0.0
    var _t0_reservoir_dilution = perf_counter_ns()
    for _ in range(N):
        _acc_reservoir_dilution += reservoir_dilution(0.5, 0.5, 0.5)
    var _t1_reservoir_dilution = perf_counter_ns()
    var _ns_reservoir_dilution = Float64(_t1_reservoir_dilution - _t0_reservoir_dilution) / Float64(N)
    print("MOJO_TIMING hydroponics::reservoir_dilution", _ns_reservoir_dilution, _acc_reservoir_dilution)
    var _result_reservoir_dilution = reservoir_dilution(0.5, 0.5, 0.5)
    var _summary_reservoir_dilution = _summary_float64(_result_reservoir_dilution)
    print("MOJO_RESULT hydroponics::reservoir_dilution", _summary_reservoir_dilution)
    var _acc_yield_per_area: Float64 = 0.0
    var _t0_yield_per_area = perf_counter_ns()
    for _ in range(N):
        _acc_yield_per_area += yield_per_area(0.5, 0.5)
    var _t1_yield_per_area = perf_counter_ns()
    var _ns_yield_per_area = Float64(_t1_yield_per_area - _t0_yield_per_area) / Float64(N)
    print("MOJO_TIMING hydroponics::yield_per_area", _ns_yield_per_area, _acc_yield_per_area)
    var _result_yield_per_area = yield_per_area(0.5, 0.5)
    var _summary_yield_per_area = _summary_float64(_result_yield_per_area)
    print("MOJO_RESULT hydroponics::yield_per_area", _summary_yield_per_area)
    var _acc_crop_cycle_roi: Float64 = 0.0
    var _t0_crop_cycle_roi = perf_counter_ns()
    for _ in range(N):
        _acc_crop_cycle_roi += crop_cycle_roi(0.5, 0.5)
    var _t1_crop_cycle_roi = perf_counter_ns()
    var _ns_crop_cycle_roi = Float64(_t1_crop_cycle_roi - _t0_crop_cycle_roi) / Float64(N)
    print("MOJO_TIMING hydroponics::crop_cycle_roi", _ns_crop_cycle_roi, _acc_crop_cycle_roi)
    var _result_crop_cycle_roi = crop_cycle_roi(0.5, 0.5)
    var _summary_crop_cycle_roi = _summary_float64(_result_crop_cycle_roi)
    print("MOJO_RESULT hydroponics::crop_cycle_roi", _summary_crop_cycle_roi)
