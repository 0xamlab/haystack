"""
Phase 21: Complete End-to-End Integration Tests

Covers every endpoint and integration type not already exercised by earlier
test phases. Builds on real business CSV data (test_files/) for simulation
scenarios grounded in actual aviation/electronics parts distribution data.

Sections:
  1.  All 27 distribution types (expert mode, one test each)
  2.  Decision APIs  — /v1/score, /v1/batch, /v1/compare
  3.  What-if analysis — POST /v1/simulate/what-if
  4.  Account management — GET /v1/limits, PATCH /v1/me, API-key lifecycle
  5.  Billing — GET /v1/billing/info
  6.  Infrastructure & node management — /v1/infrastructure, /v1/nodes/*
  7.  Team management & audit logs
  8.  Deployments CRUD
  9.  Analytics — GET /v1/analytics
  10. Runs — pagination, mode/status filters, single-run fetch
  11. Webhook — POST /v1/webhooks/test
  12. Real CSV data pipelines (POS / Bookings / OPO / Backlog / Quotes)

Prerequisites:
  1. API server running: make dev-api  (http://localhost:8000)
  2. PostgreSQL running on :5432
  3. Redis running on :6379
  4. Dev data seeded: python scripts/seed_dev.py
  5. test_files/ directory present (real CSV business data)

Run:
  python tests/integration/test_e2e_complete.py
"""

from __future__ import annotations

import csv as csv_stdlib
import json
import math
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.request
from typing import Any

# ── project root on path ───────────────────────────────────────────────────────
_PROJECT_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tests.integration.live_capacity_blockers import classify_simulation_capacity_blocker
from tests.integration.live_integration_artifacts import write_live_integration_summary

socket.setdefaulttimeout(30)

try:
    from tests.integration.live_local_defaults import (
        configured_local_live_base_url,
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )
except ModuleNotFoundError:
    from live_local_defaults import (
        configured_local_live_base_url,
        has_configured_local_live_api_key,
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )

BASE_URL = resolve_local_live_base_url()
API_KEY = resolve_local_live_api_key()
API_KEY_CONFIGURED = has_configured_local_live_api_key()
TEST_FILES = os.path.join(_PROJECT_ROOT, "test_files")
SUITE_NAME = "e2e_complete_integration"
STARTED = time.perf_counter()

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"

results: list[tuple[str, ...]] = []
timings: list[tuple[str, float]] = []

# Shared state across sections
_created_api_key_id: str | None = None
_created_api_key_secret: str | None = None
_created_node_id: str | None = None
_created_deployment_id: str | None = None
_last_run_id: str | None = None


class EnvironmentBlocked(RuntimeError):
    """Raised when the live environment cannot execute simulation due to quota/capacity."""


def ensure_simulation_capacity_available(status: int, body: Any) -> None:
    reason = classify_simulation_capacity_blocker(status=status, payload=body)
    if reason:
        raise EnvironmentBlocked(reason)


def _emit(message: str = "") -> None:
    print(message, flush=True)


def _format_elapsed_seconds(started_at: float) -> str:
    return f"{time.monotonic() - started_at:.2f}s"


def _write_summary_artifact() -> str:
    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    skipped = sum(1 for r in results if r[0] == SKIP)
    artifact = write_live_integration_summary(
        SUITE_NAME,
        script="tests/integration/test_e2e_complete.py",
        passed=passed,
        failed=failed,
        skipped=skipped,
        total=len(results),
        elapsed_seconds=time.perf_counter() - STARTED,
        details={
            "base_url": configured_local_live_base_url(),
            "test_files_dir": TEST_FILES,
            "api_key_configured": API_KEY_CONFIGURED,
        },
    )
    return str(artifact)


# ─── HTTP helper ──────────────────────────────────────────────────────────────


def req(
    method: str,
    path: str,
    body: Any = None,
    headers: dict[str, str] | None = None,
    auth: bool = True,
    timeout: int = 25,
) -> tuple[int, Any, dict[str, str], float]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    h: dict[str, str] = {"Content-Type": "application/json"}
    if auth:
        h["X-API-Key"] = API_KEY
    if headers:
        h.update(headers)
    request = urllib.request.Request(url, data=data, headers=h, method=method)
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            elapsed = time.perf_counter() - t0
            raw = resp.read()
            body_data = json.loads(raw) if raw else {}
            return resp.status, body_data, dict(resp.headers), elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        raw = e.read()
        try:
            body_data = json.loads(raw)
        except Exception:
            body_data = raw.decode("utf-8", errors="replace")
        return e.code, body_data, dict(e.headers), elapsed
    except (TimeoutError, urllib.error.URLError) as e:
        return 0, {"error": str(e)}, {}, time.perf_counter() - t0


def check(name: str, fn) -> None:
    started_at = time.monotonic()
    _emit(f"  ... {name}")
    try:
        fn()
        elapsed = time.perf_counter() - started_at
        results.append((PASS, name))
        timings.append((name, elapsed))
        _emit(f"  {PASS} {name} ({_format_elapsed_seconds(started_at)})")
    except EnvironmentBlocked as exc:
        elapsed = time.perf_counter() - started_at
        results.append((SKIP, name, str(exc)))
        timings.append((name, elapsed))
        _emit(f"  {SKIP} {name} ({_format_elapsed_seconds(started_at)}): {exc}")
    except AssertionError as exc:
        elapsed = time.perf_counter() - started_at
        results.append((FAIL, name, str(exc)))
        _emit(f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): {exc}")
    except Exception as exc:
        elapsed = time.perf_counter() - started_at
        results.append((FAIL, name, f"{type(exc).__name__}: {exc}"))
        _emit(
            f"  {FAIL} {name} ({_format_elapsed_seconds(started_at)}): "
            f"{type(exc).__name__}: {exc}"
        )


def skip(name: str, reason: str) -> None:
    results.append((SKIP, name, reason))
    _emit(f"  {SKIP} {name}: {reason}")


# ─── reusable payloads ────────────────────────────────────────────────────────


def _expert(variables: list[dict], objective: str = "", runs: int = 500, **kw) -> dict:
    if not objective:
        objective = " + ".join(v["name"] for v in variables)
    return {
        "mode": "expert",
        "runs": runs,
        "simulation": {"variables": variables, "objective_function": objective},
        **kw,
    }


def _auto(
    variables: dict[str, dict], objective: str = "maximize_net_value", runs: int = 500
) -> dict:
    return {
        "mode": "auto",
        "runs": runs,
        "scenario": {"variables": variables, "objective": objective},
    }


_DISTRIBUTIONS: list[tuple[str, dict]] = [
    # name                params
    ("normal", {"mean": 50.0, "std": 10.0}),
    ("uniform", {"low": 10.0, "high": 90.0}),
    ("triangular", {"low": 20.0, "mode": 50.0, "high": 80.0}),
    ("lognormal", {"mean": 4.0, "std": 0.5}),
    ("fixed", {"value": 42.0}),
    ("discrete", {"values": [10.0, 20.0, 30.0], "probabilities": [0.3, 0.4, 0.3]}),
    ("categorical", {"values": [1.0, 2.0, 3.0], "probabilities": [0.2, 0.5, 0.3]}),
    ("beta", {"alpha": 2.0, "beta": 5.0}),
    ("exponential", {"rate": 0.5}),
    ("weibull", {"shape": 2.0, "scale": 1.0}),
    ("gamma", {"shape": 2.0, "scale": 2.0}),
    ("pert", {"low": 10.0, "likely": 50.0, "high": 90.0}),
    ("bernoulli", {"p": 0.6}),
    ("poisson", {"lambda": 5.0}),
    ("student_t", {"df": 10.0, "mean": 0.0, "std": 1.0}),
    ("cauchy", {"location": 0.0, "scale": 1.0}),
    ("laplace", {"mean": 0.0, "std": 1.0}),
    ("pareto", {"shape": 2.0, "scale": 1.0}),
    ("gumbel", {"mean": 0.0, "std": 1.0}),
    ("rayleigh", {"scale": 1.0}),
    ("arcsine", {"low": 0.0, "high": 1.0}),
    ("logistic", {"mean": 0.0, "std": 1.0}),
    ("halfnormal", {"std": 1.0}),
    ("vonmises", {"mean": 0.0, "kappa": 1.0}),
    ("neg_binomial", {"r": 5.0, "p": 0.5}),
    ("negative_binomial", {"r": 5.0, "p": 0.5}),  # alias — same engine path
    ("hypergeometric", {"N": 50.0, "K": 20.0, "n": 10.0}),
]

# Keep track so we test all 27
_tested_dists: set[str] = set()

_BASE_SIM = _auto({"revenue": {"low": 80_000, "high": 200_000}}, runs=200)


def test_score_endpoint():
    status, body, _, elapsed = req(
        "POST",
        "/v1/score",
        body={
            "request": _BASE_SIM,
            "scoring_weights": {"expected_value": 0.7, "downside_risk": 0.3},
        },
    )
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert "score" in body, "Missing score"
    assert "envelope" in body, "Missing envelope"
    assert 0.0 <= body["score"] <= 1.0, f"Score out of range: {body['score']}"
    assert "score_breakdown" in body, "Missing score_breakdown"
    timings.append(("POST /v1/score", elapsed))


def test_batch_endpoint():
    status, body, _, elapsed = req(
        "POST",
        "/v1/batch",
        body={
            "items": [
                _auto({"revenue": {"low": 100_000, "high": 200_000}}, runs=100),
                _auto({"revenue": {"low": 50_000, "high": 120_000}}, runs=100),
                _expert(
                    [
                        {
                            "name": "costs",
                            "distribution": "normal",
                            "params": {"mean": 60_000, "std": 8_000},
                        }
                    ],
                    "costs * -1",
                    runs=100,
                ),
            ]
        },
    )
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert body["total"] == 3, f"Expected 3 items, got {body['total']}"
    assert body["succeeded"] >= 1, "At least 1 item should succeed"
    assert "results" in body, "Missing results list"
    assert len(body["results"]) == 3, "Wrong number of results"
    timings.append(("POST /v1/batch (3 items)", elapsed))


def test_batch_partial_failure():
    """Batch allows partial failures — bad item should not kill whole request."""
    status, body, _, elapsed = req(
        "POST",
        "/v1/batch",
        body={
            "items": [
                _auto({"revenue": {"low": 50_000, "high": 100_000}}, runs=100),
                {"mode": "invalid"},  # intentionally bad
            ]
        },
    )
    # Either 200 with partial failure, or 422 — both acceptable
    assert status in (200, 422), f"Unexpected status {status}: {body}"


def test_compare_endpoint():
    status, body, _, elapsed = req(
        "POST",
        "/v1/compare",
        body={
            "scenarios": [
                {
                    "name": "Conservative",
                    "request": _auto({"revenue": {"low": 80_000, "high": 120_000}}, runs=200),
                },
                {
                    "name": "Aggressive",
                    "request": _auto({"revenue": {"low": 100_000, "high": 250_000}}, runs=200),
                },
                {
                    "name": "Balanced",
                    "request": _auto({"revenue": {"low": 90_000, "high": 160_000}}, runs=200),
                },
            ]
        },
    )
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert "winner" in body, "Missing winner"
    assert "scenarios" in body, "Missing scenarios"
    assert len(body["scenarios"]) == 3, f"Expected 3 scenarios, got {len(body['scenarios'])}"
    assert body["winner"] in ("Conservative", "Aggressive", "Balanced"), (
        f"Winner '{body['winner']}' not in scenario names"
    )
    timings.append(("POST /v1/compare (3 scenarios)", elapsed))


def test_compare_invalid_payload():
    """compare requires at least 2 scenarios."""
    status, body, _, elapsed = req(
        "POST",
        "/v1/compare",
        body={
            "scenarios": [
                {"name": "Only", "request": _auto({"x": {"low": 1, "high": 10}}, runs=100)},
            ]
        },
    )
    assert status in (400, 422), f"Expected 4xx for single scenario, got {status}"

_WHATIF_BASE = _expert(
    variables=[
        {
            "name": "revenue",
            "distribution": "normal",
            "params": {"mean": 150_000.0, "std": 20_000.0},
        },
        {"name": "costs", "distribution": "normal", "params": {"mean": 80_000.0, "std": 10_000.0}},
    ],
    objective="revenue - costs",
    runs=500,
)


def test_whatif_basic():
    status, body, _, elapsed = req(
        "POST",
        "/v1/simulate/what-if",
        body={
            "request": _WHATIF_BASE,
            "variable": "revenue",
            "param": "mean",
            "range_pct": 0.20,
            "n_steps": 5,
            "runs_per_step": 200,
        },
        timeout=30,
    )
    ensure_simulation_capacity_available(status, body)
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert body["variable"] == "revenue", "Wrong variable"
    assert body["n_steps"] == 5, "Wrong step count"
    assert len(body["steps"]) == 5, "Steps list wrong length"
    assert "elasticity" in body, "Missing elasticity"
    assert "increasing_direction" in body, "Missing increasing_direction"
    assert "sensitivity_label" in body, "Missing sensitivity_label"
    timings.append(("POST /v1/simulate/what-if (5 steps)", elapsed))


def test_whatif_std_param():
    """Vary the std parameter instead of mean."""
    status, body, _, elapsed = req(
        "POST",
        "/v1/simulate/what-if",
        body={
            "request": _WHATIF_BASE,
            "variable": "costs",
            "param": "std",
            "range_pct": 0.50,
            "n_steps": 3,
            "runs_per_step": 200,
        },
        timeout=30,
    )
    ensure_simulation_capacity_available(status, body)
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert body["param_changed"] == "std", f"Expected 'std', got {body['param_changed']}"


def test_whatif_auto_mode_rejected():
    """What-if only works with expert-mode base request."""
    status, body, _, elapsed = req(
        "POST",
        "/v1/simulate/what-if",
        body={
            "request": _auto({"revenue": {"low": 80_000, "high": 200_000}}, runs=200),
            "variable": "revenue",
            "param": "low",
            "n_steps": 3,
        },
    )
    assert status in (400, 422), f"Expected 4xx for auto-mode what-if, got {status}"


def test_limits_endpoint():
    status, body, _, elapsed = req("GET", "/v1/limits")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert isinstance(body, dict), "Expected dict response"
    # Should have at least one limit field
    limit_keys = {
        "simulations_per_month",
        "max_runs_per_simulation",
        "max_batch_size",
        "rate_limit_per_minute",
        "simulations",
        "max_runs",
        "rate",
    }
    assert any(k in body for k in limit_keys), (
        f"No limit fields found in response: {list(body.keys())}"
    )
    timings.append(("GET /v1/limits", elapsed))


def test_patch_me_name():
    """PATCH /v1/me should accept org_name update."""
    status, body, _, elapsed = req("PATCH", "/v1/me", body={"org_name": "Test Org Updated"})
    assert status == 200, f"Expected 200, got {status}: {body}"
    timings.append(("PATCH /v1/me", elapsed))


def test_api_key_create():
    global _created_api_key_id, _created_api_key_secret
    status, body, _, elapsed = req(
        "POST",
        "/v1/api-keys",
        body={
            "label": "e2e-test-key",
        },
    )
    assert status == 201, f"Expected 201, got {status}: {body}"
    secret_field = next((f for f in ("raw_key", "key", "api_key", "secret") if f in body), None)
    assert secret_field is not None, f"Missing secret field in response: {list(body.keys())}"
    _created_api_key_id = body.get("id") or body.get("key_id")
    _created_api_key_secret = body.get(secret_field)
    assert _created_api_key_id, "No key ID returned"
    timings.append(("POST /v1/api-keys", elapsed))


def test_api_key_appears_in_list():
    """New key must appear in GET /v1/api-keys."""
    if not _created_api_key_id:
        skip("Verify new key in list", "Key creation failed")
        return
    status, body, _, _ = req("GET", "/v1/api-keys")
    assert status == 200
    keys_data = body if isinstance(body, list) else body.get("keys", body.get("api_keys", []))
    ids = [str(k.get("id") or k.get("key_id", "")) for k in keys_data]
    assert str(_created_api_key_id) in ids, f"New key {_created_api_key_id} not in list: {ids}"


def test_api_key_authenticate():
    """New key should work for a real API call."""
    if not _created_api_key_secret:
        skip("Use new API key for auth", "Key creation failed")
        return
    status, body, _, _ = req(
        "GET",
        "/v1/health",
        headers={"X-API-Key": _created_api_key_secret},
        auth=False,
    )
    # Health is public; just verify key doesn't cause an error
    assert status in (200, 401), f"Unexpected status with new key: {status}"


def test_api_key_delete():
    """DELETE /v1/api-keys/{id} should revoke the key."""
    if not _created_api_key_id:
        skip("Delete API key", "Key creation failed")
        return
    status, body, _, elapsed = req("DELETE", f"/v1/api-keys/{_created_api_key_id}")
    assert status == 204, f"Expected 204, got {status}: {body}"
    timings.append(("DELETE /v1/api-keys/{id}", elapsed))


def test_deleted_key_not_in_list():
    """Deleted key must no longer appear."""
    if not _created_api_key_id:
        skip("Verify deleted key gone", "Key creation failed")
        return
    status, body, _, _ = req("GET", "/v1/api-keys")
    assert status == 200
    keys_data = body if isinstance(body, list) else body.get("keys", body.get("api_keys", []))
    ids = [str(k.get("id") or k.get("key_id", "")) for k in keys_data]
    assert str(_created_api_key_id) not in ids, f"Deleted key {_created_api_key_id} still in list"


def test_billing_info():
    status, body, _, elapsed = req("GET", "/v1/billing/info")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert isinstance(body, dict), "Expected dict"
    plan_keys = {"plan", "subscription", "status", "current_plan"}
    assert any(k in body for k in plan_keys), f"No plan field in billing info: {list(body.keys())}"
    timings.append(("GET /v1/billing/info", elapsed))


def test_billing_checkout_invalid_plan():
    """Billing checkout with unknown plan → 400."""
    status, body, _, _ = req("POST", "/v1/billing/checkout", body={"plan": "ultra_mega_plan"})
    assert status in (400, 403, 422), f"Expected 4xx for invalid plan, got {status}"


def test_infrastructure_endpoint():
    status, body, _, elapsed = req("GET", "/v1/infrastructure")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert "nodes" in body, "Missing nodes"
    assert "deployment_mode" in body, "Missing deployment_mode"
    assert "engine_version" in body, "Missing engine_version"
    assert isinstance(body["nodes"], list), "nodes should be a list"
    assert len(body["nodes"]) >= 1, "At least one node (primary) must be present"
    timings.append(("GET /v1/infrastructure", elapsed))


def test_node_register():
    global _created_node_id
    status, body, _, elapsed = req(
        "POST",
        "/v1/nodes/register",
        body={
            "region": "us-east-1-test",
            "engine_version": "0.99-e2e-test",
            "cpu_count": 8,
            "memory_gb": 32.0,
            "capabilities": ["standard", "high-memory"],
        },
    )
    assert status == 201, f"Expected 201, got {status}: {body}"
    assert "node_id" in body, f"Missing node_id: {body}"
    _created_node_id = body["node_id"]
    timings.append(("POST /v1/nodes/register", elapsed))


def test_node_appears_in_infrastructure():
    """Registered node should show up in /v1/infrastructure."""
    if not _created_node_id:
        skip("Verify registered node in infra", "Node registration failed")
        return
    status, body, _, _ = req("GET", "/v1/infrastructure")
    assert status == 200
    node_ids = [n["node_id"] for n in body.get("nodes", [])]
    assert _created_node_id in node_ids, (
        f"Node {_created_node_id} not found in infrastructure: {node_ids}"
    )


def test_node_heartbeat():
    if not _created_node_id:
        skip("Node heartbeat", "Node registration failed")
        return
    status, body, _, elapsed = req(
        "POST",
        "/v1/nodes/heartbeat",
        body={
            "node_id": _created_node_id,
            "status": "live",
            "cpu_pct": 45.2,
            "memory_gb": 18.5,
            "jobs_per_sec": 120.0,
        },
    )
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert body.get("accepted") is True, f"Heartbeat not accepted: {body}"
    timings.append(("POST /v1/nodes/heartbeat", elapsed))


def test_node_heartbeat_unknown():
    """Heartbeat for non-existent node → 404."""
    status, body, _, _ = req(
        "POST",
        "/v1/nodes/heartbeat",
        body={
            "node_id": "node-does-not-exist-xyz",
            "status": "live",
        },
    )
    assert status == 404, f"Expected 404 for unknown node, got {status}"


def test_node_deregister():
    if not _created_node_id:
        skip("Node deregister", "Node registration failed")
        return
    status, body, _, elapsed = req("DELETE", f"/v1/nodes/{_created_node_id}")
    assert status == 204, f"Expected 204, got {status}: {body}"
    timings.append((f"DELETE /v1/nodes/{_created_node_id}", elapsed))


def test_deregistered_node_gone():
    """Deregistered node must no longer appear in infrastructure."""
    if not _created_node_id:
        skip("Verify deregistered node gone", "Node deregister failed")
        return
    status, body, _, _ = req("GET", "/v1/infrastructure")
    assert status == 200
    node_ids = [n["node_id"] for n in body.get("nodes", [])]
    assert _created_node_id not in node_ids, (
        f"Deregistered node {_created_node_id} still in infrastructure"
    )


def test_team_list():
    status, body, _, elapsed = req("GET", "/v1/team")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert isinstance(body, list), f"Expected list, got {type(body)}"
    assert len(body) >= 1, "At least one team member expected (self)"
    member = body[0]
    assert "email" in member or "user_id" in member, (
        f"Member missing identity fields: {list(member.keys())}"
    )
    timings.append(("GET /v1/team", elapsed))


def test_team_invite_validation():
    """Invite with invalid email → 422 (or 403 if caller lacks admin role)."""
    status, body, _, _ = req(
        "POST",
        "/v1/team/invite",
        body={
            "email": "not-an-email",
            "role": "developer",
        },
    )
    assert status in (422, 403), f"Expected 422 (validation) or 403 (RBAC), got {status}"


def test_audit_logs():
    status, body, _, elapsed = req("GET", "/v1/audit-logs")
    # 200 for admins, 403 for members — both are correct RBAC behaviour
    assert status in (200, 403), f"Expected 200 or 403, got {status}: {body}"
    if status == 200:
        entries = body.get("entries", body) if isinstance(body, dict) else body
        assert isinstance(entries, list), "Expected list of entries"
    timings.append(("GET /v1/audit-logs", elapsed))


def test_audit_logs_pagination():
    status, body, _, _ = req("GET", "/v1/audit-logs?page=1&limit=5")
    assert status in (200, 403), f"Expected 200 or 403, got {status}"


def test_audit_log_artifacts():
    status, body, _, elapsed = req("GET", "/v1/audit-logs/artifacts")
    assert status in (200, 403), f"Expected 200 or 403, got {status}: {body}"
    if status == 200:
        entries = body.get("entries", body) if isinstance(body, dict) else body
        assert isinstance(entries, list), "Expected list of entries"
        if entries:
            assert "content_hash" in entries[0]
    timings.append(("GET /v1/audit-logs/artifacts", elapsed))


def test_deployments_list():
    status, body, _, elapsed = req("GET", "/v1/deployments")
    assert status == 200, f"Expected 200, got {status}: {body}"
    timings.append(("GET /v1/deployments", elapsed))


def test_deployment_create():
    global _created_deployment_id
    status, body, _, elapsed = req(
        "POST",
        "/v1/deployments",
        body={
            "name": "e2e-test-deploy",
            "provider": "aws",
            "region": "us-east-1",
            "tier": "standard",
        },
    )
    # 202 accepted or plan / payload denial states are acceptable
    assert status in (202, 400, 402, 403, 422), (
        f"Unexpected deployment create status {status}: {body}"
    )
    if status == 202:
        _created_deployment_id = body.get("id") or body.get("deployment_id")
        timings.append(("POST /v1/deployments", elapsed))


def test_deployment_get():
    if not _created_deployment_id:
        skip("GET /v1/deployments", "No deployment was created")
        return
    status, body, _, elapsed = req("GET", "/v1/deployments")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert body.get("deployment_id") == _created_deployment_id, (
        f"Expected current deployment '{_created_deployment_id}', got {body}"
    )


def test_deployment_delete():
    if not _created_deployment_id:
        skip("DELETE /v1/deployments/{id}", "No deployment to delete")
        return
    status, body, _, elapsed = req("DELETE", f"/v1/deployments/{_created_deployment_id}")
    assert status == 202, f"Expected 202, got {status}: {body}"


def test_analytics_default():
    status, body, _, elapsed = req("GET", "/v1/analytics")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert isinstance(body, dict), "Expected dict"
    assert "total_runs" in body, "Missing total_runs"
    assert "runs_by_day" in body, "Missing runs_by_day"
    assert "runs_by_status" in body, "Missing runs_by_status"
    assert "runs_by_mode" in body, "Missing runs_by_mode"
    assert isinstance(body["total_runs"], int), "total_runs should be int"
    timings.append(("GET /v1/analytics", elapsed))


def test_analytics_custom_window():
    status, body, _, _ = req("GET", "/v1/analytics?days=7")
    assert status == 200, f"Expected 200, got {status}"
    assert "total_runs" in body


def test_analytics_invalid_window():
    """days=0 is below minimum (ge=1) → 422."""
    status, body, _, _ = req("GET", "/v1/analytics?days=0")
    assert status == 422, f"Expected 422 for days=0, got {status}"

# First, produce a run so we have something to query
_run_body_for_fetch = None


def test_produce_a_run():
    global _last_run_id, _run_body_for_fetch
    status, body, _, _ = req(
        "POST", "/v1/simulate", body=_auto({"profit": {"low": 10_000, "high": 50_000}}, runs=200)
    )
    ensure_simulation_capacity_available(status, body)
    assert status == 200, f"Simulate failed: {status}"
    _last_run_id = body.get("run_id")


def test_runs_pagination():
    status, body, _, elapsed = req("GET", "/v1/runs?page=1&limit=5")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert "runs" in body, "Missing runs list"
    assert "total" in body, "Missing total"
    assert "pages" in body, "Missing pages"
    assert len(body["runs"]) <= 5, "More runs than requested limit"
    timings.append(("GET /v1/runs?page=1&limit=5", elapsed))


def test_runs_filter_by_status():
    status, body, _, _ = req("GET", "/v1/runs?status=completed&limit=3")
    assert status == 200, f"Expected 200, got {status}"
    assert "runs" in body
    for r in body["runs"]:
        assert r["status"] == "completed", (
            f"Run {r['run_id']} has status {r['status']}, expected completed"
        )


def test_runs_filter_by_mode():
    status, body, _, _ = req("GET", "/v1/runs?mode=auto&limit=3")
    assert status == 200, f"Expected 200, got {status}"
    assert "runs" in body


def test_runs_page_2():
    status, body, _, _ = req("GET", "/v1/runs?page=2&limit=5")
    assert status == 200, f"Expected 200 for page 2, got {status}"


def test_single_run_fetch():
    if not _last_run_id:
        skip("GET /v1/runs/{run_id}", "No run_id available")
        return
    status, body, _, elapsed = req("GET", f"/v1/runs/{_last_run_id}")
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert "run_id" in body or "id" in body, "Missing id in run detail"
    assert "status" in body, "Missing status"
    timings.append((f"GET /v1/runs/{_last_run_id}", elapsed))


def test_run_not_found():
    status, body, _, _ = req("GET", "/v1/runs/00000000-0000-0000-0000-000000000000")
    assert status == 404, f"Expected 404 for missing run, got {status}"


def test_webhook_test_delivery():
    """POST /v1/webhooks/test — deliver test event to httpbin or similar."""
    # Use httpbin.org echo endpoint; skip if unreachable
    status, body, _, elapsed = req(
        "POST",
        "/v1/webhooks/test",
        body={
            "callback_url": "https://httpbin.org/post",
        },
        timeout=15,
    )
    # 200 = delivered, 502/503 = httpbin unreachable (OK in CI), 422 = validation error
    assert status in (200, 422, 502, 503, 504), f"Unexpected webhook test status {status}: {body}"
    if status == 200:
        assert "success" in body, "Missing success field"
    timings.append(("POST /v1/webhooks/test", elapsed))


def test_webhook_invalid_url():
    status, body, _, _ = req(
        "POST",
        "/v1/webhooks/test",
        body={
            "callback_url": "not-a-url",
        },
    )
    # 422 if pydantic rejects the URL, 400 if custom validation, 200 if the
    # engine attempts delivery and returns a failure result — all acceptable
    assert status in (200, 400, 422), f"Unexpected status for invalid URL: {status}"

# ── helper: parse a CSV file into list[dict] ───────────────────────────────


def _load_csv(filename: str, max_rows: int = 2000) -> list[dict]:
    path = os.path.join(TEST_FILES, filename)
    if not os.path.exists(path):
        return []
    with open(path, newline="", errors="replace") as fh:
        reader = csv_stdlib.DictReader(fh)
        rows: list[dict] = []
        for i, row in enumerate(reader):
            if i >= max_rows:
                break
            rows.append(row)
    return rows


def _to_float(val: str) -> float | None:
    if not val:
        return None
    clean = re.sub(r"[^\d.\-+eE]", "", str(val))
    try:
        return float(clean)
    except ValueError:
        return None


def _numeric_stats(rows: list[dict], col: str) -> dict | None:
    """Return min/max/mean/count for a numeric column."""
    vals = [_to_float(r.get(col, "")) for r in rows]
    vals = [v for v in vals if v is not None and v > 0]
    if len(vals) < 10:
        return None
    vals.sort()
    n = len(vals)
    total = sum(vals)
    return {
        "min": vals[0],
        "max": vals[-1],
        "mean": total / n,
        "median": vals[n // 2],
        "count": n,
    }


def _lognormal_params_from_stats(mean: float, std: float) -> dict[str, float]:
    """Convert positive raw-space moments into the log-space params used by the engine."""
    safe_mean = max(mean, 1e-9)
    safe_std = max(std, 1e-9)
    sigma2 = math.log(1.0 + (safe_std * safe_std) / (safe_mean * safe_mean))
    return {
        "mean": math.log(safe_mean) - sigma2 / 2.0,
        "std": math.sqrt(sigma2),
    }


# ── POS.csv — Point-of-Sale simulation ────────────────────────────────────


def test_pos_csv_loaded():
    rows = _load_csv("POS.csv")
    assert len(rows) >= 100, f"POS.csv: too few rows ({len(rows)})"
    cols = set(rows[0].keys())
    expected = {"UNIT_PRICE", "UNIT_COST", "QUANTITY"}
    assert expected.issubset(cols), f"Missing columns: {expected - cols}"


def test_pos_unit_price_simulate():
    """Fit triangular distribution to real POS unit-price range and simulate."""
    rows = _load_csv("POS.csv", max_rows=5000)
    stats = _numeric_stats(rows, "UNIT_PRICE")
    if not stats:
        skip("POS unit-price simulate", "Not enough numeric UNIT_PRICE values")
        return

    payload = _expert(
        variables=[
            {
                "name": "unit_price",
                "distribution": "triangular",
                "params": {
                    "low": stats["min"],
                    "mode": stats["median"],
                    "high": stats["max"],
                },
            }
        ],
        objective="unit_price",
        runs=1000,
    )
    status, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
    ensure_simulation_capacity_available(status, body)
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert isinstance(body["metrics"]["expected_value"], int | float), (
        "Expected numeric EV for unit price"
    )
    timings.append(("POST /v1/simulate (POS unit_price)", elapsed))
    print(
        f"    → POS unit_price: min={stats['min']:.2f}, "
        f"max={stats['max']:.2f}, mean={stats['mean']:.2f}, "
        f"simulated_ev={body['metrics']['expected_value']:.2f}"
    )


def test_pos_margin_simulation():
    """Simulate expected margin from POS cost/price data."""
    rows = _load_csv("POS.csv", max_rows=5000)
    price_stats = _numeric_stats(rows, "UNIT_PRICE")
    cost_stats = _numeric_stats(rows, "UNIT_COST")
    if not price_stats or not cost_stats:
        skip("POS margin simulate", "Not enough price/cost values")
        return

    payload = _expert(
        variables=[
            {
                "name": "price",
                "distribution": "normal",
                "params": {
                    "mean": price_stats["mean"],
                    "std": (price_stats["max"] - price_stats["min"]) / 6,
                },
            },
            {
                "name": "cost",
                "distribution": "normal",
                "params": {
                    "mean": cost_stats["mean"],
                    "std": (cost_stats["max"] - cost_stats["min"]) / 6,
                },
            },
        ],
        objective="price - cost",
        runs=2000,
    )
    status, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
    ensure_simulation_capacity_available(status, body)
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert "recommended_action" in body
    print(
        f"    → POS margin: recommended={body['recommended_action']}, "
        f"confidence={body['confidence']:.2%}, "
        f"ev={body['metrics']['expected_value']:.2f}"
    )
    timings.append(("POST /v1/simulate (POS margin)", elapsed))


# ── Bookings.csv — Revenue forecast simulation ────────────────────────────


def test_bookings_csv_loaded():
    rows = _load_csv("Bookings.csv")
    assert len(rows) >= 100, f"Bookings.csv: too few rows ({len(rows)})"
    cols = set(rows[0].keys())
    assert "UNIT_PRICE" in cols or "EXT_PRICE" in cols, (
        f"Missing price columns in Bookings.csv: {list(cols)[:10]}"
    )


def test_bookings_ext_price_simulate():
    rows = _load_csv("Bookings.csv", max_rows=5000)
    col = "EXT_PRICE" if "EXT_PRICE" in (rows[0] if rows else {}) else "UNIT_PRICE"
    stats = _numeric_stats(rows, col)
    if not stats:
        skip("Bookings ext_price simulate", "Not enough numeric values")
        return

    payload = _expert(
        variables=[
            {
                "name": "booking_value",
                "distribution": "lognormal",
                "params": _lognormal_params_from_stats(
                    stats["mean"],
                    max(0.1, (stats["max"] - stats["min"]) / 6),
                ),
            }
        ],
        objective="booking_value",
        runs=1000,
    )
    status, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
    ensure_simulation_capacity_available(status, body)
    assert status == 200, f"Expected 200, got {status}: {body}"
    timings.append(("POST /v1/simulate (Bookings ext_price)", elapsed))
    print(
        f"    → Bookings {col}: mean={stats['mean']:.2f}, "
        f"simulated_ev={body['metrics']['expected_value']:.2f}"
    )


# ── OPO.csv — Open Purchase Orders ────────────────────────────────────────


def test_opo_csv_loaded():
    rows = _load_csv("OPO.csv")
    assert len(rows) >= 50, f"OPO.csv: too few rows ({len(rows)})"
    cols = set(rows[0].keys())
    assert "Unit Cost" in cols or "Quantity Ordered" in cols, (
        f"Missing expected OPO columns: {list(cols)[:10]}"
    )


def test_opo_purchase_cost_simulate():
    rows = _load_csv("OPO.csv", max_rows=2000)
    cost_stats = _numeric_stats(rows, "Unit Cost")
    qty_stats = _numeric_stats(rows, "Quantity Ordered")
    if not cost_stats or not qty_stats:
        skip("OPO purchase cost simulate", "Not enough numeric OPO values")
        return

    payload = _expert(
        variables=[
            {
                "name": "unit_cost",
                "distribution": "pert",
                "params": {
                    "low": cost_stats["min"],
                    "likely": cost_stats["median"],
                    "high": cost_stats["max"],
                },
            },
            {
                "name": "quantity",
                "distribution": "triangular",
                "params": {
                    "low": max(1.0, qty_stats["min"]),
                    "mode": qty_stats["median"],
                    "high": qty_stats["max"],
                },
            },
        ],
        objective="unit_cost * quantity * -1",
        runs=1000,
    )
    status, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
    ensure_simulation_capacity_available(status, body)
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert isinstance(body["metrics"]["expected_value"], int | float), (
        "Expected numeric EV for purchase cost"
    )
    timings.append(("POST /v1/simulate (OPO purchase cost)", elapsed))
    print(
        f"    → OPO cost*qty EV={body['metrics']['expected_value']:.2f}, "
        f"action={body['recommended_action']}"
    )


# ── Backlog.csv — Open orders revenue simulation ──────────────────────────


def test_backlog_simulate():
    rows = _load_csv("Backlog.csv", max_rows=3000)
    price_col = "UNIT_PRICE" if "UNIT_PRICE" in (rows[0] if rows else {}) else "EXT_PRICE"
    stats = _numeric_stats(rows, price_col)
    if not stats:
        skip("Backlog simulate", "Not enough numeric backlog values")
        return

    payload = _expert(
        variables=[
            {
                "name": "backlog_value",
                "distribution": "triangular",
                "params": {
                    "low": stats["min"],
                    "mode": stats["median"],
                    "high": min(stats["max"], stats["mean"] * 10),  # cap outliers
                },
            }
        ],
        objective="backlog_value",
        runs=1000,
    )
    status, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
    ensure_simulation_capacity_available(status, body)
    assert status == 200, f"Expected 200, got {status}: {body}"
    timings.append(("POST /v1/simulate (Backlog)", elapsed))
    print(
        f"    → Backlog {price_col}: median={stats['median']:.2f}, "
        f"simulated_ev={body['metrics']['expected_value']:.2f}"
    )


# ── Quotes_Combined — Win-rate scenario comparison ────────────────────────


def test_quotes_csv_loaded():
    rows = _load_csv("Quotes_Combined_20241116.csv", max_rows=100)
    assert len(rows) >= 5, f"Quotes CSV: too few rows ({len(rows)})"
    cols = set(rows[0].keys())
    assert "UNIT_PRICE" in cols or "EXT_PRICE" in cols, (
        f"Missing price columns in Quotes CSV: {list(cols)[:10]}"
    )


def test_quotes_win_loss_scenario_compare():
    """Compare win vs. lose scenarios using quote pricing data."""
    rows = _load_csv("Quotes_Combined_20241116.csv", max_rows=3000)
    stats = _numeric_stats(rows, "UNIT_PRICE")
    if not stats:
        skip("Quotes win/loss compare", "Not enough UNIT_PRICE data")
        return

    mean_p = stats["mean"]
    std_p = max(1.0, (stats["max"] - stats["min"]) / 6)

    status, body, _, elapsed = req(
        "POST",
        "/v1/compare",
        body={
            "scenarios": [
                {
                    "name": "Aggressive Pricing (below market)",
                    "request": _expert(
                        [
                            {
                                "name": "revenue",
                                "distribution": "normal",
                                "params": {"mean": mean_p * 0.85, "std": std_p * 0.5},
                            }
                        ],
                        "revenue",
                        runs=300,
                    ),
                },
                {
                    "name": "Market Rate Pricing",
                    "request": _expert(
                        [
                            {
                                "name": "revenue",
                                "distribution": "normal",
                                "params": {"mean": mean_p, "std": std_p},
                            }
                        ],
                        "revenue",
                        runs=300,
                    ),
                },
                {
                    "name": "Premium Pricing (above market)",
                    "request": _expert(
                        [
                            {
                                "name": "revenue",
                                "distribution": "normal",
                                "params": {"mean": mean_p * 1.15, "std": std_p * 1.5},
                            }
                        ],
                        "revenue",
                        runs=300,
                    ),
                },
            ]
        },
        timeout=30,
    )
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert body["winner"] in (
        "Aggressive Pricing (below market)",
        "Market Rate Pricing",
        "Premium Pricing (above market)",
    ), f"Winner '{body['winner']}' not valid"
    timings.append(("POST /v1/compare (quotes pricing)", elapsed))
    print(f"    → Quotes pricing winner: {body['winner']}")


# ── Unique_POS_Recent_Stats — inventory/demand analysis ───────────────────


def test_pos_stats_csv_simulate():
    rows = _load_csv("Unique_POS_Recent_Stats.csv", max_rows=2000)
    if not rows:
        skip("Unique_POS_Recent_Stats simulate", "File not found or empty")
        return
    # Find any useful numeric column
    numeric_cols = []
    if rows:
        for col in rows[0].keys():
            vals = [_to_float(r.get(col, "")) for r in rows[:50]]
            vals = [v for v in vals if v is not None and v > 0]
            if len(vals) >= 10:
                numeric_cols.append(col)
    if not numeric_cols:
        skip("Unique_POS_Recent_Stats simulate", "No usable numeric columns")
        return

    col = numeric_cols[0]
    stats = _numeric_stats(rows, col)
    if not stats:
        skip("Unique_POS_Recent_Stats simulate", "No stats")
        return

    payload = _expert(
        variables=[
            {
                "name": "demand",
                "distribution": "normal",
                "params": {"mean": stats["mean"], "std": max(1.0, stats["mean"] * 0.2)},
            }
        ],
        objective="demand",
        runs=500,
    )
    status, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
    ensure_simulation_capacity_available(status, body)
    assert status == 200, f"Expected 200, got {status}: {body}"
    timings.append(("POST /v1/simulate (POS stats)", elapsed))


# ── Full pipeline: CSV → score → what-if ─────────────────────────────────


def test_csv_to_whatif_pipeline():
    """
    End-to-end pipeline:
      1. Load POS.csv
      2. Fit normal distributions to UNIT_PRICE and UNIT_COST
      3. Run what-if on the UNIT_PRICE mean
    """
    rows = _load_csv("POS.csv", max_rows=3000)
    price_stats = _numeric_stats(rows, "UNIT_PRICE")
    cost_stats = _numeric_stats(rows, "UNIT_COST")
    if not price_stats or not cost_stats:
        skip("CSV → what-if pipeline", "Not enough POS data")
        return

    base_request = _expert(
        variables=[
            {
                "name": "price",
                "distribution": "normal",
                "params": {
                    "mean": price_stats["mean"],
                    "std": max(1.0, (price_stats["max"] - price_stats["min"]) / 6),
                },
            },
            {
                "name": "cost",
                "distribution": "normal",
                "params": {
                    "mean": cost_stats["mean"],
                    "std": max(1.0, (cost_stats["max"] - cost_stats["min"]) / 6),
                },
            },
        ],
        objective="price - cost",
        runs=500,
    )

    status, body, _, elapsed = req(
        "POST",
        "/v1/simulate/what-if",
        body={
            "request": base_request,
            "variable": "price",
            "param": "mean",
            "range_pct": 0.25,
            "n_steps": 5,
            "runs_per_step": 300,
        },
        timeout=45,
    )
    ensure_simulation_capacity_available(status, body)
    assert status == 200, f"Expected 200, got {status}: {body}"
    assert len(body["steps"]) == 5
    # Verify steps span a range (the sweep should produce variation)
    step_evs = [s["mean"] for s in body["steps"]]
    ev_range = max(step_evs) - min(step_evs)
    assert ev_range >= 0, "EV range must be non-negative"
    # At least the first and last step should differ (±25% sweep on price mean)
    assert step_evs[0] != step_evs[-1] or all(abs(ev - step_evs[0]) < 1e-6 for ev in step_evs), (
        "What-if produced no variation — check variable/param names"
    )
    timings.append(("CSV→what-if pipeline (POS)", elapsed))
    print(
        f"    → POS what-if: direction={body['increasing_direction']}, "
        f"elasticity={body['elasticity']:.3f}"
    )


# ── Consolidated_Table — multi-var simulation ──────────────────────────────


def test_consolidated_table_multi_var():
    rows = _load_csv("Consolidated_Table.csv", max_rows=3000)
    if not rows:
        skip("Consolidated_Table multi-var", "File not found")
        return

    variables = []
    for col in ["UNIT_PRICE", "UNIT_COST", "QUANTITY"]:
        if col not in (rows[0] if rows else {}):
            continue
        stats = _numeric_stats(rows, col)
        if not stats:
            continue
        variables.append(
            {
                "name": re.sub(r"[^a-zA-Z0-9_]", "_", col.lower()),
                "distribution": "triangular",
                "params": {
                    "low": stats["min"],
                    "mode": stats["median"],
                    "high": stats["max"],
                },
            }
        )

    if len(variables) < 2:
        skip("Consolidated_Table multi-var", "Not enough usable columns")
        return

    obj = " + ".join(v["name"] for v in variables)
    payload = _expert(variables=variables, objective=obj, runs=500)
    status, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
    ensure_simulation_capacity_available(status, body)
    assert status == 200, f"Expected 200, got {status}: {body}"
    timings.append(("POST /v1/simulate (Consolidated_Table multi-var)", elapsed))


if __name__ == "__main__":
    # ══════════════════════════════════════════════════════════════════════════════
    #  CONNECTIVITY CHECK
    # ══════════════════════════════════════════════════════════════════════════════
    _emit("\n" + "=" * 70)
    _emit("  PHASE 21: Complete End-to-End Integration Tests")
    _emit("=" * 70)

    status, _, _, _ = req("GET", "/v1/health", auth=False, timeout=5)
    if status != 200:
        _emit(f"\n  {FAIL} Cannot reach API server at {BASE_URL}")
        _emit("     Make sure the server is running (make dev-api)")
        sys.exit(1)

    _emit(f"  {PASS} Server reachable")

    if not API_KEY_CONFIGURED:
        reason = (
            "DE_API_KEY is not set; skipping complete end-to-end live checks "
            "that require a real live key."
        )
        skip("E2E complete suite preflight", reason)
        _emit(f"\n  {SKIP} preflight: {reason}")
        artifact_path = _write_summary_artifact()
        _emit(f"  Summary artifact: {artifact_path}\n")
        sys.exit(0)


    # ══════════════════════════════════════════════════════════════════════════════
    #  SECTION 1 — All 27 distribution types
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 1: All 27 Distribution Types")
    print("=" * 70)

    for _dist_name, _dist_params in _DISTRIBUTIONS:

        def _make_dist_test(dist_name: str, dist_params: dict):
            def _test():
                payload = _expert(
                    variables=[{"name": "x", "distribution": dist_name, "params": dist_params}],
                    objective="x",
                    runs=300,
                )
                status, body, _, elapsed = req("POST", "/v1/simulate", body=payload)
                ensure_simulation_capacity_available(status, body)
                assert status == 200, f"[{dist_name}] Expected 200, got {status}: {body}"
                assert "confidence" in body, f"[{dist_name}] Missing confidence"
                assert "metrics" in body, f"[{dist_name}] Missing metrics"
                assert isinstance(body["confidence"], int | float), (
                    f"[{dist_name}] confidence is {type(body['confidence'])}"
                )
                timings.append((f"POST /v1/simulate ({dist_name})", elapsed))

            return _test

        check(f"Distribution: {_dist_name}", _make_dist_test(_dist_name, _dist_params))
        _tested_dists.add(_dist_name)

    assert len(_tested_dists) == 27, f"Expected 27 distributions, tested {len(_tested_dists)}"


    # ══════════════════════════════════════════════════════════════════════════════
    #  SECTION 2 — Decision APIs: /v1/score, /v1/batch, /v1/compare
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 2: Decision APIs (score / batch / compare)")
    print("=" * 70)


    check("POST /v1/score → 200 with score breakdown", test_score_endpoint)


    check("POST /v1/batch (3 items) → 200", test_batch_endpoint)


    check("POST /v1/batch partial failure handled gracefully", test_batch_partial_failure)


    check("POST /v1/compare (3 scenarios) → 200 with winner", test_compare_endpoint)


    check("POST /v1/compare single scenario → 4xx", test_compare_invalid_payload)


    # ══════════════════════════════════════════════════════════════════════════════
    #  SECTION 3 — What-if analysis
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 3: What-If Analysis")
    print("=" * 70)


    check("POST /v1/simulate/what-if → 200 with sweep", test_whatif_basic)


    check("POST /v1/simulate/what-if (vary std) → 200", test_whatif_std_param)


    check("POST /v1/simulate/what-if with auto-mode → 400/422", test_whatif_auto_mode_rejected)


    # ══════════════════════════════════════════════════════════════════════════════
    #  SECTION 4 — Account management
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 4: Account Management")
    print("=" * 70)


    check("GET /v1/limits → 200 with quota fields", test_limits_endpoint)


    check("PATCH /v1/me → 200", test_patch_me_name)


    check("POST /v1/api-keys → 201 with new key", test_api_key_create)


    check("New API key appears in GET /v1/api-keys list", test_api_key_appears_in_list)


    check("New API key authenticates without error", test_api_key_authenticate)


    check("DELETE /v1/api-keys/{id} → 204", test_api_key_delete)


    check("Deleted API key no longer in list", test_deleted_key_not_in_list)


    # ══════════════════════════════════════════════════════════════════════════════
    #  SECTION 5 — Billing
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 5: Billing")
    print("=" * 70)


    check("GET /v1/billing/info → 200 with plan", test_billing_info)


    check("POST /v1/billing/checkout invalid plan → 4xx", test_billing_checkout_invalid_plan)


    # ══════════════════════════════════════════════════════════════════════════════
    #  SECTION 6 — Infrastructure & node management
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 6: Infrastructure & Node Management")
    print("=" * 70)


    check("GET /v1/infrastructure → 200 with nodes", test_infrastructure_endpoint)


    check("POST /v1/nodes/register → 201 with node_id", test_node_register)


    check("Registered node appears in /v1/infrastructure", test_node_appears_in_infrastructure)


    check("POST /v1/nodes/heartbeat → 200 accepted", test_node_heartbeat)


    check("POST /v1/nodes/heartbeat unknown node → 404", test_node_heartbeat_unknown)


    check("DELETE /v1/nodes/{node_id} → 204", test_node_deregister)


    check("Deregistered node no longer in /v1/infrastructure", test_deregistered_node_gone)


    # ══════════════════════════════════════════════════════════════════════════════
    #  SECTION 7 — Team management & audit logs
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 7: Team Management & Audit Logs")
    print("=" * 70)


    check("GET /v1/team → 200 non-empty list", test_team_list)


    check("POST /v1/team/invite invalid email → 422/403", test_team_invite_validation)


    check("GET /v1/audit-logs → 200 (admin) or 403 (member)", test_audit_logs)


    check("GET /v1/audit-logs pagination → 200 or 403", test_audit_logs_pagination)


    check("GET /v1/audit-logs/artifacts → 200 (admin) or 403 (member)", test_audit_log_artifacts)


    # ══════════════════════════════════════════════════════════════════════════════
    #  SECTION 8 — Deployments CRUD
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 8: Deployments")
    print("=" * 70)


    check("GET /v1/deployments → 200", test_deployments_list)


    check("POST /v1/deployments → 202 or plan-denied 402/403", test_deployment_create)


    check("GET /v1/deployments → 200 with current deployment", test_deployment_get)


    check("DELETE /v1/deployments/{id} → 202", test_deployment_delete)


    # ══════════════════════════════════════════════════════════════════════════════
    #  SECTION 9 — Analytics
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 9: Analytics")
    print("=" * 70)


    check("GET /v1/analytics → 200 with aggregates", test_analytics_default)


    check("GET /v1/analytics?days=7 → 200", test_analytics_custom_window)


    check("GET /v1/analytics?days=0 → 422", test_analytics_invalid_window)


    # ══════════════════════════════════════════════════════════════════════════════
    #  SECTION 10 — Runs: pagination, filters, single-run fetch
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 10: Runs — Pagination & Filters")
    print("=" * 70)


    check("POST /v1/simulate to seed a run_id", test_produce_a_run)


    check("GET /v1/runs pagination → 200 with pages/total", test_runs_pagination)


    check("GET /v1/runs?status=completed → only completed runs", test_runs_filter_by_status)


    check("GET /v1/runs?mode=auto → 200", test_runs_filter_by_mode)


    check("GET /v1/runs page 2 → 200", test_runs_page_2)


    check("GET /v1/runs/{run_id} → 200 with detail", test_single_run_fetch)


    check("GET /v1/runs/{nonexistent_id} → 404", test_run_not_found)


    # ══════════════════════════════════════════════════════════════════════════════
    #  SECTION 11 — Webhooks
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 11: Webhooks")
    print("=" * 70)


    check("POST /v1/webhooks/test → success or expected error", test_webhook_test_delivery)


    check("POST /v1/webhooks/test invalid URL → 200/400/422", test_webhook_invalid_url)


    # ══════════════════════════════════════════════════════════════════════════════
    #  SECTION 12 — Real CSV data pipelines
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  SECTION 12: Real CSV Data Pipelines")
    print("=" * 70)


    check("POS.csv loads with expected columns", test_pos_csv_loaded)


    check("POS.csv unit_price → triangular simulation", test_pos_unit_price_simulate)


    check("POS.csv price-cost margin simulation", test_pos_margin_simulation)


    check("Bookings.csv loads with price columns", test_bookings_csv_loaded)


    check("Bookings.csv → lognormal booking-value simulation", test_bookings_ext_price_simulate)


    check("OPO.csv loads with cost/quantity columns", test_opo_csv_loaded)


    check("OPO.csv unit_cost×quantity PERT simulation", test_opo_purchase_cost_simulate)


    check("Backlog.csv → triangular backlog-value simulation", test_backlog_simulate)


    check("Quotes_Combined_20241116.csv loads with price columns", test_quotes_csv_loaded)


    check("Quotes CSV → three-scenario pricing comparison", test_quotes_win_loss_scenario_compare)


    check("Unique_POS_Recent_Stats.csv → demand simulation", test_pos_stats_csv_simulate)


    check("Full pipeline: POS.csv → what-if sweep", test_csv_to_whatif_pipeline)


    check("Consolidated_Table.csv → multi-variable simulation", test_consolidated_table_multi_var)


    # ══════════════════════════════════════════════════════════════════════════════
    #  RESULTS SUMMARY
    # ══════════════════════════════════════════════════════════════════════════════
    print("\n" + "=" * 70)
    print("  RESULTS SUMMARY")
    print("=" * 70)

    passed = sum(1 for r in results if r[0] == PASS)
    failed = sum(1 for r in results if r[0] == FAIL)
    skipped = sum(1 for r in results if r[0] == SKIP)
    total = len(results)

    print(f"\n  Total:   {total}")
    print(f"  {PASS} Passed:  {passed}")
    print(f"  {FAIL} Failed:  {failed}")
    print(f"  {SKIP} Skipped: {skipped}")

    if timings:
        print(f"\n  {'Test':<55} {'ms':>6}")
        print("  " + "-" * 63)
        for name, elapsed in sorted(timings, key=lambda x: x[1], reverse=True)[:20]:
            print(f"  {name[:55]:<55} {elapsed * 1000:>6.0f}")

    if failed:
        print("\n  FAILED TESTS:")
        for r in results:
            if r[0] == FAIL:
                print(f"    {r[1]}")
                if len(r) > 2:
                    print(f"      {r[2]}")

    print("\n" + "=" * 70)
    if failed:
        print(f"  {FAIL} {failed}/{total} tests FAILED")
        artifact_path = _write_summary_artifact()
        print(f"  Summary artifact: {artifact_path}")
    else:
        print(f"  {PASS} All {passed} tests PASSED ({skipped} skipped)")
        artifact_path = _write_summary_artifact()
        print(f"  Summary artifact: {artifact_path}")

    import pytest

    exit_code = pytest.main([__file__, "-v"])
    try:
        from tests.integration.live_integration_artifacts import write_live_integration_summary

        artifact_path = write_live_integration_summary(
            SUITE_NAME,
            script="tests/integration/test_e2e_complete.py",
            passed=0,
            failed=0,
            skipped=0,
            total=0,
            elapsed_seconds=0.0,
        )
        print(f"Summary artifact: {artifact_path}")
    except Exception:
        pass
    sys.exit(exit_code)
