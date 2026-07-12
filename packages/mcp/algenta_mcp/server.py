"""
Algenta MCP Server — entry point.

Transports:
  stdio  — for Claude Desktop, Cursor, Zed, Windsurf, VS Code (Cline/Continue)
  http   — Streamable HTTP for OpenWebUI, LibreChat, n8n, custom apps

Usage:
  python -m algenta_mcp.server                      # stdio (default)
  python -m algenta_mcp.server --mode http           # Streamable HTTP on port 8001
  python -m algenta_mcp.server --mode http --port 9000

Environment variables:
  ALGENTA_API_KEY /      — required; legacy DE_API_KEY remains accepted for
  DE_API_KEY               compatibility. Use Cloud Managed API keys only in
                           Cloud Managed. In self_hosted and air_gapped, use
                           the key provisioned by your self-hosted operator deployment
  ALGENTA_BASE_URL /     — default: https://api.algenta.ai in Cloud Managed.
  DE_BASE_URL /            Legacy ALGENTA_API_URL remains accepted for
  ALGENTA_API_URL          compatibility. Required for self_hosted and air_gapped
                           profiles, which fail closed and do not silently fall back
                           to Algenta cloud.
  ALGENTA_MCP_PORT       — default: 8001
  ALGENTA_MCP_HOST       — default: 127.0.0.1; set explicitly for remote ingress
"""

from __future__ import annotations

import argparse
import asyncio
from typing import TYPE_CHECKING

import structlog

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from fastapi import APIRouter


def create_fastapi_router() -> APIRouter | None:
    """
    Return a FastAPI router that mounts the MCP server at /mcp/*.
    Called from apps/api_server/main.py to embed MCP into the main API process.

    Always exposes /mcp/tools when FastAPI dependencies are available.
    The optional mcp package enables /mcp Streamable HTTP and legacy SSE routes.
    Without it, those endpoints still mount but fail closed with a structured
    503 mcp_transport_unavailable contract.
    """
    try:
        from algenta_mcp.transports.http_sse import _build_fastapi_router

        return _build_fastapi_router()
    except Exception as exc:
        logger.warning("mcp_fastapi_router_unavailable", error=str(exc))
        return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Algenta MCP Server")
    parser.add_argument(
        "--mode",
        "--transport",
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
        from algenta_mcp.transports.stdio import run_stdio_server

        await run_stdio_server()
    else:
        from algenta_mcp import config
        from algenta_mcp.transports.http_sse import run_http_server

        await run_http_server(host=config.HOST, port=port or config.PORT)


def main() -> None:
    args = _parse_args()
    try:
        asyncio.run(_run(args.mode, args.port))
    except KeyboardInterrupt:
        logger.info("mcp_server_stopped")


if __name__ == "__main__":
    main()
