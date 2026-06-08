from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
if str(PYTHON_SDK) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK))

pytestmark = pytest.mark.anyio

decision_engine = importlib.import_module("decision_engine")

AsyncDecisionEngineClient = decision_engine.AsyncDecisionEngineClient
DecisionEngineClient = decision_engine.DecisionEngineClient
ProductAgentRunResult = decision_engine.ProductAgentRunResult
ProductDecisionResult = decision_engine.ProductDecisionResult
ProductForecastResult = decision_engine.ProductForecastResult
ProductOptimizeResult = decision_engine.ProductOptimizeResult
ProductRetrieveResult = decision_engine.ProductRetrieveResult


def _decision_payload() -> dict[str, object]:
    return {
        "decision_id": "decision_product_123",
        "action": "proceed",
        "confidence": 0.82,
        "reasoning": "Expected value remains attractive within the selected risk tolerance.",
        "why": ["Positive expected value", "Downside remains bounded", "Risk is within tolerance"],
        "expected_outcome": 125000.0,
        "downside_risk": 81000.0,
        "upside_potential": 189000.0,
        "probability_of_loss": 0.14,
        "scenarios_evaluated": 10000,
        "latency_ms": 41.2,
    }


def _agent_run_payload() -> dict[str, object]:
    return {
        "run_id": "agent_product_123",
        "status": "completed",
        "result": "Task finished successfully.",
        "steps": [
            {
                "step": 1,
                "action": "search",
                "tool": "search",
                "result": "Found 3 documents",
                "status": "completed",
            }
        ],
        "tools_used": ["search", "simulate"],
        "latency_ms": 88.4,
    }


def _optimize_payload() -> dict[str, object]:
    return {
        "optimization_id": "opt_123",
        "status": "completed",
        "optimal_values": {"price": 119.0, "discount": 0.08},
        "objective_value": 183000.0,
        "improvement_vs_midpoint": 14.6,
        "constraints_satisfied": True,
        "iterations_run": 1200,
        "latency_ms": 63.0,
    }


def _retrieve_payload() -> dict[str, object]:
    return {
        "retrieval_id": "ret_123",
        "query": "launch checklist",
        "results": [
            {
                "rank": 1,
                "document_id": "doc_1",
                "content": "Launch checklist for product release.",
                "relevance_score": 0.93,
                "snippet": "Launch checklist",
            }
        ],
        "total_searched": 4,
        "latency_ms": 27.5,
    }


def _forecast_payload() -> dict[str, object]:
    return {
        "forecast_id": "forecast_123",
        "metric": "monthly_revenue",
        "baseline": 125000.0,
        "forecast_mean": 149000.0,
        "total_change_pct": 19.2,
        "periods": [
            {
                "period": 1,
                "forecast": 129000.0,
                "lower_bound": 118000.0,
                "upper_bound": 141000.0,
                "trend": "up",
            }
        ],
        "scenarios_evaluated": 5000,
        "latency_ms": 35.8,
    }


def test_sync_client_product_methods_return_typed_models(monkeypatch: pytest.MonkeyPatch) -> None:
    client = DecisionEngineClient(api_key="de_test_sync", base_url="https://example.test")
    calls: list[tuple[str, str, dict[str, Any]]] = []

    def fake_request(method: str, path: str, **kwargs: Any) -> Any:
        calls.append((method, path, kwargs))
        if (method, path) == ("POST", "/v1/decision"):
            return _decision_payload()
        if (method, path) == ("POST", "/v1/agent/run"):
            return _agent_run_payload()
        if (method, path) == ("POST", "/v1/optimize"):
            return _optimize_payload()
        if (method, path) == ("POST", "/v1/retrieve"):
            return _retrieve_payload()
        if (method, path) == ("POST", "/v1/forecast"):
            return _forecast_payload()
        raise AssertionError((method, path, kwargs))

    monkeypatch.setattr(client, "_request", fake_request)

    decision = client.product_decision({"inputs": [{"name": "revenue", "value": 120000.0}]})
    agent_run = client.product_agent_run({"task": "Summarize the launch blockers"})
    optimize = client.product_optimize(
        {"objective": "maximize profit", "variables": [{"name": "price", "min": 10, "max": 200}]}
    )
    retrieve = client.product_retrieve(
        {"query": "launch checklist", "documents": [{"content": "Launch checklist for product release."}]}
    )
    forecast = client.product_forecast({"metric": "monthly_revenue", "history": [100.0, 120.0, 130.0]})

    assert isinstance(decision, ProductDecisionResult)
    assert decision.action == "proceed"
    assert isinstance(agent_run, ProductAgentRunResult)
    assert agent_run.steps[0].tool == "search"
    assert isinstance(optimize, ProductOptimizeResult)
    assert optimize.optimal_values["price"] == 119.0
    assert isinstance(retrieve, ProductRetrieveResult)
    assert retrieve.results[0].document_id == "doc_1"
    assert isinstance(forecast, ProductForecastResult)
    assert forecast.periods[0].trend == "up"
    assert calls == [
        ("POST", "/v1/decision", {"json": {"inputs": [{"name": "revenue", "value": 120000.0}]}}),
        ("POST", "/v1/agent/run", {"json": {"task": "Summarize the launch blockers"}}),
        (
            "POST",
            "/v1/optimize",
            {
                "json": {
                    "objective": "maximize profit",
                    "variables": [{"name": "price", "min": 10, "max": 200}],
                }
            },
        ),
        (
            "POST",
            "/v1/retrieve",
            {
                "json": {
                    "query": "launch checklist",
                    "documents": [{"content": "Launch checklist for product release."}],
                }
            },
        ),
        (
            "POST",
            "/v1/forecast",
            {"json": {"metric": "monthly_revenue", "history": [100.0, 120.0, 130.0]}},
        ),
    ]


async def test_async_client_product_methods_return_typed_models(monkeypatch: pytest.MonkeyPatch) -> None:
    client = AsyncDecisionEngineClient(api_key="de_test_async", base_url="https://example.test")
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def fake_request(method: str, path: str, **kwargs: Any) -> Any:
        calls.append((method, path, kwargs))
        if (method, path) == ("POST", "/v1/decision"):
            return _decision_payload()
        if (method, path) == ("POST", "/v1/agent/run"):
            return _agent_run_payload()
        if (method, path) == ("POST", "/v1/optimize"):
            return _optimize_payload()
        if (method, path) == ("POST", "/v1/retrieve"):
            return _retrieve_payload()
        if (method, path) == ("POST", "/v1/forecast"):
            return _forecast_payload()
        raise AssertionError((method, path, kwargs))

    monkeypatch.setattr(client, "_request", fake_request)

    decision = await client.product_decision({"inputs": [{"name": "revenue", "value": 120000.0}]})
    agent_run = await client.product_agent_run({"task": "Summarize the launch blockers"})
    optimize = await client.product_optimize(
        {"objective": "maximize profit", "variables": [{"name": "price", "min": 10, "max": 200}]}
    )
    retrieve = await client.product_retrieve(
        {"query": "launch checklist", "documents": [{"content": "Launch checklist for product release."}]}
    )
    forecast = await client.product_forecast(
        {"metric": "monthly_revenue", "history": [100.0, 120.0, 130.0]}
    )

    assert isinstance(decision, ProductDecisionResult)
    assert decision.scenarios_evaluated == 10000
    assert isinstance(agent_run, ProductAgentRunResult)
    assert agent_run.tools_used == ["search", "simulate"]
    assert isinstance(optimize, ProductOptimizeResult)
    assert optimize.constraints_satisfied is True
    assert isinstance(retrieve, ProductRetrieveResult)
    assert retrieve.total_searched == 4
    assert isinstance(forecast, ProductForecastResult)
    assert forecast.forecast_mean == 149000.0
    assert calls[0][1] == "/v1/decision"
    assert calls[-1][1] == "/v1/forecast"
