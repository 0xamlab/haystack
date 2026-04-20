"""bench_photovoltaics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from photovoltaics import cell_efficiency, fill_factor, power_output, temperature_coefficient, energy_yield, irradiance_on_tilted_plane, lcoe_solar, capacity_factor, peak_sun_hours, system_pr
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

    var _acc_cell_efficiency: Float64 = 0.0
    var _t0_cell_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_cell_efficiency += cell_efficiency(0.5, 0.5, 0.5)
    var _t1_cell_efficiency = perf_counter_ns()
    var _ns_cell_efficiency = Float64(_t1_cell_efficiency - _t0_cell_efficiency) / Float64(N)
    print("MOJO_TIMING photovoltaics::cell_efficiency", _ns_cell_efficiency, _acc_cell_efficiency)
    var _acc_fill_factor: Float64 = 0.0
    var _t0_fill_factor = perf_counter_ns()
    for _ in range(N):
        _acc_fill_factor += fill_factor(0.5, 0.5, 0.5)
    var _t1_fill_factor = perf_counter_ns()
    var _ns_fill_factor = Float64(_t1_fill_factor - _t0_fill_factor) / Float64(N)
    print("MOJO_TIMING photovoltaics::fill_factor", _ns_fill_factor, _acc_fill_factor)
    var _acc_power_output: Float64 = 0.0
    var _t0_power_output = perf_counter_ns()
    for _ in range(N):
        _acc_power_output += power_output(0.5, 0.5, 0.5)
    var _t1_power_output = perf_counter_ns()
    var _ns_power_output = Float64(_t1_power_output - _t0_power_output) / Float64(N)
    print("MOJO_TIMING photovoltaics::power_output", _ns_power_output, _acc_power_output)
    var _acc_temperature_coefficient: Float64 = 0.0
    var _t0_temperature_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_temperature_coefficient += temperature_coefficient(0.5, 0.5, 0.5)
    var _t1_temperature_coefficient = perf_counter_ns()
    var _ns_temperature_coefficient = Float64(_t1_temperature_coefficient - _t0_temperature_coefficient) / Float64(N)
    print("MOJO_TIMING photovoltaics::temperature_coefficient", _ns_temperature_coefficient, _acc_temperature_coefficient)
    var _acc_energy_yield: Float64 = 0.0
    var _t0_energy_yield = perf_counter_ns()
    for _ in range(N):
        _acc_energy_yield += energy_yield(0.5, 0.5, 0.5)
    var _t1_energy_yield = perf_counter_ns()
    var _ns_energy_yield = Float64(_t1_energy_yield - _t0_energy_yield) / Float64(N)
    print("MOJO_TIMING photovoltaics::energy_yield", _ns_energy_yield, _acc_energy_yield)
    var _acc_irradiance_on_tilted_plane: Float64 = 0.0
    var _t0_irradiance_on_tilted_plane = perf_counter_ns()
    for _ in range(N):
        _acc_irradiance_on_tilted_plane += irradiance_on_tilted_plane(0.5, 0.5, 0.5)
    var _t1_irradiance_on_tilted_plane = perf_counter_ns()
    var _ns_irradiance_on_tilted_plane = Float64(_t1_irradiance_on_tilted_plane - _t0_irradiance_on_tilted_plane) / Float64(N)
    print("MOJO_TIMING photovoltaics::irradiance_on_tilted_plane", _ns_irradiance_on_tilted_plane, _acc_irradiance_on_tilted_plane)
    var _acc_lcoe_solar: Float64 = 0.0
    var _t0_lcoe_solar = perf_counter_ns()
    for _ in range(N):
        _acc_lcoe_solar += lcoe_solar(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_lcoe_solar = perf_counter_ns()
    var _ns_lcoe_solar = Float64(_t1_lcoe_solar - _t0_lcoe_solar) / Float64(N)
    print("MOJO_TIMING photovoltaics::lcoe_solar", _ns_lcoe_solar, _acc_lcoe_solar)
    var _acc_capacity_factor: Float64 = 0.0
    var _t0_capacity_factor = perf_counter_ns()
    for _ in range(N):
        _acc_capacity_factor += capacity_factor(0.5, 0.5, 0.5)
    var _t1_capacity_factor = perf_counter_ns()
    var _ns_capacity_factor = Float64(_t1_capacity_factor - _t0_capacity_factor) / Float64(N)
    print("MOJO_TIMING photovoltaics::capacity_factor", _ns_capacity_factor, _acc_capacity_factor)
    var _acc_peak_sun_hours: Float64 = 0.0
    var _t0_peak_sun_hours = perf_counter_ns()
    for _ in range(N):
        _acc_peak_sun_hours += peak_sun_hours(0.5)
    var _t1_peak_sun_hours = perf_counter_ns()
    var _ns_peak_sun_hours = Float64(_t1_peak_sun_hours - _t0_peak_sun_hours) / Float64(N)
    print("MOJO_TIMING photovoltaics::peak_sun_hours", _ns_peak_sun_hours, _acc_peak_sun_hours)
    var _acc_system_pr: Float64 = 0.0
    var _t0_system_pr = perf_counter_ns()
    for _ in range(N):
        _acc_system_pr += system_pr(0.5, 0.5)
    var _t1_system_pr = perf_counter_ns()
    var _ns_system_pr = Float64(_t1_system_pr - _t0_system_pr) / Float64(N)
    print("MOJO_TIMING photovoltaics::system_pr", _ns_system_pr, _acc_system_pr)
