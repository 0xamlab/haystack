---
icon: database
description: Create a MySQL connector with its real config fields, and understand the managed connection-test behavior for MySQL before you onboard data.
---

# Connect MySQL

This page creates a saved `mysql` connector with its real configuration fields and explains exactly how the engine handles a MySQL connection so you know what to expect at each step. A `mysql` connector is a SQLAlchemy-based connection built on the `mysql+pymysql` driver.

Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)), and MySQL credentials — a host, a database, a user, and that user's password. Use `https://api.algenta.ai` for Algenta cloud, or your own origin such as `http://localhost:8000` for a self-hosted deployment.

{% hint style="info" %}
A `mysql` connector takes these `config` fields: `host` (default `localhost`), `port` (default `3306`), `database`, `user` (alias `username`), and `password`. `schema` is optional. Alternatively, supply a single `connection_string` DSN of the form `mysql+pymysql://user:password@host:3306/database`. These are the fields the engine reads for a MySQL connection.
{% endhint %}

{% hint style="warning" %}
The engine does not run a **managed connection test** for MySQL. `POST /v1/connectors/{id}/test` returns `success: false` with the message `"Connector type 'mysql' test not yet implemented. Please verify credentials manually."` Because `POST /v1/data/connect` runs that same managed test before it onboards a table, MySQL sources are not onboarded as governed datasets through this flow. Verify MySQL credentials from your own client (Step 4), and use a fully validated database — see [Snowflake](snowflake.md), [PostgreSQL](postgres.md), or [Connect a database](databases.md) — when you need governed queries today.
{% endhint %}

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL, and keep your MySQL password in its own variable so it never appears inline in shell history.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="https://api.algenta.ai"
export MYSQL_PASSWORD="$MYSQL_PASSWORD"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
echo "${MYSQL_PASSWORD:?set MYSQL_PASSWORD}" >/dev/null && echo "password present"
```

**Expected result:** three lines print without error — `key present`, your base URL, and `password present`. If any line errors, export the missing variable before continuing.
{% endstep %}

{% step %}
### Confirm the engine accepts `mysql`

Ask the engine which connector types it supports and confirm `mysql` is in the list.

```bash title="List connector types"
curl -s "$ALGENTA_BASE_URL/v1/connectors/types" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a JSON object with a `types` array that includes `"mysql"`, for example `{"types": ["mssql", "mysql", "postgres", ...]}`.
{% endstep %}

{% step %}
### Create the MySQL connector

`POST /v1/connectors` stores the connection name, type, and credentials, and returns the connector with `status: "untested"`. Supply the discrete `host`, `port`, `database`, `user`, and `password` fields.

```bash title="Create a mysql connector (structured fields)"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"App MySQL\",
    \"connector_type\": \"mysql\",
    \"config\": {
      \"host\": \"db.internal\",
      \"port\": 3306,
      \"database\": \"app\",
      \"user\": \"reader\",
      \"password\": \"$MYSQL_PASSWORD\"
    }
  }"
```

If you already have a DSN, pass it as `connection_string` instead of the discrete fields:

```bash title="Alternative: a connection_string DSN"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"App MySQL\",
    \"connector_type\": \"mysql\",
    \"config\": {
      \"connection_string\": \"mysql+pymysql://reader:$MYSQL_PASSWORD@db.internal:3306/app\"
    }
  }"
```

Capture the returned `id`:

```bash title="Capture the connector id"
export CONNECTOR_ID="$CONNECTOR_ID"
```

**Expected result:** a `201` response with the connector `id`, `"connector_type": "mysql"`, and `"status": "untested"`. Credentials are encrypted at rest — the connector object never returns your `config` back to you, only its name, type, status, and last test result.
{% endstep %}

{% step %}
### Verify the credentials from your own client

Because the engine does not run a managed test for MySQL, confirm the same host, database, user, and password work from a client you control. This is the check the engine would otherwise perform.

```bash title="Verify MySQL reachability with the mysql client"
mysql -h db.internal -P 3306 -u reader -p"$MYSQL_PASSWORD" app -e "SELECT 1;"
```

**Expected result:** the `mysql` client prints a single-row result for `SELECT 1`. If it errors, fix the host, port, database, user, or password before relying on the saved connector.
{% endstep %}
{% endstepper %}

{% hint style="success" %}
**Expected result:** you have a saved `mysql` connector visible in `GET /v1/connectors` with `"connector_type": "mysql"` and its credentials encrypted at rest, and you have independently confirmed those credentials reach your database. Governed dataset onboarding for MySQL is not available through `POST /v1/data/connect` in this deployment.
{% endhint %}

## Other ways to create the connector

The same endpoint backs the `de` CLI and the Python SDK.

```bash title="Create a MySQL connector with the de CLI"
de connectors create connector.json     # POST /v1/connectors from a JSON body
de connectors list                      # GET /v1/connectors
```

```python title="Create a MySQL connector with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

connector = client.create_connector(
    name="App MySQL",
    connector_type="mysql",
    config={
        "host": "db.internal",
        "port": 3306,
        "database": "app",
        "user": "reader",
        "password": os.environ["MYSQL_PASSWORD"],
    },
)
print(connector.id, connector.status)  # "untested"
```

## Troubleshooting

<details>

<summary>`POST /v1/connectors/{id}/test` returns success: false</summary>

The response message is `"Connector type 'mysql' test not yet implemented. Please verify credentials manually."` with `error_type: "invalid_config"` and `recoverable: true`. This is expected — there is no managed test for MySQL. Verify the credentials from your own client instead (Step 4).

</details>

<details>

<summary>`POST /v1/data/connect` returns status: failed for a MySQL connector</summary>

`/v1/data/connect` runs the managed connection test before onboarding, so it reports the same "not yet implemented" message for MySQL and does not register a dataset. To run governed queries today, connect a fully validated database — see [Snowflake](snowflake.md), [PostgreSQL](postgres.md), or the [database overview](databases.md).

</details>

<details>

<summary>Choosing between structured fields and a connection_string</summary>

Both are accepted. The DSN form uses the `mysql+pymysql` driver: `mysql+pymysql://user:password@host:3306/database`. Discrete fields are easier to read and edit; a DSN is convenient if you already have one from another tool.

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
