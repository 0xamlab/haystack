"""bench_quantum_computing.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from quantum_computing import qubit_state_probability, measurement_probability_0, measurement_probability_1, bell_state_fidelity, gate_error_rate, circuit_depth_error, logical_qubit_overhead, decoherence_time_ratio, quantum_volume, grover_iterations, shor_qubits_needed, error_correction_threshold
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))


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
    var _result_qubit_state_probability = qubit_state_probability(0.5)
    var _summary_qubit_state_probability = _summary_float64(_result_qubit_state_probability)
    print("MOJO_RESULT quantum_computing::qubit_state_probability", _summary_qubit_state_probability)
    var _acc_measurement_probability_0: Float64 = 0.0
    var _t0_measurement_probability_0 = perf_counter_ns()
    for _ in range(N):
        _acc_measurement_probability_0 += measurement_probability_0(0.5)
    var _t1_measurement_probability_0 = perf_counter_ns()
    var _ns_measurement_probability_0 = Float64(_t1_measurement_probability_0 - _t0_measurement_probability_0) / Float64(N)
    print("MOJO_TIMING quantum_computing::measurement_probability_0", _ns_measurement_probability_0, _acc_measurement_probability_0)
    var _result_measurement_probability_0 = measurement_probability_0(0.5)
    var _summary_measurement_probability_0 = _summary_float64(_result_measurement_probability_0)
    print("MOJO_RESULT quantum_computing::measurement_probability_0", _summary_measurement_probability_0)
    var _acc_measurement_probability_1: Float64 = 0.0
    var _t0_measurement_probability_1 = perf_counter_ns()
    for _ in range(N):
        _acc_measurement_probability_1 += measurement_probability_1(0.5)
    var _t1_measurement_probability_1 = perf_counter_ns()
    var _ns_measurement_probability_1 = Float64(_t1_measurement_probability_1 - _t0_measurement_probability_1) / Float64(N)
    print("MOJO_TIMING quantum_computing::measurement_probability_1", _ns_measurement_probability_1, _acc_measurement_probability_1)
    var _result_measurement_probability_1 = measurement_probability_1(0.5)
    var _summary_measurement_probability_1 = _summary_float64(_result_measurement_probability_1)
    print("MOJO_RESULT quantum_computing::measurement_probability_1", _summary_measurement_probability_1)
    var _acc_bell_state_fidelity: Float64 = 0.0
    var _t0_bell_state_fidelity = perf_counter_ns()
    for _ in range(N):
        _acc_bell_state_fidelity += bell_state_fidelity(0.5)
    var _t1_bell_state_fidelity = perf_counter_ns()
    var _ns_bell_state_fidelity = Float64(_t1_bell_state_fidelity - _t0_bell_state_fidelity) / Float64(N)
    print("MOJO_TIMING quantum_computing::bell_state_fidelity", _ns_bell_state_fidelity, _acc_bell_state_fidelity)
    var _result_bell_state_fidelity = bell_state_fidelity(0.5)
    var _summary_bell_state_fidelity = _summary_float64(_result_bell_state_fidelity)
    print("MOJO_RESULT quantum_computing::bell_state_fidelity", _summary_bell_state_fidelity)
    var _acc_gate_error_rate: Float64 = 0.0
    var _t0_gate_error_rate = perf_counter_ns()
    for _ in range(N):
        _acc_gate_error_rate += gate_error_rate(0.5)
    var _t1_gate_error_rate = perf_counter_ns()
    var _ns_gate_error_rate = Float64(_t1_gate_error_rate - _t0_gate_error_rate) / Float64(N)
    print("MOJO_TIMING quantum_computing::gate_error_rate", _ns_gate_error_rate, _acc_gate_error_rate)
    var _result_gate_error_rate = gate_error_rate(0.5)
    var _summary_gate_error_rate = _summary_float64(_result_gate_error_rate)
    print("MOJO_RESULT quantum_computing::gate_error_rate", _summary_gate_error_rate)
    var _acc_circuit_depth_error: Float64 = 0.0
    var _t0_circuit_depth_error = perf_counter_ns()
    for _ in range(N):
        _acc_circuit_depth_error += circuit_depth_error(0.5, 0.5)
    var _t1_circuit_depth_error = perf_counter_ns()
    var _ns_circuit_depth_error = Float64(_t1_circuit_depth_error - _t0_circuit_depth_error) / Float64(N)
    print("MOJO_TIMING quantum_computing::circuit_depth_error", _ns_circuit_depth_error, _acc_circuit_depth_error)
    var _result_circuit_depth_error = circuit_depth_error(0.5, 0.5)
    var _summary_circuit_depth_error = _summary_float64(_result_circuit_depth_error)
    print("MOJO_RESULT quantum_computing::circuit_depth_error", _summary_circuit_depth_error)
    var _acc_logical_qubit_overhead: Float64 = 0.0
    var _t0_logical_qubit_overhead = perf_counter_ns()
    for _ in range(N):
        _acc_logical_qubit_overhead += Float64(logical_qubit_overhead(5))
    var _t1_logical_qubit_overhead = perf_counter_ns()
    var _ns_logical_qubit_overhead = Float64(_t1_logical_qubit_overhead - _t0_logical_qubit_overhead) / Float64(N)
    print("MOJO_TIMING quantum_computing::logical_qubit_overhead", _ns_logical_qubit_overhead, _acc_logical_qubit_overhead)
    var _result_logical_qubit_overhead = logical_qubit_overhead(5)
    var _summary_logical_qubit_overhead = _summary_int(_result_logical_qubit_overhead)
    print("MOJO_RESULT quantum_computing::logical_qubit_overhead", _summary_logical_qubit_overhead)
    var _acc_decoherence_time_ratio: Float64 = 0.0
    var _t0_decoherence_time_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_decoherence_time_ratio += decoherence_time_ratio(0.5, 0.5)
    var _t1_decoherence_time_ratio = perf_counter_ns()
    var _ns_decoherence_time_ratio = Float64(_t1_decoherence_time_ratio - _t0_decoherence_time_ratio) / Float64(N)
    print("MOJO_TIMING quantum_computing::decoherence_time_ratio", _ns_decoherence_time_ratio, _acc_decoherence_time_ratio)
    var _result_decoherence_time_ratio = decoherence_time_ratio(0.5, 0.5)
    var _summary_decoherence_time_ratio = _summary_float64(_result_decoherence_time_ratio)
    print("MOJO_RESULT quantum_computing::decoherence_time_ratio", _summary_decoherence_time_ratio)
    var _acc_quantum_volume: Float64 = 0.0
    var _t0_quantum_volume = perf_counter_ns()
    for _ in range(N):
        _acc_quantum_volume += quantum_volume(5, 5)
    var _t1_quantum_volume = perf_counter_ns()
    var _ns_quantum_volume = Float64(_t1_quantum_volume - _t0_quantum_volume) / Float64(N)
    print("MOJO_TIMING quantum_computing::quantum_volume", _ns_quantum_volume, _acc_quantum_volume)
    var _result_quantum_volume = quantum_volume(5, 5)
    var _summary_quantum_volume = _summary_float64(_result_quantum_volume)
    print("MOJO_RESULT quantum_computing::quantum_volume", _summary_quantum_volume)
    var _acc_grover_iterations: Float64 = 0.0
    var _t0_grover_iterations = perf_counter_ns()
    for _ in range(N):
        _acc_grover_iterations += grover_iterations(0.5)
    var _t1_grover_iterations = perf_counter_ns()
    var _ns_grover_iterations = Float64(_t1_grover_iterations - _t0_grover_iterations) / Float64(N)
    print("MOJO_TIMING quantum_computing::grover_iterations", _ns_grover_iterations, _acc_grover_iterations)
    var _result_grover_iterations = grover_iterations(0.5)
    var _summary_grover_iterations = _summary_float64(_result_grover_iterations)
    print("MOJO_RESULT quantum_computing::grover_iterations", _summary_grover_iterations)
    var _acc_shor_qubits_needed: Float64 = 0.0
    var _t0_shor_qubits_needed = perf_counter_ns()
    for _ in range(N):
        _acc_shor_qubits_needed += Float64(shor_qubits_needed(5))
    var _t1_shor_qubits_needed = perf_counter_ns()
    var _ns_shor_qubits_needed = Float64(_t1_shor_qubits_needed - _t0_shor_qubits_needed) / Float64(N)
    print("MOJO_TIMING quantum_computing::shor_qubits_needed", _ns_shor_qubits_needed, _acc_shor_qubits_needed)
    var _result_shor_qubits_needed = shor_qubits_needed(5)
    var _summary_shor_qubits_needed = _summary_int(_result_shor_qubits_needed)
    print("MOJO_RESULT quantum_computing::shor_qubits_needed", _summary_shor_qubits_needed)
    var _acc_error_correction_threshold: Float64 = 0.0
    var _t0_error_correction_threshold = perf_counter_ns()
    for _ in range(N):
        _acc_error_correction_threshold += Float64(error_correction_threshold(0.5, 0.5))
    var _t1_error_correction_threshold = perf_counter_ns()
    var _ns_error_correction_threshold = Float64(_t1_error_correction_threshold - _t0_error_correction_threshold) / Float64(N)
    print("MOJO_TIMING quantum_computing::error_correction_threshold", _ns_error_correction_threshold, _acc_error_correction_threshold)
    var _result_error_correction_threshold = error_correction_threshold(0.5, 0.5)
    var _summary_error_correction_threshold = _summary_bool(_result_error_correction_threshold)
    print("MOJO_RESULT quantum_computing::error_correction_threshold", _summary_error_correction_threshold)
