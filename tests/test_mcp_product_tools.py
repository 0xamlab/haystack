from __future__ import annotations

import json

import pytest

from apps.mcp_server.tools import products

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize(
    ("spec", "required_fields"),
    [
        (products.PRODUCT_DECISION_SPEC, {"inputs"}),
        (products.PRODUCT_AGENT_RUN_SPEC, {"task"}),
        (products.PRODUCT_OPTIMIZE_SPEC, {"objective", "variables"}),
        (products.PRODUCT_RETRIEVE_SPEC, {"query"}),
        (products.PRODUCT_FORECAST_SPEC, {"metric", "history"}),
    ],
)
def test_product_specs_expose_required_fields(
    spec: dict[str, object],
    required_fields: set[str],
) -> None:
    assert required_fields.issubset(set(spec["inputSchema"]["required"]))  # type: ignore[index]
    assert spec["inputSchema"]["additionalProperties"] is False  # type: ignore[index]


@pytest.mark.parametrize(
    ("handler", "path", "arguments", "expected"),
    [
        (
            products.product_decision_handler,
            "/v1/decision",
            {"inputs": [{"name": "revenue", "value": 125000.0}]},
            {"decision_id": "decision_product_123", "action": "proceed"},
        ),
        (
            products.product_agent_run_handler,
            "/v1/agent/run",
            {"task": "Summarize launch blockers"},
            {"run_id": "agent_product_123", "status": "completed"},
        ),
        (
            products.product_optimize_handler,
            "/v1/optimize",
            {"objective": "maximize_margin", "variables": [{"name": "price", "min": 95, "max": 140}]},
            {"optimization_id": "opt_123", "status": "completed"},
        ),
        (
            products.product_retrieve_handler,
            "/v1/retrieve",
            {"query": "launch checklist"},
            {"retrieval_id": "ret_123", "results": []},
        ),
        (
            products.product_forecast_handler,
            "/v1/forecast",
            {"metric": "monthly_revenue", "history": [118000.0, 121000.0, 125000.0]},
            {"forecast_id": "forecast_123", "forecast_mean": 149000.0},
        ),
    ],
)
async def test_product_handlers_forward_payloads(
    monkeypatch: pytest.MonkeyPatch,
    handler,
    path: str,
    arguments: dict[str, object],
    expected: dict[str, object],
) -> None:
    async def _fake_api(method: str, requested_path: str, **kwargs):  # type: ignore[no-untyped-def]
        assert method == "POST"
        assert requested_path == path
        assert kwargs == {"json": arguments}
        return expected

    monkeypatch.setattr(products, "api", _fake_api)

    body = json.loads(await handler(arguments))
    assert body == expected
