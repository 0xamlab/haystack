"""Wave 17 test suite — Fuzzy String Matching, Copula Functions, K-Means Clustering."""

from text.fuzzy import (
    levenshtein_distance,
    normalized_levenshtein,
    jaro_similarity,
    jaro_winkler_similarity,
    hamming_distance,
    longest_common_subsequence,
    fuzzy_ratio,
)
from copula import (
    norm_cdf_approx,
    norm_ppf_approx,
    gaussian_copula_sample,
    rank_correlation,
    kendall_tau,
)
from ml.clustering import (
    KMeansResult,
    euclidean_distance,
    assign_cluster,
    kmeans,
    silhouette_score,
)
from std.math import abs as fabs


def assert_true(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("ASSERTION FAILED: " + msg)


def _float_list2(v0: Float64, v1: Float64) -> List[Float64]:
    var l = List[Float64]()
    l.append(v0)
    l.append(v1)
    return l^


def _float_list3(v0: Float64, v1: Float64, v2: Float64) -> List[Float64]:
    var l = List[Float64]()
    l.append(v0)
    l.append(v1)
    l.append(v2)
    return l^


def _float_list5(v0: Float64, v1: Float64, v2: Float64, v3: Float64, v4: Float64) -> List[Float64]:
    var l = List[Float64]()
    l.append(v0)
    l.append(v1)
    l.append(v2)
    l.append(v3)
    l.append(v4)
    return l^


def main() raises:
    print("━━━ Wave 17 test suite (Fuzzy, Copula, Clustering) ━━━\n")

    # ═══════════════════════════════════════════════════════════════════════════
    # FUZZY STRING MATCHING
    # ═══════════════════════════════════════════════════════════════════════════

    # 1. levenshtein_distance("kitten", "sitting") == 3
    var ld1 = levenshtein_distance("kitten", "sitting")
    assert_true(ld1 == 3, "levenshtein('kitten','sitting') == 3")

    # 2. levenshtein_distance("", "abc") == 3
    var ld2 = levenshtein_distance("", "abc")
    assert_true(ld2 == 3, "levenshtein('','abc') == 3")

    # 3. levenshtein_distance("abc", "abc") == 0
    var ld3 = levenshtein_distance("abc", "abc")
    assert_true(ld3 == 0, "levenshtein('abc','abc') == 0")

    # 4. levenshtein_distance("abc", "") == 3
    var ld4 = levenshtein_distance("abc", "")
    assert_true(ld4 == 3, "levenshtein('abc','') == 3")

    # 5. normalized_levenshtein("abc", "abc") ≈ 1.0
    var nl1 = normalized_levenshtein("abc", "abc")
    assert_true(fabs(nl1 - 1.0) < 0.001, "normalized_levenshtein('abc','abc') ≈ 1.0")

    # 6. normalized_levenshtein("abc", "xyz") ≈ 0.0
    var nl2 = normalized_levenshtein("abc", "xyz")
    assert_true(fabs(nl2 - 0.0) < 0.001, "normalized_levenshtein('abc','xyz') ≈ 0.0")

    # 7. jaro_similarity("martha", "marhta") ≈ 0.944
    var js1 = jaro_similarity("martha", "marhta")
    assert_true(fabs(js1 - 0.944) < 0.01, "jaro('martha','marhta') ≈ 0.944")

    # 8. jaro_similarity("abc", "abc") == 1.0
    var js2 = jaro_similarity("abc", "abc")
    assert_true(fabs(js2 - 1.0) < 0.001, "jaro('abc','abc') == 1.0")

    # 9. jaro_winkler > jaro for strings with common prefix
    var jw1 = jaro_winkler_similarity("martha", "marhta")
    assert_true(jw1 > js1, "jaro_winkler('martha','marhta') > jaro('martha','marhta')")

    # 10. jaro_winkler("abc", "abc") == 1.0
    var jw2 = jaro_winkler_similarity("abc", "abc")
    assert_true(fabs(jw2 - 1.0) < 0.001, "jaro_winkler('abc','abc') == 1.0")

    # 11. hamming_distance("karolin", "kathrin") == 3
    var hd1 = hamming_distance("karolin", "kathrin")
    assert_true(hd1 == 3, "hamming('karolin','kathrin') == 3")

    # 12. hamming_distance("abc", "abc") == 0
    var hd2 = hamming_distance("abc", "abc")
    assert_true(hd2 == 0, "hamming('abc','abc') == 0")

    # 13. longest_common_subsequence("abcde", "ace") == 3
    var lcs1 = longest_common_subsequence("abcde", "ace")
    assert_true(lcs1 == 3, "LCS('abcde','ace') == 3")

    # 14. longest_common_subsequence("abc", "def") == 0
    var lcs2 = longest_common_subsequence("abc", "def")
    assert_true(lcs2 == 0, "LCS('abc','def') == 0")

    # 15. fuzzy_ratio("abc", "abc") ≈ 1.0
    var fr1 = fuzzy_ratio("abc", "abc")
    assert_true(fabs(fr1 - 1.0) < 0.001, "fuzzy_ratio('abc','abc') ≈ 1.0")

    # 16. fuzzy_ratio("abc", "xyz") ≈ 0.0
    var fr2 = fuzzy_ratio("abc", "xyz")
    assert_true(fabs(fr2 - 0.0) < 0.001, "fuzzy_ratio('abc','xyz') ≈ 0.0")

    print("✅ Fuzzy string matching (16 assertions)")

    # ═══════════════════════════════════════════════════════════════════════════
    # COPULA FUNCTIONS
    # ═══════════════════════════════════════════════════════════════════════════

    # 17. norm_cdf_approx(0.0) ≈ 0.5
    var cdf0 = norm_cdf_approx(0.0)
    assert_true(fabs(cdf0 - 0.5) < 0.001, "norm_cdf(0) ≈ 0.5")

    # 18. norm_cdf_approx(1.96) ≈ 0.975
    var cdf196 = norm_cdf_approx(1.96)
    assert_true(fabs(cdf196 - 0.975) < 0.01, "norm_cdf(1.96) ≈ 0.975")

    # 19. norm_cdf_approx(-1.96) ≈ 0.025
    var cdf_neg = norm_cdf_approx(-1.96)
    assert_true(fabs(cdf_neg - 0.025) < 0.01, "norm_cdf(-1.96) ≈ 0.025")

    # 20. norm_ppf_approx(0.5) ≈ 0.0
    var ppf05 = norm_ppf_approx(0.5)
    assert_true(fabs(ppf05) < 0.01, "norm_ppf(0.5) ≈ 0.0")

    # 21. norm_ppf_approx(0.975) ≈ 1.96
    var ppf975 = norm_ppf_approx(0.975)
    assert_true(fabs(ppf975 - 1.96) < 0.05, "norm_ppf(0.975) ≈ 1.96")

    # 22. norm_ppf_approx(0.025) ≈ -1.96
    var ppf025 = norm_ppf_approx(0.025)
    assert_true(fabs(ppf025 + 1.96) < 0.05, "norm_ppf(0.025) ≈ -1.96")

    # 23. gaussian_copula_sample(500, 0.0) — verify all u in [0,1]
    var samples0 = gaussian_copula_sample(500, 0.0)
    var all_in_range = True
    for i in range(len(samples0)):
        if samples0[i][0] < 0.0 or samples0[i][0] > 1.0:
            all_in_range = False
        if samples0[i][1] < 0.0 or samples0[i][1] > 1.0:
            all_in_range = False
    assert_true(all_in_range, "copula(rho=0): all u in [0,1]")

    # 24. gaussian_copula_sample(1000, 0.9) — verify rank_correlation > 0.5
    var samples9 = gaussian_copula_sample(1000, 0.9)
    var u1_list = List[Float64]()
    var u2_list = List[Float64]()
    for i in range(len(samples9)):
        u1_list.append(samples9[i][0])
        u2_list.append(samples9[i][1])
    var rho_est = rank_correlation(u1_list, u2_list)
    assert_true(rho_est > 0.5, "copula(rho=0.9): rank_corr > 0.5")

    # 25. rank_correlation on perfectly correlated data
    var rc_x = _float_list5(1.0, 2.0, 3.0, 4.0, 5.0)
    var rc_y = _float_list5(10.0, 20.0, 30.0, 40.0, 50.0)
    var rc1 = rank_correlation(rc_x, rc_y)
    assert_true(fabs(rc1 - 1.0) < 0.01, "rank_corr(perfect) ≈ 1.0")

    # 26. kendall_tau on concordant data
    var kt_x = _float_list5(1.0, 2.0, 3.0, 4.0, 5.0)
    var kt_y = _float_list5(2.0, 4.0, 6.0, 8.0, 10.0)
    var kt1 = kendall_tau(kt_x, kt_y)
    assert_true(fabs(kt1 - 1.0) < 0.01, "kendall_tau(concordant) ≈ 1.0")

    # 27. kendall_tau on discordant data
    var kt_y2 = _float_list5(10.0, 8.0, 6.0, 4.0, 2.0)
    var kt2 = kendall_tau(kt_x, kt_y2)
    assert_true(fabs(kt2 + 1.0) < 0.01, "kendall_tau(discordant) ≈ -1.0")

    print("✅ Copula functions (11 assertions)")

    # ═══════════════════════════════════════════════════════════════════════════
    # K-MEANS CLUSTERING
    # ═══════════════════════════════════════════════════════════════════════════

    # 28. euclidean_distance([0,0], [3,4]) ≈ 5.0
    var ed1 = euclidean_distance(_float_list2(0.0, 0.0), _float_list2(3.0, 4.0))
    assert_true(fabs(ed1 - 5.0) < 0.001, "euclidean_distance([0,0],[3,4]) ≈ 5.0")

    # 29. euclidean_distance identical points == 0
    var ed2 = euclidean_distance(_float_list2(1.0, 2.0), _float_list2(1.0, 2.0))
    assert_true(fabs(ed2) < 0.001, "euclidean_distance same point ≈ 0.0")

    # 30. assign_cluster picks nearest centroid
    var centroids = List[List[Float64]]()
    centroids.append(_float_list2(0.0, 0.0))
    centroids.append(_float_list2(10.0, 10.0))
    centroids.append(_float_list2(20.0, 20.0))
    var ac1 = assign_cluster(_float_list2(1.0, 1.0), centroids)
    assert_true(ac1 == 0, "assign_cluster([1,1]) == 0 (nearest to origin)")
    var ac2 = assign_cluster(_float_list2(19.0, 19.0), centroids)
    assert_true(ac2 == 2, "assign_cluster([19,19]) == 2 (nearest to [20,20])")

    # Build well-separated cluster data
    # Cluster A: around (0, 0)
    # Cluster B: around (50, 50)
    # Cluster C: around (100, 0)
    var cluster_data = List[List[Float64]]()
    # Cluster A (indices 0-9)
    for i in range(10):
        cluster_data.append(_float_list2(Float64(i) * 0.5, Float64(i) * 0.3))
    # Cluster B (indices 10-19)
    for i in range(10):
        cluster_data.append(_float_list2(50.0 + Float64(i) * 0.5, 50.0 + Float64(i) * 0.3))
    # Cluster C (indices 20-29)
    for i in range(10):
        cluster_data.append(_float_list2(100.0 + Float64(i) * 0.5, Float64(i) * 0.3))

    # 32. kmeans on 3 well-separated clusters
    var km = kmeans(cluster_data, 3, max_iter=100)
    assert_true(len(km.labels) == 30, "kmeans: 30 labels returned")

    # 33. Verify iterations <= max_iter
    assert_true(km.iterations <= 100, "kmeans: iterations <= 100")

    # 34. Verify labels are in range [0, k)
    var labels_valid = True
    for i in range(len(km.labels)):
        if km.labels[i] < 0 or km.labels[i] >= 3:
            labels_valid = False
    assert_true(labels_valid, "kmeans: all labels in [0, 3)")

    # 35. Verify points in same original cluster share a label
    var label_a = km.labels[0]
    var same_a = True
    for i in range(1, 10):
        if km.labels[i] != label_a:
            same_a = False
    assert_true(same_a, "kmeans: cluster A points share label")

    var label_b = km.labels[10]
    var same_b = True
    for i in range(11, 20):
        if km.labels[i] != label_b:
            same_b = False
    assert_true(same_b, "kmeans: cluster B points share label")

    var label_c = km.labels[20]
    var same_c = True
    for i in range(21, 30):
        if km.labels[i] != label_c:
            same_c = False
    assert_true(same_c, "kmeans: cluster C points share label")

    # 36. Three clusters have distinct labels
    assert_true(label_a != label_b and label_b != label_c and label_a != label_c,
        "kmeans: 3 distinct cluster labels")

    # 37. Inertia is non-negative
    assert_true(km.inertia >= 0.0, "kmeans: inertia >= 0")

    # 38. silhouette_score > 0.5 for well-separated data
    var sil = silhouette_score(cluster_data, km.labels)
    assert_true(sil > 0.5, "silhouette > 0.5 for well-separated data")

    # 39. KMeansResult has 3 centroids
    assert_true(len(km.centroids) == 3, "kmeans: 3 centroids returned")

    # 40. Each centroid has 2 dimensions
    assert_true(len(km.centroids[0]) == 2, "kmeans: centroid dim == 2")

    print("✅ K-Means clustering (13 assertions)")

    print("\n✅ All Wave 17 tests passed (40 assertions)")
