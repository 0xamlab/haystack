"""bench_pharmacokinetics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pharmacokinetics import one_compartment_oral, one_compartment_iv, half_life, elimination_rate, clearance, bioavailability, loading_dose, maintenance_dose, steady_state_concentration, time_to_peak, accumulation_factor, drug_auc_trapezoidal
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

    var _acc_one_compartment_oral: Float64 = 0.0
    var _t0_one_compartment_oral = perf_counter_ns()
    for _ in range(N):
        _acc_one_compartment_oral += one_compartment_oral(100.0, 0.8, 0.2, 10.0, 2.0)
    var _t1_one_compartment_oral = perf_counter_ns()
    var _ns_one_compartment_oral = Float64(_t1_one_compartment_oral - _t0_one_compartment_oral) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::one_compartment_oral", _ns_one_compartment_oral, _acc_one_compartment_oral)
    var _acc_one_compartment_iv: Float64 = 0.0
    var _t0_one_compartment_iv = perf_counter_ns()
    for _ in range(N):
        _acc_one_compartment_iv += one_compartment_iv(0.5, 0.5, 0.5, 0.5)
    var _t1_one_compartment_iv = perf_counter_ns()
    var _ns_one_compartment_iv = Float64(_t1_one_compartment_iv - _t0_one_compartment_iv) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::one_compartment_iv", _ns_one_compartment_iv, _acc_one_compartment_iv)
    var _acc_half_life: Float64 = 0.0
    var _t0_half_life = perf_counter_ns()
    for _ in range(N):
        _acc_half_life += half_life(0.5)
    var _t1_half_life = perf_counter_ns()
    var _ns_half_life = Float64(_t1_half_life - _t0_half_life) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::half_life", _ns_half_life, _acc_half_life)
    var _acc_elimination_rate: Float64 = 0.0
    var _t0_elimination_rate = perf_counter_ns()
    for _ in range(N):
        _acc_elimination_rate += elimination_rate(0.5)
    var _t1_elimination_rate = perf_counter_ns()
    var _ns_elimination_rate = Float64(_t1_elimination_rate - _t0_elimination_rate) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::elimination_rate", _ns_elimination_rate, _acc_elimination_rate)
    var _acc_clearance: Float64 = 0.0
    var _t0_clearance = perf_counter_ns()
    for _ in range(N):
        _acc_clearance += clearance(0.5, 0.5)
    var _t1_clearance = perf_counter_ns()
    var _ns_clearance = Float64(_t1_clearance - _t0_clearance) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::clearance", _ns_clearance, _acc_clearance)
    var _acc_bioavailability: Float64 = 0.0
    var _t0_bioavailability = perf_counter_ns()
    for _ in range(N):
        _acc_bioavailability += bioavailability(0.5, 0.5)
    var _t1_bioavailability = perf_counter_ns()
    var _ns_bioavailability = Float64(_t1_bioavailability - _t0_bioavailability) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::bioavailability", _ns_bioavailability, _acc_bioavailability)
    var _acc_loading_dose: Float64 = 0.0
    var _t0_loading_dose = perf_counter_ns()
    for _ in range(N):
        _acc_loading_dose += loading_dose(0.5, 0.5)
    var _t1_loading_dose = perf_counter_ns()
    var _ns_loading_dose = Float64(_t1_loading_dose - _t0_loading_dose) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::loading_dose", _ns_loading_dose, _acc_loading_dose)
    var _acc_maintenance_dose: Float64 = 0.0
    var _t0_maintenance_dose = perf_counter_ns()
    for _ in range(N):
        _acc_maintenance_dose += maintenance_dose(0.5, 0.5, 0.5)
    var _t1_maintenance_dose = perf_counter_ns()
    var _ns_maintenance_dose = Float64(_t1_maintenance_dose - _t0_maintenance_dose) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::maintenance_dose", _ns_maintenance_dose, _acc_maintenance_dose)
    var _acc_steady_state_concentration: Float64 = 0.0
    var _t0_steady_state_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_steady_state_concentration += steady_state_concentration(0.5, 0.5, 0.5)
    var _t1_steady_state_concentration = perf_counter_ns()
    var _ns_steady_state_concentration = Float64(_t1_steady_state_concentration - _t0_steady_state_concentration) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::steady_state_concentration", _ns_steady_state_concentration, _acc_steady_state_concentration)
    var _acc_time_to_peak: Float64 = 0.0
    var _t0_time_to_peak = perf_counter_ns()
    for _ in range(N):
        _acc_time_to_peak += time_to_peak(0.8, 0.2)
    var _t1_time_to_peak = perf_counter_ns()
    var _ns_time_to_peak = Float64(_t1_time_to_peak - _t0_time_to_peak) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::time_to_peak", _ns_time_to_peak, _acc_time_to_peak)
    var _acc_accumulation_factor: Float64 = 0.0
    var _t0_accumulation_factor = perf_counter_ns()
    for _ in range(N):
        _acc_accumulation_factor += accumulation_factor(0.5, 0.5)
    var _t1_accumulation_factor = perf_counter_ns()
    var _ns_accumulation_factor = Float64(_t1_accumulation_factor - _t0_accumulation_factor) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::accumulation_factor", _ns_accumulation_factor, _acc_accumulation_factor)
    var _acc_drug_auc_trapezoidal: Float64 = 0.0
    var _t0_drug_auc_trapezoidal = perf_counter_ns()
    for _ in range(N):
        _acc_drug_auc_trapezoidal += drug_auc_trapezoidal(0.5, 0.5, 0.5, 0.5)
    var _t1_drug_auc_trapezoidal = perf_counter_ns()
    var _ns_drug_auc_trapezoidal = Float64(_t1_drug_auc_trapezoidal - _t0_drug_auc_trapezoidal) / Float64(N)
    print("MOJO_TIMING pharmacokinetics::drug_auc_trapezoidal", _ns_drug_auc_trapezoidal, _acc_drug_auc_trapezoidal)
