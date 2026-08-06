"""bench_welding.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from welding import heat_input, heat_input_kj, preheat_carbon_equivalent, cooling_rate_2d, weld_dilution, electrode_consumption, welding_speed_from_deposition, joint_efficiency, throat_thickness_fillet, allowable_shear_fillet, interpass_temperature_max, hydrogen_cracking_risk
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

    var _acc_heat_input: Float64 = 0.0
    var _t0_heat_input = perf_counter_ns()
    for _ in range(N):
        _acc_heat_input += heat_input(0.5, 0.5, 0.5)
    var _t1_heat_input = perf_counter_ns()
    var _ns_heat_input = Float64(_t1_heat_input - _t0_heat_input) / Float64(N)
    print("MOJO_TIMING welding::heat_input", _ns_heat_input, _acc_heat_input)
    var _result_heat_input = heat_input(0.5, 0.5, 0.5)
    var _summary_heat_input = _summary_float64(_result_heat_input)
    print("MOJO_RESULT welding::heat_input", _summary_heat_input)
    var _acc_heat_input_kj: Float64 = 0.0
    var _t0_heat_input_kj = perf_counter_ns()
    for _ in range(N):
        _acc_heat_input_kj += heat_input_kj(0.5, 0.5, 0.5)
    var _t1_heat_input_kj = perf_counter_ns()
    var _ns_heat_input_kj = Float64(_t1_heat_input_kj - _t0_heat_input_kj) / Float64(N)
    print("MOJO_TIMING welding::heat_input_kj", _ns_heat_input_kj, _acc_heat_input_kj)
    var _result_heat_input_kj = heat_input_kj(0.5, 0.5, 0.5)
    var _summary_heat_input_kj = _summary_float64(_result_heat_input_kj)
    print("MOJO_RESULT welding::heat_input_kj", _summary_heat_input_kj)
    var _acc_preheat_carbon_equivalent: Float64 = 0.0
    var _t0_preheat_carbon_equivalent = perf_counter_ns()
    for _ in range(N):
        _acc_preheat_carbon_equivalent += preheat_carbon_equivalent(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_preheat_carbon_equivalent = perf_counter_ns()
    var _ns_preheat_carbon_equivalent = Float64(_t1_preheat_carbon_equivalent - _t0_preheat_carbon_equivalent) / Float64(N)
    print("MOJO_TIMING welding::preheat_carbon_equivalent", _ns_preheat_carbon_equivalent, _acc_preheat_carbon_equivalent)
    var _result_preheat_carbon_equivalent = preheat_carbon_equivalent(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_preheat_carbon_equivalent = _summary_float64(_result_preheat_carbon_equivalent)
    print("MOJO_RESULT welding::preheat_carbon_equivalent", _summary_preheat_carbon_equivalent)
    var _acc_cooling_rate_2d: Float64 = 0.0
    var _t0_cooling_rate_2d = perf_counter_ns()
    for _ in range(N):
        _acc_cooling_rate_2d += cooling_rate_2d(0.5, 0.5, 0.5)
    var _t1_cooling_rate_2d = perf_counter_ns()
    var _ns_cooling_rate_2d = Float64(_t1_cooling_rate_2d - _t0_cooling_rate_2d) / Float64(N)
    print("MOJO_TIMING welding::cooling_rate_2d", _ns_cooling_rate_2d, _acc_cooling_rate_2d)
    var _result_cooling_rate_2d = cooling_rate_2d(0.5, 0.5, 0.5)
    var _summary_cooling_rate_2d = _summary_float64(_result_cooling_rate_2d)
    print("MOJO_RESULT welding::cooling_rate_2d", _summary_cooling_rate_2d)
    var _acc_weld_dilution: Float64 = 0.0
    var _t0_weld_dilution = perf_counter_ns()
    for _ in range(N):
        _acc_weld_dilution += weld_dilution(0.5, 0.5)
    var _t1_weld_dilution = perf_counter_ns()
    var _ns_weld_dilution = Float64(_t1_weld_dilution - _t0_weld_dilution) / Float64(N)
    print("MOJO_TIMING welding::weld_dilution", _ns_weld_dilution, _acc_weld_dilution)
    var _result_weld_dilution = weld_dilution(0.5, 0.5)
    var _summary_weld_dilution = _summary_float64(_result_weld_dilution)
    print("MOJO_RESULT welding::weld_dilution", _summary_weld_dilution)
    var _acc_electrode_consumption: Float64 = 0.0
    var _t0_electrode_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_electrode_consumption += electrode_consumption(0.5, 0.5)
    var _t1_electrode_consumption = perf_counter_ns()
    var _ns_electrode_consumption = Float64(_t1_electrode_consumption - _t0_electrode_consumption) / Float64(N)
    print("MOJO_TIMING welding::electrode_consumption", _ns_electrode_consumption, _acc_electrode_consumption)
    var _result_electrode_consumption = electrode_consumption(0.5, 0.5)
    var _summary_electrode_consumption = _summary_float64(_result_electrode_consumption)
    print("MOJO_RESULT welding::electrode_consumption", _summary_electrode_consumption)
    var _acc_welding_speed_from_deposition: Float64 = 0.0
    var _t0_welding_speed_from_deposition = perf_counter_ns()
    for _ in range(N):
        _acc_welding_speed_from_deposition += welding_speed_from_deposition(0.5, 0.5, 0.5)
    var _t1_welding_speed_from_deposition = perf_counter_ns()
    var _ns_welding_speed_from_deposition = Float64(_t1_welding_speed_from_deposition - _t0_welding_speed_from_deposition) / Float64(N)
    print("MOJO_TIMING welding::welding_speed_from_deposition", _ns_welding_speed_from_deposition, _acc_welding_speed_from_deposition)
    var _result_welding_speed_from_deposition = welding_speed_from_deposition(0.5, 0.5, 0.5)
    var _summary_welding_speed_from_deposition = _summary_float64(_result_welding_speed_from_deposition)
    print("MOJO_RESULT welding::welding_speed_from_deposition", _summary_welding_speed_from_deposition)
    var _acc_joint_efficiency: Float64 = 0.0
    var _t0_joint_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_joint_efficiency += joint_efficiency(0.5, 0.5)
    var _t1_joint_efficiency = perf_counter_ns()
    var _ns_joint_efficiency = Float64(_t1_joint_efficiency - _t0_joint_efficiency) / Float64(N)
    print("MOJO_TIMING welding::joint_efficiency", _ns_joint_efficiency, _acc_joint_efficiency)
    var _result_joint_efficiency = joint_efficiency(0.5, 0.5)
    var _summary_joint_efficiency = _summary_float64(_result_joint_efficiency)
    print("MOJO_RESULT welding::joint_efficiency", _summary_joint_efficiency)
    var _acc_throat_thickness_fillet: Float64 = 0.0
    var _t0_throat_thickness_fillet = perf_counter_ns()
    for _ in range(N):
        _acc_throat_thickness_fillet += throat_thickness_fillet(0.5)
    var _t1_throat_thickness_fillet = perf_counter_ns()
    var _ns_throat_thickness_fillet = Float64(_t1_throat_thickness_fillet - _t0_throat_thickness_fillet) / Float64(N)
    print("MOJO_TIMING welding::throat_thickness_fillet", _ns_throat_thickness_fillet, _acc_throat_thickness_fillet)
    var _result_throat_thickness_fillet = throat_thickness_fillet(0.5)
    var _summary_throat_thickness_fillet = _summary_float64(_result_throat_thickness_fillet)
    print("MOJO_RESULT welding::throat_thickness_fillet", _summary_throat_thickness_fillet)
    var _acc_allowable_shear_fillet: Float64 = 0.0
    var _t0_allowable_shear_fillet = perf_counter_ns()
    for _ in range(N):
        _acc_allowable_shear_fillet += allowable_shear_fillet(0.5, 0.5, 0.5)
    var _t1_allowable_shear_fillet = perf_counter_ns()
    var _ns_allowable_shear_fillet = Float64(_t1_allowable_shear_fillet - _t0_allowable_shear_fillet) / Float64(N)
    print("MOJO_TIMING welding::allowable_shear_fillet", _ns_allowable_shear_fillet, _acc_allowable_shear_fillet)
    var _result_allowable_shear_fillet = allowable_shear_fillet(0.5, 0.5, 0.5)
    var _summary_allowable_shear_fillet = _summary_float64(_result_allowable_shear_fillet)
    print("MOJO_RESULT welding::allowable_shear_fillet", _summary_allowable_shear_fillet)
    var _acc_interpass_temperature_max: Float64 = 0.0
    var _t0_interpass_temperature_max = perf_counter_ns()
    for _ in range(N):
        _acc_interpass_temperature_max += interpass_temperature_max(0.5)
    var _t1_interpass_temperature_max = perf_counter_ns()
    var _ns_interpass_temperature_max = Float64(_t1_interpass_temperature_max - _t0_interpass_temperature_max) / Float64(N)
    print("MOJO_TIMING welding::interpass_temperature_max", _ns_interpass_temperature_max, _acc_interpass_temperature_max)
    var _result_interpass_temperature_max = interpass_temperature_max(0.5)
    var _summary_interpass_temperature_max = _summary_float64(_result_interpass_temperature_max)
    print("MOJO_RESULT welding::interpass_temperature_max", _summary_interpass_temperature_max)
    var _acc_hydrogen_cracking_risk: Float64 = 0.0
    var _t0_hydrogen_cracking_risk = perf_counter_ns()
    for _ in range(N):
        _acc_hydrogen_cracking_risk += hydrogen_cracking_risk(0.5, 0.5, 0.5)
    var _t1_hydrogen_cracking_risk = perf_counter_ns()
    var _ns_hydrogen_cracking_risk = Float64(_t1_hydrogen_cracking_risk - _t0_hydrogen_cracking_risk) / Float64(N)
    print("MOJO_TIMING welding::hydrogen_cracking_risk", _ns_hydrogen_cracking_risk, _acc_hydrogen_cracking_risk)
    var _result_hydrogen_cracking_risk = hydrogen_cracking_risk(0.5, 0.5, 0.5)
    var _summary_hydrogen_cracking_risk = _summary_float64(_result_hydrogen_cracking_risk)
    print("MOJO_RESULT welding::hydrogen_cracking_risk", _summary_hydrogen_cracking_risk)
