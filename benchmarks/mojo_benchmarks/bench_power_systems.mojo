"""bench_power_systems.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from power_systems import active_power, reactive_power, apparent_power, power_factor_from_pq, three_phase_power, transformer_turns_ratio, transformer_secondary_voltage, line_loss, voltage_drop, power_efficiency, capacitor_reactive_power, load_factor
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

    var _acc_active_power: Float64 = 0.0
    var _t0_active_power = perf_counter_ns()
    for _ in range(N):
        _acc_active_power += active_power(0.5, 0.5, 0.5)
    var _t1_active_power = perf_counter_ns()
    var _ns_active_power = Float64(_t1_active_power - _t0_active_power) / Float64(N)
    print("MOJO_TIMING power_systems::active_power", _ns_active_power, _acc_active_power)
    var _acc_reactive_power: Float64 = 0.0
    var _t0_reactive_power = perf_counter_ns()
    for _ in range(N):
        _acc_reactive_power += reactive_power(0.5, 0.5, 0.5)
    var _t1_reactive_power = perf_counter_ns()
    var _ns_reactive_power = Float64(_t1_reactive_power - _t0_reactive_power) / Float64(N)
    print("MOJO_TIMING power_systems::reactive_power", _ns_reactive_power, _acc_reactive_power)
    var _acc_apparent_power: Float64 = 0.0
    var _t0_apparent_power = perf_counter_ns()
    for _ in range(N):
        _acc_apparent_power += apparent_power(0.5, 0.5)
    var _t1_apparent_power = perf_counter_ns()
    var _ns_apparent_power = Float64(_t1_apparent_power - _t0_apparent_power) / Float64(N)
    print("MOJO_TIMING power_systems::apparent_power", _ns_apparent_power, _acc_apparent_power)
    var _acc_power_factor_from_pq: Float64 = 0.0
    var _t0_power_factor_from_pq = perf_counter_ns()
    for _ in range(N):
        _acc_power_factor_from_pq += power_factor_from_pq(0.5, 0.5)
    var _t1_power_factor_from_pq = perf_counter_ns()
    var _ns_power_factor_from_pq = Float64(_t1_power_factor_from_pq - _t0_power_factor_from_pq) / Float64(N)
    print("MOJO_TIMING power_systems::power_factor_from_pq", _ns_power_factor_from_pq, _acc_power_factor_from_pq)
    var _acc_three_phase_power: Float64 = 0.0
    var _t0_three_phase_power = perf_counter_ns()
    for _ in range(N):
        _acc_three_phase_power += three_phase_power(0.5, 0.5, 0.5)
    var _t1_three_phase_power = perf_counter_ns()
    var _ns_three_phase_power = Float64(_t1_three_phase_power - _t0_three_phase_power) / Float64(N)
    print("MOJO_TIMING power_systems::three_phase_power", _ns_three_phase_power, _acc_three_phase_power)
    var _acc_transformer_turns_ratio: Float64 = 0.0
    var _t0_transformer_turns_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_transformer_turns_ratio += transformer_turns_ratio(0.5, 0.5)
    var _t1_transformer_turns_ratio = perf_counter_ns()
    var _ns_transformer_turns_ratio = Float64(_t1_transformer_turns_ratio - _t0_transformer_turns_ratio) / Float64(N)
    print("MOJO_TIMING power_systems::transformer_turns_ratio", _ns_transformer_turns_ratio, _acc_transformer_turns_ratio)
    var _acc_transformer_secondary_voltage: Float64 = 0.0
    var _t0_transformer_secondary_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_transformer_secondary_voltage += transformer_secondary_voltage(0.5, 0.5)
    var _t1_transformer_secondary_voltage = perf_counter_ns()
    var _ns_transformer_secondary_voltage = Float64(_t1_transformer_secondary_voltage - _t0_transformer_secondary_voltage) / Float64(N)
    print("MOJO_TIMING power_systems::transformer_secondary_voltage", _ns_transformer_secondary_voltage, _acc_transformer_secondary_voltage)
    var _acc_line_loss: Float64 = 0.0
    var _t0_line_loss = perf_counter_ns()
    for _ in range(N):
        _acc_line_loss += line_loss(0.5, 0.5)
    var _t1_line_loss = perf_counter_ns()
    var _ns_line_loss = Float64(_t1_line_loss - _t0_line_loss) / Float64(N)
    print("MOJO_TIMING power_systems::line_loss", _ns_line_loss, _acc_line_loss)
    var _acc_voltage_drop: Float64 = 0.0
    var _t0_voltage_drop = perf_counter_ns()
    for _ in range(N):
        _acc_voltage_drop += voltage_drop(0.5, 0.5, 0.5)
    var _t1_voltage_drop = perf_counter_ns()
    var _ns_voltage_drop = Float64(_t1_voltage_drop - _t0_voltage_drop) / Float64(N)
    print("MOJO_TIMING power_systems::voltage_drop", _ns_voltage_drop, _acc_voltage_drop)
    var _acc_power_efficiency: Float64 = 0.0
    var _t0_power_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_power_efficiency += power_efficiency(0.5, 0.5)
    var _t1_power_efficiency = perf_counter_ns()
    var _ns_power_efficiency = Float64(_t1_power_efficiency - _t0_power_efficiency) / Float64(N)
    print("MOJO_TIMING power_systems::power_efficiency", _ns_power_efficiency, _acc_power_efficiency)
    var _acc_capacitor_reactive_power: Float64 = 0.0
    var _t0_capacitor_reactive_power = perf_counter_ns()
    for _ in range(N):
        _acc_capacitor_reactive_power += capacitor_reactive_power(0.5, 0.5, 0.5)
    var _t1_capacitor_reactive_power = perf_counter_ns()
    var _ns_capacitor_reactive_power = Float64(_t1_capacitor_reactive_power - _t0_capacitor_reactive_power) / Float64(N)
    print("MOJO_TIMING power_systems::capacitor_reactive_power", _ns_capacitor_reactive_power, _acc_capacitor_reactive_power)
    var _acc_load_factor: Float64 = 0.0
    var _t0_load_factor = perf_counter_ns()
    for _ in range(N):
        _acc_load_factor += load_factor(0.5, 0.5)
    var _t1_load_factor = perf_counter_ns()
    var _ns_load_factor = Float64(_t1_load_factor - _t0_load_factor) / Float64(N)
    print("MOJO_TIMING power_systems::load_factor", _ns_load_factor, _acc_load_factor)
