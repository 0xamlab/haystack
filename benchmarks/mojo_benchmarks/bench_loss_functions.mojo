"""bench_loss_functions.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from loss_functions import binary_cross_entropy, categorical_cross_entropy, focal_loss, pow_approx, huber_loss, kl_divergence, contrastive_loss, triplet_loss, mse_loss, mae_loss, label_smoothing_loss
from std.time import perf_counter_ns
def _summary_hash_string(value: String) -> Int:
    var h = 7
    var bytes = value.as_bytes()
    for i in range(len(bytes)):
        h = (h * 131 + Int(bytes[i])) % 2147483647
    return h

def _summary_float64(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    return "float:" + String(value)

def _summary_float64_rounded6(value: Float64) -> String:
    if isnan(value): return "float:nan"
    if isinf(value): return "float:inf" if value > 0.0 else "float:-inf"
    var scaled = value * 1000000.0
    var rounded = Float64(Int(scaled + (0.5 if scaled >= 0.0 else -0.5))) / 1000000.0
    return "float:" + String(rounded)

def _summary_float32(value: Float32) -> String:
    return _summary_float64(Float64(value))

def _summary_int(value: Int) -> String:
    return "int:" + String(value)

def _summary_uint8(value: UInt8) -> String:
    return "int:" + String(value)

def _summary_uint16(value: UInt16) -> String:
    return "int:" + String(value)

def _summary_uint32(value: UInt32) -> String:
    return "int:" + String(value)

def _summary_uint64(value: UInt64) -> String:
    return "int:" + String(value)

def _summary_bool(value: Bool) -> String:
    return "bool:1" if value else "bool:0"

def _summary_string(value: String) -> String:
    return "str:" + String(len(value.as_bytes())) + ":" + String(_summary_hash_string(value))

def _summary_list_float64(value: List[Float64]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_float32(value: List[Float32]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_float32(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_int(value: List[Int]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_bool(value: List[Bool]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_bool(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_string(value: List[String]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_string(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_float64(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_float64_rounded6(value: List[List[Float64]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        var row_joined = String("")
        for j in range(len(value[i])):
            if j > 0: row_joined += "|"
            row_joined += _summary_float64_rounded6(value[i][j])
        joined += "list:" + String(len(value[i])) + ":" + String(_summary_hash_string(row_joined))
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_int(value: List[List[Int]]) -> String:
    var joined = String("")
    for i in range(len(value)):
        if i > 0: joined += "|"
        joined += _summary_list_int(value[i])
    return "list:" + String(len(value)) + ":" + String(_summary_hash_string(joined))

def _summary_list_list_string(value: List[List[String]]) -> String:
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

    var _acc_binary_cross_entropy: Float64 = 0.0
    var _t0_binary_cross_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_binary_cross_entropy += binary_cross_entropy(0.5, 0.5)
    var _t1_binary_cross_entropy = perf_counter_ns()
    var _ns_binary_cross_entropy = Float64(_t1_binary_cross_entropy - _t0_binary_cross_entropy) / Float64(N)
    print("MOJO_TIMING loss_functions::binary_cross_entropy", _ns_binary_cross_entropy, _acc_binary_cross_entropy)
    var _result_binary_cross_entropy = binary_cross_entropy(0.5, 0.5)
    var _summary_binary_cross_entropy = _summary_float64(_result_binary_cross_entropy)
    print("MOJO_RESULT loss_functions::binary_cross_entropy", _summary_binary_cross_entropy)
    var _acc_categorical_cross_entropy: Float64 = 0.0
    var _t0_categorical_cross_entropy = perf_counter_ns()
    for _ in range(N):
        _acc_categorical_cross_entropy += categorical_cross_entropy(0.5, 0.5)
    var _t1_categorical_cross_entropy = perf_counter_ns()
    var _ns_categorical_cross_entropy = Float64(_t1_categorical_cross_entropy - _t0_categorical_cross_entropy) / Float64(N)
    print("MOJO_TIMING loss_functions::categorical_cross_entropy", _ns_categorical_cross_entropy, _acc_categorical_cross_entropy)
    var _result_categorical_cross_entropy = categorical_cross_entropy(0.5, 0.5)
    var _summary_categorical_cross_entropy = _summary_float64(_result_categorical_cross_entropy)
    print("MOJO_RESULT loss_functions::categorical_cross_entropy", _summary_categorical_cross_entropy)
    var _acc_focal_loss: Float64 = 0.0
    var _t0_focal_loss = perf_counter_ns()
    for _ in range(N):
        _acc_focal_loss += focal_loss(0.5, 0.5, 0.5, 0.5)
    var _t1_focal_loss = perf_counter_ns()
    var _ns_focal_loss = Float64(_t1_focal_loss - _t0_focal_loss) / Float64(N)
    print("MOJO_TIMING loss_functions::focal_loss", _ns_focal_loss, _acc_focal_loss)
    var _result_focal_loss = focal_loss(0.5, 0.5, 0.5, 0.5)
    var _summary_focal_loss = _summary_float64(_result_focal_loss)
    print("MOJO_RESULT loss_functions::focal_loss", _summary_focal_loss)
    var _acc_pow_approx: Float64 = 0.0
    var _t0_pow_approx = perf_counter_ns()
    for _ in range(N):
        _acc_pow_approx += pow_approx(0.5, 0.5)
    var _t1_pow_approx = perf_counter_ns()
    var _ns_pow_approx = Float64(_t1_pow_approx - _t0_pow_approx) / Float64(N)
    print("MOJO_TIMING loss_functions::pow_approx", _ns_pow_approx, _acc_pow_approx)
    var _result_pow_approx = pow_approx(0.5, 0.5)
    var _summary_pow_approx = _summary_float64(_result_pow_approx)
    print("MOJO_RESULT loss_functions::pow_approx", _summary_pow_approx)
    var _acc_huber_loss: Float64 = 0.0
    var _t0_huber_loss = perf_counter_ns()
    for _ in range(N):
        _acc_huber_loss += huber_loss(0.5, 0.5, 0.5)
    var _t1_huber_loss = perf_counter_ns()
    var _ns_huber_loss = Float64(_t1_huber_loss - _t0_huber_loss) / Float64(N)
    print("MOJO_TIMING loss_functions::huber_loss", _ns_huber_loss, _acc_huber_loss)
    var _result_huber_loss = huber_loss(0.5, 0.5, 0.5)
    var _summary_huber_loss = _summary_float64(_result_huber_loss)
    print("MOJO_RESULT loss_functions::huber_loss", _summary_huber_loss)
    var _acc_kl_divergence: Float64 = 0.0
    var _t0_kl_divergence = perf_counter_ns()
    for _ in range(N):
        _acc_kl_divergence += kl_divergence(0.5, 0.5)
    var _t1_kl_divergence = perf_counter_ns()
    var _ns_kl_divergence = Float64(_t1_kl_divergence - _t0_kl_divergence) / Float64(N)
    print("MOJO_TIMING loss_functions::kl_divergence", _ns_kl_divergence, _acc_kl_divergence)
    var _result_kl_divergence = kl_divergence(0.5, 0.5)
    var _summary_kl_divergence = _summary_float64(_result_kl_divergence)
    print("MOJO_RESULT loss_functions::kl_divergence", _summary_kl_divergence)
    var _acc_contrastive_loss: Float64 = 0.0
    var _t0_contrastive_loss = perf_counter_ns()
    for _ in range(N):
        _acc_contrastive_loss += contrastive_loss(0.5, 0.5, 0.5)
    var _t1_contrastive_loss = perf_counter_ns()
    var _ns_contrastive_loss = Float64(_t1_contrastive_loss - _t0_contrastive_loss) / Float64(N)
    print("MOJO_TIMING loss_functions::contrastive_loss", _ns_contrastive_loss, _acc_contrastive_loss)
    var _result_contrastive_loss = contrastive_loss(0.5, 0.5, 0.5)
    var _summary_contrastive_loss = _summary_float64(_result_contrastive_loss)
    print("MOJO_RESULT loss_functions::contrastive_loss", _summary_contrastive_loss)
    var _acc_triplet_loss: Float64 = 0.0
    var _t0_triplet_loss = perf_counter_ns()
    for _ in range(N):
        _acc_triplet_loss += triplet_loss(0.5, 0.5, 0.5)
    var _t1_triplet_loss = perf_counter_ns()
    var _ns_triplet_loss = Float64(_t1_triplet_loss - _t0_triplet_loss) / Float64(N)
    print("MOJO_TIMING loss_functions::triplet_loss", _ns_triplet_loss, _acc_triplet_loss)
    var _result_triplet_loss = triplet_loss(0.5, 0.5, 0.5)
    var _summary_triplet_loss = _summary_float64(_result_triplet_loss)
    print("MOJO_RESULT loss_functions::triplet_loss", _summary_triplet_loss)
    var _acc_mse_loss: Float64 = 0.0
    var _t0_mse_loss = perf_counter_ns()
    for _ in range(N):
        _acc_mse_loss += mse_loss(0.5, 0.5)
    var _t1_mse_loss = perf_counter_ns()
    var _ns_mse_loss = Float64(_t1_mse_loss - _t0_mse_loss) / Float64(N)
    print("MOJO_TIMING loss_functions::mse_loss", _ns_mse_loss, _acc_mse_loss)
    var _result_mse_loss = mse_loss(0.5, 0.5)
    var _summary_mse_loss = _summary_float64(_result_mse_loss)
    print("MOJO_RESULT loss_functions::mse_loss", _summary_mse_loss)
    var _acc_mae_loss: Float64 = 0.0
    var _t0_mae_loss = perf_counter_ns()
    for _ in range(N):
        _acc_mae_loss += mae_loss(0.5, 0.5)
    var _t1_mae_loss = perf_counter_ns()
    var _ns_mae_loss = Float64(_t1_mae_loss - _t0_mae_loss) / Float64(N)
    print("MOJO_TIMING loss_functions::mae_loss", _ns_mae_loss, _acc_mae_loss)
    var _result_mae_loss = mae_loss(0.5, 0.5)
    var _summary_mae_loss = _summary_float64(_result_mae_loss)
    print("MOJO_RESULT loss_functions::mae_loss", _summary_mae_loss)
    var _acc_label_smoothing_loss: Float64 = 0.0
    var _t0_label_smoothing_loss = perf_counter_ns()
    for _ in range(N):
        _acc_label_smoothing_loss += label_smoothing_loss(0.5, 0.5, 0.5, 0.5)
    var _t1_label_smoothing_loss = perf_counter_ns()
    var _ns_label_smoothing_loss = Float64(_t1_label_smoothing_loss - _t0_label_smoothing_loss) / Float64(N)
    print("MOJO_TIMING loss_functions::label_smoothing_loss", _ns_label_smoothing_loss, _acc_label_smoothing_loss)
    var _result_label_smoothing_loss = label_smoothing_loss(0.5, 0.5, 0.5, 0.5)
    var _summary_label_smoothing_loss = _summary_float64(_result_label_smoothing_loss)
    print("MOJO_RESULT loss_functions::label_smoothing_loss", _summary_label_smoothing_loss)
