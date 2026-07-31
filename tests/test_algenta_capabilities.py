"""Declared-capability surface tests: UNDECLARED is not False, and a typo raises.

No worker here — this surface reads the shipped library contract plus the declared
capability blocks, so it is pure metadata. The rule under test throughout is that
"we have not said" and "we have said no" are different answers.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_ALGENTA = _REPO_ROOT / "packages" / "algenta"
if str(_ALGENTA) not in sys.path:
    sys.path.insert(0, str(_ALGENTA))

from algenta.capabilities import (  # noqa: E402
    CAPABILITY_FIELDS,
    UNDECLARED,
    CapabilityCatalog,
    CapabilityError,
    CapabilityRecord,
    CountRelation,
    capabilities,
)

# ── fixtures: a small contract and a small manifest ───────────────────────────


@dataclass(frozen=True)
class _Fn:
    name: str


@dataclass(frozen=True)
class _Mod:
    import_path: str
    functions: tuple[_Fn, ...]


CONTRACT = (
    _Mod("stats", (_Fn("sort_values"), _Fn("mean"), _Fn("bootstrap_ci"))),
    _Mod("optimization.linear", (_Fn("lp_solve_default"), _Fn("lp_rhs_ranges"))),
    _Mod("sparse_numerics.csr", (_Fn("csr_matvec"),)),
)

MANIFEST = {
    "schema_version": 1,
    "modules": [
        {
            "name": "stats",
            "functions": [
                {
                    "name": "sort_values",
                    "capability": {
                        "deterministic": True,
                        "seed_requirements": "none",
                        "stateful": False,
                        "batch_capable": True,
                        "stream_capable": False,
                        "supported_dtypes": ["Float64"],
                        "complexity": "O(n log n)",
                        "backend": "mojo",
                        "surfaces": ["library_execute", "batch_execute"],
                        "count_relations": [{"factors": ["n"], "bounds": ["v"]}],
                        "golden_vectors": "stats/sort_values",
                        "benchmark": "bench_stats",
                        "docs": "engine/capabilities.md",
                        "version_introduced": "1.0.4",
                        "deprecation_state": "active",
                    },
                },
                {
                    # A declared block that stops short: it says nothing about batching.
                    "name": "bootstrap_ci",
                    "capability": {
                        "deterministic": False,
                        "seed_requirements": "required",
                        "stateful": False,
                        "complexity": "O(b n)",
                    },
                },
                # `mean` carries no entry at all.
            ],
        },
        {
            "name": "optimization.linear",
            "functions": [
                {
                    "name": "lp_solve_default",
                    # Inline spelling: the block's fields sit on the function entry.
                    "deterministic": True,
                    "seed_requirements": "optional",
                    "stateful": False,
                    "batch_capable": True,
                    "supported_dtypes": ["Float64", "Int"],
                    "complexity": "O(iterations * rows * cols)",
                    "count_relations": [
                        # a is row-major rows*cols; senses and b are one entry per row
                        {"factors": ["rows", "cols"], "bounds": ["a"]},
                        {"factors": ["rows"], "bounds": ["senses", "b"]},
                        {"factors": ["cols"], "bounds": ["c"]},
                    ],
                },
                {"name": "lp_rhs_ranges", "capability": {"deterministic": True}},
            ],
        },
        {
            "name": "sparse_numerics.csr",
            "functions": [
                {
                    "name": "csr_matvec",
                    "capability": {
                        "deterministic": True,
                        "count_relations": [
                            {"factors": ["nnz"], "bounds": ["values", "col_index"]},
                            {"factors": ["rows"], "bounds": ["row_ptr"], "plus": 1},
                            {
                                "factors": ["node"],
                                "bounds": ["adjacency"],
                                "plus": 1,
                                "role": "index",
                            },
                        ],
                    },
                }
            ],
        },
    ],
}


def _catalog(manifest=MANIFEST) -> CapabilityCatalog:
    return CapabilityCatalog(contract_modules=CONTRACT, manifest_payload=manifest)


# ── UNDECLARED is a third answer ──────────────────────────────────────────────


def test_a_function_with_no_block_is_undeclared_not_false():
    """The defect class this whole surface exists to avoid."""
    record = _catalog().describe("stats", "mean")
    assert record.has_block is False
    assert record.deterministic is UNDECLARED
    assert record.stateful is UNDECLARED
    assert record.count_relations is UNDECLARED
    assert record.undeclared_fields() == CAPABILITY_FIELDS
    assert record.declared_fields() == ()


def test_undeclared_refuses_to_be_truth_tested():
    """`if record.deterministic:` must not silently read as 'not deterministic'."""
    record = _catalog().describe("stats", "mean")
    with pytest.raises(TypeError) as excinfo:
        bool(record.deterministic)
    assert "UNDECLARED" in str(excinfo.value)
    assert repr(UNDECLARED) == "UNDECLARED"
    assert UNDECLARED is not False
    assert UNDECLARED != False  # noqa: E712 - the point is that it is not False


def test_declared_false_is_a_real_answer_and_stays_distinct():
    record = _catalog().describe("stats", "bootstrap_ci")
    assert record.has_block is True
    assert record.deterministic is False
    assert record.batch_capable is UNDECLARED


def test_as_dict_omits_undeclared_fields_instead_of_nulling_them():
    payload = _catalog().describe("stats", "bootstrap_ci").as_dict()
    assert "batch_capable" not in payload
    assert payload["deterministic"] is False
    assert payload["requires_seed"] is True
    assert "batch_capable" in payload["undeclared_fields"]
    assert "deterministic" not in payload["undeclared_fields"]

    bare = _catalog().describe("stats", "mean").as_dict()
    assert "requires_seed" not in bare
    assert set(bare["undeclared_fields"]) >= {"deterministic", "count_relations"}


def test_requires_seed_distinguishes_none_from_silence():
    catalog = _catalog()
    assert catalog.describe("stats", "sort_values").requires_seed is False
    assert catalog.describe("stats", "bootstrap_ci").requires_seed is True
    assert catalog.describe("stats", "mean").requires_seed is UNDECLARED
    # `optional` reads as "not required" but keeps its own third value.
    optional = catalog.describe("optimization.linear", "lp_solve_default")
    assert optional.requires_seed is False
    assert optional.seed_requirements == "optional"


def test_the_seed_filter_separates_none_from_optional():
    catalog = _catalog()
    assert {r.function for r in catalog.search(requires_seed=False)} == {
        "sort_values",
        "lp_solve_default",
    }
    assert {r.function for r in catalog.search(seed_requirements="none")} == {"sort_values"}
    assert {r.function for r in catalog.search(seed_requirements="optional")} == {
        "lp_solve_default"
    }
    with pytest.raises(CapabilityError) as excinfo:
        catalog.search(seed_requirements="maybe")
    assert excinfo.value.code == "invalid_arguments"


@pytest.mark.parametrize(
    ("kwargs", "field"),
    [
        ({"backend": "cuda"}, "backend"),
        ({"surface": "grpc"}, "surface"),
        ({"deprecation_state": "retired"}, "deprecation_state"),
    ],
)
def test_a_filter_value_outside_the_vocabulary_raises(kwargs, field):
    """Zero matches for a value no declaration can carry reads as 'nothing does that'."""
    with pytest.raises(CapabilityError) as excinfo:
        _catalog().search(**kwargs)
    assert excinfo.value.code == "invalid_arguments"
    assert excinfo.value.details["filter"] == field


# ── describe raises rather than returning nothing ─────────────────────────────


def test_describe_raises_on_an_unknown_module():
    with pytest.raises(CapabilityError) as excinfo:
        _catalog().describe("nope", "mean")
    assert excinfo.value.code == "module_not_registered"


def test_describe_raises_on_an_unknown_function():
    with pytest.raises(CapabilityError) as excinfo:
        _catalog().describe("stats", "nope")
    assert excinfo.value.code == "function_not_registered"
    assert excinfo.value.details == {"module": "stats", "function": "nope"}


def test_describe_rejects_blank_names():
    for module, function in (("", "mean"), ("stats", "")):
        with pytest.raises(CapabilityError) as excinfo:
            _catalog().describe(module, function)
        assert excinfo.value.code == "invalid_arguments"


def test_is_declared_rejects_an_unknown_field_name():
    record = _catalog().describe("stats", "sort_values")
    assert record.is_declared("deterministic") is True
    with pytest.raises(CapabilityError) as excinfo:
        record.is_declared("determinstic")
    assert excinfo.value.code == "invalid_arguments"


# ── search: matches, and what could not be judged ─────────────────────────────


def test_search_reports_undeclared_separately_from_non_matches():
    result = _catalog().search(deterministic=True)
    names = {(r.module, r.function) for r in result}
    assert names == {
        ("stats", "sort_values"),
        ("optimization.linear", "lp_solve_default"),
        ("optimization.linear", "lp_rhs_ranges"),
        ("sparse_numerics.csr", "csr_matvec"),
    }
    # bootstrap_ci declared False, so it is a genuine non-match, not undeclared.
    undeclared = {(u.module, u.function): u for u in result.undeclared}
    assert ("stats", "mean") in undeclared
    assert ("stats", "bootstrap_ci") not in undeclared
    assert undeclared[("stats", "mean")].missing == ("deterministic",)
    assert undeclared[("stats", "mean")].has_block is False
    assert result.scanned == 6
    assert result.total_matches == 4
    assert len(result) == 4


def test_a_block_that_omits_the_filtered_field_is_undeclared_not_excluded():
    result = _catalog().search(batch_capable=True)
    assert {(r.module, r.function) for r in result} == {
        ("stats", "sort_values"),
        ("optimization.linear", "lp_solve_default"),
    }
    partial = {u.function: u for u in result.undeclared}
    assert partial["bootstrap_ci"].has_block is True
    assert partial["bootstrap_ci"].missing == ("batch_capable",)
    assert partial["mean"].has_block is False


def test_multiple_filters_collect_every_missing_field():
    result = _catalog().search(
        module="stats", function="bootstrap", stateful=False, stream_capable=False
    )
    assert result.matches == ()
    (item,) = result.undeclared
    assert item.function == "bootstrap_ci"
    assert item.missing == ("stream_capable",)


def test_search_scope_filters_apply_to_the_undeclared_list_too():
    result = _catalog().search(module_prefix="optimization.", stream_capable=True)
    assert result.matches == ()
    assert {u.function for u in result.undeclared} == {"lp_solve_default", "lp_rhs_ranges"}


def test_function_substring_is_case_insensitive():
    result = _catalog().search(function="SORT")
    assert [r.function for r in result] == ["sort_values"]


def test_dtype_and_surface_filters_test_membership():
    catalog = _catalog()
    assert {r.function for r in catalog.search(dtype="float64")} == {
        "sort_values",
        "lp_solve_default",
    }
    assert {r.function for r in catalog.search(dtype="int")} == {"lp_solve_default"}
    assert {r.function for r in catalog.search(surface="batch_execute")} == {"sort_values"}


def test_complexity_and_backend_filters():
    catalog = _catalog()
    assert [r.function for r in catalog.search(complexity="O(n log n)")] == ["sort_values"]
    assert [r.function for r in catalog.search(backend="MOJO")] == ["sort_values"]
    assert catalog.describe("stats", "bootstrap_ci").complexity == "O(b n)"


def test_search_on_an_unknown_module_raises_rather_than_returning_nothing():
    with pytest.raises(CapabilityError) as excinfo:
        _catalog().search(module="statz")
    assert excinfo.value.code == "module_not_registered"


def test_search_on_a_prefix_that_matches_nothing_raises():
    with pytest.raises(CapabilityError) as excinfo:
        _catalog().search(module_prefix="optimisation.")
    assert excinfo.value.code == "module_not_registered"
    assert excinfo.value.details == {"module_prefix": "optimisation."}


@pytest.mark.parametrize(
    "kwargs",
    [
        {"deterministic": "yes"},
        {"stateful": 1},
        {"module": 7},
        {"function": "   "},
        {"limit": 0},
        {"limit": -3},
        {"limit": 1.5},
        {"limit": True},
    ],
)
def test_search_rejects_malformed_filters(kwargs):
    with pytest.raises(CapabilityError) as excinfo:
        _catalog().search(**kwargs)
    assert excinfo.value.code == "invalid_arguments"


def test_limit_truncates_and_says_so():
    result = _catalog().search(deterministic=True, limit=2)
    assert len(result) == 2
    assert result.total_matches == 4
    assert result.truncated is True
    assert result.filters["limit"] == 2
    assert "truncated=True" in repr(result)
    assert "undeclared=1" in repr(result)


def test_result_as_dict_carries_both_lists():
    payload = _catalog().search(module="stats", deterministic=True).as_dict()
    assert payload["filters"] == {"module": "stats", "deterministic": True}
    assert [m["function"] for m in payload["matches"]] == ["sort_values"]
    assert [u["function"] for u in payload["undeclared"]] == ["mean"]
    assert payload["total_matches"] == 1


# ── count relations: the field with a caller-facing consequence ───────────────


def test_count_relations_carry_the_list_they_bound():
    record = _catalog().describe("stats", "sort_values")
    assert record.count_relations == (CountRelation(factors=("n",), bounds=("v",)),)
    assert record.count_relations[0].expression == "n <= len(v)"


def test_a_row_major_matrix_bounds_its_list_by_the_product():
    record = _catalog().describe("optimization.linear", "lp_solve_default")
    dense, per_row, columns = record.count_relations
    assert dense.factors == ("rows", "cols")
    assert dense.bounds == ("a",)
    assert dense.expression == "rows * cols <= len(a)"
    # ONE count bounding SEVERAL parallel lists is one relation with several bounds.
    assert per_row == CountRelation(factors=("rows",), bounds=("senses", "b"))
    assert columns.expression == "cols <= len(c)"
    assert dense.as_dict() == {
        "factors": ["rows", "cols"],
        "bounds": ["a"],
        "plus": 0,
        "scope": "length",
        "role": "count",
    }


def test_a_sparse_triple_and_an_index_parameter_are_both_expressible():
    relations = _catalog().describe("sparse_numerics.csr", "csr_matvec").count_relations
    by_factor = {relation.factors: relation for relation in relations}
    assert by_factor[("nnz",)].bounds == ("values", "col_index")
    # A row pointer holds rows + 1 entries, which the additive term states exactly.
    assert by_factor[("rows",)].expression == "rows + 1 <= len(row_ptr)"
    # An INDEX is a bound too: reading adjacency[node] needs node + 1 elements.
    index = by_factor[("node",)]
    assert index.role == "index"
    assert index.expression == "node + 1 <= len(adjacency)"


def test_declares_count_relations_filter_separates_silence_from_a_declared_absence():
    catalog = _catalog()
    declared = catalog.search(declares_count_relations=True)
    assert {r.function for r in declared} == {"sort_values", "lp_solve_default", "csr_matvec"}
    missing = {u.function for u in declared.undeclared}
    assert missing == {"mean", "bootstrap_ci", "lp_rhs_ranges"}
    assert all(u.missing == ("count_relations",) for u in declared.undeclared)

    none_declared = CapabilityCatalog(
        contract_modules=CONTRACT,
        manifest_payload={
            "schema_version": 1,
            "modules": [
                {
                    "name": "stats",
                    "functions": [{"name": "mean", "capability": {"count_relations": []}}],
                }
            ],
        },
    ).search(declares_count_relations=False)
    assert [r.function for r in none_declared] == ["mean"]


# ── manifest shapes and manifest failures ────────────────────────────────────


def test_a_flat_function_list_is_accepted():
    catalog = CapabilityCatalog(
        contract_modules=CONTRACT,
        manifest_payload={
            "schema_version": 1,
            "functions": [
                {"module": "stats", "function": "mean", "capability": {"deterministic": True}}
            ],
        },
    )
    assert catalog.describe("stats", "mean").deterministic is True


def test_an_explicit_null_reads_as_silence_not_as_false():
    catalog = CapabilityCatalog(
        contract_modules=CONTRACT,
        manifest_payload={
            "schema_version": 1,
            "functions": [
                {
                    "module": "stats",
                    "function": "mean",
                    "capability": {"deterministic": None, "stateful": False},
                }
            ],
        },
    )
    record = catalog.describe("stats", "mean")
    assert record.deterministic is UNDECLARED
    assert record.stateful is False
    assert record.has_block is True


@pytest.mark.parametrize(
    "payload",
    [
        {"schema_version": 2, "modules": []},
        {"modules": []},
        {"schema_version": 1},
        {"schema_version": 1, "modules": {}},
        {"schema_version": 1, "modules": [{"functions": []}]},
        {"schema_version": 1, "modules": [{"name": "stats", "functions": [{}]}]},
        {
            "schema_version": 1,
            "modules": [
                {
                    "name": "stats",
                    "functions": [{"name": "mean", "capability": {"deterministic": "true"}}],
                }
            ],
        },
        {
            "schema_version": 1,
            "modules": [
                {
                    "name": "stats",
                    "functions": [{"name": "mean", "capability": {"complexity": 3}}],
                }
            ],
        },
        {
            "schema_version": 1,
            "modules": [
                {
                    "name": "stats",
                    "functions": [{"name": "mean", "capability": {"count_relations": [{}]}}],
                }
            ],
        },
        {
            "schema_version": 1,
            "modules": [
                {
                    "name": "stats",
                    "functions": [
                        {
                            "name": "mean",
                            "capability": {
                                "count_relations": [
                                    {"factors": ["n"], "bounds": ["v"]},
                                    {"factors": ["n"], "bounds": ["v"]},
                                ],
                            },
                        }
                    ],
                }
            ],
        },
        {
            "schema_version": 1,
            "functions": [
                {"module": "stats", "function": "mean", "capability": {"deterministic": True}},
                {"module": "stats", "function": "mean", "capability": {"deterministic": False}},
            ],
        },
    ],
)
def test_a_malformed_manifest_raises_instead_of_reading_as_undeclared(payload):
    """Degrading to 'everything undeclared' would look exactly like an un-annotated tree."""
    with pytest.raises(CapabilityError) as excinfo:
        CapabilityCatalog(contract_modules=CONTRACT, manifest_payload=payload)
    assert excinfo.value.code == "invalid_capability_manifest"


def test_a_declaration_for_a_function_the_contract_lacks_is_reported_not_dropped():
    catalog = CapabilityCatalog(
        contract_modules=CONTRACT,
        manifest_payload={
            "schema_version": 1,
            "functions": [
                {"module": "stats", "function": "gone", "capability": {"deterministic": True}}
            ],
        },
    )
    assert catalog.orphan_declarations == (("stats", "gone"),)
    with pytest.raises(CapabilityError) as excinfo:
        catalog.describe("stats", "gone")
    assert excinfo.value.code == "function_not_registered"


def test_an_empty_manifest_leaves_every_function_undeclared():
    catalog = CapabilityCatalog(
        contract_modules=CONTRACT, manifest_payload={"schema_version": 1, "modules": []}
    )
    result = catalog.search(deterministic=True)
    assert result.matches == ()
    assert len(result.undeclared) == 6
    assert catalog.describe("stats", "mean").deterministic is UNDECLARED


# ── inventory coverage and the runtime seam ────────────────────────────────────


def test_modules_and_functions_cover_the_contract_including_undeclared_ones():
    catalog = _catalog()
    assert catalog.modules() == ("optimization.linear", "sparse_numerics.csr", "stats")
    assert catalog.functions("stats") == ("sort_values", "mean", "bootstrap_ci")
    with pytest.raises(CapabilityError) as excinfo:
        catalog.functions("nope")
    assert excinfo.value.code == "module_not_registered"


def test_the_shipped_catalog_loads_and_covers_the_real_contract():
    """No manifest yet is a legitimate state: everything is UNDECLARED, nothing is False."""
    catalog = capabilities()
    modules = catalog.modules()
    assert len(modules) >= 500
    assert "stats" in modules
    # `sort_values` is the function whose unguarded count argument aborted a worker; the
    # relation between its count and its list is exactly what a declaration can state.
    record = catalog.describe("stats", "sort_values")
    assert isinstance(record, CapabilityRecord)
    if not catalog.manifest_present:
        assert record.has_block is False
        assert record.deterministic is UNDECLARED
        assert record.count_relations is UNDECLARED
    assert catalog.orphan_declarations == ()
    with pytest.raises(CapabilityError) as excinfo:
        catalog.describe("stats", "mean")  # the real module exports compute_mean
    assert excinfo.value.code == "function_not_registered"


def test_the_declaration_source_is_reported_rather_than_assumed():
    """ "Nothing declared" and "declarations read from X" must be tellable apart."""
    from algenta import capabilities as caps_module

    catalog = capabilities()
    assert catalog.manifest_present is bool(catalog.declaration_source)
    supplied = CapabilityCatalog(
        contract_modules=CONTRACT, manifest_payload={"schema_version": 1, "modules": []}
    )
    assert supplied.declaration_source == "supplied"
    assert supplied.manifest_present is True
    assert caps_module.__name__ == "algenta.capabilities"


@dataclass(frozen=True)
class _FnRel:
    name: str
    count_relations: tuple = ()


# The library contract carries count relations beside the signature they constrain, so the
# relation this surface reports is the same statement the runtime enforces.
CONTRACT_WITH_RELATIONS = (
    _Mod(
        "stats",
        (
            _FnRel("compute_mean", ({"factors": ["n"], "bounds": ["v"]},)),
            _FnRel("median"),
        ),
    ),
)


def test_count_relations_published_on_the_contract_are_read(monkeypatch):
    """They arrive with the signature, not in the declaration artifact."""
    from algenta import capabilities as caps_module

    monkeypatch.setattr(caps_module, "_read_bundled_json", lambda name: None)
    caps_module._bundled_declarations.cache_clear()
    try:
        catalog = CapabilityCatalog(contract_modules=CONTRACT_WITH_RELATIONS)
        record = catalog.describe("stats", "compute_mean")
        assert record.count_relations == (CountRelation(factors=("n",), bounds=("v",)),)
        assert record.declared_fields() == ("count_relations",)
        # No capability block was declared, and the surface does not pretend otherwise.
        assert record.has_block is False
        assert record.deterministic is UNDECLARED
        # An unpublished relation is silence, NOT "this function has no count arguments".
        assert catalog.describe("stats", "median").count_relations is UNDECLARED
        found = catalog.search(declares_count_relations=True)
        assert [r.function for r in found] == ["compute_mean"]
        assert [u.function for u in found.undeclared] == ["median"]
    finally:
        caps_module._bundled_declarations.cache_clear()


def test_a_declared_block_owns_its_count_relations_even_when_empty(monkeypatch):
    """ "The author said there are none" must not be overwritten by the contract."""
    from algenta import capabilities as caps_module

    monkeypatch.setattr(caps_module, "_read_bundled_json", lambda name: None)
    caps_module._bundled_declarations.cache_clear()
    try:
        catalog = CapabilityCatalog(
            contract_modules=CONTRACT_WITH_RELATIONS,
            manifest_payload={
                "schema_version": 1,
                "functions": [
                    {
                        "module": "stats",
                        "function": "compute_mean",
                        "capability": {"deterministic": True, "count_relations": []},
                    },
                    {
                        "module": "stats",
                        "function": "median",
                        "capability": {"deterministic": True},
                    },
                ],
            },
        )
        declared_none = catalog.describe("stats", "compute_mean")
        assert declared_none.count_relations == ()
        assert declared_none.deterministic is True
        # A block silent about relations still inherits what the contract published.
        assert catalog.describe("stats", "median").count_relations is UNDECLARED
        assert [r.function for r in catalog.search(declares_count_relations=False)] == [
            "compute_mean"
        ]
    finally:
        caps_module._bundled_declarations.cache_clear()


def test_no_bundled_declarations_reports_undeclared_and_says_where_from(monkeypatch):
    from algenta import capabilities as caps_module

    monkeypatch.setattr(caps_module, "_read_bundled_json", lambda name: None)
    caps_module._bundled_declarations.cache_clear()
    try:
        catalog = CapabilityCatalog(contract_modules=CONTRACT)
        assert catalog.declaration_source == ""
        assert catalog.manifest_present is False
        assert catalog.describe("stats", "sort_values").deterministic is UNDECLARED
    finally:
        caps_module._bundled_declarations.cache_clear()


def test_runtime_exposes_the_catalog_without_touching_the_worker():
    from algenta.mojo_runtime import MojoRuntime

    runtime = MojoRuntime(mode="local")
    catalog = runtime.capabilities()
    assert isinstance(catalog, CapabilityCatalog)
    assert runtime.capabilities() is catalog
    # The compute path is untouched: no runtime was constructed to read metadata.
    assert runtime._runtime is None


def test_package_exports_are_additive():
    import algenta

    for name in (
        "UNDECLARED",
        "CapabilityCatalog",
        "CapabilityError",
        "CapabilityRecord",
        "CapabilitySearchResult",
        "CountRelation",
        "UndeclaredCapability",
        "capabilities",
    ):
        assert name in algenta.__all__
        assert getattr(algenta, name) is not None
    # Pre-existing exports still resolve.
    assert "MojoRuntime" in algenta.__all__
    assert algenta.__all__.index("MojoRuntime") < algenta.__all__.index("capabilities")
