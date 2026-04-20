"""bench_supply_chain.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from supply_chain import lead_time_demand, bullwhip_effect, forecast_error_mae, forecast_error_mape, forecast_bias, tracking_signal, economic_production_qty, total_cost_of_ownership, service_level_type1, fill_rate_type2, moving_average_forecast, exponential_smoothing_forecast
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

    var _acc_lead_time_demand: Float64 = 0.0
    var _t0_lead_time_demand = perf_counter_ns()
    for _ in range(N):
        _acc_lead_time_demand += lead_time_demand(0.5, 0.5)
    var _t1_lead_time_demand = perf_counter_ns()
    var _ns_lead_time_demand = Float64(_t1_lead_time_demand - _t0_lead_time_demand) / Float64(N)
    print("MOJO_TIMING supply_chain::lead_time_demand", _ns_lead_time_demand, _acc_lead_time_demand)
    var _acc_bullwhip_effect: Float64 = 0.0
    var _t0_bullwhip_effect = perf_counter_ns()
    for _ in range(N):
        _acc_bullwhip_effect += bullwhip_effect(0.5, 0.5)
    var _t1_bullwhip_effect = perf_counter_ns()
    var _ns_bullwhip_effect = Float64(_t1_bullwhip_effect - _t0_bullwhip_effect) / Float64(N)
    print("MOJO_TIMING supply_chain::bullwhip_effect", _ns_bullwhip_effect, _acc_bullwhip_effect)
    var _acc_forecast_error_mae: Float64 = 0.0
    var _t0_forecast_error_mae = perf_counter_ns()
    for _ in range(N):
        _acc_forecast_error_mae += forecast_error_mae(_lf5, _lf5)
    var _t1_forecast_error_mae = perf_counter_ns()
    var _ns_forecast_error_mae = Float64(_t1_forecast_error_mae - _t0_forecast_error_mae) / Float64(N)
    print("MOJO_TIMING supply_chain::forecast_error_mae", _ns_forecast_error_mae, _acc_forecast_error_mae)
    var _acc_forecast_error_mape: Float64 = 0.0
    var _t0_forecast_error_mape = perf_counter_ns()
    for _ in range(N):
        _acc_forecast_error_mape += forecast_error_mape(_lf5, _lf5)
    var _t1_forecast_error_mape = perf_counter_ns()
    var _ns_forecast_error_mape = Float64(_t1_forecast_error_mape - _t0_forecast_error_mape) / Float64(N)
    print("MOJO_TIMING supply_chain::forecast_error_mape", _ns_forecast_error_mape, _acc_forecast_error_mape)
    var _acc_forecast_bias: Float64 = 0.0
    var _t0_forecast_bias = perf_counter_ns()
    for _ in range(N):
        _acc_forecast_bias += forecast_bias(_lf5, _lf5)
    var _t1_forecast_bias = perf_counter_ns()
    var _ns_forecast_bias = Float64(_t1_forecast_bias - _t0_forecast_bias) / Float64(N)
    print("MOJO_TIMING supply_chain::forecast_bias", _ns_forecast_bias, _acc_forecast_bias)
    var _acc_tracking_signal: Float64 = 0.0
    var _t0_tracking_signal = perf_counter_ns()
    for _ in range(N):
        _acc_tracking_signal += tracking_signal(_lf5, _lf5)
    var _t1_tracking_signal = perf_counter_ns()
    var _ns_tracking_signal = Float64(_t1_tracking_signal - _t0_tracking_signal) / Float64(N)
    print("MOJO_TIMING supply_chain::tracking_signal", _ns_tracking_signal, _acc_tracking_signal)
    var _acc_economic_production_qty: Float64 = 0.0
    var _t0_economic_production_qty = perf_counter_ns()
    for _ in range(N):
        _acc_economic_production_qty += economic_production_qty(0.5, 0.5, 0.5, 0.5)
    var _t1_economic_production_qty = perf_counter_ns()
    var _ns_economic_production_qty = Float64(_t1_economic_production_qty - _t0_economic_production_qty) / Float64(N)
    print("MOJO_TIMING supply_chain::economic_production_qty", _ns_economic_production_qty, _acc_economic_production_qty)
    var _acc_total_cost_of_ownership: Float64 = 0.0
    var _t0_total_cost_of_ownership = perf_counter_ns()
    for _ in range(N):
        _acc_total_cost_of_ownership += total_cost_of_ownership(0.5, 0.5, 0.5, 0.5)
    var _t1_total_cost_of_ownership = perf_counter_ns()
    var _ns_total_cost_of_ownership = Float64(_t1_total_cost_of_ownership - _t0_total_cost_of_ownership) / Float64(N)
    print("MOJO_TIMING supply_chain::total_cost_of_ownership", _ns_total_cost_of_ownership, _acc_total_cost_of_ownership)
    var _acc_service_level_type1: Float64 = 0.0
    var _t0_service_level_type1 = perf_counter_ns()
    for _ in range(N):
        _acc_service_level_type1 += service_level_type1(0.5)
    var _t1_service_level_type1 = perf_counter_ns()
    var _ns_service_level_type1 = Float64(_t1_service_level_type1 - _t0_service_level_type1) / Float64(N)
    print("MOJO_TIMING supply_chain::service_level_type1", _ns_service_level_type1, _acc_service_level_type1)
    var _acc_fill_rate_type2: Float64 = 0.0
    var _t0_fill_rate_type2 = perf_counter_ns()
    for _ in range(N):
        _acc_fill_rate_type2 += fill_rate_type2(0.5, 0.5)
    var _t1_fill_rate_type2 = perf_counter_ns()
    var _ns_fill_rate_type2 = Float64(_t1_fill_rate_type2 - _t0_fill_rate_type2) / Float64(N)
    print("MOJO_TIMING supply_chain::fill_rate_type2", _ns_fill_rate_type2, _acc_fill_rate_type2)
    var _acc_moving_average_forecast: Float64 = 0.0
    var _t0_moving_average_forecast = perf_counter_ns()
    for _ in range(N):
        _acc_moving_average_forecast += moving_average_forecast(_lf5, 5)
    var _t1_moving_average_forecast = perf_counter_ns()
    var _ns_moving_average_forecast = Float64(_t1_moving_average_forecast - _t0_moving_average_forecast) / Float64(N)
    print("MOJO_TIMING supply_chain::moving_average_forecast", _ns_moving_average_forecast, _acc_moving_average_forecast)
    var _acc_exponential_smoothing_forecast: Float64 = 0.0
    var _t0_exponential_smoothing_forecast = perf_counter_ns()
    for _ in range(N):
        _acc_exponential_smoothing_forecast += exponential_smoothing_forecast(_lf5, 0.5)
    var _t1_exponential_smoothing_forecast = perf_counter_ns()
    var _ns_exponential_smoothing_forecast = Float64(_t1_exponential_smoothing_forecast - _t0_exponential_smoothing_forecast) / Float64(N)
    print("MOJO_TIMING supply_chain::exponential_smoothing_forecast", _ns_exponential_smoothing_forecast, _acc_exponential_smoothing_forecast)
