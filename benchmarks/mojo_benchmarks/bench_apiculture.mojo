"""bench_apiculture.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from apiculture import honey_yield_per_hive, colony_strength_estimate, varroa_infestation_rate, sugar_syrup_ratio, foraging_range_area, nectar_to_honey_ratio, brood_viability, winter_feed_requirement, queen_laying_rate, pollination_value, hive_density_per_hectare, overwintering_survival_rate
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

    var _acc_honey_yield_per_hive: Float64 = 0.0
    var _t0_honey_yield_per_hive = perf_counter_ns()
    for _ in range(N):
        _acc_honey_yield_per_hive += honey_yield_per_hive(0.5, 0.5)
    var _t1_honey_yield_per_hive = perf_counter_ns()
    var _ns_honey_yield_per_hive = Float64(_t1_honey_yield_per_hive - _t0_honey_yield_per_hive) / Float64(N)
    print("MOJO_TIMING apiculture::honey_yield_per_hive", _ns_honey_yield_per_hive, _acc_honey_yield_per_hive)
    var _result_honey_yield_per_hive = honey_yield_per_hive(0.5, 0.5)
    var _summary_honey_yield_per_hive = _summary_float64(_result_honey_yield_per_hive)
    print("MOJO_RESULT apiculture::honey_yield_per_hive", _summary_honey_yield_per_hive)
    var _acc_colony_strength_estimate: Float64 = 0.0
    var _t0_colony_strength_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_colony_strength_estimate += colony_strength_estimate(0.5, 0.5)
    var _t1_colony_strength_estimate = perf_counter_ns()
    var _ns_colony_strength_estimate = Float64(_t1_colony_strength_estimate - _t0_colony_strength_estimate) / Float64(N)
    print("MOJO_TIMING apiculture::colony_strength_estimate", _ns_colony_strength_estimate, _acc_colony_strength_estimate)
    var _result_colony_strength_estimate = colony_strength_estimate(0.5, 0.5)
    var _summary_colony_strength_estimate = _summary_float64(_result_colony_strength_estimate)
    print("MOJO_RESULT apiculture::colony_strength_estimate", _summary_colony_strength_estimate)
    var _acc_varroa_infestation_rate: Float64 = 0.0
    var _t0_varroa_infestation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_varroa_infestation_rate += varroa_infestation_rate(0.5, 0.5)
    var _t1_varroa_infestation_rate = perf_counter_ns()
    var _ns_varroa_infestation_rate = Float64(_t1_varroa_infestation_rate - _t0_varroa_infestation_rate) / Float64(N)
    print("MOJO_TIMING apiculture::varroa_infestation_rate", _ns_varroa_infestation_rate, _acc_varroa_infestation_rate)
    var _result_varroa_infestation_rate = varroa_infestation_rate(0.5, 0.5)
    var _summary_varroa_infestation_rate = _summary_float64(_result_varroa_infestation_rate)
    print("MOJO_RESULT apiculture::varroa_infestation_rate", _summary_varroa_infestation_rate)
    var _acc_sugar_syrup_ratio: Float64 = 0.0
    var _t0_sugar_syrup_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_sugar_syrup_ratio += sugar_syrup_ratio(0.5, 0.5)
    var _t1_sugar_syrup_ratio = perf_counter_ns()
    var _ns_sugar_syrup_ratio = Float64(_t1_sugar_syrup_ratio - _t0_sugar_syrup_ratio) / Float64(N)
    print("MOJO_TIMING apiculture::sugar_syrup_ratio", _ns_sugar_syrup_ratio, _acc_sugar_syrup_ratio)
    var _result_sugar_syrup_ratio = sugar_syrup_ratio(0.5, 0.5)
    var _summary_sugar_syrup_ratio = _summary_float64(_result_sugar_syrup_ratio)
    print("MOJO_RESULT apiculture::sugar_syrup_ratio", _summary_sugar_syrup_ratio)
    var _acc_foraging_range_area: Float64 = 0.0
    var _t0_foraging_range_area = perf_counter_ns()
    for _ in range(N):
        _acc_foraging_range_area += foraging_range_area(0.5)
    var _t1_foraging_range_area = perf_counter_ns()
    var _ns_foraging_range_area = Float64(_t1_foraging_range_area - _t0_foraging_range_area) / Float64(N)
    print("MOJO_TIMING apiculture::foraging_range_area", _ns_foraging_range_area, _acc_foraging_range_area)
    var _result_foraging_range_area = foraging_range_area(0.5)
    var _summary_foraging_range_area = _summary_float64(_result_foraging_range_area)
    print("MOJO_RESULT apiculture::foraging_range_area", _summary_foraging_range_area)
    var _acc_nectar_to_honey_ratio: Float64 = 0.0
    var _t0_nectar_to_honey_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_nectar_to_honey_ratio += nectar_to_honey_ratio(0.5)
    var _t1_nectar_to_honey_ratio = perf_counter_ns()
    var _ns_nectar_to_honey_ratio = Float64(_t1_nectar_to_honey_ratio - _t0_nectar_to_honey_ratio) / Float64(N)
    print("MOJO_TIMING apiculture::nectar_to_honey_ratio", _ns_nectar_to_honey_ratio, _acc_nectar_to_honey_ratio)
    var _result_nectar_to_honey_ratio = nectar_to_honey_ratio(0.5)
    var _summary_nectar_to_honey_ratio = _summary_float64(_result_nectar_to_honey_ratio)
    print("MOJO_RESULT apiculture::nectar_to_honey_ratio", _summary_nectar_to_honey_ratio)
    var _acc_brood_viability: Float64 = 0.0
    var _t0_brood_viability = perf_counter_ns()
    for _ in range(N):
        _acc_brood_viability += brood_viability(0.5, 0.5)
    var _t1_brood_viability = perf_counter_ns()
    var _ns_brood_viability = Float64(_t1_brood_viability - _t0_brood_viability) / Float64(N)
    print("MOJO_TIMING apiculture::brood_viability", _ns_brood_viability, _acc_brood_viability)
    var _result_brood_viability = brood_viability(0.5, 0.5)
    var _summary_brood_viability = _summary_float64(_result_brood_viability)
    print("MOJO_RESULT apiculture::brood_viability", _summary_brood_viability)
    var _acc_winter_feed_requirement: Float64 = 0.0
    var _t0_winter_feed_requirement = perf_counter_ns()
    for _ in range(N):
        _acc_winter_feed_requirement += winter_feed_requirement(0.5, 0.5, 0.5)
    var _t1_winter_feed_requirement = perf_counter_ns()
    var _ns_winter_feed_requirement = Float64(_t1_winter_feed_requirement - _t0_winter_feed_requirement) / Float64(N)
    print("MOJO_TIMING apiculture::winter_feed_requirement", _ns_winter_feed_requirement, _acc_winter_feed_requirement)
    var _result_winter_feed_requirement = winter_feed_requirement(0.5, 0.5, 0.5)
    var _summary_winter_feed_requirement = _summary_float64(_result_winter_feed_requirement)
    print("MOJO_RESULT apiculture::winter_feed_requirement", _summary_winter_feed_requirement)
    var _acc_queen_laying_rate: Float64 = 0.0
    var _t0_queen_laying_rate = perf_counter_ns()
    for _ in range(N):
        _acc_queen_laying_rate += queen_laying_rate(0.5)
    var _t1_queen_laying_rate = perf_counter_ns()
    var _ns_queen_laying_rate = Float64(_t1_queen_laying_rate - _t0_queen_laying_rate) / Float64(N)
    print("MOJO_TIMING apiculture::queen_laying_rate", _ns_queen_laying_rate, _acc_queen_laying_rate)
    var _result_queen_laying_rate = queen_laying_rate(0.5)
    var _summary_queen_laying_rate = _summary_float64(_result_queen_laying_rate)
    print("MOJO_RESULT apiculture::queen_laying_rate", _summary_queen_laying_rate)
    var _acc_pollination_value: Float64 = 0.0
    var _t0_pollination_value = perf_counter_ns()
    for _ in range(N):
        _acc_pollination_value += pollination_value(0.5, 0.5)
    var _t1_pollination_value = perf_counter_ns()
    var _ns_pollination_value = Float64(_t1_pollination_value - _t0_pollination_value) / Float64(N)
    print("MOJO_TIMING apiculture::pollination_value", _ns_pollination_value, _acc_pollination_value)
    var _result_pollination_value = pollination_value(0.5, 0.5)
    var _summary_pollination_value = _summary_float64(_result_pollination_value)
    print("MOJO_RESULT apiculture::pollination_value", _summary_pollination_value)
    var _acc_hive_density_per_hectare: Float64 = 0.0
    var _t0_hive_density_per_hectare = perf_counter_ns()
    for _ in range(N):
        _acc_hive_density_per_hectare += hive_density_per_hectare(0.5, 0.5)
    var _t1_hive_density_per_hectare = perf_counter_ns()
    var _ns_hive_density_per_hectare = Float64(_t1_hive_density_per_hectare - _t0_hive_density_per_hectare) / Float64(N)
    print("MOJO_TIMING apiculture::hive_density_per_hectare", _ns_hive_density_per_hectare, _acc_hive_density_per_hectare)
    var _result_hive_density_per_hectare = hive_density_per_hectare(0.5, 0.5)
    var _summary_hive_density_per_hectare = _summary_float64(_result_hive_density_per_hectare)
    print("MOJO_RESULT apiculture::hive_density_per_hectare", _summary_hive_density_per_hectare)
    var _acc_overwintering_survival_rate: Float64 = 0.0
    var _t0_overwintering_survival_rate = perf_counter_ns()
    for _ in range(N):
        _acc_overwintering_survival_rate += overwintering_survival_rate(0.5, 0.5)
    var _t1_overwintering_survival_rate = perf_counter_ns()
    var _ns_overwintering_survival_rate = Float64(_t1_overwintering_survival_rate - _t0_overwintering_survival_rate) / Float64(N)
    print("MOJO_TIMING apiculture::overwintering_survival_rate", _ns_overwintering_survival_rate, _acc_overwintering_survival_rate)
    var _result_overwintering_survival_rate = overwintering_survival_rate(0.5, 0.5)
    var _summary_overwintering_survival_rate = _summary_float64(_result_overwintering_survival_rate)
    print("MOJO_RESULT apiculture::overwintering_survival_rate", _summary_overwintering_survival_rate)
