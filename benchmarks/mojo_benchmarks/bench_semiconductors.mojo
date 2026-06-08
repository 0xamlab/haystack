"""bench_semiconductors.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from semiconductors import intrinsic_carrier_concentration, drift_velocity, resistivity, conductivity, depletion_width, built_in_potential, thermal_voltage, diode_current, mosfet_saturation_current, junction_capacitance, diffusion_length, band_gap_temperature
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

    var _acc_intrinsic_carrier_concentration: Float64 = 0.0
    var _t0_intrinsic_carrier_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_intrinsic_carrier_concentration += intrinsic_carrier_concentration(0.5, 0.5, 0.5, 0.5)
    var _t1_intrinsic_carrier_concentration = perf_counter_ns()
    var _ns_intrinsic_carrier_concentration = Float64(_t1_intrinsic_carrier_concentration - _t0_intrinsic_carrier_concentration) / Float64(N)
    print("MOJO_TIMING semiconductors::intrinsic_carrier_concentration", _ns_intrinsic_carrier_concentration, _acc_intrinsic_carrier_concentration)
    var _result_intrinsic_carrier_concentration = intrinsic_carrier_concentration(0.5, 0.5, 0.5, 0.5)
    var _summary_intrinsic_carrier_concentration = _summary_float64(_result_intrinsic_carrier_concentration)
    print("MOJO_RESULT semiconductors::intrinsic_carrier_concentration", _summary_intrinsic_carrier_concentration)
    var _acc_drift_velocity: Float64 = 0.0
    var _t0_drift_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_drift_velocity += drift_velocity(0.5, 0.5)
    var _t1_drift_velocity = perf_counter_ns()
    var _ns_drift_velocity = Float64(_t1_drift_velocity - _t0_drift_velocity) / Float64(N)
    print("MOJO_TIMING semiconductors::drift_velocity", _ns_drift_velocity, _acc_drift_velocity)
    var _result_drift_velocity = drift_velocity(0.5, 0.5)
    var _summary_drift_velocity = _summary_float64(_result_drift_velocity)
    print("MOJO_RESULT semiconductors::drift_velocity", _summary_drift_velocity)
    var _acc_resistivity: Float64 = 0.0
    var _t0_resistivity = perf_counter_ns()
    for _ in range(N):
        _acc_resistivity += resistivity(0.5, 0.5, 0.5)
    var _t1_resistivity = perf_counter_ns()
    var _ns_resistivity = Float64(_t1_resistivity - _t0_resistivity) / Float64(N)
    print("MOJO_TIMING semiconductors::resistivity", _ns_resistivity, _acc_resistivity)
    var _result_resistivity = resistivity(0.5, 0.5, 0.5)
    var _summary_resistivity = _summary_float64(_result_resistivity)
    print("MOJO_RESULT semiconductors::resistivity", _summary_resistivity)
    var _acc_conductivity: Float64 = 0.0
    var _t0_conductivity = perf_counter_ns()
    for _ in range(N):
        _acc_conductivity += conductivity(0.5, 0.5, 0.5)
    var _t1_conductivity = perf_counter_ns()
    var _ns_conductivity = Float64(_t1_conductivity - _t0_conductivity) / Float64(N)
    print("MOJO_TIMING semiconductors::conductivity", _ns_conductivity, _acc_conductivity)
    var _result_conductivity = conductivity(0.5, 0.5, 0.5)
    var _summary_conductivity = _summary_float64(_result_conductivity)
    print("MOJO_RESULT semiconductors::conductivity", _summary_conductivity)
    var _acc_depletion_width: Float64 = 0.0
    var _t0_depletion_width = perf_counter_ns()
    for _ in range(N):
        _acc_depletion_width += depletion_width(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_depletion_width = perf_counter_ns()
    var _ns_depletion_width = Float64(_t1_depletion_width - _t0_depletion_width) / Float64(N)
    print("MOJO_TIMING semiconductors::depletion_width", _ns_depletion_width, _acc_depletion_width)
    var _result_depletion_width = depletion_width(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_depletion_width = _summary_float64(_result_depletion_width)
    print("MOJO_RESULT semiconductors::depletion_width", _summary_depletion_width)
    var _acc_built_in_potential: Float64 = 0.0
    var _t0_built_in_potential = perf_counter_ns()
    for _ in range(N):
        _acc_built_in_potential += built_in_potential(0.5, 0.5, 0.5, 0.5)
    var _t1_built_in_potential = perf_counter_ns()
    var _ns_built_in_potential = Float64(_t1_built_in_potential - _t0_built_in_potential) / Float64(N)
    print("MOJO_TIMING semiconductors::built_in_potential", _ns_built_in_potential, _acc_built_in_potential)
    var _result_built_in_potential = built_in_potential(0.5, 0.5, 0.5, 0.5)
    var _summary_built_in_potential = _summary_float64(_result_built_in_potential)
    print("MOJO_RESULT semiconductors::built_in_potential", _summary_built_in_potential)
    var _acc_thermal_voltage: Float64 = 0.0
    var _t0_thermal_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_voltage += thermal_voltage(0.5, 0.5, 0.5)
    var _t1_thermal_voltage = perf_counter_ns()
    var _ns_thermal_voltage = Float64(_t1_thermal_voltage - _t0_thermal_voltage) / Float64(N)
    print("MOJO_TIMING semiconductors::thermal_voltage", _ns_thermal_voltage, _acc_thermal_voltage)
    var _result_thermal_voltage = thermal_voltage(0.5, 0.5, 0.5)
    var _summary_thermal_voltage = _summary_float64(_result_thermal_voltage)
    print("MOJO_RESULT semiconductors::thermal_voltage", _summary_thermal_voltage)
    var _acc_diode_current: Float64 = 0.0
    var _t0_diode_current = perf_counter_ns()
    for _ in range(N):
        _acc_diode_current += diode_current(0.5, 0.5, 0.5, 0.5)
    var _t1_diode_current = perf_counter_ns()
    var _ns_diode_current = Float64(_t1_diode_current - _t0_diode_current) / Float64(N)
    print("MOJO_TIMING semiconductors::diode_current", _ns_diode_current, _acc_diode_current)
    var _result_diode_current = diode_current(0.5, 0.5, 0.5, 0.5)
    var _summary_diode_current = _summary_float64(_result_diode_current)
    print("MOJO_RESULT semiconductors::diode_current", _summary_diode_current)
    var _acc_mosfet_saturation_current: Float64 = 0.0
    var _t0_mosfet_saturation_current = perf_counter_ns()
    for _ in range(N):
        _acc_mosfet_saturation_current += mosfet_saturation_current(0.5, 0.5, 0.5)
    var _t1_mosfet_saturation_current = perf_counter_ns()
    var _ns_mosfet_saturation_current = Float64(_t1_mosfet_saturation_current - _t0_mosfet_saturation_current) / Float64(N)
    print("MOJO_TIMING semiconductors::mosfet_saturation_current", _ns_mosfet_saturation_current, _acc_mosfet_saturation_current)
    var _result_mosfet_saturation_current = mosfet_saturation_current(0.5, 0.5, 0.5)
    var _summary_mosfet_saturation_current = _summary_float64(_result_mosfet_saturation_current)
    print("MOJO_RESULT semiconductors::mosfet_saturation_current", _summary_mosfet_saturation_current)
    var _acc_junction_capacitance: Float64 = 0.0
    var _t0_junction_capacitance = perf_counter_ns()
    for _ in range(N):
        _acc_junction_capacitance += junction_capacitance(1e-12, 0.3, 0.7, 0.5)
    var _t1_junction_capacitance = perf_counter_ns()
    var _ns_junction_capacitance = Float64(_t1_junction_capacitance - _t0_junction_capacitance) / Float64(N)
    print("MOJO_TIMING semiconductors::junction_capacitance", _ns_junction_capacitance, _acc_junction_capacitance)
    var _result_junction_capacitance = junction_capacitance(1e-12, 0.3, 0.7, 0.5)
    var _summary_junction_capacitance = _summary_float64(_result_junction_capacitance)
    print("MOJO_RESULT semiconductors::junction_capacitance", _summary_junction_capacitance)
    var _acc_diffusion_length: Float64 = 0.0
    var _t0_diffusion_length = perf_counter_ns()
    for _ in range(N):
        _acc_diffusion_length += diffusion_length(0.5, 0.5)
    var _t1_diffusion_length = perf_counter_ns()
    var _ns_diffusion_length = Float64(_t1_diffusion_length - _t0_diffusion_length) / Float64(N)
    print("MOJO_TIMING semiconductors::diffusion_length", _ns_diffusion_length, _acc_diffusion_length)
    var _result_diffusion_length = diffusion_length(0.5, 0.5)
    var _summary_diffusion_length = _summary_float64(_result_diffusion_length)
    print("MOJO_RESULT semiconductors::diffusion_length", _summary_diffusion_length)
    var _acc_band_gap_temperature: Float64 = 0.0
    var _t0_band_gap_temperature = perf_counter_ns()
    for _ in range(N):
        _acc_band_gap_temperature += band_gap_temperature(0.5, 0.5, 0.5, 0.5)
    var _t1_band_gap_temperature = perf_counter_ns()
    var _ns_band_gap_temperature = Float64(_t1_band_gap_temperature - _t0_band_gap_temperature) / Float64(N)
    print("MOJO_TIMING semiconductors::band_gap_temperature", _ns_band_gap_temperature, _acc_band_gap_temperature)
    var _result_band_gap_temperature = band_gap_temperature(0.5, 0.5, 0.5, 0.5)
    var _summary_band_gap_temperature = _summary_float64(_result_band_gap_temperature)
    print("MOJO_RESULT semiconductors::band_gap_temperature", _summary_band_gap_temperature)
