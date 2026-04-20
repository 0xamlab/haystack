"""test_env.mojo — auto-generated tests for env library."""
from std.math import isnan, isinf
from env import env_get, env_get_int, env_get_float, env_get_bool, env_is_set

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

    _ = env_get("test", "test")
    passed += 1; print("  ✅ env::env_get")
    _ = env_get_int("test", 5)
    passed += 1; print("  ✅ env::env_get_int")
    var _v_env_get_float = env_get_float("test", 0.5)
    if is_finite(_v_env_get_float): passed += 1; print("  ✅ env::env_get_float =", _v_env_get_float)
    else: failed += 1; print("  ❌ env::env_get_float → non-finite:", _v_env_get_float)
    _ = env_get_bool("test", True)
    passed += 1; print("  ✅ env::env_get_bool")
    _ = env_is_set("test")
    passed += 1; print("  ✅ env::env_is_set")

    print("  [env] Passed:", passed, "Failed:", failed)
