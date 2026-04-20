from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from apps.api_server.routers import decisions as decisions_router


def _decision_response_dict() -> dict:
    now = "2026-04-18T00:00:00Z"
    org_id = uuid.uuid4()
    decision_id = uuid.uuid4()
    return {
        "id": decision_id,
        "org_id": org_id,
        "run_id": None,
        "context": "ctx",
        "chosen_action": "proceed",
        "options_considered": ["proceed", "pause"],
        "expected_value": 100.0,
        "confidence": 0.9,
        "rationale": "good",
        "risk_p5": 10.0,
        "risk_p95": 200.0,
        "risk_pol": 0.1,
        "request_hash": None,
        "result_hash": None,
        "actual_outcome": None,
        "outcome_delta": None,
        "outcome_notes": None,
        "outcome_recorded_at": None,
        "executed_at": None,
        "execution_status": None,
        "execution_webhook_url": None,
        "execution_response_code": None,
        "created_at": now,
        "updated_at": now,
    }


@pytest.mark.asyncio
async def test_list_decisions_returns_limit_and_pages(monkeypatch) -> None:
    row_result = MagicMock()
    row_result.scalars.return_value.all.return_value = [SimpleNamespace()]
    count_result = MagicMock()
    count_result.scalar_one.return_value = 45
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[row_result, count_result])

    monkeypatch.setattr(
        decisions_router.DecisionLogResponse,
        "from_model",
        classmethod(lambda cls, row: _decision_response_dict()),
    )

    response = await decisions_router.list_decisions(
        auth={"org_id": uuid.uuid4()},
        db=db,
        page=2,
        limit=25,
        page_size=None,
        with_outcome_only=False,
    )

    assert response.page == 2
    assert response.limit == 25
    assert response.page_size == 25
    assert response.pages == 2
    assert response.total == 45


@pytest.mark.asyncio
async def test_list_decisions_limit_overrides_legacy_page_size(monkeypatch) -> None:
    row_result = MagicMock()
    row_result.scalars.return_value.all.return_value = []
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0
    db = AsyncMock()
    db.execute = AsyncMock(side_effect=[row_result, count_result])

    monkeypatch.setattr(
        decisions_router.DecisionLogResponse,
        "from_model",
        classmethod(lambda cls, row: _decision_response_dict()),
    )

    response = await decisions_router.list_decisions(
        auth={"org_id": uuid.uuid4()},
        db=db,
        page=1,
        limit=50,
        page_size=10,
        with_outcome_only=False,
    )

    assert response.limit == 50
    assert response.page_size == 50
    assert response.pages == 1
