---
icon: chart-scatter
description: Distance functions, k-means and k-NN, Gaussian Naive Bayes, preprocessing transforms, evaluation metrics, and a bagged decision-stump random forest across seven independent kernel modules.
---

# Classical ML algorithms

Seven small, self-contained modules for the classical ML operations that sit underneath (or
alongside) the single-model pages elsewhere in this section — ARIMA, SVM, HMM, gradient boosting,
and the rest. Where those pages are one estimator each, this page is the toolbox: distance metrics,
k-means and k-nearest-neighbors, a from-scratch Gaussian Naive Bayes classifier, one-shot feature
preprocessing (scaling, one-hot, polynomial features, train/test split), the point-prediction
metrics almost every other module calls to grade itself, and a bootstrap-aggregated ensemble of
single-split decision stumps standing in for a random forest. None of the seven import Python or
share code with each other — each module implements its own copy of anything it needs, including
distance functions duplicated verbatim across three of them.

```python
from algenta import MojoRuntime

runtime = MojoRuntime(mode="local")

runtime.execute("ml.knn", "euclidean_distance_knn", [[0.0, 0.0], [3.0, 4.0]])["result"]
# 5.0 — the classic 3-4-5 right triangle

runtime.execute("ml.metrics", "precision_recall_f1",
                [[1, 1, 0, 0, 1], [1, 0, 0, 1, 1]])["result"]
# {"precision": 0.6666666666666666, "recall": 0.6666666666666666, "f1": 0.6666666666666666}
```

## The modules

| Module | What it does |
| --- | --- |
| `ml.classifiers` | Euclidean/Manhattan/cosine distance, logistic sigmoid and softmax, a majority-vote k-NN predictor, and a k-means (`kmeans_cluster`) that `raise`s a catchable error on ragged input instead of aborting. |
| `ml.clustering` | A second, independent k-means (`kmeans`) returning a full `KMeansResult` (centroids, labels, inertia, iteration count), plus `assign_cluster` and `silhouette_score`. |
| `ml.knn` | The full k-NN toolbox: batched and distance-weighted classification, true mean-based regression, leave-one-out cross-validation, and `optimal_k` search. |
| `ml.metrics` | Accuracy, MSE/RMSE/MAE/R², an n×n confusion matrix, and binary precision/recall/F1 over `Float64`/`Int` label lists. |
| `ml.naive_bayes` | A Gaussian Naive Bayes classifier (fit, predict, batch predict) with its own priors, accuracy, confusion matrix, and per-class precision/recall/F1. |
| `ml.preprocessing` | Stateless one-shot transforms: min-max, z-score and median-IQR scaling, one-hot encoding, polynomial features, and a deterministic train/test split. |
| `ml.random_forest` | Bootstrap aggregation of single-split decision stumps: bagging, feature subsampling, out-of-bag R², permutation feature importance, and cross-tree prediction variance. |

## Distance functions, duplicated on purpose

Each module is self-contained, so the same handful of distance functions exist more than once
rather than being imported from a shared location:

- `euclidean_distance` is defined identically in `ml.classifiers` and `ml.clustering`; `ml.knn`
  has the same body under the name `euclidean_distance_knn` (renamed to avoid a symbol clash with
  its own file, not because it behaves differently).
- `manhattan_distance` is defined identically in `ml.classifiers` and `ml.knn`.

All three implementations take `min(len(a), len(b))` as the comparison length rather than
requiring equal-length vectors, so a longer vector's trailing elements are silently ignored instead
of raising.

## Two k-means implementations, one guarded

`ml.classifiers.kmeans_cluster(data, k, max_iter=100)` and `ml.clustering.kmeans(data, k,
max_iter=100, tol=1e-6)` are independent implementations of Lloyd's algorithm with random restart
of empty clusters, not a shared core with two entry points, and they diverge in an important way:

- `kmeans_cluster` returns only `List[Int]` labels and `raise`s a catchable `Error` the moment any
  point after the first has a different dimensionality than `data[0]`. The source comment is
  explicit about why: a bounds-check abort here would kill the whole worker process, "the exact
  same bug shape as `embeddings.centroid`," so — unlike this same module's lenient min-length
  distance functions above — it is "fixed in place rather than given a `_strict` sibling."
- `kmeans` returns a full `KMeansResult` (centroids, labels, inertia, iterations) and adds a
  convergence tolerance, but has no equivalent length check. A ragged `data` list handed to it
  directly hits the same uncaught bounds violation that `kmeans_cluster` was fixed to avoid —
  validate that every row shares `len(data[0])` before calling `ml.clustering.kmeans`, or call
  `ml.classifiers.kmeans_cluster` instead if labels alone are enough.

Neither function takes a seed. Both draw initial centroids from `random_float64()` with no
parameter to fix it, so two calls on the same `data` can converge to differently-numbered (though
not necessarily differently-shaped) clusters. `ml.random_forest.bootstrap_indices` and
`feature_subsample` share the same property and the same reason — every bootstrap sample and every
feature subset is freshly unseeded.

{% hint style="warning" %}
**`ml.classifiers.knn_predict`'s docstring promises averaging the code doesn't do.** Its docstring
reads: "Computes Euclidean distance from test_point to every training point, finds the k nearest
neighbours, and returns the most common label. For regression, this returns the mean of the k
nearest labels." The implementation only ever takes the mode (most frequent label among the k
nearest, ties broken toward the first-seen value) — there is no averaging branch in the source, for
`Float64` labels or otherwise. For real k-NN regression (an actual mean of the k nearest continuous
labels), use `ml.knn.knn_regression`, which does average.
{% endhint %}

## Worked examples

Every number below was traced by hand against the real algorithm in `mojo/engine/ml/*.mojo`, not
lifted from the module's own test file — see [Verification](#verification).

**k-NN classification.** Two well-separated clusters:

```python
X_train = [[0.0, 0.0], [0.0, 1.0], [5.0, 5.0], [5.0, 6.0]]
y_train = [0, 0, 1, 1]

runtime.execute("ml.knn", "knn_predict", [X_train, y_train, [0.5, 0.5], 3])["result"]
# 0 — the 3 nearest neighbours of (0.5, 0.5) are both label-0 points
#     (distance ~0.707 each) and the nearer label-1 point (~6.36); majority is 0
```

**Silhouette score.** Two 1-D clusters, `{0.0, 1.0}` and `{10.0, 11.0}`:

```python
data = [[0.0], [1.0], [10.0], [11.0]]
labels = [0, 0, 1, 1]

runtime.execute("ml.clustering", "silhouette_score", [data, labels])["result"]
# 0.899749373433584
```

Per-point coefficients are `[0.9047619047619048, 0.8947368421052632, 0.8947368421052632,
0.9047619047619048]` — each point's same-cluster neighbor is 1.0 away while the nearer of the two
other-cluster points is roughly 9.5–10.5 away, so every point scores close to the 1.0 ceiling of a
cleanly separated pair of clusters.

**Gaussian Naive Bayes.** One feature, two classes centered at 1.5 and 10.5:

```python
X = [[1.0], [2.0], [10.0], [11.0]]
y = [0, 0, 1, 1]

priors = runtime.execute("ml.naive_bayes", "compute_priors", [y, 2])["result"]
# [0.5, 0.5]
params = runtime.execute("ml.naive_bayes", "gaussian_nb_fit", [X, y, 2])["result"]
# [[1.5, 0.5], [10.5, 0.5]] — [mean, std] per class (std uses population variance, floored at 1e-9)

runtime.execute("ml.naive_bayes", "gaussian_nb_predict", [params, priors, [1.8]])["result"]
# 0 — log-posterior for class 0 is -1.0989..., for class 1 it is roughly -152.3
#     (the (x-mean)^2 term for class 1 is 75.69/(2*0.25) = 151.38, which swamps everything else)
```

**Preprocessing.** The textbook eight-point dataset used to teach sample standard deviation
(mean 5, sample stdev ≈2.138):

```python
data = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]

runtime.execute("ml.preprocessing", "normalize_minmax", [data])["result"]
# [0.0, 0.2857142857142857, 0.2857142857142857, 0.2857142857142857,
#  0.42857142857142855, 0.42857142857142855, 0.7142857142857143, 1.0]

runtime.execute("ml.preprocessing", "normalize_zscore", [data])["result"]
# [-1.403121520040228, -0.46770717334674267, -0.46770717334674267, -0.46770717334674267,
#  0.0, 0.0, 0.9354143466934853, 1.8708286933869707]

runtime.execute("ml.preprocessing", "normalize_robust", [data])["result"]
# median 4.5, IQR 5.5 - 4.0 = 1.5 (linear-interpolated quartiles):
# [-1.6666666666666667, -0.3333333333333333, -0.3333333333333333, -0.3333333333333333,
#  0.3333333333333333, 0.3333333333333333, 1.6666666666666667, 3.0]

runtime.execute("ml.preprocessing", "one_hot_encode", [[2], 4])["result"]
# [[0.0, 0.0, 1.0, 0.0]]

runtime.execute("ml.preprocessing", "polynomial_features", [[2.0], 3])["result"]
# [[2.0, 4.0, 8.0]] — [x, x^2, x^3]

split = runtime.execute("ml.preprocessing", "train_test_split",
                        [list(range(1, 11)), list(range(1, 11)), 0.3])["result"]
split["train_data"]   # [1, 2, 3, 4, 5, 6, 7]
split["test_data"]    # [8, 9, 10]
```

`normalize_zscore` uses `math_ext.stdev`, which is the **sample** standard deviation (divides by
`n - 1`), not the population standard deviation `sklearn.preprocessing.StandardScaler` uses by
default (divides by `n`) — porting a pipeline that assumes `StandardScaler`'s exact output will
need to account for that difference, especially at small `n`.

`train_test_split` computes `n_test = Int(Float64(n) * test_ratio)`, truncating toward zero rather
than rounding. `10 * 0.3` happens to round to exactly `3.0` in `Float64`, giving the clean 7/3 split
above, but `Int()` truncation means a `test_ratio` that lands a hair below an integer boundary in
binary floating point (rather than in the reals) will silently produce one fewer test row than the
ratio implies — there is no rounding step to correct for it.

**A random forest is a bag of single-split stumps.** `tree_predict_simple` tries five candidate
thresholds per feature (`fmin + t/6 * (fmax - fmin)` for `t` in 1..5) and keeps whichever split
reduces total sum-of-squared-error the most, with ties going to the first threshold tried:

```python
X_train = [[1.0], [2.0], [3.0], [8.0], [9.0], [10.0]]
y_train = [1.0, 2.0, 3.0, 8.0, 9.0, 10.0]

runtime.execute("ml.random_forest", "tree_predict_simple",
                [X_train, y_train, [4.0], [0]])["result"]
# 2.0 — best split lands at threshold 4.0 (t=2), separating {1,2,3} from {8,9,10};
#       4.0 <= 4.0 falls left, predicting the left group's mean (2.0)

runtime.execute("ml.random_forest", "tree_predict_simple",
                [X_train, y_train, [6.0], [0]])["result"]
# 9.0 — 6.0 > 4.0 falls right, predicting the right group's mean (9.0)
```

Thresholds at `t=2` (4.0), `t=3` (5.5) and `t=4` (7.0) all produce the identical {1,2,3}/{8,9,10}
partition and tie at the maximum SSE reduction (73.5); because the comparison is strict `>`, the
first one tried (4.0) wins. `random_forest_predict` averages many such stumps, each over a fresh
unseeded bootstrap sample and feature subset — a single stump is deterministic given its inputs,
but the forest built around it is not, run to run.

## Two accuracy/confusion-matrix implementations

`ml.metrics` and `ml.naive_bayes` each ship their own `accuracy` and `confusion_matrix` rather than
sharing one:

- `ml.metrics.accuracy(predicted: List[Float64], actual: List[Float64])` compares by rounding each
  value to the nearest integer (`Int(x + 0.5)`), so it works on raw class-id floats or on rounded
  regression output.
- `ml.naive_bayes.accuracy(predicted: List[Int], actual: List[Int])` compares `Int`s directly, no
  rounding.
- Both modules' `confusion_matrix(predicted, actual, n_classes)` take `Int` labels and are
  byte-for-byte the same algorithm (`matrix[actual][predicted] += 1`, out-of-range labels ignored).

All four — plus `mse`, `mae`, `r2_score`, and `precision_recall_f1`/`precision_recall` — take
`min(len(predicted), len(actual))` as the comparison length. A length mismatch is never an error
here; the longer list's extra entries are dropped silently.

## Refusal behavior

Several functions guard explicitly against a length mismatch that would otherwise index past a
list's end — an uncatchable, worker-killing bounds abort in this runtime rather than a normal
exception — and return a defined sentinel instead:

- `ml.knn.knn_predict`, `knn_predict_batch`, `weighted_knn_predict`, and `knn_regression` all
  return `0`/`0.0` if `len(y_train) == 0` or `len(y_train) != len(X_train)`.
- `ml.knn.leave_one_out_cv` and `optimal_k` return `0.0`/`0` if `len(y) != len(X)`.
- `ml.naive_bayes.gaussian_nb_fit` returns an empty result if `len(y) != len(X)`; `gaussian_nb_predict`
  returns `0` if `priors` is shorter than the number of classes, or if any class's fitted `params`
  row is narrower than `2 * len(x)`.
- `ml.preprocessing.train_test_split` returns an empty `SplitResult` if `len(labels) != len(data)`.
- `ml.random_forest.tree_predict_simple` has the most thorough guard of the seven modules: it
  checks `y_train`/`x_test` length against `X_train`, every row of `X_train` for raggedness,
  `isnan`/`isinf` on every `y_train` value, and every `feature_subset` index for range — all before
  touching the data. `random_forest_predict` and `oob_score` refuse the same way if `y_train`/`y`
  is short, or if `n_trees <= 0`.

The one module without this guard is `ml.clustering.kmeans`, covered above.

`ml.naive_bayes.gaussian_log_likelihood` floors `std` at `MIN_STD = 1e-9` before dividing by it
(and `gaussian_nb_fit` applies the same floor to any class/feature with zero fitted variance), so a
class with a single training sample, or a constant feature, never divides by zero or takes
`log(0)`.

## Verification

The seven `mojo/tests/libs/test_ml_*.mojo` files behind this module family
(`test_ml_classifiers.mojo`, `test_ml_clustering.mojo`, `test_ml_knn.mojo`, `test_ml_metrics.mojo`,
`test_ml_naive_bayes.mojo`, `test_ml_preprocessing.mojo`, `test_ml_random_forest.mojo`) are
auto-generated coverage smoke tests: each calls every function once on a shared, arbitrary fixture
vector and checks only that the result is finite (for scalars) or non-empty (for lists and
structs) — they do not pin specific numeric outputs. The worked examples above were hand-traced
against the real formulas in `mojo/engine/ml/classifiers.mojo`, `clustering.mojo`, `knn.mojo`,
`metrics.mojo`, `naive_bayes.mojo`, `preprocessing.mojo`, and `random_forest.mojo`, and every number
given can be reproduced by re-running the same arithmetic.

**Next:** compare with [fit/transform pipelines](ml-pipelines.md) for stateful, invertible
preprocessing, or [model ensembling](ml-ensembles.md) for combining predictions from arbitrary base
models instead of bagging decision stumps.
