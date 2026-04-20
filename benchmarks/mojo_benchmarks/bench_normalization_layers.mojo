"""bench_normalization_layers.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from normalization_layers import layer_norm, rms_norm, batch_norm_inference, group_norm_scale, instance_norm, weight_norm_magnitude, spectral_norm_estimate, adaptive_layer_norm, deep_norm_alpha, pre_norm_residual
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

    var _acc_layer_norm: Float64 = 0.0
    var _t0_layer_norm = perf_counter_ns()
    for _ in range(N):
        _acc_layer_norm += layer_norm(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_layer_norm = perf_counter_ns()
    var _ns_layer_norm = Float64(_t1_layer_norm - _t0_layer_norm) / Float64(N)
    print("MOJO_TIMING normalization_layers::layer_norm", _ns_layer_norm, _acc_layer_norm)
    var _acc_rms_norm: Float64 = 0.0
    var _t0_rms_norm = perf_counter_ns()
    for _ in range(N):
        _acc_rms_norm += rms_norm(0.5, 0.5, 0.5, 0.5)
    var _t1_rms_norm = perf_counter_ns()
    var _ns_rms_norm = Float64(_t1_rms_norm - _t0_rms_norm) / Float64(N)
    print("MOJO_TIMING normalization_layers::rms_norm", _ns_rms_norm, _acc_rms_norm)
    var _acc_batch_norm_inference: Float64 = 0.0
    var _t0_batch_norm_inference = perf_counter_ns()
    for _ in range(N):
        _acc_batch_norm_inference += batch_norm_inference(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_batch_norm_inference = perf_counter_ns()
    var _ns_batch_norm_inference = Float64(_t1_batch_norm_inference - _t0_batch_norm_inference) / Float64(N)
    print("MOJO_TIMING normalization_layers::batch_norm_inference", _ns_batch_norm_inference, _acc_batch_norm_inference)
    var _acc_group_norm_scale: Float64 = 0.0
    var _t0_group_norm_scale = perf_counter_ns()
    for _ in range(N):
        _acc_group_norm_scale += group_norm_scale(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_group_norm_scale = perf_counter_ns()
    var _ns_group_norm_scale = Float64(_t1_group_norm_scale - _t0_group_norm_scale) / Float64(N)
    print("MOJO_TIMING normalization_layers::group_norm_scale", _ns_group_norm_scale, _acc_group_norm_scale)
    var _acc_instance_norm: Float64 = 0.0
    var _t0_instance_norm = perf_counter_ns()
    for _ in range(N):
        _acc_instance_norm += instance_norm(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_instance_norm = perf_counter_ns()
    var _ns_instance_norm = Float64(_t1_instance_norm - _t0_instance_norm) / Float64(N)
    print("MOJO_TIMING normalization_layers::instance_norm", _ns_instance_norm, _acc_instance_norm)
    var _acc_weight_norm_magnitude: Float64 = 0.0
    var _t0_weight_norm_magnitude = perf_counter_ns()
    for _ in range(N):
        _acc_weight_norm_magnitude += weight_norm_magnitude(0.5, 0.5)
    var _t1_weight_norm_magnitude = perf_counter_ns()
    var _ns_weight_norm_magnitude = Float64(_t1_weight_norm_magnitude - _t0_weight_norm_magnitude) / Float64(N)
    print("MOJO_TIMING normalization_layers::weight_norm_magnitude", _ns_weight_norm_magnitude, _acc_weight_norm_magnitude)
    var _acc_spectral_norm_estimate: Float64 = 0.0
    var _t0_spectral_norm_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_spectral_norm_estimate += spectral_norm_estimate(0.5, 0.5)
    var _t1_spectral_norm_estimate = perf_counter_ns()
    var _ns_spectral_norm_estimate = Float64(_t1_spectral_norm_estimate - _t0_spectral_norm_estimate) / Float64(N)
    print("MOJO_TIMING normalization_layers::spectral_norm_estimate", _ns_spectral_norm_estimate, _acc_spectral_norm_estimate)
    var _acc_adaptive_layer_norm: Float64 = 0.0
    var _t0_adaptive_layer_norm = perf_counter_ns()
    for _ in range(N):
        _acc_adaptive_layer_norm += adaptive_layer_norm(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_adaptive_layer_norm = perf_counter_ns()
    var _ns_adaptive_layer_norm = Float64(_t1_adaptive_layer_norm - _t0_adaptive_layer_norm) / Float64(N)
    print("MOJO_TIMING normalization_layers::adaptive_layer_norm", _ns_adaptive_layer_norm, _acc_adaptive_layer_norm)
    var _acc_deep_norm_alpha: Float64 = 0.0
    var _t0_deep_norm_alpha = perf_counter_ns()
    for _ in range(N):
        _acc_deep_norm_alpha += deep_norm_alpha(0.5)
    var _t1_deep_norm_alpha = perf_counter_ns()
    var _ns_deep_norm_alpha = Float64(_t1_deep_norm_alpha - _t0_deep_norm_alpha) / Float64(N)
    print("MOJO_TIMING normalization_layers::deep_norm_alpha", _ns_deep_norm_alpha, _acc_deep_norm_alpha)
    var _acc_pre_norm_residual: Float64 = 0.0
    var _t0_pre_norm_residual = perf_counter_ns()
    for _ in range(N):
        _acc_pre_norm_residual += pre_norm_residual(0.5, 0.5)
    var _t1_pre_norm_residual = perf_counter_ns()
    var _ns_pre_norm_residual = Float64(_t1_pre_norm_residual - _t0_pre_norm_residual) / Float64(N)
    print("MOJO_TIMING normalization_layers::pre_norm_residual", _ns_pre_norm_residual, _acc_pre_norm_residual)
