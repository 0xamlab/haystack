#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api_server.services.cline_proof_bundle import build_cline_proof_bundle
from apps.api_server.services.cline_proof_common import repo_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the canonical Cline proof bundle in deterministic stage order."
    )
    parser.add_argument(
        "--root",
        default=str(repo_root()),
        help="Repository root to evaluate.",
    )
    parser.add_argument(
        "--allow-dirty-tree",
        action="store_true",
        help="Allow dirty-tree proof artifacts to satisfy provenance validation.",
    )
    parser.add_argument(
        "--review-live-docs",
        action="store_true",
        help="Fetch live Cline docs for review instead of using only the checked-in snapshot.",
    )
    parser.add_argument(
        "--execute-live-matrix",
        action="store_true",
        help="Execute the selected live language matrix instead of writing readiness-only results.",
    )
    parser.add_argument(
        "--max-live-matrix-languages",
        type=int,
        default=None,
        help="Optional cap on the number of selected live matrix languages to execute.",
    )
    parser.add_argument(
        "--execute-competitive",
        action="store_true",
        help="Collect live cursor/MCP and warm-cache competitive artifacts before building the report.",
    )
    parser.add_argument(
        "--cursor-repetitions",
        type=int,
        default=4,
        help="Paired direct/MCP repetitions for the live competitive collector.",
    )
    parser.add_argument(
        "--warm-repetitions",
        type=int,
        default=5,
        help="Cold/warm suite repetitions for the live warm-cache collector.",
    )
    parser.add_argument(
        "--g0-artifact",
        default=None,
        help="Optional path to a prebuilt g0 benchmark artifact.",
    )
    args = parser.parse_args()
    build_cline_proof_bundle(
        root=args.root,
        allow_dirty_tree=args.allow_dirty_tree,
        allow_offline_live_docs=not args.review_live_docs,
        execute_live_matrix=args.execute_live_matrix,
        max_live_matrix_languages=args.max_live_matrix_languages,
        execute_competitive=args.execute_competitive,
        cursor_repetitions=args.cursor_repetitions,
        warm_repetitions=args.warm_repetitions,
        g0_artifact_path=args.g0_artifact,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
