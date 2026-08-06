"""bench_bryology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from bryology import sphagnum_water_holding, moss_growth_rate, carbon_accumulation_peatland, bryophyte_desiccation_recovery, nitrogen_deposition_effect, moss_photosynthesis_rate, peat_accumulation_rate, sphagnum_acidity, patch_colonisation_probability, biomass_to_litter_ratio
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

    var _acc_sphagnum_water_holding: Float64 = 0.0
    var _t0_sphagnum_water_holding = perf_counter_ns()
    for _ in range(N):
        _acc_sphagnum_water_holding += sphagnum_water_holding(0.5, 0.5)
    var _t1_sphagnum_water_holding = perf_counter_ns()
    var _ns_sphagnum_water_holding = Float64(_t1_sphagnum_water_holding - _t0_sphagnum_water_holding) / Float64(N)
    print("MOJO_TIMING bryology::sphagnum_water_holding", _ns_sphagnum_water_holding, _acc_sphagnum_water_holding)
    var _result_sphagnum_water_holding = sphagnum_water_holding(0.5, 0.5)
    var _summary_sphagnum_water_holding = _summary_float64(_result_sphagnum_water_holding)
    print("MOJO_RESULT bryology::sphagnum_water_holding", _summary_sphagnum_water_holding)
    var _acc_moss_growth_rate: Float64 = 0.0
    var _t0_moss_growth_rate = perf_counter_ns()
    for _ in range(N):
        _acc_moss_growth_rate += moss_growth_rate(0.5, 0.5, 0.5)
    var _t1_moss_growth_rate = perf_counter_ns()
    var _ns_moss_growth_rate = Float64(_t1_moss_growth_rate - _t0_moss_growth_rate) / Float64(N)
    print("MOJO_TIMING bryology::moss_growth_rate", _ns_moss_growth_rate, _acc_moss_growth_rate)
    var _result_moss_growth_rate = moss_growth_rate(0.5, 0.5, 0.5)
    var _summary_moss_growth_rate = _summary_float64(_result_moss_growth_rate)
    print("MOJO_RESULT bryology::moss_growth_rate", _summary_moss_growth_rate)
    var _acc_carbon_accumulation_peatland: Float64 = 0.0
    var _t0_carbon_accumulation_peatland = perf_counter_ns()
    for _ in range(N):
        _acc_carbon_accumulation_peatland += carbon_accumulation_peatland(0.5, 0.5)
    var _t1_carbon_accumulation_peatland = perf_counter_ns()
    var _ns_carbon_accumulation_peatland = Float64(_t1_carbon_accumulation_peatland - _t0_carbon_accumulation_peatland) / Float64(N)
    print("MOJO_TIMING bryology::carbon_accumulation_peatland", _ns_carbon_accumulation_peatland, _acc_carbon_accumulation_peatland)
    var _result_carbon_accumulation_peatland = carbon_accumulation_peatland(0.5, 0.5)
    var _summary_carbon_accumulation_peatland = _summary_float64(_result_carbon_accumulation_peatland)
    print("MOJO_RESULT bryology::carbon_accumulation_peatland", _summary_carbon_accumulation_peatland)
    var _acc_bryophyte_desiccation_recovery: Float64 = 0.0
    var _t0_bryophyte_desiccation_recovery = perf_counter_ns()
    for _ in range(N):
        _acc_bryophyte_desiccation_recovery += bryophyte_desiccation_recovery(0.5, 0.5, 0.5)
    var _t1_bryophyte_desiccation_recovery = perf_counter_ns()
    var _ns_bryophyte_desiccation_recovery = Float64(_t1_bryophyte_desiccation_recovery - _t0_bryophyte_desiccation_recovery) / Float64(N)
    print("MOJO_TIMING bryology::bryophyte_desiccation_recovery", _ns_bryophyte_desiccation_recovery, _acc_bryophyte_desiccation_recovery)
    var _result_bryophyte_desiccation_recovery = bryophyte_desiccation_recovery(0.5, 0.5, 0.5)
    var _summary_bryophyte_desiccation_recovery = _summary_float64(_result_bryophyte_desiccation_recovery)
    print("MOJO_RESULT bryology::bryophyte_desiccation_recovery", _summary_bryophyte_desiccation_recovery)
    var _acc_nitrogen_deposition_effect: Float64 = 0.0
    var _t0_nitrogen_deposition_effect = perf_counter_ns()
    for _ in range(N):
        _acc_nitrogen_deposition_effect += nitrogen_deposition_effect(0.5, 0.5)
    var _t1_nitrogen_deposition_effect = perf_counter_ns()
    var _ns_nitrogen_deposition_effect = Float64(_t1_nitrogen_deposition_effect - _t0_nitrogen_deposition_effect) / Float64(N)
    print("MOJO_TIMING bryology::nitrogen_deposition_effect", _ns_nitrogen_deposition_effect, _acc_nitrogen_deposition_effect)
    var _result_nitrogen_deposition_effect = nitrogen_deposition_effect(0.5, 0.5)
    var _summary_nitrogen_deposition_effect = _summary_float64(_result_nitrogen_deposition_effect)
    print("MOJO_RESULT bryology::nitrogen_deposition_effect", _summary_nitrogen_deposition_effect)
    var _acc_moss_photosynthesis_rate: Float64 = 0.0
    var _t0_moss_photosynthesis_rate = perf_counter_ns()
    for _ in range(N):
        _acc_moss_photosynthesis_rate += moss_photosynthesis_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_moss_photosynthesis_rate = perf_counter_ns()
    var _ns_moss_photosynthesis_rate = Float64(_t1_moss_photosynthesis_rate - _t0_moss_photosynthesis_rate) / Float64(N)
    print("MOJO_TIMING bryology::moss_photosynthesis_rate", _ns_moss_photosynthesis_rate, _acc_moss_photosynthesis_rate)
    var _result_moss_photosynthesis_rate = moss_photosynthesis_rate(0.5, 0.5, 0.5, 0.5)
    var _summary_moss_photosynthesis_rate = _summary_float64(_result_moss_photosynthesis_rate)
    print("MOJO_RESULT bryology::moss_photosynthesis_rate", _summary_moss_photosynthesis_rate)
    var _acc_peat_accumulation_rate: Float64 = 0.0
    var _t0_peat_accumulation_rate = perf_counter_ns()
    for _ in range(N):
        _acc_peat_accumulation_rate += peat_accumulation_rate(0.5, 0.5)
    var _t1_peat_accumulation_rate = perf_counter_ns()
    var _ns_peat_accumulation_rate = Float64(_t1_peat_accumulation_rate - _t0_peat_accumulation_rate) / Float64(N)
    print("MOJO_TIMING bryology::peat_accumulation_rate", _ns_peat_accumulation_rate, _acc_peat_accumulation_rate)
    var _result_peat_accumulation_rate = peat_accumulation_rate(0.5, 0.5)
    var _summary_peat_accumulation_rate = _summary_float64(_result_peat_accumulation_rate)
    print("MOJO_RESULT bryology::peat_accumulation_rate", _summary_peat_accumulation_rate)
    var _acc_sphagnum_acidity: Float64 = 0.0
    var _t0_sphagnum_acidity = perf_counter_ns()
    for _ in range(N):
        _acc_sphagnum_acidity += sphagnum_acidity(0.5, 0.5)
    var _t1_sphagnum_acidity = perf_counter_ns()
    var _ns_sphagnum_acidity = Float64(_t1_sphagnum_acidity - _t0_sphagnum_acidity) / Float64(N)
    print("MOJO_TIMING bryology::sphagnum_acidity", _ns_sphagnum_acidity, _acc_sphagnum_acidity)
    var _result_sphagnum_acidity = sphagnum_acidity(0.5, 0.5)
    var _summary_sphagnum_acidity = _summary_float64(_result_sphagnum_acidity)
    print("MOJO_RESULT bryology::sphagnum_acidity", _summary_sphagnum_acidity)
    var _acc_patch_colonisation_probability: Float64 = 0.0
    var _t0_patch_colonisation_probability = perf_counter_ns()
    for _ in range(N):
        _acc_patch_colonisation_probability += patch_colonisation_probability(0.5, 0.5, 0.5)
    var _t1_patch_colonisation_probability = perf_counter_ns()
    var _ns_patch_colonisation_probability = Float64(_t1_patch_colonisation_probability - _t0_patch_colonisation_probability) / Float64(N)
    print("MOJO_TIMING bryology::patch_colonisation_probability", _ns_patch_colonisation_probability, _acc_patch_colonisation_probability)
    var _result_patch_colonisation_probability = patch_colonisation_probability(0.5, 0.5, 0.5)
    var _summary_patch_colonisation_probability = _summary_float64(_result_patch_colonisation_probability)
    print("MOJO_RESULT bryology::patch_colonisation_probability", _summary_patch_colonisation_probability)
    var _acc_biomass_to_litter_ratio: Float64 = 0.0
    var _t0_biomass_to_litter_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_biomass_to_litter_ratio += biomass_to_litter_ratio(0.5, 0.5)
    var _t1_biomass_to_litter_ratio = perf_counter_ns()
    var _ns_biomass_to_litter_ratio = Float64(_t1_biomass_to_litter_ratio - _t0_biomass_to_litter_ratio) / Float64(N)
    print("MOJO_TIMING bryology::biomass_to_litter_ratio", _ns_biomass_to_litter_ratio, _acc_biomass_to_litter_ratio)
    var _result_biomass_to_litter_ratio = biomass_to_litter_ratio(0.5, 0.5)
    var _summary_biomass_to_litter_ratio = _summary_float64(_result_biomass_to_litter_ratio)
    print("MOJO_RESULT bryology::biomass_to_litter_ratio", _summary_biomass_to_litter_ratio)
