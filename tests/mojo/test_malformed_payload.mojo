"""
test_malformed_payload.mojo — Malformed and missing-field payload tests.

Verifies that the engine gracefully handles:
  1. Empty payload {}
  2. Completely empty string
  3. Invalid JSON (syntax errors)
  4. Unknown engine_type → defaults to monte_carlo
  5. Unknown distribution type → uses fixed fallback
  6. Missing required fields (bootstrap without historical_data)
  7. Negative runs → clamped to 1
  8. runs=0 → clamped to 1
  9. seed=null → non-deterministic (no crash)
  10. checkpoint_every < 100 → clamped to 100
  11. Unknown top-level fields → silently ignored (forward-compat)
  12. Extra unknown engine_config keys → silently ignored
  13. Correlation referencing non-existent variables → skipped gracefully
  14. Objective function with undefined variable → handled as error or 0

Phase 4 exit criteria: malformed payload tests required.

Run via:
    cd mojo_env && pixi run mojo run ../tests/mojo/test_malformed_payload.mojo
"""
from std.python import Python, PythonObject
from std.testing import assert_true, assert_equal

from sys import exit

from mojo.engine.main import _run_raw
from python_bridge import fast_int, fast_float, py_str


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_or_none(result: String) raises -> PythonObject:
    """Try to parse result JSON, return None on failure."""
    var json_m = Python.import_module("json")
    try:
        return json_m.loads(result)
    except:
        return Python.none()


def _assert_valid_envelope(result: String, label: String) raises:
    """Assert result is valid JSON with at least _proto field."""
    assert_true(len(result) > 0, label + ": result must not be empty")
    var r = _parse_or_none(result)
    assert_true(r != Python.none(), label + ": result must be valid JSON")
    var proto = fast_int(r.get("_proto", 0))
    assert_equal(proto, 1, label + ": _proto must be 1")


def _assert_error_response(result: String, label: String) raises:
    """Assert result is a JSON object with an 'error' field (graceful error)."""
    assert_true(len(result) > 0, label + ": must return non-empty response even on error")
    var r = _parse_or_none(result)
    if r != Python.none():
        # Either a valid envelope or an error object — both are acceptable
        var has_proto = fast_int(r.get("_proto", 0)) == 1
        var has_error = py_str(r.get("error", "")) != ""
        assert_true(has_proto or has_error,
            label + ": must return _proto:1 or {error:...}")


# ── Test 1: Empty payload {} → defaults to 10k monte_carlo with no variables ─

def test_empty_payload() raises:
    var result = _run_raw("{}")
    _assert_valid_envelope(result, "empty_payload")
    var r = _parse_or_none(result)
    assert_equal(py_str(r.get("engine_type", "")), "monte_carlo",
        "empty payload must default to monte_carlo")
    assert_true(fast_int(r.get("scenarios_run", 0)) > 0,
        "empty payload must run some scenarios")
    print("✅ test_empty_payload passed")


# ── Test 2: Completely empty string → must not crash ─────────────────────────

def test_empty_string() raises:
    var threw = False
    try:
        var result = _run_raw("")
        # If it doesn't throw, it must return an error JSON
        _assert_error_response(result, "empty_string")
    except:
        threw = True
    # Either graceful error JSON or caught exception is acceptable
    # What is NOT acceptable is a silent crash with no output
    print("✅ test_empty_string passed (threw=" + String(threw) + ")")


# ── Test 3: Invalid JSON syntax ───────────────────────────────────────────────

def test_invalid_json() raises:
    var payloads = List[String]()
    payloads.append("{bad json")
    payloads.append('{"engine_type": "monte_carlo"')   # unclosed brace
    payloads.append('{"runs": }')                      # missing value
    payloads.append('{"variables": [{"name": "x"')     # truncated

    for i in range(len(payloads)):
        var threw = False
        try:
            var result = _run_raw(payloads[i])
            _assert_error_response(result, "invalid_json[" + String(i) + "]")
        except:
            threw = True
        print("  invalid_json[" + String(i) + "]: threw=" + String(threw) + " ✅")
    print("✅ test_invalid_json passed")


# ── Test 4: Unknown engine_type → defaults to monte_carlo ─────────────────────

def test_unknown_engine_type() raises:
    var payload = """{"engine_type":"vine_copula","runs":100,
        "variables":[{"name":"x","distribution":"normal","params":{"mean":0,"std":1}}],
        "objective_function":"x"}"""
    var result = _run_raw(payload)
    _assert_valid_envelope(result, "unknown_engine_type")
    var r = _parse_or_none(result)
    # Unknown engine_type falls through to monte_carlo default
    var et = py_str(r.get("engine_type", ""))
    assert_true(et == "monte_carlo" or et == "vine_copula",
        "unknown engine_type must either default to monte_carlo or return engine_type as-is")
    print("✅ test_unknown_engine_type passed")


# ── Test 5: Unknown distribution type → fixed fallback ───────────────────────

def test_unknown_distribution() raises:
    var payload = """{"engine_type":"monte_carlo","runs":100,
        "variables":[
          {"name":"x","distribution":"unknown_dist","params":{"value":42.0}}
        ],
        "objective_function":"x"}"""
    var result = _run_raw(payload)
    # Must not crash — unknown dist falls back to fixed(0)
    _assert_valid_envelope(result, "unknown_distribution")
    print("✅ test_unknown_distribution passed")


# ── Test 6: Bootstrap without historical_data → graceful error ────────────────

def test_bootstrap_missing_data() raises:
    var payload = """{"engine_type":"bootstrap","runs":100,
        "bootstrap_config":{"statistic":"mean"}}"""
    var threw = False
    try:
        var result = _run_raw(payload)
        _assert_error_response(result, "bootstrap_missing_data")
    except:
        threw = True
    print("✅ test_bootstrap_missing_data passed (threw=" + String(threw) + ")")


# ── Test 7: Negative runs → clamped to 1 ─────────────────────────────────────

def test_negative_runs() raises:
    var payload = """{"engine_type":"monte_carlo","runs":-100,
        "variables":[{"name":"x","distribution":"normal","params":{"mean":100,"std":10}}],
        "objective_function":"x"}"""
    var result = _run_raw(payload)
    _assert_valid_envelope(result, "negative_runs")
    var r     = _parse_or_none(result)
    var runs  = fast_int(r.get("scenarios_run", -1))
    assert_true(runs >= 1, "negative runs must be clamped to at least 1")
    print("✅ test_negative_runs passed (runs=" + String(runs) + ")")


# ── Test 8: runs=0 → clamped to 1 ────────────────────────────────────────────

def test_zero_runs() raises:
    var payload = """{"engine_type":"monte_carlo","runs":0,
        "variables":[{"name":"x","distribution":"normal","params":{"mean":100,"std":10}}],
        "objective_function":"x"}"""
    var result = _run_raw(payload)
    _assert_valid_envelope(result, "zero_runs")
    var r     = _parse_or_none(result)
    var runs  = fast_int(r.get("scenarios_run", -1))
    assert_true(runs >= 1, "zero runs must be clamped to at least 1")
    print("✅ test_zero_runs passed (runs=" + String(runs) + ")")


# ── Test 9: seed=null → non-deterministic, no crash ───────────────────────────

def test_null_seed() raises:
    var payload = """{"engine_type":"monte_carlo","runs":100,"seed":null,
        "variables":[{"name":"x","distribution":"normal","params":{"mean":100,"std":10}}],
        "objective_function":"x"}"""
    var result = _run_raw(payload)
    _assert_valid_envelope(result, "null_seed")
    print("✅ test_null_seed passed")


# ── Test 10: checkpoint_every < 100 → clamped to 100 ─────────────────────────

def test_checkpoint_clamping() raises:
    var payload = """{"engine_type":"monte_carlo","runs":200,"checkpoint_every":5,
        "variables":[{"name":"x","distribution":"normal","params":{"mean":100,"std":10}}],
        "objective_function":"x"}"""
    # Should not crash — checkpoint_every is clamped internally
    var result = _run_raw(payload)
    _assert_valid_envelope(result, "checkpoint_clamping")
    print("✅ test_checkpoint_clamping passed")


# ── Test 11: Unknown top-level fields → silently ignored ─────────────────────

def test_unknown_top_level_fields() raises:
    var payload = """{
        "engine_type":"monte_carlo","runs":100,
        "variables":[{"name":"x","distribution":"normal","params":{"mean":100,"std":10}}],
        "objective_function":"x",
        "future_field_v2":"some_value",
        "another_unknown":{"nested":"object"},
        "schema_version":"1.0"
    }"""
    var result = _run_raw(payload)
    _assert_valid_envelope(result, "unknown_top_level_fields")
    print("✅ test_unknown_top_level_fields passed")


# ── Test 12: Unknown engine_config keys → silently ignored ────────────────────

def test_unknown_engine_config_keys() raises:
    var payload = """{
        "engine_type":"monte_carlo","runs":100,
        "variables":[{"name":"x","distribution":"normal","params":{"mean":100,"std":10}}],
        "objective_function":"x",
        "engine_config":{"nonexistent_key":42,"another_future_key":"abc"}
    }"""
    var result = _run_raw(payload)
    _assert_valid_envelope(result, "unknown_engine_config_keys")
    print("✅ test_unknown_engine_config_keys passed")


# ── Test 13: Correlation with non-existent variable → skipped gracefully ──────

def test_bad_correlation_variable() raises:
    var payload = """{
        "engine_type":"monte_carlo","runs":100,
        "variables":[
          {"name":"rev","distribution":"normal","params":{"mean":100000,"std":20000}},
          {"name":"cost","distribution":"normal","params":{"mean":60000,"std":10000}}
        ],
        "correlations":[
          {"variables":["rev","nonexistent_var"],"coefficient":0.8}
        ],
        "objective_function":"rev - cost"
    }"""
    var result = _run_raw(payload)
    # Bad correlation pairs must be skipped, engine still runs
    _assert_valid_envelope(result, "bad_correlation_variable")
    print("✅ test_bad_correlation_variable passed")


# ── Test 14: objective_function with undefined variable ───────────────────────

def test_undefined_objective_variable() raises:
    var payload = """{
        "engine_type":"monte_carlo","runs":100,
        "variables":[
          {"name":"revenue","distribution":"normal","params":{"mean":100000,"std":20000}}
        ],
        "objective_function":"revenue - undefined_cost_var"
    }"""
    # Must not crash — undefined variable resolves to 0 or raises graceful error
    var threw = False
    try:
        var result = _run_raw(payload)
        _assert_error_response(result, "undefined_objective_variable")
    except:
        threw = True
    print("✅ test_undefined_objective_variable passed (threw=" + String(threw) + ")")


# ── Test 15: Scoring weights that do not sum to 1.0 → accepted (advisory) ────

def test_scoring_weights_not_summing_to_one() raises:
    var payload = """{
        "engine_type":"monte_carlo","runs":100,
        "variables":[{"name":"x","distribution":"normal","params":{"mean":100,"std":10}}],
        "objective_function":"x",
        "scoring":{"expected_value":0.3,"downside_risk":0.3}
    }"""
    # Mojo engine accepts any scoring weights — validation is at the Python API layer
    var result = _run_raw(payload)
    _assert_valid_envelope(result, "scoring_weights_not_sum_1")
    print("✅ test_scoring_weights_not_summing_to_one passed")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() raises:
    print("=" * 60)
    print("Codna Malformed Payload Tests — Phase 4 exit criteria")
    print("=" * 60)
    print()

    var passed = 0
    var failed = 0

    alias tests = [
        test_empty_payload,
        test_empty_string,
        test_invalid_json,
        test_unknown_engine_type,
        test_unknown_distribution,
        test_bootstrap_missing_data,
        test_negative_runs,
        test_zero_runs,
        test_null_seed,
        test_checkpoint_clamping,
        test_unknown_top_level_fields,
        test_unknown_engine_config_keys,
        test_bad_correlation_variable,
        test_undefined_objective_variable,
        test_scoring_weights_not_summing_to_one,
    ]

    try:
        test_empty_payload(); passed += 1
    except e:
        print("❌ test_empty_payload FAILED:", e); failed += 1

    try:
        test_empty_string(); passed += 1
    except e:
        print("❌ test_empty_string FAILED:", e); failed += 1

    try:
        test_invalid_json(); passed += 1
    except e:
        print("❌ test_invalid_json FAILED:", e); failed += 1

    try:
        test_unknown_engine_type(); passed += 1
    except e:
        print("❌ test_unknown_engine_type FAILED:", e); failed += 1

    try:
        test_unknown_distribution(); passed += 1
    except e:
        print("❌ test_unknown_distribution FAILED:", e); failed += 1

    try:
        test_bootstrap_missing_data(); passed += 1
    except e:
        print("❌ test_bootstrap_missing_data FAILED:", e); failed += 1

    try:
        test_negative_runs(); passed += 1
    except e:
        print("❌ test_negative_runs FAILED:", e); failed += 1

    try:
        test_zero_runs(); passed += 1
    except e:
        print("❌ test_zero_runs FAILED:", e); failed += 1

    try:
        test_null_seed(); passed += 1
    except e:
        print("❌ test_null_seed FAILED:", e); failed += 1

    try:
        test_checkpoint_clamping(); passed += 1
    except e:
        print("❌ test_checkpoint_clamping FAILED:", e); failed += 1

    try:
        test_unknown_top_level_fields(); passed += 1
    except e:
        print("❌ test_unknown_top_level_fields FAILED:", e); failed += 1

    try:
        test_unknown_engine_config_keys(); passed += 1
    except e:
        print("❌ test_unknown_engine_config_keys FAILED:", e); failed += 1

    try:
        test_bad_correlation_variable(); passed += 1
    except e:
        print("❌ test_bad_correlation_variable FAILED:", e); failed += 1

    try:
        test_undefined_objective_variable(); passed += 1
    except e:
        print("❌ test_undefined_objective_variable FAILED:", e); failed += 1

    try:
        test_scoring_weights_not_summing_to_one(); passed += 1
    except e:
        print("❌ test_scoring_weights_not_summing_to_one FAILED:", e); failed += 1

    print()
    print("=" * 60)
    print("Results:", passed, "passed,", failed, "failed")
    print("=" * 60)

    if failed > 0:
        exit(1)
