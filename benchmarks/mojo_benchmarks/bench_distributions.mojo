"""bench_distributions.mojo — auto-generated timing benchmark."""
from std.math import isnan, isinf
from distributions import sample_normal, sample_uniform, sample_triangular, sample_lognormal, sample_exponential, sample_weibull, sample_gamma_mt, sample_beta, sample_pert, sample_bernoulli, sample_poisson, sample_student_t, sample_cauchy, sample_laplace, sample_pareto, sample_gumbel, sample_rayleigh, sample_arcsine, sample_logistic, sample_halfnormal, acos_approx, sample_vonmises, sample_neg_binomial, sample_hypergeometric, sample_one
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

    var _acc_sample_normal: Float64 = 0.0
    var _t0_sample_normal = perf_counter_ns()
    for _ in range(N):
        _acc_sample_normal += sample_normal(0.5, 0.5)
    var _t1_sample_normal = perf_counter_ns()
    var _ns_sample_normal = Float64(_t1_sample_normal - _t0_sample_normal) / Float64(N)
    print("MOJO_TIMING distributions::sample_normal", _ns_sample_normal, _acc_sample_normal)
    var _result_sample_normal = sample_normal(0.5, 0.5)
    var _summary_sample_normal = _summary_float64(_result_sample_normal)
    print("MOJO_RESULT distributions::sample_normal", _summary_sample_normal)
    var _acc_sample_uniform: Float64 = 0.0
    var _t0_sample_uniform = perf_counter_ns()
    for _ in range(N):
        _acc_sample_uniform += sample_uniform(0.5, 0.5)
    var _t1_sample_uniform = perf_counter_ns()
    var _ns_sample_uniform = Float64(_t1_sample_uniform - _t0_sample_uniform) / Float64(N)
    print("MOJO_TIMING distributions::sample_uniform", _ns_sample_uniform, _acc_sample_uniform)
    var _result_sample_uniform = sample_uniform(0.5, 0.5)
    var _summary_sample_uniform = _summary_float64(_result_sample_uniform)
    print("MOJO_RESULT distributions::sample_uniform", _summary_sample_uniform)
    var _acc_sample_triangular: Float64 = 0.0
    var _t0_sample_triangular = perf_counter_ns()
    for _ in range(N):
        _acc_sample_triangular += sample_triangular(0.5, 0.5, 0.5)
    var _t1_sample_triangular = perf_counter_ns()
    var _ns_sample_triangular = Float64(_t1_sample_triangular - _t0_sample_triangular) / Float64(N)
    print("MOJO_TIMING distributions::sample_triangular", _ns_sample_triangular, _acc_sample_triangular)
    var _result_sample_triangular = sample_triangular(0.5, 0.5, 0.5)
    var _summary_sample_triangular = _summary_float64(_result_sample_triangular)
    print("MOJO_RESULT distributions::sample_triangular", _summary_sample_triangular)
    var _acc_sample_lognormal: Float64 = 0.0
    var _t0_sample_lognormal = perf_counter_ns()
    for _ in range(N):
        _acc_sample_lognormal += sample_lognormal(0.5, 0.5)
    var _t1_sample_lognormal = perf_counter_ns()
    var _ns_sample_lognormal = Float64(_t1_sample_lognormal - _t0_sample_lognormal) / Float64(N)
    print("MOJO_TIMING distributions::sample_lognormal", _ns_sample_lognormal, _acc_sample_lognormal)
    var _result_sample_lognormal = sample_lognormal(0.5, 0.5)
    var _summary_sample_lognormal = _summary_float64(_result_sample_lognormal)
    print("MOJO_RESULT distributions::sample_lognormal", _summary_sample_lognormal)
    var _acc_sample_exponential: Float64 = 0.0
    var _t0_sample_exponential = perf_counter_ns()
    for _ in range(N):
        _acc_sample_exponential += sample_exponential(0.5)
    var _t1_sample_exponential = perf_counter_ns()
    var _ns_sample_exponential = Float64(_t1_sample_exponential - _t0_sample_exponential) / Float64(N)
    print("MOJO_TIMING distributions::sample_exponential", _ns_sample_exponential, _acc_sample_exponential)
    var _result_sample_exponential = sample_exponential(0.5)
    var _summary_sample_exponential = _summary_float64(_result_sample_exponential)
    print("MOJO_RESULT distributions::sample_exponential", _summary_sample_exponential)
    var _acc_sample_weibull: Float64 = 0.0
    var _t0_sample_weibull = perf_counter_ns()
    for _ in range(N):
        _acc_sample_weibull += sample_weibull(0.5, 0.5)
    var _t1_sample_weibull = perf_counter_ns()
    var _ns_sample_weibull = Float64(_t1_sample_weibull - _t0_sample_weibull) / Float64(N)
    print("MOJO_TIMING distributions::sample_weibull", _ns_sample_weibull, _acc_sample_weibull)
    var _result_sample_weibull = sample_weibull(0.5, 0.5)
    var _summary_sample_weibull = _summary_float64(_result_sample_weibull)
    print("MOJO_RESULT distributions::sample_weibull", _summary_sample_weibull)
    var _acc_sample_gamma_mt: Float64 = 0.0
    var _t0_sample_gamma_mt = perf_counter_ns()
    for _ in range(N):
        _acc_sample_gamma_mt += sample_gamma_mt(0.5, 0.5)
    var _t1_sample_gamma_mt = perf_counter_ns()
    var _ns_sample_gamma_mt = Float64(_t1_sample_gamma_mt - _t0_sample_gamma_mt) / Float64(N)
    print("MOJO_TIMING distributions::sample_gamma_mt", _ns_sample_gamma_mt, _acc_sample_gamma_mt)
    var _result_sample_gamma_mt = sample_gamma_mt(0.5, 0.5)
    var _summary_sample_gamma_mt = _summary_float64(_result_sample_gamma_mt)
    print("MOJO_RESULT distributions::sample_gamma_mt", _summary_sample_gamma_mt)
    var _acc_sample_beta: Float64 = 0.0
    var _t0_sample_beta = perf_counter_ns()
    for _ in range(N):
        _acc_sample_beta += sample_beta(0.5, 0.5)
    var _t1_sample_beta = perf_counter_ns()
    var _ns_sample_beta = Float64(_t1_sample_beta - _t0_sample_beta) / Float64(N)
    print("MOJO_TIMING distributions::sample_beta", _ns_sample_beta, _acc_sample_beta)
    var _result_sample_beta = sample_beta(0.5, 0.5)
    var _summary_sample_beta = _summary_float64(_result_sample_beta)
    print("MOJO_RESULT distributions::sample_beta", _summary_sample_beta)
    var _acc_sample_pert: Float64 = 0.0
    var _t0_sample_pert = perf_counter_ns()
    for _ in range(N):
        _acc_sample_pert += sample_pert(0.5, 0.5, 0.5, 0.5)
    var _t1_sample_pert = perf_counter_ns()
    var _ns_sample_pert = Float64(_t1_sample_pert - _t0_sample_pert) / Float64(N)
    print("MOJO_TIMING distributions::sample_pert", _ns_sample_pert, _acc_sample_pert)
    var _result_sample_pert = sample_pert(0.5, 0.5, 0.5, 0.5)
    var _summary_sample_pert = _summary_float64(_result_sample_pert)
    print("MOJO_RESULT distributions::sample_pert", _summary_sample_pert)
    var _acc_sample_bernoulli: Float64 = 0.0
    var _t0_sample_bernoulli = perf_counter_ns()
    for _ in range(N):
        _acc_sample_bernoulli += sample_bernoulli(0.5)
    var _t1_sample_bernoulli = perf_counter_ns()
    var _ns_sample_bernoulli = Float64(_t1_sample_bernoulli - _t0_sample_bernoulli) / Float64(N)
    print("MOJO_TIMING distributions::sample_bernoulli", _ns_sample_bernoulli, _acc_sample_bernoulli)
    var _result_sample_bernoulli = sample_bernoulli(0.5)
    var _summary_sample_bernoulli = _summary_float64(_result_sample_bernoulli)
    print("MOJO_RESULT distributions::sample_bernoulli", _summary_sample_bernoulli)
    var _acc_sample_poisson: Float64 = 0.0
    var _t0_sample_poisson = perf_counter_ns()
    for _ in range(N):
        _acc_sample_poisson += sample_poisson(0.5)
    var _t1_sample_poisson = perf_counter_ns()
    var _ns_sample_poisson = Float64(_t1_sample_poisson - _t0_sample_poisson) / Float64(N)
    print("MOJO_TIMING distributions::sample_poisson", _ns_sample_poisson, _acc_sample_poisson)
    var _result_sample_poisson = sample_poisson(0.5)
    var _summary_sample_poisson = _summary_float64(_result_sample_poisson)
    print("MOJO_RESULT distributions::sample_poisson", _summary_sample_poisson)
    var _acc_sample_student_t: Float64 = 0.0
    var _t0_sample_student_t = perf_counter_ns()
    for _ in range(N):
        _acc_sample_student_t += sample_student_t(0.5, 0.5, 0.5)
    var _t1_sample_student_t = perf_counter_ns()
    var _ns_sample_student_t = Float64(_t1_sample_student_t - _t0_sample_student_t) / Float64(N)
    print("MOJO_TIMING distributions::sample_student_t", _ns_sample_student_t, _acc_sample_student_t)
    var _result_sample_student_t = sample_student_t(0.5, 0.5, 0.5)
    var _summary_sample_student_t = _summary_float64(_result_sample_student_t)
    print("MOJO_RESULT distributions::sample_student_t", _summary_sample_student_t)
    var _acc_sample_cauchy: Float64 = 0.0
    var _t0_sample_cauchy = perf_counter_ns()
    for _ in range(N):
        _acc_sample_cauchy += sample_cauchy(0.5, 0.5)
    var _t1_sample_cauchy = perf_counter_ns()
    var _ns_sample_cauchy = Float64(_t1_sample_cauchy - _t0_sample_cauchy) / Float64(N)
    print("MOJO_TIMING distributions::sample_cauchy", _ns_sample_cauchy, _acc_sample_cauchy)
    var _result_sample_cauchy = sample_cauchy(0.5, 0.5)
    var _summary_sample_cauchy = _summary_float64(_result_sample_cauchy)
    print("MOJO_RESULT distributions::sample_cauchy", _summary_sample_cauchy)
    var _acc_sample_laplace: Float64 = 0.0
    var _t0_sample_laplace = perf_counter_ns()
    for _ in range(N):
        _acc_sample_laplace += sample_laplace(0.5, 0.5)
    var _t1_sample_laplace = perf_counter_ns()
    var _ns_sample_laplace = Float64(_t1_sample_laplace - _t0_sample_laplace) / Float64(N)
    print("MOJO_TIMING distributions::sample_laplace", _ns_sample_laplace, _acc_sample_laplace)
    var _result_sample_laplace = sample_laplace(0.5, 0.5)
    var _summary_sample_laplace = _summary_float64(_result_sample_laplace)
    print("MOJO_RESULT distributions::sample_laplace", _summary_sample_laplace)
    var _acc_sample_pareto: Float64 = 0.0
    var _t0_sample_pareto = perf_counter_ns()
    for _ in range(N):
        _acc_sample_pareto += sample_pareto(0.5, 0.5)
    var _t1_sample_pareto = perf_counter_ns()
    var _ns_sample_pareto = Float64(_t1_sample_pareto - _t0_sample_pareto) / Float64(N)
    print("MOJO_TIMING distributions::sample_pareto", _ns_sample_pareto, _acc_sample_pareto)
    var _result_sample_pareto = sample_pareto(0.5, 0.5)
    var _summary_sample_pareto = _summary_float64(_result_sample_pareto)
    print("MOJO_RESULT distributions::sample_pareto", _summary_sample_pareto)
    var _acc_sample_gumbel: Float64 = 0.0
    var _t0_sample_gumbel = perf_counter_ns()
    for _ in range(N):
        _acc_sample_gumbel += sample_gumbel(0.5, 0.5)
    var _t1_sample_gumbel = perf_counter_ns()
    var _ns_sample_gumbel = Float64(_t1_sample_gumbel - _t0_sample_gumbel) / Float64(N)
    print("MOJO_TIMING distributions::sample_gumbel", _ns_sample_gumbel, _acc_sample_gumbel)
    var _result_sample_gumbel = sample_gumbel(0.5, 0.5)
    var _summary_sample_gumbel = _summary_float64(_result_sample_gumbel)
    print("MOJO_RESULT distributions::sample_gumbel", _summary_sample_gumbel)
    var _acc_sample_rayleigh: Float64 = 0.0
    var _t0_sample_rayleigh = perf_counter_ns()
    for _ in range(N):
        _acc_sample_rayleigh += sample_rayleigh(0.5)
    var _t1_sample_rayleigh = perf_counter_ns()
    var _ns_sample_rayleigh = Float64(_t1_sample_rayleigh - _t0_sample_rayleigh) / Float64(N)
    print("MOJO_TIMING distributions::sample_rayleigh", _ns_sample_rayleigh, _acc_sample_rayleigh)
    var _result_sample_rayleigh = sample_rayleigh(0.5)
    var _summary_sample_rayleigh = _summary_float64(_result_sample_rayleigh)
    print("MOJO_RESULT distributions::sample_rayleigh", _summary_sample_rayleigh)
    var _acc_sample_arcsine: Float64 = 0.0
    var _t0_sample_arcsine = perf_counter_ns()
    for _ in range(N):
        _acc_sample_arcsine += sample_arcsine(0.5, 0.5)
    var _t1_sample_arcsine = perf_counter_ns()
    var _ns_sample_arcsine = Float64(_t1_sample_arcsine - _t0_sample_arcsine) / Float64(N)
    print("MOJO_TIMING distributions::sample_arcsine", _ns_sample_arcsine, _acc_sample_arcsine)
    var _result_sample_arcsine = sample_arcsine(0.5, 0.5)
    var _summary_sample_arcsine = _summary_float64(_result_sample_arcsine)
    print("MOJO_RESULT distributions::sample_arcsine", _summary_sample_arcsine)
    var _acc_sample_logistic: Float64 = 0.0
    var _t0_sample_logistic = perf_counter_ns()
    for _ in range(N):
        _acc_sample_logistic += sample_logistic(0.5, 0.5)
    var _t1_sample_logistic = perf_counter_ns()
    var _ns_sample_logistic = Float64(_t1_sample_logistic - _t0_sample_logistic) / Float64(N)
    print("MOJO_TIMING distributions::sample_logistic", _ns_sample_logistic, _acc_sample_logistic)
    var _result_sample_logistic = sample_logistic(0.5, 0.5)
    var _summary_sample_logistic = _summary_float64(_result_sample_logistic)
    print("MOJO_RESULT distributions::sample_logistic", _summary_sample_logistic)
    var _acc_sample_halfnormal: Float64 = 0.0
    var _t0_sample_halfnormal = perf_counter_ns()
    for _ in range(N):
        _acc_sample_halfnormal += sample_halfnormal(0.5)
    var _t1_sample_halfnormal = perf_counter_ns()
    var _ns_sample_halfnormal = Float64(_t1_sample_halfnormal - _t0_sample_halfnormal) / Float64(N)
    print("MOJO_TIMING distributions::sample_halfnormal", _ns_sample_halfnormal, _acc_sample_halfnormal)
    var _result_sample_halfnormal = sample_halfnormal(0.5)
    var _summary_sample_halfnormal = _summary_float64(_result_sample_halfnormal)
    print("MOJO_RESULT distributions::sample_halfnormal", _summary_sample_halfnormal)
    var _acc_acos_approx: Float64 = 0.0
    var _t0_acos_approx = perf_counter_ns()
    for _ in range(N):
        _acc_acos_approx += acos_approx(0.5)
    var _t1_acos_approx = perf_counter_ns()
    var _ns_acos_approx = Float64(_t1_acos_approx - _t0_acos_approx) / Float64(N)
    print("MOJO_TIMING distributions::acos_approx", _ns_acos_approx, _acc_acos_approx)
    var _result_acos_approx = acos_approx(0.5)
    var _summary_acos_approx = _summary_float64(_result_acos_approx)
    print("MOJO_RESULT distributions::acos_approx", _summary_acos_approx)
    var _acc_sample_vonmises: Float64 = 0.0
    var _t0_sample_vonmises = perf_counter_ns()
    for _ in range(N):
        _acc_sample_vonmises += sample_vonmises(0.5, 0.5)
    var _t1_sample_vonmises = perf_counter_ns()
    var _ns_sample_vonmises = Float64(_t1_sample_vonmises - _t0_sample_vonmises) / Float64(N)
    print("MOJO_TIMING distributions::sample_vonmises", _ns_sample_vonmises, _acc_sample_vonmises)
    var _result_sample_vonmises = sample_vonmises(0.5, 0.5)
    var _summary_sample_vonmises = _summary_float64(_result_sample_vonmises)
    print("MOJO_RESULT distributions::sample_vonmises", _summary_sample_vonmises)
    var _acc_sample_neg_binomial: Float64 = 0.0
    var _t0_sample_neg_binomial = perf_counter_ns()
    for _ in range(N):
        _acc_sample_neg_binomial += sample_neg_binomial(0.5, 0.5)
    var _t1_sample_neg_binomial = perf_counter_ns()
    var _ns_sample_neg_binomial = Float64(_t1_sample_neg_binomial - _t0_sample_neg_binomial) / Float64(N)
    print("MOJO_TIMING distributions::sample_neg_binomial", _ns_sample_neg_binomial, _acc_sample_neg_binomial)
    var _result_sample_neg_binomial = sample_neg_binomial(0.5, 0.5)
    var _summary_sample_neg_binomial = _summary_float64(_result_sample_neg_binomial)
    print("MOJO_RESULT distributions::sample_neg_binomial", _summary_sample_neg_binomial)
    var _acc_sample_hypergeometric: Float64 = 0.0
    var _t0_sample_hypergeometric = perf_counter_ns()
    for _ in range(N):
        _acc_sample_hypergeometric += sample_hypergeometric(0.5, 0.5, 0.5)
    var _t1_sample_hypergeometric = perf_counter_ns()
    var _ns_sample_hypergeometric = Float64(_t1_sample_hypergeometric - _t0_sample_hypergeometric) / Float64(N)
    print("MOJO_TIMING distributions::sample_hypergeometric", _ns_sample_hypergeometric, _acc_sample_hypergeometric)
    var _result_sample_hypergeometric = sample_hypergeometric(0.5, 0.5, 0.5)
    var _summary_sample_hypergeometric = _summary_float64(_result_sample_hypergeometric)
    print("MOJO_RESULT distributions::sample_hypergeometric", _summary_sample_hypergeometric)
    var _acc_sample_one: Float64 = 0.0
    var _t0_sample_one = perf_counter_ns()
    for _ in range(N):
        _acc_sample_one += sample_one(5, 0.5, 0.5, 0.5, 0.5, _lf5, _lf5)
    var _t1_sample_one = perf_counter_ns()
    var _ns_sample_one = Float64(_t1_sample_one - _t0_sample_one) / Float64(N)
    print("MOJO_TIMING distributions::sample_one", _ns_sample_one, _acc_sample_one)
    var _result_sample_one = sample_one(5, 0.5, 0.5, 0.5, 0.5, _lf5, _lf5)
    var _summary_sample_one = _summary_float64(_result_sample_one)
    print("MOJO_RESULT distributions::sample_one", _summary_sample_one)
