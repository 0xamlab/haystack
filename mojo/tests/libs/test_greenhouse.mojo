"""test_greenhouse.mojo — auto-generated tests for greenhouse library."""
from std.math import isnan, isinf
from greenhouse import heat_loss_conduction, ventilation_rate, solar_gain, heating_requirement, co2_enrichment_rate, light_supplementation_hours, irrigation_volume, growing_area_utilization, energy_cost_heating, yield_per_sq_meter, temperature_setpoint_night, shade_factor

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

    var _v_heat_loss_conduction = heat_loss_conduction(0.5, 0.5, 0.5)
    if is_finite(_v_heat_loss_conduction): passed += 1; print("  ✅ greenhouse::heat_loss_conduction =", _v_heat_loss_conduction)
    else: failed += 1; print("  ❌ greenhouse::heat_loss_conduction → non-finite:", _v_heat_loss_conduction)
    var _v_ventilation_rate = ventilation_rate(0.5, 0.5)
    if is_finite(_v_ventilation_rate): passed += 1; print("  ✅ greenhouse::ventilation_rate =", _v_ventilation_rate)
    else: failed += 1; print("  ❌ greenhouse::ventilation_rate → non-finite:", _v_ventilation_rate)
    var _v_solar_gain = solar_gain(0.5, 0.5, 0.5)
    if is_finite(_v_solar_gain): passed += 1; print("  ✅ greenhouse::solar_gain =", _v_solar_gain)
    else: failed += 1; print("  ❌ greenhouse::solar_gain → non-finite:", _v_solar_gain)
    var _v_heating_requirement = heating_requirement(0.5, 0.5)
    if is_finite(_v_heating_requirement): passed += 1; print("  ✅ greenhouse::heating_requirement =", _v_heating_requirement)
    else: failed += 1; print("  ❌ greenhouse::heating_requirement → non-finite:", _v_heating_requirement)
    var _v_co2_enrichment_rate = co2_enrichment_rate(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_co2_enrichment_rate): passed += 1; print("  ✅ greenhouse::co2_enrichment_rate =", _v_co2_enrichment_rate)
    else: failed += 1; print("  ❌ greenhouse::co2_enrichment_rate → non-finite:", _v_co2_enrichment_rate)
    var _v_light_supplementation_hours = light_supplementation_hours(0.5, 0.5, 0.5)
    if is_finite(_v_light_supplementation_hours): passed += 1; print("  ✅ greenhouse::light_supplementation_hours =", _v_light_supplementation_hours)
    else: failed += 1; print("  ❌ greenhouse::light_supplementation_hours → non-finite:", _v_light_supplementation_hours)
    var _v_irrigation_volume = irrigation_volume(0.5, 0.5, 0.5)
    if is_finite(_v_irrigation_volume): passed += 1; print("  ✅ greenhouse::irrigation_volume =", _v_irrigation_volume)
    else: failed += 1; print("  ❌ greenhouse::irrigation_volume → non-finite:", _v_irrigation_volume)
    var _v_growing_area_utilization = growing_area_utilization(0.5, 0.5)
    if is_finite(_v_growing_area_utilization): passed += 1; print("  ✅ greenhouse::growing_area_utilization =", _v_growing_area_utilization)
    else: failed += 1; print("  ❌ greenhouse::growing_area_utilization → non-finite:", _v_growing_area_utilization)
    var _v_energy_cost_heating = energy_cost_heating(0.5, 0.5)
    if is_finite(_v_energy_cost_heating): passed += 1; print("  ✅ greenhouse::energy_cost_heating =", _v_energy_cost_heating)
    else: failed += 1; print("  ❌ greenhouse::energy_cost_heating → non-finite:", _v_energy_cost_heating)
    var _v_yield_per_sq_meter = yield_per_sq_meter(0.5, 0.5)
    if is_finite(_v_yield_per_sq_meter): passed += 1; print("  ✅ greenhouse::yield_per_sq_meter =", _v_yield_per_sq_meter)
    else: failed += 1; print("  ❌ greenhouse::yield_per_sq_meter → non-finite:", _v_yield_per_sq_meter)
    var _v_temperature_setpoint_night = temperature_setpoint_night(0.5, 0.5)
    if is_finite(_v_temperature_setpoint_night): passed += 1; print("  ✅ greenhouse::temperature_setpoint_night =", _v_temperature_setpoint_night)
    else: failed += 1; print("  ❌ greenhouse::temperature_setpoint_night → non-finite:", _v_temperature_setpoint_night)
    var _v_shade_factor = shade_factor(0.5)
    if is_finite(_v_shade_factor): passed += 1; print("  ✅ greenhouse::shade_factor =", _v_shade_factor)
    else: failed += 1; print("  ❌ greenhouse::shade_factor → non-finite:", _v_shade_factor)

    print("  [greenhouse] Passed:", passed, "Failed:", failed)
