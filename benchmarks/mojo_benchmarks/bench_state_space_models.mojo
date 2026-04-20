"""bench_state_space_models.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from state_space_models import ssm_discretize_zoh, ssm_discretize_b, ssm_recurrence_step, ssm_output_step, mamba_selective_scan_step, mamba_delta_softplus, hippo_legt_update, s4_kernel_element, ssm_shift_register_step, retnet_decay
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

    var _acc_ssm_discretize_zoh: Float64 = 0.0
    var _t0_ssm_discretize_zoh = perf_counter_ns()
    for _ in range(N):
        _acc_ssm_discretize_zoh += ssm_discretize_zoh(0.5, 0.5)
    var _t1_ssm_discretize_zoh = perf_counter_ns()
    var _ns_ssm_discretize_zoh = Float64(_t1_ssm_discretize_zoh - _t0_ssm_discretize_zoh) / Float64(N)
    print("MOJO_TIMING state_space_models::ssm_discretize_zoh", _ns_ssm_discretize_zoh, _acc_ssm_discretize_zoh)
    var _acc_ssm_discretize_b: Float64 = 0.0
    var _t0_ssm_discretize_b = perf_counter_ns()
    for _ in range(N):
        _acc_ssm_discretize_b += ssm_discretize_b(0.5, 0.5, 0.5)
    var _t1_ssm_discretize_b = perf_counter_ns()
    var _ns_ssm_discretize_b = Float64(_t1_ssm_discretize_b - _t0_ssm_discretize_b) / Float64(N)
    print("MOJO_TIMING state_space_models::ssm_discretize_b", _ns_ssm_discretize_b, _acc_ssm_discretize_b)
    var _acc_ssm_recurrence_step: Float64 = 0.0
    var _t0_ssm_recurrence_step = perf_counter_ns()
    for _ in range(N):
        _acc_ssm_recurrence_step += ssm_recurrence_step(0.5, 0.5, 0.5, 0.5)
    var _t1_ssm_recurrence_step = perf_counter_ns()
    var _ns_ssm_recurrence_step = Float64(_t1_ssm_recurrence_step - _t0_ssm_recurrence_step) / Float64(N)
    print("MOJO_TIMING state_space_models::ssm_recurrence_step", _ns_ssm_recurrence_step, _acc_ssm_recurrence_step)
    var _acc_ssm_output_step: Float64 = 0.0
    var _t0_ssm_output_step = perf_counter_ns()
    for _ in range(N):
        _acc_ssm_output_step += ssm_output_step(0.5, 0.5)
    var _t1_ssm_output_step = perf_counter_ns()
    var _ns_ssm_output_step = Float64(_t1_ssm_output_step - _t0_ssm_output_step) / Float64(N)
    print("MOJO_TIMING state_space_models::ssm_output_step", _ns_ssm_output_step, _acc_ssm_output_step)
    var _acc_mamba_selective_scan_step: Float64 = 0.0
    var _t0_mamba_selective_scan_step = perf_counter_ns()
    for _ in range(N):
        _acc_mamba_selective_scan_step += mamba_selective_scan_step(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_mamba_selective_scan_step = perf_counter_ns()
    var _ns_mamba_selective_scan_step = Float64(_t1_mamba_selective_scan_step - _t0_mamba_selective_scan_step) / Float64(N)
    print("MOJO_TIMING state_space_models::mamba_selective_scan_step", _ns_mamba_selective_scan_step, _acc_mamba_selective_scan_step)
    var _acc_mamba_delta_softplus: Float64 = 0.0
    var _t0_mamba_delta_softplus = perf_counter_ns()
    for _ in range(N):
        _acc_mamba_delta_softplus += mamba_delta_softplus(0.5)
    var _t1_mamba_delta_softplus = perf_counter_ns()
    var _ns_mamba_delta_softplus = Float64(_t1_mamba_delta_softplus - _t0_mamba_delta_softplus) / Float64(N)
    print("MOJO_TIMING state_space_models::mamba_delta_softplus", _ns_mamba_delta_softplus, _acc_mamba_delta_softplus)
    var _acc_hippo_legt_update: Float64 = 0.0
    var _t0_hippo_legt_update = perf_counter_ns()
    for _ in range(N):
        _acc_hippo_legt_update += hippo_legt_update(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_hippo_legt_update = perf_counter_ns()
    var _ns_hippo_legt_update = Float64(_t1_hippo_legt_update - _t0_hippo_legt_update) / Float64(N)
    print("MOJO_TIMING state_space_models::hippo_legt_update", _ns_hippo_legt_update, _acc_hippo_legt_update)
    var _acc_s4_kernel_element: Float64 = 0.0
    var _t0_s4_kernel_element = perf_counter_ns()
    for _ in range(N):
        _acc_s4_kernel_element += s4_kernel_element(0.5, 0.5, 0.5)
    var _t1_s4_kernel_element = perf_counter_ns()
    var _ns_s4_kernel_element = Float64(_t1_s4_kernel_element - _t0_s4_kernel_element) / Float64(N)
    print("MOJO_TIMING state_space_models::s4_kernel_element", _ns_s4_kernel_element, _acc_s4_kernel_element)
    var _acc_ssm_shift_register_step: Float64 = 0.0
    var _t0_ssm_shift_register_step = perf_counter_ns()
    for _ in range(N):
        _acc_ssm_shift_register_step += ssm_shift_register_step(0.5, 0.5, 0.5)
    var _t1_ssm_shift_register_step = perf_counter_ns()
    var _ns_ssm_shift_register_step = Float64(_t1_ssm_shift_register_step - _t0_ssm_shift_register_step) / Float64(N)
    print("MOJO_TIMING state_space_models::ssm_shift_register_step", _ns_ssm_shift_register_step, _acc_ssm_shift_register_step)
    var _acc_retnet_decay: Float64 = 0.0
    var _t0_retnet_decay = perf_counter_ns()
    for _ in range(N):
        _acc_retnet_decay += retnet_decay(0.5, 0.5)
    var _t1_retnet_decay = perf_counter_ns()
    var _ns_retnet_decay = Float64(_t1_retnet_decay - _t0_retnet_decay) / Float64(N)
    print("MOJO_TIMING state_space_models::retnet_decay", _ns_retnet_decay, _acc_retnet_decay)
