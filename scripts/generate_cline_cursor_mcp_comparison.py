#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api_server.services.cline_competitive_measurements import (
    CURSOR_MCP_COMPARISON_PATH,
    build_cursor_mcp_comparison_artifact,
)
from apps.api_server.services.cline_proof_common import read_json, repo_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Cursor-vs-direct competitive comparison artifact."
    )
    parser.add_argument("--g0-artifact", required=True, help="Path to the G0 benchmark artifact.")
    parser.add_argument(
        "--direct-json",
        required=True,
        help="Path to the direct agent-core run JSON payload.",
    )
    parser.add_argument(
        "--mcp-json",
        required=True,
        help="Path to the Cursor MCP run JSON payload.",
    )
    parser.add_argument(
        "--direct-wall-seconds",
        required=True,
        type=float,
        help="Measured wall time for the direct agent-core run.",
    )
    parser.add_argument(
        "--mcp-wall-seconds",
        required=True,
        type=float,
        help="Measured wall time for the Cursor MCP run.",
    )
    parser.add_argument(
        "--output",
        default=str((repo_root() / CURSOR_MCP_COMPARISON_PATH).resolve()),
        help="Path to write the Cursor-vs-direct comparison artifact.",
    )
    args = parser.parse_args()
    build_cursor_mcp_comparison_artifact(
        g0_payload=read_json(Path(args.g0_artifact).resolve()),
        direct_payload=read_json(Path(args.direct_json).resolve()),
        mcp_payload=read_json(Path(args.mcp_json).resolve()),
        direct_wall_time_seconds=args.direct_wall_seconds,
        mcp_wall_time_seconds=args.mcp_wall_seconds,
        output_path=Path(args.output).resolve(),
        direct_source_path=Path(args.direct_json).resolve(),
        mcp_source_path=Path(args.mcp_json).resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
