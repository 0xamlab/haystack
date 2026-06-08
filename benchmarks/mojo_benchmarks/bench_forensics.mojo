"""bench_forensics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from forensics import time_of_death_newton, algor_mortis_rate, blood_alcohol_widmark, alcohol_elimination_rate, rigor_mortis_stage, ballistic_drop, bloodstain_impact_angle, dna_match_probability, fingerprint_minutiae_score, glass_refractive_index_match, decomposition_add, toxicology_lethal_dose
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_time_of_death_newton: Float64 = 0.0
    var _t0_time_of_death_newton = perf_counter_ns()
    for _ in range(N):
        _acc_time_of_death_newton += time_of_death_newton(0.5, 0.5, 0.5, 0.5)
    var _t1_time_of_death_newton = perf_counter_ns()
    var _ns_time_of_death_newton = Float64(_t1_time_of_death_newton - _t0_time_of_death_newton) / Float64(N)
    print("MOJO_TIMING forensics::time_of_death_newton", _ns_time_of_death_newton, _acc_time_of_death_newton)
    var _result_time_of_death_newton = time_of_death_newton(0.5, 0.5, 0.5, 0.5)
    var _summary_time_of_death_newton = _summary_float64(_result_time_of_death_newton)
    print("MOJO_RESULT forensics::time_of_death_newton", _summary_time_of_death_newton)
    var _acc_algor_mortis_rate: Float64 = 0.0
    var _t0_algor_mortis_rate = perf_counter_ns()
    for _ in range(N):
        _acc_algor_mortis_rate += algor_mortis_rate(0.5, 0.5)
    var _t1_algor_mortis_rate = perf_counter_ns()
    var _ns_algor_mortis_rate = Float64(_t1_algor_mortis_rate - _t0_algor_mortis_rate) / Float64(N)
    print("MOJO_TIMING forensics::algor_mortis_rate", _ns_algor_mortis_rate, _acc_algor_mortis_rate)
    var _result_algor_mortis_rate = algor_mortis_rate(0.5, 0.5)
    var _summary_algor_mortis_rate = _summary_float64(_result_algor_mortis_rate)
    print("MOJO_RESULT forensics::algor_mortis_rate", _summary_algor_mortis_rate)
    var _acc_blood_alcohol_widmark: Float64 = 0.0
    var _t0_blood_alcohol_widmark = perf_counter_ns()
    for _ in range(N):
        _acc_blood_alcohol_widmark += blood_alcohol_widmark(0.5, 0.5, 0.5)
    var _t1_blood_alcohol_widmark = perf_counter_ns()
    var _ns_blood_alcohol_widmark = Float64(_t1_blood_alcohol_widmark - _t0_blood_alcohol_widmark) / Float64(N)
    print("MOJO_TIMING forensics::blood_alcohol_widmark", _ns_blood_alcohol_widmark, _acc_blood_alcohol_widmark)
    var _result_blood_alcohol_widmark = blood_alcohol_widmark(0.5, 0.5, 0.5)
    var _summary_blood_alcohol_widmark = _summary_float64(_result_blood_alcohol_widmark)
    print("MOJO_RESULT forensics::blood_alcohol_widmark", _summary_blood_alcohol_widmark)
    var _acc_alcohol_elimination_rate: Float64 = 0.0
    var _t0_alcohol_elimination_rate = perf_counter_ns()
    for _ in range(N):
        _acc_alcohol_elimination_rate += alcohol_elimination_rate(0.5, 0.5, 0.5)
    var _t1_alcohol_elimination_rate = perf_counter_ns()
    var _ns_alcohol_elimination_rate = Float64(_t1_alcohol_elimination_rate - _t0_alcohol_elimination_rate) / Float64(N)
    print("MOJO_TIMING forensics::alcohol_elimination_rate", _ns_alcohol_elimination_rate, _acc_alcohol_elimination_rate)
    var _result_alcohol_elimination_rate = alcohol_elimination_rate(0.5, 0.5, 0.5)
    var _summary_alcohol_elimination_rate = _summary_float64(_result_alcohol_elimination_rate)
    print("MOJO_RESULT forensics::alcohol_elimination_rate", _summary_alcohol_elimination_rate)
    var _acc_rigor_mortis_stage: Float64 = 0.0
    var _t0_rigor_mortis_stage = perf_counter_ns()
    for _ in range(N):
        _acc_rigor_mortis_stage += Float64(rigor_mortis_stage(0.5))
    var _t1_rigor_mortis_stage = perf_counter_ns()
    var _ns_rigor_mortis_stage = Float64(_t1_rigor_mortis_stage - _t0_rigor_mortis_stage) / Float64(N)
    print("MOJO_TIMING forensics::rigor_mortis_stage", _ns_rigor_mortis_stage, _acc_rigor_mortis_stage)
    var _result_rigor_mortis_stage = rigor_mortis_stage(0.5)
    var _summary_rigor_mortis_stage = _summary_int(_result_rigor_mortis_stage)
    print("MOJO_RESULT forensics::rigor_mortis_stage", _summary_rigor_mortis_stage)
    var _acc_ballistic_drop: Float64 = 0.0
    var _t0_ballistic_drop = perf_counter_ns()
    for _ in range(N):
        _acc_ballistic_drop += ballistic_drop(0.5, 0.5, 0.5)
    var _t1_ballistic_drop = perf_counter_ns()
    var _ns_ballistic_drop = Float64(_t1_ballistic_drop - _t0_ballistic_drop) / Float64(N)
    print("MOJO_TIMING forensics::ballistic_drop", _ns_ballistic_drop, _acc_ballistic_drop)
    var _result_ballistic_drop = ballistic_drop(0.5, 0.5, 0.5)
    var _summary_ballistic_drop = _summary_float64(_result_ballistic_drop)
    print("MOJO_RESULT forensics::ballistic_drop", _summary_ballistic_drop)
    var _acc_bloodstain_impact_angle: Float64 = 0.0
    var _t0_bloodstain_impact_angle = perf_counter_ns()
    for _ in range(N):
        _acc_bloodstain_impact_angle += bloodstain_impact_angle(0.5, 0.5)
    var _t1_bloodstain_impact_angle = perf_counter_ns()
    var _ns_bloodstain_impact_angle = Float64(_t1_bloodstain_impact_angle - _t0_bloodstain_impact_angle) / Float64(N)
    print("MOJO_TIMING forensics::bloodstain_impact_angle", _ns_bloodstain_impact_angle, _acc_bloodstain_impact_angle)
    var _result_bloodstain_impact_angle = bloodstain_impact_angle(0.5, 0.5)
    var _summary_bloodstain_impact_angle = _summary_float64(_result_bloodstain_impact_angle)
    print("MOJO_RESULT forensics::bloodstain_impact_angle", _summary_bloodstain_impact_angle)
    var _acc_dna_match_probability: Float64 = 0.0
    var _t0_dna_match_probability = perf_counter_ns()
    for _ in range(N):
        _acc_dna_match_probability += dna_match_probability(0.5, 0.5)
    var _t1_dna_match_probability = perf_counter_ns()
    var _ns_dna_match_probability = Float64(_t1_dna_match_probability - _t0_dna_match_probability) / Float64(N)
    print("MOJO_TIMING forensics::dna_match_probability", _ns_dna_match_probability, _acc_dna_match_probability)
    var _result_dna_match_probability = dna_match_probability(0.5, 0.5)
    var _summary_dna_match_probability = _summary_float64(_result_dna_match_probability)
    print("MOJO_RESULT forensics::dna_match_probability", _summary_dna_match_probability)
    var _acc_fingerprint_minutiae_score: Float64 = 0.0
    var _t0_fingerprint_minutiae_score = perf_counter_ns()
    for _ in range(N):
        _acc_fingerprint_minutiae_score += fingerprint_minutiae_score(0.5, 0.5)
    var _t1_fingerprint_minutiae_score = perf_counter_ns()
    var _ns_fingerprint_minutiae_score = Float64(_t1_fingerprint_minutiae_score - _t0_fingerprint_minutiae_score) / Float64(N)
    print("MOJO_TIMING forensics::fingerprint_minutiae_score", _ns_fingerprint_minutiae_score, _acc_fingerprint_minutiae_score)
    var _result_fingerprint_minutiae_score = fingerprint_minutiae_score(0.5, 0.5)
    var _summary_fingerprint_minutiae_score = _summary_float64(_result_fingerprint_minutiae_score)
    print("MOJO_RESULT forensics::fingerprint_minutiae_score", _summary_fingerprint_minutiae_score)
    var _acc_glass_refractive_index_match: Float64 = 0.0
    var _t0_glass_refractive_index_match = perf_counter_ns()
    for _ in range(N):
        _acc_glass_refractive_index_match += Float64(glass_refractive_index_match(0.5, 0.5, 0.5))
    var _t1_glass_refractive_index_match = perf_counter_ns()
    var _ns_glass_refractive_index_match = Float64(_t1_glass_refractive_index_match - _t0_glass_refractive_index_match) / Float64(N)
    print("MOJO_TIMING forensics::glass_refractive_index_match", _ns_glass_refractive_index_match, _acc_glass_refractive_index_match)
    var _result_glass_refractive_index_match = glass_refractive_index_match(0.5, 0.5, 0.5)
    var _summary_glass_refractive_index_match = _summary_bool(_result_glass_refractive_index_match)
    print("MOJO_RESULT forensics::glass_refractive_index_match", _summary_glass_refractive_index_match)
    var _acc_decomposition_add: Float64 = 0.0
    var _t0_decomposition_add = perf_counter_ns()
    for _ in range(N):
        _acc_decomposition_add += decomposition_add(0.5, 0.5, 0.5)
    var _t1_decomposition_add = perf_counter_ns()
    var _ns_decomposition_add = Float64(_t1_decomposition_add - _t0_decomposition_add) / Float64(N)
    print("MOJO_TIMING forensics::decomposition_add", _ns_decomposition_add, _acc_decomposition_add)
    var _result_decomposition_add = decomposition_add(0.5, 0.5, 0.5)
    var _summary_decomposition_add = _summary_float64(_result_decomposition_add)
    print("MOJO_RESULT forensics::decomposition_add", _summary_decomposition_add)
    var _acc_toxicology_lethal_dose: Float64 = 0.0
    var _t0_toxicology_lethal_dose = perf_counter_ns()
    for _ in range(N):
        _acc_toxicology_lethal_dose += toxicology_lethal_dose(0.5, 0.5)
    var _t1_toxicology_lethal_dose = perf_counter_ns()
    var _ns_toxicology_lethal_dose = Float64(_t1_toxicology_lethal_dose - _t0_toxicology_lethal_dose) / Float64(N)
    print("MOJO_TIMING forensics::toxicology_lethal_dose", _ns_toxicology_lethal_dose, _acc_toxicology_lethal_dose)
    var _result_toxicology_lethal_dose = toxicology_lethal_dose(0.5, 0.5)
    var _summary_toxicology_lethal_dose = _summary_float64(_result_toxicology_lethal_dose)
    print("MOJO_RESULT forensics::toxicology_lethal_dose", _summary_toxicology_lethal_dose)
