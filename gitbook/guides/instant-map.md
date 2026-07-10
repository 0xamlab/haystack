---
icon: sitemap
description: Drop in CSV, JSON, or connected tables and get back a unified schema with every field mapped, join keys detected, and confidence for each match — no schema, no ETL.
---

# Map a dataset instantly

`POST /v1/map` connects and understands any dataset with zero configuration. Hand it one or more sources — CSV text, JSON records, a URL, base64 Excel/Parquet, a connector config, or the id of a source you already registered — and the engine returns a unified schema: which fields mean the same thing across sources, their distribution shapes, polarity (revenue is positive, cost is negative), detected join keys, and a plain-English reason and confidence for every mapping.

Mapping runs a two-speed pipeline. Phase 1 (the unified schema plus column matches) returns immediately. Phase 2 (join-key detection and derived formulas like `A × B ≈ C`) is embedded in the same response when it finishes fast; otherwise the response sets `deep_analysis_pending: true` and you poll `GET /v1/map/{map_id}` for the rest.

## Before you start

You need:

- An API key sent as `Authorization: Bearer $ALGENTA_API_KEY`.
- At least one data source. The examples use inline `csv`, but every `DataSource` accepts exactly one payload field — pick whichever you have.

| Field | Use it for |
| --- | --- |
| `records` | Inline JSON array of objects (fastest inline path). |
| `csv` | Raw CSV text. |
| `json_str` | Raw JSON array/object text (nested JSON is auto-flattened). |
| `url` | An HTTP(S) URL; format auto-detected from content type/extension. |
| `excel_b64` / `parquet_b64` | A base64-encoded `.xlsx` or Parquet file. |
| `connection` | A connector config dict (`sql`, `rest_api`, `s3`, `gcs`, `azure_blob`). |
| `source_id` / `dataset_id` | A source you already registered — avoids re-uploading data. |

## Map your sources

{% stepper %}
{% step %}
### Send the sources to `/v1/map`

Every source needs a `name`. `min_confidence` (default `0.5`) sets the threshold below which a mapping is dropped; `include_statistics` (default `true`) keeps distribution stats in the response.

{% tabs %}
{% tab title="cURL" %}
```bash title="map.sh"
curl -sS -X POST "https://api.algenta.ai/v1/map" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "sources": [
      {"name": "sales",  "csv": "order_id,revenue,cost\n1,1200,800\n2,900,600"},
      {"name": "orders", "csv": "id,amount,qty\n1,1200,3\n2,900,2"}
    ],
    "min_confidence": 0.5
  }'
```
{% endtab %}

{% tab title="Python" %}
```python title="map.py"
import os
import requests

BASE = os.environ.get("ALGENTA_API_URL", "https://api.algenta.ai")

resp = requests.post(
    f"{BASE}/v1/map",
    headers={"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"},
    json={
        "sources": [
            {"name": "sales",  "csv": "order_id,revenue,cost\n1,1200,800\n2,900,600"},
            {"name": "orders", "csv": "id,amount,qty\n1,1200,3\n2,900,2"},
        ],
        "min_confidence": 0.5,
    },
)
resp.raise_for_status()
data = resp.json()

for m in data["mappings"]:
    print(f"{m['confidence']:.0%}  {m['source']}.{m['source_field']} -> {m['target']}.{m['target_field']}")
```
{% endtab %}

{% tab title="TypeScript" %}
```typescript title="map.ts"
const base = process.env.ALGENTA_API_URL ?? "https://api.algenta.ai";

const res = await fetch(`${base}/v1/map`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${process.env.ALGENTA_API_KEY}`,
    "Content-Type": "application/json",
  },
  body: JSON.stringify({
    sources: [
      { name: "sales",  csv: "order_id,revenue,cost\n1,1200,800\n2,900,600" },
      { name: "orders", csv: "id,amount,qty\n1,1200,3\n2,900,2" },
    ],
    min_confidence: 0.5,
  }),
});
if (!res.ok) throw new Error(`map failed: ${res.status}`);
const data = await res.json();
console.log(data.mappings);
```
{% endtab %}
{% endtabs %}

The `200` `MapResponse` carries the unified schema, the ranked field mappings, and the deep-analysis fields:

```json title="map-response.json"
{
  "map_id": "1f3c9a2e-4b7d-4a11-9c6e-0f2b8d5a7c31",
  "sources_analyzed": 2,
  "total_fields": 6,
  "mappings": [
    {
      "source_field": "revenue",
      "source": "sales",
      "target_field": "amount",
      "target": "orders",
      "confidence": 0.86,
      "reason": ["semantic match: revenue ~ amount", "overlapping value distribution"],
      "match_type": "semantic"
    }
  ],
  "unified_schema": [
    {
      "name": "revenue",
      "sources": ["sales", "orders"],
      "distribution": "lognormal",
      "unit": "USD",
      "polarity": 1,
      "sample_values": [1200, 900]
    }
  ],
  "join_keys": [],
  "derived_relationships": [],
  "simulation_ready": true,
  "simulation_payload": {},
  "deep_analysis_pending": false,
  "latency_ms": 42.3
}
```

Each mapping's `match_type` is one of `exact`, `semantic`, or `statistical`; `confidence` is `0`–`1`; `reason` is a short list of human-readable justifications. Keep `map_id` — you need it if deep analysis is still running.
{% endstep %}

{% step %}
### Poll for deep analysis if it is pending

When the response has `deep_analysis_pending: true`, join keys and derived relationships are still computing. Poll with the `map_id`:

`GET /v1/map/{map_id}`

```bash title="poll.sh"
curl -sS "https://api.algenta.ai/v1/map/$MAP_ID" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

A `200` returns the completed `join_keys`, `derived_relationships`, and `simulation_payload`. While the work is still in flight the endpoint returns `404` with `"map_id not found or still processing"` — retry after a short backoff. Results are scoped to your organization, so a `map_id` from another org is never readable.
{% endstep %}

{% step %}
### Promote a source to a queryable dataset (optional)

Mapping is stateless. To persist a source and query it later, connect it as a dataset with `POST /v1/data/connect`:

```bash title="connect.sh"
curl -sS -X POST "https://api.algenta.ai/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "dataset_name": "sales",
    "csv": "order_id,revenue,cost\n1,1200,800\n2,900,600",
    "visibility": "private"
  }'
```

The response carries a `dataset_id` you reuse across the `/v1/data/*` endpoints below and in [governed queries](governed-query.md).
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result** — `/v1/map` returns `200` with `sources_analyzed` matching the number of sources you sent, a non-empty `unified_schema`, and a `mappings` list ranked by `confidence`. `simulation_ready: true` means the schema has enough numeric metric fields to run a decision on.
{% endhint %}

## Manage datasets

Once a source is connected, these routes list, inspect, refresh, and disconnect it. All are scoped to the caller's workspace.

| Method & path | What it does |
| --- | --- |
| `GET /v1/data` | List visible datasets. Supports `page`, `limit`, `search`, `status`, `source_name`, `compact`. |
| `GET /v1/data/{dataset_id}` | Get one dataset plus its full schema. |
| `GET /v1/data/{dataset_id}/summary` | Low-token discovery summary (row/column counts, query hints). |
| `POST /v1/data/{dataset_id}/refresh` | Re-pull the dataset from its saved origin. |
| `DELETE /v1/data/{dataset_id}` | Disconnect the dataset (and its connector when nothing else uses it). |

## Map locally with the CLI

The source-built `algenta` CLI runs the same mapping on your machine — no server, no key, no network. Use it to preview data before you send anything to the engine. The local runtime package is not a public PyPI install yet.

```bash title="local-map.sh"
git clone https://github.com/thyn-ai/algenta.git
cd algenta
python3 -m pip install -e packages/algenta

# Map one or more files and see cross-table field matches + join keys
algenta map sales.csv orders.csv

# Import preview: validates local registration + schema discovery, prints the Runtime snippet
algenta import orders.csv --name orders

# Deterministic natural-language query over local files
algenta query "total revenue by customer" sales.csv
```

`algenta map` prints the mapping table, detected join keys, and whether the schema is simulation-ready. `algenta import` ends with a copy-pasteable `Runtime` snippet so you can continue in Python.

{% hint style="info" %}
The CLI runs entirely locally and fails closed — it never silently falls back to the cloud. Run `algenta upgrade` when you are ready to point the same code at your engine over the API.
{% endhint %}

## Next steps

<table data-view="cards"><thead><tr><th></th><th></th><th data-hidden data-card-target data-type="content-ref"></th></tr></thead>
<tbody>
<tr><td><strong>Query your mapped data</strong></td><td>Ask questions over a connected dataset.</td><td><a href="governed-query.md">governed-query.md</a></td></tr>
<tr><td><strong>Connect a data source</strong></td><td>Register databases and object storage as reusable connectors.</td><td><a href="connect-data.md">connect-data.md</a></td></tr>
<tr><td><strong>Recommend a decision</strong></td><td>Turn the mapped schema into a ranked recommendation.</td><td><a href="recommend-and-score.md">recommend-and-score.md</a></td></tr>
</tbody></table>
