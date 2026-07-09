---
icon: code-branch
description: MCP reference for Algenta's repository-intelligence tools — snapshot, triage, plan, graph-query, simulate, and apply a code fix from any MCP client.
---

# Repository intelligence MCP tools

These tools drive Algenta's repository-intelligence lane over MCP: take an immutable snapshot of a saved repository connector, triage it into a bounded evidence bundle, plan a fix, query the dependency graph, simulate patch risk, and apply the result as a patch, a local branch, or a pull request. Every tool is a thin, one-to-one wrapper over an authenticated `/v1/repositories` endpoint, so anything you do here you can reproduce with `curl`.

Before you start, install and configure `algenta-mcp` so the `algenta` tools appear in your client — see [MCP server](../sdk/mcp.md). Most tools need a `$REPOSITORY_ID` from a saved repository connector; snapshot, plan, and simulate steps then hand you a `$SNAPSHOT_ID`, `$DECISION_PLAN_ID`, and `$SIMULATION_ID` to chain forward.

{% hint style="info" %}
Prefer `run_repository_pipeline` for the common path: it runs snapshot → triage → plan → simulate in one call and returns the canonical repository envelope. Reach for the individual tools when you need to inspect or override a single stage.
{% endhint %}

## Tools

| Tool | What it does | Key inputs |
|------|--------------|------------|
| `get_repository_intelligence_capabilities` | List globally supported languages and their ranked support levels. | _(none)_ |
| `create_repository_snapshot` | Create or reuse an immutable snapshot for a saved repository connector. | `repository_id` (required); `ref`, `include_patterns`, `exclude_patterns`, `max_files`, `max_file_size_bytes` |
| `get_repository_snapshot` | Fetch one immutable snapshot by id. | `repository_id`, `snapshot_id` (both required) |
| `triage_repository` | Triage a snapshot into a bounded workspace evidence bundle of suspect files and symbols. | `repository_id`, `snapshot_id`, `signals` (all required); `max_evidence_items`, `max_snippet_lines`, `token_budget` |
| `create_repository_decision_plan` | Create one immutable DecisionPlan revision from an evidence bundle (resolves `snapshot_id` from triage when omitted). | `repository_id`, `workspace_evidence_bundle_ref` (required); `snapshot_id`, `model` |
| `query_repository_graph` | Query a snapshot for dependency, dependent, and change-risk graph edges. | `repository_id` (required) + `snapshot_id` **or** `workspace_evidence_bundle_ref`; `file_path`, `symbol_name`, `direction` (`inbound`\|`outbound`\|`both`), `max_depth` (1–6), `max_nodes` (1–1024) |
| `simulate_repository` | Simulate patch risk and return the gated DecisionEnvelope (resolves `snapshot_id` from the plan when omitted). | `repository_id`, `decision_plan_id` (required); `snapshot_id`, `runs` (≥100), `seed` |
| `run_repository_pipeline` | Run the snapshot → triage → plan → simulate chain and return the canonical repository envelope. | `repository_id` (required); `snapshot_id`, `snapshot`, `signals`, `max_evidence_items`, `max_snippet_lines`, `token_budget`, `model`, `runs`, `seed`, `stop_after` (`snapshot`\|`triage`\|`plan`\|`simulate`) |
| `simulate_repository_patch` | Simulate an in-flight patch diff and return the canonical repository envelope. | `repository_id`, `snapshot_id`, `patch_diff` (required); `confidence` (0.0–1.0) |
| `run_repository_fix` | Run the pipeline, then apply the result, in one call. | `repository_id` (required); `pipeline` (object), `apply` (object) |
| `apply_repository` | Apply a simulated decision as `patch_only`, `local_branch`, or `remote_pr`. | `repository_id`, `decision_plan_id`, `simulation_id`, `mode` (required); `snapshot_id`, `write_permission`, `branch_name`, `commit_message`, `base_branch`, `pull_request_title`, `pull_request_body` |

{% hint style="warning" %}
`mode: "patch_only"` never writes to your repository — it returns the diff. `local_branch` and `remote_pr` do write; pass `write_permission: true` to authorize the engine to create a branch or open a pull request.
{% endhint %}

## Endpoint mapping

Each tool maps to exactly one endpoint, so you can verify any call against the raw API.

| Tool | Method | Endpoint |
|------|--------|----------|
| `get_repository_intelligence_capabilities` | `GET` | `/v1/repositories/capabilities` |
| `create_repository_snapshot` | `POST` | `/v1/repositories/{repository_id}/snapshots` |
| `get_repository_snapshot` | `GET` | `/v1/repositories/{repository_id}/snapshots/{snapshot_id}` |
| `triage_repository` | `POST` | `/v1/repositories/{repository_id}/triage` |
| `create_repository_decision_plan` | `POST` | `/v1/repositories/{repository_id}/decision-plans` |
| `query_repository_graph` | `POST` | `/v1/repositories/{repository_id}/graph-query` |
| `simulate_repository` | `POST` | `/v1/repositories/{repository_id}/simulate` |
| `run_repository_pipeline` | `POST` | `/v1/repositories/{repository_id}/pipeline` |
| `simulate_repository_patch` | `POST` | `/v1/repositories/{repository_id}/simulate-patch` |
| `run_repository_fix` | `POST` | `/v1/repositories/{repository_id}/pipeline` then `/v1/repositories/{repository_id}/apply` |
| `apply_repository` | `POST` | `/v1/repositories/{repository_id}/apply` |

## Worked examples

### Run the full pipeline in one call

Give the engine a `$REPOSITORY_ID` and a free-form `signals` object describing what is wrong. The `signals` payload is illustrative — any evidence the model can use to locate the fault is valid.

{% code title="run_repository_pipeline (tool call)" %}
```json
{
  "name": "run_repository_pipeline",
  "arguments": {
    "repository_id": "$REPOSITORY_ID",
    "signals": {
      "failing_test": "test_checkout_totals",
      "error_message": "AssertionError: expected 42, got 41",
      "stack_trace": ["src/checkout/totals.py:88"]
    },
    "runs": 1000,
    "seed": 7
  }
}
```
{% endcode %}

The canonical envelope carries the ids you need to apply the fix (output abbreviated):

```json title="pipeline envelope (abbreviated)"
{
  "pipeline": {
    "snapshot_id": "$SNAPSHOT_ID",
    "plan_id": "$DECISION_PLAN_ID",
    "simulation_id": "$SIMULATION_ID"
  }
}
```

Reproduce it directly against the endpoint:

```bash
curl -sS "$ALGENTA_BASE_URL/v1/repositories/$REPOSITORY_ID/pipeline" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "signals": { "failing_test": "test_checkout_totals" }, "runs": 1000 }'
```

### Triage a snapshot on its own

When you want to inspect the evidence bundle before planning, snapshot first, then triage. `triage_repository` returns a bounded bundle of suspect files and symbols within your `token_budget`.

{% code title="triage_repository (tool call)" %}
```json
{
  "name": "triage_repository",
  "arguments": {
    "repository_id": "$REPOSITORY_ID",
    "snapshot_id": "$SNAPSHOT_ID",
    "signals": {
      "error_message": "NullReferenceException in OrderService.Total"
    },
    "max_evidence_items": 12,
    "max_snippet_lines": 40,
    "token_budget": 6000
  }
}
```
{% endcode %}

### Apply a simulated decision as a pull request

Once a decision plan has been simulated, apply it. Use `mode: "remote_pr"` with `write_permission: true` to open a PR from the fix.

{% code title="apply_repository (tool call)" %}
```json
{
  "name": "apply_repository",
  "arguments": {
    "repository_id": "$REPOSITORY_ID",
    "snapshot_id": "$SNAPSHOT_ID",
    "decision_plan_id": "$DECISION_PLAN_ID",
    "simulation_id": "$SIMULATION_ID",
    "mode": "remote_pr",
    "write_permission": true,
    "branch_name": "fix/checkout-totals",
    "commit_message": "Fix off-by-one in checkout totals",
    "base_branch": "main",
    "pull_request_title": "Fix off-by-one in checkout totals",
    "pull_request_body": "Corrects rounding in OrderService.Total."
  }
}
```
{% endcode %}

{% hint style="info" %}
`run_repository_fix` wraps the pipeline and apply in a single tool: pass a `pipeline` object and an `apply` object, and the engine chains the simulation ids for you. It refuses to apply unless the pipeline completed through the simulate stage.
{% endhint %}

## Related pages

{% content-ref url="../guides/repository-intelligence.md" %}
[repository-intelligence.md](../guides/repository-intelligence.md)
{% endcontent-ref %}

{% content-ref url="../sdk/mcp.md" %}
[mcp.md](../sdk/mcp.md)
{% endcontent-ref %}

{% content-ref url="../api/reference.md" %}
[reference.md](../api/reference.md)
{% endcontent-ref %}
