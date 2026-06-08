from __future__ import annotations

import json
from pathlib import Path

from tests.integration import test_csv_pipeline


def test_write_results_summary_emits_machine_readable_artifact(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(test_csv_pipeline, "PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(
        test_csv_pipeline,
        "results",
        [
            (test_csv_pipeline.PASS, "one"),
            (test_csv_pipeline.PASS, "two"),
            (test_csv_pipeline.SKIP, "three", "reason"),
        ],
    )
    monkeypatch.setattr(test_csv_pipeline, "timings", [("one", 1.25), ("two", 0.75)])
    monkeypatch.setattr(
        test_csv_pipeline,
        "pipeline_results",
        [
            {
                "filename": "Backlog.csv",
                "rows": 100,
                "parse_time_ms": 10.0,
                "map_time_ms": 3.0,
                "sim_time_ms": 2.0,
            },
            {
                "filename": "Bookings.csv",
                "rows": 50,
                "parse_time_ms": 5.0,
                "map_time_ms": 1.0,
                "sim_time_ms": 0.0,
            },
        ],
    )

    test_csv_pipeline._write_results_summary()

    payload = json.loads((tmp_path / "build" / "csv_pipeline_summary.json").read_text())
    assert payload["passed"] == 2
    assert payload["failed"] == 0
    assert payload["skipped"] == 1
    assert payload["total"] == 3
    assert payload["pipeline_file_count"] == 2
    assert payload["pipeline_rows_total"] == 150
    assert payload["total_parse_ms"] == 15.0
    assert payload["total_map_ms"] == 4.0
    assert payload["total_sim_ms"] == 2.0
    assert payload["overall_rows_per_sec"] == 10000.0
    assert payload["total_test_time_s"] == 2.0


def test_write_results_csv_uses_lf_line_endings(monkeypatch, tmp_path: Path) -> None:
    csv_module_path = tmp_path / "test_csv_pipeline.py"
    csv_module_path.write_text("# synthetic module path\n", encoding="utf-8")
    monkeypatch.setattr(test_csv_pipeline, "__file__", str(csv_module_path))
    monkeypatch.setattr(
        test_csv_pipeline,
        "pipeline_results",
        [
            {
                "filename": "Backlog.csv",
                "rows": 100,
                "columns": 4,
                "numeric_cols": 2,
                "parse_time_ms": 10.0,
                "map_time_ms": 1.0,
                "sim_time_ms": 2.0,
                "total_time_ms": 13.0,
                "status": "parsed",
                "rows_per_sec": 10000,
            }
        ],
    )

    test_csv_pipeline._write_results_csv()

    payload = (tmp_path / "csv_pipeline_results.csv").read_bytes()
    assert b"\r\n" not in payload
    assert b"\n" in payload
