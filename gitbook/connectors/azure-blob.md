---
icon: microsoft
description: Create an Azure Blob Storage connector with its real config fields, test blob access, browse a container, onboard one blob as a governed dataset, and run a first governed query.
---

# Connect Azure Blob Storage

By the end of this page you will have a saved `azure` connector that reaches a container, a confirmed `live` access check, a browse listing of the blobs it can see, one of those blobs onboarded as a queryable **dataset**, and a first [governed query](../guides/governed-query.md) returning rows from it. The engine reads the blob in place, parses it (CSV, TSV, JSON, Parquet, or Excel), and registers the rows as [governed data](../concepts/governed-data.md) under a typed, validated contract.

Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)), and access to an Azure Storage container — a connection string, an account URL, or a public blob URL. Use `https://api.algenta.ai` for Algenta cloud, or your own origin such as `http://localhost:8000` for a self-hosted deployment.

{% hint style="info" %}
An `azure` connector reads these `config` fields. To identify the blob, supply either `blob_url` (a full blob URL, treated as public) or a `container` plus a `blob` path. To authenticate a private blob, supply a `connection_string` or an `account_url`. `file_type` overrides the format otherwise inferred from the blob's extension; `json_path` is a dot-path to a records array inside a JSON file; `anonymous: true` reads a public blob without credentials. Browsing a container additionally accepts a `prefix` to filter blob names.
{% endhint %}

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL, and keep your Azure Storage connection string in its own variable.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="https://api.algenta.ai"
export AZURE_STORAGE_CONNECTION_STRING="$AZURE_STORAGE_CONNECTION_STRING"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
echo "${AZURE_STORAGE_CONNECTION_STRING:?set AZURE_STORAGE_CONNECTION_STRING}" >/dev/null && echo "connection string present"
```

**Expected result:** three lines print without error — `key present`, your base URL, and `connection string present`. If any line errors, export the missing variable before continuing.
{% endstep %}

{% step %}
### Confirm the engine accepts `azure`

Ask the engine which connector types it supports and confirm `azure` is in the list.

```bash title="List connector types"
curl -s "$ALGENTA_BASE_URL/v1/connectors/types" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a JSON object with a `types` array that includes `"azure"`, for example `{"types": ["azure", "gcs", "s3", ...]}`.
{% endstep %}

{% step %}
### Create the Azure connector

`POST /v1/connectors` stores the connection name, type, and credentials, and returns the connector with `status: "untested"`. Supply a `connection_string` plus the `container` and `blob` you want to reach.

```bash title="Create an azure connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Analytics Blob\",
    \"connector_type\": \"azure\",
    \"config\": {
      \"connection_string\": \"$AZURE_STORAGE_CONNECTION_STRING\",
      \"container\": \"analytics\",
      \"blob\": \"exports/orders.csv\"
    }
  }"
```

For a public blob, drop the credentials and pass a `blob_url`:

```bash title="Alternative: a public blob URL"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Public Blob\",
    \"connector_type\": \"azure\",
    \"config\": {
      \"blob_url\": \"https://acme.blob.core.windows.net/public/census.parquet\"
    }
  }"
```

Capture the returned `id` for the steps that follow:

```bash title="Capture the connector id"
export CONNECTOR_ID="$CONNECTOR_ID"
```

**Expected result:** a `201` response with the connector `id`, `"connector_type": "azure"`, and `"status": "untested"`. Credentials are encrypted at rest.

{% hint style="warning" %}
The connection test resolves the blob from `blob_url`, or from `account_url` + `container` + `blob`, or from `connection_string` + `container` + `blob`. If none of those combinations is complete the test fails — supply a `blob` alongside your `container` and credentials.
{% endhint %}
{% endstep %}

{% step %}
### Test blob access

`POST /v1/connectors/{id}/test` makes a real request that confirms the blob is readable, then flips the connector to `live` on success or `error` on failure.

```bash title="Test the connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** `{"success": true, "status": "live", "latency_ms": 260, "message": "azure://analytics/exports/orders.csv is accessible."}` (or, for a public `blob_url`, a message naming that URL), and the connector's stored `status` is now `live`. On failure, `error_type` (for example `not_found`, `auth`, or `permission`) plus `recoverable` guide your fix.
{% endstep %}

{% step %}
### Browse the container

`GET /v1/connectors/{id}/browse` lists up to 100 blobs in the container, so you can pick what to onboard. This returns `409 not_connected` if the connector is not `live` — run the test step first, and make sure `container` and a `connection_string` or `account_url` are set.

```bash title="Browse the connector"
curl -s "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a response with `"connector_type": "azure"`, an `items` array (each entry is a blob, with its `selection.object_path`), a `total`, and a `message` such as `"Found 12 blobs in azure://analytics"`. Note the `object_path` you want to onboard — for example `exports/orders.csv`. Set a `prefix` in the connector `config` to narrow the listing.
{% endstep %}

{% step %}
### Onboard one blob as a dataset

`POST /v1/data/connect` ties the saved connector to a selection — a blob path — and registers the parsed rows as a queryable dataset. Reference the connector by `connection_id` and name the blob in `selection.object_path`.

```bash title="Connect a dataset from the azure connector"
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

The format is inferred from the blob's extension; override it with `file_type` in the connector `config` (one of `csv`, `tsv`, `json`, `parquet`, `excel`), and use `json_path` to point at a records array inside a JSON file.

**Expected result:** `"status": "ready"` with a `dataset_id`, a `schema_summary` (row and column counts), and the `connection_id`. If more than one blob matches and no selection is given, you get `"status": "needs_selection"` with a `choices` array — re-call with one `object_path` from `choices`. Save the `dataset_id`:

```bash title="Capture the dataset id"
export DATASET_ID="$DATASET_ID"
```
{% endstep %}

{% step %}
### Run a governed query

The parsed blob is now governed data. `POST /v1/query` runs a deterministic, typed query against the dataset and returns rows under the engine's validated contract.

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

You have a saved `azure` connector with `status: "live"`, a browse listing of a container's blobs, a dataset onboarded from one of them that appears in `GET /v1/data` with a `dataset_id` and a profiled schema, and a first query returning rows. The same intent against the same dataset returns the same deterministic answer, and every access is auditable.

## Other ways to connect

The same endpoints back the `de` CLI and the Python SDK — all three hit the identical API.

```bash title="Azure Blob connect flow with the de CLI"
de connectors create connector.json        # POST /v1/connectors from a JSON body
de connectors test $CONNECTOR_ID           # real blob-access check
de connectors browse $CONNECTOR_ID         # browse the container's blobs
de data connect --request connect.json     # POST /v1/data/connect from a JSON body
de data list                               # list registered datasets
```

```python title="Connect Azure Blob with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

connector = client.create_connector(
    name="Analytics Blob",
    connector_type="azure",
    config={
        "connection_string": os.environ["AZURE_STORAGE_CONNECTION_STRING"],
        "container": "analytics",
        "blob": "exports/orders.csv",
    },
)

test = client.test_connector(connector.id)
assert test.success, test.message

result = client.connect_data(
    connection_type="object_storage",
    provider="azure",
    dataset_name="sales_orders",
    connection_id=connector.id,
    selection={"object_path": "exports/orders.csv"},
    visibility="private",
)
print(result.status, result.dataset_id)
```

## Troubleshooting

<details>

<summary>Test fails to resolve the blob</summary>

The config did not form a complete target. Provide a `blob_url`, or a `container` and `blob` together with either a `connection_string` or an `account_url`. A `container` without a `blob` is enough to browse but not to test a specific object.

</details>

<details>

<summary>Test fails with `error_type: "auth"` or `"not_found"`</summary>

For `auth`, the connection string or account credentials are missing or invalid. For `not_found`, confirm the `container` and `blob` name a real object. A private blob read anonymously will also fail.

</details>

<details>

<summary>Test fails with a privacy-policy or permission message</summary>

`error_type` is `permission`. The Azure Storage endpoint is outside the egress allowlist for your deployment. Confirm the `account_url` / `connection_string` account and that the destination is permitted by your deployment's egress policy. See [Troubleshooting](../troubleshooting.md).

</details>

<details>

<summary>`409 not_connected` when browsing</summary>

The connector is not `live`. Run `POST /v1/connectors/{id}/test` first; only a connector that passes its test can be browsed. Browsing also requires `container` plus a `connection_string` or `account_url`. Editing a connector's `config` resets it to `untested`, so re-test after any change.

</details>

## Next

{% content-ref url="../guides/governed-query.md" %}
[governed-query.md](../guides/governed-query.md)
{% endcontent-ref %}

{% content-ref url="s3.md" %}
[s3.md](s3.md)
{% endcontent-ref %}

{% content-ref url="gcs.md" %}
[gcs.md](gcs.md)
{% endcontent-ref %}
