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
from apps.api_server.services import (
    repository_intelligence_verified_agentic as verified_agentic,
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
            "session_id": "session_456",
            "telemetry": {
                "tokens_in_uncached": 900,
                "tokens_out": 120,
                "cache_read_tokens": 300,
                "cache_write_tokens": 50,
                "provider": "anthropic",
                "model": "claude-sonnet-4-6",
            },
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
    assert result["session_id"] == "session_456"
    assert result["runtime_kind"] == "cline"
    assert result["runtime_provider"] == "anthropic"
    assert result["runtime_model"] == "claude-sonnet-4-6"
    assert result["planner_usage"] == {
        "input_tokens": 1250.0,
        "output_tokens": 120.0,
        "cache_read_tokens": 300.0,
        "cache_write_tokens": 50.0,
        "cost_usd": None,
    }
    assert result["transcript_ref"] == "minio://transcripts/run_123"
    assert result["confidence"] == 0.8
    # Python-authoritative diff, recomputed from before/after tree state.
    assert "a/foo.py" in result["patch_diff"]
    assert '-    return "bye"' in result["patch_diff"]
    assert '+    return "hi"' in result["patch_diff"]


def test_verified_agentic_sends_tool_profile_and_context_bundle(monkeypatch, tmp_path):
    """AR-OPT-4: the seam carries the tool profile in task_spec and injects the
    full line-context bundle (numbered source of suspect symbols) for the agent."""
    _patch_materialized(monkeypatch, tmp_path)
    monkeypatch.delenv("ALGENTA_REPOSITORY_AGENT_TOOL_PROFILE", raising=False)
    captured: dict = {}

    def fake_run_agent(*, working_dir, task_spec, injected_context, limits):
        captured["task_spec"] = task_spec
        captured["injected_context"] = injected_context
        (Path(working_dir) / "foo.py").write_text(_FIXED, encoding="utf-8")
        return {"status": "completed", "agent_run_id": "run_ctx"}

    snapshot = {
        "snapshot_id": "snap_test",
        "resolved_revision": "deadbeef",
        "files": [
            {
                "file_path": "foo.py",
                "language": "python",
                "symbols": [
                    {"symbol_id": "g", "symbol_name": "greet", "symbol_kind": "function",
                     "start_line": 1, "end_line": 2, "parent_symbol_id": None}
                ],
                "dependencies": [],
            }
        ],
    }

    asyncio.run(
        planner_generation._generate_verified_agentic_repository_patch_plan(
            model_id=_VERIFIED_AGENTIC_ID,
            snapshot_manifest=snapshot,
            triage_manifest=_TRIAGE_MANIFEST,
            run_agent=fake_run_agent,
        )
    )

    # Default controlled profile reaches the agent via task_spec.
    assert captured["task_spec"]["tool_profile"] == "no_exploration_local_validation"
    # The line-context bundle is injected with the suspect symbol's numbered source.
    bundle = captured["injected_context"]["context_bundle"]
    assert any(
        entry["symbol_name"] == "greet" and "return" in entry["numbered_source"]
        for entry in bundle
    )


def test_agent_tool_profile_env_override(monkeypatch):
    monkeypatch.delenv("ALGENTA_REPOSITORY_AGENT_TOOL_PROFILE", raising=False)
    assert planner_generation._agent_tool_profile() == "no_exploration_local_validation"
    monkeypatch.setenv("ALGENTA_REPOSITORY_AGENT_TOOL_PROFILE", "no_exploration_no_shell")
    assert planner_generation._agent_tool_profile() == "no_exploration_no_shell"
    monkeypatch.setenv("ALGENTA_REPOSITORY_AGENT_TOOL_PROFILE", "bogus")
    assert planner_generation._agent_tool_profile() == "no_exploration_local_validation"


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

    # _DEFAULT_RUN_AGENT now lives in the extracted verified_agentic module; patch it there.
    monkeypatch.setattr(verified_agentic, "_DEFAULT_RUN_AGENT", fake_run_agent)

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


def test_dedupe_bundled_evidence_strips_only_bundle_covered_symbols():
    """AR-OPT token de-dup: drop snippets the context bundle already carries in
    full (matched by file+symbol), keep complementary evidence intact, and never
    mutate the inputs."""
    bundle = [
        {"file_path": "src/a.py", "symbol_name": "do_thing", "numbered_source": "1\tx"},
    ]
    evidence = [
        # same (file, symbol) as the bundle → snippet is redundant → stripped
        {"file_path": "src/a.py", "symbol_name": "do_thing", "snippet": "def do_thing(): ...", "rank": 1},
        # same file, DIFFERENT symbol → complementary → kept
        {"file_path": "src/a.py", "symbol_name": "other", "snippet": "def other(): ...", "rank": 2},
        # different file → kept
        {"file_path": "src/b.py", "symbol_name": "do_thing", "snippet": "B code", "rank": 3},
        # file-level (no symbol) → kept
        {"file_path": "src/a.py", "symbol_name": None, "snippet": "module top", "rank": 4},
    ]
    original = [dict(item) for item in evidence]

    result = verified_agentic._dedupe_bundled_evidence(evidence, bundle)

    assert result[0]["snippet"] == "[full source in context_bundle]"
    assert result[1]["snippet"] == "def other(): ..."
    assert result[2]["snippet"] == "B code"
    assert result[3]["snippet"] == "module top"
    # ranking/metadata preserved on the stripped item
    assert result[0]["rank"] == 1
    # inputs were not mutated in place
    assert evidence == original


def test_dedupe_bundled_evidence_noop_without_bundle():
    evidence = [{"file_path": "src/a.py", "symbol_name": "f", "snippet": "code"}]
    assert verified_agentic._dedupe_bundled_evidence(evidence, []) is evidence
