"""bench_cryogenics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from cryogenics import ideal_gas_density, joule_thomson_cooling, carnot_cop_cooling, liquefaction_yield, boiloff_rate, thermal_contraction, heat_leak_through_wall, superconductor_critical_temp_estimate, residual_resistivity_ratio, cryocooler_input_power, vacuum_insulation_heat_flux, helium_lambda_point
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

    var _acc_ideal_gas_density: Float64 = 0.0
    var _t0_ideal_gas_density = perf_counter_ns()
    for _ in range(N):
        _acc_ideal_gas_density += ideal_gas_density(0.5, 0.5, 0.5, 0.5)
    var _t1_ideal_gas_density = perf_counter_ns()
    var _ns_ideal_gas_density = Float64(_t1_ideal_gas_density - _t0_ideal_gas_density) / Float64(N)
    print("MOJO_TIMING cryogenics::ideal_gas_density", _ns_ideal_gas_density, _acc_ideal_gas_density)
    var _acc_joule_thomson_cooling: Float64 = 0.0
    var _t0_joule_thomson_cooling = perf_counter_ns()
    for _ in range(N):
        _acc_joule_thomson_cooling += joule_thomson_cooling(0.5, 0.5)
    var _t1_joule_thomson_cooling = perf_counter_ns()
    var _ns_joule_thomson_cooling = Float64(_t1_joule_thomson_cooling - _t0_joule_thomson_cooling) / Float64(N)
    print("MOJO_TIMING cryogenics::joule_thomson_cooling", _ns_joule_thomson_cooling, _acc_joule_thomson_cooling)
    var _acc_carnot_cop_cooling: Float64 = 0.0
    var _t0_carnot_cop_cooling = perf_counter_ns()
    for _ in range(N):
        _acc_carnot_cop_cooling += carnot_cop_cooling(200.0, 300.0)
    var _t1_carnot_cop_cooling = perf_counter_ns()
    var _ns_carnot_cop_cooling = Float64(_t1_carnot_cop_cooling - _t0_carnot_cop_cooling) / Float64(N)
    print("MOJO_TIMING cryogenics::carnot_cop_cooling", _ns_carnot_cop_cooling, _acc_carnot_cop_cooling)
    var _acc_liquefaction_yield: Float64 = 0.0
    var _t0_liquefaction_yield = perf_counter_ns()
    for _ in range(N):
        _acc_liquefaction_yield += liquefaction_yield(0.5, 0.5, 0.5, 0.5)
    var _t1_liquefaction_yield = perf_counter_ns()
    var _ns_liquefaction_yield = Float64(_t1_liquefaction_yield - _t0_liquefaction_yield) / Float64(N)
    print("MOJO_TIMING cryogenics::liquefaction_yield", _ns_liquefaction_yield, _acc_liquefaction_yield)
    var _acc_boiloff_rate: Float64 = 0.0
    var _t0_boiloff_rate = perf_counter_ns()
    for _ in range(N):
        _acc_boiloff_rate += boiloff_rate(0.5, 0.5, 0.5)
    var _t1_boiloff_rate = perf_counter_ns()
    var _ns_boiloff_rate = Float64(_t1_boiloff_rate - _t0_boiloff_rate) / Float64(N)
    print("MOJO_TIMING cryogenics::boiloff_rate", _ns_boiloff_rate, _acc_boiloff_rate)
    var _acc_thermal_contraction: Float64 = 0.0
    var _t0_thermal_contraction = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_contraction += thermal_contraction(0.5, 0.5, 0.5)
    var _t1_thermal_contraction = perf_counter_ns()
    var _ns_thermal_contraction = Float64(_t1_thermal_contraction - _t0_thermal_contraction) / Float64(N)
    print("MOJO_TIMING cryogenics::thermal_contraction", _ns_thermal_contraction, _acc_thermal_contraction)
    var _acc_heat_leak_through_wall: Float64 = 0.0
    var _t0_heat_leak_through_wall = perf_counter_ns()
    for _ in range(N):
        _acc_heat_leak_through_wall += heat_leak_through_wall(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_heat_leak_through_wall = perf_counter_ns()
    var _ns_heat_leak_through_wall = Float64(_t1_heat_leak_through_wall - _t0_heat_leak_through_wall) / Float64(N)
    print("MOJO_TIMING cryogenics::heat_leak_through_wall", _ns_heat_leak_through_wall, _acc_heat_leak_through_wall)
    var _acc_superconductor_critical_temp_estimate: Float64 = 0.0
    var _t0_superconductor_critical_temp_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_superconductor_critical_temp_estimate += superconductor_critical_temp_estimate(0.5, 0.5, 0.5)
    var _t1_superconductor_critical_temp_estimate = perf_counter_ns()
    var _ns_superconductor_critical_temp_estimate = Float64(_t1_superconductor_critical_temp_estimate - _t0_superconductor_critical_temp_estimate) / Float64(N)
    print("MOJO_TIMING cryogenics::superconductor_critical_temp_estimate", _ns_superconductor_critical_temp_estimate, _acc_superconductor_critical_temp_estimate)
    var _acc_residual_resistivity_ratio: Float64 = 0.0
    var _t0_residual_resistivity_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_residual_resistivity_ratio += residual_resistivity_ratio(0.5, 0.5)
    var _t1_residual_resistivity_ratio = perf_counter_ns()
    var _ns_residual_resistivity_ratio = Float64(_t1_residual_resistivity_ratio - _t0_residual_resistivity_ratio) / Float64(N)
    print("MOJO_TIMING cryogenics::residual_resistivity_ratio", _ns_residual_resistivity_ratio, _acc_residual_resistivity_ratio)
    var _acc_cryocooler_input_power: Float64 = 0.0
    var _t0_cryocooler_input_power = perf_counter_ns()
    for _ in range(N):
        _acc_cryocooler_input_power += cryocooler_input_power(0.5, 0.5)
    var _t1_cryocooler_input_power = perf_counter_ns()
    var _ns_cryocooler_input_power = Float64(_t1_cryocooler_input_power - _t0_cryocooler_input_power) / Float64(N)
    print("MOJO_TIMING cryogenics::cryocooler_input_power", _ns_cryocooler_input_power, _acc_cryocooler_input_power)
    var _acc_vacuum_insulation_heat_flux: Float64 = 0.0
    var _t0_vacuum_insulation_heat_flux = perf_counter_ns()
    for _ in range(N):
        _acc_vacuum_insulation_heat_flux += vacuum_insulation_heat_flux(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_vacuum_insulation_heat_flux = perf_counter_ns()
    var _ns_vacuum_insulation_heat_flux = Float64(_t1_vacuum_insulation_heat_flux - _t0_vacuum_insulation_heat_flux) / Float64(N)
    print("MOJO_TIMING cryogenics::vacuum_insulation_heat_flux", _ns_vacuum_insulation_heat_flux, _acc_vacuum_insulation_heat_flux)
    var _acc_helium_lambda_point: Float64 = 0.0
    var _t0_helium_lambda_point = perf_counter_ns()
    for _ in range(N):
        _acc_helium_lambda_point += helium_lambda_point()
    var _t1_helium_lambda_point = perf_counter_ns()
    var _ns_helium_lambda_point = Float64(_t1_helium_lambda_point - _t0_helium_lambda_point) / Float64(N)
    print("MOJO_TIMING cryogenics::helium_lambda_point", _ns_helium_lambda_point, _acc_helium_lambda_point)
