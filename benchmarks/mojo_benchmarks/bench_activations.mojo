"""bench_activations.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from activations import gelu, gelu_fast, swish, swiglu, mish, elu, selu, hard_swish, gelu_new, relu6
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

    var _acc_gelu: Float64 = 0.0
    var _t0_gelu = perf_counter_ns()
    for _ in range(N):
        _acc_gelu += gelu(0.5)
    var _t1_gelu = perf_counter_ns()
    var _ns_gelu = Float64(_t1_gelu - _t0_gelu) / Float64(N)
    print("MOJO_TIMING activations::gelu", _ns_gelu, _acc_gelu)
    var _acc_gelu_fast: Float64 = 0.0
    var _t0_gelu_fast = perf_counter_ns()
    for _ in range(N):
        _acc_gelu_fast += gelu_fast(0.5)
    var _t1_gelu_fast = perf_counter_ns()
    var _ns_gelu_fast = Float64(_t1_gelu_fast - _t0_gelu_fast) / Float64(N)
    print("MOJO_TIMING activations::gelu_fast", _ns_gelu_fast, _acc_gelu_fast)
    var _acc_swish: Float64 = 0.0
    var _t0_swish = perf_counter_ns()
    for _ in range(N):
        _acc_swish += swish(0.5)
    var _t1_swish = perf_counter_ns()
    var _ns_swish = Float64(_t1_swish - _t0_swish) / Float64(N)
    print("MOJO_TIMING activations::swish", _ns_swish, _acc_swish)
    var _acc_swiglu: Float64 = 0.0
    var _t0_swiglu = perf_counter_ns()
    for _ in range(N):
        _acc_swiglu += swiglu(0.5, 0.5)
    var _t1_swiglu = perf_counter_ns()
    var _ns_swiglu = Float64(_t1_swiglu - _t0_swiglu) / Float64(N)
    print("MOJO_TIMING activations::swiglu", _ns_swiglu, _acc_swiglu)
    var _acc_mish: Float64 = 0.0
    var _t0_mish = perf_counter_ns()
    for _ in range(N):
        _acc_mish += mish(0.5)
    var _t1_mish = perf_counter_ns()
    var _ns_mish = Float64(_t1_mish - _t0_mish) / Float64(N)
    print("MOJO_TIMING activations::mish", _ns_mish, _acc_mish)
    var _acc_elu: Float64 = 0.0
    var _t0_elu = perf_counter_ns()
    for _ in range(N):
        _acc_elu += elu(0.5, 0.5)
    var _t1_elu = perf_counter_ns()
    var _ns_elu = Float64(_t1_elu - _t0_elu) / Float64(N)
    print("MOJO_TIMING activations::elu", _ns_elu, _acc_elu)
    var _acc_selu: Float64 = 0.0
    var _t0_selu = perf_counter_ns()
    for _ in range(N):
        _acc_selu += selu(0.5)
    var _t1_selu = perf_counter_ns()
    var _ns_selu = Float64(_t1_selu - _t0_selu) / Float64(N)
    print("MOJO_TIMING activations::selu", _ns_selu, _acc_selu)
    var _acc_hard_swish: Float64 = 0.0
    var _t0_hard_swish = perf_counter_ns()
    for _ in range(N):
        _acc_hard_swish += hard_swish(0.5)
    var _t1_hard_swish = perf_counter_ns()
    var _ns_hard_swish = Float64(_t1_hard_swish - _t0_hard_swish) / Float64(N)
    print("MOJO_TIMING activations::hard_swish", _ns_hard_swish, _acc_hard_swish)
    var _acc_gelu_new: Float64 = 0.0
    var _t0_gelu_new = perf_counter_ns()
    for _ in range(N):
        _acc_gelu_new += gelu_new(0.5)
    var _t1_gelu_new = perf_counter_ns()
    var _ns_gelu_new = Float64(_t1_gelu_new - _t0_gelu_new) / Float64(N)
    print("MOJO_TIMING activations::gelu_new", _ns_gelu_new, _acc_gelu_new)
    var _acc_relu6: Float64 = 0.0
    var _t0_relu6 = perf_counter_ns()
    for _ in range(N):
        _acc_relu6 += relu6(0.5)
    var _t1_relu6 = perf_counter_ns()
    var _ns_relu6 = Float64(_t1_relu6 - _t0_relu6) / Float64(N)
    print("MOJO_TIMING activations::relu6", _ns_relu6, _acc_relu6)
