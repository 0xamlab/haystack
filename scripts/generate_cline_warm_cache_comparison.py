#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api_server.services.cline_competitive_measurements import (
    WARM_CACHE_COMPARISON_PATH,
    build_warm_cache_comparison_artifact,
)
from apps.api_server.services.cline_proof_common import read_json, repo_root


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate cold-vs-warm cache competitive comparison artifact."
    )
    parser.add_argument("--g0-artifact", required=True, help="Path to the G0 benchmark artifact.")
    parser.add_argument(
        "--cold-json",
        required=True,
        help="Path to the cold run JSON payload.",
    )
    parser.add_argument(
        "--warm-json",
        required=True,
        help="Path to the warm run JSON payload.",
    )
    parser.add_argument(
        "--output",
        default=str((repo_root() / WARM_CACHE_COMPARISON_PATH).resolve()),
        help="Path to write the warm-cache comparison artifact.",
    )
    args = parser.parse_args()
    build_warm_cache_comparison_artifact(
        g0_payload=read_json(Path(args.g0_artifact).resolve()),
        cold_payload=read_json(Path(args.cold_json).resolve()),
        warm_payload=read_json(Path(args.warm_json).resolve()),
        output_path=Path(args.output).resolve(),
        cold_source_path=Path(args.cold_json).resolve(),
        warm_source_path=Path(args.warm_json).resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
