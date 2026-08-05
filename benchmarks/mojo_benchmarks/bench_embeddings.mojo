"""bench_embeddings.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from embeddings import dot_product, dot_product_strict, vector_magnitude, cosine_similarity, cosine_similarity_strict, euclidean_distance, euclidean_distance_strict, manhattan_distance, manhattan_distance_strict, normalize_vector, centroid, nearest_neighbor, nearest_neighbor_strict, k_nearest_neighbors, k_nearest_neighbors_strict, cosine_similarity_matrix, cosine_similarity_matrix_strict, vector_add, vector_add_strict, vector_scale
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

fn _summary_list_float64_rounded6(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64_rounded6(value[i])
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
    var _lf12_colorcheck2x2 = List[Float64]()
    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)
    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)
    _lf12_colorcheck2x2.append(200.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0)
    _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(20.0); _lf12_colorcheck2x2.append(200.0)
    var _lf48_video3x4x4 = List[Float64]()
    for _ in range(16):
        _lf48_video3x4x4.append(10.0)
    for pixel in range(16):
        if pixel < 4:
            _lf48_video3x4x4.append(200.0)
        else:
            _lf48_video3x4x4.append(10.0)
    for _ in range(16):
        _lf48_video3x4x4.append(200.0)
    var _lf48_video3x4x4_alt = List[Float64]()
    for _ in range(16):
        _lf48_video3x4x4_alt.append(12.0)
    for pixel in range(16):
        if pixel < 4:
            _lf48_video3x4x4_alt.append(188.0)
        else:
            _lf48_video3x4x4_alt.append(12.0)
    for _ in range(16):
        _lf48_video3x4x4_alt.append(192.0)
    var _lf36_video_rgb3x2x2 = List[Float64]()
    for _ in range(4):
        _lf36_video_rgb3x2x2.append(200.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0)
    for pixel in range(4):
        if pixel < 3:
            _lf36_video_rgb3x2x2.append(200.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0)
        else:
            _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(200.0)
    for _ in range(4):
        _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(20.0); _lf36_video_rgb3x2x2.append(200.0)
    var _lf25_block5x5 = List[Float64]()
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 3 and x >= 1 and x <= 3:
                _lf25_block5x5.append(255.0)
            else:
                _lf25_block5x5.append(0.0)
    var _lf25_ring5x5 = List[Float64]()
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 3 and x >= 1 and x <= 3 and not (y == 2 and x == 2):
                _lf25_ring5x5.append(255.0)
            else:
                _lf25_ring5x5.append(0.0)
    var _lf36_components6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if (x == 0 and (y == 1 or y == 2)) or ((x == 3 and (y == 1 or y == 2 or y == 3)) or (x == 4 and y == 1)):
                _lf36_components6x6.append(255.0)
            else:
                _lf36_components6x6.append(0.0)
    var _lf64_doc8x8 = List[Float64]()
    var _lf64_doc8x8_alt = List[Float64]()
    var _lf64_docmask8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if (y == 2 and x >= 1 and x <= 6) or (y == 5 and x >= 2 and x <= 5):
                _lf64_doc8x8.append(20.0)
                _lf64_doc8x8_alt.append(60.0)
                _lf64_docmask8x8.append(255.0)
            else:
                _lf64_doc8x8.append(240.0)
                _lf64_doc8x8_alt.append(235.0)
                _lf64_docmask8x8.append(0.0)
    var _lf36_adaptive_doc6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if y == 2 and x >= 2 and x <= 3:
                _lf36_adaptive_doc6x6.append(40.0)
            elif x < 3:
                _lf36_adaptive_doc6x6.append(220.0)
            else:
                _lf36_adaptive_doc6x6.append(245.0)
    var _lf36_skewmask6x6 = List[Float64]()
    for y in range(6):
        for x in range(6):
            if y >= 1 and y <= 4 and x == y:
                _lf36_skewmask6x6.append(255.0)
            else:
                _lf36_skewmask6x6.append(0.0)
    var _lf64_blobdoc8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if (y >= 2 and y <= 4 and x >= 1 and x <= 3) or (x == 6 and (y == 1 or y == 2)):
                _lf64_blobdoc8x8.append(20.0)
            else:
                _lf64_blobdoc8x8.append(235.0)
    var _lf64_doccolumns8x8 = List[Float64]()
    for y in range(8):
        for x in range(8):
            if y >= 1 and y <= 6 and ((x >= 1 and x <= 2) or (x >= 5 and x <= 6)):
                _lf64_doccolumns8x8.append(255.0)
            else:
                _lf64_doccolumns8x8.append(0.0)
    var _lf81_doctable9x9 = List[Float64]()
    for y in range(9):
        for x in range(9):
            if ((y >= 1 and y <= 2) or (y >= 4 and y <= 5) or (y >= 7 and y <= 8)) and ((x >= 1 and x <= 2) or (x >= 4 and x <= 5) or (x >= 7 and x <= 8)):
                _lf81_doctable9x9.append(255.0)
            else:
                _lf81_doctable9x9.append(0.0)
    var _lf256_texture16x16 = List[Float64]()
    for y in range(16):
        for x in range(16):
            if y >= 8 and x >= 8:
                _lf256_texture16x16.append(255.0 if (x + y) % 2 == 0 else 0.0)
            else:
                _lf256_texture16x16.append(64.0)
    var _lf75_video_motion3x5x5 = List[Float64]()
    for _ in range(25):
        _lf75_video_motion3x5x5.append(10.0)
    for y in range(5):
        for x in range(5):
            if y >= 1 and y <= 2 and x >= 1 and x <= 2:
                _lf75_video_motion3x5x5.append(200.0)
            else:
                _lf75_video_motion3x5x5.append(10.0)
    for y in range(5):
        for x in range(5):
            if (y >= 1 and y <= 2 and x >= 1 and x <= 2) or (x == 4 and y == 4):
                _lf75_video_motion3x5x5.append(200.0)
            else:
                _lf75_video_motion3x5x5.append(10.0)
    var _lf16_grid4x4 = List[Float64]()
    for i in range(16):
        _lf16_grid4x4.append(Float64(i))
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _li4_box_a = List[Int]()
    _li4_box_a.append(0); _li4_box_a.append(0); _li4_box_a.append(2); _li4_box_a.append(2)
    var _li4_box_b = List[Int]()
    _li4_box_b.append(1); _li4_box_b.append(1); _li4_box_b.append(3); _li4_box_b.append(3)
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
    var _llf3_imageops = List[List[Float64]]()
    _llf3_imageops.append(List[Float64]()); _llf3_imageops.append(List[Float64]()); _llf3_imageops.append(List[Float64]())
    _llf3_imageops[0].append(0.5); _llf3_imageops[0].append(0.6); _llf3_imageops[0].append(0.7)
    _llf3_imageops[1].append(0.4); _llf3_imageops[1].append(0.3); _llf3_imageops[1].append(0.2)
    _llf3_imageops[2].append(0.1); _llf3_imageops[2].append(0.2); _llf3_imageops[2].append(0.3)
    var N: Int = 10000

    var _acc_dot_product: Float64 = 0.0
    var _t0_dot_product = perf_counter_ns()
    for _ in range(N):
        _acc_dot_product += dot_product(_lf5, _lf5)
    var _t1_dot_product = perf_counter_ns()
    var _ns_dot_product = Float64(_t1_dot_product - _t0_dot_product) / Float64(N)
    print("MOJO_TIMING embeddings::dot_product", _ns_dot_product, _acc_dot_product)
    var _result_dot_product = dot_product(_lf5, _lf5)
    var _summary_dot_product = _summary_float64(_result_dot_product)
    print("MOJO_RESULT embeddings::dot_product", _summary_dot_product)
    var _acc_dot_product_strict: Float64 = 0.0
    var _t0_dot_product_strict = perf_counter_ns()
    for _ in range(N):
        _acc_dot_product_strict += dot_product_strict(_lf5, _lf5)
    var _t1_dot_product_strict = perf_counter_ns()
    var _ns_dot_product_strict = Float64(_t1_dot_product_strict - _t0_dot_product_strict) / Float64(N)
    print("MOJO_TIMING embeddings::dot_product_strict", _ns_dot_product_strict, _acc_dot_product_strict)
    var _result_dot_product_strict = dot_product_strict(_lf5, _lf5)
    var _summary_dot_product_strict = _summary_float64(_result_dot_product_strict)
    print("MOJO_RESULT embeddings::dot_product_strict", _summary_dot_product_strict)
    var _acc_vector_magnitude: Float64 = 0.0
    var _t0_vector_magnitude = perf_counter_ns()
    for _ in range(N):
        _acc_vector_magnitude += vector_magnitude(_lf5)
    var _t1_vector_magnitude = perf_counter_ns()
    var _ns_vector_magnitude = Float64(_t1_vector_magnitude - _t0_vector_magnitude) / Float64(N)
    print("MOJO_TIMING embeddings::vector_magnitude", _ns_vector_magnitude, _acc_vector_magnitude)
    var _result_vector_magnitude = vector_magnitude(_lf5)
    var _summary_vector_magnitude = _summary_float64(_result_vector_magnitude)
    print("MOJO_RESULT embeddings::vector_magnitude", _summary_vector_magnitude)
    var _acc_cosine_similarity: Float64 = 0.0
    var _t0_cosine_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_similarity += cosine_similarity(_lf5, _lf5)
    var _t1_cosine_similarity = perf_counter_ns()
    var _ns_cosine_similarity = Float64(_t1_cosine_similarity - _t0_cosine_similarity) / Float64(N)
    print("MOJO_TIMING embeddings::cosine_similarity", _ns_cosine_similarity, _acc_cosine_similarity)
    var _result_cosine_similarity = cosine_similarity(_lf5, _lf5)
    var _summary_cosine_similarity = _summary_float64(_result_cosine_similarity)
    print("MOJO_RESULT embeddings::cosine_similarity", _summary_cosine_similarity)
    var _acc_cosine_similarity_strict: Float64 = 0.0
    var _t0_cosine_similarity_strict = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_similarity_strict += cosine_similarity_strict(_lf5, _lf5)
    var _t1_cosine_similarity_strict = perf_counter_ns()
    var _ns_cosine_similarity_strict = Float64(_t1_cosine_similarity_strict - _t0_cosine_similarity_strict) / Float64(N)
    print("MOJO_TIMING embeddings::cosine_similarity_strict", _ns_cosine_similarity_strict, _acc_cosine_similarity_strict)
    var _result_cosine_similarity_strict = cosine_similarity_strict(_lf5, _lf5)
    var _summary_cosine_similarity_strict = _summary_float64(_result_cosine_similarity_strict)
    print("MOJO_RESULT embeddings::cosine_similarity_strict", _summary_cosine_similarity_strict)
    var _acc_euclidean_distance: Float64 = 0.0
    var _t0_euclidean_distance = perf_counter_ns()
    for _ in range(N):
        _acc_euclidean_distance += euclidean_distance(_lf5, _lf5)
    var _t1_euclidean_distance = perf_counter_ns()
    var _ns_euclidean_distance = Float64(_t1_euclidean_distance - _t0_euclidean_distance) / Float64(N)
    print("MOJO_TIMING embeddings::euclidean_distance", _ns_euclidean_distance, _acc_euclidean_distance)
    var _result_euclidean_distance = euclidean_distance(_lf5, _lf5)
    var _summary_euclidean_distance = _summary_float64(_result_euclidean_distance)
    print("MOJO_RESULT embeddings::euclidean_distance", _summary_euclidean_distance)
    var _acc_euclidean_distance_strict: Float64 = 0.0
    var _t0_euclidean_distance_strict = perf_counter_ns()
    for _ in range(N):
        _acc_euclidean_distance_strict += euclidean_distance_strict(_lf5, _lf5)
    var _t1_euclidean_distance_strict = perf_counter_ns()
    var _ns_euclidean_distance_strict = Float64(_t1_euclidean_distance_strict - _t0_euclidean_distance_strict) / Float64(N)
    print("MOJO_TIMING embeddings::euclidean_distance_strict", _ns_euclidean_distance_strict, _acc_euclidean_distance_strict)
    var _result_euclidean_distance_strict = euclidean_distance_strict(_lf5, _lf5)
    var _summary_euclidean_distance_strict = _summary_float64(_result_euclidean_distance_strict)
    print("MOJO_RESULT embeddings::euclidean_distance_strict", _summary_euclidean_distance_strict)
    var _acc_manhattan_distance: Float64 = 0.0
    var _t0_manhattan_distance = perf_counter_ns()
    for _ in range(N):
        _acc_manhattan_distance += manhattan_distance(_lf5, _lf5)
    var _t1_manhattan_distance = perf_counter_ns()
    var _ns_manhattan_distance = Float64(_t1_manhattan_distance - _t0_manhattan_distance) / Float64(N)
    print("MOJO_TIMING embeddings::manhattan_distance", _ns_manhattan_distance, _acc_manhattan_distance)
    var _result_manhattan_distance = manhattan_distance(_lf5, _lf5)
    var _summary_manhattan_distance = _summary_float64(_result_manhattan_distance)
    print("MOJO_RESULT embeddings::manhattan_distance", _summary_manhattan_distance)
    var _acc_manhattan_distance_strict: Float64 = 0.0
    var _t0_manhattan_distance_strict = perf_counter_ns()
    for _ in range(N):
        _acc_manhattan_distance_strict += manhattan_distance_strict(_lf5, _lf5)
    var _t1_manhattan_distance_strict = perf_counter_ns()
    var _ns_manhattan_distance_strict = Float64(_t1_manhattan_distance_strict - _t0_manhattan_distance_strict) / Float64(N)
    print("MOJO_TIMING embeddings::manhattan_distance_strict", _ns_manhattan_distance_strict, _acc_manhattan_distance_strict)
    var _result_manhattan_distance_strict = manhattan_distance_strict(_lf5, _lf5)
    var _summary_manhattan_distance_strict = _summary_float64(_result_manhattan_distance_strict)
    print("MOJO_RESULT embeddings::manhattan_distance_strict", _summary_manhattan_distance_strict)
    var _acc_normalize_vector: Float64 = 0.0
    var _t0_normalize_vector = perf_counter_ns()
    for _ in range(N):
        var _r_normalize_vector = normalize_vector(_lf5)
        _acc_normalize_vector += Float64(len(_r_normalize_vector))
    var _t1_normalize_vector = perf_counter_ns()
    var _ns_normalize_vector = Float64(_t1_normalize_vector - _t0_normalize_vector) / Float64(N)
    print("MOJO_TIMING embeddings::normalize_vector", _ns_normalize_vector, _acc_normalize_vector)
    var _result_normalize_vector = normalize_vector(_lf5)
    var _summary_normalize_vector = _summary_list_float64(_result_normalize_vector)
    print("MOJO_RESULT embeddings::normalize_vector", _summary_normalize_vector)
    var _acc_centroid: Float64 = 0.0
    var _t0_centroid = perf_counter_ns()
    for _ in range(N):
        var _r_centroid = centroid([[0.5,0.6,0.7,0.4,0.3],[0.6,0.7,0.4,0.3,0.5],[0.7,0.4,0.3,0.5,0.6]])
        _acc_centroid += Float64(len(_r_centroid))
    var _t1_centroid = perf_counter_ns()
    var _ns_centroid = Float64(_t1_centroid - _t0_centroid) / Float64(N)
    print("MOJO_TIMING embeddings::centroid", _ns_centroid, _acc_centroid)
    var _result_centroid = centroid([[0.5,0.6,0.7,0.4,0.3],[0.6,0.7,0.4,0.3,0.5],[0.7,0.4,0.3,0.5,0.6]])
    var _summary_centroid = _summary_list_float64(_result_centroid)
    print("MOJO_RESULT embeddings::centroid", _summary_centroid)
    var _acc_nearest_neighbor: Float64 = 0.0
    var _t0_nearest_neighbor = perf_counter_ns()
    for _ in range(N):
        _acc_nearest_neighbor += Float64(nearest_neighbor(_lf5, [[0.5,0.6,0.7,0.4,0.3],[0.6,0.7,0.4,0.3,0.5],[0.7,0.4,0.3,0.5,0.6]]))
    var _t1_nearest_neighbor = perf_counter_ns()
    var _ns_nearest_neighbor = Float64(_t1_nearest_neighbor - _t0_nearest_neighbor) / Float64(N)
    print("MOJO_TIMING embeddings::nearest_neighbor", _ns_nearest_neighbor, _acc_nearest_neighbor)
    var _result_nearest_neighbor = nearest_neighbor(_lf5, [[0.5,0.6,0.7,0.4,0.3],[0.6,0.7,0.4,0.3,0.5],[0.7,0.4,0.3,0.5,0.6]])
    var _summary_nearest_neighbor = _summary_int(_result_nearest_neighbor)
    print("MOJO_RESULT embeddings::nearest_neighbor", _summary_nearest_neighbor)
    var _acc_nearest_neighbor_strict: Float64 = 0.0
    var _t0_nearest_neighbor_strict = perf_counter_ns()
    for _ in range(N):
        _acc_nearest_neighbor_strict += Float64(nearest_neighbor_strict(_lf5, [[0.5,0.6,0.7,0.4,0.3],[0.6,0.7,0.4,0.3,0.5],[0.7,0.4,0.3,0.5,0.6]]))
    var _t1_nearest_neighbor_strict = perf_counter_ns()
    var _ns_nearest_neighbor_strict = Float64(_t1_nearest_neighbor_strict - _t0_nearest_neighbor_strict) / Float64(N)
    print("MOJO_TIMING embeddings::nearest_neighbor_strict", _ns_nearest_neighbor_strict, _acc_nearest_neighbor_strict)
    var _result_nearest_neighbor_strict = nearest_neighbor_strict(_lf5, [[0.5,0.6,0.7,0.4,0.3],[0.6,0.7,0.4,0.3,0.5],[0.7,0.4,0.3,0.5,0.6]])
    var _summary_nearest_neighbor_strict = _summary_int(_result_nearest_neighbor_strict)
    print("MOJO_RESULT embeddings::nearest_neighbor_strict", _summary_nearest_neighbor_strict)
    var _acc_k_nearest_neighbors: Float64 = 0.0
    var _t0_k_nearest_neighbors = perf_counter_ns()
    for _ in range(N):
        var _r_k_nearest_neighbors = k_nearest_neighbors(_lf5, [[0.5,0.6,0.7,0.4,0.3],[0.6,0.7,0.4,0.3,0.5],[0.7,0.4,0.3,0.5,0.6]], 5)
        _acc_k_nearest_neighbors += Float64(len(_r_k_nearest_neighbors))
    var _t1_k_nearest_neighbors = perf_counter_ns()
    var _ns_k_nearest_neighbors = Float64(_t1_k_nearest_neighbors - _t0_k_nearest_neighbors) / Float64(N)
    print("MOJO_TIMING embeddings::k_nearest_neighbors", _ns_k_nearest_neighbors, _acc_k_nearest_neighbors)
    var _result_k_nearest_neighbors = k_nearest_neighbors(_lf5, [[0.5,0.6,0.7,0.4,0.3],[0.6,0.7,0.4,0.3,0.5],[0.7,0.4,0.3,0.5,0.6]], 5)
    var _summary_k_nearest_neighbors = _summary_list_int(_result_k_nearest_neighbors)
    print("MOJO_RESULT embeddings::k_nearest_neighbors", _summary_k_nearest_neighbors)
    var _acc_k_nearest_neighbors_strict: Float64 = 0.0
    var _t0_k_nearest_neighbors_strict = perf_counter_ns()
    for _ in range(N):
        var _r_k_nearest_neighbors_strict = k_nearest_neighbors_strict(_lf5, [[0.5,0.6,0.7,0.4,0.3],[0.6,0.7,0.4,0.3,0.5],[0.7,0.4,0.3,0.5,0.6]], 5)
        _acc_k_nearest_neighbors_strict += Float64(len(_r_k_nearest_neighbors_strict))
    var _t1_k_nearest_neighbors_strict = perf_counter_ns()
    var _ns_k_nearest_neighbors_strict = Float64(_t1_k_nearest_neighbors_strict - _t0_k_nearest_neighbors_strict) / Float64(N)
    print("MOJO_TIMING embeddings::k_nearest_neighbors_strict", _ns_k_nearest_neighbors_strict, _acc_k_nearest_neighbors_strict)
    var _result_k_nearest_neighbors_strict = k_nearest_neighbors_strict(_lf5, [[0.5,0.6,0.7,0.4,0.3],[0.6,0.7,0.4,0.3,0.5],[0.7,0.4,0.3,0.5,0.6]], 5)
    var _summary_k_nearest_neighbors_strict = _summary_list_int(_result_k_nearest_neighbors_strict)
    print("MOJO_RESULT embeddings::k_nearest_neighbors_strict", _summary_k_nearest_neighbors_strict)
    var _acc_cosine_similarity_matrix: Float64 = 0.0
    var _t0_cosine_similarity_matrix = perf_counter_ns()
    for _ in range(N):
        var _r_cosine_similarity_matrix = cosine_similarity_matrix([[0.5,0.6,0.7,0.4,0.3],[0.6,0.7,0.4,0.3,0.5],[0.7,0.4,0.3,0.5,0.6]])
        _acc_cosine_similarity_matrix += Float64(len(_r_cosine_similarity_matrix))
    var _t1_cosine_similarity_matrix = perf_counter_ns()
    var _ns_cosine_similarity_matrix = Float64(_t1_cosine_similarity_matrix - _t0_cosine_similarity_matrix) / Float64(N)
    print("MOJO_TIMING embeddings::cosine_similarity_matrix", _ns_cosine_similarity_matrix, _acc_cosine_similarity_matrix)
    var _result_cosine_similarity_matrix = cosine_similarity_matrix([[0.5,0.6,0.7,0.4,0.3],[0.6,0.7,0.4,0.3,0.5],[0.7,0.4,0.3,0.5,0.6]])
    var _summary_cosine_similarity_matrix = _summary_list_list_float64_rounded6(_result_cosine_similarity_matrix)
    print("MOJO_RESULT embeddings::cosine_similarity_matrix", _summary_cosine_similarity_matrix)
    var _acc_cosine_similarity_matrix_strict: Float64 = 0.0
    var _t0_cosine_similarity_matrix_strict = perf_counter_ns()
    for _ in range(N):
        var _r_cosine_similarity_matrix_strict = cosine_similarity_matrix_strict([[0.5,0.6,0.7,0.4,0.3],[0.6,0.7,0.4,0.3,0.5],[0.7,0.4,0.3,0.5,0.6]])
        _acc_cosine_similarity_matrix_strict += Float64(len(_r_cosine_similarity_matrix_strict))
    var _t1_cosine_similarity_matrix_strict = perf_counter_ns()
    var _ns_cosine_similarity_matrix_strict = Float64(_t1_cosine_similarity_matrix_strict - _t0_cosine_similarity_matrix_strict) / Float64(N)
    print("MOJO_TIMING embeddings::cosine_similarity_matrix_strict", _ns_cosine_similarity_matrix_strict, _acc_cosine_similarity_matrix_strict)
    var _result_cosine_similarity_matrix_strict = cosine_similarity_matrix_strict([[0.5,0.6,0.7,0.4,0.3],[0.6,0.7,0.4,0.3,0.5],[0.7,0.4,0.3,0.5,0.6]])
    var _summary_cosine_similarity_matrix_strict = _summary_list_list_float64(_result_cosine_similarity_matrix_strict)
    print("MOJO_RESULT embeddings::cosine_similarity_matrix_strict", _summary_cosine_similarity_matrix_strict)
    var _acc_vector_add: Float64 = 0.0
    var _t0_vector_add = perf_counter_ns()
    for _ in range(N):
        var _r_vector_add = vector_add(_lf5, _lf5)
        _acc_vector_add += Float64(len(_r_vector_add))
    var _t1_vector_add = perf_counter_ns()
    var _ns_vector_add = Float64(_t1_vector_add - _t0_vector_add) / Float64(N)
    print("MOJO_TIMING embeddings::vector_add", _ns_vector_add, _acc_vector_add)
    var _result_vector_add = vector_add(_lf5, _lf5)
    var _summary_vector_add = _summary_list_float64(_result_vector_add)
    print("MOJO_RESULT embeddings::vector_add", _summary_vector_add)
    var _acc_vector_add_strict: Float64 = 0.0
    var _t0_vector_add_strict = perf_counter_ns()
    for _ in range(N):
        var _r_vector_add_strict = vector_add_strict(_lf5, _lf5)
        _acc_vector_add_strict += Float64(len(_r_vector_add_strict))
    var _t1_vector_add_strict = perf_counter_ns()
    var _ns_vector_add_strict = Float64(_t1_vector_add_strict - _t0_vector_add_strict) / Float64(N)
    print("MOJO_TIMING embeddings::vector_add_strict", _ns_vector_add_strict, _acc_vector_add_strict)
    var _result_vector_add_strict = vector_add_strict(_lf5, _lf5)
    var _summary_vector_add_strict = _summary_list_float64(_result_vector_add_strict)
    print("MOJO_RESULT embeddings::vector_add_strict", _summary_vector_add_strict)
    var _acc_vector_scale: Float64 = 0.0
    var _t0_vector_scale = perf_counter_ns()
    for _ in range(N):
        var _r_vector_scale = vector_scale(_lf5, 0.5)
        _acc_vector_scale += Float64(len(_r_vector_scale))
    var _t1_vector_scale = perf_counter_ns()
    var _ns_vector_scale = Float64(_t1_vector_scale - _t0_vector_scale) / Float64(N)
    print("MOJO_TIMING embeddings::vector_scale", _ns_vector_scale, _acc_vector_scale)
    var _result_vector_scale = vector_scale(_lf5, 0.5)
    var _summary_vector_scale = _summary_list_float64(_result_vector_scale)
    print("MOJO_RESULT embeddings::vector_scale", _summary_vector_scale)
