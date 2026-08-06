"""bench_solar_energy.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from solar_energy import solar_irradiance_on_surface, panel_power_output, temperature_derate, cell_temperature_noct, solar_declination, hour_angle, solar_altitude, capacity_factor_solar, lcoe, payback_period, inverter_efficiency, string_voltage
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

    var _acc_solar_irradiance_on_surface: Float64 = 0.0
    var _t0_solar_irradiance_on_surface = perf_counter_ns()
    for _ in range(N):
        _acc_solar_irradiance_on_surface += solar_irradiance_on_surface(0.5, 0.5)
    var _t1_solar_irradiance_on_surface = perf_counter_ns()
    var _ns_solar_irradiance_on_surface = Float64(_t1_solar_irradiance_on_surface - _t0_solar_irradiance_on_surface) / Float64(N)
    print("MOJO_TIMING solar_energy::solar_irradiance_on_surface", _ns_solar_irradiance_on_surface, _acc_solar_irradiance_on_surface)
    var _result_solar_irradiance_on_surface = solar_irradiance_on_surface(0.5, 0.5)
    var _summary_solar_irradiance_on_surface = _summary_float64(_result_solar_irradiance_on_surface)
    print("MOJO_RESULT solar_energy::solar_irradiance_on_surface", _summary_solar_irradiance_on_surface)
    var _acc_panel_power_output: Float64 = 0.0
    var _t0_panel_power_output = perf_counter_ns()
    for _ in range(N):
        _acc_panel_power_output += panel_power_output(0.5, 0.5, 0.5)
    var _t1_panel_power_output = perf_counter_ns()
    var _ns_panel_power_output = Float64(_t1_panel_power_output - _t0_panel_power_output) / Float64(N)
    print("MOJO_TIMING solar_energy::panel_power_output", _ns_panel_power_output, _acc_panel_power_output)
    var _result_panel_power_output = panel_power_output(0.5, 0.5, 0.5)
    var _summary_panel_power_output = _summary_float64(_result_panel_power_output)
    print("MOJO_RESULT solar_energy::panel_power_output", _summary_panel_power_output)
    var _acc_temperature_derate: Float64 = 0.0
    var _t0_temperature_derate = perf_counter_ns()
    for _ in range(N):
        _acc_temperature_derate += temperature_derate(0.5, 0.5, 0.5, 0.5)
    var _t1_temperature_derate = perf_counter_ns()
    var _ns_temperature_derate = Float64(_t1_temperature_derate - _t0_temperature_derate) / Float64(N)
    print("MOJO_TIMING solar_energy::temperature_derate", _ns_temperature_derate, _acc_temperature_derate)
    var _result_temperature_derate = temperature_derate(0.5, 0.5, 0.5, 0.5)
    var _summary_temperature_derate = _summary_float64(_result_temperature_derate)
    print("MOJO_RESULT solar_energy::temperature_derate", _summary_temperature_derate)
    var _acc_cell_temperature_noct: Float64 = 0.0
    var _t0_cell_temperature_noct = perf_counter_ns()
    for _ in range(N):
        _acc_cell_temperature_noct += cell_temperature_noct(0.5, 0.5, 0.5)
    var _t1_cell_temperature_noct = perf_counter_ns()
    var _ns_cell_temperature_noct = Float64(_t1_cell_temperature_noct - _t0_cell_temperature_noct) / Float64(N)
    print("MOJO_TIMING solar_energy::cell_temperature_noct", _ns_cell_temperature_noct, _acc_cell_temperature_noct)
    var _result_cell_temperature_noct = cell_temperature_noct(0.5, 0.5, 0.5)
    var _summary_cell_temperature_noct = _summary_float64(_result_cell_temperature_noct)
    print("MOJO_RESULT solar_energy::cell_temperature_noct", _summary_cell_temperature_noct)
    var _acc_solar_declination: Float64 = 0.0
    var _t0_solar_declination = perf_counter_ns()
    for _ in range(N):
        _acc_solar_declination += solar_declination(0.5)
    var _t1_solar_declination = perf_counter_ns()
    var _ns_solar_declination = Float64(_t1_solar_declination - _t0_solar_declination) / Float64(N)
    print("MOJO_TIMING solar_energy::solar_declination", _ns_solar_declination, _acc_solar_declination)
    var _result_solar_declination = solar_declination(0.5)
    var _summary_solar_declination = _summary_float64(_result_solar_declination)
    print("MOJO_RESULT solar_energy::solar_declination", _summary_solar_declination)
    var _acc_hour_angle: Float64 = 0.0
    var _t0_hour_angle = perf_counter_ns()
    for _ in range(N):
        _acc_hour_angle += hour_angle(0.5)
    var _t1_hour_angle = perf_counter_ns()
    var _ns_hour_angle = Float64(_t1_hour_angle - _t0_hour_angle) / Float64(N)
    print("MOJO_TIMING solar_energy::hour_angle", _ns_hour_angle, _acc_hour_angle)
    var _result_hour_angle = hour_angle(0.5)
    var _summary_hour_angle = _summary_float64(_result_hour_angle)
    print("MOJO_RESULT solar_energy::hour_angle", _summary_hour_angle)
    var _acc_solar_altitude: Float64 = 0.0
    var _t0_solar_altitude = perf_counter_ns()
    for _ in range(N):
        _acc_solar_altitude += solar_altitude(0.5, 0.5, 0.5)
    var _t1_solar_altitude = perf_counter_ns()
    var _ns_solar_altitude = Float64(_t1_solar_altitude - _t0_solar_altitude) / Float64(N)
    print("MOJO_TIMING solar_energy::solar_altitude", _ns_solar_altitude, _acc_solar_altitude)
    var _result_solar_altitude = solar_altitude(0.5, 0.5, 0.5)
    var _summary_solar_altitude = _summary_float64(_result_solar_altitude)
    print("MOJO_RESULT solar_energy::solar_altitude", _summary_solar_altitude)
    var _acc_capacity_factor_solar: Float64 = 0.0
    var _t0_capacity_factor_solar = perf_counter_ns()
    for _ in range(N):
        _acc_capacity_factor_solar += capacity_factor_solar(0.5, 0.5, 0.5)
    var _t1_capacity_factor_solar = perf_counter_ns()
    var _ns_capacity_factor_solar = Float64(_t1_capacity_factor_solar - _t0_capacity_factor_solar) / Float64(N)
    print("MOJO_TIMING solar_energy::capacity_factor_solar", _ns_capacity_factor_solar, _acc_capacity_factor_solar)
    var _result_capacity_factor_solar = capacity_factor_solar(0.5, 0.5, 0.5)
    var _summary_capacity_factor_solar = _summary_float64(_result_capacity_factor_solar)
    print("MOJO_RESULT solar_energy::capacity_factor_solar", _summary_capacity_factor_solar)
    var _acc_lcoe: Float64 = 0.0
    var _t0_lcoe = perf_counter_ns()
    for _ in range(N):
        _acc_lcoe += lcoe(0.5, 0.5)
    var _t1_lcoe = perf_counter_ns()
    var _ns_lcoe = Float64(_t1_lcoe - _t0_lcoe) / Float64(N)
    print("MOJO_TIMING solar_energy::lcoe", _ns_lcoe, _acc_lcoe)
    var _result_lcoe = lcoe(0.5, 0.5)
    var _summary_lcoe = _summary_float64(_result_lcoe)
    print("MOJO_RESULT solar_energy::lcoe", _summary_lcoe)
    var _acc_payback_period: Float64 = 0.0
    var _t0_payback_period = perf_counter_ns()
    for _ in range(N):
        _acc_payback_period += payback_period(0.5, 0.5)
    var _t1_payback_period = perf_counter_ns()
    var _ns_payback_period = Float64(_t1_payback_period - _t0_payback_period) / Float64(N)
    print("MOJO_TIMING solar_energy::payback_period", _ns_payback_period, _acc_payback_period)
    var _result_payback_period = payback_period(0.5, 0.5)
    var _summary_payback_period = _summary_float64(_result_payback_period)
    print("MOJO_RESULT solar_energy::payback_period", _summary_payback_period)
    var _acc_inverter_efficiency: Float64 = 0.0
    var _t0_inverter_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_inverter_efficiency += inverter_efficiency(0.5, 0.5)
    var _t1_inverter_efficiency = perf_counter_ns()
    var _ns_inverter_efficiency = Float64(_t1_inverter_efficiency - _t0_inverter_efficiency) / Float64(N)
    print("MOJO_TIMING solar_energy::inverter_efficiency", _ns_inverter_efficiency, _acc_inverter_efficiency)
    var _result_inverter_efficiency = inverter_efficiency(0.5, 0.5)
    var _summary_inverter_efficiency = _summary_float64(_result_inverter_efficiency)
    print("MOJO_RESULT solar_energy::inverter_efficiency", _summary_inverter_efficiency)
    var _acc_string_voltage: Float64 = 0.0
    var _t0_string_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_string_voltage += string_voltage(0.5, 0.5)
    var _t1_string_voltage = perf_counter_ns()
    var _ns_string_voltage = Float64(_t1_string_voltage - _t0_string_voltage) / Float64(N)
    print("MOJO_TIMING solar_energy::string_voltage", _ns_string_voltage, _acc_string_voltage)
    var _result_string_voltage = string_voltage(0.5, 0.5)
    var _summary_string_voltage = _summary_float64(_result_string_voltage)
    print("MOJO_RESULT solar_energy::string_voltage", _summary_string_voltage)
