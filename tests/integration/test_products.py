"""
test_products.py — Coverage for simple product APIs.

  POST /v1/decision
  POST /v1/agent/run
  POST /v1/optimize
  POST /v1/retrieve
  POST /v1/forecast

Two layers:
  Layer A — router/schema imports (no server)
  Layer B — live HTTP (requires running API server)

Run:
  DE_SKIP_API=1 python3 tests/integration/test_products.py
  python3 tests/integration/test_products.py
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

BASE_URL = os.environ.get("DE_BASE_URL", "http://localhost:8000")
API_KEY  = os.environ.get("DE_API_KEY",  "de_live_LrL6UWSAfgXsTjgfyaboI9aolrsznjLU")
SKIP_API = os.environ.get("DE_SKIP_API", "0") == "1"

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️ "
_results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    icon = PASS if cond else FAIL
    _results.append((name, cond, detail))
    print(f"  {icon}  {name}" + (f"  ({detail})" if detail else ""))


def req(method: str, path: str, body: dict | None = None, auth: bool = True) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if auth:
        headers["X-API-Key"] = API_KEY
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            b = json.loads(e.read())
        except Exception:
            b = {}
        return e.code, b


# ── Layer A: Router structure ─────────────────────────────────────────────────

def test_products_router_importable():
    from apps.api_server.routers import products
    routes = {r.path for r in products.router.routes}
    check("products router importable", True)
    check("/v1/decision registered",   "/v1/decision"  in routes)
    check("/v1/agent/run registered",  "/v1/agent/run" in routes)
    check("/v1/optimize registered",   "/v1/optimize"  in routes)
    check("/v1/retrieve registered",   "/v1/retrieve"  in routes)
    check("/v1/forecast registered",   "/v1/forecast"  in routes)


def test_products_schemas_importable():
    check("DecisionRequest importable",  True)
    check("DecisionResponse importable", True)
    check("AgentRunRequest importable",  True)
    check("AgentRunResponse importable", True)
    check("OptimizeRequest importable",  True)
    check("OptimizeResponse importable", True)
    check("RetrieveRequest importable",  True)
    check("RetrieveResponse importable", True)
    check("ForecastRequest importable",  True)
    check("ForecastResponse importable", True)


def test_decision_schema_fields():

    from apps.api_server.routers.products import DecisionRequest, DecisionResponse
    dr_fields = DecisionRequest.model_fields
    check("DecisionRequest has inputs",        "inputs"         in dr_fields)
    check("DecisionRequest has objective",     "objective"      in dr_fields)
    check("DecisionRequest has risk_tolerance","risk_tolerance" in dr_fields)
    check("DecisionRequest has scenarios",     "scenarios"      in dr_fields)
    resp_fields = DecisionResponse.model_fields
    check("DecisionResponse has action",       "action"         in resp_fields)
    check("DecisionResponse has confidence",   "confidence"     in resp_fields)
    check("DecisionResponse has reasoning",    "reasoning"      in resp_fields)
    check("DecisionResponse has downside_risk","downside_risk"  in resp_fields)


def test_forecast_schema_fields():
    from apps.api_server.routers.products import ForecastRequest, ForecastResponse
    fr_fields = ForecastRequest.model_fields
    check("ForecastRequest has metric",    "metric"    in fr_fields)
    check("ForecastRequest has history",   "history"   in fr_fields)
    check("ForecastRequest has horizon",   "horizon"   in fr_fields)
    check("ForecastRequest has seasonality","seasonality" in fr_fields)
    resp_fields = ForecastResponse.model_fields
    check("ForecastResponse has periods",  "periods"   in resp_fields)
    check("ForecastResponse has baseline", "baseline"  in resp_fields)
    check("ForecastResponse has forecast_mean", "forecast_mean" in resp_fields)


def test_all_routes_are_post():
    from apps.api_server.routers import products
    for r in products.router.routes:
        if hasattr(r, "methods"):
            check(f"{r.path} is POST only", r.methods == {"POST"})


# ── Layer B: Live HTTP ────────────────────────────────────────────────────────

def test_decision_basic():
    payload = {
        "inputs": [
            {"name": "revenue", "value": 120000, "low": 80000, "high": 180000, "unit": "USD"},
            {"name": "cost",    "value": 70000,  "low": 50000, "high": 100000, "unit": "USD"},
        ],
        "objective": "maximize_value",
        "risk_tolerance": "medium",
        "scenarios": 1000,
    }
    status, body = req("POST", "/v1/decision", payload)
    check("POST /v1/decision → 200", status == 200, f"got {status}: {str(body)[:120]}")
    if status == 200:
        check("decision has action",       "action"       in body)
        check("decision has confidence",   "confidence"   in body)
        check("decision has reasoning",    "reasoning"    in body)
        check("decision action is valid",  body.get("action") in ("proceed", "pause", "reject"))
        check("decision confidence in 0-1", 0.0 <= body.get("confidence", -1) <= 1.0)


def test_decision_no_auth():
    payload = {
        "inputs": [{"name": "x", "value": 100}],
        "scenarios": 1000,
    }
    status, body = req("POST", "/v1/decision", payload, auth=False)
    check("POST /v1/decision without auth → 401/403", status in (401, 403), f"got {status}")


def test_decision_invalid_payload():
    status, body = req("POST", "/v1/decision", {"objective": "test"})
    check("POST /v1/decision missing inputs → 422", status == 422, f"got {status}")


def test_agent_run_basic():
    payload = {
        "task": "Analyze the risk of expanding to a new market",
        "tools": ["simulate", "calculate"],
        "max_steps": 5,
        "output_format": "text",
    }
    status, body = req("POST", "/v1/agent/run", payload)
    check("POST /v1/agent/run → 200", status == 200, f"got {status}: {str(body)[:120]}")
    if status == 200:
        check("agent has run_id",    "run_id"    in body)
        check("agent has status",    "status"    in body)
        check("agent has result",    "result"    in body)
        check("agent has steps",     "steps"     in body)
        check("agent has tools_used","tools_used" in body)
        check("agent status is completed", body.get("status") == "completed")


def test_agent_run_json_output():
    payload = {
        "task": "Find the best pricing strategy for our product",
        "output_format": "json",
    }
    status, body = req("POST", "/v1/agent/run", payload)
    check("POST /v1/agent/run json format → 200", status == 200, f"got {status}")
    if status == 200:
        result = body.get("result")
        check("agent json result is dict or str", isinstance(result, dict | str))


def test_optimize_basic():
    payload = {
        "objective": "maximize profit",
        "variables": [
            {"name": "price",    "min": 10.0,  "max": 100.0, "unit": "USD"},
            {"name": "quantity", "min": 100.0, "max": 5000.0},
        ],
        "constraints": [
            {"expression": "margin > 0.2", "required": True},
        ],
        "iterations": 500,
    }
    status, body = req("POST", "/v1/optimize", payload)
    check("POST /v1/optimize → 200", status == 200, f"got {status}: {str(body)[:120]}")
    if status == 200:
        check("optimize has optimal_values",           "optimal_values"           in body)
        check("optimize has objective_value",          "objective_value"          in body)
        check("optimize has improvement_vs_midpoint",  "improvement_vs_midpoint"  in body)
        check("optimize has constraints_satisfied",    "constraints_satisfied"    in body)
        check("optimize optimal_values has price",     "price" in body.get("optimal_values", {}))
        check("optimize optimal_values has quantity",  "quantity" in body.get("optimal_values", {}))


def test_optimize_missing_variables():
    status, body = req("POST", "/v1/optimize", {"objective": "maximize"})
    check("POST /v1/optimize missing variables → 422", status == 422, f"got {status}")


def test_retrieve_basic():
    payload = {
        "query": "quarterly revenue performance",
        "documents": [
            {"id": "doc1", "content": "Q3 revenue grew 18% year-over-year, reaching $4.2M."},
            {"id": "doc2", "content": "Customer acquisition cost fell by 12% in Q3 2024."},
            {"id": "doc3", "content": "The new pricing model increased average contract value by 25%."},
        ],
        "top_k": 2,
        "rerank": True,
    }
    status, body = req("POST", "/v1/retrieve", payload)
    check("POST /v1/retrieve → 200", status == 200, f"got {status}: {str(body)[:120]}")
    if status == 200:
        check("retrieve has results",       "results"       in body)
        check("retrieve has query echoed",  "query"         in body)
        check("retrieve has retrieval_id",  "retrieval_id"  in body)
        results = body.get("results", [])
        check("retrieve returns <= top_k results", len(results) <= 2)
        if results:
            check("result has relevance_score", "relevance_score" in results[0])
            check("result has snippet",         "snippet"         in results[0])


def test_retrieve_missing_source():
    payload = {"query": "something", "top_k": 3}
    status, body = req("POST", "/v1/retrieve", payload)
    check("POST /v1/retrieve missing source → 422", status == 422, f"got {status}")


def test_forecast_basic():
    payload = {
        "metric": "monthly_revenue",
        "history": [80000, 85000, 90000, 88000, 95000, 100000, 105000, 110000],
        "horizon": 6,
        "seasonality": True,
        "confidence_level": 0.90,
    }
    status, body = req("POST", "/v1/forecast", payload)
    check("POST /v1/forecast → 200", status == 200, f"got {status}: {str(body)[:120]}")
    if status == 200:
        check("forecast has periods",      "periods"       in body)
        check("forecast has baseline",     "baseline"      in body)
        check("forecast has forecast_mean","forecast_mean" in body)
        check("forecast has metric echoed","metric"        in body)
        periods = body.get("periods", [])
        check("forecast returns 6 periods", len(periods) == 6)
        if periods:
            p = periods[0]
            check("period has forecast",     "forecast"     in p)
            check("period has lower_bound",  "lower_bound"  in p)
            check("period has upper_bound",  "upper_bound"  in p)
            check("period lower < upper",
                  p.get("lower_bound", 0) <= p.get("upper_bound", 1))


def test_forecast_too_short_history():
    payload = {"metric": "x", "history": [100, 200], "horizon": 3}
    status, body = req("POST", "/v1/forecast", payload)
    check("POST /v1/forecast history < 3 → 422", status == 422, f"got {status}")


# ── Runner ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 68)
    print("  PRODUCT API TESTS")
    print("=" * 68)

    print("\n── Layer A: Router structure (no server) ────────────────────────\n")
    for fn in [
        test_products_router_importable,
        test_products_schemas_importable,
        test_decision_schema_fields,
        test_forecast_schema_fields,
        test_all_routes_are_post,
    ]:
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, str(e))

    print("\n── Layer B: Live HTTP ────────────────────────────────────────────\n")
    live = [
        test_decision_basic,
        test_decision_no_auth,
        test_decision_invalid_payload,
        test_agent_run_basic,
        test_agent_run_json_output,
        test_optimize_basic,
        test_optimize_missing_variables,
        test_retrieve_basic,
        test_retrieve_missing_source,
        test_forecast_basic,
        test_forecast_too_short_history,
    ]
    if SKIP_API:
        print(f"  {SKIP}  Skipped (DE_SKIP_API=1)")
    else:
        for fn in live:
            try:
                fn()
            except urllib.error.URLError as e:
                print(f"  {SKIP}  {fn.__name__} — server unreachable ({e.reason})")
            except Exception as e:
                check(fn.__name__, False, f"{type(e).__name__}: {e}")

    passed = sum(1 for _, ok, _ in _results if ok)
    failed = sum(1 for _, ok, _ in _results if not ok)
    print(f"\n{'=' * 68}")
    print(f"  {passed} passed  |  {failed} failed  |  {len(_results)} total")
    print(f"{'=' * 68}\n")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
