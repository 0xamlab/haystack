#!/usr/bin/env python3
"""Generate the public rate-limit page from the exact enforcement sources."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "gitbook" / "api" / "rate-limits.md"

PUBLIC_PLANS = (
    ("Community", "algenta_free"),
    ("Pro", "algenta_pro"),
    ("Team", "algenta_team"),
    ("Enterprise", "enterprise"),
)
ABUSE_FIELDS = (
    ("Create an API key", "organization", "api_key_create_rate_limit_per_minute", "/minute"),
    ("Login", "email + client IP", "login_rate_limit_per_minute", "/minute"),
    ("Signup", "client IP", "signup_rate_limit_per_minute", "/minute"),
    ("Create organizations by signup", "email", "signup_max_per_day_per_email", "/day"),
)


def _setting_default(field_name: str) -> int:
    from pydantic_core import PydanticUndefined

    from apps.api_server.config import Settings

    value = Settings.model_fields[field_name].default
    if value is PydanticUndefined or isinstance(value, bool) or not isinstance(value, int):
        raise AssertionError(f"{field_name} must have an integer default")
    return value


def extract() -> dict[str, list[dict[str, Any]]]:
    from apps.api_server.services import plan_limits
    from apps.api_server.services.quota_service import get_plan_quota

    plans: list[dict[str, Any]] = []
    for edition, plan in PUBLIC_PLANS:
        quota = get_plan_quota(plan)
        config = plan_limits.get(plan)
        plans.append(
            {
                "edition": edition,
                "rate": int(quota["rate_per_minute"]),
                "monthly": int(quota["simulations_month"]),
                "runs": int(quota["max_runs"]),
                "batch": int(quota["max_batch"]),
                "async_jobs": bool(quota["async_jobs"]),
                "concurrent_jobs": config.concurrent_jobs,
                "workers": plan_limits.worker_limit(plan),
            }
        )
    abuse = [
        {
            "operation": operation,
            "scope": scope,
            "default": _setting_default(field_name),
            "period": period,
        }
        for operation, scope, field_name, period in ABUSE_FIELDS
    ]
    return {"plans": plans, "abuse": abuse}


def _number(value: int, *, zero: str = "unlimited") -> str:
    return zero if value == 0 else f"{value:,}"


def render(data: dict[str, list[dict[str, Any]]]) -> str:
    out = [
        "---",
        "icon: gauge-high",
        "description: Unlimited Algenta execution, request safety bounds, licensed worker "
        "capacity, and configurable abuse controls.",
        "---",
        "",
        "# Execution policy & safety limits",
        "",
        "Algenta is licensed per device at a flat price. **Decisions and executions are unlimited "
        "on every edition**: there is no monthly quota, per-decision charge, overage rate, or "
        "edition-specific request meter. The self-hosted engine does not send execution counts to "
        "Algenta or Stripe.",
        "",
        "The runtime still records customer-owned audit events inside the deployment. Those local "
        "records are governance data, not vendor telemetry or a billing meter.",
        "",
        "`GET /v1/limits` reports the effective execution policy. A value of `0` for monthly "
        "execution, plan request rate, or concurrent jobs means unlimited.",
        "",
        "```bash",
        'curl -sS "$ALGENTA_API_URL/v1/limits" \\',
        '  -H "Authorization: Bearer $ALGENTA_API_KEY"',
        "```",
        "",
        "## Edition contract",
        "",
        "All editions have unlimited decisions, no edition request meter, async execution, and no "
        "plan-level concurrent-job quota. The only tiered execution capacity is workers per "
        "licensed device:",
        "",
        "| Edition | Decisions | Workers/device |",
        "| --- | --- | ---: |",
    ]
    for row in data["plans"]:
        out.append(
            f"| {row['edition']} | {_number(row['monthly'])} | "
            f"{_number(row['workers'], zero='negotiated')} |"
        )
    out += [
        "",
        "## Request-shape validation",
        "",
        "The current API schema accepts up to 1,000,000 simulation runs in one request and up to "
        "100 items in one batch. These uniform per-payload validation bounds prevent a single "
        "request from monopolizing memory; they do not cap total calls, decisions, or monthly "
        "execution. Split larger work across calls or async jobs.",
        "",
        "Workers/device is licensed capacity, not a rate limit. The bundled runtime enforces the "
        "signed-license value locally. See [Licensing & "
        "editions](../licensing.md).",
        "",
        "## Security abuse controls",
        "",
        "Authentication and key-management endpoints retain narrow security controls. These are "
        "not decision or execution quotas, and self-hosted operators can configure them:",
        "",
        "| Operation | Scope | Default |",
        "| --- | --- | ---: |",
    ]
    for row in data["abuse"]:
        out.append(f"| {row['operation']} | {row['scope']} | {row['default']}{row['period']} |")
    out += [
        "",
        "When one of these security controls is exceeded, the response is HTTP `429` with its "
        "operation-specific error code and a `Retry-After` header. This does not consume or reduce "
        "an edition execution allowance; no such allowance exists.",
        "",
        "Provider APIs and customer infrastructure can still apply their own capacity or rate "
        "controls. Algenta surfaces those external errors explicitly rather than relabeling them as "
        "an Algenta plan quota.",
        "",
        "## Related",
        "",
        '{% content-ref url="../billing.md" %}',
        "[billing.md](../billing.md)",
        "{% endcontent-ref %}",
        "",
        '{% content-ref url="errors.md" %}',
        "[errors.md](errors.md)",
        "{% endcontent-ref %}",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    data = extract()
    assert len(data["plans"]) == len(PUBLIC_PLANS)
    assert len(data["abuse"]) == len(ABUSE_FIELDS)
    for row in data["plans"]:
        assert row["monthly"] == 0
        assert row["rate"] == 0
        assert row["runs"] == 1_000_000
        assert row["batch"] == 100
        assert row["async_jobs"] is True
        assert row["concurrent_jobs"] == 0
    markdown = render(data)
    if "--check" in sys.argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != markdown:
            print("DRIFT: gitbook/api/rate-limits.md is stale vs enforcement sources")
            return 1
        print(
            f"rate-limits.md OK ({len(data['plans'])} plans, {len(data['abuse'])} abuse controls)"
        )
        return 0
    OUT.write_text(markdown, encoding="utf-8")
    print(
        f"wrote gitbook/api/rate-limits.md ({len(data['plans'])} plans, "
        f"{len(data['abuse'])} abuse controls)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
