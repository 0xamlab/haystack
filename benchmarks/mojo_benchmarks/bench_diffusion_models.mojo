"""bench_diffusion_models.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from diffusion_models import linear_beta_schedule, cosine_beta_schedule, alpha_from_beta, forward_diffusion_sample, ddpm_reverse_mean, ddpm_posterior_variance, ddim_step, snr, noise_prediction_to_x0, edm_preconditioning
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

    var _acc_linear_beta_schedule: Float64 = 0.0
    var _t0_linear_beta_schedule = perf_counter_ns()
    for _ in range(N):
        _acc_linear_beta_schedule += linear_beta_schedule(0.5, 0.5, 0.5, 0.5)
    var _t1_linear_beta_schedule = perf_counter_ns()
    var _ns_linear_beta_schedule = Float64(_t1_linear_beta_schedule - _t0_linear_beta_schedule) / Float64(N)
    print("MOJO_TIMING diffusion_models::linear_beta_schedule", _ns_linear_beta_schedule, _acc_linear_beta_schedule)
    var _acc_cosine_beta_schedule: Float64 = 0.0
    var _t0_cosine_beta_schedule = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_beta_schedule += cosine_beta_schedule(0.5, 0.5, 0.5)
    var _t1_cosine_beta_schedule = perf_counter_ns()
    var _ns_cosine_beta_schedule = Float64(_t1_cosine_beta_schedule - _t0_cosine_beta_schedule) / Float64(N)
    print("MOJO_TIMING diffusion_models::cosine_beta_schedule", _ns_cosine_beta_schedule, _acc_cosine_beta_schedule)
    var _acc_alpha_from_beta: Float64 = 0.0
    var _t0_alpha_from_beta = perf_counter_ns()
    for _ in range(N):
        _acc_alpha_from_beta += alpha_from_beta(0.5, 0.5)
    var _t1_alpha_from_beta = perf_counter_ns()
    var _ns_alpha_from_beta = Float64(_t1_alpha_from_beta - _t0_alpha_from_beta) / Float64(N)
    print("MOJO_TIMING diffusion_models::alpha_from_beta", _ns_alpha_from_beta, _acc_alpha_from_beta)
    var _acc_forward_diffusion_sample: Float64 = 0.0
    var _t0_forward_diffusion_sample = perf_counter_ns()
    for _ in range(N):
        _acc_forward_diffusion_sample += forward_diffusion_sample(0.5, 0.5, 0.5)
    var _t1_forward_diffusion_sample = perf_counter_ns()
    var _ns_forward_diffusion_sample = Float64(_t1_forward_diffusion_sample - _t0_forward_diffusion_sample) / Float64(N)
    print("MOJO_TIMING diffusion_models::forward_diffusion_sample", _ns_forward_diffusion_sample, _acc_forward_diffusion_sample)
    var _acc_ddpm_reverse_mean: Float64 = 0.0
    var _t0_ddpm_reverse_mean = perf_counter_ns()
    for _ in range(N):
        _acc_ddpm_reverse_mean += ddpm_reverse_mean(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_ddpm_reverse_mean = perf_counter_ns()
    var _ns_ddpm_reverse_mean = Float64(_t1_ddpm_reverse_mean - _t0_ddpm_reverse_mean) / Float64(N)
    print("MOJO_TIMING diffusion_models::ddpm_reverse_mean", _ns_ddpm_reverse_mean, _acc_ddpm_reverse_mean)
    var _acc_ddpm_posterior_variance: Float64 = 0.0
    var _t0_ddpm_posterior_variance = perf_counter_ns()
    for _ in range(N):
        _acc_ddpm_posterior_variance += ddpm_posterior_variance(0.5, 0.5, 0.5)
    var _t1_ddpm_posterior_variance = perf_counter_ns()
    var _ns_ddpm_posterior_variance = Float64(_t1_ddpm_posterior_variance - _t0_ddpm_posterior_variance) / Float64(N)
    print("MOJO_TIMING diffusion_models::ddpm_posterior_variance", _ns_ddpm_posterior_variance, _acc_ddpm_posterior_variance)
    var _acc_ddim_step: Float64 = 0.0
    var _t0_ddim_step = perf_counter_ns()
    for _ in range(N):
        _acc_ddim_step += ddim_step(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_ddim_step = perf_counter_ns()
    var _ns_ddim_step = Float64(_t1_ddim_step - _t0_ddim_step) / Float64(N)
    print("MOJO_TIMING diffusion_models::ddim_step", _ns_ddim_step, _acc_ddim_step)
    var _acc_snr: Float64 = 0.0
    var _t0_snr = perf_counter_ns()
    for _ in range(N):
        _acc_snr += snr(0.5)
    var _t1_snr = perf_counter_ns()
    var _ns_snr = Float64(_t1_snr - _t0_snr) / Float64(N)
    print("MOJO_TIMING diffusion_models::snr", _ns_snr, _acc_snr)
    var _acc_noise_prediction_to_x0: Float64 = 0.0
    var _t0_noise_prediction_to_x0 = perf_counter_ns()
    for _ in range(N):
        _acc_noise_prediction_to_x0 += noise_prediction_to_x0(0.5, 0.5, 0.5)
    var _t1_noise_prediction_to_x0 = perf_counter_ns()
    var _ns_noise_prediction_to_x0 = Float64(_t1_noise_prediction_to_x0 - _t0_noise_prediction_to_x0) / Float64(N)
    print("MOJO_TIMING diffusion_models::noise_prediction_to_x0", _ns_noise_prediction_to_x0, _acc_noise_prediction_to_x0)
    var _acc_edm_preconditioning: Float64 = 0.0
    var _t0_edm_preconditioning = perf_counter_ns()
    for _ in range(N):
        _acc_edm_preconditioning += edm_preconditioning(0.5, 0.5)
    var _t1_edm_preconditioning = perf_counter_ns()
    var _ns_edm_preconditioning = Float64(_t1_edm_preconditioning - _t0_edm_preconditioning) / Float64(N)
    print("MOJO_TIMING diffusion_models::edm_preconditioning", _ns_edm_preconditioning, _acc_edm_preconditioning)
