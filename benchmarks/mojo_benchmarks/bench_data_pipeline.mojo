"""bench_data_pipeline.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from data_pipeline import sequence_packing_efficiency, deduplication_minhash_band, curriculum_difficulty_score, dataset_mixing_weight, token_accounting_cost, quality_filter_score, shard_balance_score, streaming_buffer_fullness, epoch_sample_index, data_augmentation_weight
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

    var _acc_sequence_packing_efficiency: Float64 = 0.0
    var _t0_sequence_packing_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_sequence_packing_efficiency += sequence_packing_efficiency(0.5, 0.5)
    var _t1_sequence_packing_efficiency = perf_counter_ns()
    var _ns_sequence_packing_efficiency = Float64(_t1_sequence_packing_efficiency - _t0_sequence_packing_efficiency) / Float64(N)
    print("MOJO_TIMING data_pipeline::sequence_packing_efficiency", _ns_sequence_packing_efficiency, _acc_sequence_packing_efficiency)
    var _acc_deduplication_minhash_band: Float64 = 0.0
    var _t0_deduplication_minhash_band = perf_counter_ns()
    for _ in range(N):
        _acc_deduplication_minhash_band += deduplication_minhash_band(0.5, 0.5)
    var _t1_deduplication_minhash_band = perf_counter_ns()
    var _ns_deduplication_minhash_band = Float64(_t1_deduplication_minhash_band - _t0_deduplication_minhash_band) / Float64(N)
    print("MOJO_TIMING data_pipeline::deduplication_minhash_band", _ns_deduplication_minhash_band, _acc_deduplication_minhash_band)
    var _acc_curriculum_difficulty_score: Float64 = 0.0
    var _t0_curriculum_difficulty_score = perf_counter_ns()
    for _ in range(N):
        _acc_curriculum_difficulty_score += curriculum_difficulty_score(0.5, 0.5, 0.5)
    var _t1_curriculum_difficulty_score = perf_counter_ns()
    var _ns_curriculum_difficulty_score = Float64(_t1_curriculum_difficulty_score - _t0_curriculum_difficulty_score) / Float64(N)
    print("MOJO_TIMING data_pipeline::curriculum_difficulty_score", _ns_curriculum_difficulty_score, _acc_curriculum_difficulty_score)
    var _acc_dataset_mixing_weight: Float64 = 0.0
    var _t0_dataset_mixing_weight = perf_counter_ns()
    for _ in range(N):
        _acc_dataset_mixing_weight += dataset_mixing_weight(0.5, 0.5, 0.5)
    var _t1_dataset_mixing_weight = perf_counter_ns()
    var _ns_dataset_mixing_weight = Float64(_t1_dataset_mixing_weight - _t0_dataset_mixing_weight) / Float64(N)
    print("MOJO_TIMING data_pipeline::dataset_mixing_weight", _ns_dataset_mixing_weight, _acc_dataset_mixing_weight)
    var _acc_token_accounting_cost: Float64 = 0.0
    var _t0_token_accounting_cost = perf_counter_ns()
    for _ in range(N):
        _acc_token_accounting_cost += token_accounting_cost(0.5, 0.5, 0.5)
    var _t1_token_accounting_cost = perf_counter_ns()
    var _ns_token_accounting_cost = Float64(_t1_token_accounting_cost - _t0_token_accounting_cost) / Float64(N)
    print("MOJO_TIMING data_pipeline::token_accounting_cost", _ns_token_accounting_cost, _acc_token_accounting_cost)
    var _acc_quality_filter_score: Float64 = 0.0
    var _t0_quality_filter_score = perf_counter_ns()
    for _ in range(N):
        _acc_quality_filter_score += quality_filter_score(0.5, 0.5, 0.5, 0.5)
    var _t1_quality_filter_score = perf_counter_ns()
    var _ns_quality_filter_score = Float64(_t1_quality_filter_score - _t0_quality_filter_score) / Float64(N)
    print("MOJO_TIMING data_pipeline::quality_filter_score", _ns_quality_filter_score, _acc_quality_filter_score)
    var _acc_shard_balance_score: Float64 = 0.0
    var _t0_shard_balance_score = perf_counter_ns()
    for _ in range(N):
        _acc_shard_balance_score += shard_balance_score(0.5, 0.5)
    var _t1_shard_balance_score = perf_counter_ns()
    var _ns_shard_balance_score = Float64(_t1_shard_balance_score - _t0_shard_balance_score) / Float64(N)
    print("MOJO_TIMING data_pipeline::shard_balance_score", _ns_shard_balance_score, _acc_shard_balance_score)
    var _acc_streaming_buffer_fullness: Float64 = 0.0
    var _t0_streaming_buffer_fullness = perf_counter_ns()
    for _ in range(N):
        _acc_streaming_buffer_fullness += streaming_buffer_fullness(0.5, 0.5)
    var _t1_streaming_buffer_fullness = perf_counter_ns()
    var _ns_streaming_buffer_fullness = Float64(_t1_streaming_buffer_fullness - _t0_streaming_buffer_fullness) / Float64(N)
    print("MOJO_TIMING data_pipeline::streaming_buffer_fullness", _ns_streaming_buffer_fullness, _acc_streaming_buffer_fullness)
    var _acc_epoch_sample_index: Float64 = 0.0
    var _t0_epoch_sample_index = perf_counter_ns()
    for _ in range(N):
        _acc_epoch_sample_index += epoch_sample_index(0.5, 0.5, 0.5, 0.5)
    var _t1_epoch_sample_index = perf_counter_ns()
    var _ns_epoch_sample_index = Float64(_t1_epoch_sample_index - _t0_epoch_sample_index) / Float64(N)
    print("MOJO_TIMING data_pipeline::epoch_sample_index", _ns_epoch_sample_index, _acc_epoch_sample_index)
    var _acc_data_augmentation_weight: Float64 = 0.0
    var _t0_data_augmentation_weight = perf_counter_ns()
    for _ in range(N):
        _acc_data_augmentation_weight += data_augmentation_weight(0.5, 0.5)
    var _t1_data_augmentation_weight = perf_counter_ns()
    var _ns_data_augmentation_weight = Float64(_t1_data_augmentation_weight - _t0_data_augmentation_weight) / Float64(N)
    print("MOJO_TIMING data_pipeline::data_augmentation_weight", _ns_data_augmentation_weight, _acc_data_augmentation_weight)
