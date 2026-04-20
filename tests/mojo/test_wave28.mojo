"""Tests for Wave 28 — Fuzzy Logic, Game Theory, Huffman Coding."""

from fuzzy_logic import (
    triangular_mf,
    trapezoidal_mf,
    gaussian_mf,
    fuzzy_and,
    fuzzy_or,
    fuzzy_not,
    defuzzify_centroid,
    defuzzify_bisector,
    defuzzify_mom,
    fuzzy_rule_eval,
    alpha_cut,
)
from game_theory import (
    nash_2x2,
    minimax_value,
    dominated_strategy_check,
    expected_payoff,
    prisoners_dilemma_payoff,
    iterated_pd,
    shapley_value_3player,
    pareto_optimal_outcomes,
)
from compression.huffman import (
    HuffmanNode,
    frequency_count,
    build_huffman_tree,
    generate_codes,
    huffman_encode,
    huffman_decode,
    compression_ratio_huffman,
    avg_code_length,
)
from std.math import abs as fabs


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


fn _assert_eq(a: Int, b: Int, msg: String) raises:
    if a != b:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


fn _assert_eq_f(a: Float64, b: Float64, msg: String) raises:
    if fabs(a - b) > 1e-12:
        raise Error("FAIL: " + msg + " | got " + String(a) + " expected " + String(b))


# ── Fuzzy Logic Tests ─────────────────────────────────────────────────────────


fn test_triangular_mf() raises:
    print("  test_triangular_mf...")
    # 1: Peak at b
    _assert_eq_f(triangular_mf(5.0, 0.0, 5.0, 10.0), 1.0, "tri peak")
    # 2: Left edge
    _assert_eq_f(triangular_mf(0.0, 0.0, 5.0, 10.0), 0.0, "tri left edge")
    # 3: Right edge
    _assert_eq_f(triangular_mf(10.0, 0.0, 5.0, 10.0), 0.0, "tri right edge")
    # 4: Midway ascending
    _assert_close(triangular_mf(2.5, 0.0, 5.0, 10.0), 0.5, 1e-9, "tri midway up")
    # 5: Midway descending
    _assert_close(triangular_mf(7.5, 0.0, 5.0, 10.0), 0.5, 1e-9, "tri midway down")
    # 6: Outside left
    _assert_eq_f(triangular_mf(-1.0, 0.0, 5.0, 10.0), 0.0, "tri outside left")
    # 7: Outside right
    _assert_eq_f(triangular_mf(11.0, 0.0, 5.0, 10.0), 0.0, "tri outside right")
    print("    PASS")


fn test_trapezoidal_mf() raises:
    print("  test_trapezoidal_mf...")
    # 8: Flat region
    _assert_eq_f(trapezoidal_mf(5.0, 0.0, 3.0, 7.0, 10.0), 1.0, "trap flat")
    # 9: Rising slope
    _assert_close(trapezoidal_mf(1.5, 0.0, 3.0, 7.0, 10.0), 0.5, 1e-9, "trap rise")
    # 10: Falling slope
    _assert_close(trapezoidal_mf(8.5, 0.0, 3.0, 7.0, 10.0), 0.5, 1e-9, "trap fall")
    # 11: Outside
    _assert_eq_f(trapezoidal_mf(-1.0, 0.0, 3.0, 7.0, 10.0), 0.0, "trap outside")
    print("    PASS")


fn test_gaussian_mf() raises:
    print("  test_gaussian_mf...")
    # 12: Center
    _assert_close(gaussian_mf(0.0, 0.0, 1.0), 1.0, 1e-9, "gauss center")
    # 13: 1 sigma away
    _assert_close(gaussian_mf(1.0, 0.0, 1.0), 0.6065306597, 1e-4, "gauss 1sigma")
    # 14: Far away is near zero
    _assert(gaussian_mf(10.0, 0.0, 1.0) < 0.001, "gauss far away")
    print("    PASS")


fn test_fuzzy_operators() raises:
    print("  test_fuzzy_operators...")
    # 15: fuzzy_and
    _assert_eq_f(fuzzy_and(0.3, 0.7), 0.3, "fuzzy_and(0.3,0.7)")
    # 16: fuzzy_or
    _assert_eq_f(fuzzy_or(0.3, 0.7), 0.7, "fuzzy_or(0.3,0.7)")
    # 17: fuzzy_not
    _assert_close(fuzzy_not(0.3), 0.7, 1e-9, "fuzzy_not(0.3)")
    # 18: fuzzy_not(0)
    _assert_eq_f(fuzzy_not(0.0), 1.0, "fuzzy_not(0)")
    # 19: fuzzy_not(1)
    _assert_eq_f(fuzzy_not(1.0), 0.0, "fuzzy_not(1)")
    print("    PASS")


fn test_defuzzification() raises:
    print("  test_defuzzification...")
    var x = List[Float64]()
    var mu = List[Float64]()
    # Triangle-like: [1,2,3,4,5] with mu [0, 0.5, 1, 0.5, 0]
    x.append(1.0); x.append(2.0); x.append(3.0); x.append(4.0); x.append(5.0)
    mu.append(0.0); mu.append(0.5); mu.append(1.0); mu.append(0.5); mu.append(0.0)

    # 20: Centroid should be at 3.0 (symmetric)
    var c = defuzzify_centroid(x, mu)
    _assert_close(c, 3.0, 1e-9, "centroid symmetric")

    # 21: Centroid between min and max x
    _assert(c >= 1.0 and c <= 5.0, "centroid in range")

    # 22: Bisector
    var b = defuzzify_bisector(x, mu)
    _assert(b >= 1.0 and b <= 5.0, "bisector in range")

    # 23: MoM should be 3.0 (max at x=3)
    var m = defuzzify_mom(x, mu)
    _assert_close(m, 3.0, 1e-9, "mom at peak")

    # 24: MoM with flat top
    var mu2 = List[Float64]()
    mu2.append(0.0); mu2.append(1.0); mu2.append(1.0); mu2.append(1.0); mu2.append(0.0)
    var m2 = defuzzify_mom(x, mu2)
    _assert_close(m2, 3.0, 1e-9, "mom flat top center")
    print("    PASS")


fn test_fuzzy_rule_eval() raises:
    print("  test_fuzzy_rule_eval...")
    var inputs = List[Float64]()
    inputs.append(0.3); inputs.append(0.7); inputs.append(0.5)
    # 25: AND rule
    _assert_eq_f(fuzzy_rule_eval(inputs, 0), 0.3, "rule AND")
    # 26: OR rule
    _assert_eq_f(fuzzy_rule_eval(inputs, 1), 0.7, "rule OR")
    print("    PASS")


fn test_alpha_cut() raises:
    print("  test_alpha_cut...")
    var x = List[Float64]()
    var mu = List[Float64]()
    x.append(1.0); x.append(2.0); x.append(3.0); x.append(4.0); x.append(5.0)
    mu.append(0.0); mu.append(0.5); mu.append(1.0); mu.append(0.5); mu.append(0.0)

    # 27: Alpha=0.5 should include x=2,3,4
    var cut = alpha_cut(x, mu, 0.5)
    _assert_eq(len(cut), 3, "alpha_cut 0.5 count")

    # 28: Alpha=1.0 should include only x=3
    var cut2 = alpha_cut(x, mu, 1.0)
    _assert_eq(len(cut2), 1, "alpha_cut 1.0 count")
    _assert_close(cut2[0], 3.0, 1e-9, "alpha_cut 1.0 value")
    print("    PASS")


# ── Game Theory Tests ─────────────────────────────────────────────────────────


fn test_prisoners_dilemma() raises:
    print("  test_prisoners_dilemma...")
    # 30: CC = (3,3)
    var cc = prisoners_dilemma_payoff(True, True)
    _assert_eq_f(cc[0], 3.0, "PD CC p1")
    _assert_eq_f(cc[1], 3.0, "PD CC p2")

    # 32: DC = (5,0)
    var dc = prisoners_dilemma_payoff(False, True)
    _assert_eq_f(dc[0], 5.0, "PD DC p1")
    _assert_eq_f(dc[1], 0.0, "PD DC p2")

    # 34: CD = (0,5)
    var cd = prisoners_dilemma_payoff(True, False)
    _assert_eq_f(cd[0], 0.0, "PD CD p1")
    _assert_eq_f(cd[1], 5.0, "PD CD p2")

    # 36: DD = (1,1)
    var dd = prisoners_dilemma_payoff(False, False)
    _assert_eq_f(dd[0], 1.0, "PD DD p1")
    _assert_eq_f(dd[1], 1.0, "PD DD p2")
    print("    PASS")


fn test_iterated_pd() raises:
    print("  test_iterated_pd...")
    # 38: Both cooperate → (30, 30) over 10 rounds
    var r1 = iterated_pd(0, 0, 10)
    _assert_close(r1[0], 30.0, 1e-9, "ipd coop-coop p1")
    _assert_close(r1[1], 30.0, 1e-9, "ipd coop-coop p2")

    # 40: Both defect → (10, 10)
    var r2 = iterated_pd(1, 1, 10)
    _assert_close(r2[0], 10.0, 1e-9, "ipd defect-defect p1")
    _assert_close(r2[1], 10.0, 1e-9, "ipd defect-defect p2")

    # 42: TFT vs TFT → cooperates all rounds → (30, 30)
    var r3 = iterated_pd(2, 2, 10)
    _assert_close(r3[0], 30.0, 1e-9, "ipd tft-tft p1")
    _assert_close(r3[1], 30.0, 1e-9, "ipd tft-tft p2")
    print("    PASS")


fn test_nash_2x2() raises:
    print("  test_nash_2x2...")
    # Matching pennies: A=[[1,-1],[-1,1]], B=[[-1,1],[1,-1]]
    var pa = List[List[Float64]]()
    var r0a = List[Float64](); r0a.append(1.0); r0a.append(-1.0)
    var r1a = List[Float64](); r1a.append(-1.0); r1a.append(1.0)
    pa.append(r0a^); pa.append(r1a^)

    var pb = List[List[Float64]]()
    var r0b = List[Float64](); r0b.append(-1.0); r0b.append(1.0)
    var r1b = List[Float64](); r1b.append(1.0); r1b.append(-1.0)
    pb.append(r0b^); pb.append(r1b^)

    var nash = nash_2x2(pa, pb)
    # 44: Both probs should be 0.5 for matching pennies
    _assert_close(nash[0], 0.5, 1e-9, "nash p1 = 0.5")
    _assert_close(nash[1], 0.5, 1e-9, "nash p2 = 0.5")

    # 46: Probabilities in [0,1]
    _assert(nash[0] >= 0.0 and nash[0] <= 1.0, "nash p1 valid")
    _assert(nash[1] >= 0.0 and nash[1] <= 1.0, "nash p2 valid")
    print("    PASS")


fn test_minimax() raises:
    print("  test_minimax...")
    var payoff = List[List[Float64]]()
    var r0 = List[Float64](); r0.append(3.0); r0.append(-2.0)
    var r1 = List[Float64](); r1.append(-1.0); r1.append(4.0)
    payoff.append(r0^); payoff.append(r1^)

    var mm = minimax_value(payoff)
    # 48: Row 0 min = -2, Row 1 min = -1, maximin = -1
    _assert_close(mm, -1.0, 1e-9, "minimax value")
    print("    PASS")


fn test_dominated_strategy() raises:
    print("  test_dominated_strategy...")
    var payoff = List[List[Float64]]()
    var r0 = List[Float64](); r0.append(1.0); r0.append(2.0)
    var r1 = List[Float64](); r1.append(3.0); r1.append(4.0)
    payoff.append(r0^); payoff.append(r1^)

    var dom = dominated_strategy_check(payoff)
    # 49: Row 0 is dominated by Row 1
    _assert(dom[0], "row 0 dominated")
    # 50: Row 1 is not dominated
    _assert(not dom[1], "row 1 not dominated")
    print("    PASS")


fn test_expected_payoff() raises:
    print("  test_expected_payoff...")
    var payoff = List[List[Float64]]()
    var r0 = List[Float64](); r0.append(4.0); r0.append(0.0)
    var r1 = List[Float64](); r1.append(0.0); r1.append(4.0)
    payoff.append(r0^); payoff.append(r1^)

    var pr = List[Float64](); pr.append(0.5); pr.append(0.5)
    var pc = List[Float64](); pc.append(0.5); pc.append(0.5)
    var ep = expected_payoff(payoff, pr, pc)
    # 51: Expected = 0.5*0.5*4 + 0.5*0.5*0 + 0.5*0.5*0 + 0.5*0.5*4 = 2.0
    _assert_close(ep, 2.0, 1e-9, "expected payoff")
    print("    PASS")


fn test_shapley_value() raises:
    print("  test_shapley_value...")
    # Simple majority game: coalition wins if ≥ 2 players
    var v = List[Float64]()
    v.append(0.0)  # v({})
    v.append(0.0)  # v({1})
    v.append(0.0)  # v({2})
    v.append(1.0)  # v({1,2})
    v.append(0.0)  # v({3})
    v.append(1.0)  # v({1,3})
    v.append(1.0)  # v({2,3})
    v.append(1.0)  # v({1,2,3})

    var phi = shapley_value_3player(v)
    # 52: All players equal → each gets 1/3
    _assert_close(phi[0], 1.0 / 3.0, 1e-9, "shapley p1")
    _assert_close(phi[1], 1.0 / 3.0, 1e-9, "shapley p2")
    _assert_close(phi[2], 1.0 / 3.0, 1e-9, "shapley p3")
    # 55: Sum equals v(grand coalition)
    _assert_close(phi[0] + phi[1] + phi[2], 1.0, 1e-9, "shapley sum")
    print("    PASS")


fn test_pareto_optimal() raises:
    print("  test_pareto_optimal...")
    var pa = List[Float64]()
    var pb = List[Float64]()
    # Outcomes: (3,3), (0,5), (5,0), (1,1)
    pa.append(3.0); pa.append(0.0); pa.append(5.0); pa.append(1.0)
    pb.append(3.0); pb.append(5.0); pb.append(0.0); pb.append(1.0)

    var pareto = pareto_optimal_outcomes(pa, pb)
    # 56: At least one is Pareto optimal
    var any_optimal = False
    for i in range(len(pareto)):
        if pareto[i]:
            any_optimal = True
            break
    _assert(any_optimal, "at least one pareto optimal")

    # 57: (1,1) is dominated by (3,3) so not Pareto optimal
    _assert(not pareto[3], "(1,1) not pareto optimal")

    # 58: (3,3) is Pareto optimal
    _assert(pareto[0], "(3,3) is pareto optimal")
    print("    PASS")


# ── Huffman Tests ─────────────────────────────────────────────────────────────


fn test_frequency_count() raises:
    print("  test_frequency_count...")
    var data = List[Int]()
    data.append(1); data.append(1); data.append(2); data.append(2); data.append(2); data.append(3)

    var freqs = frequency_count(data)
    # 59: 3 unique symbols
    _assert_eq(len(freqs), 3, "freq count 3 symbols")

    # 60: Sorted ascending by count — first is symbol 3 (count 1)
    _assert_eq(freqs[0][1], 1, "freq min count = 1")
    # 61: Last is symbol 2 (count 3)
    _assert_eq(freqs[2][1], 3, "freq max count = 3")

    # Check symbols
    # 62: Find symbol 1 with count 2
    var found_1 = False
    for i in range(len(freqs)):
        if freqs[i][0] == 1 and freqs[i][1] == 2:
            found_1 = True
            break
    _assert(found_1, "symbol 1 count 2")
    print("    PASS")


fn test_build_huffman_tree() raises:
    print("  test_build_huffman_tree...")
    var data = List[Int]()
    data.append(1); data.append(1); data.append(2); data.append(2); data.append(2); data.append(3)

    var freqs = frequency_count(data)
    var tree = build_huffman_tree(freqs)

    # 63: For n=3 symbols, tree should have 2n-1 = 5 nodes
    _assert_eq(len(tree), 5, "tree has 2n-1 nodes")

    # 64: Root is last element
    var root = tree[len(tree) - 1].copy()
    _assert_eq(root.symbol, -1, "root is internal node")

    # 65: Root freq = total freq = 6
    _assert_eq(root.freq, 6, "root freq = total")
    print("    PASS")


fn test_generate_codes() raises:
    print("  test_generate_codes...")
    var data = List[Int]()
    data.append(1); data.append(1); data.append(2); data.append(2); data.append(2); data.append(3)

    var freqs = frequency_count(data)
    var tree = build_huffman_tree(freqs)
    var codes = generate_codes(tree)

    # 66: One code per symbol (3 symbols)
    _assert_eq(len(codes), 3, "3 codes generated")

    # 67: Most frequent symbol (2) should have shortest or equal code
    var code_len_2 = 0
    var max_code_len = 0
    for i in range(len(codes)):
        if codes[i][0] == 2:
            code_len_2 = codes[i][1]
        if codes[i][1] > max_code_len:
            max_code_len = codes[i][1]
    _assert(code_len_2 <= max_code_len, "most frequent has short code")
    print("    PASS")


fn test_huffman_roundtrip() raises:
    print("  test_huffman_roundtrip...")
    var data = List[Int]()
    data.append(1); data.append(1); data.append(2); data.append(2); data.append(2); data.append(3)

    var freqs = frequency_count(data)
    var tree = build_huffman_tree(freqs)
    var encoded = huffman_encode(data)

    # 68: Encoded is non-empty
    _assert(len(encoded) > 0, "encoded non-empty")

    # Decode
    var decoded = huffman_decode(encoded, tree)

    # 69: Decoded length matches original
    _assert_eq(len(decoded), len(data), "decoded length matches")

    # 70-75: Each element matches
    for i in range(len(data)):
        _assert_eq(decoded[i], data[i], "roundtrip elem " + String(i))
    print("    PASS")


fn test_huffman_compression() raises:
    print("  test_huffman_compression...")
    # Highly compressible data: lots of repeats
    var data = List[Int]()
    for _ in range(100):
        data.append(1)
    for _ in range(10):
        data.append(2)
    for _ in range(5):
        data.append(3)

    var encoded = huffman_encode(data)
    var original_bits = len(data) * 8

    # 76: Encoded bits < original bits
    _assert(len(encoded) < original_bits, "compression: encoded < original bits")

    # 77: Compression ratio > 1.0
    var ratio = compression_ratio_huffman(len(data), len(encoded))
    _assert(ratio > 1.0, "compression ratio > 1.0")
    print("    PASS")


fn test_avg_code_length() raises:
    print("  test_avg_code_length...")
    var data = List[Int]()
    data.append(1); data.append(1); data.append(2); data.append(2); data.append(2); data.append(3)

    var freqs = frequency_count(data)
    var tree = build_huffman_tree(freqs)
    var codes = generate_codes(tree)
    var acl = avg_code_length(freqs, codes)

    # 78: Average code length > 0
    _assert(acl > 0.0, "avg code length > 0")

    # 79: Average code length <= max possible (number of symbols - 1 for binary)
    _assert(acl <= 3.0, "avg code length reasonable")
    print("    PASS")


fn test_compression_ratio_edge() raises:
    print("  test_compression_ratio_edge...")
    # 80: Zero encoded bits → 0.0
    _assert_eq_f(compression_ratio_huffman(100, 0), 0.0, "ratio with 0 bits")
    # 81: Equal bits → ratio based on 8x expansion
    _assert_close(compression_ratio_huffman(10, 80), 1.0, 1e-9, "ratio 10 bytes 80 bits")
    print("    PASS")


# ── Main ──────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 28 Tests ===")

    print("\n--- Fuzzy Logic ---")
    test_triangular_mf()
    test_trapezoidal_mf()
    test_gaussian_mf()
    test_fuzzy_operators()
    test_defuzzification()
    test_fuzzy_rule_eval()
    test_alpha_cut()

    print("\n--- Game Theory ---")
    test_prisoners_dilemma()
    test_iterated_pd()
    test_nash_2x2()
    test_minimax()
    test_dominated_strategy()
    test_expected_payoff()
    test_shapley_value()
    test_pareto_optimal()

    print("\n--- Huffman Coding ---")
    test_frequency_count()
    test_build_huffman_tree()
    test_generate_codes()
    test_huffman_roundtrip()
    test_huffman_compression()
    test_avg_code_length()
    test_compression_ratio_edge()

    print("\n=== All Wave 28 tests passed! ===")
