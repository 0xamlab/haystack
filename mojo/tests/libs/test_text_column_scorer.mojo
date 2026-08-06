"""test_text_column_scorer.mojo — auto-generated tests for text.column_scorer."""
from std.math import isnan, isinf
from text.column_scorer import score_token_overlap, score_ngram_overlap, score_prefix_match, score_column_hint

def is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _li3 = List[Int]()
    _li3.append(1); _li3.append(2); _li3.append(3)
    var _li2_zero = List[Int]()
    _li2_zero.append(0); _li2_zero.append(1)
    var _li3_tail = List[Int]()
    _li3_tail.append(2); _li3_tail.append(3); _li3_tail.append(4)
    var _li8 = List[Int]()
    for i in range(8):
        _li8.append(i + 1)
    var _li6_grid2x3 = List[Int]()
    _li6_grid2x3.append(0); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    _li6_grid2x3.append(1); _li6_grid2x3.append(1); _li6_grid2x3.append(0)
    var _li10_borda = List[Int]()
    _li10_borda.append(0); _li10_borda.append(1); _li10_borda.append(2); _li10_borda.append(3); _li10_borda.append(4)
    _li10_borda.append(1); _li10_borda.append(0); _li10_borda.append(2); _li10_borda.append(4); _li10_borda.append(3)
    var _li16 = List[Int]()
    for i in range(16):
        _li16.append(i)
    var _lf6_matrix = List[Float64]()
    _lf6_matrix.append(1.0); _lf6_matrix.append(2.0); _lf6_matrix.append(3.0)
    _lf6_matrix.append(4.0); _lf6_matrix.append(5.0); _lf6_matrix.append(6.0)
    var _lf8_coalitions = List[Float64]()
    _lf8_coalitions.append(0.0); _lf8_coalitions.append(1.0); _lf8_coalitions.append(2.0); _lf8_coalitions.append(4.0)
    _lf8_coalitions.append(3.0); _lf8_coalitions.append(5.0); _lf8_coalitions.append(6.0); _lf8_coalitions.append(9.0)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_score_token_overlap = score_token_overlap("test", "test")
    if is_finite(_v_score_token_overlap): passed += 1; print("  ✅ text.column_scorer::score_token_overlap =", _v_score_token_overlap)
    else: failed += 1; print("  ❌ text.column_scorer::score_token_overlap → non-finite:", _v_score_token_overlap)
    var _v_score_ngram_overlap = score_ngram_overlap("test", "test", 5)
    if is_finite(_v_score_ngram_overlap): passed += 1; print("  ✅ text.column_scorer::score_ngram_overlap =", _v_score_ngram_overlap)
    else: failed += 1; print("  ❌ text.column_scorer::score_ngram_overlap → non-finite:", _v_score_ngram_overlap)
    var _v_score_prefix_match = score_prefix_match("test", "test")
    if is_finite(_v_score_prefix_match): passed += 1; print("  ✅ text.column_scorer::score_prefix_match =", _v_score_prefix_match)
    else: failed += 1; print("  ❌ text.column_scorer::score_prefix_match → non-finite:", _v_score_prefix_match)
    var _v_score_column_hint = score_column_hint("test", "test", 0.5, 0.5, 0.5)
    if is_finite(_v_score_column_hint): passed += 1; print("  ✅ text.column_scorer::score_column_hint =", _v_score_column_hint)
    else: failed += 1; print("  ❌ text.column_scorer::score_column_hint → non-finite:", _v_score_column_hint)

    print("  [text.column_scorer] Passed:", passed, "Failed:", failed)
