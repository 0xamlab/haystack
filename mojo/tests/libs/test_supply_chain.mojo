"""test_supply_chain.mojo — auto-generated tests for supply_chain library."""
from std.math import isnan, isinf
from supply_chain import lead_time_demand, bullwhip_effect, forecast_error_mae, forecast_error_mape, forecast_bias, tracking_signal, economic_production_qty, total_cost_of_ownership, service_level_type1, fill_rate_type2, moving_average_forecast, exponential_smoothing_forecast

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_lead_time_demand = lead_time_demand(0.5, 0.5)
    if is_finite(_v_lead_time_demand): passed += 1; print("  ✅ supply_chain::lead_time_demand =", _v_lead_time_demand)
    else: failed += 1; print("  ❌ supply_chain::lead_time_demand → non-finite:", _v_lead_time_demand)
    var _v_bullwhip_effect = bullwhip_effect(0.5, 0.5)
    if is_finite(_v_bullwhip_effect): passed += 1; print("  ✅ supply_chain::bullwhip_effect =", _v_bullwhip_effect)
    else: failed += 1; print("  ❌ supply_chain::bullwhip_effect → non-finite:", _v_bullwhip_effect)
    var _v_forecast_error_mae = forecast_error_mae(_lf5, _lf5)
    if is_finite(_v_forecast_error_mae): passed += 1; print("  ✅ supply_chain::forecast_error_mae =", _v_forecast_error_mae)
    else: failed += 1; print("  ❌ supply_chain::forecast_error_mae → non-finite:", _v_forecast_error_mae)
    var _v_forecast_error_mape = forecast_error_mape(_lf5, _lf5)
    if is_finite(_v_forecast_error_mape): passed += 1; print("  ✅ supply_chain::forecast_error_mape =", _v_forecast_error_mape)
    else: failed += 1; print("  ❌ supply_chain::forecast_error_mape → non-finite:", _v_forecast_error_mape)
    var _v_forecast_bias = forecast_bias(_lf5, _lf5)
    if is_finite(_v_forecast_bias): passed += 1; print("  ✅ supply_chain::forecast_bias =", _v_forecast_bias)
    else: failed += 1; print("  ❌ supply_chain::forecast_bias → non-finite:", _v_forecast_bias)
    var _v_tracking_signal = tracking_signal(_lf5, _lf5)
    if is_finite(_v_tracking_signal): passed += 1; print("  ✅ supply_chain::tracking_signal =", _v_tracking_signal)
    else: failed += 1; print("  ❌ supply_chain::tracking_signal → non-finite:", _v_tracking_signal)
    var _v_economic_production_qty = economic_production_qty(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_economic_production_qty): passed += 1; print("  ✅ supply_chain::economic_production_qty =", _v_economic_production_qty)
    else: failed += 1; print("  ❌ supply_chain::economic_production_qty → non-finite:", _v_economic_production_qty)
    var _v_total_cost_of_ownership = total_cost_of_ownership(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_total_cost_of_ownership): passed += 1; print("  ✅ supply_chain::total_cost_of_ownership =", _v_total_cost_of_ownership)
    else: failed += 1; print("  ❌ supply_chain::total_cost_of_ownership → non-finite:", _v_total_cost_of_ownership)
    var _v_service_level_type1 = service_level_type1(0.5)
    if is_finite(_v_service_level_type1): passed += 1; print("  ✅ supply_chain::service_level_type1 =", _v_service_level_type1)
    else: failed += 1; print("  ❌ supply_chain::service_level_type1 → non-finite:", _v_service_level_type1)
    var _v_fill_rate_type2 = fill_rate_type2(0.5, 0.5)
    if is_finite(_v_fill_rate_type2): passed += 1; print("  ✅ supply_chain::fill_rate_type2 =", _v_fill_rate_type2)
    else: failed += 1; print("  ❌ supply_chain::fill_rate_type2 → non-finite:", _v_fill_rate_type2)
    var _v_moving_average_forecast = moving_average_forecast(_lf5, 5)
    if is_finite(_v_moving_average_forecast): passed += 1; print("  ✅ supply_chain::moving_average_forecast =", _v_moving_average_forecast)
    else: failed += 1; print("  ❌ supply_chain::moving_average_forecast → non-finite:", _v_moving_average_forecast)
    var _v_exponential_smoothing_forecast = exponential_smoothing_forecast(_lf5, 0.5)
    if is_finite(_v_exponential_smoothing_forecast): passed += 1; print("  ✅ supply_chain::exponential_smoothing_forecast =", _v_exponential_smoothing_forecast)
    else: failed += 1; print("  ❌ supply_chain::exponential_smoothing_forecast → non-finite:", _v_exponential_smoothing_forecast)

    print("  [supply_chain] Passed:", passed, "Failed:", failed)
