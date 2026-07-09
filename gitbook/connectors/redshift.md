---
icon: aws
description: Create an Amazon Redshift connector with its real config fields, test the connection over the PostgreSQL wire, browse its tables, onboard one as a governed dataset, and run a first governed query.
---

# Connect Amazon Redshift

By the end of this page you will have a saved `redshift` connector that reaches your cluster, a confirmed `live` connection test, a browse listing of the tables it exposes, one of those tables onboarded as a queryable **dataset**, and a first [governed query](../guides/governed-query.md) returning rows from it. Redshift speaks the PostgreSQL wire protocol, so the engine connects to it the same way — reading your tables in place under a typed, validated [governed contract](../concepts/governed-data.md) and never copying the cluster.

Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)), and Redshift credentials — the cluster endpoint host, the database, a user, and that user's password. Use `https://api.algenta.ai` for Algenta cloud, or your own origin such as `http://localhost:8000` for a self-hosted deployment.

{% hint style="info" %}
A `redshift` connector reads these `config` fields at test time: `host` (the cluster endpoint), `port` (default `5432` — set it to your cluster's port, usually `5439`), `database`, `user`, and `password`. `ssl_mode` is optional — set `require` or `verify-full` to enforce TLS, which Redshift clusters expect. `schema` is optional and scopes browsing. You may instead pass a single `connection_string` DSN of the form `postgresql://user:password@endpoint:5439/database`, which the browse and onboard steps read directly.
{% endhint %}

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL so every command below picks them up from the environment, and keep the cluster password in its own variable.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="https://api.algenta.ai"
export REDSHIFT_PASSWORD="$REDSHIFT_PASSWORD"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
echo "${REDSHIFT_PASSWORD:?set REDSHIFT_PASSWORD}" >/dev/null && echo "password present"
```

**Expected result:** three lines print without error — `key present`, your base URL, and `password present`. If any line errors, export the missing variable before continuing.
{% endstep %}

{% step %}
### Confirm the engine accepts `redshift`

Ask the engine which connector types it supports and confirm `redshift` is in the list.

```bash title="List connector types"
curl -s "$ALGENTA_BASE_URL/v1/connectors/types" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a JSON object with a `types` array that includes `"redshift"`, for example `{"types": ["postgres", "redshift", "snowflake", ...]}`.
{% endstep %}

{% step %}
### Create the Redshift connector

`POST /v1/connectors` stores the connection name, type, and credentials, and returns the connector with `status: "untested"`. Supply the cluster endpoint as `host`, set `port` to your cluster's port (usually `5439`), and provide `database`, `user`, and `password`.

```bash title="Create a redshift connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Warehouse Redshift\",
    \"connector_type\": \"redshift\",
    \"config\": {
      \"host\": \"my-cluster.abc123.us-east-1.redshift.amazonaws.com\",
      \"port\": 5439,
      \"database\": \"analytics\",
      \"user\": \"reader\",
      \"password\": \"$REDSHIFT_PASSWORD\",
      \"ssl_mode\": \"require\"
    }
  }"
```

Capture the returned `id` for the steps that follow:

```bash title="Capture the connector id"
export CONNECTOR_ID="$CONNECTOR_ID"
```

**Expected result:** a `201` response with the connector `id`, `"connector_type": "redshift"`, and `"status": "untested"`. Credentials are encrypted at rest.

{% hint style="warning" %}
`port` defaults to `5432` if omitted, but Redshift clusters listen on `5439` by default — set `port` explicitly or the connection test will target the wrong port. Set `ssl_mode` to `require` so the client negotiates TLS, which most clusters require.
{% endhint %}
{% endstep %}

{% step %}
### Test the connection

`POST /v1/connectors/{id}/test` makes a real connection attempt — it logs in and runs `SELECT 1` — then flips the connector to `live` on success or `error` on failure. Browsing requires a `live` connector, so always test first.

```bash title="Test the connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** `{"success": true, "status": "live", "latency_ms": 118, "message": "PostgreSQL connection successful (my-cluster.abc123.us-east-1.redshift.amazonaws.com:5439/analytics)"}`, and the connector's stored `status` is now `live`. Because Redshift uses the PostgreSQL protocol, the success message names PostgreSQL. On failure, `error_type` plus `recoverable` tell you whether to fix credentials and retry.
{% endstep %}

{% step %}
### Browse the tables it exposes

`GET /v1/connectors/{id}/browse` lists the tables and views the live connector can see, so you can pick what to onboard. This returns `409 not_connected` if the connector is not `live` — run the test step first.

```bash title="Browse the connector"
curl -s "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a response with `"connector_type": "redshift"`, an `items` array (each entry is a table or view, labelled `schema.name`), a `total`, a `message` such as `"Found 8 browsable database objects"`, and `discovery` metadata. Note the label of the table you want to query — for example `public.events`.
{% endstep %}

{% step %}
### Onboard one table as a dataset

`POST /v1/data/connect` ties the saved connector to a selection — a table or a SQL query — and registers the result as a queryable dataset. Reference the connector by `connection_id` and name the table in `selection`.

```bash title="Connect a dataset from the redshift connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_name\": \"warehouse_events\",
    \"connection_id\": \"$CONNECTOR_ID\",
    \"selection\": {\"table\": \"public.events\"},
    \"visibility\": \"private\"
  }"
```

To onboard a derived shape instead of a whole table, pass `selection` as a SQL query — for example `{"sql_query": "SELECT region, revenue FROM public.events"}`.

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
    \"select\": [\"region\", \"revenue\"],
    \"limit\": 10
  }"
```

**Expected result:** a `200` response with the matching rows and the resolved query plan. Re-running the same request against the same dataset returns the same rows in the same order — governed queries are deterministic by design.
{% endstep %}
{% endstepper %}

## Expected result

You have a saved `redshift` connector with `status: "live"`, a browse listing of its tables, a dataset onboarded from one of them that appears in `GET /v1/data` with a `dataset_id` and a profiled schema, and a first query returning rows. The same intent against the same dataset returns the same deterministic answer, and every access is auditable.

## Other ways to connect

The same endpoints back the `de` CLI and the Python SDK — all three hit the identical API.

```bash title="Redshift connect flow with the de CLI"
de connectors create connector.json        # POST /v1/connectors from a JSON body
de connectors test $CONNECTOR_ID           # real connection health check
de connectors browse $CONNECTOR_ID         # browse the live connector's tables
de data connect --request connect.json     # POST /v1/data/connect from a JSON body
de data list                               # list registered datasets
```

```python title="Connect Redshift with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

connector = client.create_connector(
    name="Warehouse Redshift",
    connector_type="redshift",
    config={
        "host": "my-cluster.abc123.us-east-1.redshift.amazonaws.com",
        "port": 5439,
        "database": "analytics",
        "user": "reader",
        "password": os.environ["REDSHIFT_PASSWORD"],
        "ssl_mode": "require",
    },
)

test = client.test_connector(connector.id)
assert test.success, test.message

result = client.connect_data(
    connection_type="database",
    provider="redshift",
    dataset_name="warehouse_events",
    connection_id=connector.id,
    selection={"table": "public.events"},
    visibility="private",
)
print(result.status, result.dataset_id)
```

## Troubleshooting

<details>

<summary>Test times out even though credentials are correct</summary>

`error_type` is `timeout`. The most common cause is the default `port` of `5432` — Redshift listens on `5439`. Set `port` explicitly, and confirm the cluster's security group allows inbound access from the engine's network.

</details>

<details>

<summary>Test fails with an authentication error</summary>

`error_type` is `auth` and the message mentions a password or role. Confirm the `user`, `password`, and `database` are correct and that the user has `CONNECT` on the database. See [Authentication](../authentication.md).

</details>

<details>

<summary>Test fails with a privacy-policy or permission message</summary>

`error_type` is `permission` and the message mentions the privacy policy. The cluster endpoint is outside the egress allowlist for your deployment. Confirm the `host` and that the destination is permitted by your deployment's egress policy. See [Troubleshooting](../troubleshooting.md).

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

{% content-ref url="snowflake.md" %}
[snowflake.md](snowflake.md)
{% endcontent-ref %}
