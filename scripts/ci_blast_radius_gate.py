#!/usr/bin/env python3
"""Decide whether the blast-radius extras are allowed to have failed.

The extras are test files no CI invocation has ever run (176 curated of 1014 measured
2026-08-26, so 838 never execute). A file's FIRST execution therefore surfaces failures
that predate the PR which happened to reach it, and failing the job on those punishes
whoever touches a neighbouring file -- the wider the diff, the more files it reaches, so
a naive gate gets stricter the *less* related the change is. That is why the extras
started out advisory. Leaving them advisory forever, though, means the surface never
actually becomes covered.

The ratchet: a MEASURED baseline of known-red node IDs is tolerated with a warning, and
anything outside it fails the job. Every line removed from the baseline is a real fix,
and the file can only shrink.

Two deliberate choices:

- **Reads pytest's terse summary, not its exit code.** A run can exit non-zero with every
  red already baselined; exit status alone cannot separate that from a new regression.
- **The baseline must be measured on CI, never on a developer machine.** Two independent
  classes of false red were observed locally on 2026-08-26 -- a shared Postgres stamped
  at an alembic revision present in no tree (every DB fixture errors) and a pixi
  environment built from a stale branch pinning an older `mcp` (7 phantom failures).
  Baselining either would have committed a lie that then silences a real failure.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_KEYWORDS = ("FAILED ", "ERROR ")


def _node_from_summary(rest: str) -> str:
    """Split `<nodeid> - <message>` when the node ID may itself contain ` - `.

    A parametrised id is built from the repr of its arguments, so `[a - b]` is possible,
    and cutting at the first ` - ` would yield `...::test_x[a` -- a node ID matching no
    baseline entry, which in a BLOCKING gate means a spurious block on a red that was
    already accepted. Brackets are the signal: keep absorbing segments while a `[` is
    still unclosed. A message containing balanced brackets (`assert [1] == [2]`) is
    unaffected, because the cut already happened before it.
    """
    parts = rest.split(" - ")
    node = parts[0]
    index = 1
    while index < len(parts) and node.count("[") > node.count("]"):
        node = f"{node} - {parts[index]}"
        index += 1
    return node.strip()


def parse_reds(text: str) -> list[str]:
    """Node IDs pytest reported as FAILED or ERROR, in first-seen order.

    `-q` short-summary lines look like `FAILED tests/x.py::test_y[p] - AssertionError: ..`.
    A parametrised id can contain spaces and brackets, so splitting on whitespace would
    truncate it; `_node_from_summary` handles the ` - ` boundary.
    """
    seen: dict[str, None] = {}
    for raw in text.splitlines():
        line = raw.strip()
        for keyword in _KEYWORDS:
            if line.startswith(keyword):
                node = _node_from_summary(line[len(keyword) :])
                if node:
                    seen.setdefault(node, None)
                break
    return list(seen)


def parse_baseline(text: str) -> set[str]:
    """Baseline entries: a full node ID, or a bare path meaning "this whole file"."""
    out: set[str] = set()
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            out.add(line)
    return out


def is_baselined(node: str, baseline: set[str]) -> bool:
    """True when `node` is covered by the baseline.

    An entry naming a file covers every red in that file (a collection ERROR has no test
    part at all, so file granularity has to be expressible). An entry naming one node
    covers only that node -- it must NOT excuse a different test in the same file, which
    is the whole point of the ratchet.
    """
    if node in baseline:
        return True
    return node.split("::", 1)[0] in baseline


def new_reds(pytest_output: str, baseline_text: str) -> list[str]:
    baseline = parse_baseline(baseline_text)
    return [n for n in parse_reds(pytest_output) if not is_baselined(n, baseline)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pytest-output", required=True, type=Path)
    parser.add_argument("--baseline", type=Path, default=None)
    args = parser.parse_args(argv)

    try:
        output = args.pytest_output.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        # Fail CLOSED: if the run's own output cannot be read, nothing has been shown to
        # be fine. Reporting "no new reds" here would be the failure mode this gate exists
        # to prevent.
        print(f"::error::blast-radius gate could not read {args.pytest_output}: {exc}")
        return 1

    baseline_text = ""
    if args.baseline is not None and args.baseline.is_file():
        baseline_text = args.baseline.read_text(encoding="utf-8", errors="replace")

    reds = parse_reds(output)
    fresh = new_reds(output, baseline_text)
    baselined = len(reds) - len(fresh)

    if baselined:
        print(
            f"::warning::blast-radius: {baselined} known-red result(s) tolerated by "
            f"{args.baseline}. Each one is triage owed; the baseline may only shrink."
        )
    if not fresh:
        print(f"::notice::blast-radius gate: no new reds ({len(reds)} total, all baselined)")
        return 0

    print(
        f"::error::blast-radius gate: {len(fresh)} result(s) are NOT in the baseline. "
        "Blast radius reached a test file this change affects and it failed."
    )
    for node in fresh:
        print(f"::error::  new red: {node}")
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
