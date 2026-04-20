"""Tests for Wave 50 — Signal Processing, Portfolio Allocation, Cellular Automata.
🎯 200 LIBRARY MILESTONE! 🎯
"""

from signal_processing import (
    hamming_window,
    hann_window,
    blackman_window,
    apply_window,
    peak_detect,
    zero_crossings,
    spectral_energy,
    spectral_centroid,
    spectral_flatness,
    signal_power,
)
from allocation import (
    equal_weight,
    inverse_variance,
    risk_parity_simple,
    max_sharpe_2asset,
    min_variance_2asset,
    portfolio_return,
    portfolio_variance_2asset,
    kelly_criterion,
    efficient_frontier_2asset,
    rebalance_threshold,
)
from cellular import (
    game_of_life_step,
    count_neighbors,
    elementary_ca_step,
    rule_lookup,
    run_elementary_ca,
    count_alive,
    grid_create,
    grid_randomize,
    grid_to_density,
    is_still_life,
    population_history,
)
from std.math import abs as fabs, sqrt


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error(
            "FAIL: " + msg + " | got " + String(a) + " expected " + String(b)
        )


# ── Signal Processing Tests ───────────────────────────────────────────────────


fn test_hamming_window() raises:
    print("  Testing hamming_window...")
    var w = hamming_window(5)
    _assert(len(w) == 5, "hamming_window(5) length")                    # 1
    _assert(w[2] > w[0], "hamming middle > first")                       # 2
    _assert(w[2] > w[4], "hamming middle > last")                        # 3
    _assert(w[0] > 0.0, "hamming first > 0")                            # 4
    # Symmetric
    _assert_close(w[0], w[4], 1e-10, "hamming symmetric 0,4")           # 5
    _assert_close(w[1], w[3], 1e-10, "hamming symmetric 1,3")           # 6
    # hamming(1) should be [1.0]
    var w1 = hamming_window(1)
    _assert(len(w1) == 1, "hamming_window(1) length")                   # 7
    _assert_close(w1[0], 1.0, 1e-10, "hamming_window(1) == 1.0")       # 8


fn test_hann_window() raises:
    print("  Testing hann_window...")
    var w = hann_window(4)
    _assert(len(w) == 4, "hann_window(4) length")                       # 9
    _assert_close(w[0], 0.0, 1e-10, "hann first ≈ 0")                  # 10
    _assert(w[1] > 0.0, "hann second > 0")                              # 11
    # hann(5) symmetric
    var w5 = hann_window(5)
    _assert_close(w5[0], w5[4], 1e-10, "hann symmetric 0,4")           # 12


fn test_blackman_window() raises:
    print("  Testing blackman_window...")
    var w = blackman_window(5)
    _assert(len(w) == 5, "blackman_window(5) length")                   # 13
    _assert(w[2] > w[0], "blackman middle > first")                      # 14
    _assert_close(w[0], w[4], 1e-10, "blackman symmetric")              # 15


fn test_apply_window() raises:
    print("  Testing apply_window...")
    var data = List[Float64]()
    data.append(1.0)
    data.append(2.0)
    data.append(3.0)
    var win = List[Float64]()
    win.append(0.5)
    win.append(1.0)
    win.append(0.5)
    var out = apply_window(data, win)
    _assert(len(out) == len(data), "apply_window output length")        # 16
    _assert_close(out[0], 0.5, 1e-10, "apply_window[0]")               # 17
    _assert_close(out[1], 2.0, 1e-10, "apply_window[1]")               # 18
    _assert_close(out[2], 1.5, 1e-10, "apply_window[2]")               # 19


fn test_peak_detect() raises:
    print("  Testing peak_detect...")
    var data = List[Float64]()
    data.append(0.0)
    data.append(1.0)
    data.append(0.0)
    data.append(3.0)
    data.append(0.0)
    data.append(2.0)
    data.append(0.0)
    var peaks = peak_detect(data, 0.5)
    _assert(len(peaks) == 3, "peak_detect finds 3 peaks")              # 20
    _assert(peaks[0] == 1, "peak at 1")                                 # 21
    _assert(peaks[1] == 3, "peak at 3")                                 # 22
    _assert(peaks[2] == 5, "peak at 5")                                 # 23


fn test_zero_crossings() raises:
    print("  Testing zero_crossings...")
    var data = List[Float64]()
    data.append(-1.0)
    data.append(1.0)
    data.append(-1.0)
    data.append(1.0)
    var zc = zero_crossings(data)
    _assert(len(zc) == 3, "3 zero crossings")                           # 24


fn test_spectral_energy() raises:
    print("  Testing spectral_energy...")
    var mags = List[Float64]()
    mags.append(1.0)
    mags.append(2.0)
    mags.append(3.0)
    var e = spectral_energy(mags)
    _assert(e > 0.0, "spectral_energy positive")                        # 25
    _assert_close(e, 14.0, 1e-10, "spectral_energy = 1+4+9")           # 26


fn test_spectral_centroid() raises:
    print("  Testing spectral_centroid...")
    var mags = List[Float64]()
    mags.append(1.0)
    mags.append(2.0)
    mags.append(3.0)
    mags.append(4.0)
    var sr: Float64 = 44100.0
    var c = spectral_centroid(mags, sr)
    _assert(c > 0.0, "spectral_centroid > 0")                           # 27
    _assert(c < sr / 2.0, "spectral_centroid < sr/2")                   # 28


fn test_spectral_flatness() raises:
    print("  Testing spectral_flatness...")
    # Uniform magnitudes → flatness near 1
    var flat = List[Float64]()
    flat.append(5.0)
    flat.append(5.0)
    flat.append(5.0)
    flat.append(5.0)
    var sf = spectral_flatness(flat)
    _assert(sf >= 0.0, "spectral_flatness >= 0")                        # 29
    _assert(sf <= 1.0, "spectral_flatness <= 1")                        # 30
    _assert_close(sf, 1.0, 0.01, "uniform flatness ≈ 1")               # 31


fn test_signal_power() raises:
    print("  Testing signal_power...")
    var data = List[Float64]()
    data.append(3.0)
    data.append(-3.0)
    var p = signal_power(data)
    _assert(p >= 0.0, "signal_power >= 0")                              # 32
    _assert_close(p, 9.0, 1e-10, "signal_power([3,-3]) = 9")           # 33


# ── Allocation Tests ──────────────────────────────────────────────────────────


fn test_equal_weight() raises:
    print("  Testing equal_weight...")
    var w = equal_weight(4)
    _assert(len(w) == 4, "equal_weight(4) length")                      # 34
    for i in range(4):
        _assert_close(w[i], 0.25, 1e-10, "equal_weight[" + String(i) + "]")  # 35-38


fn test_inverse_variance() raises:
    print("  Testing inverse_variance...")
    var vars = List[Float64]()
    vars.append(0.01)
    vars.append(0.04)
    var w = inverse_variance(vars)
    _assert(len(w) == 2, "inverse_variance length")                      # 39
    _assert(w[0] > w[1], "lower var → higher weight")                   # 40
    _assert_close(w[0] + w[1], 1.0, 1e-10, "weights sum to 1")         # 41


fn test_portfolio_return() raises:
    print("  Testing portfolio_return...")
    var w = List[Float64]()
    w.append(0.6)
    w.append(0.4)
    var r = List[Float64]()
    r.append(0.1)
    r.append(0.05)
    var pr = portfolio_return(w, r)
    _assert_close(pr, 0.08, 1e-10, "portfolio_return ≈ 0.08")          # 42


fn test_kelly_criterion() raises:
    print("  Testing kelly_criterion...")
    var k = kelly_criterion(0.6, 2.0)
    _assert(k > 0.0, "kelly positive")                                  # 43
    _assert(k < 1.0, "kelly < 1")                                       # 44
    # kelly = 0.6 - 0.4/2 = 0.6 - 0.2 = 0.4
    _assert_close(k, 0.4, 1e-10, "kelly = 0.4")                        # 45


fn test_min_variance_2asset() raises:
    print("  Testing min_variance_2asset...")
    var w = min_variance_2asset(0.2, 0.3, 0.5)
    _assert_close(w[0] + w[1], 1.0, 1e-10, "min_var weights sum to 1") # 46
    _assert(w[0] >= 0.0, "min_var w1 >= 0")                            # 47
    _assert(w[1] >= 0.0, "min_var w2 >= 0")                            # 48


fn test_efficient_frontier() raises:
    print("  Testing efficient_frontier_2asset...")
    var ef = efficient_frontier_2asset(0.10, 0.05, 0.20, 0.15, 0.3, 10)
    _assert(len(ef) == 10, "ef has n_points entries")                    # 49
    # Check risk generally varies (not all same)
    _assert(ef[0][1] != ef[9][1], "risk varies across frontier")        # 50


fn test_rebalance_threshold() raises:
    print("  Testing rebalance_threshold...")
    var curr = List[Float64]()
    curr.append(0.55)
    curr.append(0.45)
    var target = List[Float64]()
    target.append(0.50)
    target.append(0.50)
    _assert(
        rebalance_threshold(curr, target, 0.03),
        "rebalance True when drifted > 3%",
    )                                                                    # 51
    _assert(
        not rebalance_threshold(curr, target, 0.10),
        "rebalance False when drift < 10%",
    )                                                                    # 52


fn test_risk_parity() raises:
    print("  Testing risk_parity_simple...")
    var vars = List[Float64]()
    vars.append(0.01)
    vars.append(0.04)
    vars.append(0.09)
    var w = risk_parity_simple(vars)
    _assert(len(w) == 3, "risk_parity length")                          # 53
    var total: Float64 = 0.0
    for i in range(3):
        total += w[i]
    _assert_close(total, 1.0, 1e-10, "risk_parity sums to 1")          # 54
    # Lower variance should get higher weight
    _assert(w[0] > w[1], "risk_parity: lower var → higher weight")      # 55


fn test_portfolio_variance_2asset() raises:
    print("  Testing portfolio_variance_2asset...")
    var v = portfolio_variance_2asset(0.5, 0.2, 0.2, 1.0)
    # With perfect correlation and equal weight: var = (0.5*0.2 + 0.5*0.2)^2 = 0.04
    _assert_close(v, 0.04, 1e-10, "portfolio_var perfect corr")         # 56


# ── Cellular Automata Tests ───────────────────────────────────────────────────


fn test_grid_create() raises:
    print("  Testing grid_create...")
    var g = grid_create(3, 3)
    _assert(len(g) == 3, "grid_create rows")                            # 57
    _assert(len(g[0]) == 3, "grid_create cols")                         # 58
    _assert(count_alive(g) == 0, "grid_create all zeros")               # 59


fn test_count_neighbors() raises:
    print("  Testing count_neighbors...")
    # All-ones 3x3 grid, center should have 8 neighbors
    var g = List[List[Int]]()
    for _ in range(3):
        var row = List[Int]()
        for _ in range(3):
            row.append(1)
        g.append(row^)
    var n = count_neighbors(g, 1, 1, 3, 3)
    _assert(n == 8, "center of all-ones = 8 neighbors")                 # 60
    # Corner should have 3 neighbors
    var c = count_neighbors(g, 0, 0, 3, 3)
    _assert(c == 3, "corner of all-ones = 3 neighbors")                 # 61


fn test_game_of_life_block() raises:
    print("  Testing game_of_life_step (block still life)...")
    # Block: 2x2 alive in center of 4x4 grid
    var g = grid_create(4, 4)
    g[1][1] = 1
    g[1][2] = 1
    g[2][1] = 1
    g[2][2] = 1
    var next_g = game_of_life_step(g, 4, 4)
    _assert(next_g[1][1] == 1, "block survives [1][1]")                 # 62
    _assert(next_g[1][2] == 1, "block survives [1][2]")                 # 63
    _assert(next_g[2][1] == 1, "block survives [2][1]")                 # 64
    _assert(next_g[2][2] == 1, "block survives [2][2]")                 # 65


fn test_is_still_life() raises:
    print("  Testing is_still_life...")
    # Block is a still life
    var g = grid_create(4, 4)
    g[1][1] = 1
    g[1][2] = 1
    g[2][1] = 1
    g[2][2] = 1
    _assert(is_still_life(g, 4, 4), "block is still life")              # 66
    # Single cell is not a still life (will die)
    var g2 = grid_create(3, 3)
    g2[1][1] = 1
    _assert(not is_still_life(g2, 3, 3), "single cell not still life")  # 67


fn test_rule_lookup() raises:
    print("  Testing rule_lookup...")
    # Rule 30: binary 00011110
    # Neighborhood (1,1,0) = index 6, bit 6 of 30 = 0
    # 30 = 0b00011110
    # idx=0→0, 1→1, 2→1, 3→1, 4→1, 5→0, 6→0, 7→0
    var r = rule_lookup(1, 1, 0, 30)
    _assert(r == 0, "rule_lookup(1,1,0,30) = 0")                        # 68
    # Neighborhood (0,0,1) = index 1, bit 1 of 30 = 1
    var r2 = rule_lookup(0, 0, 1, 30)
    _assert(r2 == 1, "rule_lookup(0,0,1,30) = 1")                       # 69


fn test_elementary_ca_step() raises:
    print("  Testing elementary_ca_step (Rule 30)...")
    # Start with single cell in center
    var state = List[Int]()
    for _ in range(7):
        state.append(0)
    state[3] = 1  # center
    var next_s = elementary_ca_step(state, 30)
    _assert(len(next_s) == 7, "elementary_ca_step length preserved")    # 70
    # Rule 30 from [0,0,0,1,0,0,0] → [0,0,1,1,1,0,0]
    _assert(next_s[2] == 1, "Rule 30 step: pos 2")                     # 71
    _assert(next_s[3] == 1, "Rule 30 step: pos 3")                     # 72
    _assert(next_s[4] == 1, "Rule 30 step: pos 4")                     # 73


fn test_run_elementary_ca() raises:
    print("  Testing run_elementary_ca...")
    var init = List[Int]()
    for _ in range(5):
        init.append(0)
    init[2] = 1
    var hist = run_elementary_ca(init, 30, 3)
    _assert(len(hist) == 4, "run_elementary_ca: steps+1 rows")          # 74
    _assert(len(hist[0]) == 5, "run_elementary_ca: width preserved")    # 75


fn test_grid_to_density() raises:
    print("  Testing grid_to_density...")
    # All-ones 2x2
    var g = List[List[Int]]()
    for _ in range(2):
        var row = List[Int]()
        for _ in range(2):
            row.append(1)
        g.append(row^)
    _assert_close(grid_to_density(g), 1.0, 1e-10, "all-ones density=1")  # 76
    # All-zeros
    var g0 = grid_create(2, 2)
    _assert_close(grid_to_density(g0), 0.0, 1e-10, "all-zeros density=0")  # 77


fn test_population_history() raises:
    print("  Testing population_history...")
    # Block still life: population should be constant
    var g = grid_create(4, 4)
    g[1][1] = 1
    g[1][2] = 1
    g[2][1] = 1
    g[2][2] = 1
    var hist = population_history(g, 4, 4, 5)
    _assert(len(hist) == 6, "population_history length == steps+1")      # 78
    for i in range(6):
        _assert(hist[i] == 4, "block population constant at 4")         # 79-84


fn test_max_sharpe_2asset() raises:
    print("  Testing max_sharpe_2asset...")
    var w = max_sharpe_2asset(0.12, 0.08, 0.20, 0.15, 0.3, 0.03)
    _assert_close(w[0] + w[1], 1.0, 1e-10, "max_sharpe weights sum 1") # 85
    _assert(w[0] >= 0.0, "max_sharpe w1 >= 0")                         # 86
    _assert(w[1] >= 0.0, "max_sharpe w2 >= 0")                         # 87


# ── Main ──────────────────────────────────────────────────────────────────────


fn main() raises:
    print("")
    print("=" * 70)
    print("🎯🎯🎯  200 LIBRARY MILESTONE — WAVE 50  🎯🎯🎯")
    print("=" * 70)
    print("  Signal Processing + Portfolio Allocation + Cellular Automata")
    print("  This wave brings us to 200 Mojo libraries! 🏆")
    print("=" * 70)
    print("")

    print("── Signal Processing ──")
    test_hamming_window()
    test_hann_window()
    test_blackman_window()
    test_apply_window()
    test_peak_detect()
    test_zero_crossings()
    test_spectral_energy()
    test_spectral_centroid()
    test_spectral_flatness()
    test_signal_power()

    print("── Portfolio Allocation ──")
    test_equal_weight()
    test_inverse_variance()
    test_portfolio_return()
    test_kelly_criterion()
    test_min_variance_2asset()
    test_efficient_frontier()
    test_rebalance_threshold()
    test_risk_parity()
    test_portfolio_variance_2asset()
    test_max_sharpe_2asset()

    print("── Cellular Automata ──")
    test_grid_create()
    test_count_neighbors()
    test_game_of_life_block()
    test_is_still_life()
    test_rule_lookup()
    test_elementary_ca_step()
    test_run_elementary_ca()
    test_grid_to_density()
    test_population_history()
    test_max_sharpe_2asset()

    print("")
    print("=" * 70)
    print("🎯  ALL WAVE 50 TESTS PASSED — 200 LIBRARY MILESTONE ACHIEVED!  🎯")
    print("=" * 70)
    print("")
