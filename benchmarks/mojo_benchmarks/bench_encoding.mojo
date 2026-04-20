"""bench_encoding.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from encoding import build_vocabulary, label_encode, label_decode, one_hot_encode, ordinal_encode, binary_encode, frequency_encode
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

    var _acc_build_vocabulary: Float64 = 0.0
    var _t0_build_vocabulary = perf_counter_ns()
    for _ in range(N):
        var _r_build_vocabulary = build_vocabulary(["a","b","c","d","e"])
        _acc_build_vocabulary += Float64(len(_r_build_vocabulary))
    var _t1_build_vocabulary = perf_counter_ns()
    var _ns_build_vocabulary = Float64(_t1_build_vocabulary - _t0_build_vocabulary) / Float64(N)
    print("MOJO_TIMING encoding::build_vocabulary", _ns_build_vocabulary, _acc_build_vocabulary)
    var _acc_label_encode: Float64 = 0.0
    var _t0_label_encode = perf_counter_ns()
    for _ in range(N):
        var _r_label_encode = label_encode(["a","b","c","d","e"])
        _acc_label_encode += Float64(len(_r_label_encode))
    var _t1_label_encode = perf_counter_ns()
    var _ns_label_encode = Float64(_t1_label_encode - _t0_label_encode) / Float64(N)
    print("MOJO_TIMING encoding::label_encode", _ns_label_encode, _acc_label_encode)
    var _acc_label_decode: Float64 = 0.0
    var _t0_label_decode = perf_counter_ns()
    for _ in range(N):
        var _r_label_decode = label_decode(_li5, ["a","b","c","d","e"])
        _acc_label_decode += Float64(len(_r_label_decode))
    var _t1_label_decode = perf_counter_ns()
    var _ns_label_decode = Float64(_t1_label_decode - _t0_label_decode) / Float64(N)
    print("MOJO_TIMING encoding::label_decode", _ns_label_decode, _acc_label_decode)
    var _acc_one_hot_encode: Float64 = 0.0
    var _t0_one_hot_encode = perf_counter_ns()
    for _ in range(N):
        var _r_one_hot_encode = one_hot_encode(_li5, 5)
        _acc_one_hot_encode += Float64(len(_r_one_hot_encode))
    var _t1_one_hot_encode = perf_counter_ns()
    var _ns_one_hot_encode = Float64(_t1_one_hot_encode - _t0_one_hot_encode) / Float64(N)
    print("MOJO_TIMING encoding::one_hot_encode", _ns_one_hot_encode, _acc_one_hot_encode)
    var _acc_ordinal_encode: Float64 = 0.0
    var _t0_ordinal_encode = perf_counter_ns()
    for _ in range(N):
        var _r_ordinal_encode = ordinal_encode(["a","b","c","d","e"], ["a","b","c","d","e"])
        _acc_ordinal_encode += Float64(len(_r_ordinal_encode))
    var _t1_ordinal_encode = perf_counter_ns()
    var _ns_ordinal_encode = Float64(_t1_ordinal_encode - _t0_ordinal_encode) / Float64(N)
    print("MOJO_TIMING encoding::ordinal_encode", _ns_ordinal_encode, _acc_ordinal_encode)
    var _acc_binary_encode: Float64 = 0.0
    var _t0_binary_encode = perf_counter_ns()
    for _ in range(N):
        var _r_binary_encode = binary_encode(5, 5)
        _acc_binary_encode += Float64(len(_r_binary_encode))
    var _t1_binary_encode = perf_counter_ns()
    var _ns_binary_encode = Float64(_t1_binary_encode - _t0_binary_encode) / Float64(N)
    print("MOJO_TIMING encoding::binary_encode", _ns_binary_encode, _acc_binary_encode)
    var _acc_frequency_encode: Float64 = 0.0
    var _t0_frequency_encode = perf_counter_ns()
    for _ in range(N):
        var _r_frequency_encode = frequency_encode(["a","b","c","d","e"])
        _acc_frequency_encode += Float64(len(_r_frequency_encode))
    var _t1_frequency_encode = perf_counter_ns()
    var _ns_frequency_encode = Float64(_t1_frequency_encode - _t0_frequency_encode) / Float64(N)
    print("MOJO_TIMING encoding::frequency_encode", _ns_frequency_encode, _acc_frequency_encode)
