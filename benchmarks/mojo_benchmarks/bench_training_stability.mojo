"""bench_training_stability.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from training_stability import loss_scale_adjust, is_finite_check, gradient_accumulation_step, warmup_lr_schedule, cosine_warmup_schedule, ema_weight_update, overflow_skip_step, grad_norm_finite, loss_spike_detector, training_step_budget
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

    var _acc_loss_scale_adjust: Float64 = 0.0
    var _t0_loss_scale_adjust = perf_counter_ns()
    for _ in range(N):
        _acc_loss_scale_adjust += loss_scale_adjust(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_loss_scale_adjust = perf_counter_ns()
    var _ns_loss_scale_adjust = Float64(_t1_loss_scale_adjust - _t0_loss_scale_adjust) / Float64(N)
    print("MOJO_TIMING training_stability::loss_scale_adjust", _ns_loss_scale_adjust, _acc_loss_scale_adjust)
    var _acc_is_finite_check: Float64 = 0.0
    var _t0_is_finite_check = perf_counter_ns()
    for _ in range(N):
        _acc_is_finite_check += is_finite_check(0.5)
    var _t1_is_finite_check = perf_counter_ns()
    var _ns_is_finite_check = Float64(_t1_is_finite_check - _t0_is_finite_check) / Float64(N)
    print("MOJO_TIMING training_stability::is_finite_check", _ns_is_finite_check, _acc_is_finite_check)
    var _acc_gradient_accumulation_step: Float64 = 0.0
    var _t0_gradient_accumulation_step = perf_counter_ns()
    for _ in range(N):
        _acc_gradient_accumulation_step += gradient_accumulation_step(0.5, 0.5, 0.5)
    var _t1_gradient_accumulation_step = perf_counter_ns()
    var _ns_gradient_accumulation_step = Float64(_t1_gradient_accumulation_step - _t0_gradient_accumulation_step) / Float64(N)
    print("MOJO_TIMING training_stability::gradient_accumulation_step", _ns_gradient_accumulation_step, _acc_gradient_accumulation_step)
    var _acc_warmup_lr_schedule: Float64 = 0.0
    var _t0_warmup_lr_schedule = perf_counter_ns()
    for _ in range(N):
        _acc_warmup_lr_schedule += warmup_lr_schedule(0.5, 0.5, 0.5)
    var _t1_warmup_lr_schedule = perf_counter_ns()
    var _ns_warmup_lr_schedule = Float64(_t1_warmup_lr_schedule - _t0_warmup_lr_schedule) / Float64(N)
    print("MOJO_TIMING training_stability::warmup_lr_schedule", _ns_warmup_lr_schedule, _acc_warmup_lr_schedule)
    var _acc_cosine_warmup_schedule: Float64 = 0.0
    var _t0_cosine_warmup_schedule = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_warmup_schedule += cosine_warmup_schedule(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_cosine_warmup_schedule = perf_counter_ns()
    var _ns_cosine_warmup_schedule = Float64(_t1_cosine_warmup_schedule - _t0_cosine_warmup_schedule) / Float64(N)
    print("MOJO_TIMING training_stability::cosine_warmup_schedule", _ns_cosine_warmup_schedule, _acc_cosine_warmup_schedule)
    var _acc_ema_weight_update: Float64 = 0.0
    var _t0_ema_weight_update = perf_counter_ns()
    for _ in range(N):
        _acc_ema_weight_update += ema_weight_update(0.5, 0.5, 0.5)
    var _t1_ema_weight_update = perf_counter_ns()
    var _ns_ema_weight_update = Float64(_t1_ema_weight_update - _t0_ema_weight_update) / Float64(N)
    print("MOJO_TIMING training_stability::ema_weight_update", _ns_ema_weight_update, _acc_ema_weight_update)
    var _acc_overflow_skip_step: Float64 = 0.0
    var _t0_overflow_skip_step = perf_counter_ns()
    for _ in range(N):
        _acc_overflow_skip_step += overflow_skip_step(0.5, 0.5)
    var _t1_overflow_skip_step = perf_counter_ns()
    var _ns_overflow_skip_step = Float64(_t1_overflow_skip_step - _t0_overflow_skip_step) / Float64(N)
    print("MOJO_TIMING training_stability::overflow_skip_step", _ns_overflow_skip_step, _acc_overflow_skip_step)
    var _acc_grad_norm_finite: Float64 = 0.0
    var _t0_grad_norm_finite = perf_counter_ns()
    for _ in range(N):
        _acc_grad_norm_finite += grad_norm_finite(0.5, 0.5)
    var _t1_grad_norm_finite = perf_counter_ns()
    var _ns_grad_norm_finite = Float64(_t1_grad_norm_finite - _t0_grad_norm_finite) / Float64(N)
    print("MOJO_TIMING training_stability::grad_norm_finite", _ns_grad_norm_finite, _acc_grad_norm_finite)
    var _acc_loss_spike_detector: Float64 = 0.0
    var _t0_loss_spike_detector = perf_counter_ns()
    for _ in range(N):
        _acc_loss_spike_detector += loss_spike_detector(0.5, 0.5, 0.5)
    var _t1_loss_spike_detector = perf_counter_ns()
    var _ns_loss_spike_detector = Float64(_t1_loss_spike_detector - _t0_loss_spike_detector) / Float64(N)
    print("MOJO_TIMING training_stability::loss_spike_detector", _ns_loss_spike_detector, _acc_loss_spike_detector)
    var _acc_training_step_budget: Float64 = 0.0
    var _t0_training_step_budget = perf_counter_ns()
    for _ in range(N):
        _acc_training_step_budget += training_step_budget(0.5, 0.5)
    var _t1_training_step_budget = perf_counter_ns()
    var _ns_training_step_budget = Float64(_t1_training_step_budget - _t0_training_step_budget) / Float64(N)
    print("MOJO_TIMING training_stability::training_step_budget", _ns_training_step_budget, _acc_training_step_budget)
