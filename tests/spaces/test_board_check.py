"""apps/spaces/tools/board_check.py — leaderboard attribution."""

from __future__ import annotations

import json
from pathlib import Path

import board_check as bc
import pytest

HERE = "l4x1:sm_89:24gb"
ROWS = [
    {
        "hardware_id": HERE,
        "space_id": "thyn-ai/algenta",
        "ts_utc": "2026-09-22T14:02:00Z",
        "ratio": 3.1,
    },
    {"hardware_id": HERE, "space_id": "thyn-ai/algenta", "ts_utc": "2026-09-22T14:03:00+00:00"},
    {"hardware_id": "m4-max", "space_id": "local", "ts_utc": "2026-09-01T09:00:00Z"},
    {"space_id": "thyn-ai/algenta", "ts_utc": "2026-09-22T14:02:00Z"},
    {"hardware_id": "", "space_id": "x", "ts_utc": "2026-09-22T14:02:00Z"},
    {"hardware_id": HERE, "space_id": "x", "ts_utc": "2026-09-22 14:02"},
    {"hardware_id": HERE, "space_id": "x", "ts_utc": "2026-09-22T14:02:00+02:00"},
    {"hardware_id": HERE, "space_id": 7, "ts_utc": 1700000000},
]


def test_validate_row_messages() -> None:
    assert bc.validate_row(ROWS[0]) == []
    assert bc.validate_row(ROWS[1]) == []
    assert bc.validate_row(ROWS[3]) == ["missing hardware_id"]
    assert bc.validate_row(ROWS[4]) == ["hardware_id must be a non-empty string"]
    assert bc.validate_row(ROWS[5]) == ["ts_utc '2026-09-22 14:02' has no timezone"]
    assert bc.validate_row(ROWS[6]) == ["ts_utc '2026-09-22T14:02:00+02:00' is not UTC"]
    assert bc.validate_row(ROWS[7]) == [
        "space_id must be a non-empty string",
        "ts_utc must be a non-empty ISO 8601 string",
    ]
    assert bc.validate_row({"hardware_id": "h", "space_id": "s", "ts_utc": "yesterday"}) == [
        "ts_utc 'yesterday' is not ISO 8601"
    ]
    assert bc.validate_row({}) == ["missing hardware_id", "missing space_id", "missing ts_utc"]


def test_partition_by_hardware_id() -> None:
    here, elsewhere = bc.partition(ROWS[:3], HERE)
    assert here == ROWS[:2] and elsewhere == [ROWS[2]]
    assert bc.partition([], HERE) == ([], [])


def test_check_board_json_and_jsonl(tmp_path: Path) -> None:
    board = tmp_path / "board.json"
    board.write_text(json.dumps(ROWS), encoding="utf-8")
    report = bc.check_board(board, HERE)
    assert report.total == 8 and not report.ok
    assert [i for i, _ in report.invalid] == [3, 4, 5, 6, 7]
    assert report.measured_here == 2 and report.published_elsewhere == 1
    lines = report.lines()
    assert lines[0].endswith("board.json: 8 rows")
    assert "  row 3: missing hardware_id" in lines
    assert lines[-1] == "  FAIL: 5 row(s) cannot be attributed"

    jsonl = tmp_path / "board.jsonl"
    jsonl.write_text("\n".join(json.dumps(r) for r in ROWS[:3]) + "\n\n", encoding="utf-8")
    report = bc.check_board(jsonl, HERE)
    assert (
        report.ok
        and report.total == 3
        and report.measured_here == 2
        and report.published_elsewhere == 1
    )
    assert report.lines()[-1] == "  OK"
    assert bc.check_board(jsonl, "m4-max").measured_here == 1


def test_load_rows_errors(tmp_path: Path) -> None:
    p = tmp_path / "b.json"
    p.write_text('{"rows": []}', encoding="utf-8")
    with pytest.raises(bc.BoardError, match="top level must be a JSON array"):
        bc.load_rows(p)
    p.write_text("[1, 2]", encoding="utf-8")
    with pytest.raises(bc.BoardError, match="row 0 is not an object"):
        bc.load_rows(p)
    p.write_text("not json", encoding="utf-8")
    with pytest.raises(bc.BoardError, match="b.json"):
        bc.load_rows(p)
    p.write_text("", encoding="utf-8")
    assert bc.load_rows(p) == []
    q = tmp_path / "b.jsonl"
    q.write_text('{"a": 1}\n{bad\n', encoding="utf-8")
    with pytest.raises(bc.BoardError, match="b.jsonl:2"):
        bc.load_rows(q)
    with pytest.raises(bc.BoardError, match="must not be empty"):
        bc.check_board(p, "  ")


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    board = tmp_path / "board.jsonl"
    board.write_text("\n".join(json.dumps(r) for r in ROWS[:3]), encoding="utf-8")
    assert bc.main([str(board), "--hardware-id", HERE]) == 0
    out = capsys.readouterr().out
    assert "measured here: 2" in out and "published elsewhere: 1" in out
    board = tmp_path / "board.json"
    board.write_text(json.dumps(ROWS), encoding="utf-8")
    assert bc.main([str(board), "--hardware-id", HERE]) == 1
    assert "FAIL: 5 row(s)" in capsys.readouterr().out
    assert bc.main([str(tmp_path / "missing.json"), "--hardware-id", HERE]) == 1
    assert "board check failed" in capsys.readouterr().out
