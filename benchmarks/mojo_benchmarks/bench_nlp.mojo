"""bench_nlp.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from nlp import tokenize, ngrams, term_frequency, tf, cosine_similarity_vec, jaccard_similarity, word_count, char_count, unique_tokens
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

    var _acc_tokenize: Float64 = 0.0
    var _t0_tokenize = perf_counter_ns()
    for _ in range(N):
        var _r_tokenize = tokenize("test")
        _acc_tokenize += Float64(len(_r_tokenize))
    var _t1_tokenize = perf_counter_ns()
    var _ns_tokenize = Float64(_t1_tokenize - _t0_tokenize) / Float64(N)
    print("MOJO_TIMING nlp::tokenize", _ns_tokenize, _acc_tokenize)
    var _acc_ngrams: Float64 = 0.0
    var _t0_ngrams = perf_counter_ns()
    for _ in range(N):
        var _r_ngrams = ngrams(["a","b","c","d","e"], 5)
        _acc_ngrams += Float64(len(_r_ngrams))
    var _t1_ngrams = perf_counter_ns()
    var _ns_ngrams = Float64(_t1_ngrams - _t0_ngrams) / Float64(N)
    print("MOJO_TIMING nlp::ngrams", _ns_ngrams, _acc_ngrams)
    var _acc_term_frequency: Float64 = 0.0
    var _t0_term_frequency = perf_counter_ns()
    for _ in range(N):
        var _r_term_frequency = term_frequency(["a","b","c","d","e"])
        _acc_term_frequency += Float64(len(_r_term_frequency))
    var _t1_term_frequency = perf_counter_ns()
    var _ns_term_frequency = Float64(_t1_term_frequency - _t0_term_frequency) / Float64(N)
    print("MOJO_TIMING nlp::term_frequency", _ns_term_frequency, _acc_term_frequency)
    var _acc_tf: Float64 = 0.0
    var _t0_tf = perf_counter_ns()
    for _ in range(N):
        _acc_tf += tf("test", ["a","b","c","d","e"])
    var _t1_tf = perf_counter_ns()
    var _ns_tf = Float64(_t1_tf - _t0_tf) / Float64(N)
    print("MOJO_TIMING nlp::tf", _ns_tf, _acc_tf)
    var _acc_cosine_similarity_vec: Float64 = 0.0
    var _t0_cosine_similarity_vec = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_similarity_vec += cosine_similarity_vec(_lf5, _lf5)
    var _t1_cosine_similarity_vec = perf_counter_ns()
    var _ns_cosine_similarity_vec = Float64(_t1_cosine_similarity_vec - _t0_cosine_similarity_vec) / Float64(N)
    print("MOJO_TIMING nlp::cosine_similarity_vec", _ns_cosine_similarity_vec, _acc_cosine_similarity_vec)
    var _acc_jaccard_similarity: Float64 = 0.0
    var _t0_jaccard_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_jaccard_similarity += jaccard_similarity(["a","b","c","d","e"], ["a","b","c","d","e"])
    var _t1_jaccard_similarity = perf_counter_ns()
    var _ns_jaccard_similarity = Float64(_t1_jaccard_similarity - _t0_jaccard_similarity) / Float64(N)
    print("MOJO_TIMING nlp::jaccard_similarity", _ns_jaccard_similarity, _acc_jaccard_similarity)
    var _acc_word_count: Float64 = 0.0
    var _t0_word_count = perf_counter_ns()
    for _ in range(N):
        _acc_word_count += Float64(word_count("test"))
    var _t1_word_count = perf_counter_ns()
    var _ns_word_count = Float64(_t1_word_count - _t0_word_count) / Float64(N)
    print("MOJO_TIMING nlp::word_count", _ns_word_count, _acc_word_count)
    var _acc_char_count: Float64 = 0.0
    var _t0_char_count = perf_counter_ns()
    for _ in range(N):
        _acc_char_count += Float64(char_count("test"))
    var _t1_char_count = perf_counter_ns()
    var _ns_char_count = Float64(_t1_char_count - _t0_char_count) / Float64(N)
    print("MOJO_TIMING nlp::char_count", _ns_char_count, _acc_char_count)
    var _acc_unique_tokens: Float64 = 0.0
    var _t0_unique_tokens = perf_counter_ns()
    for _ in range(N):
        var _r_unique_tokens = unique_tokens(["a","b","c","d","e"])
        _acc_unique_tokens += Float64(len(_r_unique_tokens))
    var _t1_unique_tokens = perf_counter_ns()
    var _ns_unique_tokens = Float64(_t1_unique_tokens - _t0_unique_tokens) / Float64(N)
    print("MOJO_TIMING nlp::unique_tokens", _ns_unique_tokens, _acc_unique_tokens)
