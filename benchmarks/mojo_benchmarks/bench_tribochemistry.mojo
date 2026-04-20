"""bench_tribochemistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from tribochemistry import friction_coefficient, archard_wear_rate, hertz_contact_radius, hertz_max_pressure, flash_temperature, film_thickness_ehd, lambda_ratio, surface_energy_work, tribocorrosion_rate, wear_volume
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

    var _acc_friction_coefficient: Float64 = 0.0
    var _t0_friction_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_friction_coefficient += friction_coefficient(0.5, 0.5)
    var _t1_friction_coefficient = perf_counter_ns()
    var _ns_friction_coefficient = Float64(_t1_friction_coefficient - _t0_friction_coefficient) / Float64(N)
    print("MOJO_TIMING tribochemistry::friction_coefficient", _ns_friction_coefficient, _acc_friction_coefficient)
    var _acc_archard_wear_rate: Float64 = 0.0
    var _t0_archard_wear_rate = perf_counter_ns()
    for _ in range(N):
        _acc_archard_wear_rate += archard_wear_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_archard_wear_rate = perf_counter_ns()
    var _ns_archard_wear_rate = Float64(_t1_archard_wear_rate - _t0_archard_wear_rate) / Float64(N)
    print("MOJO_TIMING tribochemistry::archard_wear_rate", _ns_archard_wear_rate, _acc_archard_wear_rate)
    var _acc_hertz_contact_radius: Float64 = 0.0
    var _t0_hertz_contact_radius = perf_counter_ns()
    for _ in range(N):
        _acc_hertz_contact_radius += hertz_contact_radius(0.5, 0.5, 0.5)
    var _t1_hertz_contact_radius = perf_counter_ns()
    var _ns_hertz_contact_radius = Float64(_t1_hertz_contact_radius - _t0_hertz_contact_radius) / Float64(N)
    print("MOJO_TIMING tribochemistry::hertz_contact_radius", _ns_hertz_contact_radius, _acc_hertz_contact_radius)
    var _acc_hertz_max_pressure: Float64 = 0.0
    var _t0_hertz_max_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_hertz_max_pressure += hertz_max_pressure(0.5, 0.5)
    var _t1_hertz_max_pressure = perf_counter_ns()
    var _ns_hertz_max_pressure = Float64(_t1_hertz_max_pressure - _t0_hertz_max_pressure) / Float64(N)
    print("MOJO_TIMING tribochemistry::hertz_max_pressure", _ns_hertz_max_pressure, _acc_hertz_max_pressure)
    var _acc_flash_temperature: Float64 = 0.0
    var _t0_flash_temperature = perf_counter_ns()
    for _ in range(N):
        _acc_flash_temperature += flash_temperature(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_flash_temperature = perf_counter_ns()
    var _ns_flash_temperature = Float64(_t1_flash_temperature - _t0_flash_temperature) / Float64(N)
    print("MOJO_TIMING tribochemistry::flash_temperature", _ns_flash_temperature, _acc_flash_temperature)
    var _acc_film_thickness_ehd: Float64 = 0.0
    var _t0_film_thickness_ehd = perf_counter_ns()
    for _ in range(N):
        _acc_film_thickness_ehd += film_thickness_ehd(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_film_thickness_ehd = perf_counter_ns()
    var _ns_film_thickness_ehd = Float64(_t1_film_thickness_ehd - _t0_film_thickness_ehd) / Float64(N)
    print("MOJO_TIMING tribochemistry::film_thickness_ehd", _ns_film_thickness_ehd, _acc_film_thickness_ehd)
    var _acc_lambda_ratio: Float64 = 0.0
    var _t0_lambda_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_lambda_ratio += lambda_ratio(0.5, 0.5)
    var _t1_lambda_ratio = perf_counter_ns()
    var _ns_lambda_ratio = Float64(_t1_lambda_ratio - _t0_lambda_ratio) / Float64(N)
    print("MOJO_TIMING tribochemistry::lambda_ratio", _ns_lambda_ratio, _acc_lambda_ratio)
    var _acc_surface_energy_work: Float64 = 0.0
    var _t0_surface_energy_work = perf_counter_ns()
    for _ in range(N):
        _acc_surface_energy_work += surface_energy_work(0.5)
    var _t1_surface_energy_work = perf_counter_ns()
    var _ns_surface_energy_work = Float64(_t1_surface_energy_work - _t0_surface_energy_work) / Float64(N)
    print("MOJO_TIMING tribochemistry::surface_energy_work", _ns_surface_energy_work, _acc_surface_energy_work)
    var _acc_tribocorrosion_rate: Float64 = 0.0
    var _t0_tribocorrosion_rate = perf_counter_ns()
    for _ in range(N):
        _acc_tribocorrosion_rate += tribocorrosion_rate(0.5, 0.5, 0.5)
    var _t1_tribocorrosion_rate = perf_counter_ns()
    var _ns_tribocorrosion_rate = Float64(_t1_tribocorrosion_rate - _t0_tribocorrosion_rate) / Float64(N)
    print("MOJO_TIMING tribochemistry::tribocorrosion_rate", _ns_tribocorrosion_rate, _acc_tribocorrosion_rate)
    var _acc_wear_volume: Float64 = 0.0
    var _t0_wear_volume = perf_counter_ns()
    for _ in range(N):
        _acc_wear_volume += wear_volume(0.5, 0.5, 0.5, 0.5)
    var _t1_wear_volume = perf_counter_ns()
    var _ns_wear_volume = Float64(_t1_wear_volume - _t0_wear_volume) / Float64(N)
    print("MOJO_TIMING tribochemistry::wear_volume", _ns_wear_volume, _acc_wear_volume)
