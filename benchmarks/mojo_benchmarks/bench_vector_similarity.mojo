"""bench_vector_similarity.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from vector_similarity import cosine_similarity, dot_product, euclidean_distance, manhattan_distance, chebyshev_distance, hamming_distance_bits, jaccard_similarity, pearson_correlation, minkowski_distance, angular_distance
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

    var _acc_cosine_similarity: Float64 = 0.0
    var _t0_cosine_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_similarity += cosine_similarity(0.5, 0.5, 0.5)
    var _t1_cosine_similarity = perf_counter_ns()
    var _ns_cosine_similarity = Float64(_t1_cosine_similarity - _t0_cosine_similarity) / Float64(N)
    print("MOJO_TIMING vector_similarity::cosine_similarity", _ns_cosine_similarity, _acc_cosine_similarity)
    var _result_cosine_similarity = cosine_similarity(0.5, 0.5, 0.5)
    var _summary_cosine_similarity = _summary_float64(_result_cosine_similarity)
    print("MOJO_RESULT vector_similarity::cosine_similarity", _summary_cosine_similarity)
    var _acc_dot_product: Float64 = 0.0
    var _t0_dot_product = perf_counter_ns()
    for _ in range(N):
        _acc_dot_product += dot_product(0.5)
    var _t1_dot_product = perf_counter_ns()
    var _ns_dot_product = Float64(_t1_dot_product - _t0_dot_product) / Float64(N)
    print("MOJO_TIMING vector_similarity::dot_product", _ns_dot_product, _acc_dot_product)
    var _result_dot_product = dot_product(0.5)
    var _summary_dot_product = _summary_float64(_result_dot_product)
    print("MOJO_RESULT vector_similarity::dot_product", _summary_dot_product)
    var _acc_euclidean_distance: Float64 = 0.0
    var _t0_euclidean_distance = perf_counter_ns()
    for _ in range(N):
        _acc_euclidean_distance += euclidean_distance(0.5)
    var _t1_euclidean_distance = perf_counter_ns()
    var _ns_euclidean_distance = Float64(_t1_euclidean_distance - _t0_euclidean_distance) / Float64(N)
    print("MOJO_TIMING vector_similarity::euclidean_distance", _ns_euclidean_distance, _acc_euclidean_distance)
    var _result_euclidean_distance = euclidean_distance(0.5)
    var _summary_euclidean_distance = _summary_float64(_result_euclidean_distance)
    print("MOJO_RESULT vector_similarity::euclidean_distance", _summary_euclidean_distance)
    var _acc_manhattan_distance: Float64 = 0.0
    var _t0_manhattan_distance = perf_counter_ns()
    for _ in range(N):
        _acc_manhattan_distance += manhattan_distance(0.5)
    var _t1_manhattan_distance = perf_counter_ns()
    var _ns_manhattan_distance = Float64(_t1_manhattan_distance - _t0_manhattan_distance) / Float64(N)
    print("MOJO_TIMING vector_similarity::manhattan_distance", _ns_manhattan_distance, _acc_manhattan_distance)
    var _result_manhattan_distance = manhattan_distance(0.5)
    var _summary_manhattan_distance = _summary_float64(_result_manhattan_distance)
    print("MOJO_RESULT vector_similarity::manhattan_distance", _summary_manhattan_distance)
    var _acc_chebyshev_distance: Float64 = 0.0
    var _t0_chebyshev_distance = perf_counter_ns()
    for _ in range(N):
        _acc_chebyshev_distance += chebyshev_distance(0.5)
    var _t1_chebyshev_distance = perf_counter_ns()
    var _ns_chebyshev_distance = Float64(_t1_chebyshev_distance - _t0_chebyshev_distance) / Float64(N)
    print("MOJO_TIMING vector_similarity::chebyshev_distance", _ns_chebyshev_distance, _acc_chebyshev_distance)
    var _result_chebyshev_distance = chebyshev_distance(0.5)
    var _summary_chebyshev_distance = _summary_float64(_result_chebyshev_distance)
    print("MOJO_RESULT vector_similarity::chebyshev_distance", _summary_chebyshev_distance)
    var _acc_hamming_distance_bits: Float64 = 0.0
    var _t0_hamming_distance_bits = perf_counter_ns()
    for _ in range(N):
        _acc_hamming_distance_bits += hamming_distance_bits(0.5, 0.5)
    var _t1_hamming_distance_bits = perf_counter_ns()
    var _ns_hamming_distance_bits = Float64(_t1_hamming_distance_bits - _t0_hamming_distance_bits) / Float64(N)
    print("MOJO_TIMING vector_similarity::hamming_distance_bits", _ns_hamming_distance_bits, _acc_hamming_distance_bits)
    var _result_hamming_distance_bits = hamming_distance_bits(0.5, 0.5)
    var _summary_hamming_distance_bits = _summary_float64(_result_hamming_distance_bits)
    print("MOJO_RESULT vector_similarity::hamming_distance_bits", _summary_hamming_distance_bits)
    var _acc_jaccard_similarity: Float64 = 0.0
    var _t0_jaccard_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_jaccard_similarity += jaccard_similarity(0.5, 0.5)
    var _t1_jaccard_similarity = perf_counter_ns()
    var _ns_jaccard_similarity = Float64(_t1_jaccard_similarity - _t0_jaccard_similarity) / Float64(N)
    print("MOJO_TIMING vector_similarity::jaccard_similarity", _ns_jaccard_similarity, _acc_jaccard_similarity)
    var _result_jaccard_similarity = jaccard_similarity(0.5, 0.5)
    var _summary_jaccard_similarity = _summary_float64(_result_jaccard_similarity)
    print("MOJO_RESULT vector_similarity::jaccard_similarity", _summary_jaccard_similarity)
    var _acc_pearson_correlation: Float64 = 0.0
    var _t0_pearson_correlation = perf_counter_ns()
    for _ in range(N):
        _acc_pearson_correlation += pearson_correlation(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_pearson_correlation = perf_counter_ns()
    var _ns_pearson_correlation = Float64(_t1_pearson_correlation - _t0_pearson_correlation) / Float64(N)
    print("MOJO_TIMING vector_similarity::pearson_correlation", _ns_pearson_correlation, _acc_pearson_correlation)
    var _result_pearson_correlation = pearson_correlation(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_pearson_correlation = _summary_float64(_result_pearson_correlation)
    print("MOJO_RESULT vector_similarity::pearson_correlation", _summary_pearson_correlation)
    var _acc_minkowski_distance: Float64 = 0.0
    var _t0_minkowski_distance = perf_counter_ns()
    for _ in range(N):
        _acc_minkowski_distance += minkowski_distance(0.5, 0.5)
    var _t1_minkowski_distance = perf_counter_ns()
    var _ns_minkowski_distance = Float64(_t1_minkowski_distance - _t0_minkowski_distance) / Float64(N)
    print("MOJO_TIMING vector_similarity::minkowski_distance", _ns_minkowski_distance, _acc_minkowski_distance)
    var _result_minkowski_distance = minkowski_distance(0.5, 0.5)
    var _summary_minkowski_distance = _summary_float64(_result_minkowski_distance)
    print("MOJO_RESULT vector_similarity::minkowski_distance", _summary_minkowski_distance)
    var _acc_angular_distance: Float64 = 0.0
    var _t0_angular_distance = perf_counter_ns()
    for _ in range(N):
        _acc_angular_distance += angular_distance(0.5, 0.5, 0.5)
    var _t1_angular_distance = perf_counter_ns()
    var _ns_angular_distance = Float64(_t1_angular_distance - _t0_angular_distance) / Float64(N)
    print("MOJO_TIMING vector_similarity::angular_distance", _ns_angular_distance, _acc_angular_distance)
    var _result_angular_distance = angular_distance(0.5, 0.5, 0.5)
    var _summary_angular_distance = _summary_float64(_result_angular_distance)
    print("MOJO_RESULT vector_similarity::angular_distance", _summary_angular_distance)
