"""Regression gate for generated struct construction in the Mojo dispatch table.

Background: `scripts/generate_runtime_library_dispatch.py` used to emit positional
construction `T(field_0^, ..., fieldN^)` for every struct, while computing (and
then discarding) a `memberwise` flag. Structs that only declare
`fn __init__(out self)` — SVMModel, PLSResult, PipelineState, GRUState, GPFit —
therefore produced code that does not compile, so `make build-mojo` failed and
the affected kernels could not be reached from the local SDK at all.

These tests are a fast proxy for "the regenerated dispatch compiles". A full
`make build-mojo` is the authoritative gate but takes minutes and ~18 GB of RSS,
so it stays a CI/release step; this suite catches the specific defect class in
under a second.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GENERATOR = _REPO_ROOT / "scripts" / "generate_runtime_library_dispatch.py"
_ENGINE_DIR = _REPO_ROOT / "mojo" / "engine"
_DISPATCH = _ENGINE_DIR / "runtime_library_dispatch_generated.mojo"

VALID_STRATEGIES = {"positional", "assign", "none"}


def _load_generator():
    spec = importlib.util.spec_from_file_location("_dispatch_generator", _GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator():
    return _load_generator()


@pytest.fixture(scope="module")
def struct_strategies(generator) -> dict[tuple[str, str], tuple[list, str]]:
    """{(module_stem, struct_name): (fields, construction)} across mojo/engine."""
    resolved: dict[tuple[str, str], tuple[list, str]] = {}
    for path in sorted(_ENGINE_DIR.rglob("*.mojo")):
        if path.name == _DISPATCH.name:
            continue
        for name, (fields, construction) in generator._parse_struct_defs(path).items():
            resolved.setdefault((path.stem, name), (fields, construction))
    return resolved


def test_every_struct_resolves_a_known_strategy(struct_strategies) -> None:
    unknown = {
        key: construction
        for key, (_fields, construction) in struct_strategies.items()
        if construction not in VALID_STRATEGIES
    }
    assert not unknown, f"unrecognised construction strategies: {unknown}"


def test_default_init_structs_resolve_to_assign(struct_strategies) -> None:
    """The five structs that broke the build must resolve to `assign`.

    Pinned by name because these are the concrete regression: each declares only
    `fn __init__(out self)`, so positional construction cannot compile.
    """
    expected = {
        ("svm_solver", "SVMModel"),
        ("pls", "PLSResult"),
        ("pipelines", "PipelineState"),
        ("seq_nn", "GRUState"),
        ("gaussian_process", "GPFit"),
    }
    for key in expected:
        assert key in struct_strategies, f"{key} no longer found — did the struct move?"
        _fields, construction = struct_strategies[key]
        assert construction == "assign", f"{key} resolved to {construction!r}, expected 'assign'"


def test_fieldwise_structs_still_resolve_to_positional(struct_strategies) -> None:
    """Structs with a real field-wise __init__ must keep positional construction.

    This is the no-regression half: the fix must not change how any struct that
    already compiled is built.
    """
    _fields, construction = struct_strategies[("geometry", "Point")]
    assert construction == "positional"


def test_generated_dispatch_never_positionally_builds_an_assign_struct(
    struct_strategies,
) -> None:
    """The actual defect: `return T(field_0^, ...)` for an `assign` struct.

    Scans the committed dispatch table so a stale regeneration is caught too.
    """
    source = _DISPATCH.read_text(encoding="utf-8")
    assign_structs = {
        name for (_stem, name), (_f, con) in struct_strategies.items() if con == "assign"
    }
    offenders = sorted(
        name
        for name in assign_structs
        if re.search(rf"^{' ' * 4}return {re.escape(name)}\(field_0\^", source, re.M)
    )
    assert not offenders, (
        "dispatch positionally constructs structs that only have a default "
        f"__init__ — this will not compile: {offenders}"
    )


def test_assign_structs_reachable_in_dispatch_use_field_assignment(
    struct_strategies,
) -> None:
    """Every emitted parser for an `assign` struct uses default-construct+assign."""
    source = _DISPATCH.read_text(encoding="utf-8")
    assign_structs = {
        name for (_stem, name), (_f, con) in struct_strategies.items() if con == "assign"
    }
    emitted = {
        name for name in assign_structs if re.search(rf"raises -> {re.escape(name)}:", source)
    }
    # Only structs actually reachable as a parameter get a parser emitted.
    assert emitted, "expected at least one assign-strategy struct parser in the dispatch"
    for name in sorted(emitted):
        assert re.search(rf"^{' ' * 4}var decoded = {re.escape(name)}\(\)$", source, re.M), (
            f"{name} has a parser but does not default-construct — regenerate the dispatch"
        )


def test_committed_dispatch_matches_a_fresh_generation(generator) -> None:
    """Drift gate: the committed table must equal what the generator produces."""
    from apps.runtime.mojo_inventory import discover_runtime_library_modules

    modules = discover_runtime_library_modules(executable_only=True)
    rendered = generator.render_dispatch_source(modules)
    assert rendered == _DISPATCH.read_text(encoding="utf-8"), (
        "committed dispatch is stale — run `make inventory-refresh`"
    )
