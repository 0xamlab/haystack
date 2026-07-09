---
icon: magnifying-glass
description: Create an Elasticsearch connector with its real config fields, test the connection, browse its indices, onboard one as a dataset, and run a governed query against it.
---

# Connect Elasticsearch

By the end of this page you will have a saved `elasticsearch` connector that reaches your cluster, a confirmed `live` connection test, a browse listing of the indices it exposes, one of those indices onboarded as a queryable **dataset**, and a first [governed query](../guides/governed-query.md) returning documents. Once onboarded, the index becomes [governed data](../concepts/governed-data.md): the engine reads it under a typed, validated contract, so results stay deterministic and auditable.

Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)), and Elasticsearch access — a cluster URL and a base64-encoded API key. A self-managed cluster and an Elastic Cloud deployment both work. Use `https://api.algenta.ai` for Algenta cloud, or your own origin such as `http://localhost:8000` for a self-hosted deployment.

{% hint style="info" %}
An `elasticsearch` connector takes these `config` fields: supply one of `url`, `endpoint`, or `connection_string` as the cluster base URL (for example `https://cluster.example.com:443`; `http`/`https` only). `api_key` is required — a base64-encoded Elasticsearch API key sent as `Authorization: ApiKey <value>` (`apiKey` and `password` are accepted aliases). To materialize data, set `index`; optionally a `query` (Query DSL as an object or a JSON string, default `match_all`), a `limit` (alias `size`, default `100`), and `include_hidden` to include dot-prefixed indices in browse output. The alias type name `elastic` resolves to `elasticsearch`.
{% endhint %}

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL so every command below picks them up from the environment. Keep your Elasticsearch API key in its own variable so it never appears in shell history inline.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="https://api.algenta.ai"
export ELASTIC_API_KEY="$ELASTIC_API_KEY"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
echo "${ELASTIC_API_KEY:?set ELASTIC_API_KEY}" >/dev/null && echo "elastic key present"
```

**Expected result:** three lines print without error — `key present`, your base URL, and `elastic key present`. If any line errors, export the missing variable before continuing.
{% endstep %}

{% step %}
### Confirm the engine accepts `elasticsearch`

Ask the engine which connector types it supports and confirm `elasticsearch` is in the list.

```bash title="List connector types"
curl -s "$ALGENTA_BASE_URL/v1/connectors/types" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a JSON object with a `types` array that includes `"elasticsearch"` (and its alias `"elastic"`), for example `{"types": ["elasticsearch", "elastic", "postgres", ...]}`. If `elasticsearch` is present, the next step's `config` shape is accepted.
{% endstep %}

{% step %}
### Create the Elasticsearch connector

`POST /v1/connectors` stores the connection name, type, and credentials, and returns the connector with `status: "untested"`. Supply the cluster `url` and the base64-encoded `api_key`.

```bash title="Create an elasticsearch connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Log Search\",
    \"connector_type\": \"elasticsearch\",
    \"config\": {
      \"url\": \"https://cluster.example.com:443\",
      \"api_key\": \"$ELASTIC_API_KEY\"
    }
  }"
```

Capture the returned `id` for the steps that follow:

```bash title="Capture the connector id"
export CONNECTOR_ID="$CONNECTOR_ID"
```

**Expected result:** a `201` response with the connector `id`, `"connector_type": "elasticsearch"`, and `"status": "untested"`. Credentials are encrypted at rest — the connector object never returns your `config` back to you, only its name, type, status, and last test result.

{% hint style="warning" %}
An `elasticsearch` connector requires both a base URL (`url`, `endpoint`, or `connection_string`) and an `api_key`. A missing key surfaces `Elasticsearch connector requires api_key` at test time.
{% endhint %}
{% endstep %}

{% step %}
### Test the connection

`POST /v1/connectors/{id}/test` makes a real connection attempt — it issues a `GET /` and confirms the cluster returns a version payload — then flips the connector to `live` on success or `error` on failure. Browsing requires a `live` connector, so always test first.

```bash title="Test the connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** `{"success": true, "status": "live", "latency_ms": 96, "message": "Elasticsearch connection successful (cluster.example.com:443)"}`, and the connector's stored `status` is now `live`. On failure, `success` is `false`; `error_type` plus `recoverable` tell you whether to fix credentials and retry.
{% endstep %}

{% step %}
### Browse the indices it exposes

`GET /v1/connectors/{id}/browse` lists the indices the live cluster exposes (via `_cat/indices`), so you can pick what to onboard. Dot-prefixed system indices are hidden unless you set `include_hidden`. This returns `409 not_connected` if the connector is not `live` — run the test step first.

```bash title="Browse the connector"
curl -s "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a response with `"connector_type": "elasticsearch"`, an `items` array (each entry has `id`, `label`, a `kind` of `index`, a `selection` of `{"index": "<name>"}`, plus `health`, `status`, and `docs_count`), a `total`, and a message such as `Found 5 browsable Elasticsearch indices`. Note the index you want to query — for example `logs-2024`.
{% endstep %}

{% step %}
### Onboard one index as a dataset

`POST /v1/data/connect` ties the saved connector to a selection and registers the result as a queryable dataset. Reference the connector by `connection_id`, set `connection_type` to `database` and `provider` to `elasticsearch`, and name the index in `selection`.

```bash title="Connect a dataset from the elasticsearch connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"connection_type\": \"database\",
    \"provider\": \"elasticsearch\",
    \"dataset_name\": \"app_logs\",
    \"connection_id\": \"$CONNECTOR_ID\",
    \"selection\": {\"index\": \"logs-2024\"},
    \"visibility\": \"private\"
  }"
```

**Expected result:** `"status": "ready"` with a `dataset_id`, a `schema_summary` (row and column counts), and the `connection_id`. Each hit becomes a row of its `_source` fields plus `_index`, `_id`, and `_score`. Save the `dataset_id`:

```bash title="Capture the dataset id"
export DATASET_ID="$DATASET_ID"
```
{% endstep %}

{% step %}
### Run a governed query

The index is now governed data. `POST /v1/query` runs a deterministic, typed query against the dataset and returns rows under the engine's validated contract.

```bash title="Query the new dataset"
curl -s -X POST "$ALGENTA_BASE_URL/v1/query" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"select\": [\"level\", \"message\"],
    \"limit\": 10
  }"
```

**Expected result:** a `200` response with the matching rows and the resolved query plan. Re-running the same request against the same dataset returns the same rows in the same order — governed queries are deterministic by design.
{% endstep %}
{% endstepper %}

## Expected result

{% hint style="success" %}
You have a saved `elasticsearch` connector with `status: "live"`, a browse listing of its indices, a dataset onboarded from one of them that appears in `GET /v1/data` with a `dataset_id` and a profiled schema, and a first query returning documents. The same intent against the same dataset returns the same deterministic answer, and every access is auditable.
{% endhint %}

## Other ways to connect

The same endpoints back the `de` CLI and the Python SDK — all three hit the identical API.

```bash title="Elasticsearch connect flow with the de CLI"
de connectors create connector.json     # POST /v1/connectors from a JSON body
de connectors test $CONNECTOR_ID         # real connection health check
de connectors browse $CONNECTOR_ID       # browse the live cluster's indices
de data connect connect.json             # POST /v1/data/connect from a JSON body
de data list                             # list registered datasets
```

```python title="Connect Elasticsearch with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

connector = client.create_connector(
    name="Log Search",
    connector_type="elasticsearch",
    config={
        "url": "https://cluster.example.com:443",
        "api_key": os.environ["ELASTIC_API_KEY"],
    },
)

test = client.test_connector(connector.id)
assert test.success, test.message

browse = client.browse_connector(connector.id)
print(browse.total, "indices")

result = client.connect_data(
    connection_type="database",
    provider="elasticsearch",
    dataset_name="app_logs",
    connection_id=connector.id,
    selection={"index": "logs-2024"},
    visibility="private",
)
print(result.status, result.dataset_id)
```

## Troubleshooting

{% hint style="warning" %}
**Test fails with an authentication error.** The `api_key` is wrong or lacks read access. Confirm it is the base64-encoded API key (not the raw `id:secret` pair) and that it can read the target index.
{% endhint %}

{% hint style="warning" %}
**`Unsupported Elasticsearch connection string`.** The URL scheme is not `http` or `https`. Provide a full cluster URL such as `https://cluster.example.com:443`.
{% endhint %}

{% hint style="warning" %}
**`409 not_connected` when browsing.** The connector is not `live`. Run `POST /v1/connectors/{id}/test` first; only a connector that passes its test can be browsed.
{% endhint %}

{% hint style="info" %}
**Test fails with a privacy-policy or `error_type: "permission"` message.** The cluster host is outside your deployment's egress allowlist. Confirm the host and that the destination is permitted by your deployment's egress policy. See [Troubleshooting](../troubleshooting.md) for the full diagnosis flow.
{% endhint %}

## Next

{% content-ref url="../guides/governed-query.md" %}
[governed-query.md](../guides/governed-query.md)
{% endcontent-ref %}

{% content-ref url="files.md" %}
[files.md](files.md)
{% endcontent-ref %}

{% content-ref url="reference.md" %}
[reference.md](reference.md)
{% endcontent-ref %}
