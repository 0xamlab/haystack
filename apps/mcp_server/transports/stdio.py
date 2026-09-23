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
        from mcp.server import Server
        from mcp.server.models import InitializationOptions
        from mcp.server.stdio import stdio_server
        from mcp.types import (
            CallToolRequestParams,
            CallToolResult,
            ListToolsResult,
            TextContent,
            Tool,
        )
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

    # mcp>=2.0.0 deleted the @server.list_tools()/@server.call_tool() decorator API; handlers are
    # now passed as on_list_tools=/on_call_tool= constructor kwargs and take the SDK's per-request
    # ServerRequestContext as their first argument. stdio has no per-request transport object, so
    # ctx.request is always None here — this dispatch is otherwise unchanged, including dual-era
    # serving (an opening `initialize` frame always negotiates the legacy handshake regardless of
    # any modern _meta envelope; a non-initialize opening frame with the envelope negotiates
    # 2026-07-28), with zero extra registration required.
    async def handle_list_tools(ctx: Any, params: Any) -> ListToolsResult:
        return ListToolsResult(
            tools=[
                Tool(
                    name=spec["name"],
                    description=spec["description"],
                    inputSchema=spec["inputSchema"],
                    annotations=spec.get("annotations"),
                )
                for spec in get_tool_specs(allowed)
            ]
        )

    async def handle_call_tool(ctx: Any, params: CallToolRequestParams) -> CallToolResult:
        name = params.name
        arguments = params.arguments
        is_error = False
        try:
            result = await call_tool(name, arguments or {}, allowed)
        except Exception as exc:
            logger.error("tool_error", tool=name, error=str(exc))
            result = serialize_tool_error(exc, tool_name=name)
            # The payload is a serialized error: mark the envelope so MCP clients/agents
            # treat it as a failed call instead of acting on it as successful output.
            is_error = True
        return CallToolResult(content=[TextContent(type="text", text=result)], isError=is_error)

    server = Server(
        "algenta-mcp",
        version=config.VERSION,
        on_list_tools=handle_list_tools,
        on_call_tool=handle_call_tool,
    )

    async with stdio_server() as (read_stream, write_stream):
        init_opts = InitializationOptions(
            server_name="algenta-mcp",
            server_version=config.VERSION,
            capabilities=server.get_capabilities(
                notification_options=None,
                experimental_capabilities={},
            ),
        )
        await server.run(read_stream, write_stream, init_opts, raise_exceptions=True)
