"""bench_embeddings.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from embeddings import dot_product, vector_magnitude, cosine_similarity, euclidean_distance, manhattan_distance, normalize_vector, centroid, nearest_neighbor, k_nearest_neighbors, cosine_similarity_matrix, vector_add, vector_scale
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

    var _acc_dot_product: Float64 = 0.0
    var _t0_dot_product = perf_counter_ns()
    for _ in range(N):
        _acc_dot_product += dot_product(_lf5, _lf5)
    var _t1_dot_product = perf_counter_ns()
    var _ns_dot_product = Float64(_t1_dot_product - _t0_dot_product) / Float64(N)
    print("MOJO_TIMING embeddings::dot_product", _ns_dot_product, _acc_dot_product)
    var _acc_vector_magnitude: Float64 = 0.0
    var _t0_vector_magnitude = perf_counter_ns()
    for _ in range(N):
        _acc_vector_magnitude += vector_magnitude(_lf5)
    var _t1_vector_magnitude = perf_counter_ns()
    var _ns_vector_magnitude = Float64(_t1_vector_magnitude - _t0_vector_magnitude) / Float64(N)
    print("MOJO_TIMING embeddings::vector_magnitude", _ns_vector_magnitude, _acc_vector_magnitude)
    var _acc_cosine_similarity: Float64 = 0.0
    var _t0_cosine_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_similarity += cosine_similarity(_lf5, _lf5)
    var _t1_cosine_similarity = perf_counter_ns()
    var _ns_cosine_similarity = Float64(_t1_cosine_similarity - _t0_cosine_similarity) / Float64(N)
    print("MOJO_TIMING embeddings::cosine_similarity", _ns_cosine_similarity, _acc_cosine_similarity)
    var _acc_euclidean_distance: Float64 = 0.0
    var _t0_euclidean_distance = perf_counter_ns()
    for _ in range(N):
        _acc_euclidean_distance += euclidean_distance(_lf5, _lf5)
    var _t1_euclidean_distance = perf_counter_ns()
    var _ns_euclidean_distance = Float64(_t1_euclidean_distance - _t0_euclidean_distance) / Float64(N)
    print("MOJO_TIMING embeddings::euclidean_distance", _ns_euclidean_distance, _acc_euclidean_distance)
    var _acc_manhattan_distance: Float64 = 0.0
    var _t0_manhattan_distance = perf_counter_ns()
    for _ in range(N):
        _acc_manhattan_distance += manhattan_distance(_lf5, _lf5)
    var _t1_manhattan_distance = perf_counter_ns()
    var _ns_manhattan_distance = Float64(_t1_manhattan_distance - _t0_manhattan_distance) / Float64(N)
    print("MOJO_TIMING embeddings::manhattan_distance", _ns_manhattan_distance, _acc_manhattan_distance)
    var _acc_normalize_vector: Float64 = 0.0
    var _t0_normalize_vector = perf_counter_ns()
    for _ in range(N):
        var _r_normalize_vector = normalize_vector(_lf5)
        _acc_normalize_vector += Float64(len(_r_normalize_vector))
    var _t1_normalize_vector = perf_counter_ns()
    var _ns_normalize_vector = Float64(_t1_normalize_vector - _t0_normalize_vector) / Float64(N)
    print("MOJO_TIMING embeddings::normalize_vector", _ns_normalize_vector, _acc_normalize_vector)
    var _acc_centroid: Float64 = 0.0
    var _t0_centroid = perf_counter_ns()
    for _ in range(N):
        var _r_centroid = centroid([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_centroid += Float64(len(_r_centroid))
    var _t1_centroid = perf_counter_ns()
    var _ns_centroid = Float64(_t1_centroid - _t0_centroid) / Float64(N)
    print("MOJO_TIMING embeddings::centroid", _ns_centroid, _acc_centroid)
    var _acc_nearest_neighbor: Float64 = 0.0
    var _t0_nearest_neighbor = perf_counter_ns()
    for _ in range(N):
        _acc_nearest_neighbor += Float64(nearest_neighbor(_lf5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]]))
    var _t1_nearest_neighbor = perf_counter_ns()
    var _ns_nearest_neighbor = Float64(_t1_nearest_neighbor - _t0_nearest_neighbor) / Float64(N)
    print("MOJO_TIMING embeddings::nearest_neighbor", _ns_nearest_neighbor, _acc_nearest_neighbor)
    var _acc_k_nearest_neighbors: Float64 = 0.0
    var _t0_k_nearest_neighbors = perf_counter_ns()
    for _ in range(N):
        var _r_k_nearest_neighbors = k_nearest_neighbors(_lf5, [[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]], 5)
        _acc_k_nearest_neighbors += Float64(len(_r_k_nearest_neighbors))
    var _t1_k_nearest_neighbors = perf_counter_ns()
    var _ns_k_nearest_neighbors = Float64(_t1_k_nearest_neighbors - _t0_k_nearest_neighbors) / Float64(N)
    print("MOJO_TIMING embeddings::k_nearest_neighbors", _ns_k_nearest_neighbors, _acc_k_nearest_neighbors)
    var _acc_cosine_similarity_matrix: Float64 = 0.0
    var _t0_cosine_similarity_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_cosine_similarity_matrix = cosine_similarity_matrix([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_cosine_similarity_matrix += Float64(len(_r_cosine_similarity_matrix))
    var _t1_cosine_similarity_matrix = perf_counter_ns()
    var _ns_cosine_similarity_matrix = Float64(_t1_cosine_similarity_matrix - _t0_cosine_similarity_matrix) / Float64(N)
    print("MOJO_TIMING embeddings::cosine_similarity_matrix", _ns_cosine_similarity_matrix, _acc_cosine_similarity_matrix)
    var _acc_vector_add: Float64 = 0.0
    var _t0_vector_add = perf_counter_ns()
    for _ in range(N):
        var _r_vector_add = vector_add(_lf5, _lf5)
        _acc_vector_add += Float64(len(_r_vector_add))
    var _t1_vector_add = perf_counter_ns()
    var _ns_vector_add = Float64(_t1_vector_add - _t0_vector_add) / Float64(N)
    print("MOJO_TIMING embeddings::vector_add", _ns_vector_add, _acc_vector_add)
    var _acc_vector_scale: Float64 = 0.0
    var _t0_vector_scale = perf_counter_ns()
    for _ in range(N):
        var _r_vector_scale = vector_scale(_lf5, 0.5)
        _acc_vector_scale += Float64(len(_r_vector_scale))
    var _t1_vector_scale = perf_counter_ns()
    var _ns_vector_scale = Float64(_t1_vector_scale - _t0_vector_scale) / Float64(N)
    print("MOJO_TIMING embeddings::vector_scale", _ns_vector_scale, _acc_vector_scale)
