"""bench_tribology.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from tribology import coulomb_friction_force, kinetic_friction, static_friction_max, coefficient_of_friction, hertz_contact_pressure, archard_wear_volume, bearing_pressure, sommerfeld_number, stribeck_parameter, flash_temperature_rise, lubrication_film_thickness, friction_power_loss
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

    var _acc_coulomb_friction_force: Float64 = 0.0
    var _t0_coulomb_friction_force = perf_counter_ns()
    for _ in range(N):
        _acc_coulomb_friction_force += coulomb_friction_force(0.5, 0.5)
    var _t1_coulomb_friction_force = perf_counter_ns()
    var _ns_coulomb_friction_force = Float64(_t1_coulomb_friction_force - _t0_coulomb_friction_force) / Float64(N)
    print("MOJO_TIMING tribology::coulomb_friction_force", _ns_coulomb_friction_force, _acc_coulomb_friction_force)
    var _acc_kinetic_friction: Float64 = 0.0
    var _t0_kinetic_friction = perf_counter_ns()
    for _ in range(N):
        _acc_kinetic_friction += kinetic_friction(0.5, 0.5)
    var _t1_kinetic_friction = perf_counter_ns()
    var _ns_kinetic_friction = Float64(_t1_kinetic_friction - _t0_kinetic_friction) / Float64(N)
    print("MOJO_TIMING tribology::kinetic_friction", _ns_kinetic_friction, _acc_kinetic_friction)
    var _acc_static_friction_max: Float64 = 0.0
    var _t0_static_friction_max = perf_counter_ns()
    for _ in range(N):
        _acc_static_friction_max += static_friction_max(0.5, 0.5)
    var _t1_static_friction_max = perf_counter_ns()
    var _ns_static_friction_max = Float64(_t1_static_friction_max - _t0_static_friction_max) / Float64(N)
    print("MOJO_TIMING tribology::static_friction_max", _ns_static_friction_max, _acc_static_friction_max)
    var _acc_coefficient_of_friction: Float64 = 0.0
    var _t0_coefficient_of_friction = perf_counter_ns()
    for _ in range(N):
        _acc_coefficient_of_friction += coefficient_of_friction(0.5, 0.5)
    var _t1_coefficient_of_friction = perf_counter_ns()
    var _ns_coefficient_of_friction = Float64(_t1_coefficient_of_friction - _t0_coefficient_of_friction) / Float64(N)
    print("MOJO_TIMING tribology::coefficient_of_friction", _ns_coefficient_of_friction, _acc_coefficient_of_friction)
    var _acc_hertz_contact_pressure: Float64 = 0.0
    var _t0_hertz_contact_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_hertz_contact_pressure += hertz_contact_pressure(0.5, 0.5)
    var _t1_hertz_contact_pressure = perf_counter_ns()
    var _ns_hertz_contact_pressure = Float64(_t1_hertz_contact_pressure - _t0_hertz_contact_pressure) / Float64(N)
    print("MOJO_TIMING tribology::hertz_contact_pressure", _ns_hertz_contact_pressure, _acc_hertz_contact_pressure)
    var _acc_archard_wear_volume: Float64 = 0.0
    var _t0_archard_wear_volume = perf_counter_ns()
    for _ in range(N):
        _acc_archard_wear_volume += archard_wear_volume(0.5, 0.5, 0.5, 0.5)
    var _t1_archard_wear_volume = perf_counter_ns()
    var _ns_archard_wear_volume = Float64(_t1_archard_wear_volume - _t0_archard_wear_volume) / Float64(N)
    print("MOJO_TIMING tribology::archard_wear_volume", _ns_archard_wear_volume, _acc_archard_wear_volume)
    var _acc_bearing_pressure: Float64 = 0.0
    var _t0_bearing_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_bearing_pressure += bearing_pressure(0.5, 0.5)
    var _t1_bearing_pressure = perf_counter_ns()
    var _ns_bearing_pressure = Float64(_t1_bearing_pressure - _t0_bearing_pressure) / Float64(N)
    print("MOJO_TIMING tribology::bearing_pressure", _ns_bearing_pressure, _acc_bearing_pressure)
    var _acc_sommerfeld_number: Float64 = 0.0
    var _t0_sommerfeld_number = perf_counter_ns()
    for _ in range(N):
        _acc_sommerfeld_number += sommerfeld_number(0.5, 0.5, 0.5, 0.5)
    var _t1_sommerfeld_number = perf_counter_ns()
    var _ns_sommerfeld_number = Float64(_t1_sommerfeld_number - _t0_sommerfeld_number) / Float64(N)
    print("MOJO_TIMING tribology::sommerfeld_number", _ns_sommerfeld_number, _acc_sommerfeld_number)
    var _acc_stribeck_parameter: Float64 = 0.0
    var _t0_stribeck_parameter = perf_counter_ns()
    for _ in range(N):
        _acc_stribeck_parameter += stribeck_parameter(0.5, 0.5, 0.5)
    var _t1_stribeck_parameter = perf_counter_ns()
    var _ns_stribeck_parameter = Float64(_t1_stribeck_parameter - _t0_stribeck_parameter) / Float64(N)
    print("MOJO_TIMING tribology::stribeck_parameter", _ns_stribeck_parameter, _acc_stribeck_parameter)
    var _acc_flash_temperature_rise: Float64 = 0.0
    var _t0_flash_temperature_rise = perf_counter_ns()
    for _ in range(N):
        _acc_flash_temperature_rise += flash_temperature_rise(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_flash_temperature_rise = perf_counter_ns()
    var _ns_flash_temperature_rise = Float64(_t1_flash_temperature_rise - _t0_flash_temperature_rise) / Float64(N)
    print("MOJO_TIMING tribology::flash_temperature_rise", _ns_flash_temperature_rise, _acc_flash_temperature_rise)
    var _acc_lubrication_film_thickness: Float64 = 0.0
    var _t0_lubrication_film_thickness = perf_counter_ns()
    for _ in range(N):
        _acc_lubrication_film_thickness += lubrication_film_thickness(0.5, 0.5, 0.5)
    var _t1_lubrication_film_thickness = perf_counter_ns()
    var _ns_lubrication_film_thickness = Float64(_t1_lubrication_film_thickness - _t0_lubrication_film_thickness) / Float64(N)
    print("MOJO_TIMING tribology::lubrication_film_thickness", _ns_lubrication_film_thickness, _acc_lubrication_film_thickness)
    var _acc_friction_power_loss: Float64 = 0.0
    var _t0_friction_power_loss = perf_counter_ns()
    for _ in range(N):
        _acc_friction_power_loss += friction_power_loss(0.5, 0.5)
    var _t1_friction_power_loss = perf_counter_ns()
    var _ns_friction_power_loss = Float64(_t1_friction_power_loss - _t0_friction_power_loss) / Float64(N)
    print("MOJO_TIMING tribology::friction_power_loss", _ns_friction_power_loss, _acc_friction_power_loss)
