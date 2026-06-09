"""Regression tests for the CodeQL ReDoS + bad-tag-filter batch fix.

Each test exercises one of the regex sites that was rewritten:

  * py/bad-tag-filter sites accept browser-permissive malformed end tags
    (e.g. ``</script >``, ``</script\n>``).
  * py/redos and py/polynomial-redos sites complete on pathological inputs
    in well under 100ms even when the input is large.

The tests are intentionally lightweight - they don't need fixtures; they
import the compiled module-level patterns directly and assert behaviour.
"""

from __future__ import annotations

import re
import time

import pytest

from apps.api_server.services import data_coercion, source_registry
from apps.api_server.services.repository_intelligence_adapters import (
    astro_primitives,
    c_family,
    cfml_primitives,
    d_language,
    mermaid_primitives,
    stan_primitives,
    svelte_primitives,
    vbscript_primitives,
    vue_primitives,
)


# Each pathological input is small enough that any nonlinear-backtracking
# regex would still take far longer than 100ms - the bound is loose.
_REDOS_BUDGET_SECONDS = 0.1


def _run_with_budget(fn) -> float:
    start = time.perf_counter()
    fn()
    return time.perf_counter() - start


# ---------------------------------------------------------------------------
# py/bad-tag-filter: malformed close tags
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "close_tag",
    ["</script>", "</script >", "</script\t>", "</script\n>", "</SCRIPT >"],
)
def test_vue_script_block_handles_permissive_close_tag(close_tag: str) -> None:
    source = f"<script setup>console.log('x'){close_tag}"
    match = vue_primitives._SCRIPT_BLOCK_RE.search(source)
    assert match is not None
    assert match.group("body") == "console.log('x')"


@pytest.mark.parametrize(
    "close_tag",
    ["</script>", "</script >", "</script\n>", "</style >", "</STYLE\n>"],
)
def test_astro_blocks_handle_permissive_close_tag(close_tag: str) -> None:
    if "script" in close_tag.lower():
        source = f"<script>doit(){close_tag}"
        match = astro_primitives._SCRIPT_BLOCK_RE.search(source)
    else:
        source = f"<style>body{{}}{close_tag}"
        match = astro_primitives._STYLE_BLOCK_RE.search(source)
    assert match is not None


@pytest.mark.parametrize("close_tag", ["</script>", "</script >", "</script\n>"])
def test_svelte_script_block_handles_permissive_close_tag(close_tag: str) -> None:
    source = f"<script lang='ts'>doit(){close_tag}"
    match = svelte_primitives._SCRIPT_BLOCK_RE.search(source)
    assert match is not None


@pytest.mark.parametrize("close_tag", ["</script>", "</script >", "</script\n>"])
def test_vbscript_script_tag_handles_permissive_close_tag(close_tag: str) -> None:
    source = f"<script language='vbscript'>Sub Foo()\nEnd Sub{close_tag}"
    match = vbscript_primitives._SCRIPT_TAG_RE.search(source)
    assert match is not None


def test_mermaid_edge_operator_still_matches_diagram_syntax() -> None:
    # Sanity check: mermaid arrow operators still match after the refactor.
    for arrow in ["-->", "==>", "<-->", "-.->", "x--x"]:
        assert mermaid_primitives._EDGE_OPERATOR_RE.search(f"A {arrow} B") is not None


# ---------------------------------------------------------------------------
# py/redos and py/polynomial-redos: pathological-input timing
# ---------------------------------------------------------------------------


def test_stan_function_head_re_no_exponential_backtrack() -> None:
    # The original pattern had overlapping '\s' inside the inner class and an
    # outer '\s+' separator; tab-separated tokens caused exponential blowup.
    pathological = "\t".join(["A"] * 4000) + " X"  # missing '{' -> no match
    elapsed = _run_with_budget(
        lambda: stan_primitives._FUNCTION_HEAD_RE.search(pathological)
    )
    assert elapsed < _REDOS_BUDGET_SECONDS, f"took {elapsed * 1000:.1f}ms"


def test_stan_function_head_re_still_matches_valid_declaration() -> None:
    match = stan_primitives._FUNCTION_HEAD_RE.search("real foo(real x) {")
    assert match is not None and match.group("name") == "foo"


def test_cfml_script_function_re_no_polynomial_backtrack() -> None:
    pathological = "final " * 4000 + "X"  # no 'function' keyword -> no match
    elapsed = _run_with_budget(
        lambda: cfml_primitives._SCRIPT_FUNCTION_RE.search(pathological)
    )
    assert elapsed < _REDOS_BUDGET_SECONDS, f"took {elapsed * 1000:.1f}ms"


@pytest.mark.parametrize(
    "source,expected",
    [
        ("public function foo(", "foo"),
        ("function bar(", "bar"),
        ("public static final function baz(", "baz"),
        ("public String function getName(", "getName"),
        ("private numeric function calc(", "calc"),
    ],
)
def test_cfml_script_function_re_matches_supported_declarations(
    source: str, expected: str
) -> None:
    match = cfml_primitives._SCRIPT_FUNCTION_RE.search(source)
    assert match is not None and match.group("name") == expected


def test_data_coercion_float_re_no_polynomial_backtrack() -> None:
    # '9' * N with a trailing non-digit forces fullmatch to fail at the end.
    pathological = "9" * 4000 + "x"
    elapsed = _run_with_budget(lambda: data_coercion._FLOAT_RE.fullmatch(pathological))
    assert elapsed < _REDOS_BUDGET_SECONDS, f"took {elapsed * 1000:.1f}ms"


@pytest.mark.parametrize(
    "text,is_float",
    [
        ("1", True),
        ("1.5", True),
        ("1.", True),
        (".5", True),
        ("-2.5e10", True),
        ("+1.5E-3", True),
        ("abc", False),
        ("1.5.6", False),
    ],
)
def test_data_coercion_float_re_matches_expected(text: str, is_float: bool) -> None:
    assert bool(data_coercion._FLOAT_RE.fullmatch(text)) is is_float


def test_source_registry_trailing_zero_float_no_redos() -> None:
    # The normalized-sample path used to call ``re.fullmatch`` directly on
    # arbitrary-length input. The new code length-caps the input first.
    text = "1" * 10_000 + ".0"
    elapsed = _run_with_budget(lambda: source_registry._normalized_sample(text))
    assert elapsed < _REDOS_BUDGET_SECONDS, f"took {elapsed * 1000:.1f}ms"


def test_source_registry_trailing_zero_float_still_normalises() -> None:
    assert source_registry._normalized_sample("42.0") == "42"
    assert source_registry._normalized_sample("-7.000") == "-7"
    # Genuine non-trailing-zero floats are untouched.
    assert source_registry._normalized_sample("3.14") == "3.14"


def test_d_language_function_decl_re_no_redos() -> None:
    pathological = "extern " * 1000 + "X"  # no '(' -> no match
    elapsed = _run_with_budget(
        lambda: d_language.FUNCTION_DECL_RE.search(pathological)
    )
    assert elapsed < _REDOS_BUDGET_SECONDS, f"took {elapsed * 1000:.1f}ms"


def test_c_family_function_decl_re_no_redos() -> None:
    pathological = "inline " * 1000 + "X"  # no '(' / ';' / '{' -> no match
    elapsed = _run_with_budget(
        lambda: c_family.FUNCTION_DECL_RE.search(pathological)
    )
    assert elapsed < _REDOS_BUDGET_SECONDS, f"took {elapsed * 1000:.1f}ms"


def test_benchmark_list_regexes_no_redos() -> None:
    # The benchmark module rewrites Mojo expressions; ensure the bounded
    # quantifiers do not blow up on pathological 'List[...' input.
    import tests.benchmark_mojo_vs_python as bench  # noqa: PLC0415

    pathological = "List[" + "x" * 4000  # never closes the bracket
    elapsed = _run_with_budget(lambda: bench._mojo_expr_to_python(pathological))
    assert elapsed < _REDOS_BUDGET_SECONDS, f"took {elapsed * 1000:.1f}ms"


# ---------------------------------------------------------------------------
# Smoke test: bad-tag-filter rewrites preserve the existing extract_* APIs
# ---------------------------------------------------------------------------


def test_vue_extract_script_blocks_still_returns_body() -> None:
    text = "<template><div/></template><script setup>let a=1</script>"
    assert vue_primitives._extract_script_blocks(text) == ("let a=1",)


def test_vue_extract_template_block_still_returns_body() -> None:
    text = "<template><Foo/></template><script>0</script>"
    assert vue_primitives.extract_template_block(text) == "<Foo/>"
