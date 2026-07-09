---
icon: database
description: Create a SQLite connector from a database file path, test the connection, browse its tables, onboard one as a governed dataset, and run a first governed query against it.
---

# Connect SQLite

By the end of this page you will have a saved `sqlite` connector that opens a database file on the engine host, a confirmed `live` connection test, a browse listing of the tables it exposes, one of those tables onboarded as a queryable **dataset**, and a first [governed query](../guides/governed-query.md) returning rows from it. Once onboarded, the table becomes [governed data](../concepts/governed-data.md): the engine reads it under a typed, validated contract, so results stay deterministic and auditable.

Because SQLite is a file-based database, the engine opens the file from its own filesystem. This connector is most useful on a self-hosted deployment where the `.db` file lives alongside the engine. Use your own origin such as `http://localhost:8000`, or `https://api.algenta.ai` for Algenta cloud. See [Authentication](../authentication.md) for your API key and base URL.

{% hint style="info" %}
A `sqlite` connector needs one of two `config` fields: `path` — an absolute path to the `.db` file on the engine host (use `:memory:` for an ephemeral in-memory database) — or a single `connection_string` DSN. Accepted DSN forms are `sqlite:///` followed by an absolute path, `sqlite+pysqlite:///` followed by an absolute path, and the literal `sqlite:///:memory:`. There is no host, port, user, or password. `schema` is optional and scopes browsing.
{% endhint %}

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL so every command below picks them up from the environment.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="http://localhost:8000"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
```

**Expected result:** two lines print without error — `key present` and your base URL. If either errors, export the missing variable before continuing.
{% endstep %}

{% step %}
### Confirm the engine accepts `sqlite`

Ask the engine which connector types it supports and confirm `sqlite` is in the list.

```bash title="List connector types"
curl -s "$ALGENTA_BASE_URL/v1/connectors/types" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a JSON object with a `types` array that includes `"sqlite"`, for example `{"types": ["postgres", "sqlite", "snowflake", ...]}`.
{% endstep %}

{% step %}
### Create the SQLite connector

`POST /v1/connectors` stores the connection name, type, and file path, and returns the connector with `status: "untested"`. Point `path` at a database file the engine can read.

```bash title="Create a sqlite connector (file path)"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Local Analytics\",
    \"connector_type\": \"sqlite\",
    \"config\": {
      \"path\": \"/data/analytics.db\"
    }
  }"
```

If you prefer a DSN, pass `connection_string` instead of `path` — the engine reads either form:

```bash title="Alternative: a connection_string DSN"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Local Analytics\",
    \"connector_type\": \"sqlite\",
    \"config\": {
      \"connection_string\": \"sqlite:////data/analytics.db\"
    }
  }"
```

Capture the returned `id` for the steps that follow:

```bash title="Capture the connector id"
export CONNECTOR_ID="$CONNECTOR_ID"
```

**Expected result:** a `201` response with the connector `id`, `"connector_type": "sqlite"`, and `"status": "untested"`.

{% hint style="warning" %}
If neither `path` nor a recognizable `connection_string` is provided, the engine returns `422 missing_connection_string`. The path is resolved on the **engine host** — a path that exists on your laptop is not visible to a remote engine.
{% endhint %}
{% endstep %}

{% step %}
### Test the connection

`POST /v1/connectors/{id}/test` opens the database file and runs `SELECT 1`, then flips the connector to `live` on success or `error` on failure. Browsing requires a `live` connector, so always test first.

```bash title="Test the connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** `{"success": true, "status": "live", "latency_ms": 3, "message": "SQLite connection successful (/data/analytics.db)"}`, and the connector's stored `status` is now `live`. On failure, `error_type` plus `recoverable` tell you whether to fix the path and retry.
{% endstep %}

{% step %}
### Browse the tables it exposes

`GET /v1/connectors/{id}/browse` lists the tables and views in the database, so you can pick what to onboard. This returns `409 not_connected` if the connector is not `live` — run the test step first.

```bash title="Browse the connector"
curl -s "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a response with `"connector_type": "sqlite"`, an `items` array (each entry is a table or view), a `total`, a `message` such as `"Found 4 browsable database objects"`, and `discovery` metadata. Note the name of the table you want to query — for example `orders`.
{% endstep %}

{% step %}
### Onboard one table as a dataset

`POST /v1/data/connect` ties the saved connector to a selection — a table or a SQL query — and registers the result as a queryable dataset. Reference the connector by `connection_id` and name the table in `selection`.

```bash title="Connect a dataset from the sqlite connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_name\": \"sales_orders\",
    \"connection_id\": \"$CONNECTOR_ID\",
    \"selection\": {\"table\": \"orders\"},
    \"visibility\": \"private\"
  }"
```

To onboard a derived shape instead of a whole table, pass `selection` as a SQL query — for example `{"sql_query": "SELECT region, amount FROM orders"}`.

**Expected result:** when the selection identifies one table, `"status": "ready"` with a `dataset_id`, a `schema_summary` (row and column counts), and the `connection_id`. If more than one table matches and no selection is given, you get `"status": "needs_selection"` with a `choices` array — re-call with one `selection` from `choices`. Save the `dataset_id`:

```bash title="Capture the dataset id"
export DATASET_ID="$DATASET_ID"
```
{% endstep %}

{% step %}
### Run a governed query

The table is now governed data. `POST /v1/query` runs a deterministic, typed query against the dataset and returns rows under the engine's validated contract.

```bash title="Query the new dataset"
curl -s -X POST "$ALGENTA_BASE_URL/v1/query" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"select\": [\"region\", \"amount\"],
    \"limit\": 10
  }"
```

**Expected result:** a `200` response with the matching rows and the resolved query plan. Re-running the same request against the same dataset returns the same rows in the same order — governed queries are deterministic by design.
{% endstep %}
{% endstepper %}

## Expected result

You have a saved `sqlite` connector with `status: "live"`, a browse listing of its tables, a dataset onboarded from one of them that appears in `GET /v1/data` with a `dataset_id` and a profiled schema, and a first query returning rows. The same intent against the same dataset returns the same deterministic answer, and every access is auditable.

## Other ways to connect

The same endpoints back the `de` CLI and the Python SDK — all three hit the identical API.

```bash title="SQLite connect flow with the de CLI"
de connectors create connector.json        # POST /v1/connectors from a JSON body
de connectors test $CONNECTOR_ID           # real connection health check
de connectors browse $CONNECTOR_ID         # browse the live connector's tables
de data connect --request connect.json     # POST /v1/data/connect from a JSON body
de data list                               # list registered datasets
```

```python title="Connect SQLite with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="http://localhost:8000",
)

connector = client.create_connector(
    name="Local Analytics",
    connector_type="sqlite",
    config={"path": "/data/analytics.db"},
)

test = client.test_connector(connector.id)
assert test.success, test.message

result = client.connect_data(
    connection_type="database",
    provider="sqlite",
    dataset_name="sales_orders",
    connection_id=connector.id,
    selection={"table": "orders"},
    visibility="private",
)
print(result.status, result.dataset_id)
```

## Troubleshooting

<details>

<summary>`422 missing_connection_string` on create or connect</summary>

Neither `path` nor a recognizable `connection_string` was provided. Supply an absolute `path` to the `.db` file, or a DSN of the form `sqlite:///` followed by an absolute path (use the literal `sqlite:///:memory:` for an in-memory database).

</details>

<details>

<summary>Test fails with "unable to open database file"</summary>

`error_type` is often `not_found`. The path does not exist or is not readable from the engine host. Remember the path resolves on the engine's filesystem, not your local machine — copy the file to the engine or mount it, then re-test.

</details>

<details>

<summary>`409 not_connected` when browsing</summary>

The connector is not `live`. Run `POST /v1/connectors/{id}/test` first; only a connector that passes its test can be browsed. Editing a connector's `config` resets it to `untested`, so re-test after any change.

</details>

## Next

{% content-ref url="../guides/governed-query.md" %}
[governed-query.md](../guides/governed-query.md)
{% endcontent-ref %}

{% content-ref url="postgres.md" %}
[postgres.md](postgres.md)
{% endcontent-ref %}

{% content-ref url="../guides/first-query.md" %}
[first-query.md](../guides/first-query.md)
{% endcontent-ref %}
