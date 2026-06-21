#!/usr/bin/env python3
"""Generate gitbook/api/rate-limits.md — rate limits & quotas — from the server settings model
(apps/api_server/config.py) so the numbers are authoritative, never a hand-maintained policy page.

    python3 scripts/docs/gen_limits_reference.py            # write the page
    python3 scripts/docs/gen_limits_reference.py --check     # CI: fail if stale
"""
from __future__ import annotations

import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "gitbook", "api", "rate-limits.md")
FLOOR = 6

# A config field is a "limit/quota" if its env name contains one of these tokens.
TOKENS = ("QUOTA", "RATE_LIMIT", "MAX_", "PER_MINUTE", "PER_DAY", "_LIMIT", "PAYLOAD")

MEANINGS = {
    "QUOTA_FREE_SIMULATIONS_MONTH": "Monthly simulations on the Free plan.",
    "QUOTA_DEVELOPER_SIMULATIONS_MONTH": "Monthly simulations on the Developer plan.",
    "QUOTA_PRO_SIMULATIONS_MONTH": "Monthly simulations on the Pro plan.",
    "SIGNUP_RATE_LIMIT_PER_MINUTE": "Sign-up attempts per minute (abuse protection).",
    "SIGNUP_MAX_PER_DAY_PER_EMAIL": "Sign-ups per day per email.",
    "LOGIN_RATE_LIMIT_PER_MINUTE": "Login attempts per minute.",
    "API_KEY_CREATE_RATE_LIMIT_PER_MINUTE": "API-key creations per minute.",
    "MAX_PAYLOAD_SIZE_BYTES": "Maximum request body size.",
    "MAX_SYNC_RUNS": "Maximum simulation runs in a synchronous request.",
    "MAX_BATCH_ITEMS_FREE": "Maximum batch items on the Free plan.",
    "MAX_BATCH_ITEMS_PRO": "Maximum batch items on the Pro plan.",
}


def _primary(name, info):
    alias = getattr(info, "validation_alias", None)
    if alias is not None and getattr(alias, "choices", None):
        return str(alias.choices[0])
    if alias is not None:
        return str(alias)
    return name.upper()


def extract():
    from apps.api_server.config import Settings
    from pydantic_core import PydanticUndefined

    rows = []
    for name, info in Settings.model_fields.items():
        env = _primary(name, info)
        if not any(tok in env for tok in TOKENS):
            continue
        default = info.default
        dflt = "" if default is PydanticUndefined or default is None else str(default)
        rows.append((env, dflt))
    rows.sort(key=lambda r: r[0])
    return rows


def render(rows):
    out = [
        "---",
        "icon: gauge-high",
        "description: Algenta rate limits and plan quotas — the authoritative numbers the engine "
        "enforces, with how to handle 429 and quota errors.",
        "---",
        "",
        "# Rate limits & quotas",
        "",
        "Algenta enforces per-plan **quotas** (monthly usage) and per-endpoint **rate limits** (abuse "
        "protection). The values below are the authoritative numbers the engine enforces. Plan tiers "
        "are on [Plans, billing & credits](../billing.md).",
        "",
        "| Setting | Default | What it limits |",
        "| --- | --- | --- |",
    ]
    for env, dflt in rows:
        dv = f"`{dflt}`" if dflt != "" else "—"
        out.append(f"| `{env}` | {dv} | {MEANINGS.get(env, '—')} |")
    out += [
        "",
        "## Handling limits",
        "",
        "{% hint style=\"info\" %}",
        "A quota or rate-limit rejection returns the standard error envelope (for example "
        "`quota_exceeded` or a `429`). Back off and retry with jitter on `429`; for `quota_exceeded`, "
        "upgrade the plan or wait for the monthly reset. See [Error codes](errors.md).",
        "{% endhint %}",
        "",
        "## Related",
        "",
        "{% content-ref url=\"../billing.md\" %}",
        "[billing.md](../billing.md)",
        "{% endcontent-ref %}",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    rows = extract()
    names = [r[0] for r in rows]
    dupes = [k for k, c in Counter(names).items() if c > 1]
    assert not dupes, f"duplicate limit settings: {dupes}"
    assert len(names) >= FLOOR, f"only {len(names)} limit settings (< floor {FLOOR}) — parse broke"
    md = render(rows)
    if "--check" in sys.argv:
        current = open(OUT).read() if os.path.exists(OUT) else ""
        if current != md:
            print("DRIFT: gitbook/api/rate-limits.md is stale vs config.py — run `make docs-gen`")
            return 1
        print(f"rate-limits.md OK ({len(names)} settings)")
        return 0
    open(OUT, "w").write(md)
    print(f"wrote gitbook/api/rate-limits.md ({len(names)} settings)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
