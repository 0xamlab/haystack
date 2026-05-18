"""
quantum_computing.mojo — Quantum computing metrics and estimates.

Public API:
  qubit_state_probability       — P = |α|²
  measurement_probability_0     — P(0) = |α|²
  measurement_probability_1     — P(1) = |β|²
  bell_state_fidelity           — F = overlap²
  gate_error_rate               — ε = 1 - F
  circuit_depth_error           — P_success ≈ (1-ε)^d
  logical_qubit_overhead        — Physical = (2d-1)² surface code
  decoherence_time_ratio        — Ratio = T2/T1
  quantum_volume                — QV = 2^min(n, d)
  grover_iterations             — Iterations ≈ π/4 * √N
  shor_qubits_needed            — Qubits ≈ 2n + 3
  error_correction_threshold    — Below = physical < threshold
"""
from std.math import sqrt, pow


comptime PI: Float64 = 3.141592653589793


# ── qubit_state_probability ──────────────────────────────────────────────────


fn qubit_state_probability(amplitude_squared: Float64) -> Float64:
    """Return probability from amplitude squared: P = |α|²."""
    return amplitude_squared


# ── measurement_probability_0 ────────────────────────────────────────────────


fn measurement_probability_0(alpha_sq: Float64) -> Float64:
    """Probability of measuring |0⟩: P(0) = |α|²."""
    return alpha_sq


# ── measurement_probability_1 ────────────────────────────────────────────────


fn measurement_probability_1(beta_sq: Float64) -> Float64:
    """Probability of measuring |1⟩: P(1) = |β|²."""
    return beta_sq


# ── bell_state_fidelity ─────────────────────────────────────────────────────


fn bell_state_fidelity(overlap: Float64) -> Float64:
    """Simplified fidelity: F = overlap²."""
    return overlap * overlap


# ── gate_error_rate ──────────────────────────────────────────────────────────


fn gate_error_rate(fidelity: Float64) -> Float64:
    """Gate error rate: ε = 1 - F."""
    return 1.0 - fidelity


# ── circuit_depth_error ──────────────────────────────────────────────────────


fn circuit_depth_error(single_gate_error: Float64, depth: Float64) -> Float64:
    """Success probability for circuit depth: P_success ≈ (1-ε)^d."""
    return pow(1.0 - single_gate_error, depth)


# ── logical_qubit_overhead ───────────────────────────────────────────────────


fn logical_qubit_overhead(code_distance: Int) -> Int:
    """Physical qubits for surface code: (2d-1)²."""
    var side = 2 * code_distance - 1
    return side * side


# ── decoherence_time_ratio ───────────────────────────────────────────────────


fn decoherence_time_ratio(t1: Float64, t2: Float64) -> Float64:
    """Decoherence ratio: T2/T1 (should be ≤ 2)."""
    return t2 / t1


# ── quantum_volume ───────────────────────────────────────────────────────────


fn quantum_volume(n_qubits: Int, circuit_depth_eff: Int) -> Float64:
    """Quantum volume: QV = 2^min(n, d)."""
    var m = n_qubits
    if circuit_depth_eff < m:
        m = circuit_depth_eff
    return pow(2.0, Float64(m))


# ── grover_iterations ────────────────────────────────────────────────────────


fn grover_iterations(n_items: Float64) -> Float64:
    """Optimal Grover iterations: ≈ π/4 * √N."""
    return PI / 4.0 * sqrt(n_items)


# ── shor_qubits_needed ──────────────────────────────────────────────────────


fn shor_qubits_needed(n_bits: Int) -> Int:
    """Qubits needed for Shor's algorithm: ≈ 2n + 3."""
    return 2 * n_bits + 3


# ── error_correction_threshold ───────────────────────────────────────────────


fn error_correction_threshold(physical_error: Float64, threshold: Float64) -> Bool:
    """True if physical error rate is below correction threshold."""
    return physical_error < threshold
