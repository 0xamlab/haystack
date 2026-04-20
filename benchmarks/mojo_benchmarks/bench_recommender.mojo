"""bench_recommender.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from recommender import cosine_sim_users, predict_rating, popularity_ranking, mean_rating_per_item, mean_rating_per_user, top_n_items, item_overlap, cold_start_recommend, rmse_ratings
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

    var _acc_cosine_sim_users: Float64 = 0.0
    var _t0_cosine_sim_users = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_sim_users += cosine_sim_users(_llf3, 0, 1)
    var _t1_cosine_sim_users = perf_counter_ns()
    var _ns_cosine_sim_users = Float64(_t1_cosine_sim_users - _t0_cosine_sim_users) / Float64(N)
    print("MOJO_TIMING recommender::cosine_sim_users", _ns_cosine_sim_users, _acc_cosine_sim_users)
    var _acc_predict_rating: Float64 = 0.0
    var _t0_predict_rating = perf_counter_ns()
    for _ in range(N):
        _acc_predict_rating += predict_rating(_llf3, 0, 2, 2)
    var _t1_predict_rating = perf_counter_ns()
    var _ns_predict_rating = Float64(_t1_predict_rating - _t0_predict_rating) / Float64(N)
    print("MOJO_TIMING recommender::predict_rating", _ns_predict_rating, _acc_predict_rating)
    var _acc_popularity_ranking: Float64 = 0.0
    var _t0_popularity_ranking = perf_counter_ns()
    for _ in range(N):
        var _r_popularity_ranking = popularity_ranking(_llf3)
        _acc_popularity_ranking += Float64(len(_r_popularity_ranking))
    var _t1_popularity_ranking = perf_counter_ns()
    var _ns_popularity_ranking = Float64(_t1_popularity_ranking - _t0_popularity_ranking) / Float64(N)
    print("MOJO_TIMING recommender::popularity_ranking", _ns_popularity_ranking, _acc_popularity_ranking)
    var _acc_mean_rating_per_item: Float64 = 0.0
    var _t0_mean_rating_per_item = perf_counter_ns()
    for _ in range(N):
        var _r_mean_rating_per_item = mean_rating_per_item(_llf3)
        _acc_mean_rating_per_item += Float64(len(_r_mean_rating_per_item))
    var _t1_mean_rating_per_item = perf_counter_ns()
    var _ns_mean_rating_per_item = Float64(_t1_mean_rating_per_item - _t0_mean_rating_per_item) / Float64(N)
    print("MOJO_TIMING recommender::mean_rating_per_item", _ns_mean_rating_per_item, _acc_mean_rating_per_item)
    var _acc_mean_rating_per_user: Float64 = 0.0
    var _t0_mean_rating_per_user = perf_counter_ns()
    for _ in range(N):
        var _r_mean_rating_per_user = mean_rating_per_user(_llf3)
        _acc_mean_rating_per_user += Float64(len(_r_mean_rating_per_user))
    var _t1_mean_rating_per_user = perf_counter_ns()
    var _ns_mean_rating_per_user = Float64(_t1_mean_rating_per_user - _t0_mean_rating_per_user) / Float64(N)
    print("MOJO_TIMING recommender::mean_rating_per_user", _ns_mean_rating_per_user, _acc_mean_rating_per_user)
    var _acc_top_n_items: Float64 = 0.0
    var _t0_top_n_items = perf_counter_ns()
    for _ in range(N):
        var _r_top_n_items = top_n_items(_lf5, 5)
        _acc_top_n_items += Float64(len(_r_top_n_items))
    var _t1_top_n_items = perf_counter_ns()
    var _ns_top_n_items = Float64(_t1_top_n_items - _t0_top_n_items) / Float64(N)
    print("MOJO_TIMING recommender::top_n_items", _ns_top_n_items, _acc_top_n_items)
    var _acc_item_overlap: Float64 = 0.0
    var _t0_item_overlap = perf_counter_ns()
    for _ in range(N):
        _acc_item_overlap += Float64(item_overlap(_llf3, 0, 1))
    var _t1_item_overlap = perf_counter_ns()
    var _ns_item_overlap = Float64(_t1_item_overlap - _t0_item_overlap) / Float64(N)
    print("MOJO_TIMING recommender::item_overlap", _ns_item_overlap, _acc_item_overlap)
    var _acc_cold_start_recommend: Float64 = 0.0
    var _t0_cold_start_recommend = perf_counter_ns()
    for _ in range(N):
        var _r_cold_start_recommend = cold_start_recommend(_llf3, 2)
        _acc_cold_start_recommend += Float64(len(_r_cold_start_recommend))
    var _t1_cold_start_recommend = perf_counter_ns()
    var _ns_cold_start_recommend = Float64(_t1_cold_start_recommend - _t0_cold_start_recommend) / Float64(N)
    print("MOJO_TIMING recommender::cold_start_recommend", _ns_cold_start_recommend, _acc_cold_start_recommend)
    var _acc_rmse_ratings: Float64 = 0.0
    var _t0_rmse_ratings = perf_counter_ns()
    for _ in range(N):
        _acc_rmse_ratings += rmse_ratings(_lf5, _lf5)
    var _t1_rmse_ratings = perf_counter_ns()
    var _ns_rmse_ratings = Float64(_t1_rmse_ratings - _t0_rmse_ratings) / Float64(N)
    print("MOJO_TIMING recommender::rmse_ratings", _ns_rmse_ratings, _acc_rmse_ratings)
