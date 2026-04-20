"""bench_fire_safety.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from fire_safety import fire_load_density, heat_release_rate, flashover_mfo, sprinkler_activation_time, smoke_layer_height, evacuation_time, safe_egress_time, fire_resistance_rating, ventilation_factor, fire_severity, co_concentration_danger, occupant_load
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

    var _acc_fire_load_density: Float64 = 0.0
    var _t0_fire_load_density = perf_counter_ns()
    for _ in range(N):
        _acc_fire_load_density += fire_load_density(0.5, 0.5)
    var _t1_fire_load_density = perf_counter_ns()
    var _ns_fire_load_density = Float64(_t1_fire_load_density - _t0_fire_load_density) / Float64(N)
    print("MOJO_TIMING fire_safety::fire_load_density", _ns_fire_load_density, _acc_fire_load_density)
    var _acc_heat_release_rate: Float64 = 0.0
    var _t0_heat_release_rate = perf_counter_ns()
    for _ in range(N):
        _acc_heat_release_rate += heat_release_rate(0.5, 0.5)
    var _t1_heat_release_rate = perf_counter_ns()
    var _ns_heat_release_rate = Float64(_t1_heat_release_rate - _t0_heat_release_rate) / Float64(N)
    print("MOJO_TIMING fire_safety::heat_release_rate", _ns_heat_release_rate, _acc_heat_release_rate)
    var _acc_flashover_mfo: Float64 = 0.0
    var _t0_flashover_mfo = perf_counter_ns()
    for _ in range(N):
        _acc_flashover_mfo += flashover_mfo(0.5, 0.5, 0.5)
    var _t1_flashover_mfo = perf_counter_ns()
    var _ns_flashover_mfo = Float64(_t1_flashover_mfo - _t0_flashover_mfo) / Float64(N)
    print("MOJO_TIMING fire_safety::flashover_mfo", _ns_flashover_mfo, _acc_flashover_mfo)
    var _acc_sprinkler_activation_time: Float64 = 0.0
    var _t0_sprinkler_activation_time = perf_counter_ns()
    for _ in range(N):
        _acc_sprinkler_activation_time += sprinkler_activation_time(0.5, 0.5, 0.5, 0.5)
    var _t1_sprinkler_activation_time = perf_counter_ns()
    var _ns_sprinkler_activation_time = Float64(_t1_sprinkler_activation_time - _t0_sprinkler_activation_time) / Float64(N)
    print("MOJO_TIMING fire_safety::sprinkler_activation_time", _ns_sprinkler_activation_time, _acc_sprinkler_activation_time)
    var _acc_smoke_layer_height: Float64 = 0.0
    var _t0_smoke_layer_height = perf_counter_ns()
    for _ in range(N):
        _acc_smoke_layer_height += smoke_layer_height(0.5, 0.5, 0.5)
    var _t1_smoke_layer_height = perf_counter_ns()
    var _ns_smoke_layer_height = Float64(_t1_smoke_layer_height - _t0_smoke_layer_height) / Float64(N)
    print("MOJO_TIMING fire_safety::smoke_layer_height", _ns_smoke_layer_height, _acc_smoke_layer_height)
    var _acc_evacuation_time: Float64 = 0.0
    var _t0_evacuation_time = perf_counter_ns()
    for _ in range(N):
        _acc_evacuation_time += evacuation_time(0.5, 0.5, 0.5)
    var _t1_evacuation_time = perf_counter_ns()
    var _ns_evacuation_time = Float64(_t1_evacuation_time - _t0_evacuation_time) / Float64(N)
    print("MOJO_TIMING fire_safety::evacuation_time", _ns_evacuation_time, _acc_evacuation_time)
    var _acc_safe_egress_time: Float64 = 0.0
    var _t0_safe_egress_time = perf_counter_ns()
    for _ in range(N):
        _acc_safe_egress_time += safe_egress_time(0.5, 0.5, 0.5, 0.5)
    var _t1_safe_egress_time = perf_counter_ns()
    var _ns_safe_egress_time = Float64(_t1_safe_egress_time - _t0_safe_egress_time) / Float64(N)
    print("MOJO_TIMING fire_safety::safe_egress_time", _ns_safe_egress_time, _acc_safe_egress_time)
    var _acc_fire_resistance_rating: Float64 = 0.0
    var _t0_fire_resistance_rating = perf_counter_ns()
    for _ in range(N):
        _acc_fire_resistance_rating += fire_resistance_rating(0.5, 0.5)
    var _t1_fire_resistance_rating = perf_counter_ns()
    var _ns_fire_resistance_rating = Float64(_t1_fire_resistance_rating - _t0_fire_resistance_rating) / Float64(N)
    print("MOJO_TIMING fire_safety::fire_resistance_rating", _ns_fire_resistance_rating, _acc_fire_resistance_rating)
    var _acc_ventilation_factor: Float64 = 0.0
    var _t0_ventilation_factor = perf_counter_ns()
    for _ in range(N):
        _acc_ventilation_factor += ventilation_factor(0.5, 0.5)
    var _t1_ventilation_factor = perf_counter_ns()
    var _ns_ventilation_factor = Float64(_t1_ventilation_factor - _t0_ventilation_factor) / Float64(N)
    print("MOJO_TIMING fire_safety::ventilation_factor", _ns_ventilation_factor, _acc_ventilation_factor)
    var _acc_fire_severity: Float64 = 0.0
    var _t0_fire_severity = perf_counter_ns()
    for _ in range(N):
        _acc_fire_severity += fire_severity(0.5, 0.5)
    var _t1_fire_severity = perf_counter_ns()
    var _ns_fire_severity = Float64(_t1_fire_severity - _t0_fire_severity) / Float64(N)
    print("MOJO_TIMING fire_safety::fire_severity", _ns_fire_severity, _acc_fire_severity)
    var _acc_co_concentration_danger: Float64 = 0.0
    var _t0_co_concentration_danger = perf_counter_ns()
    for _ in range(N):
        _acc_co_concentration_danger += Float64(co_concentration_danger(0.5))
    var _t1_co_concentration_danger = perf_counter_ns()
    var _ns_co_concentration_danger = Float64(_t1_co_concentration_danger - _t0_co_concentration_danger) / Float64(N)
    print("MOJO_TIMING fire_safety::co_concentration_danger", _ns_co_concentration_danger, _acc_co_concentration_danger)
    var _acc_occupant_load: Float64 = 0.0
    var _t0_occupant_load = perf_counter_ns()
    for _ in range(N):
        _acc_occupant_load += occupant_load(0.5, 0.5)
    var _t1_occupant_load = perf_counter_ns()
    var _ns_occupant_load = Float64(_t1_occupant_load - _t0_occupant_load) / Float64(N)
    print("MOJO_TIMING fire_safety::occupant_load", _ns_occupant_load, _acc_occupant_load)
