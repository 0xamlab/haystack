#!/usr/bin/env python3
"""Print the test files the curated CI gate already runs.

`pnpm check` gates Python purely through hand-listed files in package.json. Measured
2026-08-26: 1014 test files exist under tests/, 176 are referenced by ANY CI invocation, and
838 never execute on any PR or push -- a curated list cannot grow, so new coverage is born
dead (all 36 orchestrator tests written that day were in the 838).

Blast-radius selection is the fix, but replacing the curated list outright would risk DROPPING
coverage if the selector ever under-selects. So the gate is `curated UNION subset`: this script
emits the curated half, and the workflow subtracts it from the selected set to avoid running
the same file twice. Coverage can therefore only ever grow.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_TEST_PATH = re.compile(r"tests/[\w/.\-]+\.py")


def curated_files() -> set[str]:
    out: set[str] = set()
    pkg = REPO_ROOT / "package.json"
    try:
        scripts = (json.loads(pkg.read_text(encoding="utf-8")) or {}).get("scripts") or {}
    except (OSError, json.JSONDecodeError):
        return out
    for body in scripts.values():
        if isinstance(body, str):
            out |= set(_TEST_PATH.findall(body))
    return {f for f in out if (REPO_ROOT / f).is_file()}


def main() -> int:
    for f in sorted(curated_files()):
        print(f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
