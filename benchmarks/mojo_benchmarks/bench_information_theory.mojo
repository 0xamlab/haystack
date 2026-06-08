"""bench_information_theory.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from information_theory import entropy, joint_entropy, conditional_entropy, mutual_information, kl_divergence, cross_entropy, binary_entropy, channel_capacity_bsc, redundancy, normalized_entropy
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

    var _acc_entropy: Float64 = 0.0
    var _t0_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_entropy += entropy(_lf5)
    var _t1_entropy = perf_counter_ns()
    var _ns_entropy = Float64(_t1_entropy - _t0_entropy) / Float64(N)
    print("MOJO_TIMING information_theory::entropy", _ns_entropy, _acc_entropy)
    var _result_entropy = entropy(_lf5)
    var _summary_entropy = _summary_float64(_result_entropy)
    print("MOJO_RESULT information_theory::entropy", _summary_entropy)
    var _acc_joint_entropy: Float64 = 0.0
    var _t0_joint_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_joint_entropy += joint_entropy([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_joint_entropy = perf_counter_ns()
    var _ns_joint_entropy = Float64(_t1_joint_entropy - _t0_joint_entropy) / Float64(N)
    print("MOJO_TIMING information_theory::joint_entropy", _ns_joint_entropy, _acc_joint_entropy)
    var _result_joint_entropy = joint_entropy([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_joint_entropy = _summary_float64(_result_joint_entropy)
    print("MOJO_RESULT information_theory::joint_entropy", _summary_joint_entropy)
    var _acc_conditional_entropy: Float64 = 0.0
    var _t0_conditional_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_conditional_entropy += conditional_entropy([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_conditional_entropy = perf_counter_ns()
    var _ns_conditional_entropy = Float64(_t1_conditional_entropy - _t0_conditional_entropy) / Float64(N)
    print("MOJO_TIMING information_theory::conditional_entropy", _ns_conditional_entropy, _acc_conditional_entropy)
    var _result_conditional_entropy = conditional_entropy([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_conditional_entropy = _summary_float64(_result_conditional_entropy)
    print("MOJO_RESULT information_theory::conditional_entropy", _summary_conditional_entropy)
    var _acc_mutual_information: Float64 = 0.0
    var _t0_mutual_information = perf_counter_ns()
    for _ in range(N):
        _acc_mutual_information += mutual_information([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_mutual_information = perf_counter_ns()
    var _ns_mutual_information = Float64(_t1_mutual_information - _t0_mutual_information) / Float64(N)
    print("MOJO_TIMING information_theory::mutual_information", _ns_mutual_information, _acc_mutual_information)
    var _result_mutual_information = mutual_information([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _summary_mutual_information = _summary_float64(_result_mutual_information)
    print("MOJO_RESULT information_theory::mutual_information", _summary_mutual_information)
    var _acc_kl_divergence: Float64 = 0.0
    var _t0_kl_divergence = perf_counter_ns()
    for _ in range(N):
        _acc_kl_divergence += kl_divergence(_lf5, _lf5)
    var _t1_kl_divergence = perf_counter_ns()
    var _ns_kl_divergence = Float64(_t1_kl_divergence - _t0_kl_divergence) / Float64(N)
    print("MOJO_TIMING information_theory::kl_divergence", _ns_kl_divergence, _acc_kl_divergence)
    var _result_kl_divergence = kl_divergence(_lf5, _lf5)
    var _summary_kl_divergence = _summary_float64(_result_kl_divergence)
    print("MOJO_RESULT information_theory::kl_divergence", _summary_kl_divergence)
    var _acc_cross_entropy: Float64 = 0.0
    var _t0_cross_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_cross_entropy += cross_entropy(_lf5, _lf5)
    var _t1_cross_entropy = perf_counter_ns()
    var _ns_cross_entropy = Float64(_t1_cross_entropy - _t0_cross_entropy) / Float64(N)
    print("MOJO_TIMING information_theory::cross_entropy", _ns_cross_entropy, _acc_cross_entropy)
    var _result_cross_entropy = cross_entropy(_lf5, _lf5)
    var _summary_cross_entropy = _summary_float64(_result_cross_entropy)
    print("MOJO_RESULT information_theory::cross_entropy", _summary_cross_entropy)
    var _acc_binary_entropy: Float64 = 0.0
    var _t0_binary_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_binary_entropy += binary_entropy(0.5)
    var _t1_binary_entropy = perf_counter_ns()
    var _ns_binary_entropy = Float64(_t1_binary_entropy - _t0_binary_entropy) / Float64(N)
    print("MOJO_TIMING information_theory::binary_entropy", _ns_binary_entropy, _acc_binary_entropy)
    var _result_binary_entropy = binary_entropy(0.5)
    var _summary_binary_entropy = _summary_float64(_result_binary_entropy)
    print("MOJO_RESULT information_theory::binary_entropy", _summary_binary_entropy)
    var _acc_channel_capacity_bsc: Float64 = 0.0
    var _t0_channel_capacity_bsc = perf_counter_ns()
    for _ in range(N):
        _acc_channel_capacity_bsc += channel_capacity_bsc(0.5)
    var _t1_channel_capacity_bsc = perf_counter_ns()
    var _ns_channel_capacity_bsc = Float64(_t1_channel_capacity_bsc - _t0_channel_capacity_bsc) / Float64(N)
    print("MOJO_TIMING information_theory::channel_capacity_bsc", _ns_channel_capacity_bsc, _acc_channel_capacity_bsc)
    var _result_channel_capacity_bsc = channel_capacity_bsc(0.5)
    var _summary_channel_capacity_bsc = _summary_float64(_result_channel_capacity_bsc)
    print("MOJO_RESULT information_theory::channel_capacity_bsc", _summary_channel_capacity_bsc)
    var _acc_redundancy: Float64 = 0.0
    var _t0_redundancy = perf_counter_ns()
    for _ in range(N):
        _acc_redundancy += redundancy(_lf5)
    var _t1_redundancy = perf_counter_ns()
    var _ns_redundancy = Float64(_t1_redundancy - _t0_redundancy) / Float64(N)
    print("MOJO_TIMING information_theory::redundancy", _ns_redundancy, _acc_redundancy)
    var _result_redundancy = redundancy(_lf5)
    var _summary_redundancy = _summary_float64(_result_redundancy)
    print("MOJO_RESULT information_theory::redundancy", _summary_redundancy)
    var _acc_normalized_entropy: Float64 = 0.0
    var _t0_normalized_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_normalized_entropy += normalized_entropy(_lf5)
    var _t1_normalized_entropy = perf_counter_ns()
    var _ns_normalized_entropy = Float64(_t1_normalized_entropy - _t0_normalized_entropy) / Float64(N)
    print("MOJO_TIMING information_theory::normalized_entropy", _ns_normalized_entropy, _acc_normalized_entropy)
    var _result_normalized_entropy = normalized_entropy(_lf5)
    var _summary_normalized_entropy = _summary_float64(_result_normalized_entropy)
    print("MOJO_RESULT information_theory::normalized_entropy", _summary_normalized_entropy)
