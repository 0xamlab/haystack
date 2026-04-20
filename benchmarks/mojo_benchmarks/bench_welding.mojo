"""bench_welding.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from welding import heat_input, heat_input_kj, preheat_carbon_equivalent, cooling_rate_2d, weld_dilution, electrode_consumption, welding_speed_from_deposition, joint_efficiency, throat_thickness_fillet, allowable_shear_fillet, interpass_temperature_max, hydrogen_cracking_risk
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

    var _acc_heat_input: Float64 = 0.0
    var _t0_heat_input = perf_counter_ns()
    for _ in range(N):
        _acc_heat_input += heat_input(0.5, 0.5, 0.5)
    var _t1_heat_input = perf_counter_ns()
    var _ns_heat_input = Float64(_t1_heat_input - _t0_heat_input) / Float64(N)
    print("MOJO_TIMING welding::heat_input", _ns_heat_input, _acc_heat_input)
    var _acc_heat_input_kj: Float64 = 0.0
    var _t0_heat_input_kj = perf_counter_ns()
    for _ in range(N):
        _acc_heat_input_kj += heat_input_kj(0.5, 0.5, 0.5)
    var _t1_heat_input_kj = perf_counter_ns()
    var _ns_heat_input_kj = Float64(_t1_heat_input_kj - _t0_heat_input_kj) / Float64(N)
    print("MOJO_TIMING welding::heat_input_kj", _ns_heat_input_kj, _acc_heat_input_kj)
    var _acc_preheat_carbon_equivalent: Float64 = 0.0
    var _t0_preheat_carbon_equivalent = perf_counter_ns()
    for _ in range(N):
        _acc_preheat_carbon_equivalent += preheat_carbon_equivalent(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_preheat_carbon_equivalent = perf_counter_ns()
    var _ns_preheat_carbon_equivalent = Float64(_t1_preheat_carbon_equivalent - _t0_preheat_carbon_equivalent) / Float64(N)
    print("MOJO_TIMING welding::preheat_carbon_equivalent", _ns_preheat_carbon_equivalent, _acc_preheat_carbon_equivalent)
    var _acc_cooling_rate_2d: Float64 = 0.0
    var _t0_cooling_rate_2d = perf_counter_ns()
    for _ in range(N):
        _acc_cooling_rate_2d += cooling_rate_2d(0.5, 0.5, 0.5)
    var _t1_cooling_rate_2d = perf_counter_ns()
    var _ns_cooling_rate_2d = Float64(_t1_cooling_rate_2d - _t0_cooling_rate_2d) / Float64(N)
    print("MOJO_TIMING welding::cooling_rate_2d", _ns_cooling_rate_2d, _acc_cooling_rate_2d)
    var _acc_weld_dilution: Float64 = 0.0
    var _t0_weld_dilution = perf_counter_ns()
    for _ in range(N):
        _acc_weld_dilution += weld_dilution(0.5, 0.5)
    var _t1_weld_dilution = perf_counter_ns()
    var _ns_weld_dilution = Float64(_t1_weld_dilution - _t0_weld_dilution) / Float64(N)
    print("MOJO_TIMING welding::weld_dilution", _ns_weld_dilution, _acc_weld_dilution)
    var _acc_electrode_consumption: Float64 = 0.0
    var _t0_electrode_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_electrode_consumption += electrode_consumption(0.5, 0.5)
    var _t1_electrode_consumption = perf_counter_ns()
    var _ns_electrode_consumption = Float64(_t1_electrode_consumption - _t0_electrode_consumption) / Float64(N)
    print("MOJO_TIMING welding::electrode_consumption", _ns_electrode_consumption, _acc_electrode_consumption)
    var _acc_welding_speed_from_deposition: Float64 = 0.0
    var _t0_welding_speed_from_deposition = perf_counter_ns()
    for _ in range(N):
        _acc_welding_speed_from_deposition += welding_speed_from_deposition(0.5, 0.5, 0.5)
    var _t1_welding_speed_from_deposition = perf_counter_ns()
    var _ns_welding_speed_from_deposition = Float64(_t1_welding_speed_from_deposition - _t0_welding_speed_from_deposition) / Float64(N)
    print("MOJO_TIMING welding::welding_speed_from_deposition", _ns_welding_speed_from_deposition, _acc_welding_speed_from_deposition)
    var _acc_joint_efficiency: Float64 = 0.0
    var _t0_joint_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_joint_efficiency += joint_efficiency(0.5, 0.5)
    var _t1_joint_efficiency = perf_counter_ns()
    var _ns_joint_efficiency = Float64(_t1_joint_efficiency - _t0_joint_efficiency) / Float64(N)
    print("MOJO_TIMING welding::joint_efficiency", _ns_joint_efficiency, _acc_joint_efficiency)
    var _acc_throat_thickness_fillet: Float64 = 0.0
    var _t0_throat_thickness_fillet = perf_counter_ns()
    for _ in range(N):
        _acc_throat_thickness_fillet += throat_thickness_fillet(0.5)
    var _t1_throat_thickness_fillet = perf_counter_ns()
    var _ns_throat_thickness_fillet = Float64(_t1_throat_thickness_fillet - _t0_throat_thickness_fillet) / Float64(N)
    print("MOJO_TIMING welding::throat_thickness_fillet", _ns_throat_thickness_fillet, _acc_throat_thickness_fillet)
    var _acc_allowable_shear_fillet: Float64 = 0.0
    var _t0_allowable_shear_fillet = perf_counter_ns()
    for _ in range(N):
        _acc_allowable_shear_fillet += allowable_shear_fillet(0.5, 0.5, 0.5)
    var _t1_allowable_shear_fillet = perf_counter_ns()
    var _ns_allowable_shear_fillet = Float64(_t1_allowable_shear_fillet - _t0_allowable_shear_fillet) / Float64(N)
    print("MOJO_TIMING welding::allowable_shear_fillet", _ns_allowable_shear_fillet, _acc_allowable_shear_fillet)
    var _acc_interpass_temperature_max: Float64 = 0.0
    var _t0_interpass_temperature_max = perf_counter_ns()
    for _ in range(N):
        _acc_interpass_temperature_max += interpass_temperature_max(0.5)
    var _t1_interpass_temperature_max = perf_counter_ns()
    var _ns_interpass_temperature_max = Float64(_t1_interpass_temperature_max - _t0_interpass_temperature_max) / Float64(N)
    print("MOJO_TIMING welding::interpass_temperature_max", _ns_interpass_temperature_max, _acc_interpass_temperature_max)
    var _acc_hydrogen_cracking_risk: Float64 = 0.0
    var _t0_hydrogen_cracking_risk = perf_counter_ns()
    for _ in range(N):
        _acc_hydrogen_cracking_risk += hydrogen_cracking_risk(0.5, 0.5, 0.5)
    var _t1_hydrogen_cracking_risk = perf_counter_ns()
    var _ns_hydrogen_cracking_risk = Float64(_t1_hydrogen_cracking_risk - _t0_hydrogen_cracking_risk) / Float64(N)
    print("MOJO_TIMING welding::hydrogen_cracking_risk", _ns_hydrogen_cracking_risk, _acc_hydrogen_cracking_risk)
