---
icon: database
description: Create a PostgreSQL connector with its real config fields, test the connection, browse its tables, onboard one as a governed dataset, and run a first governed query against it.
---

# Connect PostgreSQL

By the end of this page you will have a saved `postgres` connector that reaches your database, a confirmed `live` connection test, a browse listing of the tables it exposes, one of those tables onboarded as a queryable **dataset**, and a first [governed query](../guides/governed-query.md) returning rows from it. Once onboarded, the table becomes [governed data](../concepts/governed-data.md): the engine queries it in place under a typed, validated contract — it never copies your database — so results stay deterministic and auditable.

Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)), and PostgreSQL credentials — a host, a database, a user, and that user's password. Use `https://api.algenta.ai` for Algenta cloud, or your own origin such as `http://localhost:8000` for a self-hosted deployment.

{% hint style="info" %}
A `postgres` connector reads these `config` fields at test time: `host` (default `localhost`), `port` (default `5432`), `database` (default `postgres`), `user` (default `postgres`), and `password`. `ssl_mode` is optional — only `require` or `verify-full` enforce TLS; the default `prefer` connects without requiring it. `schema` is optional and scopes browsing to one schema. You may instead pass a single `connection_string` DSN of the form `postgresql://user:password@host:5432/database`, which the browse and onboard steps read directly. The type `postgresql` is accepted and normalized to `postgres`.
{% endhint %}

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL so every command below picks them up from the environment. Keep your database password in its own variable so it never appears inline in shell history.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="https://api.algenta.ai"
export POSTGRES_PASSWORD="$POSTGRES_PASSWORD"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
echo "${POSTGRES_PASSWORD:?set POSTGRES_PASSWORD}" >/dev/null && echo "password present"
```

**Expected result:** three lines print without error — `key present`, your base URL, and `password present`. If any line errors, export the missing variable before continuing.
{% endstep %}

{% step %}
### Confirm the engine accepts `postgres`

Ask the engine which connector types it supports and confirm `postgres` is in the list.

```bash title="List connector types"
curl -s "$ALGENTA_BASE_URL/v1/connectors/types" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a JSON object with a `types` array that includes `"postgres"` (and its alias `"postgresql"`), for example `{"types": ["mysql", "postgres", "postgresql", "snowflake", ...]}`.
{% endstep %}

{% step %}
### Create the PostgreSQL connector

`POST /v1/connectors` stores the connection name, type, and credentials, and returns the connector with `status: "untested"`. Supply the discrete `host`, `port`, `database`, `user`, and `password` fields — the connection test reads these directly.

```bash title="Create a postgres connector (structured fields)"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Analytics DB\",
    \"connector_type\": \"postgres\",
    \"config\": {
      \"host\": \"db.internal\",
      \"port\": 5432,
      \"database\": \"analytics\",
      \"user\": \"reader\",
      \"password\": \"$POSTGRES_PASSWORD\",
      \"ssl_mode\": \"require\"
    }
  }"
```

Capture the returned `id` for the steps that follow:

```bash title="Capture the connector id"
export CONNECTOR_ID="$CONNECTOR_ID"
```

**Expected result:** a `201` response with the connector `id`, `"connector_type": "postgres"`, and `"status": "untested"`. Credentials are encrypted at rest — the connector object never returns your `config` back to you, only its name, type, status, and last test result.

{% hint style="warning" %}
`ssl_mode` only enforces TLS when set to `require` or `verify-full`; any other value (including the default `prefer`) connects without requiring TLS. If you supply only a `connection_string`, the connection test still reads the discrete `host`/`port`/`database`/`user`/`password` fields — set them too so the test targets the right server.
{% endhint %}
{% endstep %}

{% step %}
### Test the connection

`POST /v1/connectors/{id}/test` makes a real connection attempt — it logs in and runs `SELECT 1` — then flips the connector to `live` on success or `error` on failure. Browsing requires a `live` connector, so always test first.

```bash title="Test the connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** `{"success": true, "status": "live", "latency_ms": 42, "message": "PostgreSQL connection successful (db.internal:5432/analytics)"}`, and the connector's stored `status` is now `live`. On failure, `success` is `false`; `error_type` plus `recoverable` tell you whether to fix credentials and retry. An `error_type: "permission"` with a privacy-policy message means the host is outside your deployment's egress allowlist.
{% endstep %}

{% step %}
### Browse the tables it exposes

`GET /v1/connectors/{id}/browse` lists the tables and views the live connector can see, so you can pick what to onboard. This returns `409 not_connected` if the connector is not `live` — run the test step first.

```bash title="Browse the connector"
curl -s "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a response with `"connector_type": "postgres"`, an `items` array (each entry is a table or view, labelled `schema.name`), a `total`, a `message` such as `"Found 12 browsable database objects"`, and `discovery` metadata. Note the label of the table you want to query — for example `public.orders`.
{% endstep %}

{% step %}
### Onboard one table as a dataset

`POST /v1/data/connect` ties the saved connector to a selection — a table or a SQL query — and registers the result as a queryable dataset. Reference the connector by `connection_id` and name the table in `selection`.

```bash title="Connect a dataset from the postgres connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_name\": \"sales_orders\",
    \"connection_id\": \"$CONNECTOR_ID\",
    \"selection\": {\"table\": \"public.orders\"},
    \"visibility\": \"private\"
  }"
```

To onboard a derived shape instead of a whole table, pass `selection` as a SQL query — for example `{"sql_query": "SELECT region, amount FROM public.orders"}`.

**Expected result:** when the selection identifies one table, `"status": "ready"` with a `dataset_id`, a `schema_summary` (row and column counts), and the `connection_id`. If the connection resolves to more than one table and no selection is given, you get `"status": "needs_selection"` with a `choices` array — re-call `/v1/data/connect` with the returned `connection_id` and one `selection` from `choices`. Save the `dataset_id`:

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

You have a saved `postgres` connector with `status: "live"`, a browse listing of its tables, a dataset onboarded from one of them that appears in `GET /v1/data` with a `dataset_id` and a profiled schema, and a first query returning rows. The same intent against the same dataset returns the same deterministic answer, and every access is auditable.

## Other ways to connect

The same endpoints back the `de` CLI and the Python SDK — all three hit the identical API.

```bash title="PostgreSQL connect flow with the de CLI"
de connectors create connector.json        # POST /v1/connectors from a JSON body
de connectors test $CONNECTOR_ID           # real connection health check
de connectors browse $CONNECTOR_ID         # browse the live connector's tables
de data connect --request connect.json     # POST /v1/data/connect from a JSON body
de data list                               # list registered datasets
```

```python title="Connect PostgreSQL with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

connector = client.create_connector(
    name="Analytics DB",
    connector_type="postgres",
    config={
        "host": "db.internal",
        "port": 5432,
        "database": "analytics",
        "user": "reader",
        "password": os.environ["POSTGRES_PASSWORD"],
        "ssl_mode": "require",
    },
)

test = client.test_connector(connector.id)
assert test.success, test.message

browse = client.browse_connector(connector.id)
print(browse.total, "tables")

result = client.connect_data(
    connection_type="database",
    provider="postgres",
    dataset_name="sales_orders",
    connection_id=connector.id,
    selection={"table": "public.orders"},
    visibility="private",
)
print(result.status, result.dataset_id)
```

## Troubleshooting

<details>

<summary>Test fails with a password or role error</summary>

The message mentions `password authentication failed` or `role "..." does not exist`, and `error_type` is `auth`. Confirm the `user`, `password`, and `database` are correct and that the role may log in to that database. See [Authentication](../authentication.md).

</details>

<details>

<summary>Test fails with a timeout or "connection refused"</summary>

`error_type` is `timeout`. The `host`/`port` is unreachable from the engine, the server is down, or a firewall blocks it. Confirm the engine's network can reach `host:port` and that PostgreSQL is accepting TCP connections.

</details>

<details>

<summary>Test fails with a privacy-policy or permission message</summary>

`error_type` is `permission` and the message mentions the privacy policy. The database host is outside the egress allowlist for your deployment. Confirm the `host` value and that the destination is permitted by your deployment's egress policy. See [Troubleshooting](../troubleshooting.md) for the full diagnosis flow.

</details>

<details>

<summary>`409 not_connected` when browsing</summary>

The connector is not `live`. Run `POST /v1/connectors/{id}/test` first; only a connector that passes its test can be browsed. Editing a connector's `config` resets it to `untested`, so re-test after any change.

</details>

## Next

{% content-ref url="../guides/governed-query.md" %}
[governed-query.md](../guides/governed-query.md)
{% endcontent-ref %}

{% content-ref url="../guides/first-query.md" %}
[first-query.md](../guides/first-query.md)
{% endcontent-ref %}

{% content-ref url="redshift.md" %}
[redshift.md](redshift.md)
{% endcontent-ref %}
