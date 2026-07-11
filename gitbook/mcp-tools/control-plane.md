---
icon: sliders
description: MCP reference for deployments, team members, devices, audit logs, execution policy, billing, and managed-runtime compatibility.
---

# Control plane MCP tools

These tools administer an organization: its **deployments**, **team**, **devices**, **audit trail**, **autonomous execution policy**, and **billing**. The full registry also contains generic managed-runtime compatibility tools for credits and analytics ingestion. Product-scoped Algenta agents do not discover those compatibility tools because Algenta decisions are unmetered. Each tool maps one-to-one to an authenticated API endpoint scoped to the active organization.

## Deployment tools

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `list_deployment_regions` | List available deployment providers and regions. | none |
| `get_deployment` | Fetch the current deployment for the org, if one exists. | none |
| `create_deployment` | Request a new isolated deployment. | `provider`, `region`, `config`, `billing_markup_pct` (0–200) |
| `get_deployment_cost` | Get current-month cost details for one deployment. | `deployment_id` (required) |
| `delete_deployment` | Request deprovisioning for one deployment. | `deployment_id` (required) |

## Team & device tools

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `list_team_members` | List team members for the org. | `page`, `limit` (max 200) |
| `invite_team_member` | Invite a member by email. | `email` (required), `role` (`owner`/`admin`/`member`/`viewer`, default `member`) |
| `update_team_member_role` | Change one member's role by user id. | `user_id` (required), `role` (required) |
| `remove_team_member` | Remove one member by user id. | `user_id` (required) |
| `list_devices` | List registered devices for the org. | `page`, `limit` (max 200) |
| `revoke_device` | Revoke one registered device by registration id. | `registration_id` (required) |

## Audit & execution-policy tools

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `get_audit_logs` | Get paginated audit logs. | `page`, `limit` (max 100), `actor_email`, `action`, `resource_type`, `result`, `policy_snapshot_id`, `schema_snapshot_id`, `manifest_version`, `request_hash` |
| `get_audit_log_artifacts` | Get paginated immutable audit-log artifacts. | same as `get_audit_logs`, plus `content_hash` |
| `get_execution_policy` | Get the current autonomous execution policy. | none |
| `list_execution_policy_snapshots` | List persisted execution-policy snapshots. | none |
| `update_execution_policy` | Update one or more execution-policy thresholds. | `min_confidence` (0–1), `risk_floor` (≥0), `require_calibration` (bool), `allow_reexecution` (bool) |

## Billing and managed-runtime compatibility tools

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `get_billing_info` | Get the current billing plan and subscription info. | none |
| `create_billing_checkout` | Create a checkout session to change plan. | `plan` (`developer`/`pro`) |
| `create_billing_portal` | Create a billing-portal session to manage the subscription. | none |
| `refresh_credits` | Issue a compatibility credit batch for a quota-governed managed runtime. Not used by Algenta editions. | `device_id` (required), `billing_period` (required, `YYYY-MM`), `credits_used` (≥0) |
| `ingest_metering_events` | Ingest an explicitly enabled managed-runtime analytics batch. Not used automatically by private Algenta profiles. | `device_id` (required), `events` (required array of `{event_type, module, function, engine_used, latency_ms, success, timestamp, request_id}`) |

{% hint style="warning" %}
Control-plane tools change organization state — new deployments, role changes, device revocation, policy thresholds, and plan changes. They require an API key whose role permits the operation. Prefer a scoped key and review the change before confirming it.
{% endhint %}

## HTTP mapping

| Tool | Method | Endpoint |
| --- | --- | --- |
| `list_deployment_regions` | `GET` | `/v1/deployments/regions` |
| `get_deployment` | `GET` | `/v1/deployments` |
| `create_deployment` | `POST` | `/v1/deployments` |
| `get_deployment_cost` | `GET` | `/v1/deployments/{deployment_id}/cost` |
| `delete_deployment` | `DELETE` | `/v1/deployments/{deployment_id}` |
| `list_team_members` | `GET` | `/v1/team` |
| `invite_team_member` | `POST` | `/v1/team/invite` |
| `update_team_member_role` | `PATCH` | `/v1/team/{user_id}/role` |
| `remove_team_member` | `DELETE` | `/v1/team/{user_id}` |
| `list_devices` | `GET` | `/v1/device/list` |
| `revoke_device` | `DELETE` | `/v1/device/{registration_id}` |
| `get_audit_logs` | `GET` | `/v1/audit-logs` |
| `get_audit_log_artifacts` | `GET` | `/v1/audit-logs/artifacts` |
| `get_execution_policy` | `GET` | `/v1/execution/policy` |
| `list_execution_policy_snapshots` | `GET` | `/v1/execution/policy/snapshots` |
| `update_execution_policy` | `PATCH` | `/v1/execution/policy` |
| `get_billing_info` | `GET` | `/v1/billing/info` |
| `create_billing_checkout` | `POST` | `/v1/billing/checkout` |
| `create_billing_portal` | `POST` | `/v1/billing/portal` |
| `refresh_credits` | `POST` | `/v1/credits/refresh` |
| `ingest_metering_events` | `POST` | `/v1/metering` |

## Worked examples

### Invite a team member

{% tabs %}
{% tab title="MCP tool call" %}
```json title="invite_team_member — arguments"
{ "email": "teammate@example.com", "role": "member" }
```

Later, promote them with `update_team_member_role`:

```json title="update_team_member_role — arguments"
{ "user_id": "$USER_ID", "role": "admin" }
```
{% endtab %}

{% tab title="HTTP" %}
```bash title="invite.sh"
curl -sS "$ALGENTA_BASE_URL/v1/team/invite" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "email": "teammate@example.com", "role": "member" }'
```
{% endtab %}
{% endtabs %}

### Tighten the execution policy

Raise the confidence floor and require calibration before any autonomous execution. Only the fields you send are changed.

{% tabs %}
{% tab title="MCP tool call" %}
```json title="update_execution_policy — arguments"
{ "min_confidence": 0.9, "require_calibration": true }
```
{% endtab %}

{% tab title="HTTP" %}
```bash title="policy.sh"
curl -sS -X PATCH "$ALGENTA_BASE_URL/v1/execution/policy" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "min_confidence": 0.9, "require_calibration": true }'
```
{% endtab %}
{% endtabs %}

### Provision an isolated deployment

{% tabs %}
{% tab title="MCP tool call" %}
Discover regions first with `list_deployment_regions`, then request a deployment.

```json title="create_deployment — arguments"
{ "provider": "fly", "region": "iad", "config": { "size": "performance" } }
```

Track spend with `get_deployment_cost`:

```json title="get_deployment_cost — arguments"
{ "deployment_id": "$DEPLOYMENT_ID" }
```
{% endtab %}

{% tab title="HTTP" %}
```bash title="deploy.sh"
curl -sS "$ALGENTA_BASE_URL/v1/deployments/regions" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"

curl -sS "$ALGENTA_BASE_URL/v1/deployments" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "provider": "fly", "region": "iad", "config": { "size": "performance" } }'

curl -sS "$ALGENTA_BASE_URL/v1/deployments/$DEPLOYMENT_ID/cost" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}
{% endtabs %}

## Related references

{% content-ref url="account-and-meta.md" %}
[account-and-meta.md](account-and-meta.md)
{% endcontent-ref %}

{% content-ref url="../billing.md" %}
[billing.md](../billing.md)
{% endcontent-ref %}

{% content-ref url="../operate/monitoring.md" %}
[monitoring.md](../operate/monitoring.md)
{% endcontent-ref %}
