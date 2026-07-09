---
icon: code-branch
description: TypeScript SDK reference for repository intelligence — snapshot a repo, triage an issue into ranked evidence, build a decision plan, query the symbol graph, simulate, and apply a fix.
---

# TypeScript repository intelligence

Repository intelligence turns a code repository into governed, queryable evidence. With `AlgentaClient` you snapshot the repo, triage an issue into ranked evidence, build a decision plan from that evidence, walk the symbol graph, simulate a candidate plan, and apply the result as a patch, a local branch, or a pull request. Method names are camelCase; request bodies stay snake_case, mirroring the [HTTP contract](../../api/overview.md). See the [repository intelligence guide](../../guides/repository-intelligence.md) for the end-to-end story.

```ts title="client.ts"
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({
  apiKey: process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY,
  baseUrl: process.env.ALGENTA_BASE_URL ?? "https://api.algenta.ai",
});
```

## Check support, then snapshot

Start with `getRepositoryIntelligenceCapabilities` to see which languages the engine supports, then take a snapshot with `createRepositorySnapshot`. A snapshot returns a `snapshot_id` plus content hashes and per-artifact references you reuse for every later call.

{% tabs %}
{% tab title="TypeScript" %}
```ts title="snapshot.ts"
const capabilities = await client.getRepositoryIntelligenceCapabilities();
console.log(
  capabilities.supported_languages.length,
  capabilities.support_progress.progress_label,
);

const snapshot = await client.createRepositorySnapshot("$REPOSITORY_ID", {
  ref: "main",
  include_patterns: ["src/**"],
  max_files: 5_000,
});
console.log(snapshot.snapshot_id, snapshot.file_count, snapshot.status);

// Re-read a snapshot later by id.
const again = await client.getRepositorySnapshot("$REPOSITORY_ID", snapshot.snapshot_id);
console.log(again.resolved_revision, again.content_hash);
```
{% endtab %}

{% tab title="cURL" %}
```bash
curl -sS "$ALGENTA_BASE_URL/v1/repositories/$REPOSITORY_ID/snapshots" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{ "ref": "main", "include_patterns": ["src/**"], "max_files": 5000 }'
```
{% endtab %}
{% endtabs %}

## Triage, plan, and inspect the graph

`triageRepository` reduces the whole repo to ranked evidence for a set of `signals` (`issue_text`, `failing_tests`, `changed_files`, `diagnostics`, `workspace_context`) and returns a `workspace_evidence_bundle_ref`. Feed that bundle into `createRepositoryDecisionPlan` to get a `decision_plan_id`, and use `queryRepositoryGraph` to understand blast radius around a file or symbol.

```ts title="triage_plan_graph.ts"
// 1. Triage the issue into ranked evidence.
const triage = await client.triageRepository("$REPOSITORY_ID", {
  snapshot_id: snapshot.snapshot_id,
  signals: {
    issue_text: "Null pointer when the cart is empty at checkout",
    failing_tests: ["test_checkout_empty_cart"],
  },
  max_evidence_items: 20,
});
console.log(triage.suspect_files, triage.reduction_ratio, triage.evidence_items.length);

// 2. Build a decision plan from the evidence bundle.
const plan = await client.createRepositoryDecisionPlan("$REPOSITORY_ID", {
  snapshot_id: snapshot.snapshot_id,
  workspace_evidence_bundle_ref: triage.workspace_evidence_bundle_ref,
});
console.log(plan.decision_plan_id);

// 3. Walk the symbol/file graph around a symbol.
const graph = await client.queryRepositoryGraph("$REPOSITORY_ID", {
  snapshot_id: snapshot.snapshot_id,
  symbol_name: "checkout",
  direction: "both", // "inbound" | "outbound" | "both"
  max_depth: 2,
});
console.log(graph.impacted_files, graph.top_change_risk_files.length);
```

## Simulate, then apply

`simulateRepository` scores a candidate `decision_plan_id` and returns a `DecisionEnvelope`. The envelope exposes the `simulation_id` in `validated_inputs` — pass that to `applyRepository`, which writes the result according to `mode`.

```ts title="simulate_apply.ts"
const decision = await client.simulateRepository("$REPOSITORY_ID", {
  snapshot_id: snapshot.snapshot_id,
  decision_plan_id: plan.decision_plan_id,
  runs: 256,
});
const simulationId = decision.validated_inputs?.simulation_id as string;
console.log(decision.recommended_action, decision.confidence, simulationId);

const applied = await client.applyRepository("$REPOSITORY_ID", {
  snapshot_id: snapshot.snapshot_id,
  decision_plan_id: plan.decision_plan_id,
  simulation_id: simulationId, // from the simulate step's validated_inputs
  mode: "remote_pr", // "patch_only" | "local_branch" | "remote_pr"
  write_permission: true,
  pull_request_title: "Fix empty-cart checkout crash",
});
console.log(applied.applied, applied.pull_request_url, applied.commit_sha);
```

{% hint style="warning" %}
`applyRepository` with `mode: "remote_pr"` or `"local_branch"` writes to your repository. Both require `write_permission: true` and a `simulation_id` from a prior `simulateRepository` call. Use `mode: "patch_only"` to get the unified diff in `patch` without writing anything.
{% endhint %}

## Method reference

| Method | HTTP | Notes |
| --- | --- | --- |
| `getRepositoryIntelligenceCapabilities()` | `GET /v1/repositories/capabilities` | `supported_languages` and `support_progress`. |
| `createRepositorySnapshot(repositoryId, request)` | `POST /v1/repositories/{id}/snapshots` | `RepositorySnapshotCreateRequest` (`ref`, `include_patterns`, `exclude_patterns`, `max_files`, `max_file_size_bytes`). |
| `getRepositorySnapshot(repositoryId, snapshotId)` | `GET /v1/repositories/{id}/snapshots/{snapshot_id}` | Re-read a snapshot by id. |
| `triageRepository(repositoryId, request)` | `POST /v1/repositories/{id}/triage` | `RepositoryTriageRequest` (`snapshot_id`, `signals`, `max_evidence_items`, `max_snippet_lines`, `token_budget`); returns ranked `evidence_items`. |
| `createRepositoryDecisionPlan(repositoryId, request)` | `POST /v1/repositories/{id}/decision-plans` | `RepositoryDecisionPlanCreateRequest` (`workspace_evidence_bundle_ref` required, `snapshot_id`, `model`). |
| `queryRepositoryGraph(repositoryId, request)` | `POST /v1/repositories/{id}/graph-query` | `RepositoryGraphQueryRequest` (`snapshot_id`, `file_path`, `symbol_name`, `direction`, `max_depth`, `max_nodes`). |
| `simulateRepository(repositoryId, request)` | `POST /v1/repositories/{id}/simulate` | `RepositorySimulationRequest` (`decision_plan_id` required, `snapshot_id`, `runs`, `seed`); returns a `DecisionEnvelope`. |
| `applyRepository(repositoryId, request)` | `POST /v1/repositories/{id}/apply` | `RepositoryApplyRequest` (`decision_plan_id`, `simulation_id`, `mode` required; `write_permission`, `branch_name`, `commit_message`, `base_branch`, `pull_request_title`, `pull_request_body`). |

## Related pages

{% content-ref url="../../guides/repository-intelligence.md" %}
[repository-intelligence.md](../../guides/repository-intelligence.md)
{% endcontent-ref %}

{% content-ref url="agent-runs.md" %}
[agent-runs.md](agent-runs.md)
{% endcontent-ref %}

{% content-ref url="../typescript.md" %}
[typescript.md](../typescript.md)
{% endcontent-ref %}
