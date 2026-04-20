"""bench_cryology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cryology import permafrost_thickness, active_layer_depth, ground_ice_content, freeze_thaw_cycles, thermal_conductivity_frozen, ice_wedge_volume, thermokarst_subsidence, permafrost_carbon_release, sea_ice_extent_anomaly, snow_ice_albedo_feedback
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

    var _acc_permafrost_thickness: Float64 = 0.0
    var _t0_permafrost_thickness = perf_counter_ns()
    for _ in range(N):
        _acc_permafrost_thickness += permafrost_thickness(0.5, 0.5)
    var _t1_permafrost_thickness = perf_counter_ns()
    var _ns_permafrost_thickness = Float64(_t1_permafrost_thickness - _t0_permafrost_thickness) / Float64(N)
    print("MOJO_TIMING cryology::permafrost_thickness", _ns_permafrost_thickness, _acc_permafrost_thickness)
    var _acc_active_layer_depth: Float64 = 0.0
    var _t0_active_layer_depth = perf_counter_ns()
    for _ in range(N):
        _acc_active_layer_depth += active_layer_depth(0.5, 0.5, 0.5)
    var _t1_active_layer_depth = perf_counter_ns()
    var _ns_active_layer_depth = Float64(_t1_active_layer_depth - _t0_active_layer_depth) / Float64(N)
    print("MOJO_TIMING cryology::active_layer_depth", _ns_active_layer_depth, _acc_active_layer_depth)
    var _acc_ground_ice_content: Float64 = 0.0
    var _t0_ground_ice_content = perf_counter_ns()
    for _ in range(N):
        _acc_ground_ice_content += ground_ice_content(0.5, 0.5)
    var _t1_ground_ice_content = perf_counter_ns()
    var _ns_ground_ice_content = Float64(_t1_ground_ice_content - _t0_ground_ice_content) / Float64(N)
    print("MOJO_TIMING cryology::ground_ice_content", _ns_ground_ice_content, _acc_ground_ice_content)
    var _acc_freeze_thaw_cycles: Float64 = 0.0
    var _t0_freeze_thaw_cycles = perf_counter_ns()
    for _ in range(N):
        _acc_freeze_thaw_cycles += freeze_thaw_cycles(0.5, 0.5)
    var _t1_freeze_thaw_cycles = perf_counter_ns()
    var _ns_freeze_thaw_cycles = Float64(_t1_freeze_thaw_cycles - _t0_freeze_thaw_cycles) / Float64(N)
    print("MOJO_TIMING cryology::freeze_thaw_cycles", _ns_freeze_thaw_cycles, _acc_freeze_thaw_cycles)
    var _acc_thermal_conductivity_frozen: Float64 = 0.0
    var _t0_thermal_conductivity_frozen = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_conductivity_frozen += thermal_conductivity_frozen(0.5, 0.5, 0.5)
    var _t1_thermal_conductivity_frozen = perf_counter_ns()
    var _ns_thermal_conductivity_frozen = Float64(_t1_thermal_conductivity_frozen - _t0_thermal_conductivity_frozen) / Float64(N)
    print("MOJO_TIMING cryology::thermal_conductivity_frozen", _ns_thermal_conductivity_frozen, _acc_thermal_conductivity_frozen)
    var _acc_ice_wedge_volume: Float64 = 0.0
    var _t0_ice_wedge_volume = perf_counter_ns()
    for _ in range(N):
        _acc_ice_wedge_volume += ice_wedge_volume(0.5, 0.5, 0.5)
    var _t1_ice_wedge_volume = perf_counter_ns()
    var _ns_ice_wedge_volume = Float64(_t1_ice_wedge_volume - _t0_ice_wedge_volume) / Float64(N)
    print("MOJO_TIMING cryology::ice_wedge_volume", _ns_ice_wedge_volume, _acc_ice_wedge_volume)
    var _acc_thermokarst_subsidence: Float64 = 0.0
    var _t0_thermokarst_subsidence = perf_counter_ns()
    for _ in range(N):
        _acc_thermokarst_subsidence += thermokarst_subsidence(0.5, 0.5)
    var _t1_thermokarst_subsidence = perf_counter_ns()
    var _ns_thermokarst_subsidence = Float64(_t1_thermokarst_subsidence - _t0_thermokarst_subsidence) / Float64(N)
    print("MOJO_TIMING cryology::thermokarst_subsidence", _ns_thermokarst_subsidence, _acc_thermokarst_subsidence)
    var _acc_permafrost_carbon_release: Float64 = 0.0
    var _t0_permafrost_carbon_release = perf_counter_ns()
    for _ in range(N):
        _acc_permafrost_carbon_release += permafrost_carbon_release(0.5, 0.5, 0.5)
    var _t1_permafrost_carbon_release = perf_counter_ns()
    var _ns_permafrost_carbon_release = Float64(_t1_permafrost_carbon_release - _t0_permafrost_carbon_release) / Float64(N)
    print("MOJO_TIMING cryology::permafrost_carbon_release", _ns_permafrost_carbon_release, _acc_permafrost_carbon_release)
    var _acc_sea_ice_extent_anomaly: Float64 = 0.0
    var _t0_sea_ice_extent_anomaly = perf_counter_ns()
    for _ in range(N):
        _acc_sea_ice_extent_anomaly += sea_ice_extent_anomaly(0.5, 0.5)
    var _t1_sea_ice_extent_anomaly = perf_counter_ns()
    var _ns_sea_ice_extent_anomaly = Float64(_t1_sea_ice_extent_anomaly - _t0_sea_ice_extent_anomaly) / Float64(N)
    print("MOJO_TIMING cryology::sea_ice_extent_anomaly", _ns_sea_ice_extent_anomaly, _acc_sea_ice_extent_anomaly)
    var _acc_snow_ice_albedo_feedback: Float64 = 0.0
    var _t0_snow_ice_albedo_feedback = perf_counter_ns()
    for _ in range(N):
        _acc_snow_ice_albedo_feedback += snow_ice_albedo_feedback(0.5, 0.5, 0.5)
    var _t1_snow_ice_albedo_feedback = perf_counter_ns()
    var _ns_snow_ice_albedo_feedback = Float64(_t1_snow_ice_albedo_feedback - _t0_snow_ice_albedo_feedback) / Float64(N)
    print("MOJO_TIMING cryology::snow_ice_albedo_feedback", _ns_snow_ice_albedo_feedback, _acc_snow_ice_albedo_feedback)
