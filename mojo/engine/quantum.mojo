"""
quantum.mojo — Quantum computing primitives. Pure Mojo, zero Python imports.
Qubit = [a_re, a_im, b_re, b_im] where |ψ⟩ = a|0⟩ + b|1⟩.

Public API:
  qubit_zero, qubit_one, hadamard, pauli_x, pauli_z, phase_gate,
  measure_probability, qubit_norm, bell_state, expectation_z, bloch_coords
"""
from std.math import sqrt, cos, sin, atan2


# ── Helper constants ──────────────────────────────────────────────────────────

comptime _SQRT2_INV: Float64 = 0.7071067811865476  # 1/√2


# ── Qubit constructors ────────────────────────────────────────────────────────


fn qubit_zero() -> List[Float64]:
    """|0⟩ state: a=1+0i, b=0+0i → [1,0,0,0]."""
    var q = List[Float64]()
    q.append(1.0)
    q.append(0.0)
    q.append(0.0)
    q.append(0.0)
    return q^


fn qubit_one() -> List[Float64]:
    """|1⟩ state: a=0+0i, b=1+0i → [0,0,1,0]."""
    var q = List[Float64]()
    q.append(0.0)
    q.append(0.0)
    q.append(1.0)
    q.append(0.0)
    return q^


# ── Single-qubit gates ───────────────────────────────────────────────────────


fn hadamard(q: List[Float64]) -> List[Float64]:
    """Hadamard gate: H = (1/√2)[[1,1],[1,-1]].
    H|0⟩ = (|0⟩+|1⟩)/√2, H|1⟩ = (|0⟩-|1⟩)/√2."""
    var a_re = q[0]
    var a_im = q[1]
    var b_re = q[2]
    var b_im = q[3]
    var out = List[Float64]()
    out.append(_SQRT2_INV * (a_re + b_re))
    out.append(_SQRT2_INV * (a_im + b_im))
    out.append(_SQRT2_INV * (a_re - b_re))
    out.append(_SQRT2_INV * (a_im - b_im))
    return out^


fn pauli_x(q: List[Float64]) -> List[Float64]:
    """Pauli-X (NOT) gate: X = [[0,1],[1,0]]. Swaps |0⟩ and |1⟩."""
    var out = List[Float64]()
    out.append(q[2])
    out.append(q[3])
    out.append(q[0])
    out.append(q[1])
    return out^


fn pauli_z(q: List[Float64]) -> List[Float64]:
    """Pauli-Z gate: Z = [[1,0],[0,-1]]. Phase flip on |1⟩."""
    var out = List[Float64]()
    out.append(q[0])
    out.append(q[1])
    out.append(-q[2])
    out.append(-q[3])
    return out^


fn phase_gate(q: List[Float64], theta: Float64) -> List[Float64]:
    """Phase gate: P(θ) = [[1,0],[0,e^(iθ)]].
    Multiplies |1⟩ amplitude by e^(iθ) = cos(θ)+i·sin(θ)."""
    var b_re = q[2]
    var b_im = q[3]
    var c = cos(theta)
    var s = sin(theta)
    var out = List[Float64]()
    out.append(q[0])
    out.append(q[1])
    # (b_re + i·b_im)(cos θ + i·sin θ) = (b_re·cos - b_im·sin) + i(b_re·sin + b_im·cos)
    out.append(b_re * c - b_im * s)
    out.append(b_re * s + b_im * c)
    return out^


# ── Measurement ───────────────────────────────────────────────────────────────


fn measure_probability(q: List[Float64]) -> List[Float64]:
    """Returns [P(|0⟩), P(|1⟩)] = [|a|², |b|²]."""
    var p0 = q[0] * q[0] + q[1] * q[1]
    var p1 = q[2] * q[2] + q[3] * q[3]
    var out = List[Float64]()
    out.append(p0)
    out.append(p1)
    return out^


fn qubit_norm(q: List[Float64]) -> Float64:
    """|a|² + |b|² — should be 1.0 for a valid quantum state."""
    return q[0] * q[0] + q[1] * q[1] + q[2] * q[2] + q[3] * q[3]


# ── Bell state ────────────────────────────────────────────────────────────────


fn bell_state() -> List[Float64]:
    """Bell state |Φ+⟩ = (|00⟩ + |11⟩)/√2 as 2-qubit state vector.
    [1/√2, 0, 0, 0, 0, 0, 1/√2, 0] — 4 basis states × (re, im)."""
    var out = List[Float64]()
    out.append(_SQRT2_INV)  # |00⟩ re
    out.append(0.0)         # |00⟩ im
    out.append(0.0)         # |01⟩ re
    out.append(0.0)         # |01⟩ im
    out.append(0.0)         # |10⟩ re
    out.append(0.0)         # |10⟩ im
    out.append(_SQRT2_INV)  # |11⟩ re
    out.append(0.0)         # |11⟩ im
    return out^


# ── Expectation values ────────────────────────────────────────────────────────


fn expectation_z(q: List[Float64]) -> Float64:
    """⟨Z⟩ = P(|0⟩) - P(|1⟩)."""
    var p0 = q[0] * q[0] + q[1] * q[1]
    var p1 = q[2] * q[2] + q[3] * q[3]
    return p0 - p1


# ── Bloch sphere ──────────────────────────────────────────────────────────────


fn bloch_coords(q: List[Float64]) -> List[Float64]:
    """Bloch sphere coordinates [x, y, z] for a single qubit.
    For |ψ⟩ = a|0⟩ + b|1⟩:
      x = 2·Re(a*·b), y = 2·Im(a*·b), z = |a|² - |b|².
    a* = (a_re - i·a_im), so a*·b = (a_re·b_re + a_im·b_im) + i(a_re·b_im - a_im·b_re)."""
    var a_re = q[0]
    var a_im = q[1]
    var b_re = q[2]
    var b_im = q[3]
    # a* · b
    var re_part = a_re * b_re + a_im * b_im
    var im_part = a_re * b_im - a_im * b_re
    var p0 = a_re * a_re + a_im * a_im
    var p1 = b_re * b_re + b_im * b_im
    var out = List[Float64]()
    out.append(2.0 * re_part)   # x
    out.append(2.0 * im_part)   # y
    out.append(p0 - p1)         # z
    return out^
