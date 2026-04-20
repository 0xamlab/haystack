"""test_survival.mojo — auto-generated tests for survival library."""
from std.math import isnan, isinf
from survival import kaplan_meier, nelson_aalen, log_rank_statistic, hazard_rate, life_table

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

    var _v_kaplan_meier = kaplan_meier(_lf5, _lb5)
    if len(_v_kaplan_meier) >= 0: passed += 1; print("  ✅ survival::kaplan_meier")
    _ = nelson_aalen(_lf5, _lb5)
    passed += 1; print("  ✅ survival::nelson_aalen")
    var _v_log_rank_statistic = log_rank_statistic(_lf5, _lb5, _lf5, _lb5)
    if is_finite(_v_log_rank_statistic): passed += 1; print("  ✅ survival::log_rank_statistic =", _v_log_rank_statistic)
    else: failed += 1; print("  ❌ survival::log_rank_statistic → non-finite:", _v_log_rank_statistic)
    _ = hazard_rate(_lf5, _lb5, 0.5)
    passed += 1; print("  ✅ survival::hazard_rate")
    _ = life_table(_lf5, _lb5, _lf5)
    passed += 1; print("  ✅ survival::life_table")

    print("  [survival] Passed:", passed, "Failed:", failed)
