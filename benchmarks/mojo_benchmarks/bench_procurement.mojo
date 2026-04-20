"""bench_procurement.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from procurement import total_cost_of_ownership, price_variance, purchase_price_variance_pct, inventory_turnover, days_inventory_outstanding, economic_order_quantity, reorder_point, safety_stock, supplier_score_weighted, savings_percentage, maverick_spend_ratio, payment_discount_annualized
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

    var _acc_total_cost_of_ownership: Float64 = 0.0
    var _t0_total_cost_of_ownership = perf_counter_ns()
    for _ in range(N):
        _acc_total_cost_of_ownership += total_cost_of_ownership(0.5, 0.5, 0.5, 0.5)
    var _t1_total_cost_of_ownership = perf_counter_ns()
    var _ns_total_cost_of_ownership = Float64(_t1_total_cost_of_ownership - _t0_total_cost_of_ownership) / Float64(N)
    print("MOJO_TIMING procurement::total_cost_of_ownership", _ns_total_cost_of_ownership, _acc_total_cost_of_ownership)
    var _acc_price_variance: Float64 = 0.0
    var _t0_price_variance = perf_counter_ns()
    for _ in range(N):
        _acc_price_variance += price_variance(0.5, 0.5, 0.5)
    var _t1_price_variance = perf_counter_ns()
    var _ns_price_variance = Float64(_t1_price_variance - _t0_price_variance) / Float64(N)
    print("MOJO_TIMING procurement::price_variance", _ns_price_variance, _acc_price_variance)
    var _acc_purchase_price_variance_pct: Float64 = 0.0
    var _t0_purchase_price_variance_pct = perf_counter_ns()
    for _ in range(N):
        _acc_purchase_price_variance_pct += purchase_price_variance_pct(0.5, 0.5)
    var _t1_purchase_price_variance_pct = perf_counter_ns()
    var _ns_purchase_price_variance_pct = Float64(_t1_purchase_price_variance_pct - _t0_purchase_price_variance_pct) / Float64(N)
    print("MOJO_TIMING procurement::purchase_price_variance_pct", _ns_purchase_price_variance_pct, _acc_purchase_price_variance_pct)
    var _acc_inventory_turnover: Float64 = 0.0
    var _t0_inventory_turnover = perf_counter_ns()
    for _ in range(N):
        _acc_inventory_turnover += inventory_turnover(0.5, 0.5)
    var _t1_inventory_turnover = perf_counter_ns()
    var _ns_inventory_turnover = Float64(_t1_inventory_turnover - _t0_inventory_turnover) / Float64(N)
    print("MOJO_TIMING procurement::inventory_turnover", _ns_inventory_turnover, _acc_inventory_turnover)
    var _acc_days_inventory_outstanding: Float64 = 0.0
    var _t0_days_inventory_outstanding = perf_counter_ns()
    for _ in range(N):
        _acc_days_inventory_outstanding += days_inventory_outstanding(0.5)
    var _t1_days_inventory_outstanding = perf_counter_ns()
    var _ns_days_inventory_outstanding = Float64(_t1_days_inventory_outstanding - _t0_days_inventory_outstanding) / Float64(N)
    print("MOJO_TIMING procurement::days_inventory_outstanding", _ns_days_inventory_outstanding, _acc_days_inventory_outstanding)
    var _acc_economic_order_quantity: Float64 = 0.0
    var _t0_economic_order_quantity = perf_counter_ns()
    for _ in range(N):
        _acc_economic_order_quantity += economic_order_quantity(0.5, 0.5, 0.5)
    var _t1_economic_order_quantity = perf_counter_ns()
    var _ns_economic_order_quantity = Float64(_t1_economic_order_quantity - _t0_economic_order_quantity) / Float64(N)
    print("MOJO_TIMING procurement::economic_order_quantity", _ns_economic_order_quantity, _acc_economic_order_quantity)
    var _acc_reorder_point: Float64 = 0.0
    var _t0_reorder_point = perf_counter_ns()
    for _ in range(N):
        _acc_reorder_point += reorder_point(0.5, 0.5, 0.5)
    var _t1_reorder_point = perf_counter_ns()
    var _ns_reorder_point = Float64(_t1_reorder_point - _t0_reorder_point) / Float64(N)
    print("MOJO_TIMING procurement::reorder_point", _ns_reorder_point, _acc_reorder_point)
    var _acc_safety_stock: Float64 = 0.0
    var _t0_safety_stock = perf_counter_ns()
    for _ in range(N):
        _acc_safety_stock += safety_stock(0.5, 0.5, 0.5)
    var _t1_safety_stock = perf_counter_ns()
    var _ns_safety_stock = Float64(_t1_safety_stock - _t0_safety_stock) / Float64(N)
    print("MOJO_TIMING procurement::safety_stock", _ns_safety_stock, _acc_safety_stock)
    var _acc_supplier_score_weighted: Float64 = 0.0
    var _t0_supplier_score_weighted = perf_counter_ns()
    for _ in range(N):
        _acc_supplier_score_weighted += supplier_score_weighted(0.5, 0.5)
    var _t1_supplier_score_weighted = perf_counter_ns()
    var _ns_supplier_score_weighted = Float64(_t1_supplier_score_weighted - _t0_supplier_score_weighted) / Float64(N)
    print("MOJO_TIMING procurement::supplier_score_weighted", _ns_supplier_score_weighted, _acc_supplier_score_weighted)
    var _acc_savings_percentage: Float64 = 0.0
    var _t0_savings_percentage = perf_counter_ns()
    for _ in range(N):
        _acc_savings_percentage += savings_percentage(0.5, 0.5)
    var _t1_savings_percentage = perf_counter_ns()
    var _ns_savings_percentage = Float64(_t1_savings_percentage - _t0_savings_percentage) / Float64(N)
    print("MOJO_TIMING procurement::savings_percentage", _ns_savings_percentage, _acc_savings_percentage)
    var _acc_maverick_spend_ratio: Float64 = 0.0
    var _t0_maverick_spend_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_maverick_spend_ratio += maverick_spend_ratio(0.5, 0.5)
    var _t1_maverick_spend_ratio = perf_counter_ns()
    var _ns_maverick_spend_ratio = Float64(_t1_maverick_spend_ratio - _t0_maverick_spend_ratio) / Float64(N)
    print("MOJO_TIMING procurement::maverick_spend_ratio", _ns_maverick_spend_ratio, _acc_maverick_spend_ratio)
    var _acc_payment_discount_annualized: Float64 = 0.0
    var _t0_payment_discount_annualized = perf_counter_ns()
    for _ in range(N):
        _acc_payment_discount_annualized += payment_discount_annualized(0.5, 0.5, 0.5)
    var _t1_payment_discount_annualized = perf_counter_ns()
    var _ns_payment_discount_annualized = Float64(_t1_payment_discount_annualized - _t0_payment_discount_annualized) / Float64(N)
    print("MOJO_TIMING procurement::payment_discount_annualized", _ns_payment_discount_annualized, _acc_payment_discount_annualized)
