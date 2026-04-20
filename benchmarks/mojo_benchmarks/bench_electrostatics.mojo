"""bench_electrostatics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from electrostatics import coulomb_force, electric_field_point, electric_potential, capacitance_parallel_plate, energy_stored_capacitor, electric_flux, surface_charge_density, dielectric_polarization, breakdown_voltage, image_charge_force
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

    var _acc_coulomb_force: Float64 = 0.0
    var _t0_coulomb_force = perf_counter_ns()
    for _ in range(N):
        _acc_coulomb_force += coulomb_force(0.5, 0.5, 0.5)
    var _t1_coulomb_force = perf_counter_ns()
    var _ns_coulomb_force = Float64(_t1_coulomb_force - _t0_coulomb_force) / Float64(N)
    print("MOJO_TIMING electrostatics::coulomb_force", _ns_coulomb_force, _acc_coulomb_force)
    var _acc_electric_field_point: Float64 = 0.0
    var _t0_electric_field_point = perf_counter_ns()
    for _ in range(N):
        _acc_electric_field_point += electric_field_point(0.5, 0.5)
    var _t1_electric_field_point = perf_counter_ns()
    var _ns_electric_field_point = Float64(_t1_electric_field_point - _t0_electric_field_point) / Float64(N)
    print("MOJO_TIMING electrostatics::electric_field_point", _ns_electric_field_point, _acc_electric_field_point)
    var _acc_electric_potential: Float64 = 0.0
    var _t0_electric_potential = perf_counter_ns()
    for _ in range(N):
        _acc_electric_potential += electric_potential(0.5, 0.5)
    var _t1_electric_potential = perf_counter_ns()
    var _ns_electric_potential = Float64(_t1_electric_potential - _t0_electric_potential) / Float64(N)
    print("MOJO_TIMING electrostatics::electric_potential", _ns_electric_potential, _acc_electric_potential)
    var _acc_capacitance_parallel_plate: Float64 = 0.0
    var _t0_capacitance_parallel_plate = perf_counter_ns()
    for _ in range(N):
        _acc_capacitance_parallel_plate += capacitance_parallel_plate(0.5, 0.5, 0.5)
    var _t1_capacitance_parallel_plate = perf_counter_ns()
    var _ns_capacitance_parallel_plate = Float64(_t1_capacitance_parallel_plate - _t0_capacitance_parallel_plate) / Float64(N)
    print("MOJO_TIMING electrostatics::capacitance_parallel_plate", _ns_capacitance_parallel_plate, _acc_capacitance_parallel_plate)
    var _acc_energy_stored_capacitor: Float64 = 0.0
    var _t0_energy_stored_capacitor = perf_counter_ns()
    for _ in range(N):
        _acc_energy_stored_capacitor += energy_stored_capacitor(0.5, 0.5)
    var _t1_energy_stored_capacitor = perf_counter_ns()
    var _ns_energy_stored_capacitor = Float64(_t1_energy_stored_capacitor - _t0_energy_stored_capacitor) / Float64(N)
    print("MOJO_TIMING electrostatics::energy_stored_capacitor", _ns_energy_stored_capacitor, _acc_energy_stored_capacitor)
    var _acc_electric_flux: Float64 = 0.0
    var _t0_electric_flux = perf_counter_ns()
    for _ in range(N):
        _acc_electric_flux += electric_flux(0.5, 0.5, 0.5)
    var _t1_electric_flux = perf_counter_ns()
    var _ns_electric_flux = Float64(_t1_electric_flux - _t0_electric_flux) / Float64(N)
    print("MOJO_TIMING electrostatics::electric_flux", _ns_electric_flux, _acc_electric_flux)
    var _acc_surface_charge_density: Float64 = 0.0
    var _t0_surface_charge_density = perf_counter_ns()
    for _ in range(N):
        _acc_surface_charge_density += surface_charge_density(0.5, 0.5)
    var _t1_surface_charge_density = perf_counter_ns()
    var _ns_surface_charge_density = Float64(_t1_surface_charge_density - _t0_surface_charge_density) / Float64(N)
    print("MOJO_TIMING electrostatics::surface_charge_density", _ns_surface_charge_density, _acc_surface_charge_density)
    var _acc_dielectric_polarization: Float64 = 0.0
    var _t0_dielectric_polarization = perf_counter_ns()
    for _ in range(N):
        _acc_dielectric_polarization += dielectric_polarization(0.5, 0.5)
    var _t1_dielectric_polarization = perf_counter_ns()
    var _ns_dielectric_polarization = Float64(_t1_dielectric_polarization - _t0_dielectric_polarization) / Float64(N)
    print("MOJO_TIMING electrostatics::dielectric_polarization", _ns_dielectric_polarization, _acc_dielectric_polarization)
    var _acc_breakdown_voltage: Float64 = 0.0
    var _t0_breakdown_voltage = perf_counter_ns()
    for _ in range(N):
        _acc_breakdown_voltage += breakdown_voltage(0.5, 0.5)
    var _t1_breakdown_voltage = perf_counter_ns()
    var _ns_breakdown_voltage = Float64(_t1_breakdown_voltage - _t0_breakdown_voltage) / Float64(N)
    print("MOJO_TIMING electrostatics::breakdown_voltage", _ns_breakdown_voltage, _acc_breakdown_voltage)
    var _acc_image_charge_force: Float64 = 0.0
    var _t0_image_charge_force = perf_counter_ns()
    for _ in range(N):
        _acc_image_charge_force += image_charge_force(0.5, 0.5)
    var _t1_image_charge_force = perf_counter_ns()
    var _ns_image_charge_force = Float64(_t1_image_charge_force - _t0_image_charge_force) / Float64(N)
    print("MOJO_TIMING electrostatics::image_charge_force", _ns_image_charge_force, _acc_image_charge_force)
