"""
test_field_mapper.mojo — Tests for the pure-Mojo adaptive field mapping library.

Validates polarity detection, distribution inference, unit hints, full mapping,
objective function construction, and variables JSON generation.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_field_mapper.mojo
"""
from field_mapper import (
    detect_polarity,
    infer_distribution,
    infer_distribution_from_values,
    detect_unit_hint,
    map_fields,
    build_objective_function,
    build_variables_json,
    contains_keyword,
    to_lower,
    FieldMapping,
)


def main() raises:
    # ── Polarity detection ──
    assert_equal(detect_polarity("revenue"), 1, "revenue → +1")
    assert_equal(detect_polarity("total_revenue_q4"), 1, "total_revenue_q4 → +1")
    assert_equal(detect_polarity("profit_margin"), 1, "profit_margin → +1")
    assert_equal(detect_polarity("cost"), -1, "cost → -1")
    assert_equal(detect_polarity("monthly_expense"), -1, "monthly_expense → -1")
    assert_equal(detect_polarity("churn_risk"), -1, "churn_risk → -1")
    assert_equal(detect_polarity("unit_count"), 0, "unit_count → 0")
    assert_equal(detect_polarity("factor_x"), 0, "factor_x → 0")
    assert_equal(detect_polarity("REVENUE"), 1, "REVENUE → +1 (case insensitive)")
    print("✅ Polarity detection")

    # ── Distribution inference from range ──
    var d1 = infer_distribution(80000.0, 200000.0)
    assert_true(d1[0] == "triangular", "80k-200k → triangular, got: " + d1[0])

    var d2 = infer_distribution(0.0, 1.0)
    assert_true(d2[0] == "beta", "[0,1] → beta, got: " + d2[0])

    var d3 = infer_distribution(0.05, 0.25)
    assert_true(d3[0] == "beta", "[0.05,0.25] → beta, got: " + d3[0])

    print("✅ Distribution inference from range")

    # ── Distribution inference from values ──
    var binary_vals = List[Float64]()
    binary_vals.append(0.0)
    binary_vals.append(1.0)
    binary_vals.append(1.0)
    binary_vals.append(0.0)
    binary_vals.append(1.0)
    var d4 = infer_distribution_from_values(binary_vals)
    assert_true(d4[0] == "bernoulli", "binary values → bernoulli, got: " + d4[0])

    var bounded_vals = List[Float64]()
    bounded_vals.append(0.1)
    bounded_vals.append(0.3)
    bounded_vals.append(0.5)
    bounded_vals.append(0.7)
    bounded_vals.append(0.2)
    var d5 = infer_distribution_from_values(bounded_vals)
    assert_true(d5[0] == "beta", "[0,1]-bounded values → beta, got: " + d5[0])

    var normal_vals = List[Float64]()
    normal_vals.append(-2.0)
    normal_vals.append(-1.0)
    normal_vals.append(0.0)
    normal_vals.append(1.0)
    normal_vals.append(2.0)
    var d6 = infer_distribution_from_values(normal_vals)
    assert_true(d6[0] == "normal", "symmetric values → normal, got: " + d6[0])

    print("✅ Distribution inference from values")

    # ── Unit hints ──
    assert_true(detect_unit_hint("revenue") == "currency", "revenue → currency")
    assert_true(detect_unit_hint("price_per_unit") == "currency", "price_per_unit → currency")
    assert_true(detect_unit_hint("churn_rate") == "percentage", "churn_rate → percentage")
    assert_true(detect_unit_hint("user_count") == "count", "user_count → count")
    assert_true(detect_unit_hint("processing_days") == "time", "processing_days → time")
    assert_true(detect_unit_hint("random_field") == "", "random_field → empty")
    print("✅ Unit hint detection")

    # ── Full field mapping ──
    var raw = '{"revenue":{"low":80000,"high":200000},"cost":{"low":40000,"high":90000},"churn_risk":{"low":0.05,"high":0.25}}'
    var mappings = map_fields(raw)
    assert_true(len(mappings) == 3, "expected 3 mappings, got: " + String(len(mappings)))
    print("✅ Full field mapping: " + String(len(mappings)) + " fields")

    # ── Objective function ──
    var obj = build_objective_function(mappings)
    # Should contain revenue (positive) and cost/churn_risk (negative)
    assert_true(len(obj) > 0, "objective function should not be empty")
    print("✅ Objective function: " + obj)

    # ── Variables JSON ──
    var vars_json = build_variables_json(mappings)
    assert_true(len(vars_json) > 2, "variables JSON should be more than '[]'")
    print("✅ Variables JSON generated")

    # ── Scalar fields ──
    var scalar_raw = '{"revenue":100000,"cost":50000}'
    var scalar_mappings = map_fields(scalar_raw)
    assert_true(len(scalar_mappings) == 2, "expected 2 scalar mappings, got: " + String(len(scalar_mappings)))
    print("✅ Scalar field mapping")

    # ── Case insensitive ──
    assert_true(contains_keyword("Total_Revenue_Q4", "revenue") == True, "Total_Revenue_Q4 contains revenue")
    assert_true(contains_keyword("COST_CENTER", "cost") == True, "COST_CENTER contains cost")
    assert_true(contains_keyword("hello", "world") == False, "hello does not contain world")
    print("✅ Case-insensitive keyword matching")

    # ── to_lower ──
    assert_true(to_lower("Hello World") == "hello world", "to_lower Hello World")
    assert_true(to_lower("ABC123") == "abc123", "to_lower ABC123")
    print("✅ to_lower")

    print("✅ All field mapper tests passed")


def assert_equal(got: Int, expected: Int, label: String) raises:
    """Assert two integers are equal."""
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected))
        print("   got:      " + String(got))
        raise Error("Assertion failed: " + label)


def assert_true(cond: Bool, label: String) raises:
    """Assert a condition is true."""
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("Assertion failed: " + label)
