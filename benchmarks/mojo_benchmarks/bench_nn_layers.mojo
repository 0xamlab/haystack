"""bench_nn_layers.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from nn_layers import dense_forward, relu, sigmoid_activation, tanh_activation, softmax_layer, mse_loss, cross_entropy_loss, dropout, batch_norm, leaky_relu, init_weights_xavier
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_dense_forward = dense_forward(_lf5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], _lf5)
    var _summary_dense_forward = _summary_list_float64(_result_dense_forward)
    print("MOJO_RESULT nn_layers::dense_forward", _summary_dense_forward)
    var _acc_relu: Float64 = 0.0
    var _t0_relu = perf_counter_ns()
    for _ in range(N):
        var _r_relu = relu(_lf5)
        _acc_relu += Float64(len(_r_relu))
    var _t1_relu = perf_counter_ns()
    var _ns_relu = Float64(_t1_relu - _t0_relu) / Float64(N)
    print("MOJO_TIMING nn_layers::relu", _ns_relu, _acc_relu)
    var _result_relu = relu(_lf5)
    var _summary_relu = _summary_list_float64(_result_relu)
    print("MOJO_RESULT nn_layers::relu", _summary_relu)
    var _acc_sigmoid_activation: Float64 = 0.0
    var _t0_sigmoid_activation = perf_counter_ns()
    for _ in range(N):
        var _r_sigmoid_activation = sigmoid_activation(_lf5)
        _acc_sigmoid_activation += Float64(len(_r_sigmoid_activation))
    var _t1_sigmoid_activation = perf_counter_ns()
    var _ns_sigmoid_activation = Float64(_t1_sigmoid_activation - _t0_sigmoid_activation) / Float64(N)
    print("MOJO_TIMING nn_layers::sigmoid_activation", _ns_sigmoid_activation, _acc_sigmoid_activation)
    var _result_sigmoid_activation = sigmoid_activation(_lf5)
    var _summary_sigmoid_activation = _summary_list_float64(_result_sigmoid_activation)
    print("MOJO_RESULT nn_layers::sigmoid_activation", _summary_sigmoid_activation)
    var _acc_tanh_activation: Float64 = 0.0
    var _t0_tanh_activation = perf_counter_ns()
    for _ in range(N):
        var _r_tanh_activation = tanh_activation(_lf5)
        _acc_tanh_activation += Float64(len(_r_tanh_activation))
    var _t1_tanh_activation = perf_counter_ns()
    var _ns_tanh_activation = Float64(_t1_tanh_activation - _t0_tanh_activation) / Float64(N)
    print("MOJO_TIMING nn_layers::tanh_activation", _ns_tanh_activation, _acc_tanh_activation)
    var _result_tanh_activation = tanh_activation(_lf5)
    var _summary_tanh_activation = _summary_list_float64(_result_tanh_activation)
    print("MOJO_RESULT nn_layers::tanh_activation", _summary_tanh_activation)
    var _acc_softmax_layer: Float64 = 0.0
    var _t0_softmax_layer = perf_counter_ns()
    for _ in range(N):
        var _r_softmax_layer = softmax_layer(_lf5)
        _acc_softmax_layer += Float64(len(_r_softmax_layer))
    var _t1_softmax_layer = perf_counter_ns()
    var _ns_softmax_layer = Float64(_t1_softmax_layer - _t0_softmax_layer) / Float64(N)
    print("MOJO_TIMING nn_layers::softmax_layer", _ns_softmax_layer, _acc_softmax_layer)
    var _result_softmax_layer = softmax_layer(_lf5)
    var _summary_softmax_layer = _summary_list_float64(_result_softmax_layer)
    print("MOJO_RESULT nn_layers::softmax_layer", _summary_softmax_layer)
    var _acc_mse_loss: Float64 = 0.0
    var _t0_mse_loss = perf_counter_ns()
    for _ in range(N):
        _acc_mse_loss += mse_loss(_lf5, _lf5)
    var _t1_mse_loss = perf_counter_ns()
    var _ns_mse_loss = Float64(_t1_mse_loss - _t0_mse_loss) / Float64(N)
    print("MOJO_TIMING nn_layers::mse_loss", _ns_mse_loss, _acc_mse_loss)
    var _result_mse_loss = mse_loss(_lf5, _lf5)
    var _summary_mse_loss = _summary_float64(_result_mse_loss)
    print("MOJO_RESULT nn_layers::mse_loss", _summary_mse_loss)
    var _acc_cross_entropy_loss: Float64 = 0.0
    var _t0_cross_entropy_loss = perf_counter_ns()
    for _ in range(N):
        _acc_cross_entropy_loss += cross_entropy_loss(_lf5, _lf5)
    var _t1_cross_entropy_loss = perf_counter_ns()
    var _ns_cross_entropy_loss = Float64(_t1_cross_entropy_loss - _t0_cross_entropy_loss) / Float64(N)
    print("MOJO_TIMING nn_layers::cross_entropy_loss", _ns_cross_entropy_loss, _acc_cross_entropy_loss)
    var _result_cross_entropy_loss = cross_entropy_loss(_lf5, _lf5)
    var _summary_cross_entropy_loss = _summary_float64(_result_cross_entropy_loss)
    print("MOJO_RESULT nn_layers::cross_entropy_loss", _summary_cross_entropy_loss)
    var _acc_dropout: Float64 = 0.0
    var _t0_dropout = perf_counter_ns()
    for _ in range(N):
        var _r_dropout = dropout(_lf5, 0.5)
        _acc_dropout += Float64(len(_r_dropout))
    var _t1_dropout = perf_counter_ns()
    var _ns_dropout = Float64(_t1_dropout - _t0_dropout) / Float64(N)
    print("MOJO_TIMING nn_layers::dropout", _ns_dropout, _acc_dropout)
    var _result_dropout = dropout(_lf5, 0.5)
    var _summary_dropout = _summary_list_float64(_result_dropout)
    print("MOJO_RESULT nn_layers::dropout", _summary_dropout)
    var _acc_batch_norm: Float64 = 0.0
    var _t0_batch_norm = perf_counter_ns()
    for _ in range(N):
        var _r_batch_norm = batch_norm(_lf5, 0.5, 0.5)
        _acc_batch_norm += Float64(len(_r_batch_norm))
    var _t1_batch_norm = perf_counter_ns()
    var _ns_batch_norm = Float64(_t1_batch_norm - _t0_batch_norm) / Float64(N)
    print("MOJO_TIMING nn_layers::batch_norm", _ns_batch_norm, _acc_batch_norm)
    var _result_batch_norm = batch_norm(_lf5, 0.5, 0.5)
    var _summary_batch_norm = _summary_list_float64(_result_batch_norm)
    print("MOJO_RESULT nn_layers::batch_norm", _summary_batch_norm)
    var _acc_leaky_relu: Float64 = 0.0
    var _t0_leaky_relu = perf_counter_ns()
    for _ in range(N):
        var _r_leaky_relu = leaky_relu(_lf5, 0.5)
        _acc_leaky_relu += Float64(len(_r_leaky_relu))
    var _t1_leaky_relu = perf_counter_ns()
    var _ns_leaky_relu = Float64(_t1_leaky_relu - _t0_leaky_relu) / Float64(N)
    print("MOJO_TIMING nn_layers::leaky_relu", _ns_leaky_relu, _acc_leaky_relu)
    var _result_leaky_relu = leaky_relu(_lf5, 0.5)
    var _summary_leaky_relu = _summary_list_float64(_result_leaky_relu)
    print("MOJO_RESULT nn_layers::leaky_relu", _summary_leaky_relu)
    var _acc_init_weights_xavier: Float64 = 0.0
    var _t0_init_weights_xavier = perf_counter_ns()
    for _ in range(N):
        var _r_init_weights_xavier = init_weights_xavier(5, 5)
        _acc_init_weights_xavier += Float64(len(_r_init_weights_xavier))
    var _t1_init_weights_xavier = perf_counter_ns()
    var _ns_init_weights_xavier = Float64(_t1_init_weights_xavier - _t0_init_weights_xavier) / Float64(N)
    print("MOJO_TIMING nn_layers::init_weights_xavier", _ns_init_weights_xavier, _acc_init_weights_xavier)
    var _result_init_weights_xavier = init_weights_xavier(5, 5)
    var _summary_init_weights_xavier = _summary_list_list_float64(_result_init_weights_xavier)
    print("MOJO_RESULT nn_layers::init_weights_xavier", _summary_init_weights_xavier)
