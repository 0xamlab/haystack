"""Wave 19 test suite — Hypothesis Testing, Data Encoding, Dimensionality Reduction."""

from hypothesis import (
    rank_data,
    mann_whitney_u,
    wilcoxon_signed_rank,
    kruskal_wallis,
    fisher_exact_2x2,
    sign_test,
)
from encoding import (
    label_encode,
    label_decode,
    one_hot_encode,
    ordinal_encode,
    binary_encode,
    frequency_encode,
    build_vocabulary,
)
from dimensionality import (
    PCAResult,
    column_means,
    center_data,
    covariance_matrix,
    power_iteration,
    eigenvalue_from_vector,
    deflate_matrix,
    pca,
    transform_pca,
)
from std.math import abs as fabs, sqrt


fn assert_true(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("ASSERTION FAILED: " + msg)


fn _flist3(v0: Float64, v1: Float64, v2: Float64) -> List[Float64]:
    var l = List[Float64]()
    l.append(v0)
    l.append(v1)
    l.append(v2)
    return l^


fn _flist5(v0: Float64, v1: Float64, v2: Float64, v3: Float64, v4: Float64) -> List[Float64]:
    var l = List[Float64]()
    l.append(v0)
    l.append(v1)
    l.append(v2)
    l.append(v3)
    l.append(v4)
    return l^


fn _slist(a: String, b: String, c: String, d: String) -> List[String]:
    var l = List[String]()
    l.append(a)
    l.append(b)
    l.append(c)
    l.append(d)
    return l^


fn _slist3(a: String, b: String, c: String) -> List[String]:
    var l = List[String]()
    l.append(a)
    l.append(b)
    l.append(c)
    return l^


fn _slist5(a: String, b: String, c: String, d: String, e: String) -> List[String]:
    var l = List[String]()
    l.append(a)
    l.append(b)
    l.append(c)
    l.append(d)
    l.append(e)
    return l^


fn _ilist3(a: Int, b: Int, c: Int) -> List[Int]:
    var l = List[Int]()
    l.append(a)
    l.append(b)
    l.append(c)
    return l^


fn _make_row2(a: Float64, b: Float64) -> List[Float64]:
    var l = List[Float64]()
    l.append(a)
    l.append(b)
    return l^


def main() raises:
    print("━━━ Wave 19 test suite (Hypothesis, Encoding, Dimensionality) ━━━\n")

    # ═══════════════════════════════════════════════════════════════════════════
    # HYPOTHESIS TESTING
    # ═══════════════════════════════════════════════════════════════════════════

    # 1. rank_data([3.0, 1.0, 2.0]) == [3.0, 1.0, 2.0]
    var r1 = rank_data(_flist3(3.0, 1.0, 2.0))
    assert_true(fabs(r1[0] - 3.0) < 1e-10, "rank_data([3,1,2])[0] == 3.0")
    assert_true(fabs(r1[1] - 1.0) < 1e-10, "rank_data([3,1,2])[1] == 1.0")
    assert_true(fabs(r1[2] - 2.0) < 1e-10, "rank_data([3,1,2])[2] == 2.0")

    # 2. rank_data([1.0, 1.0, 3.0]) — tied ranks averaged: [1.5, 1.5, 3.0]
    var r2 = rank_data(_flist3(1.0, 1.0, 3.0))
    assert_true(fabs(r2[0] - 1.5) < 1e-10, "rank_data tied [0] == 1.5")
    assert_true(fabs(r2[1] - 1.5) < 1e-10, "rank_data tied [1] == 1.5")
    assert_true(fabs(r2[2] - 3.0) < 1e-10, "rank_data tied [2] == 3.0")

    # 3. mann_whitney_u on two clearly different groups
    var mw_x = _flist5(1.0, 2.0, 3.0, 4.0, 5.0)
    var mw_y = _flist5(6.0, 7.0, 8.0, 9.0, 10.0)
    var mw = mann_whitney_u(mw_x, mw_y)
    assert_true(len(mw) == 2, "mann_whitney returns 2 values")
    # U should be 0 for x (all ranks of x are lower)
    assert_true(fabs(mw[0] - 0.0) < 1e-10, "mann_whitney U=0 for all-lower group")

    # 4. mann_whitney_u on identical groups — U ≈ n1*n2/2
    var mw_same = mann_whitney_u(_flist3(1.0, 2.0, 3.0), _flist3(1.0, 2.0, 3.0))
    var expected_u = 3.0 * 3.0 / 2.0  # 4.5
    assert_true(fabs(mw_same[0] - expected_u) < 1.5, "mann_whitney identical ≈ n1*n2/2")

    # 5. wilcoxon_signed_rank on paired data — W stat finite
    var wsr = wilcoxon_signed_rank(
        _flist5(1.0, 2.0, 3.0, 4.0, 5.0),
        _flist5(1.5, 2.5, 2.5, 3.5, 4.5),
    )
    assert_true(len(wsr) == 2, "wilcoxon returns 2 values")
    assert_true(wsr[0] > -1e10 and wsr[0] < 1e10, "wilcoxon W is finite")
    assert_true(wsr[1] > -1e10 and wsr[1] < 1e10, "wilcoxon z is finite")

    # 6. kruskal_wallis on 3 groups — H stat > 0 for different groups
    var kw_groups = List[List[Float64]]()
    kw_groups.append(_flist3(1.0, 2.0, 3.0))
    kw_groups.append(_flist3(4.0, 5.0, 6.0))
    kw_groups.append(_flist3(7.0, 8.0, 9.0))
    var kw = kruskal_wallis(kw_groups)
    assert_true(len(kw) == 2, "kruskal_wallis returns 2 values")
    assert_true(kw[0] > 0.0, "kruskal_wallis H > 0 for different groups")
    assert_true(fabs(kw[1] - 2.0) < 1e-10, "kruskal_wallis df == k-1 == 2")

    # 7. fisher_exact_2x2(1, 9, 11, 3) — probability should be small (< 0.05)
    var fe = fisher_exact_2x2(1, 9, 11, 3)
    assert_true(fe < 0.05, "fisher_exact(1,9,11,3) < 0.05")
    assert_true(fe > 0.0, "fisher_exact(1,9,11,3) > 0")

    # 8. sign_test([1,2,3,4,5], 3.0) — n_positive=2, n_negative=2, n_ties=1
    var st = sign_test(_flist5(1.0, 2.0, 3.0, 4.0, 5.0), 3.0)
    assert_true(fabs(st[0] - 2.0) < 1e-10, "sign_test n_positive == 2")
    assert_true(fabs(st[1] - 2.0) < 1e-10, "sign_test n_negative == 2")
    assert_true(fabs(st[2] - 1.0) < 1e-10, "sign_test n_ties == 1")

    print("✅ Hypothesis testing (18 assertions)")

    # ═══════════════════════════════════════════════════════════════════════════
    # DATA ENCODING
    # ═══════════════════════════════════════════════════════════════════════════

    # 9. label_encode(["cat", "dog", "cat", "bird"]) == [0, 1, 0, 2]
    var le = label_encode(_slist("cat", "dog", "cat", "bird"))
    assert_true(le[0] == 0, "label_encode[0] == 0")
    assert_true(le[1] == 1, "label_encode[1] == 1")
    assert_true(le[2] == 0, "label_encode[2] == 0")
    assert_true(le[3] == 2, "label_encode[3] == 2")

    # 10. build_vocabulary(["cat", "dog", "cat", "bird"]) == ["cat", "dog", "bird"]
    var vocab = build_vocabulary(_slist("cat", "dog", "cat", "bird"))
    assert_true(len(vocab) == 3, "vocabulary has 3 unique labels")
    assert_true(vocab[0] == "cat", "vocab[0] == cat")
    assert_true(vocab[1] == "dog", "vocab[1] == dog")
    assert_true(vocab[2] == "bird", "vocab[2] == bird")

    # 11. label_decode([0, 1, 2], ["cat", "dog", "bird"]) == ["cat", "dog", "bird"]
    var ld = label_decode(_ilist3(0, 1, 2), _slist3("cat", "dog", "bird"))
    assert_true(ld[0] == "cat", "label_decode[0] == cat")
    assert_true(ld[1] == "dog", "label_decode[1] == dog")
    assert_true(ld[2] == "bird", "label_decode[2] == bird")

    # 12. one_hot_encode([0, 1, 2], 3) — verify [1,0,0], [0,1,0], [0,0,1]
    var oh = one_hot_encode(_ilist3(0, 1, 2), 3)
    assert_true(fabs(oh[0][0] - 1.0) < 1e-10, "one_hot[0] == [1,0,0]")
    assert_true(fabs(oh[0][1] - 0.0) < 1e-10, "one_hot[0][1] == 0")
    assert_true(fabs(oh[1][1] - 1.0) < 1e-10, "one_hot[1] == [0,1,0]")
    assert_true(fabs(oh[2][2] - 1.0) < 1e-10, "one_hot[2] == [0,0,1]")

    # 13. ordinal_encode(["low", "high", "med"], ["low", "med", "high"]) == [0, 2, 1]
    var oe = ordinal_encode(_slist3("low", "high", "med"), _slist3("low", "med", "high"))
    assert_true(oe[0] == 0, "ordinal_encode[0] == 0")
    assert_true(oe[1] == 2, "ordinal_encode[1] == 2")
    assert_true(oe[2] == 1, "ordinal_encode[2] == 1")

    # 14. binary_encode(5, 4) == [0, 1, 0, 1]
    var be = binary_encode(5, 4)
    assert_true(be[0] == 0, "binary_encode(5,4)[0] == 0")
    assert_true(be[1] == 1, "binary_encode(5,4)[1] == 1")
    assert_true(be[2] == 0, "binary_encode(5,4)[2] == 0")
    assert_true(be[3] == 1, "binary_encode(5,4)[3] == 1")

    # 15. frequency_encode(["a", "a", "b", "a", "b"]) — "a" gets 0.6, "b" gets 0.4
    var freq = frequency_encode(_slist5("a", "a", "b", "a", "b"))
    assert_true(fabs(freq[0] - 0.6) < 1e-10, "freq_encode 'a' == 0.6")
    assert_true(fabs(freq[2] - 0.4) < 1e-10, "freq_encode 'b' == 0.4")
    assert_true(fabs(freq[3] - 0.6) < 1e-10, "freq_encode 'a' [3] == 0.6")

    print("✅ Data encoding (21 assertions)")

    # ═══════════════════════════════════════════════════════════════════════════
    # DIMENSIONALITY REDUCTION
    # ═══════════════════════════════════════════════════════════════════════════

    # 16. column_means([[1,2],[3,4],[5,6]]) == [3.0, 4.0]
    var data3x2 = List[List[Float64]]()
    data3x2.append(_make_row2(1.0, 2.0))
    data3x2.append(_make_row2(3.0, 4.0))
    data3x2.append(_make_row2(5.0, 6.0))
    var cm = column_means(data3x2)
    assert_true(fabs(cm[0] - 3.0) < 1e-10, "column_means[0] == 3.0")
    assert_true(fabs(cm[1] - 4.0) < 1e-10, "column_means[1] == 4.0")

    # 17. center_data — verify all column means ≈ 0
    var centered = center_data(data3x2)
    var cm2 = column_means(centered)
    assert_true(fabs(cm2[0]) < 1e-10, "centered column_means[0] ≈ 0")
    assert_true(fabs(cm2[1]) < 1e-10, "centered column_means[1] ≈ 0")

    # 18. covariance_matrix — symmetric check
    var cov = covariance_matrix(centered)
    assert_true(fabs(cov[0][1] - cov[1][0]) < 1e-10, "covariance matrix symmetric")
    # For this data, cov should be [[4, 4], [4, 4]]
    assert_true(fabs(cov[0][0] - 4.0) < 1e-10, "cov[0][0] == 4.0")

    # 19. power_iteration on identity matrix — returns a unit vector
    var eye2 = List[List[Float64]]()
    eye2.append(_make_row2(1.0, 0.0))
    eye2.append(_make_row2(0.0, 1.0))
    var pi_vec = power_iteration(eye2, 100)
    var pi_norm = sqrt(pi_vec[0] * pi_vec[0] + pi_vec[1] * pi_vec[1])
    assert_true(fabs(pi_norm - 1.0) < 1e-10, "power_iteration(I) returns unit vector")

    # 20. pca on 2D data with clear axis — first component captures most variance
    # Data: strong linear correlation along x=y axis
    var pca_data = List[List[Float64]]()
    pca_data.append(_make_row2(1.0, 1.1))
    pca_data.append(_make_row2(2.0, 2.0))
    pca_data.append(_make_row2(3.0, 3.1))
    pca_data.append(_make_row2(4.0, 3.9))
    pca_data.append(_make_row2(5.0, 5.0))
    pca_data.append(_make_row2(6.0, 6.1))
    pca_data.append(_make_row2(7.0, 6.9))
    pca_data.append(_make_row2(8.0, 8.0))
    pca_data.append(_make_row2(9.0, 9.1))
    pca_data.append(_make_row2(10.0, 9.9))

    var pca_result = pca(pca_data, 2)
    assert_true(len(pca_result.components) == 2, "pca returns 2 components")
    assert_true(pca_result.explained_variance[0] > pca_result.explained_variance[1],
        "first eigenvalue > second eigenvalue")

    # 21. explained_variance_ratio should sum to ≈ 1.0 when all components extracted
    var evr_sum = pca_result.explained_variance_ratio[0] + pca_result.explained_variance_ratio[1]
    assert_true(fabs(evr_sum - 1.0) < 0.05, "explained_variance_ratio sums ≈ 1.0")

    # 22. transform_pca output should have n_components columns
    var transformed = transform_pca(pca_data, pca_result)
    assert_true(len(transformed) == 10, "transform_pca has 10 rows")
    assert_true(len(transformed[0]) == 2, "transform_pca has 2 columns")

    # 23. deflate_matrix reduces dominant eigenvalue
    var cov_pca = covariance_matrix(center_data(pca_data))
    var evec1 = power_iteration(cov_pca, 200)
    var eval1 = eigenvalue_from_vector(cov_pca, evec1)
    var deflated = deflate_matrix(cov_pca, eval1, evec1)
    var evec2 = power_iteration(deflated, 200)
    var eval2 = eigenvalue_from_vector(deflated, evec2)
    assert_true(eval1 > eval2, "deflation: first eigenvalue > second")

    # 24. eigenvalue_from_vector on identity → λ = 1.0
    var ev_ident = eigenvalue_from_vector(eye2, pi_vec)
    assert_true(fabs(ev_ident - 1.0) < 1e-10, "eigenvalue(I, v) == 1.0")

    print("✅ Dimensionality reduction (14 assertions)")

    print("\n✅ All Wave 19 tests passed (53 assertions)")
