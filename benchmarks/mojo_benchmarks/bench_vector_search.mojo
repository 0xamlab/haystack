"""bench_vector_search.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from vector_search import hnsw_layer_probability, hnsw_search_ef_scale, ivf_coarse_quantizer_dist, pq_quantization_error, lsh_hash_bit, recall_at_k, mrr_score, beam_search_score, faiss_nprobe_coverage, ann_distance_bound
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

    var _acc_hnsw_layer_probability: Float64 = 0.0
    var _t0_hnsw_layer_probability = perf_counter_ns()
    for _ in range(N):
        _acc_hnsw_layer_probability += hnsw_layer_probability(0.5, 0.5)
    var _t1_hnsw_layer_probability = perf_counter_ns()
    var _ns_hnsw_layer_probability = Float64(_t1_hnsw_layer_probability - _t0_hnsw_layer_probability) / Float64(N)
    print("MOJO_TIMING vector_search::hnsw_layer_probability", _ns_hnsw_layer_probability, _acc_hnsw_layer_probability)
    var _acc_hnsw_search_ef_scale: Float64 = 0.0
    var _t0_hnsw_search_ef_scale = perf_counter_ns()
    for _ in range(N):
        _acc_hnsw_search_ef_scale += hnsw_search_ef_scale(0.5, 0.5)
    var _t1_hnsw_search_ef_scale = perf_counter_ns()
    var _ns_hnsw_search_ef_scale = Float64(_t1_hnsw_search_ef_scale - _t0_hnsw_search_ef_scale) / Float64(N)
    print("MOJO_TIMING vector_search::hnsw_search_ef_scale", _ns_hnsw_search_ef_scale, _acc_hnsw_search_ef_scale)
    var _acc_ivf_coarse_quantizer_dist: Float64 = 0.0
    var _t0_ivf_coarse_quantizer_dist = perf_counter_ns()
    for _ in range(N):
        _acc_ivf_coarse_quantizer_dist += ivf_coarse_quantizer_dist(0.5, 0.5)
    var _t1_ivf_coarse_quantizer_dist = perf_counter_ns()
    var _ns_ivf_coarse_quantizer_dist = Float64(_t1_ivf_coarse_quantizer_dist - _t0_ivf_coarse_quantizer_dist) / Float64(N)
    print("MOJO_TIMING vector_search::ivf_coarse_quantizer_dist", _ns_ivf_coarse_quantizer_dist, _acc_ivf_coarse_quantizer_dist)
    var _acc_pq_quantization_error: Float64 = 0.0
    var _t0_pq_quantization_error = perf_counter_ns()
    for _ in range(N):
        _acc_pq_quantization_error += pq_quantization_error(0.5, 0.5, 0.5)
    var _t1_pq_quantization_error = perf_counter_ns()
    var _ns_pq_quantization_error = Float64(_t1_pq_quantization_error - _t0_pq_quantization_error) / Float64(N)
    print("MOJO_TIMING vector_search::pq_quantization_error", _ns_pq_quantization_error, _acc_pq_quantization_error)
    var _acc_lsh_hash_bit: Float64 = 0.0
    var _t0_lsh_hash_bit = perf_counter_ns()
    for _ in range(N):
        _acc_lsh_hash_bit += lsh_hash_bit(0.5, 0.5, 0.5)
    var _t1_lsh_hash_bit = perf_counter_ns()
    var _ns_lsh_hash_bit = Float64(_t1_lsh_hash_bit - _t0_lsh_hash_bit) / Float64(N)
    print("MOJO_TIMING vector_search::lsh_hash_bit", _ns_lsh_hash_bit, _acc_lsh_hash_bit)
    var _acc_recall_at_k: Float64 = 0.0
    var _t0_recall_at_k = perf_counter_ns()
    for _ in range(N):
        _acc_recall_at_k += recall_at_k(0.5, 0.5, 0.5)
    var _t1_recall_at_k = perf_counter_ns()
    var _ns_recall_at_k = Float64(_t1_recall_at_k - _t0_recall_at_k) / Float64(N)
    print("MOJO_TIMING vector_search::recall_at_k", _ns_recall_at_k, _acc_recall_at_k)
    var _acc_mrr_score: Float64 = 0.0
    var _t0_mrr_score = perf_counter_ns()
    for _ in range(N):
        _acc_mrr_score += mrr_score(0.5)
    var _t1_mrr_score = perf_counter_ns()
    var _ns_mrr_score = Float64(_t1_mrr_score - _t0_mrr_score) / Float64(N)
    print("MOJO_TIMING vector_search::mrr_score", _ns_mrr_score, _acc_mrr_score)
    var _acc_beam_search_score: Float64 = 0.0
    var _t0_beam_search_score = perf_counter_ns()
    for _ in range(N):
        _acc_beam_search_score += beam_search_score(0.5, 0.5, 0.5)
    var _t1_beam_search_score = perf_counter_ns()
    var _ns_beam_search_score = Float64(_t1_beam_search_score - _t0_beam_search_score) / Float64(N)
    print("MOJO_TIMING vector_search::beam_search_score", _ns_beam_search_score, _acc_beam_search_score)
    var _acc_faiss_nprobe_coverage: Float64 = 0.0
    var _t0_faiss_nprobe_coverage = perf_counter_ns()
    for _ in range(N):
        _acc_faiss_nprobe_coverage += faiss_nprobe_coverage(0.5, 0.5)
    var _t1_faiss_nprobe_coverage = perf_counter_ns()
    var _ns_faiss_nprobe_coverage = Float64(_t1_faiss_nprobe_coverage - _t0_faiss_nprobe_coverage) / Float64(N)
    print("MOJO_TIMING vector_search::faiss_nprobe_coverage", _ns_faiss_nprobe_coverage, _acc_faiss_nprobe_coverage)
    var _acc_ann_distance_bound: Float64 = 0.0
    var _t0_ann_distance_bound = perf_counter_ns()
    for _ in range(N):
        _acc_ann_distance_bound += ann_distance_bound(0.5, 0.5)
    var _t1_ann_distance_bound = perf_counter_ns()
    var _ns_ann_distance_bound = Float64(_t1_ann_distance_bound - _t0_ann_distance_bound) / Float64(N)
    print("MOJO_TIMING vector_search::ann_distance_bound", _ns_ann_distance_bound, _acc_ann_distance_bound)
