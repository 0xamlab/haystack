"""
imbalance.mojo — Imbalanced-data resampling tools. Zero Python imports.

Replaces imbalanced-learn (SMOTE, RandomOverSampler, RandomUnderSampler)
and sklearn.utils.class_weight.compute_class_weight("balanced") for
classification datasets where one class dominates: synthetic minority
oversampling by interpolation between nearest minority neighbors, seeded
random over/under-sampling to the majority/minority count, and
inverse-frequency class weights.

Public API:
  smote_1d                   — SMOTE for 1 feature: synthetic minority values
  smote_nd                   — SMOTE for d features (row-major flat X)
  random_oversample_indices  — indices resampled so every class hits max count
  random_undersample_indices — indices downsampled so every class hits min count
  class_weights              — balanced weights per class: n / (k * count_c)
"""


# ── ClassWeights ─────────────────────────────────────────────────────────────


struct ClassWeights(Copyable, Movable):
    """Per-class balanced weights. classes[i] (first-appearance order) has
    weight weights[i] = n / (n_classes * count_i), so that
    sum_c count_c * weight_c == n (sample-weight mass is preserved)."""
    var classes: List[Int]
    var weights: List[Float64]

    fn __init__(out self):
        self.classes = List[Int]()
        self.weights = List[Float64]()


# ── seeded RNG helpers (deterministic xorshift64) ────────────────────────────


fn _xorshift64(state: UInt64) -> UInt64:
    var s = state
    s ^= s << 13
    s ^= s >> 7
    s ^= s << 17
    return s


fn _seed_state(seed: Int) -> UInt64:
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


fn _rand_below(mut state: UInt64, bound: Int) -> Int:
    """Uniform-ish integer in [0, bound). bound must be >= 1."""
    state = _xorshift64(state)
    return Int(state % UInt64(bound))


fn _rand_unit(mut state: UInt64) -> Float64:
    """Uniform Float64 in [0, 1) from the top 53 bits of the state."""
    state = _xorshift64(state)
    return Float64(state >> 11) / 9007199254740992.0  # 2^53


# ── class bookkeeping helpers ────────────────────────────────────────────────


fn _distinct_classes(labels: List[Int]) -> List[Int]:
    """Distinct label values in order of first appearance."""
    var classes = List[Int]()
    for i in range(len(labels)):
        var found = False
        for c in range(len(classes)):
            if classes[c] == labels[i]:
                found = True
                break
        if not found:
            classes.append(labels[i])
    return classes^


fn _class_index_lists(
    labels: List[Int], classes: List[Int]
) -> List[List[Int]]:
    """For each class (in `classes` order) the ascending sample indices."""
    var buckets = List[List[Int]]()
    for c in range(len(classes)):
        var idxs = List[Int]()
        for i in range(len(labels)):
            if labels[i] == classes[c]:
                idxs.append(i)
        buckets.append(idxs^)
    return buckets^


# ── k-nearest minority neighbors ─────────────────────────────────────────────


fn _k_nearest_positions(
    X: List[Float64],
    n_features: Int,
    min_idx: List[Int],
    base_pos: Int,
    k: Int,
) -> List[Int]:
    """Positions (into min_idx) of the k nearest minority neighbors of
    min_idx[base_pos] by squared Euclidean distance, excluding itself.
    Result is sorted by ascending distance; ties break toward the lower
    scan position (deterministic). Caller guarantees 1 <= k < len(min_idx).
    """
    var n_min = len(min_idx)
    var base_off = min_idx[base_pos] * n_features
    var best_d = List[Float64]()
    var best_pos = List[Int]()
    for p in range(n_min):
        if p == base_pos:
            continue
        var off = min_idx[p] * n_features
        var d = 0.0
        for f in range(n_features):
            var diff = X[off + f] - X[base_off + f]
            d += diff * diff
        var m = len(best_d)
        if m < k:
            best_d.append(0.0)
            best_pos.append(0)
            var j = m
            while j > 0 and best_d[j - 1] > d:
                best_d[j] = best_d[j - 1]
                best_pos[j] = best_pos[j - 1]
                j -= 1
            best_d[j] = d
            best_pos[j] = p
        elif d < best_d[k - 1]:
            var j = k - 1
            while j > 0 and best_d[j - 1] > d:
                best_d[j] = best_d[j - 1]
                best_pos[j] = best_pos[j - 1]
                j -= 1
            best_d[j] = d
            best_pos[j] = p
    return best_pos^


# ── smote_nd ─────────────────────────────────────────────────────────────────


fn smote_nd(
    X: List[Float64],
    n_features: Int,
    labels: List[Int],
    minority_label: Int,
    k_neighbors: Int,
    n_synthetic: Int,
    seed: Int,
) -> List[Float64]:
    """SMOTE: synthetic minority rows by neighbor interpolation.

    X is row-major flat (len == len(labels) * n_features). Each of the
    n_synthetic output rows is built by picking a random minority row b,
    one of its k nearest minority neighbors nb (k clamped to
    min(k_neighbors, n_minority - 1)), and gap ~ U[0, 1):
        row = x_b + gap * (x_nb - x_b)
    so every synthetic row lies on the segment between two minority rows.
    Deterministic for a given seed. Returns a flat list of
    n_synthetic * n_features values; returns empty when the config is
    infeasible (fewer than 2 minority rows, k_neighbors < 1,
    n_synthetic < 1, n_features < 1, or mis-sized X).

    Cost note: nearest neighbors are computed lazily once per distinct
    base row and cached, so worst case is
    O(min(n_synthetic, n_min) * n_min * n_features). With a 10k-row
    minority class this exceeds 1ms; acceptable because SMOTE is offline
    training-data prep (never in the live decision loop) and minority
    classes are small by definition — for typical n_min <= ~1k it is
    sub-millisecond.
    """
    var out = List[Float64]()
    if n_features <= 0 or n_synthetic <= 0 or k_neighbors <= 0:
        return out^
    var n = len(labels)
    if n <= 0 or len(X) != n * n_features:
        return out^

    var min_idx = List[Int]()
    for i in range(n):
        if labels[i] == minority_label:
            min_idx.append(i)
    var n_min = len(min_idx)
    if n_min < 2:
        return out^

    var k = k_neighbors
    if k > n_min - 1:
        k = n_min - 1

    # Lazy per-base neighbor cache (empty list == not yet computed; a
    # computed entry always holds exactly k >= 1 positions).
    var cache = List[List[Int]]()
    for _ in range(n_min):
        cache.append(List[Int]())

    var rng = _seed_state(seed)
    for _ in range(n_synthetic):
        var b = _rand_below(rng, n_min)
        if len(cache[b]) == 0:
            cache[b] = _k_nearest_positions(X, n_features, min_idx, b, k)
        var nb = cache[b][_rand_below(rng, k)]
        var gap = _rand_unit(rng)
        var boff = min_idx[b] * n_features
        var noff = min_idx[nb] * n_features
        for f in range(n_features):
            var xb = X[boff + f]
            out.append(xb + gap * (X[noff + f] - xb))
    return out^


# ── smote_1d ─────────────────────────────────────────────────────────────────


fn smote_1d(
    x: List[Float64],
    labels: List[Int],
    minority_label: Int,
    k_neighbors: Int,
    n_synthetic: Int,
    seed: Int,
) -> List[Float64]:
    """SMOTE for a single feature: smote_nd with n_features=1.

    Returns n_synthetic synthetic minority values, each on the segment
    (interval) between a minority value and one of its k nearest minority
    neighbors. Empty on infeasible config (see smote_nd).
    """
    return smote_nd(
        x, 1, labels, minority_label, k_neighbors, n_synthetic, seed
    )


# ── random_oversample_indices ────────────────────────────────────────────────


fn random_oversample_indices(labels: List[Int], seed: Int) -> List[Int]:
    """Seeded random oversampling to the majority count.

    Returns sample indices such that every class ends with max class
    count entries: first the original indices 0..n-1 in order, then for
    each deficient class (first-appearance order) its deficit filled by
    sampling that class's indices uniformly with replacement.
    Deterministic for a given seed. Empty labels -> empty; already
    balanced labels -> identity [0, n).
    """
    var out = List[Int]()
    var n = len(labels)
    if n == 0:
        return out^
    var classes = _distinct_classes(labels)
    var buckets = _class_index_lists(labels, classes)

    var max_count = 0
    for c in range(len(buckets)):
        if len(buckets[c]) > max_count:
            max_count = len(buckets[c])

    for i in range(n):
        out.append(i)
    var rng = _seed_state(seed)
    for c in range(len(buckets)):
        var count = len(buckets[c])
        for _ in range(max_count - count):
            out.append(buckets[c][_rand_below(rng, count)])
    return out^


# ── random_undersample_indices ───────────────────────────────────────────────


fn random_undersample_indices(labels: List[Int], seed: Int) -> List[Int]:
    """Seeded random undersampling to the minority count.

    Keeps min class count samples per class, chosen uniformly without
    replacement (partial Fisher-Yates per class), and returns the kept
    indices in ascending order. Deterministic for a given seed. Empty
    labels -> empty; already balanced labels -> identity [0, n).
    """
    var out = List[Int]()
    var n = len(labels)
    if n == 0:
        return out^
    var classes = _distinct_classes(labels)
    var buckets = _class_index_lists(labels, classes)

    var min_count = n
    for c in range(len(buckets)):
        if len(buckets[c]) < min_count:
            min_count = len(buckets[c])

    var keep = List[Bool](capacity=n)
    for _ in range(n):
        keep.append(False)
    var rng = _seed_state(seed)
    for c in range(len(buckets)):
        var idxs = buckets[c].copy()
        var m = len(idxs)
        # Partial Fisher-Yates: fix positions [0, min_count).
        for i in range(min_count):
            var j = i + _rand_below(rng, m - i)
            var tmp = idxs[i]
            idxs[i] = idxs[j]
            idxs[j] = tmp
            keep[idxs[i]] = True
    for i in range(n):
        if keep[i]:
            out.append(i)
    return out^


# ── class_weights ────────────────────────────────────────────────────────────


fn class_weights(labels: List[Int]) -> ClassWeights:
    """Balanced inverse-frequency class weights (sklearn 'balanced').

    For each distinct class c (first-appearance order):
        weight_c = n / (n_classes * count_c)
    Normalization property: sum_c count_c * weight_c == n, i.e. total
    sample-weight mass equals the sample count, and a perfectly balanced
    dataset gets weight 1.0 for every class. Empty labels -> empty result.
    """
    var out = ClassWeights()
    var n = len(labels)
    if n == 0:
        return out^
    var classes = _distinct_classes(labels)
    var k = len(classes)
    for c in range(k):
        var count = 0
        for i in range(n):
            if labels[i] == classes[c]:
                count += 1
        out.classes.append(classes[c])
        out.weights.append(Float64(n) / (Float64(k) * Float64(count)))
    return out^
