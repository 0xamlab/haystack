"""bench_training_stability.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from training_stability import loss_scale_adjust, is_finite_check, gradient_accumulation_step, warmup_lr_schedule, cosine_warmup_schedule, ema_weight_update, overflow_skip_step, grad_norm_finite, loss_spike_detector, training_step_budget
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

    var _acc_loss_scale_adjust: Float64 = 0.0
    var _t0_loss_scale_adjust = perf_counter_ns()
    for _ in range(N):
        _acc_loss_scale_adjust += loss_scale_adjust(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_loss_scale_adjust = perf_counter_ns()
    var _ns_loss_scale_adjust = Float64(_t1_loss_scale_adjust - _t0_loss_scale_adjust) / Float64(N)
    print("MOJO_TIMING training_stability::loss_scale_adjust", _ns_loss_scale_adjust, _acc_loss_scale_adjust)
    var _result_loss_scale_adjust = loss_scale_adjust(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_loss_scale_adjust = _summary_float64(_result_loss_scale_adjust)
    print("MOJO_RESULT training_stability::loss_scale_adjust", _summary_loss_scale_adjust)
    var _acc_is_finite_check: Float64 = 0.0
    var _t0_is_finite_check = perf_counter_ns()
    for _ in range(N):
        _acc_is_finite_check += is_finite_check(0.5)
    var _t1_is_finite_check = perf_counter_ns()
    var _ns_is_finite_check = Float64(_t1_is_finite_check - _t0_is_finite_check) / Float64(N)
    print("MOJO_TIMING training_stability::is_finite_check", _ns_is_finite_check, _acc_is_finite_check)
    var _result_is_finite_check = is_finite_check(0.5)
    var _summary_is_finite_check = _summary_float64(_result_is_finite_check)
    print("MOJO_RESULT training_stability::is_finite_check", _summary_is_finite_check)
    var _acc_gradient_accumulation_step: Float64 = 0.0
    var _t0_gradient_accumulation_step = perf_counter_ns()
    for _ in range(N):
        _acc_gradient_accumulation_step += gradient_accumulation_step(0.5, 0.5, 0.5)
    var _t1_gradient_accumulation_step = perf_counter_ns()
    var _ns_gradient_accumulation_step = Float64(_t1_gradient_accumulation_step - _t0_gradient_accumulation_step) / Float64(N)
    print("MOJO_TIMING training_stability::gradient_accumulation_step", _ns_gradient_accumulation_step, _acc_gradient_accumulation_step)
    var _result_gradient_accumulation_step = gradient_accumulation_step(0.5, 0.5, 0.5)
    var _summary_gradient_accumulation_step = _summary_float64(_result_gradient_accumulation_step)
    print("MOJO_RESULT training_stability::gradient_accumulation_step", _summary_gradient_accumulation_step)
    var _acc_warmup_lr_schedule: Float64 = 0.0
    var _t0_warmup_lr_schedule = perf_counter_ns()
    for _ in range(N):
        _acc_warmup_lr_schedule += warmup_lr_schedule(0.5, 0.5, 0.5)
    var _t1_warmup_lr_schedule = perf_counter_ns()
    var _ns_warmup_lr_schedule = Float64(_t1_warmup_lr_schedule - _t0_warmup_lr_schedule) / Float64(N)
    print("MOJO_TIMING training_stability::warmup_lr_schedule", _ns_warmup_lr_schedule, _acc_warmup_lr_schedule)
    var _result_warmup_lr_schedule = warmup_lr_schedule(0.5, 0.5, 0.5)
    var _summary_warmup_lr_schedule = _summary_float64(_result_warmup_lr_schedule)
    print("MOJO_RESULT training_stability::warmup_lr_schedule", _summary_warmup_lr_schedule)
    var _acc_cosine_warmup_schedule: Float64 = 0.0
    var _t0_cosine_warmup_schedule = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_warmup_schedule += cosine_warmup_schedule(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_cosine_warmup_schedule = perf_counter_ns()
    var _ns_cosine_warmup_schedule = Float64(_t1_cosine_warmup_schedule - _t0_cosine_warmup_schedule) / Float64(N)
    print("MOJO_TIMING training_stability::cosine_warmup_schedule", _ns_cosine_warmup_schedule, _acc_cosine_warmup_schedule)
    var _result_cosine_warmup_schedule = cosine_warmup_schedule(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_cosine_warmup_schedule = _summary_float64(_result_cosine_warmup_schedule)
    print("MOJO_RESULT training_stability::cosine_warmup_schedule", _summary_cosine_warmup_schedule)
    var _acc_ema_weight_update: Float64 = 0.0
    var _t0_ema_weight_update = perf_counter_ns()
    for _ in range(N):
        _acc_ema_weight_update += ema_weight_update(0.5, 0.5, 0.5)
    var _t1_ema_weight_update = perf_counter_ns()
    var _ns_ema_weight_update = Float64(_t1_ema_weight_update - _t0_ema_weight_update) / Float64(N)
    print("MOJO_TIMING training_stability::ema_weight_update", _ns_ema_weight_update, _acc_ema_weight_update)
    var _result_ema_weight_update = ema_weight_update(0.5, 0.5, 0.5)
    var _summary_ema_weight_update = _summary_float64(_result_ema_weight_update)
    print("MOJO_RESULT training_stability::ema_weight_update", _summary_ema_weight_update)
    var _acc_overflow_skip_step: Float64 = 0.0
    var _t0_overflow_skip_step = perf_counter_ns()
    for _ in range(N):
        _acc_overflow_skip_step += overflow_skip_step(0.5, 0.5)
    var _t1_overflow_skip_step = perf_counter_ns()
    var _ns_overflow_skip_step = Float64(_t1_overflow_skip_step - _t0_overflow_skip_step) / Float64(N)
    print("MOJO_TIMING training_stability::overflow_skip_step", _ns_overflow_skip_step, _acc_overflow_skip_step)
    var _result_overflow_skip_step = overflow_skip_step(0.5, 0.5)
    var _summary_overflow_skip_step = _summary_float64(_result_overflow_skip_step)
    print("MOJO_RESULT training_stability::overflow_skip_step", _summary_overflow_skip_step)
    var _acc_grad_norm_finite: Float64 = 0.0
    var _t0_grad_norm_finite = perf_counter_ns()
    for _ in range(N):
        _acc_grad_norm_finite += grad_norm_finite(0.5, 0.5)
    var _t1_grad_norm_finite = perf_counter_ns()
    var _ns_grad_norm_finite = Float64(_t1_grad_norm_finite - _t0_grad_norm_finite) / Float64(N)
    print("MOJO_TIMING training_stability::grad_norm_finite", _ns_grad_norm_finite, _acc_grad_norm_finite)
    var _result_grad_norm_finite = grad_norm_finite(0.5, 0.5)
    var _summary_grad_norm_finite = _summary_float64(_result_grad_norm_finite)
    print("MOJO_RESULT training_stability::grad_norm_finite", _summary_grad_norm_finite)
    var _acc_loss_spike_detector: Float64 = 0.0
    var _t0_loss_spike_detector = perf_counter_ns()
    for _ in range(N):
        _acc_loss_spike_detector += loss_spike_detector(0.5, 0.5, 0.5)
    var _t1_loss_spike_detector = perf_counter_ns()
    var _ns_loss_spike_detector = Float64(_t1_loss_spike_detector - _t0_loss_spike_detector) / Float64(N)
    print("MOJO_TIMING training_stability::loss_spike_detector", _ns_loss_spike_detector, _acc_loss_spike_detector)
    var _result_loss_spike_detector = loss_spike_detector(0.5, 0.5, 0.5)
    var _summary_loss_spike_detector = _summary_float64(_result_loss_spike_detector)
    print("MOJO_RESULT training_stability::loss_spike_detector", _summary_loss_spike_detector)
    var _acc_training_step_budget: Float64 = 0.0
    var _t0_training_step_budget = perf_counter_ns()
    for _ in range(N):
        _acc_training_step_budget += training_step_budget(0.5, 0.5)
    var _t1_training_step_budget = perf_counter_ns()
    var _ns_training_step_budget = Float64(_t1_training_step_budget - _t0_training_step_budget) / Float64(N)
    print("MOJO_TIMING training_stability::training_step_budget", _ns_training_step_budget, _acc_training_step_budget)
    var _result_training_step_budget = training_step_budget(0.5, 0.5)
    var _summary_training_step_budget = _summary_float64(_result_training_step_budget)
    print("MOJO_RESULT training_stability::training_step_budget", _summary_training_step_budget)
