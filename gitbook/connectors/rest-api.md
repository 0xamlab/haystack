---
icon: cloud-arrow-down
description: Create a rest connector for any HTTP JSON API — set base_url and auth_type, test reachability, browse endpoints, connect a dataset, and run a governed query against it.
---

# Connect a REST API

This page walks you through wiring an external HTTP JSON API into Algenta as a `rest` connector. By the end you will have a saved connector that points at your API's `base_url`, authenticated with the scheme the endpoint expects, confirmed reachable with a real connection test, browsed for the resources it exposes, and turned into a queryable [dataset](../help/glossary.md). Once connected, the API's data becomes [governed data](../concepts/governed-data.md) — the engine fetches it under a typed, validated contract so the same query returns the same deterministic answer.

The `rest` connector fetches JSON over `GET` or `POST`, drills into a nested response array with a dot-path, and can page through bounded result sets. It is the right choice for SaaS APIs, internal microservices, and any endpoint that returns a list of records as JSON.

Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)), and the URL plus credentials for the API you want to connect. Use `https://api.algenta.ai` for Algenta cloud, or your own origin such as `http://localhost:8000` for a self-hosted deployment.

## The rest connector config

A REST connector is defined entirely by its `config` object. The fields below are the ones the engine reads — there are no others.

| Field | Used for | Notes |
| --- | --- | --- |
| `base_url` | Connection test | The API origin the test probes. `url` is accepted as an alias. Required to test. |
| `url` | Data fetch | The exact endpoint that returns the records. Required to fetch and browse. |
| `auth_type` | Auth scheme | One of `none`, `bearer`, `api_key`, or `basic`. Defaults to `none`. |
| `api_key` | `bearer` / `api_key` auth | The token or key value. For `bearer`, `token` is also accepted. |
| `api_key_header` | `api_key` auth | Header name for the key. Defaults to `X-API-Key`. |
| `username`, `password` | `basic` auth | Encoded into an HTTP Basic `Authorization` header. |
| `health_path` | Connection test | Optional path appended to `base_url` for the reachability probe (for example `/health`). |
| `method` | Data fetch | `GET` (default) or `POST`. Only these two are supported. |
| `headers` | Data fetch | Object of extra request headers sent on every call. |
| `params` | Data fetch | Object of query-string parameters. |
| `body` | Data fetch | JSON body, sent only when `method` is `POST`. |
| `timeout` | Data fetch | Request timeout in seconds. Defaults to `30`. |
| `data_path` | Data fetch | Dot-path to the records array in the response, for example `results.items`. |
| `pagination` | Data fetch | Optional bounded paging. `mode` is `page_number` or `cursor_path`; `max_pages` is required and must be positive. |

{% hint style="info" %}
**`base_url` vs `url`.** The connection test probes `base_url` (falling back to `url`), so a test only needs the origin. The fetch and browse steps read `url` as the precise endpoint that returns records. Set both: `base_url` to the API root and `url` to the listing endpoint. The test appends `health_path` to `base_url` when you provide one.
{% endhint %}

### How auth_type maps to headers

The test step builds the auth header for you from `auth_type`. For the fetch step, put the same credential into `headers` (the fetch path sends `headers` verbatim).

| `auth_type` | What the test sends |
| --- | --- |
| `none` | No auth header. |
| `bearer` | `Authorization: Bearer <api_key or token>`. |
| `api_key` | The value of `api_key` under the header named by `api_key_header` (default `X-API-Key`). |
| `basic` | `Authorization: Basic <base64(username:password)>`. |

## Walkthrough

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL so every command below reads them from the environment.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="https://api.algenta.ai"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
```

Both lines should print without error, and the base URL should match the deployment you intend to use.
{% endstep %}

{% step %}
### Create the rest connector

`POST /v1/connectors` stores the connector and returns it with `status: "untested"`. Pass `connector_type: "rest"` and a `config` that carries the API origin, the listing endpoint, and the auth scheme. The example below uses bearer auth and points `url` at an endpoint whose payload wraps the records under `data.items`.

```bash title="Create a bearer-auth REST connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Orders API",
    "connector_type": "rest",
    "config": {
      "base_url": "https://orders.example.com",
      "url": "https://orders.example.com/v2/orders",
      "auth_type": "bearer",
      "api_key": "$ORDERS_API_TOKEN",
      "method": "GET",
      "params": {"status": "open"},
      "headers": {"Authorization": "Bearer $ORDERS_API_TOKEN"},
      "data_path": "data.items",
      "timeout": 30
    }
  }'
```

The response includes the connector `id`, `connector_type`, and `status` (initially `untested`). Save the id for the next steps:

```bash title="Capture the connector id"
export CONNECTOR_ID="$CONNECTOR_ID_FROM_RESPONSE"
```

{% hint style="info" %}
The test step builds the auth header from `auth_type` + `api_key`, but the fetch step sends `headers` exactly as given. To make both work, set `auth_type` for the test and mirror the credential into `headers` for the fetch — as shown above, where `Authorization` carries the same bearer token.
{% endhint %}
{% endstep %}

{% step %}
### Test the connection

`POST /v1/connectors/{id}/test` makes a real HTTP request to `base_url` (plus `health_path` if set), applies the `auth_type` header, and flips the connector to `live` on a 2xx response or `error` otherwise. Browsing requires a `live` connector, so always test first.

```bash title="Test the connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result.** The connector flips to `live`, and a successful response looks like `{"success": true, "status": "ok", "latency_ms": 80, "message": "REST API reachable (200) — https://orders.example.com"}`. On failure, `success` is `false` and `error_type` plus `recoverable` tell you whether to fix the URL or credentials and retry. A non-2xx status returns the code in the message; a blocked destination returns a privacy-policy `error_type`.
{% endstep %}

{% step %}
### Browse the endpoints the connector exposes

`GET /v1/connectors/{id}/browse` fetches from the connector's `url` and reports what it found — the resource shape the API returns under your `data_path`. This returns `409 not_connected` if the connector is not `live`, so run the test step first.

```bash title="Browse the connector"
curl -s "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

The response has `connector_type`, an `items` array describing the browsable resource(s), a `total`, a `message`, and `discovery` metadata. For a REST API this surfaces the endpoint as the dataset you can onboard, along with the inferred record fields.
{% endstep %}

{% step %}
### Connect a dataset from the API

`POST /v1/data/connect` registers the connector's response as a queryable dataset. For a REST source the broad `connection_type` is `api` and the `provider` is `rest`. Reference the saved connector by `connection_id`.

```bash title="Connect a dataset from the saved connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"connection_type\": \"api\",
    \"provider\": \"rest\",
    \"dataset_name\": \"open_orders\",
    \"connection_id\": \"$CONNECTOR_ID\",
    \"visibility\": \"private\"
  }"
```

On success the response has `status: "ready"` with a `dataset_id`, a `schema_summary` (row and column counts inferred from the JSON records), and the `connection_id`. A bad credential or an unreachable endpoint returns `status: "failed"` with a message.
{% endstep %}

{% step %}
### Query the dataset

The dataset is now governed data. List your datasets to grab the `dataset_id`, then resolve a deterministic query against it.

```bash title="List datasets and query"
curl -s "$ALGENTA_BASE_URL/v1/data" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"

curl -s -X POST "$ALGENTA_BASE_URL/v1/query" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_id\": \"$DATASET_ID\",
    \"query\": \"count rows where status is open\"
  }"
```

The query runs under the dataset's typed contract, so the same intent against the same dataset returns the same answer every time. See [Run a governed query](../guides/governed-query.md) for the full query surface.
{% endstep %}
{% endstepper %}

## Paginating large endpoints

When the API returns more records than fit in one response, add a bounded `pagination` block to `config`. The connector stops at `max_pages` no matter what, so a misconfigured endpoint can never loop forever. Two modes are supported.

**Page-number paging** increments a query parameter until the page comes back empty (or a termination signal you name is exhausted):

```json title="page_number pagination"
{
  "url": "https://orders.example.com/v2/orders",
  "data_path": "data.items",
  "pagination": {
    "mode": "page_number",
    "page_param": "page",
    "start_page": 1,
    "page_size_param": "per_page",
    "page_size": 100,
    "max_pages": 50
  }
}
```

**Cursor paging** reads the next cursor from a dot-path in each response and stops when that path is empty:

```json title="cursor_path pagination"
{
  "url": "https://orders.example.com/v2/orders",
  "data_path": "data.items",
  "pagination": {
    "mode": "cursor_path",
    "next_path": "data.next_cursor",
    "cursor_param": "cursor",
    "max_pages": 50
  }
}
```

{% hint style="warning" %}
`max_pages` is required and must be a positive integer for either mode. If the connector reaches `max_pages` without an explicit termination signal, it raises a pagination error rather than silently truncating — raise `max_pages` or add a termination field such as `next_path` or `has_more_path`.
{% endhint %}

## Auth examples

The other auth schemes follow the same shape — only the `config` auth fields change.

```bash title="API-key header auth"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Metrics API",
    "connector_type": "rest",
    "config": {
      "base_url": "https://metrics.example.com",
      "url": "https://metrics.example.com/v1/series",
      "auth_type": "api_key",
      "api_key": "$METRICS_API_KEY",
      "api_key_header": "X-API-Key",
      "headers": {"X-API-Key": "$METRICS_API_KEY"},
      "data_path": "series"
    }
  }'
```

```bash title="Basic auth"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Legacy API",
    "connector_type": "rest",
    "config": {
      "base_url": "https://legacy.example.com",
      "url": "https://legacy.example.com/export",
      "auth_type": "basic",
      "username": "$LEGACY_USER",
      "password": "$LEGACY_PASSWORD",
      "data_path": "rows"
    }
  }'
```

For an unauthenticated public endpoint, omit `auth_type` (or set it to `none`) and provide just `base_url`, `url`, and `data_path`.

## Other ways to connect

The same endpoints back the `de` CLI and the Python SDK.

### de CLI

```bash title="REST connector with the de CLI"
de connectors create connector.json     # POST /v1/connectors from a JSON body
de connectors test $CONNECTOR_ID        # real reachability check
de connectors browse $CONNECTOR_ID      # browse a live connector
de data connect connect.json            # POST /v1/data/connect from a JSON body
```

### Python SDK

```python title="Connect a REST API with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

connector = client.create_connector(
    name="Orders API",
    connector_type="rest",
    config={
        "base_url": "https://orders.example.com",
        "url": "https://orders.example.com/v2/orders",
        "auth_type": "bearer",
        "api_key": os.environ["ORDERS_API_TOKEN"],
        "headers": {"Authorization": f"Bearer {os.environ['ORDERS_API_TOKEN']}"},
        "data_path": "data.items",
    },
)

test = client.test_connector(connector.id)
assert test.success, test.message

browse = client.browse_connector(connector.id)
print(browse.total, "items")

result = client.connect_data(
    connection_type="api",
    provider="rest",
    dataset_name="open_orders",
    connection_id=connector.id,
    visibility="private",
)
print(result.status, result.dataset_id)
```

## Troubleshooting

{% hint style="warning" %}
**Test fails with `REST API: 'base_url' is required`.** Add `base_url` (or `url`) to `config`. The test probes the origin; the fetch needs `url` to be the precise listing endpoint.
{% endhint %}

{% hint style="warning" %}
**Test passes but the dataset is empty.** The records live under a nested key. Set `data_path` to the dot-path of the array, for example `results.items` or `data`. If the array is at the top level, leave `data_path` unset.
{% endhint %}

{% hint style="warning" %}
**Auth works in the test but the fetch returns nothing.** The test builds the auth header from `auth_type`, but the fetch sends `headers` verbatim. Mirror the credential into `headers` (for example `Authorization: Bearer …` or your `api_key_header`).
{% endhint %}

{% hint style="info" %}
**Test fails with a privacy-policy `error_type`.** The destination host is outside the egress allowlist for your deployment. Confirm the `base_url` host and that the destination is permitted by your egress policy. See [Troubleshooting](../troubleshooting.md).
{% endhint %}

## Related

{% content-ref url="overview.md" %}
[overview.md](overview.md)
{% endcontent-ref %}

{% content-ref url="../guides/connect-data.md" %}
[connect-data.md](../guides/connect-data.md)
{% endcontent-ref %}

{% content-ref url="../concepts/governed-data.md" %}
[governed-data.md](../concepts/governed-data.md)
{% endcontent-ref %}
