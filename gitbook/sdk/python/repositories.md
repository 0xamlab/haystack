---
icon: code-branch
description: Python SDK reference for repository intelligence — capabilities, snapshots, triage, decision plans, graph queries, simulate, and apply.
---

# Repository intelligence methods

These methods drive Algenta's repository intelligence: index a repository into a snapshot, triage where to act, query its code graph, simulate a proposed change, and apply an approved one. They are available on both `AlgentaClient` and `AsyncAlgentaClient` (await the async calls). Each takes a `repository_id` and a request dict, except `get_repository_intelligence_capabilities`. See the [repository intelligence guide](../../guides/repository-intelligence.md) for the end-to-end workflow.

## Method reference

| Method | Purpose |
| --- | --- |
| `get_repository_intelligence_capabilities()` | List the repository intelligence this instance supports (`RepositoryIntelligenceCapabilitiesResult`). Reads `/v1/repositories/capabilities`. |
| `create_repository_snapshot(repository_id, request)` | Index a repository into a snapshot (`RepositorySnapshotResult`). Posts to `/v1/repositories/{repository_id}/snapshots`. |
| `get_repository_snapshot(repository_id, snapshot_id)` | Fetch a stored snapshot (`RepositorySnapshotResult`). Reads `/v1/repositories/{repository_id}/snapshots/{snapshot_id}`. |
| `triage_repository(repository_id, request)` | Rank likely-relevant files and propose where to act (`RepositoryTriageResult`). Posts to `/v1/repositories/{repository_id}/triage`. |
| `create_repository_decision_plan(repository_id, request)` | Produce a decision-plan revision for a repository change (`RepositoryDecisionPlanRevisionResult`). Posts to `/v1/repositories/{repository_id}/decision-plans`. |
| `query_repository_graph(repository_id, request)` | Query the repository's code graph (`RepositoryGraphQueryResult`). Posts to `/v1/repositories/{repository_id}/graph-query`. |
| `simulate_repository(repository_id, request)` | Simulate a proposed change and return a `DecisionEnvelope`. Posts to `/v1/repositories/{repository_id}/simulate`. |
| `apply_repository(repository_id, request)` | Apply an approved change and return the result (`RepositoryApplyResult`). Posts to `/v1/repositories/{repository_id}/apply`. |

## Example: snapshot and triage a repository

```python title="triage.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

# Confirm what the instance supports.
caps = client.get_repository_intelligence_capabilities()
print(caps.supported_languages)

# Index the repository, then rank where to act.
snapshot = client.create_repository_snapshot(
    "$REPOSITORY_ID",
    {"ref": "main"},
)

triage = client.triage_repository(
    "$REPOSITORY_ID",
    {
        "snapshot_id": snapshot.snapshot_id,
        "signals": {"failing_tests": ["test_checkout_totals"]},
    },
)
for item in triage.evidence_items:
    print(item.file_path, item.score)
```

## Example: simulate then apply a change

```python title="simulate_apply.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

# Simulate the proposed change -> DecisionEnvelope.
sim = client.simulate_repository(
    "$REPOSITORY_ID",
    {"decision_plan_id": "$DECISION_PLAN_ID"},
)
print(sim.recommended_action, sim.confidence)

# Apply the approved change.
applied = client.apply_repository(
    "$REPOSITORY_ID",
    {
        "decision_plan_id": "$DECISION_PLAN_ID",
        "simulation_id": "$SIMULATION_ID",
        "mode": "patch_only",
    },
)
print(applied.applied, applied.mode)
```

{% hint style="danger" %}
`apply_repository` can write to your repository. Use `mode: "patch_only"` to only return the diff; `local_branch` and `remote_pr` write, and require `write_permission: true` to authorize the engine to create a branch or open a pull request.
{% endhint %}

## Related pages

{% content-ref url="../../guides/repository-intelligence.md" %}
[repository-intelligence.md](../../guides/repository-intelligence.md)
{% endcontent-ref %}

{% content-ref url="simulations-and-queries.md" %}
[simulations-and-queries.md](simulations-and-queries.md)
{% endcontent-ref %}

{% content-ref url="../../api/reference.md" %}
[reference.md](../../api/reference.md)
{% endcontent-ref %}
