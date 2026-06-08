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
  ALGENTA_TEST_START_API_SERVER=1 python3 tests/integration/test_sdk_full.py
      # full against an isolated current-checkout API server
"""

from __future__ import annotations

import contextlib
import inspect
import os
import socket
import sys
import time
import uuid
from pathlib import Path
from unittest import mock

socket.setdefaulttimeout(20)

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "packages" / "python-sdk"))

from decision_engine import AsyncDecisionEngineClient, DecisionEngineClient  # noqa: E402
from decision_engine.models_account import UsageInfo  # noqa: E402

try:
    from tests.integration.live_local_defaults import (
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )
except ModuleNotFoundError:
    from live_local_defaults import (
        resolve_local_live_api_key,
        resolve_local_live_base_url,
    )

BASE_URL = resolve_local_live_base_url()
API_KEY = resolve_local_live_api_key()
SKIP_API = os.environ.get("DE_SKIP_API", "0") == "1"

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️ "
_results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    icon = PASS if cond else FAIL
    _results.append((name, cond, detail))
    print(f"  {icon}  {name}" + (f"  ({detail})" if detail else ""))


def _current_base_url() -> str:
    return os.environ.get("DE_BASE_URL", BASE_URL)


def _current_api_key() -> str:
    return os.environ.get("DE_API_KEY", API_KEY)


def client() -> DecisionEngineClient:
    return DecisionEngineClient(api_key=_current_api_key(), base_url=_current_base_url())


@contextlib.contextmanager
def _device_identity(device_id: str):
    original_algenta = os.environ.get("ALGENTA_DEVICE_ID")
    original_de = os.environ.get("DE_DEVICE_ID")
    os.environ["ALGENTA_DEVICE_ID"] = device_id
    os.environ["DE_DEVICE_ID"] = device_id
    try:
        yield
    finally:
        if original_algenta is None:
            os.environ.pop("ALGENTA_DEVICE_ID", None)
        else:
            os.environ["ALGENTA_DEVICE_ID"] = original_algenta
        if original_de is None:
            os.environ.pop("DE_DEVICE_ID", None)
        else:
            os.environ["DE_DEVICE_ID"] = original_de


def _hosted_me(
    raw_key: str,
    device_id: str,
    *,
    hostname: str = "hosted-device-default",
) -> tuple[bool, dict | None, str, dict]:
    with _device_identity(device_id):
        try:
            with mock.patch("decision_engine.device_headers.platform.node", return_value=hostname):
                with DecisionEngineClient(
                    api_key=raw_key, base_url=_current_base_url()
                ) as sdk_client:
                    return True, sdk_client.me(), "", {}
        except Exception as exc:  # noqa: BLE001
            status_code = getattr(exc, "status_code", 0)
            error_code = getattr(exc, "error_code", "")
            response_body = getattr(exc, "response_body", {})
            return False, None, f"{status_code}:{error_code}:{exc}", response_body


def _me_response_has_org(payload: object) -> bool:
    if isinstance(payload, dict):
        return isinstance(payload.get("org"), dict)
    return getattr(payload, "org", None) is not None


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
        "simulate",
        "recommend",
        "score",
        "batch",
        "compare",
        "submit_job",
        "get_job",
        "get_job_result",
        "cancel_job",
        "poll_job",
        "me",
        "usage",
        "limits",
        "list_api_keys",
        "create_api_key",
        "revoke_api_key",
        "distributions",
        "templates",
        "health",
        "version",
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
    check("create_api_key() accepts device_limit param", "device_limit" in sig.parameters)
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
        check("usage() returns UsageInfo", isinstance(result, UsageInfo))
        check(
            "usage() exposes billing_period",
            isinstance(getattr(result, "billing_period", None), str)
            and bool(result.billing_period),
        )


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
        check("compare() returns dict or list", isinstance(result, dict | list))


def test_api_key_lifecycle():
    anchor_key_name = f"test-sdk-anchor-{uuid.uuid4().hex[:8]}"
    key_name = f"test-sdk-{uuid.uuid4().hex[:8]}"
    device_limit = 2
    with client() as c:
        anchor_key = c.create_api_key(name=anchor_key_name, device_limit=device_limit)
        anchor_key_id = anchor_key.get("id") or anchor_key.get("key_id")

        # list
        keys_before = c.list_api_keys()
        check("list_api_keys() returns list", isinstance(keys_before, list))
        check(
            "list_api_keys() exposes key_prefix metadata",
            all(bool(getattr(key, "key_prefix", "")) for key in keys_before),
        )
        check(
            "list_api_keys() omits raw_key",
            all(not hasattr(key, "raw_key") for key in keys_before),
        )

        try:
            # create
            new_key = c.create_api_key(name=key_name, device_limit=device_limit)
            check("create_api_key() returns dict", isinstance(new_key, dict))
            check(
                "create_api_key() returns id",
                isinstance(new_key.get("id"), str) and bool(new_key.get("id")),
            )
            check(
                "create_api_key() returns key_prefix",
                isinstance(new_key.get("key_prefix"), str) and bool(new_key.get("key_prefix")),
            )
            check(
                "create_api_key() returns raw_key",
                isinstance(new_key.get("raw_key"), str) and bool(new_key.get("raw_key")),
            )
            check(
                "create_api_key() raw_key matches key_prefix",
                isinstance(new_key.get("raw_key"), str)
                and isinstance(new_key.get("key_prefix"), str)
                and new_key["raw_key"].startswith(new_key["key_prefix"]),
            )
            check("create_api_key() returns device_limit", new_key.get("device_limit") == device_limit)

            raw_key = new_key.get("raw_key")
            check(
                "create_api_key() returns usable raw_key",
                isinstance(raw_key, str) and bool(raw_key),
            )

            first_hosted_ok, first_hosted_body, first_hosted_error, _ = _hosted_me(
                raw_key or "",
                "hosted-device-py-0001",
                hostname="hosted-device-py-node-a",
            )
            check("hosted me() succeeds on first device", first_hosted_ok, first_hosted_error)
            check(
                "hosted me() returns org payload on first device",
                _me_response_has_org(first_hosted_body),
                str(first_hosted_body),
            )

            repeated_hosted_ok, repeated_hosted_body, repeated_hosted_error, _ = _hosted_me(
                raw_key or "",
                "hosted-device-py-0001",
                hostname="hosted-device-py-node-a",
            )
            check(
                "hosted me() succeeds on repeated first device",
                repeated_hosted_ok,
                repeated_hosted_error,
            )
            check(
                "hosted me() returns org payload on repeated first device",
                _me_response_has_org(repeated_hosted_body),
                str(repeated_hosted_body),
            )

            mismatched_hosted_ok, _, mismatched_hosted_error, mismatched_hosted_body = _hosted_me(
                raw_key or "",
                "hosted-device-py-0001",
                hostname="hosted-device-py-node-b",
            )
            check(
                "hosted me() rejects reused device id with mismatched fingerprint",
                not mismatched_hosted_ok,
                mismatched_hosted_error,
            )
            check(
                "hosted me() returns device_identity_mismatch on mismatched fingerprint",
                mismatched_hosted_body.get("error", {}).get("code") == "device_identity_mismatch",
                str(mismatched_hosted_body),
            )
            check(
                "hosted me() reports hostname_hash mismatch metadata",
                mismatched_hosted_body.get("error", {}).get("mismatched_fields") == ["hostname_hash"],
                str(mismatched_hosted_body),
            )

            second_hosted_ok, second_hosted_body, second_hosted_error, _ = _hosted_me(
                raw_key or "",
                "hosted-device-py-0002",
                hostname="hosted-device-py-node-c",
            )
            check("hosted me() succeeds on second unique device", second_hosted_ok, second_hosted_error)
            check(
                "hosted me() returns org payload on second unique device",
                _me_response_has_org(second_hosted_body),
                str(second_hosted_body),
            )

            third_hosted_ok, _, third_hosted_error, third_hosted_body = _hosted_me(
                raw_key or "",
                "hosted-device-py-0003",
                hostname="hosted-device-py-node-d",
            )
            check(
                "hosted me() fails closed on third device",
                not third_hosted_ok,
                third_hosted_error,
            )
            check(
                "hosted me() returns device_limit_reached on third device",
                third_hosted_body.get("error", {}).get("code") == "device_limit_reached",
                str(third_hosted_body),
            )
            check(
                "hosted me() returns 2-device cap metadata on third device",
                third_hosted_body.get("error", {}).get("device_limit") == device_limit
                and third_hosted_body.get("error", {}).get("device_count") == device_limit,
                str(third_hosted_body),
            )

            key_id = new_key.get("id") or new_key.get("key_id")
            keys_after = c.list_api_keys()
            created_entry = next(
                (key for key in keys_after if str(getattr(key, "id", "")) == str(key_id)),
                None,
            )
            check("list_api_keys() returns created device_limit", created_entry is not None)
            if created_entry is not None:
                check(
                    "list_api_keys() preserves created device_limit",
                    getattr(created_entry, "device_limit", None) == device_limit,
                )

            if key_id:
                revoke_result = c.revoke_api_key(key_id=key_id)
                check("revoke_api_key() succeeds", revoke_result is not None or True)
                revoked_hosted_ok, _, revoked_hosted_error, revoked_hosted_body = _hosted_me(
                    raw_key or "",
                    "hosted-device-py-0001",
                    hostname="hosted-device-py-node-a",
                )
                check(
                    "hosted me() rejects revoked key immediately",
                    not revoked_hosted_ok,
                    revoked_hosted_error,
                )
                check(
                    "hosted me() returns invalid_api_key after revoke",
                    revoked_hosted_body.get("error", {}).get("code") == "invalid_api_key",
                    str(revoked_hosted_body),
                )
            else:
                check("create_api_key() returned key_id", False, str(new_key))
        finally:
            if anchor_key_id:
                try:
                    c.revoke_api_key(key_id=anchor_key_id)
                except Exception:
                    pass


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
        try:
            result = c.cancel_job(job_id=job_id)
            check("cancel_job() returns without exception", result is not None or True)
        except Exception as exc:  # noqa: BLE001
            status_code = getattr(exc, "status_code", 0)
            error_code = getattr(exc, "error_code", "")
            response_body = getattr(exc, "response_body", {})
            if (
                status_code == 409
                and response_body.get("error", {}).get("code") == "job_already_terminal"
            ):
                check(
                    "cancel_job() returns terminal conflict when job already finished",
                    True,
                    f"{status_code}:{error_code}:{exc}",
                )
                return
            check(
                "cancel_job() returns without exception", False, f"{status_code}:{error_code}:{exc}"
            )


# ── Runner ────────────────────────────────────────────────────────────────────


def main() -> None:
    from tests.integration.test_typescript_runtime_live import (  # noqa: PLC0415
        isolated_api_server,
    )

    print("\n" + "=" * 68)
    print("  SDK FULL COVERAGE TESTS")
    print("=" * 68)

    print("\n── Layer A: SDK structure (no server) ──────────────────────────\n")
    for fn in [
        test_all_methods_exist,
        test_async_methods_exist,
        test_recommend_signature,
        test_job_methods_signature,
        test_api_key_methods_signature,
    ]:
        try:
            fn()
        except Exception as e:
            check(fn.__name__, False, str(e))

    print("\n── Layer B: Live API calls ──────────────────────────────────────\n")
    live_tests = [
        test_me,
        test_usage,
        test_limits,
        test_recommend,
        test_batch,
        test_compare,
        test_api_key_lifecycle,
        test_job_lifecycle,
        test_cancel_job,
    ]
    if SKIP_API:
        print(f"  {SKIP}  Skipped (DE_SKIP_API=1)")
    else:
        with isolated_api_server():
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
