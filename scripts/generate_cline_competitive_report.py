#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api_server.services.cline_competitive_report import (
    COMPETITIVE_REPORT_PATH,
    build_competitive_experience_report,
    build_competitive_input_from_artifact_paths,
)
from apps.api_server.services.cline_competitive_status import (
    build_blocked_competitive_experience_report,
)
from apps.api_server.services.cline_proof_common import repo_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Cline competitive experience report.")
    parser.add_argument("--g0-artifact", help="Path to the G0 benchmark JSON artifact.")
    parser.add_argument(
        "--cursor-mcp-json",
        help="Path to the Cursor-vs-direct comparison JSON artifact.",
    )
    parser.add_argument(
        "--warm-cache-json",
        help="Path to the warm-cache comparison JSON artifact.",
    )
    parser.add_argument(
        "--output",
        help="Path to write the competitive experience report JSON.",
    )
    parser.add_argument(
        "--root",
        help="Repository root used for proof context and default output resolution.",
    )
    parser.add_argument(
        "--allow-dirty-tree",
        action="store_true",
        help="Allow dirty-tree proof artifacts when validating source competitive artifacts.",
    )
    args = parser.parse_args()
    resolved_root = repo_root() if args.root is None else Path(args.root).resolve()
    output_path = (
        resolved_root / COMPETITIVE_REPORT_PATH
        if args.output is None
        else Path(args.output).resolve()
    )
    has_complete_artifacts = all(
        (
            args.g0_artifact,
            args.cursor_mcp_json,
            args.warm_cache_json,
        )
    )
    if has_complete_artifacts:
        benchmark_input = build_competitive_input_from_artifact_paths(
            g0_artifact_path=args.g0_artifact,
            cursor_mcp_artifact_path=args.cursor_mcp_json,
            warm_cache_artifact_path=args.warm_cache_json,
            root=resolved_root,
            allow_dirty_tree=args.allow_dirty_tree,
        )
        build_competitive_experience_report(
            benchmark_input=benchmark_input,
            root=resolved_root,
            output_path=output_path,
        )
        return 0
    build_blocked_competitive_experience_report(
        root=resolved_root,
        output_path=output_path,
        g0_artifact_path=args.g0_artifact,
        cursor_mcp_artifact_path=args.cursor_mcp_json,
        warm_cache_artifact_path=args.warm_cache_json,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
