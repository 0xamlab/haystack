# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any

from .request_common import _strip_none


def build_create_connector_payload(
    *,
    name: str,
    connector_type: str,
    config: dict[str, Any] | None = None,
    description: str | None = None,
    visibility: str | None = None,
) -> dict[str, Any]:
    return _strip_none(
        {
            "name": name,
            "connector_type": connector_type,
            "config": config,
            "description": description,
            "visibility": visibility,
        }
    )


def build_update_connector_payload(
    *,
    name: str | None = None,
    description: str | None = None,
    visibility: str | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _strip_none(
        {
            "name": name,
            "description": description,
            "visibility": visibility,
            "config": config,
        }
    )


def build_preview_connector_payload(
    *,
    connector_type: str,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return _strip_none({"connector_type": connector_type, "config": config})


def build_connect_data_payload(
    request: dict[str, Any] | None,
    kwargs: dict[str, Any],
) -> dict[str, Any]:
    payload = _strip_none(dict(request or {}))
    payload.update(_strip_none(kwargs))
    return payload


def build_dataset_list_params(
    *,
    page: int,
    limit: int,
    search: str | None = None,
    status: str | None = None,
    source_name: str | None = None,
    compact: bool | None = None,
) -> dict[str, Any]:
    params = {
        "page": page,
        "limit": limit,
        "search": search,
        "status": status,
        "source_name": source_name,
    }
    if compact:
        params["compact"] = "1"
    return _strip_none(params)


def normalize_paginated_items_payload(
    data: Any,
    *,
    items_key: str,
    context: str,
    requested_page: int | None,
    count_key: str | None = None,
) -> dict[str, Any]:
    if isinstance(data, list):
        if requested_page not in (None, 1):
            raise ValueError(
                f"{context} returned a raw list for page={requested_page}; "
                "paginated responses are required beyond the first page."
            )
        effective_limit = max(len(data), 1)
        payload: dict[str, Any] = {
            items_key: data,
            "total": len(data),
            "page": 1,
            "limit": effective_limit,
            "pages": 1,
        }
        if count_key is not None:
            payload[count_key] = len(data)
        return payload
    if isinstance(data, dict):
        items = data.get(items_key)
        if not isinstance(items, list):
            raise ValueError(f"{context} must be a JSON object with a list '{items_key}' field.")
        return data
    raise ValueError(f"{context} must be a JSON array or paginated object.")


def iter_page_items[PageT, ItemT](
    *,
    page: int,
    limit: int,
    max_items: int | None,
    fetch_page: Callable[[int, int], PageT],
    items_attr: str,
) -> Iterator[ItemT]:
    emitted = 0
    current_page = page
    while True:
        result = fetch_page(current_page, limit)
        items = tuple(getattr(result, items_attr))
        for item in items:
            yield item
            emitted += 1
            if max_items is not None and emitted >= max_items:
                return
        if current_page >= result.pages or not items:
            return
        current_page += 1


async def iter_page_items_async[PageT, ItemT](
    *,
    page: int,
    limit: int,
    max_items: int | None,
    fetch_page: Callable[[int, int], Awaitable[PageT]],
    items_attr: str,
) -> AsyncIterator[ItemT]:
    emitted = 0
    current_page = page
    while True:
        result = await fetch_page(current_page, limit)
        items = tuple(getattr(result, items_attr))
        for item in items:
            yield item
            emitted += 1
            if max_items is not None and emitted >= max_items:
                return
        if current_page >= result.pages or not items:
            return
        current_page += 1
