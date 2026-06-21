#!/usr/bin/env python3
"""Generate gitbook/api/errors.md — the complete error-code reference — from the codes the API
actually emits (string literals in apps/api_server, canonically apps/api_server/error_payloads.py).

    python3 scripts/docs/gen_error_reference.py            # write the page
    python3 scripts/docs/gen_error_reference.py --check     # CI: fail if stale

The code INVENTORY is complete by construction (regex over the source); curated meanings enrich the
common codes. --check regenerates and byte-compares; it also asserts uniqueness + a regression floor.
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "apps", "api_server")
OUT = os.path.join(ROOT, "gitbook", "api", "errors.md")
FLOOR = 50

_CODE_RE = re.compile(r'"code"\s*:\s*"([a-z][a-z0-9_]*)"')
_DOCS_RE = re.compile(r'docs_code\s*:\s*str\s*=\s*"([a-z][a-z0-9_]*)"')

MEANINGS = {
    "authentication_required": "No valid credential was supplied. Send `Authorization: Bearer <key>`.",
    "invalid_api_key": "The API key is malformed or not recognized.",
    "api_key_not_found": "The referenced API key does not exist.",
    "cannot_revoke_last_key": "You cannot revoke your last active key (it would lock you out).",
    "forbidden": "The key is valid but not permitted for this action.",
    "access_scope_denied": "The key's scope does not include this resource.",
    "not_found": "The requested resource does not exist.",
    "validation_error": "The request body failed schema validation; see `details`.",
    "quota_exceeded": "The plan's monthly quota is exhausted; upgrade or wait for reset.",
    "rate_limit_backend_unavailable": "The rate-limit backend (Redis) is unreachable.",
    "concurrent_jobs_exceeded": "Too many in-flight async jobs for the plan.",
    "storage_cap_exceeded": "The org's storage quota is full.",
    "managed_llm_spend_cap_exceeded": "The managed-LLM spend cap for the org was reached.",
    "egress_policy_denied": "The deployment's egress policy blocked an outbound destination.",
    "device_identity_mismatch": "A device-capped key saw a new device identity; send consistent headers or use the SDK.",
    "device_fingerprint_required": "The device-capped key needs the fingerprint headers.",
    "device_platform_required": "The device-capped key needs `X-Algenta-Platform`.",
    "device_revoked": "The device activation was revoked by an owner.",
    "idempotency_key_conflict": "An idempotency key was reused with a different payload.",
    "resource_write_conflict": "A concurrent write conflicted; retry.",
    "dataset_not_found": "The dataset id is unknown.",
    "source_not_found": "The source id is unknown.",
    "connector_test_failed": "The connector connection test did not succeed.",
    "no_data": "The query matched no rows.",
    "engine_error": "The compute engine failed to execute the request.",
    "engine_spawn_failed": "The Mojo engine could not be started.",
    "internal_error": "An unexpected server error; safe to retry.",
    "email_already_exists": "Sign-up: the email is already registered.",
    "email_verification_required": "The account email must be verified first.",
    "captcha_required": "Sign-up requires a captcha (Turnstile) token.",
    "signup_limit_exceeded": "Too many sign-ups from this source.",
    "last_owner": "You cannot remove or demote the last org owner.",
    "stripe_error": "The billing provider (Stripe) returned an error.",
    "no_billing_account": "No billing account is configured for the org.",
}


def extract() -> list[str]:
    codes: set[str] = set()
    for dp, _, fns in os.walk(SRC):
        for fn in fns:
            if not fn.endswith(".py"):
                continue
            text = open(os.path.join(dp, fn), encoding="utf-8", errors="replace").read()
            codes.update(_CODE_RE.findall(text))
            codes.update(_DOCS_RE.findall(text))
    codes.discard("code")
    return sorted(codes)


def render(codes: list[str]) -> str:
    out = [
        "---",
        "icon: triangle-exclamation",
        "description: Every Algenta API error code in one place — generated from the codes the server "
        "emits — with what each means and the shape of the error response.",
        "---",
        "",
        "# Error codes",
        "",
        "Every error the Algenta API returns uses the same envelope, with a stable `code` you can branch "
        "on, a human-readable `message`, and a `docs_url`:",
        "",
        "```json title=\"error-envelope.json\"",
        "{",
        '  "error": {',
        '    "code": "device_identity_mismatch",',
        '    "message": "Device is already bound to different identity metadata for this API key.",',
        '    "docs_url": "https://docs.algenta.ai/errors/device_identity_mismatch",',
        '    "details": {}',
        "  }",
        "}",
        "```",
        "",
        "Branch on `code` (stable), show `message` to humans. The table below is the complete set of "
        "codes the API can return; the common ones include a fix.",
        "",
        "{% hint style=\"info\" %}",
        "For symptom-first help, see [Troubleshooting](../troubleshooting.md).",
        "{% endhint %}",
        "",
        "| Code | Meaning |",
        "| --- | --- |",
    ]
    for code in codes:
        meaning = MEANINGS.get(code, "—").replace("|", "\\|")
        out.append(f"| `{code}` | {meaning} |")
    out += [
        "",
        "## Related",
        "",
        "{% content-ref url=\"../troubleshooting.md\" %}",
        "[troubleshooting.md](../troubleshooting.md)",
        "{% endcontent-ref %}",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    codes = extract()
    dupes = [k for k, c in Counter(codes).items() if c > 1]
    assert not dupes, f"duplicate error codes: {dupes}"
    assert len(codes) >= FLOOR, f"only {len(codes)} error codes (< floor {FLOOR}) — extraction broke"
    md = render(codes)
    if "--check" in sys.argv:
        current = open(OUT).read() if os.path.exists(OUT) else ""
        if current != md:
            print("DRIFT: gitbook/api/errors.md is stale vs the source codes — run `make docs-gen`")
            return 1
        print(f"errors.md OK ({len(codes)} codes)")
        return 0
    open(OUT, "w").write(md)
    print(f"wrote gitbook/api/errors.md ({len(codes)} codes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
