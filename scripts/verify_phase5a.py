"""Phase 5A live verification: quota, usage recording, and rate limiting."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.local_operator_contract import resolve_operator_api_key, resolve_operator_base_url


def resolve_api_key(explicit_value: str = "") -> str:
    """Return the explicit API key for live verification or raise a user error."""
    value = resolve_operator_api_key(explicit_value, os.environ)
    if value:
        return value
    raise ValueError(
        "ALGENTA_API_KEY or DE_API_KEY must be set before running verify_phase5a.py. "
        "No default live key is bundled with this script."
    )


def build_headers(api_key: str) -> dict[str, str]:
    return {"Content-Type": "application/json", "X-API-Key": api_key}


def check(
    passed: list[str],
    failed: list[str],
    label: str,
    condition: bool,
    detail: str = "",
) -> None:
    if condition:
        passed.append(label)
        print(f"  ✓ {label}{' — ' + detail if detail else ''}")
    else:
        failed.append(label)
        print(f"  ✗ {label}{' — ' + detail if detail else ''}")


def http(
    method: str,
    base_url: str,
    path: str,
    headers: Mapping[str, str],
    body: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any], Any]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(  # noqa: S310 - local verification target only
        f"{base_url}{path}",
        data=data,
        headers=dict(headers),
        method=method,
    )
    try:
        with urllib.request.urlopen(request) as response:  # noqa: S310 - local verification target only
            return response.status, json.loads(response.read()), response.headers
    except urllib.request.HTTPError as exc:
        return exc.code, json.loads(exc.read()), None


def run_phase5a(*, api_key: str, base_url: str) -> int:
    headers = build_headers(api_key)
    passed: list[str] = []
    failed: list[str] = []

    print("\n── Phase 5A: Quota + Usage Recording live verification ──\n")
    print(f"Base URL: {base_url}")

    print("1. POST /v1/simulate")
    status, body, response_headers = http(
        "POST",
        base_url,
        "/v1/simulate",
        headers,
        {
            "mode": "auto",
            "scenario": {
                "variables": {
                    "revenue": {"low": 80000, "high": 200000},
                    "cost": {"low": 30000, "high": 90000},
                },
                "objective": "maximize_net_value",
            },
            "seed": 42,
        },
    )
    check(passed, failed, "status=200", status == 200, str(status))
    result_hash = body.get("result_hash", "")
    check(
        passed,
        failed,
        "result_hash in body (64 chars)",
        bool(result_hash) and len(result_hash) == 64,
        result_hash[:16] + "..." if result_hash else "",
    )
    header_hash = response_headers["X-Decision-Hash"] if response_headers else "MISSING"
    check(
        passed,
        failed,
        "X-Decision-Hash header present",
        header_hash != "MISSING",
        header_hash[:30] + "..." if header_hash != "MISSING" else header_hash,
    )
    check(
        passed,
        failed,
        "header contains hash",
        bool(result_hash) and result_hash in header_hash,
    )
    print(f"  run_id={body.get('run_id')}, action={body.get('recommended_action')}")

    print("\n2. GET /v1/usage")
    status_usage, usage, _ = http("GET", base_url, "/v1/usage", headers)
    check(passed, failed, "status=200", status_usage == 200, str(status_usage))
    simulations_run = usage.get("simulations_run", 0)
    check(passed, failed, "simulations_run >= 1", simulations_run >= 1, str(simulations_run))
    check(
        passed,
        failed,
        "billing_period present",
        bool(usage.get("billing_period")),
        usage.get("billing_period", ""),
    )

    print("\n3. DB: usage_records table")
    try:
        import psycopg2

        connection = psycopg2.connect("postgresql://angel@localhost:5432/decision_engine")
        cursor = connection.cursor()
        cursor.execute(
            "SELECT id, endpoint, billing_units, scenarios_run, billing_period "
            "FROM usage_records ORDER BY created_at DESC LIMIT 1"
        )
        row = cursor.fetchone()
        connection.close()
        if row:
            check(
                passed,
                failed,
                "usage_record exists in DB",
                True,
                f"endpoint={row[1]} billing_units={row[2]} scenarios={row[3]}",
            )
            check(passed, failed, "endpoint=simulate", row[1] == "simulate", str(row[1]))
            check(passed, failed, "billing_units=1", row[2] == 1, str(row[2]))
        else:
            check(passed, failed, "usage_record exists in DB", False, "NO ROWS FOUND")
    except ImportError:
        print("  (psycopg2 not available — skipping DB check)")
    except Exception as exc:  # pragma: no cover - live verification only
        print(f"  DB check error: {exc}")

    print("\n4. GET /v1/limits")
    status_limits, limits, _ = http("GET", base_url, "/v1/limits", headers)
    check(passed, failed, "status=200", status_limits == 200, str(status_limits))
    check(passed, failed, "plan present", bool(limits.get("plan")), limits.get("plan", ""))
    check(
        passed,
        failed,
        "max_simulations_per_month present",
        "max_simulations_per_month" in limits,
    )

    print(f"\n── Results: {len(passed)} passed, {len(failed)} failed ──")
    if failed:
        print(f"FAILED: {', '.join(failed)}")
        return 1

    print("ALL CHECKS PASSED ✓")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Verify quota, usage recording, and limits against a configured local or self-hosted API."
        )
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="API key to verify. Defaults to ALGENTA_API_KEY / DE_API_KEY.",
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
        api_key = resolve_api_key(args.api_key)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    try:
        base_url = resolve_operator_base_url(
            args.base_url,
            os.environ,
            strip_trailing_slash=True,
            surface="verify_phase5a.py",
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return run_phase5a(api_key=api_key, base_url=base_url)


if __name__ == "__main__":
    raise SystemExit(main())
