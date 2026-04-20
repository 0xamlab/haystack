"""Wave 99 tests -- quantum_computing, nanotechnology, logistics (70+ assertions)."""

from std.testing import assert_true, assert_false, assert_equal
from std.math import abs, sqrt, pow

# -- quantum_computing imports --
from quantum_computing import (
    qubit_state_probability,
    measurement_probability_0,
    measurement_probability_1,
    bell_state_fidelity,
    gate_error_rate,
    circuit_depth_error,
    logical_qubit_overhead,
    decoherence_time_ratio,
    quantum_volume,
    grover_iterations,
    shor_qubits_needed,
    error_correction_threshold,
)

# -- nanotechnology imports --
from nanotechnology import (
    surface_to_volume_sphere,
    nanoparticle_surface_area,
    nanoparticle_volume,
    specific_surface_area,
    quantum_confinement_energy,
    mean_free_path,
    knudsen_number,
    van_der_waals_force,
    diffusion_coefficient_stokes_einstein,
    zeta_potential_mobility,
    aspect_ratio,
    packing_fraction_fcc,
)

# -- logistics imports --
from logistics import (
    vehicle_utilization,
    order_fill_rate,
    perfect_order_rate,
    inventory_turns,
    days_of_supply,
    warehouse_utilization,
    cost_per_unit_shipped,
    on_time_delivery_rate,
    dwell_time,
    cross_dock_throughput,
    route_efficiency,
    carbon_per_tonne_km,
)


fn _close(a: Float64, b: Float64, tol: Float64 = 1e-6) -> Bool:
    return abs(a - b) < tol


fn test_quantum_computing() raises:
    print("== quantum_computing ==")

    # qubit_state_probability
    assert_true(_close(qubit_state_probability(0.5), 0.5), "qsp half")
    assert_true(_close(qubit_state_probability(1.0), 1.0), "qsp one")
    assert_true(_close(qubit_state_probability(0.0), 0.0), "qsp zero")

    # measurement_probability_0
    assert_true(_close(measurement_probability_0(0.7), 0.7), "mp0 0.7")
    assert_true(_close(measurement_probability_0(0.25), 0.25), "mp0 0.25")

    # measurement_probability_1
    assert_true(_close(measurement_probability_1(0.3), 0.3), "mp1 0.3")
    assert_true(_close(measurement_probability_1(0.75), 0.75), "mp1 0.75")

    # bell_state_fidelity: F = overlap²
    assert_true(_close(bell_state_fidelity(1.0), 1.0), "bsf 1")
    assert_true(_close(bell_state_fidelity(0.9), 0.81), "bsf 0.9")
    assert_true(_close(bell_state_fidelity(0.5), 0.25), "bsf 0.5")

    # gate_error_rate: ε = 1 - F
    assert_true(_close(gate_error_rate(0.999), 0.001), "ger 0.999")
    assert_true(_close(gate_error_rate(0.95), 0.05), "ger 0.95")

    # circuit_depth_error: (1-ε)^d
    assert_true(_close(circuit_depth_error(0.01, 10.0), pow(0.99, 10.0)), "cde")
    assert_true(_close(circuit_depth_error(0.001, 100.0), pow(0.999, 100.0)), "cde2")

    # logical_qubit_overhead: (2d-1)²
    assert_equal(logical_qubit_overhead(3), 25, "lqo d=3")   # (5)²=25
    assert_equal(logical_qubit_overhead(5), 81, "lqo d=5")   # (9)²=81
    assert_equal(logical_qubit_overhead(7), 169, "lqo d=7")  # (13)²=169

    # decoherence_time_ratio: T2/T1
    assert_true(_close(decoherence_time_ratio(100.0, 150.0), 1.5), "dtr")
    assert_true(_close(decoherence_time_ratio(50.0, 100.0), 2.0), "dtr2")

    # quantum_volume: 2^min(n,d)
    assert_true(_close(quantum_volume(5, 3), 8.0), "qv 5,3")    # 2^3
    assert_true(_close(quantum_volume(3, 5), 8.0), "qv 3,5")    # 2^3
    assert_true(_close(quantum_volume(4, 4), 16.0), "qv 4,4")   # 2^4

    # grover_iterations: π/4 * √N
    var pi = 3.141592653589793
    assert_true(_close(grover_iterations(100.0), pi / 4.0 * 10.0), "gi 100")
    assert_true(_close(grover_iterations(1000000.0), pi / 4.0 * 1000.0), "gi 1M")

    # shor_qubits_needed: 2n + 3
    assert_equal(shor_qubits_needed(1024), 2051, "sqn 1024")
    assert_equal(shor_qubits_needed(256), 515, "sqn 256")

    # error_correction_threshold
    assert_true(error_correction_threshold(0.001, 0.01), "ect below")
    assert_false(error_correction_threshold(0.02, 0.01), "ect above")
    assert_false(error_correction_threshold(0.01, 0.01), "ect equal")

    print("  ✓ quantum_computing passed")


fn test_nanotechnology() raises:
    print("== nanotechnology ==")

    var pi = 3.141592653589793

    # surface_to_volume_sphere: 3/r
    assert_true(_close(surface_to_volume_sphere(1.0), 3.0), "stv 1")
    assert_true(_close(surface_to_volume_sphere(5.0), 0.6), "stv 5")
    assert_true(_close(surface_to_volume_sphere(0.5), 6.0), "stv 0.5")

    # nanoparticle_surface_area: 4πr²
    assert_true(_close(nanoparticle_surface_area(1.0), 4.0 * pi), "sa 1")
    assert_true(_close(nanoparticle_surface_area(2.0), 16.0 * pi), "sa 2")

    # nanoparticle_volume: 4/3*π*r³
    assert_true(_close(nanoparticle_volume(1.0), 4.0 / 3.0 * pi), "vol 1")
    assert_true(_close(nanoparticle_volume(3.0), 36.0 * pi), "vol 3")

    # specific_surface_area: SA/mass
    assert_true(_close(specific_surface_area(100.0, 5.0), 20.0), "ssa")
    assert_true(_close(specific_surface_area(50.0, 2.0), 25.0), "ssa2")

    # quantum_confinement_energy: h²/(8*m*L²)
    assert_true(_close(quantum_confinement_energy(2.0, 1.0, 1.0), 0.5), "qce")
    assert_true(_close(quantum_confinement_energy(4.0, 2.0, 2.0), 0.25), "qce2")

    # mean_free_path: kT/(√2*π*d²*P)
    # Use kb=1, t=300, d=1, p=1 → 300/(√2*π) ≈ 67.5140
    var sqrt2 = 1.4142135623730951
    var expected_mfp = 300.0 / (sqrt2 * pi * 1.0 * 1.0)
    assert_true(_close(mean_free_path(1.0, 300.0, 1.0, 1.0), expected_mfp), "mfp")

    # knudsen_number: λ/L
    assert_true(_close(knudsen_number(10.0, 2.0), 5.0), "kn")
    assert_true(_close(knudsen_number(0.1, 1.0), 0.1), "kn2")

    # van_der_waals_force: A*R/(6*d²)
    assert_true(_close(van_der_waals_force(1.0, 1.0, 1.0), 1.0 / 6.0), "vdw")
    assert_true(_close(van_der_waals_force(12.0, 3.0, 2.0), 36.0 / 24.0), "vdw2")

    # diffusion_coefficient_stokes_einstein: kT/(6πηr)
    var expected_d = 300.0 / (6.0 * pi * 1.0 * 1.0)
    assert_true(_close(diffusion_coefficient_stokes_einstein(1.0, 300.0, 1.0, 1.0), expected_d), "dcse")

    # zeta_potential_mobility: η*μ/ε
    assert_true(_close(zeta_potential_mobility(0.001, 3.0, 0.01), 0.3), "zpm")
    assert_true(_close(zeta_potential_mobility(2.0, 5.0, 4.0), 2.5), "zpm2")

    # aspect_ratio: L/D
    assert_true(_close(aspect_ratio(100.0, 5.0), 20.0), "ar")
    assert_true(_close(aspect_ratio(50.0, 10.0), 5.0), "ar2")

    # packing_fraction_fcc: π*√2/6 ≈ 0.7405
    assert_true(_close(packing_fraction_fcc(), pi * sqrt2 / 6.0), "pff")
    assert_true(packing_fraction_fcc() > 0.74, "pff>0.74")
    assert_true(packing_fraction_fcc() < 0.75, "pff<0.75")

    print("  ✓ nanotechnology passed")


fn test_logistics() raises:
    print("== logistics ==")

    # vehicle_utilization: loaded/total * 100
    assert_true(_close(vehicle_utilization(800.0, 1000.0), 80.0), "vu")
    assert_true(_close(vehicle_utilization(500.0, 500.0), 100.0), "vu full")

    # order_fill_rate: filled/total * 100
    assert_true(_close(order_fill_rate(95.0, 100.0), 95.0), "ofr")
    assert_true(_close(order_fill_rate(47.0, 50.0), 94.0), "ofr2")

    # perfect_order_rate: perfect/total * 100
    assert_true(_close(perfect_order_rate(90.0, 100.0), 90.0), "por")

    # inventory_turns: COGS/AvgInv
    assert_true(_close(inventory_turns(1000000.0, 200000.0), 5.0), "it")
    assert_true(_close(inventory_turns(500000.0, 100000.0), 5.0), "it2")

    # days_of_supply: inv/demand
    assert_true(_close(days_of_supply(300.0, 10.0), 30.0), "dos")
    assert_true(_close(days_of_supply(100.0, 5.0), 20.0), "dos2")

    # warehouse_utilization: used/total * 100
    assert_true(_close(warehouse_utilization(7500.0, 10000.0), 75.0), "wu")

    # cost_per_unit_shipped: cost/units
    assert_true(_close(cost_per_unit_shipped(5000.0, 1000.0), 5.0), "cpu")
    assert_true(_close(cost_per_unit_shipped(250.0, 50.0), 5.0), "cpu2")

    # on_time_delivery_rate: ontime/total * 100
    assert_true(_close(on_time_delivery_rate(92.0, 100.0), 92.0), "otd")

    # dwell_time: departure - arrival
    assert_true(_close(dwell_time(8.0, 14.0), 6.0), "dt")
    assert_true(_close(dwell_time(0.0, 2.5), 2.5), "dt2")

    # cross_dock_throughput: items/hours
    assert_true(_close(cross_dock_throughput(5000.0, 8.0), 625.0), "cdt")

    # route_efficiency: optimal/actual * 100
    assert_true(_close(route_efficiency(120.0, 100.0), 100.0 / 120.0 * 100.0), "re")
    assert_true(_close(route_efficiency(100.0, 100.0), 100.0), "re perfect")

    # carbon_per_tonne_km: CO2/(tonnes*km)
    assert_true(_close(carbon_per_tonne_km(50.0, 10.0, 100.0), 0.05), "cptk")
    assert_true(_close(carbon_per_tonne_km(200.0, 20.0, 50.0), 0.2), "cptk2")

    print("  ✓ logistics passed")


fn main() raises:
    test_quantum_computing()
    test_nanotechnology()
    test_logistics()
    print("Wave 99 — all tests passed ✓")
