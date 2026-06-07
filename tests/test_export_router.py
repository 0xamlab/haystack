from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from apps.api_server.routers import export as export_router


@pytest.mark.anyio
async def test_get_run_export_enforces_workspace_scope() -> None:
    """Regression: GET /v1/runs/{id}/export.{fmt} must scope the run lookup by
    org AND workspace. _get_run was org-only; a platform key scoped to workspace B
    could export workspace A's run. Now it uses workspace_scope_clauses."""
    from apps.api_server.db.session import AsyncSessionLocal
    from apps.api_server.models import Organization, OrgPlan, OrgStatus
    from apps.api_server.models.simulation_run import SimulationMode, SimulationRun

    ws_a = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        org = Organization(
            name="Export Scope Org",
            slug=f"export-scope-{uuid.uuid4().hex[:10]}",
            plan=OrgPlan.PRO,
            status=OrgStatus.ACTIVE,
        )
        session.add(org)
        await session.flush()
        run = SimulationRun(org_id=org.id, workspace_id=ws_a, mode=SimulationMode.EXPERT)
        session.add(run)
        await session.commit()
        org_id = org.id
        run_id = run.id

    ws_b = uuid.uuid4()
    async with AsyncSessionLocal() as session:
        # Sibling workspace, same org → 404 (not found).
        with pytest.raises(HTTPException) as exc:
            await export_router._get_run(
                run_id, {"org_id": org_id, "workspace_id": ws_b}, session  # type: ignore[arg-type]
            )
        assert exc.value.status_code == 404
        # Owning workspace → returns the run.
        same_ws = await export_router._get_run(
            run_id, {"org_id": org_id, "workspace_id": ws_a}, session  # type: ignore[arg-type]
        )
        assert same_ws.id == run_id
        # Org-wide platform call (no X-Workspace-Id) → returns the run.
        org_wide = await export_router._get_run(
            run_id, {"org_id": org_id, "workspace_id": None}, session  # type: ignore[arg-type]
        )
        assert org_wide.id == run_id


@pytest.mark.anyio
async def test_fetch_result_blob_uses_stored_result_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = SimpleNamespace(
        id=uuid.uuid4(),
        org_id=uuid.uuid4(),
        result_url="https://storage.example/run.json",
        output_blob_ref="s3://decision-engine-results/org/run.json",
    )

    async def _fake_get_result(
        result_url: str,
        *,
        org_id: uuid.UUID | None = None,
    ) -> dict[str, object]:
        assert result_url == "https://storage.example/run.json"
        assert org_id == run.org_id
        return {"recommended_action": "proceed"}

    monkeypatch.setattr("apps.api_server.services.storage_service.get_result", _fake_get_result)

    result = await export_router._fetch_result_blob(run)  # type: ignore[arg-type]

    assert result == {"recommended_action": "proceed"}


@pytest.mark.anyio
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

    async def _fake_get_result(
        result_url: str,
        *,
        org_id: uuid.UUID | None = None,
    ) -> dict[str, object]:
        assert result_url == "https://storage.example/fresh.json"
        assert org_id == run.org_id
        return {"recommended_action": "caution"}

    monkeypatch.setattr("apps.api_server.services.storage_service.get_result", _fake_get_result)

    result = await export_router._fetch_result_blob(run)  # type: ignore[arg-type]

    assert result == {"recommended_action": "caution"}


def test_render_pdf_sanitizes_non_latin_text_and_returns_pdf_bytes() -> None:
    summary = {
        "run_id": "abc123",
        "status": "completed",
        "rationale": "Revenue — completed 📈",
        "completed_at": None,
    }
    full = {
        "summary": {"mean": 123.456},
        "sensitivity_analysis": {
            "tornado_chart": [
                {
                    "variable": "order_status",
                    "range": 1.2,
                    "low_swing": -0.5,
                    "high_swing": 0.7,
                }
            ]
        },
    }

    content = export_router._render_pdf(summary, full, "abc123")

    assert isinstance(content, bytes)
    assert content.startswith(b"%PDF")
    assert len(content) > 100
