"""bench_compression_huffman.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from compression.huffman import frequency_count, build_huffman_tree, huffman_encode, compression_ratio_huffman, avg_code_length
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

    var _acc_frequency_count: Float64 = 0.0
    var _t0_frequency_count = perf_counter_ns()
    for _ in range(N):
        var _r_frequency_count = frequency_count(_li5)
        _acc_frequency_count += Float64(len(_r_frequency_count))
    var _t1_frequency_count = perf_counter_ns()
    var _ns_frequency_count = Float64(_t1_frequency_count - _t0_frequency_count) / Float64(N)
    print("MOJO_TIMING compression_huffman::frequency_count", _ns_frequency_count, _acc_frequency_count)
    var _acc_build_huffman_tree: Float64 = 0.0
    var _t0_build_huffman_tree = perf_counter_ns()
    for _ in range(N):
        var _r_build_huffman_tree = build_huffman_tree([[0,1,1],[1,0,1],[1,1,0]])
        _acc_build_huffman_tree += Float64(len(_r_build_huffman_tree))
    var _t1_build_huffman_tree = perf_counter_ns()
    var _ns_build_huffman_tree = Float64(_t1_build_huffman_tree - _t0_build_huffman_tree) / Float64(N)
    print("MOJO_TIMING compression_huffman::build_huffman_tree", _ns_build_huffman_tree, _acc_build_huffman_tree)
    var _acc_huffman_encode: Float64 = 0.0
    var _t0_huffman_encode = perf_counter_ns()
    for _ in range(N):
        var _r_huffman_encode = huffman_encode(_li5)
        _acc_huffman_encode += Float64(len(_r_huffman_encode))
    var _t1_huffman_encode = perf_counter_ns()
    var _ns_huffman_encode = Float64(_t1_huffman_encode - _t0_huffman_encode) / Float64(N)
    print("MOJO_TIMING compression_huffman::huffman_encode", _ns_huffman_encode, _acc_huffman_encode)
    var _acc_compression_ratio_huffman: Float64 = 0.0
    var _t0_compression_ratio_huffman = perf_counter_ns()
    for _ in range(N):
        _acc_compression_ratio_huffman += compression_ratio_huffman(5, 5)
    var _t1_compression_ratio_huffman = perf_counter_ns()
    var _ns_compression_ratio_huffman = Float64(_t1_compression_ratio_huffman - _t0_compression_ratio_huffman) / Float64(N)
    print("MOJO_TIMING compression_huffman::compression_ratio_huffman", _ns_compression_ratio_huffman, _acc_compression_ratio_huffman)
    var _acc_avg_code_length: Float64 = 0.0
    var _t0_avg_code_length = perf_counter_ns()
    for _ in range(N):
        _acc_avg_code_length += avg_code_length([[0,1,1],[1,0,1],[1,1,0]], [[0,1,1],[1,0,1],[1,1,0]])
    var _t1_avg_code_length = perf_counter_ns()
    var _ns_avg_code_length = Float64(_t1_avg_code_length - _t0_avg_code_length) / Float64(N)
    print("MOJO_TIMING compression_huffman::avg_code_length", _ns_avg_code_length, _acc_avg_code_length)
