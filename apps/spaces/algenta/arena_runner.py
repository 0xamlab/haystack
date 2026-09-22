"""Arena duel runner — the subprocess entrypoint.

Executed by the dedicated arena interpreter (CPython 3.12 venv at
/opt/arena in the Space image; ARENA_PYTHON locally), never by the main app
process. The main app is CPython 3.14 (required by the signed
algenta-runtime-native), while the pinned arena incumbents (ruptures<3.14,
numba, etc.) require 3.12 — so duel cells run in their own interpreter,
exactly as they do in the standalone Speed Arena Space.

Protocol (stdout, line-delimited, flushed):
    PROGRESS <free-text status line>     — streamed to the UI
    RESULT <absolute path of outcome JSON> — final line on success
    ERROR <message>                      — final line on unexpected crash

The runner sweeps the duel's configurations for a winning cell (run_sweep):
the outcome JSON is the best winning configuration measured on this run, or —
when no configuration won — the last attempt (a non-win the parent replaces
with the duel's latest timestamped leaderboard win). The outcome JSON is
dataclasses.asdict(DuelOutcome); the parent reconstructs the dataclasses
from it (arena.harness is pure stdlib at import time).
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duel", required=True)
    parser.add_argument("--size", required=True)
    parser.add_argument("--result", required=True, help="path to write the outcome JSON")
    args = parser.parse_args()

    # The arena package lives next to this file.
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from arena.duels import DUELS_BY_ID
    from arena.harness import run_sweep

    duel = DUELS_BY_ID.get(args.duel)
    if duel is None:
        print(f"ERROR unknown duel {args.duel!r}", flush=True)
        return 2

    def progress(msg: str) -> None:
        print(f"PROGRESS {msg}", flush=True)

    try:
        result = run_sweep(duel, args.size, progress=progress)
        outcome = result.outcome if result.outcome is not None else result.attempts[-1]
        with open(args.result, "w", encoding="utf-8") as fh:
            json.dump(dataclasses.asdict(outcome), fh)
        print(f"RESULT {args.result}", flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001 — last-resort guard; parent renders an error card
        print(f"ERROR {type(exc).__name__}: {exc}", flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
