---
icon: plug
description: Python SDK reference for connectors and datasets — create, test, browse, and update connectors, then onboard, list, summarize, refresh, and delete datasets.
---

# Connectors and datasets

These methods manage data connectors and the datasets you onboard from them. They are available on both `AlgentaClient` and `AsyncAlgentaClient` (await the async calls). Connector metadata is passed as typed keyword arguments; dataset onboarding takes a request dict. For a full walkthrough see [Connect a data source](../../guides/connect-data.md) and the per-provider pages under [Connectors](../../connectors/overview.md).

## Method reference

| Method | Purpose |
| --- | --- |
| `create_connector(*, name, connector_type, config=None, description=None, visibility=None)` | Create a data connector (`ConnectorInfo`). Posts to `/v1/connectors`. |
| `list_connectors(*, page=1, limit=200)` | List connectors (`ConnectorListResult`). Reads `/v1/connectors`. |
| `iter_connectors(*, page=1, limit=200, max_items=None)` | Iterate connectors across pages, capped by `max_items`. |
| `get_connector(connector_id)` | Fetch one connector (`ConnectorInfo`). Reads `/v1/connectors/{connector_id}`. |
| `update_connector(connector_id, *, name=None, description=None, visibility=None, config=None)` | Update a connector's metadata or config (`ConnectorInfo`). Sends `PATCH /v1/connectors/{connector_id}`. |
| `delete_connector(connector_id)` | Delete a connector. Sends `DELETE /v1/connectors/{connector_id}`. |
| `test_connector(connector_id)` | Run a real connection test on a saved connector (`ConnectorTestInfo`). Posts to `/v1/connectors/{connector_id}/test`. |
| `preview_test_connector(*, connector_type, config=None)` | Test a connector config before saving it (`ConnectorTestInfo`). Posts to `/v1/connectors/test`. |
| `browse_connector(connector_id)` | List the tables a live connector exposes (`ConnectorBrowseResult`). Reads `/v1/connectors/{connector_id}/browse`. |
| `preview_browse_connector(*, connector_type, config=None)` | Browse a connector config before saving it (`ConnectorBrowseResult`). Posts to `/v1/connectors/browse`. |
| `connect_data(request=None, **kwargs)` | Onboard a connector selection (table or query) as a queryable dataset (`DatasetConnectResult`). Posts to `/v1/data/connect`. |
| `list_datasets(*, page=1, limit=200, search=None, status=None, source_name=None, compact=False)` | List datasets (`DatasetListResult`). Reads `/v1/data`. |
| `iter_datasets(*, page=1, limit=200, max_items=None, search=None, status=None, source_name=None, compact=False)` | Iterate datasets across pages, capped by `max_items`. |
| `get_dataset(dataset_id)` | Fetch dataset detail (`DatasetDetailResult`). Reads `/v1/data/{dataset_id}`. |
| `get_dataset_summary(dataset_id)` | Fetch a dataset's profiled schema summary (`DatasetSummaryResult`). Reads `/v1/data/{dataset_id}/summary`. |
| `refresh_dataset(dataset_id)` | Re-ingest a dataset from its source (`DatasetConnectResult`). Posts to `/v1/data/{dataset_id}/refresh`. |
| `delete_dataset(dataset_id)` | Delete a dataset (`DatasetDeleteResult`). Sends `DELETE /v1/data/{dataset_id}`. |

## Example: create a connector, test it, and browse tables

```python title="connector.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

connector = client.create_connector(
    name="Analytics Warehouse",
    connector_type="snowflake",
    config={
        "account": "xy12345.eu-central-1",
        "user": "ANALYTICS",
        "password": os.environ["SNOWFLAKE_PASSWORD"],
        "warehouse": "COMPUTE_WH",
        "database": "SALES",
        "schema": "PUBLIC",
    },
)

test = client.test_connector(connector.id)
assert test.success, test.message

browse = client.browse_connector(connector.id)
print(browse.total, "tables")
```

## Example: onboard a dataset and read its summary

```python title="dataset.py"
import os
from decision_engine import AlgentaClient

client = AlgentaClient(api_key=os.environ["ALGENTA_API_KEY"])

result = client.connect_data(
    connection_type="database",
    provider="snowflake",
    dataset_name="sales_orders",
    connection_id="$CONNECTOR_ID",
    selection={"table": "PUBLIC.ORDERS"},
    visibility="private",
)
print(result.status, result.dataset_id)

summary = client.get_dataset_summary(result.dataset_id)
print(summary.row_count)

# Browse the full catalog.
datasets = client.list_datasets(search="orders", compact=True)
for dataset in datasets.datasets:
    print(dataset.dataset_id, dataset.name)
```

## Related pages

{% content-ref url="../../guides/connect-data.md" %}
[connect-data.md](../../guides/connect-data.md)
{% endcontent-ref %}

{% content-ref url="../../connectors/snowflake.md" %}
[snowflake.md](../../connectors/snowflake.md)
{% endcontent-ref %}

{% content-ref url="simulations-and-queries.md" %}
[simulations-and-queries.md](simulations-and-queries.md)
{% endcontent-ref %}
