"""bench_vector_similarity.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from vector_similarity import cosine_similarity, dot_product, euclidean_distance, manhattan_distance, chebyshev_distance, hamming_distance_bits, jaccard_similarity, pearson_correlation, minkowski_distance, angular_distance
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

    var _acc_cosine_similarity: Float64 = 0.0
    var _t0_cosine_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_similarity += cosine_similarity(0.5, 0.5, 0.5)
    var _t1_cosine_similarity = perf_counter_ns()
    var _ns_cosine_similarity = Float64(_t1_cosine_similarity - _t0_cosine_similarity) / Float64(N)
    print("MOJO_TIMING vector_similarity::cosine_similarity", _ns_cosine_similarity, _acc_cosine_similarity)
    var _acc_dot_product: Float64 = 0.0
    var _t0_dot_product = perf_counter_ns()
    for _ in range(N):
        _acc_dot_product += dot_product(0.5)
    var _t1_dot_product = perf_counter_ns()
    var _ns_dot_product = Float64(_t1_dot_product - _t0_dot_product) / Float64(N)
    print("MOJO_TIMING vector_similarity::dot_product", _ns_dot_product, _acc_dot_product)
    var _acc_euclidean_distance: Float64 = 0.0
    var _t0_euclidean_distance = perf_counter_ns()
    for _ in range(N):
        _acc_euclidean_distance += euclidean_distance(0.5)
    var _t1_euclidean_distance = perf_counter_ns()
    var _ns_euclidean_distance = Float64(_t1_euclidean_distance - _t0_euclidean_distance) / Float64(N)
    print("MOJO_TIMING vector_similarity::euclidean_distance", _ns_euclidean_distance, _acc_euclidean_distance)
    var _acc_manhattan_distance: Float64 = 0.0
    var _t0_manhattan_distance = perf_counter_ns()
    for _ in range(N):
        _acc_manhattan_distance += manhattan_distance(0.5)
    var _t1_manhattan_distance = perf_counter_ns()
    var _ns_manhattan_distance = Float64(_t1_manhattan_distance - _t0_manhattan_distance) / Float64(N)
    print("MOJO_TIMING vector_similarity::manhattan_distance", _ns_manhattan_distance, _acc_manhattan_distance)
    var _acc_chebyshev_distance: Float64 = 0.0
    var _t0_chebyshev_distance = perf_counter_ns()
    for _ in range(N):
        _acc_chebyshev_distance += chebyshev_distance(0.5)
    var _t1_chebyshev_distance = perf_counter_ns()
    var _ns_chebyshev_distance = Float64(_t1_chebyshev_distance - _t0_chebyshev_distance) / Float64(N)
    print("MOJO_TIMING vector_similarity::chebyshev_distance", _ns_chebyshev_distance, _acc_chebyshev_distance)
    var _acc_hamming_distance_bits: Float64 = 0.0
    var _t0_hamming_distance_bits = perf_counter_ns()
    for _ in range(N):
        _acc_hamming_distance_bits += hamming_distance_bits(0.5, 0.5)
    var _t1_hamming_distance_bits = perf_counter_ns()
    var _ns_hamming_distance_bits = Float64(_t1_hamming_distance_bits - _t0_hamming_distance_bits) / Float64(N)
    print("MOJO_TIMING vector_similarity::hamming_distance_bits", _ns_hamming_distance_bits, _acc_hamming_distance_bits)
    var _acc_jaccard_similarity: Float64 = 0.0
    var _t0_jaccard_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_jaccard_similarity += jaccard_similarity(0.5, 0.5)
    var _t1_jaccard_similarity = perf_counter_ns()
    var _ns_jaccard_similarity = Float64(_t1_jaccard_similarity - _t0_jaccard_similarity) / Float64(N)
    print("MOJO_TIMING vector_similarity::jaccard_similarity", _ns_jaccard_similarity, _acc_jaccard_similarity)
    var _acc_pearson_correlation: Float64 = 0.0
    var _t0_pearson_correlation = perf_counter_ns()
    for _ in range(N):
        _acc_pearson_correlation += pearson_correlation(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_pearson_correlation = perf_counter_ns()
    var _ns_pearson_correlation = Float64(_t1_pearson_correlation - _t0_pearson_correlation) / Float64(N)
    print("MOJO_TIMING vector_similarity::pearson_correlation", _ns_pearson_correlation, _acc_pearson_correlation)
    var _acc_minkowski_distance: Float64 = 0.0
    var _t0_minkowski_distance = perf_counter_ns()
    for _ in range(N):
        _acc_minkowski_distance += minkowski_distance(0.5, 0.5)
    var _t1_minkowski_distance = perf_counter_ns()
    var _ns_minkowski_distance = Float64(_t1_minkowski_distance - _t0_minkowski_distance) / Float64(N)
    print("MOJO_TIMING vector_similarity::minkowski_distance", _ns_minkowski_distance, _acc_minkowski_distance)
    var _acc_angular_distance: Float64 = 0.0
    var _t0_angular_distance = perf_counter_ns()
    for _ in range(N):
        _acc_angular_distance += angular_distance(0.5, 0.5, 0.5)
    var _t1_angular_distance = perf_counter_ns()
    var _ns_angular_distance = Float64(_t1_angular_distance - _t0_angular_distance) / Float64(N)
    print("MOJO_TIMING vector_similarity::angular_distance", _ns_angular_distance, _acc_angular_distance)
