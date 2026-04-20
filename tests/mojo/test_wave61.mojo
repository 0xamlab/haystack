"""Tests for Wave 61 — Thermodynamics, Social Networks, Chaos Theory."""

from thermodynamics import (
    ideal_gas_pressure,
    ideal_gas_volume,
    carnot_efficiency,
    entropy_change,
    heat_capacity,
    adiabatic_process,
    work_isothermal,
    stefan_boltzmann,
    thermal_conductivity_flux,
    gibbs_free_energy,
    clausius_clapeyron,
)
from social_network import (
    in_degree,
    out_degree,
    reciprocity,
    influence_spread_ic,
    local_clustering_directed,
    strongly_connected_check,
    community_label_propagation,
    network_density,
    average_path_length_estimate,
)
from chaos import (
    logistic_map,
    lorenz_step,
    lorenz_simulate,
    lyapunov_exponent_logistic,
    henon_map,
    tent_map,
    bifurcation_diagram,
    sensitivity_to_initial,
    feigenbaum_ratio,
    is_chaotic,
)
from std.math import abs as fabs, log


fn _assert(cond: Bool, msg: String) raises:
    if not cond:
        raise Error("FAIL: " + msg)


fn _assert_close(a: Float64, b: Float64, tol: Float64, msg: String) raises:
    if fabs(a - b) > tol:
        raise Error(
            "FAIL: " + msg + " | got " + String(a) + " expected " + String(b)
        )


# ── Thermodynamics tests ────────────────────────────────────────────────────


fn test_ideal_gas_pressure() raises:
    print("  test_ideal_gas_pressure...")
    # STP: 1 mol, 273.15 K, 22.4 L = 0.0224 m³ → ~101325 Pa
    var P = ideal_gas_pressure(1.0, 273.15, 0.0224)
    _assert_close(P, 101325.0, 2000.0, "ideal gas STP pressure")  # 1
    # Double moles, double pressure
    var P2 = ideal_gas_pressure(2.0, 273.15, 0.0224)
    _assert_close(P2, P * 2.0, 1.0, "double moles double pressure")  # 2
    # Zero volume guard
    var P3 = ideal_gas_pressure(1.0, 300.0, 0.0)
    _assert_close(P3, 0.0, 1e-10, "zero volume guard")  # 3
    print("    PASSED")


fn test_ideal_gas_volume() raises:
    print("  test_ideal_gas_volume...")
    var V = ideal_gas_volume(1.0, 273.15, 101325.0)
    _assert_close(V, 0.02241, 0.001, "ideal gas STP volume")  # 4
    # Zero pressure guard
    var V2 = ideal_gas_volume(1.0, 300.0, 0.0)
    _assert_close(V2, 0.0, 1e-10, "zero pressure guard")  # 5
    print("    PASSED")


fn test_carnot_efficiency() raises:
    print("  test_carnot_efficiency...")
    var eta = carnot_efficiency(500.0, 300.0)
    _assert_close(eta, 0.4, 1e-10, "carnot 500/300")  # 6
    var eta2 = carnot_efficiency(1000.0, 300.0)
    _assert_close(eta2, 0.7, 1e-10, "carnot 1000/300")  # 7
    # Same temp → 0 efficiency
    var eta3 = carnot_efficiency(300.0, 300.0)
    _assert_close(eta3, 0.0, 1e-10, "carnot same temp")  # 8
    print("    PASSED")


fn test_entropy_change() raises:
    print("  test_entropy_change...")
    var dS = entropy_change(100.0, 300.0)
    _assert_close(dS, 0.3333, 0.001, "entropy 100J/300K")  # 9
    var dS2 = entropy_change(1000.0, 500.0)
    _assert_close(dS2, 2.0, 1e-10, "entropy 1000J/500K")  # 10
    print("    PASSED")


fn test_heat_capacity() raises:
    print("  test_heat_capacity...")
    # 1 kg water, specific heat 4186, delta_T 10 K
    var Q = heat_capacity(1.0, 4186.0, 10.0)
    _assert_close(Q, 41860.0, 1e-6, "water heat capacity")  # 11
    # Zero mass
    var Q2 = heat_capacity(0.0, 4186.0, 10.0)
    _assert_close(Q2, 0.0, 1e-10, "zero mass heat")  # 12
    print("    PASSED")


fn test_adiabatic_process() raises:
    print("  test_adiabatic_process...")
    # Compress gas: V1=2, V2=1, gamma=1.4, P1=100000
    var P2 = adiabatic_process(100000.0, 2.0, 1.0, 1.4)
    _assert(P2 > 200000.0, "adiabatic compression increases pressure")  # 13
    # Same volume → same pressure
    var P3 = adiabatic_process(100000.0, 1.0, 1.0, 1.4)
    _assert_close(P3, 100000.0, 1e-6, "adiabatic same volume")  # 14
    print("    PASSED")


fn test_work_isothermal() raises:
    print("  test_work_isothermal...")
    # Expansion: V2 > V1 → positive work
    var W = work_isothermal(1.0, 300.0, 1.0, 2.0)
    _assert(W > 0.0, "isothermal expansion positive work")  # 15
    # W = nRT*ln(V2/V1) = 1*8.314*300*ln(2) ≈ 1729
    _assert_close(W, 8.314 * 300.0 * log(2.0), 1.0, "isothermal work value")  # 16
    # Compression: V2 < V1 → negative work
    var W2 = work_isothermal(1.0, 300.0, 2.0, 1.0)
    _assert(W2 < 0.0, "isothermal compression negative work")  # 17
    print("    PASSED")


fn test_stefan_boltzmann() raises:
    print("  test_stefan_boltzmann...")
    # Sun surface: T=5778K, A=1m², ε=1 → ~6.3e7 W
    var P = stefan_boltzmann(5778.0, 1.0)
    _assert_close(P, 6.32e7, 0.1e7, "solar surface power")  # 18
    # With emissivity 0.5 → half
    var P2 = stefan_boltzmann(5778.0, 1.0, 0.5)
    _assert_close(P2, P * 0.5, 1.0, "half emissivity")  # 19
    print("    PASSED")


fn test_thermal_conductivity() raises:
    print("  test_thermal_conductivity...")
    # k=200 W/(m·K), A=0.01 m², dT=100 K, dx=0.1 m → Q/t = -200*0.01*100/0.1 = -2000
    var flux = thermal_conductivity_flux(200.0, 0.01, 100.0, 0.1)
    _assert_close(flux, -2000.0, 1.0, "thermal flux")  # 20
    # Zero thickness guard
    var flux2 = thermal_conductivity_flux(200.0, 0.01, 100.0, 0.0)
    _assert_close(flux2, 0.0, 1e-10, "zero thickness guard")  # 21
    print("    PASSED")


fn test_gibbs_free_energy() raises:
    print("  test_gibbs_free_energy...")
    # G = H - TS = 100 - 298*0.1 = 70.2
    var G = gibbs_free_energy(100.0, 298.0, 0.1)
    _assert_close(G, 70.2, 0.01, "gibbs free energy")  # 22
    # Zero entropy → G = H
    var G2 = gibbs_free_energy(500.0, 300.0, 0.0)
    _assert_close(G2, 500.0, 1e-10, "gibbs zero entropy")  # 23
    print("    PASSED")


fn test_clausius_clapeyron() raises:
    print("  test_clausius_clapeyron...")
    # Water: P1=101325 Pa, T1=373.15 K, T2=383.15 K, dH_vap=40660 J/mol
    var P2 = clausius_clapeyron(101325.0, 373.15, 383.15, 40660.0)
    _assert(P2 > 101325.0, "CC: higher T → higher P")  # 24
    # Same temperature → same pressure
    var P3 = clausius_clapeyron(101325.0, 373.15, 373.15, 40660.0)
    _assert_close(P3, 101325.0, 1.0, "CC: same temp same pressure")  # 25
    print("    PASSED")


# ── Social Network tests ────────────────────────────────────────────────────


fn _make_triangle() -> List[List[Int]]:
    """Fully connected directed triangle: 0→1, 1→0, 0→2, 2→0, 1→2, 2→1."""
    var adj = List[List[Int]]()
    var n0 = List[Int]()
    n0.append(1)
    n0.append(2)
    adj.append(n0^)
    var n1 = List[Int]()
    n1.append(0)
    n1.append(2)
    adj.append(n1^)
    var n2 = List[Int]()
    n2.append(0)
    n2.append(1)
    adj.append(n2^)
    return adj^


fn _make_line() -> List[List[Int]]:
    """Line graph: 0→1→2→3."""
    var adj = List[List[Int]]()
    var n0 = List[Int]()
    n0.append(1)
    adj.append(n0^)
    var n1 = List[Int]()
    n1.append(2)
    adj.append(n1^)
    var n2 = List[Int]()
    n2.append(3)
    adj.append(n2^)
    var n3 = List[Int]()
    adj.append(n3^)
    return adj^


fn test_out_degree() raises:
    print("  test_out_degree...")
    var adj = _make_triangle()
    _assert(out_degree(adj, 0) == 2, "out_degree node 0 triangle")  # 26
    _assert(out_degree(adj, 1) == 2, "out_degree node 1 triangle")  # 27
    var line = _make_line()
    _assert(out_degree(line, 0) == 1, "out_degree node 0 line")  # 28
    _assert(out_degree(line, 3) == 0, "out_degree node 3 line")  # 29
    print("    PASSED")


fn test_in_degree() raises:
    print("  test_in_degree...")
    var adj = _make_triangle()
    _assert(in_degree(adj, 0) == 2, "in_degree node 0 triangle")  # 30
    var line = _make_line()
    _assert(in_degree(line, 0) == 0, "in_degree node 0 line")  # 31
    _assert(in_degree(line, 3) == 1, "in_degree node 3 line")  # 32
    print("    PASSED")


fn test_network_density() raises:
    print("  test_network_density...")
    # Complete directed triangle: 6 edges / (3*2) = 1.0
    var adj = _make_triangle()
    _assert_close(network_density(adj), 1.0, 1e-10, "complete graph density")  # 33
    # Line 0→1→2→3: 3 edges / (4*3) = 0.25
    var line = _make_line()
    _assert_close(network_density(line), 0.25, 1e-10, "line graph density")  # 34
    print("    PASSED")


fn test_reciprocity() raises:
    print("  test_reciprocity...")
    # Symmetric (undirected-like) → reciprocity = 1.0
    var adj = _make_triangle()
    _assert_close(reciprocity(adj), 1.0, 1e-10, "symmetric reciprocity")  # 35
    # Line graph (no reciprocated edges) → 0.0
    var line = _make_line()
    _assert_close(reciprocity(line), 0.0, 1e-10, "line reciprocity")  # 36
    print("    PASSED")


fn test_strongly_connected() raises:
    print("  test_strongly_connected...")
    var adj = _make_triangle()
    _assert(strongly_connected_check(adj), "triangle is strongly connected")  # 37
    var line = _make_line()
    _assert(not strongly_connected_check(line), "line not strongly connected")  # 38
    print("    PASSED")


fn test_community_labels() raises:
    print("  test_community_labels...")
    var adj = _make_triangle()
    var labels = community_label_propagation(adj, 10)
    _assert(len(labels) == 3, "labels length matches nodes")  # 39
    # In a complete graph all nodes should converge to same community
    _assert(labels[0] == labels[1], "triangle same community 0-1")  # 40
    _assert(labels[1] == labels[2], "triangle same community 1-2")  # 41
    print("    PASSED")


fn test_influence_spread() raises:
    print("  test_influence_spread...")
    var adj = _make_triangle()
    var seeds = List[Int]()
    seeds.append(0)
    var spread = influence_spread_ic(adj, seeds, 1.0, 50)
    # With p=1.0, all nodes should be activated from any seed
    _assert_close(spread, 3.0, 0.1, "full spread p=1.0")  # 42
    # Spread must be >= seed count
    var seeds2 = List[Int]()
    seeds2.append(0)
    seeds2.append(1)
    var spread2 = influence_spread_ic(adj, seeds2, 0.0, 50)
    _assert(spread2 >= 2.0, "spread >= seeds count")  # 43
    print("    PASSED")


fn test_local_clustering() raises:
    print("  test_local_clustering...")
    var adj = _make_triangle()
    var cc = local_clustering_directed(adj, 0)
    _assert_close(cc, 1.0, 1e-10, "triangle clustering = 1")  # 44
    print("    PASSED")


fn test_average_path_length() raises:
    print("  test_average_path_length...")
    var adj = _make_triangle()
    var apl = average_path_length_estimate(adj, 3)
    _assert(apl > 0.0, "avg path length positive")  # 45
    _assert(apl <= 2.0, "avg path length <= 2 for triangle")  # 46
    print("    PASSED")


# ── Chaos tests ──────────────────────────────────────────────────────────────


fn test_logistic_map_stable() raises:
    print("  test_logistic_map_stable...")
    # r=2.0 → converges to fixed point 0.5
    var traj = logistic_map(2.0, 0.5, 100)
    _assert(len(traj) == 101, "logistic map length")  # 47
    var last = traj[100]
    _assert_close(last, 0.5, 0.01, "logistic r=2 fixed point")  # 48
    print("    PASSED")


fn test_logistic_map_chaotic() raises:
    print("  test_logistic_map_chaotic...")
    # r=3.6 → chaotic, does not converge to single point
    var traj = logistic_map(3.6, 0.5, 200)
    var last_few_same = True
    for i in range(195, 200):
        if fabs(traj[i] - traj[200]) > 0.001:
            last_few_same = False
            break
    _assert(not last_few_same, "logistic r=3.6 does not converge")  # 49
    print("    PASSED")


fn test_lorenz_simulate() raises:
    print("  test_lorenz_simulate...")
    var traj = lorenz_simulate(1.0, 1.0, 1.0, 10.0, 28.0, 8.0 / 3.0, 0.01, 1000)
    _assert(len(traj) == 1001, "lorenz trajectory length")  # 50
    # Check bounded: |x|, |y|, |z| should stay < 100
    var bounded = True
    for i in range(len(traj)):
        if fabs(traj[i][0]) > 100.0 or fabs(traj[i][1]) > 100.0 or fabs(traj[i][2]) > 100.0:
            bounded = False
            break
    _assert(bounded, "lorenz trajectory bounded")  # 51
    print("    PASSED")


fn test_lorenz_step() raises:
    print("  test_lorenz_step...")
    var result = lorenz_step(1.0, 1.0, 1.0, 10.0, 28.0, 8.0 / 3.0, 0.01)
    _assert(len(result) == 3, "lorenz step returns 3 values")  # 52
    # dx = 10*(1-1) = 0, dy = 1*(28-1)-1 = 26, dz = 1*1 - 8/3*1 = -1.667
    _assert_close(result[0], 1.0, 0.01, "lorenz step x")  # 53
    _assert_close(result[1], 1.26, 0.01, "lorenz step y")  # 54
    print("    PASSED")


fn test_lyapunov_chaotic() raises:
    print("  test_lyapunov_chaotic...")
    var lyap = lyapunov_exponent_logistic(3.9, 10000, 1000)
    _assert(lyap > 0.0, "lyapunov r=3.9 positive (chaotic)")  # 55
    print("    PASSED")


fn test_lyapunov_stable() raises:
    print("  test_lyapunov_stable...")
    var lyap = lyapunov_exponent_logistic(2.5, 10000, 1000)
    _assert(lyap < 0.0, "lyapunov r=2.5 negative (stable)")  # 56
    print("    PASSED")


fn test_is_chaotic() raises:
    print("  test_is_chaotic...")
    _assert(is_chaotic(0.5), "positive lyapunov → chaotic")  # 57
    _assert(not is_chaotic(-0.5), "negative lyapunov → not chaotic")  # 58
    _assert(not is_chaotic(0.0), "zero lyapunov → not chaotic")  # 59
    print("    PASSED")


fn test_tent_map() raises:
    print("  test_tent_map...")
    var traj = tent_map(2.0, 0.3, 100)
    _assert(len(traj) == 101, "tent map length")  # 60
    # All values should be in [0, 1]
    var in_range = True
    for i in range(len(traj)):
        if traj[i] < -0.001 or traj[i] > 1.001:
            in_range = False
            break
    _assert(in_range, "tent map values in [0,1]")  # 61
    print("    PASSED")


fn test_henon_map() raises:
    print("  test_henon_map...")
    # Classic Hénon: a=1.4, b=0.3
    var traj = henon_map(1.4, 0.3, 0.0, 0.0, 100)
    _assert(len(traj) == 101, "henon map length")  # 62
    # Check bounded: attractor is typically within |x|<2, |y|<1
    var bounded = True
    for i in range(len(traj)):
        if fabs(traj[i][0]) > 10.0 or fabs(traj[i][1]) > 10.0:
            bounded = False
            break
    _assert(bounded, "henon trajectory bounded")  # 63
    print("    PASSED")


fn test_bifurcation_diagram() raises:
    print("  test_bifurcation_diagram...")
    var pts = bifurcation_diagram(2.5, 4.0, 10, 100, 5)
    _assert(len(pts) == 50, "bifurcation diagram 10 r values * 5 last")  # 64
    # Each point should have [r, x]
    _assert(len(pts[0]) == 2, "bifurcation point has r and x")  # 65
    # r values should be in [2.5, 4.0]
    _assert(pts[0][0] >= 2.5, "bifurcation r >= r_start")  # 66
    _assert(pts[49][0] <= 4.0, "bifurcation r <= r_end")  # 67
    print("    PASSED")


fn test_sensitivity() raises:
    print("  test_sensitivity...")
    var div = sensitivity_to_initial(3.9, 0.5, 0.5001, 50)
    _assert(len(div) == 51, "sensitivity length")  # 68
    # Initial divergence is tiny
    _assert(div[0] < 0.001, "initial divergence small")  # 69
    # After many steps in chaotic regime, divergence grows
    var max_div: Float64 = 0.0
    for i in range(len(div)):
        if div[i] > max_div:
            max_div = div[i]
    _assert(max_div > 0.01, "divergence grows in chaotic regime")  # 70
    print("    PASSED")


fn test_feigenbaum() raises:
    print("  test_feigenbaum...")
    # Known bifurcation points: r1≈3.0, r2≈3.449, r3≈3.5441
    # δ ≈ (3.449 - 3.0) / (3.5441 - 3.449) ≈ 4.72
    var delta = feigenbaum_ratio(3.0, 3.449, 3.5441)
    _assert(delta > 4.0, "feigenbaum ratio > 4")  # 71
    _assert(delta < 5.5, "feigenbaum ratio < 5.5")  # 72
    # Zero denominator guard
    var d2 = feigenbaum_ratio(1.0, 2.0, 2.0)
    _assert_close(d2, 0.0, 1e-10, "feigenbaum zero denom")  # 73
    print("    PASSED")


fn test_tent_map_mu_half() raises:
    print("  test_tent_map_mu_half...")
    # mu=0.5: tent map converges to 0 from any start
    var traj = tent_map(0.5, 0.3, 50)
    # Should converge to 0
    _assert(traj[50] < 0.01, "tent map mu=0.5 converges to 0")  # 74
    print("    PASSED")


fn test_logistic_map_r3() raises:
    print("  test_logistic_map_r3...")
    # r=3.0 → oscillates near 2/3 (period-2 onset)
    var traj = logistic_map(3.0, 0.1, 500)
    _assert_close(traj[500], 2.0 / 3.0, 0.02, "logistic r=3 near 2/3")  # 75
    print("    PASSED")


# ── Main ─────────────────────────────────────────────────────────────────────


fn main() raises:
    print("=== Wave 61 Tests: Thermodynamics, Social Networks, Chaos ===")

    # Thermodynamics
    print("--- Thermodynamics ---")
    test_ideal_gas_pressure()
    test_ideal_gas_volume()
    test_carnot_efficiency()
    test_entropy_change()
    test_heat_capacity()
    test_adiabatic_process()
    test_work_isothermal()
    test_stefan_boltzmann()
    test_thermal_conductivity()
    test_gibbs_free_energy()
    test_clausius_clapeyron()

    # Social Network
    print("--- Social Network ---")
    test_out_degree()
    test_in_degree()
    test_network_density()
    test_reciprocity()
    test_strongly_connected()
    test_community_labels()
    test_influence_spread()
    test_local_clustering()
    test_average_path_length()

    # Chaos
    print("--- Chaos Theory ---")
    test_logistic_map_stable()
    test_logistic_map_chaotic()
    test_lorenz_simulate()
    test_lorenz_step()
    test_lyapunov_chaotic()
    test_lyapunov_stable()
    test_is_chaotic()
    test_tent_map()
    test_henon_map()
    test_bifurcation_diagram()
    test_sensitivity()
    test_feigenbaum()
    test_tent_map_mu_half()
    test_logistic_map_r3()

    print("=== All 75 assertions passed! ===")
