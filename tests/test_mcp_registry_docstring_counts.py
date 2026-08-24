"""Drift guard for the MCP tool registry's own "<N> tools across <M> categories" header.

apps/mcp_server/registry.py and packages/mcp/algenta_mcp/registry.py both open with a module
docstring summarizing the registry ("117 tools across 12 categories:" ... at the time this test
was added, the real live numbers were 140 tools across 13 categories). Nothing enforced that
line against the actual `TOOLS` dict below it, so it silently went stale as tools and categories
were added over time. This test ties the header to the real structure so it can't happen again.

apps/mcp_server/registry.py is checked against the LIVE `TOOLS` dict (an in-repo import) as well
as the source text, for double confidence. packages/mcp/algenta_mcp is a standalone,
pip-installable package intentionally decoupled from the monorepo (see
tests/test_mcp_vendored_parity.py's test_mcp_package_has_no_monorepo_imports) with its own
dependency chain (packages/python-sdk); rather than reach across that boundary with sys.path
tricks, this checks the same real structural signal directly from its source text -- the same
approach test_mcp_vendored_parity.py already uses for vendored files.
"""
from __future__ import annotations

import re
from pathlib import Path

from apps.mcp_server.registry import TOOLS as LIVE_APP_TOOLS

_ROOT = Path(__file__).resolve().parent.parent

_HEADER_RE = re.compile(r"(\d+)\s+tools across\s+(\d+)\s+categories")
_TOOL_KEY_RE = re.compile(r'^ {4}"([a-zA-Z0-9_]+)":\s*\{', re.MULTILINE)
_CATEGORY_MARKER_RE = re.compile(r"^\s*#\s*──.+──\s*$", re.MULTILINE)


def _tools_dict_body(source: str) -> str:
    start = source.index("TOOLS: dict[str, ToolEntry] = {")
    end = source.index("\n}\n", start)
    return source[start:end]


def _stated_counts(source: str) -> tuple[int, int]:
    match = _HEADER_RE.search(source)
    assert match, "registry.py docstring no longer has a '<N> tools across <M> categories' header"
    return int(match.group(1)), int(match.group(2))


def _real_counts_from_source(source: str) -> tuple[int, int]:
    body = _tools_dict_body(source)
    tool_keys = _TOOL_KEY_RE.findall(body)
    category_markers = _CATEGORY_MARKER_RE.findall(body)
    return len(tool_keys), len(category_markers)


def test_apps_mcp_server_registry_docstring_matches_live_and_source_tools() -> None:
    path = _ROOT / "apps" / "mcp_server" / "registry.py"
    source = path.read_text(encoding="utf-8")
    stated_tools, stated_categories = _stated_counts(source)
    source_tools, source_categories = _real_counts_from_source(source)

    assert stated_tools == len(LIVE_APP_TOOLS) == source_tools, (
        f"apps/mcp_server/registry.py docstring says {stated_tools} tools, but len(TOOLS) is "
        f"{len(LIVE_APP_TOOLS)} live / {source_tools} entries found in source -- update the "
        "docstring header."
    )
    assert stated_categories == source_categories, (
        f"apps/mcp_server/registry.py docstring says {stated_categories} categories, but the "
        f"TOOLS dict has {source_categories} '# ── ... ──' category markers -- update the "
        "docstring header (and its category list) to match."
    )


def test_packages_mcp_registry_docstring_matches_source_tools() -> None:
    path = _ROOT / "packages" / "mcp" / "algenta_mcp" / "registry.py"
    source = path.read_text(encoding="utf-8")
    stated_tools, stated_categories = _stated_counts(source)
    source_tools, source_categories = _real_counts_from_source(source)

    assert stated_tools == source_tools, (
        f"packages/mcp/algenta_mcp/registry.py docstring says {stated_tools} tools, but the "
        f"TOOLS dict has {source_tools} entries in source -- update the docstring header."
    )
    assert stated_categories == source_categories, (
        f"packages/mcp/algenta_mcp/registry.py docstring says {stated_categories} categories, "
        f"but the TOOLS dict has {source_categories} '# ── ... ──' category markers -- update "
        "the docstring header (and its category list) to match."
    )


def test_apps_and_packages_mcp_registries_expose_the_same_tool_names() -> None:
    """Both files are meant to mirror the same tool surface (minus nothing at present -- the
    standalone package still ships list_runtime_libraries/execute_runtime_library, just wired to
    the hosted API instead of a bundled runtime). If this ever legitimately diverges, narrow this
    assertion with the specific expected difference instead of deleting it."""
    app_source = (_ROOT / "apps" / "mcp_server" / "registry.py").read_text(encoding="utf-8")
    pkg_source = (_ROOT / "packages" / "mcp" / "algenta_mcp" / "registry.py").read_text(
        encoding="utf-8"
    )
    app_tools = set(_TOOL_KEY_RE.findall(_tools_dict_body(app_source)))
    pkg_tools = set(_TOOL_KEY_RE.findall(_tools_dict_body(pkg_source)))

    assert app_tools == set(LIVE_APP_TOOLS)  # sanity: the regex agrees with the live import
    assert app_tools == pkg_tools, (
        f"only in apps/mcp_server: {sorted(app_tools - pkg_tools)}; "
        f"only in packages/mcp/algenta_mcp: {sorted(pkg_tools - app_tools)}"
    )
