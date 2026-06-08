from __future__ import annotations

import uuid
from types import SimpleNamespace

from apps.api_server.main import app
from apps.api_server.middleware.auth import get_current_org, get_redis
from apps.api_server.routers import decisions as decisions_router
from apps.api_server.schemas.response import (
    DecisionEnvelope,
    MetricsSummary,
    PercentileSummary,
    RunMetadata,
)
from tests._asgi_client import SyncASGIClient

PROTECTED_OPENAPI_SECURITY = [{"BearerAuth": []}, {"LegacyApiKey": []}]


async def _fake_auth() -> dict[str, str]:
    return {
        "org_id": "org_decision_plan",
        "key_id": "key_decision_plan",
        "plan": "enterprise",
        "role": "owner",
        "email": "owner@algenta.test",
    }


async def _noop_rate_limit(*args: object, **kwargs: object) -> None:
    del args, kwargs


async def _noop_quota(*args: object, **kwargs: object) -> None:
    del args, kwargs


def _decision_envelope() -> DecisionEnvelope:
    return DecisionEnvelope(
        run_id=uuid.uuid4(),
        engine_version="2026.05.0",
        recommended_action="expand_capacity",
        confidence=0.82,
        rationale="Expected value stays positive while downside risk remains bounded.",
        metrics=MetricsSummary(
            expected_value=125000.0,
            median=120000.0,
            std_deviation=18000.0,
            variance=324000000.0,
            probability_of_loss=0.12,
            var_95=-18000.0,
            cvar_95=-25000.0,
        ),
        percentiles=PercentileSummary(
            p5=-18000.0,
            p25=90000.0,
            p50=120000.0,
            p75=138000.0,
            p95=160000.0,
        ),
        scenarios_run=1000,
        execution_ms=13,
        metadata=RunMetadata(
            mode="auto",
            seed=42,
            billing_units=1,
            engine_version="2026.05.0",
        ),
    )


def test_decision_plan_route_requires_authentication() -> None:
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/decisions/plan",
                json={
                    "mode": "auto",
                    "scenario": {
                        "variables": {"revenue": {"low": 10, "high": 20}},
                        "objective": "maximize_revenue",
                    },
                    "runs": 100,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_decision_plan_route_returns_structured_plan(monkeypatch) -> None:
    envelope = _decision_envelope()

    async def _fake_run_simulation_fast(*, request: object, org_id: object, api_key_id: object):
        assert org_id == "org_decision_plan"
        assert api_key_id == "key_decision_plan"
        assert getattr(request, "mode", None) == "auto"
        return envelope, {"execution_ms": 13}

    def _fake_calibrate(
        confidence: float,
        org_id: str,
        *,
        workspace_id: str | None = None,
    ) -> tuple[float, SimpleNamespace]:
        assert confidence == envelope.confidence
        assert org_id == "org_decision_plan"
        return 0.77, SimpleNamespace(
            is_reliable=True,
            summary=lambda: "12 outcomes | bias=-3.0% | hit_rate=83%",
        )

    monkeypatch.setattr(decisions_router, "check_rate_limit", _noop_rate_limit)
    monkeypatch.setattr(decisions_router, "check_quota_redis", _noop_quota)
    monkeypatch.setattr(decisions_router, "run_simulation_fast", _fake_run_simulation_fast)
    from apps.api_server.services import calibration_service

    monkeypatch.setattr(calibration_service, "calibrate_confidence", _fake_calibrate)
    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = lambda: object()
    try:
        with SyncASGIClient(app) as client:
            response = client.post(
                "/v1/decisions/plan",
                json={
                    "mode": "auto",
                    "scenario": {
                        "variables": {"revenue": {"low": 10, "high": 20}},
                        "objective": "maximize_revenue",
                    },
                    "runs": 100,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "recommended_action": "expand_capacity",
        "confidence": 0.77,
        "expected_value": 125000.0,
        "risk": {
            "p5": -18000.0,
            "p95": 160000.0,
            "probability_of_loss": 0.12,
            "var_95": -18000.0,
        },
        "options": [
            {
                "name": "expand_capacity",
                "rank": 1,
                "expected_value": 125000.0,
                "risk": {
                    "p5": -18000.0,
                    "p95": 160000.0,
                    "probability_of_loss": 0.12,
                    "var_95": -18000.0,
                },
                "score": 0.82,
            }
        ],
        "rationale": "Expected value stays positive while downside risk remains bounded.",
        "integrity": None,
        "calibration": "12 outcomes | bias=-3.0% | hit_rate=83%",
        "repository_analysis": None,
    }


def test_openapi_declares_decision_plan_route_with_protected_security() -> None:
    with SyncASGIClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["paths"]["/v1/decisions/plan"]["post"]["security"] == PROTECTED_OPENAPI_SECURITY
