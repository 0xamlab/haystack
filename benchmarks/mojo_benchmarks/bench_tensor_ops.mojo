"""bench_tensor_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from tensor_ops import matmul_element, broadcast_index, stride_from_shape, flatten_index, unflatten_index_dim, transpose_index, outer_product_element, tensor_norm_contribution, softmax_stable_element, tensor_dot_contribution
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

    var _acc_matmul_element: Float64 = 0.0
    var _t0_matmul_element = perf_counter_ns()
    for _ in range(N):
        _acc_matmul_element += matmul_element(0.5, 0.5)
    var _t1_matmul_element = perf_counter_ns()
    var _ns_matmul_element = Float64(_t1_matmul_element - _t0_matmul_element) / Float64(N)
    print("MOJO_TIMING tensor_ops::matmul_element", _ns_matmul_element, _acc_matmul_element)
    var _acc_broadcast_index: Float64 = 0.0
    var _t0_broadcast_index = perf_counter_ns()
    for _ in range(N):
        _acc_broadcast_index += broadcast_index(0.5, 0.5)
    var _t1_broadcast_index = perf_counter_ns()
    var _ns_broadcast_index = Float64(_t1_broadcast_index - _t0_broadcast_index) / Float64(N)
    print("MOJO_TIMING tensor_ops::broadcast_index", _ns_broadcast_index, _acc_broadcast_index)
    var _acc_stride_from_shape: Float64 = 0.0
    var _t0_stride_from_shape = perf_counter_ns()
    for _ in range(N):
        _acc_stride_from_shape += stride_from_shape(0.5, 0.5)
    var _t1_stride_from_shape = perf_counter_ns()
    var _ns_stride_from_shape = Float64(_t1_stride_from_shape - _t0_stride_from_shape) / Float64(N)
    print("MOJO_TIMING tensor_ops::stride_from_shape", _ns_stride_from_shape, _acc_stride_from_shape)
    var _acc_flatten_index: Float64 = 0.0
    var _t0_flatten_index = perf_counter_ns()
    for _ in range(N):
        _acc_flatten_index += flatten_index(0.5, 0.5, 0.5)
    var _t1_flatten_index = perf_counter_ns()
    var _ns_flatten_index = Float64(_t1_flatten_index - _t0_flatten_index) / Float64(N)
    print("MOJO_TIMING tensor_ops::flatten_index", _ns_flatten_index, _acc_flatten_index)
    var _acc_unflatten_index_dim: Float64 = 0.0
    var _t0_unflatten_index_dim = perf_counter_ns()
    for _ in range(N):
        _acc_unflatten_index_dim += unflatten_index_dim(0.5, 0.5, 0.5)
    var _t1_unflatten_index_dim = perf_counter_ns()
    var _ns_unflatten_index_dim = Float64(_t1_unflatten_index_dim - _t0_unflatten_index_dim) / Float64(N)
    print("MOJO_TIMING tensor_ops::unflatten_index_dim", _ns_unflatten_index_dim, _acc_unflatten_index_dim)
    var _acc_transpose_index: Float64 = 0.0
    var _t0_transpose_index = perf_counter_ns()
    for _ in range(N):
        _acc_transpose_index += transpose_index(0.5, 0.5, 0.5)
    var _t1_transpose_index = perf_counter_ns()
    var _ns_transpose_index = Float64(_t1_transpose_index - _t0_transpose_index) / Float64(N)
    print("MOJO_TIMING tensor_ops::transpose_index", _ns_transpose_index, _acc_transpose_index)
    var _acc_outer_product_element: Float64 = 0.0
    var _t0_outer_product_element = perf_counter_ns()
    for _ in range(N):
        _acc_outer_product_element += outer_product_element(0.5, 0.5)
    var _t1_outer_product_element = perf_counter_ns()
    var _ns_outer_product_element = Float64(_t1_outer_product_element - _t0_outer_product_element) / Float64(N)
    print("MOJO_TIMING tensor_ops::outer_product_element", _ns_outer_product_element, _acc_outer_product_element)
    var _acc_tensor_norm_contribution: Float64 = 0.0
    var _t0_tensor_norm_contribution = perf_counter_ns()
    for _ in range(N):
        _acc_tensor_norm_contribution += tensor_norm_contribution(0.5)
    var _t1_tensor_norm_contribution = perf_counter_ns()
    var _ns_tensor_norm_contribution = Float64(_t1_tensor_norm_contribution - _t0_tensor_norm_contribution) / Float64(N)
    print("MOJO_TIMING tensor_ops::tensor_norm_contribution", _ns_tensor_norm_contribution, _acc_tensor_norm_contribution)
    var _acc_softmax_stable_element: Float64 = 0.0
    var _t0_softmax_stable_element = perf_counter_ns()
    for _ in range(N):
        _acc_softmax_stable_element += softmax_stable_element(0.5, 0.5, 0.5)
    var _t1_softmax_stable_element = perf_counter_ns()
    var _ns_softmax_stable_element = Float64(_t1_softmax_stable_element - _t0_softmax_stable_element) / Float64(N)
    print("MOJO_TIMING tensor_ops::softmax_stable_element", _ns_softmax_stable_element, _acc_softmax_stable_element)
    var _acc_tensor_dot_contribution: Float64 = 0.0
    var _t0_tensor_dot_contribution = perf_counter_ns()
    for _ in range(N):
        _acc_tensor_dot_contribution += tensor_dot_contribution(0.5, 0.5, 0.5)
    var _t1_tensor_dot_contribution = perf_counter_ns()
    var _ns_tensor_dot_contribution = Float64(_t1_tensor_dot_contribution - _t0_tensor_dot_contribution) / Float64(N)
    print("MOJO_TIMING tensor_ops::tensor_dot_contribution", _ns_tensor_dot_contribution, _acc_tensor_dot_contribution)
