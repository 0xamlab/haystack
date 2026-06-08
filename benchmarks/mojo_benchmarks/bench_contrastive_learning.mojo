"""bench_contrastive_learning.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from contrastive_learning import infonce_loss, simclr_positive_score, simclr_temperature_scale, triplet_margin_loss, nt_xent_denominator_term, moco_momentum_update, byol_ema_update, vicreg_variance_loss, vicreg_covariance_term, barlow_twins_cross_corr
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

    var _acc_infonce_loss: Float64 = 0.0
    var _t0_infonce_loss = perf_counter_ns()
    for _ in range(N):
        _acc_infonce_loss += infonce_loss(0.5, 0.5)
    var _t1_infonce_loss = perf_counter_ns()
    var _ns_infonce_loss = Float64(_t1_infonce_loss - _t0_infonce_loss) / Float64(N)
    print("MOJO_TIMING contrastive_learning::infonce_loss", _ns_infonce_loss, _acc_infonce_loss)
    var _result_infonce_loss = infonce_loss(0.5, 0.5)
    var _summary_infonce_loss = _summary_float64(_result_infonce_loss)
    print("MOJO_RESULT contrastive_learning::infonce_loss", _summary_infonce_loss)
    var _acc_simclr_positive_score: Float64 = 0.0
    var _t0_simclr_positive_score = perf_counter_ns()
    for _ in range(N):
        _acc_simclr_positive_score += simclr_positive_score(0.5, 0.5, 0.5, 0.5)
    var _t1_simclr_positive_score = perf_counter_ns()
    var _ns_simclr_positive_score = Float64(_t1_simclr_positive_score - _t0_simclr_positive_score) / Float64(N)
    print("MOJO_TIMING contrastive_learning::simclr_positive_score", _ns_simclr_positive_score, _acc_simclr_positive_score)
    var _result_simclr_positive_score = simclr_positive_score(0.5, 0.5, 0.5, 0.5)
    var _summary_simclr_positive_score = _summary_float64(_result_simclr_positive_score)
    print("MOJO_RESULT contrastive_learning::simclr_positive_score", _summary_simclr_positive_score)
    var _acc_simclr_temperature_scale: Float64 = 0.0
    var _t0_simclr_temperature_scale = perf_counter_ns()
    for _ in range(N):
        _acc_simclr_temperature_scale += simclr_temperature_scale(0.5, 0.5)
    var _t1_simclr_temperature_scale = perf_counter_ns()
    var _ns_simclr_temperature_scale = Float64(_t1_simclr_temperature_scale - _t0_simclr_temperature_scale) / Float64(N)
    print("MOJO_TIMING contrastive_learning::simclr_temperature_scale", _ns_simclr_temperature_scale, _acc_simclr_temperature_scale)
    var _result_simclr_temperature_scale = simclr_temperature_scale(0.5, 0.5)
    var _summary_simclr_temperature_scale = _summary_float64(_result_simclr_temperature_scale)
    print("MOJO_RESULT contrastive_learning::simclr_temperature_scale", _summary_simclr_temperature_scale)
    var _acc_triplet_margin_loss: Float64 = 0.0
    var _t0_triplet_margin_loss = perf_counter_ns()
    for _ in range(N):
        _acc_triplet_margin_loss += triplet_margin_loss(0.5, 0.5, 0.5)
    var _t1_triplet_margin_loss = perf_counter_ns()
    var _ns_triplet_margin_loss = Float64(_t1_triplet_margin_loss - _t0_triplet_margin_loss) / Float64(N)
    print("MOJO_TIMING contrastive_learning::triplet_margin_loss", _ns_triplet_margin_loss, _acc_triplet_margin_loss)
    var _result_triplet_margin_loss = triplet_margin_loss(0.5, 0.5, 0.5)
    var _summary_triplet_margin_loss = _summary_float64(_result_triplet_margin_loss)
    print("MOJO_RESULT contrastive_learning::triplet_margin_loss", _summary_triplet_margin_loss)
    var _acc_nt_xent_denominator_term: Float64 = 0.0
    var _t0_nt_xent_denominator_term = perf_counter_ns()
    for _ in range(N):
        _acc_nt_xent_denominator_term += nt_xent_denominator_term(0.5, 0.5)
    var _t1_nt_xent_denominator_term = perf_counter_ns()
    var _ns_nt_xent_denominator_term = Float64(_t1_nt_xent_denominator_term - _t0_nt_xent_denominator_term) / Float64(N)
    print("MOJO_TIMING contrastive_learning::nt_xent_denominator_term", _ns_nt_xent_denominator_term, _acc_nt_xent_denominator_term)
    var _result_nt_xent_denominator_term = nt_xent_denominator_term(0.5, 0.5)
    var _summary_nt_xent_denominator_term = _summary_float64(_result_nt_xent_denominator_term)
    print("MOJO_RESULT contrastive_learning::nt_xent_denominator_term", _summary_nt_xent_denominator_term)
    var _acc_moco_momentum_update: Float64 = 0.0
    var _t0_moco_momentum_update = perf_counter_ns()
    for _ in range(N):
        _acc_moco_momentum_update += moco_momentum_update(0.5, 0.5, 0.5)
    var _t1_moco_momentum_update = perf_counter_ns()
    var _ns_moco_momentum_update = Float64(_t1_moco_momentum_update - _t0_moco_momentum_update) / Float64(N)
    print("MOJO_TIMING contrastive_learning::moco_momentum_update", _ns_moco_momentum_update, _acc_moco_momentum_update)
    var _result_moco_momentum_update = moco_momentum_update(0.5, 0.5, 0.5)
    var _summary_moco_momentum_update = _summary_float64(_result_moco_momentum_update)
    print("MOJO_RESULT contrastive_learning::moco_momentum_update", _summary_moco_momentum_update)
    var _acc_byol_ema_update: Float64 = 0.0
    var _t0_byol_ema_update = perf_counter_ns()
    for _ in range(N):
        _acc_byol_ema_update += byol_ema_update(0.5, 0.5, 0.5)
    var _t1_byol_ema_update = perf_counter_ns()
    var _ns_byol_ema_update = Float64(_t1_byol_ema_update - _t0_byol_ema_update) / Float64(N)
    print("MOJO_TIMING contrastive_learning::byol_ema_update", _ns_byol_ema_update, _acc_byol_ema_update)
    var _result_byol_ema_update = byol_ema_update(0.5, 0.5, 0.5)
    var _summary_byol_ema_update = _summary_float64(_result_byol_ema_update)
    print("MOJO_RESULT contrastive_learning::byol_ema_update", _summary_byol_ema_update)
    var _acc_vicreg_variance_loss: Float64 = 0.0
    var _t0_vicreg_variance_loss = perf_counter_ns()
    for _ in range(N):
        _acc_vicreg_variance_loss += vicreg_variance_loss(0.5, 0.5)
    var _t1_vicreg_variance_loss = perf_counter_ns()
    var _ns_vicreg_variance_loss = Float64(_t1_vicreg_variance_loss - _t0_vicreg_variance_loss) / Float64(N)
    print("MOJO_TIMING contrastive_learning::vicreg_variance_loss", _ns_vicreg_variance_loss, _acc_vicreg_variance_loss)
    var _result_vicreg_variance_loss = vicreg_variance_loss(0.5, 0.5)
    var _summary_vicreg_variance_loss = _summary_float64(_result_vicreg_variance_loss)
    print("MOJO_RESULT contrastive_learning::vicreg_variance_loss", _summary_vicreg_variance_loss)
    var _acc_vicreg_covariance_term: Float64 = 0.0
    var _t0_vicreg_covariance_term = perf_counter_ns()
    for _ in range(N):
        _acc_vicreg_covariance_term += vicreg_covariance_term(0.5, 0.5, 0.5)
    var _t1_vicreg_covariance_term = perf_counter_ns()
    var _ns_vicreg_covariance_term = Float64(_t1_vicreg_covariance_term - _t0_vicreg_covariance_term) / Float64(N)
    print("MOJO_TIMING contrastive_learning::vicreg_covariance_term", _ns_vicreg_covariance_term, _acc_vicreg_covariance_term)
    var _result_vicreg_covariance_term = vicreg_covariance_term(0.5, 0.5, 0.5)
    var _summary_vicreg_covariance_term = _summary_float64(_result_vicreg_covariance_term)
    print("MOJO_RESULT contrastive_learning::vicreg_covariance_term", _summary_vicreg_covariance_term)
    var _acc_barlow_twins_cross_corr: Float64 = 0.0
    var _t0_barlow_twins_cross_corr = perf_counter_ns()
    for _ in range(N):
        _acc_barlow_twins_cross_corr += barlow_twins_cross_corr(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_barlow_twins_cross_corr = perf_counter_ns()
    var _ns_barlow_twins_cross_corr = Float64(_t1_barlow_twins_cross_corr - _t0_barlow_twins_cross_corr) / Float64(N)
    print("MOJO_TIMING contrastive_learning::barlow_twins_cross_corr", _ns_barlow_twins_cross_corr, _acc_barlow_twins_cross_corr)
    var _result_barlow_twins_cross_corr = barlow_twins_cross_corr(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_barlow_twins_cross_corr = _summary_float64(_result_barlow_twins_cross_corr)
    print("MOJO_RESULT contrastive_learning::barlow_twins_cross_corr", _summary_barlow_twins_cross_corr)
