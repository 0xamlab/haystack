"""bench_fluid.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from fluid import reynolds_number, is_turbulent, bernoulli_velocity, friction_factor_laminar, darcy_weisbach, flow_rate, pipe_velocity, hydraulic_diameter, mach_number, drag_force, buoyancy_force, stokes_drag
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

    var _acc_reynolds_number: Float64 = 0.0
    var _t0_reynolds_number = perf_counter_ns()
    for _ in range(N):
        _acc_reynolds_number += reynolds_number(0.5, 0.5, 0.5)
    var _t1_reynolds_number = perf_counter_ns()
    var _ns_reynolds_number = Float64(_t1_reynolds_number - _t0_reynolds_number) / Float64(N)
    print("MOJO_TIMING fluid::reynolds_number", _ns_reynolds_number, _acc_reynolds_number)
    var _result_reynolds_number = reynolds_number(0.5, 0.5, 0.5)
    var _summary_reynolds_number = _summary_float64(_result_reynolds_number)
    print("MOJO_RESULT fluid::reynolds_number", _summary_reynolds_number)
    var _acc_is_turbulent: Float64 = 0.0
    var _t0_is_turbulent = perf_counter_ns()
    for _ in range(N):
        _acc_is_turbulent += Float64(is_turbulent(0.5))
    var _t1_is_turbulent = perf_counter_ns()
    var _ns_is_turbulent = Float64(_t1_is_turbulent - _t0_is_turbulent) / Float64(N)
    print("MOJO_TIMING fluid::is_turbulent", _ns_is_turbulent, _acc_is_turbulent)
    var _result_is_turbulent = is_turbulent(0.5)
    var _summary_is_turbulent = _summary_bool(_result_is_turbulent)
    print("MOJO_RESULT fluid::is_turbulent", _summary_is_turbulent)
    var _acc_bernoulli_velocity: Float64 = 0.0
    var _t0_bernoulli_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_bernoulli_velocity += bernoulli_velocity(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_bernoulli_velocity = perf_counter_ns()
    var _ns_bernoulli_velocity = Float64(_t1_bernoulli_velocity - _t0_bernoulli_velocity) / Float64(N)
    print("MOJO_TIMING fluid::bernoulli_velocity", _ns_bernoulli_velocity, _acc_bernoulli_velocity)
    var _result_bernoulli_velocity = bernoulli_velocity(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_bernoulli_velocity = _summary_float64(_result_bernoulli_velocity)
    print("MOJO_RESULT fluid::bernoulli_velocity", _summary_bernoulli_velocity)
    var _acc_friction_factor_laminar: Float64 = 0.0
    var _t0_friction_factor_laminar = perf_counter_ns()
    for _ in range(N):
        _acc_friction_factor_laminar += friction_factor_laminar(0.5)
    var _t1_friction_factor_laminar = perf_counter_ns()
    var _ns_friction_factor_laminar = Float64(_t1_friction_factor_laminar - _t0_friction_factor_laminar) / Float64(N)
    print("MOJO_TIMING fluid::friction_factor_laminar", _ns_friction_factor_laminar, _acc_friction_factor_laminar)
    var _result_friction_factor_laminar = friction_factor_laminar(0.5)
    var _summary_friction_factor_laminar = _summary_float64(_result_friction_factor_laminar)
    print("MOJO_RESULT fluid::friction_factor_laminar", _summary_friction_factor_laminar)
    var _acc_darcy_weisbach: Float64 = 0.0
    var _t0_darcy_weisbach = perf_counter_ns()
    for _ in range(N):
        _acc_darcy_weisbach += darcy_weisbach(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_darcy_weisbach = perf_counter_ns()
    var _ns_darcy_weisbach = Float64(_t1_darcy_weisbach - _t0_darcy_weisbach) / Float64(N)
    print("MOJO_TIMING fluid::darcy_weisbach", _ns_darcy_weisbach, _acc_darcy_weisbach)
    var _result_darcy_weisbach = darcy_weisbach(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_darcy_weisbach = _summary_float64(_result_darcy_weisbach)
    print("MOJO_RESULT fluid::darcy_weisbach", _summary_darcy_weisbach)
    var _acc_flow_rate: Float64 = 0.0
    var _t0_flow_rate = perf_counter_ns()
    for _ in range(N):
        _acc_flow_rate += flow_rate(0.5, 0.5)
    var _t1_flow_rate = perf_counter_ns()
    var _ns_flow_rate = Float64(_t1_flow_rate - _t0_flow_rate) / Float64(N)
    print("MOJO_TIMING fluid::flow_rate", _ns_flow_rate, _acc_flow_rate)
    var _result_flow_rate = flow_rate(0.5, 0.5)
    var _summary_flow_rate = _summary_float64(_result_flow_rate)
    print("MOJO_RESULT fluid::flow_rate", _summary_flow_rate)
    var _acc_pipe_velocity: Float64 = 0.0
    var _t0_pipe_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_pipe_velocity += pipe_velocity(0.5, 0.5)
    var _t1_pipe_velocity = perf_counter_ns()
    var _ns_pipe_velocity = Float64(_t1_pipe_velocity - _t0_pipe_velocity) / Float64(N)
    print("MOJO_TIMING fluid::pipe_velocity", _ns_pipe_velocity, _acc_pipe_velocity)
    var _result_pipe_velocity = pipe_velocity(0.5, 0.5)
    var _summary_pipe_velocity = _summary_float64(_result_pipe_velocity)
    print("MOJO_RESULT fluid::pipe_velocity", _summary_pipe_velocity)
    var _acc_hydraulic_diameter: Float64 = 0.0
    var _t0_hydraulic_diameter = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_diameter += hydraulic_diameter(0.5, 0.5)
    var _t1_hydraulic_diameter = perf_counter_ns()
    var _ns_hydraulic_diameter = Float64(_t1_hydraulic_diameter - _t0_hydraulic_diameter) / Float64(N)
    print("MOJO_TIMING fluid::hydraulic_diameter", _ns_hydraulic_diameter, _acc_hydraulic_diameter)
    var _result_hydraulic_diameter = hydraulic_diameter(0.5, 0.5)
    var _summary_hydraulic_diameter = _summary_float64(_result_hydraulic_diameter)
    print("MOJO_RESULT fluid::hydraulic_diameter", _summary_hydraulic_diameter)
    var _acc_mach_number: Float64 = 0.0
    var _t0_mach_number = perf_counter_ns()
    for _ in range(N):
        _acc_mach_number += mach_number(0.5, 0.5)
    var _t1_mach_number = perf_counter_ns()
    var _ns_mach_number = Float64(_t1_mach_number - _t0_mach_number) / Float64(N)
    print("MOJO_TIMING fluid::mach_number", _ns_mach_number, _acc_mach_number)
    var _result_mach_number = mach_number(0.5, 0.5)
    var _summary_mach_number = _summary_float64(_result_mach_number)
    print("MOJO_RESULT fluid::mach_number", _summary_mach_number)
    var _acc_drag_force: Float64 = 0.0
    var _t0_drag_force = perf_counter_ns()
    for _ in range(N):
        _acc_drag_force += drag_force(0.5, 0.5, 0.5, 0.5)
    var _t1_drag_force = perf_counter_ns()
    var _ns_drag_force = Float64(_t1_drag_force - _t0_drag_force) / Float64(N)
    print("MOJO_TIMING fluid::drag_force", _ns_drag_force, _acc_drag_force)
    var _result_drag_force = drag_force(0.5, 0.5, 0.5, 0.5)
    var _summary_drag_force = _summary_float64(_result_drag_force)
    print("MOJO_RESULT fluid::drag_force", _summary_drag_force)
    var _acc_buoyancy_force: Float64 = 0.0
    var _t0_buoyancy_force = perf_counter_ns()
    for _ in range(N):
        _acc_buoyancy_force += buoyancy_force(0.5, 0.5, 0.5)
    var _t1_buoyancy_force = perf_counter_ns()
    var _ns_buoyancy_force = Float64(_t1_buoyancy_force - _t0_buoyancy_force) / Float64(N)
    print("MOJO_TIMING fluid::buoyancy_force", _ns_buoyancy_force, _acc_buoyancy_force)
    var _result_buoyancy_force = buoyancy_force(0.5, 0.5, 0.5)
    var _summary_buoyancy_force = _summary_float64(_result_buoyancy_force)
    print("MOJO_RESULT fluid::buoyancy_force", _summary_buoyancy_force)
    var _acc_stokes_drag: Float64 = 0.0
    var _t0_stokes_drag = perf_counter_ns()
    for _ in range(N):
        _acc_stokes_drag += stokes_drag(0.5, 0.5, 0.5)
    var _t1_stokes_drag = perf_counter_ns()
    var _ns_stokes_drag = Float64(_t1_stokes_drag - _t0_stokes_drag) / Float64(N)
    print("MOJO_TIMING fluid::stokes_drag", _ns_stokes_drag, _acc_stokes_drag)
    var _result_stokes_drag = stokes_drag(0.5, 0.5, 0.5)
    var _summary_stokes_drag = _summary_float64(_result_stokes_drag)
    print("MOJO_RESULT fluid::stokes_drag", _summary_stokes_drag)
