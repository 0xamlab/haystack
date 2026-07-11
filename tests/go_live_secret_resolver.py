from __future__ import annotations

import os
from collections.abc import MutableMapping
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
KEYS_PATH = ROOT / "keys.txt"

GO_LIVE_ENV_FALLBACKS: dict[str, tuple[str, ...]] = {
    "DE_TEST_FRED_API_KEY": ("FRED_API_KEY",),
    "DE_TEST_FRED_SERIES_ID": ("FRED_SERIES_ID",),
    "DE_TEST_GITHUB_TOKEN": ("GITHUB_TOKEN", "GH_TOKEN"),
    "DE_TEST_S3_BUCKET": ("S3_BUCKET",),
    "DE_TEST_S3_KEY": ("S3_KEY",),
    "DE_TEST_S3_ACCESS_KEY_ID": ("S3_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID"),
    "DE_TEST_S3_SECRET_ACCESS_KEY": ("S3_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY"),
    "DE_TEST_S3_ENDPOINT_URL": ("S3_ENDPOINT_URL",),
    "DE_TEST_S3_REGION": ("S3_REGION", "AWS_REGION", "AWS_DEFAULT_REGION"),
    "DE_TEST_S3_FILE_TYPE": ("S3_FILE_TYPE",),
    "DE_TEST_GCS_BUCKET": ("GCS_BUCKET",),
    "DE_TEST_GCS_BLOB": ("GCS_BLOB",),
    "DE_TEST_GCS_CREDENTIALS": (
        "GCS_CREDENTIALS",
        "GOOGLE_APPLICATION_CREDENTIALS_JSON",
        "GCP_SERVICE_ACCOUNT_JSON",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ),
    "DE_TEST_GCS_PROJECT_ID": ("GCS_PROJECT_ID", "GOOGLE_CLOUD_PROJECT", "GCP_PROJECT_ID"),
    "DE_TEST_GCS_FILE_TYPE": ("GCS_FILE_TYPE",),
    "DE_TEST_AZURE_CONNECTION_STRING": ("AZURE_CONNECTION_STRING",),
    "DE_TEST_AZURE_ACCOUNT_URL": ("AZURE_ACCOUNT_URL",),
    "DE_TEST_AZURE_CONTAINER": ("AZURE_CONTAINER",),
    "DE_TEST_AZURE_BLOB": ("AZURE_BLOB",),
    "DE_TEST_AZURE_BLOB_URL": ("AZURE_BLOB_URL",),
    "DE_TEST_AZURE_FILE_TYPE": ("AZURE_FILE_TYPE",),
    "DE_TEST_CLICKHOUSE_URL": ("CLICKHOUSE_URL",),
    "DE_TEST_CLICKHOUSE_USER": ("CLICKHOUSE_USER",),
    "DE_TEST_CLICKHOUSE_PASSWORD": ("CLICKHOUSE_PASSWORD",),
    "DE_TEST_CLICKHOUSE_DATABASE": ("CLICKHOUSE_DATABASE",),
    "DE_TEST_CLICKHOUSE_QUERY": ("CLICKHOUSE_QUERY",),
    "DE_TEST_CLICKHOUSE_TABLE": ("CLICKHOUSE_TABLE",),
    "DE_TEST_CLICKHOUSE_LIMIT": ("CLICKHOUSE_LIMIT",),
    "DE_TEST_ELASTICSEARCH_URL": ("ELASTICSEARCH_URL", "ELASTIC_URL"),
    "DE_TEST_ELASTICSEARCH_API_KEY": ("ELASTICSEARCH_API_KEY", "ELASTIC_API_KEY"),
    "DE_TEST_ELASTICSEARCH_INDEX": ("ELASTICSEARCH_INDEX", "ELASTIC_INDEX"),
    "DE_TEST_ELASTICSEARCH_QUERY": ("ELASTICSEARCH_QUERY",),
    "DE_TEST_ELASTICSEARCH_LIMIT": ("ELASTICSEARCH_LIMIT",),
    "DE_TEST_NEO4J_URI": ("NEO4J_URI", "NEO4J_URL"),
    "DE_TEST_NEO4J_USERNAME": ("NEO4J_USERNAME", "NEO4J_USER"),
    "DE_TEST_NEO4J_PASSWORD": ("NEO4J_PASSWORD",),
    "DE_TEST_NEO4J_DATABASE": ("NEO4J_DATABASE",),
    "DE_TEST_REDIS_URL": ("REDIS_URL",),
    "DE_TEST_SNOWFLAKE_ACCOUNT": ("SNOWFLAKE_ACCOUNT",),
    "DE_TEST_SNOWFLAKE_USER": ("SNOWFLAKE_USER",),
    "DE_TEST_SNOWFLAKE_PASSWORD": (
        "SNOWFLAKE_PASSWORD",
        "SNOWFLAKE_PAT",
        "SNOWFLAKE_ACCESS_TOKEN",
        "SNOWFLAKE_PROGRAMMATIC_ACCESS_TOKEN",
    ),
    "DE_TEST_SNOWFLAKE_WAREHOUSE": ("SNOWFLAKE_WAREHOUSE",),
    "DE_TEST_SNOWFLAKE_DATABASE": ("SNOWFLAKE_DATABASE",),
    "DE_TEST_SNOWFLAKE_SCHEMA": ("SNOWFLAKE_SCHEMA",),
    "DE_TEST_SNOWFLAKE_QUERY": ("SNOWFLAKE_QUERY",),
    "DE_TEST_SNOWFLAKE_TABLE": ("SNOWFLAKE_TABLE",),
    "DE_TEST_SNOWFLAKE_LIMIT": ("SNOWFLAKE_LIMIT",),
    "DE_TEST_BIGQUERY_PROJECT_ID": (
        "BIGQUERY_PROJECT_ID",
        "GOOGLE_CLOUD_PROJECT",
        "GCP_PROJECT_ID",
    ),
    "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": (
        "BIGQUERY_SERVICE_ACCOUNT_JSON",
        "GOOGLE_APPLICATION_CREDENTIALS_JSON",
        "GCP_SERVICE_ACCOUNT_JSON",
        "GOOGLE_APPLICATION_CREDENTIALS",
    ),
    "DE_TEST_BIGQUERY_QUERY": ("BIGQUERY_QUERY",),
    "DE_TEST_BIGQUERY_DATASET": ("BIGQUERY_DATASET",),
    "DE_TEST_BIGQUERY_TABLE": ("BIGQUERY_TABLE",),
    "DE_TEST_BIGQUERY_LIMIT": ("BIGQUERY_LIMIT",),
    "DE_TEST_ORACLE_USER": ("ORACLE_USER",),
    "DE_TEST_ORACLE_PASSWORD": ("ORACLE_PASSWORD",),
    "DE_TEST_ORACLE_DSN": ("ORACLE_DSN",),
    "DE_TEST_ORACLE_HOST": ("ORACLE_HOST",),
    "DE_TEST_ORACLE_PORT": ("ORACLE_PORT",),
    "DE_TEST_ORACLE_CONFIG_DIR": ("ORACLE_CONFIG_DIR", "TNS_ADMIN"),
    "DE_TEST_ORACLE_WALLET_LOCATION": ("ORACLE_WALLET_LOCATION",),
    "DE_TEST_ORACLE_WALLET_PASSWORD": ("ORACLE_WALLET_PASSWORD",),
    "DE_TEST_ORACLE_SCHEMA": ("ORACLE_SCHEMA",),
    "DE_TEST_ORACLE_QUERY": ("ORACLE_QUERY",),
    "DE_TEST_ORACLE_TABLE": ("ORACLE_TABLE",),
    "DE_TEST_ORACLE_LIMIT": ("ORACLE_LIMIT",),
}

_FILE_BACKED_JSON_ENV_NAMES = {
    "DE_TEST_GCS_CREDENTIALS",
    "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
}

_GROUP_REQUIREMENTS: dict[str, tuple[tuple[str, ...], ...]] = {
    "s3": (("DE_TEST_S3_BUCKET", "DE_TEST_S3_KEY"),),
    "gcs": (("DE_TEST_GCS_BUCKET", "DE_TEST_GCS_BLOB"),),
    "azure_blob": (
        ("DE_TEST_AZURE_BLOB_URL",),
        ("DE_TEST_AZURE_CONNECTION_STRING", "DE_TEST_AZURE_CONTAINER", "DE_TEST_AZURE_BLOB"),
        ("DE_TEST_AZURE_ACCOUNT_URL", "DE_TEST_AZURE_CONTAINER", "DE_TEST_AZURE_BLOB"),
    ),
    "clickhouse": (
        ("DE_TEST_CLICKHOUSE_URL", "DE_TEST_CLICKHOUSE_USER", "DE_TEST_CLICKHOUSE_PASSWORD"),
    ),
    "elasticsearch": (("DE_TEST_ELASTICSEARCH_URL", "DE_TEST_ELASTICSEARCH_API_KEY"),),
    "neo4j": (("DE_TEST_NEO4J_URI", "DE_TEST_NEO4J_USERNAME", "DE_TEST_NEO4J_PASSWORD"),),
    "redis": (("DE_TEST_REDIS_URL",),),
    "snowflake": (
        (
            "DE_TEST_SNOWFLAKE_ACCOUNT",
            "DE_TEST_SNOWFLAKE_USER",
            "DE_TEST_SNOWFLAKE_PASSWORD",
            "DE_TEST_SNOWFLAKE_WAREHOUSE",
        ),
    ),
    "bigquery": (("DE_TEST_BIGQUERY_PROJECT_ID", "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON"),),
    "oracle": (
        (
            "DE_TEST_ORACLE_USER",
            "DE_TEST_ORACLE_PASSWORD",
            "DE_TEST_ORACLE_DSN",
        ),
    ),
}

_GROUP_MEMBERS: dict[str, tuple[str, ...]] = {
    "s3": (
        "DE_TEST_S3_BUCKET",
        "DE_TEST_S3_KEY",
        "DE_TEST_S3_ACCESS_KEY_ID",
        "DE_TEST_S3_SECRET_ACCESS_KEY",
        "DE_TEST_S3_ENDPOINT_URL",
        "DE_TEST_S3_REGION",
        "DE_TEST_S3_FILE_TYPE",
    ),
    "gcs": (
        "DE_TEST_GCS_BUCKET",
        "DE_TEST_GCS_BLOB",
        "DE_TEST_GCS_CREDENTIALS",
        "DE_TEST_GCS_PROJECT_ID",
        "DE_TEST_GCS_FILE_TYPE",
    ),
    "azure_blob": (
        "DE_TEST_AZURE_CONNECTION_STRING",
        "DE_TEST_AZURE_ACCOUNT_URL",
        "DE_TEST_AZURE_CONTAINER",
        "DE_TEST_AZURE_BLOB",
        "DE_TEST_AZURE_BLOB_URL",
        "DE_TEST_AZURE_FILE_TYPE",
    ),
    "clickhouse": (
        "DE_TEST_CLICKHOUSE_URL",
        "DE_TEST_CLICKHOUSE_USER",
        "DE_TEST_CLICKHOUSE_PASSWORD",
        "DE_TEST_CLICKHOUSE_DATABASE",
        "DE_TEST_CLICKHOUSE_QUERY",
        "DE_TEST_CLICKHOUSE_TABLE",
        "DE_TEST_CLICKHOUSE_LIMIT",
    ),
    "elasticsearch": (
        "DE_TEST_ELASTICSEARCH_URL",
        "DE_TEST_ELASTICSEARCH_API_KEY",
        "DE_TEST_ELASTICSEARCH_INDEX",
        "DE_TEST_ELASTICSEARCH_QUERY",
        "DE_TEST_ELASTICSEARCH_LIMIT",
    ),
    "neo4j": (
        "DE_TEST_NEO4J_URI",
        "DE_TEST_NEO4J_USERNAME",
        "DE_TEST_NEO4J_PASSWORD",
        "DE_TEST_NEO4J_DATABASE",
    ),
    "redis": ("DE_TEST_REDIS_URL",),
    "snowflake": (
        "DE_TEST_SNOWFLAKE_ACCOUNT",
        "DE_TEST_SNOWFLAKE_USER",
        "DE_TEST_SNOWFLAKE_PASSWORD",
        "DE_TEST_SNOWFLAKE_WAREHOUSE",
        "DE_TEST_SNOWFLAKE_DATABASE",
        "DE_TEST_SNOWFLAKE_SCHEMA",
        "DE_TEST_SNOWFLAKE_QUERY",
        "DE_TEST_SNOWFLAKE_TABLE",
        "DE_TEST_SNOWFLAKE_LIMIT",
    ),
    "bigquery": (
        "DE_TEST_BIGQUERY_PROJECT_ID",
        "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
        "DE_TEST_BIGQUERY_QUERY",
        "DE_TEST_BIGQUERY_DATASET",
        "DE_TEST_BIGQUERY_TABLE",
        "DE_TEST_BIGQUERY_LIMIT",
    ),
    "oracle": (
        "DE_TEST_ORACLE_USER",
        "DE_TEST_ORACLE_PASSWORD",
        "DE_TEST_ORACLE_DSN",
        "DE_TEST_ORACLE_HOST",
        "DE_TEST_ORACLE_PORT",
        "DE_TEST_ORACLE_CONFIG_DIR",
        "DE_TEST_ORACLE_WALLET_LOCATION",
        "DE_TEST_ORACLE_WALLET_PASSWORD",
        "DE_TEST_ORACLE_SCHEMA",
        "DE_TEST_ORACLE_QUERY",
        "DE_TEST_ORACLE_TABLE",
        "DE_TEST_ORACLE_LIMIT",
    ),
}

_GROUP_BY_CANONICAL_NAME = {
    canonical_name: group_name
    for group_name, members in _GROUP_MEMBERS.items()
    for canonical_name in members
}


def load_keys_txt_assignments(path: Path | None = None) -> dict[str, str]:
    target_path = KEYS_PATH if path is None else path
    if not target_path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in target_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        name = key.strip()
        if not name:
            continue
        value = raw_value.strip().strip('"').strip("'")
        if value:
            values[name] = value
    return values


def _normalize_file_backed_json_value(raw_value: str) -> str:
    candidate = Path(raw_value).expanduser()
    if candidate.exists() and candidate.is_file():
        return candidate.read_text(encoding="utf-8").strip()
    return raw_value


def _resolve_candidate_value(
    canonical_name: str,
    *,
    target_env: MutableMapping[str, str],
    keys_values: dict[str, str],
) -> str:
    candidates = (canonical_name, *GO_LIVE_ENV_FALLBACKS.get(canonical_name, ()))
    for name in candidates:
        value = str(target_env.get(name, "")).strip()
        if not value:
            continue
        if _candidate_value_is_usable(canonical_name, name, value):
            break
    else:
        value = ""
        for name in candidates:
            candidate_value = str(keys_values.get(name, "")).strip()
            if not candidate_value:
                continue
            if not _candidate_value_is_usable(canonical_name, name, candidate_value):
                continue
            value = candidate_value
            break
    if canonical_name in _FILE_BACKED_JSON_ENV_NAMES and value:
        return _normalize_file_backed_json_value(value)
    return value


def _candidate_value_is_usable(canonical_name: str, candidate_name: str, value: str) -> bool:
    if canonical_name != "DE_TEST_REDIS_URL" or candidate_name == canonical_name:
        return True
    parsed = urlparse(value)
    return parsed.username is not None or parsed.password is not None


def _group_is_ready(
    group_name: str,
    *,
    target_env: MutableMapping[str, str],
    resolved_values: dict[str, str],
) -> bool:
    requirement_sets = _GROUP_REQUIREMENTS[group_name]
    for requirement in requirement_sets:
        if all(
            str(target_env.get(name, "")).strip() or str(resolved_values.get(name, "")).strip()
            for name in requirement
        ):
            return True
    return False


def populate_go_live_test_env_from_keys_txt(
    *,
    environ: MutableMapping[str, str] | None = None,
    keys_path: Path | None = None,
) -> dict[str, str]:
    target_env = os.environ if environ is None else environ
    keys_values = load_keys_txt_assignments(keys_path)
    resolved_values = {
        canonical_name: _resolve_candidate_value(
            canonical_name,
            target_env=target_env,
            keys_values=keys_values,
        )
        for canonical_name in GO_LIVE_ENV_FALLBACKS
    }
    applied: dict[str, str] = {}
    for canonical_name in GO_LIVE_ENV_FALLBACKS:
        if str(target_env.get(canonical_name, "")).strip():
            continue
        group_name = _GROUP_BY_CANONICAL_NAME.get(canonical_name)
        if group_name is not None and not _group_is_ready(
            group_name,
            target_env=target_env,
            resolved_values=resolved_values,
        ):
            continue
        resolved = resolved_values[canonical_name]
        if not resolved:
            continue
        target_env[canonical_name] = resolved
        applied[canonical_name] = resolved
    return applied


def describe_go_live_env_resolution(canonical_name: str) -> dict[str, object]:
    normalized_name = str(canonical_name).strip()
    fallback_aliases = list(GO_LIVE_ENV_FALLBACKS.get(normalized_name, ()))
    group_name = _GROUP_BY_CANONICAL_NAME.get(normalized_name)
    resolver_supported = normalized_name in GO_LIVE_ENV_FALLBACKS
    candidate_names = [normalized_name]
    if resolver_supported:
        candidate_names.extend(fallback_aliases)
    return {
        "canonical_name": normalized_name,
        "resolver_supported": resolver_supported,
        "manual_only": not resolver_supported,
        "fallback_aliases": fallback_aliases,
        "candidate_names": candidate_names,
        "group_name": group_name,
    }
