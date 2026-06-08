"""bench_bpe_tokenizer.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from bpe_tokenizer import bpe_merge_score, bpe_pair_frequency, subword_log_probability, sentencepiece_vocab_size_est, byte_fallback_encode, tokenization_compression_ratio, vocab_fertility, oov_rate, bpe_merge_rank_score, streaming_token_boundary
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

    var _acc_bpe_merge_score: Float64 = 0.0
    var _t0_bpe_merge_score = perf_counter_ns()
    for _ in range(N):
        _acc_bpe_merge_score += bpe_merge_score(0.5, 0.5, 0.5)
    var _t1_bpe_merge_score = perf_counter_ns()
    var _ns_bpe_merge_score = Float64(_t1_bpe_merge_score - _t0_bpe_merge_score) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::bpe_merge_score", _ns_bpe_merge_score, _acc_bpe_merge_score)
    var _result_bpe_merge_score = bpe_merge_score(0.5, 0.5, 0.5)
    var _summary_bpe_merge_score = _summary_float64(_result_bpe_merge_score)
    print("MOJO_RESULT bpe_tokenizer::bpe_merge_score", _summary_bpe_merge_score)
    var _acc_bpe_pair_frequency: Float64 = 0.0
    var _t0_bpe_pair_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_bpe_pair_frequency += bpe_pair_frequency(0.5, 0.5)
    var _t1_bpe_pair_frequency = perf_counter_ns()
    var _ns_bpe_pair_frequency = Float64(_t1_bpe_pair_frequency - _t0_bpe_pair_frequency) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::bpe_pair_frequency", _ns_bpe_pair_frequency, _acc_bpe_pair_frequency)
    var _result_bpe_pair_frequency = bpe_pair_frequency(0.5, 0.5)
    var _summary_bpe_pair_frequency = _summary_float64(_result_bpe_pair_frequency)
    print("MOJO_RESULT bpe_tokenizer::bpe_pair_frequency", _summary_bpe_pair_frequency)
    var _acc_subword_log_probability: Float64 = 0.0
    var _t0_subword_log_probability = perf_counter_ns()
    for _ in range(N):
        _acc_subword_log_probability += subword_log_probability(0.5, 0.5)
    var _t1_subword_log_probability = perf_counter_ns()
    var _ns_subword_log_probability = Float64(_t1_subword_log_probability - _t0_subword_log_probability) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::subword_log_probability", _ns_subword_log_probability, _acc_subword_log_probability)
    var _result_subword_log_probability = subword_log_probability(0.5, 0.5)
    var _summary_subword_log_probability = _summary_float64(_result_subword_log_probability)
    print("MOJO_RESULT bpe_tokenizer::subword_log_probability", _summary_subword_log_probability)
    var _acc_sentencepiece_vocab_size_est: Float64 = 0.0
    var _t0_sentencepiece_vocab_size_est = perf_counter_ns()
    for _ in range(N):
        _acc_sentencepiece_vocab_size_est += sentencepiece_vocab_size_est(0.5, 0.5, 0.5)
    var _t1_sentencepiece_vocab_size_est = perf_counter_ns()
    var _ns_sentencepiece_vocab_size_est = Float64(_t1_sentencepiece_vocab_size_est - _t0_sentencepiece_vocab_size_est) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::sentencepiece_vocab_size_est", _ns_sentencepiece_vocab_size_est, _acc_sentencepiece_vocab_size_est)
    var _result_sentencepiece_vocab_size_est = sentencepiece_vocab_size_est(0.5, 0.5, 0.5)
    var _summary_sentencepiece_vocab_size_est = _summary_float64(_result_sentencepiece_vocab_size_est)
    print("MOJO_RESULT bpe_tokenizer::sentencepiece_vocab_size_est", _summary_sentencepiece_vocab_size_est)
    var _acc_byte_fallback_encode: Float64 = 0.0
    var _t0_byte_fallback_encode = perf_counter_ns()
    for _ in range(N):
        _acc_byte_fallback_encode += byte_fallback_encode(0.5)
    var _t1_byte_fallback_encode = perf_counter_ns()
    var _ns_byte_fallback_encode = Float64(_t1_byte_fallback_encode - _t0_byte_fallback_encode) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::byte_fallback_encode", _ns_byte_fallback_encode, _acc_byte_fallback_encode)
    var _result_byte_fallback_encode = byte_fallback_encode(0.5)
    var _summary_byte_fallback_encode = _summary_float64(_result_byte_fallback_encode)
    print("MOJO_RESULT bpe_tokenizer::byte_fallback_encode", _summary_byte_fallback_encode)
    var _acc_tokenization_compression_ratio: Float64 = 0.0
    var _t0_tokenization_compression_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_tokenization_compression_ratio += tokenization_compression_ratio(0.5, 0.5)
    var _t1_tokenization_compression_ratio = perf_counter_ns()
    var _ns_tokenization_compression_ratio = Float64(_t1_tokenization_compression_ratio - _t0_tokenization_compression_ratio) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::tokenization_compression_ratio", _ns_tokenization_compression_ratio, _acc_tokenization_compression_ratio)
    var _result_tokenization_compression_ratio = tokenization_compression_ratio(0.5, 0.5)
    var _summary_tokenization_compression_ratio = _summary_float64(_result_tokenization_compression_ratio)
    print("MOJO_RESULT bpe_tokenizer::tokenization_compression_ratio", _summary_tokenization_compression_ratio)
    var _acc_vocab_fertility: Float64 = 0.0
    var _t0_vocab_fertility = perf_counter_ns()
    for _ in range(N):
        _acc_vocab_fertility += vocab_fertility(0.5, 0.5)
    var _t1_vocab_fertility = perf_counter_ns()
    var _ns_vocab_fertility = Float64(_t1_vocab_fertility - _t0_vocab_fertility) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::vocab_fertility", _ns_vocab_fertility, _acc_vocab_fertility)
    var _result_vocab_fertility = vocab_fertility(0.5, 0.5)
    var _summary_vocab_fertility = _summary_float64(_result_vocab_fertility)
    print("MOJO_RESULT bpe_tokenizer::vocab_fertility", _summary_vocab_fertility)
    var _acc_oov_rate: Float64 = 0.0
    var _t0_oov_rate = perf_counter_ns()
    for _ in range(N):
        _acc_oov_rate += oov_rate(0.5, 0.5)
    var _t1_oov_rate = perf_counter_ns()
    var _ns_oov_rate = Float64(_t1_oov_rate - _t0_oov_rate) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::oov_rate", _ns_oov_rate, _acc_oov_rate)
    var _result_oov_rate = oov_rate(0.5, 0.5)
    var _summary_oov_rate = _summary_float64(_result_oov_rate)
    print("MOJO_RESULT bpe_tokenizer::oov_rate", _summary_oov_rate)
    var _acc_bpe_merge_rank_score: Float64 = 0.0
    var _t0_bpe_merge_rank_score = perf_counter_ns()
    for _ in range(N):
        _acc_bpe_merge_rank_score += bpe_merge_rank_score(0.5, 0.5)
    var _t1_bpe_merge_rank_score = perf_counter_ns()
    var _ns_bpe_merge_rank_score = Float64(_t1_bpe_merge_rank_score - _t0_bpe_merge_rank_score) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::bpe_merge_rank_score", _ns_bpe_merge_rank_score, _acc_bpe_merge_rank_score)
    var _result_bpe_merge_rank_score = bpe_merge_rank_score(0.5, 0.5)
    var _summary_bpe_merge_rank_score = _summary_float64(_result_bpe_merge_rank_score)
    print("MOJO_RESULT bpe_tokenizer::bpe_merge_rank_score", _summary_bpe_merge_rank_score)
    var _acc_streaming_token_boundary: Float64 = 0.0
    var _t0_streaming_token_boundary = perf_counter_ns()
    for _ in range(N):
        _acc_streaming_token_boundary += streaming_token_boundary(0.5, 0.5)
    var _t1_streaming_token_boundary = perf_counter_ns()
    var _ns_streaming_token_boundary = Float64(_t1_streaming_token_boundary - _t0_streaming_token_boundary) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::streaming_token_boundary", _ns_streaming_token_boundary, _acc_streaming_token_boundary)
    var _result_streaming_token_boundary = streaming_token_boundary(0.5, 0.5)
    var _summary_streaming_token_boundary = _summary_float64(_result_streaming_token_boundary)
    print("MOJO_RESULT bpe_tokenizer::streaming_token_boundary", _summary_streaming_token_boundary)
