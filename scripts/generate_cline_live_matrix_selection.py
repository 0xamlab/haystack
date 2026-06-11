#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api_server.services.cline_live_matrix_selection import (
    DEFAULT_TOP_RANKED_LANGUAGE_COUNT,
    build_cline_live_matrix_artifacts,
)
from apps.api_server.services.cline_proof_common import repo_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate the Cline live-matrix adapter registry and selection artifacts."
    )
    parser.add_argument(
        "--root",
        default=str(repo_root()),
        help="Repository root to evaluate.",
    )
    parser.add_argument(
        "--top-ranked-language-count",
        default=DEFAULT_TOP_RANKED_LANGUAGE_COUNT,
        type=int,
        help="How many top-ranked languages to include before family expansion.",
    )
    args = parser.parse_args()
    build_cline_live_matrix_artifacts(
        root=args.root,
        top_ranked_language_count=args.top_ranked_language_count,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
