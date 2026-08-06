"""
gbdt.mojo — Gradient-boosted regression trees (squared loss). Zero Python imports.

Replaces xgboost.XGBRegressor / lightgbm.LGBMRegressor /
sklearn.ensemble.GradientBoostingRegressor for tabular regression:
depth-limited greedy variance-reduction splits, residual fitting,
shrinkage (learning rate), and seeded row subsampling. Complements
regression_tree.mojo (single CART on nested lists) with a flat
row-major feature matrix and a prefix-sum split search over feature
columns presorted once per fit (per-node O(m log m) re-sort only as a
bit-exactness fallback for columns with tied values or tiny nodes).

Model layout: one GBDTModel struct holding the whole forest as flat
parallel lists (split_feature / split_value / left_child / right_child /
leaf_value) with absolute node indices; tree_root[t] is tree t's root.
Leaf values are stored with the learning rate already applied, so
prediction is base_score + sum of one leaf per tree.

Public API:
  GBDTModel           — flattened forest model (parallel node lists)
  gbdt_fit            — fit boosted trees on flat X (rows*cols), squared loss
  gbdt_predict        — predict one feature row
  gbdt_predict_batch  — predict every row of a flat matrix
  gbdt_n_nodes        — total node count across the forest
"""
from std.math import abs as fabs


# ── GBDTModel ────────────────────────────────────────────────────────────────


@fieldwise_init
struct GBDTModel(Copyable, Movable):
    """Boosted forest stored as flat parallel arrays.

    Internal nodes: split_feature[i] >= 0, children are absolute indices.
    Leaf nodes: split_feature[i] == -1, leaf_value[i] is the (already
    shrinkage-scaled) contribution. tree_root[t] indexes tree t's root.
    """

    var n_features: Int
    var base_score: Float64
    var tree_root: List[Int]
    var split_feature: List[Int]
    var split_value: List[Float64]
    var left_child: List[Int]
    var right_child: List[Int]
    var leaf_value: List[Float64]

    def __init__(out self):
        self.n_features = 0
        self.base_score = 0.0
        self.tree_root = List[Int]()
        self.split_feature = List[Int]()
        self.split_value = List[Float64]()
        self.left_child = List[Int]()
        self.right_child = List[Int]()
        self.leaf_value = List[Float64]()


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


def _shuffle_ints(mut arr: List[Int], mut state: UInt64):
    """In-place Fisher-Yates shuffle driven by the caller's RNG state."""
    var n = len(arr)
    for i in range(n - 1, 0, -1):
        var j = _rand_below(state, i + 1)
        var tmp = arr[i]
        arr[i] = arr[j]
        arr[j] = tmp


# ── sorting helper (heapsort on parallel arrays) ─────────────────────────────


def _sift_down(
    mut keys: List[Float64], mut vals: List[Float64], start: Int, end: Int
):
    """Max-heap sift-down over keys[start..end], vals moved in lockstep."""
    var root = start
    while True:
        var child = 2 * root + 1
        if child > end:
            return
        if child + 1 <= end and keys[child] < keys[child + 1]:
            child += 1
        if keys[root] < keys[child]:
            var tk = keys[root]
            keys[root] = keys[child]
            keys[child] = tk
            var tv = vals[root]
            vals[root] = vals[child]
            vals[child] = tv
            root = child
        else:
            return


def _heapsort_pair(mut keys: List[Float64], mut vals: List[Float64]):
    """Sort keys ascending, permuting vals identically. O(m log m), no
    recursion. Not stable, but split gains only depend on sums within
    equal-key blocks, so results stay deterministic."""
    var n = len(keys)
    if n < 2:
        return
    var start = n // 2 - 1
    while start >= 0:
        _sift_down(keys, vals, start, n - 1)
        start -= 1
    var end = n - 1
    while end > 0:
        var tk = keys[0]
        keys[0] = keys[end]
        keys[end] = tk
        var tv = vals[0]
        vals[0] = vals[end]
        vals[end] = tv
        end -= 1
        _sift_down(keys, vals, 0, end)


def _sift_down_key_idx(
    mut keys: List[Float64], mut vals: List[Int], start: Int, end: Int
):
    """Max-heap sift-down over keys[start..end], Int payload in lockstep."""
    var root = start
    while True:
        var child = 2 * root + 1
        if child > end:
            return
        if child + 1 <= end and keys[child] < keys[child + 1]:
            child += 1
        if keys[root] < keys[child]:
            var tk = keys[root]
            keys[root] = keys[child]
            keys[child] = tk
            var tv = vals[root]
            vals[root] = vals[child]
            vals[child] = tv
            root = child
        else:
            return


def _heapsort_key_idx(mut keys: List[Float64], mut vals: List[Int]):
    """Sort keys ascending, permuting the Int payload identically."""
    var n = len(keys)
    if n < 2:
        return
    var start = n // 2 - 1
    while start >= 0:
        _sift_down_key_idx(keys, vals, start, n - 1)
        start -= 1
    var end = n - 1
    while end > 0:
        var tk = keys[0]
        keys[0] = keys[end]
        keys[end] = tk
        var tv = vals[0]
        vals[0] = vals[end]
        vals[end] = tv
        end -= 1
        _sift_down_key_idx(keys, vals, 0, end)


# ── global column presort (shared across every node of every tree) ──────────


@fieldwise_init
struct _SplitCtx(Copyable, Movable):
    """Per-fit presorted feature order reused by every node's split search.

    order is column-major: order[f * n_rows + r] is the row index holding
    the r-th smallest value of feature f. col_fallback[f] marks columns
    whose sorted values are not strictly increasing (exact ties, NaN):
    those keep the per-node heapsort, because heapsort's tie permutation
    feeds the float prefix-sum order and results must stay bit-identical.
    mask holds a per-node stamp so membership tests need no clearing.
    """

    var n_rows: Int
    var order: List[Int]
    var col_fallback: List[Bool]
    var mask: List[Int]
    var stamp: Int


def _presort_columns(X: List[Float64], n_rows: Int, n_cols: Int) -> _SplitCtx:
    """Sort each feature column once; flag columns needing the fallback."""
    var order = List[Int](capacity=n_rows * n_cols)
    var col_fallback = List[Bool](capacity=n_cols)
    for f in range(n_cols):
        var keys = List[Float64](capacity=n_rows)
        var idx = List[Int](capacity=n_rows)
        for r in range(n_rows):
            keys.append(X[r * n_cols + f])
            idx.append(r)
        _heapsort_key_idx(keys, idx)
        var fallback = False
        for r in range(1, n_rows):
            if not (keys[r - 1] < keys[r]):
                fallback = True
                break
        col_fallback.append(fallback)
        for r in range(n_rows):
            order.append(idx[r])
    var mask = List[Int](capacity=n_rows)
    for _ in range(n_rows):
        mask.append(0)
    return _SplitCtx(n_rows, order^, col_fallback^, mask^, 0)


# ── split search ─────────────────────────────────────────────────────────────


@fieldwise_init
struct _Split(Copyable, Movable):
    """Best split for one node: feature == -1 means no valid split."""
    var feature: Int
    var value: Float64
    var gain: Float64


def _best_split(
    X: List[Float64],
    n_cols: Int,
    resid: List[Float64],
    idxs: List[Int],
    min_leaf: Int,
    mut ctx: _SplitCtx,
) -> _Split:
    """Greedy variance-reduction split over all features.

    For each feature the node's rows are visited in ascending value
    order; a prefix-sum scan scores every boundary between distinct
    values with
      gain = S_L^2/n_L + S_R^2/n_R - S^2/m   (SSE reduction, >= 0),
    honoring min_leaf on both sides. Ties keep the first (lowest feature
    index, lowest threshold) for determinism.

    The ascending order comes from the fit-wide presort in ctx: the
    node's rows are stamped into ctx.mask and the global column order is
    walked once, O(n_rows) per feature with no per-node sort. Columns
    flagged in col_fallback — and nodes small enough that re-sorting m
    rows is cheaper than walking n_rows — use the original per-node
    heapsort path instead; on strictly-increasing columns both paths
    visit identical (value, residual) sequences, so gains, thresholds,
    and tie-breaks are bit-identical either way.
    """
    var m = len(idxs)
    var out = _Split(-1, 0.0, 0.0)
    if m < 2 or m < 2 * min_leaf:
        return out^
    var total: Float64 = 0.0
    for i in range(m):
        total += resid[idxs[i]]
    var parent_score = total * total / Float64(m)
    # Presorted walk costs ~n_rows per feature; the per-node heapsort
    # costs ~m log2(m) heavier steps. Pick the walk only when it wins.
    var lg = 0
    var v = m
    while v > 1:
        v >>= 1
        lg += 1
    var use_walk = 2 * m * lg >= ctx.n_rows
    if use_walk:
        ctx.stamp += 1
        for i in range(m):
            ctx.mask[idxs[i]] = ctx.stamp
    for f in range(n_cols):
        if use_walk and not ctx.col_fallback[f]:
            var base = f * ctx.n_rows
            var left_sum: Float64 = 0.0
            var prev_key: Float64 = 0.0
            var prev_val: Float64 = 0.0
            var cnt = 0
            for r in range(ctx.n_rows):
                var row = ctx.order[base + r]
                if ctx.mask[row] != ctx.stamp:
                    continue
                var key = X[row * n_cols + f]
                if cnt >= 1:
                    left_sum += prev_val
                    if cnt >= min_leaf and m - cnt >= min_leaf:
                        if not (fabs(key - prev_key) < 1e-15):
                            var right_sum = total - left_sum
                            var gain = (
                                left_sum * left_sum / Float64(cnt)
                                + right_sum * right_sum / Float64(m - cnt)
                                - parent_score
                            )
                            if gain > out.gain:
                                out.gain = gain
                                out.feature = f
                                out.value = (prev_key + key) / 2.0
                prev_key = key
                prev_val = resid[row]
                cnt += 1
                if cnt == m:
                    break
        else:
            var keys = List[Float64](capacity=m)
            var vals = List[Float64](capacity=m)
            for i in range(m):
                keys.append(X[idxs[i] * n_cols + f])
                vals.append(resid[idxs[i]])
            _heapsort_pair(keys, vals)
            var left_sum: Float64 = 0.0
            for s in range(1, m):
                left_sum += vals[s - 1]
                if s < min_leaf or m - s < min_leaf:
                    continue
                if fabs(keys[s] - keys[s - 1]) < 1e-15:
                    continue
                var right_sum = total - left_sum
                var gain = (
                    left_sum * left_sum / Float64(s)
                    + right_sum * right_sum / Float64(m - s)
                    - parent_score
                )
                if gain > out.gain:
                    out.gain = gain
                    out.feature = f
                    out.value = (keys[s - 1] + keys[s]) / 2.0
    return out^


# ── tree construction ────────────────────────────────────────────────────────


def _add_node(
    mut model: GBDTModel,
    feat: Int,
    val: Float64,
    left: Int,
    right: Int,
    leaf_val: Float64,
) -> Int:
    """Append a node to the flat forest, return its absolute index."""
    var idx = len(model.split_feature)
    model.split_feature.append(feat)
    model.split_value.append(val)
    model.left_child.append(left)
    model.right_child.append(right)
    model.leaf_value.append(leaf_val)
    return idx


def _grow(
    mut model: GBDTModel,
    X: List[Float64],
    n_cols: Int,
    resid: List[Float64],
    idxs: List[Int],
    depth: Int,
    max_depth: Int,
    min_leaf: Int,
    lr: Float64,
    mut ctx: _SplitCtx,
) -> Int:
    """Recursively grow one regression tree on the residuals of the rows
    in idxs. Leaf values are the mean residual scaled by lr. Returns the
    absolute node index of the subtree root."""
    var m = len(idxs)
    var mean: Float64 = 0.0
    for i in range(m):
        mean += resid[idxs[i]]
    if m > 0:
        mean /= Float64(m)
    if depth >= max_depth or m < 2 or m < 2 * min_leaf:
        return _add_node(model, -1, 0.0, -1, -1, lr * mean)
    var sp = _best_split(X, n_cols, resid, idxs, min_leaf, ctx)
    if sp.feature < 0 or sp.gain <= 1e-12:
        return _add_node(model, -1, 0.0, -1, -1, lr * mean)
    var left_idx = List[Int]()
    var right_idx = List[Int]()
    for i in range(m):
        if X[idxs[i] * n_cols + sp.feature] <= sp.value:
            left_idx.append(idxs[i])
        else:
            right_idx.append(idxs[i])
    if len(left_idx) == 0 or len(right_idx) == 0:
        return _add_node(model, -1, 0.0, -1, -1, lr * mean)
    var node = _add_node(model, sp.feature, sp.value, -1, -1, lr * mean)
    var l = _grow(
        model,
        X,
        n_cols,
        resid,
        left_idx,
        depth + 1,
        max_depth,
        min_leaf,
        lr,
        ctx,
    )
    var r = _grow(
        model,
        X,
        n_cols,
        resid,
        right_idx,
        depth + 1,
        max_depth,
        min_leaf,
        lr,
        ctx,
    )
    model.left_child[node] = l
    model.right_child[node] = r
    return node


def _predict_row_flat(
    model: GBDTModel, root: Int, X: List[Float64], n_cols: Int, row: Int
) -> Float64:
    """Walk one tree for one row of a flat matrix; returns the leaf value."""
    var node = root
    while node >= 0 and node < len(model.split_feature):
        var f = model.split_feature[node]
        if f < 0:
            return model.leaf_value[node]
        if X[row * n_cols + f] <= model.split_value[node]:
            node = model.left_child[node]
        else:
            node = model.right_child[node]
    return 0.0


# ── gbdt_fit ─────────────────────────────────────────────────────────────────


def gbdt_fit(
    X: List[Float64],
    y: List[Float64],
    n_cols: Int,
    n_trees: Int,
    max_depth: Int,
    learning_rate: Float64,
    min_leaf: Int = 1,
    subsample: Float64 = 1.0,
    seed: Int = 0,
) -> GBDTModel:
    """Fit gradient-boosted regression trees with squared loss.

    X is row-major flat (len(y) rows * n_cols). Boosting: start from
    base_score = mean(y); each round fits a depth-limited CART to the
    current residuals (greedy variance-reduction splits, >= min_leaf
    samples per leaf) and adds learning_rate * leaf_mean to the running
    prediction (shrinkage is baked into stored leaf values). subsample
    in (0, 1) trains each tree on a seeded Fisher-Yates row sample
    without replacement (>= 1 row); residual updates always use all
    rows. Deterministic for a fixed seed. Degenerate configs (empty y,
    n_cols <= 0, short X, n_trees <= 0) return a base-score-only model.
    """
    var model = GBDTModel()
    var n = len(y)
    if n == 0:
        return model^
    var base: Float64 = 0.0
    for i in range(n):
        base += y[i]
    base /= Float64(n)
    model.base_score = base
    if n_cols <= 0 or len(X) < n * n_cols or n_trees <= 0:
        return model^
    model.n_features = n_cols

    var ml = min_leaf
    if ml < 1:
        ml = 1
    var k = n
    if subsample > 0.0 and subsample < 1.0:
        k = Int(Float64(n) * subsample)
        if k < 1:
            k = 1
        if k > n:
            k = n
    var rng = _seed_state(seed)
    var ctx = _presort_columns(X, n, n_cols)

    var pred = List[Float64](capacity=n)
    for _ in range(n):
        pred.append(base)
    var resid = List[Float64](capacity=n)
    for _ in range(n):
        resid.append(0.0)

    for _ in range(n_trees):
        for i in range(n):
            resid[i] = y[i] - pred[i]
        var idxs = List[Int](capacity=n)
        for i in range(n):
            idxs.append(i)
        if k < n:
            _shuffle_ints(idxs, rng)
            var sampled = List[Int](capacity=k)
            for i in range(k):
                sampled.append(idxs[i])
            idxs = sampled^
        var root = _grow(
            model,
            X,
            n_cols,
            resid,
            idxs,
            0,
            max_depth,
            ml,
            learning_rate,
            ctx,
        )
        model.tree_root.append(root)
        for i in range(n):
            pred[i] += _predict_row_flat(model, root, X, n_cols, i)
    return model^


# ── gbdt_predict ─────────────────────────────────────────────────────────────


def gbdt_predict(model: GBDTModel, x: List[Float64]) -> Float64:
    """Predict one row: base_score + one (lr-scaled) leaf per tree.
    O(n_trees * max_depth)."""
    var out = model.base_score
    for t in range(len(model.tree_root)):
        var node = model.tree_root[t]
        while node >= 0 and node < len(model.split_feature):
            var f = model.split_feature[node]
            if f < 0:
                out += model.leaf_value[node]
                break
            if f < len(x) and x[f] <= model.split_value[node]:
                node = model.left_child[node]
            else:
                node = model.right_child[node]
    return out


# ── gbdt_predict_batch ───────────────────────────────────────────────────────


def gbdt_predict_batch(
    model: GBDTModel, X: List[Float64], n_cols: Int
) -> List[Float64]:
    """Predict every row of a flat row-major matrix (len(X) // n_cols rows)."""
    var out = List[Float64]()
    if n_cols <= 0:
        return out^
    # Model fields arrive over the wire: the five node arrays must stay
    # parallel, and every non-leaf split feature must index the row, or the
    # tree walk reads out of bounds (an uncatchable abort).
    var n_nodes = len(model.split_feature)
    if len(model.split_value) < n_nodes or len(model.left_child) < n_nodes:
        return out^
    if len(model.right_child) < n_nodes or len(model.leaf_value) < n_nodes:
        return out^
    for i in range(n_nodes):
        if model.split_feature[i] >= n_cols:  # negative marks a leaf
            return out^
    var rows = len(X) // n_cols
    for r in range(rows):
        var v = model.base_score
        for t in range(len(model.tree_root)):
            var node = model.tree_root[t]
            while node >= 0 and node < len(model.split_feature):
                var f = model.split_feature[node]
                if f < 0:
                    v += model.leaf_value[node]
                    break
                if X[r * n_cols + f] <= model.split_value[node]:
                    node = model.left_child[node]
                else:
                    node = model.right_child[node]
        out.append(v)
    return out^


# ── gbdt_n_nodes ─────────────────────────────────────────────────────────────


def gbdt_n_nodes(model: GBDTModel) -> Int:
    """Total node count across all trees in the forest."""
    return len(model.split_feature)
