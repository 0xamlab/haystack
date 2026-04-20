"""bench_bpe_tokenizer.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from bpe_tokenizer import bpe_merge_score, bpe_pair_frequency, subword_log_probability, sentencepiece_vocab_size_est, byte_fallback_encode, tokenization_compression_ratio, vocab_fertility, oov_rate, bpe_merge_rank_score, streaming_token_boundary
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

    var _acc_bpe_merge_score: Float64 = 0.0
    var _t0_bpe_merge_score = perf_counter_ns()
    for _ in range(N):
        _acc_bpe_merge_score += bpe_merge_score(0.5, 0.5, 0.5)
    var _t1_bpe_merge_score = perf_counter_ns()
    var _ns_bpe_merge_score = Float64(_t1_bpe_merge_score - _t0_bpe_merge_score) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::bpe_merge_score", _ns_bpe_merge_score, _acc_bpe_merge_score)
    var _acc_bpe_pair_frequency: Float64 = 0.0
    var _t0_bpe_pair_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_bpe_pair_frequency += bpe_pair_frequency(0.5, 0.5)
    var _t1_bpe_pair_frequency = perf_counter_ns()
    var _ns_bpe_pair_frequency = Float64(_t1_bpe_pair_frequency - _t0_bpe_pair_frequency) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::bpe_pair_frequency", _ns_bpe_pair_frequency, _acc_bpe_pair_frequency)
    var _acc_subword_log_probability: Float64 = 0.0
    var _t0_subword_log_probability = perf_counter_ns()
    for _ in range(N):
        _acc_subword_log_probability += subword_log_probability(0.5, 0.5)
    var _t1_subword_log_probability = perf_counter_ns()
    var _ns_subword_log_probability = Float64(_t1_subword_log_probability - _t0_subword_log_probability) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::subword_log_probability", _ns_subword_log_probability, _acc_subword_log_probability)
    var _acc_sentencepiece_vocab_size_est: Float64 = 0.0
    var _t0_sentencepiece_vocab_size_est = perf_counter_ns()
    for _ in range(N):
        _acc_sentencepiece_vocab_size_est += sentencepiece_vocab_size_est(0.5, 0.5, 0.5)
    var _t1_sentencepiece_vocab_size_est = perf_counter_ns()
    var _ns_sentencepiece_vocab_size_est = Float64(_t1_sentencepiece_vocab_size_est - _t0_sentencepiece_vocab_size_est) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::sentencepiece_vocab_size_est", _ns_sentencepiece_vocab_size_est, _acc_sentencepiece_vocab_size_est)
    var _acc_byte_fallback_encode: Float64 = 0.0
    var _t0_byte_fallback_encode = perf_counter_ns()
    for _ in range(N):
        _acc_byte_fallback_encode += byte_fallback_encode(0.5)
    var _t1_byte_fallback_encode = perf_counter_ns()
    var _ns_byte_fallback_encode = Float64(_t1_byte_fallback_encode - _t0_byte_fallback_encode) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::byte_fallback_encode", _ns_byte_fallback_encode, _acc_byte_fallback_encode)
    var _acc_tokenization_compression_ratio: Float64 = 0.0
    var _t0_tokenization_compression_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_tokenization_compression_ratio += tokenization_compression_ratio(0.5, 0.5)
    var _t1_tokenization_compression_ratio = perf_counter_ns()
    var _ns_tokenization_compression_ratio = Float64(_t1_tokenization_compression_ratio - _t0_tokenization_compression_ratio) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::tokenization_compression_ratio", _ns_tokenization_compression_ratio, _acc_tokenization_compression_ratio)
    var _acc_vocab_fertility: Float64 = 0.0
    var _t0_vocab_fertility = perf_counter_ns()
    for _ in range(N):
        _acc_vocab_fertility += vocab_fertility(0.5, 0.5)
    var _t1_vocab_fertility = perf_counter_ns()
    var _ns_vocab_fertility = Float64(_t1_vocab_fertility - _t0_vocab_fertility) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::vocab_fertility", _ns_vocab_fertility, _acc_vocab_fertility)
    var _acc_oov_rate: Float64 = 0.0
    var _t0_oov_rate = perf_counter_ns()
    for _ in range(N):
        _acc_oov_rate += oov_rate(0.5, 0.5)
    var _t1_oov_rate = perf_counter_ns()
    var _ns_oov_rate = Float64(_t1_oov_rate - _t0_oov_rate) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::oov_rate", _ns_oov_rate, _acc_oov_rate)
    var _acc_bpe_merge_rank_score: Float64 = 0.0
    var _t0_bpe_merge_rank_score = perf_counter_ns()
    for _ in range(N):
        _acc_bpe_merge_rank_score += bpe_merge_rank_score(0.5, 0.5)
    var _t1_bpe_merge_rank_score = perf_counter_ns()
    var _ns_bpe_merge_rank_score = Float64(_t1_bpe_merge_rank_score - _t0_bpe_merge_rank_score) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::bpe_merge_rank_score", _ns_bpe_merge_rank_score, _acc_bpe_merge_rank_score)
    var _acc_streaming_token_boundary: Float64 = 0.0
    var _t0_streaming_token_boundary = perf_counter_ns()
    for _ in range(N):
        _acc_streaming_token_boundary += streaming_token_boundary(0.5, 0.5)
    var _t1_streaming_token_boundary = perf_counter_ns()
    var _ns_streaming_token_boundary = Float64(_t1_streaming_token_boundary - _t0_streaming_token_boundary) / Float64(N)
    print("MOJO_TIMING bpe_tokenizer::streaming_token_boundary", _ns_streaming_token_boundary, _acc_streaming_token_boundary)
