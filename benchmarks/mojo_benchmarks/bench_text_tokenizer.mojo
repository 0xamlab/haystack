"""bench_text_tokenizer.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from text.tokenizer import is_stopword, word_tokenize, sentence_tokenize, char_ngrams, word_ngrams, remove_stopwords, stem_simple, vocabulary_size, token_frequency, pad_sequence
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

    var _acc_is_stopword: Float64 = 0.0
    var _t0_is_stopword = perf_counter_ns()
    for _ in range(N):
        _acc_is_stopword += Float64(is_stopword("test"))
    var _t1_is_stopword = perf_counter_ns()
    var _ns_is_stopword = Float64(_t1_is_stopword - _t0_is_stopword) / Float64(N)
    print("MOJO_TIMING text_tokenizer::is_stopword", _ns_is_stopword, _acc_is_stopword)
    var _acc_word_tokenize: Float64 = 0.0
    var _t0_word_tokenize = perf_counter_ns()
    for _ in range(N):
        var _r_word_tokenize = word_tokenize("test")
        _acc_word_tokenize += Float64(len(_r_word_tokenize))
    var _t1_word_tokenize = perf_counter_ns()
    var _ns_word_tokenize = Float64(_t1_word_tokenize - _t0_word_tokenize) / Float64(N)
    print("MOJO_TIMING text_tokenizer::word_tokenize", _ns_word_tokenize, _acc_word_tokenize)
    var _acc_sentence_tokenize: Float64 = 0.0
    var _t0_sentence_tokenize = perf_counter_ns()
    for _ in range(N):
        var _r_sentence_tokenize = sentence_tokenize("test")
        _acc_sentence_tokenize += Float64(len(_r_sentence_tokenize))
    var _t1_sentence_tokenize = perf_counter_ns()
    var _ns_sentence_tokenize = Float64(_t1_sentence_tokenize - _t0_sentence_tokenize) / Float64(N)
    print("MOJO_TIMING text_tokenizer::sentence_tokenize", _ns_sentence_tokenize, _acc_sentence_tokenize)
    var _acc_char_ngrams: Float64 = 0.0
    var _t0_char_ngrams = perf_counter_ns()
    for _ in range(N):
        var _r_char_ngrams = char_ngrams("test", 5)
        _acc_char_ngrams += Float64(len(_r_char_ngrams))
    var _t1_char_ngrams = perf_counter_ns()
    var _ns_char_ngrams = Float64(_t1_char_ngrams - _t0_char_ngrams) / Float64(N)
    print("MOJO_TIMING text_tokenizer::char_ngrams", _ns_char_ngrams, _acc_char_ngrams)
    var _acc_word_ngrams: Float64 = 0.0
    var _t0_word_ngrams = perf_counter_ns()
    for _ in range(N):
        var _r_word_ngrams = word_ngrams(["a","b","c","d","e"], 5)
        _acc_word_ngrams += Float64(len(_r_word_ngrams))
    var _t1_word_ngrams = perf_counter_ns()
    var _ns_word_ngrams = Float64(_t1_word_ngrams - _t0_word_ngrams) / Float64(N)
    print("MOJO_TIMING text_tokenizer::word_ngrams", _ns_word_ngrams, _acc_word_ngrams)
    var _acc_remove_stopwords: Float64 = 0.0
    var _t0_remove_stopwords = perf_counter_ns()
    for _ in range(N):
        var _r_remove_stopwords = remove_stopwords(["a","b","c","d","e"])
        _acc_remove_stopwords += Float64(len(_r_remove_stopwords))
    var _t1_remove_stopwords = perf_counter_ns()
    var _ns_remove_stopwords = Float64(_t1_remove_stopwords - _t0_remove_stopwords) / Float64(N)
    print("MOJO_TIMING text_tokenizer::remove_stopwords", _ns_remove_stopwords, _acc_remove_stopwords)
    var _acc_stem_simple: Float64 = 0.0
    var _t0_stem_simple = perf_counter_ns()
    for _ in range(N):
        _ = stem_simple("test")
    var _t1_stem_simple = perf_counter_ns()
    var _ns_stem_simple = Float64(_t1_stem_simple - _t0_stem_simple) / Float64(N)
    print("MOJO_TIMING text_tokenizer::stem_simple", _ns_stem_simple, _acc_stem_simple)
    var _acc_vocabulary_size: Float64 = 0.0
    var _t0_vocabulary_size = perf_counter_ns()
    for _ in range(N):
        _acc_vocabulary_size += Float64(vocabulary_size(["a","b","c","d","e"]))
    var _t1_vocabulary_size = perf_counter_ns()
    var _ns_vocabulary_size = Float64(_t1_vocabulary_size - _t0_vocabulary_size) / Float64(N)
    print("MOJO_TIMING text_tokenizer::vocabulary_size", _ns_vocabulary_size, _acc_vocabulary_size)
    var _acc_token_frequency: Float64 = 0.0
    var _t0_token_frequency = perf_counter_ns()
    for _ in range(N):
        var _r_token_frequency = token_frequency(["a","b","c","d","e"])
        _acc_token_frequency += Float64(len(_r_token_frequency))
    var _t1_token_frequency = perf_counter_ns()
    var _ns_token_frequency = Float64(_t1_token_frequency - _t0_token_frequency) / Float64(N)
    print("MOJO_TIMING text_tokenizer::token_frequency", _ns_token_frequency, _acc_token_frequency)
    var _acc_pad_sequence: Float64 = 0.0
    var _t0_pad_sequence = perf_counter_ns()
    for _ in range(N):
        var _r_pad_sequence = pad_sequence(["a","b","c","d","e"], 5, "test")
        _acc_pad_sequence += Float64(len(_r_pad_sequence))
    var _t1_pad_sequence = perf_counter_ns()
    var _ns_pad_sequence = Float64(_t1_pad_sequence - _t0_pad_sequence) / Float64(N)
    print("MOJO_TIMING text_tokenizer::pad_sequence", _ns_pad_sequence, _acc_pad_sequence)
