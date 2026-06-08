from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
import time
from contextlib import AbstractContextManager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import httpx
import requests
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from requests.auth import HTTPBasicAuth

from apps.api_server.connectors.sql_connector import SQLConnector
from apps.api_server.services.connectors.tester import classify_connector_failure
from tests.go_live_behavior_contract import schema_fingerprint
from tests.go_live_fivetran_inventory import (
    BASELINE_LOCK_PATH,
    MANIFEST_EXAMPLE_PATH,
    ROOT,
    ensure_inventory_and_selection_locks_are_consistent,
    load_json,
)
from tests.go_live_secret_resolver import load_keys_txt_assignments
from tests.integration import connector_validation_catalog as validation_catalog
from tests.integration import test_go_live_connectivity_real as connectivity

DestinationName = Literal["snowflake", "bigquery"]
VerificationState = Literal["pass", "fail", "blocked"]

FIVETRAN_API_BASE = "https://api.fivetran.com/v1"
FIVETRAN_REQUIRED_ENVS = (
    "DE_TEST_FIVETRAN_API_KEY",
    "DE_TEST_FIVETRAN_API_SECRET",
)
FIVETRAN_ENV_FALLBACKS = {
    "DE_TEST_FIVETRAN_API_KEY": ("FIVETRAN_SYSTEM_KEY",),
    "DE_TEST_FIVETRAN_API_SECRET": ("FIVETRAN_SYSTEM_KEY_SECRET",),
}
DEFAULT_MINIMUM_EXPECTED_RATIO = 0.8
DEFAULT_MINIMUM_ROW_COUNT = 1
BASELINE_REFRESH_SLEEP_SECONDS = 300
MANIFEST_ENTRY_METADATA_FIELDS = (
    "family",
    "docs_path",
    "release_class",
    "plan_class",
    "classification_confidence",
    "schema_complexity",
    "join_complexity",
    "selection_bucket",
    "source_type",
    "nested_json",
    "wide_table",
    "high_churn_rest",
    "append_only_event",
)


class FivetranManifestDestination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connection_id: str = Field(min_length=1)
    query: str | None = None
    table: str | None = None
    expected_core_tables: list[str] = Field(min_length=1)
    identity_columns: list[str] = Field(default_factory=list)
    minimum_row_count: int = Field(default=DEFAULT_MINIMUM_ROW_COUNT, ge=1)
    max_data_lag_minutes: int = Field(gt=0)
    minimum_expected_ratio: float = Field(default=DEFAULT_MINIMUM_EXPECTED_RATIO, gt=0, le=1)

    @model_validator(mode="after")
    def _validate_query_or_table(self) -> FivetranManifestDestination:
        has_query = bool((self.query or "").strip())
        has_table = bool((self.table or "").strip())
        if has_query == has_table:
            raise ValueError("Exactly one of query or table must be provided.")
        cleaned_tables = [table.strip() for table in self.expected_core_tables if table.strip()]
        if not cleaned_tables:
            raise ValueError(
                "expected_core_tables must contain at least one non-empty table identifier."
            )
        self.expected_core_tables = cleaned_tables
        self.identity_columns = [value.strip() for value in self.identity_columns if value.strip()]
        if self.query is not None:
            self.query = self.query.strip()
        if self.table is not None:
            self.table = self.table.strip()
        return self


class FivetranManifestEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    connector_slug: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    family: str = Field(min_length=1)
    docs_path: str = Field(min_length=1)
    release_class: str = Field(min_length=1)
    plan_class: str = Field(min_length=1)
    classification_confidence: str = Field(min_length=1)
    schema_complexity: str = Field(min_length=1)
    join_complexity: str = Field(min_length=1)
    selection_bucket: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    nested_json: bool
    wide_table: bool
    high_churn_rest: bool
    append_only_event: bool
    snowflake: FivetranManifestDestination
    bigquery: FivetranManifestDestination


class FivetranManifestDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inventory_version: str = Field(min_length=1)
    selection_version: str = Field(min_length=1)
    connectors: list[FivetranManifestEntry]


@dataclass(frozen=True)
class DestinationEvaluation:
    destination_name: DestinationName
    connection_id: str
    state: VerificationState
    reasons: tuple[str, ...]
    placeholder_fields: tuple[str, ...] = ()
    freshness_lag_minutes: float | None = None
    row_count: int | None = None
    baseline_row_count: int | None = None
    observed_ratio: float | None = None
    minimum_expected_ratio: float | None = None
    behavior_summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConnectorEvaluation:
    connector_slug: str
    display_name: str
    state: VerificationState
    destinations: tuple[DestinationEvaluation, DestinationEvaluation]

    def to_dict(self) -> dict[str, Any]:
        return {
            "connector_slug": self.connector_slug,
            "display_name": self.display_name,
            "state": self.state,
            "destinations": [destination.to_dict() for destination in self.destinations],
        }


class FivetranVerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class FivetranCredentialResolution:
    api_key: str
    api_secret: str
    key_source: str
    secret_source: str


@dataclass(frozen=True)
class FivetranLiveConnectionCandidate:
    connector_slug: str | None
    connection_id: str
    destination_name: DestinationName | None
    raw_service: str | None = None
    raw_destination_service: str | None = None
    group_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _utc_now_iso() -> str:
    return _utc_now().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _stable_json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _stable_hash(value: Any) -> str:
    import hashlib

    return hashlib.sha256(_stable_json_dumps(value).encode("utf-8")).hexdigest()


def _extract_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data", {})
    if isinstance(data, dict):
        items = data.get("items", [])
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    return []


def _coerce_identifier(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_fivetran_token(value: str | None) -> str:
    if value is None:
        return ""
    normalized = "".join(
        character if character.isalnum() else "-" for character in value.strip().lower()
    )
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized.strip("-")


def _extract_destination_name(payload: dict[str, Any]) -> DestinationName | None:
    config = payload.get("config")
    config_service = config.get("service") if isinstance(config, dict) else None
    for raw_value in (
        payload.get("service"),
        payload.get("destination_service"),
        payload.get("type"),
        config_service,
    ):
        normalized = _normalize_fivetran_token(_coerce_identifier(raw_value))
        if normalized == "snowflake":
            return "snowflake"
        if normalized in {"bigquery", "google-bigquery", "google-big-query"}:
            return "bigquery"
    return None


def _extract_connection_slug(payload: dict[str, Any]) -> str | None:
    config = payload.get("config")
    config_service = config.get("service") if isinstance(config, dict) else None
    for raw_value in (
        payload.get("service"),
        payload.get("connector_type"),
        payload.get("source_service"),
        config_service,
    ):
        normalized = _normalize_fivetran_token(_coerce_identifier(raw_value))
        if normalized:
            return normalized
    return None


def _normalize_placeholder(value: str) -> str:
    return value.strip().upper()


def _is_placeholder(value: str) -> bool:
    normalized = _normalize_placeholder(value)
    return not normalized or normalized.startswith("__REPLACE_WITH_")


def _manifest_version(payload: dict[str, Any]) -> str:
    return _stable_hash(payload)


def build_empty_baseline_lock() -> dict[str, Any]:
    return {
        "generated_at": _utc_now_iso(),
        "baseline_version": _stable_hash([]),
        "entries": [],
    }


def validate_baseline_lock_payload(payload: dict[str, Any]) -> None:
    expected_hash = _stable_hash(payload.get("entries", []))
    actual_hash = str(payload.get("baseline_version", "")).strip()
    if expected_hash != actual_hash:
        raise FivetranVerificationError(
            f"Baseline lock hash mismatch: expected {expected_hash}, found {actual_hash or '<missing>'}."
        )


def ensure_baseline_lock() -> dict[str, Any]:
    if not BASELINE_LOCK_PATH.exists():
        payload = build_empty_baseline_lock()
        BASELINE_LOCK_PATH.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return payload
    payload = load_json(BASELINE_LOCK_PATH)
    validate_baseline_lock_payload(payload)
    return payload


def load_manifest(path: Path) -> tuple[Path, FivetranManifestDocument, dict[str, Any], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    document = FivetranManifestDocument.model_validate(payload)
    return path, document, payload, _manifest_version(payload)


def _manifest_metadata_from_selection_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "connector_slug": str(entry["connector_slug"]),
        "display_name": str(entry["display_name"]),
        **{field_name: entry[field_name] for field_name in MANIFEST_ENTRY_METADATA_FIELDS},
    }


def validate_manifest_against_selection_lock(
    document: FivetranManifestDocument,
    *,
    inventory_lock: dict[str, Any],
    selection_lock: dict[str, Any],
) -> None:
    expected_inventory_version = str(inventory_lock["inventory_version"])
    expected_selection_version = str(selection_lock["selection_version"])
    if document.inventory_version != expected_inventory_version:
        raise FivetranVerificationError(
            "Manifest inventory_version does not match the frozen inventory lock."
        )
    if document.selection_version != expected_selection_version:
        raise FivetranVerificationError(
            "Manifest selection_version does not match the frozen selection lock."
        )

    expected_entries = [
        _manifest_metadata_from_selection_entry(entry)
        for entry in selection_lock["selected_connectors"]
    ]
    manifest_entries = [
        {
            "connector_slug": entry.connector_slug,
            "display_name": entry.display_name,
            **{
                field_name: getattr(entry, field_name)
                for field_name in MANIFEST_ENTRY_METADATA_FIELDS
            },
        }
        for entry in document.connectors
    ]
    if manifest_entries != expected_entries:
        raise FivetranVerificationError(
            "Manifest connector metadata or ordering drifted from the frozen top-20 selection."
        )


def _filter_selected_connectors(
    selection_entries: list[dict[str, Any]],
    connector_slugs: tuple[str, ...] | None,
) -> list[dict[str, Any]]:
    if connector_slugs is None:
        return list(selection_entries)
    selection_by_slug = {str(entry["connector_slug"]): entry for entry in selection_entries}
    missing = [
        connector_slug
        for connector_slug in connector_slugs
        if connector_slug not in selection_by_slug
    ]
    if missing:
        raise FivetranVerificationError(
            "Requested connectors are not part of the frozen top-20 selection: "
            + ", ".join(sorted(missing))
        )
    return [selection_by_slug[connector_slug] for connector_slug in connector_slugs]


def build_example_manifest(selection_lock: dict[str, Any]) -> dict[str, Any]:
    connectors: list[dict[str, Any]] = []
    for entry in selection_lock["selected_connectors"]:
        slug = str(entry["connector_slug"])
        display_name = str(entry["display_name"])
        connectors.append(
            {
                "connector_slug": slug,
                "display_name": display_name,
                **{field_name: entry[field_name] for field_name in MANIFEST_ENTRY_METADATA_FIELDS},
                "snowflake": {
                    "connection_id": "__REPLACE_WITH_SNOWFLAKE_CONNECTION_ID__",
                    "table": "__REPLACE_WITH_SNOWFLAKE_TABLE__",
                    "expected_core_tables": ["__REPLACE_WITH_SNOWFLAKE_TABLE__"],
                    "identity_columns": [],
                    "minimum_row_count": 1,
                    "max_data_lag_minutes": 60,
                    "minimum_expected_ratio": 0.8,
                },
                "bigquery": {
                    "connection_id": "__REPLACE_WITH_BIGQUERY_CONNECTION_ID__",
                    "table": "__REPLACE_WITH_BIGQUERY_TABLE__",
                    "expected_core_tables": ["__REPLACE_WITH_BIGQUERY_TABLE__"],
                    "identity_columns": [],
                    "minimum_row_count": 1,
                    "max_data_lag_minutes": 60,
                    "minimum_expected_ratio": 0.8,
                },
            }
        )
    return {
        "inventory_version": str(selection_lock["inventory_version"]),
        "selection_version": str(selection_lock["selection_version"]),
        "connectors": connectors,
    }


def sync_example_manifest_from_selection(selection_lock: dict[str, Any]) -> dict[str, Any]:
    payload = build_example_manifest(selection_lock)
    MANIFEST_EXAMPLE_PATH.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return payload


def resolve_manifest_path() -> Path:
    raw = str(validation_catalog.os.environ.get("DE_TEST_FIVETRAN_MANIFEST_PATH", "")).strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return MANIFEST_EXAMPLE_PATH


def _resolve_fivetran_api_credentials() -> FivetranCredentialResolution | None:
    env = validation_catalog.os.environ
    keys_values = load_keys_txt_assignments()

    def _resolve_value(canonical_name: str) -> tuple[str | None, str | None]:
        candidates = (canonical_name, *FIVETRAN_ENV_FALLBACKS.get(canonical_name, ()))
        for name in candidates:
            value = str(env.get(name, "")).strip()
            if value:
                return value, f"env:{name}"
        for name in candidates:
            value = str(keys_values.get(name, "")).strip()
            if value:
                return value, f"keys.txt:{name}"
        return None, None

    api_key, key_source = _resolve_value("DE_TEST_FIVETRAN_API_KEY")
    api_secret, secret_source = _resolve_value("DE_TEST_FIVETRAN_API_SECRET")
    if not api_key or not api_secret or not key_source or not secret_source:
        return None
    return FivetranCredentialResolution(
        api_key=api_key,
        api_secret=api_secret,
        key_source=key_source,
        secret_source=secret_source,
    )


def required_fivetran_envs_missing() -> tuple[str, ...]:
    if _resolve_fivetran_api_credentials() is not None:
        return ()
    return FIVETRAN_REQUIRED_ENVS


def _parse_timestamp(raw: str) -> datetime:
    normalized = raw.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return datetime.fromisoformat(normalized).astimezone(UTC)


def _extract_connection_payload(response_payload: dict[str, Any]) -> dict[str, Any]:
    data = response_payload.get("data")
    if isinstance(data, dict):
        return data
    return response_payload


def _extract_last_successful_sync(payload: dict[str, Any]) -> datetime | None:
    candidates = (
        payload.get("succeeded_at"),
        payload.get("sync_state_details", {}).get("succeeded_at")
        if isinstance(payload.get("sync_state_details"), dict)
        else None,
        payload.get("status", {}).get("succeeded_at")
        if isinstance(payload.get("status"), dict)
        else None,
    )
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return _parse_timestamp(candidate)
    return None


def _preflight_state_markers(payload: dict[str, Any]) -> set[str]:
    markers: set[str] = set()
    status_payload = payload.get("status")
    if isinstance(status_payload, dict):
        for key in ("setup_state", "sync_state", "schema_status"):
            value = str(status_payload.get(key, "")).strip().lower()
            if value:
                markers.add(value)
    for key in ("setup_state", "sync_state", "schema_status"):
        value = str(payload.get(key, "")).strip().lower()
        if value:
            markers.add(value)
    if payload.get("paused") is True:
        markers.add("paused")
    if payload.get("is_historical_sync") is True:
        markers.add("historical")
    return markers


def _classify_destination_exception(exc: BaseException) -> VerificationState:
    message = str(exc)
    error_type, _recoverable = classify_connector_failure(message=message, exception=exc)
    blocked_markers = (
        "warehouse is suspended",
        "quota exceeded",
        "temporarily unavailable",
        "service unavailable",
        "backend error",
        "billingnotenabled",
        "exceeded rate limits",
    )
    lower = message.lower()
    if error_type in {"timeout", "rate_limit", "auth", "permission"}:
        return "blocked"
    if any(marker in lower for marker in blocked_markers):
        return "blocked"
    return "fail"


def _build_dataset_query(destination: FivetranManifestDestination) -> str:
    if destination.query:
        return destination.query.strip().rstrip(";")
    assert destination.table is not None
    return f"SELECT * FROM {destination.table} ORDER BY 1"


def _build_count_query(destination: FivetranManifestDestination) -> str:
    return f"SELECT COUNT(*) AS algenta_row_count FROM ({_build_dataset_query(destination)}) AS algenta_fivetran_count"


def _build_exists_query(table_identifier: str) -> str:
    return f"SELECT 1 AS algenta_exists_probe FROM {table_identifier} LIMIT 1"


def _run_sql_records(connection: dict[str, Any]) -> list[dict[str, Any]]:
    return asyncio.run(SQLConnector(connection).fetch_data())


def _run_sql_schema_columns(connection: dict[str, Any]) -> list[dict[str, str]]:
    table = asyncio.run(SQLConnector(connection).fetch_table())
    if table is None:
        return []
    return [
        {
            "name": str(field.name),
            "physical_type": str(field.type),
        }
        for field in table.schema
    ]


def _warehouse_connection(
    destination_name: DestinationName,
    destination: FivetranManifestDestination,
) -> dict[str, Any]:
    if destination_name == "snowflake":
        account = str(validation_catalog.os.environ.get("DE_TEST_SNOWFLAKE_ACCOUNT", "")).strip()
        user = validation_catalog.quote(
            str(validation_catalog.os.environ.get("DE_TEST_SNOWFLAKE_USER", "")).strip(),
            safe="",
        )
        password = validation_catalog.quote(
            str(validation_catalog.os.environ.get("DE_TEST_SNOWFLAKE_PASSWORD", "")).strip(),
            safe="",
        )
        warehouse = str(
            validation_catalog.os.environ.get("DE_TEST_SNOWFLAKE_WAREHOUSE", "")
        ).strip()
        database = str(
            validation_catalog.os.environ.get("DE_TEST_SNOWFLAKE_DATABASE", "SNOWFLAKE_SAMPLE_DATA")
        ).strip()
        schema = str(
            validation_catalog.os.environ.get("DE_TEST_SNOWFLAKE_SCHEMA", "PUBLIC")
        ).strip()
        connection_string = f"snowflake://{user}:{password}@{account}/{database}/{schema}"
        if warehouse:
            connection_string += f"?warehouse={validation_catalog.quote(warehouse, safe='')}"
        return {
            "type": "sql",
            "connection_string": connection_string,
            "query": _build_dataset_query(destination),
            "limit": 100,
        }
    project_id = str(validation_catalog.os.environ.get("DE_TEST_BIGQUERY_PROJECT_ID", "")).strip()
    return {
        "type": "sql",
        "connection_string": f"bigquery://{project_id}",
        "query": _build_dataset_query(destination),
        "limit": 100,
    }


def _count_rows_for_destination(
    destination_name: DestinationName,
    destination: FivetranManifestDestination,
) -> int:
    connection = _warehouse_connection(destination_name, destination)
    connection["query"] = _build_count_query(destination)
    records = _run_sql_records(connection)
    if not records:
        raise FivetranVerificationError(
            f"{destination_name} row-count probe returned no rows for {destination.connection_id}."
        )
    raw_value = records[0].get("algenta_row_count")
    return int(raw_value)


def _sample_records_for_destination(
    destination_name: DestinationName,
    destination: FivetranManifestDestination,
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    connection = _warehouse_connection(destination_name, destination)
    records = _run_sql_records(connection)
    schema_columns = _run_sql_schema_columns(connection)
    if not schema_columns and records:
        schema_columns = connectivity._schema_columns_from_records(records)
    return records, schema_columns


def _check_expected_core_tables(
    destination_name: DestinationName,
    destination: FivetranManifestDestination,
) -> None:
    errors: list[str] = []
    for table_identifier in destination.expected_core_tables:
        connection = _warehouse_connection(destination_name, destination)
        connection["query"] = _build_exists_query(table_identifier)
        try:
            records = _run_sql_records(connection)
            if records:
                return
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))
    raise FivetranVerificationError(
        f"{destination_name} expected_core_tables were not readable: {', '.join(destination.expected_core_tables)}"
        + (f" ({'; '.join(errors)})" if errors else "")
    )


class FivetranApiClient:
    def __init__(self, api_key: str, api_secret: str) -> None:
        self._session = requests.Session()
        self._session.auth = HTTPBasicAuth(api_key, api_secret)
        self._session.headers.update({"Accept": "application/json;version=2"})

    def close(self) -> None:
        self._session.close()

    def _get(self, path: str) -> dict[str, Any]:
        response = self._session.get(
            f"{FIVETRAN_API_BASE}{path}",
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def connection_details(self, connection_id: str) -> dict[str, Any]:
        return self._get(f"/connections/{connection_id}")

    def list_groups(self) -> list[dict[str, Any]]:
        return _extract_items(self._get("/groups?limit=1000"))

    def list_destinations(self) -> list[dict[str, Any]]:
        return _extract_items(self._get("/destinations?limit=1000"))

    def list_connections(self) -> list[dict[str, Any]]:
        return _extract_items(self._get("/connections?limit=1000"))

    def account_summary(self) -> dict[str, int]:
        return {
            "groups": len(self.list_groups()),
            "destinations": len(self.list_destinations()),
            "connections": len(self.list_connections()),
        }


def discover_live_connection_candidates(
    *,
    api_client: FivetranApiClient,
    selected_connector_slugs: list[str],
) -> dict[str, Any]:
    selected_by_normalized = {
        _normalize_fivetran_token(slug): slug for slug in selected_connector_slugs
    }
    destinations = api_client.list_destinations()
    destination_name_by_identifier: dict[str, DestinationName] = {}
    raw_destination_service_by_identifier: dict[str, str | None] = {}
    for destination in destinations:
        destination_name = _extract_destination_name(destination)
        if destination_name is None:
            continue
        raw_service = (
            _coerce_identifier(destination.get("service"))
            or _coerce_identifier(destination.get("destination_service"))
            or _coerce_identifier(destination.get("type"))
        )
        for candidate_key in (
            destination.get("id"),
            destination.get("group_id"),
            destination.get("destination_id"),
        ):
            identifier = _coerce_identifier(candidate_key)
            if identifier is None:
                continue
            destination_name_by_identifier[identifier] = destination_name
            raw_destination_service_by_identifier[identifier] = raw_service

    matches_by_key: dict[tuple[str, DestinationName], list[FivetranLiveConnectionCandidate]] = {}
    unmatched_candidates: list[FivetranLiveConnectionCandidate] = []
    for connection in api_client.list_connections():
        connection_id = _coerce_identifier(connection.get("id") or connection.get("connection_id"))
        if connection_id is None:
            continue
        normalized_service = _extract_connection_slug(connection)
        connector_slug = selected_by_normalized.get(normalized_service or "")
        group_id = _coerce_identifier(
            connection.get("group_id") or connection.get("destination_id")
        )
        destination_name = None
        raw_destination_service = None
        if group_id is not None:
            destination_name = destination_name_by_identifier.get(group_id)
            raw_destination_service = raw_destination_service_by_identifier.get(group_id)
        candidate = FivetranLiveConnectionCandidate(
            connector_slug=connector_slug,
            connection_id=connection_id,
            destination_name=destination_name,
            raw_service=_coerce_identifier(
                connection.get("service") or connection.get("connector_type")
            ),
            raw_destination_service=raw_destination_service,
            group_id=group_id,
        )
        if connector_slug is None or destination_name is None:
            unmatched_candidates.append(candidate)
            continue
        matches_by_key.setdefault((connector_slug, destination_name), []).append(candidate)

    matched_candidates = [
        candidate.to_dict()
        for key in sorted(matches_by_key)
        for candidate in sorted(matches_by_key[key], key=lambda value: value.connection_id)
    ]
    return {
        "matches": {
            f"{connector_slug}:{destination_name}": [
                candidate.to_dict()
                for candidate in sorted(candidates, key=lambda value: value.connection_id)
            ]
            for (connector_slug, destination_name), candidates in sorted(matches_by_key.items())
        },
        "matched_candidates": matched_candidates,
        "unmatched_candidates": [candidate.to_dict() for candidate in unmatched_candidates],
        "summary": {
            "matched_pairs": len(matches_by_key),
            "matched_candidates": len(matched_candidates),
            "unmatched_candidates": len(unmatched_candidates),
        },
    }


def inspect_live_fivetran_account(
    *,
    connector_slugs: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    _inventory_lock, selection_lock = ensure_inventory_and_selection_locks_are_consistent()
    selected_entries = _filter_selected_connectors(
        selection_lock["selected_connectors"],
        connector_slugs,
    )
    selected_connector_slugs = [str(entry["connector_slug"]) for entry in selected_entries]
    credential_resolution = _resolve_fivetran_api_credentials()
    missing_api_envs = required_fivetran_envs_missing()
    if credential_resolution is None or missing_api_envs:
        return {
            "connector_filter": list(connector_slugs or ()),
            "selected_connectors": selected_connector_slugs,
            "missing_api_envs": list(missing_api_envs),
            "api_credential_source": (
                {
                    "key": credential_resolution.key_source,
                    "secret": credential_resolution.secret_source,
                }
                if credential_resolution is not None
                else None
            ),
            "destinations": [],
            "connections": [],
            "candidate_matches": {},
            "unmatched_candidates": [],
        }

    api_client = FivetranApiClient(
        credential_resolution.api_key,
        credential_resolution.api_secret,
    )
    try:
        destinations = api_client.list_destinations()
        connections = api_client.list_connections()
        discovery = discover_live_connection_candidates(
            api_client=api_client,
            selected_connector_slugs=selected_connector_slugs,
        )
    finally:
        api_client.close()

    normalized_destinations: list[dict[str, Any]] = []
    for destination in destinations:
        normalized_destinations.append(
            {
                "id": _coerce_identifier(destination.get("id")),
                "group_id": _coerce_identifier(destination.get("group_id")),
                "service": _coerce_identifier(destination.get("service")),
                "destination_service": _coerce_identifier(destination.get("destination_service")),
                "type": _coerce_identifier(destination.get("type")),
                "destination_name": _extract_destination_name(destination),
            }
        )

    normalized_connections: list[dict[str, Any]] = []
    for connection in connections:
        normalized_connections.append(
            {
                "id": _coerce_identifier(connection.get("id") or connection.get("connection_id")),
                "group_id": _coerce_identifier(
                    connection.get("group_id") or connection.get("destination_id")
                ),
                "service": _coerce_identifier(connection.get("service")),
                "connector_slug": _extract_connection_slug(connection),
            }
        )

    return {
        "connector_filter": list(connector_slugs or ()),
        "selected_connectors": selected_connector_slugs,
        "missing_api_envs": [],
        "api_credential_source": {
            "key": credential_resolution.key_source,
            "secret": credential_resolution.secret_source,
        },
        "destinations": normalized_destinations,
        "connections": normalized_connections,
        "candidate_matches": discovery["matches"],
        "unmatched_candidates": discovery["unmatched_candidates"],
        "summary": {
            "destinations": len(normalized_destinations),
            "connections": len(normalized_connections),
            "matched_pairs": discovery["summary"]["matched_pairs"],
            "matched_candidates": discovery["summary"]["matched_candidates"],
            "unmatched_candidates": discovery["summary"]["unmatched_candidates"],
        },
    }


def hydrate_manifest_connection_ids_from_live_account(
    *,
    connector_slugs: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    inventory_lock, selection_lock = ensure_inventory_and_selection_locks_are_consistent()
    manifest_path, manifest_document, manifest_payload, _manifest_version = load_manifest(
        resolve_manifest_path()
    )
    validate_manifest_against_selection_lock(
        manifest_document,
        inventory_lock=inventory_lock,
        selection_lock=selection_lock,
    )
    selected_entries = _filter_selected_connectors(
        selection_lock["selected_connectors"], connector_slugs
    )
    selected_slug_set = {str(entry["connector_slug"]) for entry in selected_entries}
    missing_api_envs = required_fivetran_envs_missing()
    if missing_api_envs:
        raise FivetranVerificationError(
            "Manifest hydration requires Fivetran API envs: " + ", ".join(missing_api_envs)
        )
    credential_resolution = _resolve_fivetran_api_credentials()
    if credential_resolution is None:
        raise FivetranVerificationError(
            "Manifest hydration could not resolve Fivetran API credentials."
        )
    api_client = FivetranApiClient(
        credential_resolution.api_key,
        credential_resolution.api_secret,
    )
    try:
        discovery = discover_live_connection_candidates(
            api_client=api_client,
            selected_connector_slugs=[str(entry["connector_slug"]) for entry in selected_entries],
        )
    finally:
        api_client.close()
    updated_payload = json.loads(json.dumps(manifest_payload))
    hydrated_paths: list[str] = []
    unresolved_paths: list[str] = []
    for connector in updated_payload["connectors"]:
        connector_slug = str(connector["connector_slug"])
        if connector_slug not in selected_slug_set:
            continue
        for destination_name in ("snowflake", "bigquery"):
            destination = connector[destination_name]
            if not _is_placeholder(str(destination["connection_id"])):
                continue
            matches = discovery["matches"].get(f"{connector_slug}:{destination_name}", [])
            manifest_path_label = f"{connector_slug}.{destination_name}.connection_id"
            if len(matches) == 1:
                destination["connection_id"] = matches[0]["connection_id"]
                hydrated_paths.append(manifest_path_label)
                continue
            if matches:
                unresolved_paths.append(
                    f"{manifest_path_label} ambiguous: {', '.join(str(match['connection_id']) for match in matches)}"
                )
            else:
                unresolved_paths.append(f"{manifest_path_label} missing live match")
    changed = updated_payload != manifest_payload
    if changed:
        manifest_path.write_text(
            json.dumps(updated_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    remaining_placeholder_fields = [
        path
        for path in _manifest_placeholder_paths(updated_payload)
        if connector_slugs is None or path.split(".", 1)[0] in selected_slug_set
    ]
    return {
        "manifest_path": str(manifest_path),
        "changed": changed,
        "connector_filter": list(connector_slugs or ()),
        "hydrated_paths": hydrated_paths,
        "unresolved_paths": unresolved_paths,
        "remaining_placeholder_fields": remaining_placeholder_fields,
        "discovery": discovery,
        "api_credential_source": {
            "key": credential_resolution.key_source,
            "secret": credential_resolution.secret_source,
        },
    }


class _GoLiveApiHarness(AbstractContextManager["_GoLiveApiHarness"]):
    def __init__(self) -> None:
        self._tmp_root: Path | None = None
        self._api_server = None
        self.client: httpx.Client | None = None
        self.api_key: str | None = None
        self.api_port = connectivity.free_port()

    def __enter__(self) -> _GoLiveApiHarness:
        connectivity.ensure_port_open("127.0.0.1", 5432, "Postgres")
        connectivity.ensure_port_open("127.0.0.1", 6379, "Redis")
        connectivity.run_migrations(
            {
                "PYTHONPATH": str(ROOT),
                "DATABASE_URL": connectivity.DEFAULT_DB_URL,
                "DATABASE_URL_SYNC": connectivity.DEFAULT_DB_URL_SYNC,
                "REDIS_URL": connectivity.DEFAULT_REDIS_URL,
            }
        )
        self.api_key, _org_id = asyncio.run(connectivity.seed_api_key(connectivity.DEFAULT_DB_URL))
        self._tmp_root = Path(tempfile.mkdtemp(prefix="algenta-fivetran-"))
        sources_dir = self._tmp_root / "sources"
        env = {
            "API_ENV": "development",
            "DATABASE_URL": connectivity.DEFAULT_DB_URL,
            "DATABASE_URL_SYNC": connectivity.DEFAULT_DB_URL_SYNC,
            "DATABASE_READ_REPLICA_URL": connectivity.DEFAULT_DB_URL,
            "REDIS_URL": connectivity.DEFAULT_REDIS_URL,
            "ALGENTA_SOURCES_DIR": str(sources_dir),
        }
        bigquery_credentials_path = connectivity.materialize_bigquery_service_account_json(
            self._tmp_root
        )
        if bigquery_credentials_path is not None:
            env["GOOGLE_APPLICATION_CREDENTIALS"] = str(bigquery_credentials_path)
            validation_catalog.os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
                bigquery_credentials_path
            )
        self._api_server = connectivity.start_api_server(self.api_port, sources_dir, env)
        connectivity.wait_for_http(
            f"http://127.0.0.1:{self.api_port}/v1/health",
            timeout=90.0,
            proc=self._api_server,
            log_path=getattr(self._api_server, "algenta_log_path", None),
        )
        self.client = httpx.Client(base_url=f"http://127.0.0.1:{self.api_port}")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.client is not None:
            self.client.close()
        connectivity.stop_process(self._api_server)
        if self._tmp_root is not None:
            shutil.rmtree(self._tmp_root, ignore_errors=True)
        return None

    def create_connector(self, name: str, connector_type: str, config: dict[str, Any]) -> str:
        assert self.client is not None
        assert self.api_key is not None
        _status, body = connectivity.api_request(
            self.client,
            "POST",
            "/v1/connectors",
            api_key=self.api_key,
            json_body={
                "name": name,
                "connector_type": connector_type,
                "config": config,
            },
            expected_status=201,
        )
        return str(body["id"])


def _placeholder_fields(
    destination_name: DestinationName,
    destination: FivetranManifestDestination,
) -> tuple[str, ...]:
    prefix = f"{destination_name}."
    fields: list[str] = []
    if _is_placeholder(destination.connection_id):
        fields.append(f"{prefix}connection_id")
    if destination.query is not None and _is_placeholder(destination.query):
        fields.append(f"{prefix}query")
    if destination.table is not None and _is_placeholder(destination.table):
        fields.append(f"{prefix}table")
    for index, table_name in enumerate(destination.expected_core_tables):
        if _is_placeholder(table_name):
            fields.append(f"{prefix}expected_core_tables[{index}]")
    return tuple(fields)


def _placeholder_reason(
    destination_name: DestinationName, destination: FivetranManifestDestination
) -> tuple[str | None, tuple[str, ...]]:
    fields = _placeholder_fields(destination_name, destination)
    if fields:
        return (
            f"{destination_name} manifest still contains placeholder values in: {', '.join(fields)}",
            fields,
        )
    return None, ()


def _manifest_placeholder_paths(payload: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    for connector in payload.get("connectors", []):
        if not isinstance(connector, dict):
            continue
        connector_slug = str(connector.get("connector_slug", "")).strip()
        if not connector_slug:
            continue
        for destination_name in ("snowflake", "bigquery"):
            raw_destination = connector.get(destination_name)
            if not isinstance(raw_destination, dict):
                continue
            destination = FivetranManifestDestination.model_validate(raw_destination)
            fields = _placeholder_fields(destination_name, destination)
            paths.extend(f"{connector_slug}.{field_name}" for field_name in fields)
    return paths


def _build_behavior_case(
    connector_slug: str,
    display_name: str,
    destination_name: DestinationName,
    destination: FivetranManifestDestination,
) -> validation_catalog.ConnectorValidationCase:
    def _connection_factory() -> dict[str, Any]:
        return _warehouse_connection(destination_name, destination)

    return validation_catalog.ConnectorValidationCase(
        case_id=f"fivetran_{connector_slug}_{destination_name}",
        label=f"Fivetran {display_name} {destination_name}",
        ecosystem="fivetran",
        example_name=f"{connector_slug}_{destination_name}",
        connector_type=destination_name,
        tier="customer_credentials_required",
        validation_mode="connector_test_only",
        behavior_mode="immutable",
        negative_probe="none",
        value_drift_mode="strict_sample_hash",
        behavior_validation_mode="register_and_exact_query",
        behavior_mode_override="immutable",
        behavior_connection_factory=_connection_factory,
        behavior_expected_records_loader=validation_catalog._load_sql_records,
        behavior_required_env_vars=(),
        row_count_tolerance=0.0,
        identity_columns=tuple(destination.identity_columns),
        notes="Fivetran validation-only warehouse mirror probe.",
    )


def _baseline_lookup(
    baseline_lock: dict[str, Any], connector_slug: str, destination_name: DestinationName
) -> dict[str, Any] | None:
    for entry in baseline_lock.get("entries", []):
        if (
            entry.get("connector_slug") == connector_slug
            and entry.get("destination_name") == destination_name
        ):
            return entry
    return None


def _evaluate_preflight(
    *,
    payload: dict[str, Any],
    destination: FivetranManifestDestination,
) -> tuple[VerificationState, tuple[str, ...], float | None]:
    connection_payload = _extract_connection_payload(payload)
    setup_tests = connection_payload.get("setup_tests", [])
    if isinstance(setup_tests, list):
        failing_tests = [
            str(test.get("title") or "setup_test")
            for test in setup_tests
            if str(test.get("status", "")).upper() in {"FAILED", "JOB_FAILED"}
        ]
        if failing_tests:
            return "fail", (f"Fivetran setup tests failed: {', '.join(failing_tests)}",), None
    markers = _preflight_state_markers(connection_payload)
    if {"syncing", "historical", "delayed", "incomplete", "paused"} & markers:
        return (
            "blocked",
            (f"Fivetran connection state blocks validation: {', '.join(sorted(markers))}",),
            None,
        )
    last_successful_sync = _extract_last_successful_sync(connection_payload)
    if last_successful_sync is None:
        return (
            "blocked",
            ("Fivetran connection does not expose a last successful sync timestamp.",),
            None,
        )
    lag_minutes = (_utc_now() - last_successful_sync).total_seconds() / 60.0
    if lag_minutes > destination.max_data_lag_minutes:
        return (
            "fail",
            (
                f"Fivetran data freshness exceeded max_data_lag_minutes: {lag_minutes:.2f} > {destination.max_data_lag_minutes}",
            ),
            lag_minutes,
        )
    return "pass", (), lag_minutes


def _evaluate_destination_without_behavior(
    *,
    connector_slug: str,
    destination_name: DestinationName,
    display_name: str,
    destination: FivetranManifestDestination,
    baseline_lock: dict[str, Any],
    api_client: FivetranApiClient | None,
) -> tuple[DestinationEvaluation, validation_catalog.ConnectorValidationCase | None]:
    placeholder_reason, placeholder_fields = _placeholder_reason(destination_name, destination)
    if placeholder_reason:
        return (
            DestinationEvaluation(
                destination_name=destination_name,
                connection_id=destination.connection_id,
                state="blocked",
                reasons=(placeholder_reason,),
                placeholder_fields=placeholder_fields,
            ),
            None,
        )
    if api_client is None:
        missing = ", ".join(required_fivetran_envs_missing())
        return (
            DestinationEvaluation(
                destination_name=destination_name,
                connection_id=destination.connection_id,
                state="blocked",
                reasons=(f"missing Fivetran API envs: {missing}",),
            ),
            None,
        )
    try:
        details = api_client.connection_details(destination.connection_id)
    except Exception as exc:  # noqa: BLE001
        return (
            DestinationEvaluation(
                destination_name=destination_name,
                connection_id=destination.connection_id,
                state="blocked",
                reasons=(f"Fivetran API preflight unavailable: {exc}",),
            ),
            None,
        )
    preflight_state, preflight_reasons, lag_minutes = _evaluate_preflight(
        payload=details,
        destination=destination,
    )
    if preflight_state != "pass":
        return (
            DestinationEvaluation(
                destination_name=destination_name,
                connection_id=destination.connection_id,
                state=preflight_state,
                reasons=preflight_reasons,
                freshness_lag_minutes=lag_minutes,
            ),
            None,
        )
    try:
        _check_expected_core_tables(destination_name, destination)
        sample_records, schema_columns = _sample_records_for_destination(
            destination_name, destination
        )
        row_count = _count_rows_for_destination(destination_name, destination)
    except Exception as exc:  # noqa: BLE001
        return (
            DestinationEvaluation(
                destination_name=destination_name,
                connection_id=destination.connection_id,
                state=_classify_destination_exception(exc),
                reasons=(str(exc),),
                freshness_lag_minutes=lag_minutes,
            ),
            None,
        )
    if row_count < destination.minimum_row_count:
        return (
            DestinationEvaluation(
                destination_name=destination_name,
                connection_id=destination.connection_id,
                state="fail",
                reasons=(
                    f"{destination_name} row count {row_count} is below minimum_row_count {destination.minimum_row_count}",
                ),
                freshness_lag_minutes=lag_minutes,
                row_count=row_count,
            ),
            None,
        )
    if not schema_columns:
        return (
            DestinationEvaluation(
                destination_name=destination_name,
                connection_id=destination.connection_id,
                state="fail",
                reasons=(f"{destination_name} schema is empty.",),
                freshness_lag_minutes=lag_minutes,
                row_count=row_count,
            ),
            None,
        )
    column_names = {str(column.get("name", "")) for column in schema_columns}
    missing_identity = [
        column for column in destination.identity_columns if column not in column_names
    ]
    if missing_identity:
        return (
            DestinationEvaluation(
                destination_name=destination_name,
                connection_id=destination.connection_id,
                state="fail",
                reasons=(
                    f"{destination_name} missing identity columns: {', '.join(missing_identity)}",
                ),
                freshness_lag_minutes=lag_minutes,
                row_count=row_count,
            ),
            None,
        )
    baseline_entry = _baseline_lookup(baseline_lock, connector_slug, destination_name)
    if baseline_entry is None:
        return (
            DestinationEvaluation(
                destination_name=destination_name,
                connection_id=destination.connection_id,
                state="blocked",
                reasons=(f"{destination_name} baseline entry is missing.",),
                freshness_lag_minutes=lag_minutes,
                row_count=row_count,
                minimum_expected_ratio=destination.minimum_expected_ratio,
            ),
            None,
        )
    baseline_row_count = int(baseline_entry.get("row_count", 0))
    if baseline_row_count <= 0:
        return (
            DestinationEvaluation(
                destination_name=destination_name,
                connection_id=destination.connection_id,
                state="blocked",
                reasons=(
                    f"{destination_name} baseline row_count is invalid: {baseline_row_count}",
                ),
                freshness_lag_minutes=lag_minutes,
                row_count=row_count,
                baseline_row_count=baseline_row_count,
                minimum_expected_ratio=destination.minimum_expected_ratio,
            ),
            None,
        )
    observed_ratio = row_count / baseline_row_count
    if observed_ratio < destination.minimum_expected_ratio:
        return (
            DestinationEvaluation(
                destination_name=destination_name,
                connection_id=destination.connection_id,
                state="fail",
                reasons=(
                    f"{destination_name} row-count ratio {observed_ratio:.3f} is below minimum_expected_ratio {destination.minimum_expected_ratio:.3f}",
                ),
                freshness_lag_minutes=lag_minutes,
                row_count=row_count,
                baseline_row_count=baseline_row_count,
                observed_ratio=observed_ratio,
                minimum_expected_ratio=destination.minimum_expected_ratio,
            ),
            None,
        )
    case = _build_behavior_case(
        connector_slug=connector_slug,
        display_name=display_name,
        destination_name=destination_name,
        destination=destination,
    )
    return (
        DestinationEvaluation(
            destination_name=destination_name,
            connection_id=destination.connection_id,
            state="pass",
            reasons=(),
            freshness_lag_minutes=lag_minutes,
            row_count=row_count,
            baseline_row_count=baseline_row_count,
            observed_ratio=observed_ratio,
            minimum_expected_ratio=destination.minimum_expected_ratio,
        ),
        case,
    )


def _run_behavior_cases(
    harness: _GoLiveApiHarness,
    pending: list[tuple[str, DestinationEvaluation, validation_catalog.ConnectorValidationCase]],
) -> tuple[dict[tuple[str, DestinationName], dict[str, Any]], list[str]]:
    connectivity.behavior_case_summaries.clear()
    connectivity.behavior_p1_failures.clear()
    summaries: dict[tuple[str, DestinationName], dict[str, Any]] = {}
    suite_failures: list[str] = []
    assert harness.client is not None
    assert harness.api_key is not None
    for connector_slug, destination_eval, case in pending:
        try:
            summary = connectivity.run_behavior_validation_case(
                harness.client,
                harness.api_key,
                case=case,
                create_connector=harness.create_connector,
            )
        except Exception as exc:  # noqa: BLE001
            suite_failures.append(
                f"{connector_slug}/{destination_eval.destination_name} behavioral validation failed: {exc}"
            )
            continue
        summaries[(connector_slug, destination_eval.destination_name)] = summary
        if summary.get("p1_failures"):
            suite_failures.extend(str(value) for value in summary["p1_failures"])
    try:
        connectivity.assert_behavior_sla_summary()
    except AssertionError as exc:
        suite_failures.append(str(exc))
    return summaries, suite_failures


def _aggregate_connector_state(
    destinations: tuple[DestinationEvaluation, DestinationEvaluation],
) -> VerificationState:
    if any(destination.state == "fail" for destination in destinations):
        return "fail"
    if any(destination.state == "blocked" for destination in destinations):
        return "blocked"
    return "pass"


def evaluate_fivetran_wave(
    *,
    run_behavior_validation: bool,
    connector_slugs: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    inventory_lock, selection_lock = ensure_inventory_and_selection_locks_are_consistent()
    baseline_lock = ensure_baseline_lock()
    selection_error: str | None = None
    all_selected_entries = selection_lock["selected_connectors"]
    all_selected_slugs = {str(entry["connector_slug"]) for entry in all_selected_entries}
    try:
        selected_entries = _filter_selected_connectors(all_selected_entries, connector_slugs)
    except FivetranVerificationError as exc:
        selection_error = str(exc)
        selected_entries = []
    manifest_path = resolve_manifest_path()
    manifest_error: str | None = None
    manifest_document: FivetranManifestDocument | None = None
    manifest_payload: dict[str, Any] | None = None
    manifest_version: str | None = None
    try:
        manifest_path, manifest_document, manifest_payload, manifest_version = load_manifest(
            manifest_path
        )
        validate_manifest_against_selection_lock(
            manifest_document,
            inventory_lock=inventory_lock,
            selection_lock=selection_lock,
        )
    except (FileNotFoundError, ValidationError, json.JSONDecodeError, ValueError) as exc:
        manifest_error = str(exc)
    except FivetranVerificationError as exc:
        manifest_error = str(exc)
    selected_by_slug = {str(entry["connector_slug"]): entry for entry in selected_entries}
    manifest_by_slug: dict[str, FivetranManifestEntry] = {}
    if manifest_document is not None:
        manifest_by_slug = {entry.connector_slug: entry for entry in manifest_document.connectors}
    missing_manifest_slugs = sorted(set(selected_by_slug) - set(manifest_by_slug))
    extra_manifest_slugs = sorted(set(manifest_by_slug) - all_selected_slugs)
    api_client: FivetranApiClient | None = None
    credential_resolution = _resolve_fivetran_api_credentials()
    missing_api_envs = required_fivetran_envs_missing()
    account_summary: dict[str, int] | None = None
    account_summary_error: str | None = None
    account_blockers: list[str] = []
    if credential_resolution is not None and not missing_api_envs:
        api_client = FivetranApiClient(
            credential_resolution.api_key,
            credential_resolution.api_secret,
        )
        try:
            account_summary = api_client.account_summary()
        except Exception as exc:  # noqa: BLE001
            account_summary_error = f"Fivetran account summary unavailable: {exc}"
        else:
            if account_summary["destinations"] <= 0:
                account_blockers.append("Fivetran account has no destinations.")
            if account_summary["connections"] <= 0:
                account_blockers.append("Fivetran account has no connections.")
    connector_evaluations: list[ConnectorEvaluation] = []
    pending_behavior: list[
        tuple[str, DestinationEvaluation, validation_catalog.ConnectorValidationCase]
    ] = []
    try:
        for connector_slug, selected_entry in selected_by_slug.items():
            display_name = str(selected_entry["display_name"])
            if manifest_error is not None:
                destination_evaluations = (
                    DestinationEvaluation(
                        destination_name="snowflake",
                        connection_id="",
                        state="blocked",
                        reasons=(f"manifest error: {manifest_error}",),
                    ),
                    DestinationEvaluation(
                        destination_name="bigquery",
                        connection_id="",
                        state="blocked",
                        reasons=(f"manifest error: {manifest_error}",),
                    ),
                )
                connector_evaluations.append(
                    ConnectorEvaluation(
                        connector_slug=connector_slug,
                        display_name=display_name,
                        state="blocked",
                        destinations=destination_evaluations,
                    )
                )
                continue
            if connector_slug in missing_manifest_slugs:
                destination_evaluations = (
                    DestinationEvaluation(
                        destination_name="snowflake",
                        connection_id="",
                        state="blocked",
                        reasons=(f"{connector_slug} missing from manifest.",),
                    ),
                    DestinationEvaluation(
                        destination_name="bigquery",
                        connection_id="",
                        state="blocked",
                        reasons=(f"{connector_slug} missing from manifest.",),
                    ),
                )
                connector_evaluations.append(
                    ConnectorEvaluation(
                        connector_slug=connector_slug,
                        display_name=display_name,
                        state="blocked",
                        destinations=destination_evaluations,
                    )
                )
                continue
            manifest_entry = manifest_by_slug[connector_slug]
            snowflake_eval, snowflake_case = _evaluate_destination_without_behavior(
                connector_slug=connector_slug,
                destination_name="snowflake",
                display_name=display_name,
                destination=manifest_entry.snowflake,
                baseline_lock=baseline_lock,
                api_client=api_client,
            )
            bigquery_eval, bigquery_case = _evaluate_destination_without_behavior(
                connector_slug=connector_slug,
                destination_name="bigquery",
                display_name=display_name,
                destination=manifest_entry.bigquery,
                baseline_lock=baseline_lock,
                api_client=api_client,
            )
            connector_evaluations.append(
                ConnectorEvaluation(
                    connector_slug=connector_slug,
                    display_name=display_name,
                    state=_aggregate_connector_state((snowflake_eval, bigquery_eval)),
                    destinations=(snowflake_eval, bigquery_eval),
                )
            )
            if (
                run_behavior_validation
                and snowflake_case is not None
                and snowflake_eval.state == "pass"
            ):
                pending_behavior.append((connector_slug, snowflake_eval, snowflake_case))
            if (
                run_behavior_validation
                and bigquery_case is not None
                and bigquery_eval.state == "pass"
            ):
                pending_behavior.append((connector_slug, bigquery_eval, bigquery_case))
        suite_failures: list[str] = []
        if extra_manifest_slugs:
            suite_failures.append(
                "manifest includes connectors outside the frozen top-20 selection: "
                + ", ".join(extra_manifest_slugs)
            )
        if selection_error:
            suite_failures.append(selection_error)
        if missing_manifest_slugs:
            suite_failures.append(
                "manifest is missing selected connectors: " + ", ".join(missing_manifest_slugs)
            )
        if account_summary_error:
            suite_failures.append(account_summary_error)
        suite_failures.extend(account_blockers)
        if run_behavior_validation and pending_behavior:
            with _GoLiveApiHarness() as harness:
                behavior_summaries, behavior_failures = _run_behavior_cases(
                    harness, pending_behavior
                )
            updated_connectors: list[ConnectorEvaluation] = []
            for connector_eval in connector_evaluations:
                updated_destinations: list[DestinationEvaluation] = []
                for destination_eval in connector_eval.destinations:
                    behavior_summary = behavior_summaries.get(
                        (connector_eval.connector_slug, destination_eval.destination_name)
                    )
                    if behavior_summary is None:
                        updated_destinations.append(destination_eval)
                        continue
                    state = destination_eval.state
                    reasons = list(destination_eval.reasons)
                    if behavior_summary.get("p1_failures"):
                        state = "fail"
                        reasons.extend(str(value) for value in behavior_summary["p1_failures"])
                    updated_destinations.append(
                        DestinationEvaluation(
                            destination_name=destination_eval.destination_name,
                            connection_id=destination_eval.connection_id,
                            state=state,
                            reasons=tuple(reasons),
                            freshness_lag_minutes=destination_eval.freshness_lag_minutes,
                            row_count=destination_eval.row_count,
                            baseline_row_count=destination_eval.baseline_row_count,
                            observed_ratio=destination_eval.observed_ratio,
                            minimum_expected_ratio=destination_eval.minimum_expected_ratio,
                            behavior_summary=behavior_summary,
                        )
                    )
                updated_connectors.append(
                    ConnectorEvaluation(
                        connector_slug=connector_eval.connector_slug,
                        display_name=connector_eval.display_name,
                        state=_aggregate_connector_state(tuple(updated_destinations)),  # type: ignore[arg-type]
                        destinations=tuple(updated_destinations),  # type: ignore[arg-type]
                    )
                )
            connector_evaluations = updated_connectors
            suite_failures.extend(behavior_failures)
        summary_counts = {"pass": 0, "fail": 0, "blocked": 0}
        for connector_eval in connector_evaluations:
            summary_counts[connector_eval.state] += 1
        payload = {
            "inventory_version": inventory_lock["inventory_version"],
            "selection_version": selection_lock["selection_version"],
            "baseline_version": baseline_lock["baseline_version"],
            "manifest_path": str(manifest_path),
            "manifest_version": manifest_version,
            "selected_count": len(selected_entries),
            "connector_filter": list(connector_slugs or ()),
            "missing_api_envs": list(missing_api_envs),
            "api_credential_source": (
                {
                    "key": credential_resolution.key_source,
                    "secret": credential_resolution.secret_source,
                }
                if credential_resolution is not None
                else None
            ),
            "account_summary": account_summary,
            "account_summary_error": account_summary_error,
            "account_blockers": account_blockers,
            "manifest_error": manifest_error,
            "missing_manifest_connectors": missing_manifest_slugs,
            "extra_manifest_connectors": extra_manifest_slugs,
            "connector_results": [entry.to_dict() for entry in connector_evaluations],
            "summary": summary_counts,
            "suite_failures": suite_failures,
        }
        payload["next_actions"] = build_fivetran_next_actions(payload)
        return payload
    finally:
        if api_client is not None:
            api_client.close()


def _connector_make_arg(payload: dict[str, Any]) -> str:
    connector_filter = payload.get("connector_filter") or []
    if not connector_filter:
        return ""
    return " CONNECTOR=" + ",".join(str(value) for value in connector_filter)


def _placeholder_connectors(payload: dict[str, Any]) -> list[dict[str, Any]]:
    connectors: list[dict[str, Any]] = []
    for connector in payload.get("connector_results", []):
        destination_fields: dict[str, list[str]] = {}
        for destination in connector.get("destinations", []):
            placeholder_fields = [
                str(field_name)
                for field_name in destination.get("placeholder_fields", []) or []
                if str(field_name).strip()
            ]
            if placeholder_fields:
                destination_fields[str(destination["destination_name"])] = placeholder_fields
        if destination_fields:
            connectors.append(
                {
                    "connector_slug": str(connector["connector_slug"]),
                    "destinations": destination_fields,
                }
            )
    return connectors


def _only_missing_baseline_blockers(payload: dict[str, Any]) -> bool:
    summary = payload.get("summary", {})
    if int(summary.get("fail", 0) or 0) > 0:
        return False
    found_blocked = False
    for connector in payload.get("connector_results", []):
        for destination in connector.get("destinations", []):
            state = str(destination.get("state", "")).strip()
            if state == "pass":
                continue
            if state != "blocked":
                return False
            destination_name = str(destination.get("destination_name", "")).strip()
            expected_reason = f"{destination_name} baseline entry is missing."
            reasons = [
                str(reason).strip()
                for reason in destination.get("reasons", []) or []
                if str(reason).strip()
            ]
            if not reasons or any(reason != expected_reason for reason in reasons):
                return False
            found_blocked = True
    return found_blocked


def build_fivetran_next_actions(payload: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    connector_arg = _connector_make_arg(payload)
    missing_api_envs = [
        str(value) for value in payload.get("missing_api_envs", []) or [] if str(value).strip()
    ]
    if missing_api_envs:
        actions.append(
            {
                "code": "set_fivetran_api_credentials",
                "message": "Set the missing Fivetran API credentials before running status or verify.",
                "details": {"missing_api_envs": missing_api_envs},
            }
        )
    account_summary = payload.get("account_summary")
    if isinstance(account_summary, dict):
        if int(account_summary.get("destinations", 0) or 0) <= 0:
            actions.append(
                {
                    "code": "create_fivetran_destinations",
                    "message": "Create one Snowflake destination and one BigQuery destination in Fivetran.",
                    "details": {"required_destinations": ["snowflake", "bigquery"]},
                }
            )
        if int(account_summary.get("connections", 0) or 0) <= 0:
            connector_target = (
                list(payload["connector_filter"])
                if payload.get("connector_filter")
                else "one logical source"
            )
            actions.append(
                {
                    "code": "create_fivetran_connections",
                    "message": (
                        "Create two destination-specific Fivetran connections for the same logical "
                        "source, one to Snowflake and one to BigQuery, and wait for the first sync "
                        "to complete."
                    ),
                    "details": {
                        "required_connection_count": 2,
                        "connector_target": connector_target,
                    },
                }
            )
    placeholder_connectors = _placeholder_connectors(payload)
    if placeholder_connectors:
        actions.append(
            {
                "code": "hydrate_manifest_connection_ids",
                "message": "Hydrate live Fivetran connection IDs into the manifest once the account has matching connections.",
                "command": f"make go-live-hydrate-fivetran-manifest{connector_arg}".strip(),
            }
        )
        actions.append(
            {
                "code": "fill_manifest_selectors",
                "message": "Replace the remaining manifest placeholder fields before running the verifier.",
                "details": {"connectors": placeholder_connectors},
            }
        )
    if not missing_api_envs and not payload.get("account_blockers") and not placeholder_connectors:
        if _only_missing_baseline_blockers(payload):
            actions.append(
                {
                    "code": "refresh_fivetran_baseline",
                    "message": (
                        "The connector is clean except for missing baseline entries. Refresh the "
                        "baseline now, then rerun strict verify."
                    ),
                    "command": f"make go-live-refresh-fivetran-baseline{connector_arg}".strip(),
                }
            )
        else:
            actions.append(
                {
                    "code": "run_fivetran_prebaseline_verify",
                    "message": (
                        "Run the strict pre-baseline verify and fix every failure except missing "
                        "baseline before capturing the baseline."
                    ),
                    "command": f"make go-live-verify-fivetran-prebaseline{connector_arg}".strip(),
                }
            )
    if _only_missing_baseline_blockers(payload):
        actions.append(
            {
                "code": "run_fivetran_strict_verify",
                "message": "After baseline refresh succeeds, rerun the strict Fivetran verifier.",
                "command": f"make go-live-verify-fivetran{connector_arg}".strip(),
            }
        )
    return actions


def build_connector_manifest_view(*, connector_slug: str) -> dict[str, Any]:
    manifest_path, manifest_document, manifest_payload, manifest_version = load_manifest(
        resolve_manifest_path()
    )
    connector_entry = next(
        (entry for entry in manifest_document.connectors if entry.connector_slug == connector_slug),
        None,
    )
    if connector_entry is None:
        available = sorted(entry.connector_slug for entry in manifest_document.connectors)
        raise FivetranVerificationError(
            f"Connector '{connector_slug}' not found in manifest. Available connectors: {', '.join(available)}"
        )
    placeholder_fields: list[str] = []
    for destination_name, destination in (
        ("snowflake", connector_entry.snowflake),
        ("bigquery", connector_entry.bigquery),
    ):
        _reason, fields = _placeholder_reason(destination_name, destination)
        placeholder_fields.extend(fields)
    return {
        "manifest_path": str(manifest_path),
        "manifest_version": manifest_version,
        "connector_slug": connector_slug,
        "manifest_entry": connector_entry.model_dump(),
        "remaining_placeholder_fields": placeholder_fields,
        "next_commands": [
            f"make go-live-hydrate-fivetran-manifest CONNECTOR={connector_slug}",
            f"make go-live-verify-fivetran-prebaseline CONNECTOR={connector_slug}",
            f"make go-live-refresh-fivetran-baseline CONNECTOR={connector_slug}",
            f"make go-live-verify-fivetran CONNECTOR={connector_slug}",
        ],
    }


def render_fivetran_status(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "Fivetran wave-1 validation status",
        f"Inventory version: {payload['inventory_version']}",
        f"Selection version: {payload['selection_version']}",
        f"Baseline version: {payload['baseline_version']}",
        f"Manifest path: {payload['manifest_path']}",
        f"Selected connectors: {payload['selected_count']}",
        (f"Pass: {summary['pass']} | Fail: {summary['fail']} | Blocked: {summary['blocked']}"),
    ]
    if payload.get("connector_filter"):
        lines.append(
            "Connector filter: " + ", ".join(str(value) for value in payload["connector_filter"])
        )
    credential_source = payload.get("api_credential_source")
    if isinstance(credential_source, dict) and credential_source:
        lines.append(
            "API credential source: "
            f"key={credential_source.get('key')} secret={credential_source.get('secret')}"
        )
    if payload.get("missing_api_envs"):
        lines.append("Missing Fivetran envs: " + ", ".join(payload["missing_api_envs"]))
    account_summary = payload.get("account_summary")
    if isinstance(account_summary, dict):
        lines.append(
            "Account summary: "
            f"groups={account_summary.get('groups')} | "
            f"destinations={account_summary.get('destinations')} | "
            f"connections={account_summary.get('connections')}"
        )
    if payload.get("account_summary_error"):
        lines.append("Account summary error: " + str(payload["account_summary_error"]))
    if payload.get("account_blockers"):
        lines.append("Account blockers:")
        for blocker in payload["account_blockers"]:
            lines.append(f"  - {blocker}")
    if payload.get("manifest_error"):
        lines.append("Manifest error: " + str(payload["manifest_error"]))
    for connector in payload["connector_results"]:
        lines.append(f"{connector['connector_slug']} | {connector['state']}")
        for destination in connector["destinations"]:
            line = (
                f"  - {destination['destination_name']} | {destination['state']} | "
                f"lag={destination.get('freshness_lag_minutes')} | "
                f"ratio={destination.get('observed_ratio')}"
            )
            lines.append(line)
            for reason in destination.get("reasons", []):
                lines.append(f"      reason: {reason}")
    if payload.get("suite_failures"):
        lines.append("Suite failures:")
        for failure in payload["suite_failures"]:
            lines.append(f"  - {failure}")
    if payload.get("next_actions"):
        lines.append("Next actions:")
        for action in payload["next_actions"]:
            lines.append(f"  - {action['code']}: {action['message']}")
            command = str(action.get("command", "") or "").strip()
            if command:
                lines.append(f"      command: {command}")
    return "\n".join(lines)


def render_fivetran_markdown_report(
    payload: dict[str, Any],
    *,
    selection_lock: dict[str, Any],
) -> str:
    metadata_by_slug = {
        str(entry["connector_slug"]): entry for entry in selection_lock["selected_connectors"]
    }
    summary = payload["summary"]
    lines = [
        "# Fivetran Wave-1 Validation Report",
        "",
        f"- Inventory version: `{payload['inventory_version']}`",
        f"- Selection version: `{payload['selection_version']}`",
        f"- Baseline version: `{payload['baseline_version']}`",
        f"- Manifest version: `{payload['manifest_version']}`",
        f"- Manifest path: `{payload['manifest_path']}`",
        f"- Selected connectors: `{payload['selected_count']}`",
        (
            f"- Summary: `pass={summary['pass']}` `fail={summary['fail']}` "
            f"`blocked={summary['blocked']}`"
        ),
    ]
    if payload.get("connector_filter"):
        lines.append(
            "- Connector filter: "
            + ", ".join(f"`{value}`" for value in payload["connector_filter"])
        )
    credential_source = payload.get("api_credential_source")
    if isinstance(credential_source, dict) and credential_source:
        lines.append(
            "- API credential source: "
            f"`{credential_source.get('key')}` / `{credential_source.get('secret')}`"
        )
    if payload.get("missing_api_envs"):
        lines.append(
            "- Missing Fivetran envs: "
            + ", ".join(f"`{value}`" for value in payload["missing_api_envs"])
        )
    account_summary = payload.get("account_summary")
    if isinstance(account_summary, dict):
        lines.append(
            "- Account summary: "
            f"`groups={account_summary.get('groups')}` "
            f"`destinations={account_summary.get('destinations')}` "
            f"`connections={account_summary.get('connections')}`"
        )
    if payload.get("account_summary_error"):
        lines.append(f"- Account summary error: `{payload['account_summary_error']}`")
    if payload.get("account_blockers"):
        lines.append("- Account blockers:")
        lines.extend(f"  - {blocker}" for blocker in payload["account_blockers"])
    if payload.get("manifest_error"):
        lines.append(f"- Manifest error: {payload['manifest_error']}")

    lines.extend(
        [
            "",
            "## Connector Summary",
            "",
            "| Connector | Bucket | Docs | Traits | Verdict | Snowflake | BigQuery |",
            "|---|---|---|---|---|---|---|",
        ]
    )
    for connector in payload["connector_results"]:
        metadata = metadata_by_slug.get(connector["connector_slug"], {})
        destination_states = {
            destination["destination_name"]: destination["state"]
            for destination in connector["destinations"]
        }
        traits = [
            trait_name
            for trait_name in (
                "nested_json",
                "wide_table",
                "high_churn_rest",
                "append_only_event",
            )
            if metadata.get(trait_name) is True
        ]
        docs_path = str(metadata.get("docs_path", "") or "")
        lines.append(
            "| "
            + " | ".join(
                [
                    str(connector["connector_slug"]),
                    str(metadata.get("selection_bucket", "")),
                    (f"`{docs_path}`" if docs_path else ""),
                    (", ".join(traits) if traits else "none"),
                    str(connector["state"]),
                    str(destination_states.get("snowflake", "")),
                    str(destination_states.get("bigquery", "")),
                ]
            )
            + " |"
        )

    destination_issue_lines: list[str] = []
    for connector in payload["connector_results"]:
        connector_issue_lines: list[str] = []
        for destination in connector["destinations"]:
            reasons = [
                str(reason) for reason in destination.get("reasons", []) if str(reason).strip()
            ]
            if destination["state"] == "pass" and not reasons:
                continue
            connector_issue_lines.append(
                f"- `{destination['destination_name']}`: `{destination['state']}` "
                f"(lag={destination.get('freshness_lag_minutes')}, "
                f"ratio={destination.get('observed_ratio')})"
            )
            placeholder_fields = [
                str(field_name)
                for field_name in destination.get("placeholder_fields", []) or []
                if str(field_name).strip()
            ]
            if placeholder_fields:
                connector_issue_lines.append(
                    f"  - placeholder_fields: {', '.join(placeholder_fields)}"
                )
            connector_issue_lines.extend(f"  - {reason}" for reason in reasons)
        if connector_issue_lines:
            destination_issue_lines.extend(
                [
                    "",
                    f"### {connector['connector_slug']}",
                    *connector_issue_lines,
                ]
            )
    if destination_issue_lines:
        lines.extend(["", "## Destination Details", *destination_issue_lines])
    next_actions = payload.get("next_actions") or []
    if next_actions:
        lines.extend(["", "## Next Actions", ""])
        for action in next_actions:
            lines.append(f"- `{action['code']}`: {action['message']}")
            command = str(action.get("command", "") or "").strip()
            if command:
                lines.append(f"  - command: `{command}`")
    if payload.get("suite_failures"):
        lines.extend(["", "## Suite Failures", ""])
        lines.extend(f"- {failure}" for failure in payload["suite_failures"])
    return "\n".join(lines)


def refresh_baseline_lock(
    *,
    connector_slugs: tuple[str, ...] | None = None,
    sleep_seconds: int = BASELINE_REFRESH_SLEEP_SECONDS,
    sleep_fn=time.sleep,
) -> dict[str, Any]:
    _inventory_lock, selection_lock = ensure_inventory_and_selection_locks_are_consistent()
    manifest_path, manifest_document, manifest_payload, manifest_version = load_manifest(
        resolve_manifest_path()
    )
    all_selected_entries = selection_lock["selected_connectors"]
    selected_entries = _filter_selected_connectors(all_selected_entries, connector_slugs)
    selected_slugs = {str(entry["connector_slug"]) for entry in selected_entries}
    all_selected_slugs = {str(entry["connector_slug"]) for entry in all_selected_entries}
    manifest_by_slug = {entry.connector_slug: entry for entry in manifest_document.connectors}
    missing = sorted(selected_slugs - set(manifest_by_slug))
    extra = sorted(set(manifest_by_slug) - all_selected_slugs)
    if missing or extra:
        raise FivetranVerificationError(
            "Manifest does not match frozen top-20 selection. "
            f"missing={missing or []} extra={extra or []}"
        )
    missing_api_envs = required_fivetran_envs_missing()
    if missing_api_envs:
        raise FivetranVerificationError(
            "Baseline refresh requires Fivetran API envs: " + ", ".join(missing_api_envs)
        )
    credential_resolution = _resolve_fivetran_api_credentials()
    if credential_resolution is None:
        raise FivetranVerificationError(
            "Baseline refresh could not resolve Fivetran API credentials."
        )
    api_client = FivetranApiClient(
        credential_resolution.api_key,
        credential_resolution.api_secret,
    )
    entries: list[dict[str, Any]] = []
    try:
        for connector_slug in selected_slugs:
            connector = manifest_by_slug[connector_slug]
            for destination_name, destination in (
                ("snowflake", connector.snowflake),
                ("bigquery", connector.bigquery),
            ):
                placeholder_reason, _placeholder_fields = _placeholder_reason(
                    destination_name, destination
                )
                if placeholder_reason:
                    raise FivetranVerificationError(placeholder_reason)
                details = api_client.connection_details(destination.connection_id)
                preflight_state, preflight_reasons, _lag = _evaluate_preflight(
                    payload=details,
                    destination=destination,
                )
                if preflight_state != "pass":
                    raise FivetranVerificationError(
                        f"{connector.connector_slug}/{destination_name} cannot refresh baseline: "
                        + "; ".join(preflight_reasons)
                    )
                _check_expected_core_tables(destination_name, destination)
                first_records, first_schema = _sample_records_for_destination(
                    destination_name, destination
                )
                first_count = _count_rows_for_destination(destination_name, destination)
                if first_count < destination.minimum_row_count:
                    raise FivetranVerificationError(
                        f"{connector.connector_slug}/{destination_name} baseline row_count {first_count} "
                        f"is below minimum_row_count {destination.minimum_row_count}"
                    )
                sleep_fn(sleep_seconds)
                second_records, second_schema = _sample_records_for_destination(
                    destination_name, destination
                )
                second_count = _count_rows_for_destination(destination_name, destination)
                first_fingerprint = schema_fingerprint(
                    first_schema or connectivity._schema_columns_from_records(first_records)
                )
                second_fingerprint = schema_fingerprint(
                    second_schema or connectivity._schema_columns_from_records(second_records)
                )
                if first_fingerprint != second_fingerprint:
                    raise FivetranVerificationError(
                        f"{connector.connector_slug}/{destination_name} schema fingerprint changed between baseline reads."
                    )
                if first_count <= 0:
                    raise FivetranVerificationError(
                        f"{connector.connector_slug}/{destination_name} produced a non-positive baseline row count."
                    )
                row_delta = abs(second_count - first_count) / first_count
                if row_delta > 0.01:
                    raise FivetranVerificationError(
                        f"{connector.connector_slug}/{destination_name} row-count delta {row_delta:.3%} exceeded 1% baseline threshold."
                    )
                entries.append(
                    {
                        "connector_slug": connector.connector_slug,
                        "destination_name": destination_name,
                        "connection_id": destination.connection_id,
                        "row_count": second_count,
                        "captured_at": _utc_now_iso(),
                        "manifest_version": manifest_version,
                        "schema_fingerprint": second_fingerprint,
                    }
                )
    finally:
        api_client.close()
    payload = {
        "generated_at": _utc_now_iso(),
        "baseline_version": _stable_hash(entries),
        "entries": entries,
        "manifest_path": str(manifest_path),
    }
    validate_baseline_lock_payload(payload)
    return payload
