"""bench_inventory.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from inventory import eoq, reorder_point, safety_stock, total_inventory_cost, newsvendor_qty, service_level, abc_classify, days_of_supply, inventory_turnover, fill_rate, periodic_review_order
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

    var _acc_eoq: Float64 = 0.0
    var _t0_eoq = perf_counter_ns()
    for _ in range(N):
        _acc_eoq += eoq(0.5, 0.5, 0.5)
    var _t1_eoq = perf_counter_ns()
    var _ns_eoq = Float64(_t1_eoq - _t0_eoq) / Float64(N)
    print("MOJO_TIMING inventory::eoq", _ns_eoq, _acc_eoq)
    var _result_eoq = eoq(0.5, 0.5, 0.5)
    var _summary_eoq = _summary_float64(_result_eoq)
    print("MOJO_RESULT inventory::eoq", _summary_eoq)
    var _acc_reorder_point: Float64 = 0.0
    var _t0_reorder_point = perf_counter_ns()
    for _ in range(N):
        _acc_reorder_point += reorder_point(0.5, 0.5, 0.5)
    var _t1_reorder_point = perf_counter_ns()
    var _ns_reorder_point = Float64(_t1_reorder_point - _t0_reorder_point) / Float64(N)
    print("MOJO_TIMING inventory::reorder_point", _ns_reorder_point, _acc_reorder_point)
    var _result_reorder_point = reorder_point(0.5, 0.5, 0.5)
    var _summary_reorder_point = _summary_float64(_result_reorder_point)
    print("MOJO_RESULT inventory::reorder_point", _summary_reorder_point)
    var _acc_safety_stock: Float64 = 0.0
    var _t0_safety_stock = perf_counter_ns()
    for _ in range(N):
        _acc_safety_stock += safety_stock(0.5, 0.5, 0.5)
    var _t1_safety_stock = perf_counter_ns()
    var _ns_safety_stock = Float64(_t1_safety_stock - _t0_safety_stock) / Float64(N)
    print("MOJO_TIMING inventory::safety_stock", _ns_safety_stock, _acc_safety_stock)
    var _result_safety_stock = safety_stock(0.5, 0.5, 0.5)
    var _summary_safety_stock = _summary_float64(_result_safety_stock)
    print("MOJO_RESULT inventory::safety_stock", _summary_safety_stock)
    var _acc_total_inventory_cost: Float64 = 0.0
    var _t0_total_inventory_cost = perf_counter_ns()
    for _ in range(N):
        _acc_total_inventory_cost += total_inventory_cost(0.5, 0.5, 0.5, 0.5)
    var _t1_total_inventory_cost = perf_counter_ns()
    var _ns_total_inventory_cost = Float64(_t1_total_inventory_cost - _t0_total_inventory_cost) / Float64(N)
    print("MOJO_TIMING inventory::total_inventory_cost", _ns_total_inventory_cost, _acc_total_inventory_cost)
    var _result_total_inventory_cost = total_inventory_cost(0.5, 0.5, 0.5, 0.5)
    var _summary_total_inventory_cost = _summary_float64(_result_total_inventory_cost)
    print("MOJO_RESULT inventory::total_inventory_cost", _summary_total_inventory_cost)
    var _acc_newsvendor_qty: Float64 = 0.0
    var _t0_newsvendor_qty = perf_counter_ns()
    for _ in range(N):
        _acc_newsvendor_qty += newsvendor_qty(0.5, 0.5, 0.5, 0.5)
    var _t1_newsvendor_qty = perf_counter_ns()
    var _ns_newsvendor_qty = Float64(_t1_newsvendor_qty - _t0_newsvendor_qty) / Float64(N)
    print("MOJO_TIMING inventory::newsvendor_qty", _ns_newsvendor_qty, _acc_newsvendor_qty)
    var _result_newsvendor_qty = newsvendor_qty(0.5, 0.5, 0.5, 0.5)
    var _summary_newsvendor_qty = _summary_float64(_result_newsvendor_qty)
    print("MOJO_RESULT inventory::newsvendor_qty", _summary_newsvendor_qty)
    var _acc_service_level: Float64 = 0.0
    var _t0_service_level = perf_counter_ns()
    for _ in range(N):
        _acc_service_level += service_level(0.5)
    var _t1_service_level = perf_counter_ns()
    var _ns_service_level = Float64(_t1_service_level - _t0_service_level) / Float64(N)
    print("MOJO_TIMING inventory::service_level", _ns_service_level, _acc_service_level)
    var _result_service_level = service_level(0.5)
    var _summary_service_level = _summary_float64(_result_service_level)
    print("MOJO_RESULT inventory::service_level", _summary_service_level)
    var _acc_abc_classify: Float64 = 0.0
    var _t0_abc_classify = perf_counter_ns()
    for _ in range(N):
        var _r_abc_classify = abc_classify(_lf5)
        _acc_abc_classify += Float64(len(_r_abc_classify))
    var _t1_abc_classify = perf_counter_ns()
    var _ns_abc_classify = Float64(_t1_abc_classify - _t0_abc_classify) / Float64(N)
    print("MOJO_TIMING inventory::abc_classify", _ns_abc_classify, _acc_abc_classify)
    var _result_abc_classify = abc_classify(_lf5)
    var _summary_abc_classify = _summary_list_int(_result_abc_classify)
    print("MOJO_RESULT inventory::abc_classify", _summary_abc_classify)
    var _acc_days_of_supply: Float64 = 0.0
    var _t0_days_of_supply = perf_counter_ns()
    for _ in range(N):
        _acc_days_of_supply += days_of_supply(0.5, 0.5)
    var _t1_days_of_supply = perf_counter_ns()
    var _ns_days_of_supply = Float64(_t1_days_of_supply - _t0_days_of_supply) / Float64(N)
    print("MOJO_TIMING inventory::days_of_supply", _ns_days_of_supply, _acc_days_of_supply)
    var _result_days_of_supply = days_of_supply(0.5, 0.5)
    var _summary_days_of_supply = _summary_float64(_result_days_of_supply)
    print("MOJO_RESULT inventory::days_of_supply", _summary_days_of_supply)
    var _acc_inventory_turnover: Float64 = 0.0
    var _t0_inventory_turnover = perf_counter_ns()
    for _ in range(N):
        _acc_inventory_turnover += inventory_turnover(0.5, 0.5)
    var _t1_inventory_turnover = perf_counter_ns()
    var _ns_inventory_turnover = Float64(_t1_inventory_turnover - _t0_inventory_turnover) / Float64(N)
    print("MOJO_TIMING inventory::inventory_turnover", _ns_inventory_turnover, _acc_inventory_turnover)
    var _result_inventory_turnover = inventory_turnover(0.5, 0.5)
    var _summary_inventory_turnover = _summary_float64(_result_inventory_turnover)
    print("MOJO_RESULT inventory::inventory_turnover", _summary_inventory_turnover)
    var _acc_fill_rate: Float64 = 0.0
    var _t0_fill_rate = perf_counter_ns()
    for _ in range(N):
        _acc_fill_rate += fill_rate(5, 5)
    var _t1_fill_rate = perf_counter_ns()
    var _ns_fill_rate = Float64(_t1_fill_rate - _t0_fill_rate) / Float64(N)
    print("MOJO_TIMING inventory::fill_rate", _ns_fill_rate, _acc_fill_rate)
    var _result_fill_rate = fill_rate(5, 5)
    var _summary_fill_rate = _summary_float64(_result_fill_rate)
    print("MOJO_RESULT inventory::fill_rate", _summary_fill_rate)
    var _acc_periodic_review_order: Float64 = 0.0
    var _t0_periodic_review_order = perf_counter_ns()
    for _ in range(N):
        _acc_periodic_review_order += periodic_review_order(0.5, 0.5, 0.5)
    var _t1_periodic_review_order = perf_counter_ns()
    var _ns_periodic_review_order = Float64(_t1_periodic_review_order - _t0_periodic_review_order) / Float64(N)
    print("MOJO_TIMING inventory::periodic_review_order", _ns_periodic_review_order, _acc_periodic_review_order)
    var _result_periodic_review_order = periodic_review_order(0.5, 0.5, 0.5)
    var _summary_periodic_review_order = _summary_float64(_result_periodic_review_order)
    print("MOJO_RESULT inventory::periodic_review_order", _summary_periodic_review_order)
