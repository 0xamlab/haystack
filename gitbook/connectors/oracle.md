---
icon: database
description: Connect Oracle Database or Autonomous Database with Algenta's bundled Thin-mode driver, verify credentials once, browse schemas, and onboard a table or query.
---

# Connect Oracle Database

Algenta connects to Oracle Database and Oracle Autonomous Database with the bundled `python-oracledb` Thin-mode driver. You do not install Oracle Instant Client, manage a separate sidecar, or add a Python package to the Algenta service. Algenta owns the driver, bounded connection pool, credential verification, schema browse, and Arrow-batch fetch path.

Use either:

* **TLS without a wallet** with an Easy Connect DSN.
* **mTLS with an Autonomous Database wallet** using a TNS alias, `tnsnames.ora`, and `ewallet.pem`.

{% hint style="warning" %}
OCI control-plane credentials are not Oracle Database credentials. Do not place an OCI user OCID, API signing key, fingerprint, tenancy OCID, or OCI auth token in connector config. The connector needs a database user and database password, plus its DSN and optional wallet files.
{% endhint %}

## No separate Oracle setup in Algenta

The API image pins `oracledb==4.0.1`, which supports Python 3.9 through 3.14 and defaults to Thin mode. Thin mode connects directly to Oracle Database and does not require Oracle Client libraries. Your only external prerequisite is a reachable Oracle database and valid database credentials.

For Autonomous Database wallet details, see Oracle's [python-oracledb Thin-mode mTLS guide](https://python-oracledb.readthedocs.io/en/stable/user_guide/connection_handling.html#connecting-with-python-oracledb-thin-mode-using-mtls).

## Config fields

| Field | Required | Notes |
| --- | --- | --- |
| `user` | yes | Oracle Database user, for example a dedicated read-only application user. `username` is accepted as an alias. |
| `password` | yes | Database-user password. This is not an OCI auth token or wallet password. |
| `dsn` | yes* | Easy Connect string, full connect descriptor, or TNS alias. `connect_descriptor` is accepted as an alias. |
| `host` | yes for a TNS alias | Required separately when `dsn` is an alias so the egress policy can validate the destination. It is inferred from Easy Connect strings and full descriptors. |
| `port` | no | Defaults to `1521`, or `1522` when `wallet_location` is set. |
| `service_name` | yes* | Used with `host` to build a DSN when `dsn` is omitted. `database` is accepted as an alias. |
| `config_dir` | wallet connections | Directory containing `tnsnames.ora`. `tns_admin` is accepted as an alias. |
| `wallet_location` | mTLS only | Directory containing `ewallet.pem` for Thin mode. |
| `wallet_password` | with `wallet_location` | Password used to decrypt the wallet. This is distinct from the database password. |
| `schema` | no | Limits browse results to one Oracle owner/schema. |
| `pool_min` | no | Idle sessions kept per connector config; defaults to `0`. |
| `pool_max` | no | Maximum pooled sessions; defaults to `4`. |
| `pool_wait_timeout_ms` | no | Bounded acquire wait; defaults to `2000`. |
| `fetch_batch_size` | no | Arrow fetch batch size; defaults to `10000`. |
| `limit` | no | Positive maximum rows fetched from the selected query. |

`*` Provide `dsn`, or provide both `host` and `service_name` so Algenta can build one.

## Connect and onboard in one request

`POST /v1/data/connect` is the shortest production path. It stores the connector, performs one credential probe while its status is `untested`, persists the resulting `live` or `error` state, and onboards the selected table or query.

```bash title="Set local environment variables"
export ALGENTA_API_URL="https://api.algenta.ai"
export ORACLE_DB_USER="APP_READER"
export ORACLE_DB_PASSWORD="${ORACLE_DB_PASSWORD:?set ORACLE_DB_PASSWORD}"
export ORACLE_DSN="db.example.oraclecloud.com:1521/analytics_low"
```

```bash title="Connect an Oracle table"
curl -sS -X POST "$ALGENTA_API_URL/v1/data/connect" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"connection_type\": \"database\",
    \"provider\": \"oracle\",
    \"connection_name\": \"Oracle analytics\",
    \"dataset_name\": \"oracle_orders\",
    \"connection_config\": {
      \"user\": \"$ORACLE_DB_USER\",
      \"password\": \"$ORACLE_DB_PASSWORD\",
      \"dsn\": \"$ORACLE_DSN\"
    },
    \"selection\": {\"table\": \"REPORTING.ORDERS\"},
    \"visibility\": \"private\"
  }"
```

**Expected result:** `status` is `ready`, `provider` is `oracle`, and the response includes a `connection_id`, `dataset_id`, and schema summary. A failed first probe returns `status: "failed"`, the saved `connection_id`, and a classified message without returning credentials.

{% hint style="info" %}
Selection resume, dataset refresh, and query execution do not repeat the credential-only probe. A persisted `live` or `error` result is reused at `0 ms`. Reads still perform the database operation they were asked to perform; external Oracle network latency is not reported as an Algenta warm-cache latency.
{% endhint %}

## Autonomous Database with an mTLS wallet

Extract the wallet into a directory readable by the Algenta API process. Thin mode uses `tnsnames.ora` and `ewallet.pem`; Algenta does not require Instant Client or `sqlnet.ora`.

```bash title="Set wallet variables"
export ORACLE_WALLET_DIR="/run/secrets/oracle-wallet"
export ORACLE_WALLET_PASSWORD="${ORACLE_WALLET_PASSWORD:?set ORACLE_WALLET_PASSWORD}"
export ORACLE_DSN="analytics_low"
export ORACLE_HOST="adb.example.oraclecloud.com"
```

Use the wallet fields in `connection_config`:

```json title="Oracle Autonomous Database connection_config"
{
  "user": "APP_READER",
  "password": "$ORACLE_DB_PASSWORD",
  "dsn": "analytics_low",
  "host": "adb.example.oraclecloud.com",
  "port": 1522,
  "config_dir": "/run/secrets/oracle-wallet",
  "wallet_location": "/run/secrets/oracle-wallet",
  "wallet_password": "$ORACLE_WALLET_PASSWORD",
  "schema": "REPORTING"
}
```

The literal `$...` values above are placeholders. SDK and HTTP clients must resolve them from their secret store before sending JSON; Algenta never expands environment-variable names inside a JSON request.

## Explicit connector lifecycle

Use the connector endpoints when you want to save, inspect, or browse the connection before onboarding data.

```bash title="Create, test, and browse an Oracle connector"
curl -sS -X POST "$ALGENTA_API_URL/v1/connectors" \
  -H "Authorization: Bearer $ALGENTA_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"name\": \"Oracle analytics\",
    \"connector_type\": \"oracle\",
    \"config\": {
      \"user\": \"$ORACLE_DB_USER\",
      \"password\": \"$ORACLE_DB_PASSWORD\",
      \"dsn\": \"$ORACLE_DSN\"
    }
  }"

export CONNECTOR_ID="${CONNECTOR_ID:?set CONNECTOR_ID from the create response}"

curl -sS -X POST "$ALGENTA_API_URL/v1/connectors/$CONNECTOR_ID/test" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"

curl -sS "$ALGENTA_API_URL/v1/connectors/$CONNECTOR_ID/browse" \
  -H "Authorization: Bearer $ALGENTA_API_KEY"
```

The explicit create endpoint returns `untested`; `/test` runs `SELECT 1 FROM DUAL` and persists `live` or `error`. Calling `/test` is always an explicit operator-requested probe. Browsing lists at most 200 tables and views and requires a `live` connector.

## Query and pool behavior

Algenta accepts only `SELECT` and `WITH` query roots for Oracle datasets. When `limit` is set, it wraps the query with a bound `ROWNUM` limit. Results are fetched in Arrow-compatible batches and the bounded pool is reused across requests with the same connector config. If every configured pool slot is unavailable, the operation fails explicitly; it never opens a hidden unpooled fallback connection.

The pool removes cold-start setup from repeated reads, but it cannot remove the network round trip to Oracle. Governed queries run against Algenta's registered dataset path; use dataset refresh when you intentionally need a new Oracle snapshot.

## Troubleshooting

{% hint style="warning" %}
**`Oracle Database connector configuration is invalid.`** Confirm `user`, `password`, and `dsn`. For a TNS alias, also provide `host` plus `config_dir`. If `wallet_location` is set, `wallet_password` is required.
{% endhint %}

{% hint style="warning" %}
**`DPY-6005` or a network error.** Confirm the host, port, service name, database access-control list, and VCN/public endpoint. For a private deployment, add only the exact Oracle destination to `ALGENTA_EGRESS_ALLOWLIST`.
{% endhint %}

{% hint style="warning" %}
**`ORA-01017`.** The database username or database password was rejected. An OCI auth token cannot replace the database password.
{% endhint %}

{% hint style="warning" %}
**Wallet or TNS alias cannot be resolved.** Confirm that `config_dir` contains `tnsnames.ora`, `wallet_location` contains `ewallet.pem`, the API process can read both files, and `dsn` exactly matches an alias in `tnsnames.ora`.
{% endhint %}

## Next

{% content-ref url="databases.md" %}
[databases.md](databases.md)
{% endcontent-ref %}

{% content-ref url="reference.md" %}
[reference.md](reference.md)
{% endcontent-ref %}

{% content-ref url="../guides/governed-query.md" %}
[governed-query.md](../guides/governed-query.md)
{% endcontent-ref %}
