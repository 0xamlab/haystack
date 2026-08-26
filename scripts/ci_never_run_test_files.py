#!/usr/bin/env python3
"""Print the top-level test files no CI invocation ever runs.

The complement of `ci_curated_test_files.py` within the universe blast-radius selection can
actually reach. Used to MEASURE the known-red baseline the ratchet gate consumes
(`ci_blast_radius_gate.py`), which is why the universe has to match the selector's exactly:
a baseline covering files the gate can never see would be dead weight, and one missing files
it can see would block PRs on unmeasured reds.

`scripts/test_impact.py` enumerates top-level `tests/test_*.py`, so subdirectories such as
`tests/integration/` are deliberately OUT of scope here -- selection cannot reach them, and
including them would have added 18 live-stack failures to the baseline that no PR can ever
trigger.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from ci_curated_test_files import curated_files  # noqa: E402


def selectable_test_files() -> set[str]:
    """Top-level `tests/test_*.py` -- the same universe `test_impact.py` selects from."""
    return {
        f"tests/{p.name}"
        for p in (REPO_ROOT / "tests").glob("test_*.py")
        if p.is_file()
    }


def never_run_test_files() -> list[str]:
    return sorted(selectable_test_files() - curated_files())


def main() -> int:
    for f in never_run_test_files():
        print(f)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
