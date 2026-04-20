"""
mcmc.mojo — Metropolis-Hastings Bayesian MCMC engine.
Extracted from main.mojo (Phase 7). Accepts SimRequest typed struct.
"""
from std.random import random_float64, randn_float64
from std.math import sqrt, log, abs as fabs

from types  import SimRequest
from stats  import compute_mean, compute_variance, pctile, fast_sort
from output import build_output


def run_mcmc(req: SimRequest) raises -> String:
    """Metropolis-Hastings MCMC with multiple chains."""
    var runs = req.runs
    var w_ev = req.scoring.w_ev
    var w_dr = req.scoring.w_dr

    if not req.has_mcmc_cfg:
        return '{"error":"mcmc_config required for mcmc engine"}'

    var mcc    = req.mcmc_cfg.copy()
    var n_data = mcc.n_data
    if n_data == 0:
        return '{"error":"mcmc_config.observed_data required"}'

    var data       = mcc.observed_data.copy()
    var burn_in    = mcc.burn_in
    var n_chains   = mcc.n_chains
    var lik_str    = mcc.likelihood
    var lik_type   = 1 if lik_str == "lognormal" else 0

    var d_mean: Float64 = 0.0
    for i in range(n_data): d_mean += data[i]
    d_mean /= Float64(max(n_data, 1))
    var d_var: Float64 = 0.0
    for i in range(n_data):
        var dv = data[i] - d_mean; d_var += dv * dv
    d_var /= Float64(max(n_data - 1, 1))
    var d_std = sqrt(d_var) if d_var > 0.0 else 1.0

    var LOG2PI: Float64 = 0.9189385332
    var all_mu    = List[Float64]()
    var all_sigma = List[Float64]()
    var total_accepted: Int = 0
    var total_steps: Int    = 0

    for _ in range(n_chains):
        var cur_mu    = d_mean + randn_float64() * d_std * 0.1
        var cur_sigma = d_std * (0.8 + 0.4 * random_float64())
        if cur_sigma <= 0.0: cur_sigma = d_std
        var step_mu  = d_std * 0.1; var step_sig = d_std * 0.05
        var accepted: Int = 0

        var z0 = (cur_mu - d_mean) / max(d_std * 3.0, 1e-10)
        var cur_lp: Float64 = -0.5 * z0 * z0
        if cur_sigma < d_std * 0.1 or cur_sigma > d_std * 10.0: cur_lp = -1e30
        var ll0: Float64 = 0.0
        for i in range(n_data):
            var x = data[i]; var z = (x - cur_mu) / max(cur_sigma, 1e-10)
            if lik_type == 0: ll0 += -0.5 * z * z - log(cur_sigma) - LOG2PI
            elif x > 0.0:
                var lz = (log(x) - cur_mu) / max(cur_sigma, 1e-10)
                ll0 += -0.5 * lz * lz - log(cur_sigma) - log(x) - LOG2PI
            else: ll0 = -1e30; break
        cur_lp += ll0

        for iter in range(runs + burn_in):
            var prop_mu    = cur_mu + randn_float64() * step_mu
            var prop_sigma = fabs(cur_sigma + randn_float64() * step_sig) + 1e-10
            var zm = (prop_mu - d_mean) / max(d_std * 3.0, 1e-10)
            var prop_lp: Float64 = -0.5 * zm * zm
            if prop_sigma < d_std * 0.01 or prop_sigma > d_std * 20.0: prop_lp = -1e30
            if prop_lp > -1e29:
                var ll: Float64 = 0.0
                for i in range(n_data):
                    var x = data[i]; var z = (x - prop_mu) / prop_sigma
                    if lik_type == 0: ll += -0.5 * z * z - log(prop_sigma) - LOG2PI
                    elif x > 0.0:
                        var lz = (log(x) - prop_mu) / prop_sigma
                        ll += -0.5 * lz * lz - log(prop_sigma) - log(x) - LOG2PI
                    else: ll = -1e30; break
                prop_lp += ll
            var log_u = log(max(random_float64(), 1e-300))
            if log_u < prop_lp - cur_lp:
                cur_mu = prop_mu; cur_sigma = prop_sigma; cur_lp = prop_lp; accepted += 1
            if iter > 0 and iter % 200 == 0:
                var ar = Float64(accepted) / Float64(iter + 1)
                if ar > 0.44: step_mu *= 1.1; step_sig *= 1.1
                elif ar < 0.10: step_mu *= 0.9; step_sig *= 0.9
            if iter >= burn_in: all_mu.append(cur_mu); all_sigma.append(cur_sigma)
        total_accepted += accepted; total_steps += runs + burn_in

    var n_out     = len(all_mu)
    var sorted_mu  = all_mu.copy();    fast_sort(sorted_mu,  n_out)
    var sorted_sig = all_sigma.copy(); fast_sort(sorted_sig, n_out)
    var mu_mean   = compute_mean(sorted_mu,  n_out)
    var sig_mean  = compute_mean(sorted_sig, n_out)
    var acc_rate  = Float64(total_accepted) / Float64(max(total_steps, 1))

    var mcmc_json = ('"simulation_model":"mcmc"'
        + ',"mcmc_result":{"n_chains":' + String(n_chains)
        + ',"n_samples_per_chain":' + String(runs)
        + ',"burn_in":' + String(burn_in)
        + ',"total_samples":' + String(n_out)
        + ',"acceptance_rate":' + String(acc_rate)
        + ',"n_observations":' + String(n_data)
        + ',"likelihood":"' + lik_str + '"'
        + ',"posterior":{'
        + '"mean":{"mean":' + String(mu_mean)
        + ',"std":' + String(sqrt(compute_variance(sorted_mu, n_out, mu_mean)))
        + ',"hdi_lower":' + String(pctile(sorted_mu, n_out, 2))
        + ',"hdi_upper":' + String(pctile(sorted_mu, n_out, 97)) + '}'
        + ',"sigma":{"mean":' + String(sig_mean)
        + ',"std":' + String(sqrt(compute_variance(sorted_sig, n_out, sig_mean)))
        + ',"hdi_lower":' + String(pctile(sorted_sig, n_out, 2))
        + ',"hdi_upper":' + String(pctile(sorted_sig, n_out, 97)) + '}'
        + '},"converged":' + ("true" if acc_rate > 0.05 and acc_rate < 0.9 else "false") + '}')
    return build_output(sorted_mu, n_out, "0.7.0-mojo-mcmc-mh", "mcmc", "mcmc", w_ev, w_dr, mcmc_json)
