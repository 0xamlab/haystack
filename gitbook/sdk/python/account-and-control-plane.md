---
icon: id-card
description: Python SDK reference for identity, usage, API keys, teams, billing, devices, audit logs, execution policy, and the platform contract — every AlgentaClient method and endpoint.
---

# Account and control plane (Python SDK)

These `AlgentaClient` methods manage who you are and how your organization is governed: identity and usage, API keys, team members, billing and metering, devices, audit logs, execution policy, and the machine-readable platform contract. Each is a faithful client over the `/v1` HTTP contract; the async client `AsyncAlgentaClient` exposes the same names to `await`.

```python title="client.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",   # or http://localhost:8000 self-hosted
)
```

## Identity and usage

| Method | HTTP | Returns |
| --- | --- | --- |
| `me()` | `GET /v1/me` | `MeResult` |
| `update_me(*, name=None, org_name=None)` | `PATCH /v1/me` | `Any` |
| `usage()` | `GET /v1/usage` | `UsageInfo` |
| `limits()` | `GET /v1/limits` | `dict` |
| `distributions()` | `GET /v1/distributions` | `DistributionListResult` |
| `templates()` | `GET /v1/templates` | `TemplateListResult` |
| `health()` | `GET /v1/health` | `dict` |
| `version()` | `GET /v1/version` | `dict` |

- `me` returns your user and organization (`me.user`, `me.org`); `update_me` renames your user (`name`) or organization (`org_name`).
- `usage` reports the current `billing_period`, `simulations_run`, `api_calls`, and `quota_used_pct`; `limits` returns the raw quota ceilings.
- `health` and `version` are unauthenticated liveness and build endpoints.

## API keys

| Method | HTTP | Returns |
| --- | --- | --- |
| `list_api_keys()` | `GET /v1/api-keys` | `list[APIKeyInfo]` |
| `create_api_key(label=None, *, name=None, expires_at=None, device_limit=None)` | `POST /v1/api-keys` | `dict` |
| `revoke_api_key(key_id)` | `DELETE /v1/api-keys/{key_id}` | `dict` |

- `create_api_key` returns the new key's full secret exactly once — store it immediately. `device_limit` caps how many devices may bind to the key; `expires_at` accepts a `datetime` or ISO-8601 string.
- `list_api_keys` returns metadata only (`id`, `label`, `key_prefix`, `status`), never the secret.

## Team members

| Method | HTTP | Returns |
| --- | --- | --- |
| `list_team_members(*, page=None, limit=None)` | `GET /v1/team` | `TeamListResult` |
| `invite_team_member(*, email, role="member")` | `POST /v1/team/invite` | `TeamInviteResult` |
| `update_team_member_role(user_id, *, role)` | `PATCH /v1/team/{user_id}/role` | `TeamRoleUpdateResult` |
| `remove_team_member(user_id)` | `DELETE /v1/team/{user_id}` | `TeamRemoveResult` |

## Billing, credits and metering

| Method | HTTP | Returns |
| --- | --- | --- |
| `get_billing_info()` | `GET /v1/billing/info` | `BillingInfoResult` |
| `create_billing_checkout(*, plan=None)` | `POST /v1/billing/checkout` | `BillingSessionResult` |
| `create_billing_portal()` | `POST /v1/billing/portal` | `BillingSessionResult` |
| `refresh_credits(*, device_id, billing_period, credits_used=0)` | `POST /v1/credits/refresh` | `CreditRefreshResult` |
| `ingest_metering_events(*, device_id, events)` | `POST /v1/metering` | `MeteringBatchResult` |

- `create_billing_checkout` and `create_billing_portal` return a hosted session you redirect the user to.
- `refresh_credits` and `ingest_metering_events` are used by a local runtime to reconcile its credit bucket and flush metered usage for a `device_id`.

## Devices

| Method | HTTP | Returns |
| --- | --- | --- |
| `list_devices(*, page=None, limit=None)` | `GET /v1/device/list` | `DeviceListResult` |
| `revoke_device(registration_id)` | `DELETE /v1/device/{registration_id}` | `DeviceRevokeResult` |

## Audit logs and execution policy

| Method | HTTP | Returns |
| --- | --- | --- |
| `get_audit_logs(*, page=1, limit=25, actor_email=None, action=None, resource_type=None, result=None, policy_snapshot_id=None, schema_snapshot_id=None, manifest_version=None, request_hash=None)` | `GET /v1/audit-logs` | `AuditLogResult` |
| `get_audit_log_artifacts(*, page=1, limit=25, actor_email=None, action=None, resource_type=None, result=None, policy_snapshot_id=None, schema_snapshot_id=None, manifest_version=None, request_hash=None, content_hash=None)` | `GET /v1/audit-logs/artifacts` | `Any` |
| `get_execution_policy()` | `GET /v1/execution/policy` | `ExecutionPolicyResult` |
| `list_execution_policy_snapshots()` | `GET /v1/execution/policy/snapshots` | `ExecutionPolicySnapshotListResult` |
| `update_execution_policy(*, min_confidence=None, risk_floor=None, require_calibration=None, allow_reexecution=None)` | `PATCH /v1/execution/policy` | `ExecutionPolicyResult` |

- Audit queries filter on provenance (`policy_snapshot_id`, `schema_snapshot_id`, `manifest_version`, `request_hash`) so you can reconstruct exactly what governed any action; `get_audit_log_artifacts` additionally filters by `content_hash`.
- `update_execution_policy` tunes the gate that decides whether a recommendation may auto-execute: `min_confidence`, `risk_floor`, `require_calibration`, and `allow_reexecution`. Only the fields you pass are changed.

## Platform contract and runtime

| Method | HTTP | Returns |
| --- | --- | --- |
| `get_contract()` | `GET /v1/meta/contract` | `PlatformContractResult` |
| `get_runtime_manifest()` | `GET /v1/runtime/manifest` | `RuntimeManifestResult` |
| `get_runtime_modules()` | `GET /v1/admin/runtime/modules` | `RuntimeAdminModulesResult` |
| `get_runtime_benchmarks()` | `GET /v1/admin/runtime/benchmarks` | `RuntimeAdminBenchmarksResult` |
| `get_runtime_release_validation()` | `GET /v1/admin/runtime/validation` | `RuntimeReleaseValidationResult` |

- `get_contract` is the machine-readable description of everything this instance supports — endpoint families, SDK/CLI/MCP method names, and governed-filter rules. It is what the SDKs bootstrap from.
- `get_runtime_manifest` reports the signed engine build serving requests; the `admin/runtime/*` methods surface module inventory, benchmarks, and release validation for the running engine.

{% hint style="info" %}
Every list result carries pagination fields (`total`, `page`, `limit`, `pages`); page until you have what you need. Snapshot ids (`policy_snapshot_id`, `schema_snapshot_id`) returned by these methods are the same values you can pass as filters to `get_audit_logs` and the agent-run query methods.
{% endhint %}

## Example: who am I, and how much have I used

```python title="whoami.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"], base_url="https://api.algenta.ai")

me = client.me()
print(me.user.email, "in", me.org.name, f"({me.org.plan})")

usage = client.usage()
print(f"{usage.billing_period}: {usage.api_calls} API calls, {usage.quota_used_pct:.1f}% of quota")

for key in client.list_api_keys():
    print(key.key_prefix, key.label, key.status)
```

Expected output resembles:

```text title="whoami.out"
you@example.com in Acme (team)
2026-07: 1842 API calls, 18.4% of quota
de_live_ab12 CI key active
```

## Example: tighten the execution policy

```python title="execution_policy.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"], base_url="https://api.algenta.ai")

current = client.get_execution_policy()
print("min_confidence before:", current.min_confidence)

updated = client.update_execution_policy(
    min_confidence=0.9,
    require_calibration=True,
)
print("min_confidence after:", updated.min_confidence)

# Every policy change is recorded — read it back from the audit log.
logs = client.get_audit_logs(action="execution_policy.update", limit=5)
```

## Related references

{% content-ref url="agent-runs.md" %}
[agent-runs.md](agent-runs.md)
{% endcontent-ref %}

{% content-ref url="../../api/overview.md" %}
[overview.md](../../api/overview.md)
{% endcontent-ref %}

{% content-ref url="../../billing.md" %}
[billing.md](../../billing.md)
{% endcontent-ref %}
