"""bench_dosimetry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from dosimetry import absorbed_dose, equivalent_dose, effective_dose, dose_rate, activity_decay, specific_activity, tenth_value_layer, buildup_factor, kerma, radiation_weighting
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

    var _acc_absorbed_dose: Float64 = 0.0
    var _t0_absorbed_dose = perf_counter_ns()
    for _ in range(N):
        _acc_absorbed_dose += absorbed_dose(0.5, 0.5)
    var _t1_absorbed_dose = perf_counter_ns()
    var _ns_absorbed_dose = Float64(_t1_absorbed_dose - _t0_absorbed_dose) / Float64(N)
    print("MOJO_TIMING dosimetry::absorbed_dose", _ns_absorbed_dose, _acc_absorbed_dose)
    var _acc_equivalent_dose: Float64 = 0.0
    var _t0_equivalent_dose = perf_counter_ns()
    for _ in range(N):
        _acc_equivalent_dose += equivalent_dose(0.5, 0.5)
    var _t1_equivalent_dose = perf_counter_ns()
    var _ns_equivalent_dose = Float64(_t1_equivalent_dose - _t0_equivalent_dose) / Float64(N)
    print("MOJO_TIMING dosimetry::equivalent_dose", _ns_equivalent_dose, _acc_equivalent_dose)
    var _acc_effective_dose: Float64 = 0.0
    var _t0_effective_dose = perf_counter_ns()
    for _ in range(N):
        _acc_effective_dose += effective_dose(0.5, 0.5)
    var _t1_effective_dose = perf_counter_ns()
    var _ns_effective_dose = Float64(_t1_effective_dose - _t0_effective_dose) / Float64(N)
    print("MOJO_TIMING dosimetry::effective_dose", _ns_effective_dose, _acc_effective_dose)
    var _acc_dose_rate: Float64 = 0.0
    var _t0_dose_rate = perf_counter_ns()
    for _ in range(N):
        _acc_dose_rate += dose_rate(0.5, 0.5, 0.5)
    var _t1_dose_rate = perf_counter_ns()
    var _ns_dose_rate = Float64(_t1_dose_rate - _t0_dose_rate) / Float64(N)
    print("MOJO_TIMING dosimetry::dose_rate", _ns_dose_rate, _acc_dose_rate)
    var _acc_activity_decay: Float64 = 0.0
    var _t0_activity_decay = perf_counter_ns()
    for _ in range(N):
        _acc_activity_decay += activity_decay(0.5, 0.5, 0.5)
    var _t1_activity_decay = perf_counter_ns()
    var _ns_activity_decay = Float64(_t1_activity_decay - _t0_activity_decay) / Float64(N)
    print("MOJO_TIMING dosimetry::activity_decay", _ns_activity_decay, _acc_activity_decay)
    var _acc_specific_activity: Float64 = 0.0
    var _t0_specific_activity = perf_counter_ns()
    for _ in range(N):
        _acc_specific_activity += specific_activity(0.5, 0.5)
    var _t1_specific_activity = perf_counter_ns()
    var _ns_specific_activity = Float64(_t1_specific_activity - _t0_specific_activity) / Float64(N)
    print("MOJO_TIMING dosimetry::specific_activity", _ns_specific_activity, _acc_specific_activity)
    var _acc_tenth_value_layer: Float64 = 0.0
    var _t0_tenth_value_layer = perf_counter_ns()
    for _ in range(N):
        _acc_tenth_value_layer += tenth_value_layer(0.5)
    var _t1_tenth_value_layer = perf_counter_ns()
    var _ns_tenth_value_layer = Float64(_t1_tenth_value_layer - _t0_tenth_value_layer) / Float64(N)
    print("MOJO_TIMING dosimetry::tenth_value_layer", _ns_tenth_value_layer, _acc_tenth_value_layer)
    var _acc_buildup_factor: Float64 = 0.0
    var _t0_buildup_factor = perf_counter_ns()
    for _ in range(N):
        _acc_buildup_factor += buildup_factor(0.5, 0.5, 0.5)
    var _t1_buildup_factor = perf_counter_ns()
    var _ns_buildup_factor = Float64(_t1_buildup_factor - _t0_buildup_factor) / Float64(N)
    print("MOJO_TIMING dosimetry::buildup_factor", _ns_buildup_factor, _acc_buildup_factor)
    var _acc_kerma: Float64 = 0.0
    var _t0_kerma = perf_counter_ns()
    for _ in range(N):
        _acc_kerma += kerma(0.5, 0.5)
    var _t1_kerma = perf_counter_ns()
    var _ns_kerma = Float64(_t1_kerma - _t0_kerma) / Float64(N)
    print("MOJO_TIMING dosimetry::kerma", _ns_kerma, _acc_kerma)
    var _acc_radiation_weighting: Float64 = 0.0
    var _t0_radiation_weighting = perf_counter_ns()
    for _ in range(N):
        _acc_radiation_weighting += radiation_weighting(0.5)
    var _t1_radiation_weighting = perf_counter_ns()
    var _ns_radiation_weighting = Float64(_t1_radiation_weighting - _t0_radiation_weighting) / Float64(N)
    print("MOJO_TIMING dosimetry::radiation_weighting", _ns_radiation_weighting, _acc_radiation_weighting)
