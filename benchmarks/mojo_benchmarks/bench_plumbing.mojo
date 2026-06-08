"""bench_plumbing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from plumbing import pipe_flow_velocity, reynolds_number, friction_factor_laminar, head_loss_darcy, head_loss_minor, total_dynamic_head, pump_power, water_demand_fixture_units, pipe_sizing_velocity_method, thermal_expansion_pipe, water_hammer_pressure, drainage_slope_minimum
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

    var _acc_pipe_flow_velocity: Float64 = 0.0
    var _t0_pipe_flow_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_pipe_flow_velocity += pipe_flow_velocity(0.5, 0.5)
    var _t1_pipe_flow_velocity = perf_counter_ns()
    var _ns_pipe_flow_velocity = Float64(_t1_pipe_flow_velocity - _t0_pipe_flow_velocity) / Float64(N)
    print("MOJO_TIMING plumbing::pipe_flow_velocity", _ns_pipe_flow_velocity, _acc_pipe_flow_velocity)
    var _result_pipe_flow_velocity = pipe_flow_velocity(0.5, 0.5)
    var _summary_pipe_flow_velocity = _summary_float64(_result_pipe_flow_velocity)
    print("MOJO_RESULT plumbing::pipe_flow_velocity", _summary_pipe_flow_velocity)
    var _acc_reynolds_number: Float64 = 0.0
    var _t0_reynolds_number = perf_counter_ns()
    for _ in range(N):
        _acc_reynolds_number += reynolds_number(0.5, 0.5, 0.5)
    var _t1_reynolds_number = perf_counter_ns()
    var _ns_reynolds_number = Float64(_t1_reynolds_number - _t0_reynolds_number) / Float64(N)
    print("MOJO_TIMING plumbing::reynolds_number", _ns_reynolds_number, _acc_reynolds_number)
    var _result_reynolds_number = reynolds_number(0.5, 0.5, 0.5)
    var _summary_reynolds_number = _summary_float64(_result_reynolds_number)
    print("MOJO_RESULT plumbing::reynolds_number", _summary_reynolds_number)
    var _acc_friction_factor_laminar: Float64 = 0.0
    var _t0_friction_factor_laminar = perf_counter_ns()
    for _ in range(N):
        _acc_friction_factor_laminar += friction_factor_laminar(0.5)
    var _t1_friction_factor_laminar = perf_counter_ns()
    var _ns_friction_factor_laminar = Float64(_t1_friction_factor_laminar - _t0_friction_factor_laminar) / Float64(N)
    print("MOJO_TIMING plumbing::friction_factor_laminar", _ns_friction_factor_laminar, _acc_friction_factor_laminar)
    var _result_friction_factor_laminar = friction_factor_laminar(0.5)
    var _summary_friction_factor_laminar = _summary_float64(_result_friction_factor_laminar)
    print("MOJO_RESULT plumbing::friction_factor_laminar", _summary_friction_factor_laminar)
    var _acc_head_loss_darcy: Float64 = 0.0
    var _t0_head_loss_darcy = perf_counter_ns()
    for _ in range(N):
        _acc_head_loss_darcy += head_loss_darcy(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_head_loss_darcy = perf_counter_ns()
    var _ns_head_loss_darcy = Float64(_t1_head_loss_darcy - _t0_head_loss_darcy) / Float64(N)
    print("MOJO_TIMING plumbing::head_loss_darcy", _ns_head_loss_darcy, _acc_head_loss_darcy)
    var _result_head_loss_darcy = head_loss_darcy(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_head_loss_darcy = _summary_float64(_result_head_loss_darcy)
    print("MOJO_RESULT plumbing::head_loss_darcy", _summary_head_loss_darcy)
    var _acc_head_loss_minor: Float64 = 0.0
    var _t0_head_loss_minor = perf_counter_ns()
    for _ in range(N):
        _acc_head_loss_minor += head_loss_minor(0.5, 0.5, 0.5)
    var _t1_head_loss_minor = perf_counter_ns()
    var _ns_head_loss_minor = Float64(_t1_head_loss_minor - _t0_head_loss_minor) / Float64(N)
    print("MOJO_TIMING plumbing::head_loss_minor", _ns_head_loss_minor, _acc_head_loss_minor)
    var _result_head_loss_minor = head_loss_minor(0.5, 0.5, 0.5)
    var _summary_head_loss_minor = _summary_float64(_result_head_loss_minor)
    print("MOJO_RESULT plumbing::head_loss_minor", _summary_head_loss_minor)
    var _acc_total_dynamic_head: Float64 = 0.0
    var _t0_total_dynamic_head = perf_counter_ns()
    for _ in range(N):
        _acc_total_dynamic_head += total_dynamic_head(0.5, 0.5, 0.5)
    var _t1_total_dynamic_head = perf_counter_ns()
    var _ns_total_dynamic_head = Float64(_t1_total_dynamic_head - _t0_total_dynamic_head) / Float64(N)
    print("MOJO_TIMING plumbing::total_dynamic_head", _ns_total_dynamic_head, _acc_total_dynamic_head)
    var _result_total_dynamic_head = total_dynamic_head(0.5, 0.5, 0.5)
    var _summary_total_dynamic_head = _summary_float64(_result_total_dynamic_head)
    print("MOJO_RESULT plumbing::total_dynamic_head", _summary_total_dynamic_head)
    var _acc_pump_power: Float64 = 0.0
    var _t0_pump_power = perf_counter_ns()
    for _ in range(N):
        _acc_pump_power += pump_power(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_pump_power = perf_counter_ns()
    var _ns_pump_power = Float64(_t1_pump_power - _t0_pump_power) / Float64(N)
    print("MOJO_TIMING plumbing::pump_power", _ns_pump_power, _acc_pump_power)
    var _result_pump_power = pump_power(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_pump_power = _summary_float64(_result_pump_power)
    print("MOJO_RESULT plumbing::pump_power", _summary_pump_power)
    var _acc_water_demand_fixture_units: Float64 = 0.0
    var _t0_water_demand_fixture_units = perf_counter_ns()
    for _ in range(N):
        _acc_water_demand_fixture_units += water_demand_fixture_units(0.5, 0.5)
    var _t1_water_demand_fixture_units = perf_counter_ns()
    var _ns_water_demand_fixture_units = Float64(_t1_water_demand_fixture_units - _t0_water_demand_fixture_units) / Float64(N)
    print("MOJO_TIMING plumbing::water_demand_fixture_units", _ns_water_demand_fixture_units, _acc_water_demand_fixture_units)
    var _result_water_demand_fixture_units = water_demand_fixture_units(0.5, 0.5)
    var _summary_water_demand_fixture_units = _summary_float64(_result_water_demand_fixture_units)
    print("MOJO_RESULT plumbing::water_demand_fixture_units", _summary_water_demand_fixture_units)
    var _acc_pipe_sizing_velocity_method: Float64 = 0.0
    var _t0_pipe_sizing_velocity_method = perf_counter_ns()
    for _ in range(N):
        _acc_pipe_sizing_velocity_method += pipe_sizing_velocity_method(0.5, 0.5)
    var _t1_pipe_sizing_velocity_method = perf_counter_ns()
    var _ns_pipe_sizing_velocity_method = Float64(_t1_pipe_sizing_velocity_method - _t0_pipe_sizing_velocity_method) / Float64(N)
    print("MOJO_TIMING plumbing::pipe_sizing_velocity_method", _ns_pipe_sizing_velocity_method, _acc_pipe_sizing_velocity_method)
    var _result_pipe_sizing_velocity_method = pipe_sizing_velocity_method(0.5, 0.5)
    var _summary_pipe_sizing_velocity_method = _summary_float64(_result_pipe_sizing_velocity_method)
    print("MOJO_RESULT plumbing::pipe_sizing_velocity_method", _summary_pipe_sizing_velocity_method)
    var _acc_thermal_expansion_pipe: Float64 = 0.0
    var _t0_thermal_expansion_pipe = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_expansion_pipe += thermal_expansion_pipe(0.5, 0.5, 0.5)
    var _t1_thermal_expansion_pipe = perf_counter_ns()
    var _ns_thermal_expansion_pipe = Float64(_t1_thermal_expansion_pipe - _t0_thermal_expansion_pipe) / Float64(N)
    print("MOJO_TIMING plumbing::thermal_expansion_pipe", _ns_thermal_expansion_pipe, _acc_thermal_expansion_pipe)
    var _result_thermal_expansion_pipe = thermal_expansion_pipe(0.5, 0.5, 0.5)
    var _summary_thermal_expansion_pipe = _summary_float64(_result_thermal_expansion_pipe)
    print("MOJO_RESULT plumbing::thermal_expansion_pipe", _summary_thermal_expansion_pipe)
    var _acc_water_hammer_pressure: Float64 = 0.0
    var _t0_water_hammer_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_water_hammer_pressure += water_hammer_pressure(0.5, 0.5, 0.5)
    var _t1_water_hammer_pressure = perf_counter_ns()
    var _ns_water_hammer_pressure = Float64(_t1_water_hammer_pressure - _t0_water_hammer_pressure) / Float64(N)
    print("MOJO_TIMING plumbing::water_hammer_pressure", _ns_water_hammer_pressure, _acc_water_hammer_pressure)
    var _result_water_hammer_pressure = water_hammer_pressure(0.5, 0.5, 0.5)
    var _summary_water_hammer_pressure = _summary_float64(_result_water_hammer_pressure)
    print("MOJO_RESULT plumbing::water_hammer_pressure", _summary_water_hammer_pressure)
    var _acc_drainage_slope_minimum: Float64 = 0.0
    var _t0_drainage_slope_minimum = perf_counter_ns()
    for _ in range(N):
        _acc_drainage_slope_minimum += drainage_slope_minimum(0.5)
    var _t1_drainage_slope_minimum = perf_counter_ns()
    var _ns_drainage_slope_minimum = Float64(_t1_drainage_slope_minimum - _t0_drainage_slope_minimum) / Float64(N)
    print("MOJO_TIMING plumbing::drainage_slope_minimum", _ns_drainage_slope_minimum, _acc_drainage_slope_minimum)
    var _result_drainage_slope_minimum = drainage_slope_minimum(0.5)
    var _summary_drainage_slope_minimum = _summary_float64(_result_drainage_slope_minimum)
    print("MOJO_RESULT plumbing::drainage_slope_minimum", _summary_drainage_slope_minimum)
