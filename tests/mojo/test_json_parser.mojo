"""
test_json_parser.mojo — Comprehensive tests for the pure-Mojo JSON parser.

Validates json_get_string, json_get_float, json_get_int, json_get_bool,
json_get_object, json_get_array, json_is_null, json_array_len, json_array_get
against all edge cases including nested structures, escapes, and real payloads.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_json_parser.mojo
"""
from json.parser import (
    json_get_string,
    json_get_float,
    json_get_int,
    json_get_bool,
    json_get_object,
    json_get_array,
    json_is_null,
    json_array_len,
    json_array_get,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def approx_eq(a: Float64, b: Float64, eps: Float64 = 1e-6) -> Bool:
    """Check if two Float64 values are approximately equal."""
    var diff = a - b
    if diff < 0:
        diff = -diff
    return diff < eps


def _assert_float(got: Float64, expected: Float64, label: String) raises:
    """Assert two floats are approximately equal."""
    if not approx_eq(got, expected):
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected))
        print("   got:      " + String(got))
        raise Error("assertion failed: " + label)
    print("✅ " + label)


def _assert_int(got: Int, expected: Int, label: String) raises:
    """Assert two ints are equal."""
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected))
        print("   got:      " + String(got))
        raise Error("assertion failed: " + label)
    print("✅ " + label)


def _assert_str(got: String, expected: String, label: String) raises:
    """Assert two strings are equal."""
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: '" + expected + "'")
        print("   got:      '" + got + "'")
        raise Error("assertion failed: " + label)
    print("✅ " + label)


def _assert_true(cond: Bool, label: String) raises:
    """Assert condition is true."""
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)
    print("✅ " + label)


# ── String extraction tests ──────────────────────────────────────────────────


def test_string_extraction() raises:
    print("\n── String extraction ──")
    var obj = '{"engine_type":"monte_carlo","runs":10000}'
    _assert_str(
        json_get_string(obj, "engine_type"),
        "monte_carlo",
        "json_get_string(engine_type) == monte_carlo",
    )


def test_string_default() raises:
    print("\n── String default ──")
    _assert_str(
        json_get_string('{"a":"b"}', "missing"),
        "",
        'json_get_string(missing) == ""',
    )


# ── Number extraction tests ──────────────────────────────────────────────────


def test_int_extraction() raises:
    print("\n── Int extraction ──")
    var obj = '{"engine_type":"monte_carlo","runs":10000}'
    _assert_int(
        json_get_int(obj, "runs", 0),
        10000,
        "json_get_int(runs) == 10000",
    )


def test_float_extraction() raises:
    print("\n── Float extraction ──")
    var obj = '{"engine_type":"monte_carlo","runs":10000}'
    _assert_float(
        json_get_float(obj, "runs", 0.0),
        10000.0,
        "json_get_float(runs) == 10000.0",
    )


def test_default_values() raises:
    print("\n── Default values ──")
    var obj = '{"engine_type":"monte_carlo","runs":10000}'
    _assert_int(
        json_get_int(obj, "missing", 42),
        42,
        "json_get_int(missing, 42) == 42",
    )
    _assert_str(
        json_get_string(obj, "missing"),
        "",
        'json_get_string(missing) == ""',
    )


# ── Boolean extraction tests ─────────────────────────────────────────────────


def test_bool_extraction() raises:
    print("\n── Boolean extraction ──")
    var obj2 = '{"stream":true,"debug":false}'
    _assert_true(
        json_get_bool(obj2, "stream", False) == True,
        "json_get_bool(stream) == True",
    )
    _assert_true(
        json_get_bool(obj2, "debug", True) == False,
        "json_get_bool(debug) == False",
    )


# ── Null handling tests ──────────────────────────────────────────────────────


def test_null_handling() raises:
    print("\n── Null handling ──")
    var obj3 = '{"seed":null,"runs":10000}'
    _assert_true(
        json_is_null(obj3, "seed") == True,
        "json_is_null(seed) == True",
    )
    _assert_true(
        json_is_null(obj3, "runs") == False,
        "json_is_null(runs) == False",
    )


# ── Nested object extraction tests ───────────────────────────────────────────


def test_nested_object() raises:
    print("\n── Nested object extraction ──")
    var obj4 = '{"scoring":{"expected_value":0.6,"downside_risk":0.4},"runs":5000}'
    var scoring = json_get_object(obj4, "scoring")
    _assert_float(
        json_get_float(scoring, "expected_value", 0.0),
        0.6,
        "nested: expected_value == 0.6",
    )
    _assert_float(
        json_get_float(scoring, "downside_risk", 0.0),
        0.4,
        "nested: downside_risk == 0.4",
    )
    _assert_int(
        json_get_int(obj4, "runs", 0),
        5000,
        "not confused by nested obj: runs == 5000",
    )


# ── Array extraction tests ───────────────────────────────────────────────────


def test_array_extraction() raises:
    print("\n── Array extraction ──")
    var obj5 = '{"variables":[{"name":"rev"},{"name":"cost"}],"runs":1000}'
    var arr = json_get_array(obj5, "variables")
    _assert_int(
        json_array_len(arr),
        2,
        "json_array_len(variables) == 2",
    )
    var elem0 = json_array_get(arr, 0)
    _assert_str(
        json_get_string(elem0, "name"),
        "rev",
        'array[0].name == "rev"',
    )
    var elem1 = json_array_get(arr, 1)
    _assert_str(
        json_get_string(elem1, "name"),
        "cost",
        'array[1].name == "cost"',
    )
    _assert_int(
        json_get_int(obj5, "runs", 0),
        1000,
        "not confused by array: runs == 1000",
    )


# ── Negative numbers tests ───────────────────────────────────────────────────


def test_negative_numbers() raises:
    print("\n── Negative numbers ──")
    var obj6 = '{"threshold":-500000,"coeff":-0.3}'
    _assert_float(
        json_get_float(obj6, "threshold", 0.0),
        -500000.0,
        "json_get_float(threshold) == -500000.0",
    )
    _assert_float(
        json_get_float(obj6, "coeff", 0.0),
        -0.3,
        "json_get_float(coeff) == -0.3",
    )


# ── Escaped strings tests ────────────────────────────────────────────────────


def test_escaped_strings() raises:
    print("\n── Escaped strings ──")
    var obj7 = '{"label":"hello \\"world\\""}'
    _assert_str(
        json_get_string(obj7, "label"),
        'hello "world"',
        'escaped quotes: hello "world"',
    )


# ── Real simulation payload test ─────────────────────────────────────────────


def test_real_payload() raises:
    print("\n── Real simulation payload ──")
    var payload = '{"engine_type":"monte_carlo","runs":10000,"seed":42,"variables":[{"name":"revenue","distribution":"normal","params":{"mean":100000,"std":20000}}],"objective_function":"revenue","scoring":{"expected_value":0.6,"downside_risk":0.4}}'
    _assert_str(
        json_get_string(payload, "engine_type"),
        "monte_carlo",
        "payload: engine_type == monte_carlo",
    )
    _assert_int(
        json_get_int(payload, "runs", 0),
        10000,
        "payload: runs == 10000",
    )
    _assert_int(
        json_get_int(payload, "seed", -1),
        42,
        "payload: seed == 42",
    )
    _assert_str(
        json_get_string(payload, "objective_function"),
        "revenue",
        "payload: objective_function == revenue",
    )
    var vars_arr = json_get_array(payload, "variables")
    _assert_int(
        json_array_len(vars_arr),
        1,
        "payload: variables array len == 1",
    )
    var v0 = json_array_get(vars_arr, 0)
    _assert_str(
        json_get_string(v0, "name"),
        "revenue",
        'payload: vars[0].name == "revenue"',
    )
    _assert_str(
        json_get_string(v0, "distribution"),
        "normal",
        'payload: vars[0].distribution == "normal"',
    )
    var params = json_get_object(v0, "params")
    _assert_float(
        json_get_float(params, "mean", 0.0),
        100000.0,
        "payload: vars[0].params.mean == 100000.0",
    )
    _assert_float(
        json_get_float(params, "std", 0.0),
        20000.0,
        "payload: vars[0].params.std == 20000.0",
    )


# ── Empty/missing tests ──────────────────────────────────────────────────────


def test_empty_missing() raises:
    print("\n── Empty/missing ──")
    _assert_str(
        json_get_string("{}", "x"),
        "",
        'json_get_string({}, x) == ""',
    )
    _assert_int(
        json_get_int("{}", "x", 99),
        99,
        "json_get_int({}, x, 99) == 99",
    )
    _assert_int(
        json_array_len("[]"),
        0,
        "json_array_len([]) == 0",
    )


# ── Runner ────────────────────────────────────────────────────────────────────


def main() raises:
    print("━━━ json/parser.mojo test suite ━━━")

    test_string_extraction()
    test_string_default()
    test_int_extraction()
    test_float_extraction()
    test_default_values()
    test_bool_extraction()
    test_null_handling()
    test_nested_object()
    test_array_extraction()
    test_negative_numbers()
    test_escaped_strings()
    test_real_payload()
    test_empty_missing()

    print("\n━━━ ✅ All JSON parser tests passed ━━━")
