"""bench_semiconductors.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from semiconductors import intrinsic_carrier_concentration, drift_velocity, resistivity, conductivity, depletion_width, built_in_potential, thermal_voltage, diode_current, mosfet_saturation_current, junction_capacitance, diffusion_length, band_gap_temperature
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

    var _acc_intrinsic_carrier_concentration: Float64 = 0.0
    var _t0_intrinsic_carrier_concentration = perf_counter_ns()
    for _ in range(N):
        _acc_intrinsic_carrier_concentration += intrinsic_carrier_concentration(0.5, 0.5, 0.5, 0.5)
    var _t1_intrinsic_carrier_concentration = perf_counter_ns()
    var _ns_intrinsic_carrier_concentration = Float64(_t1_intrinsic_carrier_concentration - _t0_intrinsic_carrier_concentration) / Float64(N)
    print("MOJO_TIMING semiconductors::intrinsic_carrier_concentration", _ns_intrinsic_carrier_concentration, _acc_intrinsic_carrier_concentration)
    var _acc_drift_velocity: Float64 = 0.0
    var _t0_drift_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_drift_velocity += drift_velocity(0.5, 0.5)
    var _t1_drift_velocity = perf_counter_ns()
    var _ns_drift_velocity = Float64(_t1_drift_velocity - _t0_drift_velocity) / Float64(N)
    print("MOJO_TIMING semiconductors::drift_velocity", _ns_drift_velocity, _acc_drift_velocity)
    var _acc_resistivity: Float64 = 0.0
    var _t0_resistivity = perf_counter_ns()
    for _ in range(N):
        _acc_resistivity += resistivity(0.5, 0.5, 0.5)
    var _t1_resistivity = perf_counter_ns()
    var _ns_resistivity = Float64(_t1_resistivity - _t0_resistivity) / Float64(N)
    print("MOJO_TIMING semiconductors::resistivity", _ns_resistivity, _acc_resistivity)
    var _acc_conductivity: Float64 = 0.0
    var _t0_conductivity = perf_counter_ns()
    for _ in range(N):
        _acc_conductivity += conductivity(0.5, 0.5, 0.5)
    var _t1_conductivity = perf_counter_ns()
    var _ns_conductivity = Float64(_t1_conductivity - _t0_conductivity) / Float64(N)
    print("MOJO_TIMING semiconductors::conductivity", _ns_conductivity, _acc_conductivity)
    var _acc_depletion_width: Float64 = 0.0
    var _t0_depletion_width = perf_counter_ns()
    for _ in range(N):
        _acc_depletion_width += depletion_width(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_depletion_width = perf_counter_ns()
    var _ns_depletion_width = Float64(_t1_depletion_width - _t0_depletion_width) / Float64(N)
    print("MOJO_TIMING semiconductors::depletion_width", _ns_depletion_width, _acc_depletion_width)
    var _acc_built_in_potential: Float64 = 0.0
    var _t0_built_in_potential = perf_counter_ns()
    for _ in range(N):
        _acc_built_in_potential += built_in_potential(0.5, 0.5, 0.5, 0.5)
    var _t1_built_in_potential = perf_counter_ns()
    var _ns_built_in_potential = Float64(_t1_built_in_potential - _t0_built_in_potential) / Float64(N)
    print("MOJO_TIMING semiconductors::built_in_potential", _ns_built_in_potential, _acc_built_in_potential)
    var _acc_thermal_voltage: Float64 = 0.0
    var _t0_thermal_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_voltage += thermal_voltage(0.5, 0.5, 0.5)
    var _t1_thermal_voltage = perf_counter_ns()
    var _ns_thermal_voltage = Float64(_t1_thermal_voltage - _t0_thermal_voltage) / Float64(N)
    print("MOJO_TIMING semiconductors::thermal_voltage", _ns_thermal_voltage, _acc_thermal_voltage)
    var _acc_diode_current: Float64 = 0.0
    var _t0_diode_current = perf_counter_ns()
    for _ in range(N):
        _acc_diode_current += diode_current(0.5, 0.5, 0.5, 0.5)
    var _t1_diode_current = perf_counter_ns()
    var _ns_diode_current = Float64(_t1_diode_current - _t0_diode_current) / Float64(N)
    print("MOJO_TIMING semiconductors::diode_current", _ns_diode_current, _acc_diode_current)
    var _acc_mosfet_saturation_current: Float64 = 0.0
    var _t0_mosfet_saturation_current = perf_counter_ns()
    for _ in range(N):
        _acc_mosfet_saturation_current += mosfet_saturation_current(0.5, 0.5, 0.5)
    var _t1_mosfet_saturation_current = perf_counter_ns()
    var _ns_mosfet_saturation_current = Float64(_t1_mosfet_saturation_current - _t0_mosfet_saturation_current) / Float64(N)
    print("MOJO_TIMING semiconductors::mosfet_saturation_current", _ns_mosfet_saturation_current, _acc_mosfet_saturation_current)
    var _acc_junction_capacitance: Float64 = 0.0
    var _t0_junction_capacitance = perf_counter_ns()
    for _ in range(N):
        _acc_junction_capacitance += junction_capacitance(1e-12, 0.3, 0.7, 0.5)
    var _t1_junction_capacitance = perf_counter_ns()
    var _ns_junction_capacitance = Float64(_t1_junction_capacitance - _t0_junction_capacitance) / Float64(N)
    print("MOJO_TIMING semiconductors::junction_capacitance", _ns_junction_capacitance, _acc_junction_capacitance)
    var _acc_diffusion_length: Float64 = 0.0
    var _t0_diffusion_length = perf_counter_ns()
    for _ in range(N):
        _acc_diffusion_length += diffusion_length(0.5, 0.5)
    var _t1_diffusion_length = perf_counter_ns()
    var _ns_diffusion_length = Float64(_t1_diffusion_length - _t0_diffusion_length) / Float64(N)
    print("MOJO_TIMING semiconductors::diffusion_length", _ns_diffusion_length, _acc_diffusion_length)
    var _acc_band_gap_temperature: Float64 = 0.0
    var _t0_band_gap_temperature = perf_counter_ns()
    for _ in range(N):
        _acc_band_gap_temperature += band_gap_temperature(0.5, 0.5, 0.5, 0.5)
    var _t1_band_gap_temperature = perf_counter_ns()
    var _ns_band_gap_temperature = Float64(_t1_band_gap_temperature - _t0_band_gap_temperature) / Float64(N)
    print("MOJO_TIMING semiconductors::band_gap_temperature", _ns_band_gap_temperature, _acc_band_gap_temperature)
