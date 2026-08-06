"""bench_geophysics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from geophysics import gravity_anomaly_bouguer, gravitational_acceleration, magnetic_inclination, seismic_p_wave_velocity, seismic_s_wave_velocity, depth_from_reflection, vp_vs_ratio, earth_radius_at_latitude, free_air_correction, isostasy_airy
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

    var _acc_gravity_anomaly_bouguer: Float64 = 0.0
    var _t0_gravity_anomaly_bouguer = perf_counter_ns()
    for _ in range(N):
        _acc_gravity_anomaly_bouguer += gravity_anomaly_bouguer(0.5, 0.5, 0.5, 0.5)
    var _t1_gravity_anomaly_bouguer = perf_counter_ns()
    var _ns_gravity_anomaly_bouguer = Float64(_t1_gravity_anomaly_bouguer - _t0_gravity_anomaly_bouguer) / Float64(N)
    print("MOJO_TIMING geophysics::gravity_anomaly_bouguer", _ns_gravity_anomaly_bouguer, _acc_gravity_anomaly_bouguer)
    var _result_gravity_anomaly_bouguer = gravity_anomaly_bouguer(0.5, 0.5, 0.5, 0.5)
    var _summary_gravity_anomaly_bouguer = _summary_float64(_result_gravity_anomaly_bouguer)
    print("MOJO_RESULT geophysics::gravity_anomaly_bouguer", _summary_gravity_anomaly_bouguer)
    var _acc_gravitational_acceleration: Float64 = 0.0
    var _t0_gravitational_acceleration = perf_counter_ns()
    for _ in range(N):
        _acc_gravitational_acceleration += gravitational_acceleration(0.5, 0.5)
    var _t1_gravitational_acceleration = perf_counter_ns()
    var _ns_gravitational_acceleration = Float64(_t1_gravitational_acceleration - _t0_gravitational_acceleration) / Float64(N)
    print("MOJO_TIMING geophysics::gravitational_acceleration", _ns_gravitational_acceleration, _acc_gravitational_acceleration)
    var _result_gravitational_acceleration = gravitational_acceleration(0.5, 0.5)
    var _summary_gravitational_acceleration = _summary_float64(_result_gravitational_acceleration)
    print("MOJO_RESULT geophysics::gravitational_acceleration", _summary_gravitational_acceleration)
    var _acc_magnetic_inclination: Float64 = 0.0
    var _t0_magnetic_inclination = perf_counter_ns()
    for _ in range(N):
        _acc_magnetic_inclination += magnetic_inclination(0.5, 0.5)
    var _t1_magnetic_inclination = perf_counter_ns()
    var _ns_magnetic_inclination = Float64(_t1_magnetic_inclination - _t0_magnetic_inclination) / Float64(N)
    print("MOJO_TIMING geophysics::magnetic_inclination", _ns_magnetic_inclination, _acc_magnetic_inclination)
    var _result_magnetic_inclination = magnetic_inclination(0.5, 0.5)
    var _summary_magnetic_inclination = _summary_float64(_result_magnetic_inclination)
    print("MOJO_RESULT geophysics::magnetic_inclination", _summary_magnetic_inclination)
    var _acc_seismic_p_wave_velocity: Float64 = 0.0
    var _t0_seismic_p_wave_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_seismic_p_wave_velocity += seismic_p_wave_velocity(0.5, 0.5, 0.5)
    var _t1_seismic_p_wave_velocity = perf_counter_ns()
    var _ns_seismic_p_wave_velocity = Float64(_t1_seismic_p_wave_velocity - _t0_seismic_p_wave_velocity) / Float64(N)
    print("MOJO_TIMING geophysics::seismic_p_wave_velocity", _ns_seismic_p_wave_velocity, _acc_seismic_p_wave_velocity)
    var _result_seismic_p_wave_velocity = seismic_p_wave_velocity(0.5, 0.5, 0.5)
    var _summary_seismic_p_wave_velocity = _summary_float64(_result_seismic_p_wave_velocity)
    print("MOJO_RESULT geophysics::seismic_p_wave_velocity", _summary_seismic_p_wave_velocity)
    var _acc_seismic_s_wave_velocity: Float64 = 0.0
    var _t0_seismic_s_wave_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_seismic_s_wave_velocity += seismic_s_wave_velocity(0.5, 0.5)
    var _t1_seismic_s_wave_velocity = perf_counter_ns()
    var _ns_seismic_s_wave_velocity = Float64(_t1_seismic_s_wave_velocity - _t0_seismic_s_wave_velocity) / Float64(N)
    print("MOJO_TIMING geophysics::seismic_s_wave_velocity", _ns_seismic_s_wave_velocity, _acc_seismic_s_wave_velocity)
    var _result_seismic_s_wave_velocity = seismic_s_wave_velocity(0.5, 0.5)
    var _summary_seismic_s_wave_velocity = _summary_float64(_result_seismic_s_wave_velocity)
    print("MOJO_RESULT geophysics::seismic_s_wave_velocity", _summary_seismic_s_wave_velocity)
    var _acc_depth_from_reflection: Float64 = 0.0
    var _t0_depth_from_reflection = perf_counter_ns()
    for _ in range(N):
        _acc_depth_from_reflection += depth_from_reflection(0.5, 0.5)
    var _t1_depth_from_reflection = perf_counter_ns()
    var _ns_depth_from_reflection = Float64(_t1_depth_from_reflection - _t0_depth_from_reflection) / Float64(N)
    print("MOJO_TIMING geophysics::depth_from_reflection", _ns_depth_from_reflection, _acc_depth_from_reflection)
    var _result_depth_from_reflection = depth_from_reflection(0.5, 0.5)
    var _summary_depth_from_reflection = _summary_float64(_result_depth_from_reflection)
    print("MOJO_RESULT geophysics::depth_from_reflection", _summary_depth_from_reflection)
    var _acc_vp_vs_ratio: Float64 = 0.0
    var _t0_vp_vs_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_vp_vs_ratio += vp_vs_ratio(0.5, 0.5)
    var _t1_vp_vs_ratio = perf_counter_ns()
    var _ns_vp_vs_ratio = Float64(_t1_vp_vs_ratio - _t0_vp_vs_ratio) / Float64(N)
    print("MOJO_TIMING geophysics::vp_vs_ratio", _ns_vp_vs_ratio, _acc_vp_vs_ratio)
    var _result_vp_vs_ratio = vp_vs_ratio(0.5, 0.5)
    var _summary_vp_vs_ratio = _summary_float64(_result_vp_vs_ratio)
    print("MOJO_RESULT geophysics::vp_vs_ratio", _summary_vp_vs_ratio)
    var _acc_earth_radius_at_latitude: Float64 = 0.0
    var _t0_earth_radius_at_latitude = perf_counter_ns()
    for _ in range(N):
        _acc_earth_radius_at_latitude += earth_radius_at_latitude(0.5)
    var _t1_earth_radius_at_latitude = perf_counter_ns()
    var _ns_earth_radius_at_latitude = Float64(_t1_earth_radius_at_latitude - _t0_earth_radius_at_latitude) / Float64(N)
    print("MOJO_TIMING geophysics::earth_radius_at_latitude", _ns_earth_radius_at_latitude, _acc_earth_radius_at_latitude)
    var _result_earth_radius_at_latitude = earth_radius_at_latitude(0.5)
    var _summary_earth_radius_at_latitude = _summary_float64(_result_earth_radius_at_latitude)
    print("MOJO_RESULT geophysics::earth_radius_at_latitude", _summary_earth_radius_at_latitude)
    var _acc_free_air_correction: Float64 = 0.0
    var _t0_free_air_correction = perf_counter_ns()
    for _ in range(N):
        _acc_free_air_correction += free_air_correction(0.5)
    var _t1_free_air_correction = perf_counter_ns()
    var _ns_free_air_correction = Float64(_t1_free_air_correction - _t0_free_air_correction) / Float64(N)
    print("MOJO_TIMING geophysics::free_air_correction", _ns_free_air_correction, _acc_free_air_correction)
    var _result_free_air_correction = free_air_correction(0.5)
    var _summary_free_air_correction = _summary_float64(_result_free_air_correction)
    print("MOJO_RESULT geophysics::free_air_correction", _summary_free_air_correction)
    var _acc_isostasy_airy: Float64 = 0.0
    var _t0_isostasy_airy = perf_counter_ns()
    for _ in range(N):
        _acc_isostasy_airy += isostasy_airy(0.5, 0.5, 0.5)
    var _t1_isostasy_airy = perf_counter_ns()
    var _ns_isostasy_airy = Float64(_t1_isostasy_airy - _t0_isostasy_airy) / Float64(N)
    print("MOJO_TIMING geophysics::isostasy_airy", _ns_isostasy_airy, _acc_isostasy_airy)
    var _result_isostasy_airy = isostasy_airy(0.5, 0.5, 0.5)
    var _summary_isostasy_airy = _summary_float64(_result_isostasy_airy)
    print("MOJO_RESULT geophysics::isostasy_airy", _summary_isostasy_airy)
