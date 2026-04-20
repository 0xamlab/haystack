"""bench_hydraulics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from hydraulics import pascals_law_force, pascals_law_pressure, hydraulic_advantage, flow_rate_cylinder, cylinder_velocity, pump_displacement, hydraulic_power, system_pressure_loss, accumulator_volume, relief_valve_flow, oil_compressibility, cylinder_bore_from_force
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

    var _acc_pascals_law_force: Float64 = 0.0
    var _t0_pascals_law_force = perf_counter_ns()
    for _ in range(N):
        _acc_pascals_law_force += pascals_law_force(0.5, 0.5)
    var _t1_pascals_law_force = perf_counter_ns()
    var _ns_pascals_law_force = Float64(_t1_pascals_law_force - _t0_pascals_law_force) / Float64(N)
    print("MOJO_TIMING hydraulics::pascals_law_force", _ns_pascals_law_force, _acc_pascals_law_force)
    var _acc_pascals_law_pressure: Float64 = 0.0
    var _t0_pascals_law_pressure = perf_counter_ns()
    for _ in range(N):
        _acc_pascals_law_pressure += pascals_law_pressure(0.5, 0.5)
    var _t1_pascals_law_pressure = perf_counter_ns()
    var _ns_pascals_law_pressure = Float64(_t1_pascals_law_pressure - _t0_pascals_law_pressure) / Float64(N)
    print("MOJO_TIMING hydraulics::pascals_law_pressure", _ns_pascals_law_pressure, _acc_pascals_law_pressure)
    var _acc_hydraulic_advantage: Float64 = 0.0
    var _t0_hydraulic_advantage = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_advantage += hydraulic_advantage(0.5, 0.5)
    var _t1_hydraulic_advantage = perf_counter_ns()
    var _ns_hydraulic_advantage = Float64(_t1_hydraulic_advantage - _t0_hydraulic_advantage) / Float64(N)
    print("MOJO_TIMING hydraulics::hydraulic_advantage", _ns_hydraulic_advantage, _acc_hydraulic_advantage)
    var _acc_flow_rate_cylinder: Float64 = 0.0
    var _t0_flow_rate_cylinder = perf_counter_ns()
    for _ in range(N):
        _acc_flow_rate_cylinder += flow_rate_cylinder(0.5, 0.5)
    var _t1_flow_rate_cylinder = perf_counter_ns()
    var _ns_flow_rate_cylinder = Float64(_t1_flow_rate_cylinder - _t0_flow_rate_cylinder) / Float64(N)
    print("MOJO_TIMING hydraulics::flow_rate_cylinder", _ns_flow_rate_cylinder, _acc_flow_rate_cylinder)
    var _acc_cylinder_velocity: Float64 = 0.0
    var _t0_cylinder_velocity = perf_counter_ns()
    for _ in range(N):
        _acc_cylinder_velocity += cylinder_velocity(0.5, 0.5)
    var _t1_cylinder_velocity = perf_counter_ns()
    var _ns_cylinder_velocity = Float64(_t1_cylinder_velocity - _t0_cylinder_velocity) / Float64(N)
    print("MOJO_TIMING hydraulics::cylinder_velocity", _ns_cylinder_velocity, _acc_cylinder_velocity)
    var _acc_pump_displacement: Float64 = 0.0
    var _t0_pump_displacement = perf_counter_ns()
    for _ in range(N):
        _acc_pump_displacement += pump_displacement(0.5, 0.5)
    var _t1_pump_displacement = perf_counter_ns()
    var _ns_pump_displacement = Float64(_t1_pump_displacement - _t0_pump_displacement) / Float64(N)
    print("MOJO_TIMING hydraulics::pump_displacement", _ns_pump_displacement, _acc_pump_displacement)
    var _acc_hydraulic_power: Float64 = 0.0
    var _t0_hydraulic_power = perf_counter_ns()
    for _ in range(N):
        _acc_hydraulic_power += hydraulic_power(0.5, 0.5)
    var _t1_hydraulic_power = perf_counter_ns()
    var _ns_hydraulic_power = Float64(_t1_hydraulic_power - _t0_hydraulic_power) / Float64(N)
    print("MOJO_TIMING hydraulics::hydraulic_power", _ns_hydraulic_power, _acc_hydraulic_power)
    var _acc_system_pressure_loss: Float64 = 0.0
    var _t0_system_pressure_loss = perf_counter_ns()
    for _ in range(N):
        _acc_system_pressure_loss += system_pressure_loss(0.5, 0.5)
    var _t1_system_pressure_loss = perf_counter_ns()
    var _ns_system_pressure_loss = Float64(_t1_system_pressure_loss - _t0_system_pressure_loss) / Float64(N)
    print("MOJO_TIMING hydraulics::system_pressure_loss", _ns_system_pressure_loss, _acc_system_pressure_loss)
    var _acc_accumulator_volume: Float64 = 0.0
    var _t0_accumulator_volume = perf_counter_ns()
    for _ in range(N):
        _acc_accumulator_volume += accumulator_volume(0.5, 0.5, 0.5)
    var _t1_accumulator_volume = perf_counter_ns()
    var _ns_accumulator_volume = Float64(_t1_accumulator_volume - _t0_accumulator_volume) / Float64(N)
    print("MOJO_TIMING hydraulics::accumulator_volume", _ns_accumulator_volume, _acc_accumulator_volume)
    var _acc_relief_valve_flow: Float64 = 0.0
    var _t0_relief_valve_flow = perf_counter_ns()
    for _ in range(N):
        _acc_relief_valve_flow += relief_valve_flow(0.5, 0.5, 0.5)
    var _t1_relief_valve_flow = perf_counter_ns()
    var _ns_relief_valve_flow = Float64(_t1_relief_valve_flow - _t0_relief_valve_flow) / Float64(N)
    print("MOJO_TIMING hydraulics::relief_valve_flow", _ns_relief_valve_flow, _acc_relief_valve_flow)
    var _acc_oil_compressibility: Float64 = 0.0
    var _t0_oil_compressibility = perf_counter_ns()
    for _ in range(N):
        _acc_oil_compressibility += oil_compressibility(0.5, 0.5, 0.5)
    var _t1_oil_compressibility = perf_counter_ns()
    var _ns_oil_compressibility = Float64(_t1_oil_compressibility - _t0_oil_compressibility) / Float64(N)
    print("MOJO_TIMING hydraulics::oil_compressibility", _ns_oil_compressibility, _acc_oil_compressibility)
    var _acc_cylinder_bore_from_force: Float64 = 0.0
    var _t0_cylinder_bore_from_force = perf_counter_ns()
    for _ in range(N):
        _acc_cylinder_bore_from_force += cylinder_bore_from_force(0.5, 0.5)
    var _t1_cylinder_bore_from_force = perf_counter_ns()
    var _ns_cylinder_bore_from_force = Float64(_t1_cylinder_bore_from_force - _t0_cylinder_bore_from_force) / Float64(N)
    print("MOJO_TIMING hydraulics::cylinder_bore_from_force", _ns_cylinder_bore_from_force, _acc_cylinder_bore_from_force)
