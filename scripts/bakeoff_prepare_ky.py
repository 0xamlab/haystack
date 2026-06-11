#!/usr/bin/env python3
"""Prepare a reproducible bake-off fixture from a public TypeScript repo.

Clones sindresorhus/ky (a public-repo-matrix training repo) at a pinned tag and
plants ONE subtle bug in the prefix/baseUrl resolution (source/core/Ky.ts): it
drops the leading-slash normalization of the input, so `ky('/users', {prefix:
'v1', ...})` builds the wrong path. The agents' task: find + fix it; ky's own
`test/base-url.ts` (ava, in-process test server — no build needed via tsx) is the
objective oracle. npm install runs once so the fixture carries node_modules.

  python scripts/bakeoff_prepare_ky.py --dest build/bakeoff_src/ky
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO_URL = "https://github.com/sindresorhus/ky.git"
PIN = "v2.0.2"  # stable release tag
BUG_FILE = "source/core/Ky.ts"
BUG_OLD = "\t\t\t\tconst normalizedInput = this.#input.replace(/^\\/+/, '');\n"
BUG_NEW = "\t\t\t\tconst normalizedInput = this.#input;\n"

VERIFY = "npx ava test/base-url.ts"
PROMPT = (
    "A unit test in this repository is failing. Run it with:  npx ava "
    "test/base-url.ts  — then find the single bug in source/ that causes the "
    "failure and fix it. Keep the public API and all other behavior unchanged. "
    "Do not modify any tests."
)


def _run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dest", default="build/bakeoff_src/ky")
    ap.add_argument("--skip-install", action="store_true")
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
        print(f"ERROR: bug-target line not found in {BUG_FILE} at {PIN} (drift).",
              file=sys.stderr)
        return 1
    target.write_text(text.replace(BUG_OLD, BUG_NEW, 1), encoding="utf-8")
    _run(["git", "-C", str(dest),
          "-c", "user.email=bakeoff@algenta", "-c", "user.name=bakeoff",
          "commit", "-aqm", "planted bug for agent bake-off"])
    print("planted bug + committed.")

    if not args.skip_install:
        print("npm install (so the fixture carries node_modules for verify)…")
        _run(["npm", "install", "--no-audit", "--no-fund", "--silent"], cwd=str(dest))
        print("npm install done.")

    print(f"\nverify (the planted bug should make this FAIL):\n  (cd {dest} && {VERIFY})")
    print(f"\nprompt:\n  {PROMPT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
