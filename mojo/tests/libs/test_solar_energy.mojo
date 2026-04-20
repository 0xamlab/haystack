"""test_solar_energy.mojo — auto-generated tests for solar_energy library."""
from std.math import isnan, isinf
from solar_energy import solar_irradiance_on_surface, panel_power_output, temperature_derate, cell_temperature_noct, solar_declination, hour_angle, solar_altitude, capacity_factor_solar, lcoe, payback_period, inverter_efficiency, string_voltage

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

    var _v_solar_irradiance_on_surface = solar_irradiance_on_surface(0.5, 0.5)
    if is_finite(_v_solar_irradiance_on_surface): passed += 1; print("  ✅ solar_energy::solar_irradiance_on_surface =", _v_solar_irradiance_on_surface)
    else: failed += 1; print("  ❌ solar_energy::solar_irradiance_on_surface → non-finite:", _v_solar_irradiance_on_surface)
    var _v_panel_power_output = panel_power_output(0.5, 0.5, 0.5)
    if is_finite(_v_panel_power_output): passed += 1; print("  ✅ solar_energy::panel_power_output =", _v_panel_power_output)
    else: failed += 1; print("  ❌ solar_energy::panel_power_output → non-finite:", _v_panel_power_output)
    var _v_temperature_derate = temperature_derate(0.5, 0.5, 0.5, 0.5)
    if is_finite(_v_temperature_derate): passed += 1; print("  ✅ solar_energy::temperature_derate =", _v_temperature_derate)
    else: failed += 1; print("  ❌ solar_energy::temperature_derate → non-finite:", _v_temperature_derate)
    var _v_cell_temperature_noct = cell_temperature_noct(0.5, 0.5, 0.5)
    if is_finite(_v_cell_temperature_noct): passed += 1; print("  ✅ solar_energy::cell_temperature_noct =", _v_cell_temperature_noct)
    else: failed += 1; print("  ❌ solar_energy::cell_temperature_noct → non-finite:", _v_cell_temperature_noct)
    var _v_solar_declination = solar_declination(0.5)
    if is_finite(_v_solar_declination): passed += 1; print("  ✅ solar_energy::solar_declination =", _v_solar_declination)
    else: failed += 1; print("  ❌ solar_energy::solar_declination → non-finite:", _v_solar_declination)
    var _v_hour_angle = hour_angle(0.5)
    if is_finite(_v_hour_angle): passed += 1; print("  ✅ solar_energy::hour_angle =", _v_hour_angle)
    else: failed += 1; print("  ❌ solar_energy::hour_angle → non-finite:", _v_hour_angle)
    var _v_solar_altitude = solar_altitude(0.5, 0.5, 0.5)
    if is_finite(_v_solar_altitude): passed += 1; print("  ✅ solar_energy::solar_altitude =", _v_solar_altitude)
    else: failed += 1; print("  ❌ solar_energy::solar_altitude → non-finite:", _v_solar_altitude)
    var _v_capacity_factor_solar = capacity_factor_solar(0.5, 0.5, 0.5)
    if is_finite(_v_capacity_factor_solar): passed += 1; print("  ✅ solar_energy::capacity_factor_solar =", _v_capacity_factor_solar)
    else: failed += 1; print("  ❌ solar_energy::capacity_factor_solar → non-finite:", _v_capacity_factor_solar)
    var _v_lcoe = lcoe(0.5, 0.5)
    if is_finite(_v_lcoe): passed += 1; print("  ✅ solar_energy::lcoe =", _v_lcoe)
    else: failed += 1; print("  ❌ solar_energy::lcoe → non-finite:", _v_lcoe)
    var _v_payback_period = payback_period(0.5, 0.5)
    if is_finite(_v_payback_period): passed += 1; print("  ✅ solar_energy::payback_period =", _v_payback_period)
    else: failed += 1; print("  ❌ solar_energy::payback_period → non-finite:", _v_payback_period)
    var _v_inverter_efficiency = inverter_efficiency(0.5, 0.5)
    if is_finite(_v_inverter_efficiency): passed += 1; print("  ✅ solar_energy::inverter_efficiency =", _v_inverter_efficiency)
    else: failed += 1; print("  ❌ solar_energy::inverter_efficiency → non-finite:", _v_inverter_efficiency)
    var _v_string_voltage = string_voltage(0.5, 0.5)
    if is_finite(_v_string_voltage): passed += 1; print("  ✅ solar_energy::string_voltage =", _v_string_voltage)
    else: failed += 1; print("  ❌ solar_energy::string_voltage → non-finite:", _v_string_voltage)

    print("  [solar_energy] Passed:", passed, "Failed:", failed)
