"""bench_pipeline.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pipeline import map_list, filter_list, reduce_sum, reduce_product, reduce_min, reduce_max, chain_map_filter, batch, flatten, zip_lists, window, unique_values
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

    var _acc_map_list: Float64 = 0.0
    var _t0_map_list = perf_counter_ns()
    for _ in range(N):
        var _r_map_list = map_list(_lf5, 5)
        _acc_map_list += Float64(len(_r_map_list))
    var _t1_map_list = perf_counter_ns()
    var _ns_map_list = Float64(_t1_map_list - _t0_map_list) / Float64(N)
    print("MOJO_TIMING pipeline::map_list", _ns_map_list, _acc_map_list)
    var _acc_filter_list: Float64 = 0.0
    var _t0_filter_list = perf_counter_ns()
    for _ in range(N):
        var _r_filter_list = filter_list(_lf5, 5, 0.5)
        _acc_filter_list += Float64(len(_r_filter_list))
    var _t1_filter_list = perf_counter_ns()
    var _ns_filter_list = Float64(_t1_filter_list - _t0_filter_list) / Float64(N)
    print("MOJO_TIMING pipeline::filter_list", _ns_filter_list, _acc_filter_list)
    var _acc_reduce_sum: Float64 = 0.0
    var _t0_reduce_sum = perf_counter_ns()
    for _ in range(N):
        _acc_reduce_sum += reduce_sum(_lf5)
    var _t1_reduce_sum = perf_counter_ns()
    var _ns_reduce_sum = Float64(_t1_reduce_sum - _t0_reduce_sum) / Float64(N)
    print("MOJO_TIMING pipeline::reduce_sum", _ns_reduce_sum, _acc_reduce_sum)
    var _acc_reduce_product: Float64 = 0.0
    var _t0_reduce_product = perf_counter_ns()
    for _ in range(N):
        _acc_reduce_product += reduce_product(_lf5)
    var _t1_reduce_product = perf_counter_ns()
    var _ns_reduce_product = Float64(_t1_reduce_product - _t0_reduce_product) / Float64(N)
    print("MOJO_TIMING pipeline::reduce_product", _ns_reduce_product, _acc_reduce_product)
    var _acc_reduce_min: Float64 = 0.0
    var _t0_reduce_min = perf_counter_ns()
    for _ in range(N):
        _acc_reduce_min += reduce_min(_lf5)
    var _t1_reduce_min = perf_counter_ns()
    var _ns_reduce_min = Float64(_t1_reduce_min - _t0_reduce_min) / Float64(N)
    print("MOJO_TIMING pipeline::reduce_min", _ns_reduce_min, _acc_reduce_min)
    var _acc_reduce_max: Float64 = 0.0
    var _t0_reduce_max = perf_counter_ns()
    for _ in range(N):
        _acc_reduce_max += reduce_max(_lf5)
    var _t1_reduce_max = perf_counter_ns()
    var _ns_reduce_max = Float64(_t1_reduce_max - _t0_reduce_max) / Float64(N)
    print("MOJO_TIMING pipeline::reduce_max", _ns_reduce_max, _acc_reduce_max)
    var _acc_chain_map_filter: Float64 = 0.0
    var _t0_chain_map_filter = perf_counter_ns()
    for _ in range(N):
        var _r_chain_map_filter = chain_map_filter(_lf5, 5, 5, 0.5)
        _acc_chain_map_filter += Float64(len(_r_chain_map_filter))
    var _t1_chain_map_filter = perf_counter_ns()
    var _ns_chain_map_filter = Float64(_t1_chain_map_filter - _t0_chain_map_filter) / Float64(N)
    print("MOJO_TIMING pipeline::chain_map_filter", _ns_chain_map_filter, _acc_chain_map_filter)
    var _acc_batch: Float64 = 0.0
    var _t0_batch = perf_counter_ns()
    for _ in range(N):
        var _r_batch = batch(_lf5, 5)
        _acc_batch += Float64(len(_r_batch))
    var _t1_batch = perf_counter_ns()
    var _ns_batch = Float64(_t1_batch - _t0_batch) / Float64(N)
    print("MOJO_TIMING pipeline::batch", _ns_batch, _acc_batch)
    var _acc_flatten: Float64 = 0.0
    var _t0_flatten = perf_counter_ns()
    for _ in range(N):
        var _r_flatten = flatten([[0.5,0.6,0.7],[0.4,0.3,0.2],[0.1,0.2,0.3]])
        _acc_flatten += Float64(len(_r_flatten))
    var _t1_flatten = perf_counter_ns()
    var _ns_flatten = Float64(_t1_flatten - _t0_flatten) / Float64(N)
    print("MOJO_TIMING pipeline::flatten", _ns_flatten, _acc_flatten)
    var _acc_zip_lists: Float64 = 0.0
    var _t0_zip_lists = perf_counter_ns()
    for _ in range(N):
        var _r_zip_lists = zip_lists(_lf5, _lf5)
        _acc_zip_lists += Float64(len(_r_zip_lists))
    var _t1_zip_lists = perf_counter_ns()
    var _ns_zip_lists = Float64(_t1_zip_lists - _t0_zip_lists) / Float64(N)
    print("MOJO_TIMING pipeline::zip_lists", _ns_zip_lists, _acc_zip_lists)
    var _acc_window: Float64 = 0.0
    var _t0_window = perf_counter_ns()
    for _ in range(N):
        var _r_window = window(_lf5, 5)
        _acc_window += Float64(len(_r_window))
    var _t1_window = perf_counter_ns()
    var _ns_window = Float64(_t1_window - _t0_window) / Float64(N)
    print("MOJO_TIMING pipeline::window", _ns_window, _acc_window)
    var _acc_unique_values: Float64 = 0.0
    var _t0_unique_values = perf_counter_ns()
    for _ in range(N):
        var _r_unique_values = unique_values(_lf5)
        _acc_unique_values += Float64(len(_r_unique_values))
    var _t1_unique_values = perf_counter_ns()
    var _ns_unique_values = Float64(_t1_unique_values - _t0_unique_values) / Float64(N)
    print("MOJO_TIMING pipeline::unique_values", _ns_unique_values, _acc_unique_values)
