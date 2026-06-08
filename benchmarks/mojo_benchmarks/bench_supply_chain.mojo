"""bench_supply_chain.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from supply_chain import lead_time_demand, bullwhip_effect, forecast_error_mae, forecast_error_mape, forecast_bias, tracking_signal, economic_production_qty, total_cost_of_ownership, service_level_type1, fill_rate_type2, moving_average_forecast, exponential_smoothing_forecast
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

    var _acc_lead_time_demand: Float64 = 0.0
    var _t0_lead_time_demand = perf_counter_ns()
    for _ in range(N):
        _acc_lead_time_demand += lead_time_demand(0.5, 0.5)
    var _t1_lead_time_demand = perf_counter_ns()
    var _ns_lead_time_demand = Float64(_t1_lead_time_demand - _t0_lead_time_demand) / Float64(N)
    print("MOJO_TIMING supply_chain::lead_time_demand", _ns_lead_time_demand, _acc_lead_time_demand)
    var _result_lead_time_demand = lead_time_demand(0.5, 0.5)
    var _summary_lead_time_demand = _summary_float64(_result_lead_time_demand)
    print("MOJO_RESULT supply_chain::lead_time_demand", _summary_lead_time_demand)
    var _acc_bullwhip_effect: Float64 = 0.0
    var _t0_bullwhip_effect = perf_counter_ns()
    for _ in range(N):
        _acc_bullwhip_effect += bullwhip_effect(0.5, 0.5)
    var _t1_bullwhip_effect = perf_counter_ns()
    var _ns_bullwhip_effect = Float64(_t1_bullwhip_effect - _t0_bullwhip_effect) / Float64(N)
    print("MOJO_TIMING supply_chain::bullwhip_effect", _ns_bullwhip_effect, _acc_bullwhip_effect)
    var _result_bullwhip_effect = bullwhip_effect(0.5, 0.5)
    var _summary_bullwhip_effect = _summary_float64(_result_bullwhip_effect)
    print("MOJO_RESULT supply_chain::bullwhip_effect", _summary_bullwhip_effect)
    var _acc_forecast_error_mae: Float64 = 0.0
    var _t0_forecast_error_mae = perf_counter_ns()
    for _ in range(N):
        _acc_forecast_error_mae += forecast_error_mae(_lf5, _lf5)
    var _t1_forecast_error_mae = perf_counter_ns()
    var _ns_forecast_error_mae = Float64(_t1_forecast_error_mae - _t0_forecast_error_mae) / Float64(N)
    print("MOJO_TIMING supply_chain::forecast_error_mae", _ns_forecast_error_mae, _acc_forecast_error_mae)
    var _result_forecast_error_mae = forecast_error_mae(_lf5, _lf5)
    var _summary_forecast_error_mae = _summary_float64(_result_forecast_error_mae)
    print("MOJO_RESULT supply_chain::forecast_error_mae", _summary_forecast_error_mae)
    var _acc_forecast_error_mape: Float64 = 0.0
    var _t0_forecast_error_mape = perf_counter_ns()
    for _ in range(N):
        _acc_forecast_error_mape += forecast_error_mape(_lf5, _lf5)
    var _t1_forecast_error_mape = perf_counter_ns()
    var _ns_forecast_error_mape = Float64(_t1_forecast_error_mape - _t0_forecast_error_mape) / Float64(N)
    print("MOJO_TIMING supply_chain::forecast_error_mape", _ns_forecast_error_mape, _acc_forecast_error_mape)
    var _result_forecast_error_mape = forecast_error_mape(_lf5, _lf5)
    var _summary_forecast_error_mape = _summary_float64(_result_forecast_error_mape)
    print("MOJO_RESULT supply_chain::forecast_error_mape", _summary_forecast_error_mape)
    var _acc_forecast_bias: Float64 = 0.0
    var _t0_forecast_bias = perf_counter_ns()
    for _ in range(N):
        _acc_forecast_bias += forecast_bias(_lf5, _lf5)
    var _t1_forecast_bias = perf_counter_ns()
    var _ns_forecast_bias = Float64(_t1_forecast_bias - _t0_forecast_bias) / Float64(N)
    print("MOJO_TIMING supply_chain::forecast_bias", _ns_forecast_bias, _acc_forecast_bias)
    var _result_forecast_bias = forecast_bias(_lf5, _lf5)
    var _summary_forecast_bias = _summary_float64(_result_forecast_bias)
    print("MOJO_RESULT supply_chain::forecast_bias", _summary_forecast_bias)
    var _acc_tracking_signal: Float64 = 0.0
    var _t0_tracking_signal = perf_counter_ns()
    for _ in range(N):
        _acc_tracking_signal += tracking_signal(_lf5, _lf5)
    var _t1_tracking_signal = perf_counter_ns()
    var _ns_tracking_signal = Float64(_t1_tracking_signal - _t0_tracking_signal) / Float64(N)
    print("MOJO_TIMING supply_chain::tracking_signal", _ns_tracking_signal, _acc_tracking_signal)
    var _result_tracking_signal = tracking_signal(_lf5, _lf5)
    var _summary_tracking_signal = _summary_float64(_result_tracking_signal)
    print("MOJO_RESULT supply_chain::tracking_signal", _summary_tracking_signal)
    var _acc_economic_production_qty: Float64 = 0.0
    var _t0_economic_production_qty = perf_counter_ns()
    for _ in range(N):
        _acc_economic_production_qty += economic_production_qty(0.5, 0.5, 0.5, 0.5)
    var _t1_economic_production_qty = perf_counter_ns()
    var _ns_economic_production_qty = Float64(_t1_economic_production_qty - _t0_economic_production_qty) / Float64(N)
    print("MOJO_TIMING supply_chain::economic_production_qty", _ns_economic_production_qty, _acc_economic_production_qty)
    var _result_economic_production_qty = economic_production_qty(0.5, 0.5, 0.5, 0.5)
    var _summary_economic_production_qty = _summary_float64(_result_economic_production_qty)
    print("MOJO_RESULT supply_chain::economic_production_qty", _summary_economic_production_qty)
    var _acc_total_cost_of_ownership: Float64 = 0.0
    var _t0_total_cost_of_ownership = perf_counter_ns()
    for _ in range(N):
        _acc_total_cost_of_ownership += total_cost_of_ownership(0.5, 0.5, 0.5, 0.5)
    var _t1_total_cost_of_ownership = perf_counter_ns()
    var _ns_total_cost_of_ownership = Float64(_t1_total_cost_of_ownership - _t0_total_cost_of_ownership) / Float64(N)
    print("MOJO_TIMING supply_chain::total_cost_of_ownership", _ns_total_cost_of_ownership, _acc_total_cost_of_ownership)
    var _result_total_cost_of_ownership = total_cost_of_ownership(0.5, 0.5, 0.5, 0.5)
    var _summary_total_cost_of_ownership = _summary_float64(_result_total_cost_of_ownership)
    print("MOJO_RESULT supply_chain::total_cost_of_ownership", _summary_total_cost_of_ownership)
    var _acc_service_level_type1: Float64 = 0.0
    var _t0_service_level_type1 = perf_counter_ns()
    for _ in range(N):
        _acc_service_level_type1 += service_level_type1(0.5)
    var _t1_service_level_type1 = perf_counter_ns()
    var _ns_service_level_type1 = Float64(_t1_service_level_type1 - _t0_service_level_type1) / Float64(N)
    print("MOJO_TIMING supply_chain::service_level_type1", _ns_service_level_type1, _acc_service_level_type1)
    var _result_service_level_type1 = service_level_type1(0.5)
    var _summary_service_level_type1 = _summary_float64(_result_service_level_type1)
    print("MOJO_RESULT supply_chain::service_level_type1", _summary_service_level_type1)
    var _acc_fill_rate_type2: Float64 = 0.0
    var _t0_fill_rate_type2 = perf_counter_ns()
    for _ in range(N):
        _acc_fill_rate_type2 += fill_rate_type2(0.5, 0.5)
    var _t1_fill_rate_type2 = perf_counter_ns()
    var _ns_fill_rate_type2 = Float64(_t1_fill_rate_type2 - _t0_fill_rate_type2) / Float64(N)
    print("MOJO_TIMING supply_chain::fill_rate_type2", _ns_fill_rate_type2, _acc_fill_rate_type2)
    var _result_fill_rate_type2 = fill_rate_type2(0.5, 0.5)
    var _summary_fill_rate_type2 = _summary_float64(_result_fill_rate_type2)
    print("MOJO_RESULT supply_chain::fill_rate_type2", _summary_fill_rate_type2)
    var _acc_moving_average_forecast: Float64 = 0.0
    var _t0_moving_average_forecast = perf_counter_ns()
    for _ in range(N):
        _acc_moving_average_forecast += moving_average_forecast(_lf5, 5)
    var _t1_moving_average_forecast = perf_counter_ns()
    var _ns_moving_average_forecast = Float64(_t1_moving_average_forecast - _t0_moving_average_forecast) / Float64(N)
    print("MOJO_TIMING supply_chain::moving_average_forecast", _ns_moving_average_forecast, _acc_moving_average_forecast)
    var _result_moving_average_forecast = moving_average_forecast(_lf5, 5)
    var _summary_moving_average_forecast = _summary_float64(_result_moving_average_forecast)
    print("MOJO_RESULT supply_chain::moving_average_forecast", _summary_moving_average_forecast)
    var _acc_exponential_smoothing_forecast: Float64 = 0.0
    var _t0_exponential_smoothing_forecast = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_smoothing_forecast += exponential_smoothing_forecast(_lf5, 0.5)
    var _t1_exponential_smoothing_forecast = perf_counter_ns()
    var _ns_exponential_smoothing_forecast = Float64(_t1_exponential_smoothing_forecast - _t0_exponential_smoothing_forecast) / Float64(N)
    print("MOJO_TIMING supply_chain::exponential_smoothing_forecast", _ns_exponential_smoothing_forecast, _acc_exponential_smoothing_forecast)
    var _result_exponential_smoothing_forecast = exponential_smoothing_forecast(_lf5, 0.5)
    var _summary_exponential_smoothing_forecast = _summary_float64(_result_exponential_smoothing_forecast)
    print("MOJO_RESULT supply_chain::exponential_smoothing_forecast", _summary_exponential_smoothing_forecast)
