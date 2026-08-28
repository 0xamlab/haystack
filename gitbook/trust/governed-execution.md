---
icon: gavel
description: The control statements behind every plan approval and execution — named denial codes, single-use approval binding, versioned receipts.
---

# Governed execution

These are control statements, not a how-to. They describe what the engine enforces on every
decision-plan lifecycle, so a security reviewer can assess it without reading the source.

## The lifecycle is a state machine, not a convention

A decision case moves `proposed → approved → executed` through
`POST /v1/decision-cases → POST .../analysis-runs → POST .../action-plans → POST
/v1/decision-plans/{id}/approve → POST /v1/decision-plans/{id}/execute`. Each transition is
enforced server-side against the plan's current `lifecycle_state` — there is no client-supplied
field that skips a step.

## Approval is bound to an exact plan, by hash and by a single-use nonce

Proposing a plan returns a `plan_hash` and a nonce. Approving requires both, exactly:

- A different `plan_hash` than the one proposed is refused as `plan_hash_mismatch` — an approval
  cannot be silently re-pointed at a plan that was edited after review.
- A reused or wrong nonce is refused as `invalid_nonce` — nothing about the flow allows replaying
  an approval.
- An approval past its expiry window is refused as `approval_expired`.
- Two concurrent approval attempts on the same plan: exactly one succeeds, the other gets
  `plan_not_approvable` — a compare-and-set, not a race that both sides can win.

## Execution requires prior approval, and runs exactly once

`POST /v1/decision-plans/{id}/execute` on a plan that is not `approved` is refused as
`plan_not_approved` — including a plan that was already executed, so a duplicate execute call
cannot run twice. This is also a compare-and-set on the `approved` state: under concurrent
execute calls, exactly one wins.

## Every denial has a name, not a generic error

`plan_not_approved`, `plan_hash_mismatch`, `invalid_nonce`, `approval_expired`,
`plan_not_approvable` — a caller (or an integration built on the API) can distinguish *why* an
operation was refused without parsing prose. See [Error codes](../api/errors.md) for the full,
generated list of every code the server emits.

## The execution receipt is a versioned, typed contract

Every execution produces an `ExecutionReceipt`: a schema-versioned (`receipt_version`) record
carrying `status`, a machine-readable `code` for anything other than success, whether the
condition is `retryable`, the `execution_id` (distinct from the plan — the plan is what was
authorized, the execution is the act), the bound `plan_hash`, the `approval_state` at execution
time, and correlation identifiers (`request_id`, W3C `trace_id`, the caller's `Idempotency-Key`
if supplied). It is a real, enforced response schema — not an untyped blob a client has to parse
speculatively.

## Execution policy is a content-hashed, revisioned snapshot

Org-level execution policy (`GET/PATCH /v1/execution/policy`) is never edited in place. Each
change produces a new snapshot: `snapshot_id` embeds a schema revision and a SHA-256 prefix of the
policy's own serialized content (`content_hash`), and every snapshot records its
`previous_snapshot_id`. Two snapshots with the same content hash are, by construction, the same
policy — there is no way for two different policies to collide on one identifier, and no way to
silently mutate a policy a decision was evaluated against. Snapshots are listed at
`GET /v1/execution/policy/snapshots`.

This content-hashed guarantee applies to the org's execution policy specifically. It is a distinct
mechanism from the decision-plan's `plan_hash` above — a decision plan does not carry a policy
snapshot reference today, and its receipt's `policy_snapshot_hash` field is `null` rather than
populated with a value that is not actually a policy hash.

## What this section does not (yet) claim

There is no replay-manifest mechanism today — "re-run this past execution and get a byte-identical
result" is not a capability this engine exposes, and this page does not claim it is. If that
changes, it will be documented here as a control statement backed by working code, the same way
everything above is.

## Next steps

- [Error codes](../api/errors.md)
- [Audit and evidence](audit-and-evidence.md)
- [Execution policy & safety limits](../api/rate-limits.md)
