"""bench_loss_functions.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from loss_functions import binary_cross_entropy, categorical_cross_entropy, focal_loss, pow_approx, huber_loss, kl_divergence, contrastive_loss, triplet_loss, mse_loss, mae_loss, label_smoothing_loss
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

    var _acc_binary_cross_entropy: Float64 = 0.0
    var _t0_binary_cross_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_binary_cross_entropy += binary_cross_entropy(0.5, 0.5)
    var _t1_binary_cross_entropy = perf_counter_ns()
    var _ns_binary_cross_entropy = Float64(_t1_binary_cross_entropy - _t0_binary_cross_entropy) / Float64(N)
    print("MOJO_TIMING loss_functions::binary_cross_entropy", _ns_binary_cross_entropy, _acc_binary_cross_entropy)
    var _acc_categorical_cross_entropy: Float64 = 0.0
    var _t0_categorical_cross_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_categorical_cross_entropy += categorical_cross_entropy(0.5, 0.5)
    var _t1_categorical_cross_entropy = perf_counter_ns()
    var _ns_categorical_cross_entropy = Float64(_t1_categorical_cross_entropy - _t0_categorical_cross_entropy) / Float64(N)
    print("MOJO_TIMING loss_functions::categorical_cross_entropy", _ns_categorical_cross_entropy, _acc_categorical_cross_entropy)
    var _acc_focal_loss: Float64 = 0.0
    var _t0_focal_loss = perf_counter_ns()
    for _ in range(N):
        _acc_focal_loss += focal_loss(0.5, 0.5, 0.5, 0.5)
    var _t1_focal_loss = perf_counter_ns()
    var _ns_focal_loss = Float64(_t1_focal_loss - _t0_focal_loss) / Float64(N)
    print("MOJO_TIMING loss_functions::focal_loss", _ns_focal_loss, _acc_focal_loss)
    var _acc_pow_approx: Float64 = 0.0
    var _t0_pow_approx = perf_counter_ns()
    for _ in range(N):
        _acc_pow_approx += pow_approx(0.5, 0.5)
    var _t1_pow_approx = perf_counter_ns()
    var _ns_pow_approx = Float64(_t1_pow_approx - _t0_pow_approx) / Float64(N)
    print("MOJO_TIMING loss_functions::pow_approx", _ns_pow_approx, _acc_pow_approx)
    var _acc_huber_loss: Float64 = 0.0
    var _t0_huber_loss = perf_counter_ns()
    for _ in range(N):
        _acc_huber_loss += huber_loss(0.5, 0.5, 0.5)
    var _t1_huber_loss = perf_counter_ns()
    var _ns_huber_loss = Float64(_t1_huber_loss - _t0_huber_loss) / Float64(N)
    print("MOJO_TIMING loss_functions::huber_loss", _ns_huber_loss, _acc_huber_loss)
    var _acc_kl_divergence: Float64 = 0.0
    var _t0_kl_divergence = perf_counter_ns()
    for _ in range(N):
        _acc_kl_divergence += kl_divergence(0.5, 0.5)
    var _t1_kl_divergence = perf_counter_ns()
    var _ns_kl_divergence = Float64(_t1_kl_divergence - _t0_kl_divergence) / Float64(N)
    print("MOJO_TIMING loss_functions::kl_divergence", _ns_kl_divergence, _acc_kl_divergence)
    var _acc_contrastive_loss: Float64 = 0.0
    var _t0_contrastive_loss = perf_counter_ns()
    for _ in range(N):
        _acc_contrastive_loss += contrastive_loss(0.5, 0.5, 0.5)
    var _t1_contrastive_loss = perf_counter_ns()
    var _ns_contrastive_loss = Float64(_t1_contrastive_loss - _t0_contrastive_loss) / Float64(N)
    print("MOJO_TIMING loss_functions::contrastive_loss", _ns_contrastive_loss, _acc_contrastive_loss)
    var _acc_triplet_loss: Float64 = 0.0
    var _t0_triplet_loss = perf_counter_ns()
    for _ in range(N):
        _acc_triplet_loss += triplet_loss(0.5, 0.5, 0.5)
    var _t1_triplet_loss = perf_counter_ns()
    var _ns_triplet_loss = Float64(_t1_triplet_loss - _t0_triplet_loss) / Float64(N)
    print("MOJO_TIMING loss_functions::triplet_loss", _ns_triplet_loss, _acc_triplet_loss)
    var _acc_mse_loss: Float64 = 0.0
    var _t0_mse_loss = perf_counter_ns()
    for _ in range(N):
        _acc_mse_loss += mse_loss(0.5, 0.5)
    var _t1_mse_loss = perf_counter_ns()
    var _ns_mse_loss = Float64(_t1_mse_loss - _t0_mse_loss) / Float64(N)
    print("MOJO_TIMING loss_functions::mse_loss", _ns_mse_loss, _acc_mse_loss)
    var _acc_mae_loss: Float64 = 0.0
    var _t0_mae_loss = perf_counter_ns()
    for _ in range(N):
        _acc_mae_loss += mae_loss(0.5, 0.5)
    var _t1_mae_loss = perf_counter_ns()
    var _ns_mae_loss = Float64(_t1_mae_loss - _t0_mae_loss) / Float64(N)
    print("MOJO_TIMING loss_functions::mae_loss", _ns_mae_loss, _acc_mae_loss)
    var _acc_label_smoothing_loss: Float64 = 0.0
    var _t0_label_smoothing_loss = perf_counter_ns()
    for _ in range(N):
        _acc_label_smoothing_loss += label_smoothing_loss(0.5, 0.5, 0.5, 0.5)
    var _t1_label_smoothing_loss = perf_counter_ns()
    var _ns_label_smoothing_loss = Float64(_t1_label_smoothing_loss - _t0_label_smoothing_loss) / Float64(N)
    print("MOJO_TIMING loss_functions::label_smoothing_loss", _ns_label_smoothing_loss, _acc_label_smoothing_loss)
