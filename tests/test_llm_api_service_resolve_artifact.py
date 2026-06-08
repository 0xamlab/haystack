"""Tests for test_llm_api_service: resolve_artifact.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-2/tests/test_llm_api_service.py during modularization.
"""
from __future__ import annotations

from tests._test_llm_api_service_helpers import *  # noqa: F401,F403


def test_resolve_artifact_bridge_returns_not_cached_for_local_only_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class LocalEntryNotFoundError(Exception):
        pass

    monkeypatch.setattr(
        llm_api_service,
        "_detect_bridge_backends",
        lambda specs: ("safetensors", "huggingface_hub")
        if specs == llm_api_service._ARTIFACT_BRIDGE_SPECS
        else (),
    )
    monkeypatch.setenv("HUGGINGFACE_HUB_CACHE", "/tmp/algenta-hf-cache")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setattr(
        llm_api_service,
        "_hf_hub_download",
        lambda **kwargs: (_ for _ in ()).throw(LocalEntryNotFoundError(kwargs["filename"])),
    )

    resolved = llm_api_service.resolve_artifact_bridge(
        repo_id="org/model",
        filename="weights.safetensors",
        revision="main",
        local_files_only=True,
    )

    assert resolved.status == "not_cached"
    assert resolved.backend == "huggingface_hub"
    assert resolved.artifact_backend == "safetensors"
    assert resolved.cache_root == "/tmp/algenta-hf-cache"
    assert resolved.auth_env_var_used is None
    assert resolved.resolved_path is None


def test_resolve_artifact_bridge_passes_auth_and_returns_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        llm_api_service,
        "_detect_bridge_backends",
        lambda specs: ("safetensors", "huggingface_hub")
        if specs == llm_api_service._ARTIFACT_BRIDGE_SPECS
        else (),
    )
    monkeypatch.setenv("HF_TOKEN", "hf_test")

    def _fake_download(**kwargs: object) -> str:
        assert kwargs == {
            "repo_id": "org/model",
            "filename": "tokenizer.json",
            "revision": "main",
            "cache_root": str(Path.home() / ".cache" / "huggingface" / "hub"),
            "local_files_only": False,
            "auth_token": "hf_test",
        }
        return "/tmp/algenta-hf-cache/models--org--model/tokenizer.json"

    monkeypatch.setattr(llm_api_service, "_hf_hub_download", _fake_download)

    resolved = llm_api_service.resolve_artifact_bridge(
        repo_id="org/model",
        filename="tokenizer.json",
        revision="main",
        local_files_only=False,
    )

    assert resolved.status == "resolved"
    assert resolved.auth_configured is True
    assert resolved.auth_env_var_used == "HF_TOKEN"
    assert resolved.resolved_path == "/tmp/algenta-hf-cache/models--org--model/tokenizer.json"


def test_resolve_artifact_bridge_fails_closed_without_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_api_service, "_detect_bridge_backends", lambda specs: ())

    with pytest.raises(LLMAPIError, match="artifact bridge backend is not available"):
        llm_api_service.resolve_artifact_bridge(
            repo_id="org/model",
            filename="weights.safetensors",
        )


