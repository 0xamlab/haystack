---
icon: circle-nodes
description: Create a Neo4j connector with its real config fields, test the connection, browse its labels and relationship types, onboard a selection as a dataset, and run a governed query against it.
---

# Connect Neo4j

By the end of this page you will have a saved `neo4j` connector that reaches your database, a confirmed `live` connection test, a browse listing of the labels and relationship types it exposes, one of those onboarded as a queryable **dataset**, and a first [governed query](../guides/governed-query.md) returning graph rows. Once onboarded, the result becomes [governed data](../concepts/governed-data.md): the engine reads it under a typed, validated contract, so results stay deterministic and auditable.

Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)), and Neo4j credentials — a URI, a username, and a password (an Aura connection string works directly). Use `https://api.algenta.ai` for Algenta cloud, or your own origin such as `http://localhost:8000` for a self-hosted deployment.

{% hint style="info" %}
A `neo4j` connector takes these `config` fields: supply one of `uri`, `url`, or `connection_string` (for example `neo4j+s://example.databases.neo4j.io`; the schemes `neo4j`, `neo4j+s`, `neo4j+ssc`, `bolt`, `bolt+s`, and `bolt+ssc` are accepted), or a `host` with an optional `scheme` (default `neo4j`) and `port`. `username` (alias `user`) and `password` are required; `database` (alias `db`) is optional. To materialize data, set `query` (alias `cypher`) with optional `parameters` and a `limit` (default `1000`).
{% endhint %}

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL so every command below picks them up from the environment. Keep your Neo4j password in its own variable so it never appears in shell history inline.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="https://api.algenta.ai"
export NEO4J_PASSWORD="$NEO4J_PASSWORD"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
echo "${NEO4J_PASSWORD:?set NEO4J_PASSWORD}" >/dev/null && echo "password present"
```

**Expected result:** three lines print without error — `key present`, your base URL, and `password present`. If any line errors, export the missing variable before continuing.
{% endstep %}

{% step %}
### Confirm the engine accepts `neo4j`

Ask the engine which connector types it supports and confirm `neo4j` is in the list.

```bash title="List connector types"
curl -s "$ALGENTA_BASE_URL/v1/connectors/types" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a JSON object with a `types` array that includes `"neo4j"`, for example `{"types": ["postgres", "neo4j", "redis", ...]}`. If `neo4j` is present, the next step's `config` shape is accepted.
{% endstep %}

{% step %}
### Create the Neo4j connector

`POST /v1/connectors` stores the connection name, type, and credentials, and returns the connector with `status: "untested"`. Supply the `uri`, `username`, and `password`; add `database` if your deployment uses a non-default one.

```bash title="Create a neo4j connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Product Graph\",
    \"connector_type\": \"neo4j\",
    \"config\": {
      \"uri\": \"neo4j+s://example.databases.neo4j.io\",
      \"username\": \"neo4j\",
      \"password\": \"$NEO4J_PASSWORD\",
      \"database\": \"neo4j\"
    }
  }"
```

Capture the returned `id` for the steps that follow:

```bash title="Capture the connector id"
export CONNECTOR_ID="$CONNECTOR_ID"
```

**Expected result:** a `201` response with the connector `id`, `"connector_type": "neo4j"`, and `"status": "untested"`. Credentials are encrypted at rest — the connector object never returns your `config` back to you, only its name, type, status, and last test result.

{% hint style="warning" %}
A `neo4j` connector requires a `username` (or `user`) and a `password`, plus a `uri`/`url`/`connection_string` or a `host`. A missing username or password surfaces a clear config error at test time.
{% endhint %}
{% endstep %}

{% step %}
### Test the connection

`POST /v1/connectors/{id}/test` makes a real connection attempt — it opens a driver session and runs `RETURN 1 AS ok` — then flips the connector to `live` on success or `error` on failure. Browsing requires a `live` connector, so always test first.

```bash title="Test the connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** `{"success": true, "status": "live", "latency_ms": 120, "message": "Neo4j connection successful (example.databases.neo4j.io/neo4j)"}`, and the connector's stored `status` is now `live`. On failure, `success` is `false`; `error_type` plus `recoverable` tell you whether to fix credentials and retry.
{% endstep %}

{% step %}
### Browse the labels and relationship types it exposes

`GET /v1/connectors/{id}/browse` lists the node labels and relationship types the live database contains, so you can pick what to onboard. This returns `409 not_connected` if the connector is not `live` — run the test step first.

```bash title="Browse the connector"
curl -s "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a response with `"connector_type": "neo4j"`, an `items` array (each entry has `id`, `label`, a `kind` of `label` or `relationship_type`, and a `selection` such as `{"label": "Product"}` or `{"relationship_type": "PURCHASED"}`), a `total`, and a message such as `Found 8 browsable Neo4j labels and relationship types`.
{% endstep %}

{% step %}
### Onboard a selection as a dataset

`POST /v1/data/connect` ties the saved connector to a selection and registers the result as a queryable dataset. Reference the connector by `connection_id`, set `connection_type` to `database` and `provider` to `neo4j`, and pass a `selection` — a `label`, a `relationship_type`, or an explicit `query` (alias `cypher`).

```bash title="Connect a dataset from the neo4j connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"connection_type\": \"database\",
    \"provider\": \"neo4j\",
    \"dataset_name\": \"products\",
    \"connection_id\": \"$CONNECTOR_ID\",
    \"selection\": {\"label\": \"Product\"},
    \"visibility\": \"private\"
  }"
```

To onboard a derived shape instead of a whole label, pass `selection` as a Cypher query — for example `{"query": "MATCH (p:Product)-[:IN]->(c:Category) RETURN p.name AS name, c.name AS category"}`.

**Expected result:** `"status": "ready"` with a `dataset_id`, a `schema_summary` (row and column counts), and the `connection_id`. Save the `dataset_id`:

```bash title="Capture the dataset id"
export DATASET_ID="$DATASET_ID"
```
{% endstep %}

{% step %}
### Run a governed query

The result is now governed data. `POST /v1/query` runs a deterministic, typed query against the dataset and returns rows under the engine's validated contract.

```bash title="Query the new dataset"
curl -s -X POST "$ALGENTA_BASE_URL/v1/query" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"select\": [\"name\", \"category\"],
    \"limit\": 10
  }"
```

**Expected result:** a `200` response with the matching rows and the resolved query plan. Re-running the same request against the same dataset returns the same rows in the same order — governed queries are deterministic by design.
{% endstep %}
{% endstepper %}

## Expected result

{% hint style="success" %}
You have a saved `neo4j` connector with `status: "live"`, a browse listing of its labels and relationship types, a dataset onboarded from one of them that appears in `GET /v1/data` with a `dataset_id` and a profiled schema, and a first query returning graph rows. The same intent against the same dataset returns the same deterministic answer, and every access is auditable.
{% endhint %}

## Other ways to connect

The same endpoints back the `de` CLI and the Python SDK — all three hit the identical API.

```bash title="Neo4j connect flow with the de CLI"
de connectors create connector.json     # POST /v1/connectors from a JSON body
de connectors test $CONNECTOR_ID         # real connection health check
de connectors browse $CONNECTOR_ID       # browse labels and relationship types
de data connect connect.json             # POST /v1/data/connect from a JSON body
de data list                             # list registered datasets
```

```python title="Connect Neo4j with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

connector = client.create_connector(
    name="Product Graph",
    connector_type="neo4j",
    config={
        "uri": "neo4j+s://example.databases.neo4j.io",
        "username": "neo4j",
        "password": os.environ["NEO4J_PASSWORD"],
        "database": "neo4j",
    },
)

test = client.test_connector(connector.id)
assert test.success, test.message

browse = client.browse_connector(connector.id)
print(browse.total, "labels and relationship types")

result = client.connect_data(
    connection_type="database",
    provider="neo4j",
    dataset_name="products",
    connection_id=connector.id,
    selection={"label": "Product"},
    visibility="private",
)
print(result.status, result.dataset_id)
```

## Troubleshooting

{% hint style="warning" %}
**Test fails with an authentication error.** The `username`/`password` pair is wrong. Confirm the credentials and that the login has access to the target `database`.
{% endhint %}

{% hint style="warning" %}
**`Unsupported Neo4j connection string`.** The URI scheme is not one of `neo4j`, `neo4j+s`, `neo4j+ssc`, `bolt`, `bolt+s`, or `bolt+ssc`. Use a supported scheme — Aura instances use `neo4j+s://`.
{% endhint %}

{% hint style="warning" %}
**`409 not_connected` when browsing.** The connector is not `live`. Run `POST /v1/connectors/{id}/test` first; only a connector that passes its test can be browsed.
{% endhint %}

{% hint style="info" %}
**Test fails with a privacy-policy or `error_type: "permission"` message.** The Neo4j host is outside your deployment's egress allowlist. Confirm the host and that the destination is permitted by your deployment's egress policy. See [Troubleshooting](../troubleshooting.md) for the full diagnosis flow.
{% endhint %}

## Next

{% content-ref url="../guides/governed-query.md" %}
[governed-query.md](../guides/governed-query.md)
{% endcontent-ref %}

{% content-ref url="elasticsearch.md" %}
[elasticsearch.md](elasticsearch.md)
{% endcontent-ref %}

{% content-ref url="reference.md" %}
[reference.md](reference.md)
{% endcontent-ref %}
