"""bench_contrastive_learning.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from contrastive_learning import infonce_loss, simclr_positive_score, simclr_temperature_scale, triplet_margin_loss, nt_xent_denominator_term, moco_momentum_update, byol_ema_update, vicreg_variance_loss, vicreg_covariance_term, barlow_twins_cross_corr
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

    var _acc_infonce_loss: Float64 = 0.0
    var _t0_infonce_loss = perf_counter_ns()
    for _ in range(N):
        _acc_infonce_loss += infonce_loss(0.5, 0.5)
    var _t1_infonce_loss = perf_counter_ns()
    var _ns_infonce_loss = Float64(_t1_infonce_loss - _t0_infonce_loss) / Float64(N)
    print("MOJO_TIMING contrastive_learning::infonce_loss", _ns_infonce_loss, _acc_infonce_loss)
    var _acc_simclr_positive_score: Float64 = 0.0
    var _t0_simclr_positive_score = perf_counter_ns()
    for _ in range(N):
        _acc_simclr_positive_score += simclr_positive_score(0.5, 0.5, 0.5, 0.5)
    var _t1_simclr_positive_score = perf_counter_ns()
    var _ns_simclr_positive_score = Float64(_t1_simclr_positive_score - _t0_simclr_positive_score) / Float64(N)
    print("MOJO_TIMING contrastive_learning::simclr_positive_score", _ns_simclr_positive_score, _acc_simclr_positive_score)
    var _acc_simclr_temperature_scale: Float64 = 0.0
    var _t0_simclr_temperature_scale = perf_counter_ns()
    for _ in range(N):
        _acc_simclr_temperature_scale += simclr_temperature_scale(0.5, 0.5)
    var _t1_simclr_temperature_scale = perf_counter_ns()
    var _ns_simclr_temperature_scale = Float64(_t1_simclr_temperature_scale - _t0_simclr_temperature_scale) / Float64(N)
    print("MOJO_TIMING contrastive_learning::simclr_temperature_scale", _ns_simclr_temperature_scale, _acc_simclr_temperature_scale)
    var _acc_triplet_margin_loss: Float64 = 0.0
    var _t0_triplet_margin_loss = perf_counter_ns()
    for _ in range(N):
        _acc_triplet_margin_loss += triplet_margin_loss(0.5, 0.5, 0.5)
    var _t1_triplet_margin_loss = perf_counter_ns()
    var _ns_triplet_margin_loss = Float64(_t1_triplet_margin_loss - _t0_triplet_margin_loss) / Float64(N)
    print("MOJO_TIMING contrastive_learning::triplet_margin_loss", _ns_triplet_margin_loss, _acc_triplet_margin_loss)
    var _acc_nt_xent_denominator_term: Float64 = 0.0
    var _t0_nt_xent_denominator_term = perf_counter_ns()
    for _ in range(N):
        _acc_nt_xent_denominator_term += nt_xent_denominator_term(0.5, 0.5)
    var _t1_nt_xent_denominator_term = perf_counter_ns()
    var _ns_nt_xent_denominator_term = Float64(_t1_nt_xent_denominator_term - _t0_nt_xent_denominator_term) / Float64(N)
    print("MOJO_TIMING contrastive_learning::nt_xent_denominator_term", _ns_nt_xent_denominator_term, _acc_nt_xent_denominator_term)
    var _acc_moco_momentum_update: Float64 = 0.0
    var _t0_moco_momentum_update = perf_counter_ns()
    for _ in range(N):
        _acc_moco_momentum_update += moco_momentum_update(0.5, 0.5, 0.5)
    var _t1_moco_momentum_update = perf_counter_ns()
    var _ns_moco_momentum_update = Float64(_t1_moco_momentum_update - _t0_moco_momentum_update) / Float64(N)
    print("MOJO_TIMING contrastive_learning::moco_momentum_update", _ns_moco_momentum_update, _acc_moco_momentum_update)
    var _acc_byol_ema_update: Float64 = 0.0
    var _t0_byol_ema_update = perf_counter_ns()
    for _ in range(N):
        _acc_byol_ema_update += byol_ema_update(0.5, 0.5, 0.5)
    var _t1_byol_ema_update = perf_counter_ns()
    var _ns_byol_ema_update = Float64(_t1_byol_ema_update - _t0_byol_ema_update) / Float64(N)
    print("MOJO_TIMING contrastive_learning::byol_ema_update", _ns_byol_ema_update, _acc_byol_ema_update)
    var _acc_vicreg_variance_loss: Float64 = 0.0
    var _t0_vicreg_variance_loss = perf_counter_ns()
    for _ in range(N):
        _acc_vicreg_variance_loss += vicreg_variance_loss(0.5, 0.5)
    var _t1_vicreg_variance_loss = perf_counter_ns()
    var _ns_vicreg_variance_loss = Float64(_t1_vicreg_variance_loss - _t0_vicreg_variance_loss) / Float64(N)
    print("MOJO_TIMING contrastive_learning::vicreg_variance_loss", _ns_vicreg_variance_loss, _acc_vicreg_variance_loss)
    var _acc_vicreg_covariance_term: Float64 = 0.0
    var _t0_vicreg_covariance_term = perf_counter_ns()
    for _ in range(N):
        _acc_vicreg_covariance_term += vicreg_covariance_term(0.5, 0.5, 0.5)
    var _t1_vicreg_covariance_term = perf_counter_ns()
    var _ns_vicreg_covariance_term = Float64(_t1_vicreg_covariance_term - _t0_vicreg_covariance_term) / Float64(N)
    print("MOJO_TIMING contrastive_learning::vicreg_covariance_term", _ns_vicreg_covariance_term, _acc_vicreg_covariance_term)
    var _acc_barlow_twins_cross_corr: Float64 = 0.0
    var _t0_barlow_twins_cross_corr = perf_counter_ns()
    for _ in range(N):
        _acc_barlow_twins_cross_corr += barlow_twins_cross_corr(0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_barlow_twins_cross_corr = perf_counter_ns()
    var _ns_barlow_twins_cross_corr = Float64(_t1_barlow_twins_cross_corr - _t0_barlow_twins_cross_corr) / Float64(N)
    print("MOJO_TIMING contrastive_learning::barlow_twins_cross_corr", _ns_barlow_twins_cross_corr, _acc_barlow_twins_cross_corr)
