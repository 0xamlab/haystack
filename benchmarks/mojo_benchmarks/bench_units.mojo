"""bench_units.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from units import convert_length, convert_mass, convert_temperature, convert_time, convert_area, convert_volume, convert_speed, convert_data
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

    var _acc_convert_length: Float64 = 0.0
    var _t0_convert_length = perf_counter_ns()
    for _ in range(N):
        _acc_convert_length += convert_length(0.5, "test", "test")
    var _t1_convert_length = perf_counter_ns()
    var _ns_convert_length = Float64(_t1_convert_length - _t0_convert_length) / Float64(N)
    print("MOJO_TIMING units::convert_length", _ns_convert_length, _acc_convert_length)
    var _acc_convert_mass: Float64 = 0.0
    var _t0_convert_mass = perf_counter_ns()
    for _ in range(N):
        _acc_convert_mass += convert_mass(0.5, "test", "test")
    var _t1_convert_mass = perf_counter_ns()
    var _ns_convert_mass = Float64(_t1_convert_mass - _t0_convert_mass) / Float64(N)
    print("MOJO_TIMING units::convert_mass", _ns_convert_mass, _acc_convert_mass)
    var _acc_convert_temperature: Float64 = 0.0
    var _t0_convert_temperature = perf_counter_ns()
    for _ in range(N):
        _acc_convert_temperature += convert_temperature(0.5, "test", "test")
    var _t1_convert_temperature = perf_counter_ns()
    var _ns_convert_temperature = Float64(_t1_convert_temperature - _t0_convert_temperature) / Float64(N)
    print("MOJO_TIMING units::convert_temperature", _ns_convert_temperature, _acc_convert_temperature)
    var _acc_convert_time: Float64 = 0.0
    var _t0_convert_time = perf_counter_ns()
    for _ in range(N):
        _acc_convert_time += convert_time(0.5, "test", "test")
    var _t1_convert_time = perf_counter_ns()
    var _ns_convert_time = Float64(_t1_convert_time - _t0_convert_time) / Float64(N)
    print("MOJO_TIMING units::convert_time", _ns_convert_time, _acc_convert_time)
    var _acc_convert_area: Float64 = 0.0
    var _t0_convert_area = perf_counter_ns()
    for _ in range(N):
        _acc_convert_area += convert_area(0.5, "test", "test")
    var _t1_convert_area = perf_counter_ns()
    var _ns_convert_area = Float64(_t1_convert_area - _t0_convert_area) / Float64(N)
    print("MOJO_TIMING units::convert_area", _ns_convert_area, _acc_convert_area)
    var _acc_convert_volume: Float64 = 0.0
    var _t0_convert_volume = perf_counter_ns()
    for _ in range(N):
        _acc_convert_volume += convert_volume(0.5, "test", "test")
    var _t1_convert_volume = perf_counter_ns()
    var _ns_convert_volume = Float64(_t1_convert_volume - _t0_convert_volume) / Float64(N)
    print("MOJO_TIMING units::convert_volume", _ns_convert_volume, _acc_convert_volume)
    var _acc_convert_speed: Float64 = 0.0
    var _t0_convert_speed = perf_counter_ns()
    for _ in range(N):
        _acc_convert_speed += convert_speed(0.5, "test", "test")
    var _t1_convert_speed = perf_counter_ns()
    var _ns_convert_speed = Float64(_t1_convert_speed - _t0_convert_speed) / Float64(N)
    print("MOJO_TIMING units::convert_speed", _ns_convert_speed, _acc_convert_speed)
    var _acc_convert_data: Float64 = 0.0
    var _t0_convert_data = perf_counter_ns()
    for _ in range(N):
        _acc_convert_data += convert_data(0.5, "test", "test")
    var _t1_convert_data = perf_counter_ns()
    var _ns_convert_data = Float64(_t1_convert_data - _t0_convert_data) / Float64(N)
    print("MOJO_TIMING units::convert_data", _ns_convert_data, _acc_convert_data)
