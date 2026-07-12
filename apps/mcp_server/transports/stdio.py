"""
stdio transport — for Claude Desktop, Cursor, Zed, Windsurf, VS Code extensions.

Reads MCP protocol messages from stdin, writes responses to stdout.
"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


async def run_stdio_server() -> None:
    """Run the MCP server over stdio."""
    try:
        from mcp.server import NotificationOptions, Server
        from mcp.server.models import InitializationOptions
        from mcp.server.stdio import stdio_server
        from mcp.types import TextContent, Tool
    except ImportError:
        logger.error(
            "mcp_package_missing",
            hint="pip install mcp",
        )
        raise

    import os

    from apps.mcp_server import config
    from apps.mcp_server.errors import serialize_tool_error
    from apps.mcp_server.products import feature_tool_constraint, resolve_visible_tools
    from apps.mcp_server.registry import call_tool, get_tool_specs

    def _license_feature_constraints(product: str | None) -> tuple[frozenset[str] | None, ...]:
        # Narrow visible tools by the local license's product/feature entitlements.
        # Dark by default: no license, an invalid one, or a license with NO product
        # entitlements → no constraint (product-only gating, unchanged). A license that
        # DOES carry product entitlements narrows to its granted features; one that does
        # NOT grant the selected product fails closed (empty set → no tools).
        if not product:
            return ()
        try:
            from apps.runtime.license import load_license

            lic = load_license(
                os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
            )
        except Exception:  # noqa: BLE001 — never let license resolution break tool listing
            return ()
        if lic is None or not getattr(lic, "valid", False) or not getattr(lic, "products", None):
            return ()
        if not lic.has_product(product):
            return (frozenset(),)
        return (feature_tool_constraint(product, lic.product_features(product)),)

    # stdio is a single-tenant process: the product edition is fixed for the whole
    # session via ALGENTA_PRODUCT (set by the self-hosted/enterprise plugin package).
    _product = (os.environ.get("ALGENTA_PRODUCT") or "").strip() or None
    allowed = resolve_visible_tools(_product, constraints=_license_feature_constraints(_product))

    server = Server("algenta-mcp", version=config.VERSION)

    @server.list_tools()  # type: ignore[misc]
    async def handle_list_tools() -> list[Tool]:
        return [
            Tool(
                name=spec["name"],
                description=spec["description"],
                inputSchema=spec["inputSchema"],
            )
            for spec in get_tool_specs(allowed)
        ]

    @server.call_tool()  # type: ignore[misc]
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        try:
            result = await call_tool(name, arguments or {}, allowed)
        except Exception as exc:
            logger.error("tool_error", tool=name, error=str(exc))
            result = serialize_tool_error(exc, tool_name=name)
        return [TextContent(type="text", text=result)]

    async with stdio_server() as (read_stream, write_stream):
        init_opts = InitializationOptions(
            server_name="algenta-mcp",
            server_version=config.VERSION,
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )
        await server.run(read_stream, write_stream, init_opts, raise_exceptions=True)
