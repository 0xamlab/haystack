"""bench_thermodynamics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from thermodynamics import ideal_gas_pressure, ideal_gas_volume, carnot_efficiency, entropy_change, heat_capacity, adiabatic_process, work_isothermal, stefan_boltzmann, thermal_conductivity_flux, gibbs_free_energy, clausius_clapeyron
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

    var _acc_ideal_gas_pressure: Float64 = 0.0
    var _t0_ideal_gas_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_ideal_gas_pressure += ideal_gas_pressure(0.5, 0.5, 0.5)
    var _t1_ideal_gas_pressure = perf_counter_ns()
    var _ns_ideal_gas_pressure = Float64(_t1_ideal_gas_pressure - _t0_ideal_gas_pressure) / Float64(N)
    print("MOJO_TIMING thermodynamics::ideal_gas_pressure", _ns_ideal_gas_pressure, _acc_ideal_gas_pressure)
    var _acc_ideal_gas_volume: Float64 = 0.0
    var _t0_ideal_gas_volume = perf_counter_ns()
    for _ in range(N):
        _acc_ideal_gas_volume += ideal_gas_volume(0.5, 0.5, 0.5)
    var _t1_ideal_gas_volume = perf_counter_ns()
    var _ns_ideal_gas_volume = Float64(_t1_ideal_gas_volume - _t0_ideal_gas_volume) / Float64(N)
    print("MOJO_TIMING thermodynamics::ideal_gas_volume", _ns_ideal_gas_volume, _acc_ideal_gas_volume)
    var _acc_carnot_efficiency: Float64 = 0.0
    var _t0_carnot_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_carnot_efficiency += carnot_efficiency(0.5, 0.5)
    var _t1_carnot_efficiency = perf_counter_ns()
    var _ns_carnot_efficiency = Float64(_t1_carnot_efficiency - _t0_carnot_efficiency) / Float64(N)
    print("MOJO_TIMING thermodynamics::carnot_efficiency", _ns_carnot_efficiency, _acc_carnot_efficiency)
    var _acc_entropy_change: Float64 = 0.0
    var _t0_entropy_change = perf_counter_ns()
    for _ in range(N):
        _acc_entropy_change += entropy_change(0.5, 0.5)
    var _t1_entropy_change = perf_counter_ns()
    var _ns_entropy_change = Float64(_t1_entropy_change - _t0_entropy_change) / Float64(N)
    print("MOJO_TIMING thermodynamics::entropy_change", _ns_entropy_change, _acc_entropy_change)
    var _acc_heat_capacity: Float64 = 0.0
    var _t0_heat_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_heat_capacity += heat_capacity(0.5, 0.5, 0.5)
    var _t1_heat_capacity = perf_counter_ns()
    var _ns_heat_capacity = Float64(_t1_heat_capacity - _t0_heat_capacity) / Float64(N)
    print("MOJO_TIMING thermodynamics::heat_capacity", _ns_heat_capacity, _acc_heat_capacity)
    var _acc_adiabatic_process: Float64 = 0.0
    var _t0_adiabatic_process = perf_counter_ns()
    for _ in range(N):
        _acc_adiabatic_process += adiabatic_process(0.5, 0.5, 0.5, 0.5)
    var _t1_adiabatic_process = perf_counter_ns()
    var _ns_adiabatic_process = Float64(_t1_adiabatic_process - _t0_adiabatic_process) / Float64(N)
    print("MOJO_TIMING thermodynamics::adiabatic_process", _ns_adiabatic_process, _acc_adiabatic_process)
    var _acc_work_isothermal: Float64 = 0.0
    var _t0_work_isothermal = perf_counter_ns()
    for _ in range(N):
        _acc_work_isothermal += work_isothermal(0.5, 0.5, 0.5, 0.5)
    var _t1_work_isothermal = perf_counter_ns()
    var _ns_work_isothermal = Float64(_t1_work_isothermal - _t0_work_isothermal) / Float64(N)
    print("MOJO_TIMING thermodynamics::work_isothermal", _ns_work_isothermal, _acc_work_isothermal)
    var _acc_stefan_boltzmann: Float64 = 0.0
    var _t0_stefan_boltzmann = perf_counter_ns()
    for _ in range(N):
        _acc_stefan_boltzmann += stefan_boltzmann(0.5, 0.5, 0.5)
    var _t1_stefan_boltzmann = perf_counter_ns()
    var _ns_stefan_boltzmann = Float64(_t1_stefan_boltzmann - _t0_stefan_boltzmann) / Float64(N)
    print("MOJO_TIMING thermodynamics::stefan_boltzmann", _ns_stefan_boltzmann, _acc_stefan_boltzmann)
    var _acc_thermal_conductivity_flux: Float64 = 0.0
    var _t0_thermal_conductivity_flux = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_conductivity_flux += thermal_conductivity_flux(0.5, 0.5, 0.5, 0.5)
    var _t1_thermal_conductivity_flux = perf_counter_ns()
    var _ns_thermal_conductivity_flux = Float64(_t1_thermal_conductivity_flux - _t0_thermal_conductivity_flux) / Float64(N)
    print("MOJO_TIMING thermodynamics::thermal_conductivity_flux", _ns_thermal_conductivity_flux, _acc_thermal_conductivity_flux)
    var _acc_gibbs_free_energy: Float64 = 0.0
    var _t0_gibbs_free_energy = perf_counter_ns()
    for _ in range(N):
        _acc_gibbs_free_energy += gibbs_free_energy(0.5, 0.5, 0.5)
    var _t1_gibbs_free_energy = perf_counter_ns()
    var _ns_gibbs_free_energy = Float64(_t1_gibbs_free_energy - _t0_gibbs_free_energy) / Float64(N)
    print("MOJO_TIMING thermodynamics::gibbs_free_energy", _ns_gibbs_free_energy, _acc_gibbs_free_energy)
    var _acc_clausius_clapeyron: Float64 = 0.0
    var _t0_clausius_clapeyron = perf_counter_ns()
    for _ in range(N):
        _acc_clausius_clapeyron += clausius_clapeyron(0.5, 0.5, 0.5, 0.5)
    var _t1_clausius_clapeyron = perf_counter_ns()
    var _ns_clausius_clapeyron = Float64(_t1_clausius_clapeyron - _t0_clausius_clapeyron) / Float64(N)
    print("MOJO_TIMING thermodynamics::clausius_clapeyron", _ns_clausius_clapeyron, _acc_clausius_clapeyron)
