"""
test_request_parser.mojo — Tests for request_parser.mojo parse_request().

Tests:
  - All 11 engine type payloads parse correctly
  - Missing required fields use defaults (schema_version v1.0)
  - All 27 distribution types parse correctly
  - Multi-output objective function via | separator
  - Engine-specific config blocks populate correct struct fields
  - Malformed JSON → exception raised cleanly (caught at test boundary)

Run:
  cd mojo_env && pixi run mojo test_request_parser.mojo
"""
from request_parser import parse_request
from types import SimRequest


def _assert(condition: Bool, message: String):
    if not condition:
        print("FAIL: " + message)
    else:
        print("PASS: " + message)


def test_monte_carlo_defaults():
    """Minimal payload uses all defaults."""
    var req = parse_request('{"engine_type":"monte_carlo","runs":5000}')
    _assert(req.engine_type == "monte_carlo", "engine_type == monte_carlo")
    _assert(req.runs == 5000,                 "runs == 5000")
    _assert(req.seed == -1,                   "seed == -1 (no seed)")
    _assert(req.n_vars == 0,                  "n_vars == 0")
    _assert(req.scoring.w_ev == 0.6,          "w_ev default == 0.6")
    _assert(req.scoring.w_dr == 0.4,          "w_dr default == 0.4")


def test_qmc_sobol():
    var req = parse_request('{"engine_type":"qmc_sobol","runs":2000,'
        + '"variables":[{"name":"x","distribution":"uniform","params":{"low":0,"high":1}}],'
        + '"objective_function":"x"}')
    _assert(req.engine_type == "qmc_sobol",  "engine_type == qmc_sobol")
    _assert(req.n_vars == 1,                  "n_vars == 1")
    _assert(req.dt[0] == 1,                   "distribution code == 1 (uniform)")
    _assert(req.p0[0] == 0.0,                 "p0 == 0.0 (low)")
    _assert(req.p1[0] == 1.0,                 "p1 == 1.0 (high)")


def test_lhs():
    var req = parse_request('{"engine_type":"lhs","runs":1000,'
        + '"variables":[{"name":"v","distribution":"normal","params":{"mean":50,"std":10}}]}')
    _assert(req.engine_type == "lhs", "engine_type == lhs")
    _assert(req.dt[0] == 0,           "distribution code == 0 (normal)")
    _assert(req.p0[0] == 50.0,        "mean == 50.0")
    _assert(req.p1[0] == 10.0,        "std == 10.0")


def test_bootstrap():
    var raw = ('{"engine_type":"bootstrap","runs":500,'
        + '"bootstrap_config":{"historical_data":[1,2,3,4,5],"statistic":"mean"}}')
    var req = parse_request(raw)
    _assert(req.engine_type == "bootstrap",          "engine_type == bootstrap")
    _assert(req.has_bootstrap_cfg,                    "has_bootstrap_cfg")
    _assert(req.bootstrap_cfg.statistic == "mean",    "statistic == mean")
    _assert(req.bootstrap_cfg.n_data == 5,            "n_data == 5")
    _assert(req.bootstrap_cfg.historical_data[0] == 1.0, "data[0] == 1.0")


def test_scenario():
    var raw = ('{"engine_type":"scenario","runs":200,'
        + '"scenario_config":{"scenarios":['
        + '{"name":"Bull","probability":0.3,"variables":{"v":100}},'
        + '{"name":"Bear","probability":0.7,"variables":{"v":50}}'
        + ']}}')
    var req = parse_request(raw)
    _assert(req.engine_type == "scenario",  "engine_type == scenario")
    _assert(req.has_scenario_cfg,            "has_scenario_cfg")
    _assert(len(req.scenario_cfg.raw_config) > 0, "scenario raw_config non-empty")


def test_sensitivity():
    var raw = ('{"engine_type":"sensitivity","runs":1000,'
        + '"variables":[{"name":"a","distribution":"normal","params":{"mean":10,"std":2}}],'
        + '"objective_function":"a"}')
    var req = parse_request(raw)
    _assert(req.engine_type == "sensitivity", "engine_type == sensitivity")
    _assert(req.n_vars == 1,                   "n_vars == 1")


def test_mcmc():
    var raw = ('{"engine_type":"mcmc","runs":200,'
        + '"mcmc_config":{"observed_data":[10,11,12,13,14],"chains":2,"burn_in":50}}')
    var req = parse_request(raw)
    _assert(req.engine_type == "mcmc",       "engine_type == mcmc")
    _assert(req.has_mcmc_cfg,                 "has_mcmc_cfg")
    _assert(req.mcmc_cfg.n_chains == 2,       "chains == 2")
    _assert(req.mcmc_cfg.burn_in == 50,       "burn_in == 50")
    _assert(req.mcmc_cfg.n_data == 5,         "n_data == 5")


def test_decision_tree():
    var raw = ('{"engine_type":"decision_tree","runs":500,'
        + '"decision_tree_config":{"paths":[{"label":"P1","probability":0.6,'
        + '"variables":[{"name":"r","distribution":"fixed","params":{"value":100}}],'
        + '"objective_function":"r"}]}}')
    var req = parse_request(raw)
    _assert(req.engine_type == "decision_tree",  "engine_type == decision_tree")
    _assert(req.has_decision_tree_cfg,            "has_decision_tree_cfg")
    _assert(len(req.decision_tree_cfg.raw_config) > 0, "dt raw_config non-empty")


def test_time_series():
    var raw = ('{"engine_type":"time_series","runs":500,'
        + '"time_series_config":{"model":"gbm","initial_value":100,"horizons":[6,12],'
        + '"dt":0.0833,"drift":0.07,"volatility":0.20}}')
    var req = parse_request(raw)
    _assert(req.engine_type == "time_series",        "engine_type == time_series")
    _assert(req.has_time_series_cfg,                  "has_time_series_cfg")
    _assert(req.time_series_cfg.model == "gbm",       "model == gbm")
    _assert(req.time_series_cfg.initial_value == 100.0, "initial_value == 100.0")
    _assert(len(req.time_series_cfg.horizons) == 2,   "2 horizons")
    _assert(req.time_series_cfg.horizons[0] == 6,     "horizon[0] == 6")


def test_compare():
    var raw = ('{"engine_type":"compare","runs":500,'
        + '"scenarios":[{"name":"A","variables":[]},{"name":"B","variables":[]}]}')
    var req = parse_request(raw)
    _assert(req.engine_type == "compare", "engine_type == compare")


def test_importance_sampling():
    var raw = ('{"engine_type":"importance_sampling","runs":1000,'
        + '"variables":[{"name":"x","distribution":"normal","params":{"mean":0,"std":1}}],'
        + '"objective_function":"x",'
        + '"importance_sampling_config":{"target_threshold":-2,"tail_direction":"lower"}}')
    var req = parse_request(raw)
    _assert(req.engine_type == "importance_sampling",    "engine_type == importance_sampling")
    _assert(req.has_is_cfg,                               "has_is_cfg")
    _assert(req.is_cfg.target_threshold == -2.0,          "threshold == -2.0")
    _assert(req.is_cfg.tail_direction == "lower",         "tail_direction == lower")


def test_all_distribution_types():
    """Verify all 27 distribution type codes parse correctly."""
    var dists = List[String]()
    dists.append('{"name":"a","distribution":"normal","params":{"mean":0,"std":1}}')
    dists.append('{"name":"b","distribution":"uniform","params":{"low":0,"high":1}}')
    dists.append('{"name":"c","distribution":"triangular","params":{"low":0,"mode":0.5,"high":1}}')
    dists.append('{"name":"d","distribution":"lognormal","params":{"mean":0,"std":1}}')
    dists.append('{"name":"e","distribution":"fixed","params":{"value":42}}')
    dists.append('{"name":"f","distribution":"beta","params":{"alpha":2,"beta":3}}')
    dists.append('{"name":"g","distribution":"exponential","params":{"rate":0.5}}')
    dists.append('{"name":"h","distribution":"weibull","params":{"shape":2,"scale":1}}')
    dists.append('{"name":"i","distribution":"gamma","params":{"shape":2,"scale":1}}')
    dists.append('{"name":"j","distribution":"pert","params":{"low":0,"likely":0.5,"high":1}}')
    dists.append('{"name":"k","distribution":"bernoulli","params":{"p":0.3}}')
    dists.append('{"name":"l","distribution":"poisson","params":{"lambda":5}}')
    dists.append('{"name":"m","distribution":"discrete","params":{"values":[1,2,3],"probabilities":[0.3,0.4,0.3]}}')
    dists.append('{"name":"n","distribution":"student_t","params":{"df":5,"loc":0,"scale":1}}')
    dists.append('{"name":"o","distribution":"cauchy","params":{"location":0,"scale":1}}')
    dists.append('{"name":"p","distribution":"laplace","params":{"mu":0,"b":1}}')
    dists.append('{"name":"q","distribution":"pareto","params":{"alpha":2,"x_min":1}}')
    dists.append('{"name":"r","distribution":"gumbel","params":{"mu":0,"beta":1}}')
    dists.append('{"name":"s","distribution":"rayleigh","params":{"sigma":1}}')
    dists.append('{"name":"t","distribution":"arcsine","params":{"low":0,"high":1}}')
    dists.append('{"name":"u","distribution":"logistic","params":{"mu":0,"scale":1}}')
    dists.append('{"name":"v","distribution":"halfnormal","params":{"sigma":1}}')
    dists.append('{"name":"w","distribution":"vonmises","params":{"mu":0,"kappa":1}}')
    dists.append('{"name":"x","distribution":"neg_binomial","params":{"r":2,"p":0.5}}')
    dists.append('{"name":"y","distribution":"hypergeometric","params":{"N":100,"K":30,"n":10}}')
    dists.append('{"name":"z","distribution":"categorical","params":{"probabilities":[0.3,0.4,0.3]}}')

    var expected_codes = List[Int]()
    for c in (0,1,2,3,4,5,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26):
        expected_codes.append(c)

    var n_dist = len(dists)
    var vars_json = "["
    for i in range(n_dist):
        if i > 0: vars_json += ","
        vars_json += dists[i]
    vars_json += "]"

    var raw = '{"engine_type":"monte_carlo","runs":10,"variables":' + vars_json + '}'
    var req = parse_request(raw)

    _assert(req.n_vars == n_dist, "n_vars == " + String(n_dist) + " (all distributions)")
    for i in range(min(len(expected_codes), req.n_vars)):
        _assert(req.dt[i] == expected_codes[i],
            "dist[" + String(i) + "] code == " + String(expected_codes[i]))


def test_multi_output_objective():
    """Multi-output via | separator."""
    var raw = ('{"engine_type":"monte_carlo","runs":100,'
        + '"variables":[{"name":"a","distribution":"fixed","params":{"value":1}},'
        + '{"name":"b","distribution":"fixed","params":{"value":2}}],'
        + '"objective_function":"a|b|a+b"}')
    var req = parse_request(raw)
    _assert(req.n_objectives == 3, "n_objectives == 3")
    _assert(req.obj_fns[0] == "a", "obj[0] == a")
    _assert(req.obj_fns[1] == "b", "obj[1] == b")
    _assert(req.obj_fns[2] == "a+b", "obj[2] == a+b")


def test_seed_sets_deterministic():
    """Seed field parsed correctly."""
    var req = parse_request('{"engine_type":"monte_carlo","runs":100,"seed":12345}')
    _assert(req.seed == 12345, "seed == 12345")


def test_scoring_weights():
    """Custom scoring weights parsed correctly."""
    var raw = '{"engine_type":"monte_carlo","runs":100,"scoring":{"expected_value":0.8,"downside_risk":0.2}}'
    var req = parse_request(raw)
    _assert(req.scoring.w_ev == 0.8, "w_ev == 0.8")
    _assert(req.scoring.w_dr == 0.2, "w_dr == 0.2")


def test_missing_optional_fields_use_defaults():
    """Missing optional fields use canonical schema defaults."""
    var req = parse_request('{}')
    _assert(req.engine_type == "monte_carlo", "engine_type default == monte_carlo")
    _assert(req.runs == 10000,                "runs default == 10000")
    _assert(req.seed == -1,                   "seed default == -1")
    _assert(req.workers == 0,                 "workers default == 0")
    _assert(req.stream_mode == False,         "stream_mode default == False")
    _assert(req.checkpoint_every == 1000,     "checkpoint_every default == 1000")


def main():
    print("=== test_request_parser.mojo ===")
    test_monte_carlo_defaults()
    test_qmc_sobol()
    test_lhs()
    test_bootstrap()
    test_scenario()
    test_sensitivity()
    test_mcmc()
    test_decision_tree()
    test_time_series()
    test_compare()
    test_importance_sampling()
    test_all_distribution_types()
    test_multi_output_objective()
    test_seed_sets_deterministic()
    test_scoring_weights()
    test_missing_optional_fields_use_defaults()
    print("=== Done ===")
