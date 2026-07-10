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
| `account_suspended` | The account is suspended; contact your organization owner or support to restore access. |
| `algenta_managed_capability_not_executable` | This capability runs on the Algenta-managed plane and can't be executed directly from a client-managed binding. |
| `already_deprovisioned` | The resource was already deprovisioned. |
| `already_member` | The user is already a member of this organization. |
| `api_key_identity_required` | This endpoint needs an API-key identity; the caller authenticated with a non-key credential (e.g. a Microsoft Entra token). |
| `api_key_not_found` | The referenced API key does not exist. |
| `authentication_required` | No valid credential was supplied. Send `Authorization: Bearer <key>`. |
| `billing_not_enabled` | Self-serve billing is not enabled for this product yet. |
| `browse_failed` | Browsing the connector's contents failed; check the connection and permissions. |
| `cannot_revoke_last_key` | You cannot revoke your last active key (it would lock you out). |
| `captcha_required` | Sign-up requires a captcha (Turnstile) token. |
| `client_managed_capability_requires_adapter` | This client-managed capability needs a registered adapter before it can run. |
| `column_not_found` | A referenced column does not exist in the source schema. |
| `concurrent_jobs_exceeded` | Too many in-flight async jobs for the plan. |
| `connector_test_failed` | The connector connection test did not succeed. |
| `constraint_violated` | The write violated a uniqueness or referential constraint. |
| `dataset_execution_requires_governed_query_path` | This dataset must be queried through the governed query path, not a raw execution. |
| `dataset_not_found` | The dataset id is unknown. |
| `deployment_exists` | A deployment already exists for this organization. |
| `device_fingerprint_required` | The device-capped key needs the fingerprint headers. |
| `device_key_mismatch` | The device's key does not match the one bound to this activation. |
| `device_platform_required` | The device-capped key needs `X-Algenta-Platform`. |
| `device_revoked` | The device activation was revoked by an owner. |
| `egress_policy_denied` | The deployment's egress policy blocked an outbound destination. |
| `email_verification_required` | The account email must be verified first. |
| `empty_events` | No events were supplied. |
| `empty_source` | The source contained no data. |
| `empty_table` | The referenced table is empty. |
| `engine_error` | The compute engine failed to execute the request. |
| `engine_spawn_failed` | The local compute engine could not be started. |
| `forbidden` | The key is valid but not permitted for this action. |
| `group_column_not_found` | A group-by column was not found in the source schema. |
| `http_error` | An upstream HTTP request failed. |
| `idempotency_key_conflict` | An idempotency key was reused with a different payload. |
| `internal_error` | An unexpected server error; safe to retry. |
| `invalid_agent_run_status` | The agent run is not in a state that allows this action. |
| `invalid_aliases` | One or more field aliases are invalid. |
| `invalid_api_key` | The API key is malformed or not recognized. |
| `invalid_connection` | The connection details are invalid. |
| `invalid_connection_config` | The connector configuration is missing required fields or has invalid values. |
| `invalid_connection_provider` | The connection provider is not recognized. |
| `invalid_connection_type` | The connector type is not one of the supported types. |
| `invalid_credentials` | The supplied credentials were rejected by the data source. |
| `invalid_device_limit` | The requested device limit is out of the allowed range. |
| `invalid_filter_condition` | A query filter condition is malformed. |
| `invalid_plan` | The plan name is not a valid, purchasable plan. |
| `invalid_provider` | The provider is not recognized. |
| `invalid_region` | The deployment region is not supported. |
| `invalid_role` | The team role is not one of the allowed roles. |
| `invalid_selection` | The selection is invalid for this operation. |
| `invalid_token` | The token is malformed or expired. |
| `invalid_type` | The value's type does not match what the field expects. |
| `invalid_visibility` | The visibility value is not allowed. |
| `invalid_workspace_id` | The workspace id is unknown or malformed. |
| `invite_expired` | The team invitation has expired; request a new one. |
| `invite_invalid` | The team invitation token is invalid. |
| `job_access_denied` | The async job belongs to another organization. |
| `job_already_terminal` | The job has already finished and can't be changed. |
| `job_cannot_be_cancelled` | The job is in a state that cannot be cancelled. |
| `job_not_found` | The async job id is unknown. |
| `join_path_invalid` | The requested join path between sources is not valid. |
| `join_path_requires_group_column` | This join path requires a group-by column. |
| `join_source_error` | A joined source could not be read. |
| `last_owner` | You cannot remove or demote the last org owner. |
| `load_error` | The data could not be loaded. |
| `managed_llm_spend_cap_exceeded` | The managed-LLM spend cap for the org was reached. |
| `mcp_egress_denied` | The external MCP server's host is not permitted by the deployment's egress policy. Add it to `ALGENTA_EGRESS_ALLOWLIST`. |
| `mcp_server_url_missing` | The MCP capability binding has no `config.server_url` to connect to. |
| `mcp_tool_execution_failed` | Calling the tool on the external MCP server failed (unreachable, transport error, or a protocol error). |
| `mcp_tool_name_missing` | The MCP capability is missing the remote tool name to invoke. |
| `mcp_tool_reported_error` | The external MCP tool ran but returned an error result. |
| `missing_connection_string` | A connection string is required for this connector. |
| `missing_dataset_name` | A dataset name is required. |
| `missing_org_context` | The request could not be associated with an organization. |
| `missing_source` | A source is required for this operation. |
| `no_billing_account` | No billing account is configured for the org. |
| `no_data` | The query matched no rows. |
| `node_not_found` | The runtime node id is unknown. |
| `not_connected` | The data source is not connected. |
| `not_found` | The requested resource does not exist. |
| `not_implemented` | This operation is not available in the current deployment. |
| `not_refreshable` | This dataset cannot be refreshed. |
| `onboard_failed` | Onboarding the account or dataset failed. |
| `org_not_found` | The organization id is unknown. |
| `organization_suspended` | The organization is suspended. |
| `owner_grant_forbidden` | You cannot grant the owner role. |
| `persistence_backend_unavailable` | The persistence backend is temporarily unavailable; retry. |
| `playground_error` | The playground request could not be processed. |
| `playground_rate_limit` | The keyless playground rate limit was hit; slow down or use an API key. |
| `preview_capability_not_executable` | This capability can be previewed but not executed in preview mode. |
| `provider_key_not_found` | No BYOK provider key is configured for this backend. |
| `quota_exceeded` | The plan's monthly quota is exhausted; upgrade or wait for reset. |
| `rate_limit_backend_unavailable` | The rate-limit backend (Redis) is unreachable. |
| `resource_write_conflict` | A concurrent write conflicted; retry. |
| `runtime_library_metadata_missing` | The runtime library is missing required metadata. |
| `seat_limit_reached` | The team has no available seats; add seats before inviting more members. |
| `seats_not_available` | No seats are available on the current plan. |
| `selection_required` | A selection is required for this operation. |
| `self_role_change_forbidden` | You cannot change your own role. |
| `semantic_training_unavailable` | Semantic training is not available for this dataset. |
| `signup_limit_exceeded` | Too many sign-ups from this source. |
| `source_cache_error` | The source cache could not be read or written. |
| `source_not_found` | The source id is unknown. |
| `source_registration_failed` | Registering the source failed. |
| `storage_cap_exceeded` | The org's storage quota is full. |
| `stripe_error` | The billing provider (Stripe) returned an error. |
| `template_not_found` | The template name is unknown. |
| `template_run_error` | Running the template failed. |
| `unknown_source_id` | The source id is unknown. |
| `use_connection` | Provide a saved connection id instead of inline connection details for this operation. |
| `user_not_found` | The user id is unknown. |
| `validation_error` | The request body failed schema validation; see `details`. |
| `webhook_processing_failed` | Processing the inbound webhook failed; the sender may retry. |
| `webhook_signature_invalid` | The inbound webhook signature did not verify. |
| `workspace_scope_not_permitted` | The key is not permitted to act in this workspace scope. |

## Related

{% content-ref url="../troubleshooting.md" %}
[troubleshooting.md](../troubleshooting.md)
{% endcontent-ref %}
