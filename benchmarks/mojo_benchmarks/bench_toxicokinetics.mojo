"""bench_toxicokinetics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from toxicokinetics import internal_dose, peak_plasma_concentration, time_to_peak, plasma_auc, apparent_volume_distribution, elimination_half_life, systemic_clearance, bioconcentration_factor, toxic_equivalency_factor, margin_of_exposure
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

    var _acc_internal_dose: Float64 = 0.0
    var _t0_internal_dose = perf_counter_ns()
    for _ in range(N):
        _acc_internal_dose += internal_dose(0.5, 0.5)
    var _t1_internal_dose = perf_counter_ns()
    var _ns_internal_dose = Float64(_t1_internal_dose - _t0_internal_dose) / Float64(N)
    print("MOJO_TIMING toxicokinetics::internal_dose", _ns_internal_dose, _acc_internal_dose)
    var _acc_peak_plasma_concentration: Float64 = 0.0
    var _t0_peak_plasma_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_peak_plasma_concentration += peak_plasma_concentration(0.5, 0.5)
    var _t1_peak_plasma_concentration = perf_counter_ns()
    var _ns_peak_plasma_concentration = Float64(_t1_peak_plasma_concentration - _t0_peak_plasma_concentration) / Float64(N)
    print("MOJO_TIMING toxicokinetics::peak_plasma_concentration", _ns_peak_plasma_concentration, _acc_peak_plasma_concentration)
    var _acc_time_to_peak: Float64 = 0.0
    var _t0_time_to_peak = perf_counter_ns()
    for _ in range(N):
        _acc_time_to_peak += time_to_peak(0.5, 0.5)
    var _t1_time_to_peak = perf_counter_ns()
    var _ns_time_to_peak = Float64(_t1_time_to_peak - _t0_time_to_peak) / Float64(N)
    print("MOJO_TIMING toxicokinetics::time_to_peak", _ns_time_to_peak, _acc_time_to_peak)
    var _acc_plasma_auc: Float64 = 0.0
    var _t0_plasma_auc = perf_counter_ns()
    for _ in range(N):
        _acc_plasma_auc += plasma_auc(0.5, 0.5, 0.5, 0.5)
    var _t1_plasma_auc = perf_counter_ns()
    var _ns_plasma_auc = Float64(_t1_plasma_auc - _t0_plasma_auc) / Float64(N)
    print("MOJO_TIMING toxicokinetics::plasma_auc", _ns_plasma_auc, _acc_plasma_auc)
    var _acc_apparent_volume_distribution: Float64 = 0.0
    var _t0_apparent_volume_distribution = perf_counter_ns()
    for _ in range(N):
        _acc_apparent_volume_distribution += apparent_volume_distribution(0.5, 0.5)
    var _t1_apparent_volume_distribution = perf_counter_ns()
    var _ns_apparent_volume_distribution = Float64(_t1_apparent_volume_distribution - _t0_apparent_volume_distribution) / Float64(N)
    print("MOJO_TIMING toxicokinetics::apparent_volume_distribution", _ns_apparent_volume_distribution, _acc_apparent_volume_distribution)
    var _acc_elimination_half_life: Float64 = 0.0
    var _t0_elimination_half_life = perf_counter_ns()
    for _ in range(N):
        _acc_elimination_half_life += elimination_half_life(0.5)
    var _t1_elimination_half_life = perf_counter_ns()
    var _ns_elimination_half_life = Float64(_t1_elimination_half_life - _t0_elimination_half_life) / Float64(N)
    print("MOJO_TIMING toxicokinetics::elimination_half_life", _ns_elimination_half_life, _acc_elimination_half_life)
    var _acc_systemic_clearance: Float64 = 0.0
    var _t0_systemic_clearance = perf_counter_ns()
    for _ in range(N):
        _acc_systemic_clearance += systemic_clearance(0.5, 0.5)
    var _t1_systemic_clearance = perf_counter_ns()
    var _ns_systemic_clearance = Float64(_t1_systemic_clearance - _t0_systemic_clearance) / Float64(N)
    print("MOJO_TIMING toxicokinetics::systemic_clearance", _ns_systemic_clearance, _acc_systemic_clearance)
    var _acc_bioconcentration_factor: Float64 = 0.0
    var _t0_bioconcentration_factor = perf_counter_ns()
    for _ in range(N):
        _acc_bioconcentration_factor += bioconcentration_factor(0.5, 0.5)
    var _t1_bioconcentration_factor = perf_counter_ns()
    var _ns_bioconcentration_factor = Float64(_t1_bioconcentration_factor - _t0_bioconcentration_factor) / Float64(N)
    print("MOJO_TIMING toxicokinetics::bioconcentration_factor", _ns_bioconcentration_factor, _acc_bioconcentration_factor)
    var _acc_toxic_equivalency_factor: Float64 = 0.0
    var _t0_toxic_equivalency_factor = perf_counter_ns()
    for _ in range(N):
        _acc_toxic_equivalency_factor += toxic_equivalency_factor(0.5, 0.5)
    var _t1_toxic_equivalency_factor = perf_counter_ns()
    var _ns_toxic_equivalency_factor = Float64(_t1_toxic_equivalency_factor - _t0_toxic_equivalency_factor) / Float64(N)
    print("MOJO_TIMING toxicokinetics::toxic_equivalency_factor", _ns_toxic_equivalency_factor, _acc_toxic_equivalency_factor)
    var _acc_margin_of_exposure: Float64 = 0.0
    var _t0_margin_of_exposure = perf_counter_ns()
    for _ in range(N):
        _acc_margin_of_exposure += margin_of_exposure(0.5, 0.5)
    var _t1_margin_of_exposure = perf_counter_ns()
    var _ns_margin_of_exposure = Float64(_t1_margin_of_exposure - _t0_margin_of_exposure) / Float64(N)
    print("MOJO_TIMING toxicokinetics::margin_of_exposure", _ns_margin_of_exposure, _acc_margin_of_exposure)
