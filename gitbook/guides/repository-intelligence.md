---
icon: magnifying-glass-chart
description: Triage a code repository with the Algenta engine — snapshot it, reduce it to a bounded evidence bundle, and read back the findings over the HTTP API
---

# Triage a repository

Repository intelligence is a [capability plane](../concepts/capability-plane.md) of the Algenta engine: you point it at a code repository, it builds an immutable snapshot, and it reduces the whole tree down to a small, ranked evidence bundle focused on the signals you supply (an issue description, failing tests, diagnostics, changed files). The reduction is deterministic and server-side — the engine does the parsing, graphing, and ranking so a downstream agent or LLM never has to read the raw repository.

This guide covers the core triage flow: register a repository connector, create a snapshot, run triage, and read the results. All routes live under `/v1/repositories` and require authentication.

{% hint style="info" %}
Repository intelligence is the server-side capability plane. The SDK entry `rt.triage_repository(...)` is only a thin trigger over this HTTP API — it never runs analysis in your process. Treat the engine (self-hosted or `$ALGENTA_API_URL`) as the boundary. See [Capability plane](../concepts/capability-plane.md).
{% endhint %}

## Before you start

You need:

- An API key sent as `Authorization: Bearer <key>` (the legacy `X-API-Key` header is also accepted).
- A **repository connector**, whose id becomes the `$REPO_ID` you pass in every repository path. The connector records where the code lives and (for private remotes) an access token. Supported `connector_type` source kinds are:

| Source kind | `connector_type` | Where the code is | Config keys |
| --- | --- | --- | --- |
| GitHub | `github_repo` | a clone URL | `repository_url` (or `clone_url` / `url`), optional `access_token` (or `token` / `api_token`) |
| GitLab | `gitlab_repo` | a clone URL | same as above |
| Bitbucket | `bitbucket_repo` | a clone URL | same as above |
| Local checkout | `local_repo` | a path the engine can read | `path` |
| Archive | `repo_archive` | an extracted archive path | `path` |

Create the connector once, then reuse its id:

```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-service",
    "connector_type": "github_repo",
    "config": {
      "repository_url": "https://github.com/acme/my-service",
      "access_token": "$GITHUB_TOKEN"
    }
  }'
```

The `201` response contains an `id` — export it as `$REPO_ID` for the steps below. See [Connect data](connect-data.md) for the full connector lifecycle.

{% hint style="warning" %}
`$ALGENTA_API_URL` defaults to `https://api.algenta.ai`. Local checkouts (`local_repo`) and archives (`repo_archive`) are the self-hosted path — the engine must be able to read the configured `path` on its own host.
{% endhint %}

## The flow

Triage runs in two steps: create an immutable **snapshot** of a ref, then **triage** that snapshot against your signals.

{% stepper %}
{% step %}
### Create a snapshot

A snapshot pins one revision of the repository and pre-computes the parse, symbol graph, and dependency graph. Snapshots are content-addressed and reused, so the same ref + scope returns `status: "existing"` instead of re-parsing.

`POST /v1/repositories/{repository_id}/snapshots`

```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/repositories/$REPO_ID/snapshots" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "ref": "main",
    "focus_paths": ["src/payments"],
    "max_files": 20000
  }'
```

All snapshot fields are optional. `ref` defaults to the connector's default branch; `focus_paths`, `include_patterns`, and `exclude_patterns` scope which files are pulled in; `max_files` (default `20000`), `max_file_size_bytes` (default `1000000`), and `max_total_bytes` cap the snapshot size.

**Expected result:** a `200` `RepositorySnapshotResponse` carrying the `snapshot_id` you pass to triage, plus `resolved_revision`, `content_hash`, `status` (`"created"` or `"existing"`), `file_count`, `language_counts`, `raw_repo_token_estimate`, and refs to the persisted artifacts (`repository_snapshot_artifact`, `repository_graph_artifact`, `symbol_graph_artifact`, `dependency_graph_artifact`). Save `snapshot_id` as `$SNAPSHOT_ID`.
{% endstep %}

{% step %}
### Triage the snapshot

Triage takes the snapshot plus your **signals** and returns a bounded, ranked evidence bundle — the suspect files and symbols, with scored snippets, fit inside a token budget.

`POST /v1/repositories/{repository_id}/triage`
{% endstep %}
{% endstepper %}

## Submit a triage request

The request names the snapshot and supplies `signals` — the issue text and any failing tests, diagnostics, changed files, or workspace context you have. `max_evidence_items` (default `16`), `max_snippet_lines` (default `40`), and `token_budget` (default `6000`) bound the output.

{% tabs %}
{% tab title="cURL" %}
```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/repositories/$REPO_ID/triage" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_id": "'"$SNAPSHOT_ID"'",
    "signals": {
      "issue_text": "Refund webhook double-charges on retry",
      "failing_tests": ["tests/test_refunds.py::test_idempotent_retry"],
      "changed_files": ["src/payments/refund.py"],
      "diagnostics": [
        {"path": "src/payments/refund.py", "line": 88, "severity": "error", "message": "duplicate ledger write"}
      ]
    },
    "max_evidence_items": 16,
    "token_budget": 6000
  }'
```
{% endtab %}

{% tab title="Python" %}
```python
import os
from decision_engine import Client

client = Client(
    base_url=os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai"),
    api_key=os.environ["ALGENTA_API_KEY"],
)

repo_id = os.environ["REPO_ID"]

# Snapshot a ref (reused if it already exists).
snapshot = client.create_repository_snapshot(
    repo_id,
    {"ref": "main", "focus_paths": ["src/payments"]},
)

# Triage that snapshot against the signals you have.
result = client.triage_repository(
    repo_id,
    {
        "snapshot_id": snapshot.snapshot_id,
        "signals": {
            "issue_text": "Refund webhook double-charges on retry",
            "failing_tests": ["tests/test_refunds.py::test_idempotent_retry"],
            "changed_files": ["src/payments/refund.py"],
        },
        "max_evidence_items": 16,
        "token_budget": 6000,
    },
)

print(result.suspect_files, result.reduction_ratio)
for item in result.evidence_items:
    print(item.rank, item.file_path, item.summary)
```
{% endtab %}
{% endtabs %}

**Expected result:** a `200` `RepositoryTriageResponse`. The key fields:

- `workspace_evidence_bundle_ref` — the handle to the persisted bundle, which you can feed into a [graph query](#explore-impact-optional), a decision plan, or an [agent run](agent-runs.md).
- `suspect_files` / `suspect_symbols` — the engine's ranked guess at where the problem lives.
- `evidence_items` — the bundle itself: each item has a `rank`, a `source_type` (`diagnostic`, `failing_test`, `changed_file`, `workspace_context`, or `repository_file`), `source_ref`, optional `file_path` / `symbol_name`, a `summary`, a `snippet`, a `token_count`, and a `score`.
- `raw_repo_token_estimate`, `evidence_bundle_token_count`, and `reduction_ratio` — how much the engine compressed the repository (a `reduction_ratio` of `40.0` means the bundle is 1/40th the size of the raw tree).
- `workspace_evidence_bundle_artifact` — the immutable artifact reference (`artifact_id`, `artifact_kind`, `content_hash`, `storage_path`, `created_at`).

{% hint style="success" %}
The evidence bundle is deterministic for a given snapshot + signals. The same inputs yield the same `content_hash`, so you can cache and replay triage without re-running the engine.
{% endhint %}

## Explore impact (optional)

To trace blast radius from the suspect files or symbols — what depends on them and what they depend on — query the dependency graph. Seed it with the `snapshot_id` or the `workspace_evidence_bundle_ref` from triage:

`POST /v1/repositories/{repository_id}/graph-query`

```bash
curl -sS -X POST "$ALGENTA_API_URL/v1/repositories/$REPO_ID/graph-query" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "snapshot_id": "'"$SNAPSHOT_ID"'",
    "file_path": "src/payments/refund.py",
    "direction": "both",
    "max_depth": 2,
    "max_nodes": 128
  }'
```

You must supply `snapshot_id` or `workspace_evidence_bundle_ref` as the seed source. The `200` `RepositoryGraphQueryResponse` returns `direct_dependencies`, `direct_dependents`, `impacted_files`, `impacted_symbols`, full `graph_nodes` and `graph_edges`, and `top_change_risk_files` (each with a `relationship` of `seed`, `dependent`, `dependency`, or `connected` and a `risk_score`).

## Running large analyses asynchronously

Triage itself returns inline. The heavier downstream stages — a security analysis over a SARIF batch, a decision plan, or the one-call `pipeline` (snapshot → triage → plan → simulate) — accept an `async_execution=true` query parameter. When set, the engine takes the work off the request path and returns **`202 Accepted`** with a poll handle instead of the result:

```json
{
  "job_id": "...",
  "status": "queued",
  "job_kind": "repository_pipeline",
  "poll_url": "https://api.algenta.ai/v1/jobs/...",
  "message": "Repository job queued. Poll the poll_url for status and result."
}
```

Poll `GET /v1/jobs/{job_id}` for status and `GET /v1/jobs/{job_id}/result` for the completed payload. See [Run asynchronous jobs](agent-runs.md) for the full async pattern.

{% hint style="info" %}
Every repository compute call is rate-limited per minute and counted against your monthly quota (an over-cap call returns `429`). Free-tier storage caps may also apply. Errors return a structured `{ "error": { "code", "message", "details", "request_id" } }` body — see [API errors](../api/reference.md).
{% endhint %}

## Capabilities check

To see which languages the engine parses today and how far language support has progressed, call:

`GET /v1/repositories/capabilities`

It returns `supported_languages` and a `support_progress` object (`progress_fraction`, `progress_label`, and supported/target language counts). This route is unmetered.

## Next steps

- [Run asynchronous jobs](agent-runs.md) — poll the `202` job handle returned by pipeline and security analyses.
- [Connect data](connect-data.md) — register and manage the repository connector that gives you `$REPO_ID`.
- [Capability plane](../concepts/capability-plane.md) — how triage fits the engine's server-side capability model.
- [API reference](../api/reference.md) — full request/response schemas, status codes, and error shapes.
- [Glossary](../help/glossary.md) — definitions for snapshot, evidence bundle, and connector terms.
