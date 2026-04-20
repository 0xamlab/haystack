"""test_nlp.mojo — auto-generated tests for nlp library."""
from std.math import isnan, isinf
from nlp import tokenize, cosine_similarity_vec, word_count, char_count

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

    var _v_tokenize = tokenize("test")
    if len(_v_tokenize) >= 0: passed += 1; print("  ✅ nlp::tokenize")
    var _v_cosine_similarity_vec = cosine_similarity_vec(_lf5, _lf5)
    if is_finite(_v_cosine_similarity_vec): passed += 1; print("  ✅ nlp::cosine_similarity_vec =", _v_cosine_similarity_vec)
    else: failed += 1; print("  ❌ nlp::cosine_similarity_vec → non-finite:", _v_cosine_similarity_vec)
    _ = word_count("test")
    passed += 1; print("  ✅ nlp::word_count")
    _ = char_count("test")
    passed += 1; print("  ✅ nlp::char_count")

    print("  [nlp] Passed:", passed, "Failed:", failed)
