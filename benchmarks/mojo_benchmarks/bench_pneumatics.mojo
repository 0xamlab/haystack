"""bench_pneumatics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from pneumatics import ideal_gas_volume, flow_rate_orifice, compressor_power, pressure_drop_pipe, air_consumption, cylinder_force, bore_area, piston_speed, receiver_volume, free_air_delivery, specific_power, dew_point_pressure
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

    var _acc_ideal_gas_volume: Float64 = 0.0
    var _t0_ideal_gas_volume = perf_counter_ns()
    for _ in range(N):
        _acc_ideal_gas_volume += ideal_gas_volume(0.5, 0.5, 0.5)
    var _t1_ideal_gas_volume = perf_counter_ns()
    var _ns_ideal_gas_volume = Float64(_t1_ideal_gas_volume - _t0_ideal_gas_volume) / Float64(N)
    print("MOJO_TIMING pneumatics::ideal_gas_volume", _ns_ideal_gas_volume, _acc_ideal_gas_volume)
    var _acc_flow_rate_orifice: Float64 = 0.0
    var _t0_flow_rate_orifice = perf_counter_ns()
    for _ in range(N):
        _acc_flow_rate_orifice += flow_rate_orifice(0.5, 0.5, 0.5, 0.5)
    var _t1_flow_rate_orifice = perf_counter_ns()
    var _ns_flow_rate_orifice = Float64(_t1_flow_rate_orifice - _t0_flow_rate_orifice) / Float64(N)
    print("MOJO_TIMING pneumatics::flow_rate_orifice", _ns_flow_rate_orifice, _acc_flow_rate_orifice)
    var _acc_compressor_power: Float64 = 0.0
    var _t0_compressor_power = perf_counter_ns()
    for _ in range(N):
        _acc_compressor_power += compressor_power(0.5, 0.5, 0.5, 0.5)
    var _t1_compressor_power = perf_counter_ns()
    var _ns_compressor_power = Float64(_t1_compressor_power - _t0_compressor_power) / Float64(N)
    print("MOJO_TIMING pneumatics::compressor_power", _ns_compressor_power, _acc_compressor_power)
    var _acc_pressure_drop_pipe: Float64 = 0.0
    var _t0_pressure_drop_pipe = perf_counter_ns()
    for _ in range(N):
        _acc_pressure_drop_pipe += pressure_drop_pipe(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_pressure_drop_pipe = perf_counter_ns()
    var _ns_pressure_drop_pipe = Float64(_t1_pressure_drop_pipe - _t0_pressure_drop_pipe) / Float64(N)
    print("MOJO_TIMING pneumatics::pressure_drop_pipe", _ns_pressure_drop_pipe, _acc_pressure_drop_pipe)
    var _acc_air_consumption: Float64 = 0.0
    var _t0_air_consumption = perf_counter_ns()
    for _ in range(N):
        _acc_air_consumption += air_consumption(0.5, 0.5, 0.5, 0.5)
    var _t1_air_consumption = perf_counter_ns()
    var _ns_air_consumption = Float64(_t1_air_consumption - _t0_air_consumption) / Float64(N)
    print("MOJO_TIMING pneumatics::air_consumption", _ns_air_consumption, _acc_air_consumption)
    var _acc_cylinder_force: Float64 = 0.0
    var _t0_cylinder_force = perf_counter_ns()
    for _ in range(N):
        _acc_cylinder_force += cylinder_force(0.5, 0.5)
    var _t1_cylinder_force = perf_counter_ns()
    var _ns_cylinder_force = Float64(_t1_cylinder_force - _t0_cylinder_force) / Float64(N)
    print("MOJO_TIMING pneumatics::cylinder_force", _ns_cylinder_force, _acc_cylinder_force)
    var _acc_bore_area: Float64 = 0.0
    var _t0_bore_area = perf_counter_ns()
    for _ in range(N):
        _acc_bore_area += bore_area(0.5)
    var _t1_bore_area = perf_counter_ns()
    var _ns_bore_area = Float64(_t1_bore_area - _t0_bore_area) / Float64(N)
    print("MOJO_TIMING pneumatics::bore_area", _ns_bore_area, _acc_bore_area)
    var _acc_piston_speed: Float64 = 0.0
    var _t0_piston_speed = perf_counter_ns()
    for _ in range(N):
        _acc_piston_speed += piston_speed(0.5, 0.5)
    var _t1_piston_speed = perf_counter_ns()
    var _ns_piston_speed = Float64(_t1_piston_speed - _t0_piston_speed) / Float64(N)
    print("MOJO_TIMING pneumatics::piston_speed", _ns_piston_speed, _acc_piston_speed)
    var _acc_receiver_volume: Float64 = 0.0
    var _t0_receiver_volume = perf_counter_ns()
    for _ in range(N):
        _acc_receiver_volume += receiver_volume(0.5, 0.5, 0.5, 0.5)
    var _t1_receiver_volume = perf_counter_ns()
    var _ns_receiver_volume = Float64(_t1_receiver_volume - _t0_receiver_volume) / Float64(N)
    print("MOJO_TIMING pneumatics::receiver_volume", _ns_receiver_volume, _acc_receiver_volume)
    var _acc_free_air_delivery: Float64 = 0.0
    var _t0_free_air_delivery = perf_counter_ns()
    for _ in range(N):
        _acc_free_air_delivery += free_air_delivery(0.5, 0.5, 0.5)
    var _t1_free_air_delivery = perf_counter_ns()
    var _ns_free_air_delivery = Float64(_t1_free_air_delivery - _t0_free_air_delivery) / Float64(N)
    print("MOJO_TIMING pneumatics::free_air_delivery", _ns_free_air_delivery, _acc_free_air_delivery)
    var _acc_specific_power: Float64 = 0.0
    var _t0_specific_power = perf_counter_ns()
    for _ in range(N):
        _acc_specific_power += specific_power(0.5, 0.5)
    var _t1_specific_power = perf_counter_ns()
    var _ns_specific_power = Float64(_t1_specific_power - _t0_specific_power) / Float64(N)
    print("MOJO_TIMING pneumatics::specific_power", _ns_specific_power, _acc_specific_power)
    var _acc_dew_point_pressure: Float64 = 0.0
    var _t0_dew_point_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_dew_point_pressure += dew_point_pressure(0.5, 0.5)
    var _t1_dew_point_pressure = perf_counter_ns()
    var _ns_dew_point_pressure = Float64(_t1_dew_point_pressure - _t0_dew_point_pressure) / Float64(N)
    print("MOJO_TIMING pneumatics::dew_point_pressure", _ns_dew_point_pressure, _acc_dew_point_pressure)
