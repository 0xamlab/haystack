"""bench_sentiment.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from sentiment import tokenize_lower, word_sentiment, sentiment_score, polarity, sentiment_label, subjectivity, count_positive_words, count_negative_words, most_positive_word, most_negative_word
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

    var _acc_tokenize_lower: Float64 = 0.0
    var _t0_tokenize_lower = perf_counter_ns()
    for _ in range(N):
        var _r_tokenize_lower = tokenize_lower("test")
        _acc_tokenize_lower += Float64(len(_r_tokenize_lower))
    var _t1_tokenize_lower = perf_counter_ns()
    var _ns_tokenize_lower = Float64(_t1_tokenize_lower - _t0_tokenize_lower) / Float64(N)
    print("MOJO_TIMING sentiment::tokenize_lower", _ns_tokenize_lower, _acc_tokenize_lower)
    var _acc_word_sentiment: Float64 = 0.0
    var _t0_word_sentiment = perf_counter_ns()
    for _ in range(N):
        _acc_word_sentiment += word_sentiment("test")
    var _t1_word_sentiment = perf_counter_ns()
    var _ns_word_sentiment = Float64(_t1_word_sentiment - _t0_word_sentiment) / Float64(N)
    print("MOJO_TIMING sentiment::word_sentiment", _ns_word_sentiment, _acc_word_sentiment)
    var _acc_sentiment_score: Float64 = 0.0
    var _t0_sentiment_score = perf_counter_ns()
    for _ in range(N):
        _acc_sentiment_score += sentiment_score("test")
    var _t1_sentiment_score = perf_counter_ns()
    var _ns_sentiment_score = Float64(_t1_sentiment_score - _t0_sentiment_score) / Float64(N)
    print("MOJO_TIMING sentiment::sentiment_score", _ns_sentiment_score, _acc_sentiment_score)
    var _acc_polarity: Float64 = 0.0
    var _t0_polarity = perf_counter_ns()
    for _ in range(N):
        _acc_polarity += polarity("test")
    var _t1_polarity = perf_counter_ns()
    var _ns_polarity = Float64(_t1_polarity - _t0_polarity) / Float64(N)
    print("MOJO_TIMING sentiment::polarity", _ns_polarity, _acc_polarity)
    var _acc_sentiment_label: Float64 = 0.0
    var _t0_sentiment_label = perf_counter_ns()
    for _ in range(N):
        _ = sentiment_label(0.5)
    var _t1_sentiment_label = perf_counter_ns()
    var _ns_sentiment_label = Float64(_t1_sentiment_label - _t0_sentiment_label) / Float64(N)
    print("MOJO_TIMING sentiment::sentiment_label", _ns_sentiment_label, _acc_sentiment_label)
    var _acc_subjectivity: Float64 = 0.0
    var _t0_subjectivity = perf_counter_ns()
    for _ in range(N):
        _acc_subjectivity += subjectivity("test")
    var _t1_subjectivity = perf_counter_ns()
    var _ns_subjectivity = Float64(_t1_subjectivity - _t0_subjectivity) / Float64(N)
    print("MOJO_TIMING sentiment::subjectivity", _ns_subjectivity, _acc_subjectivity)
    var _acc_count_positive_words: Float64 = 0.0
    var _t0_count_positive_words = perf_counter_ns()
    for _ in range(N):
        _acc_count_positive_words += Float64(count_positive_words("test"))
    var _t1_count_positive_words = perf_counter_ns()
    var _ns_count_positive_words = Float64(_t1_count_positive_words - _t0_count_positive_words) / Float64(N)
    print("MOJO_TIMING sentiment::count_positive_words", _ns_count_positive_words, _acc_count_positive_words)
    var _acc_count_negative_words: Float64 = 0.0
    var _t0_count_negative_words = perf_counter_ns()
    for _ in range(N):
        _acc_count_negative_words += Float64(count_negative_words("test"))
    var _t1_count_negative_words = perf_counter_ns()
    var _ns_count_negative_words = Float64(_t1_count_negative_words - _t0_count_negative_words) / Float64(N)
    print("MOJO_TIMING sentiment::count_negative_words", _ns_count_negative_words, _acc_count_negative_words)
    var _acc_most_positive_word: Float64 = 0.0
    var _t0_most_positive_word = perf_counter_ns()
    for _ in range(N):
        _ = most_positive_word("test")
    var _t1_most_positive_word = perf_counter_ns()
    var _ns_most_positive_word = Float64(_t1_most_positive_word - _t0_most_positive_word) / Float64(N)
    print("MOJO_TIMING sentiment::most_positive_word", _ns_most_positive_word, _acc_most_positive_word)
    var _acc_most_negative_word: Float64 = 0.0
    var _t0_most_negative_word = perf_counter_ns()
    for _ in range(N):
        _ = most_negative_word("test")
    var _t1_most_negative_word = perf_counter_ns()
    var _ns_most_negative_word = Float64(_t1_most_negative_word - _t0_most_negative_word) / Float64(N)
    print("MOJO_TIMING sentiment::most_negative_word", _ns_most_negative_word, _acc_most_negative_word)
