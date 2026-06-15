"""Live API verification script for a configured local or self-hosted server."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.platform_contract_constants import API_KEY_PREFIX_LIVE
from scripts.local_operator_contract import resolve_operator_base_url

PASS = "✅"  # noqa: S105 - status glyph, not a credential
FAIL = "❌"


def _invalid_api_key(label: str) -> str:
    return f"{API_KEY_PREFIX_LIVE}{label}"


def req(
    *,
    base_url: str,
    method: str,
    path: str,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Make HTTP request, return (status_code, response_body_dict)."""
    url = f"{base_url}{path}"
    data = json.dumps(body).encode() if body else None
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(  # noqa: S310 - explicit verification target chosen by operator
        url,
        data=data,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310 - explicit verification target
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Cannot connect to {base_url} — is the API server running?") from exc


def run_check(
    results: list[tuple[str, str, str]],
    name: str,
    fn,
) -> None:
    try:
        fn()
        results.append((PASS, name, ""))
        print(f"{PASS} {name}")
    except Exception as exc:  # noqa: BLE001 - verification script surfaces exact failure
        results.append((FAIL, name, str(exc)))
        print(f"{FAIL} {name}: {exc}")


def run_verification(base_url: str) -> int:
    results: list[tuple[str, str, str]] = []

    def test_health() -> None:
        status, body = req(base_url=base_url, method="GET", path="/v1/health")
        assert status == 200, f"Expected 200, got {status}"
        assert body["status"] == "ok", f"Expected 'ok', got {body}"

    run_check(results, "GET /v1/health → 200 {'status': 'ok'}", test_health)

    def test_version() -> None:
        status, body = req(base_url=base_url, method="GET", path="/v1/version")
        assert status == 200
        assert "api_version" in body
        assert "engine_version" in body
        assert "environment" in body

    run_check(results, "GET /v1/version → 200 with version fields", test_version)

    def test_openapi() -> None:
        status, body = req(base_url=base_url, method="GET", path="/openapi.json")
        assert status == 200
        assert "openapi" in body
        assert "paths" in body
        assert "/v1/simulate" in body["paths"]
        assert "/v1/health" in body["paths"]

    run_check(results, "GET /openapi.json → valid OpenAPI spec with /v1/simulate", test_openapi)

    def test_auth_required() -> None:
        status, body = req(
            base_url=base_url,
            method="POST",
            path="/v1/simulate",
            body={
                "mode": "auto",
                "scenario": {
                    "variables": {"revenue": {"low": 80000, "high": 200000}},
                    "objective": "maximize_net_value",
                },
            },
        )
        assert status == 401, f"Expected 401 without auth, got {status}"
        assert "error" in body

    run_check(results, "POST /v1/simulate without auth → 401", test_auth_required)

    def test_invalid_key() -> None:
        status, body = req(
            base_url=base_url,
            method="POST",
            path="/v1/simulate",
            body={
                "mode": "auto",
                "scenario": {
                    "variables": {"x": {"low": 1, "high": 10}},
                    "objective": "maximize_net_value",
                },
            },
            headers={"X-API-Key": _invalid_api_key("totally_invalid_key_that_does_not_exist")},
        )
        assert status == 401, f"Expected 401 with invalid key, got {status}"
        error = body.get("error", {})
        assert error.get("code") == "invalid_api_key"

    run_check(results, "POST /v1/simulate with invalid key → 401 + code: invalid_api_key", test_invalid_key)

    def test_malformed_body() -> None:
        status, body = req(
            base_url=base_url,
            method="POST",
            path="/v1/simulate",
            body={"bad": "payload"},
            headers={"X-API-Key": _invalid_api_key("something")},
        )
        assert status in (401, 422), f"Expected 401 or 422, got {status}: {body}"

    run_check(results, "POST /v1/simulate with bad payload → 401 or 422", test_malformed_body)

    def test_request_id_header() -> None:
        request = urllib.request.Request(  # noqa: S310 - explicit verification target
            f"{base_url}/v1/health",
            method="GET",
        )
        with urllib.request.urlopen(request) as response:  # noqa: S310 - explicit verification target
            lower_headers = {key.lower(): value for key, value in dict(response.headers).items()}
            assert "x-request-id" in lower_headers, (
                f"X-Request-Id not in response headers: {list(lower_headers.keys())}"
            )

    run_check(results, "GET /v1/health response has X-Request-Id header", test_request_id_header)

    def test_simulate_no_traceback_leak() -> None:
        status, body = req(
            base_url=base_url,
            method="POST",
            path="/v1/simulate",
            body={
                "mode": "auto",
                "scenario": {
                    "variables": {"revenue": {"low": 80000, "high": 200000}},
                    "objective": "maximize_net_value",
                },
            },
            headers={"X-API-Key": _invalid_api_key("fakekeyfortestingonly1234567")},
        )
        assert status in (200, 401, 402, 429, 500), f"Unexpected status: {status}"
        assert "error" in body or "run_id" in body, f"Response must be structured JSON, got: {body}"
        body_text = json.dumps(body)
        assert "Traceback" not in body_text, "Raw Python traceback leaked to client!"
        assert "AttributeError" not in body_text

    run_check(
        results,
        "POST /v1/simulate never leaks raw tracebacks to client",
        test_simulate_no_traceback_leak,
    )

    print()
    print("=" * 60)
    passed = sum(1 for status, _, _ in results if status == PASS)
    failed = sum(1 for status, _, _ in results if status == FAIL)
    print(f"Base URL: {base_url}")
    print(f"Results: {passed} passed, {failed} failed out of {len(results)} checks")
    if failed == 0:
        print("🚀 Live API verification complete!")
        print()
        print("Next steps:")
        print("  - Start Postgres + Redis to test full /v1/simulate flow")
        print("  - Run: make dev (once Docker is available)")
        return 0

    print("Fix the failures above")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify a local or self-hosted Codna API surface without relying on hosted defaults."
        )
    )
    parser.add_argument(
        "--base-url",
        default="",
        help=(
            "API base URL. Defaults to ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL. "
            "Outside self_hosted / air_gapped only, falls back to localhost."
        ),
    )
    args = parser.parse_args()
    try:
        base_url = resolve_operator_base_url(
            args.base_url,
            os.environ,
            strip_trailing_slash=True,
            surface="verify_live_api.py",
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return run_verification(base_url)


if __name__ == "__main__":
    raise SystemExit(main())
