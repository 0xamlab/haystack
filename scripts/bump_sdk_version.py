#!/usr/bin/env python3
"""Bump the public SDK version in lockstep across every manifest the D2 guard checks.

The eight locations below MUST agree (tests/test_sdk_package_metadata.py fails the build
otherwise), so a release is never "bump one file and hope". Used by
.github/workflows/sdk-auto-bump.yml on every merge that touches SDK code, and by hand:

    python3 scripts/bump_sdk_version.py --level patch          # 1.0.13 -> 1.0.14
    python3 scripts/bump_sdk_version.py --to 1.1.0             # explicit
    python3 scripts/bump_sdk_version.py --level minor --dry-run

Prints ``<old> -> <new>`` on success; exits 1 (touching nothing) if any location does not carry
the current version, so a half-bumped tree is impossible.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# (relative path, regexes); each regex must match exactly once and capture the version.
LOCKSTEP: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("packages/python-sdk/pyproject.toml", (r'(?m)^version = "([^"]+)"$',)),
    ("packages/python-sdk/decision_engine/__init__.py",
     (r'(?m)^__version__ = "([^"]+)"$',)),
    ("packages/algenta/pyproject.toml", (r'(?m)^version = "([^"]+)"$',)),
    ("packages/algenta/algenta/__init__.py", (r'(?m)^__version__ = "([^"]+)"$',)),
    ("packages/mcp/pyproject.toml", (r'(?m)^version = "([^"]+)"$',)),
    ("packages/ts-sdk/package.json", (r'(?m)^  "version": "([^"]+)",$',)),
    # lockfile v3: the root "version" and packages[""].version. The latter is matched INSIDE the
    # `"": {` block (every dependency entry also has an indent-6 "version" line -- 226 of them).
    (
        "packages/ts-sdk/package-lock.json",
        (
            r'(?m)^  "version": "([^"]+)",$',
            r'(?ms)^    "": \{\n'
            r'(?:      "(?!version")[^"\n]+": [^\n]*\n)*?'
            r'      "version": "([^"]+)",$',
        ),
    ),
    # MCP registry manifest: top-level version + packages[0].version
    ("server.json", (r'(?m)^  "version": "([^"]+)",$', r'(?m)^      "version": "([^"]+)",$')),
)
LOCKSTEP_FILES = tuple(path for path, _ in LOCKSTEP)
_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def current_version(root: Path) -> str:
    text = (root / LOCKSTEP[0][0]).read_text(encoding="utf-8")
    m = re.search(LOCKSTEP[0][1][0], text)
    if not m:
        raise SystemExit(f"{LOCKSTEP[0][0]}: no version line")
    return m.group(1)


def next_version(current: str, level: str) -> str:
    m = _SEMVER.match(current)
    if not m:
        raise SystemExit(f"current version {current!r} is not MAJOR.MINOR.PATCH")
    major, minor, patch = (int(x) for x in m.groups())
    if level == "major":
        return f"{major + 1}.0.0"
    if level == "minor":
        return f"{major}.{minor + 1}.0"
    if level == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise SystemExit(f"unknown level {level!r}")


def plan(root: Path, old: str, new: str) -> dict[Path, str]:
    """New file contents, or SystemExit if any location does not carry ``old`` exactly once."""
    out: dict[Path, str] = {}
    problems: list[str] = []
    for rel, patterns in LOCKSTEP:
        path = root / rel
        if not path.exists():
            problems.append(f"{rel}: missing")
            continue
        text = path.read_text(encoding="utf-8")
        file_ok = True
        for pat in patterns:
            matches = list(re.finditer(pat, text))
            if len(matches) != 1:
                problems.append(f"{rel}: pattern {pat!r} matched {len(matches)} time(s), expected 1")
                file_ok = False
                continue
            m = matches[0]
            if m.group(1) != old:
                problems.append(f"{rel}: carries {m.group(1)!r}, expected {old!r}")
                file_ok = False
                continue
            # Replace exactly the captured version -- never the first occurrence of `old` inside the
            # whole match (a multi-line match may contain the same digits in an earlier field).
            text = text[: m.start(1)] + new + text[m.end(1):]
        if file_ok:
            out[path] = text
    if problems:
        raise SystemExit("lockstep check failed -- nothing written:\n  " + "\n  ".join(problems))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])  # first paragraph
    ap.add_argument("--root", default=".", help="repository root (default: cwd)")
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument("--level", choices=("patch", "minor", "major"), default="patch")
    grp.add_argument("--to", help="explicit MAJOR.MINOR.PATCH target")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true", help="print {old, new, files} as JSON")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()
    old = current_version(root)
    new = args.to if args.to else next_version(old, args.level)
    if args.to and not _SEMVER.match(new):
        raise SystemExit(f"--to {new!r} is not MAJOR.MINOR.PATCH")
    if new == old:
        raise SystemExit(f"target {new} equals the current version")
    changes = plan(root, old, new)
    if not args.dry_run:
        for path, text in changes.items():
            path.write_text(text, encoding="utf-8")
    if args.json:
        files = [str(p.relative_to(root)) for p in changes]
        print(json.dumps({"old": old, "new": new, "files": files, "dry_run": args.dry_run}))
    else:
        print(f"{old} -> {new}" + (" (dry run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
