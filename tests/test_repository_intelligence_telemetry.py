"""AR-OPT-0 telemetry: primitives + the parse-span presence gate.

The presence test fails the build if `_analyze_snapshot_files` ever stops
recording `snapshot_parse_ms` — so future perf changes can't silently drop the
measurement that proves their impact.
"""

from __future__ import annotations

from pathlib import Path

from apps.api_server.services import (
    repository_intelligence_analysis_workflow as analysis_workflow,
)
from apps.api_server.services import repository_intelligence_telemetry as telemetry


def test_span_and_counters_accumulate():
    with telemetry.collect() as data:
        with telemetry.span("x_ms"):
            pass
        with telemetry.span("x_ms"):  # additive
            pass
        telemetry.record("count", 3)
        telemetry.record("count", 4)
        telemetry.record_tokens(input_uncached=10, input_cached_read=5, output=2)

    assert "x_ms" in data["spans_ms"]
    assert data["counters"]["count"] == 7
    assert data["counters"]["llm_input_tokens_uncached"] == 10
    assert data["counters"]["llm_input_tokens_cached_read"] == 5
    assert data["counters"]["llm_output_tokens"] == 2


def test_noop_outside_scope():
    assert telemetry.current() is None
    with telemetry.span("y_ms"):  # must not raise
        pass
    telemetry.record("z", 1)  # must not raise
    telemetry.record_tokens(output=99)  # must not raise
    telemetry.record_span_ms("w_ms", 1.5)  # must not raise
    assert telemetry.current() is None


def test_record_span_ms_is_additive():
    with telemetry.collect() as data:
        telemetry.record_span_ms("graph_build_ms", 2.0)
        telemetry.record_span_ms("graph_build_ms", 3.0)  # additive
    assert data["spans_ms"]["graph_build_ms"] == 5.0


def test_missing_fields_gate():
    with telemetry.collect() as data:
        with telemetry.span("snapshot_parse_ms"):
            pass
    missing = telemetry.missing_fields(data, telemetry.SNAPSHOT_SPANS, kind="spans_ms")
    assert "snapshot_parse_ms" not in missing
    assert "graph_build_ms" in missing  # not recorded here


def test_analyze_snapshot_files_records_parse_span():
    """The parse hotspot records snapshot_parse_ms inside a telemetry scope."""
    files = [Path("a.py"), Path("b.py")]

    def fake_cached(**kwargs):
        return ("analysis", kwargs["path"].name)

    with telemetry.collect() as data:
        out = analysis_workflow._analyze_snapshot_files(
            root_path=Path("/tmp"),
            files=files,
            module_index={},
            workspace_package_index={},
            workspace_go_module_index=None,
            max_file_size_bytes=1000,
            analysis_context_hash="ctx",
            analyze_file_cached=fake_cached,
            max_workers=1,
        )

    assert len(out) == 2
    assert "snapshot_parse_ms" in data["spans_ms"]
    assert data["spans_ms"]["snapshot_parse_ms"] >= 0.0
