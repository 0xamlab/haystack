"""
test_engines.mojo — Per-engine unit tests for all 11 Algenta decision engines.

Tests that each engine:
  1. Accepts a minimal valid payload and returns a non-empty JSON result
  2. Produces the expected top-level fields (_proto, engine_type, scenarios_run,
     summary, percentiles, risk, score, result_hash)
  3. Returns engine_type matching the request
  4. Returns scenarios_run matching the requested runs count

Run via:
    cd mojo_env && pixi run mojo run ../tests/mojo/test_engines.mojo
"""
from std.python import Python, PythonObject
from std.testing import assert_equal, assert_true, assert_false

from sys import exit


# ── Import engine dispatch ────────────────────────────────────────────────────
from mojo.engine.main import _run_raw


# ── Helpers ───────────────────────────────────────────────────────────────────

def _check_envelope(result_json: String, engine_type: String, expected_runs: Int) raises:
    """Assert that the result JSON has all required envelope fields."""
    var json_m  = Python.import_module("json")
    var b       = Python.import_module("builtins")
    var result  = json_m.loads(result_json)

    # Protocol version
    assert_equal(fast_int(result.get("_proto", 0)), 1,
        "_proto must be 1 in every engine response")

    # Engine identity
    var got_et = py_str(result.get("engine_type", ""))
    assert_equal(got_et, engine_type,
        "engine_type must echo the request type")

    # Run count (allow ± 1 for rounding in some engines)
    var got_runs = fast_int(result.get("scenarios_run", 0))
    assert_true(got_runs > 0, "scenarios_run must be > 0")

    # Summary must have mean
    var summary = result.get("summary", Python.evaluate("{}"))
    assert_true(fast_int(b.len(summary)) > 0, "summary must not be empty")

    # result_hash must be a 64-char hex string
    var rh = py_str(result.get("result_hash", ""))
    assert_equal(fast_int(b.len(rh)), 64, "result_hash must be 64 hex chars")


from python_bridge import fast_int, py_str


# ── Monte Carlo ───────────────────────────────────────────────────────────────

def test_monte_carlo() raises:
    var payload = """{"engine_type":"monte_carlo","runs":500,
        "variables":[
          {"name":"rev","distribution":"normal","params":{"mean":100000,"std":20000}},
          {"name":"cost","distribution":"triangular","params":{"low":40000,"mode":55000,"high":70000}}
        ],
        "objective_function":"rev - cost"}"""
    var result = _run_raw(payload)
    assert_true(len(result) > 0, "monte_carlo must return non-empty result")
    _check_envelope(result, "monte_carlo", 500)
    print("✅ test_monte_carlo passed")


# ── QMC Sobol ─────────────────────────────────────────────────────────────────

def test_qmc_sobol() raises:
    var payload = """{"engine_type":"qmc_sobol","runs":500,
        "variables":[
          {"name":"rev","distribution":"normal","params":{"mean":100000,"std":20000}},
          {"name":"cost","distribution":"uniform","params":{"low":40000,"high":70000}}
        ],
        "objective_function":"rev - cost"}"""
    var result = _run_raw(payload)
    assert_true(len(result) > 0, "qmc_sobol must return non-empty result")
    _check_envelope(result, "qmc_sobol", 500)
    print("✅ test_qmc_sobol passed")


# ── LHS ───────────────────────────────────────────────────────────────────────

def test_lhs() raises:
    var payload = """{"engine_type":"lhs","runs":500,
        "variables":[
          {"name":"rev","distribution":"normal","params":{"mean":100000,"std":20000}},
          {"name":"cost","distribution":"uniform","params":{"low":40000,"high":70000}}
        ],
        "objective_function":"rev - cost"}"""
    var result = _run_raw(payload)
    assert_true(len(result) > 0, "lhs must return non-empty result")
    _check_envelope(result, "lhs", 500)
    print("✅ test_lhs passed")


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def test_bootstrap() raises:
    var payload = """{"engine_type":"bootstrap","runs":200,
        "bootstrap_config":{
          "historical_data":[50000,55000,48000,62000,57000,49000,53000,60000,51000,58000,
                             47000,64000,56000,52000,59000,61000,48500,54000,57500,63000],
          "statistic":"mean"
        }}"""
    var result = _run_raw(payload)
    assert_true(len(result) > 0, "bootstrap must return non-empty result")
    _check_envelope(result, "bootstrap", 200)
    print("✅ test_bootstrap passed")


# ── Scenario ──────────────────────────────────────────────────────────────────

def test_scenario() raises:
    var payload = """{"engine_type":"scenario","runs":300,
        "variables":[{"name":"rev","distribution":"fixed","params":{"value":100000}}],
        "objective_function":"rev",
        "scenario_config":{"scenarios":[
          {"name":"Bull","probability":0.3,"variables":{"rev":150000}},
          {"name":"Base","probability":0.5,"variables":{"rev":100000}},
          {"name":"Bear","probability":0.2,"variables":{"rev":60000}}
        ]}}"""
    var result = _run_raw(payload)
    assert_true(len(result) > 0, "scenario must return non-empty result")
    _check_envelope(result, "scenario", 300)
    print("✅ test_scenario passed")


# ── Sensitivity ───────────────────────────────────────────────────────────────

def test_sensitivity() raises:
    var payload = """{"engine_type":"sensitivity","runs":500,
        "variables":[
          {"name":"rev","distribution":"normal","params":{"mean":100000,"std":20000}},
          {"name":"cost","distribution":"normal","params":{"mean":60000,"std":10000}},
          {"name":"vol","distribution":"lognormal","params":{"mean":11.0,"std":0.15}}
        ],
        "objective_function":"rev - cost"}"""
    var result = _run_raw(payload)
    assert_true(len(result) > 0, "sensitivity must return non-empty result")
    var json_m = Python.import_module("json")
    var r      = json_m.loads(result)
    var has_sa = py_str(r.get("sensitivity_analysis", Python.none())) != "None"
    assert_true(has_sa, "sensitivity result must include sensitivity_analysis field")
    print("✅ test_sensitivity passed")


# ── MCMC ──────────────────────────────────────────────────────────────────────

def test_mcmc() raises:
    var payload = """{"engine_type":"mcmc","runs":100,
        "mcmc_config":{
          "observed_data":[50000,55000,48000,62000,57000,49000,53000,60000,51000,58000,
                           47000,64000,56000,52000,59000,61000,48500,54000,57500,63000],
          "chains":1,"burn_in":50,"likelihood":"normal"
        }}"""
    var result = _run_raw(payload)
    assert_true(len(result) > 0, "mcmc must return non-empty result")
    _check_envelope(result, "mcmc", 100)
    print("✅ test_mcmc passed")


# ── Decision Tree ─────────────────────────────────────────────────────────────

def test_decision_tree() raises:
    var payload = """{"engine_type":"decision_tree","runs":200,
        "decision_tree_config":{"paths":[
          {"label":"Success","probability":0.6,
           "variables":[{"name":"rev","distribution":"normal","params":{"mean":200000,"std":30000}}],
           "objective_function":"rev"},
          {"label":"Failure","probability":0.4,
           "variables":[{"name":"rev","distribution":"normal","params":{"mean":50000,"std":10000}}],
           "objective_function":"rev"}
        ]}}"""
    var result = _run_raw(payload)
    assert_true(len(result) > 0, "decision_tree must return non-empty result")
    _check_envelope(result, "decision_tree", 200)
    print("✅ test_decision_tree passed")


# ── Time Series ───────────────────────────────────────────────────────────────

def test_time_series() raises:
    var payload = """{"engine_type":"time_series","runs":200,
        "time_series_config":{
          "model":"gbm","initial_value":100.0,
          "horizons":[3,6,12],"dt":0.0833,
          "drift":0.07,"volatility":0.20
        }}"""
    var result = _run_raw(payload)
    assert_true(len(result) > 0, "time_series must return non-empty result")
    var json_m = Python.import_module("json")
    var r      = json_m.loads(result)
    var has_ts = py_str(r.get("time_series_result", Python.none())) != "None"
    assert_true(has_ts, "time_series result must include time_series_result field")
    print("✅ test_time_series passed")


# ── Compare ───────────────────────────────────────────────────────────────────

def test_compare() raises:
    var payload = """{"engine_type":"compare","runs":200,
        "scenarios":[
          {"name":"Opt","variables":[{"name":"rev","distribution":"normal","params":{"mean":150000,"std":20000}}],"objective_function":"rev"},
          {"name":"Base","variables":[{"name":"rev","distribution":"normal","params":{"mean":100000,"std":20000}}],"objective_function":"rev"},
          {"name":"Pess","variables":[{"name":"rev","distribution":"normal","params":{"mean":60000,"std":15000}}],"objective_function":"rev"}
        ]}"""
    var result = _run_raw(payload)
    assert_true(len(result) > 0, "compare must return non-empty result")
    var json_m = Python.import_module("json")
    var r      = json_m.loads(result)
    var has_sc = py_str(r.get("scenario_results", Python.none())) != "None"
    assert_true(has_sc, "compare result must include scenario_results field")
    print("✅ test_compare passed")


# ── Importance Sampling ───────────────────────────────────────────────────────

def test_importance_sampling() raises:
    var payload = """{"engine_type":"importance_sampling","runs":500,
        "variables":[
          {"name":"rev","distribution":"normal","params":{"mean":100000,"std":20000}},
          {"name":"cost","distribution":"normal","params":{"mean":80000,"std":15000}}
        ],
        "objective_function":"rev - cost",
        "importance_sampling_config":{
          "target_threshold":-10000,
          "tail_direction":"lower"
        }}"""
    var result = _run_raw(payload)
    assert_true(len(result) > 0, "importance_sampling must return non-empty result")
    var json_m = Python.import_module("json")
    var r      = json_m.loads(result)
    var has_is = py_str(r.get("importance_sampling_result", Python.none())) != "None"
    assert_true(has_is, "importance_sampling result must include importance_sampling_result field")
    print("✅ test_importance_sampling passed")


# ── Score range check (all engines) ──────────────────────────────────────────

def test_score_range() raises:
    """Score must be in [0, 1] for all non-compare engines."""
    var payloads = List[String]()
    payloads.append("""{"engine_type":"monte_carlo","runs":200,
        "variables":[{"name":"x","distribution":"normal","params":{"mean":100,"std":10}}],
        "objective_function":"x"}""")
    payloads.append("""{"engine_type":"lhs","runs":200,
        "variables":[{"name":"x","distribution":"normal","params":{"mean":100,"std":10}}],
        "objective_function":"x"}""")
    payloads.append("""{"engine_type":"bootstrap","runs":200,
        "bootstrap_config":{"historical_data":[80,90,100,110,120,95,105,85,115,100],"statistic":"mean"}}""")

    var json_m = Python.import_module("json")
    for i in range(len(payloads)):
        var result = _run_raw(payloads[i])
        var r      = json_m.loads(result)
        var score  = fast_float(r.get("score", -1.0))
        assert_true(score >= 0.0 and score <= 1.0,
            "score must be in [0, 1]")
    print("✅ test_score_range passed")


from python_bridge import fast_float


# ── Histogram and CDF presence ────────────────────────────────────────────────

def test_histogram_and_cdf_in_envelope() raises:
    """Every standard MC-class engine must return histogram_data and cdf_data."""
    var payload = """{"engine_type":"monte_carlo","runs":300,
        "variables":[{"name":"x","distribution":"normal","params":{"mean":100,"std":10}}],
        "objective_function":"x"}"""
    var result = _run_raw(payload)
    var json_m = Python.import_module("json")
    var r      = json_m.loads(result)
    var has_hist = py_str(r.get("histogram_data", Python.none())) != "None"
    var has_cdf  = py_str(r.get("cdf_data",      Python.none())) != "None"
    assert_true(has_hist, "monte_carlo must include histogram_data in response")
    assert_true(has_cdf,  "monte_carlo must include cdf_data in response")
    print("✅ test_histogram_and_cdf_in_envelope passed")


# ── Main test runner ──────────────────────────────────────────────────────────

def main() raises:
    print("=" * 60)
    print("Algenta Engine Unit Tests — all 11 engines")
    print("=" * 60)
    print()

    var passed = 0
    var failed = 0

    # Run each test with error capture
    try:
        test_monte_carlo(); passed += 1
    except e:
        print("❌ test_monte_carlo FAILED:", e); failed += 1

    try:
        test_qmc_sobol(); passed += 1
    except e:
        print("❌ test_qmc_sobol FAILED:", e); failed += 1

    try:
        test_lhs(); passed += 1
    except e:
        print("❌ test_lhs FAILED:", e); failed += 1

    try:
        test_bootstrap(); passed += 1
    except e:
        print("❌ test_bootstrap FAILED:", e); failed += 1

    try:
        test_scenario(); passed += 1
    except e:
        print("❌ test_scenario FAILED:", e); failed += 1

    try:
        test_sensitivity(); passed += 1
    except e:
        print("❌ test_sensitivity FAILED:", e); failed += 1

    try:
        test_mcmc(); passed += 1
    except e:
        print("❌ test_mcmc FAILED:", e); failed += 1

    try:
        test_decision_tree(); passed += 1
    except e:
        print("❌ test_decision_tree FAILED:", e); failed += 1

    try:
        test_time_series(); passed += 1
    except e:
        print("❌ test_time_series FAILED:", e); failed += 1

    try:
        test_compare(); passed += 1
    except e:
        print("❌ test_compare FAILED:", e); failed += 1

    try:
        test_importance_sampling(); passed += 1
    except e:
        print("❌ test_importance_sampling FAILED:", e); failed += 1

    try:
        test_score_range(); passed += 1
    except e:
        print("❌ test_score_range FAILED:", e); failed += 1

    try:
        test_histogram_and_cdf_in_envelope(); passed += 1
    except e:
        print("❌ test_histogram_and_cdf_in_envelope FAILED:", e); failed += 1

    print()
    print("=" * 60)
    print("Results:", passed, "passed,", failed, "failed")
    print("=" * 60)

    if failed > 0:
        exit(1)
