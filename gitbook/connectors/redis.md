---
icon: bolt
description: Create a Redis connector with its real config fields, test the connection, browse its keys, onboard selected keys as a dataset, and run a governed query against them.
---

# Connect Redis

By the end of this page you will have a saved `redis` connector that reaches your instance, a confirmed `live` connection test, a browse listing of the keys it exposes, a selection of those keys onboarded as a queryable **dataset**, and a first [governed query](../guides/governed-query.md) returning key snapshots. Once onboarded, the key snapshot becomes [governed data](../concepts/governed-data.md): the engine reads it under a typed, validated contract, so results stay deterministic and auditable.

Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)), and a reachable Redis instance — either a DSN or a host, port, and (optionally) a password. Use `https://api.algenta.ai` for Algenta cloud, or your own origin such as `http://localhost:8000` for a self-hosted deployment.

{% hint style="info" %}
A `redis` connector takes these `config` fields: supply one of `url`, `redis_url`, or `connection_string` as a DSN (`redis://user:password@host:6379/0`, or `rediss://` for TLS), **or** the discrete fields `host`, `port` (default `6379`), `database` (alias `db`, default `0`), `user` (alias `username`), and `password`. To materialize data, set `keys` (a list or a comma-separated string). Optional: `value_max_items` (members per collection snapshot, default `100`), and `key_pattern` (default `*`) plus `limit` for browse.
{% endhint %}

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL so every command below picks them up from the environment. Keep your Redis password in its own variable so it never appears in shell history inline.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="https://api.algenta.ai"
export REDIS_PASSWORD="$REDIS_PASSWORD"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
echo "${REDIS_PASSWORD:?set REDIS_PASSWORD}" >/dev/null && echo "password present"
```

**Expected result:** three lines print without error — `key present`, your base URL, and `password present`. If any line errors, export the missing variable before continuing.
{% endstep %}

{% step %}
### Confirm the engine accepts `redis`

Ask the engine which connector types it supports and confirm `redis` is in the list.

```bash title="List connector types"
curl -s "$ALGENTA_BASE_URL/v1/connectors/types" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a JSON object with a `types` array that includes `"redis"`, for example `{"types": ["postgres", "redis", "neo4j", ...]}`. If `redis` is present, the next step's `config` shape is accepted.
{% endstep %}

{% step %}
### Create the Redis connector

`POST /v1/connectors` stores the connection name, type, and credentials, and returns the connector with `status: "untested"`. Use the discrete fields, or a single DSN — the engine reads either form.

```bash title="Create a redis connector (structured fields)"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Session Cache\",
    \"connector_type\": \"redis\",
    \"config\": {
      \"host\": \"cache.internal\",
      \"port\": 6379,
      \"database\": 0,
      \"password\": \"$REDIS_PASSWORD\"
    }
  }"
```

If you already have a Redis DSN, pass it as `connection_string` (or `url` / `redis_url`) instead of the discrete fields:

```bash title="Alternative: a single connection_string DSN"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Session Cache\",
    \"connector_type\": \"redis\",
    \"config\": {
      \"connection_string\": \"rediss://default:$REDIS_PASSWORD@cache.internal:6379/0\"
    }
  }"
```

Capture the returned `id` for the steps that follow:

```bash title="Capture the connector id"
export CONNECTOR_ID="$CONNECTOR_ID"
```

**Expected result:** a `201` response with the connector `id`, `"connector_type": "redis"`, and `"status": "untested"`. Credentials are encrypted at rest — the connector object never returns your `config` back to you, only its name, type, status, and last test result.

{% hint style="warning" %}
Provide either a DSN (`url`, `redis_url`, or `connection_string`) **or** a `host`. If neither is present the engine reports `Redis connector requires url, redis_url, or connection_string`.
{% endhint %}
{% endstep %}

{% step %}
### Test the connection

`POST /v1/connectors/{id}/test` makes a real connection attempt — it opens the client and issues a `PING` — then flips the connector to `live` on success or `error` on failure. Browsing requires a `live` connector, so always test first.

```bash title="Test the connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** `{"success": true, "status": "live", "latency_ms": 8, "message": "Redis connection successful (cache.internal:6379/0)"}`, and the connector's stored `status` is now `live`. On failure, `success` is `false`; `error_type` plus `recoverable` tell you whether to fix credentials and retry.
{% endstep %}

{% step %}
### Browse the keys it exposes

`GET /v1/connectors/{id}/browse` scans the live instance for keys matching `key_pattern` (default `*`) and returns a snapshot of each, so you can pick what to onboard. This returns `409 not_connected` if the connector is not `live` — run the test step first.

```bash title="Browse the connector"
curl -s "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a response with `"connector_type": "redis"`, an `items` array (each entry has `id`, `label`, `value_type`, `ttl_seconds`, and a `selection` of `{"keys": ["<key>"]}`), a `total`, and a message such as `Found 12 browsable Redis keys`. Note the keys you want to query — for example `session:active`.
{% endstep %}

{% step %}
### Onboard selected keys as a dataset

`POST /v1/data/connect` ties the saved connector to a selection and registers the result as a queryable dataset. Reference the connector by `connection_id`, set `connection_type` to `database` and `provider` to `redis`, and name the keys in `selection`.

```bash title="Connect a dataset from the redis connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"connection_type\": \"database\",
    \"provider\": \"redis\",
    \"dataset_name\": \"active_sessions\",
    \"connection_id\": \"$CONNECTOR_ID\",
    \"selection\": {\"keys\": [\"session:active\", \"session:pending\"]},
    \"visibility\": \"private\"
  }"
```

**Expected result:** `"status": "ready"` with a `dataset_id`, a `schema_summary` (row and column counts), and the `connection_id`. Each selected key becomes a row with fields such as `key`, `value_type`, `ttl_seconds`, `value_text`, and `value_json`. Save the `dataset_id`:

```bash title="Capture the dataset id"
export DATASET_ID="$DATASET_ID"
```
{% endstep %}

{% step %}
### Run a governed query

The key snapshot is now governed data. `POST /v1/query` runs a deterministic, typed query against the dataset and returns rows under the engine's validated contract.

```bash title="Query the new dataset"
curl -s -X POST "$ALGENTA_BASE_URL/v1/query" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"select\": [\"key\", \"value_type\", \"ttl_seconds\"],
    \"limit\": 10
  }"
```

**Expected result:** a `200` response with the matching rows and the resolved query plan. Re-running the same request against the same dataset returns the same rows in the same order — governed queries are deterministic by design.
{% endstep %}
{% endstepper %}

## Expected result

{% hint style="success" %}
You have a saved `redis` connector with `status: "live"`, a browse listing of its keys, a dataset onboarded from a selection of them that appears in `GET /v1/data` with a `dataset_id` and a profiled schema, and a first query returning key snapshots. The same intent against the same dataset returns the same deterministic answer, and every access is auditable.
{% endhint %}

## Other ways to connect

The same endpoints back the `de` CLI and the Python SDK — all three hit the identical API.

```bash title="Redis connect flow with the de CLI"
de connectors create connector.json     # POST /v1/connectors from a JSON body
de connectors test $CONNECTOR_ID         # real connection health check
de connectors browse $CONNECTOR_ID       # browse the live connector's keys
de data connect connect.json             # POST /v1/data/connect from a JSON body
de data list                             # list registered datasets
```

```python title="Connect Redis with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

connector = client.create_connector(
    name="Session Cache",
    connector_type="redis",
    config={
        "host": "cache.internal",
        "port": 6379,
        "database": 0,
        "password": os.environ["REDIS_PASSWORD"],
    },
)

test = client.test_connector(connector.id)
assert test.success, test.message

browse = client.browse_connector(connector.id)
print(browse.total, "keys")

result = client.connect_data(
    connection_type="database",
    provider="redis",
    dataset_name="active_sessions",
    connection_id=connector.id,
    selection={"keys": ["session:active", "session:pending"]},
    visibility="private",
)
print(result.status, result.dataset_id)
```

## Troubleshooting

{% hint style="warning" %}
**Test fails with a connection or timeout error.** The host, port, or DSN is wrong or the instance is unreachable. Confirm `host`/`port` (or the DSN) and that the instance accepts connections from your deployment.
{% endhint %}

{% hint style="warning" %}
**`409 not_connected` when browsing.** The connector is not `live`. Run `POST /v1/connectors/{id}/test` first; only a connector that passes its test can be browsed.
{% endhint %}

{% hint style="warning" %}
**`Redis connector fetch_data requires a non-empty 'keys' list`.** You onboarded without selecting keys. Pass `selection` as `{"keys": ["<key>", ...]}`, or set `keys` in the connector `config`.
{% endhint %}

{% hint style="info" %}
**Test fails with a privacy-policy or `error_type: "permission"` message.** The Redis host is outside your deployment's egress allowlist. Confirm the host and that the destination is permitted by your deployment's egress policy. See [Troubleshooting](../troubleshooting.md) for the full diagnosis flow.
{% endhint %}

## Next

{% content-ref url="../guides/governed-query.md" %}
[governed-query.md](../guides/governed-query.md)
{% endcontent-ref %}

{% content-ref url="neo4j.md" %}
[neo4j.md](neo4j.md)
{% endcontent-ref %}

{% content-ref url="reference.md" %}
[reference.md](reference.md)
{% endcontent-ref %}
