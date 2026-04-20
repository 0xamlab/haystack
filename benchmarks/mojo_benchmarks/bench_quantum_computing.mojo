"""bench_quantum_computing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from quantum_computing import qubit_state_probability, measurement_probability_0, measurement_probability_1, bell_state_fidelity, gate_error_rate, circuit_depth_error, logical_qubit_overhead, decoherence_time_ratio, quantum_volume, grover_iterations, shor_qubits_needed, error_correction_threshold
from std.time import perf_counter_ns

def main() raises:
    var _lf5 = List[Float64]()
    _lf5.append(0.5); _lf5.append(0.6); _lf5.append(0.7)
    _lf5.append(0.4); _lf5.append(0.3)
    var _li5 = List[Int]()
    _li5.append(0); _li5.append(1); _li5.append(2)
    _li5.append(3); _li5.append(4)
    var _lb5 = List[Bool]()
    _lb5.append(True); _lb5.append(False); _lb5.append(True)
    _lb5.append(True); _lb5.append(False)
    var _lub5 = List[UInt8]()
    _lub5.append(1); _lub5.append(2); _lub5.append(3)
    _lub5.append(4); _lub5.append(5)
    var _llf3 = List[List[Float64]]()
    _llf3.append(List[Float64]()); _llf3.append(List[Float64]()); _llf3.append(List[Float64]())
    _llf3[0].append(4.0); _llf3[0].append(0.0); _llf3[0].append(5.0)
    _llf3[1].append(0.0); _llf3[1].append(3.0); _llf3[1].append(4.0)
    _llf3[2].append(3.0); _llf3[2].append(4.0); _llf3[2].append(0.0)
    var N: Int = 10000

    var _acc_qubit_state_probability: Float64 = 0.0
    var _t0_qubit_state_probability = perf_counter_ns()
    for _ in range(N):
        _acc_qubit_state_probability += qubit_state_probability(0.5)
    var _t1_qubit_state_probability = perf_counter_ns()
    var _ns_qubit_state_probability = Float64(_t1_qubit_state_probability - _t0_qubit_state_probability) / Float64(N)
    print("MOJO_TIMING quantum_computing::qubit_state_probability", _ns_qubit_state_probability, _acc_qubit_state_probability)
    var _acc_measurement_probability_0: Float64 = 0.0
    var _t0_measurement_probability_0 = perf_counter_ns()
    for _ in range(N):
        _acc_measurement_probability_0 += measurement_probability_0(0.5)
    var _t1_measurement_probability_0 = perf_counter_ns()
    var _ns_measurement_probability_0 = Float64(_t1_measurement_probability_0 - _t0_measurement_probability_0) / Float64(N)
    print("MOJO_TIMING quantum_computing::measurement_probability_0", _ns_measurement_probability_0, _acc_measurement_probability_0)
    var _acc_measurement_probability_1: Float64 = 0.0
    var _t0_measurement_probability_1 = perf_counter_ns()
    for _ in range(N):
        _acc_measurement_probability_1 += measurement_probability_1(0.5)
    var _t1_measurement_probability_1 = perf_counter_ns()
    var _ns_measurement_probability_1 = Float64(_t1_measurement_probability_1 - _t0_measurement_probability_1) / Float64(N)
    print("MOJO_TIMING quantum_computing::measurement_probability_1", _ns_measurement_probability_1, _acc_measurement_probability_1)
    var _acc_bell_state_fidelity: Float64 = 0.0
    var _t0_bell_state_fidelity = perf_counter_ns()
    for _ in range(N):
        _acc_bell_state_fidelity += bell_state_fidelity(0.5)
    var _t1_bell_state_fidelity = perf_counter_ns()
    var _ns_bell_state_fidelity = Float64(_t1_bell_state_fidelity - _t0_bell_state_fidelity) / Float64(N)
    print("MOJO_TIMING quantum_computing::bell_state_fidelity", _ns_bell_state_fidelity, _acc_bell_state_fidelity)
    var _acc_gate_error_rate: Float64 = 0.0
    var _t0_gate_error_rate = perf_counter_ns()
    for _ in range(N):
        _acc_gate_error_rate += gate_error_rate(0.5)
    var _t1_gate_error_rate = perf_counter_ns()
    var _ns_gate_error_rate = Float64(_t1_gate_error_rate - _t0_gate_error_rate) / Float64(N)
    print("MOJO_TIMING quantum_computing::gate_error_rate", _ns_gate_error_rate, _acc_gate_error_rate)
    var _acc_circuit_depth_error: Float64 = 0.0
    var _t0_circuit_depth_error = perf_counter_ns()
    for _ in range(N):
        _acc_circuit_depth_error += circuit_depth_error(0.5, 0.5)
    var _t1_circuit_depth_error = perf_counter_ns()
    var _ns_circuit_depth_error = Float64(_t1_circuit_depth_error - _t0_circuit_depth_error) / Float64(N)
    print("MOJO_TIMING quantum_computing::circuit_depth_error", _ns_circuit_depth_error, _acc_circuit_depth_error)
    var _acc_logical_qubit_overhead: Float64 = 0.0
    var _t0_logical_qubit_overhead = perf_counter_ns()
    for _ in range(N):
        _acc_logical_qubit_overhead += Float64(logical_qubit_overhead(5))
    var _t1_logical_qubit_overhead = perf_counter_ns()
    var _ns_logical_qubit_overhead = Float64(_t1_logical_qubit_overhead - _t0_logical_qubit_overhead) / Float64(N)
    print("MOJO_TIMING quantum_computing::logical_qubit_overhead", _ns_logical_qubit_overhead, _acc_logical_qubit_overhead)
    var _acc_decoherence_time_ratio: Float64 = 0.0
    var _t0_decoherence_time_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_decoherence_time_ratio += decoherence_time_ratio(0.5, 0.5)
    var _t1_decoherence_time_ratio = perf_counter_ns()
    var _ns_decoherence_time_ratio = Float64(_t1_decoherence_time_ratio - _t0_decoherence_time_ratio) / Float64(N)
    print("MOJO_TIMING quantum_computing::decoherence_time_ratio", _ns_decoherence_time_ratio, _acc_decoherence_time_ratio)
    var _acc_quantum_volume: Float64 = 0.0
    var _t0_quantum_volume = perf_counter_ns()
    for _ in range(N):
        _acc_quantum_volume += quantum_volume(5, 5)
    var _t1_quantum_volume = perf_counter_ns()
    var _ns_quantum_volume = Float64(_t1_quantum_volume - _t0_quantum_volume) / Float64(N)
    print("MOJO_TIMING quantum_computing::quantum_volume", _ns_quantum_volume, _acc_quantum_volume)
    var _acc_grover_iterations: Float64 = 0.0
    var _t0_grover_iterations = perf_counter_ns()
    for _ in range(N):
        _acc_grover_iterations += grover_iterations(0.5)
    var _t1_grover_iterations = perf_counter_ns()
    var _ns_grover_iterations = Float64(_t1_grover_iterations - _t0_grover_iterations) / Float64(N)
    print("MOJO_TIMING quantum_computing::grover_iterations", _ns_grover_iterations, _acc_grover_iterations)
    var _acc_shor_qubits_needed: Float64 = 0.0
    var _t0_shor_qubits_needed = perf_counter_ns()
    for _ in range(N):
        _acc_shor_qubits_needed += Float64(shor_qubits_needed(5))
    var _t1_shor_qubits_needed = perf_counter_ns()
    var _ns_shor_qubits_needed = Float64(_t1_shor_qubits_needed - _t0_shor_qubits_needed) / Float64(N)
    print("MOJO_TIMING quantum_computing::shor_qubits_needed", _ns_shor_qubits_needed, _acc_shor_qubits_needed)
    var _acc_error_correction_threshold: Float64 = 0.0
    var _t0_error_correction_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_error_correction_threshold += Float64(error_correction_threshold(0.5, 0.5))
    var _t1_error_correction_threshold = perf_counter_ns()
    var _ns_error_correction_threshold = Float64(_t1_error_correction_threshold - _t0_error_correction_threshold) / Float64(N)
    print("MOJO_TIMING quantum_computing::error_correction_threshold", _ns_error_correction_threshold, _acc_error_correction_threshold)
