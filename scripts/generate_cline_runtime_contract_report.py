#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.api_server.services.cline_runtime_contract import (
    RUNTIME_CONTRACT_REPORT_PATH,
    collect_runtime_contract_report,
)
from apps.api_server.services.cline_proof_common import repo_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect the Cline runtime contract proof report.")
    parser.add_argument(
        "--output",
        default=str((repo_root() / RUNTIME_CONTRACT_REPORT_PATH).resolve()),
        help="Path to write the runtime contract report JSON.",
    )
    args = parser.parse_args()
    collect_runtime_contract_report(output_path=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
