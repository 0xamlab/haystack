"""AR-OPT-0 telemetry presence gate (integration).

Runs a real snapshot + triage on a fixture repo inside a telemetry scope and
fails the build if any required span stops being recorded. This is the mandatory
CI guard from the optimization roadmap: future perf changes (process-pool
parsing, slim manifests, incremental graph) cannot silently drop the
measurement that proves their impact against `scripts/g0_token_benchmark.py`.
"""
from __future__ import annotations

from tests._repository_intelligence_service_helpers import *  # noqa: F401,F403

from apps.api_server.services import repository_intelligence_telemetry as telemetry


def test_snapshot_and_triage_populate_required_spans(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))
    repo_path = _literal_mismatch_repo(tmp_path)
    connector = _connector_for_repo(repo_path)

    with telemetry.collect() as data:
        snapshot = repository_service.create_repository_snapshot(
            connector=connector,
            request=RepositorySnapshotCreateRequest(),
        )
        repository_service.triage_repository(
            connector=connector,
            request=RepositoryTriageRequest(
                snapshot_id=snapshot.snapshot_id,
                signals={
                    "issue_text": (
                        "normalize_status returns closed for OPEN inputs."
                    ),
                    "diagnostics": [
                        {
                            "path": "src/service.py",
                            "line": 4,
                            "severity": "error",
                            "message": "normalize_status('OPEN') returns 'closed'.",
                        }
                    ],
                    "failing_tests": ["tests/test_service.py::test_normalize_status_open"],
                    "changed_files": ["src/service.py"],
                },
            ),
        )

    # Snapshot must record both the parse hotspot and the graph build.
    assert not telemetry.missing_fields(data, telemetry.SNAPSHOT_SPANS, kind="spans_ms")
    # Triage must record the ranking span.
    assert not telemetry.missing_fields(data, telemetry.TRIAGE_SPANS, kind="spans_ms")
    # Every recorded span must be a non-negative duration.
    for name, value in data["spans_ms"].items():
        assert value >= 0.0, name
