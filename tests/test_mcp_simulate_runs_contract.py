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
