"""REST API data source connector."""

from __future__ import annotations

import asyncio
import copy
from functools import lru_cache
from typing import Any

import httpx

from apps.api_server.services.columnar_loader import records_to_arrow_table
from apps.api_server.services.egress_guard import (
    audit_context_from_config,
    sync_http_request,
)

from .base import BaseConnector, ConnectorRegistry


class RESTPaginationError(RuntimeError):
    """Raised when REST pagination configuration cannot terminate safely."""


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


def _normalize_records(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        return [data]
    return []


def _is_empty_pagination_value(value: Any) -> bool:
    if value is None:
        return True
    if value == "":
        return True
    if isinstance(value, list | dict):
        return len(value) == 0
    return False


def _parse_link_header(value: str) -> dict[str, str]:
    links: dict[str, str] = {}
    for part in value.split(","):
        section = part.strip()
        if not section or ";" not in section:
            continue
        url_part, *params = [item.strip() for item in section.split(";")]
        if not (url_part.startswith("<") and url_part.endswith(">")):
            continue
        url = url_part[1:-1].strip()
        rel = ""
        for param in params:
            if param.startswith("rel="):
                rel = param.split("=", 1)[1].strip().strip('"')
                break
        if url and rel:
            links[rel] = url
    return links


def _payload_error_message(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    raw_errors = payload.get("Errors")
    if not raw_errors:
        raw_errors = payload.get("errors")
    if not raw_errors:
        return None
    normalized_errors: list[str] = []
    if isinstance(raw_errors, list):
        for item in raw_errors:
            if isinstance(item, dict):
                description = str(item.get("description") or item.get("message") or "").strip()
                field = str(item.get("field") or "").strip()
                if description and field:
                    normalized_errors.append(f"{field}: {description}")
                elif description:
                    normalized_errors.append(description)
                else:
                    normalized_errors.append(str(item))
            else:
                normalized_errors.append(str(item))
    elif isinstance(raw_errors, dict):
        normalized_errors.append(str(raw_errors.get("message") or raw_errors))
    else:
        normalized_errors.append(str(raw_errors))
    message = "; ".join(part for part in normalized_errors if part)
    return message or "unknown API error"


def _validated_pagination_config(config: dict[str, Any]) -> dict[str, Any] | None:
    raw = config.get("pagination")
    if not isinstance(raw, dict) or not raw:
        return None
    pagination = copy.deepcopy(raw)
    mode = str(pagination.get("mode", "")).strip().lower()
    if mode not in {"page_number", "cursor_path"}:
        raise ValueError("REST pagination.mode must be 'page_number' or 'cursor_path'")
    max_pages = int(pagination.get("max_pages", 0) or 0)
    if max_pages <= 0:
        raise ValueError("REST pagination.max_pages must be a positive integer")
    pagination["mode"] = mode
    pagination["max_pages"] = max_pages
    if mode == "page_number":
        pagination["page_param"] = str(pagination.get("page_param", "page") or "page")
        pagination["start_page"] = int(pagination.get("start_page", 1) or 1)
    else:
        next_path = str(pagination.get("next_path") or pagination.get("cursor_path") or "").strip()
        if not next_path:
            raise ValueError("REST cursor pagination requires pagination.next_path or cursor_path")
        pagination["next_path"] = next_path
        cursor_param = str(pagination.get("cursor_param", "") or "").strip()
        if cursor_param:
            pagination["cursor_param"] = cursor_param
    page_size_param = str(pagination.get("page_size_param", "") or "").strip()
    if page_size_param:
        pagination["page_size_param"] = page_size_param
    if pagination.get("page_size") is not None:
        pagination["page_size"] = int(pagination["page_size"])
    next_link_rel = str(pagination.get("next_link_rel", "") or "").strip()
    if next_link_rel:
        pagination["next_link_rel"] = next_link_rel
    has_more_path = str(pagination.get("has_more_path", "") or "").strip()
    if has_more_path:
        pagination["has_more_path"] = has_more_path
    next_path = str(pagination.get("next_path", "") or "").strip()
    if next_path:
        pagination["next_path"] = next_path
    return pagination


def _request_parts(
    config: dict[str, Any],
) -> tuple[str, str, dict[str, str], dict[str, Any], Any, float, str]:
    url = str(config.get("url", "") or "").strip()
    if not url:
        raise ValueError("REST connector requires config.url")
    method = str(config.get("method", "GET") or "GET").upper()
    if method not in {"GET", "POST"}:
        raise ValueError("REST connector only supports GET and POST")
    headers = dict(config.get("headers", {}) or {})
    params = dict(config.get("params", {}) or {})
    body = copy.deepcopy(config.get("body"))
    timeout = float(config.get("timeout", 30) or 30)
    data_path = str(config.get("data_path", "") or "")
    if data_path and any(not segment.strip() for segment in data_path.split(".")):
        raise ValueError("invalid identifier: REST data_path must not contain empty path segments")
    return url, method, headers, params, body, timeout, data_path


def _request_payload_to_records(payload: Any, data_path: str) -> list[dict[str, Any]]:
    records = _normalize_records(_follow_data_path(payload, data_path))
    if not records:
        error_message = _payload_error_message(payload)
        if error_message:
            raise ValueError(f"REST API error payload: {error_message}")
    return records


def _page_number_termination(
    *,
    payload: Any,
    headers: httpx.Headers,
    page_records: list[dict[str, Any]],
    pagination: dict[str, Any],
) -> bool:
    next_link_rel = str(pagination.get("next_link_rel", "") or "").strip()
    if next_link_rel:
        links = _parse_link_header(headers.get("link", ""))
        return not bool(links.get(next_link_rel))
    has_more_path = str(pagination.get("has_more_path", "") or "").strip()
    if has_more_path:
        return not bool(_follow_data_path(payload, has_more_path))
    next_path = str(pagination.get("next_path", "") or "").strip()
    if next_path:
        next_value = _follow_data_path(payload, next_path)
        return _is_empty_pagination_value(next_value)
    return not page_records


def _cursor_termination(
    *,
    payload: Any,
    pagination: dict[str, Any],
) -> tuple[bool, str | None, str | None]:
    next_value = _follow_data_path(payload, str(pagination["next_path"]))
    if _is_empty_pagination_value(next_value):
        return True, None, None
    if isinstance(next_value, str) and next_value.startswith(("http://", "https://")):
        return False, None, next_value
    return False, str(next_value), None


@lru_cache(maxsize=8)
def _sync_rest_client(timeout: float) -> httpx.Client:
    return httpx.Client(timeout=timeout, follow_redirects=True)


async def fetch_rest_records_async(config: dict[str, Any]) -> list[dict[str, Any]]:
    return await asyncio.to_thread(fetch_rest_records_sync, copy.deepcopy(config))


def fetch_rest_records_sync(config: dict[str, Any]) -> list[dict[str, Any]]:
    url, method, headers, params, body, timeout, data_path = _request_parts(config)
    pagination = _validated_pagination_config(config)
    client = _sync_rest_client(timeout)
    audit_context = audit_context_from_config(config)
    if pagination is None:
        if method == "POST":
            response = sync_http_request(
                method="POST",
                url=url,
                surface="rest_connector_fetch",
                explicit_configured=True,
                egress_class="customer_connector",
                audit_context=audit_context,
                client=client,
                headers=headers,
                params=params,
                json=body,
            )
        else:
            response = sync_http_request(
                method="GET",
                url=url,
                surface="rest_connector_fetch",
                explicit_configured=True,
                egress_class="customer_connector",
                audit_context=audit_context,
                client=client,
                headers=headers,
                params=params,
            )
        response.raise_for_status()
        return _request_payload_to_records(response.json(), data_path)

    records: list[dict[str, Any]] = []
    seen_cursors: set[str] = set()
    page_number = int(pagination.get("start_page", 1) or 1)
    cursor_value = str(pagination.get("initial_cursor", "") or "").strip() or None
    next_url_override: str | None = None

    for _ in range(int(pagination["max_pages"])):
        page_url = next_url_override or url
        page_params = copy.deepcopy(params)
        page_body = copy.deepcopy(body)
        if pagination["mode"] == "page_number":
            page_params[str(pagination["page_param"])] = page_number
        elif cursor_value is not None and pagination.get("cursor_param"):
            page_params[str(pagination["cursor_param"])] = cursor_value
        page_size_param = str(pagination.get("page_size_param", "") or "").strip()
        if page_size_param and pagination.get("page_size") is not None:
            page_params[page_size_param] = pagination["page_size"]

        if method == "POST":
            response = sync_http_request(
                method="POST",
                url=page_url,
                surface="rest_connector_pagination",
                explicit_configured=True,
                egress_class="customer_connector",
                audit_context=audit_context,
                client=client,
                headers=headers,
                params=page_params,
                json=page_body,
            )
        else:
            response = sync_http_request(
                method="GET",
                url=page_url,
                surface="rest_connector_pagination",
                explicit_configured=True,
                egress_class="customer_connector",
                audit_context=audit_context,
                client=client,
                headers=headers,
                params=page_params,
            )
        response.raise_for_status()
        payload = response.json()
        page_records = _request_payload_to_records(payload, data_path)
        records.extend(page_records)

        if pagination["mode"] == "page_number":
            if _page_number_termination(
                payload=payload,
                headers=response.headers,
                page_records=page_records,
                pagination=pagination,
            ):
                return records
            page_number += 1
            continue

        terminated, next_cursor, next_url = _cursor_termination(
            payload=payload,
            pagination=pagination,
        )
        if terminated:
            return records
        token = next_url or next_cursor or ""
        if token in seen_cursors:
            raise RESTPaginationError("REST cursor pagination repeated a cursor token")
        seen_cursors.add(token)
        cursor_value = next_cursor
        next_url_override = next_url

    raise RESTPaginationError(
        "REST pagination exhausted pagination.max_pages without an explicit termination signal"
    )


@ConnectorRegistry.register
class RESTConnector(BaseConnector):
    """Fetch data from any REST API endpoint.

    Config keys:
        url:        Target URL (required).
        method:     HTTP method — ``GET`` (default) or ``POST``.
        headers:    Dict of request headers.
        params:     Dict of query-string parameters.
        body:       JSON body for POST requests.
        timeout:    Request timeout in seconds (default 30).
        data_path:  Dot-separated path to the data array in the response
                    (e.g. ``"results.items"``).
        pagination: Optional bounded pagination config. Supported modes:
                    ``page_number`` and ``cursor_path``.
    """

    connector_type: str = "rest_api"

    async def fetch_data(self) -> list[dict[str, Any]]:
        return await fetch_rest_records_async(self.config)

    async def fetch_table(self) -> Any | None:
        records = await self.fetch_data()
        if not records:
            return None
        return records_to_arrow_table(records)

    async def validate_connection(self) -> tuple[bool, str]:
        """Attempt a fetch and report record count or error."""
        try:
            data = await self.fetch_data()
            return True, f"Connected. Retrieved {len(data)} records."
        except Exception as exc:
            return False, f"Connection failed: {exc}"
