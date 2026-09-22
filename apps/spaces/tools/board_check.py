"""Leaderboard integrity check.

A board is a JSON array or a JSONL file of result rows. Every row must carry
``hardware_id``, ``space_id`` and an ISO 8601 UTC ``ts_utc``. Rows whose ``hardware_id``
differs from the id of the machine reading the board belong to the "published elsewhere"
set and never to "measured here" — this tool partitions them and fails on any row that
cannot be attributed.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

REQUIRED_FIELDS = ("hardware_id", "space_id", "ts_utc")


class BoardError(ValueError):
    """The board file cannot be read as rows."""


def load_rows(path: Path) -> list[dict]:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        rows = []
        for n, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise BoardError(f"{path}:{n}: {exc.msg}") from exc
    else:
        try:
            rows = json.loads(text) if text.strip() else []
        except json.JSONDecodeError as exc:
            raise BoardError(f"{path}: {exc.msg}") from exc
        if not isinstance(rows, list):
            raise BoardError(f"{path}: top level must be a JSON array")
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise BoardError(f"{path}: row {i} is not an object")
    return rows


def _utc_timestamp(value: object) -> str | None:
    if not isinstance(value, str) or not value:
        return "ts_utc must be a non-empty ISO 8601 string"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return f"ts_utc {value!r} is not ISO 8601"
    if parsed.tzinfo is None:
        return f"ts_utc {value!r} has no timezone"
    if parsed.utcoffset() != timedelta(0):
        return f"ts_utc {value!r} is not UTC"
    return None


def validate_row(row: dict) -> list[str]:
    problems: list[str] = []
    for key in REQUIRED_FIELDS:
        if key not in row:
            problems.append(f"missing {key}")
        elif key != "ts_utc" and (not isinstance(row[key], str) or not row[key].strip()):
            problems.append(f"{key} must be a non-empty string")
    if "ts_utc" in row:
        issue = _utc_timestamp(row["ts_utc"])
        if issue:
            problems.append(issue)
    return problems


def partition(rows: list[dict], current_hardware_id: str) -> tuple[list[dict], list[dict]]:
    """(measured here, published elsewhere) — attribution by hardware_id only."""
    here = [r for r in rows if r.get("hardware_id") == current_hardware_id]
    elsewhere = [r for r in rows if r.get("hardware_id") != current_hardware_id]
    return here, elsewhere


@dataclass(frozen=True)
class BoardReport:
    path: Path
    total: int
    invalid: tuple[tuple[int, tuple[str, ...]], ...]
    measured_here: int
    published_elsewhere: int

    @property
    def ok(self) -> bool:
        return not self.invalid

    def lines(self) -> list[str]:
        out = [f"{self.path}: {self.total} rows"]
        for index, problems in self.invalid:
            out.append(f"  row {index}: {'; '.join(problems)}")
        out.append(f"  measured here: {self.measured_here}")
        out.append(f"  published elsewhere: {self.published_elsewhere}")
        out.append(
            "  OK" if self.ok else f"  FAIL: {len(self.invalid)} row(s) cannot be attributed"
        )
        return out


def check_board(path: Path, current_hardware_id: str) -> BoardReport:
    if not current_hardware_id.strip():
        raise BoardError("current hardware id must not be empty")
    rows = load_rows(path)
    invalid = tuple(
        (i, tuple(problems)) for i, row in enumerate(rows) if (problems := validate_row(row))
    )
    valid = [row for i, row in enumerate(rows) if not validate_row(row)]
    here, elsewhere = partition(valid, current_hardware_id)
    return BoardReport(
        path=Path(path),
        total=len(rows),
        invalid=invalid,
        measured_here=len(here),
        published_elsewhere=len(elsewhere),
    )


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="validate a leaderboard JSON/JSONL file")
    ap.add_argument("path", type=Path)
    ap.add_argument(
        "--hardware-id", required=True, help="hardware id of the machine reading the board"
    )
    a = ap.parse_args(argv)
    try:
        report = check_board(a.path, a.hardware_id)
    except (BoardError, OSError) as exc:
        print(f"board check failed: {exc}")
        return 1
    for line in report.lines():
        print(line)
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
