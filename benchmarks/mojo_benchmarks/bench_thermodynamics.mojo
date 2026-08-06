"""bench_thermodynamics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from thermodynamics import ideal_gas_pressure, ideal_gas_volume, carnot_efficiency, entropy_change, heat_capacity, adiabatic_process, work_isothermal, stefan_boltzmann, thermal_conductivity_flux, gibbs_free_energy, clausius_clapeyron
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

    var _acc_ideal_gas_pressure: Float64 = 0.0
    var _t0_ideal_gas_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_ideal_gas_pressure += ideal_gas_pressure(0.5, 0.5, 0.5)
    var _t1_ideal_gas_pressure = perf_counter_ns()
    var _ns_ideal_gas_pressure = Float64(_t1_ideal_gas_pressure - _t0_ideal_gas_pressure) / Float64(N)
    print("MOJO_TIMING thermodynamics::ideal_gas_pressure", _ns_ideal_gas_pressure, _acc_ideal_gas_pressure)
    var _result_ideal_gas_pressure = ideal_gas_pressure(0.5, 0.5, 0.5)
    var _summary_ideal_gas_pressure = _summary_float64(_result_ideal_gas_pressure)
    print("MOJO_RESULT thermodynamics::ideal_gas_pressure", _summary_ideal_gas_pressure)
    var _acc_ideal_gas_volume: Float64 = 0.0
    var _t0_ideal_gas_volume = perf_counter_ns()
    for _ in range(N):
        _acc_ideal_gas_volume += ideal_gas_volume(0.5, 0.5, 0.5)
    var _t1_ideal_gas_volume = perf_counter_ns()
    var _ns_ideal_gas_volume = Float64(_t1_ideal_gas_volume - _t0_ideal_gas_volume) / Float64(N)
    print("MOJO_TIMING thermodynamics::ideal_gas_volume", _ns_ideal_gas_volume, _acc_ideal_gas_volume)
    var _result_ideal_gas_volume = ideal_gas_volume(0.5, 0.5, 0.5)
    var _summary_ideal_gas_volume = _summary_float64(_result_ideal_gas_volume)
    print("MOJO_RESULT thermodynamics::ideal_gas_volume", _summary_ideal_gas_volume)
    var _acc_carnot_efficiency: Float64 = 0.0
    var _t0_carnot_efficiency = perf_counter_ns()
    for _ in range(N):
        _acc_carnot_efficiency += carnot_efficiency(0.5, 0.5)
    var _t1_carnot_efficiency = perf_counter_ns()
    var _ns_carnot_efficiency = Float64(_t1_carnot_efficiency - _t0_carnot_efficiency) / Float64(N)
    print("MOJO_TIMING thermodynamics::carnot_efficiency", _ns_carnot_efficiency, _acc_carnot_efficiency)
    var _result_carnot_efficiency = carnot_efficiency(0.5, 0.5)
    var _summary_carnot_efficiency = _summary_float64(_result_carnot_efficiency)
    print("MOJO_RESULT thermodynamics::carnot_efficiency", _summary_carnot_efficiency)
    var _acc_entropy_change: Float64 = 0.0
    var _t0_entropy_change = perf_counter_ns()
    for _ in range(N):
        _acc_entropy_change += entropy_change(0.5, 0.5)
    var _t1_entropy_change = perf_counter_ns()
    var _ns_entropy_change = Float64(_t1_entropy_change - _t0_entropy_change) / Float64(N)
    print("MOJO_TIMING thermodynamics::entropy_change", _ns_entropy_change, _acc_entropy_change)
    var _result_entropy_change = entropy_change(0.5, 0.5)
    var _summary_entropy_change = _summary_float64(_result_entropy_change)
    print("MOJO_RESULT thermodynamics::entropy_change", _summary_entropy_change)
    var _acc_heat_capacity: Float64 = 0.0
    var _t0_heat_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_heat_capacity += heat_capacity(0.5, 0.5, 0.5)
    var _t1_heat_capacity = perf_counter_ns()
    var _ns_heat_capacity = Float64(_t1_heat_capacity - _t0_heat_capacity) / Float64(N)
    print("MOJO_TIMING thermodynamics::heat_capacity", _ns_heat_capacity, _acc_heat_capacity)
    var _result_heat_capacity = heat_capacity(0.5, 0.5, 0.5)
    var _summary_heat_capacity = _summary_float64(_result_heat_capacity)
    print("MOJO_RESULT thermodynamics::heat_capacity", _summary_heat_capacity)
    var _acc_adiabatic_process: Float64 = 0.0
    var _t0_adiabatic_process = perf_counter_ns()
    for _ in range(N):
        _acc_adiabatic_process += adiabatic_process(0.5, 0.5, 0.5, 0.5)
    var _t1_adiabatic_process = perf_counter_ns()
    var _ns_adiabatic_process = Float64(_t1_adiabatic_process - _t0_adiabatic_process) / Float64(N)
    print("MOJO_TIMING thermodynamics::adiabatic_process", _ns_adiabatic_process, _acc_adiabatic_process)
    var _result_adiabatic_process = adiabatic_process(0.5, 0.5, 0.5, 0.5)
    var _summary_adiabatic_process = _summary_float64(_result_adiabatic_process)
    print("MOJO_RESULT thermodynamics::adiabatic_process", _summary_adiabatic_process)
    var _acc_work_isothermal: Float64 = 0.0
    var _t0_work_isothermal = perf_counter_ns()
    for _ in range(N):
        _acc_work_isothermal += work_isothermal(0.5, 0.5, 0.5, 0.5)
    var _t1_work_isothermal = perf_counter_ns()
    var _ns_work_isothermal = Float64(_t1_work_isothermal - _t0_work_isothermal) / Float64(N)
    print("MOJO_TIMING thermodynamics::work_isothermal", _ns_work_isothermal, _acc_work_isothermal)
    var _result_work_isothermal = work_isothermal(0.5, 0.5, 0.5, 0.5)
    var _summary_work_isothermal = _summary_float64(_result_work_isothermal)
    print("MOJO_RESULT thermodynamics::work_isothermal", _summary_work_isothermal)
    var _acc_stefan_boltzmann: Float64 = 0.0
    var _t0_stefan_boltzmann = perf_counter_ns()
    for _ in range(N):
        _acc_stefan_boltzmann += stefan_boltzmann(0.5, 0.5, 0.5)
    var _t1_stefan_boltzmann = perf_counter_ns()
    var _ns_stefan_boltzmann = Float64(_t1_stefan_boltzmann - _t0_stefan_boltzmann) / Float64(N)
    print("MOJO_TIMING thermodynamics::stefan_boltzmann", _ns_stefan_boltzmann, _acc_stefan_boltzmann)
    var _result_stefan_boltzmann = stefan_boltzmann(0.5, 0.5, 0.5)
    var _summary_stefan_boltzmann = _summary_float64(_result_stefan_boltzmann)
    print("MOJO_RESULT thermodynamics::stefan_boltzmann", _summary_stefan_boltzmann)
    var _acc_thermal_conductivity_flux: Float64 = 0.0
    var _t0_thermal_conductivity_flux = perf_counter_ns()
    for _ in range(N):
        _acc_thermal_conductivity_flux += thermal_conductivity_flux(0.5, 0.5, 0.5, 0.5)
    var _t1_thermal_conductivity_flux = perf_counter_ns()
    var _ns_thermal_conductivity_flux = Float64(_t1_thermal_conductivity_flux - _t0_thermal_conductivity_flux) / Float64(N)
    print("MOJO_TIMING thermodynamics::thermal_conductivity_flux", _ns_thermal_conductivity_flux, _acc_thermal_conductivity_flux)
    var _result_thermal_conductivity_flux = thermal_conductivity_flux(0.5, 0.5, 0.5, 0.5)
    var _summary_thermal_conductivity_flux = _summary_float64(_result_thermal_conductivity_flux)
    print("MOJO_RESULT thermodynamics::thermal_conductivity_flux", _summary_thermal_conductivity_flux)
    var _acc_gibbs_free_energy: Float64 = 0.0
    var _t0_gibbs_free_energy = perf_counter_ns()
    for _ in range(N):
        _acc_gibbs_free_energy += gibbs_free_energy(0.5, 0.5, 0.5)
    var _t1_gibbs_free_energy = perf_counter_ns()
    var _ns_gibbs_free_energy = Float64(_t1_gibbs_free_energy - _t0_gibbs_free_energy) / Float64(N)
    print("MOJO_TIMING thermodynamics::gibbs_free_energy", _ns_gibbs_free_energy, _acc_gibbs_free_energy)
    var _result_gibbs_free_energy = gibbs_free_energy(0.5, 0.5, 0.5)
    var _summary_gibbs_free_energy = _summary_float64(_result_gibbs_free_energy)
    print("MOJO_RESULT thermodynamics::gibbs_free_energy", _summary_gibbs_free_energy)
    var _acc_clausius_clapeyron: Float64 = 0.0
    var _t0_clausius_clapeyron = perf_counter_ns()
    for _ in range(N):
        _acc_clausius_clapeyron += clausius_clapeyron(0.5, 0.5, 0.5, 0.5)
    var _t1_clausius_clapeyron = perf_counter_ns()
    var _ns_clausius_clapeyron = Float64(_t1_clausius_clapeyron - _t0_clausius_clapeyron) / Float64(N)
    print("MOJO_TIMING thermodynamics::clausius_clapeyron", _ns_clausius_clapeyron, _acc_clausius_clapeyron)
    var _result_clausius_clapeyron = clausius_clapeyron(0.5, 0.5, 0.5, 0.5)
    var _summary_clausius_clapeyron = _summary_float64(_result_clausius_clapeyron)
    print("MOJO_RESULT thermodynamics::clausius_clapeyron", _summary_clausius_clapeyron)
