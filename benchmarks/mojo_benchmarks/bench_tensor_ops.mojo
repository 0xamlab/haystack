"""bench_tensor_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from tensor_ops import matmul_element, broadcast_index, stride_from_shape, flatten_index, unflatten_index_dim, transpose_index, outer_product_element, tensor_norm_contribution, softmax_stable_element, tensor_dot_contribution
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

    var _acc_matmul_element: Float64 = 0.0
    var _t0_matmul_element = perf_counter_ns()
    for _ in range(N):
        _acc_matmul_element += matmul_element(0.5, 0.5)
    var _t1_matmul_element = perf_counter_ns()
    var _ns_matmul_element = Float64(_t1_matmul_element - _t0_matmul_element) / Float64(N)
    print("MOJO_TIMING tensor_ops::matmul_element", _ns_matmul_element, _acc_matmul_element)
    var _result_matmul_element = matmul_element(0.5, 0.5)
    var _summary_matmul_element = _summary_float64(_result_matmul_element)
    print("MOJO_RESULT tensor_ops::matmul_element", _summary_matmul_element)
    var _acc_broadcast_index: Float64 = 0.0
    var _t0_broadcast_index = perf_counter_ns()
    for _ in range(N):
        _acc_broadcast_index += broadcast_index(0.5, 0.5)
    var _t1_broadcast_index = perf_counter_ns()
    var _ns_broadcast_index = Float64(_t1_broadcast_index - _t0_broadcast_index) / Float64(N)
    print("MOJO_TIMING tensor_ops::broadcast_index", _ns_broadcast_index, _acc_broadcast_index)
    var _result_broadcast_index = broadcast_index(0.5, 0.5)
    var _summary_broadcast_index = _summary_float64(_result_broadcast_index)
    print("MOJO_RESULT tensor_ops::broadcast_index", _summary_broadcast_index)
    var _acc_stride_from_shape: Float64 = 0.0
    var _t0_stride_from_shape = perf_counter_ns()
    for _ in range(N):
        _acc_stride_from_shape += stride_from_shape(0.5, 0.5)
    var _t1_stride_from_shape = perf_counter_ns()
    var _ns_stride_from_shape = Float64(_t1_stride_from_shape - _t0_stride_from_shape) / Float64(N)
    print("MOJO_TIMING tensor_ops::stride_from_shape", _ns_stride_from_shape, _acc_stride_from_shape)
    var _result_stride_from_shape = stride_from_shape(0.5, 0.5)
    var _summary_stride_from_shape = _summary_float64(_result_stride_from_shape)
    print("MOJO_RESULT tensor_ops::stride_from_shape", _summary_stride_from_shape)
    var _acc_flatten_index: Float64 = 0.0
    var _t0_flatten_index = perf_counter_ns()
    for _ in range(N):
        _acc_flatten_index += flatten_index(0.5, 0.5, 0.5)
    var _t1_flatten_index = perf_counter_ns()
    var _ns_flatten_index = Float64(_t1_flatten_index - _t0_flatten_index) / Float64(N)
    print("MOJO_TIMING tensor_ops::flatten_index", _ns_flatten_index, _acc_flatten_index)
    var _result_flatten_index = flatten_index(0.5, 0.5, 0.5)
    var _summary_flatten_index = _summary_float64(_result_flatten_index)
    print("MOJO_RESULT tensor_ops::flatten_index", _summary_flatten_index)
    var _acc_unflatten_index_dim: Float64 = 0.0
    var _t0_unflatten_index_dim = perf_counter_ns()
    for _ in range(N):
        _acc_unflatten_index_dim += unflatten_index_dim(0.5, 0.5, 0.5)
    var _t1_unflatten_index_dim = perf_counter_ns()
    var _ns_unflatten_index_dim = Float64(_t1_unflatten_index_dim - _t0_unflatten_index_dim) / Float64(N)
    print("MOJO_TIMING tensor_ops::unflatten_index_dim", _ns_unflatten_index_dim, _acc_unflatten_index_dim)
    var _result_unflatten_index_dim = unflatten_index_dim(0.5, 0.5, 0.5)
    var _summary_unflatten_index_dim = _summary_float64(_result_unflatten_index_dim)
    print("MOJO_RESULT tensor_ops::unflatten_index_dim", _summary_unflatten_index_dim)
    var _acc_transpose_index: Float64 = 0.0
    var _t0_transpose_index = perf_counter_ns()
    for _ in range(N):
        _acc_transpose_index += transpose_index(0.5, 0.5, 0.5)
    var _t1_transpose_index = perf_counter_ns()
    var _ns_transpose_index = Float64(_t1_transpose_index - _t0_transpose_index) / Float64(N)
    print("MOJO_TIMING tensor_ops::transpose_index", _ns_transpose_index, _acc_transpose_index)
    var _result_transpose_index = transpose_index(0.5, 0.5, 0.5)
    var _summary_transpose_index = _summary_float64(_result_transpose_index)
    print("MOJO_RESULT tensor_ops::transpose_index", _summary_transpose_index)
    var _acc_outer_product_element: Float64 = 0.0
    var _t0_outer_product_element = perf_counter_ns()
    for _ in range(N):
        _acc_outer_product_element += outer_product_element(0.5, 0.5)
    var _t1_outer_product_element = perf_counter_ns()
    var _ns_outer_product_element = Float64(_t1_outer_product_element - _t0_outer_product_element) / Float64(N)
    print("MOJO_TIMING tensor_ops::outer_product_element", _ns_outer_product_element, _acc_outer_product_element)
    var _result_outer_product_element = outer_product_element(0.5, 0.5)
    var _summary_outer_product_element = _summary_float64(_result_outer_product_element)
    print("MOJO_RESULT tensor_ops::outer_product_element", _summary_outer_product_element)
    var _acc_tensor_norm_contribution: Float64 = 0.0
    var _t0_tensor_norm_contribution = perf_counter_ns()
    for _ in range(N):
        _acc_tensor_norm_contribution += tensor_norm_contribution(0.5)
    var _t1_tensor_norm_contribution = perf_counter_ns()
    var _ns_tensor_norm_contribution = Float64(_t1_tensor_norm_contribution - _t0_tensor_norm_contribution) / Float64(N)
    print("MOJO_TIMING tensor_ops::tensor_norm_contribution", _ns_tensor_norm_contribution, _acc_tensor_norm_contribution)
    var _result_tensor_norm_contribution = tensor_norm_contribution(0.5)
    var _summary_tensor_norm_contribution = _summary_float64(_result_tensor_norm_contribution)
    print("MOJO_RESULT tensor_ops::tensor_norm_contribution", _summary_tensor_norm_contribution)
    var _acc_softmax_stable_element: Float64 = 0.0
    var _t0_softmax_stable_element = perf_counter_ns()
    for _ in range(N):
        _acc_softmax_stable_element += softmax_stable_element(0.5, 0.5, 0.5)
    var _t1_softmax_stable_element = perf_counter_ns()
    var _ns_softmax_stable_element = Float64(_t1_softmax_stable_element - _t0_softmax_stable_element) / Float64(N)
    print("MOJO_TIMING tensor_ops::softmax_stable_element", _ns_softmax_stable_element, _acc_softmax_stable_element)
    var _result_softmax_stable_element = softmax_stable_element(0.5, 0.5, 0.5)
    var _summary_softmax_stable_element = _summary_float64(_result_softmax_stable_element)
    print("MOJO_RESULT tensor_ops::softmax_stable_element", _summary_softmax_stable_element)
    var _acc_tensor_dot_contribution: Float64 = 0.0
    var _t0_tensor_dot_contribution = perf_counter_ns()
    for _ in range(N):
        _acc_tensor_dot_contribution += tensor_dot_contribution(0.5, 0.5, 0.5)
    var _t1_tensor_dot_contribution = perf_counter_ns()
    var _ns_tensor_dot_contribution = Float64(_t1_tensor_dot_contribution - _t0_tensor_dot_contribution) / Float64(N)
    print("MOJO_TIMING tensor_ops::tensor_dot_contribution", _ns_tensor_dot_contribution, _acc_tensor_dot_contribution)
    var _result_tensor_dot_contribution = tensor_dot_contribution(0.5, 0.5, 0.5)
    var _summary_tensor_dot_contribution = _summary_float64(_result_tensor_dot_contribution)
    print("MOJO_RESULT tensor_ops::tensor_dot_contribution", _summary_tensor_dot_contribution)
