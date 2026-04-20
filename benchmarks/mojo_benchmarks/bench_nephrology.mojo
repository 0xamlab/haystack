"""bench_nephrology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from nephrology import gfr_ckd_epi, creatinine_clearance_cockroft, fractional_excretion_sodium, urine_anion_gap, transtubular_potassium_gradient, renal_plasma_flow, filtration_fraction, osmolar_clearance, free_water_clearance, protein_creatinine_ratio
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

    var _acc_gfr_ckd_epi: Float64 = 0.0
    var _t0_gfr_ckd_epi = perf_counter_ns()
    for _ in range(N):
        _acc_gfr_ckd_epi += gfr_ckd_epi(0.5, 0.5, 0.5)
    var _t1_gfr_ckd_epi = perf_counter_ns()
    var _ns_gfr_ckd_epi = Float64(_t1_gfr_ckd_epi - _t0_gfr_ckd_epi) / Float64(N)
    print("MOJO_TIMING nephrology::gfr_ckd_epi", _ns_gfr_ckd_epi, _acc_gfr_ckd_epi)
    var _acc_creatinine_clearance_cockroft: Float64 = 0.0
    var _t0_creatinine_clearance_cockroft = perf_counter_ns()
    for _ in range(N):
        _acc_creatinine_clearance_cockroft += creatinine_clearance_cockroft(0.5, 0.5, 0.5, 0.5)
    var _t1_creatinine_clearance_cockroft = perf_counter_ns()
    var _ns_creatinine_clearance_cockroft = Float64(_t1_creatinine_clearance_cockroft - _t0_creatinine_clearance_cockroft) / Float64(N)
    print("MOJO_TIMING nephrology::creatinine_clearance_cockroft", _ns_creatinine_clearance_cockroft, _acc_creatinine_clearance_cockroft)
    var _acc_fractional_excretion_sodium: Float64 = 0.0
    var _t0_fractional_excretion_sodium = perf_counter_ns()
    for _ in range(N):
        _acc_fractional_excretion_sodium += fractional_excretion_sodium(0.5, 0.5, 0.5, 0.5)
    var _t1_fractional_excretion_sodium = perf_counter_ns()
    var _ns_fractional_excretion_sodium = Float64(_t1_fractional_excretion_sodium - _t0_fractional_excretion_sodium) / Float64(N)
    print("MOJO_TIMING nephrology::fractional_excretion_sodium", _ns_fractional_excretion_sodium, _acc_fractional_excretion_sodium)
    var _acc_urine_anion_gap: Float64 = 0.0
    var _t0_urine_anion_gap = perf_counter_ns()
    for _ in range(N):
        _acc_urine_anion_gap += urine_anion_gap(0.5, 0.5, 0.5)
    var _t1_urine_anion_gap = perf_counter_ns()
    var _ns_urine_anion_gap = Float64(_t1_urine_anion_gap - _t0_urine_anion_gap) / Float64(N)
    print("MOJO_TIMING nephrology::urine_anion_gap", _ns_urine_anion_gap, _acc_urine_anion_gap)
    var _acc_transtubular_potassium_gradient: Float64 = 0.0
    var _t0_transtubular_potassium_gradient = perf_counter_ns()
    for _ in range(N):
        _acc_transtubular_potassium_gradient += transtubular_potassium_gradient(0.5, 0.5, 0.5, 0.5)
    var _t1_transtubular_potassium_gradient = perf_counter_ns()
    var _ns_transtubular_potassium_gradient = Float64(_t1_transtubular_potassium_gradient - _t0_transtubular_potassium_gradient) / Float64(N)
    print("MOJO_TIMING nephrology::transtubular_potassium_gradient", _ns_transtubular_potassium_gradient, _acc_transtubular_potassium_gradient)
    var _acc_renal_plasma_flow: Float64 = 0.0
    var _t0_renal_plasma_flow = perf_counter_ns()
    for _ in range(N):
        _acc_renal_plasma_flow += renal_plasma_flow(0.5, 0.5, 0.5)
    var _t1_renal_plasma_flow = perf_counter_ns()
    var _ns_renal_plasma_flow = Float64(_t1_renal_plasma_flow - _t0_renal_plasma_flow) / Float64(N)
    print("MOJO_TIMING nephrology::renal_plasma_flow", _ns_renal_plasma_flow, _acc_renal_plasma_flow)
    var _acc_filtration_fraction: Float64 = 0.0
    var _t0_filtration_fraction = perf_counter_ns()
    for _ in range(N):
        _acc_filtration_fraction += filtration_fraction(0.5, 0.5)
    var _t1_filtration_fraction = perf_counter_ns()
    var _ns_filtration_fraction = Float64(_t1_filtration_fraction - _t0_filtration_fraction) / Float64(N)
    print("MOJO_TIMING nephrology::filtration_fraction", _ns_filtration_fraction, _acc_filtration_fraction)
    var _acc_osmolar_clearance: Float64 = 0.0
    var _t0_osmolar_clearance = perf_counter_ns()
    for _ in range(N):
        _acc_osmolar_clearance += osmolar_clearance(0.5, 0.5, 0.5)
    var _t1_osmolar_clearance = perf_counter_ns()
    var _ns_osmolar_clearance = Float64(_t1_osmolar_clearance - _t0_osmolar_clearance) / Float64(N)
    print("MOJO_TIMING nephrology::osmolar_clearance", _ns_osmolar_clearance, _acc_osmolar_clearance)
    var _acc_free_water_clearance: Float64 = 0.0
    var _t0_free_water_clearance = perf_counter_ns()
    for _ in range(N):
        _acc_free_water_clearance += free_water_clearance(0.5, 0.5)
    var _t1_free_water_clearance = perf_counter_ns()
    var _ns_free_water_clearance = Float64(_t1_free_water_clearance - _t0_free_water_clearance) / Float64(N)
    print("MOJO_TIMING nephrology::free_water_clearance", _ns_free_water_clearance, _acc_free_water_clearance)
    var _acc_protein_creatinine_ratio: Float64 = 0.0
    var _t0_protein_creatinine_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_protein_creatinine_ratio += protein_creatinine_ratio(0.5, 0.5)
    var _t1_protein_creatinine_ratio = perf_counter_ns()
    var _ns_protein_creatinine_ratio = Float64(_t1_protein_creatinine_ratio - _t0_protein_creatinine_ratio) / Float64(N)
    print("MOJO_TIMING nephrology::protein_creatinine_ratio", _ns_protein_creatinine_ratio, _acc_protein_creatinine_ratio)
