from __future__ import annotations

import ast
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "docs" / "check_docs_coverage.py"
MCP_REGISTRY = ROOT / "packages" / "mcp" / "algenta_mcp" / "registry.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_docs_coverage", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _published_registry_tool_keys() -> set[str]:
    """The published registry's TOOLS keys, parsed independently of the extractor.

    ``check_docs_coverage.mcp_tools()`` regex-scans ``packages/mcp/algenta_mcp/registry.py``;
    re-deriving the same set from its AST is what proves the docs surface is the PUBLISHED
    registry — every TOOLS key and nothing else, so neither a hand-kept list nor an
    app-side inventory can silently stand in for it.
    """
    tree = ast.parse(MCP_REGISTRY.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", None) == "TOOLS":
            assert isinstance(node.value, ast.Dict)
            return {key.value for key in node.value.keys if isinstance(key, ast.Constant)}
    raise AssertionError(f"{MCP_REGISTRY.relative_to(ROOT)} publishes no TOOLS dict")


def test_mcp_coverage_uses_published_registry() -> None:
    coverage = _load_module()

    tools = coverage.mcp_tools()

    # The coverage surface IS the published registry, tool for tool.
    assert tools == _published_registry_tool_keys()
    # Extraction never silently collapses — the gate's own floor, not a second pinned count.
    assert len(tools) >= coverage.FLOORS["mcp_tools"]
    assert "get_contract" in tools
    # Both runtime-library tools are published surface ON PURPOSE: #376 exposed them as
    # API-backed tools of the standalone package (the Algenta deployment owns the bundled
    # compute lifecycle) and documented them in gitbook/sdk/mcp.md in the same change, so
    # `check_docs_coverage.py --category mcp_tools` counts them as covered — 140/140.
    # This test asserted their ABSENCE from before that change; the expectation was stale,
    # the registry is not wrong. tests/test_mcp_runtime_library_tools.py and
    # tests/integration/test_mcp_server.py both treat them as published.
    assert "list_runtime_libraries" in tools
    assert "execute_runtime_library" in tools


def test_cli_coverage_excludes_internal_runtime_lifecycle() -> None:
    coverage = _load_module()

    commands = coverage.de_cli_commands()

    assert "de health" in commands
    assert not any(command.startswith("de runtime") for command in commands)
    assert "algenta_cli_commands" not in coverage.EXTRACTORS
