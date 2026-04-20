"""bench_solar_energy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from solar_energy import solar_irradiance_on_surface, panel_power_output, temperature_derate, cell_temperature_noct, solar_declination, hour_angle, solar_altitude, capacity_factor_solar, lcoe, payback_period, inverter_efficiency, string_voltage
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

    var _acc_solar_irradiance_on_surface: Float64 = 0.0
    var _t0_solar_irradiance_on_surface = perf_counter_ns()
    for _ in range(N):
        _acc_solar_irradiance_on_surface += solar_irradiance_on_surface(0.5, 0.5)
    var _t1_solar_irradiance_on_surface = perf_counter_ns()
    var _ns_solar_irradiance_on_surface = Float64(_t1_solar_irradiance_on_surface - _t0_solar_irradiance_on_surface) / Float64(N)
    print("MOJO_TIMING solar_energy::solar_irradiance_on_surface", _ns_solar_irradiance_on_surface, _acc_solar_irradiance_on_surface)
    var _acc_panel_power_output: Float64 = 0.0
    var _t0_panel_power_output = perf_counter_ns()
    for _ in range(N):
        _acc_panel_power_output += panel_power_output(0.5, 0.5, 0.5)
    var _t1_panel_power_output = perf_counter_ns()
    var _ns_panel_power_output = Float64(_t1_panel_power_output - _t0_panel_power_output) / Float64(N)
    print("MOJO_TIMING solar_energy::panel_power_output", _ns_panel_power_output, _acc_panel_power_output)
    var _acc_temperature_derate: Float64 = 0.0
    var _t0_temperature_derate = perf_counter_ns()
    for _ in range(N):
        _acc_temperature_derate += temperature_derate(0.5, 0.5, 0.5, 0.5)
    var _t1_temperature_derate = perf_counter_ns()
    var _ns_temperature_derate = Float64(_t1_temperature_derate - _t0_temperature_derate) / Float64(N)
    print("MOJO_TIMING solar_energy::temperature_derate", _ns_temperature_derate, _acc_temperature_derate)
    var _acc_cell_temperature_noct: Float64 = 0.0
    var _t0_cell_temperature_noct = perf_counter_ns()
    for _ in range(N):
        _acc_cell_temperature_noct += cell_temperature_noct(0.5, 0.5, 0.5)
    var _t1_cell_temperature_noct = perf_counter_ns()
    var _ns_cell_temperature_noct = Float64(_t1_cell_temperature_noct - _t0_cell_temperature_noct) / Float64(N)
    print("MOJO_TIMING solar_energy::cell_temperature_noct", _ns_cell_temperature_noct, _acc_cell_temperature_noct)
    var _acc_solar_declination: Float64 = 0.0
    var _t0_solar_declination = perf_counter_ns()
    for _ in range(N):
        _acc_solar_declination += solar_declination(0.5)
    var _t1_solar_declination = perf_counter_ns()
    var _ns_solar_declination = Float64(_t1_solar_declination - _t0_solar_declination) / Float64(N)
    print("MOJO_TIMING solar_energy::solar_declination", _ns_solar_declination, _acc_solar_declination)
    var _acc_hour_angle: Float64 = 0.0
    var _t0_hour_angle = perf_counter_ns()
    for _ in range(N):
        _acc_hour_angle += hour_angle(0.5)
    var _t1_hour_angle = perf_counter_ns()
    var _ns_hour_angle = Float64(_t1_hour_angle - _t0_hour_angle) / Float64(N)
    print("MOJO_TIMING solar_energy::hour_angle", _ns_hour_angle, _acc_hour_angle)
    var _acc_solar_altitude: Float64 = 0.0
    var _t0_solar_altitude = perf_counter_ns()
    for _ in range(N):
        _acc_solar_altitude += solar_altitude(0.5, 0.5, 0.5)
    var _t1_solar_altitude = perf_counter_ns()
    var _ns_solar_altitude = Float64(_t1_solar_altitude - _t0_solar_altitude) / Float64(N)
    print("MOJO_TIMING solar_energy::solar_altitude", _ns_solar_altitude, _acc_solar_altitude)
    var _acc_capacity_factor_solar: Float64 = 0.0
    var _t0_capacity_factor_solar = perf_counter_ns()
    for _ in range(N):
        _acc_capacity_factor_solar += capacity_factor_solar(0.5, 0.5, 0.5)
    var _t1_capacity_factor_solar = perf_counter_ns()
    var _ns_capacity_factor_solar = Float64(_t1_capacity_factor_solar - _t0_capacity_factor_solar) / Float64(N)
    print("MOJO_TIMING solar_energy::capacity_factor_solar", _ns_capacity_factor_solar, _acc_capacity_factor_solar)
    var _acc_lcoe: Float64 = 0.0
    var _t0_lcoe = perf_counter_ns()
    for _ in range(N):
        _acc_lcoe += lcoe(0.5, 0.5)
    var _t1_lcoe = perf_counter_ns()
    var _ns_lcoe = Float64(_t1_lcoe - _t0_lcoe) / Float64(N)
    print("MOJO_TIMING solar_energy::lcoe", _ns_lcoe, _acc_lcoe)
    var _acc_payback_period: Float64 = 0.0
    var _t0_payback_period = perf_counter_ns()
    for _ in range(N):
        _acc_payback_period += payback_period(0.5, 0.5)
    var _t1_payback_period = perf_counter_ns()
    var _ns_payback_period = Float64(_t1_payback_period - _t0_payback_period) / Float64(N)
    print("MOJO_TIMING solar_energy::payback_period", _ns_payback_period, _acc_payback_period)
    var _acc_inverter_efficiency: Float64 = 0.0
    var _t0_inverter_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_inverter_efficiency += inverter_efficiency(0.5, 0.5)
    var _t1_inverter_efficiency = perf_counter_ns()
    var _ns_inverter_efficiency = Float64(_t1_inverter_efficiency - _t0_inverter_efficiency) / Float64(N)
    print("MOJO_TIMING solar_energy::inverter_efficiency", _ns_inverter_efficiency, _acc_inverter_efficiency)
    var _acc_string_voltage: Float64 = 0.0
    var _t0_string_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_string_voltage += string_voltage(0.5, 0.5)
    var _t1_string_voltage = perf_counter_ns()
    var _ns_string_voltage = Float64(_t1_string_voltage - _t0_string_voltage) / Float64(N)
    print("MOJO_TIMING solar_energy::string_voltage", _ns_string_voltage, _acc_string_voltage)
