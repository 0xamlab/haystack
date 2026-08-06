"""bench_hydraulics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hydraulics import pascals_law_force, pascals_law_pressure, hydraulic_advantage, flow_rate_cylinder, cylinder_velocity, pump_displacement, hydraulic_power, system_pressure_loss, accumulator_volume, relief_valve_flow, oil_compressibility, cylinder_bore_from_force
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

    var _acc_pascals_law_force: Float64 = 0.0
    var _t0_pascals_law_force = perf_counter_ns()
    for _ in range(N):
        _acc_pascals_law_force += pascals_law_force(0.5, 0.5)
    var _t1_pascals_law_force = perf_counter_ns()
    var _ns_pascals_law_force = Float64(_t1_pascals_law_force - _t0_pascals_law_force) / Float64(N)
    print("MOJO_TIMING hydraulics::pascals_law_force", _ns_pascals_law_force, _acc_pascals_law_force)
    var _result_pascals_law_force = pascals_law_force(0.5, 0.5)
    var _summary_pascals_law_force = _summary_float64(_result_pascals_law_force)
    print("MOJO_RESULT hydraulics::pascals_law_force", _summary_pascals_law_force)
    var _acc_pascals_law_pressure: Float64 = 0.0
    var _t0_pascals_law_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_pascals_law_pressure += pascals_law_pressure(0.5, 0.5)
    var _t1_pascals_law_pressure = perf_counter_ns()
    var _ns_pascals_law_pressure = Float64(_t1_pascals_law_pressure - _t0_pascals_law_pressure) / Float64(N)
    print("MOJO_TIMING hydraulics::pascals_law_pressure", _ns_pascals_law_pressure, _acc_pascals_law_pressure)
    var _result_pascals_law_pressure = pascals_law_pressure(0.5, 0.5)
    var _summary_pascals_law_pressure = _summary_float64(_result_pascals_law_pressure)
    print("MOJO_RESULT hydraulics::pascals_law_pressure", _summary_pascals_law_pressure)
    var _acc_hydraulic_advantage: Float64 = 0.0
    var _t0_hydraulic_advantage = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_advantage += hydraulic_advantage(0.5, 0.5)
    var _t1_hydraulic_advantage = perf_counter_ns()
    var _ns_hydraulic_advantage = Float64(_t1_hydraulic_advantage - _t0_hydraulic_advantage) / Float64(N)
    print("MOJO_TIMING hydraulics::hydraulic_advantage", _ns_hydraulic_advantage, _acc_hydraulic_advantage)
    var _result_hydraulic_advantage = hydraulic_advantage(0.5, 0.5)
    var _summary_hydraulic_advantage = _summary_float64(_result_hydraulic_advantage)
    print("MOJO_RESULT hydraulics::hydraulic_advantage", _summary_hydraulic_advantage)
    var _acc_flow_rate_cylinder: Float64 = 0.0
    var _t0_flow_rate_cylinder = perf_counter_ns()
    for _ in range(N):
        _acc_flow_rate_cylinder += flow_rate_cylinder(0.5, 0.5)
    var _t1_flow_rate_cylinder = perf_counter_ns()
    var _ns_flow_rate_cylinder = Float64(_t1_flow_rate_cylinder - _t0_flow_rate_cylinder) / Float64(N)
    print("MOJO_TIMING hydraulics::flow_rate_cylinder", _ns_flow_rate_cylinder, _acc_flow_rate_cylinder)
    var _result_flow_rate_cylinder = flow_rate_cylinder(0.5, 0.5)
    var _summary_flow_rate_cylinder = _summary_float64(_result_flow_rate_cylinder)
    print("MOJO_RESULT hydraulics::flow_rate_cylinder", _summary_flow_rate_cylinder)
    var _acc_cylinder_velocity: Float64 = 0.0
    var _t0_cylinder_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_cylinder_velocity += cylinder_velocity(0.5, 0.5)
    var _t1_cylinder_velocity = perf_counter_ns()
    var _ns_cylinder_velocity = Float64(_t1_cylinder_velocity - _t0_cylinder_velocity) / Float64(N)
    print("MOJO_TIMING hydraulics::cylinder_velocity", _ns_cylinder_velocity, _acc_cylinder_velocity)
    var _result_cylinder_velocity = cylinder_velocity(0.5, 0.5)
    var _summary_cylinder_velocity = _summary_float64(_result_cylinder_velocity)
    print("MOJO_RESULT hydraulics::cylinder_velocity", _summary_cylinder_velocity)
    var _acc_pump_displacement: Float64 = 0.0
    var _t0_pump_displacement = perf_counter_ns()
    for _ in range(N):
        _acc_pump_displacement += pump_displacement(0.5, 0.5)
    var _t1_pump_displacement = perf_counter_ns()
    var _ns_pump_displacement = Float64(_t1_pump_displacement - _t0_pump_displacement) / Float64(N)
    print("MOJO_TIMING hydraulics::pump_displacement", _ns_pump_displacement, _acc_pump_displacement)
    var _result_pump_displacement = pump_displacement(0.5, 0.5)
    var _summary_pump_displacement = _summary_float64(_result_pump_displacement)
    print("MOJO_RESULT hydraulics::pump_displacement", _summary_pump_displacement)
    var _acc_hydraulic_power: Float64 = 0.0
    var _t0_hydraulic_power = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_power += hydraulic_power(0.5, 0.5)
    var _t1_hydraulic_power = perf_counter_ns()
    var _ns_hydraulic_power = Float64(_t1_hydraulic_power - _t0_hydraulic_power) / Float64(N)
    print("MOJO_TIMING hydraulics::hydraulic_power", _ns_hydraulic_power, _acc_hydraulic_power)
    var _result_hydraulic_power = hydraulic_power(0.5, 0.5)
    var _summary_hydraulic_power = _summary_float64(_result_hydraulic_power)
    print("MOJO_RESULT hydraulics::hydraulic_power", _summary_hydraulic_power)
    var _acc_system_pressure_loss: Float64 = 0.0
    var _t0_system_pressure_loss = perf_counter_ns()
    for _ in range(N):
        _acc_system_pressure_loss += system_pressure_loss(0.5, 0.5)
    var _t1_system_pressure_loss = perf_counter_ns()
    var _ns_system_pressure_loss = Float64(_t1_system_pressure_loss - _t0_system_pressure_loss) / Float64(N)
    print("MOJO_TIMING hydraulics::system_pressure_loss", _ns_system_pressure_loss, _acc_system_pressure_loss)
    var _result_system_pressure_loss = system_pressure_loss(0.5, 0.5)
    var _summary_system_pressure_loss = _summary_float64(_result_system_pressure_loss)
    print("MOJO_RESULT hydraulics::system_pressure_loss", _summary_system_pressure_loss)
    var _acc_accumulator_volume: Float64 = 0.0
    var _t0_accumulator_volume = perf_counter_ns()
    for _ in range(N):
        _acc_accumulator_volume += accumulator_volume(0.5, 0.5, 0.5)
    var _t1_accumulator_volume = perf_counter_ns()
    var _ns_accumulator_volume = Float64(_t1_accumulator_volume - _t0_accumulator_volume) / Float64(N)
    print("MOJO_TIMING hydraulics::accumulator_volume", _ns_accumulator_volume, _acc_accumulator_volume)
    var _result_accumulator_volume = accumulator_volume(0.5, 0.5, 0.5)
    var _summary_accumulator_volume = _summary_float64(_result_accumulator_volume)
    print("MOJO_RESULT hydraulics::accumulator_volume", _summary_accumulator_volume)
    var _acc_relief_valve_flow: Float64 = 0.0
    var _t0_relief_valve_flow = perf_counter_ns()
    for _ in range(N):
        _acc_relief_valve_flow += relief_valve_flow(0.5, 0.5, 0.5)
    var _t1_relief_valve_flow = perf_counter_ns()
    var _ns_relief_valve_flow = Float64(_t1_relief_valve_flow - _t0_relief_valve_flow) / Float64(N)
    print("MOJO_TIMING hydraulics::relief_valve_flow", _ns_relief_valve_flow, _acc_relief_valve_flow)
    var _result_relief_valve_flow = relief_valve_flow(0.5, 0.5, 0.5)
    var _summary_relief_valve_flow = _summary_float64(_result_relief_valve_flow)
    print("MOJO_RESULT hydraulics::relief_valve_flow", _summary_relief_valve_flow)
    var _acc_oil_compressibility: Float64 = 0.0
    var _t0_oil_compressibility = perf_counter_ns()
    for _ in range(N):
        _acc_oil_compressibility += oil_compressibility(0.5, 0.5, 0.5)
    var _t1_oil_compressibility = perf_counter_ns()
    var _ns_oil_compressibility = Float64(_t1_oil_compressibility - _t0_oil_compressibility) / Float64(N)
    print("MOJO_TIMING hydraulics::oil_compressibility", _ns_oil_compressibility, _acc_oil_compressibility)
    var _result_oil_compressibility = oil_compressibility(0.5, 0.5, 0.5)
    var _summary_oil_compressibility = _summary_float64(_result_oil_compressibility)
    print("MOJO_RESULT hydraulics::oil_compressibility", _summary_oil_compressibility)
    var _acc_cylinder_bore_from_force: Float64 = 0.0
    var _t0_cylinder_bore_from_force = perf_counter_ns()
    for _ in range(N):
        _acc_cylinder_bore_from_force += cylinder_bore_from_force(0.5, 0.5)
    var _t1_cylinder_bore_from_force = perf_counter_ns()
    var _ns_cylinder_bore_from_force = Float64(_t1_cylinder_bore_from_force - _t0_cylinder_bore_from_force) / Float64(N)
    print("MOJO_TIMING hydraulics::cylinder_bore_from_force", _ns_cylinder_bore_from_force, _acc_cylinder_bore_from_force)
    var _result_cylinder_bore_from_force = cylinder_bore_from_force(0.5, 0.5)
    var _summary_cylinder_bore_from_force = _summary_float64(_result_cylinder_bore_from_force)
    print("MOJO_RESULT hydraulics::cylinder_bore_from_force", _summary_cylinder_bore_from_force)
