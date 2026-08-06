"""bench_activations.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from activations import gelu, gelu_fast, swish, swiglu, mish, elu, selu, hard_swish, gelu_new, relu6
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

    var _acc_gelu: Float64 = 0.0
    var _t0_gelu = perf_counter_ns()
    for _ in range(N):
        _acc_gelu += gelu(0.5)
    var _t1_gelu = perf_counter_ns()
    var _ns_gelu = Float64(_t1_gelu - _t0_gelu) / Float64(N)
    print("MOJO_TIMING activations::gelu", _ns_gelu, _acc_gelu)
    var _result_gelu = gelu(0.5)
    var _summary_gelu = _summary_float64(_result_gelu)
    print("MOJO_RESULT activations::gelu", _summary_gelu)
    var _acc_gelu_fast: Float64 = 0.0
    var _t0_gelu_fast = perf_counter_ns()
    for _ in range(N):
        _acc_gelu_fast += gelu_fast(0.5)
    var _t1_gelu_fast = perf_counter_ns()
    var _ns_gelu_fast = Float64(_t1_gelu_fast - _t0_gelu_fast) / Float64(N)
    print("MOJO_TIMING activations::gelu_fast", _ns_gelu_fast, _acc_gelu_fast)
    var _result_gelu_fast = gelu_fast(0.5)
    var _summary_gelu_fast = _summary_float64(_result_gelu_fast)
    print("MOJO_RESULT activations::gelu_fast", _summary_gelu_fast)
    var _acc_swish: Float64 = 0.0
    var _t0_swish = perf_counter_ns()
    for _ in range(N):
        _acc_swish += swish(0.5)
    var _t1_swish = perf_counter_ns()
    var _ns_swish = Float64(_t1_swish - _t0_swish) / Float64(N)
    print("MOJO_TIMING activations::swish", _ns_swish, _acc_swish)
    var _result_swish = swish(0.5)
    var _summary_swish = _summary_float64(_result_swish)
    print("MOJO_RESULT activations::swish", _summary_swish)
    var _acc_swiglu: Float64 = 0.0
    var _t0_swiglu = perf_counter_ns()
    for _ in range(N):
        _acc_swiglu += swiglu(0.5, 0.5)
    var _t1_swiglu = perf_counter_ns()
    var _ns_swiglu = Float64(_t1_swiglu - _t0_swiglu) / Float64(N)
    print("MOJO_TIMING activations::swiglu", _ns_swiglu, _acc_swiglu)
    var _result_swiglu = swiglu(0.5, 0.5)
    var _summary_swiglu = _summary_float64(_result_swiglu)
    print("MOJO_RESULT activations::swiglu", _summary_swiglu)
    var _acc_mish: Float64 = 0.0
    var _t0_mish = perf_counter_ns()
    for _ in range(N):
        _acc_mish += mish(0.5)
    var _t1_mish = perf_counter_ns()
    var _ns_mish = Float64(_t1_mish - _t0_mish) / Float64(N)
    print("MOJO_TIMING activations::mish", _ns_mish, _acc_mish)
    var _result_mish = mish(0.5)
    var _summary_mish = _summary_float64(_result_mish)
    print("MOJO_RESULT activations::mish", _summary_mish)
    var _acc_elu: Float64 = 0.0
    var _t0_elu = perf_counter_ns()
    for _ in range(N):
        _acc_elu += elu(0.5, 0.5)
    var _t1_elu = perf_counter_ns()
    var _ns_elu = Float64(_t1_elu - _t0_elu) / Float64(N)
    print("MOJO_TIMING activations::elu", _ns_elu, _acc_elu)
    var _result_elu = elu(0.5, 0.5)
    var _summary_elu = _summary_float64(_result_elu)
    print("MOJO_RESULT activations::elu", _summary_elu)
    var _acc_selu: Float64 = 0.0
    var _t0_selu = perf_counter_ns()
    for _ in range(N):
        _acc_selu += selu(0.5)
    var _t1_selu = perf_counter_ns()
    var _ns_selu = Float64(_t1_selu - _t0_selu) / Float64(N)
    print("MOJO_TIMING activations::selu", _ns_selu, _acc_selu)
    var _result_selu = selu(0.5)
    var _summary_selu = _summary_float64(_result_selu)
    print("MOJO_RESULT activations::selu", _summary_selu)
    var _acc_hard_swish: Float64 = 0.0
    var _t0_hard_swish = perf_counter_ns()
    for _ in range(N):
        _acc_hard_swish += hard_swish(0.5)
    var _t1_hard_swish = perf_counter_ns()
    var _ns_hard_swish = Float64(_t1_hard_swish - _t0_hard_swish) / Float64(N)
    print("MOJO_TIMING activations::hard_swish", _ns_hard_swish, _acc_hard_swish)
    var _result_hard_swish = hard_swish(0.5)
    var _summary_hard_swish = _summary_float64(_result_hard_swish)
    print("MOJO_RESULT activations::hard_swish", _summary_hard_swish)
    var _acc_gelu_new: Float64 = 0.0
    var _t0_gelu_new = perf_counter_ns()
    for _ in range(N):
        _acc_gelu_new += gelu_new(0.5)
    var _t1_gelu_new = perf_counter_ns()
    var _ns_gelu_new = Float64(_t1_gelu_new - _t0_gelu_new) / Float64(N)
    print("MOJO_TIMING activations::gelu_new", _ns_gelu_new, _acc_gelu_new)
    var _result_gelu_new = gelu_new(0.5)
    var _summary_gelu_new = _summary_float64(_result_gelu_new)
    print("MOJO_RESULT activations::gelu_new", _summary_gelu_new)
    var _acc_relu6: Float64 = 0.0
    var _t0_relu6 = perf_counter_ns()
    for _ in range(N):
        _acc_relu6 += relu6(0.5)
    var _t1_relu6 = perf_counter_ns()
    var _ns_relu6 = Float64(_t1_relu6 - _t0_relu6) / Float64(N)
    print("MOJO_TIMING activations::relu6", _ns_relu6, _acc_relu6)
    var _result_relu6 = relu6(0.5)
    var _summary_relu6 = _summary_float64(_result_relu6)
    print("MOJO_RESULT activations::relu6", _summary_relu6)
