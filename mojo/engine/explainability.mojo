"""
explainability.mojo — Model-agnostic attribution over precomputed prediction grids. Zero Python imports.

Replaces sklearn.inspection (permutation_importance, partial_dependence) and
the coalition-weighting machinery of shap.KernelExplainer. Callback-free by
design: the CALLER evaluates the model and passes precomputed metric /
prediction arrays; this kernel only aggregates and generates coalition
designs (kernel purity). Complements ensembles.mojo — solve the KernelSHAP
weighted regression by scaling coalition row s and its target by
sqrt(weights[s]) and calling stack_fit_ridge.

Public API:
  permutation_importance_from_preds — per-feature metric-shift mean/std
  partial_dependence_grid           — per-gridpoint mean/std over samples
  kernel_shap_weight                — pi(z) = (M-1)/(C(M,|z|)·|z|·(M-|z|))
  shapley_sampling_weights          — seeded 0/1 coalition matrix + pi weights
"""

from std.math import sqrt


# ── result structs ───────────────────────────────────────────────────────────


struct PermutationImportance(Copyable, Movable):
    """Per-feature permutation importance: metric-shift mean and spread."""
    var means: List[Float64]  # mean over repeats of (permuted - base) metric
    var stds: List[Float64]   # population std of the permuted metric per feature

    def __init__(out self):
        self.means = List[Float64]()
        self.stds = List[Float64]()


struct PartialDependence(Copyable, Movable):
    """Per-gridpoint partial dependence: mean and ICE spread over samples."""
    var mean: List[Float64]  # PD curve: mean prediction per grid point
    var std: List[Float64]   # population std over samples per grid point

    def __init__(out self):
        self.mean = List[Float64]()
        self.std = List[Float64]()


struct ShapleySamples(Copyable, Movable):
    """Sampled KernelSHAP coalition design: 0/1 matrix + pi kernel weights."""
    var coalitions: List[Int]   # flat n_samples x n_features, row-major, 0/1
    var weights: List[Float64]  # kernel weight pi(z) per coalition row
    var n_samples: Int
    var n_features: Int

    def __init__(out self):
        self.coalitions = List[Int]()
        self.weights = List[Float64]()
        self.n_samples = 0
        self.n_features = 0


# ── seeded RNG helpers (deterministic xorshift64) ────────────────────────────


def _xorshift64(state: UInt64) -> UInt64:
    var s = state
    s ^= s << 13
    s ^= s >> 7
    s ^= s << 17
    return s


def _seed_state(seed: Int) -> UInt64:
    """Expand an Int seed into a warmed-up nonzero xorshift64 state."""
    var base: UInt64
    if seed < 0:
        base = UInt64(-(seed + 1)) + 1
    else:
        base = UInt64(seed)
    var s = base ^ UInt64(0x9E3779B97F4A7C15)
    if s == 0:
        s = UInt64(0x9E3779B97F4A7C15)
    s = _xorshift64(s)
    s = _xorshift64(s)
    s = _xorshift64(s)
    return s


def _rand_below(mut state: UInt64, bound: Int) -> Int:
    """Uniform-ish integer in [0, bound). bound must be >= 1."""
    state = _xorshift64(state)
    return Int(state % UInt64(bound))


def _rand_bit(mut state: UInt64) -> Int:
    """One fair-ish random bit (top bit of the xorshift64 state)."""
    state = _xorshift64(state)
    return Int(state >> 63)


# ── permutation_importance_from_preds ────────────────────────────────────────


def permutation_importance_from_preds(
    base_metric: Float64,
    permuted_metrics: List[Float64],
    n_features: Int,
    n_repeats: Int,
) -> PermutationImportance:
    """Permutation importance from precomputed metric evaluations.

    The caller evaluates its metric once on unpermuted data (base_metric)
    and once per (feature, repeat) with that feature's column shuffled.
    permuted_metrics is flat FEATURE-major: metric with feature f permuted
    on repeat r at index f * n_repeats + r.

    means[f] = mean over repeats of permuted metric minus base_metric —
    for loss-style metrics (lower is better) positive means the feature
    matters; for higher-is-better scores interpret the sign flipped (or
    negate the metrics). stds[f] = population std (ddof=0) of the permuted
    metric over repeats, matching sklearn's importances_std. Returns empty
    lists if dims are non-positive or len(permuted_metrics) !=
    n_features * n_repeats.
    """
    var out = PermutationImportance()
    if n_features <= 0 or n_repeats <= 0:
        return out^
    if len(permuted_metrics) != n_features * n_repeats:
        return out^
    for f in range(n_features):
        var row = f * n_repeats
        var acc = 0.0
        for r in range(n_repeats):
            acc += permuted_metrics[row + r]
        var mean_metric = acc / Float64(n_repeats)
        var var_acc = 0.0
        for r in range(n_repeats):
            var d = permuted_metrics[row + r] - mean_metric
            var_acc += d * d
        out.means.append(mean_metric - base_metric)
        out.stds.append(sqrt(var_acc / Float64(n_repeats)))
    return out^


# ── partial_dependence_grid ──────────────────────────────────────────────────


def partial_dependence_grid(
    preds_at_gridpoints: List[Float64], n_grid: Int, n_samples: Int
) -> PartialDependence:
    """Aggregate ICE evaluations into a partial-dependence curve.

    The caller forces the feature of interest to grid value g for EVERY
    sample, evaluates the model, and passes the flat GRID-major result:
    prediction for sample s at grid point g at index g * n_samples + s.

    mean[g] is the partial dependence (average prediction at grid point g);
    std[g] is the population std over samples (ICE spread — large values
    flag interactions the PD average hides). Returns empty lists if dims
    are non-positive or len(preds_at_gridpoints) != n_grid * n_samples.
    """
    var out = PartialDependence()
    if n_grid <= 0 or n_samples <= 0:
        return out^
    if len(preds_at_gridpoints) != n_grid * n_samples:
        return out^
    for g in range(n_grid):
        var row = g * n_samples
        var acc = 0.0
        for s in range(n_samples):
            acc += preds_at_gridpoints[row + s]
        var mu = acc / Float64(n_samples)
        var var_acc = 0.0
        for s in range(n_samples):
            var d = preds_at_gridpoints[row + s] - mu
            var_acc += d * d
        out.mean.append(mu)
        out.std.append(sqrt(var_acc / Float64(n_samples)))
    return out^


# ── kernel_shap_weight ───────────────────────────────────────────────────────


def _binom(m: Int, k: Int) -> Float64:
    """C(m, k) as Float64 via the multiplicative formula (no overflow)."""
    var kk = k
    if m - k < kk:
        kk = m - k
    var out = 1.0
    for i in range(kk):
        out = out * Float64(m - i) / Float64(i + 1)
    return out


def kernel_shap_weight(n_features: Int, coalition_size: Int) -> Float64:
    """KernelSHAP kernel weight pi(z) = (M-1) / (C(M,|z|) * |z| * (M-|z|)).

    M = n_features, |z| = coalition_size. Returns 0.0 for the degenerate
    cases the kernel excludes: |z| <= 0, |z| >= M, or M < 2 (the empty and
    full coalitions carry infinite weight and are handled by the caller as
    the base value and full prediction). Symmetric: pi(k) == pi(M-k).
    """
    var m = n_features
    var k = coalition_size
    if m < 2 or k <= 0 or k >= m:
        return 0.0
    return Float64(m - 1) / (_binom(m, k) * Float64(k) * Float64(m - k))


# ── shapley_sampling_weights ─────────────────────────────────────────────────


def _sample_coalition(mut state: UInt64, m: Int) -> List[Int]:
    """One 0/1 coalition of size in [1, m-1], uniform over such coalitions.

    Bernoulli(1/2) per feature with rejection of empty/full rows (bounded
    at 64 attempts — the miss probability is at most 1/2 per attempt, so
    the fallback single-feature coalition is astronomically unlikely).
    """
    for _ in range(64):
        var row = List[Int](capacity=m)
        var k = 0
        for _ in range(m):
            var bit = _rand_bit(state)
            row.append(bit)
            k += bit
        if k > 0 and k < m:
            return row^
    var fallback = List[Int](capacity=m)
    for _ in range(m):
        fallback.append(0)
    fallback[_rand_below(state, m)] = 1
    return fallback^


def shapley_sampling_weights(
    n_features: Int, n_samples: Int, seed: Int
) -> ShapleySamples:
    """Seeded coalition sample matrix + KernelSHAP weights.

    Draws n_samples coalitions z in {0,1}^n_features uniformly over the
    non-degenerate coalitions (never all-zero, never all-one) and attaches
    pi(z) = kernel_shap_weight(n_features, |z|) to each row. coalitions is
    flat row-major: entry for sample s, feature f at s * n_features + f.

    To recover SHAP values, the caller evaluates its model on each masked
    input (feature f real when coalitions[s, f] == 1, background otherwise),
    forms y[s] = f(masked_s) - f(background), scales row s of the coalition
    matrix and y[s] by sqrt(weights[s]), and solves with
    ensembles.stack_fit_ridge (l2 = 0 or tiny). Deterministic for a given
    seed. Returns an empty struct (n_samples == 0) when n_features < 2 —
    no valid coalitions exist — or n_samples <= 0.
    """
    var out = ShapleySamples()
    if n_features < 2 or n_samples <= 0:
        return out^
    out.n_samples = n_samples
    out.n_features = n_features
    var state = _seed_state(seed)
    for _ in range(n_samples):
        var row = _sample_coalition(state, n_features)
        var k = 0
        for f in range(n_features):
            out.coalitions.append(row[f])
            k += row[f]
        out.weights.append(kernel_shap_weight(n_features, k))
    return out^
