"""bench_hydrology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hydrology import manning_velocity, manning_discharge, hydraulic_radius, froude_number, reynolds_number_pipe, darcy_weisbach_head_loss, rational_method_peak_flow, time_of_concentration_kirpich, curve_number_runoff, evapotranspiration_hargreaves, specific_yield, darcy_groundwater_velocity
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

    var _acc_manning_velocity: Float64 = 0.0
    var _t0_manning_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_manning_velocity += manning_velocity(0.5, 0.5, 0.5)
    var _t1_manning_velocity = perf_counter_ns()
    var _ns_manning_velocity = Float64(_t1_manning_velocity - _t0_manning_velocity) / Float64(N)
    print("MOJO_TIMING hydrology::manning_velocity", _ns_manning_velocity, _acc_manning_velocity)
    var _acc_manning_discharge: Float64 = 0.0
    var _t0_manning_discharge = perf_counter_ns()
    for _ in range(N):
        _acc_manning_discharge += manning_discharge(0.5, 0.5, 0.5, 0.5)
    var _t1_manning_discharge = perf_counter_ns()
    var _ns_manning_discharge = Float64(_t1_manning_discharge - _t0_manning_discharge) / Float64(N)
    print("MOJO_TIMING hydrology::manning_discharge", _ns_manning_discharge, _acc_manning_discharge)
    var _acc_hydraulic_radius: Float64 = 0.0
    var _t0_hydraulic_radius = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_radius += hydraulic_radius(0.5, 0.5)
    var _t1_hydraulic_radius = perf_counter_ns()
    var _ns_hydraulic_radius = Float64(_t1_hydraulic_radius - _t0_hydraulic_radius) / Float64(N)
    print("MOJO_TIMING hydrology::hydraulic_radius", _ns_hydraulic_radius, _acc_hydraulic_radius)
    var _acc_froude_number: Float64 = 0.0
    var _t0_froude_number = perf_counter_ns()
    for _ in range(N):
        _acc_froude_number += froude_number(0.5, 0.5, 0.5)
    var _t1_froude_number = perf_counter_ns()
    var _ns_froude_number = Float64(_t1_froude_number - _t0_froude_number) / Float64(N)
    print("MOJO_TIMING hydrology::froude_number", _ns_froude_number, _acc_froude_number)
    var _acc_reynolds_number_pipe: Float64 = 0.0
    var _t0_reynolds_number_pipe = perf_counter_ns()
    for _ in range(N):
        _acc_reynolds_number_pipe += reynolds_number_pipe(0.5, 0.5, 0.5)
    var _t1_reynolds_number_pipe = perf_counter_ns()
    var _ns_reynolds_number_pipe = Float64(_t1_reynolds_number_pipe - _t0_reynolds_number_pipe) / Float64(N)
    print("MOJO_TIMING hydrology::reynolds_number_pipe", _ns_reynolds_number_pipe, _acc_reynolds_number_pipe)
    var _acc_darcy_weisbach_head_loss: Float64 = 0.0
    var _t0_darcy_weisbach_head_loss = perf_counter_ns()
    for _ in range(N):
        _acc_darcy_weisbach_head_loss += darcy_weisbach_head_loss(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_darcy_weisbach_head_loss = perf_counter_ns()
    var _ns_darcy_weisbach_head_loss = Float64(_t1_darcy_weisbach_head_loss - _t0_darcy_weisbach_head_loss) / Float64(N)
    print("MOJO_TIMING hydrology::darcy_weisbach_head_loss", _ns_darcy_weisbach_head_loss, _acc_darcy_weisbach_head_loss)
    var _acc_rational_method_peak_flow: Float64 = 0.0
    var _t0_rational_method_peak_flow = perf_counter_ns()
    for _ in range(N):
        _acc_rational_method_peak_flow += rational_method_peak_flow(0.5, 0.5, 0.5)
    var _t1_rational_method_peak_flow = perf_counter_ns()
    var _ns_rational_method_peak_flow = Float64(_t1_rational_method_peak_flow - _t0_rational_method_peak_flow) / Float64(N)
    print("MOJO_TIMING hydrology::rational_method_peak_flow", _ns_rational_method_peak_flow, _acc_rational_method_peak_flow)
    var _acc_time_of_concentration_kirpich: Float64 = 0.0
    var _t0_time_of_concentration_kirpich = perf_counter_ns()
    for _ in range(N):
        _acc_time_of_concentration_kirpich += time_of_concentration_kirpich(0.5, 0.5)
    var _t1_time_of_concentration_kirpich = perf_counter_ns()
    var _ns_time_of_concentration_kirpich = Float64(_t1_time_of_concentration_kirpich - _t0_time_of_concentration_kirpich) / Float64(N)
    print("MOJO_TIMING hydrology::time_of_concentration_kirpich", _ns_time_of_concentration_kirpich, _acc_time_of_concentration_kirpich)
    var _acc_curve_number_runoff: Float64 = 0.0
    var _t0_curve_number_runoff = perf_counter_ns()
    for _ in range(N):
        _acc_curve_number_runoff += curve_number_runoff(0.5, 0.5)
    var _t1_curve_number_runoff = perf_counter_ns()
    var _ns_curve_number_runoff = Float64(_t1_curve_number_runoff - _t0_curve_number_runoff) / Float64(N)
    print("MOJO_TIMING hydrology::curve_number_runoff", _ns_curve_number_runoff, _acc_curve_number_runoff)
    var _acc_evapotranspiration_hargreaves: Float64 = 0.0
    var _t0_evapotranspiration_hargreaves = perf_counter_ns()
    for _ in range(N):
        _acc_evapotranspiration_hargreaves += evapotranspiration_hargreaves(0.5, 0.5, 0.5)
    var _t1_evapotranspiration_hargreaves = perf_counter_ns()
    var _ns_evapotranspiration_hargreaves = Float64(_t1_evapotranspiration_hargreaves - _t0_evapotranspiration_hargreaves) / Float64(N)
    print("MOJO_TIMING hydrology::evapotranspiration_hargreaves", _ns_evapotranspiration_hargreaves, _acc_evapotranspiration_hargreaves)
    var _acc_specific_yield: Float64 = 0.0
    var _t0_specific_yield = perf_counter_ns()
    for _ in range(N):
        _acc_specific_yield += specific_yield(0.5, 0.5)
    var _t1_specific_yield = perf_counter_ns()
    var _ns_specific_yield = Float64(_t1_specific_yield - _t0_specific_yield) / Float64(N)
    print("MOJO_TIMING hydrology::specific_yield", _ns_specific_yield, _acc_specific_yield)
    var _acc_darcy_groundwater_velocity: Float64 = 0.0
    var _t0_darcy_groundwater_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_darcy_groundwater_velocity += darcy_groundwater_velocity(0.5, 0.5)
    var _t1_darcy_groundwater_velocity = perf_counter_ns()
    var _ns_darcy_groundwater_velocity = Float64(_t1_darcy_groundwater_velocity - _t0_darcy_groundwater_velocity) / Float64(N)
    print("MOJO_TIMING hydrology::darcy_groundwater_velocity", _ns_darcy_groundwater_velocity, _acc_darcy_groundwater_velocity)
