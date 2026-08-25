---
icon: shield-halved
description: Prove reachability for scanner findings against a repository snapshot, triage by classification, and re-prove that a fix closes the finding after you patch it.
---

# Prove a security finding

Static scanners produce long lists of findings, most of which are never reachable in the running application. Algenta's security analysis takes a batch of scanner findings plus a repository snapshot and returns a **proof** for each one: whether the sink is reachable from an entrypoint, the dataflow path that reaches it, and how sound that verdict is. After you ship a fix, a **closure** call re-proves the same finding against the patched snapshot so you can show it is genuinely closed — not just filtered.

This is a triage-and-verify workflow: create the analysis on a snapshot, read the proofs to decide what to fix, patch it, then re-prove closure. All routes live under `/v1/repositories` and require `Authorization: Bearer $ALGENTA_API_KEY`.

{% hint style="info" %}
Security analysis grades a batch of scanner findings; it does not run the scanner for you. Feed it the findings and the SARIF run digest from any scanner you use, and it proves reachability against the snapshot.
{% endhint %}

## Before you start

You need:

- `$REPOSITORY_ID` — the connector id (see [Connect data](connect-data.md)).
- `$SNAPSHOT_ID` — an immutable snapshot of the ref you scanned. Create one as shown in [Triage a repository](repository-intelligence.md); the analysis is cached against it.
- A scanner run: its `sarif_digest`, the scanner `name`, and the `findings` you want proven — each with a stable `canonical_id`, its `rule_id`, a `finding_kind`, and a `primary_location`.

## Analyze a batch of findings

Post the snapshot, the scanner descriptor, and the findings. The engine proves each finding's reachability and caches the result against the snapshot, so re-submitting the same batch is cheap.

`POST /v1/repositories/{repository_id}/security-analyses`

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "https://api.algenta.ai/v1/repositories/$REPOSITORY_ID/security-analyses" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_id": "'"$SNAPSHOT_ID"'",
    "sarif_digest": "sha256:9c1f...",
    "scanner": { "name": "codeql", "version": "2.17.0" },
    "findings": [
      {
        "canonical_id": "finding-sql-injection-001",
        "rule_id": "py/sql-injection",
        "finding_kind": "sql-injection",
        "severity": "high",
        "primary_location": { "uri": "src/api/orders.py", "start_line": 142 }
      }
    ]
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="security_analysis.py"
import os
import httpx

repo_id = os.environ["REPOSITORY_ID"]
resp = httpx.post(
    f"https://api.algenta.ai/v1/repositories/{repo_id}/security-analyses",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "snapshot_id": os.environ["SNAPSHOT_ID"],
        "sarif_digest": "sha256:9c1f...",
        "scanner": {"name": "codeql", "version": "2.17.0"},
        "findings": [
            {
                "canonical_id": "finding-sql-injection-001",
                "rule_id": "py/sql-injection",
                "finding_kind": "sql-injection",
                "severity": "high",
                "primary_location": {"uri": "src/api/orders.py", "start_line": 142},
            }
        ],
    },
    timeout=300.0,
)
analysis = resp.json()
for proof in analysis["proofs"]:
    print(proof["canonical_finding_id"], proof["classification"], proof["proof_type"])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="security_analysis.ts"
const repoId = process.env.REPOSITORY_ID!;
const resp = await fetch(
  `https://api.algenta.ai/v1/repositories/${repoId}/security-analyses`,
  {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      snapshot_id: process.env.SNAPSHOT_ID,
      sarif_digest: "sha256:9c1f...",
      scanner: { name: "codeql", version: "2.17.0" },
      findings: [
        {
          canonical_id: "finding-sql-injection-001",
          rule_id: "py/sql-injection",
          finding_kind: "sql-injection",
          severity: "high",
          primary_location: { uri: "src/api/orders.py", start_line: 142 },
        },
      ],
    }),
  },
);
const analysis = await resp.json();
for (const proof of analysis.proofs) {
  console.log(proof.canonical_finding_id, proof.classification, proof.proof_type);
}
```
{% endtab %}
{% endtabs %}

{% hint style="info" %}
A large SARIF batch can be slow to prove. Add `?async_execution=true` to take the work off the request path — the engine returns `202` with a poll handle instead of the result. Poll it as described in [Run asynchronous jobs](async-jobs.md).
{% endhint %}

{% hint style="success" %}
**Expected result** — a `200` `SecurityAnalysisResponse` with an `analysis_id`, the `snapshot` and `engine` it was proven against, an echo of your `sarif_digest`, and a `proofs` array with one proof per finding.
{% endhint %}

## Read the proofs

Each proof classifies one finding and shows the evidence behind the verdict:

```json title="proof.json"
{
  "canonical_finding_id": "finding-sql-injection-001",
  "finding_kind": "sql-injection",
  "classification": "production-reachable",
  "proof_type": "dataflow",
  "analysis_envelope": { "is_complete_sound": true, "language": "python", "on_matrix": true },
  "entrypoints": [{ "uri": "src/api/orders.py", "start_line": 88 }],
  "sinks": [{ "uri": "src/api/orders.py", "start_line": 142 }],
  "propagation_paths": [[{ "from_file": "src/api/orders.py", "to_file": "src/db/query.py", "edge_type": "call" }]],
  "sanitizers": [],
  "scanner_flow_validation": { "provided": true, "corroborates_engine_path": true }
}
```

Use these fields to triage:

| Field | What it tells you |
| --- | --- |
| `classification` | The headline verdict: `exploitable`, `production-reachable`, `unreachable`, or `unknown`. |
| `proof_type` | How the verdict was reached: `dataflow`, `entrypoint_reachability`, `absence_proof`, `off_matrix`, or `no_evidence`. |
| `analysis_envelope.is_complete_sound` | Whether the analysis was sound and complete for this finding's language and framework. |
| `entrypoints` / `sinks` / `propagation_paths` | The concrete path that makes the sink reachable — the evidence to hand a reviewer. |
| `sanitizers` | Sanitizers found on the path that may neutralize the flow. |
| `scanner_flow_validation` | Whether your scanner's own flow corroborates the engine's path. |

Fix `exploitable` and `production-reachable` findings first, and deprioritize `unreachable` ones. Treat `unknown` (and any proof whose `analysis_envelope.is_complete_sound` is `false`) as needing a human look rather than an automatic dismissal.

## Re-prove closure after a fix

Once you have patched and merged the fix (for example through [Fix a repository](repository-fix.md)), create a **new** snapshot of the patched ref and re-prove the finding against it. Closure asks one question: is the original finding still reachable?

`POST /v1/repositories/{repository_id}/security-analyses/closure`

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "https://api.algenta.ai/v1/repositories/$REPOSITORY_ID/security-analyses/closure" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_id": "'"$FIXED_SNAPSHOT_ID"'",
    "canonical_finding_id": "finding-sql-injection-001",
    "patch_digest": "sha256:44ab..."
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="closure.py"
import os
import httpx

repo_id = os.environ["REPOSITORY_ID"]
resp = httpx.post(
    f"https://api.algenta.ai/v1/repositories/{repo_id}/security-analyses/closure",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "snapshot_id": os.environ["FIXED_SNAPSHOT_ID"],
        "canonical_finding_id": "finding-sql-injection-001",
        "patch_digest": "sha256:44ab...",
    },
    timeout=300.0,
)
closure = resp.json()
print(closure["closure_status"], closure["alternate_path_found"])
```
{% endtab %}

{% tab title="TypeScript" %}
```ts title="closure.ts"
const repoId = process.env.REPOSITORY_ID!;
const resp = await fetch(
  `https://api.algenta.ai/v1/repositories/${repoId}/security-analyses/closure`,
  {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      snapshot_id: process.env.FIXED_SNAPSHOT_ID,
      canonical_finding_id: "finding-sql-injection-001",
      patch_digest: "sha256:44ab...",
    }),
  },
);
const closure = await resp.json();
console.log(closure.closure_status, closure.alternate_path_found);
```
{% endtab %}
{% endtabs %}

The `200` `SecurityAnalysisClosureResponse` returns:

- `closure_status` — `closed` (the fix removed reachability), `open` (still reachable), or `unknown` (the engine could not prove either way).
- `alternate_path_found` — `true` if the finding is now reachable by a different path than the one you fixed.
- `new_blocking_findings` — canonical ids of any new findings the patch introduced that block closure.

{% hint style="success" %}
**Expected result** — `closure_status: "closed"` with `alternate_path_found: false` and an empty `new_blocking_findings` is a proven fix: the sink is no longer reachable and the patch introduced no new blockers.
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Ship the fix</strong></td><td>Generate, simulate, and apply the patch that closes the finding.</td><td><a href="repository-fix.md">repository-fix.md</a></td></tr>
<tr><td><strong>Snapshot the patched ref</strong></td><td>Create the new snapshot closure re-proves against.</td><td><a href="repository-intelligence.md">repository-intelligence.md</a></td></tr>
<tr><td><strong>Run heavy proofs async</strong></td><td>Poll the 202 handle a large SARIF batch returns.</td><td><a href="async-jobs.md">async-jobs.md</a></td></tr>
</tbody></table>
