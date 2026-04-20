"""bench_tensor.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from tensor import zeros, ones, full, arange, linspace, Tensor1D
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

    var _keeper_zeros = List[Tensor1D]()
    _keeper_zeros.append(zeros(5))
    var _acc_zeros: Float64 = 0.0
    var _t0_zeros = perf_counter_ns()
    for _ in range(N):
        _keeper_zeros[0] = zeros(5)
        _acc_zeros += Float64(len(_keeper_zeros))
    var _t1_zeros = perf_counter_ns()
    var _ns_zeros = Float64(_t1_zeros - _t0_zeros) / Float64(N)
    print("MOJO_TIMING tensor::zeros", _ns_zeros, _acc_zeros)
    var _keeper_ones = List[Tensor1D]()
    _keeper_ones.append(ones(5))
    var _acc_ones: Float64 = 0.0
    var _t0_ones = perf_counter_ns()
    for _ in range(N):
        _keeper_ones[0] = ones(5)
        _acc_ones += Float64(len(_keeper_ones))
    var _t1_ones = perf_counter_ns()
    var _ns_ones = Float64(_t1_ones - _t0_ones) / Float64(N)
    print("MOJO_TIMING tensor::ones", _ns_ones, _acc_ones)
    var _keeper_full = List[Tensor1D]()
    _keeper_full.append(full(5, 0.5))
    var _acc_full: Float64 = 0.0
    var _t0_full = perf_counter_ns()
    for _ in range(N):
        _keeper_full[0] = full(5, 0.5)
        _acc_full += Float64(len(_keeper_full))
    var _t1_full = perf_counter_ns()
    var _ns_full = Float64(_t1_full - _t0_full) / Float64(N)
    print("MOJO_TIMING tensor::full", _ns_full, _acc_full)
    var _keeper_arange = List[Tensor1D]()
    _keeper_arange.append(arange(0.5, 0.5, 0.5))
    var _acc_arange: Float64 = 0.0
    var _t0_arange = perf_counter_ns()
    for _ in range(N):
        _keeper_arange[0] = arange(0.5, 0.5, 0.5)
        _acc_arange += Float64(len(_keeper_arange))
    var _t1_arange = perf_counter_ns()
    var _ns_arange = Float64(_t1_arange - _t0_arange) / Float64(N)
    print("MOJO_TIMING tensor::arange", _ns_arange, _acc_arange)
    var _keeper_linspace = List[Tensor1D]()
    _keeper_linspace.append(linspace(0.5, 0.5, 5))
    var _acc_linspace: Float64 = 0.0
    var _t0_linspace = perf_counter_ns()
    for _ in range(N):
        _keeper_linspace[0] = linspace(0.5, 0.5, 5)
        _acc_linspace += Float64(len(_keeper_linspace))
    var _t1_linspace = perf_counter_ns()
    var _ns_linspace = Float64(_t1_linspace - _t0_linspace) / Float64(N)
    print("MOJO_TIMING tensor::linspace", _ns_linspace, _acc_linspace)
