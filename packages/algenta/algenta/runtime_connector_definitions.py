from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Mapping
from typing import Any

from algenta.runtime_errors import RuntimeValidationError

_CANONICAL_FILE_TYPES = frozenset({"csv", "tsv", "json", "excel", "xlsx", "xls", "parquet"})
_CANONICAL_API_TYPES = frozenset({"rest", "rest_api", "api"})
_LOCAL_RUNTIME_CONNECTOR_TYPES = _CANONICAL_FILE_TYPES | frozenset({"sqlite", "sqlite3"})


def _stable_connector_hash(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _inline_preview_cache_key(
    *,
    operation: str,
    connector_type: str,
    config: Mapping[str, Any],
) -> str:
    return _stable_connector_hash(
        {
            "operation": operation,
            "connector_type": connector_type,
            "config": dict(config),
        }
    )


def _inline_preview_capability_key(*, operation: str) -> str:
    return operation


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


def _normalize_connector_definition(
    *,
    connector: Mapping[str, Any] | None,
    connector_type: str | None,
    config: Mapping[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    if connector is not None:
        normalized = (
            _flatten_connector_envelope(connector)
            if _is_canonical_connector_envelope(connector)
            else _strip_none_dict(connector)
        )
        raw_type = normalized.pop("type", None) or normalized.pop("provider", None)
        if not isinstance(raw_type, str) or not raw_type.strip():
            raise RuntimeValidationError(
                "invalid_connector",
                "Connector descriptors require a non-empty type or provider.",
            )
        return raw_type.strip().lower().replace("-", "_"), dict(normalized)
    if not connector_type:
        raise RuntimeValidationError(
            "invalid_connector",
            "Provide connector=... or connector_type=... with config=....",
        )
    if config is not None and not isinstance(config, Mapping):
        raise RuntimeValidationError(
            "invalid_connector",
            "config must be an object when connector_type is provided.",
        )
    return connector_type.strip().lower().replace("-", "_"), dict(config or {})
