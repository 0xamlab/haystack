"""bench_electrochemistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from electrochemistry import nernst_cell_potential, faraday_mass_deposited, battery_capacity, energy_density, corrosion_rate, tafel_slope, exchange_current_density, charge_transfer_resistance, diffusion_limiting_current, coulombic_efficiency
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_nernst_cell_potential: Float64 = 0.0
    var _t0_nernst_cell_potential = perf_counter_ns()
    for _ in range(N):
        _acc_nernst_cell_potential += nernst_cell_potential(0.5, 0.5, 0.5, 0.5)
    var _t1_nernst_cell_potential = perf_counter_ns()
    var _ns_nernst_cell_potential = Float64(_t1_nernst_cell_potential - _t0_nernst_cell_potential) / Float64(N)
    print("MOJO_TIMING electrochemistry::nernst_cell_potential", _ns_nernst_cell_potential, _acc_nernst_cell_potential)
    var _result_nernst_cell_potential = nernst_cell_potential(0.5, 0.5, 0.5, 0.5)
    var _summary_nernst_cell_potential = _summary_float64(_result_nernst_cell_potential)
    print("MOJO_RESULT electrochemistry::nernst_cell_potential", _summary_nernst_cell_potential)
    var _acc_faraday_mass_deposited: Float64 = 0.0
    var _t0_faraday_mass_deposited = perf_counter_ns()
    for _ in range(N):
        _acc_faraday_mass_deposited += faraday_mass_deposited(0.5, 0.5, 0.5, 0.5)
    var _t1_faraday_mass_deposited = perf_counter_ns()
    var _ns_faraday_mass_deposited = Float64(_t1_faraday_mass_deposited - _t0_faraday_mass_deposited) / Float64(N)
    print("MOJO_TIMING electrochemistry::faraday_mass_deposited", _ns_faraday_mass_deposited, _acc_faraday_mass_deposited)
    var _result_faraday_mass_deposited = faraday_mass_deposited(0.5, 0.5, 0.5, 0.5)
    var _summary_faraday_mass_deposited = _summary_float64(_result_faraday_mass_deposited)
    print("MOJO_RESULT electrochemistry::faraday_mass_deposited", _summary_faraday_mass_deposited)
    var _acc_battery_capacity: Float64 = 0.0
    var _t0_battery_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_battery_capacity += battery_capacity(0.5, 0.5)
    var _t1_battery_capacity = perf_counter_ns()
    var _ns_battery_capacity = Float64(_t1_battery_capacity - _t0_battery_capacity) / Float64(N)
    print("MOJO_TIMING electrochemistry::battery_capacity", _ns_battery_capacity, _acc_battery_capacity)
    var _result_battery_capacity = battery_capacity(0.5, 0.5)
    var _summary_battery_capacity = _summary_float64(_result_battery_capacity)
    print("MOJO_RESULT electrochemistry::battery_capacity", _summary_battery_capacity)
    var _acc_energy_density: Float64 = 0.0
    var _t0_energy_density = perf_counter_ns()
    for _ in range(N):
        _acc_energy_density += energy_density(0.5, 0.5, 0.5)
    var _t1_energy_density = perf_counter_ns()
    var _ns_energy_density = Float64(_t1_energy_density - _t0_energy_density) / Float64(N)
    print("MOJO_TIMING electrochemistry::energy_density", _ns_energy_density, _acc_energy_density)
    var _result_energy_density = energy_density(0.5, 0.5, 0.5)
    var _summary_energy_density = _summary_float64(_result_energy_density)
    print("MOJO_RESULT electrochemistry::energy_density", _summary_energy_density)
    var _acc_corrosion_rate: Float64 = 0.0
    var _t0_corrosion_rate = perf_counter_ns()
    for _ in range(N):
        _acc_corrosion_rate += corrosion_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_corrosion_rate = perf_counter_ns()
    var _ns_corrosion_rate = Float64(_t1_corrosion_rate - _t0_corrosion_rate) / Float64(N)
    print("MOJO_TIMING electrochemistry::corrosion_rate", _ns_corrosion_rate, _acc_corrosion_rate)
    var _result_corrosion_rate = corrosion_rate(0.5, 0.5, 0.5, 0.5)
    var _summary_corrosion_rate = _summary_float64(_result_corrosion_rate)
    print("MOJO_RESULT electrochemistry::corrosion_rate", _summary_corrosion_rate)
    var _acc_tafel_slope: Float64 = 0.0
    var _t0_tafel_slope = perf_counter_ns()
    for _ in range(N):
        _acc_tafel_slope += tafel_slope(0.5, 0.5, 0.5)
    var _t1_tafel_slope = perf_counter_ns()
    var _ns_tafel_slope = Float64(_t1_tafel_slope - _t0_tafel_slope) / Float64(N)
    print("MOJO_TIMING electrochemistry::tafel_slope", _ns_tafel_slope, _acc_tafel_slope)
    var _result_tafel_slope = tafel_slope(0.5, 0.5, 0.5)
    var _summary_tafel_slope = _summary_float64(_result_tafel_slope)
    print("MOJO_RESULT electrochemistry::tafel_slope", _summary_tafel_slope)
    var _acc_exchange_current_density: Float64 = 0.0
    var _t0_exchange_current_density = perf_counter_ns()
    for _ in range(N):
        _acc_exchange_current_density += exchange_current_density(0.5, 0.5, 0.5, 0.5)
    var _t1_exchange_current_density = perf_counter_ns()
    var _ns_exchange_current_density = Float64(_t1_exchange_current_density - _t0_exchange_current_density) / Float64(N)
    print("MOJO_TIMING electrochemistry::exchange_current_density", _ns_exchange_current_density, _acc_exchange_current_density)
    var _result_exchange_current_density = exchange_current_density(0.5, 0.5, 0.5, 0.5)
    var _summary_exchange_current_density = _summary_float64(_result_exchange_current_density)
    print("MOJO_RESULT electrochemistry::exchange_current_density", _summary_exchange_current_density)
    var _acc_charge_transfer_resistance: Float64 = 0.0
    var _t0_charge_transfer_resistance = perf_counter_ns()
    for _ in range(N):
        _acc_charge_transfer_resistance += charge_transfer_resistance(0.5, 0.5, 0.5)
    var _t1_charge_transfer_resistance = perf_counter_ns()
    var _ns_charge_transfer_resistance = Float64(_t1_charge_transfer_resistance - _t0_charge_transfer_resistance) / Float64(N)
    print("MOJO_TIMING electrochemistry::charge_transfer_resistance", _ns_charge_transfer_resistance, _acc_charge_transfer_resistance)
    var _result_charge_transfer_resistance = charge_transfer_resistance(0.5, 0.5, 0.5)
    var _summary_charge_transfer_resistance = _summary_float64(_result_charge_transfer_resistance)
    print("MOJO_RESULT electrochemistry::charge_transfer_resistance", _summary_charge_transfer_resistance)
    var _acc_diffusion_limiting_current: Float64 = 0.0
    var _t0_diffusion_limiting_current = perf_counter_ns()
    for _ in range(N):
        _acc_diffusion_limiting_current += diffusion_limiting_current(0.5, 0.5, 0.5, 0.5)
    var _t1_diffusion_limiting_current = perf_counter_ns()
    var _ns_diffusion_limiting_current = Float64(_t1_diffusion_limiting_current - _t0_diffusion_limiting_current) / Float64(N)
    print("MOJO_TIMING electrochemistry::diffusion_limiting_current", _ns_diffusion_limiting_current, _acc_diffusion_limiting_current)
    var _result_diffusion_limiting_current = diffusion_limiting_current(0.5, 0.5, 0.5, 0.5)
    var _summary_diffusion_limiting_current = _summary_float64(_result_diffusion_limiting_current)
    print("MOJO_RESULT electrochemistry::diffusion_limiting_current", _summary_diffusion_limiting_current)
    var _acc_coulombic_efficiency: Float64 = 0.0
    var _t0_coulombic_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_coulombic_efficiency += coulombic_efficiency(0.5, 0.5)
    var _t1_coulombic_efficiency = perf_counter_ns()
    var _ns_coulombic_efficiency = Float64(_t1_coulombic_efficiency - _t0_coulombic_efficiency) / Float64(N)
    print("MOJO_TIMING electrochemistry::coulombic_efficiency", _ns_coulombic_efficiency, _acc_coulombic_efficiency)
    var _result_coulombic_efficiency = coulombic_efficiency(0.5, 0.5)
    var _summary_coulombic_efficiency = _summary_float64(_result_coulombic_efficiency)
    print("MOJO_RESULT electrochemistry::coulombic_efficiency", _summary_coulombic_efficiency)
