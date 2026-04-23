"""Runtime-first Algenta facade for deterministic resolve and query workflows."""

from __future__ import annotations

import asyncio
import base64
import builtins
import hashlib
import json
import os
import re
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import quote

from algenta._contract import DEFAULT_BASE_URL
from algenta.map import (
    _AGG_KEYWORDS,
    _METRIC_SYNONYMS,
    _execute,
    _is_numeric_field,
    _normalize,
    _parse_source,
    _semantic_similarity,
    _source_name,
)

LocalSourceInput = str | Path | list[dict[str, Any]] | Mapping[str, Any]


def _stable_hash(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _normalize_text(value: str | None) -> str:
    return _normalize(value or "")


def _ordered_fields(records: list[dict[str, Any]]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for record in records:
        for field_name in record:
            if field_name in seen:
                continue
            seen.add(field_name)
            ordered.append(field_name)
    return tuple(ordered)


_BUNDLE_FIELD_TOKEN_RE = re.compile(r"[a-z0-9]+")
_UUID_FILE_PREFIX_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}[_-]+",
    re.IGNORECASE,
)
_SQL_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_DIRECT_API_SOURCE_KEYS = frozenset(
    {
        "dataset_id",
        "source_id",
        "records",
        "csv",
        "json_str",
        "url",
        "excel_b64",
        "parquet_b64",
        "connection",
    }
)
_SQL_PROVIDER_TYPES = frozenset(
    {
        "sql",
        "postgres",
        "postgresql",
        "mysql",
        "mssql",
        "sqlite",
        "snowflake",
        "bigquery",
    }
)
_OBJECT_STORAGE_TYPES = frozenset({"s3", "gcs", "azure_blob"})
_CANONICAL_FILE_TYPES = frozenset({"csv", "tsv", "json", "excel", "xlsx", "xls", "parquet"})
_CANONICAL_API_TYPES = frozenset({"rest", "rest_api", "api"})
_LOCAL_RUNTIME_CONNECTOR_TYPES = _CANONICAL_FILE_TYPES | frozenset({"sqlite", "sqlite3"})
_SQL_DSN_SCHEMES = {
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "mysql": "mysql",
    "mssql": "mssql",
    "redshift": "redshift",
}
_SQL_DEFAULT_PORTS = {
    "postgres": 5432,
    "postgresql": 5432,
    "mysql": 3306,
    "mssql": 1433,
    "redshift": 5439,
}


def _bundle_field_tokens(field_name: str) -> set[str]:
    base_name = field_name.split("__", 1)[0]
    return set(_BUNDLE_FIELD_TOKEN_RE.findall(_normalize_text(base_name)))


def _field_overlap_score(left: str, right: str) -> float:
    left_tokens = _bundle_field_tokens(left)
    right_tokens = _bundle_field_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    shared = left_tokens & right_tokens
    if not shared:
        return 0.0
    return len(shared) / min(len(left_tokens), len(right_tokens))


def _runtime_source_name(source: Any, idx: int) -> str:
    if isinstance(source, Mapping) and _is_canonical_connector_envelope(source):
        source = _flatten_connector_envelope(source)
    name = _source_name(source, idx)
    if isinstance(source, str | Path):
        trimmed = _UUID_FILE_PREFIX_RE.sub("", name)
        return trimmed or name
    return name


def _unique_runtime_source_name(
    source: Any,
    idx: int,
    existing_names: set[str],
    explicit_name: str | None = None,
) -> str:
    if explicit_name:
        return explicit_name

    primary = _runtime_source_name(source, idx)
    if primary not in existing_names:
        return primary

    original = _source_name(source, idx)
    if original not in existing_names:
        return original

    counter = 2
    candidate = f"{primary}_{counter}"
    while candidate in existing_names:
        counter += 1
        candidate = f"{primary}_{counter}"
    return candidate


def _source_ref_label(source: LocalSourceInput, idx: int) -> str:
    if isinstance(source, Mapping) and _is_canonical_connector_envelope(source):
        source = _flatten_connector_envelope(source)
    if isinstance(source, str | Path):
        return Path(source).name
    if isinstance(source, Mapping):
        path_value = source.get("path")
        if isinstance(path_value, str | Path) and str(path_value).strip():
            base_name = Path(path_value).name
            table_name = source.get("table")
            if isinstance(table_name, str) and table_name.strip():
                return f"{base_name}#{table_name.strip()}"
            if isinstance(source.get("query"), str):
                return f"{base_name}#query"
            return base_name
        connection_string = source.get("connection_string")
        if isinstance(connection_string, str) and connection_string.strip():
            path_match = re.match(
                r"^sqlite(?:\+pysqlite)?:///(.+)$",
                connection_string.strip(),
                re.IGNORECASE,
            )
            if path_match:
                base_name = Path(path_match.group(1)).name
                table_name = source.get("table")
                if isinstance(table_name, str) and table_name.strip():
                    return f"{base_name}#{table_name.strip()}"
                if isinstance(source.get("query"), str):
                    return f"{base_name}#query"
                return base_name
            table_name = source.get("table")
            if isinstance(table_name, str) and table_name.strip():
                return f"{connection_string}#{table_name.strip()}"
            if isinstance(source.get('query'), str):
                return f"{connection_string}#query"
            return connection_string
        provider = str(source.get("provider") or source.get("type") or "").strip()
        if provider:
            return provider
    return f"source_{idx + 1}"


def _strip_none_dict(data: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in dict(data).items() if value is not None}


def _is_canonical_connector_envelope(source: Mapping[str, Any]) -> bool:
    return any(key in source for key in ("location", "auth", "options"))


def _merge_connector_section(
    target: dict[str, Any],
    section: Any,
    *,
    section_name: str,
) -> None:
    if section is None:
        return
    if not isinstance(section, Mapping):
        raise RuntimeValidationError(
            "invalid_connector",
            f"Canonical connector {section_name} must be an object.",
            {"section": section_name},
        )
    for key, value in section.items():
        if key in target and target[key] != value:
            raise RuntimeValidationError(
                "connector_conflict",
                f"Canonical connector defines conflicting values for '{key}'.",
                {"field": key, "section": section_name},
            )
        target[key] = value


def _normalize_connector_auth(flattened: dict[str, Any]) -> None:
    mode = str(flattened.pop("auth_mode", "") or "").strip().lower()
    if not mode or mode == "none":
        return

    headers = dict(flattened.get("headers") or {})
    if not isinstance(headers, dict):
        raise RuntimeValidationError(
            "invalid_connector_auth",
            "Canonical connector headers must be an object.",
            {"field": "headers"},
        )

    if mode in {"token", "bearer", "oauth"}:
        token = flattened.pop("token", None) or flattened.pop("access_token", None)
        if token is None:
            token = flattened.get("api_key")
        if not isinstance(token, str) or not token.strip():
            raise RuntimeValidationError(
                "invalid_connector_auth",
                "Bearer-style connector auth requires token, access_token, or api_key.",
                {"mode": mode},
            )
        headers.setdefault("Authorization", f"Bearer {token.strip()}")
    elif mode == "basic":
        username = flattened.pop("username", None) or flattened.get("user")
        password = flattened.pop("password", None)
        if not isinstance(username, str) or not isinstance(password, str):
            raise RuntimeValidationError(
                "invalid_connector_auth",
                "Basic connector auth requires username/user and password.",
                {"mode": mode},
            )
        token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        headers.setdefault("Authorization", f"Basic {token}")
    elif mode == "api_key":
        api_key = flattened.get("api_key") or flattened.pop("token", None)
        header_name = flattened.pop("api_key_header", None) or flattened.pop("header", None)
        if not isinstance(api_key, str) or not api_key.strip():
            raise RuntimeValidationError(
                "invalid_connector_auth",
                "API key connector auth requires api_key or token credentials.",
                {"mode": mode},
            )
        if not isinstance(header_name, str) or not header_name.strip():
            header_name = "X-API-Key"
        headers.setdefault(header_name, api_key.strip())
    else:
        raise RuntimeValidationError(
            "invalid_connector_auth",
            f"Unsupported connector auth mode '{mode}'.",
            {"mode": mode},
        )

    flattened["headers"] = headers


def _flatten_connector_envelope(source: Mapping[str, Any]) -> dict[str, Any]:
    raw_type = source.get("type")
    if not isinstance(raw_type, str) or not raw_type.strip():
        raise RuntimeValidationError(
            "invalid_connector",
            "Canonical connectors require a non-empty type.",
            {"field": "type"},
        )

    flattened = {
        key: value
        for key, value in source.items()
        if key not in {"location", "auth", "options"} and value is not None
    }
    flattened["type"] = raw_type.strip().lower().replace("-", "_")

    _merge_connector_section(flattened, source.get("location"), section_name="location")
    auth = source.get("auth")
    if auth is not None:
        if not isinstance(auth, Mapping):
            raise RuntimeValidationError(
                "invalid_connector",
                "Canonical connector auth must be an object.",
                {"field": "auth"},
            )
        auth_mode = auth.get("mode")
        if auth_mode is not None:
            flattened["auth_mode"] = str(auth_mode).strip().lower()
        _merge_connector_section(
            flattened,
            auth.get("credentials"),
            section_name="auth.credentials",
        )
        _merge_connector_section(
            flattened,
            auth.get("headers"),
            section_name="auth.headers",
        )
    _merge_connector_section(flattened, source.get("options"), section_name="options")

    if flattened["type"] in _CANONICAL_API_TYPES:
        _normalize_connector_auth(flattened)
    return _strip_none_dict(flattened)


def _file_connector_type(source: Mapping[str, Any]) -> str:
    raw_type = str(source.get("type") or source.get("provider") or "").strip().lower()
    if raw_type in {"xlsx", "xls"}:
        return "excel"
    return raw_type


def _normalize_local_runtime_source(source: Mapping[str, Any]) -> dict[str, Any]:
    normalized = (
        _flatten_connector_envelope(source)
        if _is_canonical_connector_envelope(source)
        else _strip_none_dict(source)
    )
    raw_type = str(
        normalized.get("type")
        or normalized.get("provider")
        or normalized.get("connection_type")
        or ""
    ).strip().lower()
    if raw_type in _CANONICAL_FILE_TYPES:
        file_path = normalized.get("file_path") or normalized.get("path")
        if isinstance(file_path, str) and file_path.strip():
            return {"path": file_path.strip()}
        if normalized.get("records") is not None:
            return {"records": normalized["records"]}
        if raw_type in {"csv", "tsv"} and isinstance(normalized.get("csv"), str):
            return {"csv": normalized["csv"]}
        if raw_type == "json" and isinstance(normalized.get("json_str"), str):
            return {"json_str": normalized["json_str"]}
        raise RuntimeValidationError(
            "unsupported_local_connector",
            (
                "Local Runtime.connect() supports canonical file connectors only "
                "when they point to a local path or inline data."
            ),
            {"type": raw_type},
        )
    if raw_type and raw_type not in _LOCAL_RUNTIME_CONNECTOR_TYPES:
        raise RuntimeValidationError(
            "unsupported_local_connector",
            (
                "Local Runtime.connect() supports local files and SQLite descriptors. "
                "Use Runtime(mode='api', api_key='...') for remote connectors."
            ),
            {"type": raw_type},
        )
    return normalized


def _runtime_api_source_name(
    source: Mapping[str, Any],
    *,
    explicit_name: str | None,
) -> str:
    if explicit_name:
        return explicit_name
    name_value = source.get("name")
    if isinstance(name_value, str) and name_value.strip():
        return name_value.strip()
    return _runtime_source_name(dict(source), 0)


def _sql_identifier(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RuntimeValidationError(
            "invalid_sql_descriptor",
            f"API mode SQL descriptors require a non-empty {field_name}.",
            {"field": field_name},
        )
    normalized = value.strip()
    if not _SQL_IDENTIFIER_RE.fullmatch(normalized):
        raise RuntimeValidationError(
            "invalid_sql_identifier",
            (
                "API mode SQL descriptors only auto-build queries for simple "
                "schema/table identifiers. Provide an explicit query for "
                "advanced SQL."
            ),
            {"field": field_name, "value": normalized},
        )
    return normalized


def _runtime_sql_connection_string(
    provider: str,
    source: Mapping[str, Any],
) -> str:
    connection_string = source.get("connection_string")
    if isinstance(connection_string, str) and connection_string.strip():
        return connection_string.strip()
    if provider in _SQL_DSN_SCHEMES:
        host_value = source.get("host")
        database_value = source.get("database")
        if isinstance(host_value, str) and host_value.strip() and isinstance(
            database_value, str
        ) and database_value.strip():
            username_value = source.get("user") or source.get("username")
            password_value = source.get("password")
            if password_value is not None and not isinstance(password_value, str):
                raise RuntimeValidationError(
                    "invalid_sql_descriptor",
                    "Database connector password must be a string when provided.",
                    {"field": "password", "provider": provider},
                )
            if username_value is not None and not isinstance(username_value, str):
                raise RuntimeValidationError(
                    "invalid_sql_descriptor",
                    "Database connector user must be a string when provided.",
                    {"field": "user", "provider": provider},
                )
            if password_value is not None and not username_value:
                raise RuntimeValidationError(
                    "invalid_sql_descriptor",
                    (
                        "Database connector password requires user/username when "
                        "building a connection_string."
                    ),
                    {"field": "password", "provider": provider},
                )
            host = host_value.strip()
            database = database_value.strip()
            port_value = source.get("port")
            if port_value is None:
                port = _SQL_DEFAULT_PORTS[provider]
            else:
                try:
                    port = int(port_value)
                except (TypeError, ValueError) as exc:
                    raise RuntimeValidationError(
                        "invalid_sql_descriptor",
                        "Database connector port must be an integer when provided.",
                        {"field": "port", "provider": provider},
                    ) from exc
            credentials = ""
            if isinstance(username_value, str) and username_value.strip():
                credentials = quote(username_value.strip(), safe="")
                if isinstance(password_value, str):
                    credentials = f"{credentials}:{quote(password_value, safe='')}"
                credentials = f"{credentials}@"
            return (
                f"{_SQL_DSN_SCHEMES[provider]}://"
                f"{credentials}{host}:{port}/{quote(database, safe='')}"
            )
    if provider != "sqlite":
        raise RuntimeValidationError(
            "missing_connection_string",
            (
                "API mode database descriptors require connection_string or a "
                "structured host/database descriptor."
            ),
            {"provider": provider},
        )
    path_value = source.get("path")
    if not isinstance(path_value, str) or not path_value.strip():
        raise RuntimeValidationError(
            "missing_connection_string",
            "SQLite API descriptors require path or connection_string.",
            {"provider": provider},
        )
    return f"sqlite+pysqlite:///{Path(path_value.strip())}"


def _runtime_sql_query(source: Mapping[str, Any]) -> str:
    query_value = source.get("query")
    if isinstance(query_value, str) and query_value.strip():
        return query_value.strip()
    table = _sql_identifier(source.get("table"), field_name="table")
    schema_value = source.get("schema")
    if schema_value is None:
        return f"SELECT * FROM {table}"  # noqa: S608 - identifier is validated above
    schema = _sql_identifier(schema_value, field_name="schema")
    return f"SELECT * FROM {schema}.{table}"  # noqa: S608 - identifiers are validated above


def _runtime_rest_url(source: Mapping[str, Any]) -> str:
    url_value = source.get("url")
    if isinstance(url_value, str) and url_value.strip():
        return url_value.strip()
    base_url = source.get("base_url")
    if not isinstance(base_url, str) or not base_url.strip():
        raise RuntimeValidationError(
            "missing_rest_url",
            "API mode REST descriptors require url or base_url.",
        )
    path = source.get("path")
    if not isinstance(path, str) or not path.strip():
        return base_url.rstrip("/")
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _normalize_runtime_connection(
    source: Mapping[str, Any],
) -> dict[str, Any]:
    normalized = (
        _flatten_connector_envelope(source)
        if _is_canonical_connector_envelope(source)
        else _strip_none_dict(source)
    )
    raw_type = str(
        normalized.get("type")
        or normalized.get("provider")
        or normalized.get("connection_type")
        or ""
    ).strip().lower()
    if raw_type in _CANONICAL_FILE_TYPES:
        file_type = _file_connector_type(normalized)
        connection = {
            "type": "file",
            "file_type": file_type,
            "file_path": normalized.get("file_path") or normalized.get("path"),
            "delimiter": normalized.get("delimiter"),
            "json_path": normalized.get("json_path"),
            "sheet": normalized.get("sheet"),
        }
        if connection["file_path"]:
            return _strip_none_dict(connection)
        if file_type in {"csv", "tsv"} and normalized.get("csv") is not None:
            connection["content"] = normalized.get("csv")
            return _strip_none_dict(connection)
        if file_type == "json" and normalized.get("json_str") is not None:
            connection["content"] = normalized.get("json_str")
            return _strip_none_dict(connection)
        if file_type == "excel" and normalized.get("excel_b64") is not None:
            connection["content"] = normalized.get("excel_b64")
            return _strip_none_dict(connection)
        if file_type == "parquet" and normalized.get("parquet_b64") is not None:
            connection["content"] = normalized.get("parquet_b64")
            return _strip_none_dict(connection)
        raise RuntimeValidationError(
            "invalid_file_connector",
            (
                "File connectors require a local path or inline content matching "
                "their declared type."
            ),
            {"type": file_type},
        )
    if raw_type in {"rest", "api"}:
        normalized["type"] = "rest_api"
        normalized["url"] = _runtime_rest_url(normalized)
        normalized.pop("base_url", None)
        return _strip_none_dict(normalized)
    if raw_type in _OBJECT_STORAGE_TYPES:
        normalized["type"] = raw_type
        if "format" in normalized and "file_type" not in normalized:
            normalized["file_type"] = normalized.pop("format")
        return _strip_none_dict(normalized)
    if raw_type in _SQL_PROVIDER_TYPES:
        provider = (
            raw_type
            if raw_type != "sql"
            else str(normalized.get("provider") or "").strip().lower()
        )
        normalized["type"] = "sql"
        if provider and provider != "sql":
            normalized["provider"] = provider
        normalized["connection_string"] = _runtime_sql_connection_string(
            provider or "sql",
            normalized,
        )
        for key in ("host", "port", "database", "user", "username", "password"):
            normalized.pop(key, None)
        normalized["query"] = _runtime_sql_query(normalized)
        return _strip_none_dict(normalized)
    if not raw_type:
        raise RuntimeValidationError(
            "missing_connection_type",
            (
                "API mode source descriptors require an explicit connector type "
                "or a direct source payload."
            ),
        )
    return _strip_none_dict(normalized)


def _normalize_api_source_payload(
    source: Mapping[str, Any],
    *,
    explicit_name: str | None,
) -> dict[str, Any]:
    raw_source = (
        _flatten_connector_envelope(source)
        if _is_canonical_connector_envelope(source)
        else _strip_none_dict(source)
    )
    payload = dict(raw_source)
    has_direct_source_keys = any(key in payload for key in _DIRECT_API_SOURCE_KEYS)
    payload["name"] = _runtime_api_source_name(payload, explicit_name=explicit_name)
    if "connection" in payload and isinstance(payload["connection"], Mapping):
        payload["connection"] = _normalize_runtime_connection(payload["connection"])
        return payload
    if has_direct_source_keys:
        return payload
    connection_payload = _normalize_runtime_connection(raw_source)
    return {"name": payload["name"], "connection": connection_payload}


def _is_exact_field_match(field_name: str, hint: str) -> bool:
    return _normalize_text(field_name) == _normalize_text(hint)


def _canonical_metric_hint(hint: str) -> str:
    normalized_hint = _normalize_text(hint)
    for canonical, terms in _METRIC_SYNONYMS.items():
        normalized_terms = {_normalize_text(term) for term in terms}
        if normalized_hint == _normalize_text(canonical) or normalized_hint in normalized_terms:
            return canonical
    return hint


def _parse_raw_text(raw_text: str) -> dict[str, Any]:
    text = raw_text.lower().strip()
    parsed: dict[str, Any] = {}
    for keyword, aggregation in _AGG_KEYWORDS.items():
        if keyword in text:
            parsed["aggregation"] = aggregation
            break
    for canonical, terms in _METRIC_SYNONYMS.items():
        if any(term in text for term in terms):
            parsed["metric"] = canonical
            break
    group_match = re.search(r"\b(?:by|per|grouped by|group by|for each)\s+([a-zA-Z0-9_ ]+)", text)
    if group_match:
        parsed["group_by"] = group_match.group(1).strip()
    return parsed


def _resolve_aggregation(request: Mapping[str, Any]) -> str:
    if isinstance(request.get("aggregation"), str):
        return request["aggregation"].lower().strip()
    raw_text = request.get("raw_text")
    if isinstance(raw_text, str):
        parsed = _parse_raw_text(raw_text)
        if isinstance(parsed.get("aggregation"), str):
            return parsed["aggregation"]
    return "sum"


def _merge_runtime_request(
    request: Mapping[str, Any] | None,
    overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    merged: dict[str, Any] = dict(request or {})
    merged.update(dict(overrides or {}))
    raw_text = merged.get("raw_text")
    if isinstance(raw_text, str):
        parsed = _parse_raw_text(raw_text)
        for key, value in parsed.items():
            merged.setdefault(key, value)
    return merged


def _intent_signature(source_name: str, request: Mapping[str, Any], schema_revision: str) -> str:
    normalized = {
        "source_name": source_name,
        "schema_revision": schema_revision,
        "metric": _normalize_text(str(request.get("metric", ""))),
        "group_by": _normalize_text(str(request.get("group_by", ""))),
        "aggregation": _resolve_aggregation(request),
        "limit": int(request["limit"]) if request.get("limit") is not None else None,
        "order": str(request.get("order", "desc")).lower(),
        "constraints": request.get("constraints") or {},
        "filter": request.get("filter") or {},
    }
    return _stable_hash(normalized)


def _plan_hash(plan: ResolvedPlan) -> str:
    return _stable_hash(plan.to_dict())


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class SourceRegistration:
    source_id: str | None
    dataset_id: str | None
    name: str | None
    status: str
    ingest_mode: str | None = None
    source_schema: dict[str, Any] | None = None
    planner_cache_hit: bool | None = None
    planner_schema_revision: str | None = None
    planner_prewarm_ms: float | None = None
    latency_ms: float | None = None
    row_count: int | None = None

    @classmethod
    def from_api(cls, payload: Any) -> SourceRegistration:
        data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
        return cls(
            source_id=data.get("source_id"),
            dataset_id=data.get("dataset_id"),
            name=data.get("name") or data.get("dataset_name"),
            status=data["status"],
            ingest_mode=data.get("ingest_mode"),
            source_schema=data.get("source_schema") or data.get("schema"),
            planner_cache_hit=data.get("planner_cache_hit"),
            planner_schema_revision=data.get("planner_schema_revision"),
            planner_prewarm_ms=data.get("planner_prewarm_ms"),
            latency_ms=data.get("latency_ms"),
            row_count=data.get("row_count"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ImportPreview:
    registration: SourceRegistration
    preview: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "registration": self.registration.to_dict(),
            "preview": self.preview,
        }


@dataclass(frozen=True)
class ImportFailure:
    source_ref: str
    code: str
    message: str
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ImportBundlePreview:
    registrations: list[SourceRegistration]
    failures: list[ImportFailure]
    preview: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "registrations": [registration.to_dict() for registration in self.registrations],
            "failures": [failure.to_dict() for failure in self.failures],
            "preview": self.preview,
        }


@dataclass(frozen=True)
class ResolvedPlan:
    source_name: str
    metric_column: str
    aggregation: str
    group_column: str | None = None
    join_path: dict[str, Any] | None = None
    filter: dict[str, Any] | None = None
    limit: int | None = None
    order: str = "desc"
    constraints: dict[str, Any] = field(default_factory=dict)
    schema_revision: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> ResolvedPlan:
        data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
        return cls(
            source_name=data["source_name"],
            metric_column=data["metric_column"],
            aggregation=data["aggregation"],
            group_column=data.get("group_column"),
            join_path=data.get("join_path"),
            filter=data.get("filter"),
            limit=data.get("limit"),
            order=data.get("order", "desc"),
            constraints=data.get("constraints") or {},
            schema_revision=data["schema_revision"],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ResolveOutput:
    resolved_plan: ResolvedPlan | None
    confidence: float
    plan: list[str]
    explanation: list[str]
    latency_ms: float
    decision_path: str
    schema_revision: str
    validated: bool
    deterministic_scope: str
    confidence_source: str
    clarification_required: bool = False
    rejection_reason: str | None = None
    request_id: str | None = None
    intent_signature: str = ""
    plan_hash: str | None = None
    source_set: list[str] = field(default_factory=list)
    join_path: list[dict[str, Any]] = field(default_factory=list)
    planner_mode: str | None = None
    resolved_source: str = ""
    resolved_column: str = ""
    resolved_role: str = ""
    candidates: list[dict[str, Any]] = field(default_factory=list)
    source_scores: dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_api(cls, payload: Any) -> ResolveOutput:
        data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
        resolved_plan = data.get("resolved_plan")
        return cls(
            resolved_plan=ResolvedPlan.from_api(resolved_plan) if resolved_plan else None,
            confidence=data["confidence"],
            plan=data.get("plan") or [],
            explanation=data.get("explanation") or [],
            latency_ms=data["latency_ms"],
            decision_path=data["decision_path"],
            schema_revision=data["schema_revision"],
            validated=data["validated"],
            deterministic_scope=data["deterministic_scope"],
            confidence_source=data["confidence_source"],
            clarification_required=data.get("clarification_required", False),
            rejection_reason=data.get("rejection_reason"),
            request_id=data.get("request_id"),
            intent_signature=data.get("intent_signature", ""),
            plan_hash=data.get("plan_hash"),
            source_set=data.get("source_set") or [],
            join_path=data.get("join_path") or [],
            planner_mode=data.get("planner_mode"),
            resolved_source=data.get("resolved_source", ""),
            resolved_column=data.get("resolved_column", ""),
            resolved_role=data.get("resolved_role", ""),
            candidates=data.get("candidates") or [],
            source_scores=data.get("source_scores") or {},
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.resolved_plan is not None:
            data["resolved_plan"] = self.resolved_plan.to_dict()
        return data


@dataclass(frozen=True)
class QueryOutput:
    result: Any
    result_type: str
    confidence: float
    plan: list[str]
    resolved_column: str
    resolved_role: str
    resolved_source: str
    row_count: int
    ambiguous: bool
    exact_spec: bool
    explanation: list[str]
    latency_ms: float
    decision_path: str
    plan_hash: str
    validated: bool
    deterministic_scope: str
    confidence_source: str
    schema_revision: str | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    source_scores: dict[str, float] = field(default_factory=dict)
    clarification_required: bool = False
    rejection_reason: str | None = None
    request_id: str | None = None
    source_set: list[str] = field(default_factory=list)
    join_path: list[dict[str, Any]] = field(default_factory=list)
    planner_mode: str | None = None

    @classmethod
    def from_api(cls, payload: Any) -> QueryOutput:
        data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
        return cls(
            result=data.get("result"),
            result_type=data["result_type"],
            confidence=data["confidence"],
            plan=data.get("plan") or [],
            resolved_column=data["resolved_column"],
            resolved_role=data["resolved_role"],
            resolved_source=data["resolved_source"],
            row_count=data["row_count"],
            ambiguous=data["ambiguous"],
            exact_spec=data["exact_spec"],
            explanation=data.get("explanation") or [],
            latency_ms=data["latency_ms"],
            decision_path=data["decision_path"],
            plan_hash=data["plan_hash"],
            validated=data["validated"],
            deterministic_scope=data["deterministic_scope"],
            confidence_source=data["confidence_source"],
            schema_revision=data.get("schema_revision"),
            candidates=data.get("candidates") or [],
            source_scores=data.get("source_scores") or {},
            clarification_required=data.get("clarification_required", False),
            rejection_reason=data.get("rejection_reason"),
            request_id=data.get("request_id"),
            source_set=data.get("source_set") or [],
            join_path=data.get("join_path") or [],
            planner_mode=data.get("planner_mode"),
        )

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


@dataclass(frozen=True)
class VerifyOutput:
    valid: bool
    errors: list[str]
    suggestions: list[str]
    resolved: dict[str, str]
    latency_ms: float
    verified: bool = False
    request_id: str | None = None
    schema_revision: str | None = None
    plan_hash: str | None = None
    verification_mode: str = "assist"
    rejection_reason: str | None = None
    valid_dimensions: list[str] = field(default_factory=list)
    valid_measures: list[str] = field(default_factory=list)
    source_behavior: str = ""

    @classmethod
    def from_api(cls, payload: Any) -> VerifyOutput:
        data = payload.model_dump() if hasattr(payload, "model_dump") else dict(payload)
        return cls(
            valid=data["valid"],
            errors=data.get("errors") or [],
            suggestions=data.get("suggestions") or [],
            resolved=data.get("resolved") or {},
            latency_ms=data["latency_ms"],
            verified=data.get("verified", False),
            request_id=data.get("request_id"),
            schema_revision=data.get("schema_revision"),
            plan_hash=data.get("plan_hash"),
            verification_mode=data.get("verification_mode", "assist"),
            rejection_reason=data.get("rejection_reason"),
            valid_dimensions=data.get("valid_dimensions") or [],
            valid_measures=data.get("valid_measures") or [],
            source_behavior=data.get("source_behavior", ""),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _registration_fields(registration: SourceRegistration) -> list[str]:
    if not isinstance(registration.source_schema, dict):
        return []
    raw_fields = registration.source_schema.get("fields", [])
    if isinstance(raw_fields, list):
        direct_fields = [str(field) for field in raw_fields if str(field).strip()]
        if direct_fields:
            return direct_fields
    raw_columns = registration.source_schema.get("columns", [])
    if not isinstance(raw_columns, list):
        return []
    fields: list[str] = []
    for column in raw_columns:
        if not isinstance(column, Mapping):
            continue
        name_value = column.get("name")
        if isinstance(name_value, str) and name_value.strip():
            fields.append(name_value)
    return fields


def _bundle_overlap_lines(registrations: list[SourceRegistration]) -> list[str]:
    overlap_lines: list[tuple[int, str]] = []
    for left_index, left in enumerate(registrations):
        left_fields = _registration_fields(left)
        if not left_fields:
            continue
        for right in registrations[left_index + 1 :]:
            right_fields = _registration_fields(right)
            if not right_fields:
                continue
            matches: dict[str, tuple[float, str]] = {}
            for left_field in left_fields:
                best_score = 0.0
                best_right: str | None = None
                for right_field in right_fields:
                    score = _field_overlap_score(left_field, right_field)
                    if score > best_score:
                        best_score = score
                        best_right = right_field
                if best_right is None:
                    continue
                left_tokens = _bundle_field_tokens(left_field)
                right_tokens = _bundle_field_tokens(best_right)
                if best_score >= 1.0 and left_tokens and right_tokens:
                    matches[left_field] = (best_score, best_right)
                elif best_score >= 0.75 and min(len(left_tokens), len(right_tokens)) >= 2:
                    matches[left_field] = (best_score, best_right)
            if not matches:
                continue
            summarized = [
                f"{left_field} ~ {right_field}"
                for left_field, (_score, right_field) in sorted(
                    matches.items(),
                    key=lambda item: (-item[1][0], item[0].lower(), item[1][1].lower()),
                )[:3]
            ]
            left_name = left.name or left.dataset_id or "source"
            right_name = right.name or right.dataset_id or "source"
            overlap_lines.append(
                (
                    len(matches),
                    f"{left_name} ↔ {right_name}: {', '.join(summarized)}",
                )
            )
    return [
        line
        for _count, line in sorted(overlap_lines, key=lambda item: (-item[0], item[1].lower()))[:5]
    ]


class AlgentaRuntimeError(Exception):
    """Base error for the Runtime facade."""

    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}

    def to_error(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": str(self), "details": self.details}}


class RuntimeConfigurationError(AlgentaRuntimeError):
    """Raised when the runtime is not configured for the requested mode."""


class RuntimeValidationError(AlgentaRuntimeError):
    """Raised when the runtime request is invalid or not executable."""


@dataclass
class _LocalSource:
    name: str
    records: list[dict[str, Any]]
    fields: tuple[str, ...]
    schema_revision: str
    dataset_id: str


class Runtime:
    """
    Runtime-first Algenta facade.

    Local mode executes against connected in-memory or file-backed sources.
    API mode delegates to the lower-level `decision_engine.DecisionEngineClient`.
    """

    def __init__(
        self,
        *,
        mode: str = "local",
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        enforce_limits: bool | None = None,
    ) -> None:
        if mode not in {"local", "api"}:
            raise ValueError("Invalid mode. Expected 'local' or 'api'.")
        api_key_from_env = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
        explicit_api_key = api_key is not None
        self._mode = mode
        self._api_key = api_key or api_key_from_env
        self._base_url = base_url
        self._local_sources: dict[str, _LocalSource] = {}
        self._api_registrations_by_name: dict[str, SourceRegistration] = {}
        self._api_registrations_by_dataset: dict[str, SourceRegistration] = {}
        self._api_client: Any | None = None
        self._local_license: Any | None = None
        if enforce_limits is None:
            self._enforce_limits = mode == "local" and explicit_api_key
        else:
            self._enforce_limits = enforce_limits

    def __repr__(self) -> str:
        key_state = "set" if self._api_key else "not set"
        return f"Runtime(mode={self._mode!r}, api_key={key_state})"

    def connect(
        self,
        source: LocalSourceInput,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> SourceRegistration:
        start = time.perf_counter()
        if self._mode == "api":
            if not isinstance(source, Mapping):
                raise RuntimeValidationError(
                    "api_connect_requires_source_descriptor",
                    "API mode connect() expects a structured source descriptor.",
                    {"expected": "dict", "received": type(source).__name__},
                )
            result = self._client().register_source(
                _normalize_api_source_payload(source, explicit_name=name),
                description=description,
            )
            registration = SourceRegistration.from_api(result)
            self._remember_api_registration(registration)
            return registration

        try:
            normalized_source = (
                _normalize_local_runtime_source(source)
                if isinstance(source, Mapping)
                else source
            )
            records = _parse_source(normalized_source)
        except (OSError, ValueError) as exc:
            raise RuntimeValidationError(
                "invalid_local_source",
                f"Unable to connect the local source: {exc}",
                {"name": name or _runtime_source_name(source, len(self._local_sources))},
            ) from exc
        if not records:
            raise RuntimeValidationError(
                "empty_source",
                "Connected source is empty and cannot be queried.",
                {"name": name or _runtime_source_name(source, len(self._local_sources))},
            )

        source_name = _unique_runtime_source_name(
            source,
            len(self._local_sources),
            set(self._local_sources),
            explicit_name=name,
        )
        fields = _ordered_fields(records)
        dataset_id = _stable_hash({"source_name": source_name, "fields": fields})[:24]
        schema_revision = _stable_hash({"dataset_id": dataset_id, "fields": fields})
        self._local_sources[source_name] = _LocalSource(
            name=source_name,
            records=records,
            fields=fields,
            schema_revision=schema_revision,
            dataset_id=dataset_id,
        )
        latency_ms = round((time.perf_counter() - start) * 1000, 3)
        return SourceRegistration(
            source_id=dataset_id,
            dataset_id=dataset_id,
            name=source_name,
            status="ready",
            ingest_mode="local",
            source_schema={"fields": list(fields)},
            planner_cache_hit=False,
            planner_schema_revision=schema_revision,
            planner_prewarm_ms=0.0,
            latency_ms=latency_ms,
            row_count=len(records),
        )

    register_source = connect

    def connect_many(
        self,
        sources: list[LocalSourceInput],
        *,
        names: list[str | None] | None = None,
        description: str | None = None,
    ) -> list[SourceRegistration]:
        if names is not None and len(names) != len(sources):
            raise RuntimeValidationError(
                "invalid_names_length",
                "connect_many() names must match the number of sources.",
                {"sources": len(sources), "names": len(names)},
            )
        registrations: list[SourceRegistration] = []
        for index, source in enumerate(sources):
            source_name = names[index] if names is not None else None
            registrations.append(
                self.connect(source, name=source_name, description=description)
            )
        return registrations

    def import_preview(
        self,
        source: LocalSourceInput,
        *,
        name: str | None = None,
        description: str | None = None,
        source_ref: str | None = None,
    ) -> ImportPreview:
        from algenta.branding import source_import_banner

        registration = self.connect(source, name=name, description=description)
        fields = []
        if isinstance(registration.source_schema, dict):
            raw_fields = registration.source_schema.get("fields", [])
            if isinstance(raw_fields, list):
                fields = [str(field) for field in raw_fields]
        if source_ref is not None:
            resolved_source_ref = source_ref
        else:
            resolved_source_ref = _source_ref_label(source, len(self._local_sources))
        preview = source_import_banner(
            source_name=registration.name or _runtime_source_name(source, len(self._local_sources)),
            source_ref=resolved_source_ref,
            mode=self._mode,
            status=registration.status,
            row_count=registration.row_count,
            fields=fields,
            schema_revision=registration.planner_schema_revision,
            latency_ms=registration.latency_ms,
        )
        return ImportPreview(registration=registration, preview=preview)

    def import_bundle_preview(
        self,
        sources: list[LocalSourceInput],
        *,
        names: list[str | None] | None = None,
        source_refs: list[str | None] | None = None,
        description: str | None = None,
    ) -> ImportBundlePreview:
        from algenta.branding import source_bundle_banner

        if names is not None and len(names) != len(sources):
            raise RuntimeValidationError(
                "invalid_names_length",
                "import_bundle_preview() names must match the number of sources.",
                {"sources": len(sources), "names": len(names)},
            )
        if source_refs is not None and len(source_refs) != len(sources):
            raise RuntimeValidationError(
                "invalid_source_refs_length",
                "import_bundle_preview() source_refs must match the number of sources.",
                {"sources": len(sources), "source_refs": len(source_refs)},
            )

        registrations: list[SourceRegistration] = []
        failures: list[ImportFailure] = []
        for index, source in enumerate(sources):
            source_name = names[index] if names is not None else None
            resolved_source_ref = (
                source_refs[index]
                if source_refs is not None
                else _source_ref_label(source, index)
            )
            try:
                registrations.append(
                    self.connect(source, name=source_name, description=description)
                )
            except AlgentaRuntimeError as exc:
                failures.append(
                    ImportFailure(
                        source_ref=resolved_source_ref,
                        code=exc.code,
                        message=str(exc),
                        name=source_name,
                    )
                )

        preview = source_bundle_banner(
            mode=self._mode,
            imported_count=len(registrations),
            failure_count=len(failures),
            total_rows=sum(registration.row_count or 0 for registration in registrations),
            source_names=[
                registration.name or registration.dataset_id or "source"
                for registration in registrations
            ],
            overlaps=_bundle_overlap_lines(registrations),
            failures=[
                f"{failure.name or failure.source_ref}: {failure.code}"
                for failure in failures
            ],
        )
        return ImportBundlePreview(
            registrations=registrations,
            failures=failures,
            preview=preview,
        )

    def resolve(self, request: Mapping[str, Any] | None = None, **kwargs: Any) -> ResolveOutput:
        start = time.perf_counter()
        merged = _merge_runtime_request(request, kwargs)
        if self._mode == "api":
            exact = self._try_exact_api_resolve(merged, start)
            if exact is not None:
                return exact
            return ResolveOutput.from_api(
                self._client().resolve(self._coerce_api_resolve_payload(merged))
            )
        return self._resolve_local(merged)

    def query(self, request: Any = None, **kwargs: Any) -> QueryOutput:
        if self._mode == "api":
            payload = self._coerce_api_query_payload(request, kwargs)
            return QueryOutput.from_api(self._client().query(payload))
        return self._query_local(request, kwargs)

    def verify(self, request: Any = None, **kwargs: Any) -> VerifyOutput:
        if self._mode == "api":
            payload = self._coerce_api_query_payload(request, kwargs)
            return VerifyOutput.from_api(self._client().verify(payload))
        return self._verify_local(request, kwargs)

    def _client(self) -> Any:
        if self._api_client is not None:
            return self._api_client
        if not self._api_key:
            raise RuntimeConfigurationError(
                "api_key_required",
                "API mode requires an API key. Set ALGENTA_API_KEY or pass api_key=...",
            )
        try:
            from decision_engine import DecisionEngineClient
        except ImportError as exc:  # pragma: no cover - exercised via tests
            raise RuntimeConfigurationError(
                "api_sdk_missing",
                (
                    "API mode requires the algenta-sdk package. "
                    "Install algenta-sdk or algenta-core[cloud]."
                ),
            ) from exc
        self._api_client = DecisionEngineClient(api_key=self._api_key, base_url=self._base_url)
        return self._api_client

    def _uses_hosted_local_limits(self) -> bool:
        return self._mode == "local" and self._enforce_limits

    def _remember_api_registration(self, registration: SourceRegistration) -> None:
        if registration.name:
            self._api_registrations_by_name[registration.name] = registration
        if registration.dataset_id:
            self._api_registrations_by_dataset[registration.dataset_id] = registration

    def _lookup_api_registration(self, request: Mapping[str, Any]) -> SourceRegistration | None:
        dataset_id = request.get("dataset_id")
        if isinstance(dataset_id, str) and dataset_id.strip():
            registration = self._api_registrations_by_dataset.get(dataset_id.strip())
            if registration is not None:
                return registration
        source_name = request.get("source_name")
        if isinstance(source_name, str) and source_name.strip():
            return self._api_registrations_by_name.get(source_name.strip())
        return None

    def _fetch_api_source_schema_revision(self, registration: SourceRegistration) -> str | None:
        source_id = registration.dataset_id or registration.source_id
        if not source_id:
            return None
        client = self._client()
        fetcher = getattr(client, "_request", None)
        if not callable(fetcher):
            return None
        try:
            payload = fetcher("GET", f"/v1/sources/{source_id}")
        except Exception:
            return None
        if hasattr(payload, "model_dump"):
            payload = payload.model_dump()
        if not isinstance(payload, Mapping):
            return None
        entry = payload.get("entry")
        if isinstance(entry, Mapping):
            entry_revision = entry.get("source_schema_revision") or entry.get("schema_revision")
            if isinstance(entry_revision, str) and entry_revision.strip():
                return entry_revision
        schema = payload.get("schema")
        if isinstance(schema, Mapping):
            schema_revision = schema.get("schema_revision")
            if isinstance(schema_revision, str) and schema_revision.strip():
                return schema_revision
        return None

    def _try_exact_api_resolve(
        self,
        request: Mapping[str, Any],
        start: float,
    ) -> ResolveOutput | None:
        registration = self._lookup_api_registration(request)
        if registration is None or not registration.name:
            return None
        schema_revision = (
            self._fetch_api_source_schema_revision(registration)
            or registration.planner_schema_revision
        )
        if not schema_revision:
            return None

        fields = set(_registration_fields(registration))
        if not fields:
            return None

        metric_column: str | None = None
        metric_value = request.get("metric_column")
        if isinstance(metric_value, str) and metric_value in fields:
            metric_column = metric_value
        else:
            metric_hint = request.get("metric")
            if isinstance(metric_hint, str) and metric_hint in fields:
                metric_column = metric_hint
        if metric_column is None:
            return None

        group_column: str | None = None
        group_value = request.get("group_column")
        if isinstance(group_value, str):
            if group_value not in fields:
                return None
            group_column = group_value
        else:
            group_hint = request.get("group_by")
            if isinstance(group_hint, str):
                if group_hint not in fields:
                    return None
                group_column = group_hint
            elif isinstance(group_hint, list):
                group_candidates = [
                    item.strip()
                    for item in group_hint
                    if isinstance(item, str) and item.strip()
                ]
                if len(group_candidates) > 1:
                    return None
                if group_candidates:
                    if group_candidates[0] not in fields:
                        return None
                    group_column = group_candidates[0]

        plan = ResolvedPlan(
            source_name=registration.name,
            metric_column=metric_column,
            aggregation=_resolve_aggregation(request),
            group_column=group_column,
            join_path=request.get("join_path"),
            filter=request.get("filter"),
            limit=request.get("limit"),
            order=str(request.get("order", "desc")),
            constraints=dict(request.get("constraints") or {}),
            schema_revision=schema_revision,
        )
        latency_ms = round((time.perf_counter() - start) * 1000, 3)
        intent_signature = _intent_signature(registration.name, request, schema_revision)
        plan_hash = _plan_hash(plan)
        explanation = [
            f"Using registered source '{registration.name}' as an exact source.",
            f"Using exact metric column '{metric_column}'.",
            *([f"Using exact group column '{group_column}'." ] if group_column else []),
        ]
        return ResolveOutput(
            resolved_plan=plan,
            confidence=1.0,
            plan=[
                f"Use exact source '{registration.name}'.",
                f"Use exact metric column '{metric_column}'.",
                *([f"Group by exact column '{group_column}'." ] if group_column else []),
            ],
            explanation=explanation,
            latency_ms=latency_ms,
            decision_path="exact_spec",
            schema_revision=schema_revision,
            validated=True,
            deterministic_scope="api_registered_source",
            confidence_source="runtime_exact_spec",
            request_id=f"runtime_exact_{intent_signature[:12]}",
            intent_signature=intent_signature,
            plan_hash=plan_hash,
            source_set=[registration.name],
            join_path=[],
            planner_mode="runtime_exact_spec",
            resolved_source=registration.name,
            resolved_column=metric_column,
            resolved_role="measure",
            candidates=[],
            source_scores={registration.name: 1.0},
        )

    def _coerce_api_resolve_payload(self, request: Mapping[str, Any]) -> dict[str, Any]:
        payload = dict(request)
        source_name = payload.pop("source_name", None)
        if isinstance(source_name, str) and source_name.strip():
            payload.setdefault("preferred_source", source_name.strip())
            payload.setdefault("allow_org_scope", True)

        metric = payload.get("metric")
        if isinstance(metric, str):
            payload["metric"] = {"role": "metric", "hint": metric.strip()}

        group_by = payload.get("group_by")
        if isinstance(group_by, str):
            payload["group_by"] = [group_by]
        elif group_by is None:
            group_column = payload.pop("group_column", None)
            if isinstance(group_column, str) and group_column.strip():
                payload["group_by"] = [group_column.strip()]
        else:
            payload.pop("group_column", None)

        payload.pop("metric_column", None)
        payload.pop("resolved_plan", None)
        return payload

    def _ensure_local_execution_entitlement(self) -> None:
        if not self._uses_hosted_local_limits():
            return
        if not self._api_key:
            raise RuntimeConfigurationError(
                "api_key_required",
                "Hosted local runtime limits require an API key.",
            )
        try:
            from apps.runtime.license import load_license
        except ImportError as exc:  # pragma: no cover - exercised in packaged environments
            raise RuntimeConfigurationError(
                "hosted_local_runtime_unavailable",
                (
                    "Hosted local runtime limits require the full Algenta local runtime "
                    "components. Use the repository runtime path or install the full runtime "
                    "distribution before enabling enforce_limits."
                ),
            ) from exc
        if self._local_license is None or not getattr(self._local_license, "valid", False):
            self._local_license = load_license(self._api_key)
        if not self._local_license.valid:
            raise RuntimeConfigurationError(
                "license_required",
                self._local_license.message or "A valid local device license is required.",
                {
                    "source": getattr(self._local_license, "source", "unknown"),
                    "plan": getattr(self._local_license, "plan", "unknown"),
                },
            )

    def _consume_local_credit(self) -> None:
        if not self._uses_hosted_local_limits():
            return
        try:
            from apps.runtime.credits import consume_credit
        except ImportError as exc:  # pragma: no cover - exercised in packaged environments
            raise RuntimeConfigurationError(
                "hosted_local_runtime_unavailable",
                (
                    "Hosted local runtime limits require the full Algenta local runtime "
                    "components. Use the repository runtime path or install the full runtime "
                    "distribution before enabling enforce_limits."
                ),
            ) from exc
        permitted = bool(_run_sync(consume_credit(allow_background_refresh=False)))
        if not permitted:
            raise RuntimeValidationError(
                "quota_exhausted",
                (
                    "Local execution quota exhausted. Reconnect to the control plane to "
                    "refresh credits or renew the device license before continuing."
                ),
            )

    def _select_local_source(self, request: Mapping[str, Any]) -> _LocalSource:
        requested_name = request.get("source_name") or request.get("dataset_id")
        if isinstance(requested_name, str):
            if requested_name in self._local_sources:
                return self._local_sources[requested_name]
            for source in self._local_sources.values():
                if source.dataset_id == requested_name:
                    return source
            raise RuntimeValidationError(
                "unknown_source",
                "Requested source is not connected to this runtime.",
                {"requested": requested_name, "available": sorted(self._local_sources)},
            )
        if len(self._local_sources) == 1:
            return next(iter(self._local_sources.values()))
        if not self._local_sources:
            raise RuntimeConfigurationError(
                "source_required",
                "No local sources are connected. Call Runtime.connect(...) before resolve/query.",
            )
        raise RuntimeValidationError(
            "source_required",
            "Multiple local sources are connected. Provide source_name or dataset_id.",
            {"available": sorted(self._local_sources)},
        )

    def _rank_fields(
        self,
        source: _LocalSource,
        hint: str,
        *,
        numeric_only: bool,
    ) -> list[dict[str, Any]]:
        ranked: list[dict[str, Any]] = []
        canonical_hint = _canonical_metric_hint(hint)
        hint_terms = {
            _normalize_text(canonical_hint),
            *{_normalize_text(term) for term in _METRIC_SYNONYMS.get(canonical_hint, [])},
        }

        for field_name in source.fields:
            if numeric_only and not _is_numeric_field(field_name, source.records):
                continue
            score, reasons = _semantic_similarity(field_name, hint)
            normalized_field = _normalize_text(field_name)
            if normalized_field in hint_terms:
                score = max(score, 1.0)
                reasons = [*reasons, "canonical synonym match"]
            if _is_exact_field_match(field_name, hint):
                score = 1.0
                reasons = ["exact field match"]
            normalized_phrase = _normalize_text(hint.replace(" ", "_"))
            if not numeric_only and " " in hint and normalized_phrase == normalized_field:
                score = max(score, 0.95)
                reasons = [*reasons, "normalized phrase match"]
            ranked.append(
                {
                    "field": field_name,
                    "score": round(score, 4),
                    "reasons": reasons or ["schema similarity"],
                    "is_numeric": _is_numeric_field(field_name, source.records),
                }
            )

        ranked.sort(key=lambda item: (item["score"], item["field"]), reverse=True)
        return ranked

    def _build_candidates(
        self,
        source: _LocalSource,
        ranked: list[dict[str, Any]],
        role: str,
    ) -> list[dict[str, Any]]:
        return [
            {
                "source": source.name,
                "column": item["field"],
                "role": role,
                "confidence": item["score"],
                "notes": item["reasons"],
                "score_components": {"schema_similarity": item["score"]},
            }
            for item in ranked[:5]
        ]

    def _resolve_local(self, request: Mapping[str, Any]) -> ResolveOutput:
        start = time.perf_counter()
        source = self._select_local_source(request)
        metric_hint = request.get("metric")
        group_hint = request.get("group_by")
        if not isinstance(metric_hint, str) or not metric_hint.strip():
            raise RuntimeValidationError(
                "metric_required",
                "Local Runtime.resolve() requires a structured metric field.",
                {"request": dict(request)},
            )

        aggregation = _resolve_aggregation(request)
        metric_ranked = self._rank_fields(source, metric_hint, numeric_only=True)
        if not metric_ranked:
            return self._rejected_resolve(
                source,
                request,
                "schema_unresolved",
                [f"No numeric field matched metric '{metric_hint}'."],
                start,
            )

        metric_choice = metric_ranked[0]
        metric_candidates = self._build_candidates(source, metric_ranked, "measure")
        metric_second = metric_ranked[1]["score"] if len(metric_ranked) > 1 else 0.0
        metric_gap = round(metric_choice["score"] - metric_second, 4)

        if metric_choice["score"] < 0.70:
            return self._rejected_resolve(
                source,
                request,
                "schema_unresolved",
                [f"Top metric match '{metric_choice['field']}' scored below the 0.70 threshold."],
                start,
                candidates=metric_candidates,
            )

        if metric_choice["score"] < 0.85 or metric_gap < 0.10:
            return self._clarify_resolve(
                source,
                request,
                [f"Metric mapping for '{metric_hint}' is not decisive enough for execution."],
                start,
                candidates=metric_candidates,
            )

        resolved_group: str | None = None
        group_candidates: list[dict[str, Any]] = []
        if isinstance(group_hint, str) and group_hint.strip():
            group_ranked = self._rank_fields(source, group_hint, numeric_only=False)
            group_candidates = self._build_candidates(source, group_ranked, "dimension")
            if not group_ranked:
                return self._rejected_resolve(
                    source,
                    request,
                    "schema_unresolved",
                    [f"No field matched group_by '{group_hint}'."],
                    start,
                    candidates=metric_candidates,
                )
            group_choice = group_ranked[0]
            group_second = group_ranked[1]["score"] if len(group_ranked) > 1 else 0.0
            group_gap = round(group_choice["score"] - group_second, 4)
            if group_choice["score"] < 0.70:
                return self._rejected_resolve(
                    source,
                    request,
                    "schema_unresolved",
                    [
                        "Top group_by match "
                        f"'{group_choice['field']}' scored below the 0.70 threshold."
                    ],
                    start,
                    candidates=[*metric_candidates, *group_candidates],
                )
            if group_choice["score"] < 0.85 or group_gap < 0.10:
                return self._clarify_resolve(
                    source,
                    request,
                    [f"Group_by mapping for '{group_hint}' is not decisive enough for execution."],
                    start,
                    candidates=[*metric_candidates, *group_candidates],
                )
            resolved_group = group_choice["field"]

        plan = ResolvedPlan(
            source_name=source.name,
            metric_column=metric_choice["field"],
            aggregation=aggregation,
            group_column=resolved_group,
            filter=request.get("filter"),
            limit=request.get("limit"),
            order=str(request.get("order", "desc")),
            constraints=dict(request.get("constraints") or {}),
            schema_revision=source.schema_revision,
        )
        plan_hash = _plan_hash(plan)
        intent_signature = _intent_signature(source.name, request, source.schema_revision)
        latency_ms = round((time.perf_counter() - start) * 1000, 3)
        decision_path = (
            "exact_spec"
            if _is_exact_field_match(metric_choice["field"], metric_hint)
            and (resolved_group is None or _is_exact_field_match(resolved_group, str(group_hint)))
            else "planner_hint"
        )
        explanation = [
            f"Resolved metric '{metric_hint}' to '{metric_choice['field']}'.",
            *(
                [f"Resolved group_by '{group_hint}' to '{resolved_group}'."]
                if resolved_group
                else []
            ),
        ]
        return ResolveOutput(
            resolved_plan=plan,
            confidence=1.0,
            plan=[
                f"Use source '{source.name}'.",
                f"Aggregate '{metric_choice['field']}' with '{aggregation}'.",
                *([f"Group by '{resolved_group}'." ] if resolved_group else []),
            ],
            explanation=explanation,
            latency_ms=latency_ms,
            decision_path=decision_path,
            schema_revision=source.schema_revision,
            validated=True,
            deterministic_scope="local_registered_source",
            confidence_source="local_schema_match",
            request_id=f"local_{intent_signature[:12]}",
            intent_signature=intent_signature,
            plan_hash=plan_hash,
            source_set=[source.name],
            join_path=[],
            planner_mode="local_structured_intent",
            resolved_source=source.name,
            resolved_column=metric_choice["field"],
            resolved_role="measure",
            candidates=[*metric_candidates, *group_candidates],
            source_scores={source.name: 1.0},
        )

    def _rejected_resolve(
        self,
        source: _LocalSource,
        request: Mapping[str, Any],
        reason: str,
        explanation: list[str],
        start: float,
        *,
        candidates: list[dict[str, Any]] | None = None,
    ) -> ResolveOutput:
        intent_signature = _intent_signature(source.name, request, source.schema_revision)
        latency_ms = round((time.perf_counter() - start) * 1000, 3)
        return ResolveOutput(
            resolved_plan=None,
            confidence=0.0,
            plan=[],
            explanation=explanation,
            latency_ms=latency_ms,
            decision_path="planner_hint",
            schema_revision=source.schema_revision,
            validated=False,
            deterministic_scope="local_registered_source",
            confidence_source="local_schema_match",
            clarification_required=False,
            rejection_reason=reason,
            request_id=f"local_{intent_signature[:12]}",
            intent_signature=intent_signature,
            source_set=[source.name],
            join_path=[],
            planner_mode="local_structured_intent",
            resolved_source=source.name,
            candidates=candidates or [],
            source_scores={source.name: 1.0},
        )

    def _clarify_resolve(
        self,
        source: _LocalSource,
        request: Mapping[str, Any],
        explanation: list[str],
        start: float,
        *,
        candidates: list[dict[str, Any]],
    ) -> ResolveOutput:
        intent_signature = _intent_signature(source.name, request, source.schema_revision)
        latency_ms = round((time.perf_counter() - start) * 1000, 3)
        return ResolveOutput(
            resolved_plan=None,
            confidence=0.75,
            plan=[],
            explanation=explanation,
            latency_ms=latency_ms,
            decision_path="planner_hint",
            schema_revision=source.schema_revision,
            validated=False,
            deterministic_scope="local_registered_source",
            confidence_source="local_schema_match",
            clarification_required=True,
            rejection_reason=None,
            request_id=f"local_{intent_signature[:12]}",
            intent_signature=intent_signature,
            source_set=[source.name],
            join_path=[],
            planner_mode="local_structured_intent",
            resolved_source=source.name,
            candidates=candidates,
            source_scores={source.name: 1.0},
        )

    def _coerce_plan(self, request: Any, kwargs: Mapping[str, Any]) -> ResolvedPlan:
        if kwargs:
            payload = dict(kwargs)
        elif isinstance(request, ResolveOutput):
            resolved_plan = request.resolved_plan
            if resolved_plan is None:
                raise RuntimeValidationError(
                    "query_requires_executable_plan",
                    (
                        "Runtime.query() requires an executable plan. "
                        "Resolve returned clarification or rejection."
                    ),
                )
            if isinstance(resolved_plan, ResolvedPlan):
                return resolved_plan
            return ResolvedPlan.from_api(resolved_plan)
        elif isinstance(request, Mapping) and "resolved_plan" in request:
            resolved = request.get("resolved_plan")
            if resolved is None:
                raise RuntimeValidationError(
                    "query_requires_executable_plan",
                    (
                        "Runtime.query() requires an executable plan. "
                        "The provided resolve payload is not executable."
                    ),
                )
            return ResolvedPlan.from_api(resolved)
        elif isinstance(request, ResolvedPlan):
            return request
        elif isinstance(request, Mapping):
            payload = dict(request)
        else:
            raise RuntimeValidationError(
                "query_request_invalid",
                "Runtime.query() expects a ResolvedPlan, resolve output, or exact plan mapping.",
                {"received": type(request).__name__},
            )
        return ResolvedPlan.from_api(payload)

    def _query_local(self, request: Any, kwargs: Mapping[str, Any]) -> QueryOutput:
        start = time.perf_counter()
        plan = self._coerce_plan(request, kwargs)
        if plan.source_name not in self._local_sources:
            raise RuntimeValidationError(
                "unknown_source",
                "Query plan references a source that is not connected to this runtime.",
                {"source_name": plan.source_name},
            )
        source = self._local_sources[plan.source_name]
        if plan.schema_revision != source.schema_revision:
            raise RuntimeValidationError(
                "schema_revision_mismatch",
                "Query plan schema_revision does not match the connected source.",
                {"expected": source.schema_revision, "received": plan.schema_revision},
            )
        self._ensure_local_execution_entitlement()
        self._consume_local_credit()
        result_rows = _execute(
            source.records,
            plan.metric_column,
            plan.group_column,
            plan.aggregation,
            plan.limit or 100,
        )
        if plan.group_column:
            result_type = "table"
            result_value: Any = result_rows
            row_count = len(result_rows)
        else:
            scalar_row = result_rows[0] if result_rows else {}
            result_type = "scalar"
            result_value = scalar_row.get(plan.metric_column)
            row_count = 1 if scalar_row else 0

        latency_ms = round((time.perf_counter() - start) * 1000, 3)
        return QueryOutput(
            result=result_value,
            result_type=result_type,
            confidence=1.0,
            plan=[
                f"Use source '{source.name}'.",
                f"Aggregate '{plan.metric_column}' with '{plan.aggregation}'.",
                *([f"Group by '{plan.group_column}'." ] if plan.group_column else []),
            ],
            resolved_column=plan.metric_column,
            resolved_role="measure",
            resolved_source=source.name,
            row_count=row_count,
            ambiguous=False,
            exact_spec=True,
            explanation=["Executed deterministic local plan."],
            latency_ms=latency_ms,
            decision_path="exact_spec",
            plan_hash=_plan_hash(plan),
            validated=True,
            deterministic_scope="local_registered_source",
            confidence_source="local_exact_execution",
            schema_revision=source.schema_revision,
            candidates=[],
            source_scores={source.name: 1.0},
            clarification_required=False,
            rejection_reason=None,
            request_id=f"local_query_{_plan_hash(plan)[:12]}",
            source_set=[source.name],
            join_path=[],
            planner_mode="local_structured_intent",
        )

    def _verify_local(self, request: Any, kwargs: Mapping[str, Any]) -> VerifyOutput:
        start = time.perf_counter()
        try:
            plan = self._coerce_plan(request, kwargs)
        except AlgentaRuntimeError as exc:
            latency_ms = round((time.perf_counter() - start) * 1000, 3)
            return VerifyOutput(
                valid=False,
                errors=[str(exc)],
                suggestions=[
                    "Run Runtime.resolve(...) again with a more explicit metric or source."
                ],
                resolved={},
                latency_ms=latency_ms,
                verified=False,
                rejection_reason=exc.code,
                verification_mode="local",
            )

        source = self._local_sources.get(plan.source_name)
        errors: list[str] = []
        if source is None:
            errors.append(f"Source '{plan.source_name}' is not connected.")
        else:
            if plan.schema_revision != source.schema_revision:
                errors.append("schema_revision mismatch")
            if plan.metric_column not in source.fields:
                errors.append(f"Metric column '{plan.metric_column}' is missing.")
            if plan.group_column and plan.group_column not in source.fields:
                errors.append(f"Group column '{plan.group_column}' is missing.")

        latency_ms = round((time.perf_counter() - start) * 1000, 3)
        valid = not errors
        return VerifyOutput(
            valid=valid,
            errors=errors,
            suggestions=[] if valid else [
                "Reconnect the source or rerun resolve against the current schema."
            ],
            resolved={
                "source_name": plan.source_name,
                "metric_column": plan.metric_column,
                "group_column": plan.group_column or "",
            },
            latency_ms=latency_ms,
            verified=valid,
            request_id=f"local_verify_{_plan_hash(plan)[:12]}",
            schema_revision=plan.schema_revision,
            plan_hash=_plan_hash(plan),
            verification_mode="local",
            rejection_reason=None if valid else "plan_verification_failed",
            valid_dimensions=[plan.group_column] if plan.group_column else [],
            valid_measures=[plan.metric_column],
            source_behavior="local_registered_source",
        )

    def _coerce_api_query_payload(self, request: Any, kwargs: Mapping[str, Any]) -> dict[str, Any]:
        if kwargs:
            payload = dict(kwargs)
        elif isinstance(request, ResolveOutput):
            if request.resolved_plan is None:
                raise RuntimeValidationError(
                    "query_requires_executable_plan",
                    (
                        "Runtime query/verify requires an executable plan. "
                        "Resolve returned clarification or rejection."
                    ),
                )
            payload = {"resolved_plan": request.resolved_plan.to_dict()}
        elif isinstance(request, QueryOutput | VerifyOutput):
            payload = request.to_dict()
        elif isinstance(request, ResolvedPlan):
            payload = {"resolved_plan": request.to_dict()}
        elif isinstance(request, Mapping):
            mapped = dict(request)
            if (
                isinstance(mapped.get("source_name"), str)
                and isinstance(mapped.get("metric_column"), str)
                and isinstance(mapped.get("schema_revision"), str)
            ):
                payload = {"resolved_plan": mapped}
            else:
                payload = mapped
        elif request is None:
            payload = {}
        else:
            raise RuntimeValidationError(
                "api_request_invalid",
                "API mode expects a mapping, resolve output, or exact plan.",
                {"received": type(request).__name__},
            )
        has_resolved_plan = "resolved_plan" in payload and payload["resolved_plan"] is not None
        if has_resolved_plan and hasattr(payload["resolved_plan"], "to_dict"):
            payload["resolved_plan"] = payload["resolved_plan"].to_dict()
        return payload


def _run_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except builtins.RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    import concurrent.futures

    def _run_in_thread() -> Any:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_in_thread).result()
