"""bench_magnetism.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from magnetism import biot_savart_infinite_wire, magnetic_force_wire, solenoid_field, toroid_field, magnetic_flux, inductance_solenoid, magnetic_energy_density, cyclotron_radius, larmor_frequency, hall_voltage
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

    var _acc_biot_savart_infinite_wire: Float64 = 0.0
    var _t0_biot_savart_infinite_wire = perf_counter_ns()
    for _ in range(N):
        _acc_biot_savart_infinite_wire += biot_savart_infinite_wire(0.5, 0.5)
    var _t1_biot_savart_infinite_wire = perf_counter_ns()
    var _ns_biot_savart_infinite_wire = Float64(_t1_biot_savart_infinite_wire - _t0_biot_savart_infinite_wire) / Float64(N)
    print("MOJO_TIMING magnetism::biot_savart_infinite_wire", _ns_biot_savart_infinite_wire, _acc_biot_savart_infinite_wire)
    var _result_biot_savart_infinite_wire = biot_savart_infinite_wire(0.5, 0.5)
    var _summary_biot_savart_infinite_wire = _summary_float64(_result_biot_savart_infinite_wire)
    print("MOJO_RESULT magnetism::biot_savart_infinite_wire", _summary_biot_savart_infinite_wire)
    var _acc_magnetic_force_wire: Float64 = 0.0
    var _t0_magnetic_force_wire = perf_counter_ns()
    for _ in range(N):
        _acc_magnetic_force_wire += magnetic_force_wire(0.5, 0.5, 0.5, 0.5)
    var _t1_magnetic_force_wire = perf_counter_ns()
    var _ns_magnetic_force_wire = Float64(_t1_magnetic_force_wire - _t0_magnetic_force_wire) / Float64(N)
    print("MOJO_TIMING magnetism::magnetic_force_wire", _ns_magnetic_force_wire, _acc_magnetic_force_wire)
    var _result_magnetic_force_wire = magnetic_force_wire(0.5, 0.5, 0.5, 0.5)
    var _summary_magnetic_force_wire = _summary_float64(_result_magnetic_force_wire)
    print("MOJO_RESULT magnetism::magnetic_force_wire", _summary_magnetic_force_wire)
    var _acc_solenoid_field: Float64 = 0.0
    var _t0_solenoid_field = perf_counter_ns()
    for _ in range(N):
        _acc_solenoid_field += solenoid_field(0.5, 0.5, 0.5)
    var _t1_solenoid_field = perf_counter_ns()
    var _ns_solenoid_field = Float64(_t1_solenoid_field - _t0_solenoid_field) / Float64(N)
    print("MOJO_TIMING magnetism::solenoid_field", _ns_solenoid_field, _acc_solenoid_field)
    var _result_solenoid_field = solenoid_field(0.5, 0.5, 0.5)
    var _summary_solenoid_field = _summary_float64(_result_solenoid_field)
    print("MOJO_RESULT magnetism::solenoid_field", _summary_solenoid_field)
    var _acc_toroid_field: Float64 = 0.0
    var _t0_toroid_field = perf_counter_ns()
    for _ in range(N):
        _acc_toroid_field += toroid_field(0.5, 0.5, 0.5)
    var _t1_toroid_field = perf_counter_ns()
    var _ns_toroid_field = Float64(_t1_toroid_field - _t0_toroid_field) / Float64(N)
    print("MOJO_TIMING magnetism::toroid_field", _ns_toroid_field, _acc_toroid_field)
    var _result_toroid_field = toroid_field(0.5, 0.5, 0.5)
    var _summary_toroid_field = _summary_float64(_result_toroid_field)
    print("MOJO_RESULT magnetism::toroid_field", _summary_toroid_field)
    var _acc_magnetic_flux: Float64 = 0.0
    var _t0_magnetic_flux = perf_counter_ns()
    for _ in range(N):
        _acc_magnetic_flux += magnetic_flux(0.5, 0.5, 0.5)
    var _t1_magnetic_flux = perf_counter_ns()
    var _ns_magnetic_flux = Float64(_t1_magnetic_flux - _t0_magnetic_flux) / Float64(N)
    print("MOJO_TIMING magnetism::magnetic_flux", _ns_magnetic_flux, _acc_magnetic_flux)
    var _result_magnetic_flux = magnetic_flux(0.5, 0.5, 0.5)
    var _summary_magnetic_flux = _summary_float64(_result_magnetic_flux)
    print("MOJO_RESULT magnetism::magnetic_flux", _summary_magnetic_flux)
    var _acc_inductance_solenoid: Float64 = 0.0
    var _t0_inductance_solenoid = perf_counter_ns()
    for _ in range(N):
        _acc_inductance_solenoid += inductance_solenoid(0.5, 0.5, 0.5, 0.5)
    var _t1_inductance_solenoid = perf_counter_ns()
    var _ns_inductance_solenoid = Float64(_t1_inductance_solenoid - _t0_inductance_solenoid) / Float64(N)
    print("MOJO_TIMING magnetism::inductance_solenoid", _ns_inductance_solenoid, _acc_inductance_solenoid)
    var _result_inductance_solenoid = inductance_solenoid(0.5, 0.5, 0.5, 0.5)
    var _summary_inductance_solenoid = _summary_float64(_result_inductance_solenoid)
    print("MOJO_RESULT magnetism::inductance_solenoid", _summary_inductance_solenoid)
    var _acc_magnetic_energy_density: Float64 = 0.0
    var _t0_magnetic_energy_density = perf_counter_ns()
    for _ in range(N):
        _acc_magnetic_energy_density += magnetic_energy_density(0.5)
    var _t1_magnetic_energy_density = perf_counter_ns()
    var _ns_magnetic_energy_density = Float64(_t1_magnetic_energy_density - _t0_magnetic_energy_density) / Float64(N)
    print("MOJO_TIMING magnetism::magnetic_energy_density", _ns_magnetic_energy_density, _acc_magnetic_energy_density)
    var _result_magnetic_energy_density = magnetic_energy_density(0.5)
    var _summary_magnetic_energy_density = _summary_float64(_result_magnetic_energy_density)
    print("MOJO_RESULT magnetism::magnetic_energy_density", _summary_magnetic_energy_density)
    var _acc_cyclotron_radius: Float64 = 0.0
    var _t0_cyclotron_radius = perf_counter_ns()
    for _ in range(N):
        _acc_cyclotron_radius += cyclotron_radius(0.5, 0.5, 0.5, 0.5)
    var _t1_cyclotron_radius = perf_counter_ns()
    var _ns_cyclotron_radius = Float64(_t1_cyclotron_radius - _t0_cyclotron_radius) / Float64(N)
    print("MOJO_TIMING magnetism::cyclotron_radius", _ns_cyclotron_radius, _acc_cyclotron_radius)
    var _result_cyclotron_radius = cyclotron_radius(0.5, 0.5, 0.5, 0.5)
    var _summary_cyclotron_radius = _summary_float64(_result_cyclotron_radius)
    print("MOJO_RESULT magnetism::cyclotron_radius", _summary_cyclotron_radius)
    var _acc_larmor_frequency: Float64 = 0.0
    var _t0_larmor_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_larmor_frequency += larmor_frequency(0.5, 0.5, 0.5)
    var _t1_larmor_frequency = perf_counter_ns()
    var _ns_larmor_frequency = Float64(_t1_larmor_frequency - _t0_larmor_frequency) / Float64(N)
    print("MOJO_TIMING magnetism::larmor_frequency", _ns_larmor_frequency, _acc_larmor_frequency)
    var _result_larmor_frequency = larmor_frequency(0.5, 0.5, 0.5)
    var _summary_larmor_frequency = _summary_float64(_result_larmor_frequency)
    print("MOJO_RESULT magnetism::larmor_frequency", _summary_larmor_frequency)
    var _acc_hall_voltage: Float64 = 0.0
    var _t0_hall_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_hall_voltage += hall_voltage(0.5, 0.5, 0.5, 0.5)
    var _t1_hall_voltage = perf_counter_ns()
    var _ns_hall_voltage = Float64(_t1_hall_voltage - _t0_hall_voltage) / Float64(N)
    print("MOJO_TIMING magnetism::hall_voltage", _ns_hall_voltage, _acc_hall_voltage)
    var _result_hall_voltage = hall_voltage(0.5, 0.5, 0.5, 0.5)
    var _summary_hall_voltage = _summary_float64(_result_hall_voltage)
    print("MOJO_RESULT magnetism::hall_voltage", _summary_hall_voltage)
