#!/usr/bin/env python3
"""Prepare a reproducible, objective bake-off fixture from a public repo.

Clones pallets/click (one of the public-repo-matrix training repos) at a pinned
release tag and plants ONE subtle bug in ``make_default_short_help`` — it drops
the inter-word space from the truncation length budget. The agents' task is to
run the tests, find the single bug, and fix it; click's own parametrized test
``test_make_default_short_help`` is the objective oracle (no install needed —
click is pure-Python on PYTHONPATH=src).

  python scripts/bakeoff_prepare_click.py --dest build/bakeoff_src/click
  # then run scripts/agent_bakeoff.py with the printed command.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/pallets/click.git"
PIN = "8.4.1"  # stable release tag — reproducible
BUG_FILE = "src/click/utils.py"
# Subtle, realistic bug: the truncation budget forgets the inter-word space.
BUG_OLD = "        total_length += len(word) + (i > 0)\n"
BUG_NEW = "        total_length += len(word)\n"

VERIFY = (
    "PYTHONPATH=src python -m pytest tests/test_utils.py "
    "-k make_default_short_help -p no:randomly -q"
)
PROMPT = (
    "A unit test in this repository is failing. Run the test suite, find the "
    "single bug in src/click that causes it, and fix it. Keep the public API "
    "and all other behavior unchanged. Do not edit the tests."
)


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", default="build/bakeoff_src/click")
    args = ap.parse_args()

    dest = Path(args.dest).resolve()
    if dest.exists():
        shutil.rmtree(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    print(f"cloning {REPO_URL}@{PIN} -> {dest}")
    _run(["git", "clone", "--quiet", "--depth", "1", "--branch", PIN, REPO_URL, str(dest)])

    target = dest / BUG_FILE
    text = target.read_text(encoding="utf-8")
    if BUG_OLD not in text:
        print(f"ERROR: bug-target line not found in {BUG_FILE} at {PIN} "
              f"(upstream drift — update BUG_OLD).", file=sys.stderr)
        return 1
    target.write_text(text.replace(BUG_OLD, BUG_NEW, 1), encoding="utf-8")
    _run(["git", "-C", str(dest),
          "-c", "user.email=bakeoff@algenta", "-c", "user.name=bakeoff",
          "commit", "-aqm", "planted bug for agent bake-off"])
    print("planted bug + committed.\n")

    print("bake-off command:")
    print(f"  python scripts/agent_bakeoff.py \\\n"
          f"    --repo {dest} \\\n"
          f"    --prompt {PROMPT!r} \\\n"
          f"    --verify {VERIFY!r} \\\n"
          f"    --agents algenta,codex,gemini")
    print(f"\nsanity — the planted bug should make this FAIL:\n  (cd {dest} && {VERIFY})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
