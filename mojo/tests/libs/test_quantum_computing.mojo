"""test_quantum_computing.mojo — auto-generated tests for quantum_computing library."""
from std.math import isnan, isinf
from quantum_computing import qubit_state_probability, measurement_probability_0, measurement_probability_1, bell_state_fidelity, gate_error_rate, circuit_depth_error, logical_qubit_overhead, decoherence_time_ratio, quantum_volume, grover_iterations, shor_qubits_needed, error_correction_threshold

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

    var _v_qubit_state_probability = qubit_state_probability(0.5)
    if is_finite(_v_qubit_state_probability): passed += 1; print("  ✅ quantum_computing::qubit_state_probability =", _v_qubit_state_probability)
    else: failed += 1; print("  ❌ quantum_computing::qubit_state_probability → non-finite:", _v_qubit_state_probability)
    var _v_measurement_probability_0 = measurement_probability_0(0.5)
    if is_finite(_v_measurement_probability_0): passed += 1; print("  ✅ quantum_computing::measurement_probability_0 =", _v_measurement_probability_0)
    else: failed += 1; print("  ❌ quantum_computing::measurement_probability_0 → non-finite:", _v_measurement_probability_0)
    var _v_measurement_probability_1 = measurement_probability_1(0.5)
    if is_finite(_v_measurement_probability_1): passed += 1; print("  ✅ quantum_computing::measurement_probability_1 =", _v_measurement_probability_1)
    else: failed += 1; print("  ❌ quantum_computing::measurement_probability_1 → non-finite:", _v_measurement_probability_1)
    var _v_bell_state_fidelity = bell_state_fidelity(0.5)
    if is_finite(_v_bell_state_fidelity): passed += 1; print("  ✅ quantum_computing::bell_state_fidelity =", _v_bell_state_fidelity)
    else: failed += 1; print("  ❌ quantum_computing::bell_state_fidelity → non-finite:", _v_bell_state_fidelity)
    var _v_gate_error_rate = gate_error_rate(0.5)
    if is_finite(_v_gate_error_rate): passed += 1; print("  ✅ quantum_computing::gate_error_rate =", _v_gate_error_rate)
    else: failed += 1; print("  ❌ quantum_computing::gate_error_rate → non-finite:", _v_gate_error_rate)
    var _v_circuit_depth_error = circuit_depth_error(0.5, 0.5)
    if is_finite(_v_circuit_depth_error): passed += 1; print("  ✅ quantum_computing::circuit_depth_error =", _v_circuit_depth_error)
    else: failed += 1; print("  ❌ quantum_computing::circuit_depth_error → non-finite:", _v_circuit_depth_error)
    _ = logical_qubit_overhead(5)
    passed += 1; print("  ✅ quantum_computing::logical_qubit_overhead")
    var _v_decoherence_time_ratio = decoherence_time_ratio(0.5, 0.5)
    if is_finite(_v_decoherence_time_ratio): passed += 1; print("  ✅ quantum_computing::decoherence_time_ratio =", _v_decoherence_time_ratio)
    else: failed += 1; print("  ❌ quantum_computing::decoherence_time_ratio → non-finite:", _v_decoherence_time_ratio)
    var _v_quantum_volume = quantum_volume(5, 5)
    if is_finite(_v_quantum_volume): passed += 1; print("  ✅ quantum_computing::quantum_volume =", _v_quantum_volume)
    else: failed += 1; print("  ❌ quantum_computing::quantum_volume → non-finite:", _v_quantum_volume)
    var _v_grover_iterations = grover_iterations(0.5)
    if is_finite(_v_grover_iterations): passed += 1; print("  ✅ quantum_computing::grover_iterations =", _v_grover_iterations)
    else: failed += 1; print("  ❌ quantum_computing::grover_iterations → non-finite:", _v_grover_iterations)
    _ = shor_qubits_needed(5)
    passed += 1; print("  ✅ quantum_computing::shor_qubits_needed")
    _ = error_correction_threshold(0.5, 0.5)
    passed += 1; print("  ✅ quantum_computing::error_correction_threshold")

    print("  [quantum_computing] Passed:", passed, "Failed:", failed)
