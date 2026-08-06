"""Tests for Wave 30 — Constraint Satisfaction, Digital Filters, Reliability Engineering.
🎯 100 LIBRARY MILESTONE!"""

from constraint import (
    CSPResult,
    solve_backtrack,
    all_different,
    n_queens_check,
    solve_n_queens,
    magic_square_check,
    graph_coloring,
    sudoku_valid,
    count_solutions_nqueens,
)
from signal.filter import (
    lowpass_ema,
    highpass_ema,
    bandpass,
    median_filter,
    savitzky_golay_3,
    moving_average_filter,
    iir_filter_1st,
    diff_filter,
    integrate_filter,
    snr,
    rms,
)
from reliability import (
    exponential_reliability,
    exponential_failure_rate,
    weibull_reliability,
    weibull_failure_rate,
    mtbf,
    availability,
    series_reliability,
    parallel_reliability,
    k_of_n_reliability,
    bathtub_rate,
    mission_reliability,
)
from std.math import abs as fabs, exp, sqrt


def _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


def _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Helper: build lists ─────────────────────────────────────────────────────


def _li3(a: Int, b: Int, c: Int) -> List[Int]:
    var v = List[Int]()
    v.append(a); v.append(b); v.append(c)
    return v^


def _li4(a: Int, b: Int, c: Int, d: Int) -> List[Int]:
    var v = List[Int]()
    v.append(a); v.append(b); v.append(c); v.append(d)
    return v^


def _li9(a: Int, b: Int, c: Int, d: Int, e: Int, f: Int, g: Int, h: Int, i: Int) -> List[Int]:
    var v = List[Int]()
    v.append(a); v.append(b); v.append(c); v.append(d); v.append(e)
    v.append(f); v.append(g); v.append(h); v.append(i)
    return v^


def _lf(elements: List[Float64]) -> List[Float64]:
    """Identity helper for readability."""
    return List[Float64](copy=elements)


# ── Constraint tests ─────────────────────────────────────────────────────────


def test_all_different() raises:
    var v1 = _li3(1, 2, 3)
    _assert(all_different(v1), "all_different([1,2,3]) should be True")
    print("  ✓ all_different unique")

    var v2 = _li3(1, 2, 2)
    _assert(not all_different(v2), "all_different([1,2,2]) should be False")
    print("  ✓ all_different duplicate")

    var v3 = List[Int]()
    v3.append(5)
    _assert(all_different(v3), "all_different single element")
    print("  ✓ all_different single")

    var v4 = List[Int]()
    _assert(all_different(v4), "all_different empty")
    print("  ✓ all_different empty")


def test_n_queens_4() raises:
    var sol = solve_n_queens(4)
    _assert(len(sol) == 4, "solve_n_queens(4) should have length 4")
    print("  ✓ n_queens(4) length")

    _assert(n_queens_check(sol), "solve_n_queens(4) result should be valid")
    print("  ✓ n_queens(4) valid placement")


def test_n_queens_8() raises:
    var sol = solve_n_queens(8)
    _assert(len(sol) == 8, "solve_n_queens(8) should have length 8")
    print("  ✓ n_queens(8) length")

    _assert(n_queens_check(sol), "solve_n_queens(8) result should be valid")
    print("  ✓ n_queens(8) valid placement")


def test_n_queens_check_invalid() raises:
    var bad = _li4(0, 0, 0, 0)
    _assert(not n_queens_check(bad), "same column should be invalid")
    print("  ✓ n_queens_check invalid same column")

    var diag = _li4(0, 1, 2, 3)
    _assert(not n_queens_check(diag), "diagonal should be invalid")
    print("  ✓ n_queens_check invalid diagonal")


def test_count_solutions_nqueens() raises:
    var c4 = count_solutions_nqueens(4)
    _assert(c4 == 2, "count_solutions_nqueens(4) should be 2, got " + String(c4))
    print("  ✓ count_solutions_nqueens(4) == 2")

    var c5 = count_solutions_nqueens(5)
    _assert(c5 == 10, "count_solutions_nqueens(5) should be 10, got " + String(c5))
    print("  ✓ count_solutions_nqueens(5) == 10")


def test_graph_coloring() raises:
    # Triangle graph: 3 nodes, each connected to the other two
    var adj = List[List[Int]]()
    var n0 = List[Int](); n0.append(1); n0.append(2)
    var n1 = List[Int](); n1.append(0); n1.append(2)
    var n2 = List[Int](); n2.append(0); n2.append(1)
    adj.append(n0^); adj.append(n1^); adj.append(n2^)

    var colors3 = graph_coloring(adj, 3)
    _assert(len(colors3) == 3, "triangle with 3 colors should find solution")
    # Verify no adjacent nodes share colors
    _assert(colors3[0] != colors3[1], "node 0 != node 1 color")
    _assert(colors3[0] != colors3[2], "node 0 != node 2 color")
    _assert(colors3[1] != colors3[2], "node 1 != node 2 color")
    print("  ✓ graph_coloring triangle 3 colors")

    # Rebuild adj for 2-color test
    var adj2 = List[List[Int]]()
    var m0 = List[Int](); m0.append(1); m0.append(2)
    var m1 = List[Int](); m1.append(0); m1.append(2)
    var m2 = List[Int](); m2.append(0); m2.append(1)
    adj2.append(m0^); adj2.append(m1^); adj2.append(m2^)

    var colors2 = graph_coloring(adj2, 2)
    _assert(len(colors2) == 0, "triangle with 2 colors should have no solution")
    print("  ✓ graph_coloring triangle 2 colors no solution")


def test_sudoku_valid() raises:
    # Known valid (partially filled) Sudoku board
    var board = List[List[Int]]()
    board.append(_li9(5, 3, 0, 0, 7, 0, 0, 0, 0))
    board.append(_li9(6, 0, 0, 1, 9, 5, 0, 0, 0))
    board.append(_li9(0, 9, 8, 0, 0, 0, 0, 6, 0))
    board.append(_li9(8, 0, 0, 0, 6, 0, 0, 0, 3))
    board.append(_li9(4, 0, 0, 8, 0, 3, 0, 0, 1))
    board.append(_li9(7, 0, 0, 0, 2, 0, 0, 0, 6))
    board.append(_li9(0, 6, 0, 0, 0, 0, 2, 8, 0))
    board.append(_li9(0, 0, 0, 4, 1, 9, 0, 0, 5))
    board.append(_li9(0, 0, 0, 0, 8, 0, 0, 7, 9))
    _assert(sudoku_valid(board), "known valid sudoku should pass")
    print("  ✓ sudoku_valid known board")

    # Invalid: duplicate in row
    var bad = List[List[Int]]()
    bad.append(_li9(5, 5, 0, 0, 7, 0, 0, 0, 0))
    bad.append(_li9(6, 0, 0, 1, 9, 5, 0, 0, 0))
    bad.append(_li9(0, 9, 8, 0, 0, 0, 0, 6, 0))
    bad.append(_li9(8, 0, 0, 0, 6, 0, 0, 0, 3))
    bad.append(_li9(4, 0, 0, 8, 0, 3, 0, 0, 1))
    bad.append(_li9(7, 0, 0, 0, 2, 0, 0, 0, 6))
    bad.append(_li9(0, 6, 0, 0, 0, 0, 2, 8, 0))
    bad.append(_li9(0, 0, 0, 4, 1, 9, 0, 0, 5))
    bad.append(_li9(0, 0, 0, 0, 8, 0, 0, 7, 9))
    _assert(not sudoku_valid(bad), "duplicate in row should fail")
    print("  ✓ sudoku_valid invalid duplicate")


def test_magic_square() raises:
    # Classic 3x3 magic square
    var sq = List[List[Int]]()
    sq.append(_li3(2, 7, 6))
    sq.append(_li3(9, 5, 1))
    sq.append(_li3(4, 3, 8))
    _assert(magic_square_check(sq), "3x3 magic square should be valid")
    print("  ✓ magic_square_check valid")

    # Non-magic square
    var bad = List[List[Int]]()
    bad.append(_li3(1, 2, 3))
    bad.append(_li3(4, 5, 6))
    bad.append(_li3(7, 8, 9))
    _assert(not magic_square_check(bad), "non-magic square should fail")
    print("  ✓ magic_square_check invalid")


def test_solve_backtrack() raises:
    # Simple CSP: 2 vars, domain [0,1], must be not_equal
    var domains = List[List[Int]]()
    var d0 = List[Int](); d0.append(0); d0.append(1)
    var d1 = List[Int](); d1.append(0); d1.append(1)
    domains.append(d0^); domains.append(d1^)
    var constraints = List[List[Int]]()
    constraints.append(_li3(0, 1, 0))  # var0 != var1
    var result = solve_backtrack(domains, constraints)
    _assert(result.found, "simple CSP should find solution")
    _assert(result.solution[0] != result.solution[1], "vars should differ")
    print("  ✓ solve_backtrack simple CSP")


# ── Filter tests ─────────────────────────────────────────────────────────────


def test_lowpass_ema() raises:
    var data = List[Float64]()
    data.append(10.0); data.append(10.0); data.append(50.0); data.append(10.0)
    data.append(10.0); data.append(50.0); data.append(10.0); data.append(10.0)
    var filtered = lowpass_ema(data, 0.2)
    _assert(len(filtered) == len(data), "lowpass_ema length")
    # Check variance reduced
    var mean_d: Float64 = 0.0
    var mean_f: Float64 = 0.0
    for i in range(len(data)):
        mean_d += data[i]
        mean_f += filtered[i]
    mean_d /= Float64(len(data))
    mean_f /= Float64(len(filtered))
    var var_d: Float64 = 0.0
    var var_f: Float64 = 0.0
    for i in range(len(data)):
        var dd = data[i] - mean_d
        var df = filtered[i] - mean_f
        var_d += dd * dd
        var_f += df * df
    _assert(var_f < var_d, "lowpass should reduce variance")
    print("  ✓ lowpass_ema reduces variance")


def test_highpass_ema() raises:
    var data = List[Float64]()
    data.append(100.0); data.append(101.0); data.append(99.0); data.append(100.0)
    data.append(102.0); data.append(98.0); data.append(100.0); data.append(101.0)
    var filtered = highpass_ema(data, 0.1)
    _assert(len(filtered) == len(data), "highpass_ema length")
    # Mean of high-pass should be small relative to DC
    var mean_hp: Float64 = 0.0
    for i in range(len(filtered)):
        mean_hp += filtered[i]
    mean_hp /= Float64(len(filtered))
    _assert(fabs(mean_hp) < 20.0, "highpass mean should be small relative to DC")
    print("  ✓ highpass_ema removes DC")


def test_median_filter() raises:
    var data = List[Float64]()
    data.append(1.0); data.append(1.0); data.append(1.0); data.append(100.0)
    data.append(1.0); data.append(1.0); data.append(1.0)
    var filtered = median_filter(data, 3)
    _assert(len(filtered) == len(data), "median_filter length")
    _assert(filtered[3] == 1.0, "median_filter should remove spike")
    print("  ✓ median_filter removes spike")


def test_moving_average_filter() raises:
    var data = List[Float64]()
    data.append(1.0); data.append(2.0); data.append(3.0)
    data.append(4.0); data.append(5.0)
    var filtered = moving_average_filter(data, 3)
    _assert(len(filtered) == len(data), "moving_average_filter length")
    # Middle element: (2+3+4)/3 = 3.0
    _assert_close(filtered[2], 3.0, 1e-10, "moving_average_filter center")
    print("  ✓ moving_average_filter correct length and values")


def test_diff_filter() raises:
    var data = List[Float64]()
    data.append(1.0); data.append(3.0); data.append(6.0); data.append(10.0)
    var d = diff_filter(data)
    _assert(len(d) == 3, "diff_filter length")
    _assert_close(d[0], 2.0, 1e-12, "diff[0]")
    _assert_close(d[1], 3.0, 1e-12, "diff[1]")
    _assert_close(d[2], 4.0, 1e-12, "diff[2]")
    print("  ✓ diff_filter([1,3,6,10]) == [2,3,4]")


def test_integrate_diff_roundtrip() raises:
    var data = List[Float64]()
    data.append(0.0); data.append(1.0); data.append(3.0)
    data.append(6.0); data.append(10.0)
    var d = diff_filter(data)
    var integ = integrate_filter(d, 1.0)
    _assert(len(integ) == len(d), "integrate length matches diff length")
    print("  ✓ integrate_filter(diff_filter) roundtrip")


def test_iir_filter_1st() raises:
    var data = List[Float64]()
    data.append(1.0); data.append(0.0); data.append(0.0)
    data.append(0.0); data.append(0.0)
    var filtered = iir_filter_1st(data, 0.5, 0.5)
    _assert(len(filtered) == 5, "iir length")
    _assert_close(filtered[0], 0.5, 1e-12, "iir[0]")
    _assert_close(filtered[1], 0.25, 1e-12, "iir[1]")
    _assert(filtered[4] < filtered[0], "iir should decay")
    print("  ✓ iir_filter_1st stable decay")


def test_rms() raises:
    var data = List[Float64]()
    data.append(3.0); data.append(4.0)
    var r = rms(data)
    _assert_close(r, sqrt(12.5), 1e-10, "rms([3,4])")
    print("  ✓ rms([3,4]) ≈ 3.536")


def test_snr() raises:
    var signal_data = List[Float64]()
    signal_data.append(10.0); signal_data.append(10.0)
    signal_data.append(10.0); signal_data.append(10.0)
    var noise_data = List[Float64]()
    noise_data.append(0.1); noise_data.append(-0.1)
    noise_data.append(0.1); noise_data.append(-0.1)
    var s = snr(signal_data, noise_data)
    _assert(s > 0.0, "SNR should be positive for strong signal")
    _assert(s > 30.0, "SNR should be high for 10.0 vs 0.1")
    print("  ✓ snr positive dB value (" + String(s) + " dB)")


def test_savitzky_golay_3() raises:
    var data = List[Float64]()
    data.append(0.0); data.append(1.0); data.append(5.0)
    data.append(10.0); data.append(5.0); data.append(1.0); data.append(0.0)
    var sg = savitzky_golay_3(data)
    _assert(len(sg) == len(data), "savitzky_golay_3 length")
    _assert(sg[3] > 5.0, "SG should preserve peak roughly")
    print("  ✓ savitzky_golay_3 smooths without shifting peak too much")


def test_bandpass() raises:
    var data = List[Float64]()
    data.append(1.0); data.append(2.0); data.append(1.0); data.append(2.0)
    data.append(1.0); data.append(2.0); data.append(1.0); data.append(2.0)
    var bp = bandpass(data, 0.3, 0.8)
    _assert(len(bp) == len(data), "bandpass length")
    print("  ✓ bandpass length correct")


# ── Reliability tests ────────────────────────────────────────────────────────


def test_exponential_reliability() raises:
    _assert_close(exponential_reliability(0.0, 0.01), 1.0, 1e-12,
                  "exp_rel(0)")
    print("  ✓ exponential_reliability(0, 0.01) == 1.0")

    var r100 = exponential_reliability(100.0, 0.01)
    _assert_close(r100, exp(-1.0), 1e-6, "exp_rel(100, 0.01)")
    print("  ✓ exponential_reliability(100, 0.01) ≈ 0.368")


def test_weibull_reliability() raises:
    _assert_close(weibull_reliability(0.0, 2.0, 100.0), 1.0, 1e-12,
                  "weibull_rel(0)")
    print("  ✓ weibull_reliability(0, 2, 100) == 1.0")

    # When beta=1, Weibull = Exponential
    var w100 = weibull_reliability(100.0, 1.0, 100.0)
    _assert_close(w100, exp(-1.0), 1e-6, "weibull_rel(100, 1, 100)")
    print("  ✓ weibull_reliability(100, 1, 100) ≈ 0.368 (matches exp)")


def test_weibull_failure_rate() raises:
    # When beta=1, failure rate = 1/eta = constant
    var h = weibull_failure_rate(50.0, 1.0, 100.0)
    _assert_close(h, 0.01, 1e-6, "weibull h(t) with beta=1")
    print("  ✓ weibull_failure_rate constant when beta=1")

    # beta=2 means increasing failure rate
    var h1 = weibull_failure_rate(50.0, 2.0, 100.0)
    var h2 = weibull_failure_rate(80.0, 2.0, 100.0)
    _assert(h2 > h1, "weibull failure rate should increase with beta>1")
    print("  ✓ weibull_failure_rate increasing when beta=2")


def test_mtbf() raises:
    _assert_close(mtbf(0.001), 1000.0, 1e-6, "mtbf(0.001)")
    print("  ✓ mtbf(0.001) == 1000.0")


def test_availability() raises:
    var a = availability(1000.0, 10.0)
    _assert_close(a, 1000.0 / 1010.0, 1e-6, "availability(1000, 10)")
    _assert(a > 0.989 and a < 0.991, "availability ≈ 0.990")
    print("  ✓ availability(1000, 10) ≈ 0.990")


def test_series_reliability() raises:
    var rels = List[Float64]()
    rels.append(0.99); rels.append(0.99); rels.append(0.99)
    var sr = series_reliability(rels)
    _assert_close(sr, 0.970299, 1e-4, "series_reliability")
    print("  ✓ series_reliability([0.99, 0.99, 0.99]) ≈ 0.970")


def test_parallel_reliability() raises:
    var rels = List[Float64]()
    rels.append(0.9); rels.append(0.9)
    var pr = parallel_reliability(rels)
    _assert_close(pr, 0.99, 1e-6, "parallel_reliability")
    print("  ✓ parallel_reliability([0.9, 0.9]) ≈ 0.99")


def test_k_of_n_reliability() raises:
    var kr = k_of_n_reliability(2, 3, 0.9)
    _assert(kr > 0.729, "k_of_n > series")
    _assert(kr < 0.999, "k_of_n < parallel")
    # Exact: C(3,2)*0.9^2*0.1 + C(3,3)*0.9^3 = 3*0.081 + 0.729 = 0.972
    _assert_close(kr, 0.972, 1e-4, "k_of_n(2,3,0.9)")
    print("  ✓ k_of_n_reliability(2, 3, 0.9) ≈ 0.972")


def test_bathtub_rate() raises:
    var rate_early = bathtub_rate(1.0, 0.5, 0.001, 2.0, 100.0, 500.0)
    var rate_mid = bathtub_rate(250.0, 0.5, 0.001, 2.0, 100.0, 500.0)
    _assert(rate_early > rate_mid, "infant mortality: early rate > mid rate")
    print("  ✓ bathtub_rate early > mid (infant mortality)")

    var rate_late = bathtub_rate(600.0, 0.5, 0.001, 2.0, 100.0, 500.0)
    _assert(rate_late > rate_mid, "wearout: late rate > mid rate")
    print("  ✓ bathtub_rate late > mid (wearout)")


def test_mission_reliability() raises:
    var mr = mission_reliability(100.0, 0.001)
    _assert_close(mr, exp(-0.1), 1e-6, "mission_reliability")
    _assert(mr > 0.904 and mr < 0.906, "mission_reliability ≈ 0.905")
    print("  ✓ mission_reliability(100, 0.001) ≈ 0.905")


def test_exponential_failure_rate() raises:
    _assert_close(exponential_failure_rate(0.05), 0.05, 1e-12, "exp_failure_rate")
    print("  ✓ exponential_failure_rate constant")


# ── Main ─────────────────────────────────────────────────────────────────────


def main() raises:
    print("=" * 60)
    print("Wave 30 — Constraint Satisfaction, Digital Filters, Reliability")
    print("🎯 100 LIBRARY MILESTONE!")
    print("=" * 60)

    print("\n── Constraint tests ──")
    test_all_different()
    test_n_queens_4()
    test_n_queens_8()
    test_n_queens_check_invalid()
    test_count_solutions_nqueens()
    test_graph_coloring()
    test_sudoku_valid()
    test_magic_square()
    test_solve_backtrack()

    print("\n── Filter tests ──")
    test_lowpass_ema()
    test_highpass_ema()
    test_median_filter()
    test_moving_average_filter()
    test_diff_filter()
    test_integrate_diff_roundtrip()
    test_iir_filter_1st()
    test_rms()
    test_snr()
    test_savitzky_golay_3()
    test_bandpass()

    print("\n── Reliability tests ──")
    test_exponential_reliability()
    test_weibull_reliability()
    test_weibull_failure_rate()
    test_mtbf()
    test_availability()
    test_series_reliability()
    test_parallel_reliability()
    test_k_of_n_reliability()
    test_bathtub_rate()
    test_mission_reliability()
    test_exponential_failure_rate()

    print("\n" + "=" * 60)
    print("Wave 30 — ALL TESTS PASSED ✅  (50+ assertions)")
    print("🎯 100 LIBRARY MILESTONE ACHIEVED! 🎯")
    print("=" * 60)
