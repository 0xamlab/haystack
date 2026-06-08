"""bench_meteorology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from meteorology import dew_point, wet_bulb_temperature, pressure_altitude, relative_humidity, absolute_humidity, wind_chill, heat_index, potential_temperature, precipitable_water, visibility_extinction
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

    var _acc_dew_point: Float64 = 0.0
    var _t0_dew_point = perf_counter_ns()
    for _ in range(N):
        _acc_dew_point += dew_point(0.5, 0.5)
    var _t1_dew_point = perf_counter_ns()
    var _ns_dew_point = Float64(_t1_dew_point - _t0_dew_point) / Float64(N)
    print("MOJO_TIMING meteorology::dew_point", _ns_dew_point, _acc_dew_point)
    var _result_dew_point = dew_point(0.5, 0.5)
    var _summary_dew_point = _summary_float64(_result_dew_point)
    print("MOJO_RESULT meteorology::dew_point", _summary_dew_point)
    var _acc_wet_bulb_temperature: Float64 = 0.0
    var _t0_wet_bulb_temperature = perf_counter_ns()
    for _ in range(N):
        _acc_wet_bulb_temperature += wet_bulb_temperature(0.5, 0.5)
    var _t1_wet_bulb_temperature = perf_counter_ns()
    var _ns_wet_bulb_temperature = Float64(_t1_wet_bulb_temperature - _t0_wet_bulb_temperature) / Float64(N)
    print("MOJO_TIMING meteorology::wet_bulb_temperature", _ns_wet_bulb_temperature, _acc_wet_bulb_temperature)
    var _result_wet_bulb_temperature = wet_bulb_temperature(0.5, 0.5)
    var _summary_wet_bulb_temperature = _summary_float64(_result_wet_bulb_temperature)
    print("MOJO_RESULT meteorology::wet_bulb_temperature", _summary_wet_bulb_temperature)
    var _acc_pressure_altitude: Float64 = 0.0
    var _t0_pressure_altitude = perf_counter_ns()
    for _ in range(N):
        _acc_pressure_altitude += pressure_altitude(0.5)
    var _t1_pressure_altitude = perf_counter_ns()
    var _ns_pressure_altitude = Float64(_t1_pressure_altitude - _t0_pressure_altitude) / Float64(N)
    print("MOJO_TIMING meteorology::pressure_altitude", _ns_pressure_altitude, _acc_pressure_altitude)
    var _result_pressure_altitude = pressure_altitude(0.5)
    var _summary_pressure_altitude = _summary_float64(_result_pressure_altitude)
    print("MOJO_RESULT meteorology::pressure_altitude", _summary_pressure_altitude)
    var _acc_relative_humidity: Float64 = 0.0
    var _t0_relative_humidity = perf_counter_ns()
    for _ in range(N):
        _acc_relative_humidity += relative_humidity(0.5, 0.5)
    var _t1_relative_humidity = perf_counter_ns()
    var _ns_relative_humidity = Float64(_t1_relative_humidity - _t0_relative_humidity) / Float64(N)
    print("MOJO_TIMING meteorology::relative_humidity", _ns_relative_humidity, _acc_relative_humidity)
    var _result_relative_humidity = relative_humidity(0.5, 0.5)
    var _summary_relative_humidity = _summary_float64(_result_relative_humidity)
    print("MOJO_RESULT meteorology::relative_humidity", _summary_relative_humidity)
    var _acc_absolute_humidity: Float64 = 0.0
    var _t0_absolute_humidity = perf_counter_ns()
    for _ in range(N):
        _acc_absolute_humidity += absolute_humidity(0.5, 0.5)
    var _t1_absolute_humidity = perf_counter_ns()
    var _ns_absolute_humidity = Float64(_t1_absolute_humidity - _t0_absolute_humidity) / Float64(N)
    print("MOJO_TIMING meteorology::absolute_humidity", _ns_absolute_humidity, _acc_absolute_humidity)
    var _result_absolute_humidity = absolute_humidity(0.5, 0.5)
    var _summary_absolute_humidity = _summary_float64(_result_absolute_humidity)
    print("MOJO_RESULT meteorology::absolute_humidity", _summary_absolute_humidity)
    var _acc_wind_chill: Float64 = 0.0
    var _t0_wind_chill = perf_counter_ns()
    for _ in range(N):
        _acc_wind_chill += wind_chill(0.5, 0.5)
    var _t1_wind_chill = perf_counter_ns()
    var _ns_wind_chill = Float64(_t1_wind_chill - _t0_wind_chill) / Float64(N)
    print("MOJO_TIMING meteorology::wind_chill", _ns_wind_chill, _acc_wind_chill)
    var _result_wind_chill = wind_chill(0.5, 0.5)
    var _summary_wind_chill = _summary_float64(_result_wind_chill)
    print("MOJO_RESULT meteorology::wind_chill", _summary_wind_chill)
    var _acc_heat_index: Float64 = 0.0
    var _t0_heat_index = perf_counter_ns()
    for _ in range(N):
        _acc_heat_index += heat_index(0.5, 0.5)
    var _t1_heat_index = perf_counter_ns()
    var _ns_heat_index = Float64(_t1_heat_index - _t0_heat_index) / Float64(N)
    print("MOJO_TIMING meteorology::heat_index", _ns_heat_index, _acc_heat_index)
    var _result_heat_index = heat_index(0.5, 0.5)
    var _summary_heat_index = _summary_float64(_result_heat_index)
    print("MOJO_RESULT meteorology::heat_index", _summary_heat_index)
    var _acc_potential_temperature: Float64 = 0.0
    var _t0_potential_temperature = perf_counter_ns()
    for _ in range(N):
        _acc_potential_temperature += potential_temperature(0.5, 0.5)
    var _t1_potential_temperature = perf_counter_ns()
    var _ns_potential_temperature = Float64(_t1_potential_temperature - _t0_potential_temperature) / Float64(N)
    print("MOJO_TIMING meteorology::potential_temperature", _ns_potential_temperature, _acc_potential_temperature)
    var _result_potential_temperature = potential_temperature(0.5, 0.5)
    var _summary_potential_temperature = _summary_float64(_result_potential_temperature)
    print("MOJO_RESULT meteorology::potential_temperature", _summary_potential_temperature)
    var _acc_precipitable_water: Float64 = 0.0
    var _t0_precipitable_water = perf_counter_ns()
    for _ in range(N):
        _acc_precipitable_water += precipitable_water(0.5, 0.5)
    var _t1_precipitable_water = perf_counter_ns()
    var _ns_precipitable_water = Float64(_t1_precipitable_water - _t0_precipitable_water) / Float64(N)
    print("MOJO_TIMING meteorology::precipitable_water", _ns_precipitable_water, _acc_precipitable_water)
    var _result_precipitable_water = precipitable_water(0.5, 0.5)
    var _summary_precipitable_water = _summary_float64(_result_precipitable_water)
    print("MOJO_RESULT meteorology::precipitable_water", _summary_precipitable_water)
    var _acc_visibility_extinction: Float64 = 0.0
    var _t0_visibility_extinction = perf_counter_ns()
    for _ in range(N):
        _acc_visibility_extinction += visibility_extinction(0.5, 0.5)
    var _t1_visibility_extinction = perf_counter_ns()
    var _ns_visibility_extinction = Float64(_t1_visibility_extinction - _t0_visibility_extinction) / Float64(N)
    print("MOJO_TIMING meteorology::visibility_extinction", _ns_visibility_extinction, _acc_visibility_extinction)
    var _result_visibility_extinction = visibility_extinction(0.5, 0.5)
    var _summary_visibility_extinction = _summary_float64(_result_visibility_extinction)
    print("MOJO_RESULT meteorology::visibility_extinction", _summary_visibility_extinction)
