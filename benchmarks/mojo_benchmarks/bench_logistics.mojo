"""bench_logistics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from logistics import vehicle_utilization, order_fill_rate, perfect_order_rate, inventory_turns, days_of_supply, warehouse_utilization, cost_per_unit_shipped, on_time_delivery_rate, dwell_time, cross_dock_throughput, route_efficiency, carbon_per_tonne_km
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

    var _acc_vehicle_utilization: Float64 = 0.0
    var _t0_vehicle_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_vehicle_utilization += vehicle_utilization(0.5, 0.5)
    var _t1_vehicle_utilization = perf_counter_ns()
    var _ns_vehicle_utilization = Float64(_t1_vehicle_utilization - _t0_vehicle_utilization) / Float64(N)
    print("MOJO_TIMING logistics::vehicle_utilization", _ns_vehicle_utilization, _acc_vehicle_utilization)
    var _acc_order_fill_rate: Float64 = 0.0
    var _t0_order_fill_rate = perf_counter_ns()
    for _ in range(N):
        _acc_order_fill_rate += order_fill_rate(0.5, 0.5)
    var _t1_order_fill_rate = perf_counter_ns()
    var _ns_order_fill_rate = Float64(_t1_order_fill_rate - _t0_order_fill_rate) / Float64(N)
    print("MOJO_TIMING logistics::order_fill_rate", _ns_order_fill_rate, _acc_order_fill_rate)
    var _acc_perfect_order_rate: Float64 = 0.0
    var _t0_perfect_order_rate = perf_counter_ns()
    for _ in range(N):
        _acc_perfect_order_rate += perfect_order_rate(0.5, 0.5)
    var _t1_perfect_order_rate = perf_counter_ns()
    var _ns_perfect_order_rate = Float64(_t1_perfect_order_rate - _t0_perfect_order_rate) / Float64(N)
    print("MOJO_TIMING logistics::perfect_order_rate", _ns_perfect_order_rate, _acc_perfect_order_rate)
    var _acc_inventory_turns: Float64 = 0.0
    var _t0_inventory_turns = perf_counter_ns()
    for _ in range(N):
        _acc_inventory_turns += inventory_turns(0.5, 0.5)
    var _t1_inventory_turns = perf_counter_ns()
    var _ns_inventory_turns = Float64(_t1_inventory_turns - _t0_inventory_turns) / Float64(N)
    print("MOJO_TIMING logistics::inventory_turns", _ns_inventory_turns, _acc_inventory_turns)
    var _acc_days_of_supply: Float64 = 0.0
    var _t0_days_of_supply = perf_counter_ns()
    for _ in range(N):
        _acc_days_of_supply += days_of_supply(0.5, 0.5)
    var _t1_days_of_supply = perf_counter_ns()
    var _ns_days_of_supply = Float64(_t1_days_of_supply - _t0_days_of_supply) / Float64(N)
    print("MOJO_TIMING logistics::days_of_supply", _ns_days_of_supply, _acc_days_of_supply)
    var _acc_warehouse_utilization: Float64 = 0.0
    var _t0_warehouse_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_warehouse_utilization += warehouse_utilization(0.5, 0.5)
    var _t1_warehouse_utilization = perf_counter_ns()
    var _ns_warehouse_utilization = Float64(_t1_warehouse_utilization - _t0_warehouse_utilization) / Float64(N)
    print("MOJO_TIMING logistics::warehouse_utilization", _ns_warehouse_utilization, _acc_warehouse_utilization)
    var _acc_cost_per_unit_shipped: Float64 = 0.0
    var _t0_cost_per_unit_shipped = perf_counter_ns()
    for _ in range(N):
        _acc_cost_per_unit_shipped += cost_per_unit_shipped(0.5, 0.5)
    var _t1_cost_per_unit_shipped = perf_counter_ns()
    var _ns_cost_per_unit_shipped = Float64(_t1_cost_per_unit_shipped - _t0_cost_per_unit_shipped) / Float64(N)
    print("MOJO_TIMING logistics::cost_per_unit_shipped", _ns_cost_per_unit_shipped, _acc_cost_per_unit_shipped)
    var _acc_on_time_delivery_rate: Float64 = 0.0
    var _t0_on_time_delivery_rate = perf_counter_ns()
    for _ in range(N):
        _acc_on_time_delivery_rate += on_time_delivery_rate(0.5, 0.5)
    var _t1_on_time_delivery_rate = perf_counter_ns()
    var _ns_on_time_delivery_rate = Float64(_t1_on_time_delivery_rate - _t0_on_time_delivery_rate) / Float64(N)
    print("MOJO_TIMING logistics::on_time_delivery_rate", _ns_on_time_delivery_rate, _acc_on_time_delivery_rate)
    var _acc_dwell_time: Float64 = 0.0
    var _t0_dwell_time = perf_counter_ns()
    for _ in range(N):
        _acc_dwell_time += dwell_time(0.5, 0.5)
    var _t1_dwell_time = perf_counter_ns()
    var _ns_dwell_time = Float64(_t1_dwell_time - _t0_dwell_time) / Float64(N)
    print("MOJO_TIMING logistics::dwell_time", _ns_dwell_time, _acc_dwell_time)
    var _acc_cross_dock_throughput: Float64 = 0.0
    var _t0_cross_dock_throughput = perf_counter_ns()
    for _ in range(N):
        _acc_cross_dock_throughput += cross_dock_throughput(0.5, 0.5)
    var _t1_cross_dock_throughput = perf_counter_ns()
    var _ns_cross_dock_throughput = Float64(_t1_cross_dock_throughput - _t0_cross_dock_throughput) / Float64(N)
    print("MOJO_TIMING logistics::cross_dock_throughput", _ns_cross_dock_throughput, _acc_cross_dock_throughput)
    var _acc_route_efficiency: Float64 = 0.0
    var _t0_route_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_route_efficiency += route_efficiency(0.5, 0.5)
    var _t1_route_efficiency = perf_counter_ns()
    var _ns_route_efficiency = Float64(_t1_route_efficiency - _t0_route_efficiency) / Float64(N)
    print("MOJO_TIMING logistics::route_efficiency", _ns_route_efficiency, _acc_route_efficiency)
    var _acc_carbon_per_tonne_km: Float64 = 0.0
    var _t0_carbon_per_tonne_km = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_per_tonne_km += carbon_per_tonne_km(0.5, 0.5, 0.5)
    var _t1_carbon_per_tonne_km = perf_counter_ns()
    var _ns_carbon_per_tonne_km = Float64(_t1_carbon_per_tonne_km - _t0_carbon_per_tonne_km) / Float64(N)
    print("MOJO_TIMING logistics::carbon_per_tonne_km", _ns_carbon_per_tonne_km, _acc_carbon_per_tonne_km)
