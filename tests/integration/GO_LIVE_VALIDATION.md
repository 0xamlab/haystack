# Go-Live Validation Matrix

This is the operator runbook for the real connectivity and behavioral SLA gates.

## Commands

Print what is runnable right now and why anything is skipped:

```bash
make go-live-status
```

Print only the Tier 2 credentialed-example slice:

```bash
make go-live-status-tier2
```

Print only the Tier 3 customer-credential slice:

```bash
make go-live-status-tier3
```

Print the same status as JSON for CI or scripting:

```bash
make go-live-status-json
```

Print the frozen Fivetran wave-1 status:

```bash
make go-live-status-fivetran
```

Restrict that status to one connector while onboarding the first real source:

```bash
make go-live-status-fivetran CONNECTOR=github
```

Print the same Fivetran status as JSON:

```bash
make go-live-status-fivetran-json
```

The JSON payload includes a `next_actions` array that turns the current blocked
state into the exact next operator steps, including the hydrate, selector-fill,
pre-baseline, baseline-refresh, and strict-verify commands when they become
valid.

Render the frozen Fivetran wave as a Markdown report:

```bash
make go-live-report-fivetran
```

Render only one connector while filling selectors:

```bash
make go-live-report-fivetran CONNECTOR=github
```

The report includes exact placeholder destination fields, so manifest fill-in can
be driven directly from the current blocked output instead of trial-and-error.

Hydrate placeholder Fivetran manifest connection IDs from the live account when
matches are unambiguous:

```bash
make go-live-hydrate-fivetran-manifest
```

Inspect live Fivetran destinations, connections, and connector-to-destination
match candidates while onboarding the first real source:

```bash
make go-live-inspect-fivetran-account CONNECTOR=github
```

Hydrate only one connector while onboarding the first real source:

```bash
make go-live-hydrate-fivetran-manifest CONNECTOR=github
```

Print the exact manifest block plus remaining placeholder fields for one
connector while filling selectors:

```bash
make go-live-show-fivetran-manifest CONNECTOR=github
```

Fail unless every matrix case is configured and behavior-ready:

```bash
make go-live-status-strict
```

Run the real connectivity plus behavioral SLA gate:

```bash
make test-go-live-connectivity
```

Run only the Tier 2 credentialed-example connectivity cases:

```bash
make test-go-live-connectivity-tier2
```

Run only the Tier 3 customer-credential connectivity cases:

```bash
make test-go-live-connectivity-tier3
```

Run a focused Snowflake connector probe while iterating on account policy or
credential setup:

```bash
make go-live-probe-snowflake
```

This command uses the same `keys.txt` / `DE_TEST_*` resolution path as the full
go-live matrix, but it only probes the Snowflake connector `/test` surface and
returns the structured outcome directly.

Run the same focused probe for ClickHouse:

```bash
make go-live-probe-clickhouse
```

Run the same focused probe for Redis:

```bash
make go-live-probe-redis
```

Run the same focused probe for Elasticsearch / Elastic Cloud:

```bash
make go-live-probe-elasticsearch
```

Run the same focused probe for Neo4j / Aura:

```bash
make go-live-probe-neo4j
```

Run the full curated real-path suite:

```bash
make test-go-live-full
```

This suite intentionally runs the local connectivity gate in `--skip-external-validation`
mode first, so the public external SLA cases stay owned by `make test-go-live-connectivity`
instead of being rerun inside the curated live suite.

It also includes the repo-root JavaScript workspace operator gate via:

```bash
make js-check
```

That means `make test-go-live-full` now proves the shipped Python runtime,
TypeScript package/build surface, CLI/MCP live path, LLM rollout artifacts, and
the repo-root JS bootstrap path together instead of leaving the JS workspace as
a separate manual check.

Run the whole proof serially from one command:

```bash
make go-live-verify
```

This writes the machine-readable verifier summary to:

```bash
build/go_live_verify_summary.json
```

The canonical non-strict unfiltered verifier run also keeps a synced Markdown artifact at:

```bash
build/go_live_verify_report.md
```

The fixture env example at `tests/integration/go_live_validation.env.example`
also includes the optional public-case gate `DE_ENABLE_SLOW_PUBLIC_REST_CASES`
alongside the credentialed connector envs from the current blocker set.

The JSON includes matrix counts, requirement failures, completed steps, failed
steps, per-step durations for `connectivity`, `full_real`, and optional
`pytest`, plus the selected filters, enabled verifier stages, the exact
planned step commands for that run, a `static_operational_gaps` list from the
current matrix status, an `operational_gaps` list for the remaining non-repo
credential, opt-in, or network-policy blockers after merging live results, a
`live_connectivity_skips` list for skips observed in the latest real
connectivity run, a `gap_source_summary` object with the precomputed static /
live / merged counts, tier/source/connector breakdowns, and live-only case
ids, a `gap_action_summary` object with remediation-action coverage and
unmapped-case counts plus per-action env and connector coverage, a
`gap_connector_summary` object for connector -> case/action/env routing, and a
`gap_env_summary` object for env -> case/action/connector/tier routing, and a
`gap_env_resolution_summary` object for env -> keys.txt alias/manual-only
resolution routing, and a `gap_env_template_summary` object for env ->
template-coverage routing across `.env.example` and
`tests/integration/go_live_validation.env.example`, and a
`next_actions` array with exact follow-up commands for the current blocked
state.

Each merged `operational_gaps` entry also carries per-case provenance via
`source`, `sources`, `static_reason`, and `live_reason`, so tooling can tell
whether a blocker came from the static matrix, the live connectivity run, or
both.

Render that latest summary as Markdown without rerunning the suite:

```bash
make go-live-report
```

That command renders the current JSON summary without rerunning the suite; the
canonical verifier run already keeps `build/go_live_verify_report.md` in sync,
including the current static matrix gaps, live connectivity skips, merged
operational gap list, and next actions.

Run the Tier 2 credentialed-example proof only:

```bash
make go-live-verify-tier2
```

Run the Tier 3 customer-credential proof only:

```bash
make go-live-verify-tier3
```

Run the strict 100% gate. This requires:

- `DE_ENABLE_SLOW_PUBLIC_REST_CASES=1` for the extra unauthenticated dlt GitHub issues case
- all tier 2 credentials
- all tier 3 credentials
- Snowflake and BigQuery behavior fixture selectors
- customer S3/GCS/Azure credentials intentionally replace the corresponding public object-storage defaults in the strict gate

```bash
make go-live-verify-all
```

Refresh the frozen Fivetran inventory and selection locks from the official docs catalog:

```bash
make go-live-refresh-fivetran-inventory
```

Refresh the frozen Fivetran warehouse baselines after a fully stable sync:

```bash
make go-live-refresh-fivetran-baseline
```

Refresh the baseline for one connector only:

```bash
make go-live-refresh-fivetran-baseline CONNECTOR=github
```

Run the strict Fivetran wave-1 verifier:

```bash
make go-live-verify-fivetran
```

Run the same verifier for one connector only:

```bash
make go-live-verify-fivetran CONNECTOR=github
```

Run the strict pre-baseline dry run for one connector. This allows only
`blocked = missing baseline` and fails on any other blocked or failed state:

```bash
make go-live-verify-fivetran-prebaseline CONNECTOR=github
```

## Tier contract

- `public_no_auth`
  - runs by default
  - must satisfy the behavioral SLA gate
- `credentialed_example`
  - requires fixture credentials
  - must satisfy the behavioral SLA gate when configured
- `customer_credentials_required`
  - customer-secret live validation only
  - object storage cases run as configured register/query cases
  - warehouse cases stay `connector_test_only` unless explicit fixture selectors are provided

## Tier 2 fixture envs

A copyable env template is in:

```bash
tests/integration/go_live_validation.env.example
```

- `DE_TEST_FRED_API_KEY`
- `DE_TEST_GITHUB_TOKEN`

The operator surface also accepts repo-root `keys.txt` aliases for these Tier 2
secrets:

- `FRED_API_KEY`
- `GITHUB_TOKEN` or `GH_TOKEN`

Recommended first proof once those two secrets are present:

1. `make go-live-status-tier2`
2. `make test-go-live-connectivity-tier2`
3. `make go-live-verify-tier2`

## Tier 3 customer envs

### Custom object storage

- S3:
  - `DE_TEST_S3_BUCKET`
  - `DE_TEST_S3_KEY`
  - `DE_TEST_S3_ACCESS_KEY_ID`
  - `DE_TEST_S3_SECRET_ACCESS_KEY`
  - optional: `DE_TEST_S3_ENDPOINT_URL`, `DE_TEST_S3_REGION`, `DE_TEST_S3_FILE_TYPE`
- GCS:
  - `DE_TEST_GCS_BUCKET`
  - `DE_TEST_GCS_BLOB`
  - `DE_TEST_GCS_CREDENTIALS`
  - `DE_TEST_GCS_PROJECT_ID`
  - optional: `DE_TEST_GCS_FILE_TYPE`
- Azure Blob:
  - either `DE_TEST_AZURE_BLOB_URL`
  - or:
    - `DE_TEST_AZURE_CONNECTION_STRING` or `DE_TEST_AZURE_ACCOUNT_URL`
    - `DE_TEST_AZURE_CONTAINER`
    - `DE_TEST_AZURE_BLOB`
  - optional: `DE_TEST_AZURE_FILE_TYPE`

### Warehouse behavior proof

Redis base connector test envs:

- `DE_TEST_REDIS_URL`

Redis intentionally stays `connector_test_only` in the go-live matrix. The
live proof covers connector `/test`, and Redis browsing/fetch requires explicit
key selection through the connector API rather than the database-style
register/query behavior path.

Neo4j base connector test envs:

- `DE_TEST_NEO4J_URI`
- `DE_TEST_NEO4J_USERNAME`
- `DE_TEST_NEO4J_PASSWORD`
- optional default:
  - `DE_TEST_NEO4J_DATABASE` defaults to `neo4j`

- Elasticsearch / Elastic Cloud
  - `DE_TEST_ELASTICSEARCH_URL` must be the base cluster URL, for example `https://cluster.example.com:443`
  - `DE_TEST_ELASTICSEARCH_API_KEY` must be the base64 API key used for `Authorization: ApiKey <value>`
  - `DE_TEST_ELASTICSEARCH_INDEX` and `DE_TEST_ELASTICSEARCH_QUERY` are optional helper fields for explicit browse/fetch iteration outside the strict `/test` gate

Neo4j intentionally stays `connector_test_only` in the go-live matrix. The
live proof covers connector `/test`, and graph reads remain explicit Cypher
through the connector layer instead of the SQL-style register/query path.

ClickHouse base connector test envs:

- `DE_TEST_CLICKHOUSE_URL`
- `DE_TEST_CLICKHOUSE_USER`
- `DE_TEST_CLICKHOUSE_PASSWORD`
- optional default:
  - `DE_TEST_CLICKHOUSE_DATABASE` defaults to `default`

ClickHouse behavior validation requires one of:

- `DE_TEST_CLICKHOUSE_QUERY`
- `DE_TEST_CLICKHOUSE_TABLE`

Snowflake base connector test envs:

- `DE_TEST_SNOWFLAKE_ACCOUNT`
- `DE_TEST_SNOWFLAKE_USER`
- `DE_TEST_SNOWFLAKE_PASSWORD`
- `DE_TEST_SNOWFLAKE_WAREHOUSE`
- optional defaults:
  - `DE_TEST_SNOWFLAKE_DATABASE` defaults to `SNOWFLAKE_SAMPLE_DATA`
  - `DE_TEST_SNOWFLAKE_SCHEMA` defaults to `TPCH_SF1`

Snowflake behavior validation requires one of:

- `DE_TEST_SNOWFLAKE_QUERY`
- `DE_TEST_SNOWFLAKE_TABLE`

BigQuery base connector test envs:

- `DE_TEST_BIGQUERY_PROJECT_ID`
- `DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON`

BigQuery behavior validation requires one of:

- `DE_TEST_BIGQUERY_QUERY`
- `DE_TEST_BIGQUERY_DATASET` and `DE_TEST_BIGQUERY_TABLE`

Without those selectors, Snowflake and BigQuery intentionally remain `connector_test_only`.

The operator surface also accepts repo-root `keys.txt` aliases for the Tier 3
and warehouse secrets. Examples:

- Neo4j: `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
- ClickHouse: `CLICKHOUSE_URL`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DATABASE`, `CLICKHOUSE_QUERY`, `CLICKHOUSE_TABLE`
- Snowflake: `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_PASSWORD`, `SNOWFLAKE_PAT`, `SNOWFLAKE_ACCESS_TOKEN`, `SNOWFLAKE_PROGRAMMATIC_ACCESS_TOKEN`, `SNOWFLAKE_WAREHOUSE`
- BigQuery: `BIGQUERY_PROJECT_ID`, `BIGQUERY_SERVICE_ACCOUNT_JSON`, or `GOOGLE_APPLICATION_CREDENTIALS`
- GCS: `GCS_BUCKET`, `GCS_BLOB`, `GCS_CREDENTIALS`, or `GOOGLE_APPLICATION_CREDENTIALS`
- S3: `S3_BUCKET`, `S3_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- Azure: `AZURE_CONNECTION_STRING`, `AZURE_ACCOUNT_URL`, `AZURE_CONTAINER`, `AZURE_BLOB`, `AZURE_BLOB_URL`

Recommended first proof once Tier 3 customer secrets are present:

1. `make go-live-status-tier3`
2. `make test-go-live-connectivity-tier3`
3. `make go-live-verify-tier3`

## Fivetran validation-only wave

This is additive to the existing three-tier matrix. It does not change Algenta's
runtime connector layer.

Wave 1 is a frozen top-20 Fivetran connector set mirrored into both Snowflake and
BigQuery. Verification is driven entirely by:

- `tests/integration/fivetran_inventory.lock.json`
- `tests/integration/fivetran_top20.lock.json`
- `tests/integration/fivetran_baseline.lock.json`
- `tests/integration/fivetran_wave1_manifest.example.json` as the operator template

Required Fivetran envs:

- `DE_TEST_FIVETRAN_API_KEY`
- `DE_TEST_FIVETRAN_API_SECRET`
- `DE_TEST_FIVETRAN_MANIFEST_PATH`

The operator surface also accepts the repo-root `keys.txt` aliases
`FIVETRAN_SYSTEM_KEY` and `FIVETRAN_SYSTEM_KEY_SECRET` as fallbacks for the two
API envs. `make go-live-status-fivetran-json` will report which credential
source it actually used. `make go-live-hydrate-fivetran-manifest` uses the same
credential resolution path and only fills `connection_id` values when a selected
connector has exactly one live match for the destination. It does not invent
warehouse `table`, `query`, or `expected_core_tables` selectors; it reports the
remaining placeholder fields explicitly so operators can fill those from the
first completed sync.

The manifest must provide, for every selected connector:

- one Snowflake destination section
- one BigQuery destination section
- destination `connection_id`
- one `query` or one `table`
- `expected_core_tables`
- `max_data_lag_minutes`
- optional `identity_columns`
- optional `minimum_row_count`
- optional `minimum_expected_ratio` (defaults to `0.8`)

The strict verifier fails on any `fail` or `blocked` destination. A destination is
only `pass` if all of these are true:

- Fivetran preflight succeeds
- data freshness is within `max_data_lag_minutes`
- destination sanity passes
- row count stays above the frozen baseline ratio
- the existing warehouse behavioral SLA path passes

Baseline capture safeguards:

- baseline refresh uses two consecutive destination reads separated by 5 minutes
- schema fingerprint must stay identical across both reads
- row-count delta must stay within 1%
- any unstable destination blocks the refresh and leaves the existing baseline intact

First real connector order of operations:

1. `make go-live-hydrate-fivetran-manifest`
2. fill the remaining `table` / `query` and `expected_core_tables` selectors for that connector
3. `make go-live-verify-fivetran-prebaseline CONNECTOR=<slug>`
4. fix every surfaced issue until the only remaining blocker is missing baseline
5. `make go-live-refresh-fivetran-baseline CONNECTOR=<slug>`
6. `make go-live-verify-fivetran CONNECTOR=<slug>`

## Serial validation rule

Do not overlap the live suites.

Run them in this order:

1. `make go-live-status`
2. `make test-go-live-connectivity`
3. `make test-go-live-full`
4. `./.venv/bin/python -m pytest tests -q`

If you are iterating only on the repo-root JavaScript operator path before the
full curated suite, run:

1. `make js-check`
2. `make test-go-live-full`

Or use:

```bash
make go-live-verify
```

For literal all-tier proof, use:

```bash
make go-live-verify-all
```
