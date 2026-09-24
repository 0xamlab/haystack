"""algenta_spaces.playground — contract -> form -> validated call -> snippet, offline.

The contract fixtures were extracted once from the real `torch25-cpu-aarch64-darwin` kernels
(`tests/spaces/integration/test_playground_live.py` asserts they still match the Hub). No kernel,
torch or gradio import happens here; the "kernel" is a fake that records `execute` calls.
"""

from __future__ import annotations

import builtins
import io
import json
import re
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from algenta_spaces import playground as pg
from algenta_spaces import runtime, shell

FIXTURES = Path(__file__).resolve().parent / "fixtures"
STATS_FIXTURE = FIXTURES / "contract_algenta_stats.json"
HERO_FIXTURE = FIXTURES / "hero_contracts.json"
FIXTURE_BUDGET = 500 * 1024


class FakeKernel:
    """What `get_kernel` returns, reduced to the surface the playground touches."""

    def __init__(self, contract: dict, excluded: list[str] | None = None, result: Any = None):
        self.CONTRACT = contract
        self.excluded_functions = list(excluded or [])
        self.calls: list[tuple[str, str, list]] = []
        self._result = result

    def execute(self, module: str, function: str, args: list | dict | None = None):
        self.calls.append((module, function, list(args or [])))
        return self._result


@pytest.fixture(scope="module")
def stats_record() -> dict:
    return json.loads(STATS_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def stats(stats_record: dict) -> FakeKernel:
    return FakeKernel(
        stats_record["contract"], stats_record["excluded_functions"], result=[1.0, 0.5]
    )


@pytest.fixture(scope="module")
def hero_records() -> dict:
    return json.loads(HERO_FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture
def hero_kernels(stats_record: dict, hero_records: dict) -> dict[str, FakeKernel]:
    kernels = {
        family: FakeKernel(record["contract"], record["excluded_functions"])
        for family, record in hero_records.items()
    }
    kernels["stats"] = FakeKernel(stats_record["contract"], stats_record["excluded_functions"])
    return kernels


def form(kernel: FakeKernel, module: str, function: str) -> pg.Form:
    return pg.form_spec(kernel, module, function)


# ---------------------------------------------------------------------------
# Published facts mirrored as data
# ---------------------------------------------------------------------------


def test_trust_and_exclusions_mirror_capabilities_json(repo_root: Path):
    caps = json.loads(
        (repo_root / "docs" / "hf-kernels" / "release" / "capabilities.json").read_text("utf-8")
    )
    assert list(pg.TRUST) == sorted(caps["publication_state"]["capped_v1_shas"])
    assert list(pg.EXCLUDED_FUNCTIONS) == sorted(caps["excluded_functions"])
    assert len(pg.TRUST) == 20


def test_families_are_the_nineteen_published_ones():
    assert len(pg.FAMILIES) == 19
    assert "algenta" not in pg.FAMILIES
    assert {"stats", "text", "graph", "llm", "bits-time"} <= set(pg.FAMILIES)


def test_fixtures_carry_provenance_and_fit_the_budget(stats_record: dict, hero_records: dict):
    assert STATS_FIXTURE.stat().st_size < FIXTURE_BUDGET
    assert HERO_FIXTURE.stat().st_size < FIXTURE_BUDGET
    assert stats_record["repo_id"] == "thyn-ai/algenta-stats"
    assert stats_record["variant"] == "torch25-cpu-aarch64-darwin"
    assert runtime.is_sha(stats_record["revision"])
    assert set(stats_record["contract"]) == {"modules", "status_names"}
    for family, record in hero_records.items():
        assert record["repo_id"] == pg.repo_id(family)
        assert record["contract"]["modules"], family


# ---------------------------------------------------------------------------
# Repo ids and type mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("spelling", ["stats", "algenta-stats", "thyn-ai/algenta-stats", " stats "])
def test_repo_id_accepts_every_spelling(spelling: str):
    assert pg.repo_id(spelling) == "thyn-ai/algenta-stats"
    assert pg.family_of(spelling) == "stats"


def test_repo_id_refuses_unpublished_families():
    with pytest.raises(pg.PlaygroundError):
        pg.repo_id("quantum")
    with pytest.raises(pg.PlaygroundError):
        pg.repo_id("someone-else/algenta-stats")
    assert pg.family_of("thyn-ai/algenta") == "algenta"


@pytest.mark.parametrize(
    ("type_name", "kind"),
    [
        ("Int", "int"),
        ("UInt8", "int"),
        ("UInt64", "int"),
        ("Float64", "float"),
        ("Float32", "float"),
        ("Bool", "bool"),
        ("String", "str"),
        ("List[Float64]", "json"),
        ("List[List[Int]]", "json"),
        ("WeightedEdge", "json"),
        ("None", "json"),
    ],
)
def test_field_kind_mapping(type_name: str, kind: str):
    assert pg.field_kind(type_name) == kind


def test_type_words_are_plain_language():
    structs = {"WeightedEdge": {"name": "WeightedEdge", "fields": [{"name": "src", "type": "Int"}]}}
    assert pg.type_words("UInt8") == "an int from 0 to 255"
    assert pg.type_words("List[Float64]") == "a list of numbers"
    assert pg.type_words("List[UInt16]") == "a list of ints from 0 to 65535"
    assert pg.type_words("List[List[Int]]") == "a list of lists of ints"
    assert pg.type_words("List[WeightedEdge]") == "a list of WeightedEdge objects"
    assert pg.type_words("WeightedEdge", structs) == "a WeightedEdge object with keys src"
    assert pg.type_words("Mystery") == "a Mystery object"
    assert pg.list_inner("List[Int]") == "Int"
    assert pg.list_inner("Int") is None


# ---------------------------------------------------------------------------
# form_spec
# ---------------------------------------------------------------------------


def test_form_spec_for_the_hero_z_test(stats: FakeKernel):
    spec = form(stats, "ab_testing", "z_test_proportions")
    assert isinstance(spec, pg.Form)
    assert spec.names == ("successes_a", "n_a", "successes_b", "n_b")
    assert [f.kind for f in spec] == ["int"] * 4
    assert all(f.required for f in spec)
    assert spec[0].help == "Successes in group A. — an int"
    assert spec.return_type == "List[Float64]"
    assert spec.doc == "Two-proportion z-test."
    assert len(spec) == 4 and list(spec) == list(spec.fields)


def test_form_spec_marks_kernel_defaults_optional(stats: FakeKernel):
    spec = form(stats, "ab_testing", "sample_size_proportion")
    by_name = {f.name: f for f in spec}
    assert by_name["p1"].required and by_name["p2"].required
    assert not by_name["alpha"].required and not by_name["power"].required
    assert by_name["alpha"].default is None  # the default lives in the kernel


def test_form_spec_struct_and_list_fields(hero_kernels: dict[str, FakeKernel]):
    spec = form(hero_kernels["graph"], "graph.weighted", "shortest_path_dijkstra")
    edges = {f.name: f for f in spec}["edges"]
    assert edges.kind == "json"
    assert edges.list_of == "WeightedEdge"
    assert "a list of WeightedEdge objects" in edges.help
    assert "WeightedEdge" in spec.structs
    rms = form(hero_kernels["llm"], "normk.rmsnorm", "rmsnorm_fwd_flat")
    assert len(rms.count_relations) == 2
    assert {f.name: f.kind for f in rms} == {
        "x": "json",
        "gamma": "json",
        "n_rows": "int",
        "n_cols": "int",
        "eps": "float",
    }


def test_form_spec_refuses_unknown_functions(stats: FakeKernel):
    with pytest.raises(pg.UnknownFunctionError) as unknown_module:
        form(stats, "no_such_module", "f")
    assert unknown_module.value.module == "no_such_module"
    with pytest.raises(pg.UnknownFunctionError, match="ab_testing.no_such is not part"):
        form(stats, "ab_testing", "no_such")
    with pytest.raises(LookupError):
        form(stats, "ab_testing", "no_such")


def test_form_spec_refuses_excluded_functions(stats_record: dict):
    kernel = FakeKernel(stats_record["contract"], ["ab_testing.z_test_proportions"])
    with pytest.raises(pg.ExcludedFunctionError, match="not callable in-process"):
        form(kernel, "ab_testing", "z_test_proportions")
    whole_module = FakeKernel(stats_record["contract"], ["stat_tests.*"])
    with pytest.raises(pg.ExcludedFunctionError):
        form(whole_module, "stat_tests", "pearson_r")
    assert pg.is_excluded("env", "get", pg.EXCLUDED_FUNCTIONS)
    assert pg.is_excluded("trie", "insert")
    assert not pg.is_excluded("ab_testing", "z_test_proportions")


def test_list_functions_drops_exclusions_and_is_sorted(stats_record: dict):
    kernel = FakeKernel(stats_record["contract"], ["ab_testing.z_test_proportions", "sampling.*"])
    listed = pg.list_functions(kernel)
    assert listed == sorted(listed)
    assert ("ab_testing", "z_test_proportions") not in listed
    assert not any(module == "sampling" for module, _ in listed)
    assert ("stat_tests", "pearson_r") in listed
    assert pg.excluded_of(kernel)[:2] == (
        "ab_testing.z_test_proportions",
        "column_rank.run_column_rank",
    )


def test_status_name_reads_the_engine_vocabulary(hero_kernels: dict[str, FakeKernel]):
    llm = hero_kernels["llm"]
    ok = llm.CONTRACT["status_names"]["normk.contract.norm_status_name"]
    ok_code = next(int(code) for code, name in ok.items() if pg.is_ok_status(name))
    assert ok_code != 0  # engines do not use zero for ok; a card must ask by name
    assert pg.is_ok_status(pg.status_name(llm, "normk.rmsnorm", ok_code))
    assert pg.status_name(llm, "normk.rmsnorm", ok_code + 1) == "empty_dimension"
    llmk = pg.status_name(llm, "llmk.generate", 560)
    assert llmk == "llmk_ok" and pg.is_ok_status(llmk)
    assert pg.status_name(llm, "normk.rmsnorm", 10**9) is None
    assert pg.status_name(hero_kernels["graph"], "graph.weighted", 0) is None  # no vocabulary
    assert pg.is_ok_status(None) and pg.is_ok_status("ok") and not pg.is_ok_status("shape_mismatch")
    with pytest.raises(pg.UnknownFunctionError):
        pg.status_name(llm, "no_such_module", 0)


def test_contract_of_accepts_kernels_and_mappings(stats_record: dict):
    assert pg.contract_of(stats_record["contract"]) is stats_record["contract"]
    with pytest.raises(TypeError):
        pg.contract_of(object())
    with pytest.raises(TypeError):
        pg.excluded_of({"modules": {}, "excluded_functions": "env.*"})


# ---------------------------------------------------------------------------
# parse_inputs — the kernel wrapper's rules, before the ABI
# ---------------------------------------------------------------------------


def test_parse_inputs_coerces_control_text_into_typed_arguments(stats: FakeKernel):
    spec = form(stats, "ab_testing", "z_test_proportions")
    raw = {"successes_a": "200", "n_a": 1000.0, "successes_b": " 260 ", "n_b": 1_000}
    assert pg.parse_inputs(spec, raw) == [200, 1000, 260, 1000]


def test_parse_inputs_optional_tail_can_be_left_to_the_kernel(stats: FakeKernel):
    spec = form(stats, "ab_testing", "sample_size_proportion")
    assert pg.parse_inputs(spec, {"p1": 0.1, "p2": 0.12}) == [0.1, 0.12]
    assert pg.parse_inputs(spec, {"p1": 0.1, "p2": 0.12, "alpha": ""}) == [0.1, 0.12]
    assert pg.parse_inputs(spec, {"p1": 0.1, "p2": 0.12, "alpha": 0.01}) == [0.1, 0.12, 0.01]
    with pytest.raises(pg.ValidationError) as err:
        pg.parse_inputs(spec, {"p1": 0.1, "p2": 0.12, "power": 0.9})
    assert err.value.field == "alpha"
    assert "defaults fill only from the right" in err.value.reason


@pytest.mark.parametrize(
    ("raw", "field_name", "phrase"),
    [
        ({"n_a": "abc"}, "n_a", "must be an int"),
        ({"n_a": 12.5}, "n_a", "whole number"),
        ({"n_a": True}, "n_a", "not a bool"),
        ({"n_a": 1 << 63}, "n_a", "browser can enter exactly"),
        ({"n_a": "9223372036854775808"}, "n_a", "64-bit"),
        ({"n_a": (1 << 53) + 1}, "n_a", "browser can enter exactly"),
        ({"n_a": float(1 << 53)}, "n_a", "browser can enter exactly"),
        ({"n_a": -(1 << 53)}, "n_a", "browser can enter exactly"),
        ({"n_a": None}, "n_a", "is required"),
        ({"n_a": "  "}, "n_a", "is required"),
        ({"n_a": [1]}, "n_a", "must be an int"),
        ({"bogus": 1}, "bogus", "not an argument"),
    ],
)
def test_parse_inputs_rejects_bad_ints(stats: FakeKernel, raw: dict, field_name: str, phrase: str):
    spec = form(stats, "ab_testing", "z_test_proportions")
    full = {"successes_a": 1, "n_a": 2, "successes_b": 3, "n_b": 4}
    full.update(raw)
    with pytest.raises(pg.ValidationError) as err:
        pg.parse_inputs(spec, full)
    assert err.value.field == field_name
    assert phrase in err.value.reason
    assert str(err.value).startswith(f"{field_name}: ")


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", float("nan"), float("inf"), "1e999", "x"])
def test_parse_inputs_rejects_non_finite_floats(stats: FakeKernel, bad: Any):
    spec = form(stats, "ab_testing", "sample_size_proportion")
    with pytest.raises(pg.ValidationError) as err:
        pg.parse_inputs(spec, {"p1": bad, "p2": 0.2})
    assert err.value.field == "p1"
    assert "number" in err.value.reason
    with pytest.raises(pg.ValidationError, match="p2: must be a number, not a bool"):
        pg.parse_inputs(spec, {"p1": 0.1, "p2": True})


def test_parse_inputs_lists_json_and_element_types(stats: FakeKernel):
    spec = form(stats, "stat_tests", "pearson_r")
    assert pg.parse_inputs(spec, {"x": "[1, 2, 3]", "y": [1.5, 2.5, 3.5]}) == [
        [1.0, 2.0, 3.0],
        [1.5, 2.5, 3.5],
    ]
    with pytest.raises(pg.ValidationError, match=r"x: x\[1\] must be a number"):
        pg.parse_inputs(spec, {"x": [1, "two", 3], "y": [1, 2, 3]})
    with pytest.raises(pg.ValidationError, match="x: must be a list of numbers"):
        pg.parse_inputs(spec, {"x": "3.0", "y": [1, 2, 3]})
    with pytest.raises(pg.ValidationError, match="x: is not valid JSON"):
        pg.parse_inputs(spec, {"x": "[1, 2,", "y": [1, 2, 3]})
    with pytest.raises(pg.ValidationError, match=r"x: x\[0\] must be a finite number"):
        pg.parse_inputs(spec, {"x": [float("nan")], "y": [1.0]})
    with pytest.raises(
        pg.ValidationError, match="y: holds 3 elements; the playground accepts up to 2"
    ):
        pg.parse_inputs(spec, {"x": [1, 2], "y": [1, 2, 3]}, max_list_elements=2)


def test_parse_inputs_structs_need_exactly_the_declared_keys(hero_kernels: dict[str, FakeKernel]):
    spec = form(hero_kernels["graph"], "graph.weighted", "shortest_path_dijkstra")
    good = {"n": 2, "edges": [{"weight": 1.5, "dst": 1, "src": 0}], "source": 0}
    n, edges, source = pg.parse_inputs(spec, good)
    assert (n, source) == (2, 0)
    assert edges == [{"src": 0, "dst": 1, "weight": 1.5}]  # kernel field order
    assert list(edges[0]) == ["src", "dst", "weight"]
    with pytest.raises(
        pg.ValidationError, match=r"edges\[0\] must have exactly the keys src, dst, weight"
    ):
        pg.parse_inputs(spec, {"n": 2, "edges": [{"src": 0, "dst": 1}], "source": 0})
    with pytest.raises(pg.ValidationError, match=r"edges\[0\] must have exactly the keys"):
        pg.parse_inputs(
            spec, {"n": 2, "edges": [{"src": 0, "dst": 1, "weight": 1, "x": 1}], "source": 0}
        )
    with pytest.raises(pg.ValidationError, match=r"edges\[0\].src must be an int"):
        pg.parse_inputs(spec, {"n": 2, "edges": [{"src": 0.5, "dst": 1, "weight": 1}], "source": 0})
    with pytest.raises(pg.ValidationError, match=r"edges\[0\] must be an object with keys"):
        pg.parse_inputs(spec, {"n": 2, "edges": [[0, 1, 1.0]], "source": 0})


def test_parse_inputs_enforces_count_relations(hero_kernels: dict[str, FakeKernel]):
    spec = form(hero_kernels["llm"], "normk.rmsnorm", "rmsnorm_fwd_flat")
    ok = {"x": [1.0] * 8, "gamma": [1.0] * 4, "n_rows": 2, "n_cols": 4, "eps": 1e-6}
    assert len(pg.parse_inputs(spec, ok)) == 5
    with pytest.raises(pg.ValidationError) as err:
        pg.parse_inputs(spec, {**ok, "x": [1.0] * 7})
    assert err.value.field == "x"
    assert err.value.reason == "n_rows=2, n_cols=4 counts more elements than x holds (7)"
    with pytest.raises(
        pg.ValidationError, match=r"gamma: n_cols=4 counts more elements than gamma holds \(3\)"
    ):
        pg.parse_inputs(spec, {**ok, "gamma": [1.0] * 3})
    # a longer list is allowed (the count bounds the prefix), a zero count always fits
    assert pg.parse_inputs(spec, {**ok, "x": [1.0] * 9})[0] == [1.0] * 9
    assert pg.parse_inputs(spec, {**ok, "n_rows": 0})[2] == 0


def test_whole_numbers_below_two_to_the_53_stay_exact_and_text_digits_always_do(stats: FakeKernel):
    """A number box hands the server a JavaScript double, so a JSON number at or above 2^53 is
    refused (it may already be rounded — 9007199254740993 typed, 9007199254740992 received);
    digits typed as text are exact and go to the 64-bit check instead."""
    spec = form(stats, "ab_testing", "z_test_proportions")
    full = {"successes_a": 1, "n_a": 2, "successes_b": 3, "n_b": 4}
    exact = (1 << 53) - 1
    assert pg.parse_inputs(spec, {**full, "n_a": exact}) == [1, exact, 3, 4]
    assert pg.parse_inputs(spec, {**full, "n_a": float(exact)}) == [1, exact, 3, 4]
    assert pg.parse_inputs(spec, {**full, "n_a": str((1 << 63) - 1)}) == [1, (1 << 63) - 1, 3, 4]
    assert pg.parse_inputs(spec, {**full, "n_a": str((1 << 53) + 1)}) == [1, (1 << 53) + 1, 3, 4]
    with pytest.raises(pg.ValidationError) as err:
        pg.parse_inputs(spec, {**full, "n_a": 1 << 53})
    assert err.value.reason == pg.REASON_ABOVE_BROWSER_RANGE
    assert pg.BROWSER_EXACT_MAX == 9007199254740992
    assert "_" not in pg.REASON_ABOVE_BROWSER_RANGE and "!" not in pg.REASON_ABOVE_BROWSER_RANGE


def test_field_rules_refuse_what_the_contract_cannot_say(stats: FakeKernel):
    """Counts are never negative, successes never exceed trials, levels lie strictly inside
    (0, 1): the `ab_testing` table, applied by `parse_inputs` in field order."""
    z = form(stats, "ab_testing", "z_test_proportions")
    cases = [
        (
            {"successes_a": -5, "n_a": 1000, "successes_b": 65, "n_b": 1000},
            "successes_a",
            pg.REASON_NEGATIVE,
        ),
        (
            {"successes_a": 50, "n_a": 0, "successes_b": 65, "n_b": 1000},
            "n_a",
            "must be at least 1",
        ),
        (
            {"successes_a": 2000, "n_a": 1000, "successes_b": 65, "n_b": 1000},
            "successes_a",
            "cannot exceed n_a",
        ),
        (
            {"successes_a": 50, "n_a": 1000, "successes_b": 1001, "n_b": 1000},
            "successes_b",
            "cannot exceed n_b",
        ),
        (
            {"successes_a": 50, "n_a": 1000, "successes_b": 65, "n_b": -1},
            "n_b",
            "must be at least 1",
        ),
    ]
    for raw, field_name, reason in cases:
        with pytest.raises(pg.ValidationError) as err:
            pg.parse_inputs(z, raw)
        assert (err.value.field, err.value.reason) == (field_name, reason), raw
    assert pg.parse_inputs(z, {"successes_a": 0, "n_a": 1, "successes_b": 1, "n_b": 1}) == [
        0,
        1,
        1,
        1,
    ]
    assert pg.field_rule_error(
        "ab_testing", "z_test_proportions", {"successes_a": 3, "n_a": 2}
    ) == (
        "successes_a",
        "cannot exceed n_a",
    )
    assert pg.field_rule_error("ab_testing", "z_test_proportions", {"successes_a": 3}) is None
    assert pg.field_rule_error("text.fuzzy", "levenshtein_distance", {"a": "x"}) is None
    ci = form(stats, "ab_testing", "confidence_interval_proportion")
    with pytest.raises(pg.ValidationError, match="confidence: must be above 0 and below 1"):
        pg.parse_inputs(ci, {"successes": 5, "n": 10, "confidence": 1.0})
    assert pg.parse_inputs(ci, {"successes": 5, "n": 10, "confidence": 0.95}) == [5, 10, 0.95]
    sig = form(stats, "ab_testing", "is_significant")
    assert pg.parse_inputs(sig, {"p_value": 0.0, "alpha": 0.05}) == [0.0, 0.05]
    with pytest.raises(pg.ValidationError, match="p_value: must be between 0 and 1"):
        pg.parse_inputs(sig, {"p_value": 1.5, "alpha": 0.05})
    mde = form(stats, "ab_testing", "mde")
    with pytest.raises(pg.ValidationError, match="n: must be at least 1"):
        pg.parse_inputs(mde, {"n": 0, "baseline_rate": 0.1, "alpha": 0.05, "power": 0.8})
    # every rule names a real field of a real function of the fixture, in field order
    contract = stats.CONTRACT["modules"]
    for qualname, rules in pg.FIELD_RULES.items():
        module, function = qualname.rsplit(".", 1)
        params = [p["name"] for p in contract[module]["functions"][function]["params"]]
        for rule in rules:
            assert rule.field in params, (qualname, rule)
            if rule.kind == "at_most":
                assert rule.bound in params, (qualname, rule)
    with pytest.raises(ValueError):
        pg.FieldRule("n", "bogus")
    with pytest.raises(ValueError):
        pg.FieldRule("n", "at_most")
    with pytest.raises(ValueError):
        pg.FieldRule("n", "min", 1.5)


def test_count_fits_matches_the_kernel_guard():
    assert pg.count_fits([2, 4], 8)
    assert not pg.count_fits([2, 4], 7)
    assert pg.count_fits([0, 99], 1)
    assert pg.count_fits([-1], 0)  # a negative count is a sentinel, not a length
    assert not pg.count_fits([-1], 0, role="index")
    assert not pg.count_fits([1], -1)


def test_parse_inputs_bools_strings_and_uint_ranges():
    contract = {
        "modules": {
            "m": {
                "structs": {},
                "functions": {
                    "f": {
                        "name": "f",
                        "return_type": "Bool",
                        "count_relations": [],
                        "params": [
                            {"name": "flag", "type": "Bool", "has_default": False},
                            {"name": "label", "type": "String", "has_default": False},
                            {"name": "byte", "type": "UInt8", "has_default": False},
                        ],
                    }
                },
            }
        },
        "status_names": {},
    }
    kernel = FakeKernel(contract)
    spec = form(kernel, "m", "f")
    assert pg.parse_inputs(spec, {"flag": "yes", "label": "", "byte": 255}) == [True, "", 255]
    assert pg.parse_inputs(spec, {"flag": False, "label": "héllo", "byte": "0"}) == [
        False,
        "héllo",
        0,
    ]
    with pytest.raises(pg.ValidationError, match="flag: must be true or false"):
        pg.parse_inputs(spec, {"flag": "maybe", "label": "", "byte": 1})
    with pytest.raises(pg.ValidationError, match="label: must be a string"):
        pg.parse_inputs(spec, {"flag": True, "label": 3, "byte": 1})
    with pytest.raises(pg.ValidationError, match="byte: must be an int from 0 to 255"):
        pg.parse_inputs(spec, {"flag": True, "label": "", "byte": 256})
    with pytest.raises(pg.ValidationError, match="label: contains unpaired surrogate"):
        pg.parse_inputs(spec, {"flag": True, "label": "\ud800", "byte": 1})
    with pytest.raises(pg.ValidationError, match="label: is required"):
        pg.parse_inputs(spec, {"flag": True, "label": None, "byte": 1})


def test_coerce_and_to_plain_accept_array_likes():
    class Arrayish:
        def tolist(self):
            return [1.0, 2.0]

    spec = pg.FieldSpec(name="x", kind="json", type_name="List[Float64]")
    assert pg.coerce(spec, Arrayish()) == [1.0, 2.0]
    assert pg.coerce(spec, (1, 2)) == [1, 2]
    assert pg.to_plain({"a": (1, Arrayish())}) == {"a": [1, [1.0, 2.0]]}
    assert pg.to_plain(b"\x01\x02") == [1, 2]
    with pytest.raises(pg.ValidationError, match="x: must be JSON"):
        pg.coerce(spec, 3.5)


def test_field_spec_validates_itself():
    with pytest.raises(ValueError, match="kind must be one of"):
        pg.FieldSpec(name="x", kind="tensor", type_name="Int")
    with pytest.raises(ValueError, match="not an identifier"):
        pg.FieldSpec(name="not valid", kind="int", type_name="Int")


def test_named_args_pairs_values_with_fields(stats: FakeKernel):
    spec = form(stats, "ab_testing", "z_test_proportions")
    assert pg.named_args(spec, [1, 2]) == {"successes_a": 1, "n_a": 2}
    with pytest.raises(ValueError):
        pg.named_args(spec, [1, 2, 3, 4, 5])


# ---------------------------------------------------------------------------
# Snippets
# ---------------------------------------------------------------------------

HERO_ARGS = {"successes_a": 200, "n_a": 1000, "successes_b": 260, "n_b": 1000}
LEFTOVER = re.compile(r"\{[A-Za-z_][A-Za-z0-9_.]*\}")


def _exec_capturing(code: str, modules: dict[str, types.ModuleType]) -> tuple[dict, str]:
    """Run a snippet with fake top-level modules installed and `print` captured."""
    saved = {name: sys.modules.get(name) for name in modules}
    out = io.StringIO()
    namespace: dict[str, Any] = {"__builtins__": builtins}
    try:
        sys.modules.update(modules)
        real_print = builtins.print
        builtins.print = lambda *a, **k: real_print(*a, file=out, **k)
        try:
            exec(compile(code, "<snippet>", "exec"), namespace)  # noqa: S102 - the snippet under test
        finally:
            builtins.print = real_print
    finally:
        for name, module in saved.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module
    return namespace, out.getvalue()


def test_kernels_snippet_is_exact():
    text = pg.snippet("stats", "ab_testing", "z_test_proportions", HERO_ARGS, mode="kernels")
    trust = "".join(f'    "{r}",\n' for r in pg.TRUST)
    expected = (
        "# pip install kernels torch\n"
        "from kernels import get_kernel\n\n"
        f"TRUST = [\n{trust}]\n"
        'k = get_kernel("thyn-ai/algenta-stats", version=1, backend="cpu", trust_remote_code=TRUST)\n'
        "result = k.ab_testing.z_test_proportions(\n"
        "    successes_a=200,\n"
        "    n_a=1000,\n"
        "    successes_b=260,\n"
        "    n_b=1000,\n"
        ")\n"
        "print(result)\n"
    )
    assert text == expected
    assert LEFTOVER.search(text) is None
    compile(text, "<kernels>", "exec")


def test_kernels_snippet_runs_against_a_fake_kernels_module():
    text = pg.snippet(
        "text",
        "text.fuzzy",
        "levenshtein_distance",
        {"a": "kitten", "b": "sitting"},
        mode="kernels",
    )
    seen: dict[str, Any] = {}

    def levenshtein_distance(a: str, b: str) -> int:
        seen["call"] = (a, b)
        return 3

    fake = types.ModuleType("kernels")

    def get_kernel(repo, *, version, backend, trust_remote_code):
        seen["load"] = (repo, version, backend, list(trust_remote_code))
        return types.SimpleNamespace(
            text=types.SimpleNamespace(
                fuzzy=types.SimpleNamespace(levenshtein_distance=levenshtein_distance)
            )
        )

    fake.get_kernel = get_kernel  # type: ignore[attr-defined]
    namespace, printed = _exec_capturing(text, {"kernels": fake})
    assert seen["load"] == ("thyn-ai/algenta-text", 1, "cpu", list(pg.TRUST))
    assert seen["call"] == ("kitten", "sitting")
    assert namespace["result"] == 3
    assert printed == "3\n"
    assert 'k.text.fuzzy.levenshtein_distance(a="kitten", b="sitting")' in text


def test_sdk_snippet_is_exact_and_runs():
    text = pg.snippet(
        "stats", "ab_testing", "z_test_proportions", {"successes_a": 200, "n_a": 1000}, mode="sdk"
    )
    assert text == (
        "# pip install algenta\n"
        "from algenta import libraries\n\n"
        "libs = libraries()\n"
        'result = libs.module("ab_testing").z_test_proportions(successes_a=200, n_a=1000)\n'
        "print(result)\n"
    )
    seen: dict[str, Any] = {}

    class Module:
        def __init__(self, name: str) -> None:
            seen["module"] = name

        def z_test_proportions(self, **kwargs: Any) -> list[float]:
            seen["kwargs"] = kwargs
            return [1.0, 0.05]

    class Libs:
        def module(self, name: str) -> Module:
            return Module(name)

    fake = types.ModuleType("algenta")
    fake.libraries = lambda: Libs()  # type: ignore[attr-defined]
    namespace, printed = _exec_capturing(text, {"algenta": fake})
    assert seen == {"module": "ab_testing", "kwargs": {"successes_a": 200, "n_a": 1000}}
    assert namespace["result"] == [1.0, 0.05]
    assert printed == "[1.0, 0.05]\n"


def test_mcp_snippet_is_the_tools_call_frame():
    text = pg.snippet("stats", "ab_testing", "z_test_proportions", HERO_ARGS, mode="mcp")
    frame = json.loads(text)
    assert frame == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "execute_runtime_library",
            "arguments": {
                "module": "ab_testing",
                "function": "z_test_proportions",
                "args": HERO_ARGS,
            },
        },
    }
    assert text.endswith("}\n")
    positional = json.loads(
        pg.snippet("stats", "ab_testing", "z_test_proportions", (1, 2, 3, 4), mode="mcp")
    )
    assert positional["params"]["arguments"]["args"] == [1, 2, 3, 4]
    assert (
        json.loads(pg.snippet("stats", "m", "f", None, mode="mcp"))["params"]["arguments"]["args"]
        is None
    )
    with pytest.raises(ValueError):
        pg.snippet("stats", "m", "f", {"x": float("nan")}, mode="mcp")


def test_snippet_positional_args_strings_and_nesting():
    args = [1, 2.5, True, None, 'it\'s "quoted" — ünïcode', [1, [2, 3]], {"k": [1.0]}]
    text = pg.snippet("graph", "graph.weighted", "f", args, mode="sdk")
    statement = text.split("result = ", 1)[1].split("\nprint(result)", 1)[0]
    call = statement.replace('libs.module("graph.weighted").f', "(lambda *a: a)", 1)
    assert eval(call, {}) == tuple(args)  # noqa: S307 - the rendered literal under test
    assert pg.py_literal("naïve") == '"naïve"'
    assert pg.py_literal(True) == "True" and pg.py_literal(None) == "None"
    assert pg.py_literal({"a": 1}) == '{"a": 1}'
    with pytest.raises(ValueError):
        pg.py_literal(float("inf"))
    with pytest.raises(TypeError):
        pg.py_literal(object())


def test_render_call_wraps_long_calls_one_argument_per_line():
    short = pg.render_call("f", {"a": 1})
    assert short == "f(a=1)"
    long_args = {f"argument_{i}": [float(i)] * 6 for i in range(6)}
    text = pg.render_call("result = k.m.f", long_args)
    assert text.startswith("result = k.m.f(\n    argument_0=")
    assert text.endswith(",\n)")
    assert all(len(line) <= 100 for line in text.splitlines())
    compile(text, "<call>", "exec")
    assert pg.render_call("f", None) == "f()"
    assert pg.render_call("f", [1, 2]) == "f(1, 2)"


def test_snippet_refuses_bad_modes_names_and_keywords():
    with pytest.raises(pg.PlaygroundError, match="mode must be one of"):
        pg.snippet("stats", "m", "f", {}, mode="curl")
    with pytest.raises(pg.PlaygroundError, match="not a module name"):
        pg.snippet("stats", "m-x", "f", {}, mode="sdk")
    with pytest.raises(pg.PlaygroundError, match="not a function name"):
        pg.snippet("stats", "m", "f()", {}, mode="sdk")
    with pytest.raises(pg.PlaygroundError, match="not a valid keyword"):
        pg.snippet("stats", "m", "f", {"bad name": 1}, mode="kernels")
    with pytest.raises(TypeError):
        pg.snippet("stats", "m", "f", 3, mode="sdk")
    with pytest.raises(TypeError):
        pg.snippet("stats", "m", "f", "text", mode="mcp")


def test_every_hero_renders_valid_snippets_in_every_mode():
    for hero in pg.HEROES:
        for mode in pg.MODES:
            text = pg.snippet(hero.family, hero.module, hero.function, hero.args, mode=mode)
            if mode == "mcp":
                json.loads(text)
            else:
                compile(text, f"<{hero.qualname}>", "exec")
                assert LEFTOVER.search(text) is None
            assert shell.banned_phrase(text) is None
            assert "@" not in text


# ---------------------------------------------------------------------------
# Hero functions
# ---------------------------------------------------------------------------


def test_hero_table_integrity():
    heroes = pg.hero_functions()
    assert heroes is pg.HEROES
    assert len(heroes) == pg.HERO_COUNT == 15
    assert len({(h.family, h.module, h.function) for h in heroes}) == 15
    assert {h.mode for h in heroes} == {"race", "run"}
    assert sum(h.mode == "race" for h in heroes) == 7
    assert {h.family for h in heroes} <= set(pg.FAMILIES)
    for hero in heroes:
        assert hero.args and all(isinstance(k, str) for k in hero.args)
        assert hero.incumbent and hero.note
        assert hero.repo.startswith("thyn-ai/algenta-")
        assert hero.qualname == f"{hero.module}.{hero.function}"
        for text in (hero.incumbent, hero.note):
            assert shell.banned_phrase(text) is None
            assert not shell.has_emoji(text)
    assert [h.qualname for h in pg.heroes_for("stats")] == [
        "ab_testing.z_test_proportions",
        "stat_tests.t_test_2sample",
    ]
    assert pg.heroes_for("thyn-ai/algenta-crypto")[0].function == "dhash_flat"


def test_every_hero_validates_against_the_real_darwin_contracts(
    hero_kernels: dict[str, FakeKernel],
):
    heroes = pg.hero_functions(hero_kernels)
    assert len(heroes) == 15
    assert {h.family for h in heroes} <= set(hero_kernels)
    for hero in heroes:
        values = pg.check_hero(hero, hero_kernels[hero.family])
        assert len(values) == len(hero.args)
        # what would be sent is exactly what the table declares, once normalised
        spec = pg.form_spec(hero_kernels[hero.family], hero.module, hero.function)
        assert list(pg.named_args(spec, values)) == list(hero.args)


def test_hero_functions_accepts_repo_ids_and_reports_mismatches(
    hero_kernels: dict[str, FakeKernel],
):
    by_repo = {pg.repo_id(family): kernel for family, kernel in hero_kernels.items()}
    assert pg.hero_functions(by_repo) is pg.HEROES
    assert pg.hero_functions({}) is pg.HEROES
    wrong = pg.Hero(
        "stats", "ab_testing", "z_test_proportions", "x", "run", {"successes_a": 1}, "n"
    )
    with pytest.raises(pg.HeroMismatchError, match="n_a: is required"):
        pg.check_hero(wrong, hero_kernels["stats"])
    missing = pg.Hero("stats", "ab_testing", "nope", "x", "run", {"a": 1}, "n")
    with pytest.raises(pg.HeroMismatchError, match="ab_testing.nope is not part of this kernel"):
        pg.check_hero(missing, hero_kernels["stats"])
    with pytest.raises(pg.HeroMismatchError):
        pg.hero_functions({"stats": FakeKernel({"modules": {}, "status_names": {}})})


def test_hero_constructor_rejects_bad_entries():
    with pytest.raises(ValueError, match="mode must be one of"):
        pg.Hero("stats", "m", "f", "x", "sprint", {"a": 1}, "n")
    with pytest.raises(ValueError, match="not a kernel family"):
        pg.Hero("algenta", "m", "f", "x", "run", {"a": 1}, "n")
    with pytest.raises(ValueError, match="is excluded"):
        pg.Hero("bits-time", "env", "get", "x", "run", {"a": 1}, "n")


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------


def test_run_validates_then_executes_and_times(stats: FakeKernel):
    ticks = iter([10.0, 10.0015])
    result = pg.run(stats, "ab_testing", "z_test_proportions", HERO_ARGS, clock=lambda: next(ticks))
    assert isinstance(result, pg.RunResult)
    assert stats.calls == [("ab_testing", "z_test_proportions", [200, 1000, 260, 1000])]
    assert result.args == [200, 1000, 260, 1000]
    assert result.result == [1.0, 0.5]
    assert result.latency_ms == pytest.approx(1.5)
    assert result.qualname == "ab_testing.z_test_proportions"


def test_run_never_reaches_the_kernel_with_bad_input(stats: FakeKernel):
    with pytest.raises(pg.ValidationError):
        pg.run(stats, "ab_testing", "z_test_proportions", {**HERO_ARGS, "n_b": "ten"})
    with pytest.raises(pg.UnknownFunctionError):
        pg.run(stats, "ab_testing", "missing", {})
    with pytest.raises(pg.ValidationError, match="holds 3 elements"):
        pg.run(
            stats, "stat_tests", "pearson_r", {"x": [1, 2, 3], "y": [1, 2, 3]}, max_list_elements=2
        )
    assert stats.calls == []


def test_loaded_kernel_records_are_unwrapped(stats: FakeKernel):
    """`hubkernel.LoadedKernel` carries the module as `.kernel`; every entry point accepts it."""
    loaded = types.SimpleNamespace(family="algenta-stats", kernel=stats, variant="torch25-cpu")
    assert pg.native_module(loaded) is stats
    assert pg.native_module(stats) is stats
    assert pg.contract_of(loaded) is stats.CONTRACT
    assert pg.excluded_of(loaded) == pg.excluded_of(stats)
    assert pg.form_spec(loaded, "ab_testing", "z_test_proportions").names == (
        "successes_a",
        "n_a",
        "successes_b",
        "n_b",
    )
    outcome = pg.run(loaded, "ab_testing", "z_test_proportions", HERO_ARGS)
    assert outcome.result == [1.0, 0.5]
    assert stats.calls == [("ab_testing", "z_test_proportions", [200, 1000, 260, 1000])]
    with pytest.raises(TypeError):
        pg.contract_of(types.SimpleNamespace(kernel=object()))


def test_run_lets_kernel_errors_through(stats_record: dict):
    class Boom(FakeKernel):
        def execute(self, module, function, args=None):
            raise RuntimeError("count_exceeds_list_length")

    with pytest.raises(RuntimeError, match="count_exceeds_list_length"):
        pg.run(Boom(stats_record["contract"]), "ab_testing", "z_test_proportions", HERO_ARGS)
