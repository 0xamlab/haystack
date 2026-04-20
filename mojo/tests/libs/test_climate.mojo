"""test_climate.mojo — auto-generated tests for climate library."""
from std.math import isnan, isinf
from climate import celsius_to_fahrenheit, fahrenheit_to_celsius, heat_index, wind_chill, saturation_vapor_pressure, dew_point, wet_bulb_approx, relative_humidity, apparent_temperature, cloud_base_height, pressure_altitude

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

    var _v_celsius_to_fahrenheit = celsius_to_fahrenheit(0.5)
    if is_finite(_v_celsius_to_fahrenheit): passed += 1; print("  ✅ climate::celsius_to_fahrenheit =", _v_celsius_to_fahrenheit)
    else: failed += 1; print("  ❌ climate::celsius_to_fahrenheit → non-finite:", _v_celsius_to_fahrenheit)
    var _v_fahrenheit_to_celsius = fahrenheit_to_celsius(0.5)
    if is_finite(_v_fahrenheit_to_celsius): passed += 1; print("  ✅ climate::fahrenheit_to_celsius =", _v_fahrenheit_to_celsius)
    else: failed += 1; print("  ❌ climate::fahrenheit_to_celsius → non-finite:", _v_fahrenheit_to_celsius)
    var _v_heat_index = heat_index(0.5, 0.5)
    if is_finite(_v_heat_index): passed += 1; print("  ✅ climate::heat_index =", _v_heat_index)
    else: failed += 1; print("  ❌ climate::heat_index → non-finite:", _v_heat_index)
    var _v_wind_chill = wind_chill(0.5, 0.5)
    if is_finite(_v_wind_chill): passed += 1; print("  ✅ climate::wind_chill =", _v_wind_chill)
    else: failed += 1; print("  ❌ climate::wind_chill → non-finite:", _v_wind_chill)
    var _v_saturation_vapor_pressure = saturation_vapor_pressure(0.5)
    if is_finite(_v_saturation_vapor_pressure): passed += 1; print("  ✅ climate::saturation_vapor_pressure =", _v_saturation_vapor_pressure)
    else: failed += 1; print("  ❌ climate::saturation_vapor_pressure → non-finite:", _v_saturation_vapor_pressure)
    var _v_dew_point = dew_point(0.5, 0.5)
    if is_finite(_v_dew_point): passed += 1; print("  ✅ climate::dew_point =", _v_dew_point)
    else: failed += 1; print("  ❌ climate::dew_point → non-finite:", _v_dew_point)
    var _v_wet_bulb_approx = wet_bulb_approx(0.5, 0.5)
    if is_finite(_v_wet_bulb_approx): passed += 1; print("  ✅ climate::wet_bulb_approx =", _v_wet_bulb_approx)
    else: failed += 1; print("  ❌ climate::wet_bulb_approx → non-finite:", _v_wet_bulb_approx)
    var _v_relative_humidity = relative_humidity(0.5, 0.5)
    if is_finite(_v_relative_humidity): passed += 1; print("  ✅ climate::relative_humidity =", _v_relative_humidity)
    else: failed += 1; print("  ❌ climate::relative_humidity → non-finite:", _v_relative_humidity)
    var _v_apparent_temperature = apparent_temperature(0.5, 0.5, 0.5)
    if is_finite(_v_apparent_temperature): passed += 1; print("  ✅ climate::apparent_temperature =", _v_apparent_temperature)
    else: failed += 1; print("  ❌ climate::apparent_temperature → non-finite:", _v_apparent_temperature)
    var _v_cloud_base_height = cloud_base_height(0.5, 0.5)
    if is_finite(_v_cloud_base_height): passed += 1; print("  ✅ climate::cloud_base_height =", _v_cloud_base_height)
    else: failed += 1; print("  ❌ climate::cloud_base_height → non-finite:", _v_cloud_base_height)
    var _v_pressure_altitude = pressure_altitude(0.5)
    if is_finite(_v_pressure_altitude): passed += 1; print("  ✅ climate::pressure_altitude =", _v_pressure_altitude)
    else: failed += 1; print("  ❌ climate::pressure_altitude → non-finite:", _v_pressure_altitude)

    print("  [climate] Passed:", passed, "Failed:", failed)
