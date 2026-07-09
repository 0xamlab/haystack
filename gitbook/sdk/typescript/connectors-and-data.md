---
icon: plug
description: TypeScript SDK methods for connectors, datasets, source registration, and repository intelligence — create, test, browse, onboard, snapshot, triage, and apply.
---

# Connectors and data

These `AlgentaClient` methods bring data into the engine and turn it into governed evidence: **connectors** (create, test, browse, update, delete), **datasets** (connect, list, summarize, refresh, delete), **source registration**, and **repository intelligence** (snapshot, triage, graph, simulate, apply). Method names are `camelCase`; bodies stay `snake_case`.

## Connector methods

Create a connector, test it against the live source, then browse the tables it exposes. The `preview*` variants test or browse an unsaved connector from an inline config, without persisting it first.

```typescript title="connectors.ts"
import { AlgentaClient } from "algenta-sdk";

const client = new AlgentaClient({ apiKey: process.env.ALGENTA_API_KEY });

// 1. Create a connector.
const connector = await client.createConnector({
  name: "Analytics Warehouse",
  connector_type: "snowflake",
  config: {
    account: "xy12345.eu-central-1",
    user: "ANALYTICS",
    password: process.env.SNOWFLAKE_PASSWORD,
    warehouse: "COMPUTE_WH",
    database: "SALES",
    schema: "PUBLIC",
  },
});

// 2. Test the live connection, then browse its tables.
const test = await client.testConnector(connector.id);
if (test.success) {
  const browse = await client.browseConnector(connector.id);
  console.log(browse.total, "tables");
}
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `createConnector(request)` | `POST /v1/connectors` | `name`, `connector_type`, and a `config`; returns `ConnectorInfo` with `status: "untested"`. |
| `listConnectors(options?)` | `GET /v1/connectors` | Paginate with `page`, `limit`. |
| `getConnector(connectorId)` | `GET /v1/connectors/{id}` | Fetch one connector. |
| `updateConnector(connectorId, request)` | `PATCH /v1/connectors/{id}` | Update `name`, `description`, `visibility`, or `config`. |
| `testConnector(connectorId)` | `POST /v1/connectors/{id}/test` | Real connection health check; flips status to `live` or `error`. |
| `previewTestConnector(request)` | `POST /v1/connectors/test` | Test an unsaved connector from a `{ connector_type, config }` body. |
| `browseConnector(connectorId)` | `GET /v1/connectors/{id}/browse` | List the tables a `live` connector exposes. |
| `previewBrowseConnector(request)` | `POST /v1/connectors/browse` | Browse an unsaved connector from a `{ connector_type, config }` body. |
| `deleteConnector(connectorId)` | `DELETE /v1/connectors/{id}` | Remove a connector; resolves to `void`. |

{% hint style="warning" %}
`browseConnector` requires a `live` connector. Call `testConnector` first — browsing a connector that has not passed its test returns a not-connected error.
{% endhint %}

## Dataset methods

`connectData` onboards a selection (a table or a SQL query) from a saved connector as a queryable dataset. The rest of the family lists, inspects, refreshes, and deletes datasets. `listDatasets` supports `search`, `status`, `sourceName` (sent as `source_name`), and `compact`.

| Method | HTTP | Notes |
| --- | --- | --- |
| `connectData(request)` | `POST /v1/data/connect` | Onboard a `selection` from a `connection_id`; returns a `DatasetConnectResult`. |
| `listDatasets(options?)` | `GET /v1/data` | Filter with `search`, `status`, `sourceName`; `compact` returns lighter rows. |
| `getDataset(datasetId)` | `GET /v1/data/{id}` | Full dataset detail. |
| `getDatasetSummary(datasetId)` | `GET /v1/data/{id}/summary` | Schema, fields, and row counts. |
| `refreshDataset(datasetId)` | `POST /v1/data/{id}/refresh` | Re-ingest the dataset; returns a `DatasetConnectResult`. |
| `deleteDataset(datasetId)` | `DELETE /v1/data/{id}` | Remove a dataset. |

```typescript title="datasets.ts"
// Onboard a table from a saved connector.
const dataset = await client.connectData({
  connection_type: "database",
  provider: "snowflake",
  dataset_name: "sales_orders",
  connection_id: connector.id,
  selection: { table: "PUBLIC.ORDERS" },
  visibility: "private",
});

// Inspect what was onboarded.
const summary = await client.getDatasetSummary(dataset.dataset_id);
console.log(summary.dataset_id, summary.name);
```

## Source registration methods

`registerSource` registers a raw source object as a dataset in one call; the optional second argument sets a `description` and `name`. `refreshSource` re-ingests a registered source by its dataset id.

| Method | HTTP | Notes |
| --- | --- | --- |
| `registerSource(source, options?)` | `POST /v1/sources/register` | `source` is the source object; `options` sets `{ description, name }`. |
| `refreshSource(datasetId)` | `POST /v1/data/{id}/refresh` | Re-ingest a registered source; returns a `SourceRegistrationResponse`. |

## Repository intelligence methods

Repository intelligence turns a code repository into governed evidence. Snapshot the repo, triage an issue into ranked evidence, walk the symbol graph, simulate a candidate decision plan, and apply the result as a patch, branch, or pull request. Start by checking which languages the engine supports.

```typescript title="repository_intelligence.ts"
const capabilities = await client.getRepositoryIntelligenceCapabilities();
console.log(capabilities.supported_languages.length);

// 1. Snapshot the repository.
const snapshot = await client.createRepositorySnapshot("repo_42", {
  ref: "main",
  include_patterns: ["src/**"],
  max_files: 5000,
});

// 2. Triage an issue into ranked evidence.
const triage = await client.triageRepository("repo_42", {
  snapshot_id: snapshot.snapshot_id,
  signals: {
    issue_text: "Null pointer when the cart is empty at checkout",
    failing_tests: ["test_checkout_empty_cart"],
  },
  max_evidence_items: 20,
});

// 3. Walk the symbol graph around a symbol.
const graph = await client.queryRepositoryGraph("repo_42", {
  snapshot_id: snapshot.snapshot_id,
  symbol_name: "checkout",
  direction: "both",
  max_depth: 2,
});
console.log(triage.evidence?.length, graph.nodes?.length);
```

| Method | HTTP | Notes |
| --- | --- | --- |
| `getRepositoryIntelligenceCapabilities()` | `GET /v1/repositories/capabilities` | Supported languages and support progress. |
| `createRepositorySnapshot(repositoryId, request)` | `POST /v1/repositories/{id}/snapshots` | `ref` and optional `include_patterns`, `exclude_patterns`, `max_files`. |
| `getRepositorySnapshot(repositoryId, snapshotId)` | `GET /v1/repositories/{id}/snapshots/{snapshotId}` | Fetch one snapshot. |
| `triageRepository(repositoryId, request)` | `POST /v1/repositories/{id}/triage` | Ranked evidence from `signals` (`issue_text`, `failing_tests`, `changed_files`). |
| `createRepositoryDecisionPlan(repositoryId, request)` | `POST /v1/repositories/{id}/decision-plans` | Plan from a `workspace_evidence_bundle_ref`; optional `model`. |
| `queryRepositoryGraph(repositoryId, request)` | `POST /v1/repositories/{id}/graph-query` | Symbol/file graph; `direction` is `inbound`, `outbound`, or `both`. |
| `simulateRepository(repositoryId, request)` | `POST /v1/repositories/{id}/simulate` | Returns a `DecisionEnvelope` for a `decision_plan_id`. |
| `applyRepository(repositoryId, request)` | `POST /v1/repositories/{id}/apply` | `mode` is `patch_only`, `local_branch`, or `remote_pr`. |

{% hint style="warning" %}
`applyRepository` with `mode: "local_branch"` or `"remote_pr"` writes to your repository. It requires `write_permission: true` and a `simulation_id` from a prior `simulateRepository` call. Use `mode: "patch_only"` to get the diff without writing anything.
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Connect Snowflake step by step</strong></td><td>Create a connector and onboard a table as a dataset.</td><td><a href="../../connectors/snowflake.md">../../connectors/snowflake.md</a></td></tr>
<tr><td><strong>Query governed data</strong></td><td>Run deterministic queries over onboarded datasets.</td><td><a href="simulations-and-queries.md">simulations-and-queries.md</a></td></tr>
<tr><td><strong>Fix an issue with repository intelligence</strong></td><td>Snapshot, triage, simulate, and apply a fix.</td><td><a href="../../guides/repository-intelligence.md">../../guides/repository-intelligence.md</a></td></tr>
</tbody></table>
