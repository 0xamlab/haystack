"""bench_nlp.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from nlp import tokenize, ngrams, term_frequency, tf, cosine_similarity_vec, jaccard_similarity, word_count, char_count, unique_tokens
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_tokenize: Float64 = 0.0
    var _t0_tokenize = perf_counter_ns()
    for _ in range(N):
        var _r_tokenize = tokenize("test")
        _acc_tokenize += Float64(len(_r_tokenize))
    var _t1_tokenize = perf_counter_ns()
    var _ns_tokenize = Float64(_t1_tokenize - _t0_tokenize) / Float64(N)
    print("MOJO_TIMING nlp::tokenize", _ns_tokenize, _acc_tokenize)
    var _result_tokenize = tokenize("test")
    var _summary_tokenize = _summary_list_string(_result_tokenize)
    print("MOJO_RESULT nlp::tokenize", _summary_tokenize)
    var _acc_ngrams: Float64 = 0.0
    var _t0_ngrams = perf_counter_ns()
    for _ in range(N):
        var _r_ngrams = ngrams(["a","b","c","d","e"], 5)
        _acc_ngrams += Float64(len(_r_ngrams))
    var _t1_ngrams = perf_counter_ns()
    var _ns_ngrams = Float64(_t1_ngrams - _t0_ngrams) / Float64(N)
    print("MOJO_TIMING nlp::ngrams", _ns_ngrams, _acc_ngrams)
    var _result_ngrams = ngrams(["a","b","c","d","e"], 5)
    var _summary_ngrams = _summary_list_string(_result_ngrams)
    print("MOJO_RESULT nlp::ngrams", _summary_ngrams)
    var _acc_term_frequency: Float64 = 0.0
    var _t0_term_frequency = perf_counter_ns()
    for _ in range(N):
        var _r_term_frequency = term_frequency(["a","b","c","d","e"])
        _acc_term_frequency += Float64(len(_r_term_frequency))
    var _t1_term_frequency = perf_counter_ns()
    var _ns_term_frequency = Float64(_t1_term_frequency - _t0_term_frequency) / Float64(N)
    print("MOJO_TIMING nlp::term_frequency", _ns_term_frequency, _acc_term_frequency)
    var _result_term_frequency = term_frequency(["a","b","c","d","e"])
    var _summary_term_frequency = _summary_list_list_string(_result_term_frequency)
    print("MOJO_RESULT nlp::term_frequency", _summary_term_frequency)
    var _acc_tf: Float64 = 0.0
    var _t0_tf = perf_counter_ns()
    for _ in range(N):
        _acc_tf += tf("test", ["a","b","c","d","e"])
    var _t1_tf = perf_counter_ns()
    var _ns_tf = Float64(_t1_tf - _t0_tf) / Float64(N)
    print("MOJO_TIMING nlp::tf", _ns_tf, _acc_tf)
    var _result_tf = tf("test", ["a","b","c","d","e"])
    var _summary_tf = _summary_float64(_result_tf)
    print("MOJO_RESULT nlp::tf", _summary_tf)
    var _acc_cosine_similarity_vec: Float64 = 0.0
    var _t0_cosine_similarity_vec = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_similarity_vec += cosine_similarity_vec(_lf5, _lf5)
    var _t1_cosine_similarity_vec = perf_counter_ns()
    var _ns_cosine_similarity_vec = Float64(_t1_cosine_similarity_vec - _t0_cosine_similarity_vec) / Float64(N)
    print("MOJO_TIMING nlp::cosine_similarity_vec", _ns_cosine_similarity_vec, _acc_cosine_similarity_vec)
    var _result_cosine_similarity_vec = cosine_similarity_vec(_lf5, _lf5)
    var _summary_cosine_similarity_vec = _summary_float64(_result_cosine_similarity_vec)
    print("MOJO_RESULT nlp::cosine_similarity_vec", _summary_cosine_similarity_vec)
    var _acc_jaccard_similarity: Float64 = 0.0
    var _t0_jaccard_similarity = perf_counter_ns()
    for _ in range(N):
        _acc_jaccard_similarity += jaccard_similarity(["a","b","c","d","e"], ["a","b","c","d","e"])
    var _t1_jaccard_similarity = perf_counter_ns()
    var _ns_jaccard_similarity = Float64(_t1_jaccard_similarity - _t0_jaccard_similarity) / Float64(N)
    print("MOJO_TIMING nlp::jaccard_similarity", _ns_jaccard_similarity, _acc_jaccard_similarity)
    var _result_jaccard_similarity = jaccard_similarity(["a","b","c","d","e"], ["a","b","c","d","e"])
    var _summary_jaccard_similarity = _summary_float64(_result_jaccard_similarity)
    print("MOJO_RESULT nlp::jaccard_similarity", _summary_jaccard_similarity)
    var _acc_word_count: Float64 = 0.0
    var _t0_word_count = perf_counter_ns()
    for _ in range(N):
        _acc_word_count += Float64(word_count("test"))
    var _t1_word_count = perf_counter_ns()
    var _ns_word_count = Float64(_t1_word_count - _t0_word_count) / Float64(N)
    print("MOJO_TIMING nlp::word_count", _ns_word_count, _acc_word_count)
    var _result_word_count = word_count("test")
    var _summary_word_count = _summary_int(_result_word_count)
    print("MOJO_RESULT nlp::word_count", _summary_word_count)
    var _acc_char_count: Float64 = 0.0
    var _t0_char_count = perf_counter_ns()
    for _ in range(N):
        _acc_char_count += Float64(char_count("test"))
    var _t1_char_count = perf_counter_ns()
    var _ns_char_count = Float64(_t1_char_count - _t0_char_count) / Float64(N)
    print("MOJO_TIMING nlp::char_count", _ns_char_count, _acc_char_count)
    var _result_char_count = char_count("test")
    var _summary_char_count = _summary_int(_result_char_count)
    print("MOJO_RESULT nlp::char_count", _summary_char_count)
    var _acc_unique_tokens: Float64 = 0.0
    var _t0_unique_tokens = perf_counter_ns()
    for _ in range(N):
        var _r_unique_tokens = unique_tokens(["a","b","c","d","e"])
        _acc_unique_tokens += Float64(len(_r_unique_tokens))
    var _t1_unique_tokens = perf_counter_ns()
    var _ns_unique_tokens = Float64(_t1_unique_tokens - _t0_unique_tokens) / Float64(N)
    print("MOJO_TIMING nlp::unique_tokens", _ns_unique_tokens, _acc_unique_tokens)
    var _result_unique_tokens = unique_tokens(["a","b","c","d","e"])
    var _summary_unique_tokens = _summary_list_string(_result_unique_tokens)
    print("MOJO_RESULT nlp::unique_tokens", _summary_unique_tokens)
