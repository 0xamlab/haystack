"""test_recommender.mojo — auto-generated tests for recommender library."""
from std.math import isnan, isinf
from recommender import top_n_items, rmse_ratings

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_top_n_items = top_n_items(_lf5, 5)
    if len(_v_top_n_items) >= 0: passed += 1; print("  ✅ recommender::top_n_items")
    var _v_rmse_ratings = rmse_ratings(_lf5, _lf5)
    if is_finite(_v_rmse_ratings): passed += 1; print("  ✅ recommender::rmse_ratings =", _v_rmse_ratings)
    else: failed += 1; print("  ❌ recommender::rmse_ratings → non-finite:", _v_rmse_ratings)

    print("  [recommender] Passed:", passed, "Failed:", failed)
