"""bench_logistics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from logistics import vehicle_utilization, order_fill_rate, perfect_order_rate, inventory_turns, days_of_supply, warehouse_utilization, cost_per_unit_shipped, on_time_delivery_rate, dwell_time, cross_dock_throughput, route_efficiency, carbon_per_tonne_km
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

    var _acc_vehicle_utilization: Float64 = 0.0
    var _t0_vehicle_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_vehicle_utilization += vehicle_utilization(0.5, 0.5)
    var _t1_vehicle_utilization = perf_counter_ns()
    var _ns_vehicle_utilization = Float64(_t1_vehicle_utilization - _t0_vehicle_utilization) / Float64(N)
    print("MOJO_TIMING logistics::vehicle_utilization", _ns_vehicle_utilization, _acc_vehicle_utilization)
    var _result_vehicle_utilization = vehicle_utilization(0.5, 0.5)
    var _summary_vehicle_utilization = _summary_float64(_result_vehicle_utilization)
    print("MOJO_RESULT logistics::vehicle_utilization", _summary_vehicle_utilization)
    var _acc_order_fill_rate: Float64 = 0.0
    var _t0_order_fill_rate = perf_counter_ns()
    for _ in range(N):
        _acc_order_fill_rate += order_fill_rate(0.5, 0.5)
    var _t1_order_fill_rate = perf_counter_ns()
    var _ns_order_fill_rate = Float64(_t1_order_fill_rate - _t0_order_fill_rate) / Float64(N)
    print("MOJO_TIMING logistics::order_fill_rate", _ns_order_fill_rate, _acc_order_fill_rate)
    var _result_order_fill_rate = order_fill_rate(0.5, 0.5)
    var _summary_order_fill_rate = _summary_float64(_result_order_fill_rate)
    print("MOJO_RESULT logistics::order_fill_rate", _summary_order_fill_rate)
    var _acc_perfect_order_rate: Float64 = 0.0
    var _t0_perfect_order_rate = perf_counter_ns()
    for _ in range(N):
        _acc_perfect_order_rate += perfect_order_rate(0.5, 0.5)
    var _t1_perfect_order_rate = perf_counter_ns()
    var _ns_perfect_order_rate = Float64(_t1_perfect_order_rate - _t0_perfect_order_rate) / Float64(N)
    print("MOJO_TIMING logistics::perfect_order_rate", _ns_perfect_order_rate, _acc_perfect_order_rate)
    var _result_perfect_order_rate = perfect_order_rate(0.5, 0.5)
    var _summary_perfect_order_rate = _summary_float64(_result_perfect_order_rate)
    print("MOJO_RESULT logistics::perfect_order_rate", _summary_perfect_order_rate)
    var _acc_inventory_turns: Float64 = 0.0
    var _t0_inventory_turns = perf_counter_ns()
    for _ in range(N):
        _acc_inventory_turns += inventory_turns(0.5, 0.5)
    var _t1_inventory_turns = perf_counter_ns()
    var _ns_inventory_turns = Float64(_t1_inventory_turns - _t0_inventory_turns) / Float64(N)
    print("MOJO_TIMING logistics::inventory_turns", _ns_inventory_turns, _acc_inventory_turns)
    var _result_inventory_turns = inventory_turns(0.5, 0.5)
    var _summary_inventory_turns = _summary_float64(_result_inventory_turns)
    print("MOJO_RESULT logistics::inventory_turns", _summary_inventory_turns)
    var _acc_days_of_supply: Float64 = 0.0
    var _t0_days_of_supply = perf_counter_ns()
    for _ in range(N):
        _acc_days_of_supply += days_of_supply(0.5, 0.5)
    var _t1_days_of_supply = perf_counter_ns()
    var _ns_days_of_supply = Float64(_t1_days_of_supply - _t0_days_of_supply) / Float64(N)
    print("MOJO_TIMING logistics::days_of_supply", _ns_days_of_supply, _acc_days_of_supply)
    var _result_days_of_supply = days_of_supply(0.5, 0.5)
    var _summary_days_of_supply = _summary_float64(_result_days_of_supply)
    print("MOJO_RESULT logistics::days_of_supply", _summary_days_of_supply)
    var _acc_warehouse_utilization: Float64 = 0.0
    var _t0_warehouse_utilization = perf_counter_ns()
    for _ in range(N):
        _acc_warehouse_utilization += warehouse_utilization(0.5, 0.5)
    var _t1_warehouse_utilization = perf_counter_ns()
    var _ns_warehouse_utilization = Float64(_t1_warehouse_utilization - _t0_warehouse_utilization) / Float64(N)
    print("MOJO_TIMING logistics::warehouse_utilization", _ns_warehouse_utilization, _acc_warehouse_utilization)
    var _result_warehouse_utilization = warehouse_utilization(0.5, 0.5)
    var _summary_warehouse_utilization = _summary_float64(_result_warehouse_utilization)
    print("MOJO_RESULT logistics::warehouse_utilization", _summary_warehouse_utilization)
    var _acc_cost_per_unit_shipped: Float64 = 0.0
    var _t0_cost_per_unit_shipped = perf_counter_ns()
    for _ in range(N):
        _acc_cost_per_unit_shipped += cost_per_unit_shipped(0.5, 0.5)
    var _t1_cost_per_unit_shipped = perf_counter_ns()
    var _ns_cost_per_unit_shipped = Float64(_t1_cost_per_unit_shipped - _t0_cost_per_unit_shipped) / Float64(N)
    print("MOJO_TIMING logistics::cost_per_unit_shipped", _ns_cost_per_unit_shipped, _acc_cost_per_unit_shipped)
    var _result_cost_per_unit_shipped = cost_per_unit_shipped(0.5, 0.5)
    var _summary_cost_per_unit_shipped = _summary_float64(_result_cost_per_unit_shipped)
    print("MOJO_RESULT logistics::cost_per_unit_shipped", _summary_cost_per_unit_shipped)
    var _acc_on_time_delivery_rate: Float64 = 0.0
    var _t0_on_time_delivery_rate = perf_counter_ns()
    for _ in range(N):
        _acc_on_time_delivery_rate += on_time_delivery_rate(0.5, 0.5)
    var _t1_on_time_delivery_rate = perf_counter_ns()
    var _ns_on_time_delivery_rate = Float64(_t1_on_time_delivery_rate - _t0_on_time_delivery_rate) / Float64(N)
    print("MOJO_TIMING logistics::on_time_delivery_rate", _ns_on_time_delivery_rate, _acc_on_time_delivery_rate)
    var _result_on_time_delivery_rate = on_time_delivery_rate(0.5, 0.5)
    var _summary_on_time_delivery_rate = _summary_float64(_result_on_time_delivery_rate)
    print("MOJO_RESULT logistics::on_time_delivery_rate", _summary_on_time_delivery_rate)
    var _acc_dwell_time: Float64 = 0.0
    var _t0_dwell_time = perf_counter_ns()
    for _ in range(N):
        _acc_dwell_time += dwell_time(0.5, 0.5)
    var _t1_dwell_time = perf_counter_ns()
    var _ns_dwell_time = Float64(_t1_dwell_time - _t0_dwell_time) / Float64(N)
    print("MOJO_TIMING logistics::dwell_time", _ns_dwell_time, _acc_dwell_time)
    var _result_dwell_time = dwell_time(0.5, 0.5)
    var _summary_dwell_time = _summary_float64(_result_dwell_time)
    print("MOJO_RESULT logistics::dwell_time", _summary_dwell_time)
    var _acc_cross_dock_throughput: Float64 = 0.0
    var _t0_cross_dock_throughput = perf_counter_ns()
    for _ in range(N):
        _acc_cross_dock_throughput += cross_dock_throughput(0.5, 0.5)
    var _t1_cross_dock_throughput = perf_counter_ns()
    var _ns_cross_dock_throughput = Float64(_t1_cross_dock_throughput - _t0_cross_dock_throughput) / Float64(N)
    print("MOJO_TIMING logistics::cross_dock_throughput", _ns_cross_dock_throughput, _acc_cross_dock_throughput)
    var _result_cross_dock_throughput = cross_dock_throughput(0.5, 0.5)
    var _summary_cross_dock_throughput = _summary_float64(_result_cross_dock_throughput)
    print("MOJO_RESULT logistics::cross_dock_throughput", _summary_cross_dock_throughput)
    var _acc_route_efficiency: Float64 = 0.0
    var _t0_route_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_route_efficiency += route_efficiency(0.5, 0.5)
    var _t1_route_efficiency = perf_counter_ns()
    var _ns_route_efficiency = Float64(_t1_route_efficiency - _t0_route_efficiency) / Float64(N)
    print("MOJO_TIMING logistics::route_efficiency", _ns_route_efficiency, _acc_route_efficiency)
    var _result_route_efficiency = route_efficiency(0.5, 0.5)
    var _summary_route_efficiency = _summary_float64(_result_route_efficiency)
    print("MOJO_RESULT logistics::route_efficiency", _summary_route_efficiency)
    var _acc_carbon_per_tonne_km: Float64 = 0.0
    var _t0_carbon_per_tonne_km = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_per_tonne_km += carbon_per_tonne_km(0.5, 0.5, 0.5)
    var _t1_carbon_per_tonne_km = perf_counter_ns()
    var _ns_carbon_per_tonne_km = Float64(_t1_carbon_per_tonne_km - _t0_carbon_per_tonne_km) / Float64(N)
    print("MOJO_TIMING logistics::carbon_per_tonne_km", _ns_carbon_per_tonne_km, _acc_carbon_per_tonne_km)
    var _result_carbon_per_tonne_km = carbon_per_tonne_km(0.5, 0.5, 0.5)
    var _summary_carbon_per_tonne_km = _summary_float64(_result_carbon_per_tonne_km)
    print("MOJO_RESULT logistics::carbon_per_tonne_km", _summary_carbon_per_tonne_km)
