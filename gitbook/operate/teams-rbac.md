---
icon: users
description: Invite team members and set roles, understand the owner/admin/member/viewer permission matrix, and read the org audit log and its content-hashed artifacts.
---

# Manage the team and roles

An Algenta organization has members, each with one role, and every privileged action is gated by that role. This page covers inviting and managing members, the exact capabilities each role grants, and how to read the audit log — including the tamper-evident, content-hashed artifact records.

Roles are ordered highest to lowest: **owner → admin → member → viewer**. A role grants everything below it, so an owner can do anything an admin can, and so on.

{% hint style="info" %}
Managing members and viewing audit logs require the **admin** role or higher; requesting or tearing down a cloud deployment requires **owner**. All examples send `Authorization: Bearer $ALGENTA_API_KEY`; swap `https://api.algenta.ai` for `http://localhost:8000` on a self-hosted engine.
{% endhint %}

## Invite and manage members

{% stepper %}
{% step %}
### Invite a member

Send an invite with an email and a role. Valid roles are `owner`, `admin`, `member`, and `viewer`; `role` defaults to `member` if omitted.

```bash title="POST /v1/team/invite"
curl -sS -X POST "https://api.algenta.ai/v1/team/invite" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "email": "teammate@example.com", "role": "member" }'
```

The `201` response returns the `invite_id` along with the invite's `email`, `role`, `status`, and `expires_at`. An unknown role is rejected with `422` `invalid_role`.
{% endstep %}

{% step %}
### List the team

Read the current members. Pass `page` and `limit` for a paginated envelope; omit both to get a plain array.

```bash title="GET /v1/team"
curl -sS "https://api.algenta.ai/v1/team?page=1&limit=25" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

Each member carries `user_id`, `name`, `email`, `role`, and `status` (for example `active` or `suspended`).
{% endstep %}

{% step %}
### Change a role or remove a member

Update a member's role, or remove them from the org.

```bash title="PATCH /v1/team/{user_id}/role"
curl -sS -X PATCH "https://api.algenta.ai/v1/team/$USER_ID/role" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "role": "admin" }'
```

```bash title="DELETE /v1/team/{user_id}"
curl -sS -X DELETE "https://api.algenta.ai/v1/team/$USER_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

Removing a member returns `204`. Several guardrails protect the org:

- You cannot change **your own** role (`403` `self_role_change_forbidden`).
- Only an **owner** may grant the `owner` role (`403` `owner_grant_forbidden`).
- The **last active owner** cannot be demoted or removed (`409` `last_owner`), so an org can never end up ownerless.
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — `POST /v1/team/invite` returns `201` with an `invite_id`, the new member appears in `GET /v1/team`, and a role change is reflected on the member's `role` field. Attempts that violate a guardrail return a `403` or `409` with a specific error `code`.
{% endhint %}

## Role permission matrix

Each role grants a superset of the roles beneath it. The table below shows where each capability's minimum role sits.

| Capability | viewer | member | admin | owner |
| --- | :---: | :---: | :---: | :---: |
| Run simulations, queries, and reads | yes | yes | yes | yes |
| Manage your own API keys | no | yes | yes | yes |
| Invite / remove members, change roles | no | no | yes | yes |
| View audit logs and egress policy | no | no | yes | yes |
| View deployment cost | no | no | yes | yes |
| Request / deprovision a deployment | no | no | no | yes |
| Grant the `owner` role | no | no | no | yes |
| Billing checkout and portal | no | no | no | yes |

When a call is made below the required role, the API returns `403` with the required and current roles in the error details.

## Read the audit log

Every privileged action is recorded. Two endpoints expose it: the live database log and the immutable, content-hashed artifact store. Both require the **admin** role and return the same paginated `AuditLogResponse` shape.

```bash title="GET /v1/audit-logs"
curl -sS "https://api.algenta.ai/v1/audit-logs?action=invite_member&result=success&page=1&limit=25" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

```json title="audit-logs.json"
{
  "entries": [
    {
      "id": "a1b2c3d4-...",
      "timestamp": "2026-07-05T09:12:44Z",
      "actor_email": "admin@example.com",
      "action": "invite_member",
      "resource_type": "team_member",
      "resource_id": "f2a1c0de-...",
      "ip_address": "203.0.113.11",
      "result": "success",
      "content_hash": null,
      "metadata": {}
    }
  ],
  "total": 1,
  "page": 1,
  "limit": 25,
  "pages": 1
}
```

Both endpoints accept the same filters — `actor_email`, `action`, `resource_type`, `result` (`success` or `failure`), plus lineage filters `policy_snapshot_id`, `schema_snapshot_id`, `manifest_version`, and `request_hash` — with `page` (default `1`) and `limit` (default `25`, max `100`).

<details>
<summary>Content-hashed audit artifacts</summary>

`GET /v1/audit-logs/artifacts` reads the durable, immutable artifact store rather than the live table. Its entries carry a populated `content_hash`, making each record tamper-evident, and it accepts one extra filter, `content_hash`, to fetch a specific record. Use it when you need a verifiable, exportable audit trail; use `GET /v1/audit-logs` for recent operational activity.

```bash title="GET /v1/audit-logs/artifacts"
curl -sS "https://api.algenta.ai/v1/audit-logs/artifacts?action=simulate&limit=50" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

</details>

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Audit and tighten egress</strong></td><td>Prove what the deployment can and did reach over the network.</td><td><a href="privacy-egress.md">privacy-egress.md</a></td></tr>
<tr><td><strong>Manage deployments and nodes</strong></td><td>Provision isolated cloud deployments and register worker nodes.</td><td><a href="deployments-and-nodes.md">deployments-and-nodes.md</a></td></tr>
<tr><td><strong>Manage API keys</strong></td><td>Mint, scope, and revoke the keys your team authenticates with.</td><td><a href="../authentication.md">../authentication.md</a></td></tr>
</tbody></table>
