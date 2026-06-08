"""
Quick diagnostic script — runs all checks without pytest.
Run from project root: python3 scripts/run_diagnostics.py
"""

import os
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from apps.platform_contract_constants import API_KEY_PREFIX_LIVE

PASS = "✅"  # noqa: S105
FAIL = "❌"
WARN = "⚠️ "

results = []


def check(name, fn):
    try:
        fn()
        results.append((PASS, name))
        print(f"{PASS} {name}")
    except Exception as e:
        results.append((FAIL, name, str(e)))
        print(f"{FAIL} {name}: {e}")
        traceback.print_exc()
        print()


# ── 1. Python engine import ───────────────────────────────────────────────────
def test_engine_import():
    from mojo.bindings.python_adapter import run_simulation  # noqa: F401


check("mojo.bindings.python_adapter imports", test_engine_import)


# ── 2. Engine runs ────────────────────────────────────────────────────────────
def test_engine_runs():
    from mojo.bindings.python_adapter import run_simulation

    result = run_simulation(
        {
            "runs": 1000,
            "seed": 42,
            "variables": [
                {"name": "x", "distribution": "normal", "params": {"mean": 100, "std": 10}}
            ],
            "objective_function": "x",
        }
    )
    assert result["scenarios_run"] == 1000
    assert "summary" in result
    assert "percentiles" in result
    assert "risk" in result
    assert result["percentiles"]["p5"] < result["percentiles"]["p95"]


check("Monte Carlo engine runs 1000 iterations", test_engine_runs)


# ── 3. Determinism ────────────────────────────────────────────────────────────
def test_determinism():
    from mojo.bindings.python_adapter import run_simulation

    payload = {
        "runs": 500,
        "seed": 42,
        "variables": [{"name": "x", "distribution": "normal", "params": {"mean": 100, "std": 10}}],
        "objective_function": "x",
    }
    r1 = run_simulation(payload)
    r2 = run_simulation(payload)
    assert r1["summary"]["mean"] == r2["summary"]["mean"], "Seed produces different results!"


check("Engine is deterministic with same seed", test_determinism)


# ── 4. Pydantic schemas import ────────────────────────────────────────────────
def test_schemas_import():
    from apps.api_server.schemas.common import ErrorResponse  # noqa: F401
    from apps.api_server.schemas.response import DecisionEnvelope  # noqa: F401
    from apps.api_server.schemas.simulate import (  # noqa: F401
        SimulateRequestAuto,
        SimulateRequestExpert,
    )


check("apps.api_server.schemas imports", test_schemas_import)


# ── 5. Auto mode schema validates ─────────────────────────────────────────────
def test_auto_schema():
    from apps.api_server.schemas.simulate import SimulateRequestAuto

    req = SimulateRequestAuto.model_validate(
        {
            "mode": "auto",
            "scenario": {
                "variables": {
                    "revenue": {"low": 80000, "high": 200000},
                    "cost": {"low": 40000, "high": 90000},
                },
                "objective": "maximize_net_value",
            },
        }
    )
    assert req.mode == "auto"
    assert req.runs == 10000


check("Auto mode SimulateRequest validates", test_auto_schema)


# ── 6. Expert mode schema validates ───────────────────────────────────────────
def test_expert_schema():
    from apps.api_server.schemas.simulate import SimulateRequestExpert

    req = SimulateRequestExpert.model_validate(
        {
            "mode": "expert",
            "simulation": {
                "variables": [
                    {
                        "name": "revenue",
                        "distribution": "normal",
                        "params": {"mean": 100000, "std": 20000},
                    },
                ],
            },
            "seed": 42,
        }
    )
    assert req.seed == 42


check("Expert mode SimulateRequest validates", test_expert_schema)


# ── 7. Auth service imports ───────────────────────────────────────────────────
def test_auth_import():
    from apps.api_server.services.auth_service import generate_api_key, hash_api_key  # noqa: F401


check("apps.api_server.services.auth_service imports", test_auth_import)


# ── 8. API key generation ─────────────────────────────────────────────────────
def test_key_generation():
    from apps.api_server.services.auth_service import generate_api_key, hash_api_key

    raw, prefix, hashed = generate_api_key()
    assert raw.startswith(API_KEY_PREFIX_LIVE), (
        f"Key should start with {API_KEY_PREFIX_LIVE}, got: {raw[:12]}"
    )
    assert len(hashed) == 64, f"SHA-256 should be 64 chars, got: {len(hashed)}"
    assert hash_api_key(raw) == hashed, "Hash of raw key must match generated hash"


check("API key generation and hashing", test_key_generation)


# ── 9. FastAPI app imports ────────────────────────────────────────────────────
def test_fastapi_import():
    from apps.api_server.main import app  # noqa: F401


check("apps.api_server.main (FastAPI app) imports", test_fastapi_import)


# ── 10. Models import ─────────────────────────────────────────────────────────
def test_models_import():
    from apps.api_server.models.api_key import APIKey  # noqa: F401
    from apps.api_server.models.organization import Organization  # noqa: F401
    from apps.api_server.models.simulation_run import SimulationRun  # noqa: F401
    from apps.api_server.models.user import User  # noqa: F401


check("Database models import", test_models_import)

# ── Summary ───────────────────────────────────────────────────────────────────
print()
print("=" * 60)
passed = sum(1 for r in results if r[0] == PASS)
failed = sum(1 for r in results if r[0] == FAIL)
print(f"Results: {passed} passed, {failed} failed out of {len(results)} checks")
if failed == 0:
    print("🚀 All checks passed! Run: python3 -m pytest tests/unit/ -v")
else:
    print("Fix the failures above before running pytest")
    sys.exit(1)
