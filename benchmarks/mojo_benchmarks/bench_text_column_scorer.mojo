"""bench_text_column_scorer.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from text.column_scorer import score_token_overlap, score_ngram_overlap, score_prefix_match, score_column_hint
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

    var _acc_score_token_overlap: Float64 = 0.0
    var _t0_score_token_overlap = perf_counter_ns()
    for _ in range(N):
        _acc_score_token_overlap += score_token_overlap("test", "test")
    var _t1_score_token_overlap = perf_counter_ns()
    var _ns_score_token_overlap = Float64(_t1_score_token_overlap - _t0_score_token_overlap) / Float64(N)
    print("MOJO_TIMING text_column_scorer::score_token_overlap", _ns_score_token_overlap, _acc_score_token_overlap)
    var _acc_score_ngram_overlap: Float64 = 0.0
    var _t0_score_ngram_overlap = perf_counter_ns()
    for _ in range(N):
        _acc_score_ngram_overlap += score_ngram_overlap("test", "test", 5)
    var _t1_score_ngram_overlap = perf_counter_ns()
    var _ns_score_ngram_overlap = Float64(_t1_score_ngram_overlap - _t0_score_ngram_overlap) / Float64(N)
    print("MOJO_TIMING text_column_scorer::score_ngram_overlap", _ns_score_ngram_overlap, _acc_score_ngram_overlap)
    var _acc_score_prefix_match: Float64 = 0.0
    var _t0_score_prefix_match = perf_counter_ns()
    for _ in range(N):
        _acc_score_prefix_match += score_prefix_match("test", "test")
    var _t1_score_prefix_match = perf_counter_ns()
    var _ns_score_prefix_match = Float64(_t1_score_prefix_match - _t0_score_prefix_match) / Float64(N)
    print("MOJO_TIMING text_column_scorer::score_prefix_match", _ns_score_prefix_match, _acc_score_prefix_match)
    var _acc_score_column_hint: Float64 = 0.0
    var _t0_score_column_hint = perf_counter_ns()
    for _ in range(N):
        _acc_score_column_hint += score_column_hint("test", "test", 0.5, 0.5, 0.5)
    var _t1_score_column_hint = perf_counter_ns()
    var _ns_score_column_hint = Float64(_t1_score_column_hint - _t0_score_column_hint) / Float64(N)
    print("MOJO_TIMING text_column_scorer::score_column_hint", _ns_score_column_hint, _acc_score_column_hint)
