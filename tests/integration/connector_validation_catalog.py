from __future__ import annotations

import asyncio
import copy
import io
import json
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import quote, urlparse

from apps.api_server.connectors.rest_connector import fetch_rest_records_sync
from tests.go_live_secret_resolver import populate_go_live_test_env_from_keys_txt

populate_go_live_test_env_from_keys_txt()

ValidationTier = Literal["public_no_auth", "credentialed_example", "customer_credentials_required"]
ValidationMode = Literal["register_and_exact_query", "connector_test_only"]
BehaviorMode = Literal["immutable", "mutable_rest", "connector_test_only"]
NegativeProbe = Literal["invalid_auth", "invalid_path", "invalid_identifier", "none"]
ValueDriftMode = Literal["strict_sample_hash", "distribution_sketch", "none"]
AvailabilityCheck = Callable[[], str | None]
ExpectedRecordsLoader = Callable[[dict[str, Any]], list[dict[str, Any]]]

_S3_CUSTOM_ENV_NAMES = (
    "DE_TEST_S3_BUCKET",
    "DE_TEST_S3_KEY",
    "DE_TEST_S3_ACCESS_KEY_ID",
    "DE_TEST_S3_SECRET_ACCESS_KEY",
    "DE_TEST_S3_ENDPOINT_URL",
)
_GCS_CUSTOM_ENV_NAMES = (
    "DE_TEST_GCS_BUCKET",
    "DE_TEST_GCS_BLOB",
    "DE_TEST_GCS_CREDENTIALS",
    "DE_TEST_GCS_PROJECT_ID",
)
_AZURE_CUSTOM_ENV_NAMES = (
    "DE_TEST_AZURE_CONNECTION_STRING",
    "DE_TEST_AZURE_ACCOUNT_URL",
    "DE_TEST_AZURE_CONTAINER",
    "DE_TEST_AZURE_BLOB",
    "DE_TEST_AZURE_BLOB_URL",
)


def _any_env_set(names: tuple[str, ...]) -> bool:
    return any(str(os.environ.get(name, "")).strip() for name in names)


def _skip_when_any_env_set(names: tuple[str, ...], reason: str) -> AvailabilityCheck:
    return lambda: reason if _any_env_set(names) else None


def _require_env_values(*names: str) -> AvailabilityCheck:
    def _check() -> str | None:
        missing = [name for name in names if not str(os.environ.get(name, "")).strip()]
        if not missing:
            return None
        return f"required env not provided: {', '.join(missing)}"

    return _check


def _require_opt_in_env(name: str, reason: str) -> AvailabilityCheck:
    def _check() -> str | None:
        value = str(os.environ.get(name, "")).strip().lower()
        if value in {"1", "true", "yes", "on"}:
            return None
        return reason

    return _check


def _azure_customer_skip_reason() -> str | None:
    blob_url = str(os.environ.get("DE_TEST_AZURE_BLOB_URL", "")).strip()
    if blob_url:
        return None
    connection_string = str(os.environ.get("DE_TEST_AZURE_CONNECTION_STRING", "")).strip()
    account_url = str(os.environ.get("DE_TEST_AZURE_ACCOUNT_URL", "")).strip()
    container = str(os.environ.get("DE_TEST_AZURE_CONTAINER", "")).strip()
    blob = str(os.environ.get("DE_TEST_AZURE_BLOB", "")).strip()
    if (connection_string or account_url) and container and blob:
        return None
    return (
        "required env not provided: DE_TEST_AZURE_BLOB_URL or "
        "(DE_TEST_AZURE_CONNECTION_STRING or DE_TEST_AZURE_ACCOUNT_URL) + "
        "DE_TEST_AZURE_CONTAINER + DE_TEST_AZURE_BLOB"
    )


def _follow_data_path(data: Any, data_path: str) -> Any:
    current = data
    if not data_path:
        return current
    for key in data_path.split("."):
        if isinstance(current, dict):
            current = current.get(key, [])
        elif isinstance(current, list) and key.isdigit():
            index = int(key)
            current = current[index] if 0 <= index < len(current) else []
        else:
            return []
    return current


def _load_rest_records(connection: dict[str, Any]) -> list[dict[str, Any]]:
    return fetch_rest_records_sync(connection)


def _parse_csv_text(text: str) -> list[dict[str, Any]]:
    from apps.api_server.services.data_coercion import parse_delimited_records

    return parse_delimited_records(text, delimiter=",", sniff=True)


def _decode_records_from_bytes(data: bytes, file_type: str) -> list[dict[str, Any]]:
    normalized = file_type.strip().lower()
    if normalized == "csv":
        return _parse_csv_text(data.decode("utf-8", errors="replace"))
    if normalized == "json":
        payload = json.loads(data.decode("utf-8", errors="replace"))
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            return [payload]
        raise ValueError(
            f"Expected JSON object/list for file_type=json, got {type(payload).__name__}"
        )
    if normalized == "parquet":
        import pyarrow.parquet as pq

        from apps.api_server.services.pyarrow_runtime import initialize_pyarrow_parquet_runtime

        initialize_pyarrow_parquet_runtime()
        table = pq.read_table(io.BytesIO(data))
        return table.to_pylist()
    raise ValueError(f"Unsupported file_type {file_type!r} for validation loader.")


def _load_s3_records(connection: dict[str, Any]) -> list[dict[str, Any]]:
    from apps.api_server.connectors.cloud_connector import S3Connector

    return asyncio.run(S3Connector(connection).fetch_data())


def _load_gcs_records(connection: dict[str, Any]) -> list[dict[str, Any]]:
    from apps.api_server.connectors.cloud_connector import GCSConnector

    return asyncio.run(GCSConnector(connection).fetch_data())


def _load_azure_records(connection: dict[str, Any]) -> list[dict[str, Any]]:
    from apps.api_server.connectors.cloud_connector import AzureBlobConnector

    return asyncio.run(AzureBlobConnector(connection).fetch_data())


def _load_sql_records(connection: dict[str, Any]) -> list[dict[str, Any]]:
    from apps.api_server.connectors.sql_connector import SQLConnector

    connection_string = str(connection.get("connection_string", "")).strip()
    query = str(connection.get("query", "")).strip()
    limit_raw = connection.get("limit")
    limit = None if limit_raw in (None, "") else int(limit_raw)
    if connection_string and query:
        query_body, _wrapped_query = SQLConnector._build_wrapped_query(query=query, limit=limit)
        if SQLConnector._is_clickhouse_dsn(connection_string):
            return SQLConnector._fetch_clickhouse_sync(connection_string, query_body, limit)
        if SQLConnector._is_snowflake_dsn(connection_string):
            return SQLConnector._fetch_snowflake_sync(connection_string, query_body, limit)
    return asyncio.run(SQLConnector(connection).fetch_data())


def _snowflake_database() -> str:
    return str(os.environ.get("DE_TEST_SNOWFLAKE_DATABASE", "SNOWFLAKE_SAMPLE_DATA")).strip()


def _snowflake_schema() -> str:
    return str(os.environ.get("DE_TEST_SNOWFLAKE_SCHEMA", "TPCH_SF1")).strip()


def _build_snowflake_sql_connection() -> dict[str, Any]:
    account = str(os.environ.get("DE_TEST_SNOWFLAKE_ACCOUNT", "")).strip()
    user = quote(str(os.environ.get("DE_TEST_SNOWFLAKE_USER", "")).strip(), safe="")
    password = quote(str(os.environ.get("DE_TEST_SNOWFLAKE_PASSWORD", "")).strip(), safe="")
    warehouse = str(os.environ.get("DE_TEST_SNOWFLAKE_WAREHOUSE", "")).strip()
    database = _snowflake_database()
    schema = _snowflake_schema()
    query = str(os.environ.get("DE_TEST_SNOWFLAKE_QUERY", "")).strip()
    table = str(os.environ.get("DE_TEST_SNOWFLAKE_TABLE", "")).strip()
    if not query:
        if not table:
            raise ValueError(
                "Snowflake behavior validation requires DE_TEST_SNOWFLAKE_QUERY "
                "or DE_TEST_SNOWFLAKE_TABLE."
            )
        qualified_table = table if "." in table else f"{database}.{schema}.{table}"
        query = f"SELECT * FROM {qualified_table} ORDER BY 1"
    connection_string = f"snowflake://{user}:{password}@{account}/{database}/{schema}"
    if warehouse:
        connection_string += f"?warehouse={quote(warehouse, safe='')}"
    return {
        "type": "sql",
        "connection_string": connection_string,
        "query": query,
        "limit": int(os.environ.get("DE_TEST_SNOWFLAKE_LIMIT", "100")),
    }


def _build_bigquery_sql_connection() -> dict[str, Any]:
    project_id = str(os.environ.get("DE_TEST_BIGQUERY_PROJECT_ID", "")).strip()
    query = str(os.environ.get("DE_TEST_BIGQUERY_QUERY", "")).strip()
    dataset = str(os.environ.get("DE_TEST_BIGQUERY_DATASET", "")).strip()
    table = str(os.environ.get("DE_TEST_BIGQUERY_TABLE", "")).strip()
    if not query:
        if not dataset or not table:
            raise ValueError(
                "BigQuery behavior validation requires DE_TEST_BIGQUERY_QUERY "
                "or DE_TEST_BIGQUERY_DATASET + DE_TEST_BIGQUERY_TABLE."
            )
        query = f"SELECT * FROM `{project_id}.{dataset}.{table}` ORDER BY 1 LIMIT 100"
    return {
        "type": "sql",
        "connection_string": f"bigquery://{project_id}",
        "query": query,
        "limit": int(os.environ.get("DE_TEST_BIGQUERY_LIMIT", "100")),
    }


def _clickhouse_database() -> str:
    return str(os.environ.get("DE_TEST_CLICKHOUSE_DATABASE", "default")).strip()


def _build_clickhouse_sql_connection() -> dict[str, Any]:
    url = str(os.environ.get("DE_TEST_CLICKHOUSE_URL", "")).strip()
    user = quote(str(os.environ.get("DE_TEST_CLICKHOUSE_USER", "")).strip() or "default", safe="")
    password = quote(str(os.environ.get("DE_TEST_CLICKHOUSE_PASSWORD", "")).strip(), safe="")
    parsed = urlparse(url)
    if not parsed.hostname:
        raise ValueError("ClickHouse behavior validation requires DE_TEST_CLICKHOUSE_URL.")
    secure = parsed.scheme == "https"
    port = parsed.port or (8443 if secure else 8123)
    database = _clickhouse_database()
    query = str(os.environ.get("DE_TEST_CLICKHOUSE_QUERY", "")).strip()
    table = str(os.environ.get("DE_TEST_CLICKHOUSE_TABLE", "")).strip()
    if not query:
        if not table:
            raise ValueError(
                "ClickHouse behavior validation requires DE_TEST_CLICKHOUSE_QUERY "
                "or DE_TEST_CLICKHOUSE_TABLE."
            )
        query = f"SELECT * FROM `{database}`.`{table}` ORDER BY 1 LIMIT {int(os.environ.get('DE_TEST_CLICKHOUSE_LIMIT', '100'))}"
    return {
        "type": "sql",
        "connection_string": (
            f"clickhouse://{user}:{password}@{parsed.hostname}:{port}/{quote(database, safe='')}"
            f"?secure={'true' if secure else 'false'}"
        ),
        "query": query,
        "limit": int(os.environ.get("DE_TEST_CLICKHOUSE_LIMIT", "100")),
    }


def _build_redis_connector_config() -> dict[str, Any]:
    return {
        "url": str(os.environ.get("DE_TEST_REDIS_URL", "")).strip(),
    }


def _build_elasticsearch_connector_config() -> dict[str, Any]:
    config: dict[str, Any] = {
        "url": str(os.environ.get("DE_TEST_ELASTICSEARCH_URL", "")).strip(),
        "api_key": str(os.environ.get("DE_TEST_ELASTICSEARCH_API_KEY", "")).strip(),
    }
    index = str(os.environ.get("DE_TEST_ELASTICSEARCH_INDEX", "")).strip()
    if index:
        config["index"] = index
    query = str(os.environ.get("DE_TEST_ELASTICSEARCH_QUERY", "")).strip()
    if query:
        config["query"] = query
    limit = str(os.environ.get("DE_TEST_ELASTICSEARCH_LIMIT", "")).strip()
    if limit:
        config["limit"] = int(limit)
    return config


def _neo4j_database() -> str:
    return str(os.environ.get("DE_TEST_NEO4J_DATABASE", "neo4j")).strip()


def _build_neo4j_connector_config() -> dict[str, Any]:
    return {
        "uri": str(os.environ.get("DE_TEST_NEO4J_URI", "")).strip(),
        "username": str(os.environ.get("DE_TEST_NEO4J_USERNAME", "")).strip(),
        "password": str(os.environ.get("DE_TEST_NEO4J_PASSWORD", "")).strip(),
        "database": _neo4j_database(),
    }


def _warehouse_behavior_selector_required(
    query_env: str,
    selector_envs: tuple[str, ...],
) -> AvailabilityCheck:
    def _check() -> str | None:
        query = str(os.environ.get(query_env, "")).strip()
        if query:
            return None
        missing = [name for name in selector_envs if not str(os.environ.get(name, "")).strip()]
        if not missing:
            return None
        selector_text = " + ".join(selector_envs)
        return f"behavior fixture selector not provided: {query_env} or {selector_text}"

    return _check


@dataclass(frozen=True)
class ConnectorValidationCase:
    case_id: str
    label: str
    ecosystem: str
    example_name: str
    connector_type: str
    tier: ValidationTier
    validation_mode: ValidationMode
    behavior_mode: BehaviorMode
    connection: dict[str, Any] = field(default_factory=dict)
    connection_factory: Callable[[], dict[str, Any]] | None = None
    connector_config: dict[str, Any] = field(default_factory=dict)
    connector_config_factory: Callable[[], dict[str, Any]] | None = None
    expected_records_loader: ExpectedRecordsLoader | None = None
    aggregation: str = "count"
    row_count_tolerance: float = 0.0
    identity_columns: tuple[str, ...] = ()
    rate_limit_probe_requests: int = 0
    negative_probe: NegativeProbe = "none"
    value_drift_mode: ValueDriftMode = "none"
    negative_connection_factory: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    docs_url: str = ""
    enabled_by_default: bool = True
    benchmark_enabled: bool = True
    required_env_vars: tuple[str, ...] = ()
    availability_check: AvailabilityCheck | None = None
    behavior_validation_mode: ValidationMode | None = None
    behavior_mode_override: BehaviorMode | None = None
    behavior_connection_factory: Callable[[], dict[str, Any]] | None = None
    behavior_expected_records_loader: ExpectedRecordsLoader | None = None
    behavior_required_env_vars: tuple[str, ...] = ()
    behavior_availability_check: AvailabilityCheck | None = None
    notes: str = ""

    def missing_env_vars(self) -> tuple[str, ...]:
        return tuple(
            name for name in self.required_env_vars if not str(os.environ.get(name, "")).strip()
        )

    def skip_reason(self) -> str | None:
        missing_env_vars = self.missing_env_vars()
        if missing_env_vars:
            return f"required env not provided: {', '.join(missing_env_vars)}"
        if self.availability_check is not None:
            return self.availability_check()
        return None

    def is_configured(self) -> bool:
        return self.skip_reason() is None

    def build_connection(self) -> dict[str, Any]:
        if self.connection_factory is not None:
            return copy.deepcopy(self.connection_factory())
        return copy.deepcopy(self.connection)

    def missing_behavior_env_vars(self) -> tuple[str, ...]:
        return tuple(
            name
            for name in self.behavior_required_env_vars
            if not str(os.environ.get(name, "")).strip()
        )

    def behavior_skip_reason(self) -> str | None:
        missing_env_vars = self.missing_behavior_env_vars()
        if missing_env_vars:
            return f"required env not provided: {', '.join(missing_env_vars)}"
        if self.behavior_availability_check is not None:
            return self.behavior_availability_check()
        return None

    def supports_behavior_validation(self) -> bool:
        if self.behavior_validation_mode is None or self.behavior_connection_factory is None:
            return False
        return self.behavior_skip_reason() is None

    def effective_validation_mode(self) -> ValidationMode:
        if self.supports_behavior_validation() and self.behavior_validation_mode is not None:
            return self.behavior_validation_mode
        return self.validation_mode

    def effective_behavior_mode(self) -> BehaviorMode:
        if self.supports_behavior_validation() and self.behavior_mode_override is not None:
            return self.behavior_mode_override
        return self.behavior_mode

    def build_connector_config(self) -> dict[str, Any]:
        if self.connector_config_factory is not None:
            return copy.deepcopy(self.connector_config_factory())
        return copy.deepcopy(self.connector_config)

    def load_expected_records(self) -> list[dict[str, Any]]:
        return self.load_records_for_connection(self.build_connection())

    def load_records_for_connection(self, connection: dict[str, Any]) -> list[dict[str, Any]]:
        if self.expected_records_loader is not None:
            return self.expected_records_loader(connection)
        if self.connector_type == "rest_api":
            return _load_rest_records(connection)
        raise ValueError(f"Unsupported validation loader for {self.connector_type}")

    def build_runtime_connection(self) -> dict[str, Any]:
        if self.supports_behavior_validation():
            if self.behavior_connection_factory is None:
                raise ValueError(f"Behavior connection is not configured for {self.case_id}")
            return copy.deepcopy(self.behavior_connection_factory())
        return self.build_connection()

    def load_runtime_records_for_connection(
        self, connection: dict[str, Any]
    ) -> list[dict[str, Any]]:
        if (
            self.supports_behavior_validation()
            and self.behavior_expected_records_loader is not None
        ):
            return self.behavior_expected_records_loader(connection)
        return self.load_records_for_connection(connection)


PUBLIC_VALIDATION_CASES: tuple[ConnectorValidationCase, ...] = (
    ConnectorValidationCase(
        case_id="public_s3_source_registration",
        label="Live S3 source registration",
        ecosystem="cloud",
        example_name="public_s3",
        connector_type="s3",
        tier="public_no_auth",
        validation_mode="register_and_exact_query",
        behavior_mode="immutable",
        connection={
            "type": "s3",
            "bucket": "1000genomes",
            "key": "20131219.populations.tsv",
            "region": "us-east-1",
            "anonymous": True,
            "file_type": "tsv",
        },
        expected_records_loader=_load_s3_records,
        negative_probe="none",
        value_drift_mode="strict_sample_hash",
        availability_check=_skip_when_any_env_set(
            _S3_CUSTOM_ENV_NAMES,
            "custom S3 env provided; public default case disabled",
        ),
        notes="Public S3 registration against the 1000 Genomes populations TSV sample.",
    ),
    ConnectorValidationCase(
        case_id="public_gcs_source_registration",
        label="Live GCS source registration",
        ecosystem="cloud",
        example_name="public_gcs",
        connector_type="gcs",
        tier="public_no_auth",
        validation_mode="register_and_exact_query",
        behavior_mode="immutable",
        connection={
            "type": "gcs",
            "bucket": "cloud-samples-data",
            "blob": "bigquery/us-states/us-states.csv",
            "anonymous": True,
            "file_type": "csv",
        },
        expected_records_loader=_load_gcs_records,
        negative_probe="invalid_identifier",
        negative_connection_factory=lambda connection: {
            **connection,
            "bucket": "invalid bucket name",
        },
        value_drift_mode="strict_sample_hash",
        availability_check=_skip_when_any_env_set(
            _GCS_CUSTOM_ENV_NAMES,
            "custom GCS env provided; public default case disabled",
        ),
        notes="Public GCS registration against the cloud-samples-data transaction sample.",
    ),
    ConnectorValidationCase(
        case_id="public_azure_blob_source_registration",
        label="Live Azure Blob source registration",
        ecosystem="cloud",
        example_name="public_azure_blob",
        connector_type="azure_blob",
        tier="public_no_auth",
        validation_mode="register_and_exact_query",
        behavior_mode="immutable",
        connection={
            "type": "azure_blob",
            "account_url": "https://azureopendatastorage.blob.core.windows.net",
            "container": "mlsamples",
            "blob": (
                "diabetes/part-00000-tid-6082354649623433283-5a3d3599-0872-4a3e-a027-"
                "bddf5f6d57ca-1951182-c000.snappy.parquet"
            ),
            "blob_url": (
                "https://azureopendatastorage.blob.core.windows.net/mlsamples/diabetes/"
                "part-00000-tid-6082354649623433283-5a3d3599-0872-4a3e-a027-"
                "bddf5f6d57ca-1951182-c000.snappy.parquet"
            ),
            "anonymous": True,
            "file_type": "parquet",
        },
        expected_records_loader=_load_azure_records,
        negative_probe="none",
        value_drift_mode="strict_sample_hash",
        availability_check=_skip_when_any_env_set(
            _AZURE_CUSTOM_ENV_NAMES,
            "custom Azure env provided; public default case disabled",
        ),
        notes="Public Azure Blob registration against the Azure Open Datasets diabetes parquet sample.",
    ),
    ConnectorValidationCase(
        case_id="fivetran_noaa_station_kilg",
        label="Fivetran NOAA station example source registration",
        ecosystem="fivetran",
        example_name="noaa",
        connector_type="rest_api",
        tier="public_no_auth",
        validation_mode="register_and_exact_query",
        behavior_mode="mutable_rest",
        connection={
            "type": "rest_api",
            "url": "https://api.weather.gov/stations/KILG",
            "headers": {
                "User-Agent": "decision-engine-go-live/1.0",
                "Accept": "application/geo+json",
            },
            "timeout": 60,
        },
        row_count_tolerance=0.02,
        identity_columns=("id",),
        rate_limit_probe_requests=3,
        negative_probe="none",
        value_drift_mode="distribution_sketch",
        docs_url="https://fivetran.com/docs/connector-sdk/examples",
        benchmark_enabled=False,
        notes="Public NOAA API used by the Fivetran Connector SDK example.",
    ),
    ConnectorValidationCase(
        case_id="fivetran_npi_registry_number",
        label="Fivetran NPI Registry example source registration",
        ecosystem="fivetran",
        example_name="npi_registry",
        connector_type="rest_api",
        tier="public_no_auth",
        validation_mode="register_and_exact_query",
        behavior_mode="mutable_rest",
        connection={
            "type": "rest_api",
            "url": "https://npiregistry.cms.hhs.gov/api/",
            "params": {
                "version": "2.1",
                "number": "1770911224",
            },
            "data_path": "results",
            "timeout": 60,
        },
        row_count_tolerance=0.02,
        identity_columns=("number",),
        rate_limit_probe_requests=3,
        negative_probe="invalid_identifier",
        value_drift_mode="distribution_sketch",
        negative_connection_factory=lambda connection: {
            **connection,
            "data_path": "results..invalid",
        },
        docs_url="https://fivetran.com/docs/connector-sdk/examples",
        notes="Public CMS NPI Registry API narrowed to a single NPI for deterministic SLA validation.",
    ),
    ConnectorValidationCase(
        case_id="dlt_pokeapi_pokemon",
        label="dlt PokeAPI example source registration",
        ecosystem="dlt",
        example_name="pokemon",
        connector_type="rest_api",
        tier="public_no_auth",
        validation_mode="register_and_exact_query",
        behavior_mode="mutable_rest",
        connection={
            "type": "rest_api",
            "url": "https://pokeapi.co/api/v2/pokemon",
            "params": {"limit": "10"},
            "data_path": "results",
            "timeout": 60,
        },
        row_count_tolerance=0.02,
        identity_columns=("name",),
        rate_limit_probe_requests=3,
        negative_probe="none",
        value_drift_mode="distribution_sketch",
        docs_url="https://dlthub.com/docs/tutorial/rest-api",
        notes="Public Pokemon example from the dlt REST API tutorial.",
    ),
    ConnectorValidationCase(
        case_id="pokeapi_color_pagination",
        label="PokeAPI color pagination source registration",
        ecosystem="pokeapi",
        example_name="color_pagination",
        connector_type="rest_api",
        tier="public_no_auth",
        validation_mode="register_and_exact_query",
        behavior_mode="immutable",
        connection={
            "type": "rest_api",
            "url": "https://pokeapi.co/api/v2/pokemon-color?limit=5",
            "data_path": "results",
            "timeout": 60,
            "pagination": {
                "mode": "cursor_path",
                "next_path": "next",
                "max_pages": 2,
            },
        },
        row_count_tolerance=0.0,
        identity_columns=("name",),
        rate_limit_probe_requests=3,
        negative_probe="none",
        value_drift_mode="strict_sample_hash",
        docs_url="https://pokeapi.co/docs/v2",
        benchmark_enabled=False,
        notes=(
            "Public PokéAPI pagination example using the documented resource-list next URL "
            "contract over the pokemon-color endpoint."
        ),
    ),
    ConnectorValidationCase(
        case_id="dlt_github_issues",
        label="dlt GitHub issues example source registration",
        ecosystem="dlt",
        example_name="github_issues",
        connector_type="rest_api",
        tier="public_no_auth",
        validation_mode="register_and_exact_query",
        behavior_mode="mutable_rest",
        connection={
            "type": "rest_api",
            "url": "https://api.github.com/repos/dlt-hub/dlt/issues",
            "headers": {
                "Accept": "application/vnd.github+json",
                "User-Agent": "decision-engine-go-live/1.0",
            },
            "params": {
                "per_page": "25",
                "state": "open",
                "sort": "updated",
                "direction": "desc",
                "labels": "bug",
            },
            "timeout": 60,
            "pagination": {
                "mode": "page_number",
                "page_param": "page",
                "start_page": 1,
                "page_size_param": "per_page",
                "page_size": 25,
                "next_link_rel": "next",
                "max_pages": 2,
            },
        },
        row_count_tolerance=0.10,
        identity_columns=("id",),
        rate_limit_probe_requests=3,
        negative_probe="none",
        value_drift_mode="distribution_sketch",
        docs_url="https://dlthub.com/docs/tutorial/rest-api",
        benchmark_enabled=False,
        availability_check=_require_opt_in_env(
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES",
            "unauthenticated dlt GitHub issues case disabled by default; set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1",
        ),
        notes="Public GitHub issues example from the dlt REST API tutorial.",
    ),
)


THIRD_PARTY_TIER2_CASES: tuple[ConnectorValidationCase, ...] = (
    ConnectorValidationCase(
        case_id="fivetran_fred_gnpca",
        label="Fivetran FRED example source registration",
        ecosystem="fivetran",
        example_name="fred",
        connector_type="rest_api",
        tier="credentialed_example",
        validation_mode="register_and_exact_query",
        behavior_mode="mutable_rest",
        connection_factory=lambda: {
            "type": "rest_api",
            "url": "https://api.stlouisfed.org/fred/series/observations",
            "params": {
                "series_id": os.environ.get("DE_TEST_FRED_SERIES_ID", "GNPCA"),
                "api_key": os.environ.get("DE_TEST_FRED_API_KEY", ""),
                "file_type": "json",
                "sort_order": "desc",
                "limit": "25",
            },
            "data_path": "observations",
            "timeout": 60,
        },
        row_count_tolerance=0.0,
        identity_columns=("date",),
        rate_limit_probe_requests=3,
        negative_probe="invalid_auth",
        value_drift_mode="distribution_sketch",
        docs_url="https://fivetran.com/docs/connector-sdk/examples",
        enabled_by_default=False,
        required_env_vars=("DE_TEST_FRED_API_KEY",),
        notes="Credentialed FRED API example from the Fivetran Connector SDK docs.",
    ),
    ConnectorValidationCase(
        case_id="dlt_github_issues_token",
        label="dlt GitHub token example source registration",
        ecosystem="dlt",
        example_name="github_token",
        connector_type="rest_api",
        tier="credentialed_example",
        validation_mode="register_and_exact_query",
        behavior_mode="mutable_rest",
        connection_factory=lambda: {
            "type": "rest_api",
            "url": "https://api.github.com/repos/dlt-hub/dlt/issues",
            "headers": {
                "Accept": "application/vnd.github+json",
                "User-Agent": "decision-engine-go-live/1.0",
                "Authorization": f"Bearer {os.environ.get('DE_TEST_GITHUB_TOKEN', '')}",
            },
            "params": {
                "per_page": "25",
                "state": "open",
                "sort": "updated",
                "direction": "desc",
                "labels": "bug",
            },
            "timeout": 60,
            "pagination": {
                "mode": "page_number",
                "page_param": "page",
                "start_page": 1,
                "page_size_param": "per_page",
                "page_size": 25,
                "next_link_rel": "next",
                "max_pages": 2,
            },
        },
        row_count_tolerance=0.10,
        identity_columns=("id",),
        rate_limit_probe_requests=3,
        negative_probe="invalid_auth",
        value_drift_mode="distribution_sketch",
        docs_url="https://dlthub.com/docs/dlt-ecosystem/verified-sources/rest_api/basic",
        enabled_by_default=False,
        required_env_vars=("DE_TEST_GITHUB_TOKEN",),
        notes="Credentialed GitHub API example from the dlt REST API source docs.",
    ),
)


CUSTOMER_CREDENTIAL_REQUIRED_CASES: tuple[ConnectorValidationCase, ...] = (
    ConnectorValidationCase(
        case_id="customer_s3_source_registration",
        label="Custom S3 source registration",
        ecosystem="cloud",
        example_name="customer_s3_live",
        connector_type="s3",
        tier="customer_credentials_required",
        validation_mode="register_and_exact_query",
        behavior_mode="immutable",
        connection_factory=lambda: {
            "type": "s3",
            "bucket": os.environ.get("DE_TEST_S3_BUCKET", ""),
            "key": os.environ.get("DE_TEST_S3_KEY", ""),
            "region": os.environ.get("DE_TEST_S3_REGION", "us-east-1"),
            "aws_access_key_id": os.environ.get("DE_TEST_S3_ACCESS_KEY_ID", ""),
            "aws_secret_access_key": os.environ.get("DE_TEST_S3_SECRET_ACCESS_KEY", ""),
            "endpoint_url": os.environ.get("DE_TEST_S3_ENDPOINT_URL", ""),
            "anonymous": False,
            "file_type": os.environ.get("DE_TEST_S3_FILE_TYPE", "csv"),
        },
        expected_records_loader=_load_s3_records,
        negative_probe="invalid_path",
        value_drift_mode="strict_sample_hash",
        availability_check=_require_env_values("DE_TEST_S3_BUCKET", "DE_TEST_S3_KEY"),
        enabled_by_default=False,
        notes="Live-only S3 source validation against customer-provided configuration.",
    ),
    ConnectorValidationCase(
        case_id="customer_gcs_source_registration",
        label="Custom GCS source registration",
        ecosystem="cloud",
        example_name="customer_gcs_live",
        connector_type="gcs",
        tier="customer_credentials_required",
        validation_mode="register_and_exact_query",
        behavior_mode="immutable",
        connection_factory=lambda: {
            "type": "gcs",
            "bucket": os.environ.get("DE_TEST_GCS_BUCKET", ""),
            "blob": os.environ.get("DE_TEST_GCS_BLOB", ""),
            "credentials": os.environ.get("DE_TEST_GCS_CREDENTIALS", ""),
            "project_id": os.environ.get("DE_TEST_GCS_PROJECT_ID", ""),
            "anonymous": False,
            "file_type": os.environ.get("DE_TEST_GCS_FILE_TYPE", "csv"),
        },
        expected_records_loader=_load_gcs_records,
        negative_probe="invalid_path",
        value_drift_mode="strict_sample_hash",
        availability_check=_require_env_values("DE_TEST_GCS_BUCKET", "DE_TEST_GCS_BLOB"),
        enabled_by_default=False,
        notes="Live-only GCS source validation against customer-provided configuration.",
    ),
    ConnectorValidationCase(
        case_id="customer_azure_blob_source_registration",
        label="Custom Azure Blob source registration",
        ecosystem="cloud",
        example_name="customer_azure_blob_live",
        connector_type="azure_blob",
        tier="customer_credentials_required",
        validation_mode="register_and_exact_query",
        behavior_mode="immutable",
        connection_factory=lambda: {
            "type": "azure_blob",
            "connection_string": os.environ.get("DE_TEST_AZURE_CONNECTION_STRING", ""),
            "account_url": os.environ.get("DE_TEST_AZURE_ACCOUNT_URL", ""),
            "container": os.environ.get("DE_TEST_AZURE_CONTAINER", ""),
            "blob": os.environ.get("DE_TEST_AZURE_BLOB", ""),
            "blob_url": os.environ.get("DE_TEST_AZURE_BLOB_URL", ""),
            "anonymous": False,
            "file_type": os.environ.get("DE_TEST_AZURE_FILE_TYPE", "csv"),
        },
        expected_records_loader=_load_azure_records,
        negative_probe="invalid_path",
        value_drift_mode="strict_sample_hash",
        availability_check=_azure_customer_skip_reason,
        enabled_by_default=False,
        notes="Live-only Azure Blob validation against customer-provided configuration.",
    ),
    ConnectorValidationCase(
        case_id="redis_customer_connector_test",
        label="Redis connector /test",
        ecosystem="core",
        example_name="redis_customer_live",
        connector_type="redis",
        tier="customer_credentials_required",
        validation_mode="connector_test_only",
        behavior_mode="connector_test_only",
        connector_config_factory=_build_redis_connector_config,
        enabled_by_default=False,
        negative_probe="invalid_auth",
        value_drift_mode="none",
        required_env_vars=("DE_TEST_REDIS_URL",),
        docs_url="https://redis.io/docs/latest/develop/clients/",
        notes="Live-only Redis validation against customer credentials.",
    ),
    ConnectorValidationCase(
        case_id="clickhouse_customer_connector_test",
        label="ClickHouse connector /test",
        ecosystem="core",
        example_name="clickhouse_customer_live",
        connector_type="clickhouse",
        tier="customer_credentials_required",
        validation_mode="connector_test_only",
        behavior_mode="connector_test_only",
        connector_config_factory=lambda: {
            "url": os.environ.get("DE_TEST_CLICKHOUSE_URL", ""),
            "user": os.environ.get("DE_TEST_CLICKHOUSE_USER", ""),
            "password": os.environ.get("DE_TEST_CLICKHOUSE_PASSWORD", ""),
            "database": _clickhouse_database(),
        },
        enabled_by_default=False,
        negative_probe="invalid_auth",
        value_drift_mode="strict_sample_hash",
        required_env_vars=(
            "DE_TEST_CLICKHOUSE_URL",
            "DE_TEST_CLICKHOUSE_USER",
            "DE_TEST_CLICKHOUSE_PASSWORD",
        ),
        behavior_validation_mode="register_and_exact_query",
        behavior_mode_override="immutable",
        behavior_connection_factory=_build_clickhouse_sql_connection,
        behavior_expected_records_loader=_load_sql_records,
        behavior_required_env_vars=(
            "DE_TEST_CLICKHOUSE_URL",
            "DE_TEST_CLICKHOUSE_USER",
            "DE_TEST_CLICKHOUSE_PASSWORD",
        ),
        behavior_availability_check=_warehouse_behavior_selector_required(
            "DE_TEST_CLICKHOUSE_QUERY",
            ("DE_TEST_CLICKHOUSE_TABLE",),
        ),
        docs_url="https://clickhouse.com/docs",
        notes=(
            "Live-only ClickHouse validation against customer credentials. "
            "Behavior mode requires explicit fixture selection via DE_TEST_CLICKHOUSE_QUERY "
            "or DE_TEST_CLICKHOUSE_TABLE."
        ),
    ),
    ConnectorValidationCase(
        case_id="elasticsearch_customer_connector_test",
        label="Elasticsearch connector /test",
        ecosystem="core",
        example_name="elasticsearch_customer_live",
        connector_type="elasticsearch",
        tier="customer_credentials_required",
        validation_mode="connector_test_only",
        behavior_mode="connector_test_only",
        connector_config_factory=_build_elasticsearch_connector_config,
        enabled_by_default=False,
        negative_probe="invalid_auth",
        value_drift_mode="none",
        required_env_vars=(
            "DE_TEST_ELASTICSEARCH_URL",
            "DE_TEST_ELASTICSEARCH_API_KEY",
        ),
        docs_url="https://www.elastic.co/guide/en/elasticsearch/reference/current/rest-apis.html",
        notes="Live-only Elasticsearch / Elastic Cloud validation against customer credentials.",
    ),
    ConnectorValidationCase(
        case_id="neo4j_customer_connector_test",
        label="Neo4j connector /test",
        ecosystem="core",
        example_name="neo4j_customer_live",
        connector_type="neo4j",
        tier="customer_credentials_required",
        validation_mode="connector_test_only",
        behavior_mode="connector_test_only",
        connector_config_factory=_build_neo4j_connector_config,
        enabled_by_default=False,
        negative_probe="invalid_auth",
        value_drift_mode="none",
        required_env_vars=(
            "DE_TEST_NEO4J_URI",
            "DE_TEST_NEO4J_USERNAME",
            "DE_TEST_NEO4J_PASSWORD",
        ),
        docs_url="https://neo4j.com/docs/python-manual/current/",
        notes="Live-only Neo4j Aura validation against customer credentials.",
    ),
    ConnectorValidationCase(
        case_id="snowflake_customer_connector_test",
        label="Snowflake connector /test",
        ecosystem="core",
        example_name="snowflake_customer_live",
        connector_type="snowflake",
        tier="customer_credentials_required",
        validation_mode="connector_test_only",
        behavior_mode="connector_test_only",
        connector_config_factory=lambda: {
            "account": os.environ.get("DE_TEST_SNOWFLAKE_ACCOUNT", ""),
            "user": os.environ.get("DE_TEST_SNOWFLAKE_USER", ""),
            "password": os.environ.get("DE_TEST_SNOWFLAKE_PASSWORD", ""),
            "warehouse": os.environ.get("DE_TEST_SNOWFLAKE_WAREHOUSE", ""),
            "database": _snowflake_database(),
            "schema": _snowflake_schema(),
        },
        enabled_by_default=False,
        negative_probe="invalid_auth",
        value_drift_mode="strict_sample_hash",
        required_env_vars=(
            "DE_TEST_SNOWFLAKE_ACCOUNT",
            "DE_TEST_SNOWFLAKE_USER",
            "DE_TEST_SNOWFLAKE_PASSWORD",
            "DE_TEST_SNOWFLAKE_WAREHOUSE",
        ),
        behavior_validation_mode="register_and_exact_query",
        behavior_mode_override="immutable",
        behavior_connection_factory=_build_snowflake_sql_connection,
        behavior_expected_records_loader=_load_sql_records,
        behavior_required_env_vars=(
            "DE_TEST_SNOWFLAKE_ACCOUNT",
            "DE_TEST_SNOWFLAKE_USER",
            "DE_TEST_SNOWFLAKE_PASSWORD",
            "DE_TEST_SNOWFLAKE_WAREHOUSE",
        ),
        behavior_availability_check=_warehouse_behavior_selector_required(
            "DE_TEST_SNOWFLAKE_QUERY",
            ("DE_TEST_SNOWFLAKE_TABLE",),
        ),
        docs_url="https://docs.snowflake.com/en/user-guide/sample-data-tpch",
        notes=(
            "Live-only Snowflake validation against customer credentials. "
            "Behavior mode requires explicit fixture selection via DE_TEST_SNOWFLAKE_QUERY "
            "or DE_TEST_SNOWFLAKE_TABLE. Snowflake's official sample data lives in "
            "SNOWFLAKE_SAMPLE_DATA.TPCH_SF1."
        ),
    ),
    ConnectorValidationCase(
        case_id="bigquery_customer_connector_test",
        label="BigQuery connector /test",
        ecosystem="core",
        example_name="bigquery_customer_live",
        connector_type="bigquery",
        tier="customer_credentials_required",
        validation_mode="connector_test_only",
        behavior_mode="connector_test_only",
        connector_config_factory=lambda: {
            "project_id": os.environ.get("DE_TEST_BIGQUERY_PROJECT_ID", ""),
            "service_account_json": os.environ.get("DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON", ""),
        },
        enabled_by_default=False,
        negative_probe="invalid_auth",
        value_drift_mode="strict_sample_hash",
        required_env_vars=(
            "DE_TEST_BIGQUERY_PROJECT_ID",
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
        ),
        behavior_validation_mode="register_and_exact_query",
        behavior_mode_override="immutable",
        behavior_connection_factory=_build_bigquery_sql_connection,
        behavior_expected_records_loader=_load_sql_records,
        behavior_required_env_vars=(
            "DE_TEST_BIGQUERY_PROJECT_ID",
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
        ),
        behavior_availability_check=_warehouse_behavior_selector_required(
            "DE_TEST_BIGQUERY_QUERY",
            ("DE_TEST_BIGQUERY_DATASET", "DE_TEST_BIGQUERY_TABLE"),
        ),
        docs_url="https://cloud.google.com/bigquery/public-data",
        notes=(
            "Live-only BigQuery validation against customer credentials. "
            "Behavior mode requires explicit fixture selection via DE_TEST_BIGQUERY_QUERY "
            "or DE_TEST_BIGQUERY_DATASET + DE_TEST_BIGQUERY_TABLE. BigQuery's official sample "
            "tables include bigquery-public-data.samples.shakespeare."
        ),
    ),
)


CONNECTOR_VALIDATION_MATRIX: dict[ValidationTier, tuple[ConnectorValidationCase, ...]] = {
    "public_no_auth": PUBLIC_VALIDATION_CASES,
    "credentialed_example": THIRD_PARTY_TIER2_CASES,
    "customer_credentials_required": CUSTOMER_CREDENTIAL_REQUIRED_CASES,
}

ALL_CONNECTOR_VALIDATION_CASES: tuple[ConnectorValidationCase, ...] = (
    PUBLIC_VALIDATION_CASES + THIRD_PARTY_TIER2_CASES + CUSTOMER_CREDENTIAL_REQUIRED_CASES
)
