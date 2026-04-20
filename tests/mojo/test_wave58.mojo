"""Tests for Wave 58 — Materials Science, Topology, Propensity Score Matching."""

from materials import (
    youngs_modulus,
    shear_modulus,
    bulk_modulus,
    stress_from_force,
    strain_from_deformation,
    thermal_expansion,
    safety_factor,
    stress_concentration,
    fatigue_life,
    beam_deflection_cantilever,
    moment_of_inertia_rect,
    poisson_ratio_from_moduli,
)
from topology import (
    distance_matrix,
    vietoris_rips_edges,
    connected_components_from_edges,
    betti_0,
    filtration_values,
    persistence_diagram_0,
    total_persistence,
    bottleneck_distance,
    euler_characteristic,
    rips_triangle_count,
)
from propensity import (
    propensity_scores,
    nearest_neighbor_match,
    caliper_match,
    matched_ate,
    balance_check,
    propensity_overlap,
    trimmed_sample,
    stratified_estimate,
    match_quality,
)
from std.math import abs as fabs


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error(
            "FAIL: " + msg + " | got " + String(a) + " expected " + String(b)
        )


fn _is_finite(v: Float64) -> Bool:
    return v == v and v < 1e18 and v > -1e18


# ── Materials Tests ──────────────────────────────────────────────────────────


fn test_youngs_modulus() raises:
    # E = stress / strain = 100 / 0.001 = 100000
    var E = youngs_modulus(100.0, 0.001)
    _assert_close(E, 100000.0, 1e-6, "youngs_modulus(100, 0.001)")
    # Zero strain
    var E2 = youngs_modulus(100.0, 0.0)
    _assert_close(E2, 0.0, 1e-12, "youngs_modulus zero strain")
    print("  ✓ test_youngs_modulus")


fn test_shear_modulus() raises:
    # G = 200e9 / (2*(1+0.3)) = 200e9 / 2.6 ≈ 76.923e9
    var G = shear_modulus(200e9, 0.3)
    _assert_close(G, 76.923076923e9, 1e6, "shear_modulus(200e9, 0.3)")
    print("  ✓ test_shear_modulus")


fn test_bulk_modulus() raises:
    # K = 200e9 / (3*(1-0.6)) = 200e9 / 1.2 ≈ 166.67e9
    var K = bulk_modulus(200e9, 0.3)
    _assert_close(K, 166.666666667e9, 1e6, "bulk_modulus(200e9, 0.3)")
    print("  ✓ test_bulk_modulus")


fn test_stress_from_force() raises:
    # σ = 1000 / 0.01 = 100000
    var s = stress_from_force(1000.0, 0.01)
    _assert_close(s, 100000.0, 1e-6, "stress_from_force(1000, 0.01)")
    print("  ✓ test_stress_from_force")


fn test_strain_from_deformation() raises:
    # ε = 0.002 / 1.0 = 0.002
    var e = strain_from_deformation(0.002, 1.0)
    _assert_close(e, 0.002, 1e-12, "strain_from_deformation(0.002, 1.0)")
    print("  ✓ test_strain_from_deformation")


fn test_thermal_expansion() raises:
    # ΔL = 1.0 * 12e-6 * 100 = 0.0012
    var dl = thermal_expansion(1.0, 12e-6, 100.0)
    _assert_close(dl, 0.0012, 1e-8, "thermal_expansion(1, 12e-6, 100)")
    print("  ✓ test_thermal_expansion")


fn test_safety_factor() raises:
    # SF = 500 / 100 = 5.0
    var sf = safety_factor(500.0, 100.0)
    _assert_close(sf, 5.0, 1e-12, "safety_factor(500, 100)")
    print("  ✓ test_safety_factor")


fn test_stress_concentration() raises:
    # σ_max = 2.5 * 100 = 250
    var sm = stress_concentration(100.0, 2.5)
    _assert_close(sm, 250.0, 1e-12, "stress_concentration(100, 2.5)")
    print("  ✓ test_stress_concentration")


fn test_fatigue_life() raises:
    # N = (sigma_a / sigma_f)^(1/b); just check finite and positive
    var N = fatigue_life(200e6, 900e6, -0.1)
    _assert(N > 0.0, "fatigue_life should be positive")
    _assert(_is_finite(N), "fatigue_life should be finite")
    print("  ✓ test_fatigue_life")


fn test_moment_of_inertia_rect() raises:
    # I = 0.1 * 0.2^3 / 12 = 0.1 * 0.008 / 12 = 6.667e-5
    var I = moment_of_inertia_rect(0.1, 0.2)
    _assert_close(I, 6.6666666667e-5, 1e-8, "moment_of_inertia_rect(0.1, 0.2)")
    print("  ✓ test_moment_of_inertia_rect")


fn test_beam_deflection_cantilever() raises:
    # δ = PL³/(3EI), should be positive for positive inputs
    var d = beam_deflection_cantilever(1000.0, 2.0, 200e9, 1e-4)
    _assert(d > 0.0, "beam_deflection should be positive")
    # δ = 1000 * 8 / (3 * 200e9 * 1e-4) = 8000 / 60e6 ≈ 1.333e-4
    _assert_close(d, 1.33333333e-4, 1e-8, "beam_deflection_cantilever value")
    print("  ✓ test_beam_deflection_cantilever")


fn test_poisson_ratio_from_moduli() raises:
    # Check consistency: shear_modulus(200e9, 0.3) -> G, then poisson_from_moduli(200e9, G) ≈ 0.3
    var G = shear_modulus(200e9, 0.3)
    var nu = poisson_ratio_from_moduli(200e9, G)
    _assert_close(nu, 0.3, 1e-6, "poisson_ratio_from_moduli consistency")
    print("  ✓ test_poisson_ratio_from_moduli")


# ── Topology Tests ───────────────────────────────────────────────────────────


fn test_distance_matrix_basic() raises:
    var p1 = List[Float64]()
    p1.append(0.0)
    p1.append(0.0)
    var p2 = List[Float64]()
    p2.append(3.0)
    p2.append(4.0)
    var pts = List[List[Float64]]()
    pts.append(p1^)
    pts.append(p2^)
    var dm = distance_matrix(pts)
    # Symmetric
    _assert_close(dm[0][1], dm[1][0], 1e-12, "distance_matrix symmetric")
    # Diagonal zero
    _assert_close(dm[0][0], 0.0, 1e-12, "distance_matrix diagonal zero [0]")
    _assert_close(dm[1][1], 0.0, 1e-12, "distance_matrix diagonal zero [1]")
    # d(p1, p2) = 5.0
    _assert_close(dm[0][1], 5.0, 1e-10, "distance_matrix d(p1,p2)=5")
    print("  ✓ test_distance_matrix_basic")


fn test_vietoris_rips_edges_zero() raises:
    # At ε=0, no edges (all distances > 0 for distinct points)
    var p1 = List[Float64]()
    p1.append(0.0)
    var p2 = List[Float64]()
    p2.append(1.0)
    var p3 = List[Float64]()
    p3.append(3.0)
    var pts = List[List[Float64]]()
    pts.append(p1^)
    pts.append(p2^)
    pts.append(p3^)
    var dm = distance_matrix(pts)
    var edges = vietoris_rips_edges(dm, 0.0)
    _assert(len(edges) == 0, "vietoris_rips_edges at eps=0 should be empty")
    print("  ✓ test_vietoris_rips_edges_zero")


fn test_vietoris_rips_edges_full() raises:
    # At large ε, all edges present
    var p1 = List[Float64]()
    p1.append(0.0)
    var p2 = List[Float64]()
    p2.append(1.0)
    var p3 = List[Float64]()
    p3.append(2.0)
    var pts = List[List[Float64]]()
    pts.append(p1^)
    pts.append(p2^)
    pts.append(p3^)
    var dm = distance_matrix(pts)
    var edges = vietoris_rips_edges(dm, 100.0)
    _assert(len(edges) == 3, "3 points fully connected -> 3 edges")
    print("  ✓ test_vietoris_rips_edges_full")


fn test_betti_0_disconnected() raises:
    # 4 disconnected points → β₀ = 4
    var empty_edges = List[List[Int]]()
    var b0 = betti_0(4, empty_edges)
    _assert(b0 == 4, "betti_0 of 4 disconnected points should be 4")
    print("  ✓ test_betti_0_disconnected")


fn test_betti_0_connected() raises:
    # 3 points, fully connected → β₀ = 1
    var e1 = List[Int]()
    e1.append(0)
    e1.append(1)
    var e2 = List[Int]()
    e2.append(1)
    e2.append(2)
    var e3 = List[Int]()
    e3.append(0)
    e3.append(2)
    var edges = List[List[Int]]()
    edges.append(e1^)
    edges.append(e2^)
    edges.append(e3^)
    var b0 = betti_0(3, edges)
    _assert(b0 == 1, "betti_0 of fully connected 3 points should be 1")
    print("  ✓ test_betti_0_connected")


fn test_filtration_values_sorted() raises:
    var p1 = List[Float64]()
    p1.append(0.0)
    var p2 = List[Float64]()
    p2.append(1.0)
    var p3 = List[Float64]()
    p3.append(3.0)
    var pts = List[List[Float64]]()
    pts.append(p1^)
    pts.append(p2^)
    pts.append(p3^)
    var dm = distance_matrix(pts)
    var fv = filtration_values(dm)
    _assert(len(fv) > 0, "filtration_values should be non-empty")
    # Check sorted
    for i in range(1, len(fv)):
        _assert(fv[i] >= fv[i - 1], "filtration_values should be sorted")
    print("  ✓ test_filtration_values_sorted")


fn test_persistence_diagram_0_births() raises:
    var p1 = List[Float64]()
    p1.append(0.0)
    var p2 = List[Float64]()
    p2.append(1.0)
    var p3 = List[Float64]()
    p3.append(5.0)
    var pts = List[List[Float64]]()
    pts.append(p1^)
    pts.append(p2^)
    pts.append(p3^)
    var dm = distance_matrix(pts)
    var diag = persistence_diagram_0(dm)
    # All births at 0
    for i in range(len(diag)):
        _assert_close(diag[i][0], 0.0, 1e-12, "persistence birth should be 0")
    # Should have n entries (n-1 finite deaths + 1 infinite)
    _assert(len(diag) == 3, "persistence diagram should have 3 entries for 3 points")
    print("  ✓ test_persistence_diagram_0_births")


fn test_total_persistence_positive() raises:
    var p1 = List[Float64]()
    p1.append(0.0)
    var p2 = List[Float64]()
    p2.append(1.0)
    var p3 = List[Float64]()
    p3.append(5.0)
    var pts = List[List[Float64]]()
    pts.append(p1^)
    pts.append(p2^)
    pts.append(p3^)
    var dm = distance_matrix(pts)
    var diag = persistence_diagram_0(dm)
    var tp = total_persistence(diag)
    _assert(tp > 0.0, "total_persistence should be positive")
    print("  ✓ test_total_persistence_positive")


fn test_bottleneck_distance_same() raises:
    # Bottleneck distance of diagram with itself should be 0
    var d1 = List[List[Float64]]()
    var pair1 = List[Float64]()
    pair1.append(0.0)
    pair1.append(1.0)
    d1.append(pair1^)
    var pair2 = List[Float64]()
    pair2.append(0.0)
    pair2.append(2.0)
    d1.append(pair2^)

    var d2 = List[List[Float64]]()
    var pair3 = List[Float64]()
    pair3.append(0.0)
    pair3.append(1.0)
    d2.append(pair3^)
    var pair4 = List[Float64]()
    pair4.append(0.0)
    pair4.append(2.0)
    d2.append(pair4^)

    var bd = bottleneck_distance(d1, d2)
    _assert_close(bd, 0.0, 1e-12, "bottleneck_distance same diagram = 0")
    print("  ✓ test_bottleneck_distance_same")


fn test_bottleneck_distance_diff() raises:
    var d1 = List[List[Float64]]()
    var pair1 = List[Float64]()
    pair1.append(0.0)
    pair1.append(1.0)
    d1.append(pair1^)

    var d2 = List[List[Float64]]()
    var pair2 = List[Float64]()
    pair2.append(0.0)
    pair2.append(3.0)
    d2.append(pair2^)

    var bd = bottleneck_distance(d1, d2)
    _assert(bd > 0.0, "bottleneck_distance different diagrams > 0")
    _assert_close(bd, 2.0, 1e-12, "bottleneck_distance = 2.0")
    print("  ✓ test_bottleneck_distance_diff")


fn test_euler_characteristic() raises:
    # Tetrahedron: V=4, E=6, F=4 → χ=2
    var chi = euler_characteristic(4, 6, 4)
    _assert(chi == 2, "euler_characteristic tetrahedron = 2")
    # Cube surface: V=8, E=12, F=6 → χ=2
    var chi2 = euler_characteristic(8, 12, 6)
    _assert(chi2 == 2, "euler_characteristic cube = 2")
    print("  ✓ test_euler_characteristic")


fn test_rips_triangle_count() raises:
    # 3 fully connected vertices = 1 triangle
    var e1 = List[Int]()
    e1.append(0)
    e1.append(1)
    var e2 = List[Int]()
    e2.append(1)
    e2.append(2)
    var e3 = List[Int]()
    e3.append(0)
    e3.append(2)
    var edges = List[List[Int]]()
    edges.append(e1^)
    edges.append(e2^)
    edges.append(e3^)
    var tc = rips_triangle_count(3, edges)
    _assert(tc == 1, "rips_triangle_count 3-clique = 1")

    # 4 fully connected = 4 triangles
    var edges4 = List[List[Int]]()
    var a1 = List[Int]()
    a1.append(0)
    a1.append(1)
    edges4.append(a1^)
    var a2 = List[Int]()
    a2.append(0)
    a2.append(2)
    edges4.append(a2^)
    var a3 = List[Int]()
    a3.append(0)
    a3.append(3)
    edges4.append(a3^)
    var a4 = List[Int]()
    a4.append(1)
    a4.append(2)
    edges4.append(a4^)
    var a5 = List[Int]()
    a5.append(1)
    a5.append(3)
    edges4.append(a5^)
    var a6 = List[Int]()
    a6.append(2)
    a6.append(3)
    edges4.append(a6^)
    var tc4 = rips_triangle_count(4, edges4)
    _assert(tc4 == 4, "rips_triangle_count 4-clique = 4")
    print("  ✓ test_rips_triangle_count")


# ── Propensity Tests ─────────────────────────────────────────────────────────


fn _make_features() -> List[List[Float64]]:
    """Create simple feature matrix for testing."""
    var features = List[List[Float64]]()
    # Treated group: higher feature values
    var f1 = List[Float64]()
    f1.append(2.0)
    f1.append(3.0)
    features.append(f1^)
    var f2 = List[Float64]()
    f2.append(2.5)
    f2.append(3.5)
    features.append(f2^)
    var f3 = List[Float64]()
    f3.append(3.0)
    f3.append(4.0)
    features.append(f3^)
    var f4 = List[Float64]()
    f4.append(2.2)
    f4.append(3.2)
    features.append(f4^)
    # Control group: lower feature values
    var f5 = List[Float64]()
    f5.append(0.5)
    f5.append(1.0)
    features.append(f5^)
    var f6 = List[Float64]()
    f6.append(0.8)
    f6.append(1.2)
    features.append(f6^)
    var f7 = List[Float64]()
    f7.append(1.0)
    f7.append(1.5)
    features.append(f7^)
    var f8 = List[Float64]()
    f8.append(0.3)
    f8.append(0.8)
    features.append(f8^)
    return features^


fn _make_treatment() -> List[Int]:
    var t = List[Int]()
    t.append(1)
    t.append(1)
    t.append(1)
    t.append(1)
    t.append(0)
    t.append(0)
    t.append(0)
    t.append(0)
    return t^


fn test_propensity_scores_range() raises:
    var features = _make_features()
    var treatment = _make_treatment()
    var scores = propensity_scores(features, treatment)
    _assert(len(scores) == 8, "propensity_scores length")
    for i in range(len(scores)):
        _assert(scores[i] > 0.0, "propensity score > 0")
        _assert(scores[i] < 1.0, "propensity score < 1")
    print("  ✓ test_propensity_scores_range")


fn test_nearest_neighbor_match() raises:
    var s_treated = List[Float64]()
    s_treated.append(0.7)
    s_treated.append(0.8)
    s_treated.append(0.6)
    var s_control = List[Float64]()
    s_control.append(0.3)
    s_control.append(0.65)
    s_control.append(0.75)
    var matches = nearest_neighbor_match(s_treated, s_control)
    _assert(len(matches) == 3, "nearest_neighbor_match length")
    # All indices valid
    for i in range(len(matches)):
        _assert(matches[i] >= 0, "match index >= 0")
        _assert(matches[i] < 3, "match index < n_control")
    # 0.7 equidistant to 0.65(idx1) and 0.75(idx2); first found wins → idx 1
    _assert(matches[0] == 1, "0.7 matches nearest (first tie at 0.65)")
    # 0.8 should match to 0.75 (index 2)
    _assert(matches[1] == 2, "0.8 matches nearest to 0.75")
    # 0.6 should match to 0.65 (index 1)
    _assert(matches[2] == 1, "0.6 matches nearest to 0.65")
    print("  ✓ test_nearest_neighbor_match")


fn test_caliper_match_tight() raises:
    var s_treated = List[Float64]()
    s_treated.append(0.7)
    s_treated.append(0.2)
    s_treated.append(0.9)
    var s_control = List[Float64]()
    s_control.append(0.71)
    s_control.append(0.5)
    var matches = caliper_match(s_treated, s_control, 0.05)
    # 0.7 matches 0.71 (within 0.05)
    _assert(matches[0] == 0, "caliper match 0.7 -> 0.71")
    # 0.2 no match within 0.05
    _assert(matches[1] == -1, "caliper match 0.2 -> -1")
    # 0.9 no match within 0.05
    _assert(matches[2] == -1, "caliper match 0.9 -> -1")
    print("  ✓ test_caliper_match_tight")


fn test_matched_ate() raises:
    var outcomes = List[Float64]()
    outcomes.append(10.0)  # treated 0
    outcomes.append(12.0)  # treated 1
    outcomes.append(5.0)   # control 0
    outcomes.append(6.0)   # control 1
    var treatment = List[Int]()
    treatment.append(1)
    treatment.append(1)
    treatment.append(0)
    treatment.append(0)
    # Match treated[0] -> control[0], treated[1] -> control[1]
    var matches = List[Int]()
    matches.append(0)
    matches.append(1)
    var ate = matched_ate(outcomes, treatment, matches)
    # (10-5 + 12-6) / 2 = (5+6)/2 = 5.5
    _assert(_is_finite(ate), "matched_ate should be finite")
    _assert_close(ate, 5.5, 1e-10, "matched_ate = 5.5")
    print("  ✓ test_matched_ate")


fn test_balance_check() raises:
    var ft = List[Float64]()
    ft.append(5.0)
    ft.append(6.0)
    ft.append(7.0)
    var fc = List[Float64]()
    fc.append(2.0)
    fc.append(3.0)
    fc.append(4.0)
    var smd = balance_check(ft, fc)
    _assert(smd > 0.0, "balance_check should be positive")
    _assert(_is_finite(smd), "balance_check should be finite")
    print("  ✓ test_balance_check")


fn test_propensity_overlap() raises:
    var scores = List[Float64]()
    scores.append(0.3)
    scores.append(0.5)
    scores.append(0.7)
    scores.append(0.4)
    scores.append(0.6)
    scores.append(0.8)
    var treatment = List[Int]()
    treatment.append(1)
    treatment.append(1)
    treatment.append(1)
    treatment.append(0)
    treatment.append(0)
    treatment.append(0)
    var ov = propensity_overlap(scores, treatment)
    # treated: [0.3, 0.7], control: [0.4, 0.8]
    # overlap = min(0.7, 0.8) - max(0.3, 0.4) = 0.7 - 0.4 = 0.3
    _assert_close(ov, 0.3, 1e-10, "propensity_overlap = 0.3")
    print("  ✓ test_propensity_overlap")


fn test_trimmed_sample() raises:
    var scores = List[Float64]()
    scores.append(0.1)
    scores.append(0.3)
    scores.append(0.5)
    scores.append(0.7)
    scores.append(0.9)
    var treatment = List[Int]()
    treatment.append(1)
    treatment.append(0)
    treatment.append(1)
    treatment.append(0)
    treatment.append(1)
    var trimmed = trimmed_sample(scores, treatment, 0.2, 0.8)
    # Scores within [0.2, 0.8]: indices 1(0.3), 2(0.5), 3(0.7)
    _assert(len(trimmed) == 3, "trimmed_sample should have 3 elements")
    _assert(trimmed[0] == 1, "trimmed index 0 = 1")
    _assert(trimmed[1] == 2, "trimmed index 1 = 2")
    _assert(trimmed[2] == 3, "trimmed index 2 = 3")
    # Trimmed is subset of original
    _assert(len(trimmed) < len(scores), "trimmed is subset of original")
    print("  ✓ test_trimmed_sample")


fn test_stratified_estimate() raises:
    var outcomes = List[Float64]()
    outcomes.append(10.0)
    outcomes.append(12.0)
    outcomes.append(8.0)
    outcomes.append(5.0)
    outcomes.append(6.0)
    outcomes.append(4.0)
    var treatment = List[Int]()
    treatment.append(1)
    treatment.append(1)
    treatment.append(1)
    treatment.append(0)
    treatment.append(0)
    treatment.append(0)
    var scores = List[Float64]()
    scores.append(0.8)
    scores.append(0.7)
    scores.append(0.6)
    scores.append(0.3)
    scores.append(0.2)
    scores.append(0.1)
    var ate = stratified_estimate(outcomes, treatment, scores, 2)
    _assert(_is_finite(ate), "stratified_estimate should be finite")
    print("  ✓ test_stratified_estimate")


fn test_match_quality() raises:
    var matches = List[Int]()
    matches.append(0)
    matches.append(-1)
    matches.append(2)
    matches.append(-1)
    matches.append(1)
    var q = match_quality(matches)
    # 3 out of 5 = 0.6
    _assert_close(q, 0.6, 1e-12, "match_quality = 0.6")
    _assert(q >= 0.0, "match_quality >= 0")
    _assert(q <= 1.0, "match_quality <= 1")
    print("  ✓ test_match_quality")


fn test_match_quality_all_good() raises:
    var matches = List[Int]()
    matches.append(0)
    matches.append(1)
    matches.append(2)
    var q = match_quality(matches)
    _assert_close(q, 1.0, 1e-12, "match_quality all good = 1.0")
    print("  ✓ test_match_quality_all_good")


fn test_match_quality_none() raises:
    var matches = List[Int]()
    matches.append(-1)
    matches.append(-1)
    var q = match_quality(matches)
    _assert_close(q, 0.0, 1e-12, "match_quality none = 0.0")
    print("  ✓ test_match_quality_none")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("Wave 58 Tests — Materials Science, Topology, Propensity Score Matching")
    print("═" * 70)

    print("\n── Materials Science ──")
    test_youngs_modulus()
    test_shear_modulus()
    test_bulk_modulus()
    test_stress_from_force()
    test_strain_from_deformation()
    test_thermal_expansion()
    test_safety_factor()
    test_stress_concentration()
    test_fatigue_life()
    test_moment_of_inertia_rect()
    test_beam_deflection_cantilever()
    test_poisson_ratio_from_moduli()

    print("\n── Topology ──")
    test_distance_matrix_basic()
    test_vietoris_rips_edges_zero()
    test_vietoris_rips_edges_full()
    test_betti_0_disconnected()
    test_betti_0_connected()
    test_filtration_values_sorted()
    test_persistence_diagram_0_births()
    test_total_persistence_positive()
    test_bottleneck_distance_same()
    test_bottleneck_distance_diff()
    test_euler_characteristic()
    test_rips_triangle_count()

    print("\n── Propensity Score Matching ──")
    test_propensity_scores_range()
    test_nearest_neighbor_match()
    test_caliper_match_tight()
    test_matched_ate()
    test_balance_check()
    test_propensity_overlap()
    test_trimmed_sample()
    test_stratified_estimate()
    test_match_quality()
    test_match_quality_all_good()
    test_match_quality_none()

    print("\n" + "═" * 70)
    print("All Wave 58 tests passed! ✓")
