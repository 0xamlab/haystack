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
        "description: The Algenta request-rate, execution-governance, batch, and worker limits "
        "enforced for each edition.",
        "---",
        "",
        "# Rate limits & governance limits",
        "",
        "Algenta uses four separate controls. They are not interchangeable:",
        "",
        "1. **Request rate** bounds selected compute and mutation routes per organization and UTC "
        "minute.",
        "2. **Monthly execution governance** bounds hosted control-plane execution. It is a safety "
        "limit, not usage-based billing.",
        "3. **Request shape limits** bound runs per call and batch size.",
        "4. **Worker concurrency** bounds simultaneous bundled-runtime work per licensed device.",
        "",
        "`GET /v1/limits` is the authoritative response for the authenticated organization. It is "
        "generated from the same plan table used by enforcement.",
        "",
        "```bash",
        'curl -sS "$ALGENTA_API_URL/v1/limits" \\',
        '  -H "Authorization: Bearer $ALGENTA_API_KEY"',
        "```",
        "",
        "## Algenta edition defaults",
        "",
        "| Edition | Requests/minute | Monthly execution governance | "
        "Runs/call | Batch items | Async jobs | Concurrent jobs | Workers/device |",
        "| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    for row in data["plans"]:
        out.append(
            f"| {row['edition']} | {_number(row['rate'])} | "
            f"{_number(row['monthly'])} | {_number(row['runs'])} | {_number(row['batch'])} | "
            f"{'yes' if row['async_jobs'] else 'no'} | {_number(row['concurrent_jobs'])} | "
            f"{_number(row['workers'], zero='negotiated')} |"
        )
    out += [
        "",
        "The monthly value applies to centrally governed execution. A licensed local runtime does "
        "not create a usage invoice; see [Usage & limits](../billing.md). Worker concurrency is "
        "enforced by the bundled runtime from the signed license and changes on license renewal.",
        "",
        "## Which requests use the plan rate",
        "",
        "The plan request rate is applied to compute-bearing route families, including "
        "simulations, "
        "decision generation, agent execution, repository analysis, LLM operations, and "
        "runtime-library execution. Read-only account and discovery routes are not automatically "
        "charged against this counter merely because they use the API.",
        "",
        "Separate abuse controls protect authentication and key-management routes. Their "
        "deployment "
        "defaults are:",
        "",
        "| Operation | Scope | Default |",
        "| --- | --- | ---: |",
    ]
    for row in data["abuse"]:
        out.append(f"| {row['operation']} | {row['scope']} | {row['default']}{row['period']} |")
    out += [
        "",
        "Self-hosted operators can lower or raise these abuse-control defaults in deployment "
        "configuration. The authenticated `GET /v1/limits` response remains the source for plan "
        "execution limits.",
        "",
        "## Window and headers",
        "",
        "Plan request limits use a Redis counter for the current UTC minute. On applicable "
        "successful responses, Algenta returns:",
        "",
        "```text",
        "X-RateLimit-Limit: 300",
        "X-RateLimit-Remaining: 299",
        "```",
        "",
        "When the counter is exceeded, the response is HTTP `429` with error code "
        "`rate_limit_exceeded` and:",
        "",
        "```text",
        "Retry-After: 60",
        "X-RateLimit-Limit: 300",
        "X-RateLimit-Remaining: 0",
        "```",
        "",
        "The `Retry-After` value is a conservative upper bound. Retry only idempotent operations "
        "automatically, use jitter, and honor the header rather than hard-coding a shorter delay.",
        "",
        "If the rate-limit backend is unavailable under the production fail-closed policy, Algenta "
        "returns HTTP `503` with `rate_limit_backend_unavailable` and `Retry-After: 30`. It does "
        "not "
        "silently pretend the limiter succeeded.",
        "",
        "## Monthly governance rejection",
        "",
        "When centrally governed execution reaches its monthly ceiling, Algenta returns HTTP `429` "
        "with error code `quota_exceeded`, plus `used`, `limit`, and `billing_period`. This is not "
        "a short rate window: retrying seconds later will not help. Wait for the next period or "
        "change "
        "the organization policy or edition.",
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
