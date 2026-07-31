"""Declared capability blocks: the grammar, the fail-loud parse, the checker, the gate.

Also proves the thing this change most had to avoid: existing signature/struct parse output
and the runtime-library cache key are untouched.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path

import pytest

from apps.runtime import mojo_capability_manifest as cm
from apps.runtime import mojo_inventory as mi

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "capability_manifest_gate.py"
BASELINE = ROOT / "scripts" / "capability_manifest_baseline.json"


def _param(name: str, typ: str, *, has_default: bool = False) -> mi.RuntimeParamSpec:
    return mi.RuntimeParamSpec(name=name, typ=typ, has_default=has_default)


def _spec(*params: mi.RuntimeParamSpec) -> mi.RuntimeFunctionSpec:
    return mi.RuntimeFunctionSpec(name="f", params=params, return_type="Float64")


def _capability(*relations: str) -> cm.RuntimeCapabilitySpec:
    issues: list[cm.CapabilityIssue] = []
    parsed = tuple(
        relation
        for relation in (
            cm._parse_count_relation(raw, path="<test>", line=1, issues=issues) for raw in relations
        )
        if relation is not None
    )
    assert not issues, [issue.render() for issue in issues]
    return cm.RuntimeCapabilitySpec(target="f", is_module=False, line=1, count_relations=parsed)


def _module_source(body: str) -> str:
    return body


# ── the block grammar ─────────────────────────────────────────────────────────


def test_every_declared_field_round_trips() -> None:
    parse = cm.parse_capability_blocks(
        '"""\n'
        "module prose\n"
        "\n"
        "@capability-module\n"
        "deterministic: true\n"
        "stateful: false\n"
        "batch_capable: true\n"
        "stream_capable: false\n"
        "seed_requirements: required\n"
        "supported_dtypes: float64, int64\n"
        "backend: mojo\n"
        "surfaces: library_execute, batch_execute\n"
        "golden_vectors: mojo/tests/libs/test_x.mojo\n"
        "benchmark: benchmarks/mojo_benchmarks/bench_x.mojo\n"
        "docs: none\n"
        "version_introduced: 1.1.0\n"
        "deprecation_state: soft_deprecated\n"
        "@endcapability\n"
        '"""\n'
        "fn solve(a: List[Float64], rows: Int, cols: Int) -> Float64:\n"
        '    """prose\n'
        "\n"
        "    @capability solve\n"
        "    complexity: O(rows * cols)\n"
        "    counts:\n"
        "    - rows * cols == len(a) [enforced]\n"
        "    @endcapability\n"
        '    """\n'
        "    return 0.0\n"
    )

    assert parse.issues == ()
    module = parse.module
    assert module is not None
    assert module.deterministic is True
    assert module.seed_requirements == "required"
    assert module.supported_dtypes == ("float64", "int64")
    assert module.surfaces == ("library_execute", "batch_execute")
    assert module.deprecation_state == "soft_deprecated"
    assert module.version_introduced == "1.1.0"

    solve = parse.by_name["solve"]
    assert solve.complexity == "O(rows * cols)"
    relation = (solve.count_relations or ())[0]
    assert relation.counts == ("rows", "cols")
    assert relation.comparison == "=="
    assert relation.bounded_lists == ("a",)
    assert relation.enforcement == cm.ENFORCEMENT_ENFORCED
    # A function block inherits the module block's claims without restating them.
    assert solve.inherit(module).deterministic is True


@pytest.mark.parametrize(
    ("relation", "expected"),
    [
        ("- n <= len(v) [enforced]", ("length", ("n",), 0, "<=", ("v",))),
        ("- rows * cols == len(a) [clamped]", ("length", ("rows", "cols"), 0, "==", ("a",))),
        (
            "- rows + 1 == len(indptr) [kernel_validated]",
            ("length", ("rows",), 1, "==", ("indptr",)),
        ),
        (
            "- n_acts == len(duration, start) [enforced]",
            ("length", ("n_acts",), 0, "==", ("duration", "start")),
        ),
    ],
)
def test_the_real_shapes_parse(relation: str, expected: tuple[object, ...]) -> None:
    issues: list[cm.CapabilityIssue] = []
    parsed = cm._parse_count_relation(relation[2:], path="<t>", line=1, issues=issues)
    assert issues == []
    assert parsed is not None
    assert (
        parsed.kind,
        parsed.counts,
        parsed.addend,
        parsed.comparison,
        parsed.bounded_lists,
    ) == expected


def test_a_dimension_is_declarable_as_a_dimension() -> None:
    issues: list[cm.CapabilityIssue] = []
    parsed = cm._parse_count_relation(
        "dim n_vehicles <= ROUTE_MAX_NODES [kernel_validated]",
        path="<t>",
        line=1,
        issues=issues,
        constants={"ROUTE_MAX_NODES": 4096},
    )
    assert issues == []
    assert parsed is not None
    assert parsed.kind == "dimension"
    assert parsed.bounded_lists == ()
    assert parsed.ceiling == 4096


def test_a_ceiling_naming_an_unknown_constant_is_an_issue_not_a_dropped_bound() -> None:
    issues: list[cm.CapabilityIssue] = []
    assert (
        cm._parse_count_relation(
            "dim n <= NOT_A_CONSTANT [enforced]", path="<t>", line=3, issues=issues
        )
        is None
    )
    assert [issue.code for issue in issues] == ["dimension_ceiling_unresolved"]


def test_comptime_constants_are_read_from_the_same_file() -> None:
    parse = cm.parse_capability_blocks(
        "comptime ROUTE_MAX_NODES: Int = 1 << 12\n"
        '"""\n'
        "@capability-module\n"
        "deterministic: true\n"
        "@endcapability\n"
        '"""\n'
        "fn f(v: List[Float64], n: Int) -> Float64:\n"
        '    """p\n'
        "    @capability f\n"
        "    counts:\n"
        "    - dim n <= ROUTE_MAX_NODES [enforced]\n"
        "    @endcapability\n"
        '    """\n'
        "    return 0.0\n"
    )
    assert parse.issues == ()
    assert (parse.by_name["f"].count_relations or ())[0].ceiling == 4096


# ── a parse failure is reported, never skipped ────────────────────────────────


@pytest.mark.parametrize(
    ("source", "code"),
    [
        # No enforcement tag: the author has not said who checks it.
        (
            'fn f(v: List[Float64], n: Int) -> Float64:\n    """p\n    @capability f\n'
            "    counts:\n    - n <= len(v)\n    @endcapability\n"
            '    """\n    return 0.0\n',
            "count_relation_missing_enforcement",
        ),
        (
            'fn f(v: List[Float64], n: Int) -> Float64:\n    """p\n    @capability f\n'
            "    counts:\n    - n <= len(v) [maybe]\n    @endcapability\n"
            '    """\n    return 0.0\n',
            "count_relation_unknown_enforcement",
        ),
        # Outside a docstring nothing would ever read it.
        (
            "# @capability f\nfn f(v: List[Float64], n: Int) -> Float64:\n    return 0.0\n",
            "block_outside_docstring",
        ),
        # Attached to the wrong function.
        (
            'fn g(v: List[Float64]) -> Float64:\n    """p\n    @capability f\n'
            "    counts: none\n    @endcapability\n"
            '    """\n    return 0.0\n',
            "block_scope_mismatch",
        ),
        # Never closed.
        (
            'fn f(v: List[Float64], n: Int) -> Float64:\n    """p\n    @capability f\n'
            "    counts: none\n"
            '    """\n    return 0.0\n',
            "unterminated_block",
        ),
        (
            'fn f(v: List[Float64], n: Int) -> Float64:\n    """p\n    @capability f\n'
            "    deterministic: maybe\n    @endcapability\n"
            '    """\n    return 0.0\n',
            "bad_bool",
        ),
        (
            'fn f(v: List[Float64], n: Int) -> Float64:\n    """p\n    @capability f\n'
            "    determinism: true\n    @endcapability\n"
            '    """\n    return 0.0\n',
            "unknown_field",
        ),
        (
            'fn f(v: List[Float64], n: Int) -> Float64:\n    """p\n    @capability f\n'
            "    surfaces: telepathy\n    @endcapability\n"
            '    """\n    return 0.0\n',
            "bad_surface",
        ),
        # `counts:` opened with nothing under it: say `counts: none` and mean it.
        (
            'fn f(v: List[Float64], n: Int) -> Float64:\n    """p\n    @capability f\n'
            "    counts:\n    complexity: O(n)\n    @endcapability\n"
            '    """\n    return 0.0\n',
            "counts_block_empty",
        ),
        (
            'fn f(v: List[Float64], n: Int) -> Float64:\n    """p\n    @capability f\n'
            "    complexity: O(n)\n    - n <= len(v) [enforced]\n    @endcapability\n"
            '    """\n    return 0.0\n',
            "relation_outside_counts",
        ),
        (
            'fn f(v: List[Float64], n: Int) -> Float64:\n    """p\n    @capability f\n'
            "    counts: none\n    counts: none\n    @endcapability\n"
            '    """\n    return 0.0\n',
            "duplicate_field",
        ),
        (
            '"""\n@capability-module\ncounts: none\n@endcapability\n"""\n',
            "field_not_allowed_at_module_scope",
        ),
    ],
)
def test_a_malformed_block_is_an_issue(source: str, code: str) -> None:
    parse = cm.parse_capability_blocks(_module_source(source), path="x.mojo")
    assert code in [issue.code for issue in parse.issues], [
        issue.render() for issue in parse.issues
    ]


def test_issues_carry_a_file_and_a_line() -> None:
    parse = cm.parse_capability_blocks(
        "fn f(v: List[Float64], n: Int) -> Float64:\n"
        '    """p\n'
        "    @capability f\n"
        "    counts:\n"
        "    - n <= len(v)\n"
        "    @endcapability\n"
        '    """\n',
        path="mojo/engine/x.mojo",
    )
    issue = parse.issues[0]
    assert (issue.path, issue.line) == ("mojo/engine/x.mojo", 5)
    assert "mojo/engine/x.mojo:5:" in issue.render()


# ── cross-validation against the real signature ──────────────────────────────


@pytest.mark.parametrize(
    ("relation", "code"),
    [
        ("- k <= len(v) [enforced]", "relation_unknown_parameter"),
        ("- tol <= len(v) [enforced]", "count_parameter_not_int"),
        ("- n <= len(tol) [enforced]", "bounded_parameter_not_a_list"),
    ],
)
def test_a_declaration_that_does_not_match_the_signature_is_an_issue(
    tmp_path: Path, relation: str, code: str
) -> None:
    path = tmp_path / "m.mojo"
    path.write_text(
        "fn f(v: List[Float64], n: Int, tol: Float64) -> Float64:\n"
        '    """p\n'
        "    @capability f\n"
        "    counts:\n"
        f"    {relation}\n"
        "    @endcapability\n"
        '    """\n'
        "    return 0.0\n",
        encoding="utf-8",
    )
    parse = mi.parse_runtime_capability_specs(path)
    assert [issue.code for issue in parse.issues] == [code]


def test_a_block_for_a_function_that_is_not_there_is_an_issue(tmp_path: Path) -> None:
    path = tmp_path / "m.mojo"
    path.write_text(
        '"""\n@capability-module\ndeterministic: false\n@endcapability\n"""\n'
        "fn f(v: List[Float64], n: Int) -> Float64:\n"
        '    """p\n'
        "    @capability f\n"
        "    counts: none\n"
        "    @endcapability\n"
        '    """\n'
        "    return 0.0\n",
        encoding="utf-8",
    )
    # Rename the function but not the block: the block must not follow it silently.
    path.write_text(path.read_text(encoding="utf-8").replace("fn f(", "fn g("), encoding="utf-8")
    parse = mi.parse_runtime_capability_specs(path)
    assert "block_scope_mismatch" in [issue.code for issue in parse.issues]


def test_strict_manifest_raises_rather_than_report_a_broken_block_as_absent(
    tmp_path: Path,
) -> None:
    engine = tmp_path / "engine"
    engine.mkdir()
    (engine / "m.mojo").write_text(
        "fn f(v: List[Float64], n: Int) -> Float64:\n"
        '    """p\n'
        "    @capability f\n"
        "    counts:\n"
        "    - n <= len(v)\n"
        "    @endcapability\n"
        '    """\n'
        "    return 0.0\n",
        encoding="utf-8",
    )
    with pytest.raises(mi.CapabilityManifestError):
        mi.build_capability_manifest(engine, strict=True)
    lenient = mi.build_capability_manifest(engine, strict=False)
    assert [issue.code for issue in lenient.issues] == ["count_relation_missing_enforcement"]


# ── the checker ───────────────────────────────────────────────────────────────


def test_the_measured_worker_kill_is_now_a_typed_violation() -> None:
    # `library_execute stats.sort_values [[5 floats], 25]` shape, on the unguarded twin.
    result = cm.check_count_relations(
        params=_spec(_param("v", "List[Float64]"), _param("n", "Int")).params,
        capability=_capability("n <= len(v) [enforced]"),
        args=([0.1, 0.2, 0.3, 0.4, 0.5], 25),
    )
    assert not result.ok
    violation = result.violations[0]
    assert violation.code == "count_exceeds_list_length"
    assert violation.detail == {"counts": {"n": 25}, "list": "v", "length": 5}


def test_a_satisfied_relation_is_silent() -> None:
    result = cm.check_count_relations(
        params=_spec(_param("v", "List[Float64]"), _param("n", "Int")).params,
        capability=_capability("n <= len(v) [enforced]"),
        args=([0.1, 0.2, 0.3, 0.4, 0.5], 5),
    )
    assert result.ok
    assert result.evaluated == 1


def test_the_product_is_checked_without_a_wrapping_multiply() -> None:
    # 3 * 6148914691236517206 == 2 in wrapping 64-bit arithmetic, which is how
    # csr_from_dense_driver([1.0, 2.0], 3, 6148914691236517206, tol) crashed the process.
    result = cm.check_count_relations(
        params=_spec(
            _param("dense", "List[Float64]"), _param("rows", "Int"), _param("cols", "Int")
        ).params,
        capability=_capability("rows * cols == len(dense) [enforced]"),
        args=([1.0, 2.0], 3, 6148914691236517206),
    )
    assert [violation.code for violation in result.violations] == ["count_shape_mismatch"]


def test_an_exact_product_is_accepted_and_a_wrong_one_is_not() -> None:
    params = _spec(
        _param("dense", "List[Float64]"), _param("rows", "Int"), _param("cols", "Int")
    ).params
    capability = _capability("rows * cols == len(dense) [enforced]")
    assert cm.check_count_relations(
        params=params, capability=capability, args=([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 2, 3)
    ).ok
    assert not cm.check_count_relations(
        params=params, capability=capability, args=([1.0, 2.0, 3.0, 4.0, 5.0, 6.0], 2, 4)
    ).ok


def test_a_count_out_of_int64_range_is_a_violation_because_it_wraps_on_the_way_in() -> None:
    result = cm.check_count_relations(
        params=_spec(_param("v", "List[Float64]"), _param("n", "Int")).params,
        capability=_capability("n <= len(v) [enforced]"),
        args=([1.0], 2**64),
    )
    assert [violation.code for violation in result.violations] == ["count_out_of_int64_range"]


def test_one_count_bounding_several_lists_names_the_list_that_broke() -> None:
    result = cm.check_count_relations(
        params=_spec(
            _param("duration", "List[Float64]"),
            _param("start", "List[Float64]"),
            _param("n_acts", "Int"),
        ).params,
        capability=_capability("n_acts == len(duration, start) [enforced]"),
        args=([1.0, 2.0], [1.0], 2),
    )
    assert [violation.detail["list"] for violation in result.violations] == ["start"]


def test_an_index_bound_uses_the_additive_term() -> None:
    params = _spec(_param("a", "List[Float64]"), _param("lo", "Int"), _param("hi", "Int")).params
    capability = _capability("hi + 1 <= len(a) [enforced]")
    assert cm.check_count_relations(
        params=params, capability=capability, args=([1.0, 2.0], 0, 1)
    ).ok
    assert not cm.check_count_relations(
        params=params, capability=capability, args=([1.0, 2.0], 0, 2)
    ).ok


def test_a_dimension_ceiling_is_enforced_when_declared() -> None:
    result = cm.check_count_relations(
        params=_spec(_param("v", "List[Float64]"), _param("n", "Int")).params,
        capability=_capability("dim n <= 4096 [enforced]"),
        args=([1.0], 4097),
    )
    assert [violation.code for violation in result.violations] == ["dimension_exceeds_ceiling"]


def test_kernel_validated_and_clamped_relations_are_not_pre_empted() -> None:
    for enforcement in ("kernel_validated", "clamped"):
        result = cm.check_count_relations(
            params=_spec(_param("v", "List[Float64]"), _param("n", "Int")).params,
            capability=_capability(f"n <= len(v) [{enforcement}]"),
            args=([1.0], 25),
        )
        assert result.ok
        assert result.skipped == (
            cm.SkippedRelation(f"n <= len(v) [{enforcement}]", f"enforcement_{enforcement}"),
        )


def test_no_declaration_means_exactly_todays_behaviour() -> None:
    params = _spec(_param("v", "List[Float64]"), _param("n", "Int")).params
    assert cm.check_count_relations(params=params, capability=None, args=([1.0], 999)) == (
        cm.CountCheckResult()
    )
    undeclared = cm.RuntimeCapabilitySpec(target="f", is_module=False, line=1)
    assert cm.check_count_relations(params=params, capability=undeclared, args=([1.0], 999)).ok


def test_one_undeclared_parameter_does_not_disable_the_declared_one() -> None:
    capability = _capability("rows * cols == len(a) [kernel_validated]", "n <= len(v) [enforced]")
    result = cm.check_count_relations(
        params=_spec(
            _param("a", "List[Float64]"),
            _param("rows", "Int"),
            _param("cols", "Int"),
            _param("v", "List[Float64]"),
            _param("n", "Int"),
        ).params,
        capability=capability,
        args=([1.0], 9, 9, [1.0], 25),
    )
    assert [violation.relation for violation in result.violations] == ["n <= len(v) [enforced]"]


def test_an_unevaluated_relation_is_reported_not_dropped() -> None:
    params = _spec(_param("v", "List[Float64]"), _param("n", "Int", has_default=True)).params
    capability = _capability("n <= len(v) [enforced]")
    # The caller relied on the kernel's default, so there is no argument to check.
    result = cm.check_count_relations(params=params, capability=capability, args=([1.0],))
    assert result.ok
    assert result.skipped == (
        cm.SkippedRelation("n <= len(v) [enforced]", "argument_not_provided"),
    )
    # A non-integer count is left to the existing type normalisation, and SAID so.
    result = cm.check_count_relations(params=params, capability=capability, args=([1.0], "five"))
    assert [skipped.reason for skipped in result.skipped] == ["count_not_an_integer"]


def test_undeclared_claims_are_not_granted() -> None:
    assert cm.resolved_claims(None)["deterministic"] is False
    declared = cm.RuntimeCapabilitySpec(
        target="f", is_module=False, line=1, deterministic=True, complexity="O(n)"
    )
    resolved = cm.resolved_claims(declared)
    assert resolved["deterministic"] is True
    assert resolved["complexity"] == "O(n)"
    assert resolved["benchmark"] is None


# ── the seeded declarations, on the real tree ────────────────────────────────


def test_stats_declares_every_count_pair_function() -> None:
    manifest = mi.build_capability_manifest()
    stats = manifest.by_import_path["stats"]
    assert stats.module is not None
    assert stats.undeclared_count_pair_functions == ()
    assert stats.is_fully_declared

    # The unguarded kernels are declared `enforced`; the deliberately clamped ones are not
    # pre-empted, so `quantile`'s documented clamp keeps working.
    enforced = {spec.target for spec in stats.functions if spec.enforced_relations}
    assert {
        "compute_mean",
        "compute_variance",
        "count_below_zero",
        "fast_sort",
        "pctile",
    } <= enforced
    assert {"sort_values", "quantile", "percentile", "median"}.isdisjoint(enforced)


def test_the_seeded_modules_are_declared_and_issue_free() -> None:
    manifest = mi.build_capability_manifest()  # strict: raises on any issue
    seeded = {
        "stats",
        "sparse_numerics.csr",
        "optimization.linear",
        "optimization.quadratic",
        "optimization.routing",
    }
    declared = {module.import_path for module in manifest.modules if module.is_fully_declared}
    assert seeded <= declared


def test_the_checker_catches_a_real_contract_call_that_would_abort_the_worker() -> None:
    manifest = mi.build_capability_manifest()
    module = mi.discover_runtime_library_modules().__iter__()
    stats_module = next(item for item in module if item.import_path == "stats")
    spec = next(item for item in stats_module.functions if item.name == "compute_mean")
    result = mi.check_count_relations(
        params=spec.params,
        capability=manifest.function_capability("stats", "compute_mean"),
        args=([0.1, 0.2, 0.3, 0.4, 0.5], 25),
    )
    assert [violation.code for violation in result.violations] == ["count_exceeds_list_length"]


def test_declared_relations_agree_with_the_parsed_signature_everywhere() -> None:
    # build_capability_manifest(strict=True) already raises on a cross-validation issue;
    # this asserts the tree-wide result explicitly so the failure names the count.
    manifest = mi.build_capability_manifest(strict=False)
    assert [issue.render() for issue in manifest.issues] == []


# ── the gate ──────────────────────────────────────────────────────────────────


@dataclass
class GateRun:
    returncode: int
    stdout: str


def _gate_module():
    spec = importlib.util.spec_from_file_location("_capability_manifest_gate", GATE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _run_gate(*args: str) -> GateRun:
    """In-process, so the gate is exercised by the same interpreter running the tests."""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = _gate_module().main(list(args))
    return GateRun(returncode=code, stdout=buffer.getvalue())


def test_the_repo_gate_is_green() -> None:
    result = _run_gate("--json")
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["failures"] == []
    assert summary["declaration_issues"] == 0
    assert summary["declared_modules"] >= summary["declared_module_floor"]
    assert summary["undeclared_count_pair_functions"] <= summary["undeclared_count_pair_ceiling"]


def test_the_baseline_records_a_real_ratchet() -> None:
    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    assert baseline["schema_version"] == 2
    # A seeded module has LEFT the grandfather list, so it can never regress silently.
    assert "stats" in baseline["declared_modules"]
    assert "stats" not in baseline["grandfathered_modules"]
    assert baseline["declared_module_floor"] == len(baseline["declared_modules"])
    assert baseline["undeclared_count_pair_ceiling"] > 0


def test_a_new_module_without_a_block_fails_the_gate(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    engine.mkdir()
    (engine / "grandfathered.mojo").write_text(
        "fn old(v: List[Float64], n: Int) -> Float64:\n    return 0.0\n", encoding="utf-8"
    )
    (engine / "newcomer.mojo").write_text(
        "fn fresh(v: List[Float64], n: Int) -> Float64:\n    return 0.0\n", encoding="utf-8"
    )
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "grandfathered_modules": ["grandfathered"],
                "declared_modules": [],
                "undeclared_count_pair_ceiling": 1,
            }
        ),
        encoding="utf-8",
    )
    result = _run_gate("--engine-root", str(engine), "--baseline", str(baseline))
    assert result.returncode == 1
    assert "newcomer" in result.stdout
    # The grandfathered module is not asked for anything.
    assert "grandfathered is" not in result.stdout


def test_a_new_module_that_declares_its_counts_passes(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    engine.mkdir()
    (engine / "newcomer.mojo").write_text(
        '"""\n'
        "@capability-module\n"
        "deterministic: true\n"
        "stateful: false\n"
        "backend: mojo\n"
        "surfaces: library_execute\n"
        "version_introduced: 1.1.0\n"
        "@endcapability\n"
        '"""\n'
        "fn fresh(v: List[Float64], n: Int) -> Float64:\n"
        '    """p\n'
        "    @capability fresh\n"
        "    counts:\n"
        "    - n <= len(v) [enforced]\n"
        "    @endcapability\n"
        '    """\n'
        "    return 0.0\n",
        encoding="utf-8",
    )
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "grandfathered_modules": [],
                "declared_modules": ["newcomer"],
                "undeclared_count_pair_ceiling": 0,
            }
        ),
        encoding="utf-8",
    )
    result = _run_gate("--engine-root", str(engine), "--baseline", str(baseline))
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_gate_fails_when_a_declared_module_loses_its_block(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    engine.mkdir()
    (engine / "m.mojo").write_text(
        "fn f(v: List[Float64], n: Int) -> Float64:\n    return 0.0\n", encoding="utf-8"
    )
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "grandfathered_modules": [],
                "declared_modules": ["m"],
                "undeclared_count_pair_ceiling": 0,
            }
        ),
        encoding="utf-8",
    )
    result = _run_gate("--engine-root", str(engine), "--baseline", str(baseline))
    assert result.returncode == 1
    assert "must stay declared" in result.stdout
    assert "above the ceiling" in result.stdout


def test_deleting_a_declared_module_is_not_treated_as_a_regression(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    engine.mkdir()
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "grandfathered_modules": [],
                "declared_modules": ["deleted_module"],
                "undeclared_count_pair_ceiling": 3,
            }
        ),
        encoding="utf-8",
    )
    result = _run_gate("--engine-root", str(engine), "--baseline", str(baseline))
    assert result.returncode == 0, result.stdout


def test_update_baseline_refuses_a_regression(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    engine.mkdir()
    (engine / "m.mojo").write_text(
        "fn f(v: List[Float64], n: Int) -> Float64:\n    return 0.0\n", encoding="utf-8"
    )
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "grandfathered_modules": ["m"],
                "declared_modules": [],
                "undeclared_count_pair_ceiling": 0,
            }
        ),
        encoding="utf-8",
    )
    result = _run_gate(
        "--engine-root", str(engine), "--baseline", str(baseline), "--update-baseline"
    )
    assert result.returncode == 1
    assert "refusing to raise" in result.stdout


def test_update_baseline_can_never_grandfather_a_new_module(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    engine.mkdir()
    (engine / "old.mojo").write_text(
        "fn f(v: List[Float64], n: Int) -> Float64:\n    return 0.0\n", encoding="utf-8"
    )
    (engine / "newcomer.mojo").write_text(
        "fn g(v: List[Float64], n: Int) -> Float64:\n    return 0.0\n", encoding="utf-8"
    )
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "grandfathered_modules": ["old"],
                "declared_modules": [],
                "undeclared_count_pair_ceiling": 2,
            }
        ),
        encoding="utf-8",
    )
    assert (
        _run_gate(
            "--engine-root", str(engine), "--baseline", str(baseline), "--update-baseline"
        ).returncode
        == 0
    )
    recorded = json.loads(baseline.read_text(encoding="utf-8"))
    assert recorded["grandfathered_modules"] == ["old"]
    # ...so the newcomer still fails the gate until somebody declares it.
    result = _run_gate("--engine-root", str(engine), "--baseline", str(baseline))
    assert result.returncode == 1
    assert "newcomer" in result.stdout


def test_a_module_that_becomes_declared_leaves_the_grandfather_list(tmp_path: Path) -> None:
    engine = tmp_path / "engine"
    engine.mkdir()
    (engine / "old.mojo").write_text(
        '"""\n'
        "@capability-module\n"
        "deterministic: false\n"
        "stateful: false\n"
        "backend: mojo\n"
        "surfaces: library_execute\n"
        "version_introduced: pre_manifest\n"
        "@endcapability\n"
        '"""\n'
        "fn f(v: List[Float64], n: Int) -> Float64:\n"
        '    """p\n'
        "    @capability f\n"
        "    counts:\n"
        "    - n <= len(v) [enforced]\n"
        "    @endcapability\n"
        '    """\n'
        "    return 0.0\n",
        encoding="utf-8",
    )
    baseline = tmp_path / "baseline.json"
    baseline.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "grandfathered_modules": ["old"],
                "declared_modules": [],
                "undeclared_count_pair_ceiling": 1,
            }
        ),
        encoding="utf-8",
    )
    assert (
        _run_gate(
            "--engine-root", str(engine), "--baseline", str(baseline), "--update-baseline"
        ).returncode
        == 0
    )
    recorded = json.loads(baseline.read_text(encoding="utf-8"))
    assert recorded["grandfathered_modules"] == []
    assert recorded["declared_modules"] == ["old"]
    assert recorded["undeclared_count_pair_ceiling"] == 0


# ── nothing that already worked may change ────────────────────────────────────


def _historical_module():
    """`mojo_inventory` as of the last commit that touched it, loaded side by side."""
    revision = subprocess.run(  # noqa: S603
        ["git", "log", "-n", "1", "--format=%H", "--", "apps/runtime/mojo_inventory.py"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    if revision.returncode != 0 or not revision.stdout.strip():
        pytest.skip("git history unavailable")
    blob = subprocess.run(  # noqa: S603
        ["git", "show", f"{revision.stdout.strip()}:apps/runtime/mojo_inventory.py"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(ROOT),
    )
    if blob.returncode != 0:
        pytest.skip("historical mojo_inventory unavailable")
    source = blob.stdout
    if "mojo_capability_manifest" in source:
        pytest.skip("historical revision already contains the capability parser")
    # Depth matters: the module derives the engine root from `parents[2]` of its own file,
    # so it must sit two directories below the repo root exactly as `apps/runtime/` does.
    path = ROOT / "build" / "_capability_invariance" / "_historical_mojo_inventory.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    spec = importlib.util.spec_from_file_location("_historical_mojo_inventory", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _function_tuples(specs) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            spec.name,
            tuple((p.name, p.typ, p.has_default, p.is_mut) for p in spec.params),
            spec.return_type,
        )
        for spec in specs
    )


def _struct_tuples(specs: dict) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (name, tuple((field.name, field.typ) for field in spec.fields))
        for name, spec in sorted(specs.items())
    )


def test_signature_and_struct_parsing_is_byte_for_byte_what_it_was() -> None:
    historical = _historical_module()
    paths = sorted(mi.DEFAULT_ENGINE_DIR.rglob("*.mojo"))
    assert len(paths) > 500
    differences: list[str] = []
    for path in paths:
        if _function_tuples(historical._parse_runtime_function_specs(path)) != _function_tuples(
            mi._parse_runtime_function_specs(path)
        ):
            differences.append(f"functions: {path}")
        if _struct_tuples(historical.parse_runtime_struct_specs(path)) != _struct_tuples(
            mi.parse_runtime_struct_specs(path)
        ):
            differences.append(f"structs: {path}")
    assert differences == []


def test_discovery_output_is_unchanged_for_every_shared_module(tmp_path: Path) -> None:
    # The skip lists are POLICY (another change may legitimately move a package in or out),
    # so this compares every module both revisions agree is in scope -- which is what proves
    # the parse, the executability filter and the struct resolution are untouched.
    historical = _historical_module()
    before = {
        module.import_path: _function_tuples(module.functions)
        for module in historical.discover_runtime_library_modules(
            mi.DEFAULT_ENGINE_DIR, cache_path=tmp_path / "before.json"
        )
    }
    after = {
        module.import_path: _function_tuples(module.functions)
        for module in mi.discover_runtime_library_modules(
            mi.DEFAULT_ENGINE_DIR, cache_path=tmp_path / "after.json"
        )
    }
    shared = sorted(set(before) & set(after))
    assert len(shared) >= 500
    assert [name for name in shared if before[name] != after[name]] == []


def test_the_runtime_library_cache_key_and_payload_are_untouched(tmp_path: Path) -> None:
    """Capability discovery must not touch the runtime-library cache's key or payload SHAPE.

    The version VALUE is not the invariant and pinning it here conflated the two: #427 moved it
    7 -> 8 for an unrelated parser fix (nested closures stopped being published), which failed
    this test even though nothing about the cache's shape had changed.

    What must hold is that the capability parse adds no key, drops no key, and does not move the
    version itself -- capability discovery has no on-disk cache at all, so it has no reason to.
    The payload-key assertion below is the real check; the version is pinned only so that a
    future bump has to be a deliberate edit here with a reason attached.
    """
    assert mi._RUNTIME_LIBRARY_CACHE_SCHEMA_VERSION == 8, (
        "the cache schema version moved. That is legitimate when the PARSE changes shape (see "
        "#427), but it must never move because of the capability parse -- capability discovery "
        "has no cache. Update this number only alongside a comment on the version constant "
        "saying what changed."
    )
    engine = tmp_path / "engine"
    engine.mkdir()
    (engine / "m.mojo").write_text(
        '"""\n@capability-module\ndeterministic: true\n@endcapability\n"""\n'
        "fn f(v: List[Float64], n: Int) -> Float64:\n"
        '    """p\n    @capability f\n    counts:\n    - n <= len(v) [enforced]\n'
        '    @endcapability\n    """\n'
        "    return 0.0\n",
        encoding="utf-8",
    )
    cache = tmp_path / "cache.json"
    mi.discover_runtime_library_modules(engine, cache_path=cache)
    payload = json.loads(cache.read_text(encoding="utf-8"))
    assert sorted(payload) == [
        "engine_root",
        "executable_only",
        "fingerprint",
        "module_count",
        "modules",
        "schema_version",
    ]
    assert sorted(payload["modules"][0]) == ["functions", "import_path", "lib_id", "relative_path"]
    # A declared block is nowhere in the cached payload: capability discovery is its own pass.
    assert "capability" not in cache.read_text(encoding="utf-8")


def test_the_runtime_guard_reads_the_declared_block_and_respects_the_tag() -> None:
    """The cross-layer contract: `[enforced]` reaches the guard, `[clamped]` must not.

    `apps/runtime/mojo_count_relations.py` is the enforcement point and carries a table for
    kernels that have no block yet. A block WINS over that table, so this asserts the two
    layers cannot disagree about the functions this change declared.
    """
    guard = pytest.importorskip("apps.runtime.mojo_count_relations")
    enforced = guard.declared_count_spec("stats", "compute_mean")
    assert enforced is not None
    assert [(r.factors, r.bounds, r.plus) for r in enforced.relations] == [(("n",), ("v",), 0)]

    # Deliberately clamped in the kernel: declared, decided, and NOT pre-empted.
    clamped = guard.declared_count_spec("stats", "median")
    assert clamped is not None
    assert clamped.relations == ()

    # Validated by the kernel with a typed status: same, so the status still reaches callers.
    kernel_validated = guard.declared_count_spec("sparse_numerics.csr", "csr_from_dense_driver")
    assert kernel_validated is not None
    assert kernel_validated.relations == ()


def test_a_packed_buffer_is_expressible_and_checked() -> None:
    """Two int4 codes per byte: the count and the length are not in a 1:1 ratio.

    Written as a tautology (`n <= len(packed) + n`) before the grammar could say it, which is
    why the divisor exists: an inexpressible relation becomes a FALSE one, not a missing one.
    """
    issues: list[cm.CapabilityIssue] = []
    relation = cm._parse_count_relation(
        "ceil(n_values / 2) <= len(packed) [enforced]", path="<t>", line=1, issues=issues
    )
    assert issues == []
    assert relation is not None
    assert (relation.counts, relation.divisor, relation.addend) == (("n_values",), 2, 0)

    params = _spec(_param("packed", "List[Int]"), _param("n_values", "Int")).params
    capability = cm.RuntimeCapabilitySpec(
        target="f", is_module=False, line=1, count_relations=(relation,)
    )
    # 3 bytes hold 5, 6 codes but not 7.
    assert cm.check_count_relations(params=params, capability=capability, args=([1, 2, 3], 6)).ok
    assert not cm.check_count_relations(
        params=params, capability=capability, args=([1, 2, 3], 7)
    ).ok


def test_only_the_packing_spelling_of_division_is_accepted() -> None:
    issues: list[cm.CapabilityIssue] = []
    assert (
        cm._parse_count_relation("n / 2 <= len(v) [enforced]", path="<t>", line=1, issues=issues)
        is None
    )
    assert [issue.code for issue in issues] == ["count_relation_unparsable"]


def test_a_packed_exact_relation_pins_the_buffer_to_one_length() -> None:
    issues: list[cm.CapabilityIssue] = []
    relation = cm._parse_count_relation(
        "ceil(n / 8) == len(bits) [enforced]", path="<t>", line=1, issues=issues
    )
    assert issues == []
    assert relation is not None
    capability = cm.RuntimeCapabilitySpec(
        target="f", is_module=False, line=1, count_relations=(relation,)
    )
    params = _spec(_param("bits", "List[Int]"), _param("n", "Int")).params
    # One byte holds 1..8 bits exactly; 0 needs no byte and 9 needs two.
    for n, ok in ((1, True), (8, True), (0, False), (9, False), (16, False)):
        result = cm.check_count_relations(params=params, capability=capability, args=([0], n))
        assert result.ok is ok, (n, result)
