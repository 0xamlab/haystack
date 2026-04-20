"""bench_plumbing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from plumbing import pipe_flow_velocity, reynolds_number, friction_factor_laminar, head_loss_darcy, head_loss_minor, total_dynamic_head, pump_power, water_demand_fixture_units, pipe_sizing_velocity_method, thermal_expansion_pipe, water_hammer_pressure, drainage_slope_minimum
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

    var _acc_pipe_flow_velocity: Float64 = 0.0
    var _t0_pipe_flow_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_pipe_flow_velocity += pipe_flow_velocity(0.5, 0.5)
    var _t1_pipe_flow_velocity = perf_counter_ns()
    var _ns_pipe_flow_velocity = Float64(_t1_pipe_flow_velocity - _t0_pipe_flow_velocity) / Float64(N)
    print("MOJO_TIMING plumbing::pipe_flow_velocity", _ns_pipe_flow_velocity, _acc_pipe_flow_velocity)
    var _acc_reynolds_number: Float64 = 0.0
    var _t0_reynolds_number = perf_counter_ns()
    for _ in range(N):
        _acc_reynolds_number += reynolds_number(0.5, 0.5, 0.5)
    var _t1_reynolds_number = perf_counter_ns()
    var _ns_reynolds_number = Float64(_t1_reynolds_number - _t0_reynolds_number) / Float64(N)
    print("MOJO_TIMING plumbing::reynolds_number", _ns_reynolds_number, _acc_reynolds_number)
    var _acc_friction_factor_laminar: Float64 = 0.0
    var _t0_friction_factor_laminar = perf_counter_ns()
    for _ in range(N):
        _acc_friction_factor_laminar += friction_factor_laminar(0.5)
    var _t1_friction_factor_laminar = perf_counter_ns()
    var _ns_friction_factor_laminar = Float64(_t1_friction_factor_laminar - _t0_friction_factor_laminar) / Float64(N)
    print("MOJO_TIMING plumbing::friction_factor_laminar", _ns_friction_factor_laminar, _acc_friction_factor_laminar)
    var _acc_head_loss_darcy: Float64 = 0.0
    var _t0_head_loss_darcy = perf_counter_ns()
    for _ in range(N):
        _acc_head_loss_darcy += head_loss_darcy(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_head_loss_darcy = perf_counter_ns()
    var _ns_head_loss_darcy = Float64(_t1_head_loss_darcy - _t0_head_loss_darcy) / Float64(N)
    print("MOJO_TIMING plumbing::head_loss_darcy", _ns_head_loss_darcy, _acc_head_loss_darcy)
    var _acc_head_loss_minor: Float64 = 0.0
    var _t0_head_loss_minor = perf_counter_ns()
    for _ in range(N):
        _acc_head_loss_minor += head_loss_minor(0.5, 0.5, 0.5)
    var _t1_head_loss_minor = perf_counter_ns()
    var _ns_head_loss_minor = Float64(_t1_head_loss_minor - _t0_head_loss_minor) / Float64(N)
    print("MOJO_TIMING plumbing::head_loss_minor", _ns_head_loss_minor, _acc_head_loss_minor)
    var _acc_total_dynamic_head: Float64 = 0.0
    var _t0_total_dynamic_head = perf_counter_ns()
    for _ in range(N):
        _acc_total_dynamic_head += total_dynamic_head(0.5, 0.5, 0.5)
    var _t1_total_dynamic_head = perf_counter_ns()
    var _ns_total_dynamic_head = Float64(_t1_total_dynamic_head - _t0_total_dynamic_head) / Float64(N)
    print("MOJO_TIMING plumbing::total_dynamic_head", _ns_total_dynamic_head, _acc_total_dynamic_head)
    var _acc_pump_power: Float64 = 0.0
    var _t0_pump_power = perf_counter_ns()
    for _ in range(N):
        _acc_pump_power += pump_power(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_pump_power = perf_counter_ns()
    var _ns_pump_power = Float64(_t1_pump_power - _t0_pump_power) / Float64(N)
    print("MOJO_TIMING plumbing::pump_power", _ns_pump_power, _acc_pump_power)
    var _acc_water_demand_fixture_units: Float64 = 0.0
    var _t0_water_demand_fixture_units = perf_counter_ns()
    for _ in range(N):
        _acc_water_demand_fixture_units += water_demand_fixture_units(0.5, 0.5)
    var _t1_water_demand_fixture_units = perf_counter_ns()
    var _ns_water_demand_fixture_units = Float64(_t1_water_demand_fixture_units - _t0_water_demand_fixture_units) / Float64(N)
    print("MOJO_TIMING plumbing::water_demand_fixture_units", _ns_water_demand_fixture_units, _acc_water_demand_fixture_units)
    var _acc_pipe_sizing_velocity_method: Float64 = 0.0
    var _t0_pipe_sizing_velocity_method = perf_counter_ns()
    for _ in range(N):
        _acc_pipe_sizing_velocity_method += pipe_sizing_velocity_method(0.5, 0.5)
    var _t1_pipe_sizing_velocity_method = perf_counter_ns()
    var _ns_pipe_sizing_velocity_method = Float64(_t1_pipe_sizing_velocity_method - _t0_pipe_sizing_velocity_method) / Float64(N)
    print("MOJO_TIMING plumbing::pipe_sizing_velocity_method", _ns_pipe_sizing_velocity_method, _acc_pipe_sizing_velocity_method)
    var _acc_thermal_expansion_pipe: Float64 = 0.0
    var _t0_thermal_expansion_pipe = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_expansion_pipe += thermal_expansion_pipe(0.5, 0.5, 0.5)
    var _t1_thermal_expansion_pipe = perf_counter_ns()
    var _ns_thermal_expansion_pipe = Float64(_t1_thermal_expansion_pipe - _t0_thermal_expansion_pipe) / Float64(N)
    print("MOJO_TIMING plumbing::thermal_expansion_pipe", _ns_thermal_expansion_pipe, _acc_thermal_expansion_pipe)
    var _acc_water_hammer_pressure: Float64 = 0.0
    var _t0_water_hammer_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_water_hammer_pressure += water_hammer_pressure(0.5, 0.5, 0.5)
    var _t1_water_hammer_pressure = perf_counter_ns()
    var _ns_water_hammer_pressure = Float64(_t1_water_hammer_pressure - _t0_water_hammer_pressure) / Float64(N)
    print("MOJO_TIMING plumbing::water_hammer_pressure", _ns_water_hammer_pressure, _acc_water_hammer_pressure)
    var _acc_drainage_slope_minimum: Float64 = 0.0
    var _t0_drainage_slope_minimum = perf_counter_ns()
    for _ in range(N):
        _acc_drainage_slope_minimum += drainage_slope_minimum(0.5)
    var _t1_drainage_slope_minimum = perf_counter_ns()
    var _ns_drainage_slope_minimum = Float64(_t1_drainage_slope_minimum - _t0_drainage_slope_minimum) / Float64(N)
    print("MOJO_TIMING plumbing::drainage_slope_minimum", _ns_drainage_slope_minimum, _acc_drainage_slope_minimum)
