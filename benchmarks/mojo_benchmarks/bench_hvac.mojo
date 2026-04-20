"""bench_hvac.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hvac import sensible_heat_load, latent_heat_load, total_heat_load, sensible_heat_ratio, cooling_tons, btu_from_tons, air_changes_per_hour, duct_velocity, cop_to_eer, eer_to_cop, heating_degree_days, cooling_degree_days
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

    var _acc_sensible_heat_load: Float64 = 0.0
    var _t0_sensible_heat_load = perf_counter_ns()
    for _ in range(N):
        _acc_sensible_heat_load += sensible_heat_load(0.5, 0.5)
    var _t1_sensible_heat_load = perf_counter_ns()
    var _ns_sensible_heat_load = Float64(_t1_sensible_heat_load - _t0_sensible_heat_load) / Float64(N)
    print("MOJO_TIMING hvac::sensible_heat_load", _ns_sensible_heat_load, _acc_sensible_heat_load)
    var _acc_latent_heat_load: Float64 = 0.0
    var _t0_latent_heat_load = perf_counter_ns()
    for _ in range(N):
        _acc_latent_heat_load += latent_heat_load(0.5, 0.5)
    var _t1_latent_heat_load = perf_counter_ns()
    var _ns_latent_heat_load = Float64(_t1_latent_heat_load - _t0_latent_heat_load) / Float64(N)
    print("MOJO_TIMING hvac::latent_heat_load", _ns_latent_heat_load, _acc_latent_heat_load)
    var _acc_total_heat_load: Float64 = 0.0
    var _t0_total_heat_load = perf_counter_ns()
    for _ in range(N):
        _acc_total_heat_load += total_heat_load(0.5, 0.5)
    var _t1_total_heat_load = perf_counter_ns()
    var _ns_total_heat_load = Float64(_t1_total_heat_load - _t0_total_heat_load) / Float64(N)
    print("MOJO_TIMING hvac::total_heat_load", _ns_total_heat_load, _acc_total_heat_load)
    var _acc_sensible_heat_ratio: Float64 = 0.0
    var _t0_sensible_heat_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_sensible_heat_ratio += sensible_heat_ratio(0.5, 0.5)
    var _t1_sensible_heat_ratio = perf_counter_ns()
    var _ns_sensible_heat_ratio = Float64(_t1_sensible_heat_ratio - _t0_sensible_heat_ratio) / Float64(N)
    print("MOJO_TIMING hvac::sensible_heat_ratio", _ns_sensible_heat_ratio, _acc_sensible_heat_ratio)
    var _acc_cooling_tons: Float64 = 0.0
    var _t0_cooling_tons = perf_counter_ns()
    for _ in range(N):
        _acc_cooling_tons += cooling_tons(0.5)
    var _t1_cooling_tons = perf_counter_ns()
    var _ns_cooling_tons = Float64(_t1_cooling_tons - _t0_cooling_tons) / Float64(N)
    print("MOJO_TIMING hvac::cooling_tons", _ns_cooling_tons, _acc_cooling_tons)
    var _acc_btu_from_tons: Float64 = 0.0
    var _t0_btu_from_tons = perf_counter_ns()
    for _ in range(N):
        _acc_btu_from_tons += btu_from_tons(0.5)
    var _t1_btu_from_tons = perf_counter_ns()
    var _ns_btu_from_tons = Float64(_t1_btu_from_tons - _t0_btu_from_tons) / Float64(N)
    print("MOJO_TIMING hvac::btu_from_tons", _ns_btu_from_tons, _acc_btu_from_tons)
    var _acc_air_changes_per_hour: Float64 = 0.0
    var _t0_air_changes_per_hour = perf_counter_ns()
    for _ in range(N):
        _acc_air_changes_per_hour += air_changes_per_hour(0.5, 0.5)
    var _t1_air_changes_per_hour = perf_counter_ns()
    var _ns_air_changes_per_hour = Float64(_t1_air_changes_per_hour - _t0_air_changes_per_hour) / Float64(N)
    print("MOJO_TIMING hvac::air_changes_per_hour", _ns_air_changes_per_hour, _acc_air_changes_per_hour)
    var _acc_duct_velocity: Float64 = 0.0
    var _t0_duct_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_duct_velocity += duct_velocity(0.5, 0.5)
    var _t1_duct_velocity = perf_counter_ns()
    var _ns_duct_velocity = Float64(_t1_duct_velocity - _t0_duct_velocity) / Float64(N)
    print("MOJO_TIMING hvac::duct_velocity", _ns_duct_velocity, _acc_duct_velocity)
    var _acc_cop_to_eer: Float64 = 0.0
    var _t0_cop_to_eer = perf_counter_ns()
    for _ in range(N):
        _acc_cop_to_eer += cop_to_eer(0.5)
    var _t1_cop_to_eer = perf_counter_ns()
    var _ns_cop_to_eer = Float64(_t1_cop_to_eer - _t0_cop_to_eer) / Float64(N)
    print("MOJO_TIMING hvac::cop_to_eer", _ns_cop_to_eer, _acc_cop_to_eer)
    var _acc_eer_to_cop: Float64 = 0.0
    var _t0_eer_to_cop = perf_counter_ns()
    for _ in range(N):
        _acc_eer_to_cop += eer_to_cop(0.5)
    var _t1_eer_to_cop = perf_counter_ns()
    var _ns_eer_to_cop = Float64(_t1_eer_to_cop - _t0_eer_to_cop) / Float64(N)
    print("MOJO_TIMING hvac::eer_to_cop", _ns_eer_to_cop, _acc_eer_to_cop)
    var _acc_heating_degree_days: Float64 = 0.0
    var _t0_heating_degree_days = perf_counter_ns()
    for _ in range(N):
        _acc_heating_degree_days += heating_degree_days(0.5, 0.5)
    var _t1_heating_degree_days = perf_counter_ns()
    var _ns_heating_degree_days = Float64(_t1_heating_degree_days - _t0_heating_degree_days) / Float64(N)
    print("MOJO_TIMING hvac::heating_degree_days", _ns_heating_degree_days, _acc_heating_degree_days)
    var _acc_cooling_degree_days: Float64 = 0.0
    var _t0_cooling_degree_days = perf_counter_ns()
    for _ in range(N):
        _acc_cooling_degree_days += cooling_degree_days(0.5, 0.5)
    var _t1_cooling_degree_days = perf_counter_ns()
    var _ns_cooling_degree_days = Float64(_t1_cooling_degree_days - _t0_cooling_degree_days) / Float64(N)
    print("MOJO_TIMING hvac::cooling_degree_days", _ns_cooling_degree_days, _acc_cooling_degree_days)
