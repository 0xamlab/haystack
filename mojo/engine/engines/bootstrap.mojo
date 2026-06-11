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

    # Per-replicate work is specialized by statistic so only what each one needs
    # is computed (results are identical — same RNG draw sequence per replicate):
    #   median        — needs the full sorted resample (buffer + sort);
    #   std / sharpe   — need a buffer for the numerically-stable two-pass variance
    #                    (the one-pass form cancels catastrophically on large-mean
    #                    data like financial series);
    #   mean/sum/min/max/range — computed in a single fused pass while drawing, with
    #                    no per-replicate buffer, no sort, and no separate mean pass.
    var nf = Float64(n_data)
    var outcomes = List[Float64](capacity=runs)

    if stat_code == 1 or stat_code == 2 or stat_code == 6:
        var resamp = List[Float64](capacity=n_data)
        for _ in range(n_data):
            resamp.append(0.0)
        for _ in range(runs):
            for j in range(n_data):
                var idx = Int(random_float64() * nf)
                if idx >= n_data: idx = n_data - 1
                resamp[j] = data[idx]
            if stat_code == 1:
                fast_sort(resamp, n_data)
                outcomes.append(pctile(resamp, n_data, 50))
            else:
                var r_mean = compute_mean(resamp, n_data)
                var std_v = sqrt(compute_variance(resamp, n_data, r_mean))
                if stat_code == 2: outcomes.append(std_v)
                else: outcomes.append(r_mean / std_v if std_v > 0.0 else 0.0)
    elif stat_code == 4 or stat_code == 5 or stat_code == 7:
        for _ in range(runs):
            var mn: Float64 = 0.0
            var mx: Float64 = 0.0
            for j in range(n_data):
                var idx = Int(random_float64() * nf)
                if idx >= n_data: idx = n_data - 1
                var x = data[idx]
                if j == 0:
                    mn = x
                    mx = x
                else:
                    if x < mn: mn = x
                    if x > mx: mx = x
            if stat_code == 4: outcomes.append(mn)
            elif stat_code == 5: outcomes.append(mx)
            else: outcomes.append(mx - mn)
    else:
        for _ in range(runs):
            var s: Float64 = 0.0
            for _ in range(n_data):
                var idx = Int(random_float64() * nf)
                if idx >= n_data: idx = n_data - 1
                s += data[idx]
            if stat_code == 3: outcomes.append(s)
            else: outcomes.append(s / nf)

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
