"""bench_horticulture.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from horticulture import photosynthesis_rate, crop_growth_rate, net_assimilation_rate, specific_leaf_area, transplant_shock_index, fertigation_dose, vpd_plant, chilling_requirement, pruning_efficiency, rooting_hormone_index
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

    var _acc_photosynthesis_rate: Float64 = 0.0
    var _t0_photosynthesis_rate = perf_counter_ns()
    for _ in range(N):
        _acc_photosynthesis_rate += photosynthesis_rate(0.5, 0.5, 0.5)
    var _t1_photosynthesis_rate = perf_counter_ns()
    var _ns_photosynthesis_rate = Float64(_t1_photosynthesis_rate - _t0_photosynthesis_rate) / Float64(N)
    print("MOJO_TIMING horticulture::photosynthesis_rate", _ns_photosynthesis_rate, _acc_photosynthesis_rate)
    var _result_photosynthesis_rate = photosynthesis_rate(0.5, 0.5, 0.5)
    var _summary_photosynthesis_rate = _summary_float64(_result_photosynthesis_rate)
    print("MOJO_RESULT horticulture::photosynthesis_rate", _summary_photosynthesis_rate)
    var _acc_crop_growth_rate: Float64 = 0.0
    var _t0_crop_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_crop_growth_rate += crop_growth_rate(0.5, 0.5)
    var _t1_crop_growth_rate = perf_counter_ns()
    var _ns_crop_growth_rate = Float64(_t1_crop_growth_rate - _t0_crop_growth_rate) / Float64(N)
    print("MOJO_TIMING horticulture::crop_growth_rate", _ns_crop_growth_rate, _acc_crop_growth_rate)
    var _result_crop_growth_rate = crop_growth_rate(0.5, 0.5)
    var _summary_crop_growth_rate = _summary_float64(_result_crop_growth_rate)
    print("MOJO_RESULT horticulture::crop_growth_rate", _summary_crop_growth_rate)
    var _acc_net_assimilation_rate: Float64 = 0.0
    var _t0_net_assimilation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_net_assimilation_rate += net_assimilation_rate(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_net_assimilation_rate = perf_counter_ns()
    var _ns_net_assimilation_rate = Float64(_t1_net_assimilation_rate - _t0_net_assimilation_rate) / Float64(N)
    print("MOJO_TIMING horticulture::net_assimilation_rate", _ns_net_assimilation_rate, _acc_net_assimilation_rate)
    var _result_net_assimilation_rate = net_assimilation_rate(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_net_assimilation_rate = _summary_float64(_result_net_assimilation_rate)
    print("MOJO_RESULT horticulture::net_assimilation_rate", _summary_net_assimilation_rate)
    var _acc_specific_leaf_area: Float64 = 0.0
    var _t0_specific_leaf_area = perf_counter_ns()
    for _ in range(N):
        _acc_specific_leaf_area += specific_leaf_area(0.5, 0.5)
    var _t1_specific_leaf_area = perf_counter_ns()
    var _ns_specific_leaf_area = Float64(_t1_specific_leaf_area - _t0_specific_leaf_area) / Float64(N)
    print("MOJO_TIMING horticulture::specific_leaf_area", _ns_specific_leaf_area, _acc_specific_leaf_area)
    var _result_specific_leaf_area = specific_leaf_area(0.5, 0.5)
    var _summary_specific_leaf_area = _summary_float64(_result_specific_leaf_area)
    print("MOJO_RESULT horticulture::specific_leaf_area", _summary_specific_leaf_area)
    var _acc_transplant_shock_index: Float64 = 0.0
    var _t0_transplant_shock_index = perf_counter_ns()
    for _ in range(N):
        _acc_transplant_shock_index += transplant_shock_index(0.5, 0.5)
    var _t1_transplant_shock_index = perf_counter_ns()
    var _ns_transplant_shock_index = Float64(_t1_transplant_shock_index - _t0_transplant_shock_index) / Float64(N)
    print("MOJO_TIMING horticulture::transplant_shock_index", _ns_transplant_shock_index, _acc_transplant_shock_index)
    var _result_transplant_shock_index = transplant_shock_index(0.5, 0.5)
    var _summary_transplant_shock_index = _summary_float64(_result_transplant_shock_index)
    print("MOJO_RESULT horticulture::transplant_shock_index", _summary_transplant_shock_index)
    var _acc_fertigation_dose: Float64 = 0.0
    var _t0_fertigation_dose = perf_counter_ns()
    for _ in range(N):
        _acc_fertigation_dose += fertigation_dose(0.5, 0.5, 0.5)
    var _t1_fertigation_dose = perf_counter_ns()
    var _ns_fertigation_dose = Float64(_t1_fertigation_dose - _t0_fertigation_dose) / Float64(N)
    print("MOJO_TIMING horticulture::fertigation_dose", _ns_fertigation_dose, _acc_fertigation_dose)
    var _result_fertigation_dose = fertigation_dose(0.5, 0.5, 0.5)
    var _summary_fertigation_dose = _summary_float64(_result_fertigation_dose)
    print("MOJO_RESULT horticulture::fertigation_dose", _summary_fertigation_dose)
    var _acc_vpd_plant: Float64 = 0.0
    var _t0_vpd_plant = perf_counter_ns()
    for _ in range(N):
        _acc_vpd_plant += vpd_plant(0.5, 0.5, 0.5)
    var _t1_vpd_plant = perf_counter_ns()
    var _ns_vpd_plant = Float64(_t1_vpd_plant - _t0_vpd_plant) / Float64(N)
    print("MOJO_TIMING horticulture::vpd_plant", _ns_vpd_plant, _acc_vpd_plant)
    var _result_vpd_plant = vpd_plant(0.5, 0.5, 0.5)
    var _summary_vpd_plant = _summary_float64(_result_vpd_plant)
    print("MOJO_RESULT horticulture::vpd_plant", _summary_vpd_plant)
    var _acc_chilling_requirement: Float64 = 0.0
    var _t0_chilling_requirement = perf_counter_ns()
    for _ in range(N):
        _acc_chilling_requirement += chilling_requirement(0.5, 0.5, 0.5)
    var _t1_chilling_requirement = perf_counter_ns()
    var _ns_chilling_requirement = Float64(_t1_chilling_requirement - _t0_chilling_requirement) / Float64(N)
    print("MOJO_TIMING horticulture::chilling_requirement", _ns_chilling_requirement, _acc_chilling_requirement)
    var _result_chilling_requirement = chilling_requirement(0.5, 0.5, 0.5)
    var _summary_chilling_requirement = _summary_float64(_result_chilling_requirement)
    print("MOJO_RESULT horticulture::chilling_requirement", _summary_chilling_requirement)
    var _acc_pruning_efficiency: Float64 = 0.0
    var _t0_pruning_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_pruning_efficiency += pruning_efficiency(0.5, 0.5)
    var _t1_pruning_efficiency = perf_counter_ns()
    var _ns_pruning_efficiency = Float64(_t1_pruning_efficiency - _t0_pruning_efficiency) / Float64(N)
    print("MOJO_TIMING horticulture::pruning_efficiency", _ns_pruning_efficiency, _acc_pruning_efficiency)
    var _result_pruning_efficiency = pruning_efficiency(0.5, 0.5)
    var _summary_pruning_efficiency = _summary_float64(_result_pruning_efficiency)
    print("MOJO_RESULT horticulture::pruning_efficiency", _summary_pruning_efficiency)
    var _acc_rooting_hormone_index: Float64 = 0.0
    var _t0_rooting_hormone_index = perf_counter_ns()
    for _ in range(N):
        _acc_rooting_hormone_index += rooting_hormone_index(0.5, 0.5)
    var _t1_rooting_hormone_index = perf_counter_ns()
    var _ns_rooting_hormone_index = Float64(_t1_rooting_hormone_index - _t0_rooting_hormone_index) / Float64(N)
    print("MOJO_TIMING horticulture::rooting_hormone_index", _ns_rooting_hormone_index, _acc_rooting_hormone_index)
    var _result_rooting_hormone_index = rooting_hormone_index(0.5, 0.5)
    var _summary_rooting_hormone_index = _summary_float64(_result_rooting_hormone_index)
    print("MOJO_RESULT horticulture::rooting_hormone_index", _summary_rooting_hormone_index)
