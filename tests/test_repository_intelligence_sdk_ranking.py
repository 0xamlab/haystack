"""Embed-the-Codna-SDK ranking lane: RRF fusion + the real local Mojo fuzzy
kernel (text.fuzzy.jaro_winkler) with a pure-Python fallback when the runtime is
unavailable. One test exercises the REAL Mojo engine when dev mode is enabled.
"""
from __future__ import annotations

import json
import os

import pytest

from apps.api_server.services import repository_intelligence_sdk_ranking as sdk_ranking


def _dev_runtime_available() -> bool:
    if os.environ.get("ALGENTA_RUNTIME_DEV_MODE", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return False
    try:
        from apps.runtime.mojo_library_runner import library_runtime_available

        return bool(library_runtime_available())
    except Exception:  # noqa: BLE001
        return False


def test_reciprocal_rank_fusion_orders_by_combined_rank() -> None:
    fused = sdk_ranking.reciprocal_rank_fusion([["a", "b", "c"], ["b", "c", "a"]])
    order = sorted(fused, key=lambda key: -fused[key])
    assert order[0] == "b"
    assert set(order) == {"a", "b", "c"}


def test_scores_none_when_flag_disabled(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_REPOSITORIES_SDK_RANKING", raising=False)
    assert (
        sdk_ranking.mojo_repo_rank_scores(query_terms=["x"], candidates=[{"path": "a.py"}]) is None
    )


def test_scores_none_when_runtime_unavailable(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_REPOSITORIES_SDK_RANKING", "true")
    monkeypatch.setattr(sdk_ranking, "_runtime", lambda: None)
    assert (
        sdk_ranking.mojo_repo_rank_scores(query_terms=["x"], candidates=[{"path": "a.py"}]) is None
    )


def test_batched_repo_ranker_dispatch(monkeypatch) -> None:
    """Preferred path: one batched dispatch to vector_kernels.repo_ranker."""
    monkeypatch.setenv("ALGENTA_REPOSITORIES_SDK_RANKING", "true")
    captured: dict = {}

    class _FakeRuntime:
        def execute(self, module, function, args):
            captured.update(module=module, function=function, payload=json.loads(args))
            return {
                "success": True,
                "result": json.dumps(
                    {"matches": [{"path": "src/svc.py", "score": 0.81}, {"path": "x.py", "score": 0.1}]}
                ),
            }

    monkeypatch.setattr(sdk_ranking, "_runtime", lambda: _FakeRuntime())
    scores = sdk_ranking.mojo_repo_rank_scores(
        query_terms=["normalize", "status"],
        candidates=[{"path": "src/svc.py", "text": "src svc normalize status"}, {"path": "x.py"}],
    )
    assert scores == {"src/svc.py": 0.81, "x.py": 0.1}
    assert captured["module"] == "vector_kernels.repo_ranker"
    assert captured["function"] == "run_repo_rank"
    assert captured["payload"]["query_terms"] == ["normalize", "status"]


def test_falls_back_to_fuzzy_when_repo_ranker_absent(monkeypatch) -> None:
    """When repo_ranker isn't dispatchable, the per-candidate text.fuzzy lane is used."""
    monkeypatch.setenv("ALGENTA_REPOSITORIES_SDK_RANKING", "true")

    class _FakeRuntime:
        def execute(self, module, function, args):
            if module == "vector_kernels.repo_ranker":
                return {"success": False, "error": "module_not_registered"}
            term, stem = args
            sim = 0.95 if (term == "authhandler" and stem == "auth_handler") else 0.2
            return {"success": True, "result": sim}

    monkeypatch.setattr(sdk_ranking, "_runtime", lambda: _FakeRuntime())
    scores = sdk_ranking.mojo_repo_rank_scores(
        query_terms=["authHandler"],
        candidates=[{"path": "src/auth_handler.py"}, {"path": "src/other.py"}],
    )
    assert scores == {"src/auth_handler.py": 0.95}


def test_scores_none_on_dispatch_failure(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_REPOSITORIES_SDK_RANKING", "true")

    class _FailRuntime:
        def execute(self, *args, **kwargs):
            return {"success": False, "error": "blocked"}

    monkeypatch.setattr(sdk_ranking, "_runtime", lambda: _FailRuntime())
    # valid term + stem so it reaches dispatch; every dispatch fails -> None (fallback)
    assert (
        sdk_ranking.mojo_repo_rank_scores(query_terms=["xyz"], candidates=[{"path": "abc.py"}])
        is None
    )


def test_flag_default_off(monkeypatch) -> None:
    monkeypatch.delenv("ALGENTA_REPOSITORIES_SDK_RANKING", raising=False)
    assert sdk_ranking.sdk_ranking_enabled() is False
    monkeypatch.setenv("ALGENTA_REPOSITORIES_SDK_RANKING", "true")
    assert sdk_ranking.sdk_ranking_enabled() is True


def test_load_runtime_env_reads_runtime_dir_dotenv(tmp_path, monkeypatch) -> None:
    """The runtime credential file ($ALGENTA_RUNTIME_DIR/.env) is loaded into the
    environment so the local engine is authenticated instead of falling back."""
    (tmp_path / ".env").write_text("# comment\n_ALGENTA_TEST_PROBE=loaded\nALSO=two\n")
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(sdk_ranking, "_runtime_env_loaded", False)
    monkeypatch.delenv("_ALGENTA_TEST_PROBE", raising=False)
    monkeypatch.delenv("ALSO", raising=False)
    try:
        sdk_ranking._load_runtime_env()
        assert os.environ.get("_ALGENTA_TEST_PROBE") == "loaded"
        assert os.environ.get("ALSO") == "two"
    finally:  # _load_runtime_env mutates os.environ directly (not via monkeypatch)
        os.environ.pop("_ALGENTA_TEST_PROBE", None)
        os.environ.pop("ALSO", None)


def test_load_runtime_env_does_not_override_explicit(tmp_path, monkeypatch) -> None:
    (tmp_path / ".env").write_text("_ALGENTA_TEST_PROBE=fromfile\n")
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("_ALGENTA_TEST_PROBE", "explicit")  # already set -> file must not win
    monkeypatch.setattr(sdk_ranking, "_runtime_env_loaded", False)
    sdk_ranking._load_runtime_env()
    assert os.environ["_ALGENTA_TEST_PROBE"] == "explicit"


def test_default_runtime_mode_is_local_only() -> None:
    # Repository intelligence is a local boundary: never cloud/auto, only daemon or direct.
    assert sdk_ranking._default_runtime_mode() in {"local", "direct"}


def test_triage_cache_key_is_ranking_mode_aware() -> None:
    """Heuristic and SDK-fused triage must not share a cache key, else toggling the
    SDK ranking flag serves a stale ordering from the other mode."""
    from apps.api_server.services import repository_intelligence_graph_workflow as gw

    common = dict(
        snapshot_id="snap-1",
        signals={"issue_text": "x"},
        max_evidence_items=10,
        max_snippet_lines=40,
        token_budget=6000,
        engine_revision="rev",
    )
    heuristic = gw._triage_lookup_key(ranking_mode="heuristic", **common)
    sdk = gw._triage_lookup_key(ranking_mode="sdk_rrf", **common)
    assert heuristic != sdk
    # Same mode + same inputs is stable (cache still works within a mode).
    assert heuristic == gw._triage_lookup_key(ranking_mode="heuristic", **common)


@pytest.mark.skipif(
    not _dev_runtime_available(),
    reason="Codna local Mojo runtime not enabled (set ALGENTA_RUNTIME_DEV_MODE=1)",
)
def test_real_mojo_fuzzy_similarity_camelcase_recall() -> None:
    """REAL dispatch into the local Mojo engine — the camelCase↔snake_case recall win."""
    from apps.runtime.sdk import Runtime

    runtime = Runtime(mode="direct")
    sim = sdk_ranking.mojo_fuzzy_similarity(runtime, "authHandler", "auth_handler")
    assert sim is not None
    assert sim > 0.9  # exact-substring would have missed this entirely
    # an unrelated stem scores low
    low = sdk_ranking.mojo_fuzzy_similarity(runtime, "authHandler", "zzzzzzzz")
    assert low is not None and low < 0.5
