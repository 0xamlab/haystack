---
icon: triangle-exclamation
description: Every Algenta API error code in one place — generated from the codes the server emits — with what each means and the shape of the error response.
---

# Error codes

Every error the Algenta API returns uses the same envelope, with a stable `code` you can branch on, a human-readable `message`, and a `docs_url`:

```json title="error-envelope.json"
{
  "error": {
    "code": "device_identity_mismatch",
    "message": "Device is already bound to different identity metadata for this API key.",
    "docs_url": "https://docs.algenta.ai/errors/device_identity_mismatch",
    "details": {}
  }
}
```

Branch on `code` (stable), show `message` to humans. The table below is the complete set of codes the API can return; the common ones include a fix.

{% hint style="info" %}
For symptom-first help, see [Troubleshooting](../troubleshooting.md).
{% endhint %}

| Code | Meaning |
| --- | --- |
| `access_scope_denied` | The key's scope does not include this resource. |
| `account_suspended` | — |
| `algenta_managed_capability_not_executable` | — |
| `already_deprovisioned` | — |
| `api_key_not_found` | The referenced API key does not exist. |
| `authentication_required` | No valid credential was supplied. Send `Authorization: Bearer <key>`. |
| `browse_failed` | — |
| `cannot_revoke_last_key` | You cannot revoke your last active key (it would lock you out). |
| `captcha_required` | Sign-up requires a captcha (Turnstile) token. |
| `client_managed_capability_requires_adapter` | — |
| `column_not_found` | — |
| `concurrent_jobs_exceeded` | Too many in-flight async jobs for the plan. |
| `connector_test_failed` | The connector connection test did not succeed. |
| `constraint_violated` | — |
| `dataset_execution_requires_governed_query_path` | — |
| `dataset_not_found` | The dataset id is unknown. |
| `deployment_exists` | — |
| `device_fingerprint_required` | The device-capped key needs the fingerprint headers. |
| `device_key_mismatch` | — |
| `device_platform_required` | The device-capped key needs `X-Algenta-Platform`. |
| `device_revoked` | The device activation was revoked by an owner. |
| `egress_policy_denied` | The deployment's egress policy blocked an outbound destination. |
| `email_already_exists` | Sign-up: the email is already registered. |
| `email_verification_required` | The account email must be verified first. |
| `empty_events` | — |
| `empty_source` | — |
| `empty_table` | — |
| `engine_error` | The compute engine failed to execute the request. |
| `engine_spawn_failed` | The Mojo engine could not be started. |
| `forbidden` | The key is valid but not permitted for this action. |
| `group_column_not_found` | — |
| `http_error` | — |
| `idempotency_key_conflict` | An idempotency key was reused with a different payload. |
| `internal_error` | An unexpected server error; safe to retry. |
| `invalid_agent_run_status` | — |
| `invalid_aliases` | — |
| `invalid_api_key` | The API key is malformed or not recognized. |
| `invalid_connection` | — |
| `invalid_connection_config` | — |
| `invalid_connection_provider` | — |
| `invalid_connection_type` | — |
| `invalid_credentials` | — |
| `invalid_device_limit` | — |
| `invalid_filter_condition` | — |
| `invalid_plan` | — |
| `invalid_provider` | — |
| `invalid_region` | — |
| `invalid_role` | — |
| `invalid_selection` | — |
| `invalid_token` | — |
| `invalid_type` | — |
| `invalid_visibility` | — |
| `invalid_workspace_id` | — |
| `job_access_denied` | — |
| `job_already_terminal` | — |
| `job_cannot_be_cancelled` | — |
| `job_not_found` | — |
| `join_path_invalid` | — |
| `join_path_requires_group_column` | — |
| `join_source_error` | — |
| `last_owner` | You cannot remove or demote the last org owner. |
| `load_error` | — |
| `managed_llm_spend_cap_exceeded` | The managed-LLM spend cap for the org was reached. |
| `mcp_egress_denied` | The external MCP server's host is not permitted by the deployment's egress policy. Add it to `ALGENTA_EGRESS_ALLOWLIST`. |
| `mcp_server_url_missing` | The MCP capability binding has no `config.server_url` to connect to. |
| `mcp_tool_execution_failed` | Calling the tool on the external MCP server failed (unreachable, transport error, or a protocol error). |
| `mcp_tool_name_missing` | The MCP capability is missing the remote tool name to invoke. |
| `mcp_tool_reported_error` | The external MCP tool ran but returned an error result. |
| `missing_connection_string` | — |
| `missing_dataset_name` | — |
| `missing_org_context` | — |
| `missing_source` | — |
| `no_billing_account` | No billing account is configured for the org. |
| `no_data` | The query matched no rows. |
| `node_not_found` | — |
| `not_connected` | — |
| `not_found` | The requested resource does not exist. |
| `not_implemented` | — |
| `not_refreshable` | — |
| `onboard_failed` | — |
| `org_not_found` | — |
| `organization_suspended` | — |
| `owner_grant_forbidden` | — |
| `persistence_backend_unavailable` | — |
| `playground_error` | — |
| `playground_rate_limit` | — |
| `preview_capability_not_executable` | — |
| `provider_key_not_found` | — |
| `quota_exceeded` | The plan's monthly quota is exhausted; upgrade or wait for reset. |
| `rate_limit_backend_unavailable` | The rate-limit backend (Redis) is unreachable. |
| `resource_write_conflict` | A concurrent write conflicted; retry. |
| `runtime_library_metadata_missing` | — |
| `selection_required` | — |
| `self_role_change_forbidden` | — |
| `semantic_training_unavailable` | — |
| `signup_limit_exceeded` | Too many sign-ups from this source. |
| `source_cache_error` | — |
| `source_not_found` | The source id is unknown. |
| `source_registration_failed` | — |
| `storage_cap_exceeded` | The org's storage quota is full. |
| `stripe_error` | The billing provider (Stripe) returned an error. |
| `template_not_found` | — |
| `template_run_error` | — |
| `unknown_source_id` | — |
| `use_connection` | — |
| `user_not_found` | — |
| `validation_error` | The request body failed schema validation; see `details`. |
| `webhook_processing_failed` | — |
| `webhook_signature_invalid` | — |
| `workspace_scope_not_permitted` | — |

## Related

{% content-ref url="../troubleshooting.md" %}
[troubleshooting.md](../troubleshooting.md)
{% endcontent-ref %}
