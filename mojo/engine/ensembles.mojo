"""
ensembles.mojo — Model ensembling: voting, blending, ridge stacking. Zero Python imports.

Replaces sklearn.ensemble (VotingClassifier, VotingRegressor, and the
StackingRegressor ridge meta-learner). Operates on flat PREDICTION MATRICES
so any model type can feed it. Complements voting.mojo, which is social
choice theory and unrelated to model ensembling.

Layout conventions:
  voting_classify / blend_regression — model-major: entry [m, s] at
    index m * n_samples + s (row = model, col = sample).
  stack_fit_ridge / stack_predict    — sample-major: entry [s, m] at
    index s * n_models + m (row = sample, col = model).

Public API:
  voting_classify  — majority / weighted-majority vote over class labels
  blend_regression — weight-normalized average of regression predictions
  stack_fit_ridge  — closed-form ridge meta-weights from OOF predictions
  stack_predict    — apply stacked meta-weights to a prediction matrix
"""

from std.math import abs as fabs


# ── helpers ──────────────────────────────────────────────────────────────────


def _solve_linear(a_in: List[Float64], b_in: List[Float64], m: Int) -> List[Float64]:
    """Solve A x = b for a row-major m x m system.

    Gaussian elimination with partial pivoting. Returns the empty list if
    the system is (numerically) singular: pivot magnitude below 1e-12.
    """
    var out = List[Float64]()
    if m <= 0 or len(a_in) != m * m or len(b_in) != m:
        return out^
    var a = a_in.copy()
    var b = b_in.copy()

    for col in range(m):
        # Partial pivot: largest |entry| in this column at or below the diagonal.
        var piv = col
        var best = fabs(a[col * m + col])
        for r in range(col + 1, m):
            var v = fabs(a[r * m + col])
            if v > best:
                best = v
                piv = r
        if best < 1e-12:
            return out^
        if piv != col:
            for c in range(m):
                var tmp = a[col * m + c]
                a[col * m + c] = a[piv * m + c]
                a[piv * m + c] = tmp
            var tb = b[col]
            b[col] = b[piv]
            b[piv] = tb
        for r in range(col + 1, m):
            var f = a[r * m + col] / a[col * m + col]
            if f != 0.0:
                for c in range(col, m):
                    a[r * m + c] -= f * a[col * m + c]
                b[r] -= f * b[col]

    # Back-substitution.
    var x = List[Float64](capacity=m)
    for _ in range(m):
        x.append(0.0)
    for col in range(m - 1, -1, -1):
        var s = b[col]
        for c in range(col + 1, m):
            s -= a[col * m + c] * x[c]
        x[col] = s / a[col * m + col]
    return x^


def _effective_weights(weights: List[Float64], n_models: Int) -> List[Float64]:
    """Per-model weights: caller's list if it has n_models entries, else uniform 1.0."""
    var w = List[Float64](capacity=n_models)
    if len(weights) == n_models:
        for m in range(n_models):
            w.append(weights[m])
    else:
        for _ in range(n_models):
            w.append(1.0)
    return w^


# ── voting_classify ──────────────────────────────────────────────────────────


def voting_classify(
    pred_labels: List[Int],
    n_models: Int,
    n_samples: Int,
    n_classes: Int,
    weights: List[Float64],
) -> List[Int]:
    """Majority / weighted-majority vote over per-model class labels.

    pred_labels is flat model-major: label of model m for sample s at index
    m * n_samples + s, each in [0, n_classes). For every sample, each model
    adds its weight to the class it predicted; the highest-scoring class
    wins, with exact ties broken toward the LOWEST class index
    (deterministic). weights of length n_models are used as given (hard
    voting = uniform); any other length (e.g. empty) means uniform 1.0.
    Labels outside [0, n_classes) contribute nothing. Returns one label per
    sample; empty list if dims are non-positive or len(pred_labels) !=
    n_models * n_samples.
    """
    var result = List[Int]()
    if n_models <= 0 or n_samples <= 0 or n_classes <= 0:
        return result^
    if len(pred_labels) != n_models * n_samples:
        return result^
    var w = _effective_weights(weights, n_models)

    var scores = List[Float64](capacity=n_classes)
    for _ in range(n_classes):
        scores.append(0.0)
    for s in range(n_samples):
        for c in range(n_classes):
            scores[c] = 0.0
        for m in range(n_models):
            var lbl = pred_labels[m * n_samples + s]
            if lbl >= 0 and lbl < n_classes:
                scores[lbl] += w[m]
        var best = 0
        var best_score = scores[0]
        for c in range(1, n_classes):
            if scores[c] > best_score:
                best_score = scores[c]
                best = c
        result.append(best)
    return result^


# ── blend_regression ─────────────────────────────────────────────────────────


def blend_regression(
    preds: List[Float64],
    n_models: Int,
    n_samples: Int,
    weights: List[Float64],
) -> List[Float64]:
    """Weighted average of regression predictions, per sample.

    preds is flat model-major: prediction of model m for sample s at index
    m * n_samples + s. Weights are normalized to sum to 1 (so [1, 3] equals
    [0.25, 0.75]); a weights list of the wrong length (e.g. empty) or with
    |sum| < 1e-12 falls back to the uniform mean. Returns one blended value
    per sample; empty list if dims are non-positive or len(preds) !=
    n_models * n_samples.
    """
    var result = List[Float64]()
    if n_models <= 0 or n_samples <= 0:
        return result^
    if len(preds) != n_models * n_samples:
        return result^
    var w = _effective_weights(weights, n_models)
    var total = 0.0
    for m in range(n_models):
        total += w[m]
    if fabs(total) < 1e-12:
        for m in range(n_models):
            w[m] = 1.0
        total = Float64(n_models)
    for m in range(n_models):
        w[m] /= total

    for s in range(n_samples):
        var acc = 0.0
        for m in range(n_models):
            acc += w[m] * preds[m * n_samples + s]
        result.append(acc)
    return result^


# ── stack_fit_ridge ──────────────────────────────────────────────────────────


def stack_fit_ridge(
    oof_preds: List[Float64],
    n_samples: Int,
    n_models: Int,
    y: List[Float64],
    l2: Float64,
) -> List[Float64]:
    """Closed-form ridge meta-weights from out-of-fold predictions.

    oof_preds is flat SAMPLE-major: prediction of model m for sample s at
    index s * n_models + m (rows = samples, cols = models). Solves the
    normal equations (X^T X + l2 * I) w = X^T y exactly (no intercept);
    negative l2 is treated as 0. Returns n_models meta-weights for
    stack_predict; empty list if dims are inconsistent or the system is
    singular (e.g. duplicated models with l2 = 0 — pass l2 > 0 to
    regularize).
    """
    var result = List[Float64]()
    if n_samples <= 0 or n_models <= 0:
        return result^
    if len(oof_preds) != n_samples * n_models or len(y) != n_samples:
        return result^
    var lam = l2
    if lam < 0.0:
        lam = 0.0

    # X^T X (m x m, symmetric) and X^T y (m).
    var xtx = List[Float64](capacity=n_models * n_models)
    for _ in range(n_models * n_models):
        xtx.append(0.0)
    var xty = List[Float64](capacity=n_models)
    for _ in range(n_models):
        xty.append(0.0)
    for s in range(n_samples):
        var row = s * n_models
        for i in range(n_models):
            var xi = oof_preds[row + i]
            xty[i] += xi * y[s]
            for j in range(i, n_models):
                xtx[i * n_models + j] += xi * oof_preds[row + j]
    for i in range(n_models):
        for j in range(i + 1, n_models):
            xtx[j * n_models + i] = xtx[i * n_models + j]
        xtx[i * n_models + i] += lam

    return _solve_linear(xtx, xty, n_models)


# ── stack_predict ────────────────────────────────────────────────────────────


def stack_predict(
    preds: List[Float64],
    n_samples: Int,
    n_models: Int,
    weights: List[Float64],
) -> List[Float64]:
    """Apply meta-weights: out[s] = sum_m weights[m] * preds[s, m].

    preds is flat SAMPLE-major (index s * n_models + m), matching
    stack_fit_ridge. Weights are used raw — NOT normalized — since ridge
    meta-weights already encode scale. Returns one prediction per sample;
    empty list if dims are non-positive, len(weights) != n_models, or
    len(preds) != n_samples * n_models.
    """
    var result = List[Float64]()
    if n_samples <= 0 or n_models <= 0:
        return result^
    if len(preds) != n_samples * n_models or len(weights) != n_models:
        return result^
    for s in range(n_samples):
        var acc = 0.0
        var row = s * n_models
        for m in range(n_models):
            acc += weights[m] * preds[row + m]
        result.append(acc)
    return result^
