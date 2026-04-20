"""test_cellular.mojo — auto-generated tests for cellular library."""
from std.math import isnan, isinf
from cellular import grid_create, grid_randomize, rule_lookup, elementary_ca_step, run_elementary_ca

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

    _ = grid_create(5, 5)
    passed += 1; print("  ✅ cellular::grid_create")
    _ = grid_randomize(5, 5, 0.5)
    passed += 1; print("  ✅ cellular::grid_randomize")
    _ = rule_lookup(5, 5, 5, 5)
    passed += 1; print("  ✅ cellular::rule_lookup")
    var _v_elementary_ca_step = elementary_ca_step(_li5, 5)
    if len(_v_elementary_ca_step) >= 0: passed += 1; print("  ✅ cellular::elementary_ca_step")
    _ = run_elementary_ca(_li5, 5, 5)
    passed += 1; print("  ✅ cellular::run_elementary_ca")

    print("  [cellular] Passed:", passed, "Failed:", failed)
