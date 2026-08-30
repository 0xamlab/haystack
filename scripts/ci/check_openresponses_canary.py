#!/usr/bin/env python3
"""Asserts the openresponses-conformance CI job's hard-gated canary actually ran and passed.

A real .py file, not an embedded multi-line `python3 -c "..."` block in ci.yml -- an earlier
version of a similar CI step (see this workflow's own "Deep-dive DB connectivity from inside
the api Pod" step comment) broke YAML's literal-block-scalar parsing by putting Python
continuation lines at column 0 inside an inline string. Same lesson applied here.

Usage: check_openresponses_canary.py <results.json> <expected_total>
"""
from __future__ import annotations

import json
import sys


def main() -> int:
    if len(sys.argv) != 3:
        print(
            "usage: check_openresponses_canary.py <results.json> <expected_total>",
            file=sys.stderr,
        )
        return 2

    results_path, expected_total_raw = sys.argv[1], sys.argv[2]
    expected_total = int(expected_total_raw)

    with open(results_path) as f:
        data = json.load(f)
    summary = data["summary"]
    print(json.dumps(summary))

    if summary["total"] != expected_total:
        print(
            f"::error::expected exactly {expected_total} test(s) to run, got "
            f"{summary['total']} -- a silently-empty run must never read as green"
        )
        return 1

    if summary["failed"] != 0:
        print(
            "::error::the confirmed-passing canary scenario(s) failed -- the pinned "
            "openresponses CLI/checkout itself regressed"
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
