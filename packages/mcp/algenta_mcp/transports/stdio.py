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
        from mcp.types import TextContent, Tool
    except ImportError:
        logger.error(
            "mcp_package_missing",
            hint="pip install mcp",
        )
        raise

    import os

    from algenta_mcp.errors import serialize_tool_error
    from algenta_mcp.products import resolve_visible_tools
    from algenta_mcp.registry import call_tool, get_tool_specs

    # stdio is a single-tenant process: the product edition is fixed for the whole
    # session via ALGENTA_PRODUCT (set by the self-hosted/enterprise plugin package).
    allowed = resolve_visible_tools((os.environ.get("ALGENTA_PRODUCT") or "").strip() or None)

    server = Server("algenta-decision-engine")

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
            server_name="algenta-decision-engine",
            server_version="1.0.3",
            capabilities=server.get_capabilities(
                notification_options=None,
                experimental_capabilities={},
            ),
        )
        await server.run(read_stream, write_stream, init_opts, raise_exceptions=True)
