---
icon: server
description: Create a Microsoft SQL Server connector with its real config fields, and understand the managed connection-test behavior for SQL Server before you onboard data.
---

# Connect Microsoft SQL Server

This page creates a saved `mssql` connector with its real configuration fields and explains exactly how the engine handles a SQL Server connection so you know what to expect at each step. An `mssql` connector is a SQLAlchemy-based connection built on the `mssql+pyodbc` driver.

Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)), and SQL Server credentials — a host, a database, a user, and that user's password. Use `https://api.algenta.ai` for Algenta cloud, or your own origin such as `http://localhost:8000` for a self-hosted deployment.

{% hint style="info" %}
An `mssql` connector takes these `config` fields: `host` (default `localhost`), `port` (default `1433`), `database`, `user` (alias `username`), and `password`. `driver` sets the ODBC driver name and defaults to `ODBC Driver 18 for SQL Server`; `schema` is optional. Alternatively, supply a single `connection_string` DSN of the form `mssql+pyodbc://user:password@host:1433/database?driver=ODBC+Driver+18+for+SQL+Server`.
{% endhint %}

{% hint style="warning" %}
The engine does not run a **managed connection test** for SQL Server. `POST /v1/connectors/{id}/test` returns `success: false` with the message `"Connector type 'mssql' test not yet implemented. Please verify credentials manually."` Because `POST /v1/data/connect` runs that same managed test before it onboards a table, SQL Server sources are not onboarded as governed datasets through this flow. Verify SQL Server credentials from your own client (Step 4), and use a fully validated database — see [Snowflake](snowflake.md), [PostgreSQL](postgres.md), or [Connect a database](databases.md) — when you need governed queries today.
{% endhint %}

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL, and keep your SQL Server password in its own variable so it never appears inline in shell history.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="https://api.algenta.ai"
export MSSQL_PASSWORD="$MSSQL_PASSWORD"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
echo "${MSSQL_PASSWORD:?set MSSQL_PASSWORD}" >/dev/null && echo "password present"
```

**Expected result:** three lines print without error — `key present`, your base URL, and `password present`. If any line errors, export the missing variable before continuing.
{% endstep %}

{% step %}
### Confirm the engine accepts `mssql`

Ask the engine which connector types it supports and confirm `mssql` is in the list.

```bash title="List connector types"
curl -s "$ALGENTA_BASE_URL/v1/connectors/types" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a JSON object with a `types` array that includes `"mssql"`, for example `{"types": ["mssql", "mysql", "postgres", ...]}`.
{% endstep %}

{% step %}
### Create the SQL Server connector

`POST /v1/connectors` stores the connection name, type, and credentials, and returns the connector with `status: "untested"`. Supply the discrete `host`, `port`, `database`, `user`, and `password` fields, and optionally override the ODBC `driver`.

```bash title="Create an mssql connector (structured fields)"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"App SQL Server\",
    \"connector_type\": \"mssql\",
    \"config\": {
      \"host\": \"db.internal\",
      \"port\": 1433,
      \"database\": \"app\",
      \"user\": \"reader\",
      \"password\": \"$MSSQL_PASSWORD\",
      \"driver\": \"ODBC Driver 18 for SQL Server\"
    }
  }"
```

If you already have a DSN, pass it as `connection_string` instead of the discrete fields:

```bash title="Alternative: a connection_string DSN"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"App SQL Server\",
    \"connector_type\": \"mssql\",
    \"config\": {
      \"connection_string\": \"mssql+pyodbc://reader:$MSSQL_PASSWORD@db.internal:1433/app?driver=ODBC+Driver+18+for+SQL+Server\"
    }
  }"
```

Capture the returned `id`:

```bash title="Capture the connector id"
export CONNECTOR_ID="$CONNECTOR_ID"
```

**Expected result:** a `201` response with the connector `id`, `"connector_type": "mssql"`, and `"status": "untested"`. Credentials are encrypted at rest — the connector object never returns your `config` back to you, only its name, type, status, and last test result.
{% endstep %}

{% step %}
### Verify the credentials from your own client

Because the engine does not run a managed test for SQL Server, confirm the same host, database, user, and password work from a client you control. This is the check the engine would otherwise perform.

```bash title="Verify SQL Server reachability with sqlcmd"
sqlcmd -S db.internal,1433 -d app -U reader -P "$MSSQL_PASSWORD" -Q "SELECT 1;"
```

**Expected result:** `sqlcmd` prints a single-row result for `SELECT 1`. If it errors, fix the host, port, database, user, password, or `driver` before relying on the saved connector.
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result:** you have a saved `mssql` connector visible in `GET /v1/connectors` with `"connector_type": "mssql"` and its credentials encrypted at rest, and you have independently confirmed those credentials reach your database. Governed dataset onboarding for SQL Server is not available through `POST /v1/data/connect` in this deployment.
{% endhint %}

## Other ways to create the connector

The same endpoint backs the `de` CLI and the Python SDK.

```bash title="Create an MSSQL connector with the de CLI"
de connectors create connector.json     # POST /v1/connectors from a JSON body
de connectors list                      # GET /v1/connectors
```

```python title="Create an MSSQL connector with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

connector = client.create_connector(
    name="App SQL Server",
    connector_type="mssql",
    config={
        "host": "db.internal",
        "port": 1433,
        "database": "app",
        "user": "reader",
        "password": os.environ["MSSQL_PASSWORD"],
        "driver": "ODBC Driver 18 for SQL Server",
    },
)
print(connector.id, connector.status)  # "untested"
```

## Troubleshooting

<details>

<summary>`POST /v1/connectors/{id}/test` returns success: false</summary>

The response message is `"Connector type 'mssql' test not yet implemented. Please verify credentials manually."` with `error_type: "invalid_config"` and `recoverable: true`. This is expected — there is no managed test for SQL Server. Verify the credentials from your own client instead (Step 4).

</details>

<details>

<summary>`POST /v1/data/connect` returns status: failed for an MSSQL connector</summary>

`/v1/data/connect` runs the managed connection test before onboarding, so it reports the same "not yet implemented" message for SQL Server and does not register a dataset. To run governed queries today, connect a fully validated database — see [Snowflake](snowflake.md), [PostgreSQL](postgres.md), or the [database overview](databases.md).

</details>

<details>

<summary>Choosing the ODBC driver</summary>

The DSN is built with `mssql+pyodbc` and the `driver` you set (default `ODBC Driver 18 for SQL Server`). The named driver must be installed wherever the connection is opened; if your host has a different version, set `driver` to match it — for example `ODBC Driver 17 for SQL Server`.

</details>

## Next

{% content-ref url="databases.md" %}
[databases.md](databases.md)
{% endcontent-ref %}

{% content-ref url="postgres.md" %}
[postgres.md](postgres.md)
{% endcontent-ref %}

{% content-ref url="reference.md" %}
[reference.md](reference.md)
{% endcontent-ref %}
