"""
Algenta MCP Server — entry point.

Transports:
  stdio  — for Claude Desktop, Cursor, Zed, Windsurf, VS Code (Cline/Continue)
  http   — SSE transport for OpenWebUI, LibreChat, n8n, custom apps

Usage:
  python -m apps.mcp_server.server                      # stdio (default)
  python -m apps.mcp_server.server --mode http           # HTTP/SSE on port 8001
  python -m apps.mcp_server.server --mode http --port 9000

Environment variables:
  ALGENTA_API_KEY        — required
  ALGENTA_BASE_URL       — default: https://api.algenta.ai
  ALGENTA_MCP_PORT       — default: 8001
"""
from __future__ import annotations

import argparse
import asyncio

import structlog

logger = structlog.get_logger(__name__)


def create_fastapi_router():
    """
    Return a FastAPI router that mounts the MCP server at /mcp/*.
    Called from apps/api_server/main.py to embed MCP into the main API process.

    Always exposes /mcp/tools when FastAPI dependencies are available.
    The optional mcp package enables /mcp/sse and /mcp/messages.
    """
    try:
        from apps.mcp_server.transports.http_sse import _build_fastapi_router
        return _build_fastapi_router()
    except Exception as exc:
        logger.warning("mcp_fastapi_router_unavailable", error=str(exc))
        return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Algenta MCP Server")
    parser.add_argument(
        "--mode", "--transport",
        choices=["stdio", "http"],
        default="stdio",
        help="Transport mode (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="HTTP port override (default: ALGENTA_MCP_PORT env var or 8001)",
    )
    return parser.parse_args()


async def _run(mode: str, port: int | None) -> None:
    if mode == "stdio":
        from apps.mcp_server.transports.stdio import run_stdio_server
        await run_stdio_server()
    else:
        from apps.mcp_server import config
        from apps.mcp_server.transports.http_sse import run_http_server
        await run_http_server(port=port or config.PORT)


def main() -> None:
    args = _parse_args()
    asyncio.run(_run(args.mode, args.port))


if __name__ == "__main__":
    main()
