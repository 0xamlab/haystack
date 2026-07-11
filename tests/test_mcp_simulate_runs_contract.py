"""MCP simulate must translate MCP-facing n_simulations to API-facing runs."""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path
from typing import Any

from apps.mcp_server.tools import simulate

ROOT = Path(__file__).resolve().parents[1]


def test_embedded_mcp_simulate_maps_n_simulations_to_runs(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_api(method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = json
        return {
            "recommended_action": "proceed",
            "confidence": 1.0,
            "rationale": "ok",
            "metrics": {"expected_value": 1.0, "probability_of_loss": 0.0},
            "percentiles": {"p5": 1.0, "p95": 1.0},
            "scenarios_run": 1234,
            "run_id": "run_123",
        }

    monkeypatch.setattr(simulate, "api", fake_api)

    out = asyncio.run(
        simulate.handler(
            {
                "objective": "maximize_net_value",
                "n_simulations": 1234,
                "variables": [{"name": "revenue", "low": 1.0, "high": 2.0}],
            }
        )
    )

    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/simulate"
    assert captured["json"]["runs"] == 1234
    assert "n_simulations" not in captured["json"]
    assert json.loads(out)["scenarios_run"] == 1234


def test_embedded_mcp_simulate_uses_api_auto_objective_default(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_api(method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        captured["json"] = json
        return {
            "recommended_action": "proceed",
            "confidence": 1.0,
            "rationale": "ok",
            "metrics": {"expected_value": 1.0, "probability_of_loss": 0.0},
            "percentiles": {"p5": 1.0, "p95": 1.0},
            "scenarios_run": 10000,
            "run_id": "run_123",
        }

    monkeypatch.setattr(simulate, "api", fake_api)

    asyncio.run(
        simulate.handler({"variables": [{"name": "revenue", "low": 1.0, "high": 2.0}]})
    )

    assert captured["json"]["scenario"]["objective"] == "maximize_net_value"


def test_embedded_mcp_simulate_expert_uses_api_simulation_contract(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_api(method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = json
        return {
            "recommended_action": "proceed",
            "confidence": 1.0,
            "rationale": "ok",
            "metrics": {"expected_value": 1.0, "probability_of_loss": 0.0},
            "percentiles": {"p5": 1.0, "p95": 1.0},
            "scenarios_run": 250,
            "run_id": "run_123",
        }

    monkeypatch.setattr(simulate, "api", fake_api)

    out = asyncio.run(
        simulate.handler(
            {
                "mode": "expert",
                "objective_function": "revenue - cost",
                "n_simulations": 250,
                "variables": [
                    {"name": "revenue", "low": 1.0, "mode": 1.5, "high": 2.0},
                    {"name": "cost", "low": 0.2, "mode": 0.4, "high": 0.7},
                ],
            }
        )
    )

    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/simulate"
    assert captured["json"] == {
        "mode": "expert",
        "runs": 250,
        "simulation": {
            "variables": [
                {
                    "name": "revenue",
                    "distribution": "triangular",
                    "params": {"low": 1.0, "mode": 1.5, "high": 2.0},
                },
                {
                    "name": "cost",
                    "distribution": "triangular",
                    "params": {"low": 0.2, "mode": 0.4, "high": 0.7},
                },
            ],
            "objective_function": "revenue - cost",
        },
    }
    assert json.loads(out)["scenarios_run"] == 250


def test_embedded_mcp_simulate_expert_requires_objective_function() -> None:
    out = asyncio.run(
        simulate.handler(
            {
                "mode": "expert",
                "variables": [{"name": "revenue", "low": 1.0, "mode": 1.5, "high": 2.0}],
            }
        )
    )

    assert json.loads(out) == {
        "error": {
            "code": "invalid_argument",
            "message": "expert mode requires objective_function",
        }
    }


def test_embedded_mcp_simulate_rejects_malformed_variables() -> None:
    out = asyncio.run(simulate.handler({"variables": ["not-an-object"]}))

    assert json.loads(out) == {
        "error": {
            "code": "invalid_argument",
            "message": "variables must be an array of objects",
        }
    }


def test_embedded_mcp_simulate_rejects_invalid_auto_objective() -> None:
    out = asyncio.run(
        simulate.handler(
            {
                "objective": "maximize",
                "variables": [{"name": "revenue", "low": 1.0, "high": 2.0}],
            }
        )
    )

    assert json.loads(out) == {
        "error": {
            "code": "invalid_argument",
            "message": "objective must be a supported auto-mode objective",
        }
    }


def test_standalone_mcp_simulate_maps_n_simulations_to_runs(monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "packages" / "python-sdk"))
    sys.path.insert(0, str(ROOT / "packages" / "mcp"))
    try:
        standalone_simulate = importlib.import_module("algenta_mcp.tools.simulate")
    finally:
        sys.path = [
            entry
            for entry in sys.path
            if entry
            not in {
                str(ROOT / "packages" / "python-sdk"),
                str(ROOT / "packages" / "mcp"),
            }
        ]

    captured: dict[str, Any] = {}

    async def fake_api(method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        captured["method"] = method
        captured["path"] = path
        captured["json"] = json
        return {
            "recommended_action": "proceed",
            "confidence": 1.0,
            "rationale": "ok",
            "metrics": {"expected_value": 1.0, "probability_of_loss": 0.0},
            "percentiles": {"p5": 1.0, "p95": 1.0},
            "scenarios_run": 1234,
            "run_id": "run_123",
        }

    monkeypatch.setattr(standalone_simulate, "api", fake_api)

    out = asyncio.run(
        standalone_simulate.handler(
            {
                "objective": "maximize_net_value",
                "n_simulations": 1234,
                "variables": [{"name": "revenue", "low": 1.0, "high": 2.0}],
            }
        )
    )

    assert captured["method"] == "POST"
    assert captured["path"] == "/v1/simulate"
    assert captured["json"]["runs"] == 1234
    assert "n_simulations" not in captured["json"]
    assert json.loads(out)["scenarios_run"] == 1234


def test_standalone_mcp_simulate_expert_uses_api_simulation_contract(monkeypatch) -> None:
    sys.path.insert(0, str(ROOT / "packages" / "python-sdk"))
    sys.path.insert(0, str(ROOT / "packages" / "mcp"))
    try:
        standalone_simulate = importlib.import_module("algenta_mcp.tools.simulate")
    finally:
        sys.path = [
            entry
            for entry in sys.path
            if entry
            not in {
                str(ROOT / "packages" / "python-sdk"),
                str(ROOT / "packages" / "mcp"),
            }
        ]

    captured: dict[str, Any] = {}

    async def fake_api(method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        captured["json"] = json
        return {
            "recommended_action": "proceed",
            "confidence": 1.0,
            "rationale": "ok",
            "metrics": {"expected_value": 1.0, "probability_of_loss": 0.0},
            "percentiles": {"p5": 1.0, "p95": 1.0},
            "scenarios_run": 250,
            "run_id": "run_123",
        }

    monkeypatch.setattr(standalone_simulate, "api", fake_api)

    out = asyncio.run(
        standalone_simulate.handler(
            {
                "mode": "expert",
                "objective_function": "revenue - cost",
                "n_simulations": 250,
                "variables": [
                    {"name": "revenue", "low": 1.0, "mode": 1.5, "high": 2.0},
                    {"name": "cost", "low": 0.2, "mode": 0.4, "high": 0.7},
                ],
            }
        )
    )

    assert captured["json"]["mode"] == "expert"
    assert captured["json"]["runs"] == 250
    assert "variables" not in captured["json"]
    assert "objective_function" not in captured["json"]
    assert captured["json"]["simulation"]["objective_function"] == "revenue - cost"
    assert captured["json"]["simulation"]["variables"][0] == {
        "name": "revenue",
        "distribution": "triangular",
        "params": {"low": 1.0, "mode": 1.5, "high": 2.0},
    }
    assert json.loads(out)["scenarios_run"] == 250
