"""Product-edition routing for the in-process MCP server.

The canonical ``PRODUCT_EDITIONS`` registry lives in ONE place —
``packages/mcp/algenta_mcp/products.py``. This module re-exports it: it imports the
``algenta_mcp`` package when installed (standalone/published deployment), otherwise
loads that one canonical file by path (in-monorepo). Either way there is a single
physical source of truth — never a second hand-maintained copy.
"""

from __future__ import annotations

try:  # standalone/published env: algenta_mcp is installed
    from algenta_mcp.products import (  # type: ignore[import-not-found]
        PRODUCT_EDITIONS,
        product_allowlist,
        resolve_visible_tools,
    )
except ModuleNotFoundError:  # in-monorepo: load the canonical file by path
    import importlib.util
    import pathlib

    _canonical = (
        pathlib.Path(__file__).resolve().parents[2]
        / "packages"
        / "mcp"
        / "algenta_mcp"
        / "products.py"
    )
    _spec = importlib.util.spec_from_file_location("_algenta_products_canonical", _canonical)
    if _spec is None or _spec.loader is None:  # pragma: no cover - defensive
        raise ModuleNotFoundError(f"canonical product editions not found at {_canonical}")
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    PRODUCT_EDITIONS = _mod.PRODUCT_EDITIONS
    product_allowlist = _mod.product_allowlist
    resolve_visible_tools = _mod.resolve_visible_tools

__all__ = ["PRODUCT_EDITIONS", "product_allowlist", "resolve_visible_tools"]
