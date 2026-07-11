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
    "mcp_egress_denied": "The external MCP server's host is not permitted by the deployment's egress policy. Add it to `ALGENTA_EGRESS_ALLOWLIST`.",
    "mcp_server_url_missing": "The MCP capability binding has no `config.server_url` to connect to.",
    "mcp_tool_name_missing": "The MCP capability is missing the remote tool name to invoke.",
    "mcp_tool_execution_failed": "Calling the tool on the external MCP server failed (unreachable, transport error, or a protocol error).",
    "mcp_tool_reported_error": "The external MCP tool ran but returned an error result.",
    "authentication_required": "No valid credential was supplied. Send `Authorization: Bearer <key>`.",
    "invalid_api_key": "The API key is malformed or not recognized.",
    "api_key_not_found": "The referenced API key does not exist.",
    "api_key_identity_required": "This endpoint needs an API-key identity; the caller authenticated with a non-key credential (e.g. a Microsoft Entra token).",
    "cannot_revoke_last_key": "You cannot revoke your last active key (it would lock you out).",
    "forbidden": "The key is valid but not permitted for this action.",
    "access_scope_denied": "The key's scope does not include this resource.",
    "not_found": "The requested resource does not exist.",
    "validation_error": "The request body failed schema validation; see `details`.",
    "quota_exceeded": (
        "A custom or non-Algenta governance quota is exhausted; Algenta editions have no "
        "monthly execution quota."
    ),
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
    "engine_spawn_failed": "The local compute engine could not be started.",
    "internal_error": "An unexpected server error; safe to retry.",
    "email_already_exists": "Sign-up: the email is already registered.",
    "email_verification_required": "The account email must be verified first.",
    "captcha_required": "Sign-up requires a captcha (Turnstile) token.",
    "signup_limit_exceeded": "Too many sign-ups from this source.",
    "last_owner": "You cannot remove or demote the last org owner.",
    "stripe_error": "The billing provider (Stripe) returned an error.",
    "no_billing_account": "No billing account is configured for the org.",
    "billing_not_enabled": "Self-serve billing is not enabled for this product yet.",
    "invalid_plan": "The plan name is not a valid, purchasable plan.",
    "seat_limit_reached": "The team has no available seats; add seats before inviting more members.",
    "seats_not_available": "No seats are available on the current plan.",
    "account_suspended": "The account is suspended; contact your organization owner or support to restore access.",
    "organization_suspended": "The organization is suspended.",
    "org_not_found": "The organization id is unknown.",
    "user_not_found": "The user id is unknown.",
    "missing_org_context": "The request could not be associated with an organization.",
    "already_member": "The user is already a member of this organization.",
    "invite_expired": "The team invitation has expired; request a new one.",
    "invite_invalid": "The team invitation token is invalid.",
    "invalid_role": "The team role is not one of the allowed roles.",
    "owner_grant_forbidden": "You cannot grant the owner role.",
    "self_role_change_forbidden": "You cannot change your own role.",
    # ── data sources, connectors & query ──────────────────────────────────────────
    "invalid_connection": "The connection details are invalid.",
    "invalid_connection_config": "The connector configuration is missing required fields or has invalid values.",
    "invalid_connection_provider": "The connection provider is not recognized.",
    "invalid_connection_type": "The connector type is not one of the supported types.",
    "invalid_connector_status": (
        "The saved connector has an invalid verification status; repair the persisted record "
        "before retrying."
    ),
    "invalid_credentials": "The supplied credentials were rejected by the data source.",
    "missing_connection_string": "A connection string is required for this connector.",
    "use_connection": "Provide a saved connection id instead of inline connection details for this operation.",
    "not_connected": "The data source is not connected.",
    "browse_failed": "Browsing the connector's contents failed; check the connection and permissions.",
    "invalid_provider": "The provider is not recognized.",
    "invalid_type": "The value's type does not match what the field expects.",
    "invalid_aliases": "One or more field aliases are invalid.",
    "invalid_filter_condition": "A query filter condition is malformed.",
    "invalid_selection": "The selection is invalid for this operation.",
    "selection_required": "A selection is required for this operation.",
    "invalid_visibility": "The visibility value is not allowed.",
    "invalid_workspace_id": "The workspace id is unknown or malformed.",
    "workspace_scope_not_permitted": "The key is not permitted to act in this workspace scope.",
    "column_not_found": "A referenced column does not exist in the source schema.",
    "group_column_not_found": "A group-by column was not found in the source schema.",
    "constraint_violated": "The write violated a uniqueness or referential constraint.",
    "empty_source": "The source contained no data.",
    "empty_table": "The referenced table is empty.",
    "empty_events": "No events were supplied.",
    "missing_source": "A source is required for this operation.",
    "unknown_source_id": "The source id is unknown.",
    "source_registration_failed": "Registering the source failed.",
    "source_cache_error": "The source cache could not be read or written.",
    "load_error": "The data could not be loaded.",
    "join_path_invalid": "The requested join path between sources is not valid.",
    "join_path_requires_group_column": "This join path requires a group-by column.",
    "join_source_error": "A joined source could not be read.",
    "dataset_execution_requires_governed_query_path": "This dataset must be queried through the governed query path, not a raw execution.",
    "missing_dataset_name": "A dataset name is required.",
    "not_refreshable": "This dataset cannot be refreshed.",
    "semantic_training_unavailable": "Semantic training is not available for this dataset.",
    "onboard_failed": "Onboarding the account or dataset failed.",
    "template_not_found": "The template name is unknown.",
    "template_run_error": "Running the template failed.",
    # ── jobs, agent runs & webhooks ───────────────────────────────────────────────
    "job_not_found": "The async job id is unknown.",
    "job_access_denied": "The async job belongs to another organization.",
    "job_already_terminal": "The job has already finished and can't be changed.",
    "job_cannot_be_cancelled": "The job is in a state that cannot be cancelled.",
    "invalid_agent_run_status": "The agent run is not in a state that allows this action.",
    "webhook_processing_failed": "Processing the inbound webhook failed; the sender may retry.",
    "webhook_signature_invalid": "The inbound webhook signature did not verify.",
    "http_error": "An upstream HTTP request failed.",
    # ── capability plane, playground & runtime ────────────────────────────────────
    "algenta_managed_capability_not_executable": "This capability runs on the Algenta-managed plane and can't be executed directly from a client-managed binding.",
    "client_managed_capability_requires_adapter": "This client-managed capability needs a registered adapter before it can run.",
    "preview_capability_not_executable": "This capability can be previewed but not executed in preview mode.",
    "provider_key_not_found": "No BYOK provider key is configured for this backend.",
    "playground_error": "The playground request could not be processed.",
    "playground_rate_limit": "The keyless playground rate limit was hit; slow down or use an API key.",
    "runtime_library_metadata_missing": "The runtime library is missing required metadata.",
    "not_implemented": "This operation is not available in the current deployment.",
    "no_data": "The query matched no rows.",
    "persistence_backend_unavailable": "The persistence backend is temporarily unavailable; retry.",
    # ── devices, deployments & nodes ──────────────────────────────────────────────
    "device_key_mismatch": "The device's key does not match the one bound to this activation.",
    "invalid_device_limit": "The requested device limit is out of the allowed range.",
    "deployment_exists": "A deployment already exists for this organization.",
    "already_deprovisioned": "The resource was already deprovisioned.",
    "invalid_region": "The deployment region is not supported.",
    "node_not_found": "The runtime node id is unknown.",
    "invalid_token": "The token is malformed or expired.",
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
