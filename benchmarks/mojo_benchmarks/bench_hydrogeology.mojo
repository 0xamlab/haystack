"""bench_hydrogeology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hydrogeology import darcy_velocity, transmissivity, storativity, theis_drawdown, dupuit_discharge, hydraulic_gradient, specific_yield, capillary_rise_height, leakance_factor, groundwater_age_mixing
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

    var _acc_darcy_velocity: Float64 = 0.0
    var _t0_darcy_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_darcy_velocity += darcy_velocity(0.5, 0.5)
    var _t1_darcy_velocity = perf_counter_ns()
    var _ns_darcy_velocity = Float64(_t1_darcy_velocity - _t0_darcy_velocity) / Float64(N)
    print("MOJO_TIMING hydrogeology::darcy_velocity", _ns_darcy_velocity, _acc_darcy_velocity)
    var _acc_transmissivity: Float64 = 0.0
    var _t0_transmissivity = perf_counter_ns()
    for _ in range(N):
        _acc_transmissivity += transmissivity(0.5, 0.5)
    var _t1_transmissivity = perf_counter_ns()
    var _ns_transmissivity = Float64(_t1_transmissivity - _t0_transmissivity) / Float64(N)
    print("MOJO_TIMING hydrogeology::transmissivity", _ns_transmissivity, _acc_transmissivity)
    var _acc_storativity: Float64 = 0.0
    var _t0_storativity = perf_counter_ns()
    for _ in range(N):
        _acc_storativity += storativity(0.5, 0.5)
    var _t1_storativity = perf_counter_ns()
    var _ns_storativity = Float64(_t1_storativity - _t0_storativity) / Float64(N)
    print("MOJO_TIMING hydrogeology::storativity", _ns_storativity, _acc_storativity)
    var _acc_theis_drawdown: Float64 = 0.0
    var _t0_theis_drawdown = perf_counter_ns()
    for _ in range(N):
        _acc_theis_drawdown += theis_drawdown(0.5, 0.5, 0.5)
    var _t1_theis_drawdown = perf_counter_ns()
    var _ns_theis_drawdown = Float64(_t1_theis_drawdown - _t0_theis_drawdown) / Float64(N)
    print("MOJO_TIMING hydrogeology::theis_drawdown", _ns_theis_drawdown, _acc_theis_drawdown)
    var _acc_dupuit_discharge: Float64 = 0.0
    var _t0_dupuit_discharge = perf_counter_ns()
    for _ in range(N):
        _acc_dupuit_discharge += dupuit_discharge(0.5, 0.5, 0.5, 0.5)
    var _t1_dupuit_discharge = perf_counter_ns()
    var _ns_dupuit_discharge = Float64(_t1_dupuit_discharge - _t0_dupuit_discharge) / Float64(N)
    print("MOJO_TIMING hydrogeology::dupuit_discharge", _ns_dupuit_discharge, _acc_dupuit_discharge)
    var _acc_hydraulic_gradient: Float64 = 0.0
    var _t0_hydraulic_gradient = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_gradient += hydraulic_gradient(0.5, 0.5)
    var _t1_hydraulic_gradient = perf_counter_ns()
    var _ns_hydraulic_gradient = Float64(_t1_hydraulic_gradient - _t0_hydraulic_gradient) / Float64(N)
    print("MOJO_TIMING hydrogeology::hydraulic_gradient", _ns_hydraulic_gradient, _acc_hydraulic_gradient)
    var _acc_specific_yield: Float64 = 0.0
    var _t0_specific_yield = perf_counter_ns()
    for _ in range(N):
        _acc_specific_yield += specific_yield(0.5, 0.5)
    var _t1_specific_yield = perf_counter_ns()
    var _ns_specific_yield = Float64(_t1_specific_yield - _t0_specific_yield) / Float64(N)
    print("MOJO_TIMING hydrogeology::specific_yield", _ns_specific_yield, _acc_specific_yield)
    var _acc_capillary_rise_height: Float64 = 0.0
    var _t0_capillary_rise_height = perf_counter_ns()
    for _ in range(N):
        _acc_capillary_rise_height += capillary_rise_height(0.5, 0.5, 0.5, 0.5)
    var _t1_capillary_rise_height = perf_counter_ns()
    var _ns_capillary_rise_height = Float64(_t1_capillary_rise_height - _t0_capillary_rise_height) / Float64(N)
    print("MOJO_TIMING hydrogeology::capillary_rise_height", _ns_capillary_rise_height, _acc_capillary_rise_height)
    var _acc_leakance_factor: Float64 = 0.0
    var _t0_leakance_factor = perf_counter_ns()
    for _ in range(N):
        _acc_leakance_factor += leakance_factor(0.5, 0.5, 0.5)
    var _t1_leakance_factor = perf_counter_ns()
    var _ns_leakance_factor = Float64(_t1_leakance_factor - _t0_leakance_factor) / Float64(N)
    print("MOJO_TIMING hydrogeology::leakance_factor", _ns_leakance_factor, _acc_leakance_factor)
    var _acc_groundwater_age_mixing: Float64 = 0.0
    var _t0_groundwater_age_mixing = perf_counter_ns()
    for _ in range(N):
        _acc_groundwater_age_mixing += groundwater_age_mixing(0.5, 0.5, 0.5)
    var _t1_groundwater_age_mixing = perf_counter_ns()
    var _ns_groundwater_age_mixing = Float64(_t1_groundwater_age_mixing - _t0_groundwater_age_mixing) / Float64(N)
    print("MOJO_TIMING hydrogeology::groundwater_age_mixing", _ns_groundwater_age_mixing, _acc_groundwater_age_mixing)
