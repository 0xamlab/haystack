from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

algenta = importlib.import_module("algenta")

AlgentaClient = algenta.AlgentaClient
ProductAgentRunOutput = algenta.ProductAgentRunOutput
ProductDecisionOutput = algenta.ProductDecisionOutput
ProductForecastOutput = algenta.ProductForecastOutput
ProductOptimizeOutput = algenta.ProductOptimizeOutput
ProductRetrieveOutput = algenta.ProductRetrieveOutput
Runtime = algenta.Runtime
RuntimeConfigurationError = algenta.RuntimeConfigurationError


def _decision_payload() -> dict[str, object]:
    return {
        "decision_id": "decision_product_123",
        "action": "proceed",
        "confidence": 0.82,
        "reasoning": "Expected value remains attractive within risk tolerance.",
        "why": ["Positive expected value", "Downside bounded", "Risk acceptable"],
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
        "result": {"summary": "done"},
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
        "optimal_values": {"price": 119.0},
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


class _FakeDecisionEngineClient:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.calls: list[tuple[str, tuple[object, ...], dict[str, object]]] = []

    def _record(self, call_name: str, *args: object, **kwargs: object) -> dict[str, object]:
        self.calls.append((call_name, args, kwargs))
        return {"name": call_name, "args": list(args), "kwargs": kwargs}

    def product_decision(self, request):
        return self._record("product_decision", request)

    def product_agent_run(self, request):
        return self._record("product_agent_run", request)

    def product_optimize(self, request):
        return self._record("product_optimize", request)

    def product_retrieve(self, request):
        return self._record("product_retrieve", request)

    def product_forecast(self, request):
        return self._record("product_forecast", request)


class _FakeRuntimeApiClient:
    def product_decision(self, request):
        assert request["inputs"][0]["name"] == "revenue"
        return _decision_payload()

    def product_agent_run(self, request):
        assert request["task"] == "Summarize blockers"
        return _agent_run_payload()

    def product_optimize(self, request):
        assert request["objective"] == "maximize profit"
        return _optimize_payload()

    def product_retrieve(self, request):
        assert request["query"] == "launch checklist"
        return _retrieve_payload()

    def product_forecast(self, request):
        assert request["metric"] == "monthly_revenue"
        return _forecast_payload()


def test_algenta_client_forwards_product_methods(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_client = _FakeDecisionEngineClient(api_key="de_test", base_url="https://example.test")
    client = AlgentaClient(api_key="de_test", base_url="https://example.test")
    monkeypatch.setattr(client, "_decision_engine_client", fake_client)

    decision = client.product_decision({"inputs": [{"name": "revenue", "value": 120000.0}]})
    agent_run = client.product_agent_run({"task": "Summarize blockers"})
    optimize = client.product_optimize({"objective": "maximize profit", "variables": []})
    retrieve = client.product_retrieve({"query": "launch checklist", "documents": []})
    forecast = client.product_forecast({"metric": "monthly_revenue", "history": [100.0, 120.0, 130.0]})

    assert decision["name"] == "product_decision"
    assert agent_run["name"] == "product_agent_run"
    assert optimize["name"] == "product_optimize"
    assert retrieve["name"] == "product_retrieve"
    assert forecast["name"] == "product_forecast"
    assert fake_client.calls == [
        ("product_decision", ({"inputs": [{"name": "revenue", "value": 120000.0}]},), {}),
        ("product_agent_run", ({"task": "Summarize blockers"},), {}),
        ("product_optimize", ({"objective": "maximize profit", "variables": []},), {}),
        ("product_retrieve", ({"query": "launch checklist", "documents": []},), {}),
        ("product_forecast", ({"metric": "monthly_revenue", "history": [100.0, 120.0, 130.0]},), {}),
    ]


def test_algenta_runtime_exposes_typed_product_methods(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_test_123", base_url="http://localhost:8000")
    monkeypatch.setattr(runtime, "_client", lambda: _FakeRuntimeApiClient())

    decision = runtime.product_decision({"inputs": [{"name": "revenue", "value": 120000.0}]})
    agent_run = runtime.product_agent_run({"task": "Summarize blockers"})
    optimize = runtime.product_optimize({"objective": "maximize profit", "variables": []})
    retrieve = runtime.product_retrieve({"query": "launch checklist", "documents": []})
    forecast = runtime.product_forecast({"metric": "monthly_revenue", "history": [100.0, 120.0, 130.0]})

    assert isinstance(decision, ProductDecisionOutput)
    assert decision.action == "proceed"
    assert isinstance(agent_run, ProductAgentRunOutput)
    assert agent_run.tools_used == ["search", "simulate"]
    assert isinstance(optimize, ProductOptimizeOutput)
    assert optimize.objective_value == 183000.0
    assert isinstance(retrieve, ProductRetrieveOutput)
    assert retrieve.results[0].document_id == "doc_1"
    assert isinstance(forecast, ProductForecastOutput)
    assert forecast.periods[0].trend == "up"


def test_algenta_runtime_product_methods_require_api_transport() -> None:
    runtime = Runtime(mode="local")

    with pytest.raises(RuntimeConfigurationError):
        runtime.product_decision({"inputs": [{"name": "revenue", "value": 120000.0}]})
    with pytest.raises(RuntimeConfigurationError):
        runtime.product_agent_run({"task": "Summarize blockers"})
    with pytest.raises(RuntimeConfigurationError):
        runtime.product_optimize({"objective": "maximize profit", "variables": []})
    with pytest.raises(RuntimeConfigurationError):
        runtime.product_retrieve({"query": "launch checklist", "documents": []})
    with pytest.raises(RuntimeConfigurationError):
        runtime.product_forecast({"metric": "monthly_revenue", "history": [100.0, 120.0, 130.0]})
