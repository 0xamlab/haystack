---
icon: google
description: Create a Google Cloud Storage connector with its real config fields, test object access, browse a bucket, onboard one object as a governed dataset, and run a first governed query.
---

# Connect Google Cloud Storage

By the end of this page you will have a saved `gcs` connector that reaches a bucket, a confirmed `live` access check, a browse listing of the objects it can see, one of those objects onboarded as a queryable **dataset**, and a first [governed query](../guides/governed-query.md) returning rows from it. The engine reads the object in place, parses it (CSV, TSV, JSON, Parquet, or Excel), and registers the rows as [governed data](../concepts/governed-data.md) under a typed, validated contract.

Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)), and access to a GCS bucket — either a service account or a public bucket. Use `https://api.algenta.ai` for Algenta cloud, or your own origin such as `http://localhost:8000` for a self-hosted deployment.

{% hint style="info" %}
A `gcs` connector reads these `config` fields: `bucket` and `blob` (the object path) identify the object and are both required to test the connection; `file_type` overrides the format otherwise inferred from the blob's extension; `json_path` is a dot-path to a records array inside a JSON file; `project_id` sets the billing project. For credentials, supply `credentials` (a path to a service account JSON file on the engine host, or an inline JSON string), or `service_account_json` (an inline JSON string), or set `anonymous: true` to read a public bucket without credentials.
{% endhint %}

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL. If you authenticate with a service account JSON, keep it in its own variable.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="https://api.algenta.ai"
export GCP_SERVICE_ACCOUNT_JSON="$GCP_SERVICE_ACCOUNT_JSON"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
```

**Expected result:** `key present` and your base URL print without error. If either errors, export the missing variable before continuing.
{% endstep %}

{% step %}
### Confirm the engine accepts `gcs`

Ask the engine which connector types it supports and confirm `gcs` is in the list.

```bash title="List connector types"
curl -s "$ALGENTA_BASE_URL/v1/connectors/types" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a JSON object with a `types` array that includes `"gcs"`, for example `{"types": ["azure", "gcs", "s3", ...]}`.
{% endstep %}

{% step %}
### Create the GCS connector

`POST /v1/connectors` stores the connection name, type, and credentials, and returns the connector with `status: "untested"`. Set `bucket`, `blob`, and your credentials. This example reads a public bucket with `anonymous`:

```bash title="Create a gcs connector (public bucket)"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Public GCS Data\",
    \"connector_type\": \"gcs\",
    \"config\": {
      \"bucket\": \"open-datasets\",
      \"blob\": \"census/2020.parquet\",
      \"anonymous\": true
    }
  }"
```

For a private bucket on a self-hosted engine, point `credentials` at a service account JSON file the engine can read, and set `project_id`:

```bash title="Alternative: a private bucket with a service account"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Analytics GCS\",
    \"connector_type\": \"gcs\",
    \"config\": {
      \"bucket\": \"acme-analytics\",
      \"blob\": \"exports/orders.csv\",
      \"project_id\": \"acme-prod\",
      \"credentials\": \"/secrets/gcp-sa.json\"
    }
  }"
```

Capture the returned `id` for the steps that follow:

```bash title="Capture the connector id"
export CONNECTOR_ID="$CONNECTOR_ID"
```

**Expected result:** a `201` response with the connector `id`, `"connector_type": "gcs"`, and `"status": "untested"`. Credentials are encrypted at rest.

{% hint style="warning" %}
The connection test reads both `bucket` and `blob`; if `blob` is missing the test fails. Point `blob` at a real object (for example the one you plan to onboard). On Algenta cloud, prefer `service_account_json` (an inline JSON string) or `anonymous`, since a file path in `credentials` must exist on the engine host.
{% endhint %}
{% endstep %}

{% step %}
### Test object access

`POST /v1/connectors/{id}/test` makes a real request that confirms `gs://bucket/blob` is readable, then flips the connector to `live` on success or `error` on failure.

```bash title="Test the connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** `{"success": true, "status": "live", "latency_ms": 240, "message": "gs://acme-analytics/exports/orders.csv accessible."}`, and the connector's stored `status` is now `live`. On failure, `error_type` (for example `not_found`, `auth`, or `permission`) plus `recoverable` guide your fix.
{% endstep %}

{% step %}
### Browse the bucket

`GET /v1/connectors/{id}/browse` lists up to 100 objects in the bucket, so you can pick what to onboard. This returns `409 not_connected` if the connector is not `live` — run the test step first, and make sure `bucket` is set.

```bash title="Browse the connector"
curl -s "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a response with `"connector_type": "gcs"`, an `items` array (each entry is an object, with its `selection.object_path`), a `total`, and a `message` such as `"Found 19 objects in gs://acme-analytics"`. Note the `object_path` you want to onboard — for example `exports/orders.csv`.
{% endstep %}

{% step %}
### Onboard one object as a dataset

`POST /v1/data/connect` ties the saved connector to a selection — an object path — and registers the parsed rows as a queryable dataset. Reference the connector by `connection_id` and name the object in `selection.object_path`.

```bash title="Connect a dataset from the gcs connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"dataset_name\": \"sales_orders\",
    \"connection_id\": \"$CONNECTOR_ID\",
    \"selection\": {\"object_path\": \"exports/orders.csv\"},
    \"visibility\": \"private\"
  }"
```

The format is inferred from the object's extension; override it with `file_type` in the connector `config` (one of `csv`, `tsv`, `json`, `parquet`, `excel`), and use `json_path` to point at a records array inside a JSON file.

**Expected result:** `"status": "ready"` with a `dataset_id`, a `schema_summary` (row and column counts), and the `connection_id`. If more than one object matches and no selection is given, you get `"status": "needs_selection"` with a `choices` array — re-call with one `object_path` from `choices`. Save the `dataset_id`:

```bash title="Capture the dataset id"
export DATASET_ID="$DATASET_ID"
```
{% endstep %}

{% step %}
### Run a governed query

The parsed object is now governed data. `POST /v1/query` runs a deterministic, typed query against the dataset and returns rows under the engine's validated contract.

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

You have a saved `gcs` connector with `status: "live"`, a browse listing of a bucket's objects, a dataset onboarded from one of them that appears in `GET /v1/data` with a `dataset_id` and a profiled schema, and a first query returning rows. The same intent against the same dataset returns the same deterministic answer, and every access is auditable.

## Other ways to connect

The same endpoints back the `de` CLI and the Python SDK — all three hit the identical API.

```bash title="GCS connect flow with the de CLI"
de connectors create connector.json        # POST /v1/connectors from a JSON body
de connectors test $CONNECTOR_ID           # real object-access check
de connectors browse $CONNECTOR_ID         # browse the bucket's objects
de data connect --request connect.json     # POST /v1/data/connect from a JSON body
de data list                               # list registered datasets
```

```python title="Connect GCS with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

connector = client.create_connector(
    name="Analytics GCS",
    connector_type="gcs",
    config={
        "bucket": "acme-analytics",
        "blob": "exports/orders.csv",
        "project_id": "acme-prod",
        "service_account_json": os.environ["GCP_SERVICE_ACCOUNT_JSON"],
    },
)

test = client.test_connector(connector.id)
assert test.success, test.message

result = client.connect_data(
    connection_type="object_storage",
    provider="gcs",
    dataset_name="sales_orders",
    connection_id=connector.id,
    selection={"object_path": "exports/orders.csv"},
    visibility="private",
)
print(result.status, result.dataset_id)
```

## Troubleshooting

<details>

<summary>Test fails because `blob` is not set</summary>

The GCS test reads both `bucket` and `blob`. Set `blob` to a real object path (typically the object you plan to onboard) and re-test.

</details>

<details>

<summary>Test fails with `error_type: "auth"` or `"not_found"`</summary>

For `auth`, the service account is missing or lacks access — check `credentials` / `service_account_json` and that the account can read the bucket. For `not_found`, confirm `bucket` and `blob` name a real object. A private bucket read anonymously will also fail.

</details>

<details>

<summary>Test fails with a privacy-policy or permission message</summary>

`error_type` is `permission`. Google Cloud Storage is outside the egress allowlist for your deployment. Confirm the destination is permitted by your deployment's egress policy. See [Troubleshooting](../troubleshooting.md).

</details>

<details>

<summary>`409 not_connected` when browsing</summary>

The connector is not `live`. Run `POST /v1/connectors/{id}/test` first; only a connector that passes its test can be browsed. Browsing also requires `bucket` to be set. Editing a connector's `config` resets it to `untested`, so re-test after any change.

</details>

## Next

{% content-ref url="../guides/governed-query.md" %}
[governed-query.md](../guides/governed-query.md)
{% endcontent-ref %}

{% content-ref url="s3.md" %}
[s3.md](s3.md)
{% endcontent-ref %}

{% content-ref url="azure-blob.md" %}
[azure-blob.md](azure-blob.md)
{% endcontent-ref %}
