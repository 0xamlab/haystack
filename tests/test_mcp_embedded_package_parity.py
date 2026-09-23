"""Embedded-vs-package MCP catalog parity guard (the anti-skew lock for the re-sync).

The hosted api.algenta.ai/mcp surface is served by the EMBEDDED copy (apps/mcp_server, mounted
by apps/api_server/main.py), while algenta-mcp (packages/mcp) is the published package. The two
shipped the same 140 tools but drifted for months (descriptions, annotations, the 1.0.28 error
contract, even the reported version) because nothing failed when they diverged. This test is
that failure: it compares every tool spec's description, annotations, and inputSchema between
the live embedded registry and the package sources, and pins the ONLY intentional divergences
as an explicit, commented allowlist — adding a new drift breaks the build.

Intentional divergences (embedded copy is deliberately AHEAD of / different from the package):
  - responses — the embedded spec keeps the #952 typed input array + function/tool calling +
    previous_response_id surface that the standalone package does not have.
  - list_runtime_libraries / execute_runtime_library — the embedded copy is local/runtime-backed
    (the Algenta deployment owns the bundled compute lifecycle); the package is an API-backed
    proxy of /v1/libraries. Different descriptions and schemas BY DESIGN; annotations (behavior
    hints) must still match.

The package is decoupled from the monorepo (tests/test_mcp_vendored_parity.py fails on any
apps.* import inside it), so — like tests/test_mcp_registry_docstring_counts.py — this reads
the package specs from SOURCE with ast instead of importing algenta_mcp. One package spec
composes a sub-value from another spec (query.py's QUERY_BATCH_SPEC reuses
SPEC["inputSchema"]["properties"]["filter"]), so the collector evaluates plain Name/Subscript
references within each module rather than calling ast.literal_eval alone.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from apps.mcp_server.registry import TOOLS as EMBEDDED_TOOLS

_ROOT = Path(__file__).resolve().parents[1]
_PACKAGE_TOOLS = _ROOT / "packages" / "mcp" / "algenta_mcp" / "tools"

# The ONLY tools whose description/inputSchema may differ from the package (see module docstring).
# Their annotations must still match — behavior hints are true of both variants.
_ALLOWED_SURFACE_DIVERGENCE = frozenset(
    {"responses", "list_runtime_libraries", "execute_runtime_library"}
)


def _module_assignments(tree: ast.Module) -> dict[str, ast.expr]:
    assignments: dict[str, ast.expr] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
        ):
            assignments[node.targets[0].id] = node.value
        elif (
            isinstance(node, ast.AnnAssign)
            and node.value is not None
            and isinstance(node.target, ast.Name)
        ):
            assignments[node.target.id] = node.value
    return assignments


def _evaluate(node: ast.expr, env: dict[str, ast.expr]) -> Any:
    """Literal evaluation plus the two reference forms the package specs actually use
    (a same-module Name bound to another spec, and Subscript indexing into one)."""
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Dict):
        return {
            _evaluate(key, env): _evaluate(value, env)
            for key, value in zip(node.keys, node.values, strict=True)
        }
    if isinstance(node, ast.List):
        return [_evaluate(element, env) for element in node.elts]
    if isinstance(node, ast.Tuple):
        return tuple(_evaluate(element, env) for element in node.elts)
    if isinstance(node, ast.Name):
        return _evaluate(env[node.id], env)
    if isinstance(node, ast.Subscript):
        return _evaluate(node.value, env)[_evaluate(node.slice, env)]
    raise ValueError(f"unsupported spec node: {ast.dump(node)[:200]}")


def _package_specs() -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for path in sorted(_PACKAGE_TOOLS.glob("*.py")):
        if path.name == "__init__.py":
            continue
        env = _module_assignments(ast.parse(path.read_text(encoding="utf-8")))
        for name, node in env.items():
            if not (name.endswith("_SPEC") or name == "SPEC"):
                continue
            spec = _evaluate(node, env)
            if isinstance(spec, dict) and "name" in spec:
                specs[spec["name"]] = spec
    return specs


PACKAGE_SPECS = _package_specs()


def test_package_collector_found_the_full_catalog() -> None:
    # A collector regression must fail loudly here, never silently weaken the parity tests.
    assert len(PACKAGE_SPECS) == 140
    assert set(PACKAGE_SPECS) == set(EMBEDDED_TOOLS)


def test_every_embedded_tool_carries_behavior_annotations() -> None:
    missing = [name for name, entry in EMBEDDED_TOOLS.items() if "annotations" not in entry["spec"]]
    assert not missing, f"embedded specs missing annotations: {missing}"


def test_annotations_match_the_package_for_all_140_tools() -> None:
    diffs = [
        name
        for name, entry in EMBEDDED_TOOLS.items()
        if entry["spec"].get("annotations") != PACKAGE_SPECS[name].get("annotations")
    ]
    assert not diffs, f"annotations diverge from packages/mcp for: {diffs}"


def test_descriptions_match_the_package_except_documented_divergences() -> None:
    diffs = {
        name
        for name, entry in EMBEDDED_TOOLS.items()
        if entry["spec"]["description"] != PACKAGE_SPECS[name]["description"]
    }
    assert diffs == _ALLOWED_SURFACE_DIVERGENCE, (
        f"description drift beyond the documented allowlist: {diffs - _ALLOWED_SURFACE_DIVERGENCE}; "
        f"allowlisted tools that no longer diverge (tighten the allowlist): "
        f"{_ALLOWED_SURFACE_DIVERGENCE - diffs}"
    )


def test_input_schemas_match_the_package_except_documented_divergences() -> None:
    diffs = {
        name
        for name, entry in EMBEDDED_TOOLS.items()
        if entry["spec"]["inputSchema"] != PACKAGE_SPECS[name]["inputSchema"]
    }
    assert diffs == _ALLOWED_SURFACE_DIVERGENCE, (
        f"inputSchema drift beyond the documented allowlist: {diffs - _ALLOWED_SURFACE_DIVERGENCE}; "
        f"allowlisted tools that no longer diverge (tighten the allowlist): "
        f"{_ALLOWED_SURFACE_DIVERGENCE - diffs}"
    )
