"""bench_psychometrics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from psychometrics import item_difficulty, item_discrimination, point_biserial, kuder_richardson_20, cronbach_alpha, spearman_brown_prophecy, standard_error_of_measurement, z_score, t_score, stanine, irt_1pl_probability, irt_2pl_probability
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

    var _acc_item_difficulty: Float64 = 0.0
    var _t0_item_difficulty = perf_counter_ns()
    for _ in range(N):
        _acc_item_difficulty += item_difficulty(0.5, 0.5)
    var _t1_item_difficulty = perf_counter_ns()
    var _ns_item_difficulty = Float64(_t1_item_difficulty - _t0_item_difficulty) / Float64(N)
    print("MOJO_TIMING psychometrics::item_difficulty", _ns_item_difficulty, _acc_item_difficulty)
    var _acc_item_discrimination: Float64 = 0.0
    var _t0_item_discrimination = perf_counter_ns()
    for _ in range(N):
        _acc_item_discrimination += item_discrimination(0.5, 0.5, 0.5, 0.5)
    var _t1_item_discrimination = perf_counter_ns()
    var _ns_item_discrimination = Float64(_t1_item_discrimination - _t0_item_discrimination) / Float64(N)
    print("MOJO_TIMING psychometrics::item_discrimination", _ns_item_discrimination, _acc_item_discrimination)
    var _acc_point_biserial: Float64 = 0.0
    var _t0_point_biserial = perf_counter_ns()
    for _ in range(N):
        _acc_point_biserial += point_biserial(0.5, 0.5, 0.5, 0.5)
    var _t1_point_biserial = perf_counter_ns()
    var _ns_point_biserial = Float64(_t1_point_biserial - _t0_point_biserial) / Float64(N)
    print("MOJO_TIMING psychometrics::point_biserial", _ns_point_biserial, _acc_point_biserial)
    var _acc_kuder_richardson_20: Float64 = 0.0
    var _t0_kuder_richardson_20 = perf_counter_ns()
    for _ in range(N):
        _acc_kuder_richardson_20 += kuder_richardson_20(0.5, 0.5, 0.5)
    var _t1_kuder_richardson_20 = perf_counter_ns()
    var _ns_kuder_richardson_20 = Float64(_t1_kuder_richardson_20 - _t0_kuder_richardson_20) / Float64(N)
    print("MOJO_TIMING psychometrics::kuder_richardson_20", _ns_kuder_richardson_20, _acc_kuder_richardson_20)
    var _acc_cronbach_alpha: Float64 = 0.0
    var _t0_cronbach_alpha = perf_counter_ns()
    for _ in range(N):
        _acc_cronbach_alpha += cronbach_alpha(0.5, 0.5, 0.5)
    var _t1_cronbach_alpha = perf_counter_ns()
    var _ns_cronbach_alpha = Float64(_t1_cronbach_alpha - _t0_cronbach_alpha) / Float64(N)
    print("MOJO_TIMING psychometrics::cronbach_alpha", _ns_cronbach_alpha, _acc_cronbach_alpha)
    var _acc_spearman_brown_prophecy: Float64 = 0.0
    var _t0_spearman_brown_prophecy = perf_counter_ns()
    for _ in range(N):
        _acc_spearman_brown_prophecy += spearman_brown_prophecy(0.5, 0.5)
    var _t1_spearman_brown_prophecy = perf_counter_ns()
    var _ns_spearman_brown_prophecy = Float64(_t1_spearman_brown_prophecy - _t0_spearman_brown_prophecy) / Float64(N)
    print("MOJO_TIMING psychometrics::spearman_brown_prophecy", _ns_spearman_brown_prophecy, _acc_spearman_brown_prophecy)
    var _acc_standard_error_of_measurement: Float64 = 0.0
    var _t0_standard_error_of_measurement = perf_counter_ns()
    for _ in range(N):
        _acc_standard_error_of_measurement += standard_error_of_measurement(0.5, 0.5)
    var _t1_standard_error_of_measurement = perf_counter_ns()
    var _ns_standard_error_of_measurement = Float64(_t1_standard_error_of_measurement - _t0_standard_error_of_measurement) / Float64(N)
    print("MOJO_TIMING psychometrics::standard_error_of_measurement", _ns_standard_error_of_measurement, _acc_standard_error_of_measurement)
    var _acc_z_score: Float64 = 0.0
    var _t0_z_score = perf_counter_ns()
    for _ in range(N):
        _acc_z_score += z_score(0.5, 0.5, 0.5)
    var _t1_z_score = perf_counter_ns()
    var _ns_z_score = Float64(_t1_z_score - _t0_z_score) / Float64(N)
    print("MOJO_TIMING psychometrics::z_score", _ns_z_score, _acc_z_score)
    var _acc_t_score: Float64 = 0.0
    var _t0_t_score = perf_counter_ns()
    for _ in range(N):
        _acc_t_score += t_score(0.5)
    var _t1_t_score = perf_counter_ns()
    var _ns_t_score = Float64(_t1_t_score - _t0_t_score) / Float64(N)
    print("MOJO_TIMING psychometrics::t_score", _ns_t_score, _acc_t_score)
    var _acc_stanine: Float64 = 0.0
    var _t0_stanine = perf_counter_ns()
    for _ in range(N):
        _acc_stanine += Float64(stanine(0.5))
    var _t1_stanine = perf_counter_ns()
    var _ns_stanine = Float64(_t1_stanine - _t0_stanine) / Float64(N)
    print("MOJO_TIMING psychometrics::stanine", _ns_stanine, _acc_stanine)
    var _acc_irt_1pl_probability: Float64 = 0.0
    var _t0_irt_1pl_probability = perf_counter_ns()
    for _ in range(N):
        _acc_irt_1pl_probability += irt_1pl_probability(0.5, 0.5)
    var _t1_irt_1pl_probability = perf_counter_ns()
    var _ns_irt_1pl_probability = Float64(_t1_irt_1pl_probability - _t0_irt_1pl_probability) / Float64(N)
    print("MOJO_TIMING psychometrics::irt_1pl_probability", _ns_irt_1pl_probability, _acc_irt_1pl_probability)
    var _acc_irt_2pl_probability: Float64 = 0.0
    var _t0_irt_2pl_probability = perf_counter_ns()
    for _ in range(N):
        _acc_irt_2pl_probability += irt_2pl_probability(0.5, 0.5, 0.5)
    var _t1_irt_2pl_probability = perf_counter_ns()
    var _ns_irt_2pl_probability = Float64(_t1_irt_2pl_probability - _t0_irt_2pl_probability) / Float64(N)
    print("MOJO_TIMING psychometrics::irt_2pl_probability", _ns_irt_2pl_probability, _acc_irt_2pl_probability)
