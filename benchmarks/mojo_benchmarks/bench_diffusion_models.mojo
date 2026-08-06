"""bench_diffusion_models.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from diffusion_models import linear_beta_schedule, cosine_beta_schedule, alpha_from_beta, forward_diffusion_sample, ddpm_reverse_mean, ddpm_posterior_variance, ddim_step, snr, noise_prediction_to_x0, edm_preconditioning
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

    var _acc_linear_beta_schedule: Float64 = 0.0
    var _t0_linear_beta_schedule = perf_counter_ns()
    for _ in range(N):
        _acc_linear_beta_schedule += linear_beta_schedule(0.5, 0.5, 0.5, 0.5)
    var _t1_linear_beta_schedule = perf_counter_ns()
    var _ns_linear_beta_schedule = Float64(_t1_linear_beta_schedule - _t0_linear_beta_schedule) / Float64(N)
    print("MOJO_TIMING diffusion_models::linear_beta_schedule", _ns_linear_beta_schedule, _acc_linear_beta_schedule)
    var _result_linear_beta_schedule = linear_beta_schedule(0.5, 0.5, 0.5, 0.5)
    var _summary_linear_beta_schedule = _summary_float64(_result_linear_beta_schedule)
    print("MOJO_RESULT diffusion_models::linear_beta_schedule", _summary_linear_beta_schedule)
    var _acc_cosine_beta_schedule: Float64 = 0.0
    var _t0_cosine_beta_schedule = perf_counter_ns()
    for _ in range(N):
        _acc_cosine_beta_schedule += cosine_beta_schedule(0.5, 0.5, 0.5)
    var _t1_cosine_beta_schedule = perf_counter_ns()
    var _ns_cosine_beta_schedule = Float64(_t1_cosine_beta_schedule - _t0_cosine_beta_schedule) / Float64(N)
    print("MOJO_TIMING diffusion_models::cosine_beta_schedule", _ns_cosine_beta_schedule, _acc_cosine_beta_schedule)
    var _result_cosine_beta_schedule = cosine_beta_schedule(0.5, 0.5, 0.5)
    var _summary_cosine_beta_schedule = _summary_float64(_result_cosine_beta_schedule)
    print("MOJO_RESULT diffusion_models::cosine_beta_schedule", _summary_cosine_beta_schedule)
    var _acc_alpha_from_beta: Float64 = 0.0
    var _t0_alpha_from_beta = perf_counter_ns()
    for _ in range(N):
        _acc_alpha_from_beta += alpha_from_beta(0.5, 0.5)
    var _t1_alpha_from_beta = perf_counter_ns()
    var _ns_alpha_from_beta = Float64(_t1_alpha_from_beta - _t0_alpha_from_beta) / Float64(N)
    print("MOJO_TIMING diffusion_models::alpha_from_beta", _ns_alpha_from_beta, _acc_alpha_from_beta)
    var _result_alpha_from_beta = alpha_from_beta(0.5, 0.5)
    var _summary_alpha_from_beta = _summary_float64(_result_alpha_from_beta)
    print("MOJO_RESULT diffusion_models::alpha_from_beta", _summary_alpha_from_beta)
    var _acc_forward_diffusion_sample: Float64 = 0.0
    var _t0_forward_diffusion_sample = perf_counter_ns()
    for _ in range(N):
        _acc_forward_diffusion_sample += forward_diffusion_sample(0.5, 0.5, 0.5)
    var _t1_forward_diffusion_sample = perf_counter_ns()
    var _ns_forward_diffusion_sample = Float64(_t1_forward_diffusion_sample - _t0_forward_diffusion_sample) / Float64(N)
    print("MOJO_TIMING diffusion_models::forward_diffusion_sample", _ns_forward_diffusion_sample, _acc_forward_diffusion_sample)
    var _result_forward_diffusion_sample = forward_diffusion_sample(0.5, 0.5, 0.5)
    var _summary_forward_diffusion_sample = _summary_float64(_result_forward_diffusion_sample)
    print("MOJO_RESULT diffusion_models::forward_diffusion_sample", _summary_forward_diffusion_sample)
    var _acc_ddpm_reverse_mean: Float64 = 0.0
    var _t0_ddpm_reverse_mean = perf_counter_ns()
    for _ in range(N):
        _acc_ddpm_reverse_mean += ddpm_reverse_mean(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_ddpm_reverse_mean = perf_counter_ns()
    var _ns_ddpm_reverse_mean = Float64(_t1_ddpm_reverse_mean - _t0_ddpm_reverse_mean) / Float64(N)
    print("MOJO_TIMING diffusion_models::ddpm_reverse_mean", _ns_ddpm_reverse_mean, _acc_ddpm_reverse_mean)
    var _result_ddpm_reverse_mean = ddpm_reverse_mean(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_ddpm_reverse_mean = _summary_float64(_result_ddpm_reverse_mean)
    print("MOJO_RESULT diffusion_models::ddpm_reverse_mean", _summary_ddpm_reverse_mean)
    var _acc_ddpm_posterior_variance: Float64 = 0.0
    var _t0_ddpm_posterior_variance = perf_counter_ns()
    for _ in range(N):
        _acc_ddpm_posterior_variance += ddpm_posterior_variance(0.5, 0.5, 0.5)
    var _t1_ddpm_posterior_variance = perf_counter_ns()
    var _ns_ddpm_posterior_variance = Float64(_t1_ddpm_posterior_variance - _t0_ddpm_posterior_variance) / Float64(N)
    print("MOJO_TIMING diffusion_models::ddpm_posterior_variance", _ns_ddpm_posterior_variance, _acc_ddpm_posterior_variance)
    var _result_ddpm_posterior_variance = ddpm_posterior_variance(0.5, 0.5, 0.5)
    var _summary_ddpm_posterior_variance = _summary_float64(_result_ddpm_posterior_variance)
    print("MOJO_RESULT diffusion_models::ddpm_posterior_variance", _summary_ddpm_posterior_variance)
    var _acc_ddim_step: Float64 = 0.0
    var _t0_ddim_step = perf_counter_ns()
    for _ in range(N):
        _acc_ddim_step += ddim_step(0.5, 0.5, 0.5, 0.5, 0.5)
    var _t1_ddim_step = perf_counter_ns()
    var _ns_ddim_step = Float64(_t1_ddim_step - _t0_ddim_step) / Float64(N)
    print("MOJO_TIMING diffusion_models::ddim_step", _ns_ddim_step, _acc_ddim_step)
    var _result_ddim_step = ddim_step(0.5, 0.5, 0.5, 0.5, 0.5)
    var _summary_ddim_step = _summary_float64(_result_ddim_step)
    print("MOJO_RESULT diffusion_models::ddim_step", _summary_ddim_step)
    var _acc_snr: Float64 = 0.0
    var _t0_snr = perf_counter_ns()
    for _ in range(N):
        _acc_snr += snr(0.5)
    var _t1_snr = perf_counter_ns()
    var _ns_snr = Float64(_t1_snr - _t0_snr) / Float64(N)
    print("MOJO_TIMING diffusion_models::snr", _ns_snr, _acc_snr)
    var _result_snr = snr(0.5)
    var _summary_snr = _summary_float64(_result_snr)
    print("MOJO_RESULT diffusion_models::snr", _summary_snr)
    var _acc_noise_prediction_to_x0: Float64 = 0.0
    var _t0_noise_prediction_to_x0 = perf_counter_ns()
    for _ in range(N):
        _acc_noise_prediction_to_x0 += noise_prediction_to_x0(0.5, 0.5, 0.5)
    var _t1_noise_prediction_to_x0 = perf_counter_ns()
    var _ns_noise_prediction_to_x0 = Float64(_t1_noise_prediction_to_x0 - _t0_noise_prediction_to_x0) / Float64(N)
    print("MOJO_TIMING diffusion_models::noise_prediction_to_x0", _ns_noise_prediction_to_x0, _acc_noise_prediction_to_x0)
    var _result_noise_prediction_to_x0 = noise_prediction_to_x0(0.5, 0.5, 0.5)
    var _summary_noise_prediction_to_x0 = _summary_float64(_result_noise_prediction_to_x0)
    print("MOJO_RESULT diffusion_models::noise_prediction_to_x0", _summary_noise_prediction_to_x0)
    var _acc_edm_preconditioning: Float64 = 0.0
    var _t0_edm_preconditioning = perf_counter_ns()
    for _ in range(N):
        _acc_edm_preconditioning += edm_preconditioning(0.5, 0.5)
    var _t1_edm_preconditioning = perf_counter_ns()
    var _ns_edm_preconditioning = Float64(_t1_edm_preconditioning - _t0_edm_preconditioning) / Float64(N)
    print("MOJO_TIMING diffusion_models::edm_preconditioning", _ns_edm_preconditioning, _acc_edm_preconditioning)
    var _result_edm_preconditioning = edm_preconditioning(0.5, 0.5)
    var _summary_edm_preconditioning = _summary_float64(_result_edm_preconditioning)
    print("MOJO_RESULT diffusion_models::edm_preconditioning", _summary_edm_preconditioning)
