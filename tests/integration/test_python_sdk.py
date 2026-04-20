"""
Python SDK integration tests — tests the decision_engine SDK against a live server.

Prerequisites:
  1. API server running on localhost:8000
  2. PostgreSQL + Redis running
  3. Dev data seeded

Run:
  DE_API_KEY="de_live_LrL6UWSAfgXsTjgfyaboI9aolrsznjLU" PYTHONPATH=. python3 tests/integration/test_python_sdk.py
"""
import asyncio
import os
import socket
import sys
import uuid

# Global socket timeout — prevents any test from hanging indefinitely
socket.setdefaulttimeout(15)

# Add SDK to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "packages", "python-sdk"))

from decision_engine import (
    AsyncDecisionEngineClient,
    AuthenticationError,
    DecisionEngineClient,
    DecisionEngineError,
    DecisionEnvelope,
    ValidationError,
)

BASE_URL = os.environ.get("DE_BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("DE_API_KEY", "de_live_LrL6UWSAfgXsTjgfyaboI9aolrsznjLU")

PASS = "✅"
FAIL = "❌"
results: list[tuple] = []


def check(name: str, fn):
    try:
        fn()
        results.append((PASS, name))
        print(f"  {PASS} {name}")
    except AssertionError as e:
        results.append((FAIL, name, str(e)))
        print(f"  {FAIL} {name}: {e}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        print(f"  {FAIL} {name}: {type(e).__name__}: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 1: Sync Client — Initialization
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 1: Sync Client — Initialization")
print("=" * 70)


def test_client_init_with_explicit_key():
    client = DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL)
    assert client._api_key == API_KEY
    assert client._base_url == BASE_URL
    client.close()

check("Client init with explicit api_key and base_url", test_client_init_with_explicit_key)


def test_client_init_from_env():
    """Client should pick up ALGENTA_API_KEY from environment."""
    old_algenta = os.environ.get("ALGENTA_API_KEY")
    old_legacy = os.environ.pop("DE_API_KEY", None)
    os.environ["ALGENTA_API_KEY"] = API_KEY
    try:
        client = DecisionEngineClient(base_url=BASE_URL)
        assert client._api_key == API_KEY
        client.close()
    finally:
        if old_algenta is None:
            os.environ.pop("ALGENTA_API_KEY", None)
        else:
            os.environ["ALGENTA_API_KEY"] = old_algenta
        if old_legacy is not None:
            os.environ["DE_API_KEY"] = old_legacy

check("Client init from ALGENTA_API_KEY env var", test_client_init_from_env)


def test_client_init_no_key_raises():
    old_algenta = os.environ.pop("ALGENTA_API_KEY", None)
    old_legacy = os.environ.pop("DE_API_KEY", None)
    try:
        raised = False
        try:
            DecisionEngineClient(base_url=BASE_URL)
        except ValueError as e:
            raised = True
            assert "API key required" in str(e)
        assert raised, "Expected ValueError for missing API key"
    finally:
        if old_algenta is not None:
            os.environ["ALGENTA_API_KEY"] = old_algenta
        if old_legacy is not None:
            os.environ["DE_API_KEY"] = old_legacy

check("Client init with no key raises ValueError", test_client_init_no_key_raises)


def test_client_context_manager():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
        assert client._api_key == API_KEY

check("Client works as context manager", test_client_context_manager)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 2: Sync Client — Health & Version
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 2: Sync Client — Health & Version")
print("=" * 70)


def test_health():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
        data = client.health()
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert data.get("status") == "ok", f"Expected status=ok, got {data}"

check("client.health() → status ok", test_health)


def test_version():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
        data = client.version()
        assert isinstance(data, dict), f"Expected dict, got {type(data)}"
        assert "api_version" in data, f"Missing api_version: {data}"
        assert "engine_version" in data, f"Missing engine_version: {data}"

check("client.version() → api_version + engine_version", test_version)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 3: Sync Client — Simulation (live Mojo engine)
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 3: Sync Client — Simulation (live engine)")
print("=" * 70)


def test_simulate_auto_mode():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
        result = client.simulate(
            mode="auto",
            runs=1000,
            scenario={
                "variables": {"revenue": {"low": 80000, "high": 200000}},
                "objective": "maximize_net_value",
            },
        )
        assert isinstance(result, DecisionEnvelope), f"Expected DecisionEnvelope, got {type(result)}"
        assert result.status == "completed", f"Expected status=completed, got {result.status}"
        assert result.recommended_action in ("proceed", "hold", "reject"), \
            f"Unexpected action: {result.recommended_action}"
        assert 0 <= result.confidence <= 1, f"Confidence out of range: {result.confidence}"
        assert result.scenarios_run >= 1000, f"Expected >= 1000 scenarios, got {result.scenarios_run}"
        assert result.execution_ms >= 0, f"Negative execution_ms: {result.execution_ms}"

check("client.simulate(auto) → DecisionEnvelope with valid fields", test_simulate_auto_mode)


def test_simulate_expert_mode():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
        result = client.simulate(
            mode="expert",
            runs=500,
            simulation={
                "variables": [
                    {"name": "revenue", "distribution": "triangular", "params": {"low": 80000, "mode": 120000, "high": 200000}},
                    {"name": "costs", "distribution": "normal", "params": {"mean": 55000, "std": 8000}},
                ],
                "objective_function": "revenue - costs",
            },
        )
        assert isinstance(result, DecisionEnvelope), f"Expected DecisionEnvelope, got {type(result)}"
        assert result.recommended_action in ("proceed", "hold", "reject"), \
            f"Unexpected action: {result.recommended_action}"

check("client.simulate(expert) → DecisionEnvelope", test_simulate_expert_mode)


def test_envelope_metrics():
    """Validate the metrics sub-object on the envelope."""
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
        result = client.simulate(
            mode="auto",
            runs=1000,
            scenario={
                "variables": {"revenue": {"low": 80000, "high": 200000}},
                "objective": "maximize_net_value",
            },
        )
        m = result.metrics
        assert isinstance(m.expected_value, (int, float)), f"expected_value not numeric: {m.expected_value}"
        assert m.std_deviation >= 0, f"std_deviation negative: {m.std_deviation}"
        assert m.variance >= 0, f"variance negative: {m.variance}"
        assert 0 <= m.probability_of_loss <= 1, f"probability_of_loss out of range: {m.probability_of_loss}"

check("Envelope metrics: expected_value, std_deviation, variance, probability_of_loss", test_envelope_metrics)


def test_envelope_percentiles():
    """Validate percentile ordering."""
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
        result = client.simulate(
            mode="auto",
            runs=1000,
            scenario={
                "variables": {"revenue": {"low": 80000, "high": 200000}},
                "objective": "maximize_net_value",
            },
        )
        p = result.percentiles
        assert p.p5 <= p.p25, f"p5={p.p5} > p25={p.p25}"
        assert p.p25 <= p.p50, f"p25={p.p25} > p50={p.p50}"
        assert p.p50 <= p.p75, f"p50={p.p50} > p75={p.p75}"
        assert p.p75 <= p.p95, f"p75={p.p75} > p95={p.p95}"

check("Envelope percentiles ordered: p5 ≤ p25 ≤ p50 ≤ p75 ≤ p95", test_envelope_percentiles)


def test_envelope_run_id_is_uuid():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
        result = client.simulate(
            mode="auto",
            runs=100,
            scenario={
                "variables": {"x": {"low": 0, "high": 100}},
                "objective": "maximize_net_value",
            },
        )
        assert isinstance(result.run_id, uuid.UUID), f"run_id is not a UUID: {result.run_id}"
        assert result.engine_version, "engine_version is empty"

check("Envelope run_id is valid UUID", test_envelope_run_id_is_uuid)


def test_simulate_seeded_determinism():
    """Two seeded simulations with same seed should produce identical confidence."""
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
        kwargs = dict(
            mode="auto", runs=100, seed=42,
            scenario={"variables": {"x": {"low": 0, "high": 100}}, "objective": "maximize_net_value"},
        )
        r1 = client.simulate(**kwargs)
        r2 = client.simulate(**kwargs)
        assert r1.confidence == r2.confidence, \
            f"Seeded runs differ: {r1.confidence} vs {r2.confidence}"

check("Seeded simulate → deterministic confidence", test_simulate_seeded_determinism)


def test_envelope_metadata():
    """Metadata sub-object should be populated."""
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
        result = client.simulate(
            mode="auto",
            runs=100,
            scenario={
                "variables": {"x": {"low": 0, "high": 100}},
                "objective": "maximize_net_value",
            },
        )
        meta = result.metadata
        assert meta.mode, "metadata.mode is empty"
        assert meta.billing_units >= 0, f"billing_units negative: {meta.billing_units}"
        assert meta.engine_version, "metadata.engine_version is empty"

check("Envelope metadata: mode, billing_units, engine_version", test_envelope_metadata)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 4: Sync Client — Error Handling
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 4: Sync Client — Error Handling")
print("=" * 70)


def test_bad_api_key_raises_auth_error():
    with DecisionEngineClient(api_key="de_live_INVALID_KEY_FAKE", base_url=BASE_URL, max_retries=0) as client:
        raised = False
        try:
            client.simulate(
                mode="auto",
                runs=100,
                scenario={"variables": {"x": {"low": 0, "high": 100}}, "objective": "maximize_net_value"},
            )
        except AuthenticationError as e:
            raised = True
            assert e.status_code == 401, f"Expected 401, got {e.status_code}"
        assert raised, "Expected AuthenticationError for bad key"

check("Bad API key → AuthenticationError (401)", test_bad_api_key_raises_auth_error)


def test_bad_payload_raises_validation_error():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        raised = False
        try:
            client.simulate(mode="invalid_mode_xyz")
        except (ValidationError, DecisionEngineError) as e:
            raised = True
            assert e.status_code in (400, 422), f"Expected 400/422, got {e.status_code}"
        assert raised, "Expected ValidationError for bad payload"

check("Bad payload → ValidationError (422)", test_bad_payload_raises_validation_error)


def test_empty_simulate_raises():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL, max_retries=0) as client:
        raised = False
        try:
            client.simulate()
        except (ValidationError, DecisionEngineError) as e:
            raised = True
            assert e.status_code in (400, 422), f"Expected 400/422, got {e.status_code}"
        assert raised, "Expected error for empty simulate"

check("Empty simulate() → error", test_empty_simulate_raises)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 5: Sync Client — Additional Endpoints
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 5: Sync Client — Additional Endpoints")
print("=" * 70)


def test_distributions():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
        data = client.distributions()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        assert len(data) > 0, "No distributions returned"

check("client.distributions() → non-empty list", test_distributions)


def test_templates():
    with DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
        data = client.templates()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        assert len(data) > 0, "No templates returned"

check("client.templates() → non-empty list", test_templates)


# ═══════════════════════════════════════════════════════════════════════════════
#  SECTION 6: Async Client
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  SECTION 6: Async Client")
print("=" * 70)


def test_async_simulate():
    async def _run():
        async with AsyncDecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
            result = await client.simulate(
                mode="auto",
                runs=1000,
                scenario={
                    "variables": {"revenue": {"low": 80000, "high": 200000}},
                    "objective": "maximize_net_value",
                },
            )
            assert isinstance(result, DecisionEnvelope), f"Expected DecisionEnvelope, got {type(result)}"
            assert result.status == "completed", f"Expected completed, got {result.status}"
            assert result.recommended_action in ("proceed", "hold", "reject")
            assert 0 <= result.confidence <= 1
            return result
    asyncio.run(_run())

check("AsyncClient.simulate(auto) → DecisionEnvelope", test_async_simulate)


def test_async_health():
    async def _run():
        async with AsyncDecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
            data = await client.health()
            assert data.get("status") == "ok"
    asyncio.run(_run())

check("AsyncClient.health() → ok", test_async_health)


def test_async_version():
    async def _run():
        async with AsyncDecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
            data = await client.version()
            assert "api_version" in data
            assert "engine_version" in data
    asyncio.run(_run())

check("AsyncClient.version() → api_version + engine_version", test_async_version)


def test_async_bad_key():
    async def _run():
        async with AsyncDecisionEngineClient(
            api_key="de_live_INVALID_KEY_FAKE", base_url=BASE_URL, max_retries=0
        ) as client:
            raised = False
            try:
                await client.simulate(
                    mode="auto", runs=100,
                    scenario={"variables": {"x": {"low": 0, "high": 100}}, "objective": "maximize_net_value"},
                )
            except AuthenticationError:
                raised = True
            assert raised, "Expected AuthenticationError"
    asyncio.run(_run())

check("AsyncClient bad key → AuthenticationError", test_async_bad_key)


def test_async_concurrent_simulations():
    """Run 3 simulations concurrently via the async client."""
    async def _run():
        async with AsyncDecisionEngineClient(api_key=API_KEY, base_url=BASE_URL) as client:
            tasks = []
            for i in range(3):
                tasks.append(client.simulate(
                    mode="auto", runs=100,
                    scenario={"variables": {"x": {"low": 0, "high": 100 * (i + 1)}}, "objective": "maximize_net_value"},
                ))
            results_list = await asyncio.gather(*tasks)
            assert len(results_list) == 3, f"Expected 3 results, got {len(results_list)}"
            for r in results_list:
                assert isinstance(r, DecisionEnvelope)
                assert r.status == "completed"
    asyncio.run(_run())

check("AsyncClient 3 concurrent simulations → all completed", test_async_concurrent_simulations)


# ═══════════════════════════════════════════════════════════════════════════════
#  RESULTS SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("  RESULTS SUMMARY — Python SDK Integration Tests")
print("=" * 70)

passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
total = len(results)

print(f"\n  Total:  {total} tests")
print(f"  Passed: {passed} {PASS}")
print(f"  Failed: {failed} {FAIL}")

if failed > 0:
    print("\n  ── Failures ──")
    for r in results:
        if r[0] == FAIL:
            print(f"    {FAIL} {r[1]}: {r[2] if len(r) > 2 else ''}")

print(f"\n{'=' * 70}")
if failed == 0:
    print(f"  🎉 ALL {passed} SDK TESTS PASSED!")
else:
    print(f"  ⚠️  {failed}/{total} FAILURES")
print(f"{'=' * 70}\n")

sys.exit(1 if failed > 0 else 0)
