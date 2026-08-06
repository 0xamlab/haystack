"""bench_limnology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from limnology import lake_volume_ellipsoid, hydraulic_retention_time, thermal_stratification_index, secchi_depth_estimate, trophic_state_index, phosphorus_loading, oxygen_saturation, attenuation_coefficient, lake_flushing_rate, nitrogen_fixation_rate
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

    var _acc_lake_volume_ellipsoid: Float64 = 0.0
    var _t0_lake_volume_ellipsoid = perf_counter_ns()
    for _ in range(N):
        _acc_lake_volume_ellipsoid += lake_volume_ellipsoid(0.5, 0.5, 0.5)
    var _t1_lake_volume_ellipsoid = perf_counter_ns()
    var _ns_lake_volume_ellipsoid = Float64(_t1_lake_volume_ellipsoid - _t0_lake_volume_ellipsoid) / Float64(N)
    print("MOJO_TIMING limnology::lake_volume_ellipsoid", _ns_lake_volume_ellipsoid, _acc_lake_volume_ellipsoid)
    var _result_lake_volume_ellipsoid = lake_volume_ellipsoid(0.5, 0.5, 0.5)
    var _summary_lake_volume_ellipsoid = _summary_float64(_result_lake_volume_ellipsoid)
    print("MOJO_RESULT limnology::lake_volume_ellipsoid", _summary_lake_volume_ellipsoid)
    var _acc_hydraulic_retention_time: Float64 = 0.0
    var _t0_hydraulic_retention_time = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_retention_time += hydraulic_retention_time(0.5, 0.5)
    var _t1_hydraulic_retention_time = perf_counter_ns()
    var _ns_hydraulic_retention_time = Float64(_t1_hydraulic_retention_time - _t0_hydraulic_retention_time) / Float64(N)
    print("MOJO_TIMING limnology::hydraulic_retention_time", _ns_hydraulic_retention_time, _acc_hydraulic_retention_time)
    var _result_hydraulic_retention_time = hydraulic_retention_time(0.5, 0.5)
    var _summary_hydraulic_retention_time = _summary_float64(_result_hydraulic_retention_time)
    print("MOJO_RESULT limnology::hydraulic_retention_time", _summary_hydraulic_retention_time)
    var _acc_thermal_stratification_index: Float64 = 0.0
    var _t0_thermal_stratification_index = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_stratification_index += thermal_stratification_index(0.5, 0.5, 0.5)
    var _t1_thermal_stratification_index = perf_counter_ns()
    var _ns_thermal_stratification_index = Float64(_t1_thermal_stratification_index - _t0_thermal_stratification_index) / Float64(N)
    print("MOJO_TIMING limnology::thermal_stratification_index", _ns_thermal_stratification_index, _acc_thermal_stratification_index)
    var _result_thermal_stratification_index = thermal_stratification_index(0.5, 0.5, 0.5)
    var _summary_thermal_stratification_index = _summary_float64(_result_thermal_stratification_index)
    print("MOJO_RESULT limnology::thermal_stratification_index", _summary_thermal_stratification_index)
    var _acc_secchi_depth_estimate: Float64 = 0.0
    var _t0_secchi_depth_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_secchi_depth_estimate += secchi_depth_estimate(0.5)
    var _t1_secchi_depth_estimate = perf_counter_ns()
    var _ns_secchi_depth_estimate = Float64(_t1_secchi_depth_estimate - _t0_secchi_depth_estimate) / Float64(N)
    print("MOJO_TIMING limnology::secchi_depth_estimate", _ns_secchi_depth_estimate, _acc_secchi_depth_estimate)
    var _result_secchi_depth_estimate = secchi_depth_estimate(0.5)
    var _summary_secchi_depth_estimate = _summary_float64(_result_secchi_depth_estimate)
    print("MOJO_RESULT limnology::secchi_depth_estimate", _summary_secchi_depth_estimate)
    var _acc_trophic_state_index: Float64 = 0.0
    var _t0_trophic_state_index = perf_counter_ns()
    for _ in range(N):
        _acc_trophic_state_index += trophic_state_index(0.5)
    var _t1_trophic_state_index = perf_counter_ns()
    var _ns_trophic_state_index = Float64(_t1_trophic_state_index - _t0_trophic_state_index) / Float64(N)
    print("MOJO_TIMING limnology::trophic_state_index", _ns_trophic_state_index, _acc_trophic_state_index)
    var _result_trophic_state_index = trophic_state_index(0.5)
    var _summary_trophic_state_index = _summary_float64(_result_trophic_state_index)
    print("MOJO_RESULT limnology::trophic_state_index", _summary_trophic_state_index)
    var _acc_phosphorus_loading: Float64 = 0.0
    var _t0_phosphorus_loading = perf_counter_ns()
    for _ in range(N):
        _acc_phosphorus_loading += phosphorus_loading(0.5, 0.5)
    var _t1_phosphorus_loading = perf_counter_ns()
    var _ns_phosphorus_loading = Float64(_t1_phosphorus_loading - _t0_phosphorus_loading) / Float64(N)
    print("MOJO_TIMING limnology::phosphorus_loading", _ns_phosphorus_loading, _acc_phosphorus_loading)
    var _result_phosphorus_loading = phosphorus_loading(0.5, 0.5)
    var _summary_phosphorus_loading = _summary_float64(_result_phosphorus_loading)
    print("MOJO_RESULT limnology::phosphorus_loading", _summary_phosphorus_loading)
    var _acc_oxygen_saturation: Float64 = 0.0
    var _t0_oxygen_saturation = perf_counter_ns()
    for _ in range(N):
        _acc_oxygen_saturation += oxygen_saturation(0.5, 0.5)
    var _t1_oxygen_saturation = perf_counter_ns()
    var _ns_oxygen_saturation = Float64(_t1_oxygen_saturation - _t0_oxygen_saturation) / Float64(N)
    print("MOJO_TIMING limnology::oxygen_saturation", _ns_oxygen_saturation, _acc_oxygen_saturation)
    var _result_oxygen_saturation = oxygen_saturation(0.5, 0.5)
    var _summary_oxygen_saturation = _summary_float64(_result_oxygen_saturation)
    print("MOJO_RESULT limnology::oxygen_saturation", _summary_oxygen_saturation)
    var _acc_attenuation_coefficient: Float64 = 0.0
    var _t0_attenuation_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_attenuation_coefficient += attenuation_coefficient(0.5)
    var _t1_attenuation_coefficient = perf_counter_ns()
    var _ns_attenuation_coefficient = Float64(_t1_attenuation_coefficient - _t0_attenuation_coefficient) / Float64(N)
    print("MOJO_TIMING limnology::attenuation_coefficient", _ns_attenuation_coefficient, _acc_attenuation_coefficient)
    var _result_attenuation_coefficient = attenuation_coefficient(0.5)
    var _summary_attenuation_coefficient = _summary_float64(_result_attenuation_coefficient)
    print("MOJO_RESULT limnology::attenuation_coefficient", _summary_attenuation_coefficient)
    var _acc_lake_flushing_rate: Float64 = 0.0
    var _t0_lake_flushing_rate = perf_counter_ns()
    for _ in range(N):
        _acc_lake_flushing_rate += lake_flushing_rate(0.5, 0.5)
    var _t1_lake_flushing_rate = perf_counter_ns()
    var _ns_lake_flushing_rate = Float64(_t1_lake_flushing_rate - _t0_lake_flushing_rate) / Float64(N)
    print("MOJO_TIMING limnology::lake_flushing_rate", _ns_lake_flushing_rate, _acc_lake_flushing_rate)
    var _result_lake_flushing_rate = lake_flushing_rate(0.5, 0.5)
    var _summary_lake_flushing_rate = _summary_float64(_result_lake_flushing_rate)
    print("MOJO_RESULT limnology::lake_flushing_rate", _summary_lake_flushing_rate)
    var _acc_nitrogen_fixation_rate: Float64 = 0.0
    var _t0_nitrogen_fixation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_nitrogen_fixation_rate += nitrogen_fixation_rate(0.5, 0.5)
    var _t1_nitrogen_fixation_rate = perf_counter_ns()
    var _ns_nitrogen_fixation_rate = Float64(_t1_nitrogen_fixation_rate - _t0_nitrogen_fixation_rate) / Float64(N)
    print("MOJO_TIMING limnology::nitrogen_fixation_rate", _ns_nitrogen_fixation_rate, _acc_nitrogen_fixation_rate)
    var _result_nitrogen_fixation_rate = nitrogen_fixation_rate(0.5, 0.5)
    var _summary_nitrogen_fixation_rate = _summary_float64(_result_nitrogen_fixation_rate)
    print("MOJO_RESULT limnology::nitrogen_fixation_rate", _summary_nitrogen_fixation_rate)
