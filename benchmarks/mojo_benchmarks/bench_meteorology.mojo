"""bench_meteorology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from meteorology import dew_point, wet_bulb_temperature, pressure_altitude, relative_humidity, absolute_humidity, wind_chill, heat_index, potential_temperature, precipitable_water, visibility_extinction
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

    var _acc_dew_point: Float64 = 0.0
    var _t0_dew_point = perf_counter_ns()
    for _ in range(N):
        _acc_dew_point += dew_point(0.5, 0.5)
    var _t1_dew_point = perf_counter_ns()
    var _ns_dew_point = Float64(_t1_dew_point - _t0_dew_point) / Float64(N)
    print("MOJO_TIMING meteorology::dew_point", _ns_dew_point, _acc_dew_point)
    var _acc_wet_bulb_temperature: Float64 = 0.0
    var _t0_wet_bulb_temperature = perf_counter_ns()
    for _ in range(N):
        _acc_wet_bulb_temperature += wet_bulb_temperature(0.5, 0.5)
    var _t1_wet_bulb_temperature = perf_counter_ns()
    var _ns_wet_bulb_temperature = Float64(_t1_wet_bulb_temperature - _t0_wet_bulb_temperature) / Float64(N)
    print("MOJO_TIMING meteorology::wet_bulb_temperature", _ns_wet_bulb_temperature, _acc_wet_bulb_temperature)
    var _acc_pressure_altitude: Float64 = 0.0
    var _t0_pressure_altitude = perf_counter_ns()
    for _ in range(N):
        _acc_pressure_altitude += pressure_altitude(0.5)
    var _t1_pressure_altitude = perf_counter_ns()
    var _ns_pressure_altitude = Float64(_t1_pressure_altitude - _t0_pressure_altitude) / Float64(N)
    print("MOJO_TIMING meteorology::pressure_altitude", _ns_pressure_altitude, _acc_pressure_altitude)
    var _acc_relative_humidity: Float64 = 0.0
    var _t0_relative_humidity = perf_counter_ns()
    for _ in range(N):
        _acc_relative_humidity += relative_humidity(0.5, 0.5)
    var _t1_relative_humidity = perf_counter_ns()
    var _ns_relative_humidity = Float64(_t1_relative_humidity - _t0_relative_humidity) / Float64(N)
    print("MOJO_TIMING meteorology::relative_humidity", _ns_relative_humidity, _acc_relative_humidity)
    var _acc_absolute_humidity: Float64 = 0.0
    var _t0_absolute_humidity = perf_counter_ns()
    for _ in range(N):
        _acc_absolute_humidity += absolute_humidity(0.5, 0.5)
    var _t1_absolute_humidity = perf_counter_ns()
    var _ns_absolute_humidity = Float64(_t1_absolute_humidity - _t0_absolute_humidity) / Float64(N)
    print("MOJO_TIMING meteorology::absolute_humidity", _ns_absolute_humidity, _acc_absolute_humidity)
    var _acc_wind_chill: Float64 = 0.0
    var _t0_wind_chill = perf_counter_ns()
    for _ in range(N):
        _acc_wind_chill += wind_chill(0.5, 0.5)
    var _t1_wind_chill = perf_counter_ns()
    var _ns_wind_chill = Float64(_t1_wind_chill - _t0_wind_chill) / Float64(N)
    print("MOJO_TIMING meteorology::wind_chill", _ns_wind_chill, _acc_wind_chill)
    var _acc_heat_index: Float64 = 0.0
    var _t0_heat_index = perf_counter_ns()
    for _ in range(N):
        _acc_heat_index += heat_index(0.5, 0.5)
    var _t1_heat_index = perf_counter_ns()
    var _ns_heat_index = Float64(_t1_heat_index - _t0_heat_index) / Float64(N)
    print("MOJO_TIMING meteorology::heat_index", _ns_heat_index, _acc_heat_index)
    var _acc_potential_temperature: Float64 = 0.0
    var _t0_potential_temperature = perf_counter_ns()
    for _ in range(N):
        _acc_potential_temperature += potential_temperature(0.5, 0.5)
    var _t1_potential_temperature = perf_counter_ns()
    var _ns_potential_temperature = Float64(_t1_potential_temperature - _t0_potential_temperature) / Float64(N)
    print("MOJO_TIMING meteorology::potential_temperature", _ns_potential_temperature, _acc_potential_temperature)
    var _acc_precipitable_water: Float64 = 0.0
    var _t0_precipitable_water = perf_counter_ns()
    for _ in range(N):
        _acc_precipitable_water += precipitable_water(0.5, 0.5)
    var _t1_precipitable_water = perf_counter_ns()
    var _ns_precipitable_water = Float64(_t1_precipitable_water - _t0_precipitable_water) / Float64(N)
    print("MOJO_TIMING meteorology::precipitable_water", _ns_precipitable_water, _acc_precipitable_water)
    var _acc_visibility_extinction: Float64 = 0.0
    var _t0_visibility_extinction = perf_counter_ns()
    for _ in range(N):
        _acc_visibility_extinction += visibility_extinction(0.5, 0.5)
    var _t1_visibility_extinction = perf_counter_ns()
    var _ns_visibility_extinction = Float64(_t1_visibility_extinction - _t0_visibility_extinction) / Float64(N)
    print("MOJO_TIMING meteorology::visibility_extinction", _ns_visibility_extinction, _acc_visibility_extinction)
