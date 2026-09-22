"""POST /v1/playground — the keyless demo endpoint must actually run, and must fail by name.

Regression for the 2026-09-22 production outage: every documented playground call on
api.algenta.ai returned 500 "No module named 'algenta.simple'" because the API image shipped only
runtime_library_contract.json under /app/packages/algenta/algenta, so ``import algenta`` resolved
to a namespace-package shell. The router runs the public algenta SDK's decision / optimize /
simulate / forecast paths in-process from packages/algenta -- pure Python (stdlib Monte Carlo), no
Mojo worker, no DB, no network -- so NOTHING here is mocked: every 200 below is a real engine run.
The one deliberate patch is in the 503 test, where the SDK import itself is made to fail.
"""

from __future__ import annotations

import json
import subprocess
import sys
import uuid

import pytest
from fastapi.testclient import TestClient

import apps.api_server.routers.playground as playground_router
from apps.api_server.main import app

# gitbook/playground.md -- "Make your first playground call" (the cURL tab), verbatim.
DOCUMENTED_DECISION_BODY = {
    "mode": "decision",
    "inputs": {"revenue": 120000, "cost": 70000},
    "runs": 1000,
}
# gitbook/playground.md -- "The four modes" tabs, verbatim.
DOCUMENTED_MODE_BODIES = {
    "optimize": {
        "mode": "optimize",
        "objective": "maximize profit",
        "inputs": {"price": [10, 200], "quantity": [100, 5000]},
        "runs": 1000,
    },
    "simulate": {"mode": "simulate", "inputs": {"revenue": 120000, "cost": 70000}, "runs": 5000},
    "forecast": {"mode": "forecast", "history": [80000, 85000, 90000, 95000, 100000]},
}
# gitbook/playground.md -- "Read the response".
RESPONSE_FIELDS = {
    "playground_id",
    "mode",
    "action",
    "value",
    "confidence",
    "why",
    "details",
    "latency_ms",
    "upgrade_hint",
}


@pytest.fixture
def client() -> TestClient:
    # No `with`: the route needs no lifespan (no DB, Redis, or Mojo pool start-up).
    return TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_ip_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts with an empty per-IP window so the 10/min cap never bleeds across tests."""
    monkeypatch.setattr(playground_router, "_ip_counts", {})


def test_documented_decision_call_returns_200_with_the_documented_shape(client: TestClient) -> None:
    resp = client.post("/v1/playground", json=DOCUMENTED_DECISION_BODY)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == RESPONSE_FIELDS
    uuid.UUID(body["playground_id"])
    assert body["mode"] == "decision"
    # The docs promise proceed / pause / reject. With revenue 120k and cost 70k each modelled at
    # +/-15% the loss probability is ~0, so the verdict is deterministic across seeds.
    assert body["action"] == "proceed"
    assert isinstance(body["value"], int | float) and body["value"] > 0
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["why"] and all(isinstance(reason, str) and reason for reason in body["why"])
    assert body["details"]["scenarios_evaluated"] == 1000
    assert "label" not in body["details"]  # internal SDK field, stripped from the public shape
    assert body["latency_ms"] >= 0
    assert "1,000 scenarios" in body["upgrade_hint"]


@pytest.mark.parametrize("mode", sorted(DOCUMENTED_MODE_BODIES))
def test_every_documented_mode_runs(client: TestClient, mode: str) -> None:
    resp = client.post("/v1/playground", json=DOCUMENTED_MODE_BODIES[mode])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body) == RESPONSE_FIELDS
    assert body["mode"] == mode
    assert 0.0 <= body["confidence"] <= 1.0
    assert len(body["why"]) == 3


def test_empty_object_is_schema_valid_and_runs_the_demo_defaults(client: TestClient) -> None:
    """`{}` was reported alongside the outage as "malformed -> 500". It is not malformed: every
    field has a default, so Pydantic accepts it and the router models a demo decision. Its 500 was
    the missing SDK, the same defect as the documented body's."""
    resp = client.post("/v1/playground", json={})
    assert resp.status_code == 200, resp.text
    assert resp.json()["mode"] == "decision"


@pytest.mark.parametrize(
    "body",
    [
        pytest.param({"runs": 1}, id="runs-below-floor"),
        pytest.param({"runs": "lots"}, id="runs-not-int"),
        pytest.param({"mode": ["decision"]}, id="mode-not-str"),
        pytest.param({"inputs": ["revenue"]}, id="inputs-not-object"),
        pytest.param({"mode": "forecast", "history": "80000,85000,90000"}, id="history-not-list"),
        pytest.param({"inputs": {"runs": 500}}, id="reserved-input-name"),
        pytest.param("not an object", id="body-not-object"),
    ],
)
def test_schema_violations_are_422_validation_error(client: TestClient, body: object) -> None:
    resp = client.post("/v1/playground", json=body)
    assert resp.status_code == 422, resp.text
    err = resp.json()["error"]
    assert err["code"] == "validation_error"
    assert err["details"]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        pytest.param({"inputs": {"revenue": "not-a-number"}}, "revenue", id="decision-string"),
        pytest.param(
            {"inputs": {"revenue": {"low": 1, "high": 2}}}, "revenue", id="decision-no-value"
        ),
        pytest.param({"mode": "simulate", "inputs": {"cost": None}}, "cost", id="simulate-null"),
        pytest.param(
            {"mode": "simulate", "inputs": {"cost": [1, 2, 3]}}, "cost", id="simulate-list"
        ),
        pytest.param(
            {"mode": "optimize", "inputs": {"price": ["low", "high"]}}, "price", id="optimize-range"
        ),
        pytest.param(
            {"mode": "optimize", "inputs": {"price": {"min": 1, "max": "x"}}},
            "price",
            id="optimize-max",
        ),
    ],
)
def test_unmodellable_input_values_are_422_not_500(
    client: TestClient, body: dict[str, object], field: str
) -> None:
    """Well-typed per the schema (`inputs` is an object) but the engine cannot model the value.
    Before the fix each of these raised inside the engine try-block -> 500 playground_error."""
    resp = client.post("/v1/playground", json=body)
    assert resp.status_code == 422, resp.text
    err = resp.json()["error"]
    assert err["code"] == "playground_invalid_input"
    assert f"inputs[{field!r}]" in err["message"]


def test_missing_sdk_is_a_named_503_not_an_anonymous_500(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The production failure mode exactly: `algenta` importable, `algenta.simple` not. (The image
    held a namespace-package shell; here the submodule is blocked via sys.modules[...] = None, which
    makes the import raise ImportError.) The caller must learn it is a deployment defect."""
    monkeypatch.setitem(sys.modules, "algenta.simple", None)
    resp = client.post("/v1/playground", json=DOCUMENTED_DECISION_BODY)
    assert resp.status_code == 503, resp.text
    err = resp.json()["error"]
    assert err["code"] == "playground_unavailable"
    assert "algenta SDK" in err["message"]


def test_rate_limit_still_429_after_the_cap(client: TestClient) -> None:
    body = {**DOCUMENTED_DECISION_BODY, "runs": 100}
    for _ in range(playground_router._RATE_LIMIT):
        assert client.post("/v1/playground", json=body).status_code == 200
    resp = client.post("/v1/playground", json=body)
    assert resp.status_code == 429
    assert resp.json()["error"]["code"] == "playground_rate_limit"


def test_playground_engine_paths_are_pure_python_with_no_native_runtime() -> None:
    """The dependency chain the API image must satisfy, proven in a fresh interpreter: the four
    playground entry points pull in algenta.simple/decision/simulate/optimize/forecast plus
    privacy_profile and _contract -- all stdlib -- and never algenta.mojo_runtime, the native
    runtime wheel, numpy or httpx. This is why shipping packages/algenta/algenta into the image
    (no `algenta-runtime-native`, no Mojo wiring) is the complete fix."""
    code = (
        "import json, sys; sys.path.insert(0, sys.argv[1]);"
        "from algenta.simple import decision, optimize, simulate;"
        "from algenta.forecast import predict;"
        "decision(runs=100, revenue=120000.0, cost=70000.0);"
        "optimize('maximize profit', iterations=50, price=(10.0, 200.0), quantity=(100.0, 5000.0));"
        "simulate(runs=100, revenue=120000.0, cost=70000.0);"
        "predict([80000.0, 85000.0, 90000.0, 95000.0, 100000.0], horizon=6, metric='value');"
        "print(json.dumps(sorted(m for m in sys.modules if m == 'algenta' or m.startswith(('algenta.', 'algenta_')) or m in ('numpy', 'httpx'))))"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code, playground_router._SDK_PATH],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    loaded = set(json.loads(proc.stdout))
    required = {
        "algenta",
        "algenta.simple",
        "algenta.decision",
        "algenta.simulate",
        "algenta.optimize",
        "algenta.forecast",
    }
    allowed = required | {"algenta.privacy_profile", "algenta._contract"}
    forbidden = {
        "algenta.mojo_runtime",
        "algenta.runtime_facade",
        "algenta.native",
        "algenta_runtime_native",
        "numpy",
        "httpx",
    }
    assert required <= loaded, loaded
    assert loaded <= allowed, loaded - allowed
    assert forbidden.isdisjoint(loaded), loaded & forbidden
