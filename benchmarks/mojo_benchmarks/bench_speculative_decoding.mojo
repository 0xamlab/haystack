"""bench_speculative_decoding.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from speculative_decoding import speculative_accept_prob, speculative_expected_tokens, draft_model_speedup, json_grammar_logit_mask, structured_repair_score, constrained_beam_score, token_healing_overlap, watermark_green_list_bias, contrastive_decode_score, medusa_head_acceptance
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

    var _acc_speculative_accept_prob: Float64 = 0.0
    var _t0_speculative_accept_prob = perf_counter_ns()
    for _ in range(N):
        _acc_speculative_accept_prob += speculative_accept_prob(0.5, 0.5)
    var _t1_speculative_accept_prob = perf_counter_ns()
    var _ns_speculative_accept_prob = Float64(_t1_speculative_accept_prob - _t0_speculative_accept_prob) / Float64(N)
    print("MOJO_TIMING speculative_decoding::speculative_accept_prob", _ns_speculative_accept_prob, _acc_speculative_accept_prob)
    var _acc_speculative_expected_tokens: Float64 = 0.0
    var _t0_speculative_expected_tokens = perf_counter_ns()
    for _ in range(N):
        _acc_speculative_expected_tokens += speculative_expected_tokens(0.5, 0.5)
    var _t1_speculative_expected_tokens = perf_counter_ns()
    var _ns_speculative_expected_tokens = Float64(_t1_speculative_expected_tokens - _t0_speculative_expected_tokens) / Float64(N)
    print("MOJO_TIMING speculative_decoding::speculative_expected_tokens", _ns_speculative_expected_tokens, _acc_speculative_expected_tokens)
    var _acc_draft_model_speedup: Float64 = 0.0
    var _t0_draft_model_speedup = perf_counter_ns()
    for _ in range(N):
        _acc_draft_model_speedup += draft_model_speedup(0.5, 0.5, 0.5, 0.5)
    var _t1_draft_model_speedup = perf_counter_ns()
    var _ns_draft_model_speedup = Float64(_t1_draft_model_speedup - _t0_draft_model_speedup) / Float64(N)
    print("MOJO_TIMING speculative_decoding::draft_model_speedup", _ns_draft_model_speedup, _acc_draft_model_speedup)
    var _acc_json_grammar_logit_mask: Float64 = 0.0
    var _t0_json_grammar_logit_mask = perf_counter_ns()
    for _ in range(N):
        _acc_json_grammar_logit_mask += json_grammar_logit_mask(0.5, 0.5)
    var _t1_json_grammar_logit_mask = perf_counter_ns()
    var _ns_json_grammar_logit_mask = Float64(_t1_json_grammar_logit_mask - _t0_json_grammar_logit_mask) / Float64(N)
    print("MOJO_TIMING speculative_decoding::json_grammar_logit_mask", _ns_json_grammar_logit_mask, _acc_json_grammar_logit_mask)
    var _acc_structured_repair_score: Float64 = 0.0
    var _t0_structured_repair_score = perf_counter_ns()
    for _ in range(N):
        _acc_structured_repair_score += structured_repair_score(0.5, 0.5, 0.5)
    var _t1_structured_repair_score = perf_counter_ns()
    var _ns_structured_repair_score = Float64(_t1_structured_repair_score - _t0_structured_repair_score) / Float64(N)
    print("MOJO_TIMING speculative_decoding::structured_repair_score", _ns_structured_repair_score, _acc_structured_repair_score)
    var _acc_constrained_beam_score: Float64 = 0.0
    var _t0_constrained_beam_score = perf_counter_ns()
    for _ in range(N):
        _acc_constrained_beam_score += constrained_beam_score(0.5, 0.5, 0.5, 0.5)
    var _t1_constrained_beam_score = perf_counter_ns()
    var _ns_constrained_beam_score = Float64(_t1_constrained_beam_score - _t0_constrained_beam_score) / Float64(N)
    print("MOJO_TIMING speculative_decoding::constrained_beam_score", _ns_constrained_beam_score, _acc_constrained_beam_score)
    var _acc_token_healing_overlap: Float64 = 0.0
    var _t0_token_healing_overlap = perf_counter_ns()
    for _ in range(N):
        _acc_token_healing_overlap += token_healing_overlap(0.5, 0.5, 0.5)
    var _t1_token_healing_overlap = perf_counter_ns()
    var _ns_token_healing_overlap = Float64(_t1_token_healing_overlap - _t0_token_healing_overlap) / Float64(N)
    print("MOJO_TIMING speculative_decoding::token_healing_overlap", _ns_token_healing_overlap, _acc_token_healing_overlap)
    var _acc_watermark_green_list_bias: Float64 = 0.0
    var _t0_watermark_green_list_bias = perf_counter_ns()
    for _ in range(N):
        _acc_watermark_green_list_bias += watermark_green_list_bias(0.5, 0.5, 0.5)
    var _t1_watermark_green_list_bias = perf_counter_ns()
    var _ns_watermark_green_list_bias = Float64(_t1_watermark_green_list_bias - _t0_watermark_green_list_bias) / Float64(N)
    print("MOJO_TIMING speculative_decoding::watermark_green_list_bias", _ns_watermark_green_list_bias, _acc_watermark_green_list_bias)
    var _acc_contrastive_decode_score: Float64 = 0.0
    var _t0_contrastive_decode_score = perf_counter_ns()
    for _ in range(N):
        _acc_contrastive_decode_score += contrastive_decode_score(0.5, 0.5, 0.5)
    var _t1_contrastive_decode_score = perf_counter_ns()
    var _ns_contrastive_decode_score = Float64(_t1_contrastive_decode_score - _t0_contrastive_decode_score) / Float64(N)
    print("MOJO_TIMING speculative_decoding::contrastive_decode_score", _ns_contrastive_decode_score, _acc_contrastive_decode_score)
    var _acc_medusa_head_acceptance: Float64 = 0.0
    var _t0_medusa_head_acceptance = perf_counter_ns()
    for _ in range(N):
        _acc_medusa_head_acceptance += medusa_head_acceptance(0.5, 0.5, 0.5)
    var _t1_medusa_head_acceptance = perf_counter_ns()
    var _ns_medusa_head_acceptance = Float64(_t1_medusa_head_acceptance - _t0_medusa_head_acceptance) / Float64(N)
    print("MOJO_TIMING speculative_decoding::medusa_head_acceptance", _ns_medusa_head_acceptance, _acc_medusa_head_acceptance)
