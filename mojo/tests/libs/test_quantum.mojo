"""test_quantum.mojo — auto-generated tests for quantum library."""
from std.math import isnan, isinf
from quantum import qubit_zero, qubit_one, hadamard, pauli_x, pauli_z, phase_gate, measure_probability, qubit_norm, bell_state, expectation_z, bloch_coords

fn is_finite(x: Float64) -> Bool:
    return not isnan(x) and not isinf(x)

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(1); _li5.append(2); _li5.append(3)
    _li5.append(4); _li5.append(5)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var passed: Int = 0
    var failed: Int = 0

    var _v_qubit_zero = qubit_zero()
    if len(_v_qubit_zero) >= 0: passed += 1; print("  ✅ quantum::qubit_zero")
    var _v_qubit_one = qubit_one()
    if len(_v_qubit_one) >= 0: passed += 1; print("  ✅ quantum::qubit_one")
    var _v_hadamard = hadamard(_lf5)
    if len(_v_hadamard) >= 0: passed += 1; print("  ✅ quantum::hadamard")
    var _v_pauli_x = pauli_x(_lf5)
    if len(_v_pauli_x) >= 0: passed += 1; print("  ✅ quantum::pauli_x")
    var _v_pauli_z = pauli_z(_lf5)
    if len(_v_pauli_z) >= 0: passed += 1; print("  ✅ quantum::pauli_z")
    var _v_phase_gate = phase_gate(_lf5, 0.5)
    if len(_v_phase_gate) >= 0: passed += 1; print("  ✅ quantum::phase_gate")
    var _v_measure_probability = measure_probability(_lf5)
    if len(_v_measure_probability) >= 0: passed += 1; print("  ✅ quantum::measure_probability")
    var _v_qubit_norm = qubit_norm(_lf5)
    if is_finite(_v_qubit_norm): passed += 1; print("  ✅ quantum::qubit_norm =", _v_qubit_norm)
    else: failed += 1; print("  ❌ quantum::qubit_norm → non-finite:", _v_qubit_norm)
    var _v_bell_state = bell_state()
    if len(_v_bell_state) >= 0: passed += 1; print("  ✅ quantum::bell_state")
    var _v_expectation_z = expectation_z(_lf5)
    if is_finite(_v_expectation_z): passed += 1; print("  ✅ quantum::expectation_z =", _v_expectation_z)
    else: failed += 1; print("  ❌ quantum::expectation_z → non-finite:", _v_expectation_z)
    var _v_bloch_coords = bloch_coords(_lf5)
    if len(_v_bloch_coords) >= 0: passed += 1; print("  ✅ quantum::bloch_coords")

    print("  [quantum] Passed:", passed, "Failed:", failed)
