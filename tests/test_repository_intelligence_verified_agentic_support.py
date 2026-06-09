"""Contract tests for the verified_agentic planner tier (forked-Cline agent-core).

These are hermetic: the agent runner is injected/monkeypatched (no Node, no live
model) and ``materialized_snapshot`` is faked to a temp dir. They lock the seam's
contract — the returned planner dict shape, the Python-authoritative diff, the
internal-only ``planner_engine`` attribution, and the terminal/error branches.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

import pytest

from apps.api_server.schemas.response import RepositoryAnalysis
from apps.api_server.services import (
    repository_intelligence_decision_plan_workflow as dpw,
)
from apps.api_server.services import (
    repository_intelligence_planner_generation as planner_generation,
)
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
)

_DETERMINISTIC_ID = "repository.deterministic_local_v1"
_VERIFIED_AGENTIC_ID = "repository.verified_agentic_v1"

_SNAPSHOT_MANIFEST = {
    "snapshot_id": "snap_test",
    "resolved_revision": "deadbeef",
    "files": [{"file_path": "foo.py", "language": "python", "symbols": []}],
}
_TRIAGE_MANIFEST = {
    "snapshot_id": "snap_test",
    "evidence_items": [],
    "suspect_files": ["foo.py"],
    "suspect_symbols": ["greet"],
    "signals": {"issue_text": "greet returns the wrong string"},
    "raw_repo_token_estimate": 4000,
    "evidence_bundle_token_count": 500,
    "reduction_ratio": 8.0,
}

_ORIGINAL = 'def greet():\n    return "bye"\n'
_FIXED = 'def greet():\n    return "hi"\n'


def _patch_materialized(monkeypatch, tmp_path: Path) -> None:
    """Fake ``materialized_snapshot`` to a temp checkout seeded with foo.py."""

    @contextlib.contextmanager
    def _fake(snapshot_manifest):  # noqa: ARG001 — signature parity
        (tmp_path / "foo.py").write_text(_ORIGINAL, encoding="utf-8")
        yield tmp_path

    monkeypatch.setattr(
        planner_generation.repository_storage, "materialized_snapshot", _fake
    )


def test_verified_agentic_returns_planner_dict(monkeypatch, tmp_path):
    _patch_materialized(monkeypatch, tmp_path)

    def fake_run_agent(*, working_dir, task_spec, injected_context, limits):
        # The injected repo-intelligence reaches the agent...
        assert injected_context["suspect_files"] == ["foo.py"]
        assert task_spec["snapshot_id"] == "snap_test"
        # ...and the agent edits the file in the checkout.
        (Path(working_dir) / "foo.py").write_text(_FIXED, encoding="utf-8")
        return {
            "status": "completed",
            "agent_run_id": "run_123",
            "transcript_ref": "minio://transcripts/run_123",
            "root_cause": "greet returned 'bye' instead of 'hi'",
            "recommended_action": "Return 'hi' from greet",
            "candidate_fixes": ["Fix greet return literal"],
            "confidence": 0.8,
        }

    result = asyncio.run(
        planner_generation._generate_verified_agentic_repository_patch_plan(
            model_id=_VERIFIED_AGENTIC_ID,
            snapshot_manifest=_SNAPSHOT_MANIFEST,
            triage_manifest=_TRIAGE_MANIFEST,
            run_agent=fake_run_agent,
        )
    )

    assert result["planner_execution_mode"] == "verified_agentic"
    assert result["planner_engine"] == "cline_fork"  # internal attribution
    assert result["agent_run_id"] == "run_123"
    assert result["transcript_ref"] == "minio://transcripts/run_123"
    assert result["confidence"] == 0.8
    # Python-authoritative diff, recomputed from before/after tree state.
    assert "a/foo.py" in result["patch_diff"]
    assert '-    return "bye"' in result["patch_diff"]
    assert '+    return "hi"' in result["patch_diff"]


def test_verified_agentic_ignores_agent_supplied_diff(monkeypatch, tmp_path):
    """The agent's own working_tree_diff must be ignored; Python recomputes it."""
    _patch_materialized(monkeypatch, tmp_path)

    def lying_run_agent(*, working_dir, task_spec, injected_context, limits):
        (Path(working_dir) / "foo.py").write_text(_FIXED, encoding="utf-8")
        return {
            "status": "completed",
            "agent_run_id": "run_lie",
            # A bogus diff the agent claims — must NOT appear in the result.
            "working_tree_diff": "--- a/evil.py\n+++ b/evil.py\n@@ -1 +1 @@\n-x\n+y\n",
        }

    result = asyncio.run(
        planner_generation._generate_verified_agentic_repository_patch_plan(
            model_id=_VERIFIED_AGENTIC_ID,
            snapshot_manifest=_SNAPSHOT_MANIFEST,
            triage_manifest=_TRIAGE_MANIFEST,
            run_agent=lying_run_agent,
        )
    )
    assert "evil.py" not in result["patch_diff"]
    assert "foo.py" in result["patch_diff"]


def test_verified_agentic_no_change_raises(monkeypatch, tmp_path):
    _patch_materialized(monkeypatch, tmp_path)

    def noop_run_agent(*, working_dir, task_spec, injected_context, limits):
        return {"status": "completed", "agent_run_id": "run_empty"}

    with pytest.raises(RepositoryIntelligenceError) as exc:
        asyncio.run(
            planner_generation._generate_verified_agentic_repository_patch_plan(
                model_id=_VERIFIED_AGENTIC_ID,
                snapshot_manifest=_SNAPSHOT_MANIFEST,
                triage_manifest=_TRIAGE_MANIFEST,
                run_agent=noop_run_agent,
            )
        )
    assert exc.value.code == "repository_agent_no_change"
    assert exc.value.status_code == 422


def test_verified_agentic_failed_status_raises(monkeypatch, tmp_path):
    _patch_materialized(monkeypatch, tmp_path)

    def failing_run_agent(*, working_dir, task_spec, injected_context, limits):
        # Even if it scribbled changes, a failed/aborted status must not ship.
        (Path(working_dir) / "foo.py").write_text(_FIXED, encoding="utf-8")
        return {"status": "aborted", "agent_run_id": "run_abort"}

    with pytest.raises(RepositoryIntelligenceError) as exc:
        asyncio.run(
            planner_generation._generate_verified_agentic_repository_patch_plan(
                model_id=_VERIFIED_AGENTIC_ID,
                snapshot_manifest=_SNAPSHOT_MANIFEST,
                triage_manifest=_TRIAGE_MANIFEST,
                run_agent=failing_run_agent,
            )
        )
    assert exc.value.code == "repository_agent_aborted"


def test_verified_agentic_default_runner_unavailable(monkeypatch, tmp_path):
    _patch_materialized(monkeypatch, tmp_path)
    with pytest.raises(RepositoryIntelligenceError) as exc:
        asyncio.run(
            planner_generation._generate_verified_agentic_repository_patch_plan(
                model_id=_VERIFIED_AGENTIC_ID,
                snapshot_manifest=_SNAPSHOT_MANIFEST,
                triage_manifest=_TRIAGE_MANIFEST,
            )
        )
    assert exc.value.code == "repository_agent_core_unavailable"
    assert exc.value.status_code == 503


def test_resolve_repository_model_accepts_verified_agentic_sentinel():
    resolved = planner_generation._resolve_repository_model(
        _VERIFIED_AGENTIC_ID,
        deterministic_local_model_id=_DETERMINISTIC_ID,
        verified_agentic_model_id=_VERIFIED_AGENTIC_ID,
    )
    assert resolved == _VERIFIED_AGENTIC_ID


def test_generate_patch_plan_routes_to_verified_agentic(monkeypatch, tmp_path):
    """The dispatcher routes the sentinel model id to the agentic tier."""
    _patch_materialized(monkeypatch, tmp_path)

    def fake_run_agent(*, working_dir, task_spec, injected_context, limits):
        (Path(working_dir) / "foo.py").write_text(_FIXED, encoding="utf-8")
        return {"status": "completed", "agent_run_id": "run_route"}

    monkeypatch.setattr(planner_generation, "_DEFAULT_RUN_AGENT", fake_run_agent)

    result = asyncio.run(
        planner_generation._generate_repository_patch_plan(
            model_id=_VERIFIED_AGENTIC_ID,
            snapshot_manifest=_SNAPSHOT_MANIFEST,
            triage_manifest=_TRIAGE_MANIFEST,
            deterministic_local_model_id=_DETERMINISTIC_ID,
            verified_agentic_model_id=_VERIFIED_AGENTIC_ID,
        )
    )
    assert result["planner_execution_mode"] == "verified_agentic"
    assert result["agent_run_id"] == "run_route"


# ── provenance contract (#3) ────────────────────────────────────────────────


def test_decision_plan_integrity_binds_agent_run_id():
    """For agentic runs result_hash fingerprints THIS run (binds agent_run_id);
    the input-addressed request_hash is unchanged."""
    no_agent = dpw._decision_plan_integrity("s", "e", "diff", {"x": 1})
    run_a = dpw._decision_plan_integrity("s", "e", "diff", {"x": 1}, agent_run_id="run_a")
    run_b = dpw._decision_plan_integrity("s", "e", "diff", {"x": 1}, agent_run_id="run_b")

    assert no_agent["request_hash"] == run_a["request_hash"] == run_b["request_hash"]
    # Non-agentic semantics preserved exactly (no agent_run_id => original hash).
    assert no_agent["result_hash"] == dpw._decision_plan_integrity("s", "e", "diff", {"x": 1})[
        "result_hash"
    ]
    # Agentic result_hash differs from non-agentic and between distinct runs.
    assert run_a["result_hash"] != no_agent["result_hash"]
    assert run_a["result_hash"] != run_b["result_hash"]


def test_repository_analysis_schema_excludes_internal_engine_fields():
    """Red line #4: Cline attribution must never be a customer-visible field."""
    fields = set(RepositoryAnalysis.model_fields)
    for forbidden in ("planner_engine", "transcript_ref", "agent_run_id", "vendored_engine_commit"):
        assert forbidden not in fields, f"{forbidden} must stay in the internal audit record"
    # The public tier name is allowed to surface.
    assert "planner_execution_mode" in fields


def test_decision_plan_generation_lock_acquires_and_releases(tmp_path):
    lock_dir = tmp_path / "locks"
    with dpw._decision_plan_generation_lock(lock_dir, "key123"):
        assert (lock_dir / "key123.lock").exists()
    # Re-acquire after release — no deadlock, lock is reusable.
    with dpw._decision_plan_generation_lock(lock_dir, "key123"):
        pass
