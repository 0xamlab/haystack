---
icon: stamp
description: The versioned execution-receipt envelope, the audited webhook-dispatch path, and the hash-verified audit export — three real artifacts, and an honest note on how they connect today.
---

# Evidence walkthrough

[Drive a governed decision through the API](../guides/governed-decisions.md) is the full nine-call lifecycle. This page is narrower: it shows the exact shape of the two evidence artifacts a reviewer actually asks for — the execution receipt and the audit export — and states plainly which execution path produces which today, rather than implying a single unified trail that doesn't exist yet.

## Two receipt-producing paths, and they're currently separate

This engine has two things that are each called a receipt, and one execution history:

| | `POST /v1/decision-plans/{id}/execute` (and `POST /v1/capabilities/execute`) | `POST /v1/decisions/{id}/execute` |
| --- | --- | --- |
| Returns | The versioned `ExecutionReceipt` envelope (`apps/api_server/schemas/receipt.py`) | `DecisionWebhookReceipt` — confirmation a logged decision's webhook fired |
| Fields | `receipt_version`, `status`, `code`, `retryable`, `request_id`, `trace_id`, `execution_id`, `plan_hash`, `approval_state`, `policy_snapshot_hash`, `result` | `decision_id`, `webhook_url`, `execution_status`, `response_code`, `policy_snapshot_id`, `schema_snapshot_id`, `manifest_version` |
| Writes a row to `audit_events` (and so appears in `GET /v1/audit-logs/export.{fmt}`)? | Not yet | Yes — `action: "decision.execute"` |
| Reached from | The decision-cases/decision-plans HTTP lifecycle; capability-plane `execute` | The MCP `log_decision` + `execute_decision` tools, and direct HTTP |

The code's own docstring on `DecisionWebhookReceipt` is explicit that these are "an unrelated concept that happened to share a class name" (they were disambiguated, in an A4 follow-up, specifically so the published OpenAPI spec doesn't carry two components both titled `ExecutionReceipt`). This page keeps them just as separate: Part 1 below shows the versioned envelope; Part 2 shows the audited path. Do not read this as "any execution gets you both" — today, it doesn't.

## Part 1 — the versioned receipt envelope

```bash title="execute an approved decision-plan"
curl -sS -X POST "$ALGENTA_BASE_URL/v1/decision-plans/$PLAN_ID/execute" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Idempotency-Key: exec-2026-08-29-001"
```

```json title="receipt field on the response"
{
  "receipt_version": "1",
  "status": "executed",
  "code": null,
  "retryable": false,
  "request_id": "req_c93a1e7f2b4d",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "idempotency_key": "exec-2026-08-29-001",
  "execution_id": "0b8e6f2a-1c3d-4a5b-9e7f-2d4c6a8b0e1f",
  "plan_hash": "9f86d081884c7d659a2feaa0c55ad015",
  "approval_state": "approved",
  "policy_snapshot_hash": null,
  "executed_at": "2026-08-29T17:41:03Z",
  "result": { "prepared_artifacts": ["export_allocation_table", "create_task_list"], "action_count": 2 }
}
```

Field notes: `receipt_version` is what to pin a parser to, not field presence. `status`/`code`/`retryable` together say what happened and whether retrying could help, without making a caller infer intent from an HTTP status code alone. `request_id`/`trace_id`/`idempotency_key` are correlation, not authority. `execution_id` is distinct from `plan_id` — the plan is what was authorized, this is the act. `policy_snapshot_hash` is `null` here because this specific lifecycle carries no execution-policy snapshot reference — see [Governed execution](governed-execution.md) for the mechanism where that field *is* populated.

## Part 2 — the audited path, and the export that covers it

```bash title="log, then execute, a decision"
curl -sS -X POST "$ALGENTA_BASE_URL/v1/decisions" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" -H "Content-Type: application/json" \
  -d '{"chosen_action": "renew_at_current_terms", "expected_value": 142715.16, "confidence": 0.62}'
# -> { "id": "<DECISION_ID>", ... }

curl -sS -X POST "$ALGENTA_BASE_URL/v1/decisions/$DECISION_ID/execute" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" -H "Content-Type: application/json" \
  -d '{"webhook_url": "https://your-own-endpoint.example/act"}'
```

This call writes an `audit_events` row (`action: "decision.execute"`, `resource_type: "decision_log"`) as part of the same request — not a best-effort side effect. It shows up in a filtered export:

```bash title="export, filtered to this action, then verify the hash"
curl -sS "$ALGENTA_BASE_URL/v1/audit-logs/export.json?action=decision.execute" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -D headers.txt -o export.json

grep -i ^x-content-sha256: headers.txt
shasum -a 256 export.json
```

The two hashes matching is not a claim you take on trust — it's the same check `tests/test_audit_log_export.py` runs in this repository, by re-hashing the download rather than trusting the server's own arithmetic. See [Audit and evidence](audit-and-evidence.md) for the complete filter set (`policy_snapshot_id`, `schema_snapshot_id`, `manifest_version`, `request_hash`, and more) and why the response is buffered rather than streamed.

## What this walkthrough does not claim

- It does not claim the versioned `ExecutionReceipt` envelope (Part 1) is currently mirrored into `audit_events`. It isn't, today. If you need both a schema-versioned receipt *and* an audit-log row for the same execution, use Part 2's path, whose receipt is the older, unversioned `DecisionWebhookReceipt` shape.
- It does not claim a replay-manifest capability — "re-run this past execution and get a byte-identical result" doesn't exist yet; see [Governed execution](governed-execution.md#what-this-section-does-not-yet-claim).
- It does not claim the capability-plane's own approval-required execute path (`POST /v1/capabilities/execute`) writes to `audit_events` — it produces the same versioned envelope as Part 1, with the same gap.

## Next steps

- [Drive a governed decision through the API](../guides/governed-decisions.md)
- [Governed execution](governed-execution.md)
- [Audit and evidence](audit-and-evidence.md)
- [Error codes](../api/errors.md)
