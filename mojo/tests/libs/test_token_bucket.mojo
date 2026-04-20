"""test_token_bucket.mojo — auto-generated tests for token_bucket library."""
from std.math import isnan, isinf
from token_bucket import tb_create, lb_create, sw_create

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

    _ = tb_create(0.5, 0.5)
    passed += 1; print("  ✅ token_bucket::tb_create")
    _ = lb_create(0.5, 0.5)
    passed += 1; print("  ✅ token_bucket::lb_create")
    _ = sw_create(0.5, 5)
    passed += 1; print("  ✅ token_bucket::sw_create")

    print("  [token_bucket] Passed:", passed, "Failed:", failed)
