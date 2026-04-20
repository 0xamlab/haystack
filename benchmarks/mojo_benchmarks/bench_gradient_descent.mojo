"""bench_gradient_descent.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from gradient_descent import sgd_update, sgd_momentum_update, adam_update, adamw_update, rmsprop_update, adagrad_update, lars_update, lion_update, gradient_clipping, lr_cosine_schedule
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

    var _acc_sgd_update: Float64 = 0.0
    var _t0_sgd_update = perf_counter_ns()
    for _ in range(N):
        _acc_sgd_update += sgd_update(0.5, 0.5, 0.5)
    var _t1_sgd_update = perf_counter_ns()
    var _ns_sgd_update = Float64(_t1_sgd_update - _t0_sgd_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::sgd_update", _ns_sgd_update, _acc_sgd_update)
    var _acc_sgd_momentum_update: Float64 = 0.0
    var _t0_sgd_momentum_update = perf_counter_ns()
    for _ in range(N):
        _acc_sgd_momentum_update += sgd_momentum_update(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_sgd_momentum_update = perf_counter_ns()
    var _ns_sgd_momentum_update = Float64(_t1_sgd_momentum_update - _t0_sgd_momentum_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::sgd_momentum_update", _ns_sgd_momentum_update, _acc_sgd_momentum_update)
    var _acc_adam_update: Float64 = 0.0
    var _t0_adam_update = perf_counter_ns()
    for _ in range(N):
        _acc_adam_update += adam_update(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_adam_update = perf_counter_ns()
    var _ns_adam_update = Float64(_t1_adam_update - _t0_adam_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::adam_update", _ns_adam_update, _acc_adam_update)
    var _acc_adamw_update: Float64 = 0.0
    var _t0_adamw_update = perf_counter_ns()
    for _ in range(N):
        _acc_adamw_update += adamw_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_adamw_update = perf_counter_ns()
    var _ns_adamw_update = Float64(_t1_adamw_update - _t0_adamw_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::adamw_update", _ns_adamw_update, _acc_adamw_update)
    var _acc_rmsprop_update: Float64 = 0.0
    var _t0_rmsprop_update = perf_counter_ns()
    for _ in range(N):
        _acc_rmsprop_update += rmsprop_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_rmsprop_update = perf_counter_ns()
    var _ns_rmsprop_update = Float64(_t1_rmsprop_update - _t0_rmsprop_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::rmsprop_update", _ns_rmsprop_update, _acc_rmsprop_update)
    var _acc_adagrad_update: Float64 = 0.0
    var _t0_adagrad_update = perf_counter_ns()
    for _ in range(N):
        _acc_adagrad_update += adagrad_update(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_adagrad_update = perf_counter_ns()
    var _ns_adagrad_update = Float64(_t1_adagrad_update - _t0_adagrad_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::adagrad_update", _ns_adagrad_update, _acc_adagrad_update)
    var _acc_lars_update: Float64 = 0.0
    var _t0_lars_update = perf_counter_ns()
    for _ in range(N):
        _acc_lars_update += lars_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_lars_update = perf_counter_ns()
    var _ns_lars_update = Float64(_t1_lars_update - _t0_lars_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::lars_update", _ns_lars_update, _acc_lars_update)
    var _acc_lion_update: Float64 = 0.0
    var _t0_lion_update = perf_counter_ns()
    for _ in range(N):
        _acc_lion_update += lion_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_lion_update = perf_counter_ns()
    var _ns_lion_update = Float64(_t1_lion_update - _t0_lion_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::lion_update", _ns_lion_update, _acc_lion_update)
    var _acc_gradient_clipping: Float64 = 0.0
    var _t0_gradient_clipping = perf_counter_ns()
    for _ in range(N):
        _acc_gradient_clipping += gradient_clipping(0.5, 0.5, 0.5)
    var _t1_gradient_clipping = perf_counter_ns()
    var _ns_gradient_clipping = Float64(_t1_gradient_clipping - _t0_gradient_clipping) / Float64(N)
    print("MOJO_TIMING gradient_descent::gradient_clipping", _ns_gradient_clipping, _acc_gradient_clipping)
    var _acc_lr_cosine_schedule: Float64 = 0.0
    var _t0_lr_cosine_schedule = perf_counter_ns()
    for _ in range(N):
        _acc_lr_cosine_schedule += lr_cosine_schedule(0.5, 0.5, 0.5, 0.5)
    var _t1_lr_cosine_schedule = perf_counter_ns()
    var _ns_lr_cosine_schedule = Float64(_t1_lr_cosine_schedule - _t0_lr_cosine_schedule) / Float64(N)
    print("MOJO_TIMING gradient_descent::lr_cosine_schedule", _ns_lr_cosine_schedule, _acc_lr_cosine_schedule)
