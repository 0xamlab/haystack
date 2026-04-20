"""
bootstrap.mojo — Non-parametric bootstrap resampling engine.
Extracted from main.mojo (Phase 7). Accepts SimRequest typed struct.
"""
from std.random import random_float64
from std.math import sqrt

from types  import SimRequest
from stats  import compute_mean, compute_variance, pctile, fast_sort
from output import build_output


def run_bootstrap(req: SimRequest) raises -> String:
    """Bootstrap resampling with configurable statistic."""
    var runs = req.runs
    var w_ev = req.scoring.w_ev
    var w_dr = req.scoring.w_dr

    if not req.has_bootstrap_cfg:
        return '{"error":"bootstrap_config required for bootstrap engine"}'

    var bsc    = req.bootstrap_cfg.copy()
    var n_data = bsc.n_data
    if n_data == 0:
        return '{"error":"bootstrap_config.historical_data required"}'

    var stat_str  = bsc.statistic
    var stat_code: Int = 0
    if stat_str == "mean":   stat_code = 0
    elif stat_str == "median": stat_code = 1
    elif stat_str == "std":    stat_code = 2
    elif stat_str == "sum":    stat_code = 3
    elif stat_str == "min":    stat_code = 4
    elif stat_str == "max":    stat_code = 5
    elif stat_str == "sharpe": stat_code = 6
    elif stat_str == "range":  stat_code = 7

    var data        = bsc.historical_data.copy()
    var data_sorted = data.copy()
    fast_sort(data_sorted, n_data)
    var obs_mean = compute_mean(data_sorted, n_data)
    var obs: Float64
    if stat_code == 0:   obs = obs_mean
    elif stat_code == 1: obs = pctile(data_sorted, n_data, 50)
    elif stat_code == 2: obs = sqrt(compute_variance(data_sorted, n_data, obs_mean))
    elif stat_code == 3: obs = obs_mean * Float64(n_data)
    elif stat_code == 4: obs = data_sorted[0]
    elif stat_code == 5: obs = data_sorted[n_data - 1]
    elif stat_code == 7: obs = data_sorted[n_data - 1] - data_sorted[0]
    else: obs = obs_mean

    var outcomes = List[Float64](capacity=runs)
    for _ in range(runs):
        var resamp = List[Float64](capacity=n_data)
        for _ in range(n_data):
            var idx = Int(random_float64() * Float64(n_data))
            if idx >= n_data: idx = n_data - 1
            resamp.append(data[idx])
        fast_sort(resamp, n_data)
        var r_mean  = compute_mean(resamp, n_data)
        var stat_val: Float64
        if stat_code == 0:   stat_val = r_mean
        elif stat_code == 1: stat_val = pctile(resamp, n_data, 50)
        elif stat_code == 2: stat_val = sqrt(compute_variance(resamp, n_data, r_mean))
        elif stat_code == 3: stat_val = r_mean * Float64(n_data)
        elif stat_code == 4: stat_val = resamp[0]
        elif stat_code == 5: stat_val = resamp[n_data - 1]
        elif stat_code == 6:
            var std_v = sqrt(compute_variance(resamp, n_data, r_mean))
            stat_val = r_mean / std_v if std_v > 0.0 else 0.0
        elif stat_code == 7: stat_val = resamp[n_data - 1] - resamp[0]
        else: stat_val = r_mean
        outcomes.append(stat_val)

    var boot_mean  = compute_mean(outcomes, runs)
    var boot_se    = sqrt(compute_variance(outcomes, runs, boot_mean))
    var sorted_out = outcomes.copy()
    fast_sort(sorted_out, runs)
    var ci_lo = pctile(sorted_out, runs, 2)
    var ci_hi = pctile(sorted_out, runs, 97)

    var bs_json = ('"simulation_model":"bootstrap"'
        + ',"bootstrap_result":{"statistic":"' + stat_str + '"'
        + ',"observed_value":' + String(obs)
        + ',"n_observations":' + String(n_data)
        + ',"n_resamples":' + String(runs)
        + ',"confidence_interval":{"lower":' + String(ci_lo) + ',"upper":' + String(ci_hi) + '}'
        + ',"bias":' + String(boot_mean - obs)
        + ',"standard_error":' + String(boot_se) + '}')
    return build_output(outcomes, runs, "0.7.0-mojo-bootstrap", "bootstrap", "bootstrap", w_ev, w_dr, bs_json)
