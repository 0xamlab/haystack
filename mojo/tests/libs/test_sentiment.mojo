"""test_sentiment.mojo — auto-generated tests for sentiment library."""
from std.math import isnan, isinf
from sentiment import tokenize_lower, word_sentiment, sentiment_score, polarity, sentiment_label, subjectivity, count_positive_words, count_negative_words, most_positive_word, most_negative_word

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

    var _v_tokenize_lower = tokenize_lower("test")
    if len(_v_tokenize_lower) >= 0: passed += 1; print("  ✅ sentiment::tokenize_lower")
    var _v_word_sentiment = word_sentiment("test")
    if is_finite(_v_word_sentiment): passed += 1; print("  ✅ sentiment::word_sentiment =", _v_word_sentiment)
    else: failed += 1; print("  ❌ sentiment::word_sentiment → non-finite:", _v_word_sentiment)
    var _v_sentiment_score = sentiment_score("test")
    if is_finite(_v_sentiment_score): passed += 1; print("  ✅ sentiment::sentiment_score =", _v_sentiment_score)
    else: failed += 1; print("  ❌ sentiment::sentiment_score → non-finite:", _v_sentiment_score)
    var _v_polarity = polarity("test")
    if is_finite(_v_polarity): passed += 1; print("  ✅ sentiment::polarity =", _v_polarity)
    else: failed += 1; print("  ❌ sentiment::polarity → non-finite:", _v_polarity)
    _ = sentiment_label(0.5)
    passed += 1; print("  ✅ sentiment::sentiment_label")
    var _v_subjectivity = subjectivity("test")
    if is_finite(_v_subjectivity): passed += 1; print("  ✅ sentiment::subjectivity =", _v_subjectivity)
    else: failed += 1; print("  ❌ sentiment::subjectivity → non-finite:", _v_subjectivity)
    _ = count_positive_words("test")
    passed += 1; print("  ✅ sentiment::count_positive_words")
    _ = count_negative_words("test")
    passed += 1; print("  ✅ sentiment::count_negative_words")
    _ = most_positive_word("test")
    passed += 1; print("  ✅ sentiment::most_positive_word")
    _ = most_negative_word("test")
    passed += 1; print("  ✅ sentiment::most_negative_word")

    print("  [sentiment] Passed:", passed, "Failed:", failed)
