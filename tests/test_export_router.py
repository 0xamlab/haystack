from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from apps.api_server.routers import export as export_router


@pytest.mark.asyncio
async def test_fetch_result_blob_uses_stored_result_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        result_url="https://storage.example/run.json",
        output_blob_ref="s3://decision-engine-results/org/run.json",
    )

    async def _fake_get_result(result_url: str) -> dict[str, object]:
        assert result_url == "https://storage.example/run.json"
        return {"recommended_action": "proceed"}

    monkeypatch.setattr("apps.api_server.services.storage_service.get_result", _fake_get_result)

    result = await export_router._fetch_result_blob(run)  # type: ignore[arg-type]

    assert result == {"recommended_action": "proceed"}


@pytest.mark.asyncio
async def test_fetch_result_blob_generates_presigned_url_from_blob_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = uuid.uuid4()
    org_id = uuid.uuid4()
    run = SimpleNamespace(
        id=run_id,
        org_id=org_id,
        result_url=None,
        output_blob_ref="s3://decision-engine-results/org/run.json",
    )

    monkeypatch.setattr(
        "apps.api_server.services.storage_service.generate_presigned_download_url",
        lambda given_org_id, given_run_id: (
            "https://storage.example/fresh.json"
            if given_org_id == org_id and given_run_id == run_id
            else None
        ),
    )

    async def _fake_get_result(result_url: str) -> dict[str, object]:
        assert result_url == "https://storage.example/fresh.json"
        return {"recommended_action": "caution"}

    monkeypatch.setattr("apps.api_server.services.storage_service.get_result", _fake_get_result)

    result = await export_router._fetch_result_blob(run)  # type: ignore[arg-type]

    assert result == {"recommended_action": "caution"}
