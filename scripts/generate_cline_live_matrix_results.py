#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api_server.services.cline_live_matrix_results import (
    build_live_matrix_results_artifact,
)
from apps.api_server.services.cline_proof_common import repo_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the Cline live matrix results artifact or blocked-runtime status."
    )
    parser.add_argument(
        "--root",
        default=str(repo_root()),
        help="Repository root to evaluate.",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the live matrix with the real local proof runner instead of inventory-only mode.",
    )
    parser.add_argument(
        "--max-languages",
        type=int,
        default=None,
        help="Optional limit on the number of selected live languages to execute.",
    )
    args = parser.parse_args()
    build_live_matrix_results_artifact(
        root=args.root,
        execute=args.execute,
        max_languages=args.max_languages,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
