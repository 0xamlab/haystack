"""
hypothesis.mojo — Extended nonparametric hypothesis tests. Zero Python imports.

Replaces scipy.stats nonparametric tests: mannwhitneyu, wilcoxon,
kruskal, fisher_exact, sign_test.

Public API:
  rank_data              — Assign ranks with average tie-breaking
  mann_whitney_u         — Mann-Whitney U test
  wilcoxon_signed_rank   — Wilcoxon signed-rank test for paired samples
  kruskal_wallis         — Kruskal-Wallis H test for k independent groups
  fisher_exact_2x2       — Fisher's exact test for 2×2 contingency table
  sign_test              — Sign test against a hypothesised median
"""
from std.math import sqrt, abs as fabs, log, exp


# ── Internal helpers ──────────────────────────────────────────────────────────


def _insertion_sort(mut a: List[Float64]):
    """In-place insertion sort."""
    var n = len(a)
    for i in range(1, n):
        var k = a[i]
        var j = i - 1
        while j >= 0 and a[j] > k:
            a[j + 1] = a[j]
            j -= 1
        a[j + 1] = k


def _sort_indices(data: List[Float64]) -> List[Int]:
    """Return indices that sort data in ascending order."""
    var n = len(data)
    var indices = List[Int]()
    for i in range(n):
        indices.append(i)
    for i in range(1, n):
        var key_idx = indices[i]
        var key_val = data[key_idx]
        var j = i - 1
        while j >= 0 and data[indices[j]] > key_val:
            indices[j + 1] = indices[j]
            j -= 1
        indices[j + 1] = key_idx
    return indices^


def _log_factorial(n: Int) -> Float64:
    """Compute log(n!) via summation."""
    var result: Float64 = 0.0
    for i in range(2, n + 1):
        result += log(Float64(i))
    return result


def _log_choose(n: Int, k: Int) -> Float64:
    """Compute log(C(n, k)) = log(n!) - log(k!) - log((n-k)!)."""
    if k < 0 or k > n:
        return -1e300  # log(0)
    return _log_factorial(n) - _log_factorial(k) - _log_factorial(n - k)


# ── rank_data ─────────────────────────────────────────────────────────────────


def rank_data(data: List[Float64]) -> List[Float64]:
    """Assign ranks (1-based) to data with average tie-breaking.

    Equal values receive the mean of the ranks they would span.
    """
    var n = len(data)
    if n == 0:
        return List[Float64]()

    var indices = _sort_indices(data)

    var ranks = List[Float64]()
    for _ in range(n):
        ranks.append(0.0)

    var i = 0
    while i < n:
        var j = i
        while j < n - 1 and fabs(data[indices[j + 1]] - data[indices[i]]) < 1e-12:
            j += 1
        var avg_rank = Float64(i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[indices[k]] = avg_rank
        i = j + 1

    return ranks^


# ── mann_whitney_u ────────────────────────────────────────────────────────────


def mann_whitney_u(x: List[Float64], y: List[Float64]) -> List[Float64]:
    """Mann-Whitney U test for two independent samples.

    Returns [U_statistic, z_score].
    U = sum of ranks in x minus expected = R1 - n1*(n1+1)/2.
    z = (U - n1*n2/2) / sqrt(n1*n2*(n1+n2+1)/12).
    """
    var n1 = len(x)
    var n2 = len(y)
    var result = List[Float64]()

    if n1 == 0 or n2 == 0:
        result.append(0.0)
        result.append(0.0)
        return result^

    # Combine samples
    var combined = List[Float64]()
    for i in range(n1):
        combined.append(x[i])
    for i in range(n2):
        combined.append(y[i])

    # Rank the combined sample
    var ranks = rank_data(combined)

    # Sum of ranks for x (first n1 elements)
    var r1: Float64 = 0.0
    for i in range(n1):
        r1 += ranks[i]

    var n1f = Float64(n1)
    var n2f = Float64(n2)
    var u = r1 - n1f * (n1f + 1.0) / 2.0

    # Normal approximation for z-score
    var mu_u = n1f * n2f / 2.0
    var sigma_u = sqrt(n1f * n2f * (n1f + n2f + 1.0) / 12.0)
    var z: Float64 = 0.0
    if sigma_u > 1e-15:
        z = (u - mu_u) / sigma_u

    result.append(u)
    result.append(z)
    return result^


# ── wilcoxon_signed_rank ──────────────────────────────────────────────────────


def wilcoxon_signed_rank(x: List[Float64], y: List[Float64]) -> List[Float64]:
    """Wilcoxon signed-rank test for paired samples.

    Returns [W_statistic, z_score].
    Computes signed ranks of nonzero differences.
    W = sum of positive signed ranks.
    """
    var n = len(x)
    if len(y) < n:
        n = len(y)

    var result = List[Float64]()

    # Compute absolute differences and track signs
    var abs_diffs = List[Float64]()
    var signs = List[Float64]()
    for i in range(n):
        var d = x[i] - y[i]
        if fabs(d) > 1e-12:
            abs_diffs.append(fabs(d))
            if d > 0.0:
                signs.append(1.0)
            else:
                signs.append(-1.0)

    var nr = len(abs_diffs)  # number of non-zero differences
    if nr == 0:
        result.append(0.0)
        result.append(0.0)
        return result^

    # Rank the absolute differences
    var ranks = rank_data(abs_diffs)

    # W+ = sum of ranks where difference is positive
    var w_plus: Float64 = 0.0
    for i in range(nr):
        if signs[i] > 0.0:
            w_plus += ranks[i]

    var nrf = Float64(nr)
    var mu_w = nrf * (nrf + 1.0) / 4.0
    var sigma_w = sqrt(nrf * (nrf + 1.0) * (2.0 * nrf + 1.0) / 24.0)
    var z: Float64 = 0.0
    if sigma_w > 1e-15:
        z = (w_plus - mu_w) / sigma_w

    result.append(w_plus)
    result.append(z)
    return result^


# ── kruskal_wallis ────────────────────────────────────────────────────────────


def kruskal_wallis(groups: List[List[Float64]]) -> List[Float64]:
    """Kruskal-Wallis H test for k independent groups.

    Returns [H_statistic, degrees_of_freedom].
    H = (12 / (N*(N+1))) * sum(R_i^2 / n_i) - 3*(N+1).
    """
    var k = len(groups)
    var result = List[Float64]()

    if k < 2:
        result.append(0.0)
        result.append(0.0)
        return result^

    # Combine all groups
    var combined = List[Float64]()
    var group_sizes = List[Int]()
    for g in range(k):
        group_sizes.append(len(groups[g]))
        for j in range(len(groups[g])):
            combined.append(groups[g][j])

    var big_n = len(combined)
    if big_n == 0:
        result.append(0.0)
        result.append(0.0)
        return result^

    var ranks = rank_data(combined)

    # Sum of ranks per group
    var idx = 0
    var h_sum: Float64 = 0.0
    for g in range(k):
        var rank_sum: Float64 = 0.0
        var ni = group_sizes[g]
        for _ in range(ni):
            rank_sum += ranks[idx]
            idx += 1
        if ni > 0:
            h_sum += (rank_sum * rank_sum) / Float64(ni)

    var big_nf = Float64(big_n)
    var h = (12.0 / (big_nf * (big_nf + 1.0))) * h_sum - 3.0 * (big_nf + 1.0)

    result.append(h)
    result.append(Float64(k - 1))
    return result^


# ── fisher_exact_2x2 ─────────────────────────────────────────────────────────


def fisher_exact_2x2(a: Int, b: Int, c: Int, d: Int) -> Float64:
    """Fisher's exact test for a 2×2 contingency table.

    Table:  [[a, b], [c, d]]
    Returns the hypergeometric probability:
        P = C(a+b, a) * C(c+d, c) / C(n, a+c)
    where n = a + b + c + d.
    """
    var n = a + b + c + d
    var log_p = _log_choose(a + b, a) + _log_choose(c + d, c) - _log_choose(n, a + c)
    return exp(log_p)


# ── sign_test ─────────────────────────────────────────────────────────────────


def sign_test(x: List[Float64], median: Float64 = 0.0) -> List[Float64]:
    """Sign test: count values above, below, and equal to the median.

    Returns [n_positive, n_negative, n_ties].
    """
    var n_pos: Float64 = 0.0
    var n_neg: Float64 = 0.0
    var n_tie: Float64 = 0.0

    for i in range(len(x)):
        var d = x[i] - median
        if d > 1e-12:
            n_pos += 1.0
        elif d < -1e-12:
            n_neg += 1.0
        else:
            n_tie += 1.0

    var result = List[Float64]()
    result.append(n_pos)
    result.append(n_neg)
    result.append(n_tie)
    return result^
