"""bench_autograd_ops.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from autograd_ops import grad_add, grad_mul, grad_exp, grad_log, grad_relu, grad_sigmoid, grad_tanh, grad_pow, chain_rule, grad_softmax_diag
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_grad_add: Float64 = 0.0
    var _t0_grad_add = perf_counter_ns()
    for _ in range(N):
        _acc_grad_add += grad_add(0.5)
    var _t1_grad_add = perf_counter_ns()
    var _ns_grad_add = Float64(_t1_grad_add - _t0_grad_add) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_add", _ns_grad_add, _acc_grad_add)
    var _result_grad_add = grad_add(0.5)
    var _summary_grad_add = _summary_float64(_result_grad_add)
    print("MOJO_RESULT autograd_ops::grad_add", _summary_grad_add)
    var _acc_grad_mul: Float64 = 0.0
    var _t0_grad_mul = perf_counter_ns()
    for _ in range(N):
        _acc_grad_mul += grad_mul(0.5, 0.5)
    var _t1_grad_mul = perf_counter_ns()
    var _ns_grad_mul = Float64(_t1_grad_mul - _t0_grad_mul) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_mul", _ns_grad_mul, _acc_grad_mul)
    var _result_grad_mul = grad_mul(0.5, 0.5)
    var _summary_grad_mul = _summary_float64(_result_grad_mul)
    print("MOJO_RESULT autograd_ops::grad_mul", _summary_grad_mul)
    var _acc_grad_exp: Float64 = 0.0
    var _t0_grad_exp = perf_counter_ns()
    for _ in range(N):
        _acc_grad_exp += grad_exp(0.5, 0.5)
    var _t1_grad_exp = perf_counter_ns()
    var _ns_grad_exp = Float64(_t1_grad_exp - _t0_grad_exp) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_exp", _ns_grad_exp, _acc_grad_exp)
    var _result_grad_exp = grad_exp(0.5, 0.5)
    var _summary_grad_exp = _summary_float64(_result_grad_exp)
    print("MOJO_RESULT autograd_ops::grad_exp", _summary_grad_exp)
    var _acc_grad_log: Float64 = 0.0
    var _t0_grad_log = perf_counter_ns()
    for _ in range(N):
        _acc_grad_log += grad_log(0.5, 0.5)
    var _t1_grad_log = perf_counter_ns()
    var _ns_grad_log = Float64(_t1_grad_log - _t0_grad_log) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_log", _ns_grad_log, _acc_grad_log)
    var _result_grad_log = grad_log(0.5, 0.5)
    var _summary_grad_log = _summary_float64(_result_grad_log)
    print("MOJO_RESULT autograd_ops::grad_log", _summary_grad_log)
    var _acc_grad_relu: Float64 = 0.0
    var _t0_grad_relu = perf_counter_ns()
    for _ in range(N):
        _acc_grad_relu += grad_relu(0.5, 0.5)
    var _t1_grad_relu = perf_counter_ns()
    var _ns_grad_relu = Float64(_t1_grad_relu - _t0_grad_relu) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_relu", _ns_grad_relu, _acc_grad_relu)
    var _result_grad_relu = grad_relu(0.5, 0.5)
    var _summary_grad_relu = _summary_float64(_result_grad_relu)
    print("MOJO_RESULT autograd_ops::grad_relu", _summary_grad_relu)
    var _acc_grad_sigmoid: Float64 = 0.0
    var _t0_grad_sigmoid = perf_counter_ns()
    for _ in range(N):
        _acc_grad_sigmoid += grad_sigmoid(0.5, 0.5)
    var _t1_grad_sigmoid = perf_counter_ns()
    var _ns_grad_sigmoid = Float64(_t1_grad_sigmoid - _t0_grad_sigmoid) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_sigmoid", _ns_grad_sigmoid, _acc_grad_sigmoid)
    var _result_grad_sigmoid = grad_sigmoid(0.5, 0.5)
    var _summary_grad_sigmoid = _summary_float64(_result_grad_sigmoid)
    print("MOJO_RESULT autograd_ops::grad_sigmoid", _summary_grad_sigmoid)
    var _acc_grad_tanh: Float64 = 0.0
    var _t0_grad_tanh = perf_counter_ns()
    for _ in range(N):
        _acc_grad_tanh += grad_tanh(0.5, 0.5)
    var _t1_grad_tanh = perf_counter_ns()
    var _ns_grad_tanh = Float64(_t1_grad_tanh - _t0_grad_tanh) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_tanh", _ns_grad_tanh, _acc_grad_tanh)
    var _result_grad_tanh = grad_tanh(0.5, 0.5)
    var _summary_grad_tanh = _summary_float64(_result_grad_tanh)
    print("MOJO_RESULT autograd_ops::grad_tanh", _summary_grad_tanh)
    var _acc_grad_pow: Float64 = 0.0
    var _t0_grad_pow = perf_counter_ns()
    for _ in range(N):
        _acc_grad_pow += grad_pow(0.5, 0.5, 0.5)
    var _t1_grad_pow = perf_counter_ns()
    var _ns_grad_pow = Float64(_t1_grad_pow - _t0_grad_pow) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_pow", _ns_grad_pow, _acc_grad_pow)
    var _result_grad_pow = grad_pow(0.5, 0.5, 0.5)
    var _summary_grad_pow = _summary_float64(_result_grad_pow)
    print("MOJO_RESULT autograd_ops::grad_pow", _summary_grad_pow)
    var _acc_chain_rule: Float64 = 0.0
    var _t0_chain_rule = perf_counter_ns()
    for _ in range(N):
        _acc_chain_rule += chain_rule(0.5, 0.5)
    var _t1_chain_rule = perf_counter_ns()
    var _ns_chain_rule = Float64(_t1_chain_rule - _t0_chain_rule) / Float64(N)
    print("MOJO_TIMING autograd_ops::chain_rule", _ns_chain_rule, _acc_chain_rule)
    var _result_chain_rule = chain_rule(0.5, 0.5)
    var _summary_chain_rule = _summary_float64(_result_chain_rule)
    print("MOJO_RESULT autograd_ops::chain_rule", _summary_chain_rule)
    var _acc_grad_softmax_diag: Float64 = 0.0
    var _t0_grad_softmax_diag = perf_counter_ns()
    for _ in range(N):
        _acc_grad_softmax_diag += grad_softmax_diag(0.5, 0.5)
    var _t1_grad_softmax_diag = perf_counter_ns()
    var _ns_grad_softmax_diag = Float64(_t1_grad_softmax_diag - _t0_grad_softmax_diag) / Float64(N)
    print("MOJO_TIMING autograd_ops::grad_softmax_diag", _ns_grad_softmax_diag, _acc_grad_softmax_diag)
    var _result_grad_softmax_diag = grad_softmax_diag(0.5, 0.5)
    var _summary_grad_softmax_diag = _summary_float64(_result_grad_softmax_diag)
    print("MOJO_RESULT autograd_ops::grad_softmax_diag", _summary_grad_softmax_diag)
