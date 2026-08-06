"""bench_astronomy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from astronomy import julian_date, modified_julian_date, sidereal_time, solar_declination, sunrise_hour_angle, day_length, parallax_correction, kepler_equation, orbital_period, apparent_magnitude, distance_from_magnitude, ecliptic_to_equatorial
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_julian_date: Float64 = 0.0
    var _t0_julian_date = perf_counter_ns()
    for _ in range(N):
        _acc_julian_date += julian_date(5, 5, 5)
    var _t1_julian_date = perf_counter_ns()
    var _ns_julian_date = Float64(_t1_julian_date - _t0_julian_date) / Float64(N)
    print("MOJO_TIMING astronomy::julian_date", _ns_julian_date, _acc_julian_date)
    var _result_julian_date = julian_date(5, 5, 5)
    var _summary_julian_date = _summary_float64(_result_julian_date)
    print("MOJO_RESULT astronomy::julian_date", _summary_julian_date)
    var _acc_modified_julian_date: Float64 = 0.0
    var _t0_modified_julian_date = perf_counter_ns()
    for _ in range(N):
        _acc_modified_julian_date += modified_julian_date(0.5)
    var _t1_modified_julian_date = perf_counter_ns()
    var _ns_modified_julian_date = Float64(_t1_modified_julian_date - _t0_modified_julian_date) / Float64(N)
    print("MOJO_TIMING astronomy::modified_julian_date", _ns_modified_julian_date, _acc_modified_julian_date)
    var _result_modified_julian_date = modified_julian_date(0.5)
    var _summary_modified_julian_date = _summary_float64(_result_modified_julian_date)
    print("MOJO_RESULT astronomy::modified_julian_date", _summary_modified_julian_date)
    var _acc_sidereal_time: Float64 = 0.0
    var _t0_sidereal_time = perf_counter_ns()
    for _ in range(N):
        _acc_sidereal_time += sidereal_time(0.5, 0.5)
    var _t1_sidereal_time = perf_counter_ns()
    var _ns_sidereal_time = Float64(_t1_sidereal_time - _t0_sidereal_time) / Float64(N)
    print("MOJO_TIMING astronomy::sidereal_time", _ns_sidereal_time, _acc_sidereal_time)
    var _result_sidereal_time = sidereal_time(0.5, 0.5)
    var _summary_sidereal_time = _summary_float64(_result_sidereal_time)
    print("MOJO_RESULT astronomy::sidereal_time", _summary_sidereal_time)
    var _acc_solar_declination: Float64 = 0.0
    var _t0_solar_declination = perf_counter_ns()
    for _ in range(N):
        _acc_solar_declination += solar_declination(5)
    var _t1_solar_declination = perf_counter_ns()
    var _ns_solar_declination = Float64(_t1_solar_declination - _t0_solar_declination) / Float64(N)
    print("MOJO_TIMING astronomy::solar_declination", _ns_solar_declination, _acc_solar_declination)
    var _result_solar_declination = solar_declination(5)
    var _summary_solar_declination = _summary_float64(_result_solar_declination)
    print("MOJO_RESULT astronomy::solar_declination", _summary_solar_declination)
    var _acc_sunrise_hour_angle: Float64 = 0.0
    var _t0_sunrise_hour_angle = perf_counter_ns()
    for _ in range(N):
        _acc_sunrise_hour_angle += sunrise_hour_angle(0.5, 0.5)
    var _t1_sunrise_hour_angle = perf_counter_ns()
    var _ns_sunrise_hour_angle = Float64(_t1_sunrise_hour_angle - _t0_sunrise_hour_angle) / Float64(N)
    print("MOJO_TIMING astronomy::sunrise_hour_angle", _ns_sunrise_hour_angle, _acc_sunrise_hour_angle)
    var _result_sunrise_hour_angle = sunrise_hour_angle(0.5, 0.5)
    var _summary_sunrise_hour_angle = _summary_float64(_result_sunrise_hour_angle)
    print("MOJO_RESULT astronomy::sunrise_hour_angle", _summary_sunrise_hour_angle)
    var _acc_day_length: Float64 = 0.0
    var _t0_day_length = perf_counter_ns()
    for _ in range(N):
        _acc_day_length += day_length(0.5, 5)
    var _t1_day_length = perf_counter_ns()
    var _ns_day_length = Float64(_t1_day_length - _t0_day_length) / Float64(N)
    print("MOJO_TIMING astronomy::day_length", _ns_day_length, _acc_day_length)
    var _result_day_length = day_length(0.5, 5)
    var _summary_day_length = _summary_float64(_result_day_length)
    print("MOJO_RESULT astronomy::day_length", _summary_day_length)
    var _acc_parallax_correction: Float64 = 0.0
    var _t0_parallax_correction = perf_counter_ns()
    for _ in range(N):
        _acc_parallax_correction += parallax_correction(0.5, 0.5)
    var _t1_parallax_correction = perf_counter_ns()
    var _ns_parallax_correction = Float64(_t1_parallax_correction - _t0_parallax_correction) / Float64(N)
    print("MOJO_TIMING astronomy::parallax_correction", _ns_parallax_correction, _acc_parallax_correction)
    var _result_parallax_correction = parallax_correction(0.5, 0.5)
    var _summary_parallax_correction = _summary_float64(_result_parallax_correction)
    print("MOJO_RESULT astronomy::parallax_correction", _summary_parallax_correction)
    var _acc_kepler_equation: Float64 = 0.0
    var _t0_kepler_equation = perf_counter_ns()
    for _ in range(N):
        _acc_kepler_equation += kepler_equation(0.5, 0.5, 0.5)
    var _t1_kepler_equation = perf_counter_ns()
    var _ns_kepler_equation = Float64(_t1_kepler_equation - _t0_kepler_equation) / Float64(N)
    print("MOJO_TIMING astronomy::kepler_equation", _ns_kepler_equation, _acc_kepler_equation)
    var _result_kepler_equation = kepler_equation(0.5, 0.5, 0.5)
    var _summary_kepler_equation = _summary_float64(_result_kepler_equation)
    print("MOJO_RESULT astronomy::kepler_equation", _summary_kepler_equation)
    var _acc_orbital_period: Float64 = 0.0
    var _t0_orbital_period = perf_counter_ns()
    for _ in range(N):
        _acc_orbital_period += orbital_period(0.5)
    var _t1_orbital_period = perf_counter_ns()
    var _ns_orbital_period = Float64(_t1_orbital_period - _t0_orbital_period) / Float64(N)
    print("MOJO_TIMING astronomy::orbital_period", _ns_orbital_period, _acc_orbital_period)
    var _result_orbital_period = orbital_period(0.5)
    var _summary_orbital_period = _summary_float64(_result_orbital_period)
    print("MOJO_RESULT astronomy::orbital_period", _summary_orbital_period)
    var _acc_apparent_magnitude: Float64 = 0.0
    var _t0_apparent_magnitude = perf_counter_ns()
    for _ in range(N):
        _acc_apparent_magnitude += apparent_magnitude(0.5, 0.5)
    var _t1_apparent_magnitude = perf_counter_ns()
    var _ns_apparent_magnitude = Float64(_t1_apparent_magnitude - _t0_apparent_magnitude) / Float64(N)
    print("MOJO_TIMING astronomy::apparent_magnitude", _ns_apparent_magnitude, _acc_apparent_magnitude)
    var _result_apparent_magnitude = apparent_magnitude(0.5, 0.5)
    var _summary_apparent_magnitude = _summary_float64(_result_apparent_magnitude)
    print("MOJO_RESULT astronomy::apparent_magnitude", _summary_apparent_magnitude)
    var _acc_distance_from_magnitude: Float64 = 0.0
    var _t0_distance_from_magnitude = perf_counter_ns()
    for _ in range(N):
        _acc_distance_from_magnitude += distance_from_magnitude(0.5, 0.5)
    var _t1_distance_from_magnitude = perf_counter_ns()
    var _ns_distance_from_magnitude = Float64(_t1_distance_from_magnitude - _t0_distance_from_magnitude) / Float64(N)
    print("MOJO_TIMING astronomy::distance_from_magnitude", _ns_distance_from_magnitude, _acc_distance_from_magnitude)
    var _result_distance_from_magnitude = distance_from_magnitude(0.5, 0.5)
    var _summary_distance_from_magnitude = _summary_float64(_result_distance_from_magnitude)
    print("MOJO_RESULT astronomy::distance_from_magnitude", _summary_distance_from_magnitude)
    var _acc_ecliptic_to_equatorial: Float64 = 0.0
    var _t0_ecliptic_to_equatorial = perf_counter_ns()
    for _ in range(N):
        var _r_ecliptic_to_equatorial = ecliptic_to_equatorial(0.5, 0.5, 0.5)
        _acc_ecliptic_to_equatorial += Float64(len(_r_ecliptic_to_equatorial))
    var _t1_ecliptic_to_equatorial = perf_counter_ns()
    var _ns_ecliptic_to_equatorial = Float64(_t1_ecliptic_to_equatorial - _t0_ecliptic_to_equatorial) / Float64(N)
    print("MOJO_TIMING astronomy::ecliptic_to_equatorial", _ns_ecliptic_to_equatorial, _acc_ecliptic_to_equatorial)
    var _result_ecliptic_to_equatorial = ecliptic_to_equatorial(0.5, 0.5, 0.5)
    var _summary_ecliptic_to_equatorial = _summary_list_float64(_result_ecliptic_to_equatorial)
    print("MOJO_RESULT astronomy::ecliptic_to_equatorial", _summary_ecliptic_to_equatorial)
