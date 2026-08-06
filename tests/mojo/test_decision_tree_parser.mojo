"""
test_decision_tree_parser.mojo — Tests for the pure-Mojo decision tree parser.

Validates flatten_decision_tree, merge_variables, and granularity_to_dt
against multiple tree shapes, variable overrides, and edge cases.

Run:
  cd mojo_env && pixi run mojo run -I ../mojo/engine ../tests/mojo/test_decision_tree_parser.mojo
"""

from decision_tree_parser import (
    TreePath,
    flatten_decision_tree,
    merge_variables,
    granularity_to_dt,
)
from json.parser import json_get_string, json_get_float, json_get_object, json_array_len, json_array_get


# ── Helpers ───────────────────────────────────────────────────────────────


def approx_eq(a: Float64, b: Float64, eps: Float64 = 1e-9) -> Bool:
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


def _assert_int(got: Int, expected: Int, label: String) raises:
    """Assert two ints are equal."""
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: " + String(expected))
        print("   got:      " + String(got))
        raise Error("assertion failed: " + label)


def _assert_str(got: String, expected: String, label: String) raises:
    """Assert two strings are equal."""
    if got != expected:
        print("❌ FAIL: " + label)
        print("   expected: '" + expected + "'")
        print("   got:      '" + got + "'")
        raise Error("assertion failed: " + label)


def _assert_true(cond: Bool, label: String) raises:
    """Assert condition is true."""
    if not cond:
        print("❌ FAIL: " + label)
        raise Error("assertion failed: " + label)


# ── Test: Two-leaf tree ───────────────────────────────────────────────────


def test_two_leaf_tree() raises:
    print("\n── Two-leaf tree ──")
    var nodes = '[{"id":"root","name":"Launch","probability":1.0,"children":[{"id":"accept","name":"Accepts","probability":0.6},{"id":"reject","name":"Rejects","probability":0.4}]}]'
    var base_vars = '[{"name":"revenue","distribution":"normal","params":{"mean":100000,"std":20000}}]'
    var paths = flatten_decision_tree(nodes, base_vars, "revenue")

    _assert_int(len(paths), 2, "two-leaf: path count == 2")

    # Probabilities: root=1.0, accept=0.6 -> 0.6, reject=0.4 -> 0.4
    # Normalized: 0.6/(0.6+0.4)=0.6, 0.4/(0.6+0.4)=0.4
    _assert_float(paths[0].probability, 0.6, "two-leaf: path[0] prob == 0.6")
    _assert_float(paths[1].probability, 0.4, "two-leaf: path[1] prob == 0.4")

    # Labels
    _assert_str(paths[0].label, "Launch > Accepts", "two-leaf: path[0] label")
    _assert_str(paths[1].label, "Launch > Rejects", "two-leaf: path[1] label")

    # Both should have base variables and default objective
    _assert_str(paths[0].objective_function, "revenue", "two-leaf: path[0] obj_fn")
    _assert_str(paths[1].objective_function, "revenue", "two-leaf: path[1] obj_fn")

    # Variables should include the base revenue var
    var v0_len = json_array_len(paths[0].variables_json)
    _assert_int(v0_len, 1, "two-leaf: path[0] has 1 variable")

    print("✅ Two-leaf tree: " + String(len(paths)) + " paths")


# ── Test: Single node (no children = single leaf path) ────────────────────


def test_single_node() raises:
    print("\n── Single node tree ──")
    var single = '[{"id":"only","name":"Only Option","probability":1.0}]'
    var base_vars = '[{"name":"revenue","distribution":"normal","params":{"mean":100000,"std":20000}}]'
    var paths = flatten_decision_tree(single, base_vars, "revenue")

    _assert_int(len(paths), 1, "single: path count == 1")
    _assert_str(paths[0].label, "Only Option", "single: label")
    _assert_float(paths[0].probability, 1.0, "single: probability == 1.0")

    print("✅ Single node tree")


# ── Test: Variable override ───────────────────────────────────────────────


def test_variable_override() raises:
    print("\n── Variable override tree ──")
    var nodes = '[{"id":"root","name":"Root","probability":1.0,"children":[{"id":"a","name":"A","probability":0.5,"variables":[{"name":"revenue","distribution":"normal","params":{"mean":200000,"std":30000}}]},{"id":"b","name":"B","probability":0.5}]}]'
    var base_vars = '[{"name":"revenue","distribution":"normal","params":{"mean":100000,"std":20000}}]'
    var paths = flatten_decision_tree(nodes, base_vars, "revenue")

    _assert_int(len(paths), 2, "override: path count == 2")

    # Path A should have overridden revenue with mean=200000
    var vars_a = paths[0].variables_json
    var va0 = json_array_get(vars_a, 0)
    var params_a = json_get_object(va0, "params")
    _assert_float(json_get_float(params_a, "mean", 0.0), 200000.0,
                  "override: path A revenue mean == 200000")

    # Path B should have base revenue with mean=100000
    var vars_b = paths[1].variables_json
    var vb0 = json_array_get(vars_b, 0)
    var params_b = json_get_object(vb0, "params")
    _assert_float(json_get_float(params_b, "mean", 0.0), 100000.0,
                  "override: path B revenue mean == 100000")

    print("✅ Variable override tree")


# ── Test: Three-level deep tree ──────────────────────────────────────────


def test_three_level_tree() raises:
    print("\n── Three-level tree ──")
    var nodes = '[{"id":"r","name":"Root","probability":1.0,"children":[{"id":"a","name":"A","probability":0.5,"children":[{"id":"a1","name":"A1","probability":0.3},{"id":"a2","name":"A2","probability":0.7}]},{"id":"b","name":"B","probability":0.5}]}]'
    var paths = flatten_decision_tree(nodes, "[]", "obj")

    _assert_int(len(paths), 3, "three-level: path count == 3")

    # Paths: Root>A>A1 (1.0*0.5*0.3=0.15), Root>A>A2 (1.0*0.5*0.7=0.35), Root>B (1.0*0.5=0.5)
    # Total = 0.15+0.35+0.5 = 1.0
    _assert_str(paths[0].label, "Root > A > A1", "three-level: path[0] label")
    _assert_str(paths[1].label, "Root > A > A2", "three-level: path[1] label")
    _assert_str(paths[2].label, "Root > B", "three-level: path[2] label")

    _assert_float(paths[0].probability, 0.15, "three-level: path[0] prob == 0.15")
    _assert_float(paths[1].probability, 0.35, "three-level: path[1] prob == 0.35")
    _assert_float(paths[2].probability, 0.50, "three-level: path[2] prob == 0.50")

    print("✅ Three-level tree")


# ── Test: Objective function inheritance ──────────────────────────────────


def test_objective_inheritance() raises:
    print("\n── Objective inheritance ──")
    var nodes = '[{"id":"r","name":"Root","probability":1.0,"children":[{"id":"a","name":"A","probability":0.5,"objective_function":"custom_obj"},{"id":"b","name":"B","probability":0.5}]}]'
    var paths = flatten_decision_tree(nodes, "[]", "default_obj")

    _assert_str(paths[0].objective_function, "custom_obj",
                "obj-inherit: path A has custom_obj")
    _assert_str(paths[1].objective_function, "default_obj",
                "obj-inherit: path B inherits default_obj")

    print("✅ Objective inheritance")


# ── Test: Multiple root nodes ─────────────────────────────────────────────


def test_multiple_roots() raises:
    print("\n── Multiple root nodes ──")
    var nodes = '[{"id":"r1","name":"Root1","probability":0.7},{"id":"r2","name":"Root2","probability":0.3}]'
    var paths = flatten_decision_tree(nodes, "[]", "obj")

    _assert_int(len(paths), 2, "multi-root: path count == 2")
    _assert_str(paths[0].label, "Root1", "multi-root: path[0] label")
    _assert_str(paths[1].label, "Root2", "multi-root: path[1] label")
    _assert_float(paths[0].probability, 0.7, "multi-root: path[0] prob == 0.7")
    _assert_float(paths[1].probability, 0.3, "multi-root: path[1] prob == 0.3")

    print("✅ Multiple root nodes")


# ── Test: Name defaults to id ─────────────────────────────────────────────


def test_name_defaults_to_id() raises:
    print("\n── Name defaults to id ──")
    var nodes = '[{"id":"my_node","probability":1.0}]'
    var paths = flatten_decision_tree(nodes, "[]", "obj")

    _assert_int(len(paths), 1, "name-default: path count == 1")
    _assert_str(paths[0].label, "my_node", "name-default: label uses id")

    print("✅ Name defaults to id")


# ── Test: Granularity lookup ──────────────────────────────────────────────


def test_granularity_lookup() raises:
    print("\n── Granularity lookup ──")
    _assert_float(granularity_to_dt("day"), 1.0 / 365.0, "granularity: day")
    _assert_float(granularity_to_dt("week"), 1.0 / 52.0, "granularity: week")
    _assert_float(granularity_to_dt("month"), 1.0 / 12.0, "granularity: month")
    _assert_float(granularity_to_dt("quarter"), 0.25, "granularity: quarter")
    _assert_float(granularity_to_dt("year"), 1.0, "granularity: year")
    _assert_float(granularity_to_dt("unknown"), 1.0 / 12.0, "granularity: unknown -> default")

    print("✅ Granularity lookup")


# ── Test: Merge variables ─────────────────────────────────────────────────


def test_merge_variables() raises:
    print("\n── Variable merge ──")

    var base = '[{"name":"rev","distribution":"normal","params":{"mean":100,"std":10}},{"name":"cost","distribution":"uniform","params":{"low":50,"high":80}}]'
    var override = '[{"name":"rev","distribution":"normal","params":{"mean":200,"std":20}}]'
    var merged = merge_variables(base, override)

    # merged should have 2 variables
    _assert_int(json_array_len(merged), 2, "merge: count == 2")

    # First var (rev) should have overridden mean=200
    var v0 = json_array_get(merged, 0)
    _assert_str(json_get_string(v0, "name"), "rev", "merge: var[0] name == rev")
    var p0 = json_get_object(v0, "params")
    _assert_float(json_get_float(p0, "mean", 0.0), 200.0, "merge: rev.mean == 200")

    # Second var (cost) should be unchanged
    var v1 = json_array_get(merged, 1)
    _assert_str(json_get_string(v1, "name"), "cost", "merge: var[1] name == cost")

    print("✅ Variable merge")


# ── Test: Merge variables — append new ────────────────────────────────────


def test_merge_variables_append() raises:
    print("\n── Variable merge (append new) ──")

    var base = '[{"name":"rev","distribution":"normal","params":{"mean":100,"std":10}}]'
    var override = '[{"name":"extra","distribution":"uniform","params":{"low":0,"high":1}}]'
    var merged = merge_variables(base, override)

    _assert_int(json_array_len(merged), 2, "merge-append: count == 2")

    var v0 = json_array_get(merged, 0)
    _assert_str(json_get_string(v0, "name"), "rev", "merge-append: var[0] name == rev")

    var v1 = json_array_get(merged, 1)
    _assert_str(json_get_string(v1, "name"), "extra", "merge-append: var[1] name == extra")

    print("✅ Variable merge (append new)")


# ── Test: Merge edge cases ────────────────────────────────────────────────


def test_merge_edge_cases() raises:
    print("\n── Variable merge (edge cases) ──")

    var base = '[{"name":"a","distribution":"fixed","params":{"value":1}}]'

    # Empty override returns base
    var m1 = merge_variables(base, "[]")
    _assert_int(json_array_len(m1), 1, "merge-edge: empty override returns base")

    # Empty base returns override
    var m2 = merge_variables("[]", base)
    _assert_int(json_array_len(m2), 1, "merge-edge: empty base returns override")

    print("✅ Variable merge (edge cases)")


# ── Test: Empty tree ──────────────────────────────────────────────────────


def test_empty_tree() raises:
    print("\n── Empty tree ──")
    var paths = flatten_decision_tree("[]", "[]", "obj")
    _assert_int(len(paths), 0, "empty: path count == 0")

    print("✅ Empty tree")


# ── Test: Probability normalization ───────────────────────────────────────


def test_probability_normalization() raises:
    print("\n── Probability normalization ──")
    # Two nodes with probabilities that don't sum to 1.0
    var nodes = '[{"id":"r","name":"Root","probability":1.0,"children":[{"id":"a","name":"A","probability":2.0},{"id":"b","name":"B","probability":3.0}]}]'
    var paths = flatten_decision_tree(nodes, "[]", "obj")

    _assert_int(len(paths), 2, "normalize: path count == 2")

    # Raw: A=1.0*2.0=2.0, B=1.0*3.0=3.0, total=5.0
    # Normalized: A=2.0/5.0=0.4, B=3.0/5.0=0.6
    _assert_float(paths[0].probability, 0.4, "normalize: path A prob == 0.4")
    _assert_float(paths[1].probability, 0.6, "normalize: path B prob == 0.6")

    # Probabilities should sum to 1.0
    var total = paths[0].probability + paths[1].probability
    _assert_float(total, 1.0, "normalize: probs sum to 1.0")

    print("✅ Probability normalization")


# ── Runner ────────────────────────────────────────────────────────────────


def main() raises:
    print("━━━ decision_tree_parser.mojo test suite ━━━")

    test_two_leaf_tree()
    test_single_node()
    test_variable_override()
    test_three_level_tree()
    test_objective_inheritance()
    test_multiple_roots()
    test_name_defaults_to_id()
    test_granularity_lookup()
    test_merge_variables()
    test_merge_variables_append()
    test_merge_edge_cases()
    test_empty_tree()
    test_probability_normalization()

    print("\n━━━ ✅ All decision tree parser tests passed ━━━")
