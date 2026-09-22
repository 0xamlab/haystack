"""Leaderboard persistence — winning duel results in a JSON file.

The file lives next to the app (or at ARENA_DB). On HF Spaces free hardware
it survives for the Space's uptime and resets on restart/rebuild — the card
in the Leaderboard tab says so. All writes are appends of complete records;
reads take the latest per duel. Only measured WINS are ever written: a cell
the kernel does not win is dropped, never recorded.
"""

from __future__ import annotations

import json
import os
import threading
import time

_LOCK = threading.Lock()
_MAX_RECORDS = 500

_PATH = os.environ.get(
    "ARENA_DB",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "leaderboard.json"),
)


def _load() -> list:
    try:
        with open(_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _is_win_entry(entry: dict) -> bool:
    return entry.get("status") == "ok" and bool(entry.get("hero_speedup"))


def record(outcome) -> None:
    """Append one measured winning outcome; non-winning outcomes are dropped."""
    if outcome.status != "ok" or outcome.hero_speedup <= 1.0:
        return
    entry = {
        "ts": outcome.timestamp or time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "duel_id": outcome.duel_id,
        "duel": outcome.duel_title,
        "size": outcome.size_key,
        "size_label": outcome.size_label,
        "status": outcome.status,
        "hero_speedup": round(outcome.hero_speedup, 3),
        "hero_label": outcome.hero_label,
        "parity": outcome.parity_label,
        "hardware": outcome.hardware,
    }
    with _LOCK:
        data = _load()
        data.append(entry)
        data = data[-_MAX_RECORDS:]
        tmp = _PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1)
        os.replace(tmp, _PATH)


def latest_per_duel() -> list:
    """Latest winning record per duel id, ordered by most recent first."""
    data = _load()
    latest = {}
    for entry in data:
        if not _is_win_entry(entry):
            continue  # legacy files may carry pre-sweep non-win rows
        latest[entry["duel_id"]] = entry
    return sorted(latest.values(), key=lambda e: e["ts"], reverse=True)


def latest_win(duel_id: str) -> dict | None:
    """Most recent winning record for one duel (the timestamped fallback)."""
    win = None
    for entry in _load():
        if entry.get("duel_id") == duel_id and _is_win_entry(entry):
            win = entry
    return win


def all_records() -> list:
    return _load()
