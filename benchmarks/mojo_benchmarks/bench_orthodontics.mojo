"""bench_orthodontics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from orthodontics import tooth_movement_rate, moment_to_force_ratio, anchorage_loss_estimate, arch_wire_force, levelling_torque, bolton_ratio, pont_index, arch_perimeter_estimate, growth_prediction_cephalometric, retainer_force_decay
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

    var _acc_tooth_movement_rate: Float64 = 0.0
    var _t0_tooth_movement_rate = perf_counter_ns()
    for _ in range(N):
        _acc_tooth_movement_rate += tooth_movement_rate(0.5, 0.5)
    var _t1_tooth_movement_rate = perf_counter_ns()
    var _ns_tooth_movement_rate = Float64(_t1_tooth_movement_rate - _t0_tooth_movement_rate) / Float64(N)
    print("MOJO_TIMING orthodontics::tooth_movement_rate", _ns_tooth_movement_rate, _acc_tooth_movement_rate)
    var _acc_moment_to_force_ratio: Float64 = 0.0
    var _t0_moment_to_force_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_moment_to_force_ratio += moment_to_force_ratio(0.5, 0.5)
    var _t1_moment_to_force_ratio = perf_counter_ns()
    var _ns_moment_to_force_ratio = Float64(_t1_moment_to_force_ratio - _t0_moment_to_force_ratio) / Float64(N)
    print("MOJO_TIMING orthodontics::moment_to_force_ratio", _ns_moment_to_force_ratio, _acc_moment_to_force_ratio)
    var _acc_anchorage_loss_estimate: Float64 = 0.0
    var _t0_anchorage_loss_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_anchorage_loss_estimate += anchorage_loss_estimate(0.5, 0.5)
    var _t1_anchorage_loss_estimate = perf_counter_ns()
    var _ns_anchorage_loss_estimate = Float64(_t1_anchorage_loss_estimate - _t0_anchorage_loss_estimate) / Float64(N)
    print("MOJO_TIMING orthodontics::anchorage_loss_estimate", _ns_anchorage_loss_estimate, _acc_anchorage_loss_estimate)
    var _acc_arch_wire_force: Float64 = 0.0
    var _t0_arch_wire_force = perf_counter_ns()
    for _ in range(N):
        _acc_arch_wire_force += arch_wire_force(0.5, 0.5, 0.5, 0.5)
    var _t1_arch_wire_force = perf_counter_ns()
    var _ns_arch_wire_force = Float64(_t1_arch_wire_force - _t0_arch_wire_force) / Float64(N)
    print("MOJO_TIMING orthodontics::arch_wire_force", _ns_arch_wire_force, _acc_arch_wire_force)
    var _acc_levelling_torque: Float64 = 0.0
    var _t0_levelling_torque = perf_counter_ns()
    for _ in range(N):
        _acc_levelling_torque += levelling_torque(0.5, 0.5, 0.5, 0.5)
    var _t1_levelling_torque = perf_counter_ns()
    var _ns_levelling_torque = Float64(_t1_levelling_torque - _t0_levelling_torque) / Float64(N)
    print("MOJO_TIMING orthodontics::levelling_torque", _ns_levelling_torque, _acc_levelling_torque)
    var _acc_bolton_ratio: Float64 = 0.0
    var _t0_bolton_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_bolton_ratio += bolton_ratio(0.5, 0.5)
    var _t1_bolton_ratio = perf_counter_ns()
    var _ns_bolton_ratio = Float64(_t1_bolton_ratio - _t0_bolton_ratio) / Float64(N)
    print("MOJO_TIMING orthodontics::bolton_ratio", _ns_bolton_ratio, _acc_bolton_ratio)
    var _acc_pont_index: Float64 = 0.0
    var _t0_pont_index = perf_counter_ns()
    for _ in range(N):
        _acc_pont_index += pont_index(0.5, 0.5)
    var _t1_pont_index = perf_counter_ns()
    var _ns_pont_index = Float64(_t1_pont_index - _t0_pont_index) / Float64(N)
    print("MOJO_TIMING orthodontics::pont_index", _ns_pont_index, _acc_pont_index)
    var _acc_arch_perimeter_estimate: Float64 = 0.0
    var _t0_arch_perimeter_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_arch_perimeter_estimate += arch_perimeter_estimate(0.5, 0.5)
    var _t1_arch_perimeter_estimate = perf_counter_ns()
    var _ns_arch_perimeter_estimate = Float64(_t1_arch_perimeter_estimate - _t0_arch_perimeter_estimate) / Float64(N)
    print("MOJO_TIMING orthodontics::arch_perimeter_estimate", _ns_arch_perimeter_estimate, _acc_arch_perimeter_estimate)
    var _acc_growth_prediction_cephalometric: Float64 = 0.0
    var _t0_growth_prediction_cephalometric = perf_counter_ns()
    for _ in range(N):
        _acc_growth_prediction_cephalometric += growth_prediction_cephalometric(0.5, 0.5, 0.5)
    var _t1_growth_prediction_cephalometric = perf_counter_ns()
    var _ns_growth_prediction_cephalometric = Float64(_t1_growth_prediction_cephalometric - _t0_growth_prediction_cephalometric) / Float64(N)
    print("MOJO_TIMING orthodontics::growth_prediction_cephalometric", _ns_growth_prediction_cephalometric, _acc_growth_prediction_cephalometric)
    var _acc_retainer_force_decay: Float64 = 0.0
    var _t0_retainer_force_decay = perf_counter_ns()
    for _ in range(N):
        _acc_retainer_force_decay += retainer_force_decay(0.5, 0.5, 0.5)
    var _t1_retainer_force_decay = perf_counter_ns()
    var _ns_retainer_force_decay = Float64(_t1_retainer_force_decay - _t0_retainer_force_decay) / Float64(N)
    print("MOJO_TIMING orthodontics::retainer_force_decay", _ns_retainer_force_decay, _acc_retainer_force_decay)
