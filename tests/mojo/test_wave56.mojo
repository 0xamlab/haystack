"""Tests for Wave 56 — Category Theory, Quantum Computing, Economic Indicators."""

from category_theory import (
    map_list_fn,
    filter_fn,
    fold_left,
    fold_right,
    compose,
    zip_with,
    scan_left,
    take_while,
    drop_while,
    flat_map,
)
from quantum import (
    qubit_zero,
    qubit_one,
    hadamard,
    pauli_x,
    pauli_z,
    phase_gate,
    measure_probability,
    qubit_norm,
    bell_state,
    expectation_z,
    bloch_coords,
)
from economic_indicators import (
    gdp_growth,
    inflation_rate,
    unemployment_rate,
    real_gdp,
    gini_coefficient,
    phillips_curve,
    okuns_law,
    velocity_of_money,
    fisher_equation,
    trade_balance,
    gdp_per_capita,
    purchasing_power_parity,
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




# ── Category Theory Tests ─────────────────────────────────────────────────────


fn test_map_list_fn() raises:
    print("  test_map_list_fn ...")
    # op=0: double
    var d = List[Float64]()
    d.append(1.0)
    d.append(2.0)
    d.append(3.0)
    var r = map_list_fn(d, 0)
    _assert(len(r) == 3, "map double length")                          # 1
    _assert_close(r[0], 2.0, 1e-9, "map double [0]")                  # 2
    _assert_close(r[1], 4.0, 1e-9, "map double [1]")                  # 3
    _assert_close(r[2], 6.0, 1e-9, "map double [2]")                  # 4

    # op=1: square
    var sq = map_list_fn(d, 1)
    _assert_close(sq[0], 1.0, 1e-9, "map square [0]")                 # 5
    _assert_close(sq[1], 4.0, 1e-9, "map square [1]")                 # 6
    _assert_close(sq[2], 9.0, 1e-9, "map square [2]")                 # 7

    # op=2: negate
    var neg = map_list_fn(d, 2)
    _assert_close(neg[0], -1.0, 1e-9, "map negate [0]")               # 8

    # op=3: increment
    var inc = map_list_fn(d, 3)
    _assert_close(inc[0], 2.0, 1e-9, "map increment [0]")             # 9

    # op=4: abs
    var ab = List[Float64]()
    ab.append(-5.0)
    ab.append(3.0)
    var abr = map_list_fn(ab, 4)
    _assert_close(abr[0], 5.0, 1e-9, "map abs [0]")                   # 10
    print("    PASSED")


fn test_filter_fn() raises:
    print("  test_filter_fn ...")
    var d = List[Float64]()
    d.append(1.0)
    d.append(-2.0)
    d.append(3.0)
    d.append(-4.0)

    # pred=0: greater than 0
    var r = filter_fn(d, 0, 0.0)
    _assert(len(r) == 2, "filter >0 length")                          # 11
    _assert_close(r[0], 1.0, 1e-9, "filter >0 [0]")                   # 12
    _assert_close(r[1], 3.0, 1e-9, "filter >0 [1]")                   # 13

    # pred=1: less than 0
    var lt = filter_fn(d, 1, 0.0)
    _assert(len(lt) == 2, "filter <0 length")                         # 14

    # pred=3: nonzero
    var nz = List[Float64]()
    nz.append(0.0)
    nz.append(1.0)
    nz.append(0.0)
    nz.append(2.0)
    var nzr = filter_fn(nz, 3, 0.0)
    _assert(len(nzr) == 2, "filter nonzero length")                    # 15
    print("    PASSED")


fn test_fold_left() raises:
    print("  test_fold_left ...")
    var d = List[Float64]()
    d.append(1.0)
    d.append(2.0)
    d.append(3.0)
    d.append(4.0)

    # op=0: sum
    var s = fold_left(d, 0.0, 0)
    _assert_close(s, 10.0, 1e-9, "fold_left sum")                     # 16

    # op=1: product
    var p = fold_left(d, 1.0, 1)
    _assert_close(p, 24.0, 1e-9, "fold_left product")                 # 17

    # op=2: max
    var mx = fold_left(d, -1e9, 2)
    _assert_close(mx, 4.0, 1e-9, "fold_left max")                     # 18

    # op=3: min
    var mn = fold_left(d, 1e9, 3)
    _assert_close(mn, 1.0, 1e-9, "fold_left min")                     # 19
    print("    PASSED")


fn test_fold_right() raises:
    print("  test_fold_right ...")
    var d = List[Float64]()
    d.append(1.0)
    d.append(2.0)
    d.append(3.0)

    # For add, fold_left == fold_right
    var sl = fold_left(d, 0.0, 0)
    var sr = fold_right(d, 0.0, 0)
    _assert_close(sl, sr, 1e-9, "fold_right sum == fold_left sum")     # 20

    # For multiply, fold_left == fold_right (commutative)
    var pl = fold_left(d, 1.0, 1)
    var pr = fold_right(d, 1.0, 1)
    _assert_close(pl, pr, 1e-9, "fold_right prod == fold_left prod")   # 21
    print("    PASSED")


fn test_compose() raises:
    print("  test_compose ...")
    var d = List[Float64]()
    d.append(3.0)

    # double then square: (3*2)^2 = 36
    var ds = compose(d, 0, 1)
    _assert_close(ds[0], 36.0, 1e-9, "compose double→square")         # 22

    # square then double: 3^2 * 2 = 18
    var sd = compose(d, 1, 0)
    _assert_close(sd[0], 18.0, 1e-9, "compose square→double")         # 23

    # Verify they are different (non-commutative)
    _assert(fabs(ds[0] - sd[0]) > 1.0, "compose non-commutative")     # 24
    print("    PASSED")


fn test_zip_with() raises:
    print("  test_zip_with ...")
    var a = List[Float64]()
    a.append(1.0)
    a.append(2.0)
    var b = List[Float64]()
    b.append(3.0)
    b.append(4.0)

    # op=0: add
    var r = zip_with(a, b, 0)
    _assert(len(r) == 2, "zip_with add length")                       # 25
    _assert_close(r[0], 4.0, 1e-9, "zip_with add [0]")                # 26
    _assert_close(r[1], 6.0, 1e-9, "zip_with add [1]")                # 27

    # op=1: multiply
    var m = zip_with(a, b, 1)
    _assert_close(m[0], 3.0, 1e-9, "zip_with mul [0]")                # 28
    _assert_close(m[1], 8.0, 1e-9, "zip_with mul [1]")                # 29

    # Different lengths
    var c = List[Float64]()
    c.append(10.0)
    var short = zip_with(a, c, 0)
    _assert(len(short) == 1, "zip_with different lengths")             # 30
    print("    PASSED")


fn test_scan_left() raises:
    print("  test_scan_left ...")
    var d = List[Float64]()
    d.append(1.0)
    d.append(2.0)
    d.append(3.0)

    # cumsum with init=0
    var r = scan_left(d, 0.0, 0)
    _assert(len(r) == 4, "scan_left length n+1")                      # 31
    _assert_close(r[0], 0.0, 1e-9, "scan_left [0]")                   # 32
    _assert_close(r[1], 1.0, 1e-9, "scan_left [1]")                   # 33
    _assert_close(r[2], 3.0, 1e-9, "scan_left [2]")                   # 34
    _assert_close(r[3], 6.0, 1e-9, "scan_left [3]")                   # 35
    print("    PASSED")


fn test_take_while() raises:
    print("  test_take_while ...")
    var d = List[Float64]()
    d.append(1.0)
    d.append(2.0)
    d.append(3.0)
    d.append(0.0)
    d.append(4.0)

    # pred=0: greater than 0.0 → take [1,2,3], stop at 0
    var r = take_while(d, 0, 0.0)
    _assert(len(r) == 3, "take_while >0 length")                      # 36
    _assert_close(r[0], 1.0, 1e-9, "take_while [0]")                  # 37
    _assert_close(r[2], 3.0, 1e-9, "take_while [2]")                  # 38
    print("    PASSED")


fn test_drop_while() raises:
    print("  test_drop_while ...")
    var d = List[Float64]()
    d.append(1.0)
    d.append(2.0)
    d.append(3.0)
    d.append(0.0)
    d.append(4.0)

    # pred=0: greater than 0.0 → drop [1,2,3], keep [0,4]
    var r = drop_while(d, 0, 0.0)
    _assert(len(r) == 2, "drop_while >0 length")                      # 39
    _assert_close(r[0], 0.0, 1e-9, "drop_while [0]")                  # 40
    _assert_close(r[1], 4.0, 1e-9, "drop_while [1]")                  # 41
    print("    PASSED")


fn test_flat_map() raises:
    print("  test_flat_map ...")
    var d = List[Float64]()
    d.append(2.0)
    d.append(3.0)

    # op=0: x → [x, -x]
    var r0 = flat_map(d, 0)
    _assert(len(r0) == 4, "flat_map op=0 length")                     # 42
    _assert_close(r0[0], 2.0, 1e-9, "flat_map op=0 [0]")              # 43
    _assert_close(r0[1], -2.0, 1e-9, "flat_map op=0 [1]")             # 44

    # op=1: x → [x, x*x]
    var r1 = flat_map(d, 1)
    _assert(len(r1) == 4, "flat_map op=1 length")                     # 45
    _assert_close(r1[2], 3.0, 1e-9, "flat_map op=1 [2]")              # 46
    _assert_close(r1[3], 9.0, 1e-9, "flat_map op=1 [3]")              # 47

    # Output longer than input
    _assert(len(r0) > len(d), "flat_map output > input")               # 48
    print("    PASSED")


# ── Quantum Tests ─────────────────────────────────────────────────────────────


fn test_qubit_basics() raises:
    print("  test_qubit_basics ...")
    var q0 = qubit_zero()
    var q1 = qubit_one()

    # Norm should be 1
    _assert_close(qubit_norm(q0), 1.0, 1e-9, "qubit_zero norm")       # 49
    _assert_close(qubit_norm(q1), 1.0, 1e-9, "qubit_one norm")        # 50

    # State vectors
    _assert_close(q0[0], 1.0, 1e-9, "q0 a_re")                       # 51
    _assert_close(q0[2], 0.0, 1e-9, "q0 b_re")                       # 52
    _assert_close(q1[0], 0.0, 1e-9, "q1 a_re")                       # 53
    _assert_close(q1[2], 1.0, 1e-9, "q1 b_re")                       # 54
    print("    PASSED")


fn test_hadamard_gate() raises:
    print("  test_hadamard_gate ...")
    var q0 = qubit_zero()
    var h = hadamard(q0)

    # H|0⟩ should have equal superposition
    _assert_close(qubit_norm(h), 1.0, 1e-9, "hadamard norm")          # 55

    var probs = measure_probability(h)
    _assert_close(probs[0], 0.5, 1e-9, "H|0⟩ P(0)")                  # 56
    _assert_close(probs[1], 0.5, 1e-9, "H|0⟩ P(1)")                  # 57

    # H applied twice = identity
    var hh = hadamard(h)
    _assert_close(hh[0], 1.0, 1e-9, "H²|0⟩ a_re")                    # 58
    _assert_close(hh[2], 0.0, 1e-6, "H²|0⟩ b_re")                    # 59
    print("    PASSED")


fn test_pauli_gates() raises:
    print("  test_pauli_gates ...")
    var q0 = qubit_zero()
    var q1 = qubit_one()

    # Pauli-X: X|0⟩ = |1⟩
    var x0 = pauli_x(q0)
    _assert_close(x0[0], q1[0], 1e-9, "X|0⟩ a_re == |1⟩")           # 60
    _assert_close(x0[2], q1[2], 1e-9, "X|0⟩ b_re == |1⟩")           # 61

    # Pauli-X: X|1⟩ = |0⟩
    var x1 = pauli_x(q1)
    _assert_close(x1[0], q0[0], 1e-9, "X|1⟩ a_re == |0⟩")           # 62
    _assert_close(x1[2], q0[2], 1e-9, "X|1⟩ b_re == |0⟩")           # 63

    # Pauli-Z: Z|0⟩ = |0⟩ (no change)
    var z0 = pauli_z(q0)
    _assert_close(z0[0], 1.0, 1e-9, "Z|0⟩ a_re")                     # 64
    _assert_close(z0[2], 0.0, 1e-9, "Z|0⟩ b_re")                     # 65

    # Pauli-Z: Z|1⟩ = -|1⟩
    var z1 = pauli_z(q1)
    _assert_close(z1[2], -1.0, 1e-9, "Z|1⟩ b_re")                    # 66
    print("    PASSED")


fn test_phase_gate() raises:
    print("  test_phase_gate ...")
    var q0 = qubit_zero()
    var h = hadamard(q0)

    # Phase gate should preserve norm
    var pg = phase_gate(h, 1.5708)  # ~π/2
    _assert_close(qubit_norm(pg), 1.0, 1e-6, "phase_gate norm")       # 67

    # Phase gate on |0⟩ changes nothing (|1⟩ component is 0)
    var pg0 = phase_gate(q0, 1.0)
    _assert_close(pg0[0], 1.0, 1e-9, "phase |0⟩ unchanged a_re")     # 68
    print("    PASSED")


fn test_expectation_z() raises:
    print("  test_expectation_z ...")
    var q0 = qubit_zero()
    var q1 = qubit_one()

    _assert_close(expectation_z(q0), 1.0, 1e-9, "⟨Z⟩ |0⟩")          # 69
    _assert_close(expectation_z(q1), -1.0, 1e-9, "⟨Z⟩ |1⟩")         # 70

    # Hadamard state: ⟨Z⟩ = 0
    var h = hadamard(q0)
    _assert_close(expectation_z(h), 0.0, 1e-9, "⟨Z⟩ H|0⟩")          # 71
    print("    PASSED")


fn test_bloch_coords() raises:
    print("  test_bloch_coords ...")
    var q0 = qubit_zero()
    var bc0 = bloch_coords(q0)
    _assert_close(bc0[0], 0.0, 1e-9, "bloch |0⟩ x")                  # 72
    _assert_close(bc0[1], 0.0, 1e-9, "bloch |0⟩ y")                  # 73
    _assert_close(bc0[2], 1.0, 1e-9, "bloch |0⟩ z")                  # 74

    var q1 = qubit_one()
    var bc1 = bloch_coords(q1)
    _assert_close(bc1[2], -1.0, 1e-9, "bloch |1⟩ z")                 # 75

    # Hadamard: should be on equator (x=1, y=0, z=0)
    var h = hadamard(q0)
    var bch = bloch_coords(h)
    _assert_close(bch[0], 1.0, 1e-9, "bloch H|0⟩ x")                 # 76
    _assert_close(bch[2], 0.0, 1e-9, "bloch H|0⟩ z")                 # 77
    print("    PASSED")


fn test_bell_state() raises:
    print("  test_bell_state ...")
    var bs = bell_state()
    _assert(len(bs) == 8, "bell state length")                        # 78

    # Norm should be 1: |1/√2|² + |1/√2|² = 1
    var norm: Float64 = 0.0
    for i in range(0, 8, 2):
        norm += bs[i] * bs[i] + bs[i + 1] * bs[i + 1]
    _assert_close(norm, 1.0, 1e-9, "bell state norm")                 # 79
    print("    PASSED")


# ── Economic Indicators Tests ─────────────────────────────────────────────────


fn test_gdp_growth() raises:
    print("  test_gdp_growth ...")
    _assert_close(gdp_growth(110.0, 100.0), 0.1, 1e-9, "gdp_growth 10%")  # 80
    _assert_close(gdp_growth(100.0, 100.0), 0.0, 1e-9, "gdp_growth 0%")   # 81
    _assert_close(gdp_growth(90.0, 100.0), -0.1, 1e-9, "gdp_growth -10%") # 82
    print("    PASSED")


fn test_inflation_rate() raises:
    print("  test_inflation_rate ...")
    _assert_close(inflation_rate(105.0, 100.0), 0.05, 1e-9, "inflation 5%")  # 83
    _assert_close(inflation_rate(100.0, 100.0), 0.0, 1e-9, "inflation 0%")   # 84
    print("    PASSED")


fn test_unemployment_rate() raises:
    print("  test_unemployment_rate ...")
    _assert_close(unemployment_rate(5.0, 100.0), 0.05, 1e-9, "unemp 5%")  # 85
    _assert_close(unemployment_rate(0.0, 100.0), 0.0, 1e-9, "unemp 0%")   # 86
    print("    PASSED")


fn test_real_gdp() raises:
    print("  test_real_gdp ...")
    _assert_close(real_gdp(1000.0, 110.0), 1000.0 / 110.0 * 100.0, 1e-6, "real_gdp")  # 87
    print("    PASSED")


fn test_gini() raises:
    print("  test_gini ...")
    # Perfect equality
    var equal = List[Float64]()
    equal.append(1.0)
    equal.append(1.0)
    equal.append(1.0)
    equal.append(1.0)
    _assert_close(gini_coefficient(equal), 0.0, 1e-9, "gini equal")   # 88

    # Unequal → > 0
    var unequal = List[Float64]()
    unequal.append(1.0)
    unequal.append(2.0)
    unequal.append(3.0)
    unequal.append(100.0)
    var g = gini_coefficient(unequal)
    _assert(g > 0.0, "gini unequal > 0")                              # 89
    _assert(g < 1.0, "gini unequal < 1")                              # 90

    # More unequal has higher gini
    var very_unequal = List[Float64]()
    very_unequal.append(0.0)
    very_unequal.append(0.0)
    very_unequal.append(0.0)
    very_unequal.append(1000.0)
    var g2 = gini_coefficient(very_unequal)
    _assert(g2 > g, "more unequal → higher gini")                     # 91
    print("    PASSED")


fn test_phillips_curve() raises:
    print("  test_phillips_curve ...")
    var inf = phillips_curve(4.0, 5.0, 0.5)
    _assert_close(inf, 0.5, 1e-9, "phillips curve")                   # 92

    # At natural rate, inflation = 0
    var inf0 = phillips_curve(5.0, 5.0, 0.5)
    _assert_close(inf0, 0.0, 1e-9, "phillips at natural rate")        # 93
    print("    PASSED")


fn test_okuns_law() raises:
    print("  test_okuns_law ...")
    _assert_close(okuns_law(4.0, 2.0), 2.0, 1e-9, "okun default")     # 94
    _assert_close(okuns_law(6.0, 3.0), 2.0, 1e-9, "okun custom")      # 95
    print("    PASSED")


fn test_velocity_of_money() raises:
    print("  test_velocity_of_money ...")
    _assert_close(velocity_of_money(1000.0, 200.0), 5.0, 1e-9, "V=5")  # 96
    print("    PASSED")


fn test_fisher_equation() raises:
    print("  test_fisher_equation ...")
    _assert_close(fisher_equation(0.05, 0.02), 0.03, 1e-9, "fisher")  # 97
    _assert_close(fisher_equation(0.10, 0.04), 0.06, 1e-9, "fisher 2")# 98
    print("    PASSED")


fn test_trade_balance() raises:
    print("  test_trade_balance ...")
    _assert_close(trade_balance(100.0, 80.0), 20.0, 1e-9, "surplus")  # 99
    _assert_close(trade_balance(80.0, 100.0), -20.0, 1e-9, "deficit") # 100
    print("    PASSED")


fn test_gdp_per_capita() raises:
    print("  test_gdp_per_capita ...")
    var gpc = gdp_per_capita(1e12, 330e6)
    _assert_close(gpc, 1e12 / 330e6, 1e-2, "gdp_per_capita")         # 101
    _assert(gpc > 3000.0, "gdp_per_capita > 3000")                    # 102
    _assert(gpc < 3100.0, "gdp_per_capita < 3100")                    # 103
    print("    PASSED")


fn test_purchasing_power_parity() raises:
    print("  test_purchasing_power_parity ...")
    _assert_close(
        purchasing_power_parity(10.0, 5.0), 2.0, 1e-9, "ppp"
    )                                                                  # 104
    _assert_close(
        purchasing_power_parity(5.0, 10.0), 0.5, 1e-9, "ppp inverse"
    )                                                                  # 105
    print("    PASSED")


# ── Main ──────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 56 Tests ===")

    # Category Theory
    print("Category Theory:")
    test_map_list_fn()
    test_filter_fn()
    test_fold_left()
    test_fold_right()
    test_compose()
    test_zip_with()
    test_scan_left()
    test_take_while()
    test_drop_while()
    test_flat_map()

    # Quantum
    print("Quantum Computing:")
    test_qubit_basics()
    test_hadamard_gate()
    test_pauli_gates()
    test_phase_gate()
    test_expectation_z()
    test_bloch_coords()
    test_bell_state()

    # Economic Indicators
    print("Economic Indicators:")
    test_gdp_growth()
    test_inflation_rate()
    test_unemployment_rate()
    test_real_gdp()
    test_gini()
    test_phillips_curve()
    test_okuns_law()
    test_velocity_of_money()
    test_fisher_equation()
    test_trade_balance()
    test_gdp_per_capita()
    test_purchasing_power_parity()

    print("=== All 105 Wave 56 assertions passed! ===")
