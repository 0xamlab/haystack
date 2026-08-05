"""
regression_tree.mojo — Regression tree (CART). Zero Python imports.

Replaces sklearn.tree.DecisionTreeRegressor with pure Mojo implementation
using flat-array tree storage and recursive binary splitting on MSE.

Public API:
  RegressionTree      — Flat-array tree struct
  build_tree          — Build regression tree via recursive MSE splitting
  predict_single      — Predict for one sample
  predict_batch       — Predict for multiple samples
  mse_reduction       — MSE reduction from a split
  best_split          — Find best feature/value for splitting
  tree_depth          — Maximum depth of tree
  tree_n_leaves       — Count leaf nodes
  tree_mse            — MSE on a dataset
"""
from std.math import sqrt, abs as fabs, isinf, isnan


# ── RegressionTree ────────────────────────────────────────────────────────────


@fieldwise_init
struct RegressionTree(Copyable, Movable):
    """Regression tree stored as flat arrays.

    For internal nodes: split_feature[i] >= 0, left_child/right_child valid.
    For leaf nodes: split_feature[i] == -1, leaf_value[i] holds prediction.
    """

    var split_feature: List[Int]
    var split_value: List[Float64]
    var left_child: List[Int]
    var right_child: List[Int]
    var leaf_value: List[Float64]
    var n_nodes: Int

    fn __init__(out self):
        self.split_feature = List[Int]()
        self.split_value = List[Float64]()
        self.left_child = List[Int]()
        self.right_child = List[Int]()
        self.leaf_value = List[Float64]()
        self.n_nodes = 0


# ── helpers ───────────────────────────────────────────────────────────────────


fn _mean_of(y: List[Float64], indices: List[Int]) -> Float64:
    """Mean of y at given indices."""
    var n = len(indices)
    if n == 0:
        return 0.0
    var s: Float64 = 0.0
    for i in range(n):
        s += y[indices[i]]
    return s / Float64(n)


fn _mse_of(y: List[Float64], indices: List[Int]) -> Float64:
    """MSE (variance) of y at given indices."""
    var n = len(indices)
    if n == 0:
        return 0.0
    var m = _mean_of(y, indices)
    var s: Float64 = 0.0
    for i in range(n):
        var d = y[indices[i]] - m
        s += d * d
    return s / Float64(n)


# ── mse_reduction ─────────────────────────────────────────────────────────────


fn mse_reduction(
    y: List[Float64], left_idx: List[Int], right_idx: List[Int]
) -> Float64:
    """MSE reduction from a split.

    reduction = MSE_parent - (n_L/n * MSE_L + n_R/n * MSE_R)
    """
    var n_l = len(left_idx)
    var n_r = len(right_idx)
    var n = n_l + n_r
    if n == 0:
        return 0.0
    # An out-of-range index would read past the end of y below (uncatchable
    # abort), and a non-finite y value would poison the result.
    var ny = len(y)
    for i in range(n_l):
        if left_idx[i] < 0 or left_idx[i] >= ny:
            return 0.0
        if isnan(y[left_idx[i]]) or isinf(y[left_idx[i]]):
            return 0.0
    for i in range(n_r):
        if right_idx[i] < 0 or right_idx[i] >= ny:
            return 0.0
        if isnan(y[right_idx[i]]) or isinf(y[right_idx[i]]):
            return 0.0
    # Build combined indices
    var all_idx = List[Int]()
    for i in range(n_l):
        all_idx.append(left_idx[i])
    for i in range(n_r):
        all_idx.append(right_idx[i])
    var mse_parent = _mse_of(y, all_idx)
    var mse_left = _mse_of(y, left_idx)
    var mse_right = _mse_of(y, right_idx)
    var weighted = (Float64(n_l) * mse_left + Float64(n_r) * mse_right) / Float64(n)
    return mse_parent - weighted


# ── best_split ────────────────────────────────────────────────────────────────


fn best_split(
    X: List[List[Float64]], y: List[Float64], indices: List[Int]
) -> List[Float64]:
    """Find best feature and split value for given indices.

    Returns [feature_idx, split_value, mse_reduction].
    Tries all features and all midpoints between sorted unique values.
    """
    var n = len(indices)
    var result = List[Float64]()
    result.append(-1.0)  # feature
    result.append(0.0)   # value
    result.append(0.0)   # reduction
    if n < 2:
        return result^
    # An empty/ragged X, mismatched y, or out-of-range index would be read
    # past its end below (uncatchable abort); a non-finite y would poison
    # the result. Refuse with the no-split sentinel.
    if len(X) == 0 or len(X) != len(y):
        return result^
    var n_features = len(X[0])
    for i in range(n):
        var r = indices[i]
        if r < 0 or r >= len(X) or len(X[r]) < n_features:
            return result^
        if isnan(y[r]) or isinf(y[r]):
            return result^
    var best_red: Float64 = 0.0
    var best_feat: Int = -1
    var best_val: Float64 = 0.0
    for f in range(n_features):
        # Collect feature values and sort indices by feature
        var vals = List[Float64]()
        for i in range(n):
            vals.append(X[indices[i]][f])
        # Sort vals and corresponding index positions (insertion sort)
        var sorted_idx = List[Int]()
        for i in range(n):
            sorted_idx.append(i)
        for i in range(1, n):
            var kv = vals[i]
            var ki = sorted_idx[i]
            var j = i - 1
            while j >= 0 and vals[j] > kv:
                vals[j + 1] = vals[j]
                sorted_idx[j + 1] = sorted_idx[j]
                j -= 1
            vals[j + 1] = kv
            sorted_idx[j + 1] = ki
        # Try splits between consecutive distinct values
        for s in range(1, n):
            if fabs(vals[s] - vals[s - 1]) < 1e-15:
                continue
            var split_val = (vals[s - 1] + vals[s]) / 2.0
            var left = List[Int]()
            var right = List[Int]()
            for i in range(s):
                left.append(indices[sorted_idx[i]])
            for i in range(s, n):
                right.append(indices[sorted_idx[i]])
            var red = mse_reduction(y, left, right)
            if red > best_red:
                best_red = red
                best_feat = f
                best_val = split_val
    result[0] = Float64(best_feat)
    result[1] = best_val
    result[2] = best_red
    return result^


# ── _add_node ─────────────────────────────────────────────────────────────────


fn _add_node(
    mut tree: RegressionTree,
    feat: Int,
    val: Float64,
    left: Int,
    right: Int,
    leaf_val: Float64,
) -> Int:
    """Add a node to the tree, return its index."""
    var idx = tree.n_nodes
    tree.split_feature.append(feat)
    tree.split_value.append(val)
    tree.left_child.append(left)
    tree.right_child.append(right)
    tree.leaf_value.append(leaf_val)
    tree.n_nodes += 1
    return idx


# ── _build_recursive ──────────────────────────────────────────────────────────


fn _build_recursive(
    mut tree: RegressionTree,
    X: List[List[Float64]],
    y: List[Float64],
    indices: List[Int],
    depth: Int,
    max_depth: Int,
    min_samples: Int,
) -> Int:
    """Recursively build tree, return node index."""
    var n = len(indices)
    var mean_val = _mean_of(y, indices)
    # Leaf conditions
    if n < min_samples or depth >= max_depth:
        return _add_node(tree, -1, 0.0, -1, -1, mean_val)
    # Check if all y values are the same
    var all_same = True
    var y0 = y[indices[0]]
    for i in range(1, n):
        if fabs(y[indices[i]] - y0) > 1e-15:
            all_same = False
            break
    if all_same:
        return _add_node(tree, -1, 0.0, -1, -1, mean_val)
    var split_info = best_split(X, y, indices)
    var feat = Int(split_info[0])
    var val = split_info[1]
    var red = split_info[2]
    if feat < 0 or red < 1e-15:
        return _add_node(tree, -1, 0.0, -1, -1, mean_val)
    # Partition indices
    var left_idx = List[Int]()
    var right_idx = List[Int]()
    for i in range(n):
        if X[indices[i]][feat] <= val:
            left_idx.append(indices[i])
        else:
            right_idx.append(indices[i])
    if len(left_idx) == 0 or len(right_idx) == 0:
        return _add_node(tree, -1, 0.0, -1, -1, mean_val)
    # Reserve node slot
    var node_idx = _add_node(tree, feat, val, -1, -1, mean_val)
    var left_node = _build_recursive(
        tree, X, y, left_idx, depth + 1, max_depth, min_samples
    )
    var right_node = _build_recursive(
        tree, X, y, right_idx, depth + 1, max_depth, min_samples
    )
    tree.left_child[node_idx] = left_node
    tree.right_child[node_idx] = right_node
    return node_idx


# ── build_tree ────────────────────────────────────────────────────────────────


fn build_tree(
    X: List[List[Float64]],
    y: List[Float64],
    max_depth: Int = 5,
    min_samples: Int = 2,
) -> RegressionTree:
    """Build regression tree using recursive binary splitting on MSE."""
    var tree = RegressionTree()
    var n = len(y)
    if n == 0:
        _ = _add_node(tree, -1, 0.0, -1, -1, 0.0)
        return tree^
    # Mismatched/ragged/non-finite payloads would be read past their end
    # below (uncatchable abort); refuse with the empty-data sentinel, and
    # cap the untrusted depth so it cannot drive unbounded recursion.
    if len(X) != n or min_samples < 0:
        _ = _add_node(tree, -1, 0.0, -1, -1, 0.0)
        return tree^
    var n_features = len(X[0])
    for i in range(n):
        if len(X[i]) < n_features or isnan(y[i]) or isinf(y[i]):
            _ = _add_node(tree, -1, 0.0, -1, -1, 0.0)
            return tree^
    var depth_cap = max_depth
    if depth_cap > 64:
        depth_cap = 64
    var indices = List[Int]()
    for i in range(n):
        indices.append(i)
    _ = _build_recursive(tree, X, y, indices, 0, depth_cap, min_samples)
    return tree^


# ── predict_single ────────────────────────────────────────────────────────────


fn predict_single(tree: RegressionTree, x: List[Float64]) -> Float64:
    """Predict for one sample by traversing tree from root (node 0)."""
    var node: Int = 0
    while node >= 0 and node < tree.n_nodes:
        if tree.split_feature[node] == -1:
            return tree.leaf_value[node]
        var feat = tree.split_feature[node]
        # feat comes from a caller-built tree; an index outside x aborts the worker.
        if feat < 0 or feat >= len(x):
            return 0.0
        if x[feat] <= tree.split_value[node]:
            node = tree.left_child[node]
        else:
            node = tree.right_child[node]
    return 0.0


# ── predict_batch ─────────────────────────────────────────────────────────────


fn predict_batch(
    tree: RegressionTree, X: List[List[Float64]]
) -> List[Float64]:
    """Predict for multiple samples."""
    var out = List[Float64]()
    for i in range(len(X)):
        out.append(predict_single(tree, X[i]))
    return out^


# ── tree_depth ────────────────────────────────────────────────────────────────


fn _node_depth(tree: RegressionTree, node: Int) -> Int:
    """Recursive depth of subtree rooted at node."""
    if node < 0 or node >= tree.n_nodes:
        return 0
    if tree.split_feature[node] == -1:
        return 1
    var ld = _node_depth(tree, tree.left_child[node])
    var rd = _node_depth(tree, tree.right_child[node])
    if ld > rd:
        return 1 + ld
    return 1 + rd


fn tree_depth(tree: RegressionTree) -> Int:
    """Maximum depth of tree (root = depth 1)."""
    if tree.n_nodes == 0:
        return 0
    return _node_depth(tree, 0)


# ── tree_n_leaves ─────────────────────────────────────────────────────────────


fn tree_n_leaves(tree: RegressionTree) -> Int:
    """Count leaf nodes."""
    var count: Int = 0
    for i in range(tree.n_nodes):
        if tree.split_feature[i] == -1:
            count += 1
    return count


# ── tree_mse ──────────────────────────────────────────────────────────────────


fn tree_mse(
    tree: RegressionTree, X: List[List[Float64]], y: List[Float64]
) -> Float64:
    """MSE of tree predictions on a dataset."""
    var n = len(y)
    if n == 0:
        return 0.0
    # Fewer rows than labels would be read past their end below (uncatchable
    # abort), and a non-finite y would poison the result.
    if len(X) < n:
        return 0.0
    for i in range(n):
        if isnan(y[i]) or isinf(y[i]):
            return 0.0
    var preds = predict_batch(tree, X)
    var total: Float64 = 0.0
    for i in range(n):
        var d = preds[i] - y[i]
        total += d * d
    return total / Float64(n)
