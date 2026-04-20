"""bench_information_theory.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from information_theory import entropy, joint_entropy, conditional_entropy, mutual_information, kl_divergence, cross_entropy, binary_entropy, channel_capacity_bsc, redundancy, normalized_entropy
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

    var _acc_entropy: Float64 = 0.0
    var _t0_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_entropy += entropy(_lf5)
    var _t1_entropy = perf_counter_ns()
    var _ns_entropy = Float64(_t1_entropy - _t0_entropy) / Float64(N)
    print("MOJO_TIMING information_theory::entropy", _ns_entropy, _acc_entropy)
    var _acc_joint_entropy: Float64 = 0.0
    var _t0_joint_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_joint_entropy += joint_entropy([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_joint_entropy = perf_counter_ns()
    var _ns_joint_entropy = Float64(_t1_joint_entropy - _t0_joint_entropy) / Float64(N)
    print("MOJO_TIMING information_theory::joint_entropy", _ns_joint_entropy, _acc_joint_entropy)
    var _acc_conditional_entropy: Float64 = 0.0
    var _t0_conditional_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_conditional_entropy += conditional_entropy([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_conditional_entropy = perf_counter_ns()
    var _ns_conditional_entropy = Float64(_t1_conditional_entropy - _t0_conditional_entropy) / Float64(N)
    print("MOJO_TIMING information_theory::conditional_entropy", _ns_conditional_entropy, _acc_conditional_entropy)
    var _acc_mutual_information: Float64 = 0.0
    var _t0_mutual_information = perf_counter_ns()
    for _ in range(N):
        _acc_mutual_information += mutual_information([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
    var _t1_mutual_information = perf_counter_ns()
    var _ns_mutual_information = Float64(_t1_mutual_information - _t0_mutual_information) / Float64(N)
    print("MOJO_TIMING information_theory::mutual_information", _ns_mutual_information, _acc_mutual_information)
    var _acc_kl_divergence: Float64 = 0.0
    var _t0_kl_divergence = perf_counter_ns()
    for _ in range(N):
        _acc_kl_divergence += kl_divergence(_lf5, _lf5)
    var _t1_kl_divergence = perf_counter_ns()
    var _ns_kl_divergence = Float64(_t1_kl_divergence - _t0_kl_divergence) / Float64(N)
    print("MOJO_TIMING information_theory::kl_divergence", _ns_kl_divergence, _acc_kl_divergence)
    var _acc_cross_entropy: Float64 = 0.0
    var _t0_cross_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_cross_entropy += cross_entropy(_lf5, _lf5)
    var _t1_cross_entropy = perf_counter_ns()
    var _ns_cross_entropy = Float64(_t1_cross_entropy - _t0_cross_entropy) / Float64(N)
    print("MOJO_TIMING information_theory::cross_entropy", _ns_cross_entropy, _acc_cross_entropy)
    var _acc_binary_entropy: Float64 = 0.0
    var _t0_binary_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_binary_entropy += binary_entropy(0.5)
    var _t1_binary_entropy = perf_counter_ns()
    var _ns_binary_entropy = Float64(_t1_binary_entropy - _t0_binary_entropy) / Float64(N)
    print("MOJO_TIMING information_theory::binary_entropy", _ns_binary_entropy, _acc_binary_entropy)
    var _acc_channel_capacity_bsc: Float64 = 0.0
    var _t0_channel_capacity_bsc = perf_counter_ns()
    for _ in range(N):
        _acc_channel_capacity_bsc += channel_capacity_bsc(0.5)
    var _t1_channel_capacity_bsc = perf_counter_ns()
    var _ns_channel_capacity_bsc = Float64(_t1_channel_capacity_bsc - _t0_channel_capacity_bsc) / Float64(N)
    print("MOJO_TIMING information_theory::channel_capacity_bsc", _ns_channel_capacity_bsc, _acc_channel_capacity_bsc)
    var _acc_redundancy: Float64 = 0.0
    var _t0_redundancy = perf_counter_ns()
    for _ in range(N):
        _acc_redundancy += redundancy(_lf5)
    var _t1_redundancy = perf_counter_ns()
    var _ns_redundancy = Float64(_t1_redundancy - _t0_redundancy) / Float64(N)
    print("MOJO_TIMING information_theory::redundancy", _ns_redundancy, _acc_redundancy)
    var _acc_normalized_entropy: Float64 = 0.0
    var _t0_normalized_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_normalized_entropy += normalized_entropy(_lf5)
    var _t1_normalized_entropy = perf_counter_ns()
    var _ns_normalized_entropy = Float64(_t1_normalized_entropy - _t0_normalized_entropy) / Float64(N)
    print("MOJO_TIMING information_theory::normalized_entropy", _ns_normalized_entropy, _acc_normalized_entropy)
