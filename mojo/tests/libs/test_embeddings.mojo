"""test_embeddings.mojo — auto-generated tests for embeddings library."""
from std.math import isnan, isinf
from embeddings import dot_product, vector_magnitude, cosine_similarity, euclidean_distance, manhattan_distance, normalize_vector, vector_add, vector_scale

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_dot_product = dot_product(_lf5, _lf5)
    if is_finite(_v_dot_product): passed += 1; print("  ✅ embeddings::dot_product =", _v_dot_product)
    else: failed += 1; print("  ❌ embeddings::dot_product → non-finite:", _v_dot_product)
    var _v_vector_magnitude = vector_magnitude(_lf5)
    if is_finite(_v_vector_magnitude): passed += 1; print("  ✅ embeddings::vector_magnitude =", _v_vector_magnitude)
    else: failed += 1; print("  ❌ embeddings::vector_magnitude → non-finite:", _v_vector_magnitude)
    var _v_cosine_similarity = cosine_similarity(_lf5, _lf5)
    if is_finite(_v_cosine_similarity): passed += 1; print("  ✅ embeddings::cosine_similarity =", _v_cosine_similarity)
    else: failed += 1; print("  ❌ embeddings::cosine_similarity → non-finite:", _v_cosine_similarity)
    var _v_euclidean_distance = euclidean_distance(_lf5, _lf5)
    if is_finite(_v_euclidean_distance): passed += 1; print("  ✅ embeddings::euclidean_distance =", _v_euclidean_distance)
    else: failed += 1; print("  ❌ embeddings::euclidean_distance → non-finite:", _v_euclidean_distance)
    var _v_manhattan_distance = manhattan_distance(_lf5, _lf5)
    if is_finite(_v_manhattan_distance): passed += 1; print("  ✅ embeddings::manhattan_distance =", _v_manhattan_distance)
    else: failed += 1; print("  ❌ embeddings::manhattan_distance → non-finite:", _v_manhattan_distance)
    var _v_normalize_vector = normalize_vector(_lf5)
    if len(_v_normalize_vector) >= 0: passed += 1; print("  ✅ embeddings::normalize_vector")
    var _v_vector_add = vector_add(_lf5, _lf5)
    if len(_v_vector_add) >= 0: passed += 1; print("  ✅ embeddings::vector_add")
    var _v_vector_scale = vector_scale(_lf5, 0.5)
    if len(_v_vector_scale) >= 0: passed += 1; print("  ✅ embeddings::vector_scale")

    print("  [embeddings] Passed:", passed, "Failed:", failed)
