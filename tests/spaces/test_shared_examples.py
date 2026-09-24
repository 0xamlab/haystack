"""Prefilled arguments: every field opens with a value (owner rule, round 9), the value is
contract-valid, every count relation holds exactly, and the verified files cover the catalogue."""

from __future__ import annotations

import json
from pathlib import Path

from algenta_spaces import examples, playground

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "apps" / "spaces" / "algenta" / "examples"


def _form(module: str, function: str, params: list[tuple[str, str]], *, structs=None, relations=()):
    fields = tuple(
        playground.FieldSpec(
            name=n, kind=playground.field_kind(t), type_name=t, list_of=playground.list_inner(t)
        )
        for n, t in params
    )
    return playground.Form(
        module=module,
        function=function,
        fields=fields,
        structs=structs or {},
        count_relations=tuple(relations),
    )


def test_every_parameter_gets_a_value_from_its_name_and_type():
    form = _form(
        "ab_testing",
        "z_test_proportions",
        [
            ("successes_a", "Int"),
            ("n_a", "Int"),
            ("p_value", "Float64"),
            ("alpha", "Float64"),
            ("text", "String"),
            ("strict", "Bool"),
            ("lat2", "Float64"),
            ("lon2", "Float64"),
        ],
    )
    args = examples.synthesize(form)
    assert args["successes_a"] == 50 and args["n_a"] == 1000  # a proportion that exists
    assert (
        args["p_value"] == 0.03 and args["alpha"] == 0.05
    )  # not "value" (2.5): the exact name wins
    assert args["text"].startswith("The quick brown fox") and args["strict"] is False
    assert (args["lat2"], args["lon2"]) == examples.POINTS[1]  # the second point is Paris
    assert all(v is not None and v != "" for v in args.values())


def test_structs_and_lists_fill_field_by_field():
    structs = {
        "Interval": {
            "fields": [
                {"name": "lo", "type": "Float64"},
                {"name": "hi", "type": "Float64"},
                {"name": "empty", "type": "Bool"},
            ]
        }
    }
    form = _form(
        "interval",
        "interval_add",
        [
            ("a", "Interval"),
            ("b", "Interval"),
            ("xs", "List[Float64]"),
            ("m", "List[List[Float64]]"),
        ],
        structs=structs,
    )
    args = examples.synthesize(form)
    assert args["a"] == {"lo": 0.0, "hi": 1.0, "empty": False} == args["b"]
    assert args["xs"] == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert len(args["m"]) == examples.SIDE and all(len(row) == examples.SIDE for row in args["m"])
    # the Playground's own validation accepts the proposal as typed
    values = playground.parse_inputs(form, args)
    assert values[0] == {"lo": 0.0, "hi": 1.0, "empty": False}


def test_count_relations_hold_exactly_and_indexes_are_zero():
    rel_count = {"bounds": ["v"], "factors": ["n"], "plus": 0, "role": "count", "scope": "length"}
    rel_matrix = {
        "bounds": ["data"],
        "factors": ["rows", "cols"],
        "plus": 0,
        "role": "count",
        "scope": "length",
    }
    rel_index = {"bounds": ["v"], "factors": ["i"], "plus": 1, "role": "index", "scope": "length"}
    form = _form(
        "stats",
        "pctile",
        [
            ("v", "List[Float64]"),
            ("n", "Int"),
            ("data", "List[Float64]"),
            ("rows", "Int"),
            ("cols", "Int"),
            ("i", "Int"),
        ],
        relations=[rel_count, rel_matrix, rel_index],
    )
    args = examples.synthesize(form)
    assert args["n"] == len(args["v"]) == examples.COUNT
    assert args["rows"] == args["cols"] == examples.SIDE and len(args["data"]) == examples.SIDE**2
    assert args["i"] == 0
    named = playground.named_args(form.fields, playground.parse_inputs(form, args))
    playground.enforce_count_relations(form, named)  # raises when a count outruns its list


def test_plain_args_are_the_crash_gates_shapes():
    form = _form(
        "regression_tree",
        "predict_single",
        [("tree", "List[Int]"), ("x", "Float64"), ("k", "Int"), ("flag", "Bool"), ("s", "String")],
    )
    plain = examples.plain_args(form)
    assert plain == {"tree": [2] * 8, "x": 0.5, "k": 2, "flag": True, "s": "algenta"}


def test_for_form_prefers_the_verified_file_and_falls_back_to_synthesis(tmp_path):
    form = _form("stats", "compute_mean", [("v", "List[Float64]"), ("n", "Int")])
    (tmp_path / "stats.json").write_text(
        json.dumps(
            {
                "functions": {
                    "stats.compute_mean": {"args": {"v": [9.0, 8.0], "n": 2}, "verified": True}
                }
            }
        )
    )
    assert examples.for_form(form, "stats", tmp_path) == {"v": [9.0, 8.0], "n": 2}
    other = _form("stats", "compute_std", [("v", "List[Float64]"), ("n", "Int")])
    assert examples.for_form(other, "stats", tmp_path) == examples.synthesize(other)
    assert examples.for_form(other, "stats", None) == examples.synthesize(other)


def test_verified_files_cover_every_family_and_mostly_verify():
    """One file per published family; the kernel answered at least 95 % of the proposals."""
    files = sorted(p.stem for p in EXAMPLES_DIR.glob("*.json"))
    assert files == sorted(playground.FAMILIES), files
    total = verified = 0
    for family in files:
        data = json.loads((EXAMPLES_DIR / f"{family}.json").read_text())
        functions = data["functions"]
        assert functions, family
        for qual, entry in functions.items():
            assert all(  # a function without parameters opens with no boxes (uuid4)
                v is not None and v != "" for v in entry["args"].values()
            ), qual
            total += 1
            verified += int(entry["verified"])
    assert total > 5000 and verified / total >= 0.95, (verified, total)
