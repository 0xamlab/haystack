---
icon: file-shield
description: The audit log export carries a content hash you re-derive yourself — evidence you verify, not evidence you take on trust.
---

# Audit and evidence

For day-to-day reading of the audit log through the UI, see
[Read the audit log](../operate/teams-rbac.md#read-the-audit-log). This page is about the export
you'd hand to an auditor.

## The export's hash is not a claim, it's a re-derivable fact

`GET /v1/audit-logs/export.{fmt}` (`csv` or `json`, admin-only) returns the audit log with an
`X-Content-SHA256` header equal to the SHA-256 of the exact bytes in the response body. You do not
have to trust that the file wasn't altered after export — you re-hash the bytes yourself and
compare:

```bash
curl -sS "$ALGENTA_API_URL/v1/audit-logs/export.csv" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -D headers.txt -o export.csv

grep -i ^x-content-sha256: headers.txt
shasum -a 256 export.csv
```

If those two hashes don't match, the file was modified in transit or at rest after it left the
server — not a hypothetical, a directly checkable fact.

## An empty history is an honest empty page

The export (and the underlying `GET /v1/audit-logs` list) reflects exactly what is in the
database. An org with no audit events gets an empty result — never a synthesized or
placeholder-populated one.

## Filters match what you can see, and nothing more

Filtering by `policy_snapshot_id`, `schema_snapshot_id`, `manifest_version`, `request_hash`,
`actor_email`, `action`, `resource_type`, or `result` on the export uses the identical query path
as the UI's audit log view — an export is exactly the rows an operator already saw, not a
separately-derived report that could quietly diverge from it.

## Batched, not streamed — and that's deliberate

The response body is read from the database in batches (bounded memory even for a large history)
but assembled before the response is sent, rather than streamed as it's produced. The reason is
the hash itself: `X-Content-SHA256` has to describe the complete body, and HTTP headers are sent
before the body — a genuinely streamed response could only carry that digest in a trailer, which
most HTTP clients silently drop. A hash a client cannot actually check is worse than no hash,
because it invites trust that was never earned.

## Access is admin-only and org-scoped

The export endpoint requires the `admin` role and is scoped to the caller's own organization.

## Next steps

- [Teams & roles (RBAC)](../operate/teams-rbac.md)
- [Error codes](../api/errors.md)
