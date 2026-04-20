"""bench_forensics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from forensics import time_of_death_newton, algor_mortis_rate, blood_alcohol_widmark, alcohol_elimination_rate, rigor_mortis_stage, ballistic_drop, bloodstain_impact_angle, dna_match_probability, fingerprint_minutiae_score, glass_refractive_index_match, decomposition_add, toxicology_lethal_dose
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

    var _acc_time_of_death_newton: Float64 = 0.0
    var _t0_time_of_death_newton = perf_counter_ns()
    for _ in range(N):
        _acc_time_of_death_newton += time_of_death_newton(0.5, 0.5, 0.5, 0.5)
    var _t1_time_of_death_newton = perf_counter_ns()
    var _ns_time_of_death_newton = Float64(_t1_time_of_death_newton - _t0_time_of_death_newton) / Float64(N)
    print("MOJO_TIMING forensics::time_of_death_newton", _ns_time_of_death_newton, _acc_time_of_death_newton)
    var _acc_algor_mortis_rate: Float64 = 0.0
    var _t0_algor_mortis_rate = perf_counter_ns()
    for _ in range(N):
        _acc_algor_mortis_rate += algor_mortis_rate(0.5, 0.5)
    var _t1_algor_mortis_rate = perf_counter_ns()
    var _ns_algor_mortis_rate = Float64(_t1_algor_mortis_rate - _t0_algor_mortis_rate) / Float64(N)
    print("MOJO_TIMING forensics::algor_mortis_rate", _ns_algor_mortis_rate, _acc_algor_mortis_rate)
    var _acc_blood_alcohol_widmark: Float64 = 0.0
    var _t0_blood_alcohol_widmark = perf_counter_ns()
    for _ in range(N):
        _acc_blood_alcohol_widmark += blood_alcohol_widmark(0.5, 0.5, 0.5)
    var _t1_blood_alcohol_widmark = perf_counter_ns()
    var _ns_blood_alcohol_widmark = Float64(_t1_blood_alcohol_widmark - _t0_blood_alcohol_widmark) / Float64(N)
    print("MOJO_TIMING forensics::blood_alcohol_widmark", _ns_blood_alcohol_widmark, _acc_blood_alcohol_widmark)
    var _acc_alcohol_elimination_rate: Float64 = 0.0
    var _t0_alcohol_elimination_rate = perf_counter_ns()
    for _ in range(N):
        _acc_alcohol_elimination_rate += alcohol_elimination_rate(0.5, 0.5, 0.5)
    var _t1_alcohol_elimination_rate = perf_counter_ns()
    var _ns_alcohol_elimination_rate = Float64(_t1_alcohol_elimination_rate - _t0_alcohol_elimination_rate) / Float64(N)
    print("MOJO_TIMING forensics::alcohol_elimination_rate", _ns_alcohol_elimination_rate, _acc_alcohol_elimination_rate)
    var _acc_rigor_mortis_stage: Float64 = 0.0
    var _t0_rigor_mortis_stage = perf_counter_ns()
    for _ in range(N):
        _acc_rigor_mortis_stage += Float64(rigor_mortis_stage(0.5))
    var _t1_rigor_mortis_stage = perf_counter_ns()
    var _ns_rigor_mortis_stage = Float64(_t1_rigor_mortis_stage - _t0_rigor_mortis_stage) / Float64(N)
    print("MOJO_TIMING forensics::rigor_mortis_stage", _ns_rigor_mortis_stage, _acc_rigor_mortis_stage)
    var _acc_ballistic_drop: Float64 = 0.0
    var _t0_ballistic_drop = perf_counter_ns()
    for _ in range(N):
        _acc_ballistic_drop += ballistic_drop(0.5, 0.5, 0.5)
    var _t1_ballistic_drop = perf_counter_ns()
    var _ns_ballistic_drop = Float64(_t1_ballistic_drop - _t0_ballistic_drop) / Float64(N)
    print("MOJO_TIMING forensics::ballistic_drop", _ns_ballistic_drop, _acc_ballistic_drop)
    var _acc_bloodstain_impact_angle: Float64 = 0.0
    var _t0_bloodstain_impact_angle = perf_counter_ns()
    for _ in range(N):
        _acc_bloodstain_impact_angle += bloodstain_impact_angle(0.5, 0.5)
    var _t1_bloodstain_impact_angle = perf_counter_ns()
    var _ns_bloodstain_impact_angle = Float64(_t1_bloodstain_impact_angle - _t0_bloodstain_impact_angle) / Float64(N)
    print("MOJO_TIMING forensics::bloodstain_impact_angle", _ns_bloodstain_impact_angle, _acc_bloodstain_impact_angle)
    var _acc_dna_match_probability: Float64 = 0.0
    var _t0_dna_match_probability = perf_counter_ns()
    for _ in range(N):
        _acc_dna_match_probability += dna_match_probability(0.5, 0.5)
    var _t1_dna_match_probability = perf_counter_ns()
    var _ns_dna_match_probability = Float64(_t1_dna_match_probability - _t0_dna_match_probability) / Float64(N)
    print("MOJO_TIMING forensics::dna_match_probability", _ns_dna_match_probability, _acc_dna_match_probability)
    var _acc_fingerprint_minutiae_score: Float64 = 0.0
    var _t0_fingerprint_minutiae_score = perf_counter_ns()
    for _ in range(N):
        _acc_fingerprint_minutiae_score += fingerprint_minutiae_score(0.5, 0.5)
    var _t1_fingerprint_minutiae_score = perf_counter_ns()
    var _ns_fingerprint_minutiae_score = Float64(_t1_fingerprint_minutiae_score - _t0_fingerprint_minutiae_score) / Float64(N)
    print("MOJO_TIMING forensics::fingerprint_minutiae_score", _ns_fingerprint_minutiae_score, _acc_fingerprint_minutiae_score)
    var _acc_glass_refractive_index_match: Float64 = 0.0
    var _t0_glass_refractive_index_match = perf_counter_ns()
    for _ in range(N):
        _acc_glass_refractive_index_match += Float64(glass_refractive_index_match(0.5, 0.5, 0.5))
    var _t1_glass_refractive_index_match = perf_counter_ns()
    var _ns_glass_refractive_index_match = Float64(_t1_glass_refractive_index_match - _t0_glass_refractive_index_match) / Float64(N)
    print("MOJO_TIMING forensics::glass_refractive_index_match", _ns_glass_refractive_index_match, _acc_glass_refractive_index_match)
    var _acc_decomposition_add: Float64 = 0.0
    var _t0_decomposition_add = perf_counter_ns()
    for _ in range(N):
        _acc_decomposition_add += decomposition_add(0.5, 0.5, 0.5)
    var _t1_decomposition_add = perf_counter_ns()
    var _ns_decomposition_add = Float64(_t1_decomposition_add - _t0_decomposition_add) / Float64(N)
    print("MOJO_TIMING forensics::decomposition_add", _ns_decomposition_add, _acc_decomposition_add)
    var _acc_toxicology_lethal_dose: Float64 = 0.0
    var _t0_toxicology_lethal_dose = perf_counter_ns()
    for _ in range(N):
        _acc_toxicology_lethal_dose += toxicology_lethal_dose(0.5, 0.5)
    var _t1_toxicology_lethal_dose = perf_counter_ns()
    var _ns_toxicology_lethal_dose = Float64(_t1_toxicology_lethal_dose - _t0_toxicology_lethal_dose) / Float64(N)
    print("MOJO_TIMING forensics::toxicology_lethal_dose", _ns_toxicology_lethal_dose, _acc_toxicology_lethal_dose)
