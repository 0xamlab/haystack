"""
request_parser.mojo — Pure Mojo JSON parsing for JSON → SimRequest.

Zero Python imports. All JSON field extraction uses the native Mojo JSON
parser (json/parser.mojo) and number conversion library (conv.mojo).

Phase 5 implementation: replaces the Python json.loads() boundary with
schema-aware native byte-level parsing. No PythonObject is created or
used anywhere in this module.
"""
from std.random import seed as set_seed

from types import (
    SimRequest, VarSpec, CorrSpec, ScoringSpec,
    TimeSeriesCfg, DecisionTreeCfg, ISCfg, ScenarioCfg, BootstrapCfg, MCMCCfg,
)
from json.parser import (
    json_get_string, json_get_float, json_get_int, json_get_bool,
    json_get_object, json_get_array, json_is_null,
    json_array_len, json_array_get,
)
from conv import parse_float64, parse_int, span_to_str, span_to_str_end


fn _unquote(s: String) -> String:
    """Strip surrounding JSON double-quotes from a raw array element string.

    json_array_get() returns the raw token including quotes for string
    elements, e.g. '"revenue"'.  This helper strips them so we get 'revenue'.
    Non-string tokens (numbers, objects) are returned unchanged.
    """
    var n = len(s)
    if n < 2:
        return s
    var bytes = s.as_bytes()
    if bytes[0] != UInt8(34) or bytes[n - 1] != UInt8(34):
        return s  # not a quoted string — return as-is
    var result = String("")
    var i = 1
    while i < n - 1:
        if bytes[i] == UInt8(92) and i + 1 < n - 1:  # backslash escape
            var nxt = bytes[i + 1]
            if nxt == UInt8(34):
                result += '"'
            elif nxt == UInt8(92):
                result += "\\"
            elif nxt == UInt8(110):
                result += "\n"
            elif nxt == UInt8(116):
                result += "\t"
            elif nxt == UInt8(114):
                result += "\r"
            elif nxt == UInt8(47):
                result += "/"
            else:
                result += chr(Int(nxt))
            i += 2
            continue
        result += chr(Int(bytes[i]))
        i += 1
    return result


def parse_request(raw: String) raises -> SimRequest:
    """
    Parse raw JSON string into a fully typed SimRequest.
    Pure Mojo — no Python boundary. All fields use defaults from the
    canonical schema (Phase 2) when absent.
    """
    var req = SimRequest()

    # ── Top-level scalar fields ────────────────────────────────────────────
    var et = json_get_string(raw, "engine_type")
    req.engine_type = et if len(et) > 0 else "monte_carlo"
    req.runs = json_get_int(raw, "runs", 10000)
    if req.runs < 1: req.runs = 1

    if json_is_null(raw, "seed"):
        req.seed = -1
    else:
        req.seed = json_get_int(raw, "seed", -1)
    if req.seed >= 0: set_seed(req.seed)

    req.workers          = json_get_int(raw, "workers", 0)
    req.stream_mode      = json_get_bool(raw, "stream", False)
    req.checkpoint_every = json_get_int(raw, "checkpoint_every", 1000)
    if req.checkpoint_every < 100: req.checkpoint_every = 100

    # ── Scoring weights ────────────────────────────────────────────────────
    var scoring_str = json_get_object(raw, "scoring")
    if len(scoring_str) > 2:  # "{}" is 2 chars — empty object
        req.scoring = ScoringSpec(
            json_get_float(scoring_str, "expected_value", 0.6),
            json_get_float(scoring_str, "downside_risk",  0.4),
        )

    # ── Variables ──────────────────────────────────────────────────────────
    var variables_str = json_get_array(raw, "variables")
    req.n_vars = json_array_len(variables_str)
    var disc_counter: Int = 0

    for i in range(req.n_vars):
        var v_str = json_array_get(variables_str, i)
        var nm = json_get_string(v_str, "name")
        var di = json_get_string(v_str, "distribution")
        var params_str = json_get_object(v_str, "params")
        req.vnames.append(nm)

        var p0_v: Float64 = 0.0; var p1_v: Float64 = 0.0
        var p2_v: Float64 = 0.0; var p3_v: Float64 = 0.0
        var dt_v: Int
        var disc_idx: Int = -1

        if di == "normal":
            dt_v = 0; p0_v = json_get_float(params_str, "mean", 0.0); p1_v = json_get_float(params_str, "std", 0.0)
        elif di == "uniform":
            dt_v = 1; p0_v = json_get_float(params_str, "low", 0.0);  p1_v = json_get_float(params_str, "high", 0.0)
        elif di == "triangular":
            dt_v = 2; p0_v = json_get_float(params_str, "low", 0.0);  p1_v = json_get_float(params_str, "mode", 0.0)
            p2_v = json_get_float(params_str, "high", 0.0)
        elif di == "lognormal":
            dt_v = 3; p0_v = json_get_float(params_str, "mean", 0.0); p1_v = json_get_float(params_str, "std", 0.0)
        elif di == "beta":
            dt_v = 5; p0_v = json_get_float(params_str, "alpha", 2.0); p1_v = json_get_float(params_str, "beta", 2.0)
        elif di == "exponential":
            dt_v = 7; p0_v = json_get_float(params_str, "rate", 1.0)
        elif di == "weibull":
            dt_v = 8; p0_v = json_get_float(params_str, "shape", 1.0); p1_v = json_get_float(params_str, "scale", 1.0)
        elif di == "gamma":
            dt_v = 9; p0_v = json_get_float(params_str, "shape", 1.0); p1_v = json_get_float(params_str, "scale", 1.0)
        elif di == "pert":
            dt_v = 10; p0_v = json_get_float(params_str, "low", 0.0);    p1_v = json_get_float(params_str, "likely", 0.5)
            p2_v = json_get_float(params_str, "high", 1.0); p3_v = json_get_float(params_str, "gamma", 4.0)
        elif di == "bernoulli":
            dt_v = 11; p0_v = json_get_float(params_str, "p", 0.5)
        elif di == "poisson":
            dt_v = 12; p0_v = json_get_float(params_str, "lambda", 1.0)
        elif di == "discrete":
            dt_v = 13; disc_idx = disc_counter; disc_counter += 1
            var vp_str = json_get_array(params_str, "values")
            var pp_str = json_get_array(params_str, "probabilities")
            var nv = json_array_len(vp_str)
            var vl = List[Float64](capacity=nv); var pl = List[Float64](capacity=nv)
            var cum: Float64 = 0.0
            for j in range(nv):
                vl.append(parse_float64(json_array_get(vp_str, j)))
                cum += parse_float64(json_array_get(pp_str, j))
                pl.append(cum)
            req.disc_vals.append(vl.copy()); req.disc_probs.append(pl.copy())
        elif di == "student_t":
            dt_v = 14; p0_v = json_get_float(params_str, "df", 5.0)
            p1_v = json_get_float(params_str, "loc", 0.0); p2_v = json_get_float(params_str, "scale", 1.0)
        elif di == "cauchy":
            dt_v = 15; p0_v = json_get_float(params_str, "location", 0.0); p1_v = json_get_float(params_str, "scale", 1.0)
        elif di == "laplace":
            dt_v = 16; p0_v = json_get_float(params_str, "mu", 0.0); p1_v = json_get_float(params_str, "b", 1.0)
        elif di == "pareto":
            dt_v = 17; p0_v = json_get_float(params_str, "alpha", 1.0); p1_v = json_get_float(params_str, "x_min", 1.0)
        elif di == "gumbel":
            dt_v = 18; p0_v = json_get_float(params_str, "mu", 0.0); p1_v = json_get_float(params_str, "beta", 1.0)
        elif di == "rayleigh":
            dt_v = 19; p0_v = json_get_float(params_str, "sigma", 1.0)
        elif di == "arcsine":
            dt_v = 20; p0_v = json_get_float(params_str, "low", 0.0); p1_v = json_get_float(params_str, "high", 1.0)
        elif di == "logistic":
            dt_v = 21; p0_v = json_get_float(params_str, "mu", 0.0); p1_v = json_get_float(params_str, "scale", 1.0)
        elif di == "halfnormal":
            dt_v = 22; p0_v = json_get_float(params_str, "sigma", 1.0)
        elif di == "vonmises":
            dt_v = 23; p0_v = json_get_float(params_str, "mu", 0.0); p1_v = json_get_float(params_str, "kappa", 1.0)
        elif di == "neg_binomial" or di == "negative_binomial":
            dt_v = 24; p0_v = json_get_float(params_str, "r", 1.0); p1_v = json_get_float(params_str, "p", 0.5)
        elif di == "hypergeometric":
            dt_v = 25; p0_v = json_get_float(params_str, "N", 100.0); p1_v = json_get_float(params_str, "K", 50.0)
            p2_v = json_get_float(params_str, "n", 10.0)
        elif di == "categorical":
            dt_v = 26; disc_idx = disc_counter; disc_counter += 1
            var vp2_str = json_get_array(params_str, "probabilities")
            var nv2 = json_array_len(vp2_str)
            var vl2 = List[Float64](capacity=nv2); var pl2 = List[Float64](capacity=nv2)
            var cum2: Float64 = 0.0
            for j in range(nv2):
                vl2.append(Float64(j))
                cum2 += parse_float64(json_array_get(vp2_str, j))
                pl2.append(cum2)
            req.disc_vals.append(vl2.copy()); req.disc_probs.append(pl2.copy())
        else:  # fixed / fallback
            dt_v = 4; p0_v = json_get_float(params_str, "value", 0.0)

        req.dt.append(dt_v); req.p0.append(p0_v)
        req.p1.append(p1_v); req.p2.append(p2_v); req.p3.append(p3_v)
        req.vars.append(VarSpec(nm, dt_v, p0_v, p1_v, p2_v, p3_v, disc_idx))

    # ── Correlations ───────────────────────────────────────────────────────
    var corr_str = json_get_array(raw, "correlations")
    req.n_corr = json_array_len(corr_str)
    for k in range(req.n_corr):
        var entry_str = json_array_get(corr_str, k)
        var vars_pair_str = json_get_array(entry_str, "variables")
        if json_array_len(vars_pair_str) < 2: continue
        var v1   = _unquote(json_array_get(vars_pair_str, 0))
        var v2   = _unquote(json_array_get(vars_pair_str, 1))
        var coef = json_get_float(entry_str, "coefficient", 0.0)
        var i1   = -1; var i2 = -1
        for ni in range(req.n_vars):
            if req.vnames[ni] == v1: i1 = ni
            if req.vnames[ni] == v2: i2 = ni
        if i1 >= 0 and i2 >= 0:
            req.corrs.append(CorrSpec(i1, i2, coef))

    # ── Objective functions ────────────────────────────────────────────────
    req.obj_fn = json_get_string(raw, "objective_function")

    if len(req.obj_fn) > 0:
        var cur_start = 0
        var pipe      = UInt8(ord("|"))
        var obj_bytes = req.obj_fn.as_bytes()
        for ci in range(len(req.obj_fn)):
            if obj_bytes[ci] == pipe:
                var seg = span_to_str(req.obj_fn, cur_start, ci)
                req.obj_fns.append(String(seg.strip()))
                cur_start = ci + 1
        var seg_last = span_to_str_end(req.obj_fn, cur_start)
        req.obj_fns.append(String(seg_last.strip()))
    else:
        req.obj_fns.append("")
    req.n_objectives = len(req.obj_fns)

    # ── Engine-specific config blocks ─────────────────────────────────────

    # Time Series
    var ts_str = json_get_object(raw, "time_series_config")
    if len(ts_str) > 2:
        req.has_time_series_cfg = True
        var tsc = TimeSeriesCfg()
        var ts_model = json_get_string(ts_str, "model")
        tsc.model         = ts_model if len(ts_model) > 0 else "gbm"
        tsc.initial_value = json_get_float(ts_str, "initial_value", 100.0)
        tsc.drift         = json_get_float(ts_str, "drift", 0.0)
        tsc.volatility    = json_get_float(ts_str, "volatility", 0.20)
        tsc.dt            = json_get_float(ts_str, "dt", 1.0 / 12.0)
        tsc.ou_theta      = json_get_float(ts_str, "ou_theta", 0.5)
        tsc.ou_mu         = json_get_float(ts_str, "ou_mu", tsc.initial_value)
        tsc.autocorr      = json_get_float(ts_str, "autocorrelation", 0.0)
        var ts_gran = json_get_string(ts_str, "granularity")
        tsc.granularity   = ts_gran if len(ts_gran) > 0 else "month"
        var h_str = json_get_array(ts_str, "horizons")
        var n_h = json_array_len(h_str)
        if n_h == 0:
            tsc.horizons.append(1)  # default [1]
        else:
            for i in range(n_h):
                tsc.horizons.append(parse_int(json_array_get(h_str, i)))
        var pct_str = json_get_array(ts_str, "pct_levels")
        var n_pct = json_array_len(pct_str)
        if n_pct == 0:
            # defaults: [5, 10, 25, 50, 75, 90, 95]
            tsc.pct_levels.append(5)
            tsc.pct_levels.append(10)
            tsc.pct_levels.append(25)
            tsc.pct_levels.append(50)
            tsc.pct_levels.append(75)
            tsc.pct_levels.append(90)
            tsc.pct_levels.append(95)
        else:
            for i in range(n_pct):
                tsc.pct_levels.append(parse_int(json_array_get(pct_str, i)))
        req.time_series_cfg = tsc^

    # Decision Tree — store raw JSON for re-parsing inside engine
    var dt_str = json_get_object(raw, "decision_tree_config")
    if len(dt_str) > 2:
        req.has_decision_tree_cfg = True
        req.decision_tree_cfg = DecisionTreeCfg(dt_str)

    # Importance Sampling
    var is_str = json_get_object(raw, "importance_sampling_config")
    if len(is_str) > 2:
        req.has_is_cfg = True
        var isc = ISCfg()
        isc.target_threshold = json_get_float(is_str, "target_threshold", -1e30)
        var is_dir = json_get_string(is_str, "tail_direction")
        isc.tail_direction   = is_dir if len(is_dir) > 0 else "lower"
        var is_tvar = json_get_string(is_str, "tilt_variable")
        isc.tilt_var_name    = is_tvar  # "" if absent is fine
        isc.tilt_override    = json_get_float(is_str, "tilt_sigma", 0.0)
        req.is_cfg = isc^

    # Scenario — store raw JSON for re-parsing inside engine
    var sc_str = json_get_object(raw, "scenario_config")
    if len(sc_str) > 2:
        req.has_scenario_cfg = True
        req.scenario_cfg = ScenarioCfg(sc_str)

    # Bootstrap
    var bs_str = json_get_object(raw, "bootstrap_config")
    if len(bs_str) > 2:
        req.has_bootstrap_cfg = True
        var bsc = BootstrapCfg()
        var bs_stat = json_get_string(bs_str, "statistic")
        bsc.statistic = bs_stat if len(bs_stat) > 0 else "mean"
        var hist_str = json_get_array(bs_str, "historical_data")
        bsc.n_data = json_array_len(hist_str)
        for i in range(bsc.n_data):
            bsc.historical_data.append(parse_float64(json_array_get(hist_str, i)))
        req.bootstrap_cfg = bsc^

    # MCMC
    var mc_str = json_get_object(raw, "mcmc_config")
    if len(mc_str) > 2:
        req.has_mcmc_cfg = True
        var mcc = MCMCCfg()
        mcc.burn_in    = json_get_int(mc_str, "burn_in", 1000)
        mcc.n_chains   = json_get_int(mc_str, "chains", 4)
        var mc_like = json_get_string(mc_str, "likelihood")
        mcc.likelihood = mc_like if len(mc_like) > 0 else "normal"
        var obs_str = json_get_array(mc_str, "observed_data")
        mcc.n_data = json_array_len(obs_str)
        for i in range(mcc.n_data):
            mcc.observed_data.append(parse_float64(json_array_get(obs_str, i)))
        req.mcmc_cfg = mcc^

    return req^
