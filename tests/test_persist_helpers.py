from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

import apps.api_server.services._persist_helpers as persist_helpers
from apps.api_server.services.storage_service import (
    ResultStorageUnavailableError,
    StoredResultReference,
)


@pytest.mark.asyncio
async def test_persist_result_reference_updates_run_when_storage_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = SimpleNamespace(output_blob_ref=None, result_url=None)
    monkeypatch.setattr(persist_helpers.settings, "result_storage_enabled", True)

    async def _fake_store_result(**kwargs):  # type: ignore[no-untyped-def]
        assert kwargs["result_data"] == {"status": "completed"}
        return StoredResultReference(
            blob_ref="s3://decision-engine-results/org/run.json",
            result_url="https://storage.example/run.json",
            storage_backend="s3",
            size_bytes=128,
        )

    monkeypatch.setattr("apps.api_server.services.storage_service.store_result", _fake_store_result)

    await persist_helpers._persist_result_reference(
        run=run,
        persist_meta={
            "run_id": str(uuid.uuid4()),
            "org_id": str(uuid.uuid4()),
            "envelope_json": {"status": "completed"},
        },
    )

    assert run.output_blob_ref == "s3://decision-engine-results/org/run.json"
    assert run.result_url == "https://storage.example/run.json"


@pytest.mark.asyncio
async def test_persist_result_reference_allows_degraded_storage_when_runtime_fallbacks_allowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = SimpleNamespace(output_blob_ref=None, result_url=None)
    monkeypatch.setattr(persist_helpers.settings, "result_storage_enabled", True)
    monkeypatch.setattr(persist_helpers.settings, "runtime_fallback_mode", "allow")

    async def _fake_store_result(**kwargs):  # type: ignore[no-untyped-def]
        raise ResultStorageUnavailableError("storage unavailable")

    monkeypatch.setattr("apps.api_server.services.storage_service.store_result", _fake_store_result)

    await persist_helpers._persist_result_reference(
        run=run,
        persist_meta={
            "run_id": str(uuid.uuid4()),
            "org_id": str(uuid.uuid4()),
            "envelope_json": {"status": "completed"},
        },
    )

    assert run.output_blob_ref is None
    assert run.result_url is None


@pytest.mark.asyncio
async def test_persist_result_reference_fails_closed_when_runtime_fallbacks_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = SimpleNamespace(output_blob_ref=None, result_url=None)
    monkeypatch.setattr(persist_helpers.settings, "result_storage_enabled", True)
    monkeypatch.setattr(persist_helpers.settings, "runtime_fallback_mode", "deny")

    async def _fake_store_result(**kwargs):  # type: ignore[no-untyped-def]
        raise ResultStorageUnavailableError("storage unavailable")

    monkeypatch.setattr("apps.api_server.services.storage_service.store_result", _fake_store_result)

    with pytest.raises(RuntimeError, match="Result storage backend unavailable"):
        await persist_helpers._persist_result_reference(
            run=run,
            persist_meta={
                "run_id": str(uuid.uuid4()),
                "org_id": str(uuid.uuid4()),
                "envelope_json": {"status": "completed"},
            },
        )
