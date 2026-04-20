"""bench_nn_layers.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from nn_layers import dense_forward, relu, sigmoid_activation, tanh_activation, softmax_layer, mse_loss, cross_entropy_loss, dropout, batch_norm, leaky_relu, init_weights_xavier
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

    var _acc_dense_forward: Float64 = 0.0
    var _t0_dense_forward = perf_counter_ns()
    for _ in range(N):
        var _r_dense_forward = dense_forward(_lf5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
        _acc_dense_forward += Float64(len(_r_dense_forward))
    var _t1_dense_forward = perf_counter_ns()
    var _ns_dense_forward = Float64(_t1_dense_forward - _t0_dense_forward) / Float64(N)
    print("MOJO_TIMING nn_layers::dense_forward", _ns_dense_forward, _acc_dense_forward)
    var _acc_relu: Float64 = 0.0
    var _t0_relu = perf_counter_ns()
    for _ in range(N):
        var _r_relu = relu(_lf5)
        _acc_relu += Float64(len(_r_relu))
    var _t1_relu = perf_counter_ns()
    var _ns_relu = Float64(_t1_relu - _t0_relu) / Float64(N)
    print("MOJO_TIMING nn_layers::relu", _ns_relu, _acc_relu)
    var _acc_sigmoid_activation: Float64 = 0.0
    var _t0_sigmoid_activation = perf_counter_ns()
    for _ in range(N):
        var _r_sigmoid_activation = sigmoid_activation(_lf5)
        _acc_sigmoid_activation += Float64(len(_r_sigmoid_activation))
    var _t1_sigmoid_activation = perf_counter_ns()
    var _ns_sigmoid_activation = Float64(_t1_sigmoid_activation - _t0_sigmoid_activation) / Float64(N)
    print("MOJO_TIMING nn_layers::sigmoid_activation", _ns_sigmoid_activation, _acc_sigmoid_activation)
    var _acc_tanh_activation: Float64 = 0.0
    var _t0_tanh_activation = perf_counter_ns()
    for _ in range(N):
        var _r_tanh_activation = tanh_activation(_lf5)
        _acc_tanh_activation += Float64(len(_r_tanh_activation))
    var _t1_tanh_activation = perf_counter_ns()
    var _ns_tanh_activation = Float64(_t1_tanh_activation - _t0_tanh_activation) / Float64(N)
    print("MOJO_TIMING nn_layers::tanh_activation", _ns_tanh_activation, _acc_tanh_activation)
    var _acc_softmax_layer: Float64 = 0.0
    var _t0_softmax_layer = perf_counter_ns()
    for _ in range(N):
        var _r_softmax_layer = softmax_layer(_lf5)
        _acc_softmax_layer += Float64(len(_r_softmax_layer))
    var _t1_softmax_layer = perf_counter_ns()
    var _ns_softmax_layer = Float64(_t1_softmax_layer - _t0_softmax_layer) / Float64(N)
    print("MOJO_TIMING nn_layers::softmax_layer", _ns_softmax_layer, _acc_softmax_layer)
    var _acc_mse_loss: Float64 = 0.0
    var _t0_mse_loss = perf_counter_ns()
    for _ in range(N):
        _acc_mse_loss += mse_loss(_lf5, _lf5)
    var _t1_mse_loss = perf_counter_ns()
    var _ns_mse_loss = Float64(_t1_mse_loss - _t0_mse_loss) / Float64(N)
    print("MOJO_TIMING nn_layers::mse_loss", _ns_mse_loss, _acc_mse_loss)
    var _acc_cross_entropy_loss: Float64 = 0.0
    var _t0_cross_entropy_loss = perf_counter_ns()
    for _ in range(N):
        _acc_cross_entropy_loss += cross_entropy_loss(_lf5, _lf5)
    var _t1_cross_entropy_loss = perf_counter_ns()
    var _ns_cross_entropy_loss = Float64(_t1_cross_entropy_loss - _t0_cross_entropy_loss) / Float64(N)
    print("MOJO_TIMING nn_layers::cross_entropy_loss", _ns_cross_entropy_loss, _acc_cross_entropy_loss)
    var _acc_dropout: Float64 = 0.0
    var _t0_dropout = perf_counter_ns()
    for _ in range(N):
        var _r_dropout = dropout(_lf5, 0.5)
        _acc_dropout += Float64(len(_r_dropout))
    var _t1_dropout = perf_counter_ns()
    var _ns_dropout = Float64(_t1_dropout - _t0_dropout) / Float64(N)
    print("MOJO_TIMING nn_layers::dropout", _ns_dropout, _acc_dropout)
    var _acc_batch_norm: Float64 = 0.0
    var _t0_batch_norm = perf_counter_ns()
    for _ in range(N):
        var _r_batch_norm = batch_norm(_lf5, 0.5, 0.5)
        _acc_batch_norm += Float64(len(_r_batch_norm))
    var _t1_batch_norm = perf_counter_ns()
    var _ns_batch_norm = Float64(_t1_batch_norm - _t0_batch_norm) / Float64(N)
    print("MOJO_TIMING nn_layers::batch_norm", _ns_batch_norm, _acc_batch_norm)
    var _acc_leaky_relu: Float64 = 0.0
    var _t0_leaky_relu = perf_counter_ns()
    for _ in range(N):
        var _r_leaky_relu = leaky_relu(_lf5, 0.5)
        _acc_leaky_relu += Float64(len(_r_leaky_relu))
    var _t1_leaky_relu = perf_counter_ns()
    var _ns_leaky_relu = Float64(_t1_leaky_relu - _t0_leaky_relu) / Float64(N)
    print("MOJO_TIMING nn_layers::leaky_relu", _ns_leaky_relu, _acc_leaky_relu)
    var _acc_init_weights_xavier: Float64 = 0.0
    var _t0_init_weights_xavier = perf_counter_ns()
    for _ in range(N):
        var _r_init_weights_xavier = init_weights_xavier(5, 5)
        _acc_init_weights_xavier += Float64(len(_r_init_weights_xavier))
    var _t1_init_weights_xavier = perf_counter_ns()
    var _ns_init_weights_xavier = Float64(_t1_init_weights_xavier - _t0_init_weights_xavier) / Float64(N)
    print("MOJO_TIMING nn_layers::init_weights_xavier", _ns_init_weights_xavier, _acc_init_weights_xavier)
