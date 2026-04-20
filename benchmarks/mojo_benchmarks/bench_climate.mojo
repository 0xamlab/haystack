"""bench_climate.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from climate import celsius_to_fahrenheit, fahrenheit_to_celsius, heat_index, wind_chill, saturation_vapor_pressure, dew_point, wet_bulb_approx, relative_humidity, apparent_temperature, cloud_base_height, pressure_altitude
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

    var _acc_celsius_to_fahrenheit: Float64 = 0.0
    var _t0_celsius_to_fahrenheit = perf_counter_ns()
    for _ in range(N):
        _acc_celsius_to_fahrenheit += celsius_to_fahrenheit(0.5)
    var _t1_celsius_to_fahrenheit = perf_counter_ns()
    var _ns_celsius_to_fahrenheit = Float64(_t1_celsius_to_fahrenheit - _t0_celsius_to_fahrenheit) / Float64(N)
    print("MOJO_TIMING climate::celsius_to_fahrenheit", _ns_celsius_to_fahrenheit, _acc_celsius_to_fahrenheit)
    var _acc_fahrenheit_to_celsius: Float64 = 0.0
    var _t0_fahrenheit_to_celsius = perf_counter_ns()
    for _ in range(N):
        _acc_fahrenheit_to_celsius += fahrenheit_to_celsius(0.5)
    var _t1_fahrenheit_to_celsius = perf_counter_ns()
    var _ns_fahrenheit_to_celsius = Float64(_t1_fahrenheit_to_celsius - _t0_fahrenheit_to_celsius) / Float64(N)
    print("MOJO_TIMING climate::fahrenheit_to_celsius", _ns_fahrenheit_to_celsius, _acc_fahrenheit_to_celsius)
    var _acc_heat_index: Float64 = 0.0
    var _t0_heat_index = perf_counter_ns()
    for _ in range(N):
        _acc_heat_index += heat_index(0.5, 0.5)
    var _t1_heat_index = perf_counter_ns()
    var _ns_heat_index = Float64(_t1_heat_index - _t0_heat_index) / Float64(N)
    print("MOJO_TIMING climate::heat_index", _ns_heat_index, _acc_heat_index)
    var _acc_wind_chill: Float64 = 0.0
    var _t0_wind_chill = perf_counter_ns()
    for _ in range(N):
        _acc_wind_chill += wind_chill(0.5, 0.5)
    var _t1_wind_chill = perf_counter_ns()
    var _ns_wind_chill = Float64(_t1_wind_chill - _t0_wind_chill) / Float64(N)
    print("MOJO_TIMING climate::wind_chill", _ns_wind_chill, _acc_wind_chill)
    var _acc_saturation_vapor_pressure: Float64 = 0.0
    var _t0_saturation_vapor_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_saturation_vapor_pressure += saturation_vapor_pressure(0.5)
    var _t1_saturation_vapor_pressure = perf_counter_ns()
    var _ns_saturation_vapor_pressure = Float64(_t1_saturation_vapor_pressure - _t0_saturation_vapor_pressure) / Float64(N)
    print("MOJO_TIMING climate::saturation_vapor_pressure", _ns_saturation_vapor_pressure, _acc_saturation_vapor_pressure)
    var _acc_dew_point: Float64 = 0.0
    var _t0_dew_point = perf_counter_ns()
    for _ in range(N):
        _acc_dew_point += dew_point(0.5, 0.5)
    var _t1_dew_point = perf_counter_ns()
    var _ns_dew_point = Float64(_t1_dew_point - _t0_dew_point) / Float64(N)
    print("MOJO_TIMING climate::dew_point", _ns_dew_point, _acc_dew_point)
    var _acc_wet_bulb_approx: Float64 = 0.0
    var _t0_wet_bulb_approx = perf_counter_ns()
    for _ in range(N):
        _acc_wet_bulb_approx += wet_bulb_approx(0.5, 0.5)
    var _t1_wet_bulb_approx = perf_counter_ns()
    var _ns_wet_bulb_approx = Float64(_t1_wet_bulb_approx - _t0_wet_bulb_approx) / Float64(N)
    print("MOJO_TIMING climate::wet_bulb_approx", _ns_wet_bulb_approx, _acc_wet_bulb_approx)
    var _acc_relative_humidity: Float64 = 0.0
    var _t0_relative_humidity = perf_counter_ns()
    for _ in range(N):
        _acc_relative_humidity += relative_humidity(0.5, 0.5)
    var _t1_relative_humidity = perf_counter_ns()
    var _ns_relative_humidity = Float64(_t1_relative_humidity - _t0_relative_humidity) / Float64(N)
    print("MOJO_TIMING climate::relative_humidity", _ns_relative_humidity, _acc_relative_humidity)
    var _acc_apparent_temperature: Float64 = 0.0
    var _t0_apparent_temperature = perf_counter_ns()
    for _ in range(N):
        _acc_apparent_temperature += apparent_temperature(0.5, 0.5, 0.5)
    var _t1_apparent_temperature = perf_counter_ns()
    var _ns_apparent_temperature = Float64(_t1_apparent_temperature - _t0_apparent_temperature) / Float64(N)
    print("MOJO_TIMING climate::apparent_temperature", _ns_apparent_temperature, _acc_apparent_temperature)
    var _acc_cloud_base_height: Float64 = 0.0
    var _t0_cloud_base_height = perf_counter_ns()
    for _ in range(N):
        _acc_cloud_base_height += cloud_base_height(0.5, 0.5)
    var _t1_cloud_base_height = perf_counter_ns()
    var _ns_cloud_base_height = Float64(_t1_cloud_base_height - _t0_cloud_base_height) / Float64(N)
    print("MOJO_TIMING climate::cloud_base_height", _ns_cloud_base_height, _acc_cloud_base_height)
    var _acc_pressure_altitude: Float64 = 0.0
    var _t0_pressure_altitude = perf_counter_ns()
    for _ in range(N):
        _acc_pressure_altitude += pressure_altitude(0.5)
    var _t1_pressure_altitude = perf_counter_ns()
    var _ns_pressure_altitude = Float64(_t1_pressure_altitude - _t0_pressure_altitude) / Float64(N)
    print("MOJO_TIMING climate::pressure_altitude", _ns_pressure_altitude, _acc_pressure_altitude)
