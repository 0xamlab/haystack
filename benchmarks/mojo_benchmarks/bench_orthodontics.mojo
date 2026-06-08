"""bench_orthodontics.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from orthodontics import tooth_movement_rate, moment_to_force_ratio, anchorage_loss_estimate, arch_wire_force, levelling_torque, bolton_ratio, pont_index, arch_perimeter_estimate, growth_prediction_cephalometric, retainer_force_decay
from std.time import perf_counter_ns
fn _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

fn _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

fn _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

fn _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

fn _summary_int(value: Int) -> String:
    return "int:" + String(value)

fn _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

fn _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

fn _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

fn _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

fn _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

fn _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

fn _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

fn _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_tooth_movement_rate: Float64 = 0.0
    var _t0_tooth_movement_rate = perf_counter_ns()
    for _ in range(N):
        _acc_tooth_movement_rate += tooth_movement_rate(0.5, 0.5)
    var _t1_tooth_movement_rate = perf_counter_ns()
    var _ns_tooth_movement_rate = Float64(_t1_tooth_movement_rate - _t0_tooth_movement_rate) / Float64(N)
    print("MOJO_TIMING orthodontics::tooth_movement_rate", _ns_tooth_movement_rate, _acc_tooth_movement_rate)
    var _result_tooth_movement_rate = tooth_movement_rate(0.5, 0.5)
    var _summary_tooth_movement_rate = _summary_float64(_result_tooth_movement_rate)
    print("MOJO_RESULT orthodontics::tooth_movement_rate", _summary_tooth_movement_rate)
    var _acc_moment_to_force_ratio: Float64 = 0.0
    var _t0_moment_to_force_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_moment_to_force_ratio += moment_to_force_ratio(0.5, 0.5)
    var _t1_moment_to_force_ratio = perf_counter_ns()
    var _ns_moment_to_force_ratio = Float64(_t1_moment_to_force_ratio - _t0_moment_to_force_ratio) / Float64(N)
    print("MOJO_TIMING orthodontics::moment_to_force_ratio", _ns_moment_to_force_ratio, _acc_moment_to_force_ratio)
    var _result_moment_to_force_ratio = moment_to_force_ratio(0.5, 0.5)
    var _summary_moment_to_force_ratio = _summary_float64(_result_moment_to_force_ratio)
    print("MOJO_RESULT orthodontics::moment_to_force_ratio", _summary_moment_to_force_ratio)
    var _acc_anchorage_loss_estimate: Float64 = 0.0
    var _t0_anchorage_loss_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_anchorage_loss_estimate += anchorage_loss_estimate(0.5, 0.5)
    var _t1_anchorage_loss_estimate = perf_counter_ns()
    var _ns_anchorage_loss_estimate = Float64(_t1_anchorage_loss_estimate - _t0_anchorage_loss_estimate) / Float64(N)
    print("MOJO_TIMING orthodontics::anchorage_loss_estimate", _ns_anchorage_loss_estimate, _acc_anchorage_loss_estimate)
    var _result_anchorage_loss_estimate = anchorage_loss_estimate(0.5, 0.5)
    var _summary_anchorage_loss_estimate = _summary_float64(_result_anchorage_loss_estimate)
    print("MOJO_RESULT orthodontics::anchorage_loss_estimate", _summary_anchorage_loss_estimate)
    var _acc_arch_wire_force: Float64 = 0.0
    var _t0_arch_wire_force = perf_counter_ns()
    for _ in range(N):
        _acc_arch_wire_force += arch_wire_force(0.5, 0.5, 0.5, 0.5)
    var _t1_arch_wire_force = perf_counter_ns()
    var _ns_arch_wire_force = Float64(_t1_arch_wire_force - _t0_arch_wire_force) / Float64(N)
    print("MOJO_TIMING orthodontics::arch_wire_force", _ns_arch_wire_force, _acc_arch_wire_force)
    var _result_arch_wire_force = arch_wire_force(0.5, 0.5, 0.5, 0.5)
    var _summary_arch_wire_force = _summary_float64(_result_arch_wire_force)
    print("MOJO_RESULT orthodontics::arch_wire_force", _summary_arch_wire_force)
    var _acc_levelling_torque: Float64 = 0.0
    var _t0_levelling_torque = perf_counter_ns()
    for _ in range(N):
        _acc_levelling_torque += levelling_torque(0.5, 0.5, 0.5, 0.5)
    var _t1_levelling_torque = perf_counter_ns()
    var _ns_levelling_torque = Float64(_t1_levelling_torque - _t0_levelling_torque) / Float64(N)
    print("MOJO_TIMING orthodontics::levelling_torque", _ns_levelling_torque, _acc_levelling_torque)
    var _result_levelling_torque = levelling_torque(0.5, 0.5, 0.5, 0.5)
    var _summary_levelling_torque = _summary_float64(_result_levelling_torque)
    print("MOJO_RESULT orthodontics::levelling_torque", _summary_levelling_torque)
    var _acc_bolton_ratio: Float64 = 0.0
    var _t0_bolton_ratio = perf_counter_ns()
    for _ in range(N):
        _acc_bolton_ratio += bolton_ratio(0.5, 0.5)
    var _t1_bolton_ratio = perf_counter_ns()
    var _ns_bolton_ratio = Float64(_t1_bolton_ratio - _t0_bolton_ratio) / Float64(N)
    print("MOJO_TIMING orthodontics::bolton_ratio", _ns_bolton_ratio, _acc_bolton_ratio)
    var _result_bolton_ratio = bolton_ratio(0.5, 0.5)
    var _summary_bolton_ratio = _summary_float64(_result_bolton_ratio)
    print("MOJO_RESULT orthodontics::bolton_ratio", _summary_bolton_ratio)
    var _acc_pont_index: Float64 = 0.0
    var _t0_pont_index = perf_counter_ns()
    for _ in range(N):
        _acc_pont_index += pont_index(0.5, 0.5)
    var _t1_pont_index = perf_counter_ns()
    var _ns_pont_index = Float64(_t1_pont_index - _t0_pont_index) / Float64(N)
    print("MOJO_TIMING orthodontics::pont_index", _ns_pont_index, _acc_pont_index)
    var _result_pont_index = pont_index(0.5, 0.5)
    var _summary_pont_index = _summary_float64(_result_pont_index)
    print("MOJO_RESULT orthodontics::pont_index", _summary_pont_index)
    var _acc_arch_perimeter_estimate: Float64 = 0.0
    var _t0_arch_perimeter_estimate = perf_counter_ns()
    for _ in range(N):
        _acc_arch_perimeter_estimate += arch_perimeter_estimate(0.5, 0.5)
    var _t1_arch_perimeter_estimate = perf_counter_ns()
    var _ns_arch_perimeter_estimate = Float64(_t1_arch_perimeter_estimate - _t0_arch_perimeter_estimate) / Float64(N)
    print("MOJO_TIMING orthodontics::arch_perimeter_estimate", _ns_arch_perimeter_estimate, _acc_arch_perimeter_estimate)
    var _result_arch_perimeter_estimate = arch_perimeter_estimate(0.5, 0.5)
    var _summary_arch_perimeter_estimate = _summary_float64(_result_arch_perimeter_estimate)
    print("MOJO_RESULT orthodontics::arch_perimeter_estimate", _summary_arch_perimeter_estimate)
    var _acc_growth_prediction_cephalometric: Float64 = 0.0
    var _t0_growth_prediction_cephalometric = perf_counter_ns()
    for _ in range(N):
        _acc_growth_prediction_cephalometric += growth_prediction_cephalometric(0.5, 0.5, 0.5)
    var _t1_growth_prediction_cephalometric = perf_counter_ns()
    var _ns_growth_prediction_cephalometric = Float64(_t1_growth_prediction_cephalometric - _t0_growth_prediction_cephalometric) / Float64(N)
    print("MOJO_TIMING orthodontics::growth_prediction_cephalometric", _ns_growth_prediction_cephalometric, _acc_growth_prediction_cephalometric)
    var _result_growth_prediction_cephalometric = growth_prediction_cephalometric(0.5, 0.5, 0.5)
    var _summary_growth_prediction_cephalometric = _summary_float64(_result_growth_prediction_cephalometric)
    print("MOJO_RESULT orthodontics::growth_prediction_cephalometric", _summary_growth_prediction_cephalometric)
    var _acc_retainer_force_decay: Float64 = 0.0
    var _t0_retainer_force_decay = perf_counter_ns()
    for _ in range(N):
        _acc_retainer_force_decay += retainer_force_decay(0.5, 0.5, 0.5)
    var _t1_retainer_force_decay = perf_counter_ns()
    var _ns_retainer_force_decay = Float64(_t1_retainer_force_decay - _t0_retainer_force_decay) / Float64(N)
    print("MOJO_TIMING orthodontics::retainer_force_decay", _ns_retainer_force_decay, _acc_retainer_force_decay)
    var _result_retainer_force_decay = retainer_force_decay(0.5, 0.5, 0.5)
    var _summary_retainer_force_decay = _summary_float64(_result_retainer_force_decay)
    print("MOJO_RESULT orthodontics::retainer_force_decay", _summary_retainer_force_decay)
