"""
multi_objective.mojo — Multi-objective optimization. Zero Python imports.
Pareto fronts, weighted scoring, TOPSIS, ideal/nadir points.

Public API:
  is_dominated         — True if b dominates a
  pareto_front         — indices of Pareto-optimal solutions
  weighted_score       — weighted sum of values
  normalize_objectives — min-max normalize each column
  ideal_point          — best value per objective
  nadir_point          — worst value per objective
  topsis_rank          — TOPSIS closeness scores
"""
from std.math import sqrt, abs as fabs


# ── Dominance Check ───────────────────────────────────────────────────────────


fn is_dominated(
    a: List[Float64], b: List[Float64], maximize: List[Bool]
) -> Bool:
    """Check if solution b dominates solution a.

    b dominates a if b is at least as good in ALL objectives
    and strictly better in AT LEAST ONE objective.

    Args:
        a:        Objective values of solution a.
        b:        Objective values of solution b.
        maximize: True if objective should be maximized, False for minimize.

    Returns:
        True if b dominates a.
    """
    var n = len(a)
    var m = len(b)
    var k = len(maximize)
    var count = n
    if m < count:
        count = m
    if k < count:
        count = k

    var at_least_as_good = True
    var strictly_better = False

    for i in range(count):
        if maximize[i]:
            # Maximizing: b[i] >= a[i] needed, b[i] > a[i] is strictly better
            if b[i] < a[i]:
                at_least_as_good = False
                break
            if b[i] > a[i]:
                strictly_better = True
        else:
            # Minimizing: b[i] <= a[i] needed, b[i] < a[i] is strictly better
            if b[i] > a[i]:
                at_least_as_good = False
                break
            if b[i] < a[i]:
                strictly_better = True

    return at_least_as_good and strictly_better


# ── Pareto Front ──────────────────────────────────────────────────────────────


fn pareto_front(
    objectives: List[List[Float64]], maximize: List[Bool]
) -> List[Int]:
    """Find indices of Pareto-optimal solutions using pairwise dominance.

    A solution is Pareto-optimal if no other solution dominates it.

    Args:
        objectives: List of solutions, each a List[Float64] of objective values.
        maximize:   True if objective should be maximized, False for minimize.

    Returns:
        List of indices of Pareto-optimal solutions.
    """
    var n = len(objectives)
    if n == 0:
        return List[Int]()

    # Track which solutions are dominated
    var dominated = List[Bool]()
    for i in range(n):
        dominated.append(False)

    # Pairwise dominance check
    for i in range(n):
        if dominated[i]:
            continue
        for j in range(n):
            if i == j or dominated[j]:
                continue
            # Check if j dominates i
            if is_dominated(objectives[i], objectives[j], maximize):
                dominated[i] = True
                break

    # Collect non-dominated indices
    var front = List[Int]()
    for i in range(n):
        if not dominated[i]:
            front.append(i)

    return front^


# ── Weighted Score ────────────────────────────────────────────────────────────


fn weighted_score(values: List[Float64], weights: List[Float64]) -> Float64:
    """Weighted sum: Σ values[i] * weights[i].

    Args:
        values:  Objective values.
        weights: Weights for each objective.

    Returns:
        Weighted sum score.
    """
    var n = len(values)
    var m = len(weights)
    var count = n if n < m else m
    var total: Float64 = 0.0
    for i in range(count):
        total += values[i] * weights[i]
    return total


# ── Normalize Objectives ──────────────────────────────────────────────────────


fn normalize_objectives(
    objectives: List[List[Float64]],
) -> List[List[Float64]]:
    """Min-max normalize each column (objective) to [0, 1].

    For each objective j: normalized[i][j] = (val - min_j) / (max_j - min_j).
    If max_j == min_j, all values become 0.0.

    Args:
        objectives: List of solutions, each a List[Float64] of objective values.

    Returns:
        Normalized objectives with same shape.
    """
    var n = len(objectives)
    if n == 0:
        return List[List[Float64]]()

    var n_obj = len(objectives[0])
    if n_obj == 0:
        return List[List[Float64]]()

    # Find min and max for each column
    var col_min = List[Float64]()
    var col_max = List[Float64]()
    for j in range(n_obj):
        col_min.append(objectives[0][j])
        col_max.append(objectives[0][j])

    for i in range(1, n):
        for j in range(n_obj):
            if j < len(objectives[i]):
                var v = objectives[i][j]
                if v < col_min[j]:
                    col_min[j] = v
                if v > col_max[j]:
                    col_max[j] = v

    # Normalize
    var result = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n_obj):
            if j < len(objectives[i]):
                var range_j = col_max[j] - col_min[j]
                if fabs(range_j) < 1e-15:
                    row.append(0.0)
                else:
                    row.append((objectives[i][j] - col_min[j]) / range_j)
            else:
                row.append(0.0)
        result.append(row^)

    return result^


# ── Ideal Point ───────────────────────────────────────────────────────────────


fn ideal_point(
    objectives: List[List[Float64]], maximize: List[Bool]
) -> List[Float64]:
    """Compute the ideal point (best value per objective).

    For maximize objectives, ideal = max. For minimize, ideal = min.

    Args:
        objectives: List of solutions, each a List[Float64] of objective values.
        maximize:   True if objective should be maximized.

    Returns:
        List of best values per objective.
    """
    var n = len(objectives)
    if n == 0:
        return List[Float64]()

    var n_obj = len(objectives[0])
    var ideal = List[Float64]()
    for j in range(n_obj):
        ideal.append(objectives[0][j])

    for i in range(1, n):
        for j in range(n_obj):
            if j < len(objectives[i]) and j < len(maximize):
                var v = objectives[i][j]
                if maximize[j]:
                    if v > ideal[j]:
                        ideal[j] = v
                else:
                    if v < ideal[j]:
                        ideal[j] = v

    return ideal^


# ── Nadir Point ───────────────────────────────────────────────────────────────


fn nadir_point(
    objectives: List[List[Float64]], maximize: List[Bool]
) -> List[Float64]:
    """Compute the nadir point (worst value per objective).

    For maximize objectives, nadir = min. For minimize, nadir = max.

    Args:
        objectives: List of solutions, each a List[Float64] of objective values.
        maximize:   True if objective should be maximized.

    Returns:
        List of worst values per objective.
    """
    var n = len(objectives)
    if n == 0:
        return List[Float64]()

    var n_obj = len(objectives[0])
    var nadir = List[Float64]()
    for j in range(n_obj):
        nadir.append(objectives[0][j])

    for i in range(1, n):
        for j in range(n_obj):
            if j < len(objectives[i]) and j < len(maximize):
                var v = objectives[i][j]
                if maximize[j]:
                    # Worst for maximize = min
                    if v < nadir[j]:
                        nadir[j] = v
                else:
                    # Worst for minimize = max
                    if v > nadir[j]:
                        nadir[j] = v

    return nadir^


# ── TOPSIS Rank ───────────────────────────────────────────────────────────────


fn topsis_rank(
    alternatives: List[List[Float64]],
    weights: List[Float64],
    maximize: List[Bool],
) -> List[Float64]:
    """TOPSIS (Technique for Order of Preference by Similarity to Ideal Solution).

    Steps:
    1. Normalize the decision matrix (vector normalization).
    2. Apply weights.
    3. Determine ideal and negative-ideal solutions.
    4. Calculate distances to ideal and negative-ideal.
    5. Compute closeness coefficient: C = D⁻ / (D⁺ + D⁻).

    Args:
        alternatives: List of alternatives, each a List[Float64] of criteria values.
        weights:      Weights for each criterion.
        maximize:     True if criterion should be maximized.

    Returns:
        List of closeness scores (0 to 1), higher is better.
    """
    var n = len(alternatives)
    if n == 0:
        return List[Float64]()

    var n_crit = len(alternatives[0])
    if n_crit == 0:
        var empty = List[Float64]()
        for i in range(n):
            empty.append(0.0)
        return empty^

    # Step 1: Vector normalization — compute column norms
    var col_norms = List[Float64]()
    for j in range(n_crit):
        var ss: Float64 = 0.0
        for i in range(n):
            if j < len(alternatives[i]):
                var v = alternatives[i][j]
                ss += v * v
        col_norms.append(sqrt(ss))

    # Build normalized weighted matrix
    var norm_w = List[List[Float64]]()
    for i in range(n):
        var row = List[Float64]()
        for j in range(n_crit):
            var v: Float64 = 0.0
            if j < len(alternatives[i]):
                v = alternatives[i][j]
            var norm_val: Float64 = 0.0
            if col_norms[j] > 1e-15:
                norm_val = v / col_norms[j]
            # Apply weight
            var w: Float64 = 1.0
            if j < len(weights):
                w = weights[j]
            row.append(norm_val * w)
        norm_w.append(row^)

    # Step 3: Ideal (best) and negative-ideal (worst) per criterion
    var ideal_vals = List[Float64]()
    var neg_ideal_vals = List[Float64]()
    for j in range(n_crit):
        ideal_vals.append(norm_w[0][j])
        neg_ideal_vals.append(norm_w[0][j])

    for i in range(1, n):
        for j in range(n_crit):
            var v = norm_w[i][j]
            var is_max = True
            if j < len(maximize):
                is_max = maximize[j]
            if is_max:
                if v > ideal_vals[j]:
                    ideal_vals[j] = v
                if v < neg_ideal_vals[j]:
                    neg_ideal_vals[j] = v
            else:
                if v < ideal_vals[j]:
                    ideal_vals[j] = v
                if v > neg_ideal_vals[j]:
                    neg_ideal_vals[j] = v

    # Step 4: Distances
    var scores = List[Float64]()
    for i in range(n):
        var d_plus: Float64 = 0.0
        var d_minus: Float64 = 0.0
        for j in range(n_crit):
            var diff_p = norm_w[i][j] - ideal_vals[j]
            d_plus += diff_p * diff_p
            var diff_n = norm_w[i][j] - neg_ideal_vals[j]
            d_minus += diff_n * diff_n
        d_plus = sqrt(d_plus)
        d_minus = sqrt(d_minus)

        # Step 5: Closeness coefficient
        var denom = d_plus + d_minus
        if denom < 1e-15:
            scores.append(0.0)
        else:
            scores.append(d_minus / denom)

    return scores^
