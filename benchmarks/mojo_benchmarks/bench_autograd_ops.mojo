"""bench_autograd_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from autograd_ops import grad_add, grad_mul, grad_exp, grad_log, grad_relu, grad_sigmoid, grad_tanh, grad_pow, chain_rule, grad_softmax_diag
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

    var _acc_grad_add: Float64 = 0.0
    var _t0_grad_add = perf_counter_ns()
    for _ in range(N):
        _acc_grad_add += grad_add(0.5)
    var _t1_grad_add = perf_counter_ns()
    var _ns_grad_add = Float64(_t1_grad_add - _t0_grad_add) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_add", _ns_grad_add, _acc_grad_add)
    var _acc_grad_mul: Float64 = 0.0
    var _t0_grad_mul = perf_counter_ns()
    for _ in range(N):
        _acc_grad_mul += grad_mul(0.5, 0.5)
    var _t1_grad_mul = perf_counter_ns()
    var _ns_grad_mul = Float64(_t1_grad_mul - _t0_grad_mul) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_mul", _ns_grad_mul, _acc_grad_mul)
    var _acc_grad_exp: Float64 = 0.0
    var _t0_grad_exp = perf_counter_ns()
    for _ in range(N):
        _acc_grad_exp += grad_exp(0.5, 0.5)
    var _t1_grad_exp = perf_counter_ns()
    var _ns_grad_exp = Float64(_t1_grad_exp - _t0_grad_exp) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_exp", _ns_grad_exp, _acc_grad_exp)
    var _acc_grad_log: Float64 = 0.0
    var _t0_grad_log = perf_counter_ns()
    for _ in range(N):
        _acc_grad_log += grad_log(0.5, 0.5)
    var _t1_grad_log = perf_counter_ns()
    var _ns_grad_log = Float64(_t1_grad_log - _t0_grad_log) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_log", _ns_grad_log, _acc_grad_log)
    var _acc_grad_relu: Float64 = 0.0
    var _t0_grad_relu = perf_counter_ns()
    for _ in range(N):
        _acc_grad_relu += grad_relu(0.5, 0.5)
    var _t1_grad_relu = perf_counter_ns()
    var _ns_grad_relu = Float64(_t1_grad_relu - _t0_grad_relu) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_relu", _ns_grad_relu, _acc_grad_relu)
    var _acc_grad_sigmoid: Float64 = 0.0
    var _t0_grad_sigmoid = perf_counter_ns()
    for _ in range(N):
        _acc_grad_sigmoid += grad_sigmoid(0.5, 0.5)
    var _t1_grad_sigmoid = perf_counter_ns()
    var _ns_grad_sigmoid = Float64(_t1_grad_sigmoid - _t0_grad_sigmoid) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_sigmoid", _ns_grad_sigmoid, _acc_grad_sigmoid)
    var _acc_grad_tanh: Float64 = 0.0
    var _t0_grad_tanh = perf_counter_ns()
    for _ in range(N):
        _acc_grad_tanh += grad_tanh(0.5, 0.5)
    var _t1_grad_tanh = perf_counter_ns()
    var _ns_grad_tanh = Float64(_t1_grad_tanh - _t0_grad_tanh) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_tanh", _ns_grad_tanh, _acc_grad_tanh)
    var _acc_grad_pow: Float64 = 0.0
    var _t0_grad_pow = perf_counter_ns()
    for _ in range(N):
        _acc_grad_pow += grad_pow(0.5, 0.5, 0.5)
    var _t1_grad_pow = perf_counter_ns()
    var _ns_grad_pow = Float64(_t1_grad_pow - _t0_grad_pow) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_pow", _ns_grad_pow, _acc_grad_pow)
    var _acc_chain_rule: Float64 = 0.0
    var _t0_chain_rule = perf_counter_ns()
    for _ in range(N):
        _acc_chain_rule += chain_rule(0.5, 0.5)
    var _t1_chain_rule = perf_counter_ns()
    var _ns_chain_rule = Float64(_t1_chain_rule - _t0_chain_rule) / Float64(N)
    print("MOJO_TIMING autograd_ops::chain_rule", _ns_chain_rule, _acc_chain_rule)
    var _acc_grad_softmax_diag: Float64 = 0.0
    var _t0_grad_softmax_diag = perf_counter_ns()
    for _ in range(N):
        _acc_grad_softmax_diag += grad_softmax_diag(0.5, 0.5)
    var _t1_grad_softmax_diag = perf_counter_ns()
    var _ns_grad_softmax_diag = Float64(_t1_grad_softmax_diag - _t0_grad_softmax_diag) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_softmax_diag", _ns_grad_softmax_diag, _acc_grad_softmax_diag)
