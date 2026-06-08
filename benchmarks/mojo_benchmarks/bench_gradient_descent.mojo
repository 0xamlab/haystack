"""bench_gradient_descent.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from gradient_descent import sgd_update, sgd_momentum_update, adam_update, adamw_update, rmsprop_update, adagrad_update, lars_update, lion_update, gradient_clipping, lr_cosine_schedule
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

    var _acc_sgd_update: Float64 = 0.0
    var _t0_sgd_update = perf_counter_ns()
    for _ in range(N):
        _acc_sgd_update += sgd_update(0.5, 0.5, 0.5)
    var _t1_sgd_update = perf_counter_ns()
    var _ns_sgd_update = Float64(_t1_sgd_update - _t0_sgd_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::sgd_update", _ns_sgd_update, _acc_sgd_update)
    var _result_sgd_update = sgd_update(0.5, 0.5, 0.5)
    var _summary_sgd_update = _summary_float64(_result_sgd_update)
    print("MOJO_RESULT gradient_descent::sgd_update", _summary_sgd_update)
    var _acc_sgd_momentum_update: Float64 = 0.0
    var _t0_sgd_momentum_update = perf_counter_ns()
    for _ in range(N):
        _acc_sgd_momentum_update += sgd_momentum_update(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_sgd_momentum_update = perf_counter_ns()
    var _ns_sgd_momentum_update = Float64(_t1_sgd_momentum_update - _t0_sgd_momentum_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::sgd_momentum_update", _ns_sgd_momentum_update, _acc_sgd_momentum_update)
    var _result_sgd_momentum_update = sgd_momentum_update(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_sgd_momentum_update = _summary_float64(_result_sgd_momentum_update)
    print("MOJO_RESULT gradient_descent::sgd_momentum_update", _summary_sgd_momentum_update)
    var _acc_adam_update: Float64 = 0.0
    var _t0_adam_update = perf_counter_ns()
    for _ in range(N):
        _acc_adam_update += adam_update(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_adam_update = perf_counter_ns()
    var _ns_adam_update = Float64(_t1_adam_update - _t0_adam_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::adam_update", _ns_adam_update, _acc_adam_update)
    var _result_adam_update = adam_update(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_adam_update = _summary_float64(_result_adam_update)
    print("MOJO_RESULT gradient_descent::adam_update", _summary_adam_update)
    var _acc_adamw_update: Float64 = 0.0
    var _t0_adamw_update = perf_counter_ns()
    for _ in range(N):
        _acc_adamw_update += adamw_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_adamw_update = perf_counter_ns()
    var _ns_adamw_update = Float64(_t1_adamw_update - _t0_adamw_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::adamw_update", _ns_adamw_update, _acc_adamw_update)
    var _result_adamw_update = adamw_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_adamw_update = _summary_float64(_result_adamw_update)
    print("MOJO_RESULT gradient_descent::adamw_update", _summary_adamw_update)
    var _acc_rmsprop_update: Float64 = 0.0
    var _t0_rmsprop_update = perf_counter_ns()
    for _ in range(N):
        _acc_rmsprop_update += rmsprop_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_rmsprop_update = perf_counter_ns()
    var _ns_rmsprop_update = Float64(_t1_rmsprop_update - _t0_rmsprop_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::rmsprop_update", _ns_rmsprop_update, _acc_rmsprop_update)
    var _result_rmsprop_update = rmsprop_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_rmsprop_update = _summary_float64(_result_rmsprop_update)
    print("MOJO_RESULT gradient_descent::rmsprop_update", _summary_rmsprop_update)
    var _acc_adagrad_update: Float64 = 0.0
    var _t0_adagrad_update = perf_counter_ns()
    for _ in range(N):
        _acc_adagrad_update += adagrad_update(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_adagrad_update = perf_counter_ns()
    var _ns_adagrad_update = Float64(_t1_adagrad_update - _t0_adagrad_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::adagrad_update", _ns_adagrad_update, _acc_adagrad_update)
    var _result_adagrad_update = adagrad_update(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_adagrad_update = _summary_float64(_result_adagrad_update)
    print("MOJO_RESULT gradient_descent::adagrad_update", _summary_adagrad_update)
    var _acc_lars_update: Float64 = 0.0
    var _t0_lars_update = perf_counter_ns()
    for _ in range(N):
        _acc_lars_update += lars_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_lars_update = perf_counter_ns()
    var _ns_lars_update = Float64(_t1_lars_update - _t0_lars_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::lars_update", _ns_lars_update, _acc_lars_update)
    var _result_lars_update = lars_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_lars_update = _summary_float64(_result_lars_update)
    print("MOJO_RESULT gradient_descent::lars_update", _summary_lars_update)
    var _acc_lion_update: Float64 = 0.0
    var _t0_lion_update = perf_counter_ns()
    for _ in range(N):
        _acc_lion_update += lion_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_lion_update = perf_counter_ns()
    var _ns_lion_update = Float64(_t1_lion_update - _t0_lion_update) / Float64(N)
    print("MOJO_TIMING gradient_descent::lion_update", _ns_lion_update, _acc_lion_update)
    var _result_lion_update = lion_update(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_lion_update = _summary_float64(_result_lion_update)
    print("MOJO_RESULT gradient_descent::lion_update", _summary_lion_update)
    var _acc_gradient_clipping: Float64 = 0.0
    var _t0_gradient_clipping = perf_counter_ns()
    for _ in range(N):
        _acc_gradient_clipping += gradient_clipping(0.5, 0.5, 0.5)
    var _t1_gradient_clipping = perf_counter_ns()
    var _ns_gradient_clipping = Float64(_t1_gradient_clipping - _t0_gradient_clipping) / Float64(N)
    print("MOJO_TIMING gradient_descent::gradient_clipping", _ns_gradient_clipping, _acc_gradient_clipping)
    var _result_gradient_clipping = gradient_clipping(0.5, 0.5, 0.5)
    var _summary_gradient_clipping = _summary_float64(_result_gradient_clipping)
    print("MOJO_RESULT gradient_descent::gradient_clipping", _summary_gradient_clipping)
    var _acc_lr_cosine_schedule: Float64 = 0.0
    var _t0_lr_cosine_schedule = perf_counter_ns()
    for _ in range(N):
        _acc_lr_cosine_schedule += lr_cosine_schedule(0.5, 0.5, 0.5, 0.5)
    var _t1_lr_cosine_schedule = perf_counter_ns()
    var _ns_lr_cosine_schedule = Float64(_t1_lr_cosine_schedule - _t0_lr_cosine_schedule) / Float64(N)
    print("MOJO_TIMING gradient_descent::lr_cosine_schedule", _ns_lr_cosine_schedule, _acc_lr_cosine_schedule)
    var _result_lr_cosine_schedule = lr_cosine_schedule(0.5, 0.5, 0.5, 0.5)
    var _summary_lr_cosine_schedule = _summary_float64(_result_lr_cosine_schedule)
    print("MOJO_RESULT gradient_descent::lr_cosine_schedule", _summary_lr_cosine_schedule)
