"""A nested closure is not a module function, and publishing one breaks the build.

`_parse_runtime_function_specs` matched its `fn`/`def` regex against the STRIPPED line, so
indentation was discarded and a function nested inside another function's body looked exactly
like a module-level one. Struct methods were matched too but never survived, because they take
`self` and `_parse_param_specs` rejects it -- which is why the missing check went unnoticed.

A `parallelize` worker closure has no `self`. Its signature is `(tid: Int)`, fully marshalable,
so it reached the contract and the dispatch generator emitted

    from gemm.blocked import band

for a symbol the module does not export. That does not compile, so on `origin/main`
`make inventory-check` failed with "stale generated runtime contract" while
`make inventory-refresh` -- the remedy named in the Makefile and in the error -- regenerated the
same uncompilable dispatch. Neither state was escapable without editing the parser.

Four closures exist in the tree and both spellings matter: three `fn ... capturing:` inside
`gemm`, and one plain nested `def` in `seq2_trainer`. The `def` one had been in the shipped
contract and dispatch for far longer, so the SDK contract advertised a function that could never
be imported. Nothing caught it because CI compiles filtered shards, never the whole dispatch --
so these assertions run the parser directly rather than relying on a build to notice.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from apps.runtime.mojo_inventory import (  # noqa: E402
    _parse_runtime_function_specs,
    _RUNTIME_LIBRARY_CACHE_SCHEMA_VERSION,
)

ENGINE = _REPO_ROOT / "mojo" / "engine"

# (file, closure name, the line it is declared on). Every one is nested inside another function.
KNOWN_CLOSURES = (
    ("gemm/blocked.mojo", "band"),
    ("gemm/blocked.mojo", "gemv_band"),
    ("gemm/quantized.mojo", "nf4_band"),
    ("seq2_trainer.mojo", "worker"),
)


def _names(relative: str) -> list[str]:
    return [spec.name for spec in _parse_runtime_function_specs(ENGINE / relative)]


@pytest.mark.parametrize(("relative", "closure"), KNOWN_CLOSURES)
def test_a_nested_closure_is_not_published_as_a_module_function(relative: str, closure: str):
    """THE REGRESSION. Each of these was emitted as `from <module> import <closure>`."""
    source = ENGINE / relative
    assert source.is_file(), f"{relative} moved; update this test rather than deleting it"
    assert closure not in _names(relative), (
        f"{relative} published the nested closure '{closure}' as a module function; the "
        "generated dispatch would import a symbol the module does not export and stop compiling"
    )


@pytest.mark.parametrize(("relative", "closure"), KNOWN_CLOSURES)
def test_the_closure_is_still_there_to_be_rejected(relative: str, closure: str):
    """Guards against this suite passing because the closure was deleted or renamed.

    Without this, someone refactoring `gemm` would silently turn every assertion above into a
    tautology, and the parser could regress with the suite still green.
    """
    text = (ENGINE / relative).read_text(encoding="utf-8", errors="replace")
    declarations = [
        line
        for line in text.splitlines()
        if line.strip().startswith((f"fn {closure}(", f"def {closure}("))
    ]
    assert declarations, (
        f"no `fn {closure}(`/`def {closure}(` left in {relative}; the assertions in this module "
        "no longer measure anything"
    )
    assert all(line[:1].isspace() for line in declarations), (
        f"{closure} in {relative} is now declared at column 0, i.e. it is a real module-level "
        "function. It should then BE published, and this test needs updating."
    )


def test_the_functions_around_them_are_still_published():
    """The fix must be surgical: the real kernels in those files stay reachable.

    Dropping a real export is worse than the phantom, because the kernel silently becomes
    `module_not_registered` over the wire instead of failing loudly at build time.
    """
    expected = {
        "gemm/blocked.mojo": {"gemm_tile_plan", "sgemm_flat", "gemv_flat"},
        "gemm/quantized.mojo": {"gemv_nf4_flat", "gemm_nf4_flat", "gemv_int_flat"},
    }
    for relative, wanted in expected.items():
        published = set(_names(relative))
        assert wanted <= published, f"{relative} lost {sorted(wanted - published)}"


def test_a_struct_method_is_still_not_published():
    """Struct methods were always excluded, just for the wrong reason (`self`), and stay excluded.

    Pinned on a real file so the column-0 rule cannot be "fixed" into publishing them.
    """
    published = set(_names("net/url.mojo"))
    assert published, "net/url.mojo published nothing; this assertion would be vacuous"
    assert "url_parse" in published, "a real module-level function went missing"


def test_every_symbol_the_generated_dispatch_imports_actually_exists():
    """The invariant that broke, checked directly instead of waiting for a compiler.

    The dispatch opens with ~5300 `from <module> import <symbol> as <alias>` bindings. If one
    names a symbol the module does not declare at column 0, the whole file stops compiling and
    every kernel in the shard becomes unreachable -- and CI never noticed, because it compiles
    FILTERED shards, so a broken binding in a module no shard happens to include stays invisible
    until someone builds the wrong combination.

    This is a text-level check on purpose: it costs milliseconds, needs no Mojo toolchain, and
    covers every binding rather than the subset a given shard pulls in.
    """
    import re

    dispatch = ENGINE / "runtime_library_dispatch_generated.mojo"
    assert dispatch.is_file(), "generated dispatch missing"

    bindings: list[tuple[str, str]] = []
    open_module: str | None = None
    for line in dispatch.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        block = re.match(r"^from\s+([A-Za-z_][\w.]*)\s+import\s*\($", stripped)
        if block is not None:
            open_module = block.group(1)
            continue
        if open_module is not None:
            if stripped == ")":
                open_module = None
                continue
            entry = re.match(r"^([A-Za-z_]\w*)\s+as\s+\w+,?$", stripped)
            if entry is not None:
                bindings.append((open_module, entry.group(1)))
            continue
        single = re.match(
            r"^from\s+([A-Za-z_][\w.]*)\s+import\s+([A-Za-z_]\w*)\s+as\s+\w+$", stripped
        )
        if single is not None:
            bindings.append((single.group(1), single.group(2)))

    assert len(bindings) > 4000, (
        f"only parsed {len(bindings)} import bindings out of the dispatch; the import syntax "
        "changed and this test is no longer measuring it"
    )

    declared: dict[str, set[str] | None] = {}

    def module_declares(module: str) -> set[str] | None:
        if module not in declared:
            path = ENGINE / (module.replace(".", "/") + ".mojo")
            names: set[str] | None = None
            if path.is_file():
                names = set()
                for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                    # Column 0 only: that is exactly what is importable by name.
                    hit = re.match(r"^(?:fn|def|struct|alias)\s+([A-Za-z_]\w*)", line)
                    if hit is not None:
                        names.add(hit.group(1))
            declared[module] = names
        return declared[module]

    unresolvable = [
        f"{module}.{symbol}"
        for module, symbol in bindings
        if (names := module_declares(module)) is None or symbol not in names
    ]
    assert not unresolvable, (
        "the generated dispatch imports symbols that do not exist at module scope, so it cannot "
        f"compile: {unresolvable[:10]}"
    )


def test_the_cache_schema_version_moved_with_the_parser():
    """The cache fingerprint is source mtimes only, so a parser fix is invisible to a warm cache.

    Measured while making this change: after fixing the parser, a regenerated dispatch STILL
    imported `band`, because `.cache/algenta/runtime_library_inventory.json` replayed the old
    parse. The schema version is the only thing that invalidates it, so it has to move whenever
    the parse changes shape -- otherwise the fix ships and does nothing on every machine that
    already has a cache.
    """
    assert _RUNTIME_LIBRARY_CACHE_SCHEMA_VERSION >= 8, (
        "the nested-closure fix landed at schema version 8; a parser change without a version "
        "bump is silently masked by any warm cache"
    )
