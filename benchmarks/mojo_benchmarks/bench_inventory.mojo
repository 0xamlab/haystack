"""bench_inventory.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from inventory import eoq, reorder_point, safety_stock, total_inventory_cost, newsvendor_qty, service_level, abc_classify, days_of_supply, inventory_turnover, fill_rate, periodic_review_order
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

    var _acc_eoq: Float64 = 0.0
    var _t0_eoq = perf_counter_ns()
    for _ in range(N):
        _acc_eoq += eoq(0.5, 0.5, 0.5)
    var _t1_eoq = perf_counter_ns()
    var _ns_eoq = Float64(_t1_eoq - _t0_eoq) / Float64(N)
    print("MOJO_TIMING inventory::eoq", _ns_eoq, _acc_eoq)
    var _acc_reorder_point: Float64 = 0.0
    var _t0_reorder_point = perf_counter_ns()
    for _ in range(N):
        _acc_reorder_point += reorder_point(0.5, 0.5, 0.5)
    var _t1_reorder_point = perf_counter_ns()
    var _ns_reorder_point = Float64(_t1_reorder_point - _t0_reorder_point) / Float64(N)
    print("MOJO_TIMING inventory::reorder_point", _ns_reorder_point, _acc_reorder_point)
    var _acc_safety_stock: Float64 = 0.0
    var _t0_safety_stock = perf_counter_ns()
    for _ in range(N):
        _acc_safety_stock += safety_stock(0.5, 0.5, 0.5)
    var _t1_safety_stock = perf_counter_ns()
    var _ns_safety_stock = Float64(_t1_safety_stock - _t0_safety_stock) / Float64(N)
    print("MOJO_TIMING inventory::safety_stock", _ns_safety_stock, _acc_safety_stock)
    var _acc_total_inventory_cost: Float64 = 0.0
    var _t0_total_inventory_cost = perf_counter_ns()
    for _ in range(N):
        _acc_total_inventory_cost += total_inventory_cost(0.5, 0.5, 0.5, 0.5)
    var _t1_total_inventory_cost = perf_counter_ns()
    var _ns_total_inventory_cost = Float64(_t1_total_inventory_cost - _t0_total_inventory_cost) / Float64(N)
    print("MOJO_TIMING inventory::total_inventory_cost", _ns_total_inventory_cost, _acc_total_inventory_cost)
    var _acc_newsvendor_qty: Float64 = 0.0
    var _t0_newsvendor_qty = perf_counter_ns()
    for _ in range(N):
        _acc_newsvendor_qty += newsvendor_qty(0.5, 0.5, 0.5, 0.5)
    var _t1_newsvendor_qty = perf_counter_ns()
    var _ns_newsvendor_qty = Float64(_t1_newsvendor_qty - _t0_newsvendor_qty) / Float64(N)
    print("MOJO_TIMING inventory::newsvendor_qty", _ns_newsvendor_qty, _acc_newsvendor_qty)
    var _acc_service_level: Float64 = 0.0
    var _t0_service_level = perf_counter_ns()
    for _ in range(N):
        _acc_service_level += service_level(0.5)
    var _t1_service_level = perf_counter_ns()
    var _ns_service_level = Float64(_t1_service_level - _t0_service_level) / Float64(N)
    print("MOJO_TIMING inventory::service_level", _ns_service_level, _acc_service_level)
    var _acc_abc_classify: Float64 = 0.0
    var _t0_abc_classify = perf_counter_ns()
    for _ in range(N):
        var _r_abc_classify = abc_classify(_lf5)
        _acc_abc_classify += Float64(len(_r_abc_classify))
    var _t1_abc_classify = perf_counter_ns()
    var _ns_abc_classify = Float64(_t1_abc_classify - _t0_abc_classify) / Float64(N)
    print("MOJO_TIMING inventory::abc_classify", _ns_abc_classify, _acc_abc_classify)
    var _acc_days_of_supply: Float64 = 0.0
    var _t0_days_of_supply = perf_counter_ns()
    for _ in range(N):
        _acc_days_of_supply += days_of_supply(0.5, 0.5)
    var _t1_days_of_supply = perf_counter_ns()
    var _ns_days_of_supply = Float64(_t1_days_of_supply - _t0_days_of_supply) / Float64(N)
    print("MOJO_TIMING inventory::days_of_supply", _ns_days_of_supply, _acc_days_of_supply)
    var _acc_inventory_turnover: Float64 = 0.0
    var _t0_inventory_turnover = perf_counter_ns()
    for _ in range(N):
        _acc_inventory_turnover += inventory_turnover(0.5, 0.5)
    var _t1_inventory_turnover = perf_counter_ns()
    var _ns_inventory_turnover = Float64(_t1_inventory_turnover - _t0_inventory_turnover) / Float64(N)
    print("MOJO_TIMING inventory::inventory_turnover", _ns_inventory_turnover, _acc_inventory_turnover)
    var _acc_fill_rate: Float64 = 0.0
    var _t0_fill_rate = perf_counter_ns()
    for _ in range(N):
        _acc_fill_rate += fill_rate(5, 5)
    var _t1_fill_rate = perf_counter_ns()
    var _ns_fill_rate = Float64(_t1_fill_rate - _t0_fill_rate) / Float64(N)
    print("MOJO_TIMING inventory::fill_rate", _ns_fill_rate, _acc_fill_rate)
    var _acc_periodic_review_order: Float64 = 0.0
    var _t0_periodic_review_order = perf_counter_ns()
    for _ in range(N):
        _acc_periodic_review_order += periodic_review_order(0.5, 0.5, 0.5)
    var _t1_periodic_review_order = perf_counter_ns()
    var _ns_periodic_review_order = Float64(_t1_periodic_review_order - _t0_periodic_review_order) / Float64(N)
    print("MOJO_TIMING inventory::periodic_review_order", _ns_periodic_review_order, _acc_periodic_review_order)
