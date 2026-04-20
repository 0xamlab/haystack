"""Tests for Wave 57 — Persistence, Constrained Optimization, Random Forest."""

from persistence import (
    KVStore,
    kv_create,
    kv_put,
    kv_get,
    kv_delete,
    kv_contains,
    kv_size,
    kv_keys,
    kv_values,
    kv_clear,
    snapshot,
    restore,
)
from optimization_constrained import (
    eval_objective_c,
    eval_constraint,
    penalty_method,
    barrier_method,
    is_feasible_c,
    penalty_value,
    gradient_estimate,
    augmented_lagrangian_step,
)
from ml.random_forest import (
    bootstrap_indices,
    feature_subsample,
    tree_predict_simple,
    random_forest_predict,
    random_forest_predict_batch,
    oob_score,
    feature_importance_rf,
    bagging_variance,
)
from std.math import abs as fabs


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error(
            "FAIL: " + msg + " | got " + String(a) + " expected " + String(b)
        )


fn _is_finite(v: Float64) -> Bool:
    return v == v and v < 1e18 and v > -1e18


# ── Persistence Tests ────────────────────────────────────────────────────────


fn test_kv_create() raises:
    var store = kv_create()
    _assert(kv_size(store) == 0, "kv_create: size should be 0")  # 1
    print("  ✓ kv_create")


fn test_kv_put_get() raises:
    var store = kv_create()
    kv_put(store, 10, 3.14)
    _assert(kv_size(store) == 1, "kv_put: size should be 1")  # 2
    _assert_close(kv_get(store, 10), 3.14, 1e-10, "kv_get: should return 3.14")  # 3
    # Update existing key
    kv_put(store, 10, 2.71)
    _assert(kv_size(store) == 1, "kv_put update: size stays 1")  # 4
    _assert_close(kv_get(store, 10), 2.71, 1e-10, "kv_get: should return 2.71")  # 5
    # Multiple keys
    kv_put(store, 20, 1.0)
    kv_put(store, 30, 2.0)
    _assert(kv_size(store) == 3, "kv_put multiple: size 3")  # 6
    _assert_close(kv_get(store, 20), 1.0, 1e-10, "kv_get key 20")  # 7
    _assert_close(kv_get(store, 30), 2.0, 1e-10, "kv_get key 30")  # 8
    print("  ✓ kv_put / kv_get")


fn test_kv_get_miss() raises:
    var store = kv_create()
    _assert_close(kv_get(store, 99), -999999.0, 1e-10, "kv_get miss: sentinel")  # 9
    kv_put(store, 1, 5.0)
    _assert_close(kv_get(store, 2), -999999.0, 1e-10, "kv_get miss on existing store")  # 10
    print("  ✓ kv_get miss → sentinel")


fn test_kv_contains() raises:
    var store = kv_create()
    _assert(not kv_contains(store, 1), "kv_contains: empty → False")  # 11
    kv_put(store, 1, 10.0)
    _assert(kv_contains(store, 1), "kv_contains: present → True")  # 12
    _assert(not kv_contains(store, 2), "kv_contains: absent → False")  # 13
    print("  ✓ kv_contains")


fn test_kv_delete() raises:
    var store = kv_create()
    kv_put(store, 1, 1.0)
    kv_put(store, 2, 2.0)
    kv_put(store, 3, 3.0)
    _assert(kv_size(store) == 3, "kv_delete: size before")  # 14
    var deleted = kv_delete(store, 2)
    _assert(deleted, "kv_delete: returns True")  # 15
    _assert(kv_size(store) == 2, "kv_delete: size after")  # 16
    _assert(not kv_contains(store, 2), "kv_delete: key gone")  # 17
    var not_deleted = kv_delete(store, 99)
    _assert(not not_deleted, "kv_delete: missing key returns False")  # 18
    _assert(kv_size(store) == 2, "kv_delete: size unchanged")  # 19
    print("  ✓ kv_delete")


fn test_kv_keys_values() raises:
    var store = kv_create()
    kv_put(store, 10, 100.0)
    kv_put(store, 20, 200.0)
    var ks = kv_keys(store)
    var vs = kv_values(store)
    _assert(len(ks) == 2, "kv_keys: length 2")  # 20
    _assert(len(vs) == 2, "kv_values: length 2")  # 21
    # Check all keys present (order may vary due to swap-delete)
    var has10 = False
    var has20 = False
    for i in range(len(ks)):
        if ks[i] == 10:
            has10 = True
        if ks[i] == 20:
            has20 = True
    _assert(has10 and has20, "kv_keys: contains 10 and 20")  # 22
    print("  ✓ kv_keys / kv_values")


fn test_kv_clear() raises:
    var store = kv_create()
    kv_put(store, 1, 1.0)
    kv_put(store, 2, 2.0)
    kv_clear(store)
    _assert(kv_size(store) == 0, "kv_clear: size 0")  # 23
    _assert(not kv_contains(store, 1), "kv_clear: key 1 gone")  # 24
    _assert(not kv_contains(store, 2), "kv_clear: key 2 gone")  # 25
    print("  ✓ kv_clear")


fn test_snapshot_restore() raises:
    var store = kv_create()
    kv_put(store, 1, 10.0)
    kv_put(store, 2, 20.0)
    kv_put(store, 3, 30.0)
    var snap = snapshot(store)
    _assert(len(snap) == 3, "snapshot: 3 pairs")  # 26
    # Each pair has 2 elements
    _assert(len(snap[0]) == 2, "snapshot: pair has 2 elems")  # 27
    # Restore
    var store2 = restore(snap)
    _assert(kv_size(store2) == 3, "restore: size 3")  # 28
    _assert_close(kv_get(store2, 1), 10.0, 1e-10, "restore: key 1")  # 29
    _assert_close(kv_get(store2, 2), 20.0, 1e-10, "restore: key 2")  # 30
    _assert_close(kv_get(store2, 3), 30.0, 1e-10, "restore: key 3")  # 31
    print("  ✓ snapshot / restore roundtrip")


# ── Constrained Optimization Tests ───────────────────────────────────────────


fn test_eval_objective_c() raises:
    var x = List[Float64]()
    x.append(1.0)
    x.append(2.0)
    # func_id=0: x0²+x1² = 1+4 = 5
    _assert_close(eval_objective_c(x, 0), 5.0, 1e-10, "obj 0: x0²+x1²")  # 32
    # func_id=1: -(x0*x1) = -2
    _assert_close(eval_objective_c(x, 1), -2.0, 1e-10, "obj 1: -(x0*x1)")  # 33
    # func_id=2: x0+x1 = 3
    _assert_close(eval_objective_c(x, 2), 3.0, 1e-10, "obj 2: x0+x1")  # 34
    print("  ✓ eval_objective_c")


fn test_eval_constraint() raises:
    var x = List[Float64]()
    x.append(0.3)
    x.append(0.3)
    # constraint 0: x0+x1-1 = -0.4  (feasible)
    var g0 = eval_constraint(x, 0)
    _assert(g0 < 0.0, "constraint 0: feasible")  # 35
    # constraint 1: x0²+x1²-1 = 0.18-1 = -0.82 (feasible)
    var g1 = eval_constraint(x, 1)
    _assert(g1 < 0.0, "constraint 1: feasible")  # 36
    # constraint 2: -x0 = -0.3 (feasible since x0>0)
    var g2 = eval_constraint(x, 2)
    _assert(g2 < 0.0, "constraint 2: feasible")  # 37
    # constraint 3: -x1 = -0.3 (feasible)
    var g3 = eval_constraint(x, 3)
    _assert(g3 < 0.0, "constraint 3: feasible")  # 38
    print("  ✓ eval_constraint")


fn test_is_feasible_c() raises:
    var x_feas = List[Float64]()
    x_feas.append(0.3)
    x_feas.append(0.3)
    var cons = List[Int]()
    cons.append(0)
    cons.append(2)
    cons.append(3)
    _assert(is_feasible_c(x_feas, cons), "is_feasible_c: feasible point → True")  # 39

    var x_infeas = List[Float64]()
    x_infeas.append(0.8)
    x_infeas.append(0.8)
    # constraint 0: 0.8+0.8-1 = 0.6 > 0 → infeasible
    _assert(not is_feasible_c(x_infeas, cons), "is_feasible_c: infeasible → False")  # 40
    print("  ✓ is_feasible_c")


fn test_penalty_value() raises:
    var x = List[Float64]()
    x.append(0.3)
    x.append(0.3)
    var cons = List[Int]()
    cons.append(0)
    cons.append(2)
    cons.append(3)
    var pv = penalty_value(x, cons)
    _assert_close(pv, 0.0, 1e-10, "penalty_value: feasible → 0")  # 41

    var x2 = List[Float64]()
    x2.append(0.8)
    x2.append(0.8)
    var pv2 = penalty_value(x2, cons)
    _assert(pv2 > 0.0, "penalty_value: infeasible → >0")  # 42
    print("  ✓ penalty_value")


fn test_gradient_estimate() raises:
    var x = List[Float64]()
    x.append(1.0)
    x.append(1.0)
    var cons = List[Int]()
    cons.append(0)
    var grad = gradient_estimate(x, 0, cons, 10.0)
    _assert(len(grad) == 2, "gradient: 2 components")  # 43
    _assert(_is_finite(grad[0]), "gradient[0] finite")  # 44
    _assert(_is_finite(grad[1]), "gradient[1] finite")  # 45
    print("  ✓ gradient_estimate")


fn test_penalty_method() raises:
    var x0 = List[Float64]()
    x0.append(0.8)
    x0.append(0.8)
    var cons = List[Int]()
    cons.append(0)
    cons.append(2)
    cons.append(3)
    var result = penalty_method(x0, 0, cons, 10.0, 100, 0.01)
    _assert(len(result) == 2, "penalty_method: 2D result")  # 46
    _assert(_is_finite(result[0]), "penalty result[0] finite")  # 47
    _assert(_is_finite(result[1]), "penalty result[1] finite")  # 48
    var obj = eval_objective_c(result, 0)
    _assert(obj < 10.0, "penalty_method: obj < 10")  # 49
    print("  ✓ penalty_method")


fn test_barrier_method() raises:
    var x0 = List[Float64]()
    x0.append(0.3)
    x0.append(0.3)
    var cons = List[Int]()
    cons.append(1)
    cons.append(2)
    cons.append(3)
    var obj_before = eval_objective_c(x0, 0)
    var result = barrier_method(x0, 0, cons, 1.0, 50, 0.01)
    _assert(len(result) == 2, "barrier: 2D result")  # 50
    var obj_after = eval_objective_c(result, 0)
    _assert(_is_finite(obj_after), "barrier: obj finite")  # 51
    _assert(obj_after <= obj_before + 0.1, "barrier: obj improved or stable")  # 52
    print("  ✓ barrier_method")


fn test_augmented_lagrangian() raises:
    var x = List[Float64]()
    x.append(0.7)
    x.append(0.7)
    var lambdas = List[Float64]()
    lambdas.append(0.0)
    lambdas.append(0.0)
    var cons = List[Int]()
    cons.append(0)
    cons.append(1)
    var result = augmented_lagrangian_step(x, lambdas, 0, cons, 10.0, 0.01)
    _assert(len(result) == 2, "aug_lag: returns 2 lists")  # 53
    _assert(len(result[0]) == 2, "aug_lag: new_x has 2 elems")  # 54
    _assert(len(result[1]) == 2, "aug_lag: new_lambdas has 2 elems")  # 55
    _assert(_is_finite(result[0][0]), "aug_lag: new_x[0] finite")  # 56
    _assert(result[1][0] >= 0.0, "aug_lag: lambda[0] >= 0")  # 57
    _assert(result[1][1] >= 0.0, "aug_lag: lambda[1] >= 0")  # 58
    print("  ✓ augmented_lagrangian_step")


# ── Random Forest Tests ──────────────────────────────────────────────────────


fn test_bootstrap_indices() raises:
    var idxs = bootstrap_indices(100, 50)
    _assert(len(idxs) == 50, "bootstrap: correct length")  # 59
    var all_valid = True
    for i in range(len(idxs)):
        if idxs[i] < 0 or idxs[i] >= 100:
            all_valid = False
    _assert(all_valid, "bootstrap: all indices in [0,100)")  # 60
    print("  ✓ bootstrap_indices")


fn test_feature_subsample() raises:
    var fs = feature_subsample(10, 4)
    _assert(len(fs) == 4, "feature_subsample: correct length")  # 61
    var no_dup = True
    for i in range(len(fs)):
        for j in range(i + 1, len(fs)):
            if fs[i] == fs[j]:
                no_dup = False
    _assert(no_dup, "feature_subsample: no duplicates")  # 62
    var in_range = True
    for i in range(len(fs)):
        if fs[i] < 0 or fs[i] >= 10:
            in_range = False
    _assert(in_range, "feature_subsample: all in [0,10)")  # 63
    var fs2 = feature_subsample(3, 10)
    _assert(len(fs2) == 3, "feature_subsample: clamped to n_features")  # 64
    print("  ✓ feature_subsample")


fn _make_train_X() -> List[List[Float64]]:
    """Create simple training data X."""
    var X = List[List[Float64]]()
    # row 1: [1, 0]
    var r1 = List[Float64]()
    r1.append(1.0)
    r1.append(0.0)
    X.append(r1^)
    # row 2: [0, 1]
    var r2 = List[Float64]()
    r2.append(0.0)
    r2.append(1.0)
    X.append(r2^)
    # row 3: [1, 1]
    var r3 = List[Float64]()
    r3.append(1.0)
    r3.append(1.0)
    X.append(r3^)
    # row 4: [2, 0]
    var r4 = List[Float64]()
    r4.append(2.0)
    r4.append(0.0)
    X.append(r4^)
    # row 5: [0, 2]
    var r5 = List[Float64]()
    r5.append(0.0)
    r5.append(2.0)
    X.append(r5^)
    # row 6: [2, 1]
    var r6 = List[Float64]()
    r6.append(2.0)
    r6.append(1.0)
    X.append(r6^)
    # row 7: [1, 2]
    var r7 = List[Float64]()
    r7.append(1.0)
    r7.append(2.0)
    X.append(r7^)
    # row 8: [0.5, 0.5]
    var r8 = List[Float64]()
    r8.append(0.5)
    r8.append(0.5)
    X.append(r8^)
    return X^


fn _make_train_y() -> List[Float64]:
    var y = List[Float64]()
    y.append(2.0)   # 2*1+0
    y.append(1.0)   # 2*0+1
    y.append(3.0)   # 2*1+1
    y.append(4.0)   # 2*2+0
    y.append(2.0)   # 2*0+2
    y.append(5.0)   # 2*2+1
    y.append(4.0)   # 2*1+2
    y.append(1.5)   # 2*0.5+0.5
    return y^


fn test_tree_predict_simple() raises:
    var X = _make_train_X()
    var y = _make_train_y()
    var feats = List[Int]()
    feats.append(0)
    feats.append(1)
    var x_test = List[Float64]()
    x_test.append(1.5)
    x_test.append(0.5)
    var pred = tree_predict_simple(X, y, x_test, feats)
    _assert(_is_finite(pred), "tree_predict_simple: finite")  # 65
    _assert(pred > 0.0, "tree_predict_simple: positive prediction")  # 66
    print("  ✓ tree_predict_simple")


fn test_random_forest_predict() raises:
    var X = _make_train_X()
    var y = _make_train_y()
    var x_test = List[Float64]()
    x_test.append(1.0)
    x_test.append(1.0)
    var pred = random_forest_predict(X, y, x_test, 5, 2)
    _assert(_is_finite(pred), "rf_predict: finite")  # 67
    _assert(pred > 0.0, "rf_predict: positive")  # 68
    _assert(pred < 10.0, "rf_predict: < 10")  # 69
    print("  ✓ random_forest_predict")


fn test_random_forest_predict_batch() raises:
    var X = _make_train_X()
    var y = _make_train_y()
    var X_test = List[List[Float64]]()
    var t1 = List[Float64]()
    t1.append(1.0)
    t1.append(0.5)
    X_test.append(t1^)
    var t2 = List[Float64]()
    t2.append(0.5)
    t2.append(1.0)
    X_test.append(t2^)
    var t3 = List[Float64]()
    t3.append(1.5)
    t3.append(1.5)
    X_test.append(t3^)
    var preds = random_forest_predict_batch(X, y, X_test, 5, 2)
    _assert(len(preds) == 3, "rf_batch: correct length")  # 70
    _assert(_is_finite(preds[0]), "rf_batch[0] finite")  # 71
    _assert(_is_finite(preds[1]), "rf_batch[1] finite")  # 72
    _assert(_is_finite(preds[2]), "rf_batch[2] finite")  # 73
    print("  ✓ random_forest_predict_batch")


fn test_oob_score() raises:
    var X = _make_train_X()
    var y = _make_train_y()
    var score = oob_score(X, y, 10, 2)
    _assert(_is_finite(score), "oob_score: finite")  # 74
    _assert(score >= -1.0, "oob_score: >= -1")  # 75
    _assert(score <= 1.0, "oob_score: <= 1")  # 76
    print("  ✓ oob_score")


fn test_bagging_variance() raises:
    # 3 trees, 4 samples each
    var preds = List[List[Float64]]()
    var p1 = List[Float64]()
    p1.append(1.0)
    p1.append(2.0)
    p1.append(3.0)
    p1.append(4.0)
    preds.append(p1^)
    var p2 = List[Float64]()
    p2.append(1.2)
    p2.append(1.8)
    p2.append(3.1)
    p2.append(3.9)
    preds.append(p2^)
    var p3 = List[Float64]()
    p3.append(0.8)
    p3.append(2.2)
    p3.append(2.9)
    p3.append(4.1)
    preds.append(p3^)
    var variances = bagging_variance(preds)
    _assert(len(variances) == 4, "bagging_variance: 4 samples")  # 77
    for i in range(4):
        _assert(variances[i] >= 0.0, "bagging_variance: non-negative")  # 78-81
    _assert(variances[0] > 0.0, "bagging_variance[0]: > 0")  # 82
    print("  ✓ bagging_variance")


fn test_feature_importance_rf() raises:
    var X = _make_train_X()
    var y = _make_train_y()
    var imp = feature_importance_rf(X, y, 3, 2)
    _assert(len(imp) == 2, "feature_importance: 2 features")  # 83
    _assert(_is_finite(imp[0]), "feature_importance[0] finite")  # 84
    _assert(_is_finite(imp[1]), "feature_importance[1] finite")  # 85
    print("  ✓ feature_importance_rf")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 57 Tests ===")

    print("\n── Persistence ──")
    test_kv_create()
    test_kv_put_get()
    test_kv_get_miss()
    test_kv_contains()
    test_kv_delete()
    test_kv_keys_values()
    test_kv_clear()
    test_snapshot_restore()

    print("\n── Constrained Optimization ──")
    test_eval_objective_c()
    test_eval_constraint()
    test_is_feasible_c()
    test_penalty_value()
    test_gradient_estimate()
    test_penalty_method()
    test_barrier_method()
    test_augmented_lagrangian()

    print("\n── Random Forest ──")
    test_bootstrap_indices()
    test_feature_subsample()
    test_tree_predict_simple()
    test_random_forest_predict()
    test_random_forest_predict_batch()
    test_oob_score()
    test_bagging_variance()
    test_feature_importance_rf()

    print("\n✅ All Wave 57 tests passed (85 assertions)")
