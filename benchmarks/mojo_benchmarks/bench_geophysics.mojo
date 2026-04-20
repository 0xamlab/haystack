"""bench_geophysics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from geophysics import gravity_anomaly_bouguer, gravitational_acceleration, magnetic_inclination, seismic_p_wave_velocity, seismic_s_wave_velocity, depth_from_reflection, vp_vs_ratio, earth_radius_at_latitude, free_air_correction, isostasy_airy
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

    var _acc_gravity_anomaly_bouguer: Float64 = 0.0
    var _t0_gravity_anomaly_bouguer = perf_counter_ns()
    for _ in range(N):
        _acc_gravity_anomaly_bouguer += gravity_anomaly_bouguer(0.5, 0.5, 0.5, 0.5)
    var _t1_gravity_anomaly_bouguer = perf_counter_ns()
    var _ns_gravity_anomaly_bouguer = Float64(_t1_gravity_anomaly_bouguer - _t0_gravity_anomaly_bouguer) / Float64(N)
    print("MOJO_TIMING geophysics::gravity_anomaly_bouguer", _ns_gravity_anomaly_bouguer, _acc_gravity_anomaly_bouguer)
    var _acc_gravitational_acceleration: Float64 = 0.0
    var _t0_gravitational_acceleration = perf_counter_ns()
    for _ in range(N):
        _acc_gravitational_acceleration += gravitational_acceleration(0.5, 0.5)
    var _t1_gravitational_acceleration = perf_counter_ns()
    var _ns_gravitational_acceleration = Float64(_t1_gravitational_acceleration - _t0_gravitational_acceleration) / Float64(N)
    print("MOJO_TIMING geophysics::gravitational_acceleration", _ns_gravitational_acceleration, _acc_gravitational_acceleration)
    var _acc_magnetic_inclination: Float64 = 0.0
    var _t0_magnetic_inclination = perf_counter_ns()
    for _ in range(N):
        _acc_magnetic_inclination += magnetic_inclination(0.5, 0.5)
    var _t1_magnetic_inclination = perf_counter_ns()
    var _ns_magnetic_inclination = Float64(_t1_magnetic_inclination - _t0_magnetic_inclination) / Float64(N)
    print("MOJO_TIMING geophysics::magnetic_inclination", _ns_magnetic_inclination, _acc_magnetic_inclination)
    var _acc_seismic_p_wave_velocity: Float64 = 0.0
    var _t0_seismic_p_wave_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_seismic_p_wave_velocity += seismic_p_wave_velocity(0.5, 0.5, 0.5)
    var _t1_seismic_p_wave_velocity = perf_counter_ns()
    var _ns_seismic_p_wave_velocity = Float64(_t1_seismic_p_wave_velocity - _t0_seismic_p_wave_velocity) / Float64(N)
    print("MOJO_TIMING geophysics::seismic_p_wave_velocity", _ns_seismic_p_wave_velocity, _acc_seismic_p_wave_velocity)
    var _acc_seismic_s_wave_velocity: Float64 = 0.0
    var _t0_seismic_s_wave_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_seismic_s_wave_velocity += seismic_s_wave_velocity(0.5, 0.5)
    var _t1_seismic_s_wave_velocity = perf_counter_ns()
    var _ns_seismic_s_wave_velocity = Float64(_t1_seismic_s_wave_velocity - _t0_seismic_s_wave_velocity) / Float64(N)
    print("MOJO_TIMING geophysics::seismic_s_wave_velocity", _ns_seismic_s_wave_velocity, _acc_seismic_s_wave_velocity)
    var _acc_depth_from_reflection: Float64 = 0.0
    var _t0_depth_from_reflection = perf_counter_ns()
    for _ in range(N):
        _acc_depth_from_reflection += depth_from_reflection(0.5, 0.5)
    var _t1_depth_from_reflection = perf_counter_ns()
    var _ns_depth_from_reflection = Float64(_t1_depth_from_reflection - _t0_depth_from_reflection) / Float64(N)
    print("MOJO_TIMING geophysics::depth_from_reflection", _ns_depth_from_reflection, _acc_depth_from_reflection)
    var _acc_vp_vs_ratio: Float64 = 0.0
    var _t0_vp_vs_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_vp_vs_ratio += vp_vs_ratio(0.5, 0.5)
    var _t1_vp_vs_ratio = perf_counter_ns()
    var _ns_vp_vs_ratio = Float64(_t1_vp_vs_ratio - _t0_vp_vs_ratio) / Float64(N)
    print("MOJO_TIMING geophysics::vp_vs_ratio", _ns_vp_vs_ratio, _acc_vp_vs_ratio)
    var _acc_earth_radius_at_latitude: Float64 = 0.0
    var _t0_earth_radius_at_latitude = perf_counter_ns()
    for _ in range(N):
        _acc_earth_radius_at_latitude += earth_radius_at_latitude(0.5)
    var _t1_earth_radius_at_latitude = perf_counter_ns()
    var _ns_earth_radius_at_latitude = Float64(_t1_earth_radius_at_latitude - _t0_earth_radius_at_latitude) / Float64(N)
    print("MOJO_TIMING geophysics::earth_radius_at_latitude", _ns_earth_radius_at_latitude, _acc_earth_radius_at_latitude)
    var _acc_free_air_correction: Float64 = 0.0
    var _t0_free_air_correction = perf_counter_ns()
    for _ in range(N):
        _acc_free_air_correction += free_air_correction(0.5)
    var _t1_free_air_correction = perf_counter_ns()
    var _ns_free_air_correction = Float64(_t1_free_air_correction - _t0_free_air_correction) / Float64(N)
    print("MOJO_TIMING geophysics::free_air_correction", _ns_free_air_correction, _acc_free_air_correction)
    var _acc_isostasy_airy: Float64 = 0.0
    var _t0_isostasy_airy = perf_counter_ns()
    for _ in range(N):
        _acc_isostasy_airy += isostasy_airy(0.5, 0.5, 0.5)
    var _t1_isostasy_airy = perf_counter_ns()
    var _ns_isostasy_airy = Float64(_t1_isostasy_airy - _t0_isostasy_airy) / Float64(N)
    print("MOJO_TIMING geophysics::isostasy_airy", _ns_isostasy_airy, _acc_isostasy_airy)
