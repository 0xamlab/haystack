"""bench_neuropharmacology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from neuropharmacology import receptor_occupancy_brain, blood_brain_barrier_efflux, receptor_binding_ki, synapse_neurotransmitter_level, bbb_penetration_ratio, cns_drug_exposure, d2_receptor_occupancy, minimal_effective_dose_cns, cns_side_effect_threshold, neuronal_firing_modulation
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

    var _acc_receptor_occupancy_brain: Float64 = 0.0
    var _t0_receptor_occupancy_brain = perf_counter_ns()
    for _ in range(N):
        _acc_receptor_occupancy_brain += receptor_occupancy_brain(0.5, 0.5, 0.5)
    var _t1_receptor_occupancy_brain = perf_counter_ns()
    var _ns_receptor_occupancy_brain = Float64(_t1_receptor_occupancy_brain - _t0_receptor_occupancy_brain) / Float64(N)
    print("MOJO_TIMING neuropharmacology::receptor_occupancy_brain", _ns_receptor_occupancy_brain, _acc_receptor_occupancy_brain)
    var _result_receptor_occupancy_brain = receptor_occupancy_brain(0.5, 0.5, 0.5)
    var _summary_receptor_occupancy_brain = _summary_float64(_result_receptor_occupancy_brain)
    print("MOJO_RESULT neuropharmacology::receptor_occupancy_brain", _summary_receptor_occupancy_brain)
    var _acc_blood_brain_barrier_efflux: Float64 = 0.0
    var _t0_blood_brain_barrier_efflux = perf_counter_ns()
    for _ in range(N):
        _acc_blood_brain_barrier_efflux += blood_brain_barrier_efflux(0.5, 0.5)
    var _t1_blood_brain_barrier_efflux = perf_counter_ns()
    var _ns_blood_brain_barrier_efflux = Float64(_t1_blood_brain_barrier_efflux - _t0_blood_brain_barrier_efflux) / Float64(N)
    print("MOJO_TIMING neuropharmacology::blood_brain_barrier_efflux", _ns_blood_brain_barrier_efflux, _acc_blood_brain_barrier_efflux)
    var _result_blood_brain_barrier_efflux = blood_brain_barrier_efflux(0.5, 0.5)
    var _summary_blood_brain_barrier_efflux = _summary_float64(_result_blood_brain_barrier_efflux)
    print("MOJO_RESULT neuropharmacology::blood_brain_barrier_efflux", _summary_blood_brain_barrier_efflux)
    var _acc_receptor_binding_ki: Float64 = 0.0
    var _t0_receptor_binding_ki = perf_counter_ns()
    for _ in range(N):
        _acc_receptor_binding_ki += receptor_binding_ki(0.5, 0.5, 0.5)
    var _t1_receptor_binding_ki = perf_counter_ns()
    var _ns_receptor_binding_ki = Float64(_t1_receptor_binding_ki - _t0_receptor_binding_ki) / Float64(N)
    print("MOJO_TIMING neuropharmacology::receptor_binding_ki", _ns_receptor_binding_ki, _acc_receptor_binding_ki)
    var _result_receptor_binding_ki = receptor_binding_ki(0.5, 0.5, 0.5)
    var _summary_receptor_binding_ki = _summary_float64(_result_receptor_binding_ki)
    print("MOJO_RESULT neuropharmacology::receptor_binding_ki", _summary_receptor_binding_ki)
    var _acc_synapse_neurotransmitter_level: Float64 = 0.0
    var _t0_synapse_neurotransmitter_level = perf_counter_ns()
    for _ in range(N):
        _acc_synapse_neurotransmitter_level += synapse_neurotransmitter_level(0.5, 0.5, 0.5)
    var _t1_synapse_neurotransmitter_level = perf_counter_ns()
    var _ns_synapse_neurotransmitter_level = Float64(_t1_synapse_neurotransmitter_level - _t0_synapse_neurotransmitter_level) / Float64(N)
    print("MOJO_TIMING neuropharmacology::synapse_neurotransmitter_level", _ns_synapse_neurotransmitter_level, _acc_synapse_neurotransmitter_level)
    var _result_synapse_neurotransmitter_level = synapse_neurotransmitter_level(0.5, 0.5, 0.5)
    var _summary_synapse_neurotransmitter_level = _summary_float64(_result_synapse_neurotransmitter_level)
    print("MOJO_RESULT neuropharmacology::synapse_neurotransmitter_level", _summary_synapse_neurotransmitter_level)
    var _acc_bbb_penetration_ratio: Float64 = 0.0
    var _t0_bbb_penetration_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_bbb_penetration_ratio += bbb_penetration_ratio(0.5, 0.5)
    var _t1_bbb_penetration_ratio = perf_counter_ns()
    var _ns_bbb_penetration_ratio = Float64(_t1_bbb_penetration_ratio - _t0_bbb_penetration_ratio) / Float64(N)
    print("MOJO_TIMING neuropharmacology::bbb_penetration_ratio", _ns_bbb_penetration_ratio, _acc_bbb_penetration_ratio)
    var _result_bbb_penetration_ratio = bbb_penetration_ratio(0.5, 0.5)
    var _summary_bbb_penetration_ratio = _summary_float64(_result_bbb_penetration_ratio)
    print("MOJO_RESULT neuropharmacology::bbb_penetration_ratio", _summary_bbb_penetration_ratio)
    var _acc_cns_drug_exposure: Float64 = 0.0
    var _t0_cns_drug_exposure = perf_counter_ns()
    for _ in range(N):
        _acc_cns_drug_exposure += cns_drug_exposure(0.5, 0.5, 0.5)
    var _t1_cns_drug_exposure = perf_counter_ns()
    var _ns_cns_drug_exposure = Float64(_t1_cns_drug_exposure - _t0_cns_drug_exposure) / Float64(N)
    print("MOJO_TIMING neuropharmacology::cns_drug_exposure", _ns_cns_drug_exposure, _acc_cns_drug_exposure)
    var _result_cns_drug_exposure = cns_drug_exposure(0.5, 0.5, 0.5)
    var _summary_cns_drug_exposure = _summary_float64(_result_cns_drug_exposure)
    print("MOJO_RESULT neuropharmacology::cns_drug_exposure", _summary_cns_drug_exposure)
    var _acc_d2_receptor_occupancy: Float64 = 0.0
    var _t0_d2_receptor_occupancy = perf_counter_ns()
    for _ in range(N):
        _acc_d2_receptor_occupancy += d2_receptor_occupancy(0.5, 0.5)
    var _t1_d2_receptor_occupancy = perf_counter_ns()
    var _ns_d2_receptor_occupancy = Float64(_t1_d2_receptor_occupancy - _t0_d2_receptor_occupancy) / Float64(N)
    print("MOJO_TIMING neuropharmacology::d2_receptor_occupancy", _ns_d2_receptor_occupancy, _acc_d2_receptor_occupancy)
    var _result_d2_receptor_occupancy = d2_receptor_occupancy(0.5, 0.5)
    var _summary_d2_receptor_occupancy = _summary_float64(_result_d2_receptor_occupancy)
    print("MOJO_RESULT neuropharmacology::d2_receptor_occupancy", _summary_d2_receptor_occupancy)
    var _acc_minimal_effective_dose_cns: Float64 = 0.0
    var _t0_minimal_effective_dose_cns = perf_counter_ns()
    for _ in range(N):
        _acc_minimal_effective_dose_cns += minimal_effective_dose_cns(0.5, 0.5, 0.5, 0.5)
    var _t1_minimal_effective_dose_cns = perf_counter_ns()
    var _ns_minimal_effective_dose_cns = Float64(_t1_minimal_effective_dose_cns - _t0_minimal_effective_dose_cns) / Float64(N)
    print("MOJO_TIMING neuropharmacology::minimal_effective_dose_cns", _ns_minimal_effective_dose_cns, _acc_minimal_effective_dose_cns)
    var _result_minimal_effective_dose_cns = minimal_effective_dose_cns(0.5, 0.5, 0.5, 0.5)
    var _summary_minimal_effective_dose_cns = _summary_float64(_result_minimal_effective_dose_cns)
    print("MOJO_RESULT neuropharmacology::minimal_effective_dose_cns", _summary_minimal_effective_dose_cns)
    var _acc_cns_side_effect_threshold: Float64 = 0.0
    var _t0_cns_side_effect_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_cns_side_effect_threshold += cns_side_effect_threshold(0.5, 0.5)
    var _t1_cns_side_effect_threshold = perf_counter_ns()
    var _ns_cns_side_effect_threshold = Float64(_t1_cns_side_effect_threshold - _t0_cns_side_effect_threshold) / Float64(N)
    print("MOJO_TIMING neuropharmacology::cns_side_effect_threshold", _ns_cns_side_effect_threshold, _acc_cns_side_effect_threshold)
    var _result_cns_side_effect_threshold = cns_side_effect_threshold(0.5, 0.5)
    var _summary_cns_side_effect_threshold = _summary_float64(_result_cns_side_effect_threshold)
    print("MOJO_RESULT neuropharmacology::cns_side_effect_threshold", _summary_cns_side_effect_threshold)
    var _acc_neuronal_firing_modulation: Float64 = 0.0
    var _t0_neuronal_firing_modulation = perf_counter_ns()
    for _ in range(N):
        _acc_neuronal_firing_modulation += neuronal_firing_modulation(0.5, 0.5, 0.5)
    var _t1_neuronal_firing_modulation = perf_counter_ns()
    var _ns_neuronal_firing_modulation = Float64(_t1_neuronal_firing_modulation - _t0_neuronal_firing_modulation) / Float64(N)
    print("MOJO_TIMING neuropharmacology::neuronal_firing_modulation", _ns_neuronal_firing_modulation, _acc_neuronal_firing_modulation)
    var _result_neuronal_firing_modulation = neuronal_firing_modulation(0.5, 0.5, 0.5)
    var _summary_neuronal_firing_modulation = _summary_float64(_result_neuronal_firing_modulation)
    print("MOJO_RESULT neuropharmacology::neuronal_firing_modulation", _summary_neuronal_firing_modulation)
