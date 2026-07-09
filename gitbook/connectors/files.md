---
icon: file-lines
description: Create a file connector for CSV, TSV, JSON, Excel, or Parquet data with its real config fields, test that it parses, onboard it as a dataset, and run a governed query against it.
---

# Connect a file

By the end of this page you will have a saved `file` connector that parses your CSV, TSV, JSON, Excel, or Parquet data, a confirmed parse with a record count, that data onboarded as a queryable **dataset**, and a first [governed query](../guides/governed-query.md) returning rows. Once onboarded, the file becomes [governed data](../concepts/governed-data.md): the engine reads it under a typed, validated contract, so results stay deterministic and auditable.

Prerequisites: an API key and a base URL (see [Authentication](../authentication.md)), and the data itself — either inline `content` or a `file_path` the engine can read. Use `https://api.algenta.ai` for Algenta cloud, or your own origin such as `http://localhost:8000` for a self-hosted deployment.

{% hint style="info" %}
A `file` connector takes these `config` fields: `file_type` is one of `csv` (default), `tsv`, `json`, `excel`, or `parquet`. Provide the data as `content` — raw text for CSV/TSV/JSON, or base64-encoded bytes for Excel/Parquet — **or** as a `file_path` on disk (used when `content` is empty). `json_path` is a dot-separated path to the records array in JSON (for example `data.items`). `sheet` selects an Excel sheet by name or 0-based index (default `0`). `delimiter` overrides the CSV column delimiter (auto-detected by default). The alias type name `file_upload` resolves to `file`.
{% endhint %}

{% stepper %}
{% step %}
### Set your credentials

Export your API key and base URL so every command below picks them up from the environment.

```bash title="Set credentials"
export ALGENTA_API_KEY="$ALGENTA_API_KEY"
export ALGENTA_BASE_URL="https://api.algenta.ai"
```

Verify the variables are set:

```bash title="Verify"
echo "${ALGENTA_API_KEY:?set ALGENTA_API_KEY}" >/dev/null && echo "key present"
echo "$ALGENTA_BASE_URL"
```

**Expected result:** two lines print without error — `key present` and your base URL. If either line errors, export the missing variable before continuing.
{% endstep %}

{% step %}
### Confirm the engine accepts `file`

Ask the engine which connector types it supports and confirm `file` is in the list.

```bash title="List connector types"
curl -s "$ALGENTA_BASE_URL/v1/connectors/types" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** a JSON object with a `types` array that includes `"file"` (and its alias `"file_upload"`), for example `{"types": ["file", "file_upload", "s3", ...]}`. If `file` is present, the next step's `config` shape is accepted.
{% endstep %}

{% step %}
### Create the file connector

`POST /v1/connectors` stores the connector and returns it with `status: "untested"`. Pick the tab that matches your format — each sets the right `file_type` and payload shape.

{% tabs %}
{% tab title="CSV / TSV" %}
Pass the rows as raw `content`. Use `file_type` `csv` (default) or `tsv`; override the separator with `delimiter` if auto-detection needs help.

```bash title="Create a csv file connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Regional Sales",
    "connector_type": "file",
    "config": {
      "file_type": "csv",
      "content": "region,amount\nEMEA,1200\nAMER,3400\n"
    }
  }'
```
{% endtab %}

{% tab title="JSON" %}
Pass the document as raw `content` and point `json_path` at the records array. When the array is nested, use a dot-path such as `data.items`; when the top level is an object with a well-known wrapper (`data`, `records`, `rows`, `results`, `items`, or `value`), the engine finds the array automatically. Nested objects are flattened with dotted keys.

```bash title="Create a json file connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Regional Sales",
    "connector_type": "file",
    "config": {
      "file_type": "json",
      "json_path": "data.items",
      "content": "{\"data\": {\"items\": [{\"region\": \"EMEA\", \"amount\": 1200}]}}"
    }
  }'
```
{% endtab %}

{% tab title="Excel" %}
Excel workbooks are binary, so pass base64-encoded bytes as `content` and select the worksheet with `sheet` (a name or a 0-based index).

```bash title="Create an excel file connector"
XLSX_B64="$(base64 < sales.xlsx | tr -d '\n')"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Regional Sales\",
    \"connector_type\": \"file\",
    \"config\": {
      \"file_type\": \"excel\",
      \"sheet\": 0,
      \"content\": \"$XLSX_B64\"
    }
  }"
```
{% endtab %}

{% tab title="On disk" %}
When the file lives on a path the engine can read, set `file_path` and leave `content` empty. This works for every `file_type` — text formats are read as UTF-8, Excel and Parquet as bytes.

```bash title="Create a file connector from a path"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Regional Sales",
    "connector_type": "file",
    "config": {
      "file_type": "parquet",
      "file_path": "/data/sales.parquet"
    }
  }'
```
{% endtab %}
{% endtabs %}

Capture the returned `id` for the steps that follow:

```bash title="Capture the connector id"
export CONNECTOR_ID="$CONNECTOR_ID"
```

**Expected result:** a `201` response with the connector `id`, `"connector_type": "file"`, and `"status": "untested"`.

{% hint style="warning" %}
Provide either `content` or `file_path`. For `excel` and `parquet`, `content` must be base64-encoded bytes — raw text will not parse.
{% endhint %}
{% endstep %}

{% step %}
### Test that it parses

`POST /v1/connectors/{id}/test` parses the configured payload and reports how many records it read, then flips the connector to `live` on success or `error` on failure. Unlike a database connector there is no network round-trip — the test validates the data shape.

```bash title="Test the connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

**Expected result:** `{"success": true, "status": "live", "latency_ms": 4, "message": "File connector parsed 2 records from inline payload"}` (for a `file_path` connector the source is the path). On failure, `success` is `false`; `error_type` plus `recoverable` tell you whether to fix the payload and retry.
{% endstep %}

{% step %}
### Onboard the file as a dataset

`POST /v1/data/connect` registers the parsed file as a queryable dataset. Reference the connector by `connection_id` and set `connection_type` to `file` — the file's `content` or `file_path` already lives in the connector, so no `selection` is needed.

```bash title="Connect a dataset from the file connector"
curl -s -X POST "$ALGENTA_BASE_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"connection_type\": \"file\",
    \"dataset_name\": \"regional_sales\",
    \"connection_id\": \"$CONNECTOR_ID\",
    \"visibility\": \"private\"
  }"
```

**Expected result:** `"status": "ready"` with a `dataset_id`, a `schema_summary` (row and column counts), and the `connection_id`. Save the `dataset_id`:

```bash title="Capture the dataset id"
export DATASET_ID="$DATASET_ID"
```
{% endstep %}

{% step %}
### Run a governed query

The file is now governed data. `POST /v1/query` runs a deterministic, typed query against the dataset and returns rows under the engine's validated contract.

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

{% hint style="success" %}
You have a saved `file` connector with `status: "live"`, a confirmed parse with a record count, a dataset onboarded from it that appears in `GET /v1/data` with a `dataset_id` and a profiled schema, and a first query returning rows. The same intent against the same dataset returns the same deterministic answer, and every access is auditable.
{% endhint %}

## Other ways to connect

The same endpoints back the `de` CLI and the Python SDK — all three hit the identical API.

```bash title="File connect flow with the de CLI"
de connectors create connector.json     # POST /v1/connectors from a JSON body
de connectors test $CONNECTOR_ID         # parse the configured payload
de data connect connect.json             # POST /v1/data/connect from a JSON body
de data list                             # list registered datasets
```

```python title="Connect a file with the Python SDK"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(
    api_key=os.environ["ALGENTA_API_KEY"],
    base_url="https://api.algenta.ai",
)

connector = client.create_connector(
    name="Regional Sales",
    connector_type="file",
    config={
        "file_type": "csv",
        "content": "region,amount\nEMEA,1200\nAMER,3400\n",
    },
)

test = client.test_connector(connector.id)
assert test.success, test.message

result = client.connect_data(
    connection_type="file",
    dataset_name="regional_sales",
    connection_id=connector.id,
    visibility="private",
)
print(result.status, result.dataset_id)
```

## Troubleshooting

{% hint style="warning" %}
**`Invalid JSON` on test.** The `content` is not valid JSON, or `json_path` points at a value that is not a records array. Confirm the document parses and that `json_path` reaches the array of objects.
{% endhint %}

{% hint style="warning" %}
**Excel or Parquet test fails to decode.** For `excel` and `parquet`, `content` must be base64-encoded bytes. Re-encode the file (for example `base64 < file.xlsx`) or use `file_path` instead.
{% endhint %}

{% hint style="warning" %}
**Test parses `0 records`.** Both `content` and `file_path` were empty, or the file had no data rows. Provide non-empty `content` or a readable `file_path`, and check the header row.
{% endhint %}

{% hint style="info" %}
**A path error for `file_path`.** The path is not readable by the engine. On a self-hosted deployment, mount the file where the engine runs, or send it inline as `content`. See [Troubleshooting](../troubleshooting.md) for the full diagnosis flow.
{% endhint %}

## Next

{% content-ref url="../guides/governed-query.md" %}
[governed-query.md](../guides/governed-query.md)
{% endcontent-ref %}

{% content-ref url="../guides/first-query.md" %}
[first-query.md](../guides/first-query.md)
{% endcontent-ref %}

{% content-ref url="reference.md" %}
[reference.md](reference.md)
{% endcontent-ref %}
