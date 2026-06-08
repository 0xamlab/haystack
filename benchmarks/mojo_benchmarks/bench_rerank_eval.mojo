"""bench_rerank_eval.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from rerank_eval import precision_at_k, recall_at_k, hit_rate_at_k, mrr_at_k, map_at_k, ndcg_at_k, pairwise_margin_accuracy, score_separation, latency_weighted_quality
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

    var _acc_precision_at_k: Float64 = 0.0
    var _t0_precision_at_k = perf_counter_ns()
    for _ in range(N):
        _acc_precision_at_k += precision_at_k(_li5, 5)
    var _t1_precision_at_k = perf_counter_ns()
    var _ns_precision_at_k = Float64(_t1_precision_at_k - _t0_precision_at_k) / Float64(N)
    print("MOJO_TIMING rerank_eval::precision_at_k", _ns_precision_at_k, _acc_precision_at_k)
    var _result_precision_at_k = precision_at_k(_li5, 5)
    var _summary_precision_at_k = _summary_float64(_result_precision_at_k)
    print("MOJO_RESULT rerank_eval::precision_at_k", _summary_precision_at_k)
    var _acc_recall_at_k: Float64 = 0.0
    var _t0_recall_at_k = perf_counter_ns()
    for _ in range(N):
        _acc_recall_at_k += recall_at_k(_li5, 5, 5)
    var _t1_recall_at_k = perf_counter_ns()
    var _ns_recall_at_k = Float64(_t1_recall_at_k - _t0_recall_at_k) / Float64(N)
    print("MOJO_TIMING rerank_eval::recall_at_k", _ns_recall_at_k, _acc_recall_at_k)
    var _result_recall_at_k = recall_at_k(_li5, 5, 5)
    var _summary_recall_at_k = _summary_float64(_result_recall_at_k)
    print("MOJO_RESULT rerank_eval::recall_at_k", _summary_recall_at_k)
    var _acc_hit_rate_at_k: Float64 = 0.0
    var _t0_hit_rate_at_k = perf_counter_ns()
    for _ in range(N):
        _acc_hit_rate_at_k += hit_rate_at_k(_li5, 5)
    var _t1_hit_rate_at_k = perf_counter_ns()
    var _ns_hit_rate_at_k = Float64(_t1_hit_rate_at_k - _t0_hit_rate_at_k) / Float64(N)
    print("MOJO_TIMING rerank_eval::hit_rate_at_k", _ns_hit_rate_at_k, _acc_hit_rate_at_k)
    var _result_hit_rate_at_k = hit_rate_at_k(_li5, 5)
    var _summary_hit_rate_at_k = _summary_float64(_result_hit_rate_at_k)
    print("MOJO_RESULT rerank_eval::hit_rate_at_k", _summary_hit_rate_at_k)
    var _acc_mrr_at_k: Float64 = 0.0
    var _t0_mrr_at_k = perf_counter_ns()
    for _ in range(N):
        _acc_mrr_at_k += mrr_at_k(_li5, 5)
    var _t1_mrr_at_k = perf_counter_ns()
    var _ns_mrr_at_k = Float64(_t1_mrr_at_k - _t0_mrr_at_k) / Float64(N)
    print("MOJO_TIMING rerank_eval::mrr_at_k", _ns_mrr_at_k, _acc_mrr_at_k)
    var _result_mrr_at_k = mrr_at_k(_li5, 5)
    var _summary_mrr_at_k = _summary_float64(_result_mrr_at_k)
    print("MOJO_RESULT rerank_eval::mrr_at_k", _summary_mrr_at_k)
    var _acc_map_at_k: Float64 = 0.0
    var _t0_map_at_k = perf_counter_ns()
    for _ in range(N):
        _acc_map_at_k += map_at_k(_li5, 5)
    var _t1_map_at_k = perf_counter_ns()
    var _ns_map_at_k = Float64(_t1_map_at_k - _t0_map_at_k) / Float64(N)
    print("MOJO_TIMING rerank_eval::map_at_k", _ns_map_at_k, _acc_map_at_k)
    var _result_map_at_k = map_at_k(_li5, 5)
    var _summary_map_at_k = _summary_float64(_result_map_at_k)
    print("MOJO_RESULT rerank_eval::map_at_k", _summary_map_at_k)
    var _acc_ndcg_at_k: Float64 = 0.0
    var _t0_ndcg_at_k = perf_counter_ns()
    for _ in range(N):
        _acc_ndcg_at_k += ndcg_at_k(_lf5, _lf5, 5)
    var _t1_ndcg_at_k = perf_counter_ns()
    var _ns_ndcg_at_k = Float64(_t1_ndcg_at_k - _t0_ndcg_at_k) / Float64(N)
    print("MOJO_TIMING rerank_eval::ndcg_at_k", _ns_ndcg_at_k, _acc_ndcg_at_k)
    var _result_ndcg_at_k = ndcg_at_k(_lf5, _lf5, 5)
    var _summary_ndcg_at_k = _summary_float64(_result_ndcg_at_k)
    print("MOJO_RESULT rerank_eval::ndcg_at_k", _summary_ndcg_at_k)
    var _acc_pairwise_margin_accuracy: Float64 = 0.0
    var _t0_pairwise_margin_accuracy = perf_counter_ns()
    for _ in range(N):
        _acc_pairwise_margin_accuracy += pairwise_margin_accuracy(_lf5, _lf5, 0.5)
    var _t1_pairwise_margin_accuracy = perf_counter_ns()
    var _ns_pairwise_margin_accuracy = Float64(_t1_pairwise_margin_accuracy - _t0_pairwise_margin_accuracy) / Float64(N)
    print("MOJO_TIMING rerank_eval::pairwise_margin_accuracy", _ns_pairwise_margin_accuracy, _acc_pairwise_margin_accuracy)
    var _result_pairwise_margin_accuracy = pairwise_margin_accuracy(_lf5, _lf5, 0.5)
    var _summary_pairwise_margin_accuracy = _summary_float64(_result_pairwise_margin_accuracy)
    print("MOJO_RESULT rerank_eval::pairwise_margin_accuracy", _summary_pairwise_margin_accuracy)
    var _acc_score_separation: Float64 = 0.0
    var _t0_score_separation = perf_counter_ns()
    for _ in range(N):
        _acc_score_separation += score_separation(_lf5, _lf5)
    var _t1_score_separation = perf_counter_ns()
    var _ns_score_separation = Float64(_t1_score_separation - _t0_score_separation) / Float64(N)
    print("MOJO_TIMING rerank_eval::score_separation", _ns_score_separation, _acc_score_separation)
    var _result_score_separation = score_separation(_lf5, _lf5)
    var _summary_score_separation = _summary_float64(_result_score_separation)
    print("MOJO_RESULT rerank_eval::score_separation", _summary_score_separation)
    var _acc_latency_weighted_quality: Float64 = 0.0
    var _t0_latency_weighted_quality = perf_counter_ns()
    for _ in range(N):
        _acc_latency_weighted_quality += latency_weighted_quality(0.5, 0.5, 0.5)
    var _t1_latency_weighted_quality = perf_counter_ns()
    var _ns_latency_weighted_quality = Float64(_t1_latency_weighted_quality - _t0_latency_weighted_quality) / Float64(N)
    print("MOJO_TIMING rerank_eval::latency_weighted_quality", _ns_latency_weighted_quality, _acc_latency_weighted_quality)
    var _result_latency_weighted_quality = latency_weighted_quality(0.5, 0.5, 0.5)
    var _summary_latency_weighted_quality = _summary_float64(_result_latency_weighted_quality)
    print("MOJO_RESULT rerank_eval::latency_weighted_quality", _summary_latency_weighted_quality)
