---
icon: table-list
description: Every supported Algenta connector type, grouped by category, with its required and optional config fields, the canonical type names, and the untested-live-error status lifecycle.
---

# Connectors reference

A [connector](../help/glossary.md) is a configured connection to an external system that backs a [source](../concepts/governed-data.md) or dataset. This page lists every supported connector type, the config fields each one accepts, and the status lifecycle a connector moves through.

Connectors are created through the API or [CLI](../cli.md). The two key fields on the wire are `connector_type` (one of the canonical names below) and `config` (a flat object whose keys depend on the type). For the full create/test/browse endpoints see the [API reference](../api/reference.md); to walk through connecting your first source see [Connect data](../guides/connect-data.md).

## Categories at a glance

| Category | Connector types |
| --- | --- |
| Databases | `postgres`, `mysql`, `mssql`, `sqlite`, `clickhouse`, `redshift` |
| Warehouses | `snowflake`, `bigquery` |
| Object storage | `s3`, `gcs`, `azure` |
| API | `rest` |
| Files | `file` (`csv`, `tsv`, `json`, `excel`, `parquet`) |

{% hint style="info" %}
Algenta also ships graph/cache connectors (`neo4j`, `redis`), a search connector (`elasticsearch`), and repository connectors (`github_repo`, `gitlab_repo`, `bitbucket_repo`, `local_repo`, `repo_archive`). Those are documented elsewhere; this page covers the data connectors used for governed query.
{% endhint %}

## Type names and aliases

`connector_type` is normalized before it is stored, so several spellings resolve to one canonical type. Use the canonical name in new integrations.

| You may send | Canonical type |
| --- | --- |
| `postgresql` | `postgres` |
| `rest_api` | `rest` |
| `file_upload` | `file` |
| `elastic` | `elasticsearch` |
| `azure` | `azure` (stored), `azure_blob` (provider) |

Hyphens are accepted and converted to underscores. An unknown type is rejected with a `422 invalid_type` error listing the valid set.

## The status lifecycle

Every connector carries a `status`. A new connector is `untested`; testing it transitions it to `live` or `error`.

| Status | Meaning | How you reach it |
| --- | --- | --- |
| `untested` | Created or edited but never verified. Cannot be browsed yet. | `POST /v1/connectors`, or any `PATCH` that changes `config`. |
| `live` | Last connection test succeeded. Ready to browse and query. | A successful `POST /v1/connectors/{id}/test`. |
| `error` | Last connection test failed; `error_message` holds the reason. | A failed `POST /v1/connectors/{id}/test`. |

```text
created ──▶ untested ──test──▶ live
                   │              │
                   └──test──▶ error
edit config ─▶ back to untested
```

{% hint style="warning" %}
Browsing requires a `live` connector. `GET /v1/connectors/{id}/browse` returns `409 not_connected` until you run `/test` and it passes. Editing `config` resets the connector to `untested` and clears the previous error.
{% endhint %}

You can also validate a config without saving it: `POST /v1/connectors/test` and `POST /v1/connectors/browse` accept an inline `connector_type` + `config` and never persist a connector. Inline previews are rate limited — save and reuse a connector for production workflows.

## Databases

All SQL databases accept either discrete connection fields or a single `connection_string` DSN. When `connection_string` is set, it takes precedence over the discrete fields.

### postgres

| Field | Required | Notes |
| --- | --- | --- |
| `host` | yes* | Defaults to `localhost`. |
| `port` | no | Defaults to `5432`. |
| `database` | yes* | |
| `user` | yes* | `username` accepted as an alias. |
| `password` | no | |
| `ssl_mode` | no | Defaults to `prefer`. |
| `connection_string` | yes* | SQLAlchemy DSN, e.g. `postgresql://...`. Use this **or** the discrete fields. |

`*` Provide either `connection_string` **or** the host/database/user fields.

### mysql

| Field | Required | Notes |
| --- | --- | --- |
| `host` | yes* | Defaults to `localhost`. |
| `port` | no | Defaults to `3306`. |
| `database` | yes* | |
| `user` | yes* | `username` accepted as an alias. |
| `password` | no | |
| `connection_string` | yes* | DSN, e.g. `mysql+pymysql://...`. |

### mssql

| Field | Required | Notes |
| --- | --- | --- |
| `host` | yes* | Defaults to `localhost`. |
| `port` | no | Defaults to `1433`. |
| `database` | yes* | |
| `user` | yes* | `username` accepted as an alias. |
| `password` | no | |
| `connection_string` | yes* | SQL Server DSN. |

### sqlite

| Field | Required | Notes |
| --- | --- | --- |
| `path` | yes* | Path to the database file on disk. |
| `connection_string` | yes* | e.g. `sqlite:///data.db` or `sqlite:///:memory:`. |

### clickhouse

| Field | Required | Notes |
| --- | --- | --- |
| `host` | yes* | |
| `port` | no | Defaults to `8123` (or `8443` when `secure` is set). |
| `database` | no | Defaults to `default`. |
| `user` | no | Defaults to `default`. |
| `password` | no | |
| `secure` | no | Use TLS. Inferred from a `clickhouses://`/`https://` scheme. |
| `connection_string` | yes* | e.g. `clickhouse://user:pass@host:8123/db`. |
| `url` | no | HTTP(S) endpoint used to derive host/port when no `connection_string`. |

See the [ClickHouse connector](clickhouse.md) page for a worked example.

### redshift

Redshift speaks the PostgreSQL wire protocol, so it uses the same fields as `postgres`.

| Field | Required | Notes |
| --- | --- | --- |
| `host` | yes* | Cluster endpoint. |
| `port` | no | Defaults to `5439` for clusters; the builder defaults to `5432` unless set. |
| `database` | yes* | |
| `user` | yes* | `username` accepted as an alias. |
| `password` | no | |
| `connection_string` | yes* | `postgresql://...` DSN. |

## Warehouses

### snowflake

| Field | Required | Notes |
| --- | --- | --- |
| `account` | yes* | Snowflake account identifier. |
| `user` | yes* | |
| `password` | yes* | |
| `warehouse` | no | Activated as the session warehouse when set. |
| `database` | no | |
| `schema` | no | |
| `connection_string` | yes* | `snowflake://user:pass@account/db/schema?warehouse=...`. |

`*` Provide `connection_string` **or** account/user/password. See the [Snowflake connector](snowflake.md) page.

### bigquery

| Field | Required | Notes |
| --- | --- | --- |
| `project_id` | no | GCP project. Falls back to the ambient credential's project when omitted. |
| `service_account_json` | no | Service-account JSON (string or object). Uses ambient credentials if absent. |

See the [BigQuery connector](bigquery.md) page.

## Object storage

Object-storage connectors fetch a single object and parse it with the file engine. The format is auto-detected from the object's extension; override it with `file_type` (`csv`, `tsv`, `json`, `parquet`, or `excel`). When the object is JSON, `json_path` selects the records array.

### s3

| Field | Required | Notes |
| --- | --- | --- |
| `bucket` | yes | S3 bucket name. |
| `key` | yes | Object key / path. |
| `file_type` | no | Auto-detected from `key` if omitted. |
| `region` | no | Defaults to `us-east-1`. |
| `aws_access_key_id` | no | `access_key_id` accepted as an alias. |
| `aws_secret_access_key` | no | `secret_access_key` accepted as an alias. |
| `aws_session_token` | no | `session_token` accepted as an alias. |
| `endpoint_url` | no | Override for S3-compatible stores (MinIO, Wasabi, R2). |
| `anonymous` | no | Read a public bucket/object without credentials. |
| `json_path` | no | Dot-path to the records array inside a JSON object. |

When no explicit credentials are given, the connector uses the host's IAM role or environment.

### gcs

| Field | Required | Notes |
| --- | --- | --- |
| `bucket` | yes | GCS bucket name. |
| `blob` | yes | Object path. |
| `file_type` | no | Auto-detected from `blob` if omitted. |
| `credentials` | no | Path to a service-account JSON file, or inline JSON string. |
| `service_account_json` | no | Inline service-account JSON (alias for `credentials`). |
| `project_id` | no | GCP project. |
| `anonymous` | no | Read a public object without credentials. |
| `json_path` | no | Dot-path to the records array. |

### azure

| Field | Required | Notes |
| --- | --- | --- |
| `connection_string` | yes* | Azure Storage connection string. |
| `account_url` | yes* | Storage account URL (with `container` + `blob`). |
| `blob_url` | yes* | Full public blob URL (implies anonymous access). |
| `container` | yes* | Container name (with `account_url` or `connection_string`). |
| `blob` | yes* | Blob path (with `account_url` or `connection_string`). |
| `file_type` | no | Auto-detected from the blob name if omitted. |
| `anonymous` | no | Read a public blob/container without credentials. |
| `json_path` | no | Dot-path to the records array. |

`*` Provide one of: `blob_url`; **or** `account_url` + `container` + `blob`; **or** `connection_string` + `container` + `blob`.

## API

### rest

The REST connector fetches JSON from any HTTP endpoint, navigates to the records array with `data_path`, and optionally paginates within a bounded page budget.

| Field | Required | Notes |
| --- | --- | --- |
| `url` | yes | Target URL. |
| `method` | no | `GET` (default) or `POST`. |
| `headers` | no | Object of request headers. |
| `params` | no | Object of query-string parameters. |
| `body` | no | JSON body for `POST` requests. |
| `timeout` | no | Request timeout in seconds (default `30`). |
| `data_path` | no | Dot-path to the data array, e.g. `results.items`. |
| `pagination` | no | Bounded pagination config (see below). |

When you build the connector through the canonical envelope, an `auth` block translates to headers automatically: `mode` of `token`/`bearer`/`oauth` adds an `Authorization: Bearer` header, `basic` adds Basic auth from `username`/`password`, and `api_key` adds the key under a header (default `X-API-Key`, override with `api_key_header`).

The `pagination` object requires `mode` and a positive `max_pages`:

| Pagination field | Applies to | Notes |
| --- | --- | --- |
| `mode` | both | `page_number` or `cursor_path`. |
| `max_pages` | both | Positive integer; the hard page cap. |
| `page_param` | `page_number` | Query param for the page index (default `page`). |
| `start_page` | `page_number` | First page index (default `1`). |
| `next_path` | both | Dot-path to the next cursor/URL or a more-pages signal. |
| `cursor_param` | `cursor_path` | Query param carrying the cursor token. |
| `next_link_rel` | `page_number` | `rel` name to follow in the `Link` header. |
| `has_more_path` | `page_number` | Dot-path to a boolean more-pages flag. |
| `page_size_param` / `page_size` | both | Optional page-size query param and value. |

See the [REST API connector](rest-api.md) page for examples.

## Files

The file connector parses an uploaded or on-disk file into records. The canonical envelope also accepts the file-specific type names `csv`, `tsv`, `json`, `excel` (and `xlsx`/`xls`), and `parquet`, which all map to the `file` connector with the matching `file_type`.

| Field | Required | Notes |
| --- | --- | --- |
| `file_type` | no | `csv` (default), `tsv`, `json`, `excel`, or `parquet`. |
| `content` | yes* | Raw text (CSV/TSV/JSON) or base64-encoded bytes (Excel/Parquet). |
| `file_path` | yes* | Path on disk — used when `content` is empty. |
| `json_path` | no | Dot-path to the records array in JSON, e.g. `data.items`. |
| `sheet` | no | Excel sheet name or 0-based index (default `0`). |
| `delimiter` | no | Column delimiter override (default auto-detected). |

`*` Provide `content` **or** `file_path`.

## Creating and testing a connector

Create a connector, then test it to move it to `live`.

{% tabs %}
{% tab title="Shell" %}
```bash
curl -X POST "$ALGENTA_API_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "analytics-pg",
        "connector_type": "postgres",
        "config": {
          "host": "db.internal",
          "port": 5432,
          "database": "analytics",
          "user": "reader",
          "password": "'"$ALGENTA_DB_PASSWORD"'"
        }
      }'

curl -X POST "$ALGENTA_API_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```
{% endtab %}

{% tab title="Python" %}
```python
import os

import httpx

base = "https://api.algenta.ai"
headers = {"Authorization": f"Bearer {os.environ['ALGENTA_API_KEY']}"}

created = httpx.post(
    f"{base}/v1/connectors",
    headers=headers,
    json={
        "name": "analytics-pg",
        "connector_type": "postgres",
        "config": {
            "host": "db.internal",
            "port": 5432,
            "database": "analytics",
            "user": "reader",
            "password": os.environ["ALGENTA_DB_PASSWORD"],
        },
    },
).json()

test = httpx.post(
    f"{base}/v1/connectors/{created['id']}/test",
    headers=headers,
).json()
print(test["status"])  # "live" on success
```
{% endtab %}
{% endtabs %}

A successful test returns `success: true` and `status: "live"`; a failure returns `success: false`, `status: "error"`, and a human-readable `message`, plus an `error_type` and a `recoverable` hint. See [Errors](../api/errors.md) for the failure taxonomy.

## See also

- [Connectors overview](overview.md) — concepts and the connect-test-browse flow.
- [Connect data](../guides/connect-data.md) — register a source from a connector.
- [Governed query](../guides/governed-query.md) — query the data behind a connector under contract.
- [Governed data](../concepts/governed-data.md) — what makes a query deterministic and auditable.
- [API reference](../api/reference.md) and [API explorer](../api/explorer.md) — the connector endpoints.
- [Glossary](../help/glossary.md) — canonical terms.
