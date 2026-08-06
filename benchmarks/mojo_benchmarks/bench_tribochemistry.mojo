"""bench_tribochemistry.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from tribochemistry import friction_coefficient, archard_wear_rate, hertz_contact_radius, hertz_max_pressure, flash_temperature, film_thickness_ehd, lambda_ratio, surface_energy_work, tribocorrosion_rate, wear_volume
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

    var _acc_friction_coefficient: Float64 = 0.0
    var _t0_friction_coefficient = perf_counter_ns()
    for _ in range(N):
        _acc_friction_coefficient += friction_coefficient(0.5, 0.5)
    var _t1_friction_coefficient = perf_counter_ns()
    var _ns_friction_coefficient = Float64(_t1_friction_coefficient - _t0_friction_coefficient) / Float64(N)
    print("MOJO_TIMING tribochemistry::friction_coefficient", _ns_friction_coefficient, _acc_friction_coefficient)
    var _result_friction_coefficient = friction_coefficient(0.5, 0.5)
    var _summary_friction_coefficient = _summary_float64(_result_friction_coefficient)
    print("MOJO_RESULT tribochemistry::friction_coefficient", _summary_friction_coefficient)
    var _acc_archard_wear_rate: Float64 = 0.0
    var _t0_archard_wear_rate = perf_counter_ns()
    for _ in range(N):
        _acc_archard_wear_rate += archard_wear_rate(0.5, 0.5, 0.5, 0.5)
    var _t1_archard_wear_rate = perf_counter_ns()
    var _ns_archard_wear_rate = Float64(_t1_archard_wear_rate - _t0_archard_wear_rate) / Float64(N)
    print("MOJO_TIMING tribochemistry::archard_wear_rate", _ns_archard_wear_rate, _acc_archard_wear_rate)
    var _result_archard_wear_rate = archard_wear_rate(0.5, 0.5, 0.5, 0.5)
    var _summary_archard_wear_rate = _summary_float64(_result_archard_wear_rate)
    print("MOJO_RESULT tribochemistry::archard_wear_rate", _summary_archard_wear_rate)
    var _acc_hertz_contact_radius: Float64 = 0.0
    var _t0_hertz_contact_radius = perf_counter_ns()
    for _ in range(N):
        _acc_hertz_contact_radius += hertz_contact_radius(0.5, 0.5, 0.5)
    var _t1_hertz_contact_radius = perf_counter_ns()
    var _ns_hertz_contact_radius = Float64(_t1_hertz_contact_radius - _t0_hertz_contact_radius) / Float64(N)
    print("MOJO_TIMING tribochemistry::hertz_contact_radius", _ns_hertz_contact_radius, _acc_hertz_contact_radius)
    var _result_hertz_contact_radius = hertz_contact_radius(0.5, 0.5, 0.5)
    var _summary_hertz_contact_radius = _summary_float64(_result_hertz_contact_radius)
    print("MOJO_RESULT tribochemistry::hertz_contact_radius", _summary_hertz_contact_radius)
    var _acc_hertz_max_pressure: Float64 = 0.0
    var _t0_hertz_max_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_hertz_max_pressure += hertz_max_pressure(0.5, 0.5)
    var _t1_hertz_max_pressure = perf_counter_ns()
    var _ns_hertz_max_pressure = Float64(_t1_hertz_max_pressure - _t0_hertz_max_pressure) / Float64(N)
    print("MOJO_TIMING tribochemistry::hertz_max_pressure", _ns_hertz_max_pressure, _acc_hertz_max_pressure)
    var _result_hertz_max_pressure = hertz_max_pressure(0.5, 0.5)
    var _summary_hertz_max_pressure = _summary_float64(_result_hertz_max_pressure)
    print("MOJO_RESULT tribochemistry::hertz_max_pressure", _summary_hertz_max_pressure)
    var _acc_flash_temperature: Float64 = 0.0
    var _t0_flash_temperature = perf_counter_ns()
    for _ in range(N):
        _acc_flash_temperature += flash_temperature(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_flash_temperature = perf_counter_ns()
    var _ns_flash_temperature = Float64(_t1_flash_temperature - _t0_flash_temperature) / Float64(N)
    print("MOJO_TIMING tribochemistry::flash_temperature", _ns_flash_temperature, _acc_flash_temperature)
    var _result_flash_temperature = flash_temperature(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_flash_temperature = _summary_float64(_result_flash_temperature)
    print("MOJO_RESULT tribochemistry::flash_temperature", _summary_flash_temperature)
    var _acc_film_thickness_ehd: Float64 = 0.0
    var _t0_film_thickness_ehd = perf_counter_ns()
    for _ in range(N):
        _acc_film_thickness_ehd += film_thickness_ehd(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_film_thickness_ehd = perf_counter_ns()
    var _ns_film_thickness_ehd = Float64(_t1_film_thickness_ehd - _t0_film_thickness_ehd) / Float64(N)
    print("MOJO_TIMING tribochemistry::film_thickness_ehd", _ns_film_thickness_ehd, _acc_film_thickness_ehd)
    var _result_film_thickness_ehd = film_thickness_ehd(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_film_thickness_ehd = _summary_float64(_result_film_thickness_ehd)
    print("MOJO_RESULT tribochemistry::film_thickness_ehd", _summary_film_thickness_ehd)
    var _acc_lambda_ratio: Float64 = 0.0
    var _t0_lambda_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_lambda_ratio += lambda_ratio(0.5, 0.5)
    var _t1_lambda_ratio = perf_counter_ns()
    var _ns_lambda_ratio = Float64(_t1_lambda_ratio - _t0_lambda_ratio) / Float64(N)
    print("MOJO_TIMING tribochemistry::lambda_ratio", _ns_lambda_ratio, _acc_lambda_ratio)
    var _result_lambda_ratio = lambda_ratio(0.5, 0.5)
    var _summary_lambda_ratio = _summary_float64(_result_lambda_ratio)
    print("MOJO_RESULT tribochemistry::lambda_ratio", _summary_lambda_ratio)
    var _acc_surface_energy_work: Float64 = 0.0
    var _t0_surface_energy_work = perf_counter_ns()
    for _ in range(N):
        _acc_surface_energy_work += surface_energy_work(0.5)
    var _t1_surface_energy_work = perf_counter_ns()
    var _ns_surface_energy_work = Float64(_t1_surface_energy_work - _t0_surface_energy_work) / Float64(N)
    print("MOJO_TIMING tribochemistry::surface_energy_work", _ns_surface_energy_work, _acc_surface_energy_work)
    var _result_surface_energy_work = surface_energy_work(0.5)
    var _summary_surface_energy_work = _summary_float64(_result_surface_energy_work)
    print("MOJO_RESULT tribochemistry::surface_energy_work", _summary_surface_energy_work)
    var _acc_tribocorrosion_rate: Float64 = 0.0
    var _t0_tribocorrosion_rate = perf_counter_ns()
    for _ in range(N):
        _acc_tribocorrosion_rate += tribocorrosion_rate(0.5, 0.5, 0.5)
    var _t1_tribocorrosion_rate = perf_counter_ns()
    var _ns_tribocorrosion_rate = Float64(_t1_tribocorrosion_rate - _t0_tribocorrosion_rate) / Float64(N)
    print("MOJO_TIMING tribochemistry::tribocorrosion_rate", _ns_tribocorrosion_rate, _acc_tribocorrosion_rate)
    var _result_tribocorrosion_rate = tribocorrosion_rate(0.5, 0.5, 0.5)
    var _summary_tribocorrosion_rate = _summary_float64(_result_tribocorrosion_rate)
    print("MOJO_RESULT tribochemistry::tribocorrosion_rate", _summary_tribocorrosion_rate)
    var _acc_wear_volume: Float64 = 0.0
    var _t0_wear_volume = perf_counter_ns()
    for _ in range(N):
        _acc_wear_volume += wear_volume(0.5, 0.5, 0.5, 0.5)
    var _t1_wear_volume = perf_counter_ns()
    var _ns_wear_volume = Float64(_t1_wear_volume - _t0_wear_volume) / Float64(N)
    print("MOJO_TIMING tribochemistry::wear_volume", _ns_wear_volume, _acc_wear_volume)
    var _result_wear_volume = wear_volume(0.5, 0.5, 0.5, 0.5)
    var _summary_wear_volume = _summary_float64(_result_wear_volume)
    print("MOJO_RESULT tribochemistry::wear_volume", _summary_wear_volume)
