"""bench_magnetism.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from magnetism import biot_savart_infinite_wire, magnetic_force_wire, solenoid_field, toroid_field, magnetic_flux, inductance_solenoid, magnetic_energy_density, cyclotron_radius, larmor_frequency, hall_voltage
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

    var _acc_biot_savart_infinite_wire: Float64 = 0.0
    var _t0_biot_savart_infinite_wire = perf_counter_ns()
    for _ in range(N):
        _acc_biot_savart_infinite_wire += biot_savart_infinite_wire(0.5, 0.5)
    var _t1_biot_savart_infinite_wire = perf_counter_ns()
    var _ns_biot_savart_infinite_wire = Float64(_t1_biot_savart_infinite_wire - _t0_biot_savart_infinite_wire) / Float64(N)
    print("MOJO_TIMING magnetism::biot_savart_infinite_wire", _ns_biot_savart_infinite_wire, _acc_biot_savart_infinite_wire)
    var _acc_magnetic_force_wire: Float64 = 0.0
    var _t0_magnetic_force_wire = perf_counter_ns()
    for _ in range(N):
        _acc_magnetic_force_wire += magnetic_force_wire(0.5, 0.5, 0.5, 0.5)
    var _t1_magnetic_force_wire = perf_counter_ns()
    var _ns_magnetic_force_wire = Float64(_t1_magnetic_force_wire - _t0_magnetic_force_wire) / Float64(N)
    print("MOJO_TIMING magnetism::magnetic_force_wire", _ns_magnetic_force_wire, _acc_magnetic_force_wire)
    var _acc_solenoid_field: Float64 = 0.0
    var _t0_solenoid_field = perf_counter_ns()
    for _ in range(N):
        _acc_solenoid_field += solenoid_field(0.5, 0.5, 0.5)
    var _t1_solenoid_field = perf_counter_ns()
    var _ns_solenoid_field = Float64(_t1_solenoid_field - _t0_solenoid_field) / Float64(N)
    print("MOJO_TIMING magnetism::solenoid_field", _ns_solenoid_field, _acc_solenoid_field)
    var _acc_toroid_field: Float64 = 0.0
    var _t0_toroid_field = perf_counter_ns()
    for _ in range(N):
        _acc_toroid_field += toroid_field(0.5, 0.5, 0.5)
    var _t1_toroid_field = perf_counter_ns()
    var _ns_toroid_field = Float64(_t1_toroid_field - _t0_toroid_field) / Float64(N)
    print("MOJO_TIMING magnetism::toroid_field", _ns_toroid_field, _acc_toroid_field)
    var _acc_magnetic_flux: Float64 = 0.0
    var _t0_magnetic_flux = perf_counter_ns()
    for _ in range(N):
        _acc_magnetic_flux += magnetic_flux(0.5, 0.5, 0.5)
    var _t1_magnetic_flux = perf_counter_ns()
    var _ns_magnetic_flux = Float64(_t1_magnetic_flux - _t0_magnetic_flux) / Float64(N)
    print("MOJO_TIMING magnetism::magnetic_flux", _ns_magnetic_flux, _acc_magnetic_flux)
    var _acc_inductance_solenoid: Float64 = 0.0
    var _t0_inductance_solenoid = perf_counter_ns()
    for _ in range(N):
        _acc_inductance_solenoid += inductance_solenoid(0.5, 0.5, 0.5, 0.5)
    var _t1_inductance_solenoid = perf_counter_ns()
    var _ns_inductance_solenoid = Float64(_t1_inductance_solenoid - _t0_inductance_solenoid) / Float64(N)
    print("MOJO_TIMING magnetism::inductance_solenoid", _ns_inductance_solenoid, _acc_inductance_solenoid)
    var _acc_magnetic_energy_density: Float64 = 0.0
    var _t0_magnetic_energy_density = perf_counter_ns()
    for _ in range(N):
        _acc_magnetic_energy_density += magnetic_energy_density(0.5)
    var _t1_magnetic_energy_density = perf_counter_ns()
    var _ns_magnetic_energy_density = Float64(_t1_magnetic_energy_density - _t0_magnetic_energy_density) / Float64(N)
    print("MOJO_TIMING magnetism::magnetic_energy_density", _ns_magnetic_energy_density, _acc_magnetic_energy_density)
    var _acc_cyclotron_radius: Float64 = 0.0
    var _t0_cyclotron_radius = perf_counter_ns()
    for _ in range(N):
        _acc_cyclotron_radius += cyclotron_radius(0.5, 0.5, 0.5, 0.5)
    var _t1_cyclotron_radius = perf_counter_ns()
    var _ns_cyclotron_radius = Float64(_t1_cyclotron_radius - _t0_cyclotron_radius) / Float64(N)
    print("MOJO_TIMING magnetism::cyclotron_radius", _ns_cyclotron_radius, _acc_cyclotron_radius)
    var _acc_larmor_frequency: Float64 = 0.0
    var _t0_larmor_frequency = perf_counter_ns()
    for _ in range(N):
        _acc_larmor_frequency += larmor_frequency(0.5, 0.5, 0.5)
    var _t1_larmor_frequency = perf_counter_ns()
    var _ns_larmor_frequency = Float64(_t1_larmor_frequency - _t0_larmor_frequency) / Float64(N)
    print("MOJO_TIMING magnetism::larmor_frequency", _ns_larmor_frequency, _acc_larmor_frequency)
    var _acc_hall_voltage: Float64 = 0.0
    var _t0_hall_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_hall_voltage += hall_voltage(0.5, 0.5, 0.5, 0.5)
    var _t1_hall_voltage = perf_counter_ns()
    var _ns_hall_voltage = Float64(_t1_hall_voltage - _t0_hall_voltage) / Float64(N)
    print("MOJO_TIMING magnetism::hall_voltage", _ns_hall_voltage, _acc_hall_voltage)
