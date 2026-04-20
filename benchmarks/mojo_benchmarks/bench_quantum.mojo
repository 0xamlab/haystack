"""bench_quantum.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from quantum import qubit_zero, qubit_one, hadamard, pauli_x, pauli_z, phase_gate, measure_probability, qubit_norm, bell_state, expectation_z, bloch_coords
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

    var _acc_qubit_zero: Float64 = 0.0
    var _t0_qubit_zero = perf_counter_ns()
    for _ in range(N):
        var _r_qubit_zero = qubit_zero()
        _acc_qubit_zero += Float64(len(_r_qubit_zero))
    var _t1_qubit_zero = perf_counter_ns()
    var _ns_qubit_zero = Float64(_t1_qubit_zero - _t0_qubit_zero) / Float64(N)
    print("MOJO_TIMING quantum::qubit_zero", _ns_qubit_zero, _acc_qubit_zero)
    var _acc_qubit_one: Float64 = 0.0
    var _t0_qubit_one = perf_counter_ns()
    for _ in range(N):
        var _r_qubit_one = qubit_one()
        _acc_qubit_one += Float64(len(_r_qubit_one))
    var _t1_qubit_one = perf_counter_ns()
    var _ns_qubit_one = Float64(_t1_qubit_one - _t0_qubit_one) / Float64(N)
    print("MOJO_TIMING quantum::qubit_one", _ns_qubit_one, _acc_qubit_one)
    var _acc_hadamard: Float64 = 0.0
    var _t0_hadamard = perf_counter_ns()
    for _ in range(N):
        var _r_hadamard = hadamard(_lf5)
        _acc_hadamard += Float64(len(_r_hadamard))
    var _t1_hadamard = perf_counter_ns()
    var _ns_hadamard = Float64(_t1_hadamard - _t0_hadamard) / Float64(N)
    print("MOJO_TIMING quantum::hadamard", _ns_hadamard, _acc_hadamard)
    var _acc_pauli_x: Float64 = 0.0
    var _t0_pauli_x = perf_counter_ns()
    for _ in range(N):
        var _r_pauli_x = pauli_x(_lf5)
        _acc_pauli_x += Float64(len(_r_pauli_x))
    var _t1_pauli_x = perf_counter_ns()
    var _ns_pauli_x = Float64(_t1_pauli_x - _t0_pauli_x) / Float64(N)
    print("MOJO_TIMING quantum::pauli_x", _ns_pauli_x, _acc_pauli_x)
    var _acc_pauli_z: Float64 = 0.0
    var _t0_pauli_z = perf_counter_ns()
    for _ in range(N):
        var _r_pauli_z = pauli_z(_lf5)
        _acc_pauli_z += Float64(len(_r_pauli_z))
    var _t1_pauli_z = perf_counter_ns()
    var _ns_pauli_z = Float64(_t1_pauli_z - _t0_pauli_z) / Float64(N)
    print("MOJO_TIMING quantum::pauli_z", _ns_pauli_z, _acc_pauli_z)
    var _acc_phase_gate: Float64 = 0.0
    var _t0_phase_gate = perf_counter_ns()
    for _ in range(N):
        var _r_phase_gate = phase_gate(_lf5, 0.5)
        _acc_phase_gate += Float64(len(_r_phase_gate))
    var _t1_phase_gate = perf_counter_ns()
    var _ns_phase_gate = Float64(_t1_phase_gate - _t0_phase_gate) / Float64(N)
    print("MOJO_TIMING quantum::phase_gate", _ns_phase_gate, _acc_phase_gate)
    var _acc_measure_probability: Float64 = 0.0
    var _t0_measure_probability = perf_counter_ns()
    for _ in range(N):
        var _r_measure_probability = measure_probability(_lf5)
        _acc_measure_probability += Float64(len(_r_measure_probability))
    var _t1_measure_probability = perf_counter_ns()
    var _ns_measure_probability = Float64(_t1_measure_probability - _t0_measure_probability) / Float64(N)
    print("MOJO_TIMING quantum::measure_probability", _ns_measure_probability, _acc_measure_probability)
    var _acc_qubit_norm: Float64 = 0.0
    var _t0_qubit_norm = perf_counter_ns()
    for _ in range(N):
        _acc_qubit_norm += qubit_norm(_lf5)
    var _t1_qubit_norm = perf_counter_ns()
    var _ns_qubit_norm = Float64(_t1_qubit_norm - _t0_qubit_norm) / Float64(N)
    print("MOJO_TIMING quantum::qubit_norm", _ns_qubit_norm, _acc_qubit_norm)
    var _acc_bell_state: Float64 = 0.0
    var _t0_bell_state = perf_counter_ns()
    for _ in range(N):
        var _r_bell_state = bell_state()
        _acc_bell_state += Float64(len(_r_bell_state))
    var _t1_bell_state = perf_counter_ns()
    var _ns_bell_state = Float64(_t1_bell_state - _t0_bell_state) / Float64(N)
    print("MOJO_TIMING quantum::bell_state", _ns_bell_state, _acc_bell_state)
    var _acc_expectation_z: Float64 = 0.0
    var _t0_expectation_z = perf_counter_ns()
    for _ in range(N):
        _acc_expectation_z += expectation_z(_lf5)
    var _t1_expectation_z = perf_counter_ns()
    var _ns_expectation_z = Float64(_t1_expectation_z - _t0_expectation_z) / Float64(N)
    print("MOJO_TIMING quantum::expectation_z", _ns_expectation_z, _acc_expectation_z)
    var _acc_bloch_coords: Float64 = 0.0
    var _t0_bloch_coords = perf_counter_ns()
    for _ in range(N):
        var _r_bloch_coords = bloch_coords(_lf5)
        _acc_bloch_coords += Float64(len(_r_bloch_coords))
    var _t1_bloch_coords = perf_counter_ns()
    var _ns_bloch_coords = Float64(_t1_bloch_coords - _t0_bloch_coords) / Float64(N)
    print("MOJO_TIMING quantum::bloch_coords", _ns_bloch_coords, _acc_bloch_coords)
