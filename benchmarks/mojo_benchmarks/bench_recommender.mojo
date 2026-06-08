"""bench_recommender.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from recommender import cosine_sim_users, predict_rating, popularity_ranking, mean_rating_per_item, mean_rating_per_user, top_n_items, item_overlap, cold_start_recommend, rmse_ratings
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

    var _acc_cosine_sim_users: Float64 = 0.0
    var _t0_cosine_sim_users = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_sim_users += cosine_sim_users(_llf3, 0, 1)
    var _t1_cosine_sim_users = perf_counter_ns()
    var _ns_cosine_sim_users = Float64(_t1_cosine_sim_users - _t0_cosine_sim_users) / Float64(N)
    print("MOJO_TIMING recommender::cosine_sim_users", _ns_cosine_sim_users, _acc_cosine_sim_users)
    var _result_cosine_sim_users = cosine_sim_users(_llf3, 0, 1)
    var _summary_cosine_sim_users = _summary_float64(_result_cosine_sim_users)
    print("MOJO_RESULT recommender::cosine_sim_users", _summary_cosine_sim_users)
    var _acc_predict_rating: Float64 = 0.0
    var _t0_predict_rating = perf_counter_ns()
    for _ in range(N):
        _acc_predict_rating += predict_rating(_llf3, 0, 2, 2)
    var _t1_predict_rating = perf_counter_ns()
    var _ns_predict_rating = Float64(_t1_predict_rating - _t0_predict_rating) / Float64(N)
    print("MOJO_TIMING recommender::predict_rating", _ns_predict_rating, _acc_predict_rating)
    var _result_predict_rating = predict_rating(_llf3, 0, 2, 2)
    var _summary_predict_rating = _summary_float64(_result_predict_rating)
    print("MOJO_RESULT recommender::predict_rating", _summary_predict_rating)
    var _acc_popularity_ranking: Float64 = 0.0
    var _t0_popularity_ranking = perf_counter_ns()
    for _ in range(N):
        var _r_popularity_ranking = popularity_ranking(_llf3)
        _acc_popularity_ranking += Float64(len(_r_popularity_ranking))
    var _t1_popularity_ranking = perf_counter_ns()
    var _ns_popularity_ranking = Float64(_t1_popularity_ranking - _t0_popularity_ranking) / Float64(N)
    print("MOJO_TIMING recommender::popularity_ranking", _ns_popularity_ranking, _acc_popularity_ranking)
    var _result_popularity_ranking = popularity_ranking(_llf3)
    var _summary_popularity_ranking = _summary_list_int(_result_popularity_ranking)
    print("MOJO_RESULT recommender::popularity_ranking", _summary_popularity_ranking)
    var _acc_mean_rating_per_item: Float64 = 0.0
    var _t0_mean_rating_per_item = perf_counter_ns()
    for _ in range(N):
        var _r_mean_rating_per_item = mean_rating_per_item(_llf3)
        _acc_mean_rating_per_item += Float64(len(_r_mean_rating_per_item))
    var _t1_mean_rating_per_item = perf_counter_ns()
    var _ns_mean_rating_per_item = Float64(_t1_mean_rating_per_item - _t0_mean_rating_per_item) / Float64(N)
    print("MOJO_TIMING recommender::mean_rating_per_item", _ns_mean_rating_per_item, _acc_mean_rating_per_item)
    var _result_mean_rating_per_item = mean_rating_per_item(_llf3)
    var _summary_mean_rating_per_item = _summary_list_float64(_result_mean_rating_per_item)
    print("MOJO_RESULT recommender::mean_rating_per_item", _summary_mean_rating_per_item)
    var _acc_mean_rating_per_user: Float64 = 0.0
    var _t0_mean_rating_per_user = perf_counter_ns()
    for _ in range(N):
        var _r_mean_rating_per_user = mean_rating_per_user(_llf3)
        _acc_mean_rating_per_user += Float64(len(_r_mean_rating_per_user))
    var _t1_mean_rating_per_user = perf_counter_ns()
    var _ns_mean_rating_per_user = Float64(_t1_mean_rating_per_user - _t0_mean_rating_per_user) / Float64(N)
    print("MOJO_TIMING recommender::mean_rating_per_user", _ns_mean_rating_per_user, _acc_mean_rating_per_user)
    var _result_mean_rating_per_user = mean_rating_per_user(_llf3)
    var _summary_mean_rating_per_user = _summary_list_float64(_result_mean_rating_per_user)
    print("MOJO_RESULT recommender::mean_rating_per_user", _summary_mean_rating_per_user)
    var _acc_top_n_items: Float64 = 0.0
    var _t0_top_n_items = perf_counter_ns()
    for _ in range(N):
        var _r_top_n_items = top_n_items(_lf5, 5)
        _acc_top_n_items += Float64(len(_r_top_n_items))
    var _t1_top_n_items = perf_counter_ns()
    var _ns_top_n_items = Float64(_t1_top_n_items - _t0_top_n_items) / Float64(N)
    print("MOJO_TIMING recommender::top_n_items", _ns_top_n_items, _acc_top_n_items)
    var _result_top_n_items = top_n_items(_lf5, 5)
    var _summary_top_n_items = _summary_list_int(_result_top_n_items)
    print("MOJO_RESULT recommender::top_n_items", _summary_top_n_items)
    var _acc_item_overlap: Float64 = 0.0
    var _t0_item_overlap = perf_counter_ns()
    for _ in range(N):
        _acc_item_overlap += Float64(item_overlap(_llf3, 0, 1))
    var _t1_item_overlap = perf_counter_ns()
    var _ns_item_overlap = Float64(_t1_item_overlap - _t0_item_overlap) / Float64(N)
    print("MOJO_TIMING recommender::item_overlap", _ns_item_overlap, _acc_item_overlap)
    var _result_item_overlap = item_overlap(_llf3, 0, 1)
    var _summary_item_overlap = _summary_int(_result_item_overlap)
    print("MOJO_RESULT recommender::item_overlap", _summary_item_overlap)
    var _acc_cold_start_recommend: Float64 = 0.0
    var _t0_cold_start_recommend = perf_counter_ns()
    for _ in range(N):
        var _r_cold_start_recommend = cold_start_recommend(_llf3, 2)
        _acc_cold_start_recommend += Float64(len(_r_cold_start_recommend))
    var _t1_cold_start_recommend = perf_counter_ns()
    var _ns_cold_start_recommend = Float64(_t1_cold_start_recommend - _t0_cold_start_recommend) / Float64(N)
    print("MOJO_TIMING recommender::cold_start_recommend", _ns_cold_start_recommend, _acc_cold_start_recommend)
    var _result_cold_start_recommend = cold_start_recommend(_llf3, 2)
    var _summary_cold_start_recommend = _summary_list_int(_result_cold_start_recommend)
    print("MOJO_RESULT recommender::cold_start_recommend", _summary_cold_start_recommend)
    var _acc_rmse_ratings: Float64 = 0.0
    var _t0_rmse_ratings = perf_counter_ns()
    for _ in range(N):
        _acc_rmse_ratings += rmse_ratings(_lf5, _lf5)
    var _t1_rmse_ratings = perf_counter_ns()
    var _ns_rmse_ratings = Float64(_t1_rmse_ratings - _t0_rmse_ratings) / Float64(N)
    print("MOJO_TIMING recommender::rmse_ratings", _ns_rmse_ratings, _acc_rmse_ratings)
    var _result_rmse_ratings = rmse_ratings(_lf5, _lf5)
    var _summary_rmse_ratings = _summary_float64(_result_rmse_ratings)
    print("MOJO_RESULT recommender::rmse_ratings", _summary_rmse_ratings)
