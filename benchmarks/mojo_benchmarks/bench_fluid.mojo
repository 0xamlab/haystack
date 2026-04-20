"""bench_fluid.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from fluid import reynolds_number, is_turbulent, bernoulli_velocity, friction_factor_laminar, darcy_weisbach, flow_rate, pipe_velocity, hydraulic_diameter, mach_number, drag_force, buoyancy_force, stokes_drag
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

    var _acc_reynolds_number: Float64 = 0.0
    var _t0_reynolds_number = perf_counter_ns()
    for _ in range(N):
        _acc_reynolds_number += reynolds_number(0.5, 0.5, 0.5)
    var _t1_reynolds_number = perf_counter_ns()
    var _ns_reynolds_number = Float64(_t1_reynolds_number - _t0_reynolds_number) / Float64(N)
    print("MOJO_TIMING fluid::reynolds_number", _ns_reynolds_number, _acc_reynolds_number)
    var _acc_is_turbulent: Float64 = 0.0
    var _t0_is_turbulent = perf_counter_ns()
    for _ in range(N):
        _acc_is_turbulent += Float64(is_turbulent(0.5))
    var _t1_is_turbulent = perf_counter_ns()
    var _ns_is_turbulent = Float64(_t1_is_turbulent - _t0_is_turbulent) / Float64(N)
    print("MOJO_TIMING fluid::is_turbulent", _ns_is_turbulent, _acc_is_turbulent)
    var _acc_bernoulli_velocity: Float64 = 0.0
    var _t0_bernoulli_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_bernoulli_velocity += bernoulli_velocity(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_bernoulli_velocity = perf_counter_ns()
    var _ns_bernoulli_velocity = Float64(_t1_bernoulli_velocity - _t0_bernoulli_velocity) / Float64(N)
    print("MOJO_TIMING fluid::bernoulli_velocity", _ns_bernoulli_velocity, _acc_bernoulli_velocity)
    var _acc_friction_factor_laminar: Float64 = 0.0
    var _t0_friction_factor_laminar = perf_counter_ns()
    for _ in range(N):
        _acc_friction_factor_laminar += friction_factor_laminar(0.5)
    var _t1_friction_factor_laminar = perf_counter_ns()
    var _ns_friction_factor_laminar = Float64(_t1_friction_factor_laminar - _t0_friction_factor_laminar) / Float64(N)
    print("MOJO_TIMING fluid::friction_factor_laminar", _ns_friction_factor_laminar, _acc_friction_factor_laminar)
    var _acc_darcy_weisbach: Float64 = 0.0
    var _t0_darcy_weisbach = perf_counter_ns()
    for _ in range(N):
        _acc_darcy_weisbach += darcy_weisbach(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_darcy_weisbach = perf_counter_ns()
    var _ns_darcy_weisbach = Float64(_t1_darcy_weisbach - _t0_darcy_weisbach) / Float64(N)
    print("MOJO_TIMING fluid::darcy_weisbach", _ns_darcy_weisbach, _acc_darcy_weisbach)
    var _acc_flow_rate: Float64 = 0.0
    var _t0_flow_rate = perf_counter_ns()
    for _ in range(N):
        _acc_flow_rate += flow_rate(0.5, 0.5)
    var _t1_flow_rate = perf_counter_ns()
    var _ns_flow_rate = Float64(_t1_flow_rate - _t0_flow_rate) / Float64(N)
    print("MOJO_TIMING fluid::flow_rate", _ns_flow_rate, _acc_flow_rate)
    var _acc_pipe_velocity: Float64 = 0.0
    var _t0_pipe_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_pipe_velocity += pipe_velocity(0.5, 0.5)
    var _t1_pipe_velocity = perf_counter_ns()
    var _ns_pipe_velocity = Float64(_t1_pipe_velocity - _t0_pipe_velocity) / Float64(N)
    print("MOJO_TIMING fluid::pipe_velocity", _ns_pipe_velocity, _acc_pipe_velocity)
    var _acc_hydraulic_diameter: Float64 = 0.0
    var _t0_hydraulic_diameter = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_diameter += hydraulic_diameter(0.5, 0.5)
    var _t1_hydraulic_diameter = perf_counter_ns()
    var _ns_hydraulic_diameter = Float64(_t1_hydraulic_diameter - _t0_hydraulic_diameter) / Float64(N)
    print("MOJO_TIMING fluid::hydraulic_diameter", _ns_hydraulic_diameter, _acc_hydraulic_diameter)
    var _acc_mach_number: Float64 = 0.0
    var _t0_mach_number = perf_counter_ns()
    for _ in range(N):
        _acc_mach_number += mach_number(0.5, 0.5)
    var _t1_mach_number = perf_counter_ns()
    var _ns_mach_number = Float64(_t1_mach_number - _t0_mach_number) / Float64(N)
    print("MOJO_TIMING fluid::mach_number", _ns_mach_number, _acc_mach_number)
    var _acc_drag_force: Float64 = 0.0
    var _t0_drag_force = perf_counter_ns()
    for _ in range(N):
        _acc_drag_force += drag_force(0.5, 0.5, 0.5, 0.5)
    var _t1_drag_force = perf_counter_ns()
    var _ns_drag_force = Float64(_t1_drag_force - _t0_drag_force) / Float64(N)
    print("MOJO_TIMING fluid::drag_force", _ns_drag_force, _acc_drag_force)
    var _acc_buoyancy_force: Float64 = 0.0
    var _t0_buoyancy_force = perf_counter_ns()
    for _ in range(N):
        _acc_buoyancy_force += buoyancy_force(0.5, 0.5, 0.5)
    var _t1_buoyancy_force = perf_counter_ns()
    var _ns_buoyancy_force = Float64(_t1_buoyancy_force - _t0_buoyancy_force) / Float64(N)
    print("MOJO_TIMING fluid::buoyancy_force", _ns_buoyancy_force, _acc_buoyancy_force)
    var _acc_stokes_drag: Float64 = 0.0
    var _t0_stokes_drag = perf_counter_ns()
    for _ in range(N):
        _acc_stokes_drag += stokes_drag(0.5, 0.5, 0.5)
    var _t1_stokes_drag = perf_counter_ns()
    var _ns_stokes_drag = Float64(_t1_stokes_drag - _t0_stokes_drag) / Float64(N)
    print("MOJO_TIMING fluid::stokes_drag", _ns_stokes_drag, _acc_stokes_drag)
