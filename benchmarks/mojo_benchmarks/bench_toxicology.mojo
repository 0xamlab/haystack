"""bench_toxicology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from toxicology import ld50_dose, therapeutic_index, margin_of_safety, bioconcentration_factor, hazard_quotient, hazard_index, cancer_risk, average_daily_dose, no_observed_adverse_effect_level, reference_dose, dose_response_hill, acute_exposure_ratio
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

    var _acc_ld50_dose: Float64 = 0.0
    var _t0_ld50_dose = perf_counter_ns()
    for _ in range(N):
        _acc_ld50_dose += ld50_dose(0.5, 0.5)
    var _t1_ld50_dose = perf_counter_ns()
    var _ns_ld50_dose = Float64(_t1_ld50_dose - _t0_ld50_dose) / Float64(N)
    print("MOJO_TIMING toxicology::ld50_dose", _ns_ld50_dose, _acc_ld50_dose)
    var _acc_therapeutic_index: Float64 = 0.0
    var _t0_therapeutic_index = perf_counter_ns()
    for _ in range(N):
        _acc_therapeutic_index += therapeutic_index(0.5, 0.5)
    var _t1_therapeutic_index = perf_counter_ns()
    var _ns_therapeutic_index = Float64(_t1_therapeutic_index - _t0_therapeutic_index) / Float64(N)
    print("MOJO_TIMING toxicology::therapeutic_index", _ns_therapeutic_index, _acc_therapeutic_index)
    var _acc_margin_of_safety: Float64 = 0.0
    var _t0_margin_of_safety = perf_counter_ns()
    for _ in range(N):
        _acc_margin_of_safety += margin_of_safety(0.5, 0.5)
    var _t1_margin_of_safety = perf_counter_ns()
    var _ns_margin_of_safety = Float64(_t1_margin_of_safety - _t0_margin_of_safety) / Float64(N)
    print("MOJO_TIMING toxicology::margin_of_safety", _ns_margin_of_safety, _acc_margin_of_safety)
    var _acc_bioconcentration_factor: Float64 = 0.0
    var _t0_bioconcentration_factor = perf_counter_ns()
    for _ in range(N):
        _acc_bioconcentration_factor += bioconcentration_factor(0.5, 0.5)
    var _t1_bioconcentration_factor = perf_counter_ns()
    var _ns_bioconcentration_factor = Float64(_t1_bioconcentration_factor - _t0_bioconcentration_factor) / Float64(N)
    print("MOJO_TIMING toxicology::bioconcentration_factor", _ns_bioconcentration_factor, _acc_bioconcentration_factor)
    var _acc_hazard_quotient: Float64 = 0.0
    var _t0_hazard_quotient = perf_counter_ns()
    for _ in range(N):
        _acc_hazard_quotient += hazard_quotient(0.5, 0.5)
    var _t1_hazard_quotient = perf_counter_ns()
    var _ns_hazard_quotient = Float64(_t1_hazard_quotient - _t0_hazard_quotient) / Float64(N)
    print("MOJO_TIMING toxicology::hazard_quotient", _ns_hazard_quotient, _acc_hazard_quotient)
    var _acc_hazard_index: Float64 = 0.0
    var _t0_hazard_index = perf_counter_ns()
    for _ in range(N):
        _acc_hazard_index += hazard_index(0.5)
    var _t1_hazard_index = perf_counter_ns()
    var _ns_hazard_index = Float64(_t1_hazard_index - _t0_hazard_index) / Float64(N)
    print("MOJO_TIMING toxicology::hazard_index", _ns_hazard_index, _acc_hazard_index)
    var _acc_cancer_risk: Float64 = 0.0
    var _t0_cancer_risk = perf_counter_ns()
    for _ in range(N):
        _acc_cancer_risk += cancer_risk(0.5, 0.5)
    var _t1_cancer_risk = perf_counter_ns()
    var _ns_cancer_risk = Float64(_t1_cancer_risk - _t0_cancer_risk) / Float64(N)
    print("MOJO_TIMING toxicology::cancer_risk", _ns_cancer_risk, _acc_cancer_risk)
    var _acc_average_daily_dose: Float64 = 0.0
    var _t0_average_daily_dose = perf_counter_ns()
    for _ in range(N):
        _acc_average_daily_dose += average_daily_dose(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_average_daily_dose = perf_counter_ns()
    var _ns_average_daily_dose = Float64(_t1_average_daily_dose - _t0_average_daily_dose) / Float64(N)
    print("MOJO_TIMING toxicology::average_daily_dose", _ns_average_daily_dose, _acc_average_daily_dose)
    var _acc_no_observed_adverse_effect_level: Float64 = 0.0
    var _t0_no_observed_adverse_effect_level = perf_counter_ns()
    for _ in range(N):
        _acc_no_observed_adverse_effect_level += no_observed_adverse_effect_level(0.5, 0.5)
    var _t1_no_observed_adverse_effect_level = perf_counter_ns()
    var _ns_no_observed_adverse_effect_level = Float64(_t1_no_observed_adverse_effect_level - _t0_no_observed_adverse_effect_level) / Float64(N)
    print("MOJO_TIMING toxicology::no_observed_adverse_effect_level", _ns_no_observed_adverse_effect_level, _acc_no_observed_adverse_effect_level)
    var _acc_reference_dose: Float64 = 0.0
    var _t0_reference_dose = perf_counter_ns()
    for _ in range(N):
        _acc_reference_dose += reference_dose(0.5, 0.5)
    var _t1_reference_dose = perf_counter_ns()
    var _ns_reference_dose = Float64(_t1_reference_dose - _t0_reference_dose) / Float64(N)
    print("MOJO_TIMING toxicology::reference_dose", _ns_reference_dose, _acc_reference_dose)
    var _acc_dose_response_hill: Float64 = 0.0
    var _t0_dose_response_hill = perf_counter_ns()
    for _ in range(N):
        _acc_dose_response_hill += dose_response_hill(0.5, 0.5, 0.5, 0.5)
    var _t1_dose_response_hill = perf_counter_ns()
    var _ns_dose_response_hill = Float64(_t1_dose_response_hill - _t0_dose_response_hill) / Float64(N)
    print("MOJO_TIMING toxicology::dose_response_hill", _ns_dose_response_hill, _acc_dose_response_hill)
    var _acc_acute_exposure_ratio: Float64 = 0.0
    var _t0_acute_exposure_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_acute_exposure_ratio += acute_exposure_ratio(0.5, 0.5)
    var _t1_acute_exposure_ratio = perf_counter_ns()
    var _ns_acute_exposure_ratio = Float64(_t1_acute_exposure_ratio - _t0_acute_exposure_ratio) / Float64(N)
    print("MOJO_TIMING toxicology::acute_exposure_ratio", _ns_acute_exposure_ratio, _acc_acute_exposure_ratio)
