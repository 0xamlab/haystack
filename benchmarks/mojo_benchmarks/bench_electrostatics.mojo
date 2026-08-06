"""bench_electrostatics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from electrostatics import coulomb_force, electric_field_point, electric_potential, capacitance_parallel_plate, energy_stored_capacitor, electric_flux, surface_charge_density, dielectric_polarization, breakdown_voltage, image_charge_force
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

    var _acc_coulomb_force: Float64 = 0.0
    var _t0_coulomb_force = perf_counter_ns()
    for _ in range(N):
        _acc_coulomb_force += coulomb_force(0.5, 0.5, 0.5)
    var _t1_coulomb_force = perf_counter_ns()
    var _ns_coulomb_force = Float64(_t1_coulomb_force - _t0_coulomb_force) / Float64(N)
    print("MOJO_TIMING electrostatics::coulomb_force", _ns_coulomb_force, _acc_coulomb_force)
    var _result_coulomb_force = coulomb_force(0.5, 0.5, 0.5)
    var _summary_coulomb_force = _summary_float64(_result_coulomb_force)
    print("MOJO_RESULT electrostatics::coulomb_force", _summary_coulomb_force)
    var _acc_electric_field_point: Float64 = 0.0
    var _t0_electric_field_point = perf_counter_ns()
    for _ in range(N):
        _acc_electric_field_point += electric_field_point(0.5, 0.5)
    var _t1_electric_field_point = perf_counter_ns()
    var _ns_electric_field_point = Float64(_t1_electric_field_point - _t0_electric_field_point) / Float64(N)
    print("MOJO_TIMING electrostatics::electric_field_point", _ns_electric_field_point, _acc_electric_field_point)
    var _result_electric_field_point = electric_field_point(0.5, 0.5)
    var _summary_electric_field_point = _summary_float64(_result_electric_field_point)
    print("MOJO_RESULT electrostatics::electric_field_point", _summary_electric_field_point)
    var _acc_electric_potential: Float64 = 0.0
    var _t0_electric_potential = perf_counter_ns()
    for _ in range(N):
        _acc_electric_potential += electric_potential(0.5, 0.5)
    var _t1_electric_potential = perf_counter_ns()
    var _ns_electric_potential = Float64(_t1_electric_potential - _t0_electric_potential) / Float64(N)
    print("MOJO_TIMING electrostatics::electric_potential", _ns_electric_potential, _acc_electric_potential)
    var _result_electric_potential = electric_potential(0.5, 0.5)
    var _summary_electric_potential = _summary_float64(_result_electric_potential)
    print("MOJO_RESULT electrostatics::electric_potential", _summary_electric_potential)
    var _acc_capacitance_parallel_plate: Float64 = 0.0
    var _t0_capacitance_parallel_plate = perf_counter_ns()
    for _ in range(N):
        _acc_capacitance_parallel_plate += capacitance_parallel_plate(0.5, 0.5, 0.5)
    var _t1_capacitance_parallel_plate = perf_counter_ns()
    var _ns_capacitance_parallel_plate = Float64(_t1_capacitance_parallel_plate - _t0_capacitance_parallel_plate) / Float64(N)
    print("MOJO_TIMING electrostatics::capacitance_parallel_plate", _ns_capacitance_parallel_plate, _acc_capacitance_parallel_plate)
    var _result_capacitance_parallel_plate = capacitance_parallel_plate(0.5, 0.5, 0.5)
    var _summary_capacitance_parallel_plate = _summary_float64(_result_capacitance_parallel_plate)
    print("MOJO_RESULT electrostatics::capacitance_parallel_plate", _summary_capacitance_parallel_plate)
    var _acc_energy_stored_capacitor: Float64 = 0.0
    var _t0_energy_stored_capacitor = perf_counter_ns()
    for _ in range(N):
        _acc_energy_stored_capacitor += energy_stored_capacitor(0.5, 0.5)
    var _t1_energy_stored_capacitor = perf_counter_ns()
    var _ns_energy_stored_capacitor = Float64(_t1_energy_stored_capacitor - _t0_energy_stored_capacitor) / Float64(N)
    print("MOJO_TIMING electrostatics::energy_stored_capacitor", _ns_energy_stored_capacitor, _acc_energy_stored_capacitor)
    var _result_energy_stored_capacitor = energy_stored_capacitor(0.5, 0.5)
    var _summary_energy_stored_capacitor = _summary_float64(_result_energy_stored_capacitor)
    print("MOJO_RESULT electrostatics::energy_stored_capacitor", _summary_energy_stored_capacitor)
    var _acc_electric_flux: Float64 = 0.0
    var _t0_electric_flux = perf_counter_ns()
    for _ in range(N):
        _acc_electric_flux += electric_flux(0.5, 0.5, 0.5)
    var _t1_electric_flux = perf_counter_ns()
    var _ns_electric_flux = Float64(_t1_electric_flux - _t0_electric_flux) / Float64(N)
    print("MOJO_TIMING electrostatics::electric_flux", _ns_electric_flux, _acc_electric_flux)
    var _result_electric_flux = electric_flux(0.5, 0.5, 0.5)
    var _summary_electric_flux = _summary_float64(_result_electric_flux)
    print("MOJO_RESULT electrostatics::electric_flux", _summary_electric_flux)
    var _acc_surface_charge_density: Float64 = 0.0
    var _t0_surface_charge_density = perf_counter_ns()
    for _ in range(N):
        _acc_surface_charge_density += surface_charge_density(0.5, 0.5)
    var _t1_surface_charge_density = perf_counter_ns()
    var _ns_surface_charge_density = Float64(_t1_surface_charge_density - _t0_surface_charge_density) / Float64(N)
    print("MOJO_TIMING electrostatics::surface_charge_density", _ns_surface_charge_density, _acc_surface_charge_density)
    var _result_surface_charge_density = surface_charge_density(0.5, 0.5)
    var _summary_surface_charge_density = _summary_float64(_result_surface_charge_density)
    print("MOJO_RESULT electrostatics::surface_charge_density", _summary_surface_charge_density)
    var _acc_dielectric_polarization: Float64 = 0.0
    var _t0_dielectric_polarization = perf_counter_ns()
    for _ in range(N):
        _acc_dielectric_polarization += dielectric_polarization(0.5, 0.5)
    var _t1_dielectric_polarization = perf_counter_ns()
    var _ns_dielectric_polarization = Float64(_t1_dielectric_polarization - _t0_dielectric_polarization) / Float64(N)
    print("MOJO_TIMING electrostatics::dielectric_polarization", _ns_dielectric_polarization, _acc_dielectric_polarization)
    var _result_dielectric_polarization = dielectric_polarization(0.5, 0.5)
    var _summary_dielectric_polarization = _summary_float64(_result_dielectric_polarization)
    print("MOJO_RESULT electrostatics::dielectric_polarization", _summary_dielectric_polarization)
    var _acc_breakdown_voltage: Float64 = 0.0
    var _t0_breakdown_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_breakdown_voltage += breakdown_voltage(0.5, 0.5)
    var _t1_breakdown_voltage = perf_counter_ns()
    var _ns_breakdown_voltage = Float64(_t1_breakdown_voltage - _t0_breakdown_voltage) / Float64(N)
    print("MOJO_TIMING electrostatics::breakdown_voltage", _ns_breakdown_voltage, _acc_breakdown_voltage)
    var _result_breakdown_voltage = breakdown_voltage(0.5, 0.5)
    var _summary_breakdown_voltage = _summary_float64(_result_breakdown_voltage)
    print("MOJO_RESULT electrostatics::breakdown_voltage", _summary_breakdown_voltage)
    var _acc_image_charge_force: Float64 = 0.0
    var _t0_image_charge_force = perf_counter_ns()
    for _ in range(N):
        _acc_image_charge_force += image_charge_force(0.5, 0.5)
    var _t1_image_charge_force = perf_counter_ns()
    var _ns_image_charge_force = Float64(_t1_image_charge_force - _t0_image_charge_force) / Float64(N)
    print("MOJO_TIMING electrostatics::image_charge_force", _ns_image_charge_force, _acc_image_charge_force)
    var _result_image_charge_force = image_charge_force(0.5, 0.5)
    var _summary_image_charge_force = _summary_float64(_result_image_charge_force)
    print("MOJO_RESULT electrostatics::image_charge_force", _summary_image_charge_force)
