#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api_server.services.cline_parity_report import build_cline_parity_artifacts
from apps.api_server.services.cline_proof_common import repo_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the Cline parity ledger and report.")
    parser.add_argument(
        "--allow-offline-live-docs",
        action="store_true",
        help="Use the checked-in docs snapshot as the live-docs review input.",
    )
    parser.add_argument(
        "--allow-dirty-tree",
        action="store_true",
        help="Allow dirty-tree proof artifacts to satisfy provenance validation.",
    )
    parser.add_argument(
        "--root",
        default=str(repo_root()),
        help="Repository root to evaluate.",
    )
    args = parser.parse_args()
    build_cline_parity_artifacts(
        root=args.root,
        allow_offline_live_docs=args.allow_offline_live_docs,
        allow_dirty_tree=args.allow_dirty_tree,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
