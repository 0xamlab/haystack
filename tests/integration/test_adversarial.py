"""
tests/integration/test_adversarial.py

Failure injection & adversarial input test suite for the Decision Engine.

Tests graceful degradation when inputs are:
  - Missing required columns
  - Empty datasets
  - Extreme outliers (values 1000x normal)
  - Contradictory data (all rows identical, revenue < cost)
  - Malformed simulation requests (impossible distributions, negative std)
  - Non-existent sources / columns
  - Edge-case numeric inputs (NaN proxies, zero values, negative revenue)
  - Unicode column names
  - Truncated CSV (partial row at end)
  - Very large column count (wide schema)

Run standalone:
    pytest tests/integration/test_adversarial.py -v -s

No ANTHROPIC_API_KEY needed — these are pure API-layer tests.
"""

from __future__ import annotations

import csv
import io
import os

# ── App setup (mirrors test_mcp_100_questions.py) ────────────────────────────
import sys
import tempfile
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx
from tests.integration.live_capacity_blockers import classify_simulation_capacity_blocker
from tests.integration.live_local_defaults import configured_local_live_base_url, resolve_local_live_api_key, resolve_local_live_base_url

DE_API_KEY = resolve_local_live_api_key()


class _MockRedis:
    """Minimal Redis stub — rate-limit and quota checks pass silently."""

    async def incr(self, *a, **kw):
        return 1

    async def expire(self, *a, **kw):
        pass

    async def get(self, *a, **kw):
        return b"0"  # non-None bypasses cold-start DB seed

    async def set(self, *a, **kw):
        pass

    async def setex(self, *a, **kw):
        pass

    async def incrby(self, *a, **kw):
        return 1

    async def ping(self, *a, **kw):
        return True

    async def hgetall(self, *a, **kw):
        return {}

    async def hset(self, *a, **kw):
        pass

    async def aclose(self):
        pass


def _build_test_app():
    import uuid as _uuid

    from apps.api_server.main import app
    from apps.api_server.middleware.auth import get_current_org, get_redis
    from apps.api_server.routers import query as query_router
    from apps.api_server.services import source_registry as reg
    from apps.api_server.services.auth_service import AuthContext

    test_org = AuthContext(
        org_id=_uuid.UUID("00000000-0000-0000-0000-000000000001"),
        key_id=_uuid.UUID("00000000-0000-0000-0000-000000000002"),
        plan="pro",
        role="owner",
        email="test@decision-engine.io",
        is_platform=False,
        workspace_id=None,
    )

    async def _fake_auth() -> AuthContext:
        return test_org

    async def _fake_redis() -> _MockRedis:
        return _MockRedis()

    sources_dir = Path(tempfile.mkdtemp(prefix="algenta-adversarial-sources-"))
    os.environ["ALGENTA_SOURCES_DIR"] = str(sources_dir)
    reg._SOURCES_DIR = sources_dir
    query_router._SOURCE_CACHE.clear()

    app.dependency_overrides[get_current_org] = _fake_auth
    app.dependency_overrides[get_redis] = _fake_redis
    return app


def _client():
    app = _build_test_app()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={
            "Authorization": f"Bearer {DE_API_KEY}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


# ── Fixtures / helpers ────────────────────────────────────────────────────────


def _minimal_csv(rows: list[dict]) -> str:
    if not rows:
        return "col_a,col_b\n"
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def _simulate_body(low: float, high: float, runs: int = 1000) -> dict:
    return {
        "mode": "auto",
        "scenario": {
            "variables": {"revenue": {"low": low, "high": high}},
            "objective": "maximize_net_value",
        },
        "runs": runs,
    }


def _skip_if_simulation_capacity_blocked(resp: httpx.Response) -> None:
    blocked_reason = classify_simulation_capacity_blocker(
        status=resp.status_code,
        payload=resp.json() if "application/json" in resp.headers.get("content-type", "") else None,
        text=resp.text,
    )
    if blocked_reason:
        pytest.skip(blocked_reason)


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 1: Query endpoint — malformed / missing source
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_query_nonexistent_source_id():
    """Querying a source_id that was never registered returns a clear error, not a 500."""
    async with _client() as c:
        resp = await c.post(
            "/v1/query",
            json={
                "sources": [{"name": "ghost", "source_id": "nonexistent_source_id_xyz"}],
                "metric": {"role": "derived_measure"},
                "aggregation": "sum",
            },
        )
    # Should be 400 (bad input) or 404, never 500
    assert resp.status_code in (400, 404, 422), (
        f"Expected 4xx for nonexistent source, got {resp.status_code}: {resp.text[:200]}"
    )


@pytest.mark.anyio
async def test_query_empty_csv():
    """CSV with header row but zero data rows should return 0 or empty result, not crash."""
    async with _client() as c:
        resp = await c.post(
            "/v1/query",
            json={
                "sources": [{"name": "empty", "csv": "revenue,cost\n"}],
                "metric": {"role": "derived_measure", "hint": "revenue"},
                "aggregation": "sum",
            },
        )
    assert resp.status_code in (200, 400), f"Unexpected {resp.status_code}: {resp.text[:200]}"
    if resp.status_code == 200:
        data = resp.json()
        # Result should be 0 or null, not a nonsense number
        result = data.get("result")
        assert result is None or result == 0 or result == 0.0, (
            f"Expected 0 or null for empty CSV, got {result}"
        )


@pytest.mark.anyio
async def test_query_missing_numeric_column():
    """Query for a numeric metric when the CSV has only string columns."""
    async with _client() as c:
        resp = await c.post(
            "/v1/query",
            json={
                "sources": [{"name": "strings_only", "csv": "name,category\nalice,A\nbob,B\n"}],
                "metric": {"role": "derived_measure", "hint": "revenue"},
                "aggregation": "sum",
            },
        )
    # Must not 500. Either 200 with low confidence or 400.
    assert resp.status_code in (200, 400), f"Unexpected {resp.status_code}: {resp.text[:200]}"
    if resp.status_code == 200:
        data = resp.json()
        conf = data.get("confidence", 1.0)
        assert conf < 0.8, f"Should have low confidence for all-string source, got {conf}"


@pytest.mark.anyio
async def test_query_extreme_outlier_values():
    """Extreme outliers (1e12) should not crash the engine — outliers are data, not errors."""
    rows = [
        {"revenue": 1_000_000_000_000.0, "cost": 500_000_000_000.0},  # 1 trillion
        {"revenue": 100.0, "cost": 50.0},
        {"revenue": 200.0, "cost": 80.0},
    ]
    async with _client() as c:
        resp = await c.post(
            "/v1/query",
            json={
                "sources": [{"name": "outliers", "records": rows}],
                "metric": {"role": "derived_measure", "hint": "revenue"},
                "aggregation": "sum",
            },
        )
    # Must not crash (500) — 200 with low confidence or 400 are both acceptable
    assert resp.status_code in (200, 400), (
        f"Outliers caused crash {resp.status_code}: {resp.text[:200]}"
    )
    if resp.status_code == 200:
        data = resp.json()
        result = data.get("result")
        # If a result is returned, it must include the outlier in the sum
        if result is not None:
            assert result > 1e11, f"Sum should include the 1T outlier, got {result}"


@pytest.mark.anyio
async def test_query_all_zero_values():
    """All-zero numeric column: sum=0, avg=0 — not a crash."""
    rows = [{"revenue": 0.0, "cost": 0.0} for _ in range(10)]
    async with _client() as c:
        resp = await c.post(
            "/v1/query",
            json={
                "sources": [{"name": "zeros", "records": rows}],
                "metric": {"role": "derived_measure", "hint": "revenue"},
                "aggregation": "avg",
            },
        )
    assert resp.status_code == 200, f"Zero values caused {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    assert data.get("result") == 0.0 or data.get("result") is None


@pytest.mark.anyio
async def test_query_all_negative_revenue():
    """All-negative revenue (all transactions at a loss) is valid data, not an error."""
    rows = [{"revenue": -100.0 * i, "cost": 50.0 * i} for i in range(1, 6)]
    async with _client() as c:
        resp = await c.post(
            "/v1/query",
            json={
                "sources": [{"name": "losses", "records": rows}],
                "metric": {"role": "derived_measure", "hint": "revenue"},
                "aggregation": "sum",
            },
        )
    assert resp.status_code == 200, f"Negative revenue caused {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    result = data.get("result")
    # When Mojo engine is unavailable schema resolution may return None — that's acceptable.
    # When it is available the sum of all-negative revenue must be negative.
    assert result is None or result < 0, f"Expected negative sum or None, got {result}"


@pytest.mark.anyio
async def test_query_unicode_column_names():
    """Column names with Unicode characters should be handled without crashing."""
    rows = [
        {"rëvénue": 500.0, "cöst": 200.0},
        {"rëvénue": 800.0, "cöst": 300.0},
    ]
    async with _client() as c:
        resp = await c.post(
            "/v1/query",
            json={
                "sources": [{"name": "unicode_cols", "records": rows}],
                "metric": {"role": "derived_measure", "hint": "revenue"},
                "aggregation": "sum",
            },
        )
    # Must not 500
    assert resp.status_code in (200, 400), (
        f"Unicode columns caused {resp.status_code}: {resp.text[:200]}"
    )


@pytest.mark.anyio
async def test_query_single_row():
    """Single-row dataset — statistics are degenerate but the engine must not crash."""
    async with _client() as c:
        resp = await c.post(
            "/v1/query",
            json={
                "sources": [{"name": "one_row", "records": [{"revenue": 1234.56, "cost": 500.0}]}],
                "metric": {"role": "derived_measure", "hint": "revenue"},
                "aggregation": "sum",
            },
        )
    assert resp.status_code == 200, f"Single row caused {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    result = data.get("result")
    # Without Mojo engine schema resolution may return None — acceptable in CI.
    if result is not None:
        assert abs(result - 1234.56) < 0.01, f"Expected ~1234.56, got {result}"


@pytest.mark.anyio
async def test_query_wide_schema_many_columns():
    """100-column schema: engine should pick the right metric column, not crash."""
    row = {f"col_{i}": float(i) for i in range(100)}
    row["net_sales"] = 9999.0
    async with _client() as c:
        resp = await c.post(
            "/v1/query",
            json={
                "sources": [{"name": "wide", "records": [row, row, row]}],
                "metric": {"role": "derived_measure", "hint": "net_sales"},
                "aggregation": "sum",
            },
        )
    # Must not crash — resolver may return None for wide schemas (acceptable)
    assert resp.status_code in (200, 400), (
        f"Wide schema caused crash {resp.status_code}: {resp.text[:200]}"
    )
    if resp.status_code == 200:
        data = resp.json()
        result = data.get("result")
        # If net_sales was found: 3 rows × 9999 = 29997
        if result is not None:
            assert abs(result - 29997.0) < 1.0, f"Expected ~29997 from wide schema, got {result}"


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 2: Simulation endpoint — invalid distributions and edge cases
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_simulate_low_equals_high():
    """low == high: degenerate distribution — engine validates strictly (422) or runs (200). Never 500."""
    async with _client() as c:
        resp = await c.post("/v1/simulate", json=_simulate_body(50_000.0, 50_000.0))
    # Either strict validation (422) or degenerate run (200) is acceptable.
    # What's NOT acceptable: server crash (500) or hanging.
    assert resp.status_code in (200, 422), (
        f"low==high caused unexpected {resp.status_code}: {resp.text[:200]}"
    )
    if resp.status_code == 200:
        data = resp.json()
        ev = data["metrics"]["expected_value"]
        assert abs(ev - 50_000.0) < 1.0, f"Expected EV≈50000 for degenerate dist, got {ev}"


@pytest.mark.anyio
async def test_simulate_low_greater_than_high():
    """low > high: invalid range — should return 422 validation error, not 500."""
    async with _client() as c:
        resp = await c.post("/v1/simulate", json=_simulate_body(200_000.0, 100_000.0))
    # Should be caught at validation (422) or by engine (400), never 500
    assert resp.status_code in (400, 422), (
        f"low>high should fail validation, got {resp.status_code}: {resp.text[:200]}"
    )


@pytest.mark.anyio
async def test_simulate_zero_scenarios():
    """runs=0: zero iterations — should fail validation, not hang."""
    body = _simulate_body(50_000.0, 200_000.0)
    body["runs"] = 0
    async with _client() as c:
        resp = await c.post("/v1/simulate", json=body)
    assert resp.status_code in (400, 422), (
        f"runs=0 should fail validation, got {resp.status_code}: {resp.text[:200]}"
    )


@pytest.mark.anyio
async def test_simulate_extremely_large_range():
    """Revenue range spanning 15 orders of magnitude — no overflow crash."""
    async with _client() as c:
        resp = await c.post("/v1/simulate", json=_simulate_body(1.0, 1_000_000_000_000.0))
    _skip_if_simulation_capacity_blocked(resp)
    assert resp.status_code == 200, f"Extreme range caused {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    assert "metrics" in data
    assert "expected_value" in data["metrics"]


@pytest.mark.anyio
async def test_simulate_negative_revenue_range():
    """Negative revenue range (all losses) — must produce valid result with PoL=1.0."""
    async with _client() as c:
        resp = await c.post("/v1/simulate", json=_simulate_body(-200_000.0, -50_000.0))
    _skip_if_simulation_capacity_blocked(resp)
    assert resp.status_code == 200, f"Negative range caused {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    pol = data["metrics"]["probability_of_loss"]
    assert pol > 0.95, f"All-loss scenario should have PoL≈1.0, got {pol}"


@pytest.mark.anyio
async def test_simulate_decision_plan_present():
    """Every simulate response must include a populated decision_plan field."""
    async with _client() as c:
        resp = await c.post("/v1/simulate", json=_simulate_body(80_000.0, 200_000.0))
    _skip_if_simulation_capacity_blocked(resp)
    assert resp.status_code == 200
    data = resp.json()
    dp = data.get("decision_plan")
    assert dp is not None, "decision_plan must always be present in simulate response"
    assert "recommended_action" in dp
    assert "expected_value" in dp
    assert "risk" in dp
    assert "p5" in dp["risk"]
    assert "p95" in dp["risk"]
    assert "probability_of_loss" in dp["risk"]
    assert "options" in dp
    assert len(dp["options"]) >= 1
    assert "rationale" in dp


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 3: Recommend endpoint — edge cases
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_recommend_decision_plan_has_all_options():
    """Recommend response decision_plan.options must contain every ranked action."""
    body = {
        "actions": [
            {"name": "expand", "request": _simulate_body(100_000.0, 250_000.0)},
            {"name": "stay", "request": _simulate_body(80_000.0, 120_000.0)},
            {"name": "close", "request": _simulate_body(10_000.0, 30_000.0)},
        ],
        "runs": 1000,
    }
    async with _client() as c:
        resp = await c.post("/v1/recommend", json=body)
    _skip_if_simulation_capacity_blocked(resp)
    assert resp.status_code == 200, f"recommend failed: {resp.status_code}: {resp.text[:200]}"
    data = resp.json()
    dp = data.get("decision_plan")
    assert dp is not None, "decision_plan must be present in recommend response"
    assert len(dp["options"]) == 3, f"Expected 3 options in decision_plan, got {len(dp['options'])}"
    option_names = {o["name"] for o in dp["options"]}
    assert option_names == {"expand", "stay", "close"}
    # Options must be ranked 1, 2, 3
    ranks = sorted(o["rank"] for o in dp["options"])
    assert ranks == [1, 2, 3]


@pytest.mark.anyio
async def test_recommend_identical_options():
    """Two actions with identical parameters — engine must still return a valid recommendation."""
    same = _simulate_body(100_000.0, 200_000.0)
    body = {
        "actions": [
            {"name": "option_a", "request": same},
            {"name": "option_b", "request": same},
        ],
        "runs": 1000,
    }
    async with _client() as c:
        resp = await c.post("/v1/recommend", json=body)
    _skip_if_simulation_capacity_blocked(resp)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("recommended_action") in ("option_a", "option_b")


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 4: Source registration — malformed inputs
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_register_source_empty_csv():
    """Registering a source with header-only CSV should return an error, not crash."""
    async with _client() as c:
        resp = await c.post(
            "/v1/sources/register",
            json={
                "source": {"name": "empty_source", "csv": "col_a,col_b\n"},
            },
        )
    # Engine should reject (400) or return a minimal schema — never 500
    assert resp.status_code in (200, 400, 422), (
        f"Empty CSV registration caused {resp.status_code}: {resp.text[:200]}"
    )


@pytest.mark.anyio
async def test_register_source_malformed_csv():
    """CSV with mismatched column counts should not crash the registration."""
    bad_csv = "col_a,col_b,col_c\n1,2\n3,4,5,6\n"  # rows have wrong column counts
    async with _client() as c:
        resp = await c.post(
            "/v1/sources/register",
            json={
                "source": {"name": "malformed", "csv": bad_csv},
            },
        )
    assert resp.status_code in (200, 400, 422), (
        f"Malformed CSV caused {resp.status_code}: {resp.text[:200]}"
    )


@pytest.mark.anyio
async def test_register_source_single_column():
    """Single numeric column — minimal valid source. Should register cleanly."""
    csv_data = "revenue\n100\n200\n300\n400\n500\n"
    async with _client() as c:
        resp = await c.post(
            "/v1/sources/register",
            json={
                "source": {"name": "single_col", "csv": csv_data},
            },
        )
    assert resp.status_code == 200, (
        f"Single-column source failed: {resp.status_code}: {resp.text[:200]}"
    )
    data = resp.json()
    assert data.get("source_id") is not None


@pytest.mark.anyio
async def test_register_source_duplicate_is_idempotent():
    """Registering the same CSV twice returns the same source_id — idempotent."""
    csv_data = "x,y\n1,2\n3,4\n5,6\n"
    async with _client() as c:
        r1 = await c.post(
            "/v1/sources/register", json={"source": {"name": "dup_test", "csv": csv_data}}
        )
        r2 = await c.post(
            "/v1/sources/register", json={"source": {"name": "dup_test", "csv": csv_data}}
        )

    assert r1.status_code == 200
    assert r2.status_code == 200
    id1 = r1.json().get("source_id")
    id2 = r2.json().get("source_id")
    assert id1 == id2, f"Duplicate registration returned different IDs: {id1} vs {id2}"


# ═══════════════════════════════════════════════════════════════════════════════
# GROUP 5: Decision Memory
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.mark.anyio
async def test_decision_memory_roundtrip():
    """Log a decision → retrieve it → record outcome → verify delta."""
    async with _client() as c:
        # 1. Log
        log_resp = await c.post(
            "/v1/decisions",
            json={
                "chosen_action": "expand_downtown",
                "context": "Q4 board review: expand or hold?",
                "options_considered": ["expand_downtown", "hold", "close_airport"],
                "expected_value": 75_000.0,
                "confidence": 0.82,
                "rationale": "EV highest, PoL lowest of 3 options.",
                "risk_p5": 15_000.0,
                "risk_p95": 150_000.0,
                "risk_pol": 0.08,
            },
        )
        assert log_resp.status_code == 201, f"log failed: {log_resp.text[:200]}"
        decision = log_resp.json()
        decision_id = decision["id"]
        assert decision_id is not None
        assert decision["chosen_action"] == "expand_downtown"
        assert decision["actual_outcome"] is None

        # 2. Retrieve
        get_resp = await c.get(f"/v1/decisions/{decision_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["chosen_action"] == "expand_downtown"

        # 3. Record outcome
        outcome_resp = await c.patch(
            f"/v1/decisions/{decision_id}/outcome",
            json={
                "actual_outcome": 68_000.0,
                "outcome_notes": "Revenue softer than expected due to construction next door.",
            },
        )
        assert outcome_resp.status_code == 200
        outcome = outcome_resp.json()
        assert outcome["actual_outcome"] == 68_000.0
        assert abs(outcome["outcome_delta"] - (68_000.0 - 75_000.0)) < 0.01  # Δ = -7000

        # 4. Verify in list
        list_resp = await c.get("/v1/decisions?with_outcome_only=true")
        assert list_resp.status_code == 200
        ids = [d["id"] for d in list_resp.json()["decisions"]]
        assert decision_id in ids


@pytest.mark.anyio
async def test_decision_memory_not_found():
    """GET /v1/decisions/{id} with fake ID returns 404."""
    fake_id = str(uuid.uuid4())
    async with _client() as c:
        resp = await c.get(f"/v1/decisions/{fake_id}")
    assert resp.status_code == 404


if __name__ == "__main__":
    import asyncio

    async def _run():
        tests = [
            test_query_nonexistent_source_id,
            test_query_empty_csv,
            test_query_missing_numeric_column,
            test_query_extreme_outlier_values,
            test_query_all_zero_values,
            test_query_all_negative_revenue,
            test_query_unicode_column_names,
            test_query_single_row,
            test_query_wide_schema_many_columns,
            test_simulate_low_equals_high,
            test_simulate_low_greater_than_high,
            test_simulate_zero_scenarios,
            test_simulate_extremely_large_range,
            test_simulate_negative_revenue_range,
            test_simulate_decision_plan_present,
            test_recommend_decision_plan_has_all_options,
            test_recommend_identical_options,
            test_register_source_empty_csv,
            test_register_source_malformed_csv,
            test_register_source_single_column,
            test_register_source_duplicate_is_idempotent,
            test_decision_memory_roundtrip,
            test_decision_memory_not_found,
        ]
        passed = 0
        failed = 0
        skipped = 0
        for test_fn in tests:
            name = test_fn.__name__
            try:
                await test_fn()
                print(f"  ✓ {name}")
                passed += 1
            except pytest.skip.Exception as exc:
                print(f"  ⏭️ {name}: {exc}")
                skipped += 1
            except Exception as exc:
                print(f"  ✗ {name}: {exc}")
                failed += 1
        print(f"\n  {passed}/{len(tests)} passed — {skipped} skipped — {failed} failures")

    asyncio.run(_run())
