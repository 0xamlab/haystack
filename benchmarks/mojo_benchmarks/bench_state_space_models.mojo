"""bench_state_space_models.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from state_space_models import ssm_discretize_zoh, ssm_discretize_b, ssm_recurrence_step, ssm_output_step, mamba_selective_scan_step, mamba_delta_softplus, hippo_legt_update, s4_kernel_element, ssm_shift_register_step, retnet_decay
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

    var _acc_ssm_discretize_zoh: Float64 = 0.0
    var _t0_ssm_discretize_zoh = perf_counter_ns()
    for _ in range(N):
        _acc_ssm_discretize_zoh += ssm_discretize_zoh(0.5, 0.5)
    var _t1_ssm_discretize_zoh = perf_counter_ns()
    var _ns_ssm_discretize_zoh = Float64(_t1_ssm_discretize_zoh - _t0_ssm_discretize_zoh) / Float64(N)
    print("MOJO_TIMING state_space_models::ssm_discretize_zoh", _ns_ssm_discretize_zoh, _acc_ssm_discretize_zoh)
    var _result_ssm_discretize_zoh = ssm_discretize_zoh(0.5, 0.5)
    var _summary_ssm_discretize_zoh = _summary_float64(_result_ssm_discretize_zoh)
    print("MOJO_RESULT state_space_models::ssm_discretize_zoh", _summary_ssm_discretize_zoh)
    var _acc_ssm_discretize_b: Float64 = 0.0
    var _t0_ssm_discretize_b = perf_counter_ns()
    for _ in range(N):
        _acc_ssm_discretize_b += ssm_discretize_b(0.5, 0.5, 0.5)
    var _t1_ssm_discretize_b = perf_counter_ns()
    var _ns_ssm_discretize_b = Float64(_t1_ssm_discretize_b - _t0_ssm_discretize_b) / Float64(N)
    print("MOJO_TIMING state_space_models::ssm_discretize_b", _ns_ssm_discretize_b, _acc_ssm_discretize_b)
    var _result_ssm_discretize_b = ssm_discretize_b(0.5, 0.5, 0.5)
    var _summary_ssm_discretize_b = _summary_float64(_result_ssm_discretize_b)
    print("MOJO_RESULT state_space_models::ssm_discretize_b", _summary_ssm_discretize_b)
    var _acc_ssm_recurrence_step: Float64 = 0.0
    var _t0_ssm_recurrence_step = perf_counter_ns()
    for _ in range(N):
        _acc_ssm_recurrence_step += ssm_recurrence_step(0.5, 0.5, 0.5, 0.5)
    var _t1_ssm_recurrence_step = perf_counter_ns()
    var _ns_ssm_recurrence_step = Float64(_t1_ssm_recurrence_step - _t0_ssm_recurrence_step) / Float64(N)
    print("MOJO_TIMING state_space_models::ssm_recurrence_step", _ns_ssm_recurrence_step, _acc_ssm_recurrence_step)
    var _result_ssm_recurrence_step = ssm_recurrence_step(0.5, 0.5, 0.5, 0.5)
    var _summary_ssm_recurrence_step = _summary_float64(_result_ssm_recurrence_step)
    print("MOJO_RESULT state_space_models::ssm_recurrence_step", _summary_ssm_recurrence_step)
    var _acc_ssm_output_step: Float64 = 0.0
    var _t0_ssm_output_step = perf_counter_ns()
    for _ in range(N):
        _acc_ssm_output_step += ssm_output_step(0.5, 0.5)
    var _t1_ssm_output_step = perf_counter_ns()
    var _ns_ssm_output_step = Float64(_t1_ssm_output_step - _t0_ssm_output_step) / Float64(N)
    print("MOJO_TIMING state_space_models::ssm_output_step", _ns_ssm_output_step, _acc_ssm_output_step)
    var _result_ssm_output_step = ssm_output_step(0.5, 0.5)
    var _summary_ssm_output_step = _summary_float64(_result_ssm_output_step)
    print("MOJO_RESULT state_space_models::ssm_output_step", _summary_ssm_output_step)
    var _acc_mamba_selective_scan_step: Float64 = 0.0
    var _t0_mamba_selective_scan_step = perf_counter_ns()
    for _ in range(N):
        _acc_mamba_selective_scan_step += mamba_selective_scan_step(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_mamba_selective_scan_step = perf_counter_ns()
    var _ns_mamba_selective_scan_step = Float64(_t1_mamba_selective_scan_step - _t0_mamba_selective_scan_step) / Float64(N)
    print("MOJO_TIMING state_space_models::mamba_selective_scan_step", _ns_mamba_selective_scan_step, _acc_mamba_selective_scan_step)
    var _result_mamba_selective_scan_step = mamba_selective_scan_step(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_mamba_selective_scan_step = _summary_float64(_result_mamba_selective_scan_step)
    print("MOJO_RESULT state_space_models::mamba_selective_scan_step", _summary_mamba_selective_scan_step)
    var _acc_mamba_delta_softplus: Float64 = 0.0
    var _t0_mamba_delta_softplus = perf_counter_ns()
    for _ in range(N):
        _acc_mamba_delta_softplus += mamba_delta_softplus(0.5)
    var _t1_mamba_delta_softplus = perf_counter_ns()
    var _ns_mamba_delta_softplus = Float64(_t1_mamba_delta_softplus - _t0_mamba_delta_softplus) / Float64(N)
    print("MOJO_TIMING state_space_models::mamba_delta_softplus", _ns_mamba_delta_softplus, _acc_mamba_delta_softplus)
    var _result_mamba_delta_softplus = mamba_delta_softplus(0.5)
    var _summary_mamba_delta_softplus = _summary_float64(_result_mamba_delta_softplus)
    print("MOJO_RESULT state_space_models::mamba_delta_softplus", _summary_mamba_delta_softplus)
    var _acc_hippo_legt_update: Float64 = 0.0
    var _t0_hippo_legt_update = perf_counter_ns()
    for _ in range(N):
        _acc_hippo_legt_update += hippo_legt_update(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_hippo_legt_update = perf_counter_ns()
    var _ns_hippo_legt_update = Float64(_t1_hippo_legt_update - _t0_hippo_legt_update) / Float64(N)
    print("MOJO_TIMING state_space_models::hippo_legt_update", _ns_hippo_legt_update, _acc_hippo_legt_update)
    var _result_hippo_legt_update = hippo_legt_update(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_hippo_legt_update = _summary_float64(_result_hippo_legt_update)
    print("MOJO_RESULT state_space_models::hippo_legt_update", _summary_hippo_legt_update)
    var _acc_s4_kernel_element: Float64 = 0.0
    var _t0_s4_kernel_element = perf_counter_ns()
    for _ in range(N):
        _acc_s4_kernel_element += s4_kernel_element(0.5, 0.5, 0.5)
    var _t1_s4_kernel_element = perf_counter_ns()
    var _ns_s4_kernel_element = Float64(_t1_s4_kernel_element - _t0_s4_kernel_element) / Float64(N)
    print("MOJO_TIMING state_space_models::s4_kernel_element", _ns_s4_kernel_element, _acc_s4_kernel_element)
    var _result_s4_kernel_element = s4_kernel_element(0.5, 0.5, 0.5)
    var _summary_s4_kernel_element = _summary_float64(_result_s4_kernel_element)
    print("MOJO_RESULT state_space_models::s4_kernel_element", _summary_s4_kernel_element)
    var _acc_ssm_shift_register_step: Float64 = 0.0
    var _t0_ssm_shift_register_step = perf_counter_ns()
    for _ in range(N):
        _acc_ssm_shift_register_step += ssm_shift_register_step(0.5, 0.5, 0.5)
    var _t1_ssm_shift_register_step = perf_counter_ns()
    var _ns_ssm_shift_register_step = Float64(_t1_ssm_shift_register_step - _t0_ssm_shift_register_step) / Float64(N)
    print("MOJO_TIMING state_space_models::ssm_shift_register_step", _ns_ssm_shift_register_step, _acc_ssm_shift_register_step)
    var _result_ssm_shift_register_step = ssm_shift_register_step(0.5, 0.5, 0.5)
    var _summary_ssm_shift_register_step = _summary_float64(_result_ssm_shift_register_step)
    print("MOJO_RESULT state_space_models::ssm_shift_register_step", _summary_ssm_shift_register_step)
    var _acc_retnet_decay: Float64 = 0.0
    var _t0_retnet_decay = perf_counter_ns()
    for _ in range(N):
        _acc_retnet_decay += retnet_decay(0.5, 0.5)
    var _t1_retnet_decay = perf_counter_ns()
    var _ns_retnet_decay = Float64(_t1_retnet_decay - _t0_retnet_decay) / Float64(N)
    print("MOJO_TIMING state_space_models::retnet_decay", _ns_retnet_decay, _acc_retnet_decay)
    var _result_retnet_decay = retnet_decay(0.5, 0.5)
    var _summary_retnet_decay = _summary_float64(_result_retnet_decay)
    print("MOJO_RESULT state_space_models::retnet_decay", _summary_retnet_decay)
