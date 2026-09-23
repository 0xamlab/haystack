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

    from algenta_mcp import config
    from algenta_mcp.errors import serialize_tool_error
    from algenta_mcp.products import resolve_visible_tools
    from algenta_mcp.registry import call_tool, get_tool_specs

    # stdio is a single-tenant process: the product edition is fixed for the whole
    # session via ALGENTA_PRODUCT (set by the self-hosted/enterprise plugin package).
    allowed = resolve_visible_tools((os.environ.get("ALGENTA_PRODUCT") or "").strip() or None)

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
