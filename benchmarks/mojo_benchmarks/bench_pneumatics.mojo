"""bench_pneumatics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pneumatics import ideal_gas_volume, flow_rate_orifice, compressor_power, pressure_drop_pipe, air_consumption, cylinder_force, bore_area, piston_speed, receiver_volume, free_air_delivery, specific_power, dew_point_pressure
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

    var _acc_ideal_gas_volume: Float64 = 0.0
    var _t0_ideal_gas_volume = perf_counter_ns()
    for _ in range(N):
        _acc_ideal_gas_volume += ideal_gas_volume(0.5, 0.5, 0.5)
    var _t1_ideal_gas_volume = perf_counter_ns()
    var _ns_ideal_gas_volume = Float64(_t1_ideal_gas_volume - _t0_ideal_gas_volume) / Float64(N)
    print("MOJO_TIMING pneumatics::ideal_gas_volume", _ns_ideal_gas_volume, _acc_ideal_gas_volume)
    var _result_ideal_gas_volume = ideal_gas_volume(0.5, 0.5, 0.5)
    var _summary_ideal_gas_volume = _summary_float64(_result_ideal_gas_volume)
    print("MOJO_RESULT pneumatics::ideal_gas_volume", _summary_ideal_gas_volume)
    var _acc_flow_rate_orifice: Float64 = 0.0
    var _t0_flow_rate_orifice = perf_counter_ns()
    for _ in range(N):
        _acc_flow_rate_orifice += flow_rate_orifice(0.5, 0.5, 0.5, 0.5)
    var _t1_flow_rate_orifice = perf_counter_ns()
    var _ns_flow_rate_orifice = Float64(_t1_flow_rate_orifice - _t0_flow_rate_orifice) / Float64(N)
    print("MOJO_TIMING pneumatics::flow_rate_orifice", _ns_flow_rate_orifice, _acc_flow_rate_orifice)
    var _result_flow_rate_orifice = flow_rate_orifice(0.5, 0.5, 0.5, 0.5)
    var _summary_flow_rate_orifice = _summary_float64(_result_flow_rate_orifice)
    print("MOJO_RESULT pneumatics::flow_rate_orifice", _summary_flow_rate_orifice)
    var _acc_compressor_power: Float64 = 0.0
    var _t0_compressor_power = perf_counter_ns()
    for _ in range(N):
        _acc_compressor_power += compressor_power(0.5, 0.5, 0.5, 0.5)
    var _t1_compressor_power = perf_counter_ns()
    var _ns_compressor_power = Float64(_t1_compressor_power - _t0_compressor_power) / Float64(N)
    print("MOJO_TIMING pneumatics::compressor_power", _ns_compressor_power, _acc_compressor_power)
    var _result_compressor_power = compressor_power(0.5, 0.5, 0.5, 0.5)
    var _summary_compressor_power = _summary_float64(_result_compressor_power)
    print("MOJO_RESULT pneumatics::compressor_power", _summary_compressor_power)
    var _acc_pressure_drop_pipe: Float64 = 0.0
    var _t0_pressure_drop_pipe = perf_counter_ns()
    for _ in range(N):
        _acc_pressure_drop_pipe += pressure_drop_pipe(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_pressure_drop_pipe = perf_counter_ns()
    var _ns_pressure_drop_pipe = Float64(_t1_pressure_drop_pipe - _t0_pressure_drop_pipe) / Float64(N)
    print("MOJO_TIMING pneumatics::pressure_drop_pipe", _ns_pressure_drop_pipe, _acc_pressure_drop_pipe)
    var _result_pressure_drop_pipe = pressure_drop_pipe(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_pressure_drop_pipe = _summary_float64(_result_pressure_drop_pipe)
    print("MOJO_RESULT pneumatics::pressure_drop_pipe", _summary_pressure_drop_pipe)
    var _acc_air_consumption: Float64 = 0.0
    var _t0_air_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_air_consumption += air_consumption(0.5, 0.5, 0.5, 0.5)
    var _t1_air_consumption = perf_counter_ns()
    var _ns_air_consumption = Float64(_t1_air_consumption - _t0_air_consumption) / Float64(N)
    print("MOJO_TIMING pneumatics::air_consumption", _ns_air_consumption, _acc_air_consumption)
    var _result_air_consumption = air_consumption(0.5, 0.5, 0.5, 0.5)
    var _summary_air_consumption = _summary_float64(_result_air_consumption)
    print("MOJO_RESULT pneumatics::air_consumption", _summary_air_consumption)
    var _acc_cylinder_force: Float64 = 0.0
    var _t0_cylinder_force = perf_counter_ns()
    for _ in range(N):
        _acc_cylinder_force += cylinder_force(0.5, 0.5)
    var _t1_cylinder_force = perf_counter_ns()
    var _ns_cylinder_force = Float64(_t1_cylinder_force - _t0_cylinder_force) / Float64(N)
    print("MOJO_TIMING pneumatics::cylinder_force", _ns_cylinder_force, _acc_cylinder_force)
    var _result_cylinder_force = cylinder_force(0.5, 0.5)
    var _summary_cylinder_force = _summary_float64(_result_cylinder_force)
    print("MOJO_RESULT pneumatics::cylinder_force", _summary_cylinder_force)
    var _acc_bore_area: Float64 = 0.0
    var _t0_bore_area = perf_counter_ns()
    for _ in range(N):
        _acc_bore_area += bore_area(0.5)
    var _t1_bore_area = perf_counter_ns()
    var _ns_bore_area = Float64(_t1_bore_area - _t0_bore_area) / Float64(N)
    print("MOJO_TIMING pneumatics::bore_area", _ns_bore_area, _acc_bore_area)
    var _result_bore_area = bore_area(0.5)
    var _summary_bore_area = _summary_float64(_result_bore_area)
    print("MOJO_RESULT pneumatics::bore_area", _summary_bore_area)
    var _acc_piston_speed: Float64 = 0.0
    var _t0_piston_speed = perf_counter_ns()
    for _ in range(N):
        _acc_piston_speed += piston_speed(0.5, 0.5)
    var _t1_piston_speed = perf_counter_ns()
    var _ns_piston_speed = Float64(_t1_piston_speed - _t0_piston_speed) / Float64(N)
    print("MOJO_TIMING pneumatics::piston_speed", _ns_piston_speed, _acc_piston_speed)
    var _result_piston_speed = piston_speed(0.5, 0.5)
    var _summary_piston_speed = _summary_float64(_result_piston_speed)
    print("MOJO_RESULT pneumatics::piston_speed", _summary_piston_speed)
    var _acc_receiver_volume: Float64 = 0.0
    var _t0_receiver_volume = perf_counter_ns()
    for _ in range(N):
        _acc_receiver_volume += receiver_volume(0.5, 0.5, 0.5, 0.5)
    var _t1_receiver_volume = perf_counter_ns()
    var _ns_receiver_volume = Float64(_t1_receiver_volume - _t0_receiver_volume) / Float64(N)
    print("MOJO_TIMING pneumatics::receiver_volume", _ns_receiver_volume, _acc_receiver_volume)
    var _result_receiver_volume = receiver_volume(0.5, 0.5, 0.5, 0.5)
    var _summary_receiver_volume = _summary_float64(_result_receiver_volume)
    print("MOJO_RESULT pneumatics::receiver_volume", _summary_receiver_volume)
    var _acc_free_air_delivery: Float64 = 0.0
    var _t0_free_air_delivery = perf_counter_ns()
    for _ in range(N):
        _acc_free_air_delivery += free_air_delivery(0.5, 0.5, 0.5)
    var _t1_free_air_delivery = perf_counter_ns()
    var _ns_free_air_delivery = Float64(_t1_free_air_delivery - _t0_free_air_delivery) / Float64(N)
    print("MOJO_TIMING pneumatics::free_air_delivery", _ns_free_air_delivery, _acc_free_air_delivery)
    var _result_free_air_delivery = free_air_delivery(0.5, 0.5, 0.5)
    var _summary_free_air_delivery = _summary_float64(_result_free_air_delivery)
    print("MOJO_RESULT pneumatics::free_air_delivery", _summary_free_air_delivery)
    var _acc_specific_power: Float64 = 0.0
    var _t0_specific_power = perf_counter_ns()
    for _ in range(N):
        _acc_specific_power += specific_power(0.5, 0.5)
    var _t1_specific_power = perf_counter_ns()
    var _ns_specific_power = Float64(_t1_specific_power - _t0_specific_power) / Float64(N)
    print("MOJO_TIMING pneumatics::specific_power", _ns_specific_power, _acc_specific_power)
    var _result_specific_power = specific_power(0.5, 0.5)
    var _summary_specific_power = _summary_float64(_result_specific_power)
    print("MOJO_RESULT pneumatics::specific_power", _summary_specific_power)
    var _acc_dew_point_pressure: Float64 = 0.0
    var _t0_dew_point_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_dew_point_pressure += dew_point_pressure(0.5, 0.5)
    var _t1_dew_point_pressure = perf_counter_ns()
    var _ns_dew_point_pressure = Float64(_t1_dew_point_pressure - _t0_dew_point_pressure) / Float64(N)
    print("MOJO_TIMING pneumatics::dew_point_pressure", _ns_dew_point_pressure, _acc_dew_point_pressure)
    var _result_dew_point_pressure = dew_point_pressure(0.5, 0.5)
    var _summary_dew_point_pressure = _summary_float64(_result_dew_point_pressure)
    print("MOJO_RESULT pneumatics::dew_point_pressure", _summary_dew_point_pressure)
