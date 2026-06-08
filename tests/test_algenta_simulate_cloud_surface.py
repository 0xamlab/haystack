from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
for path in (str(ALGENTA_CORE), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

simulate = importlib.import_module("algenta.simulate")


class _FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def test_cloud_run_uses_expert_payload_and_parses_decision_envelope(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def _post(url, *, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _FakeResponse(
            {
                "metrics": {
                    "expected_value": 125000.0,
                    "std_deviation": 18000.0,
                    "probability_of_loss": 0.12,
                },
                "percentiles": {
                    "p5": 80000.0,
                    "p25": 100000.0,
                    "p50": 124000.0,
                    "p75": 145000.0,
                    "p95": 170000.0,
                },
                "scenarios_run": 250,
                "execution_ms": 14,
            }
        )

    monkeypatch.setitem(sys.modules, "httpx", SimpleNamespace(post=_post))

    result = simulate._cloud_run(
        variables=[
            {
                "name": "outcome",
                "distribution": "normal",
                "params": {"mean": 100.0, "std": 10.0},
            }
        ],
        runs=250,
        api_key="de_test",
        base_url="http://localhost:8000",
    )

    assert captured["url"] == "http://localhost:8000/v1/simulate"
    assert captured["headers"] == {"Authorization": "Bearer de_test"}
    assert captured["timeout"] == 60
    assert captured["json"] == {
        "mode": "expert",
        "simulation_model": "monte_carlo",
        "runs": 250,
        "simulation": {
            "variables": [
                {
                    "name": "outcome",
                    "distribution": "normal",
                    "params": {"mean": 100.0, "std": 10.0},
                }
            ],
            "objective_function": "maximize_value",
        },
    }
    assert result.engine == "cloud"
    assert result.runs == 250
    assert result.expected_value == 125000.0
    assert result.std_deviation == 18000.0
    assert result.probability_of_loss == 0.12
    assert result.percentile_5 == 80000.0
    assert result.percentile_25 == 100000.0
    assert result.percentile_50 == 124000.0
    assert result.percentile_75 == 145000.0
    assert result.percentile_95 == 170000.0
    assert result.latency_ms == 14
