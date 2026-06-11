#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api_server.services.cline_live_run_proof import collect_live_run_proof
from apps.api_server.services.cline_proof_common import repo_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a real Cline live-run proof artifact with engine/plugin evidence."
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output path for the live-run proof JSON artifact.",
    )
    parser.add_argument(
        "--root",
        default=str(repo_root()),
        help="Repository root to evaluate.",
    )
    args = parser.parse_args()
    collect_live_run_proof(
        root=args.root,
        output_path=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
