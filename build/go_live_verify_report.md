# Go-live verifier report

- Generated at: `2026-05-30T00:22:07Z`
- Python: `python3`
- Summary path: `build/go_live_verify_summary.json`

## Matrix

- Configured: `8/19`
- Behavior-ready: `8/19`
- `public_no_auth`: `7/8` configured, `7/8` behavior-ready
- `credentialed_example`: `0/2` configured, `0/2` behavior-ready
- `customer_credentials_required`: `1/9` configured, `1/9` behavior-ready

## Execution

- Completed steps: `connectivity`
- Failed steps: `full_real`
- Planned steps: `connectivity, full_real, pytest`

## Filters

- Tiers: `none`
- Connectors: `none`

## Options

- include_full_real: `True`
- include_pytest: `True`
- require_all_configured: `False`
- require_all_behavior_ready: `False`
- strict: `False`

## Step details

### `connectivity`

- Command: `python3 -u /Users/angel/Developer/decision-engine/tests/integration/test_go_live_connectivity_real.py --parallel-tasks 4`
- Return code: `0`
- Duration: `27.63s`

### `full_real`

- Command: `python3 -u /Users/angel/Developer/decision-engine/tests/integration/test_go_live_full_real.py --parallel-tasks 4 --mojo-workers 4 --mojo-timeout 30`
- Return code: `1`
- Duration: `797.10s`

### `pytest`

- Command: `python3 -m pytest tests -q`
- Result: `not run`

## Requirement failures

- None

## Gap sources

- Static matrix gaps: `11`
- Live connectivity skips: `12`
- Merged operational gaps: `12`
- Static gaps by tier: `credentialed_example 2, customer_credentials_required 8, public_no_auth 1`
- Static gaps by connector: `azure_blob 1, bigquery 1, clickhouse 1, elasticsearch 1, gcs 1, neo4j 1, redis 1, rest_api 3, s3 1`
- Live skips by tier: `credentialed_example 2, customer_credentials_required 9, public_no_auth 1`
- Live skips by connector: `azure_blob 1, bigquery 1, clickhouse 1, elasticsearch 1, gcs 1, neo4j 1, redis 1, rest_api 3, s3 1, snowflake 1`
- Merged gaps by tier: `credentialed_example 2, customer_credentials_required 9, public_no_auth 1`
- Merged gaps by connector: `azure_blob 1, bigquery 1, clickhouse 1, elasticsearch 1, gcs 1, neo4j 1, redis 1, rest_api 3, s3 1, snowflake 1`
- Merged gaps by source: `live_connectivity 1, static_matrix+live_connectivity 11`
- Live-only blockers beyond the static matrix: `snowflake_customer_connector_test`

## Live connectivity skips

- These skips came from the latest real connectivity run and are merged into `operational_gaps`.
- `credentialed_example` / `dlt_github_issues_token` (`rest_api`, `not_configured`): required env not provided: DE_TEST_GITHUB_TOKEN
- `credentialed_example` / `fivetran_fred_gnpca` (`rest_api`, `not_configured`): required env not provided: DE_TEST_FRED_API_KEY
- `customer_credentials_required` / `bigquery_customer_connector_test` (`bigquery`, `not_configured`): required env not provided: DE_TEST_BIGQUERY_PROJECT_ID, DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON
- `customer_credentials_required` / `clickhouse_customer_connector_test` (`clickhouse`, `not_configured`): required env not provided: DE_TEST_CLICKHOUSE_URL, DE_TEST_CLICKHOUSE_USER, DE_TEST_CLICKHOUSE_PASSWORD
- `customer_credentials_required` / `customer_azure_blob_source_registration` (`azure_blob`, `not_configured`): required env not provided: DE_TEST_AZURE_BLOB_URL or (DE_TEST_AZURE_CONNECTION_STRING or DE_TEST_AZURE_ACCOUNT_URL) + DE_TEST_AZURE_CONTAINER + DE_TEST_AZURE_BLOB
- `customer_credentials_required` / `customer_gcs_source_registration` (`gcs`, `not_configured`): required env not provided: DE_TEST_GCS_BUCKET, DE_TEST_GCS_BLOB
- `customer_credentials_required` / `customer_s3_source_registration` (`s3`, `not_configured`): required env not provided: DE_TEST_S3_BUCKET, DE_TEST_S3_KEY
- `customer_credentials_required` / `elasticsearch_customer_connector_test` (`elasticsearch`, `not_configured`): required env not provided: DE_TEST_ELASTICSEARCH_URL, DE_TEST_ELASTICSEARCH_API_KEY
- `customer_credentials_required` / `neo4j_customer_connector_test` (`neo4j`, `not_configured`): required env not provided: DE_TEST_NEO4J_URI, DE_TEST_NEO4J_USERNAME, DE_TEST_NEO4J_PASSWORD
- `customer_credentials_required` / `redis_customer_connector_test` (`redis`, `not_configured`): required env not provided: DE_TEST_REDIS_URL
- `customer_credentials_required` / `snowflake_customer_connector_test` (`snowflake`, `not_behavior_ready`): Snowflake live validation blocked by account network policy; skipping external customer-credential case.
- `public_no_auth` / `dlt_github_issues` (`rest_api`, `not_configured`): unauthenticated dlt GitHub issues case disabled by default; set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1

## Operational gaps

- `credentialed_example` / `dlt_github_issues_token` (`rest_api`, `not_configured`) [source: static_matrix+live_connectivity] [actions: set_credentialed_example_envs]: required env not provided: DE_TEST_GITHUB_TOKEN
- `credentialed_example` / `fivetran_fred_gnpca` (`rest_api`, `not_configured`) [source: static_matrix+live_connectivity] [actions: set_credentialed_example_envs]: required env not provided: DE_TEST_FRED_API_KEY
- `customer_credentials_required` / `bigquery_customer_connector_test` (`bigquery`, `not_configured`) [source: static_matrix+live_connectivity] [actions: set_customer_connector_envs]: required env not provided: DE_TEST_BIGQUERY_PROJECT_ID, DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON
- `customer_credentials_required` / `clickhouse_customer_connector_test` (`clickhouse`, `not_configured`) [source: static_matrix+live_connectivity] [actions: set_customer_connector_envs]: required env not provided: DE_TEST_CLICKHOUSE_URL, DE_TEST_CLICKHOUSE_USER, DE_TEST_CLICKHOUSE_PASSWORD
- `customer_credentials_required` / `customer_azure_blob_source_registration` (`azure_blob`, `not_configured`) [source: static_matrix+live_connectivity] [actions: set_customer_connector_envs]: required env not provided: DE_TEST_AZURE_BLOB_URL or (DE_TEST_AZURE_CONNECTION_STRING or DE_TEST_AZURE_ACCOUNT_URL) + DE_TEST_AZURE_CONTAINER + DE_TEST_AZURE_BLOB
- `customer_credentials_required` / `customer_gcs_source_registration` (`gcs`, `not_configured`) [source: static_matrix+live_connectivity] [actions: set_customer_connector_envs]: required env not provided: DE_TEST_GCS_BUCKET, DE_TEST_GCS_BLOB
- `customer_credentials_required` / `customer_s3_source_registration` (`s3`, `not_configured`) [source: static_matrix+live_connectivity] [actions: set_customer_connector_envs]: required env not provided: DE_TEST_S3_BUCKET, DE_TEST_S3_KEY
- `customer_credentials_required` / `elasticsearch_customer_connector_test` (`elasticsearch`, `not_configured`) [source: static_matrix+live_connectivity] [actions: set_customer_connector_envs]: required env not provided: DE_TEST_ELASTICSEARCH_URL, DE_TEST_ELASTICSEARCH_API_KEY
- `customer_credentials_required` / `neo4j_customer_connector_test` (`neo4j`, `not_configured`) [source: static_matrix+live_connectivity] [actions: set_customer_connector_envs]: required env not provided: DE_TEST_NEO4J_URI, DE_TEST_NEO4J_USERNAME, DE_TEST_NEO4J_PASSWORD
- `customer_credentials_required` / `redis_customer_connector_test` (`redis`, `not_configured`) [source: static_matrix+live_connectivity] [actions: set_customer_connector_envs]: required env not provided: DE_TEST_REDIS_URL
- `customer_credentials_required` / `snowflake_customer_connector_test` (`snowflake`, `not_behavior_ready`) [source: live_connectivity] [actions: resolve_network_policy_blockers]: Snowflake live validation blocked by account network policy; skipping external customer-credential case.
- `public_no_auth` / `dlt_github_issues` (`rest_api`, `not_configured`) [source: static_matrix+live_connectivity] [actions: enable_opt_in_public_cases]: unauthenticated dlt GitHub issues case disabled by default; set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1

## Next actions

- `enable_opt_in_public_cases`: Enable the optional public REST cases before rerunning the public connectivity proof.
  - command: `DE_ENABLE_SLOW_PUBLIC_REST_CASES=1 make test-go-live-connectivity`
- `set_credentialed_example_envs`: Set the missing Tier 2 credentialed-example environment variables and rerun the focused Tier 2 connectivity slice.
  - command: `make go-live-status-tier2 && make test-go-live-connectivity-tier2`
- `set_customer_connector_envs`: Set the missing Tier 3 customer-credential variables and rerun the focused customer-connector connectivity slice.
  - command: `make go-live-status-tier3 && make test-go-live-connectivity-tier3`
- `resolve_network_policy_blockers`: Resolve the remaining network-policy-gated customer connector probes before rerunning the Tier 3 slice.
  - command: `make go-live-probe-snowflake`
- `rerun_strict_go_live_gate`: After the listed operational gaps are cleared, rerun the strict matrix and the full go-live verifier.
  - command: `make go-live-status-strict && make go-live-verify-all`

## Action routing

- Direct remediation coverage: `12/12` cases
- Action case counts: `enable_opt_in_public_cases 1, resolve_network_policy_blockers 1, set_credentialed_example_envs 2, set_customer_connector_envs 8`
- Action env counts: `enable_opt_in_public_cases 1, set_credentialed_example_envs 2, set_customer_connector_envs 20`
- Action connector counts: `enable_opt_in_public_cases 1, resolve_network_policy_blockers 1, set_credentialed_example_envs 1, set_customer_connector_envs 8`
- Terminal actions: `rerun_strict_go_live_gate`
- Unmapped cases: `none`
- `enable_opt_in_public_cases` cases: `dlt_github_issues`
- `resolve_network_policy_blockers` cases: `snowflake_customer_connector_test`
- `set_credentialed_example_envs` cases: `dlt_github_issues_token, fivetran_fred_gnpca`
- `set_customer_connector_envs` cases: `bigquery_customer_connector_test, clickhouse_customer_connector_test, customer_azure_blob_source_registration, customer_gcs_source_registration, customer_s3_source_registration, elasticsearch_customer_connector_test, neo4j_customer_connector_test, redis_customer_connector_test`
- `enable_opt_in_public_cases` envs: `DE_ENABLE_SLOW_PUBLIC_REST_CASES`
- `set_credentialed_example_envs` envs: `DE_TEST_FRED_API_KEY, DE_TEST_GITHUB_TOKEN`
- `set_customer_connector_envs` envs: `DE_TEST_AZURE_ACCOUNT_URL, DE_TEST_AZURE_BLOB, DE_TEST_AZURE_BLOB_URL, DE_TEST_AZURE_CONNECTION_STRING, DE_TEST_AZURE_CONTAINER, DE_TEST_BIGQUERY_PROJECT_ID, DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON, DE_TEST_CLICKHOUSE_PASSWORD, DE_TEST_CLICKHOUSE_URL, DE_TEST_CLICKHOUSE_USER, DE_TEST_ELASTICSEARCH_API_KEY, DE_TEST_ELASTICSEARCH_URL, DE_TEST_GCS_BLOB, DE_TEST_GCS_BUCKET, DE_TEST_NEO4J_PASSWORD, DE_TEST_NEO4J_URI, DE_TEST_NEO4J_USERNAME, DE_TEST_REDIS_URL, DE_TEST_S3_BUCKET, DE_TEST_S3_KEY`
- `enable_opt_in_public_cases` connectors: `rest_api`
- `resolve_network_policy_blockers` connectors: `snowflake`
- `set_credentialed_example_envs` connectors: `rest_api`
- `set_customer_connector_envs` connectors: `azure_blob, bigquery, clickhouse, elasticsearch, gcs, neo4j, redis, s3`

## Connector routing

- Connector case counts: `azure_blob 1, bigquery 1, clickhouse 1, elasticsearch 1, gcs 1, neo4j 1, redis 1, rest_api 3, s3 1, snowflake 1`
- Connector env counts: `azure_blob 5, bigquery 2, clickhouse 3, elasticsearch 2, gcs 2, neo4j 3, redis 1, rest_api 3, s3 2`
- `azure_blob` cases: `customer_azure_blob_source_registration`
- `bigquery` cases: `bigquery_customer_connector_test`
- `clickhouse` cases: `clickhouse_customer_connector_test`
- `elasticsearch` cases: `elasticsearch_customer_connector_test`
- `gcs` cases: `customer_gcs_source_registration`
- `neo4j` cases: `neo4j_customer_connector_test`
- `redis` cases: `redis_customer_connector_test`
- `rest_api` cases: `dlt_github_issues, dlt_github_issues_token, fivetran_fred_gnpca`
- `s3` cases: `customer_s3_source_registration`
- `snowflake` cases: `snowflake_customer_connector_test`
- `azure_blob` actions: `set_customer_connector_envs`
- `bigquery` actions: `set_customer_connector_envs`
- `clickhouse` actions: `set_customer_connector_envs`
- `elasticsearch` actions: `set_customer_connector_envs`
- `gcs` actions: `set_customer_connector_envs`
- `neo4j` actions: `set_customer_connector_envs`
- `redis` actions: `set_customer_connector_envs`
- `rest_api` actions: `enable_opt_in_public_cases, set_credentialed_example_envs`
- `s3` actions: `set_customer_connector_envs`
- `snowflake` actions: `resolve_network_policy_blockers`
- `azure_blob` envs: `DE_TEST_AZURE_ACCOUNT_URL, DE_TEST_AZURE_BLOB, DE_TEST_AZURE_BLOB_URL, DE_TEST_AZURE_CONNECTION_STRING, DE_TEST_AZURE_CONTAINER`
- `bigquery` envs: `DE_TEST_BIGQUERY_PROJECT_ID, DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON`
- `clickhouse` envs: `DE_TEST_CLICKHOUSE_PASSWORD, DE_TEST_CLICKHOUSE_URL, DE_TEST_CLICKHOUSE_USER`
- `elasticsearch` envs: `DE_TEST_ELASTICSEARCH_API_KEY, DE_TEST_ELASTICSEARCH_URL`
- `gcs` envs: `DE_TEST_GCS_BLOB, DE_TEST_GCS_BUCKET`
- `neo4j` envs: `DE_TEST_NEO4J_PASSWORD, DE_TEST_NEO4J_URI, DE_TEST_NEO4J_USERNAME`
- `redis` envs: `DE_TEST_REDIS_URL`
- `rest_api` envs: `DE_ENABLE_SLOW_PUBLIC_REST_CASES, DE_TEST_FRED_API_KEY, DE_TEST_GITHUB_TOKEN`
- `s3` envs: `DE_TEST_S3_BUCKET, DE_TEST_S3_KEY`

## Env routing

- Total mapped envs: `23`
- Tier env counts: `credentialed_example 2, customer_credentials_required 20, public_no_auth 1`
- Shared envs: `none`
- `DE_ENABLE_SLOW_PUBLIC_REST_CASES` cases: `dlt_github_issues`
- `DE_TEST_AZURE_ACCOUNT_URL` cases: `customer_azure_blob_source_registration`
- `DE_TEST_AZURE_BLOB` cases: `customer_azure_blob_source_registration`
- `DE_TEST_AZURE_BLOB_URL` cases: `customer_azure_blob_source_registration`
- `DE_TEST_AZURE_CONNECTION_STRING` cases: `customer_azure_blob_source_registration`
- `DE_TEST_AZURE_CONTAINER` cases: `customer_azure_blob_source_registration`
- `DE_TEST_BIGQUERY_PROJECT_ID` cases: `bigquery_customer_connector_test`
- `DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON` cases: `bigquery_customer_connector_test`
- `DE_TEST_CLICKHOUSE_PASSWORD` cases: `clickhouse_customer_connector_test`
- `DE_TEST_CLICKHOUSE_URL` cases: `clickhouse_customer_connector_test`
- `DE_TEST_CLICKHOUSE_USER` cases: `clickhouse_customer_connector_test`
- `DE_TEST_ELASTICSEARCH_API_KEY` cases: `elasticsearch_customer_connector_test`
- `DE_TEST_ELASTICSEARCH_URL` cases: `elasticsearch_customer_connector_test`
- `DE_TEST_FRED_API_KEY` cases: `fivetran_fred_gnpca`
- `DE_TEST_GCS_BLOB` cases: `customer_gcs_source_registration`
- `DE_TEST_GCS_BUCKET` cases: `customer_gcs_source_registration`
- `DE_TEST_GITHUB_TOKEN` cases: `dlt_github_issues_token`
- `DE_TEST_NEO4J_PASSWORD` cases: `neo4j_customer_connector_test`
- `DE_TEST_NEO4J_URI` cases: `neo4j_customer_connector_test`
- `DE_TEST_NEO4J_USERNAME` cases: `neo4j_customer_connector_test`
- `DE_TEST_REDIS_URL` cases: `redis_customer_connector_test`
- `DE_TEST_S3_BUCKET` cases: `customer_s3_source_registration`
- `DE_TEST_S3_KEY` cases: `customer_s3_source_registration`
- `DE_ENABLE_SLOW_PUBLIC_REST_CASES` actions: `enable_opt_in_public_cases`
- `DE_TEST_AZURE_ACCOUNT_URL` actions: `set_customer_connector_envs`
- `DE_TEST_AZURE_BLOB` actions: `set_customer_connector_envs`
- `DE_TEST_AZURE_BLOB_URL` actions: `set_customer_connector_envs`
- `DE_TEST_AZURE_CONNECTION_STRING` actions: `set_customer_connector_envs`
- `DE_TEST_AZURE_CONTAINER` actions: `set_customer_connector_envs`
- `DE_TEST_BIGQUERY_PROJECT_ID` actions: `set_customer_connector_envs`
- `DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON` actions: `set_customer_connector_envs`
- `DE_TEST_CLICKHOUSE_PASSWORD` actions: `set_customer_connector_envs`
- `DE_TEST_CLICKHOUSE_URL` actions: `set_customer_connector_envs`
- `DE_TEST_CLICKHOUSE_USER` actions: `set_customer_connector_envs`
- `DE_TEST_ELASTICSEARCH_API_KEY` actions: `set_customer_connector_envs`
- `DE_TEST_ELASTICSEARCH_URL` actions: `set_customer_connector_envs`
- `DE_TEST_FRED_API_KEY` actions: `set_credentialed_example_envs`
- `DE_TEST_GCS_BLOB` actions: `set_customer_connector_envs`
- `DE_TEST_GCS_BUCKET` actions: `set_customer_connector_envs`
- `DE_TEST_GITHUB_TOKEN` actions: `set_credentialed_example_envs`
- `DE_TEST_NEO4J_PASSWORD` actions: `set_customer_connector_envs`
- `DE_TEST_NEO4J_URI` actions: `set_customer_connector_envs`
- `DE_TEST_NEO4J_USERNAME` actions: `set_customer_connector_envs`
- `DE_TEST_REDIS_URL` actions: `set_customer_connector_envs`
- `DE_TEST_S3_BUCKET` actions: `set_customer_connector_envs`
- `DE_TEST_S3_KEY` actions: `set_customer_connector_envs`
- `DE_ENABLE_SLOW_PUBLIC_REST_CASES` connectors: `rest_api`
- `DE_TEST_AZURE_ACCOUNT_URL` connectors: `azure_blob`
- `DE_TEST_AZURE_BLOB` connectors: `azure_blob`
- `DE_TEST_AZURE_BLOB_URL` connectors: `azure_blob`
- `DE_TEST_AZURE_CONNECTION_STRING` connectors: `azure_blob`
- `DE_TEST_AZURE_CONTAINER` connectors: `azure_blob`
- `DE_TEST_BIGQUERY_PROJECT_ID` connectors: `bigquery`
- `DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON` connectors: `bigquery`
- `DE_TEST_CLICKHOUSE_PASSWORD` connectors: `clickhouse`
- `DE_TEST_CLICKHOUSE_URL` connectors: `clickhouse`
- `DE_TEST_CLICKHOUSE_USER` connectors: `clickhouse`
- `DE_TEST_ELASTICSEARCH_API_KEY` connectors: `elasticsearch`
- `DE_TEST_ELASTICSEARCH_URL` connectors: `elasticsearch`
- `DE_TEST_FRED_API_KEY` connectors: `rest_api`
- `DE_TEST_GCS_BLOB` connectors: `gcs`
- `DE_TEST_GCS_BUCKET` connectors: `gcs`
- `DE_TEST_GITHUB_TOKEN` connectors: `rest_api`
- `DE_TEST_NEO4J_PASSWORD` connectors: `neo4j`
- `DE_TEST_NEO4J_URI` connectors: `neo4j`
- `DE_TEST_NEO4J_USERNAME` connectors: `neo4j`
- `DE_TEST_REDIS_URL` connectors: `redis`
- `DE_TEST_S3_BUCKET` connectors: `s3`
- `DE_TEST_S3_KEY` connectors: `s3`
- `DE_ENABLE_SLOW_PUBLIC_REST_CASES` tiers: `public_no_auth`
- `DE_TEST_AZURE_ACCOUNT_URL` tiers: `customer_credentials_required`
- `DE_TEST_AZURE_BLOB` tiers: `customer_credentials_required`
- `DE_TEST_AZURE_BLOB_URL` tiers: `customer_credentials_required`
- `DE_TEST_AZURE_CONNECTION_STRING` tiers: `customer_credentials_required`
- `DE_TEST_AZURE_CONTAINER` tiers: `customer_credentials_required`
- `DE_TEST_BIGQUERY_PROJECT_ID` tiers: `customer_credentials_required`
- `DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON` tiers: `customer_credentials_required`
- `DE_TEST_CLICKHOUSE_PASSWORD` tiers: `customer_credentials_required`
- `DE_TEST_CLICKHOUSE_URL` tiers: `customer_credentials_required`
- `DE_TEST_CLICKHOUSE_USER` tiers: `customer_credentials_required`
- `DE_TEST_ELASTICSEARCH_API_KEY` tiers: `customer_credentials_required`
- `DE_TEST_ELASTICSEARCH_URL` tiers: `customer_credentials_required`
- `DE_TEST_FRED_API_KEY` tiers: `credentialed_example`
- `DE_TEST_GCS_BLOB` tiers: `customer_credentials_required`
- `DE_TEST_GCS_BUCKET` tiers: `customer_credentials_required`
- `DE_TEST_GITHUB_TOKEN` tiers: `credentialed_example`
- `DE_TEST_NEO4J_PASSWORD` tiers: `customer_credentials_required`
- `DE_TEST_NEO4J_URI` tiers: `customer_credentials_required`
- `DE_TEST_NEO4J_USERNAME` tiers: `customer_credentials_required`
- `DE_TEST_REDIS_URL` tiers: `customer_credentials_required`
- `DE_TEST_S3_BUCKET` tiers: `customer_credentials_required`
- `DE_TEST_S3_KEY` tiers: `customer_credentials_required`

## Env resolution

- Resolver-supported envs: `22`
- Manual-only envs: `1`
- Group env counts: `azure_blob 5, bigquery 2, clickhouse 3, elasticsearch 2, gcs 2, neo4j 3, redis 1, s3 2`
- Manual-only env names: `DE_ENABLE_SLOW_PUBLIC_REST_CASES`
- `DE_ENABLE_SLOW_PUBLIC_REST_CASES` candidates: `DE_ENABLE_SLOW_PUBLIC_REST_CASES`
- `DE_TEST_AZURE_ACCOUNT_URL` candidates: `DE_TEST_AZURE_ACCOUNT_URL, AZURE_ACCOUNT_URL`
- `DE_TEST_AZURE_BLOB` candidates: `DE_TEST_AZURE_BLOB, AZURE_BLOB`
- `DE_TEST_AZURE_BLOB_URL` candidates: `DE_TEST_AZURE_BLOB_URL, AZURE_BLOB_URL`
- `DE_TEST_AZURE_CONNECTION_STRING` candidates: `DE_TEST_AZURE_CONNECTION_STRING, AZURE_CONNECTION_STRING`
- `DE_TEST_AZURE_CONTAINER` candidates: `DE_TEST_AZURE_CONTAINER, AZURE_CONTAINER`
- `DE_TEST_BIGQUERY_PROJECT_ID` candidates: `DE_TEST_BIGQUERY_PROJECT_ID, BIGQUERY_PROJECT_ID, GOOGLE_CLOUD_PROJECT, GCP_PROJECT_ID`
- `DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON` candidates: `DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON, BIGQUERY_SERVICE_ACCOUNT_JSON, GOOGLE_APPLICATION_CREDENTIALS_JSON, GCP_SERVICE_ACCOUNT_JSON, GOOGLE_APPLICATION_CREDENTIALS`
- `DE_TEST_CLICKHOUSE_PASSWORD` candidates: `DE_TEST_CLICKHOUSE_PASSWORD, CLICKHOUSE_PASSWORD`
- `DE_TEST_CLICKHOUSE_URL` candidates: `DE_TEST_CLICKHOUSE_URL, CLICKHOUSE_URL`
- `DE_TEST_CLICKHOUSE_USER` candidates: `DE_TEST_CLICKHOUSE_USER, CLICKHOUSE_USER`
- `DE_TEST_ELASTICSEARCH_API_KEY` candidates: `DE_TEST_ELASTICSEARCH_API_KEY, ELASTICSEARCH_API_KEY, ELASTIC_API_KEY`
- `DE_TEST_ELASTICSEARCH_URL` candidates: `DE_TEST_ELASTICSEARCH_URL, ELASTICSEARCH_URL, ELASTIC_URL`
- `DE_TEST_FRED_API_KEY` candidates: `DE_TEST_FRED_API_KEY, FRED_API_KEY`
- `DE_TEST_GCS_BLOB` candidates: `DE_TEST_GCS_BLOB, GCS_BLOB`
- `DE_TEST_GCS_BUCKET` candidates: `DE_TEST_GCS_BUCKET, GCS_BUCKET`
- `DE_TEST_GITHUB_TOKEN` candidates: `DE_TEST_GITHUB_TOKEN, GITHUB_TOKEN, GH_TOKEN`
- `DE_TEST_NEO4J_PASSWORD` candidates: `DE_TEST_NEO4J_PASSWORD, NEO4J_PASSWORD`
- `DE_TEST_NEO4J_URI` candidates: `DE_TEST_NEO4J_URI, NEO4J_URI, NEO4J_URL`
- `DE_TEST_NEO4J_USERNAME` candidates: `DE_TEST_NEO4J_USERNAME, NEO4J_USERNAME, NEO4J_USER`
- `DE_TEST_REDIS_URL` candidates: `DE_TEST_REDIS_URL, REDIS_URL`
- `DE_TEST_S3_BUCKET` candidates: `DE_TEST_S3_BUCKET, S3_BUCKET`
- `DE_TEST_S3_KEY` candidates: `DE_TEST_S3_KEY, S3_KEY`
- `DE_TEST_AZURE_ACCOUNT_URL` group: `azure_blob`
- `DE_TEST_AZURE_BLOB` group: `azure_blob`
- `DE_TEST_AZURE_BLOB_URL` group: `azure_blob`
- `DE_TEST_AZURE_CONNECTION_STRING` group: `azure_blob`
- `DE_TEST_AZURE_CONTAINER` group: `azure_blob`
- `DE_TEST_BIGQUERY_PROJECT_ID` group: `bigquery`
- `DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON` group: `bigquery`
- `DE_TEST_CLICKHOUSE_PASSWORD` group: `clickhouse`
- `DE_TEST_CLICKHOUSE_URL` group: `clickhouse`
- `DE_TEST_CLICKHOUSE_USER` group: `clickhouse`
- `DE_TEST_ELASTICSEARCH_API_KEY` group: `elasticsearch`
- `DE_TEST_ELASTICSEARCH_URL` group: `elasticsearch`
- `DE_TEST_GCS_BLOB` group: `gcs`
- `DE_TEST_GCS_BUCKET` group: `gcs`
- `DE_TEST_NEO4J_PASSWORD` group: `neo4j`
- `DE_TEST_NEO4J_URI` group: `neo4j`
- `DE_TEST_NEO4J_USERNAME` group: `neo4j`
- `DE_TEST_REDIS_URL` group: `redis`
- `DE_TEST_S3_BUCKET` group: `s3`
- `DE_TEST_S3_KEY` group: `s3`

## Env template coverage

- Gap env total: `23`
- All templates cover all current gap envs: `yes`
- `go_live_validation_env_example` (`tests/integration/go_live_validation.env.example`): `23/23` documented, missing `none`
- `root_env_example` (`.env.example`): `23/23` documented, missing `none`
