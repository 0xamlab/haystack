"""
Multi-Horizon Time Series Simulation — pure Mojo hot loop.
Phase 3 refactor: accepts SimRequest instead of PythonObject cfg.
All time series config read from req.time_series_cfg (typed struct, no PythonObject).
"""
from std.random import randn_float64
from std.math import sqrt, exp, log, abs as fabs

from types  import SimRequest
from stats  import compute_mean, compute_variance, pctile, fast_sort


def run_time_series(req: SimRequest) raises -> String:
    """
    Time series simulation: GBM, OU, arithmetic, compound models.
    Reads all config from req.time_series_cfg — no PythonObject in hot loop.
    """
    var runs = req.runs
    var w_ev = req.scoring.w_ev
    var w_dr = req.scoring.w_dr

    if not req.has_time_series_cfg:
        return '{"error":"time_series_config required for time_series engine"}'

    var tsc      = req.time_series_cfg.copy()
    var model    = tsc.model
    var S0       = tsc.initial_value
    var drift    = tsc.drift
    var vol      = tsc.volatility
    var dt       = tsc.dt
    var ou_theta = tsc.ou_theta
    var ou_mu    = tsc.ou_mu
    var autocorr = tsc.autocorr
    var gran     = tsc.granularity

    var horizons  = tsc.horizons.copy()
    var n_h       = len(horizons)
    if n_h == 0:
        horizons.append(1); n_h = 1
    var T_max = horizons[0]
    for i in range(n_h):
        if horizons[i] > T_max: T_max = horizons[i]

    var pct_levels = tsc.pct_levels.copy()
    var n_pct      = len(pct_levels)
    if n_pct == 0:
        pct_levels.append(5)
        pct_levels.append(10)
        pct_levels.append(25)
        pct_levels.append(50)
        pct_levels.append(75)
        pct_levels.append(90)
        pct_levels.append(95)
        n_pct = 7

    # Horizon value buckets
    var horizon_vals  = List[List[Float64]]()
    for _ in range(n_h): horizon_vals.append(List[Float64](capacity=runs))
    var terminal_vals = List[Float64](capacity=runs)

    var dt_sqrt = sqrt(dt)
    var ac_corr = autocorr
    var ac_comp = sqrt(max(0.0, 1.0 - ac_corr * ac_corr))

    for _ in range(runs):
        var s      = S0
        var prev_z = 0.0
        for step in range(1, T_max + 1):
            var z_ind = randn_float64()
            var z     = ac_corr * prev_z + ac_comp * z_ind
            prev_z    = z
            if model == "gbm":
                s = s * exp((drift - 0.5 * vol * vol) * dt + vol * dt_sqrt * z)
            elif model == "ou":
                s = s + ou_theta * (ou_mu - s) * dt + vol * dt_sqrt * z
            elif model == "arithmetic" or model == "abm":
                s = s + drift * dt + vol * dt_sqrt * z
            elif model == "compound":
                var r = drift * dt + vol * dt_sqrt * z
                s = s * (1.0 + r)
            else:
                s = s * exp((drift - 0.5 * vol * vol) * dt + vol * dt_sqrt * z)
            for hi in range(n_h):
                if step == horizons[hi]:
                    horizon_vals[hi].append(s)
        terminal_vals.append(s)

    # Fan chart JSON
    var fan_chart_json = "["
    for hi in range(n_h):
        if hi > 0: fan_chart_json += ","
        var hvals = horizon_vals[hi].copy()
        var hn    = len(hvals)
        if hn == 0:
            fan_chart_json += '{"t":' + String(horizons[hi]) + '}'
            continue
        fast_sort(hvals, hn)
        var hmean = compute_mean(hvals, hn)
        var hstd  = sqrt(compute_variance(hvals, hn, hmean))
        fan_chart_json += '{"t":' + String(horizons[hi])
        fan_chart_json += ',"granularity":"' + gran + '"'
        fan_chart_json += ',"mean":' + String(hmean)
        fan_chart_json += ',"std":' + String(hstd)
        for pi in range(n_pct):
            var p = pct_levels[pi]
            fan_chart_json += ',"p' + String(p) + '":' + String(pctile(hvals, hn, p))
        var n_loss_h = 0
        for vi in range(hn):
            if hvals[vi] < S0: n_loss_h += 1
        fan_chart_json += ',"probability_of_loss":' + String(Float64(n_loss_h) / Float64(hn))
        fan_chart_json += '}'
    fan_chart_json += "]"

    var n_total = len(terminal_vals)
    fast_sort(terminal_vals, n_total)
    var t_mean = compute_mean(terminal_vals, n_total)
    var t_std  = sqrt(compute_variance(terminal_vals, n_total, t_mean))
    var n_loss = 0
    for i in range(n_total):
        if terminal_vals[i] < S0: n_loss += 1
    var prob_loss = Float64(n_loss) / Float64(n_total)

    var ts_result_json = (
        '"time_series_result":{"model":"' + model + '"'
        + ',"granularity":"' + gran + '"'
        + ',"dt_years":' + String(dt)
        + ',"initial_value":' + String(S0)
        + ',"n_steps":' + String(T_max)
        + ',"fan_chart":' + fan_chart_json
        + ',"terminal":{"mean":' + String(t_mean)
        + ',"std":' + String(t_std)
        + ',"p5":'  + String(pctile(terminal_vals, n_total, 5))
        + ',"p25":' + String(pctile(terminal_vals, n_total, 25))
        + ',"p50":' + String(pctile(terminal_vals, n_total, 50))
        + ',"p75":' + String(pctile(terminal_vals, n_total, 75))
        + ',"p95":' + String(pctile(terminal_vals, n_total, 95))
        + ',"probability_of_loss":' + String(prob_loss) + '}}'
    )

    var abs_m  = fabs(t_mean)
    var ev_n: Float64 = 0.5
    if abs_m > 0.0:
        ev_n = max(0.0, min(1.0, (t_mean + abs_m) / (2.0 * abs_m)))
    var score = w_ev * ev_n + w_dr * (1.0 - prob_loss)

    return (
        '{"_proto":1,"engine_version":"0.7.0-mojo-time-series"'
        + ',"engine_type":"time_series"'
        + ',"simulation_model":"time_series"'
        + ',"scenarios_run":' + String(n_total)
        + ',"summary":{"mean":' + String(t_mean)
        + ',"median":' + String(pctile(terminal_vals, n_total, 50))
        + ',"std":' + String(t_std)
        + ',"variance":' + String(t_std * t_std) + '}'
        + ',"percentiles":{"p5":'  + String(pctile(terminal_vals, n_total, 5))
        + ',"p10":' + String(pctile(terminal_vals, n_total, 10))
        + ',"p25":' + String(pctile(terminal_vals, n_total, 25))
        + ',"p50":' + String(pctile(terminal_vals, n_total, 50))
        + ',"p75":' + String(pctile(terminal_vals, n_total, 75))
        + ',"p90":' + String(pctile(terminal_vals, n_total, 90))
        + ',"p95":' + String(pctile(terminal_vals, n_total, 95))
        + ',"p99":' + String(pctile(terminal_vals, n_total, 99)) + '}'
        + ',"risk":{"probability_of_loss":' + String(prob_loss)
        + ',"var_95":' + String(pctile(terminal_vals, n_total, 5))
        + ',"cvar_95":' + String(pctile(terminal_vals, n_total, 2)) + '}'
        + ',"score":' + String(score)
        + ',' + ts_result_json + '}'
    )
