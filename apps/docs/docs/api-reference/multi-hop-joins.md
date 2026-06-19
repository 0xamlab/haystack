---
sidebar_position: 20
---

# Multi-hop Joins

Use this guide when the metric lives in one governed source and the grouping
dimension or bridge keys live one or more joins away.

Start with [Quickstart](/quickstart), then use [Query](/query) and
[Verify](/verify) as the primary exact-query flow.

## What Codna supports

Codna already supports explicit multi-hop joins on the exact-query surface.

- `POST /v1/query` accepts `join_path`
- `POST /v1/verify` accepts the same exact request body before execution
- the default join budget is `4` hops
- explicit opt-in can raise `join_path.max_hops` to `6` hops (`7` tables)
- every hop can carry `min_confidence`, `expected_cardinality`, and
  `allow_many_to_many`
- `group_column` can live in the terminal `group_source`, not just in the base
  source

Use this surface for exact grouped metrics such as:

- revenue by category through `orders -> order_items -> products -> categories`
- delay minutes by alliance through `flights -> airlines -> alliances`
- survey score by origin airport through `nps_scores -> flights -> airports`

## Pick the right surface

| Need | Surface |
| --- | --- |
| Exact grouped metric through bridge tables | `POST /v1/query` with `join_path` |
| Validate the exact join plan before execution | `POST /v1/verify` with the same body |
| Several exact multihop metrics in one call | `POST /v1/query/batch` |
| Wide joined rowset or custom SQL analysis | `POST /v1/query/sql-report` |

Do **not** use `query_sql_report` as a replacement for ordinary exact grouped
metrics. Use it only when you truly need a custom rowset or custom SQL
calculation shape.

## Mission functionality mapping

If you are porting a governed analysis flow from Mission, use the public
Codna surfaces below. Mission wrappers such as `query_sql_source` and
`register_sql_source` are **not** public hosted endpoints here.

| Mission functionality | Public HTTP / SDK / CLI surface | MCP tool | Checked-in example | Notes |
| --- | --- | --- | --- | --- |
| `list_data` | `GET /v1/data?search=...&compact=1` | `list_data(search=..., compact=true)` | Inline below | Use deterministic search plus `compact=1` for the low-token discovery pass. |
| `get_data_schema` | `GET /v1/data/{dataset_id}/summary` | `get_data_summary(dataset_id=...)` or `get_data_schema(dataset_id=...)` | Inline below | Use summary first. Read `GET /v1/data/{dataset_id}` only when you truly need the full schema body. |
| `ensure_governed_dataset` | `POST /v1/data/connect` | `connect_data(...)` | [`data_connect_request.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/data_connect_request.json) | This is the product-path onboarding surface. Database providers may first return `status = "needs_selection"` with `choices[]`. |
| `query_data` | `POST /v1/resolve` -> optional `POST /v1/verify` -> `POST /v1/query` | `query_data(...)` | [`query_request.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/query_request.json) | Use `join_path` when the metric and grouping dimension live in different governed datasets. |
| `query_data_batch` | `POST /v1/query/batch` | `query_batch(...)` | [`query_batch_request.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/query_batch_request.json) | Use this for several exact governed requests in one ordered response. |
| `query_sql_report` | `POST /v1/query/sql-report` | `query_sql_report(...)` | [`sql_report_request.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/sql_report_request.json) | Use for wide rowsets or custom read-only SQL over already authorized datasets. |
| `query_sql_source` | No one-to-one public endpoint today. Use `POST /v1/query` when the ask fits the exact metric contract, or `POST /v1/query/sql-report` when you need custom SQL/statistical logic. | No one-to-one MCP tool today. Use `query_data(...)` or `query_sql_report(...)`. | [`query_request.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/query_request.json), [`sql_report_correlation_request.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/sql_report_correlation_request.json) | This is the main place users get stuck. Do not look for a public `query_sql_source` route. |
| `get_sources_graph` | No one-to-one public endpoint today. Use `GET /v1/data` plus `GET /v1/data/{dataset_id}/summary`, then send an explicit `join_path`. | No one-to-one MCP tool today. | [`query_request.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/query_request.json) | Public callers provide the exact path directly instead of waiting for a separate graph tool. |
| `map_data_sources` | No one-to-one public endpoint today. Use deterministic dataset discovery and explicit dataset ids/source names. | No one-to-one MCP tool today. | Inline below | Search first, then verify exact dataset ids and source names from the summary response. |
| `register_sql_source` | No one-to-one public hosted endpoint today. For one-off joined analysis use `POST /v1/query/sql-report`. For a persistent governed dataset, materialize it upstream and onboard it with `POST /v1/data/connect`. | No one-to-one MCP tool today. | [`sql_report_correlation_request.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/sql_report_correlation_request.json), [`data_connect_request.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/data_connect_request.json) | Do not assume a transient joined-source registration route exists on the public surface. |

The full machine-readable Mission-to-public surface map lives at:

- [`mission_functionality_surface_map.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/mission_functionality_surface_map.json)

The checked-in MCP sequences for the same Mission governed workflows live at:

- [`mcp_governed_exact_sequence.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/mcp_governed_exact_sequence.json)
- [`mcp_governed_sql_report_sequence.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/mcp_governed_sql_report_sequence.json)

## Discovery-first workflow

1. Discover the governed datasets with `GET /v1/data?search=...&compact=1`.
2. Read `GET /v1/data/{dataset_id}/summary` for exact source names, column
   names, roles, and join hints.
3. Build the exact `join_path`.
4. Send that exact payload to `POST /v1/verify`.
5. Send the same payload to `POST /v1/query`.

Replace every source name, dataset id, key, and column in the examples below
with the exact names from your own schema summary. Do not guess names.

The HTTP and SDK examples below use Cloud Managed defaults. In `self_hosted`
and `air_gapped`, replace `https://api.codna.ai` with your self-hosted base
URL, pass an explicit self-hosted `base_url` / `baseUrl` when constructing
clients, and use the API key provisioned by your self-hosted operator
deployment.

Set the shared auth variables once before running the HTTP examples:

```bash
ALGENTA_API_KEY="${ALGENTA_API_KEY:-${DE_API_KEY:-}}"
if [ -z "$ALGENTA_API_KEY" ]; then
  echo "Set ALGENTA_API_KEY or DE_API_KEY before running this example." >&2
  exit 1
fi

ALGENTA_BASE_URL="${ALGENTA_BASE_URL:-${DE_BASE_URL:-${ALGENTA_API_URL:-https://api.codna.ai}}}"
```

## HTTP example: discover the exact datasets first

```bash
curl -X GET "${ALGENTA_BASE_URL}/v1/data?search=nps_scores&compact=1&limit=5" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"

curl -X GET "${ALGENTA_BASE_URL}/v1/data/dataset_nps_scores/summary" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}"
```

That is the public replacement for Mission-side `list_data` plus
`get_data_schema` during the first governed turn.

## HTTP example: connect a governed dataset

The checked-in onboarding body lives at
[`examples/multi-hop/data_connect_request.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/data_connect_request.json).

```bash
curl -X POST "${ALGENTA_BASE_URL}/v1/data/connect" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @examples/multi-hop/data_connect_request.json
```

If the response returns `status = "needs_selection"`, resend the same endpoint
with the returned `connection_id` plus one exact `selection` object from
`choices[]`. Do not invent the selection payload yourself.

Runnable client-side replacements for the same flow live at:

- [`python_public_client_flow.py`](/Users/angel/Developer/decision-engine/examples/multi-hop/python_public_client_flow.py)
- [`typescript_public_client_flow.ts`](/Users/angel/Developer/decision-engine/examples/multi-hop/typescript_public_client_flow.ts)

## HTTP example: exact multihop metric

The checked-in exact request body lives at
[`examples/multi-hop/query_request.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/query_request.json).

```bash
curl -X POST "${ALGENTA_BASE_URL}/v1/verify" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @examples/multi-hop/query_request.json

curl -X POST "${ALGENTA_BASE_URL}/v1/query" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @examples/multi-hop/query_request.json
```

The example request uses:

- `source_name = "orders_facts"` as the metric-owning base source
- `metric_column = "gross_revenue"`
- `group_column = "category_name"` in the terminal source
- a three-edge join path through `order_items`, `products`, and
  `product_categories`

## Python SDK example

```python
import os

from decision_engine import AlgentaClient

api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
if not api_key:
    raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

client = AlgentaClient(api_key=api_key)

request = {
    "source_name": "orders_facts",
    "metric_column": "gross_revenue",
    "group_column": "category_name",
    "aggregation": "sum",
    "limit": 10,
    "order": "desc",
    "join_path": {
        "base_source": "orders_facts",
        "group_source": "product_categories",
        "edges": [
            {
                "left_source": "orders_facts",
                "right_source": "order_items",
                "left_key": "order_id",
                "right_key": "order_id",
                "expected_cardinality": "one_to_many",
            },
            {
                "left_source": "order_items",
                "right_source": "products",
                "left_key": "product_id",
                "right_key": "id",
                "expected_cardinality": "many_to_one",
            },
            {
                "left_source": "products",
                "right_source": "product_categories",
                "left_key": "category_id",
                "right_key": "id",
                "expected_cardinality": "many_to_one",
            },
        ],
        "max_hops": 4,
        "min_path_confidence": 0.7,
        "reject_on_ambiguity": True,
        "reject_on_fanout": True,
    },
}

verified = client.verify(request)
if not verified.valid:
    raise RuntimeError(verified.errors)

result = client.query_with_metadata(request)
print(result.result)
print(result.join_path)
```

## TypeScript SDK example

```typescript
import { AlgentaClient } from "algenta-sdk";

const apiKey = process.env.ALGENTA_API_KEY ?? process.env.DE_API_KEY;
if (!apiKey) {
  throw new Error("Set ALGENTA_API_KEY or DE_API_KEY before running this example.");
}

const client = new AlgentaClient({
  apiKey,
});

const request = {
  source_name: "orders_facts",
  metric_column: "gross_revenue",
  group_column: "category_name",
  aggregation: "sum",
  limit: 10,
  order: "desc",
  join_path: {
    base_source: "orders_facts",
    group_source: "product_categories",
    edges: [
      {
        left_source: "orders_facts",
        right_source: "order_items",
        left_key: "order_id",
        right_key: "order_id",
        expected_cardinality: "one_to_many",
      },
      {
        left_source: "order_items",
        right_source: "products",
        left_key: "product_id",
        right_key: "id",
        expected_cardinality: "many_to_one",
      },
      {
        left_source: "products",
        right_source: "product_categories",
        left_key: "category_id",
        right_key: "id",
        expected_cardinality: "many_to_one",
      },
    ],
    max_hops: 4,
    min_path_confidence: 0.7,
    reject_on_ambiguity: true,
    reject_on_fanout: true,
  },
};

const verified = await client.verify(request);
if (!verified.valid) {
  throw new Error(JSON.stringify(verified.errors));
}

const result = await client.queryWithMetadata(request);
console.log(result.result);
console.log(result.join_path);
```

## CLI example: exact multihop metric through query-batch

The public CLI does not ship a standalone `de data query <request.json>`
command. For file-based exact execution, use `de data query-batch` with one or
more exact queries.

The checked-in batch request body lives at
[`examples/multi-hop/query_batch_request.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/query_batch_request.json).

```bash
de data query-batch examples/multi-hop/query_batch_request.json
```

That file wraps the same exact `join_path` request inside one batch item so
users can run it from the CLI without inventing a private request shape.

## HTTP or CLI example: wide joined rowset

Use `query_sql_report` only when you need a custom rowset or custom SQL
analysis. The checked-in example lives at
[`examples/multi-hop/sql_report_request.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/sql_report_request.json).

```bash
curl -X POST "${ALGENTA_BASE_URL}/v1/query/sql-report" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @examples/multi-hop/sql_report_request.json

de data sql-report examples/multi-hop/sql_report_request.json
```

That example intentionally uses dataset aliases and a wide joined rowset so
users can see the difference between:

- exact metric execution with `join_path`
- read-only joined rowsets with `query_sql_report`

## HTTP or CLI example: cross-source statistical SQL report

The checked-in statistical example lives at
[`examples/multi-hop/sql_report_correlation_request.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/sql_report_correlation_request.json).

```bash
curl -X POST "${ALGENTA_BASE_URL}/v1/query/sql-report" \
  -H "Authorization: Bearer ${ALGENTA_API_KEY}" \
  -H "Content-Type: application/json" \
  --data @examples/multi-hop/sql_report_correlation_request.json

de data sql-report examples/multi-hop/sql_report_correlation_request.json
```

Use this shape for asks like:

- correlation between delay minutes and NPS score
- percentile tables that need custom SQL
- custom bridge-table joins that do not fit one exact metric response

Do **not** look for a public `query_sql_source` route. The supported public
replacement is `POST /v1/query/sql-report`.

## SDK walkthroughs for Mission users

If your team is translating a Mission workflow and wants copy-pasteable SDK
code instead of endpoint prose, use these checked-in files:

- [`python_public_client_flow.py`](/Users/angel/Developer/decision-engine/examples/multi-hop/python_public_client_flow.py)
- [`typescript_public_client_flow.ts`](/Users/angel/Developer/decision-engine/examples/multi-hop/typescript_public_client_flow.ts)

They show the public replacements for:

- `ensure_governed_dataset`
- `list_data`
- `get_data_schema`
- `query_data`
- `query_data_batch`
- `query_sql_source`

## Mission Mojo LLM modules: current status

Mission also exposes the local Codna runtime library lane through
`get_algenta_library_health`, `list_algenta_libraries`,
`inspect_algenta_library`, and `execute_algenta_library`. That lane is real,
but it is **not** the default replacement for governed multihop data analysis.

Use the split below:

- governed data retrieval, exact grouped metrics, and multihop joins stay on
  `GET /v1/data` -> `GET /v1/data/{dataset_id}/summary` -> `POST /v1/query` or
  `POST /v1/query/sql-report`
- direct deterministic library compute stays on the local/runtime-backed
  library surface

Current Mission implementation status:

- Mission declares `22` Mojo LLM modules in its local runtime catalog
- `19` of those modules currently appear in Mission's end-to-end
  `agent-langgraph-ai-sdk-conversation` coverage
- `vector_kernels.ranker` appears in lower-level source-ranking helpers, not in
  the main conversation harness
- `rerank_eval` and `inference_cost_latency` are cataloged but not currently
  exercised in Mission's checked-in usage paths

This is why users should not assume Mission already routes ordinary multihop
NPS, percentile, denominator, or correlation analysis through those modules.
Mission currently keeps those asks on governed discovery plus exact query / SQL
report surfaces instead.

The checked-in module-by-module status file is:

- [`mission_mojo_llm_module_status.json`](/Users/angel/Developer/decision-engine/examples/multi-hop/mission_mojo_llm_module_status.json)

If you do need the same local runtime-library lane Mission mounts for direct
deterministic compute, use the public local-runtime guide and checked-in
examples instead of inventing wrapper shapes:

- [Local Runtime](/integrations/local-runtime)
- [`python_runtime_library_flow.py`](/Users/angel/Developer/decision-engine/examples/multi-hop/python_runtime_library_flow.py)
- [`typescript_runtime_library_flow.ts`](/Users/angel/Developer/decision-engine/examples/multi-hop/typescript_runtime_library_flow.ts)

## Guardrails that keep users from getting stuck

- Use exact source and column names from schema discovery.
- Keep `reject_on_ambiguity = true` unless you are deliberately handling
  several viable paths.
- Keep `reject_on_fanout = true` unless the fanout is known and intentional.
- Raise `join_path.max_hops` only when the actual path needs it.
- If you need more than `6` hops, redesign the governed surface first. The
  public contract stops at `6` hops (`7` tables).

## Common failure modes

- `join_path_invalid`: one or more sources or keys do not match the exact
  governed schema.
- `join_path_requires_group_column`: the request supplied a join path but did
  not name the terminal grouping column.
- `join_ambiguity`: more than one viable path exists and the score separation is
  too weak for deterministic execution.
- `sql_report_duplicate_source_alias`: two SQL report sources used the same
  alias.
- `not_found` on SQL report sources: one or more `dataset_id` values are not
  visible to the caller.

When this happens, go back to dataset discovery and schema summary. Do not guess
join keys or dataset ids from memory.
