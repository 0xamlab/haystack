#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api_server.services.cline_competitive_live_runs import (
    DIRECT_REPOSITORY_PIPELINE_PATH,
    MCP_REPOSITORY_PIPELINE_PATH,
    WARM_CACHE_COLD_RUN_PATH,
    WARM_CACHE_WARM_RUN_PATH,
    collect_live_cursor_mcp_comparison_artifact,
    collect_live_warm_cache_comparison_artifact,
)
from apps.api_server.services.cline_competitive_measurements import (
    CURSOR_MCP_COMPARISON_PATH,
    WARM_CACHE_COMPARISON_PATH,
)
from apps.api_server.services.cline_proof_common import repo_root

try:
    from tests.integration.live_local_auth_bootstrap import (
        ensure_bootstrapped_local_live_api_key,
    )
    from tests.integration.live_local_defaults import (
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
    )
except ModuleNotFoundError:  # pragma: no cover - standalone invocation fallback
    from live_local_auth_bootstrap import ensure_bootstrapped_local_live_api_key
    from live_local_defaults import (
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
    )


def _resolve_api_key(cli_value: str | None) -> str:
    if cli_value is not None and cli_value.strip():
        os.environ["ALGENTA_API_KEY"] = cli_value.strip()
        os.environ["DE_API_KEY"] = cli_value.strip()
        return cli_value.strip()
    configured = os.environ.get("ALGENTA_API_KEY", "").strip() or os.environ.get(
        "DE_API_KEY", ""
    ).strip()
    if configured:
        return configured
    seeded_api_key, seeded_ok, error = ensure_bootstrapped_local_live_api_key(
        api_key=resolve_local_live_api_key(),
        api_key_configured=has_configured_local_live_api_key(),
        active_base_url="http://127.0.0.1:8000",
    )
    if not seeded_ok:
        raise RuntimeError(error or "failed to bootstrap local live API key")
    return seeded_api_key


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate live Cursor-vs-direct and warm-cache competitive proof artifacts."
    )
    parser.add_argument(
        "--root",
        default=str(repo_root()),
        help="Repository root used to resolve default proof paths.",
    )
    parser.add_argument(
        "--g0-artifact",
        default=None,
        help="Optional path to the G0 benchmark artifact.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Optional local API key. When omitted, the script reuses env or bootstraps the localhost placeholder key.",
    )
    parser.add_argument(
        "--cursor-mcp-output",
        default=None,
        help="Optional output path for build/proofs/cline/cursor_mcp_comparison.json.",
    )
    parser.add_argument(
        "--cursor-repetitions",
        default=4,
        type=int,
        help="Number of fresh direct/MCP repository-pipeline repetitions to measure before taking the median.",
    )
    parser.add_argument(
        "--warm-cache-output",
        default=None,
        help="Optional output path for build/proofs/cline/warm_cache_comparison.json.",
    )
    parser.add_argument(
        "--warm-repetitions",
        default=5,
        type=int,
        help="Number of cold/warm suite repetitions to run before selecting the median billed-token ratio pair.",
    )
    parser.add_argument(
        "--direct-output",
        default=None,
        help="Optional output path for the raw direct repository pipeline artifact.",
    )
    parser.add_argument(
        "--mcp-output",
        default=None,
        help="Optional output path for the raw MCP repository pipeline artifact.",
    )
    parser.add_argument(
        "--cold-output",
        default=None,
        help="Optional output path for the raw cold warm-cache run artifact.",
    )
    parser.add_argument(
        "--warm-output",
        default=None,
        help="Optional output path for the raw warm warm-cache run artifact.",
    )
    args = parser.parse_args()

    resolved_root = Path(args.root).resolve()
    api_key = _resolve_api_key(args.api_key)
    g0_artifact_path = None if args.g0_artifact is None else Path(args.g0_artifact).resolve()
    collect_live_cursor_mcp_comparison_artifact(
        api_key=api_key,
        root=resolved_root,
        g0_artifact_path=g0_artifact_path,
        repetitions=args.cursor_repetitions,
        output_path=(
            resolved_root / CURSOR_MCP_COMPARISON_PATH
            if args.cursor_mcp_output is None
            else Path(args.cursor_mcp_output).resolve()
        ),
        direct_output_path=(
            resolved_root / DIRECT_REPOSITORY_PIPELINE_PATH
            if args.direct_output is None
            else Path(args.direct_output).resolve()
        ),
        mcp_output_path=(
            resolved_root / MCP_REPOSITORY_PIPELINE_PATH
            if args.mcp_output is None
            else Path(args.mcp_output).resolve()
        ),
    )
    collect_live_warm_cache_comparison_artifact(
        root=resolved_root,
        g0_artifact_path=g0_artifact_path,
        warm_repetitions=args.warm_repetitions,
        output_path=(
            resolved_root / WARM_CACHE_COMPARISON_PATH
            if args.warm_cache_output is None
            else Path(args.warm_cache_output).resolve()
        ),
        cold_output_path=(
            resolved_root / WARM_CACHE_COLD_RUN_PATH
            if args.cold_output is None
            else Path(args.cold_output).resolve()
        ),
        warm_output_path=(
            resolved_root / WARM_CACHE_WARM_RUN_PATH
            if args.warm_output is None
            else Path(args.warm_output).resolve()
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
