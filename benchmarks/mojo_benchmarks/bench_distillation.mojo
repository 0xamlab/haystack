"""bench_distillation.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from distillation import relative_volatility, min_reflux_underwood, actual_reflux, fenske_min_stages, gilliland_stages, mccabe_thiele_operating_line_enriching, mccabe_thiele_operating_line_stripping, boiling_point_elevation, raoults_law_partial_pressure, daltons_law_total_pressure, stage_efficiency, heat_duty_condenser
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

    var _acc_relative_volatility: Float64 = 0.0
    var _t0_relative_volatility = perf_counter_ns()
    for _ in range(N):
        _acc_relative_volatility += relative_volatility(0.5, 0.5)
    var _t1_relative_volatility = perf_counter_ns()
    var _ns_relative_volatility = Float64(_t1_relative_volatility - _t0_relative_volatility) / Float64(N)
    print("MOJO_TIMING distillation::relative_volatility", _ns_relative_volatility, _acc_relative_volatility)
    var _acc_min_reflux_underwood: Float64 = 0.0
    var _t0_min_reflux_underwood = perf_counter_ns()
    for _ in range(N):
        _acc_min_reflux_underwood += min_reflux_underwood(0.5, 0.5, 0.5, 0.5)
    var _t1_min_reflux_underwood = perf_counter_ns()
    var _ns_min_reflux_underwood = Float64(_t1_min_reflux_underwood - _t0_min_reflux_underwood) / Float64(N)
    print("MOJO_TIMING distillation::min_reflux_underwood", _ns_min_reflux_underwood, _acc_min_reflux_underwood)
    var _acc_actual_reflux: Float64 = 0.0
    var _t0_actual_reflux = perf_counter_ns()
    for _ in range(N):
        _acc_actual_reflux += actual_reflux(0.5, 0.5)
    var _t1_actual_reflux = perf_counter_ns()
    var _ns_actual_reflux = Float64(_t1_actual_reflux - _t0_actual_reflux) / Float64(N)
    print("MOJO_TIMING distillation::actual_reflux", _ns_actual_reflux, _acc_actual_reflux)
    var _acc_fenske_min_stages: Float64 = 0.0
    var _t0_fenske_min_stages = perf_counter_ns()
    for _ in range(N):
        _acc_fenske_min_stages += fenske_min_stages(0.5, 0.5, 0.5)
    var _t1_fenske_min_stages = perf_counter_ns()
    var _ns_fenske_min_stages = Float64(_t1_fenske_min_stages - _t0_fenske_min_stages) / Float64(N)
    print("MOJO_TIMING distillation::fenske_min_stages", _ns_fenske_min_stages, _acc_fenske_min_stages)
    var _acc_gilliland_stages: Float64 = 0.0
    var _t0_gilliland_stages = perf_counter_ns()
    for _ in range(N):
        _acc_gilliland_stages += gilliland_stages(0.5, 0.5, 0.5)
    var _t1_gilliland_stages = perf_counter_ns()
    var _ns_gilliland_stages = Float64(_t1_gilliland_stages - _t0_gilliland_stages) / Float64(N)
    print("MOJO_TIMING distillation::gilliland_stages", _ns_gilliland_stages, _acc_gilliland_stages)
    var _acc_mccabe_thiele_operating_line_enriching: Float64 = 0.0
    var _t0_mccabe_thiele_operating_line_enriching = perf_counter_ns()
    for _ in range(N):
        _acc_mccabe_thiele_operating_line_enriching += mccabe_thiele_operating_line_enriching(0.5, 0.5, 0.5)
    var _t1_mccabe_thiele_operating_line_enriching = perf_counter_ns()
    var _ns_mccabe_thiele_operating_line_enriching = Float64(_t1_mccabe_thiele_operating_line_enriching - _t0_mccabe_thiele_operating_line_enriching) / Float64(N)
    print("MOJO_TIMING distillation::mccabe_thiele_operating_line_enriching", _ns_mccabe_thiele_operating_line_enriching, _acc_mccabe_thiele_operating_line_enriching)
    var _acc_mccabe_thiele_operating_line_stripping: Float64 = 0.0
    var _t0_mccabe_thiele_operating_line_stripping = perf_counter_ns()
    for _ in range(N):
        _acc_mccabe_thiele_operating_line_stripping += mccabe_thiele_operating_line_stripping(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_mccabe_thiele_operating_line_stripping = perf_counter_ns()
    var _ns_mccabe_thiele_operating_line_stripping = Float64(_t1_mccabe_thiele_operating_line_stripping - _t0_mccabe_thiele_operating_line_stripping) / Float64(N)
    print("MOJO_TIMING distillation::mccabe_thiele_operating_line_stripping", _ns_mccabe_thiele_operating_line_stripping, _acc_mccabe_thiele_operating_line_stripping)
    var _acc_boiling_point_elevation: Float64 = 0.0
    var _t0_boiling_point_elevation = perf_counter_ns()
    for _ in range(N):
        _acc_boiling_point_elevation += boiling_point_elevation(0.5, 0.5)
    var _t1_boiling_point_elevation = perf_counter_ns()
    var _ns_boiling_point_elevation = Float64(_t1_boiling_point_elevation - _t0_boiling_point_elevation) / Float64(N)
    print("MOJO_TIMING distillation::boiling_point_elevation", _ns_boiling_point_elevation, _acc_boiling_point_elevation)
    var _acc_raoults_law_partial_pressure: Float64 = 0.0
    var _t0_raoults_law_partial_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_raoults_law_partial_pressure += raoults_law_partial_pressure(0.5, 0.5)
    var _t1_raoults_law_partial_pressure = perf_counter_ns()
    var _ns_raoults_law_partial_pressure = Float64(_t1_raoults_law_partial_pressure - _t0_raoults_law_partial_pressure) / Float64(N)
    print("MOJO_TIMING distillation::raoults_law_partial_pressure", _ns_raoults_law_partial_pressure, _acc_raoults_law_partial_pressure)
    var _acc_daltons_law_total_pressure: Float64 = 0.0
    var _t0_daltons_law_total_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_daltons_law_total_pressure += daltons_law_total_pressure(0.5, 0.5)
    var _t1_daltons_law_total_pressure = perf_counter_ns()
    var _ns_daltons_law_total_pressure = Float64(_t1_daltons_law_total_pressure - _t0_daltons_law_total_pressure) / Float64(N)
    print("MOJO_TIMING distillation::daltons_law_total_pressure", _ns_daltons_law_total_pressure, _acc_daltons_law_total_pressure)
    var _acc_stage_efficiency: Float64 = 0.0
    var _t0_stage_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_stage_efficiency += stage_efficiency(0.5, 0.5, 0.5)
    var _t1_stage_efficiency = perf_counter_ns()
    var _ns_stage_efficiency = Float64(_t1_stage_efficiency - _t0_stage_efficiency) / Float64(N)
    print("MOJO_TIMING distillation::stage_efficiency", _ns_stage_efficiency, _acc_stage_efficiency)
    var _acc_heat_duty_condenser: Float64 = 0.0
    var _t0_heat_duty_condenser = perf_counter_ns()
    for _ in range(N):
        _acc_heat_duty_condenser += heat_duty_condenser(0.5, 0.5)
    var _t1_heat_duty_condenser = perf_counter_ns()
    var _ns_heat_duty_condenser = Float64(_t1_heat_duty_condenser - _t0_heat_duty_condenser) / Float64(N)
    print("MOJO_TIMING distillation::heat_duty_condenser", _ns_heat_duty_condenser, _acc_heat_duty_condenser)
