"""bench_drones.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from drones import thrust_to_weight_ratio, hover_power, flight_time_minutes, max_range, payload_capacity, disk_loading, propeller_tip_speed, advance_ratio, battery_energy_density, communication_range_los, gsd_from_altitude, endurance_factor
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

    var _acc_thrust_to_weight_ratio: Float64 = 0.0
    var _t0_thrust_to_weight_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_thrust_to_weight_ratio += thrust_to_weight_ratio(0.5, 0.5)
    var _t1_thrust_to_weight_ratio = perf_counter_ns()
    var _ns_thrust_to_weight_ratio = Float64(_t1_thrust_to_weight_ratio - _t0_thrust_to_weight_ratio) / Float64(N)
    print("MOJO_TIMING drones::thrust_to_weight_ratio", _ns_thrust_to_weight_ratio, _acc_thrust_to_weight_ratio)
    var _acc_hover_power: Float64 = 0.0
    var _t0_hover_power = perf_counter_ns()
    for _ in range(N):
        _acc_hover_power += hover_power(0.5, 0.5, 0.5)
    var _t1_hover_power = perf_counter_ns()
    var _ns_hover_power = Float64(_t1_hover_power - _t0_hover_power) / Float64(N)
    print("MOJO_TIMING drones::hover_power", _ns_hover_power, _acc_hover_power)
    var _acc_flight_time_minutes: Float64 = 0.0
    var _t0_flight_time_minutes = perf_counter_ns()
    for _ in range(N):
        _acc_flight_time_minutes += flight_time_minutes(0.5, 0.5)
    var _t1_flight_time_minutes = perf_counter_ns()
    var _ns_flight_time_minutes = Float64(_t1_flight_time_minutes - _t0_flight_time_minutes) / Float64(N)
    print("MOJO_TIMING drones::flight_time_minutes", _ns_flight_time_minutes, _acc_flight_time_minutes)
    var _acc_max_range: Float64 = 0.0
    var _t0_max_range = perf_counter_ns()
    for _ in range(N):
        _acc_max_range += max_range(0.5, 0.5)
    var _t1_max_range = perf_counter_ns()
    var _ns_max_range = Float64(_t1_max_range - _t0_max_range) / Float64(N)
    print("MOJO_TIMING drones::max_range", _ns_max_range, _acc_max_range)
    var _acc_payload_capacity: Float64 = 0.0
    var _t0_payload_capacity = perf_counter_ns()
    for _ in range(N):
        _acc_payload_capacity += payload_capacity(0.5, 0.5, 0.5)
    var _t1_payload_capacity = perf_counter_ns()
    var _ns_payload_capacity = Float64(_t1_payload_capacity - _t0_payload_capacity) / Float64(N)
    print("MOJO_TIMING drones::payload_capacity", _ns_payload_capacity, _acc_payload_capacity)
    var _acc_disk_loading: Float64 = 0.0
    var _t0_disk_loading = perf_counter_ns()
    for _ in range(N):
        _acc_disk_loading += disk_loading(0.5, 0.5)
    var _t1_disk_loading = perf_counter_ns()
    var _ns_disk_loading = Float64(_t1_disk_loading - _t0_disk_loading) / Float64(N)
    print("MOJO_TIMING drones::disk_loading", _ns_disk_loading, _acc_disk_loading)
    var _acc_propeller_tip_speed: Float64 = 0.0
    var _t0_propeller_tip_speed = perf_counter_ns()
    for _ in range(N):
        _acc_propeller_tip_speed += propeller_tip_speed(0.5, 0.5)
    var _t1_propeller_tip_speed = perf_counter_ns()
    var _ns_propeller_tip_speed = Float64(_t1_propeller_tip_speed - _t0_propeller_tip_speed) / Float64(N)
    print("MOJO_TIMING drones::propeller_tip_speed", _ns_propeller_tip_speed, _acc_propeller_tip_speed)
    var _acc_advance_ratio: Float64 = 0.0
    var _t0_advance_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_advance_ratio += advance_ratio(0.5, 0.5, 0.5)
    var _t1_advance_ratio = perf_counter_ns()
    var _ns_advance_ratio = Float64(_t1_advance_ratio - _t0_advance_ratio) / Float64(N)
    print("MOJO_TIMING drones::advance_ratio", _ns_advance_ratio, _acc_advance_ratio)
    var _acc_battery_energy_density: Float64 = 0.0
    var _t0_battery_energy_density = perf_counter_ns()
    for _ in range(N):
        _acc_battery_energy_density += battery_energy_density(0.5, 0.5)
    var _t1_battery_energy_density = perf_counter_ns()
    var _ns_battery_energy_density = Float64(_t1_battery_energy_density - _t0_battery_energy_density) / Float64(N)
    print("MOJO_TIMING drones::battery_energy_density", _ns_battery_energy_density, _acc_battery_energy_density)
    var _acc_communication_range_los: Float64 = 0.0
    var _t0_communication_range_los = perf_counter_ns()
    for _ in range(N):
        _acc_communication_range_los += communication_range_los(0.5, 0.5)
    var _t1_communication_range_los = perf_counter_ns()
    var _ns_communication_range_los = Float64(_t1_communication_range_los - _t0_communication_range_los) / Float64(N)
    print("MOJO_TIMING drones::communication_range_los", _ns_communication_range_los, _acc_communication_range_los)
    var _acc_gsd_from_altitude: Float64 = 0.0
    var _t0_gsd_from_altitude = perf_counter_ns()
    for _ in range(N):
        _acc_gsd_from_altitude += gsd_from_altitude(0.5, 0.5, 0.5, 0.5)
    var _t1_gsd_from_altitude = perf_counter_ns()
    var _ns_gsd_from_altitude = Float64(_t1_gsd_from_altitude - _t0_gsd_from_altitude) / Float64(N)
    print("MOJO_TIMING drones::gsd_from_altitude", _ns_gsd_from_altitude, _acc_gsd_from_altitude)
    var _acc_endurance_factor: Float64 = 0.0
    var _t0_endurance_factor = perf_counter_ns()
    for _ in range(N):
        _acc_endurance_factor += endurance_factor(0.5, 0.5, 0.5, 0.5)
    var _t1_endurance_factor = perf_counter_ns()
    var _ns_endurance_factor = Float64(_t1_endurance_factor - _t0_endurance_factor) / Float64(N)
    print("MOJO_TIMING drones::endurance_factor", _ns_endurance_factor, _acc_endurance_factor)
