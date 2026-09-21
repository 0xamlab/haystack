#!/usr/bin/env python3
"""Did a push move the SDK ``version`` field? (exit 0 = yes, 1 = no, 2 = could not tell)

.github/workflows/sdk-auto-bump.yml must leave a hand bump -- a push to main that itself moved
``version`` -- to auto-tag-sdk.yml, and bump everything else that changed SDK source. Until
#1089 and #1100 that decision was "did any version manifest change at all", which is the wrong
question: #1089 edited only ``description`` and #1100 only ``[tool.ruff] target-version``, both
were classified as hand bumps, neither released, and PyPI/npm kept shipping 1.0.17 metadata.

This asks the right question: read ``version`` at both revisions with the parsers the release
chain uses (tomllib / json, never a regex over the diff) and compare the values.

    python3 scripts/sdk_version_changed.py <base> <head>      # prints "<manifest>: old -> new"
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

# The version manifests: the three the public release reads (python-sdk, mcp, ts-sdk) plus the
# algenta package's, all of which scripts/bump_sdk_version.py moves in lockstep.
MANIFESTS: tuple[str, ...] = (
    "packages/python-sdk/pyproject.toml",
    "packages/algenta/pyproject.toml",
    "packages/mcp/pyproject.toml",
    "packages/ts-sdk/package.json",
)

EXIT_CHANGED = 0
EXIT_UNCHANGED = 1
EXIT_ERROR = 2


class CompareError(Exception):
    """The two revisions could not be compared; the caller must fail, not classify."""


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    git = shutil.which("git")
    if git is None:
        raise CompareError("git is not on PATH")
    return subprocess.run([git, "-C", str(repo), *args], capture_output=True, check=False)


def blob_at(repo: Path, rev: str, rel: str) -> str | None:
    """The file's text at ``rev``; None only when the path provably does not exist there.

    Absence is established by ``git ls-tree`` (exit 0, nothing listed). Every other git failure --
    a revision that does not resolve, an unreadable object, an I/O error -- raises: a missing base
    commit or a damaged object store must stop the workflow, never silently classify the push.
    """
    if _git(repo, "cat-file", "-e", f"{rev}^{{commit}}").returncode != 0:
        raise CompareError(f"{rev}: not a commit in {repo}")
    listed = _git(repo, "ls-tree", "--name-only", rev, "--", rel)
    if listed.returncode != 0:
        raise CompareError(
            f"git ls-tree {rev} -- {rel}: {listed.stderr.decode(errors='replace').strip()}"
        )
    if not listed.stdout.strip():
        return None
    shown = _git(repo, "show", f"{rev}:{rel}")
    if shown.returncode != 0:
        raise CompareError(f"git show {rev}:{rel}: {shown.stderr.decode(errors='replace').strip()}")
    try:
        return shown.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        # Not decoded with errors="replace": a manifest the release chain could not read as UTF-8
        # is a broken manifest, and the workflow must fail on it rather than compare a mangled copy.
        raise CompareError(f"{rev}:{rel}: not UTF-8 ({exc})") from exc


def version_in(rel: str, text: str | None) -> str | None:
    """``version`` as the release chain parses it: tomllib for pyproject, json for package.json.

    A manifest that does not parse, or parses without a ``version``, is a CompareError: the
    workflow maps it to exit 2 and fails, instead of exit 1 ("unchanged") and a bump.
    """
    if text is None:
        return None
    try:
        if rel.endswith(".toml"):
            return str(tomllib.loads(text)["project"]["version"])
        return str(json.loads(text)["version"])
    except (tomllib.TOMLDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise CompareError(f"{rel}: cannot read version ({exc.__class__.__name__}: {exc})") from exc


def changed_versions(repo: Path, base: str, head: str) -> dict[str, tuple[str | None, str | None]]:
    """{manifest: (old, new)} for every manifest whose version value differs between the revisions.

    A manifest absent at ``base`` (None) and present at ``head`` counts as changed: the old
    file-name test treated an added manifest as a hand bump too, and staying on that side is the
    conservative choice (auto-tag-sdk reads whatever version it declares).
    """
    changed: dict[str, tuple[str | None, str | None]] = {}
    for rel in MANIFESTS:
        old = version_in(rel, blob_at(repo, base, rel))
        new = version_in(rel, blob_at(repo, head, rel))
        if old != new:
            changed[rel] = (old, new)
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("base", help="the revision before the push (github.event.before)")
    parser.add_argument("head", help="the revision after the push (github.sha)")
    parser.add_argument(
        "--repo", type=Path, default=Path.cwd(), help="repository root (default: cwd)"
    )
    args = parser.parse_args(argv)
    # Exit 1 MEANS "no version moved" to the workflow, and an uncaught exception would exit 1 too,
    # so every failure -- ours (CompareError) or an unforeseen one -- must become exit 2.
    try:
        changed = changed_versions(args.repo, args.base, args.head)
    except CompareError as exc:
        print(f"sdk_version_changed: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:
        print(f"sdk_version_changed: unexpected {exc.__class__.__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR
    for rel, (old, new) in changed.items():
        print(f"{rel}: {old} -> {new}")
    return EXIT_CHANGED if changed else EXIT_UNCHANGED


if __name__ == "__main__":
    sys.exit(main())
