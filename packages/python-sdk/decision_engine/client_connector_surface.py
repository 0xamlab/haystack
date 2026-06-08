from __future__ import annotations

from typing import Any

from .connector_surface_common import (
    build_connect_data_payload,
    build_create_connector_payload,
    build_dataset_list_params,
    build_preview_connector_payload,
    build_update_connector_payload,
    iter_page_items,
    normalize_paginated_items_payload,
)
from .model_loader import validate_model as _validate_model


def create_connector(
    client: Any,
    *,
    name: str,
    connector_type: str,
    config: dict[str, Any] | None = None,
    description: str | None = None,
    visibility: str | None = None,
):
    data = client._request(
        "POST",
        "/v1/connectors",
        json=build_create_connector_payload(
            name=name,
            connector_type=connector_type,
            config=config,
            description=description,
            visibility=visibility,
        ),
    )
    return _validate_model("ConnectorInfo", data)


def list_connectors(
    client: Any,
    *,
    page: int = 1,
    limit: int = 200,
):
    data = client._request(
        "GET",
        "/v1/connectors",
        params={"page": page, "limit": limit},
    )
    return _validate_model(
        "ConnectorListResult",
        normalize_paginated_items_payload(
            data,
            items_key="connectors",
            context="Connector list response",
            requested_page=page,
        ),
    )


def get_connector(client: Any, connector_id: str):
    data = client._request("GET", f"/v1/connectors/{connector_id}")
    return _validate_model("ConnectorInfo", data)


def update_connector(
    client: Any,
    connector_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    visibility: str | None = None,
    config: dict[str, Any] | None = None,
):
    data = client._request(
        "PATCH",
        f"/v1/connectors/{connector_id}",
        json=build_update_connector_payload(
            name=name,
            description=description,
            visibility=visibility,
            config=config,
        ),
    )
    return _validate_model("ConnectorInfo", data)


def iter_connectors(
    client: Any,
    *,
    page: int = 1,
    limit: int = 200,
    max_items: int | None = None,
):
    yield from iter_page_items(
        page=page,
        limit=limit,
        max_items=max_items,
        fetch_page=lambda current_page, current_limit: list_connectors(
            client,
            page=current_page,
            limit=current_limit,
        ),
        items_attr="connectors",
    )


def test_connector(client: Any, connector_id: str):
    data = client._request("POST", f"/v1/connectors/{connector_id}/test")
    return _validate_model("ConnectorTestInfo", data)


def preview_test_connector(
    client: Any,
    *,
    connector_type: str,
    config: dict[str, Any] | None = None,
):
    data = client._request(
        "POST",
        "/v1/connectors/test",
        json=build_preview_connector_payload(
            connector_type=connector_type,
            config=config,
        ),
    )
    return _validate_model("ConnectorTestInfo", data)


def browse_connector(client: Any, connector_id: str):
    data = client._request("GET", f"/v1/connectors/{connector_id}/browse")
    return _validate_model("ConnectorBrowseResult", data)


def preview_browse_connector(
    client: Any,
    *,
    connector_type: str,
    config: dict[str, Any] | None = None,
):
    data = client._request(
        "POST",
        "/v1/connectors/browse",
        json=build_preview_connector_payload(
            connector_type=connector_type,
            config=config,
        ),
    )
    return _validate_model("ConnectorBrowseResult", data)


def delete_connector(client: Any, connector_id: str) -> None:
    client._request("DELETE", f"/v1/connectors/{connector_id}")


def connect_data(
    client: Any,
    request: dict[str, Any] | None = None,
    **kwargs: Any,
):
    payload = build_connect_data_payload(request, kwargs)
    data = client._request("POST", "/v1/data/connect", json=payload)
    return _validate_model("DatasetConnectResult", data)


def list_datasets(
    client: Any,
    *,
    page: int = 1,
    limit: int = 200,
    search: str | None = None,
    status: str | None = None,
    source_name: str | None = None,
    compact: bool = False,
):
    data = client._request(
        "GET",
        "/v1/data",
        params=build_dataset_list_params(
            page=page,
            limit=limit,
            search=search,
            status=status,
            source_name=source_name,
            compact=compact,
        ),
    )
    return _validate_model(
        "DatasetListResult",
        normalize_paginated_items_payload(
            data,
            items_key="datasets",
            count_key="count",
            context="Dataset list response",
            requested_page=page,
        ),
    )


def iter_datasets(
    client: Any,
    *,
    page: int = 1,
    limit: int = 200,
    max_items: int | None = None,
    search: str | None = None,
    status: str | None = None,
    source_name: str | None = None,
    compact: bool = False,
):
    yield from iter_page_items(
        page=page,
        limit=limit,
        max_items=max_items,
        fetch_page=lambda current_page, current_limit: list_datasets(
            client,
            page=current_page,
            limit=current_limit,
            search=search,
            status=status,
            source_name=source_name,
            compact=compact,
        ),
        items_attr="datasets",
    )


def get_dataset(client: Any, dataset_id: str):
    data = client._request("GET", f"/v1/data/{dataset_id}")
    return _validate_model("DatasetDetailResult", data)


def get_dataset_summary(client: Any, dataset_id: str):
    data = client._request("GET", f"/v1/data/{dataset_id}/summary")
    return _validate_model("DatasetSummaryResult", data)


def refresh_dataset(client: Any, dataset_id: str):
    data = client._request("POST", f"/v1/data/{dataset_id}/refresh")
    return _validate_model("DatasetConnectResult", data)


def delete_dataset(client: Any, dataset_id: str):
    data = client._request("DELETE", f"/v1/data/{dataset_id}")
    return _validate_model("DatasetDeleteResult", data)
