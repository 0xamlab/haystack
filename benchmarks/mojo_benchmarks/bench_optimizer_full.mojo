"""bench_optimizer_full.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from optimizer_full import lbfgs_two_loop_scale, adadelta_update, nadam_update, sophia_hessian_clip, sophia_update, prodigy_d_estimate, adan_update, schedule_free_update, muon_orthogonal_update, gradient_centralization
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

    var _acc_lbfgs_two_loop_scale: Float64 = 0.0
    var _t0_lbfgs_two_loop_scale = perf_counter_ns()
    for _ in range(N):
        _acc_lbfgs_two_loop_scale += lbfgs_two_loop_scale(0.5, 0.5)
    var _t1_lbfgs_two_loop_scale = perf_counter_ns()
    var _ns_lbfgs_two_loop_scale = Float64(_t1_lbfgs_two_loop_scale - _t0_lbfgs_two_loop_scale) / Float64(N)
    print("MOJO_TIMING optimizer_full::lbfgs_two_loop_scale", _ns_lbfgs_two_loop_scale, _acc_lbfgs_two_loop_scale)
    var _acc_adadelta_update: Float64 = 0.0
    var _t0_adadelta_update = perf_counter_ns()
    for _ in range(N):
        _acc_adadelta_update += adadelta_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_adadelta_update = perf_counter_ns()
    var _ns_adadelta_update = Float64(_t1_adadelta_update - _t0_adadelta_update) / Float64(N)
    print("MOJO_TIMING optimizer_full::adadelta_update", _ns_adadelta_update, _acc_adadelta_update)
    var _acc_nadam_update: Float64 = 0.0
    var _t0_nadam_update = perf_counter_ns()
    for _ in range(N):
        _acc_nadam_update += nadam_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_nadam_update = perf_counter_ns()
    var _ns_nadam_update = Float64(_t1_nadam_update - _t0_nadam_update) / Float64(N)
    print("MOJO_TIMING optimizer_full::nadam_update", _ns_nadam_update, _acc_nadam_update)
    var _acc_sophia_hessian_clip: Float64 = 0.0
    var _t0_sophia_hessian_clip = perf_counter_ns()
    for _ in range(N):
        _acc_sophia_hessian_clip += sophia_hessian_clip(0.5, 0.5)
    var _t1_sophia_hessian_clip = perf_counter_ns()
    var _ns_sophia_hessian_clip = Float64(_t1_sophia_hessian_clip - _t0_sophia_hessian_clip) / Float64(N)
    print("MOJO_TIMING optimizer_full::sophia_hessian_clip", _ns_sophia_hessian_clip, _acc_sophia_hessian_clip)
    var _acc_sophia_update: Float64 = 0.0
    var _t0_sophia_update = perf_counter_ns()
    for _ in range(N):
        _acc_sophia_update += sophia_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_sophia_update = perf_counter_ns()
    var _ns_sophia_update = Float64(_t1_sophia_update - _t0_sophia_update) / Float64(N)
    print("MOJO_TIMING optimizer_full::sophia_update", _ns_sophia_update, _acc_sophia_update)
    var _acc_prodigy_d_estimate: Float64 = 0.0
    var _t0_prodigy_d_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_prodigy_d_estimate += prodigy_d_estimate(0.5, 0.5, 0.5, 0.5)
    var _t1_prodigy_d_estimate = perf_counter_ns()
    var _ns_prodigy_d_estimate = Float64(_t1_prodigy_d_estimate - _t0_prodigy_d_estimate) / Float64(N)
    print("MOJO_TIMING optimizer_full::prodigy_d_estimate", _ns_prodigy_d_estimate, _acc_prodigy_d_estimate)
    var _acc_adan_update: Float64 = 0.0
    var _t0_adan_update = perf_counter_ns()
    for _ in range(N):
        _acc_adan_update += adan_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_adan_update = perf_counter_ns()
    var _ns_adan_update = Float64(_t1_adan_update - _t0_adan_update) / Float64(N)
    print("MOJO_TIMING optimizer_full::adan_update", _ns_adan_update, _acc_adan_update)
    var _acc_schedule_free_update: Float64 = 0.0
    var _t0_schedule_free_update = perf_counter_ns()
    for _ in range(N):
        _acc_schedule_free_update += schedule_free_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_schedule_free_update = perf_counter_ns()
    var _ns_schedule_free_update = Float64(_t1_schedule_free_update - _t0_schedule_free_update) / Float64(N)
    print("MOJO_TIMING optimizer_full::schedule_free_update", _ns_schedule_free_update, _acc_schedule_free_update)
    var _acc_muon_orthogonal_update: Float64 = 0.0
    var _t0_muon_orthogonal_update = perf_counter_ns()
    for _ in range(N):
        _acc_muon_orthogonal_update += muon_orthogonal_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_muon_orthogonal_update = perf_counter_ns()
    var _ns_muon_orthogonal_update = Float64(_t1_muon_orthogonal_update - _t0_muon_orthogonal_update) / Float64(N)
    print("MOJO_TIMING optimizer_full::muon_orthogonal_update", _ns_muon_orthogonal_update, _acc_muon_orthogonal_update)
    var _acc_gradient_centralization: Float64 = 0.0
    var _t0_gradient_centralization = perf_counter_ns()
    for _ in range(N):
        _acc_gradient_centralization += gradient_centralization(0.5, 0.5)
    var _t1_gradient_centralization = perf_counter_ns()
    var _ns_gradient_centralization = Float64(_t1_gradient_centralization - _t0_gradient_centralization) / Float64(N)
    print("MOJO_TIMING optimizer_full::gradient_centralization", _ns_gradient_centralization, _acc_gradient_centralization)
