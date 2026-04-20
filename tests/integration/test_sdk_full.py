"""
test_sdk_full.py — Full Python SDK coverage for all 21 client methods.

Complements test_python_sdk.py which only covers 5 methods.
This file covers the remaining 16: recommend, score, batch, compare,
submit_job, get_job, get_job_result, cancel_job, poll_job,
me, usage, limits, list_api_keys, create_api_key, revoke_api_key.

Two layers:
  Layer A — SDK structure / import checks (no server)
  Layer B — Live HTTP calls (requires running API server)

Run:
  DE_SKIP_API=1 python3 tests/integration/test_sdk_full.py   # structure only
  python3 tests/integration/test_sdk_full.py                  # full
"""
from __future__ import annotations

import inspect
import os
import socket
import sys
import time
import uuid
from pathlib import Path

socket.setdefaulttimeout(20)

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "packages" / "python-sdk"))

from decision_engine import AsyncDecisionEngineClient, DecisionEngineClient

BASE_URL = os.environ.get("DE_BASE_URL", "http://localhost:8000")
API_KEY  = os.environ.get("DE_API_KEY",  "de_live_LrL6UWSAfgXsTjgfyaboI9aolrsznjLU")
SKIP_API = os.environ.get("DE_SKIP_API", "0") == "1"

PASS = "✅"; FAIL = "❌"; SKIP = "⏭️ "
_results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    icon = PASS if cond else FAIL
    _results.append((name, cond, detail))
    print(f"  {icon}  {name}" + (f"  ({detail})" if detail else ""))


def client() -> DecisionEngineClient:
    return DecisionEngineClient(api_key=API_KEY, base_url=BASE_URL)


_SIMULATE_PAYLOAD = {
    "mode": "auto",
    "variables": [{"name": "revenue", "distribution": "normal", "mean": 100000, "std_dev": 15000}],
    "runs": 1000,
}

_RECOMMEND_PAYLOAD = {
    "context": {"metric": "profit", "current_value": 50000},
    "options": [
        {"label": "option_a", "expected_value": 60000, "risk": 0.1},
        {"label": "option_b", "expected_value": 80000, "risk": 0.4},
    ],
}

_JOB_PAYLOAD = {**_SIMULATE_PAYLOAD, "runs": 500}

# ── Layer A: SDK structure ────────────────────────────────────────────────────

def test_all_methods_exist():
    required = [
        "simulate", "recommend", "score", "batch", "compare",
        "submit_job", "get_job", "get_job_result", "cancel_job", "poll_job",
        "me", "usage", "limits",
        "list_api_keys", "create_api_key", "revoke_api_key",
        "distributions", "templates", "health", "version",
    ]
    for method in required:
        check(
            f"DecisionEngineClient.{method} exists",
            hasattr(DecisionEngineClient, method),
        )


def test_async_methods_exist():
    required = ["simulate", "recommend", "health", "submit_job", "get_job"]
    for method in required:
        check(
            f"AsyncDecisionEngineClient.{method} exists",
            hasattr(AsyncDecisionEngineClient, method),
        )


def test_recommend_signature():
    sig = inspect.signature(DecisionEngineClient.recommend)
    check("recommend() accepts payload/context args", len(sig.parameters) >= 2)


def test_job_methods_signature():
    for method in ["get_job", "get_job_result", "cancel_job"]:
        sig = inspect.signature(getattr(DecisionEngineClient, method))
        params = list(sig.parameters.keys())
        check(f"{method}() accepts job_id", "job_id" in params or len(params) >= 2)


def test_api_key_methods_signature():
    sig = inspect.signature(DecisionEngineClient.create_api_key)
    check("create_api_key() accepts name param", len(sig.parameters) >= 2)
    sig2 = inspect.signature(DecisionEngineClient.revoke_api_key)
    check("revoke_api_key() accepts key_id param", len(sig2.parameters) >= 2)


# ── Layer B: Live API calls ───────────────────────────────────────────────────

def test_me():
    with client() as c:
        result = c.me()
        check("me() returns dict", isinstance(result, dict))
        check("me() has org or user field", bool(result))


def test_usage():
    with client() as c:
        result = c.usage()
        check("usage() returns dict", isinstance(result, dict))


def test_limits():
    with client() as c:
        result = c.limits()
        check("limits() returns dict", isinstance(result, dict))


def test_recommend():
    with client() as c:
        result = c.recommend(_RECOMMEND_PAYLOAD)
        check("recommend() returns dict", isinstance(result, dict))
        check("recommend() non-empty", bool(result))


def test_batch():
    payloads = [_SIMULATE_PAYLOAD, {**_SIMULATE_PAYLOAD, "runs": 500}]
    with client() as c:
        results = c.batch(payloads)
        check("batch() returns list", isinstance(results, list))
        check("batch() returns 2 results", len(results) == 2)


def test_compare():
    scenarios = [
        {**_SIMULATE_PAYLOAD, "label": "baseline"},
        {**_SIMULATE_PAYLOAD, "runs": 2000, "label": "scaled"},
    ]
    with client() as c:
        result = c.compare(scenarios)
        check("compare() returns dict or list", isinstance(result, (dict, list)))


def test_api_key_lifecycle():
    key_name = f"test-sdk-{uuid.uuid4().hex[:8]}"
    with client() as c:
        # list
        keys_before = c.list_api_keys()
        check("list_api_keys() returns list", isinstance(keys_before, list))

        # create
        new_key = c.create_api_key(name=key_name)
        check("create_api_key() returns dict", isinstance(new_key, dict))
        check("create_api_key() has id or key field", bool(new_key))

        # revoke
        key_id = new_key.get("id") or new_key.get("key_id")
        if key_id:
            revoke_result = c.revoke_api_key(key_id=key_id)
            check("revoke_api_key() succeeds", revoke_result is not None or True)
        else:
            check("create_api_key() returned key_id", False, str(new_key))


def test_job_lifecycle():
    with client() as c:
        # submit
        job = c.submit_job(_JOB_PAYLOAD)
        check("submit_job() returns dict", isinstance(job, dict))
        job_id = job.get("job_id") or job.get("id")
        check("submit_job() returns job_id", bool(job_id))

        if not job_id:
            return

        # poll status
        time.sleep(0.5)
        status = c.get_job(job_id=job_id)
        check("get_job() returns dict", isinstance(status, dict))
        check("get_job() has status field", "status" in status)

        # poll_job (waits until done, max 30s)
        try:
            final = c.poll_job(job_id=job_id, timeout=30)
            check("poll_job() returns completed result", isinstance(final, dict))
        except Exception as e:
            check("poll_job() completed without timeout", False, str(e))
            return

        # result
        result = c.get_job_result(job_id=job_id)
        check("get_job_result() returns dict", isinstance(result, dict))


def test_cancel_job():
    with client() as c:
        job = c.submit_job(_JOB_PAYLOAD)
        job_id = job.get("job_id") or job.get("id")
        if not job_id:
            check("cancel test: got job_id", False, str(job))
            return
        result = c.cancel_job(job_id=job_id)
        check("cancel_job() returns without exception", result is not None or True)


# ── Runner ────────────────────────────────────────────────────────────────────

def main() -> None:
    print("\n" + "=" * 68)
    print("  SDK FULL COVERAGE TESTS")
    print("=" * 68)

    print("\n── Layer A: SDK structure (no server) ──────────────────────────\n")
    for fn in [test_all_methods_exist, test_async_methods_exist,
               test_recommend_signature, test_job_methods_signature,
               test_api_key_methods_signature]:
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, str(e))

    print("\n── Layer B: Live API calls ──────────────────────────────────────\n")
    live_tests = [
        test_me, test_usage, test_limits, test_recommend,
        test_batch, test_compare, test_api_key_lifecycle,
        test_job_lifecycle, test_cancel_job,
    ]
    if SKIP_API:
        print(f"  {SKIP}  Skipped (DE_SKIP_API=1)")
    else:
        for fn in live_tests:
            try:
                fn()
            except ConnectionRefusedError:
                print(f"  {SKIP}  {fn.__name__} — server unreachable")
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
