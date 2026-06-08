"""bench_hvac.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hvac import sensible_heat_load, latent_heat_load, total_heat_load, sensible_heat_ratio, cooling_tons, btu_from_tons, air_changes_per_hour, duct_velocity, cop_to_eer, eer_to_cop, heating_degree_days, cooling_degree_days
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

    var _acc_sensible_heat_load: Float64 = 0.0
    var _t0_sensible_heat_load = perf_counter_ns()
    for _ in range(N):
        _acc_sensible_heat_load += sensible_heat_load(0.5, 0.5)
    var _t1_sensible_heat_load = perf_counter_ns()
    var _ns_sensible_heat_load = Float64(_t1_sensible_heat_load - _t0_sensible_heat_load) / Float64(N)
    print("MOJO_TIMING hvac::sensible_heat_load", _ns_sensible_heat_load, _acc_sensible_heat_load)
    var _result_sensible_heat_load = sensible_heat_load(0.5, 0.5)
    var _summary_sensible_heat_load = _summary_float64(_result_sensible_heat_load)
    print("MOJO_RESULT hvac::sensible_heat_load", _summary_sensible_heat_load)
    var _acc_latent_heat_load: Float64 = 0.0
    var _t0_latent_heat_load = perf_counter_ns()
    for _ in range(N):
        _acc_latent_heat_load += latent_heat_load(0.5, 0.5)
    var _t1_latent_heat_load = perf_counter_ns()
    var _ns_latent_heat_load = Float64(_t1_latent_heat_load - _t0_latent_heat_load) / Float64(N)
    print("MOJO_TIMING hvac::latent_heat_load", _ns_latent_heat_load, _acc_latent_heat_load)
    var _result_latent_heat_load = latent_heat_load(0.5, 0.5)
    var _summary_latent_heat_load = _summary_float64(_result_latent_heat_load)
    print("MOJO_RESULT hvac::latent_heat_load", _summary_latent_heat_load)
    var _acc_total_heat_load: Float64 = 0.0
    var _t0_total_heat_load = perf_counter_ns()
    for _ in range(N):
        _acc_total_heat_load += total_heat_load(0.5, 0.5)
    var _t1_total_heat_load = perf_counter_ns()
    var _ns_total_heat_load = Float64(_t1_total_heat_load - _t0_total_heat_load) / Float64(N)
    print("MOJO_TIMING hvac::total_heat_load", _ns_total_heat_load, _acc_total_heat_load)
    var _result_total_heat_load = total_heat_load(0.5, 0.5)
    var _summary_total_heat_load = _summary_float64(_result_total_heat_load)
    print("MOJO_RESULT hvac::total_heat_load", _summary_total_heat_load)
    var _acc_sensible_heat_ratio: Float64 = 0.0
    var _t0_sensible_heat_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_sensible_heat_ratio += sensible_heat_ratio(0.5, 0.5)
    var _t1_sensible_heat_ratio = perf_counter_ns()
    var _ns_sensible_heat_ratio = Float64(_t1_sensible_heat_ratio - _t0_sensible_heat_ratio) / Float64(N)
    print("MOJO_TIMING hvac::sensible_heat_ratio", _ns_sensible_heat_ratio, _acc_sensible_heat_ratio)
    var _result_sensible_heat_ratio = sensible_heat_ratio(0.5, 0.5)
    var _summary_sensible_heat_ratio = _summary_float64(_result_sensible_heat_ratio)
    print("MOJO_RESULT hvac::sensible_heat_ratio", _summary_sensible_heat_ratio)
    var _acc_cooling_tons: Float64 = 0.0
    var _t0_cooling_tons = perf_counter_ns()
    for _ in range(N):
        _acc_cooling_tons += cooling_tons(0.5)
    var _t1_cooling_tons = perf_counter_ns()
    var _ns_cooling_tons = Float64(_t1_cooling_tons - _t0_cooling_tons) / Float64(N)
    print("MOJO_TIMING hvac::cooling_tons", _ns_cooling_tons, _acc_cooling_tons)
    var _result_cooling_tons = cooling_tons(0.5)
    var _summary_cooling_tons = _summary_float64(_result_cooling_tons)
    print("MOJO_RESULT hvac::cooling_tons", _summary_cooling_tons)
    var _acc_btu_from_tons: Float64 = 0.0
    var _t0_btu_from_tons = perf_counter_ns()
    for _ in range(N):
        _acc_btu_from_tons += btu_from_tons(0.5)
    var _t1_btu_from_tons = perf_counter_ns()
    var _ns_btu_from_tons = Float64(_t1_btu_from_tons - _t0_btu_from_tons) / Float64(N)
    print("MOJO_TIMING hvac::btu_from_tons", _ns_btu_from_tons, _acc_btu_from_tons)
    var _result_btu_from_tons = btu_from_tons(0.5)
    var _summary_btu_from_tons = _summary_float64(_result_btu_from_tons)
    print("MOJO_RESULT hvac::btu_from_tons", _summary_btu_from_tons)
    var _acc_air_changes_per_hour: Float64 = 0.0
    var _t0_air_changes_per_hour = perf_counter_ns()
    for _ in range(N):
        _acc_air_changes_per_hour += air_changes_per_hour(0.5, 0.5)
    var _t1_air_changes_per_hour = perf_counter_ns()
    var _ns_air_changes_per_hour = Float64(_t1_air_changes_per_hour - _t0_air_changes_per_hour) / Float64(N)
    print("MOJO_TIMING hvac::air_changes_per_hour", _ns_air_changes_per_hour, _acc_air_changes_per_hour)
    var _result_air_changes_per_hour = air_changes_per_hour(0.5, 0.5)
    var _summary_air_changes_per_hour = _summary_float64(_result_air_changes_per_hour)
    print("MOJO_RESULT hvac::air_changes_per_hour", _summary_air_changes_per_hour)
    var _acc_duct_velocity: Float64 = 0.0
    var _t0_duct_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_duct_velocity += duct_velocity(0.5, 0.5)
    var _t1_duct_velocity = perf_counter_ns()
    var _ns_duct_velocity = Float64(_t1_duct_velocity - _t0_duct_velocity) / Float64(N)
    print("MOJO_TIMING hvac::duct_velocity", _ns_duct_velocity, _acc_duct_velocity)
    var _result_duct_velocity = duct_velocity(0.5, 0.5)
    var _summary_duct_velocity = _summary_float64(_result_duct_velocity)
    print("MOJO_RESULT hvac::duct_velocity", _summary_duct_velocity)
    var _acc_cop_to_eer: Float64 = 0.0
    var _t0_cop_to_eer = perf_counter_ns()
    for _ in range(N):
        _acc_cop_to_eer += cop_to_eer(0.5)
    var _t1_cop_to_eer = perf_counter_ns()
    var _ns_cop_to_eer = Float64(_t1_cop_to_eer - _t0_cop_to_eer) / Float64(N)
    print("MOJO_TIMING hvac::cop_to_eer", _ns_cop_to_eer, _acc_cop_to_eer)
    var _result_cop_to_eer = cop_to_eer(0.5)
    var _summary_cop_to_eer = _summary_float64(_result_cop_to_eer)
    print("MOJO_RESULT hvac::cop_to_eer", _summary_cop_to_eer)
    var _acc_eer_to_cop: Float64 = 0.0
    var _t0_eer_to_cop = perf_counter_ns()
    for _ in range(N):
        _acc_eer_to_cop += eer_to_cop(0.5)
    var _t1_eer_to_cop = perf_counter_ns()
    var _ns_eer_to_cop = Float64(_t1_eer_to_cop - _t0_eer_to_cop) / Float64(N)
    print("MOJO_TIMING hvac::eer_to_cop", _ns_eer_to_cop, _acc_eer_to_cop)
    var _result_eer_to_cop = eer_to_cop(0.5)
    var _summary_eer_to_cop = _summary_float64(_result_eer_to_cop)
    print("MOJO_RESULT hvac::eer_to_cop", _summary_eer_to_cop)
    var _acc_heating_degree_days: Float64 = 0.0
    var _t0_heating_degree_days = perf_counter_ns()
    for _ in range(N):
        _acc_heating_degree_days += heating_degree_days(0.5, 0.5)
    var _t1_heating_degree_days = perf_counter_ns()
    var _ns_heating_degree_days = Float64(_t1_heating_degree_days - _t0_heating_degree_days) / Float64(N)
    print("MOJO_TIMING hvac::heating_degree_days", _ns_heating_degree_days, _acc_heating_degree_days)
    var _result_heating_degree_days = heating_degree_days(0.5, 0.5)
    var _summary_heating_degree_days = _summary_float64(_result_heating_degree_days)
    print("MOJO_RESULT hvac::heating_degree_days", _summary_heating_degree_days)
    var _acc_cooling_degree_days: Float64 = 0.0
    var _t0_cooling_degree_days = perf_counter_ns()
    for _ in range(N):
        _acc_cooling_degree_days += cooling_degree_days(0.5, 0.5)
    var _t1_cooling_degree_days = perf_counter_ns()
    var _ns_cooling_degree_days = Float64(_t1_cooling_degree_days - _t0_cooling_degree_days) / Float64(N)
    print("MOJO_TIMING hvac::cooling_degree_days", _ns_cooling_degree_days, _acc_cooling_degree_days)
    var _result_cooling_degree_days = cooling_degree_days(0.5, 0.5)
    var _summary_cooling_degree_days = _summary_float64(_result_cooling_degree_days)
    print("MOJO_RESULT hvac::cooling_degree_days", _summary_cooling_degree_days)
