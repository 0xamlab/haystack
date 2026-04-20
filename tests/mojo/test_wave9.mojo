"""
test_wave9.mojo — Tests for Wave 9 libraries: ML Primitives.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_wave9.mojo
"""
from ml.preprocessing import (
    normalize_minmax,
    normalize_zscore,
    normalize_robust,
    one_hot_encode,
    polynomial_features,
    train_test_split,
)
from ml.metrics import (
    accuracy,
    mse,
    rmse,
    mae,
    r2_score,
    confusion_matrix,
    precision_recall_f1,
)
from ml.classifiers import (
    euclidean_distance,
    manhattan_distance,
    cosine_similarity,
    logistic_sigmoid,
    softmax,
    knn_predict,
    kmeans_cluster,
)
from std.math import abs as fabs


def main() raises:
    print("━━━ Wave 9 test suite (ML Primitives) ━━━")
    print("")

    # ── Preprocessing ──────────────────────────────────────────────────────
    var data = List[Float64]()
    data.append(10.0)
    data.append(20.0)
    data.append(30.0)
    data.append(40.0)
    data.append(50.0)
    var normed = normalize_minmax(data)
    assert_true(fabs(normed[0] - 0.0) < 0.001, "minmax[0] should be 0.0")
    assert_true(fabs(normed[4] - 1.0) < 0.001, "minmax[4] should be 1.0")
    assert_true(fabs(normed[2] - 0.5) < 0.001, "minmax[2] should be 0.5")

    var zscored = normalize_zscore(data)
    # mean should be ~0
    var z_mean: Float64 = 0.0
    for i in range(len(zscored)):
        z_mean += zscored[i]
    z_mean /= Float64(len(zscored))
    assert_true(fabs(z_mean) < 0.001, "zscore mean should be ~0")

    # Robust scaling
    var robust = normalize_robust(data)
    assert_true(len(robust) == 5, "robust should have 5 elements")

    # One-hot encoding
    var cats = List[Int]()
    cats.append(0)
    cats.append(1)
    cats.append(2)
    var encoded = one_hot_encode(cats, 3)
    assert_true(len(encoded) == 3, "one_hot should have 3 rows")
    assert_true(fabs(encoded[0][0] - 1.0) < 0.001, "one_hot[0][0] should be 1")
    assert_true(fabs(encoded[0][1] - 0.0) < 0.001, "one_hot[0][1] should be 0")
    assert_true(fabs(encoded[1][1] - 1.0) < 0.001, "one_hot[1][1] should be 1")
    assert_true(fabs(encoded[2][2] - 1.0) < 0.001, "one_hot[2][2] should be 1")

    # Polynomial features
    var x = List[Float64]()
    x.append(2.0)
    x.append(3.0)
    var poly = polynomial_features(x, 3)
    assert_true(len(poly) == 2, "poly should have 2 rows")
    assert_true(fabs(poly[0][0] - 2.0) < 0.001, "poly[0][0] = x = 2")
    assert_true(fabs(poly[0][1] - 4.0) < 0.001, "poly[0][1] = x^2 = 4")
    assert_true(fabs(poly[0][2] - 8.0) < 0.001, "poly[0][2] = x^3 = 8")
    assert_true(fabs(poly[1][0] - 3.0) < 0.001, "poly[1][0] = x = 3")
    assert_true(fabs(poly[1][1] - 9.0) < 0.001, "poly[1][1] = x^2 = 9")
    assert_true(fabs(poly[1][2] - 27.0) < 0.001, "poly[1][2] = x^3 = 27")

    # Train/test split
    var labels = List[Float64]()
    labels.append(0.0)
    labels.append(0.0)
    labels.append(1.0)
    labels.append(1.0)
    labels.append(1.0)
    var split = train_test_split(data, labels, 0.4)
    assert_true(len(split.train_data) == 3, "train_data should have 3 items")
    assert_true(len(split.test_data) == 2, "test_data should have 2 items")
    assert_true(len(split.train_labels) == 3, "train_labels should have 3 items")
    assert_true(len(split.test_labels) == 2, "test_labels should have 2 items")

    print("✅ Preprocessing")

    # ── Metrics ────────────────────────────────────────────────────────────
    var pred = List[Float64]()
    pred.append(1.0)
    pred.append(2.0)
    pred.append(3.0)
    var actual = List[Float64]()
    actual.append(1.0)
    actual.append(2.0)
    actual.append(3.0)
    assert_true(fabs(mse(pred, actual)) < 0.001, "perfect MSE should be 0")
    assert_true(fabs(r2_score(pred, actual) - 1.0) < 0.001, "perfect R² should be 1")
    assert_true(fabs(mae(pred, actual)) < 0.001, "perfect MAE should be 0")
    assert_true(fabs(rmse(pred, actual)) < 0.001, "perfect RMSE should be 0")
    assert_true(fabs(accuracy(pred, actual) - 1.0) < 0.001, "perfect accuracy should be 1")

    var pred2 = List[Float64]()
    pred2.append(1.5)
    pred2.append(2.5)
    pred2.append(3.5)
    assert_true(mse(pred2, actual) > 0, "imperfect MSE should be > 0")
    assert_true(mae(pred2, actual) > 0, "imperfect MAE should be > 0")
    assert_true(r2_score(pred2, actual) < 1.0, "imperfect R² should be < 1")

    # Confusion matrix
    var pred_int = List[Int]()
    pred_int.append(0)
    pred_int.append(1)
    pred_int.append(1)
    pred_int.append(0)
    var actual_int = List[Int]()
    actual_int.append(0)
    actual_int.append(1)
    actual_int.append(0)
    actual_int.append(1)
    var cm = confusion_matrix(pred_int, actual_int, 2)
    assert_true(cm[0][0] == 1, "TN should be 1")
    assert_true(cm[1][1] == 1, "TP should be 1")
    assert_true(cm[0][1] == 1, "FP should be 1")
    assert_true(cm[1][0] == 1, "FN should be 1")

    # Precision / Recall / F1
    var prf = precision_recall_f1(pred_int, actual_int)
    assert_true(fabs(prf.precision - 0.5) < 0.001, "precision should be 0.5")
    assert_true(fabs(prf.recall - 0.5) < 0.001, "recall should be 0.5")
    assert_true(fabs(prf.f1 - 0.5) < 0.001, "F1 should be 0.5")

    print("✅ Metrics")

    # ── Classifiers ────────────────────────────────────────────────────────
    # Euclidean distance
    var a = List[Float64]()
    a.append(0.0)
    a.append(0.0)
    var b = List[Float64]()
    b.append(3.0)
    b.append(4.0)
    assert_true(fabs(euclidean_distance(a, b) - 5.0) < 0.001, "euclidean (3,4) -> 5")

    # Manhattan distance
    assert_true(fabs(manhattan_distance(a, b) - 7.0) < 0.001, "manhattan (3,4) -> 7")

    # Sigmoid
    assert_true(fabs(logistic_sigmoid(0.0) - 0.5) < 0.001, "sigmoid(0) = 0.5")
    assert_true(logistic_sigmoid(100.0) > 0.99, "sigmoid(100) > 0.99")
    assert_true(logistic_sigmoid(-100.0) < 0.01, "sigmoid(-100) < 0.01")

    # Cosine similarity of identical vectors = 1.0
    assert_true(fabs(cosine_similarity(b, b) - 1.0) < 0.001, "cosine(b,b) = 1")

    # Cosine similarity of orthogonal vectors = 0.0
    var orth1 = List[Float64]()
    orth1.append(1.0)
    orth1.append(0.0)
    var orth2 = List[Float64]()
    orth2.append(0.0)
    orth2.append(1.0)
    assert_true(fabs(cosine_similarity(orth1, orth2)) < 0.001, "cosine orthogonal = 0")

    # Softmax sums to 1.0
    var vals = List[Float64]()
    vals.append(1.0)
    vals.append(2.0)
    vals.append(3.0)
    var sm = softmax(vals)
    var sm_sum: Float64 = 0.0
    for i in range(len(sm)):
        sm_sum += sm[i]
    assert_true(fabs(sm_sum - 1.0) < 0.001, "softmax sum = 1")
    # Softmax should be monotonically increasing for sorted input
    assert_true(sm[0] < sm[1], "softmax[0] < softmax[1]")
    assert_true(sm[1] < sm[2], "softmax[1] < softmax[2]")

    # KNN prediction
    var train_x = List[List[Float64]]()
    var p1 = List[Float64]()
    p1.append(0.0)
    p1.append(0.0)
    train_x.append(p1^)
    var p2 = List[Float64]()
    p2.append(1.0)
    p2.append(1.0)
    train_x.append(p2^)
    var p3 = List[Float64]()
    p3.append(0.0)
    p3.append(1.0)
    train_x.append(p3^)
    var p4 = List[Float64]()
    p4.append(10.0)
    p4.append(10.0)
    train_x.append(p4^)
    var p5 = List[Float64]()
    p5.append(11.0)
    p5.append(10.0)
    train_x.append(p5^)
    var p6 = List[Float64]()
    p6.append(10.0)
    p6.append(11.0)
    train_x.append(p6^)
    var train_y = List[Float64]()
    train_y.append(0.0)
    train_y.append(0.0)
    train_y.append(0.0)
    train_y.append(1.0)
    train_y.append(1.0)
    train_y.append(1.0)

    var test_pt = List[Float64]()
    test_pt.append(0.5)
    test_pt.append(0.5)
    var knn_result = knn_predict(train_x, train_y, test_pt, 3)
    assert_true(fabs(knn_result - 0.0) < 0.001, "KNN near origin should predict 0")

    var test_pt2 = List[Float64]()
    test_pt2.append(10.5)
    test_pt2.append(10.5)
    var knn_result2 = knn_predict(train_x, train_y, test_pt2, 3)
    assert_true(fabs(knn_result2 - 1.0) < 0.001, "KNN near (10,10) should predict 1")

    # K-means clustering (smoke test — verify it returns valid assignments)
    var km_data = List[List[Float64]]()
    for i in range(6):
        km_data.append(train_x[i].copy())
    var cluster_labels = kmeans_cluster(km_data, 2, 50)
    assert_true(len(cluster_labels) == 6, "kmeans should return 6 labels")
    # All labels should be 0 or 1
    for i in range(6):
        assert_true(
            cluster_labels[i] >= 0 and cluster_labels[i] < 2,
            "kmeans labels in [0,2)",
        )
    # Points near each other should likely have same cluster
    assert_true(
        cluster_labels[0] == cluster_labels[1]
        and cluster_labels[1] == cluster_labels[2],
        "first 3 points should cluster together",
    )
    assert_true(
        cluster_labels[3] == cluster_labels[4]
        and cluster_labels[4] == cluster_labels[5],
        "last 3 points should cluster together",
    )

    print("✅ Classifiers")

    print("")
    print("✅ All Wave 9 tests passed")


fn assert_true(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("Assertion failed: " + msg)
