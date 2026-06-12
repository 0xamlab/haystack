"""B10: the Hugging Face artifact bridge must be fail-closed.

`_hf_hub_download` fetches model/tokenizer artifacts from the HF hub when ``local_files_only`` is
False — a repo_id (often client-supplied) + HF auth-token egress that previously bypassed the
egress guard. These tests pin the fix: a non-cache-only download is denied before any hub fetch in
a fail-closed profile, allowed when the hub host is allowlisted, and cache-only resolution
(``local_files_only=True``, no network) is never guarded so air-gapped offline resolution still
works.
"""
from __future__ import annotations

import sys
from types import ModuleType

import pytest

from apps.api_server.config import get_settings
from apps.api_server.services.egress_guard import EgressPolicyDeniedError
from apps.api_server.services.llm_api_service import _definitions as d


def _fake_hf(download: object) -> ModuleType:
    mod = ModuleType("huggingface_hub")
    mod.hf_hub_download = download  # type: ignore[attr-defined]
    return mod


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_hf_download_denied_before_any_hub_fetch_in_self_hosted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "")
    monkeypatch.delenv("HF_ENDPOINT", raising=False)
    get_settings.cache_clear()

    def _must_not_fetch(**_kwargs: object) -> str:
        raise AssertionError("hf_hub_download ran despite egress being denied")

    monkeypatch.setitem(sys.modules, "huggingface_hub", _fake_hf(_must_not_fetch))

    with pytest.raises(EgressPolicyDeniedError) as exc:
        d._hf_hub_download(
            repo_id="acme/model",
            filename="config.json",
            revision=None,
            cache_root=None,
            local_files_only=False,
            auth_token="hf-secret-token",
        )
    assert exc.value.decision.surface == "artifact_bridge_hf_download"


def test_hf_download_allows_allowlisted_hub_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "huggingface.co")
    monkeypatch.delenv("HF_ENDPOINT", raising=False)
    get_settings.cache_clear()

    calls: list[dict[str, object]] = []

    def _record(**kwargs: object) -> str:
        calls.append(kwargs)
        return "/cache/acme/model/config.json"

    monkeypatch.setitem(sys.modules, "huggingface_hub", _fake_hf(_record))

    path = d._hf_hub_download(
        repo_id="acme/model",
        filename="config.json",
        revision="main",
        cache_root=None,
        local_files_only=False,
        auth_token="hf-secret-token",
    )
    assert path == "/cache/acme/model/config.json"
    assert len(calls) == 1 and calls[0]["repo_id"] == "acme/model"


def test_hf_cache_only_resolution_is_not_guarded(monkeypatch: pytest.MonkeyPatch) -> None:
    # Air-gapped, no allowlist: a guarded fetch would deny. local_files_only=True is cache-only
    # (no network), so it must skip the guard and still resolve from the local cache.
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.setenv("ALGENTA_EGRESS_ALLOWLIST", "")
    get_settings.cache_clear()

    def _local_hit(**_kwargs: object) -> str:
        return "/cache/acme/model/config.json"

    monkeypatch.setitem(sys.modules, "huggingface_hub", _fake_hf(_local_hit))

    path = d._hf_hub_download(
        repo_id="acme/model",
        filename="config.json",
        revision=None,
        cache_root=None,
        local_files_only=True,
        auth_token=None,
    )
    assert path == "/cache/acme/model/config.json"
