from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from algenta.runtime_connector_model_metadata import ConnectorMetadata
from algenta.runtime_connector_model_preview import (
    ConnectorBrowseOutput,
    ConnectorTestOutput,
)
from algenta.runtime_errors import RuntimeValidationError


class RuntimeSavedConnectorMixin:
    def _connector_page(
        self,
        *,
        page: int,
        limit: int,
    ) -> tuple[list[ConnectorMetadata], int]:
        cache_key = self._api_cache_key("connectors", "list", page, limit)
        cached = self._get_api_surface_cache(cache_key)
        if cached is not None:
            connectors, pages = cached
            return connectors, int(pages)
        result = self._client().list_connectors(page=page, limit=limit)
        payload = (
            [ConnectorMetadata.from_api(connector) for connector in result.connectors],
            int(getattr(result, "pages", page)),
        )
        cached_payload = self._put_api_surface_cache(cache_key, payload)
        connectors, pages = cached_payload
        return connectors, int(pages)

    def create_connector(
        self,
        *,
        name: str,
        connector: Mapping[str, Any] | None = None,
        connector_type: str | None = None,
        config: Mapping[str, Any] | None = None,
        description: str | None = None,
        visibility: str | None = "private",
    ) -> ConnectorMetadata:
        self._require_api_transport("create_connector")
        if not name.strip():
            raise RuntimeValidationError(
                "invalid_connector",
                "create_connector() requires a non-empty name.",
            )
        normalized_type, normalized_config = self._normalize_connector_definition(
            connector=connector,
            connector_type=connector_type,
            config=config,
        )
        created = ConnectorMetadata.from_api(
            self._client().create_connector(
                name=name.strip(),
                connector_type=normalized_type,
                config=normalized_config,
                description=description,
                visibility=visibility,
            )
        )
        self._invalidate_api_surface_cache("connectors:list:")
        return created

    def list_connectors(
        self,
        *,
        page: int = 1,
        limit: int = 200,
        all_pages: bool = False,
        max_items: int | None = None,
    ) -> list[ConnectorMetadata]:
        self._require_api_transport("list_connectors")
        if not all_pages:
            connectors, _pages = self._connector_page(page=page, limit=limit)
            if max_items is not None:
                return connectors[:max_items]
            return connectors
        return list(self.iter_connectors(page=page, limit=limit, max_items=max_items))

    def get_connector(self, connector_id: str) -> ConnectorMetadata:
        self._require_api_transport("get_connector")
        cache_key = self._api_cache_key("connectors", "get", connector_id)
        cached = self._get_api_surface_cache(cache_key)
        if isinstance(cached, ConnectorMetadata):
            return cached
        result = ConnectorMetadata.from_api(self._client().get_connector(connector_id))
        return self._put_api_surface_cache(cache_key, result)

    def update_connector(
        self,
        connector_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        visibility: str | None = None,
        config: Mapping[str, Any] | None = None,
    ) -> ConnectorMetadata:
        self._require_api_transport("update_connector")
        if name is None and description is None and visibility is None and config is None:
            raise RuntimeValidationError(
                "invalid_connector",
                "update_connector() requires at least one field to update.",
            )
        if name is not None and not name.strip():
            raise RuntimeValidationError(
                "invalid_connector",
                "update_connector() requires a non-empty name when name is provided.",
            )
        updated = ConnectorMetadata.from_api(
            self._client().update_connector(
                connector_id,
                name=name.strip() if name is not None else None,
                description=description,
                visibility=visibility,
                config=dict(config) if config is not None else None,
            )
        )
        self._invalidate_api_surface_cache(
            "connectors:list:",
            self._api_cache_key("connectors", "get", connector_id),
            self._api_cache_key("connectors", "browse", connector_id),
        )
        return updated

    def iter_connectors(
        self,
        *,
        page: int = 1,
        limit: int = 200,
        max_items: int | None = None,
    ):
        self._require_api_transport("iter_connectors")
        yield from self._iter_api_page_items(
            start_page=page,
            limit=limit,
            max_items=max_items,
            fetch_page=self._connector_page,
        )

    def test_connector(
        self,
        connector_id: str | None = None,
        *,
        connector: Mapping[str, Any] | None = None,
        connector_type: str | None = None,
        config: Mapping[str, Any] | None = None,
    ) -> ConnectorTestOutput:
        self._require_api_transport("test_connector")
        has_inline_descriptor = (
            connector is not None or connector_type is not None or config is not None
        )
        if connector_id and has_inline_descriptor:
            raise RuntimeValidationError(
                "invalid_connector",
                "Provide either connector_id=... or an inline connector descriptor, not both.",
            )
        if connector_id is not None:
            result = ConnectorTestOutput.from_api(self._client().test_connector(connector_id))
            self._invalidate_api_surface_cache(
                self._api_cache_key("connectors", "get", connector_id),
                self._api_cache_key("connectors", "browse", connector_id),
                "connectors:list:",
            )
            return result

        normalized_type, normalized_config = self._normalize_connector_definition(
            connector=connector,
            connector_type=connector_type,
            config=config,
        )
        return self._test_inline_preview(
            connector_type=normalized_type,
            config=normalized_config,
        )

    def browse_connector(
        self,
        connector_id: str | None = None,
        *,
        connector: Mapping[str, Any] | None = None,
        connector_type: str | None = None,
        config: Mapping[str, Any] | None = None,
    ) -> ConnectorBrowseOutput:
        self._require_api_transport("browse_connector")
        has_inline_descriptor = (
            connector is not None or connector_type is not None or config is not None
        )
        if connector_id and has_inline_descriptor:
            raise RuntimeValidationError(
                "invalid_connector",
                "Provide either connector_id=... or an inline connector descriptor, not both.",
            )
        if connector_id is not None:
            cache_key = self._api_cache_key("connectors", "browse", connector_id)
            cached = self._get_api_surface_cache(cache_key)
            if isinstance(cached, ConnectorBrowseOutput):
                return cached
            result = ConnectorBrowseOutput.from_api(self._client().browse_connector(connector_id))
            return self._put_api_surface_cache(cache_key, result)

        normalized_type, normalized_config = self._normalize_connector_definition(
            connector=connector,
            connector_type=connector_type,
            config=config,
        )
        return self._browse_inline_preview(
            connector_type=normalized_type,
            config=normalized_config,
        )

    def delete_connector(self, connector_id: str) -> None:
        self._require_api_transport("delete_connector")
        self._client().delete_connector(connector_id)
        self._invalidate_api_surface_cache(
            "connectors:list:",
            self._api_cache_key("connectors", "get", connector_id),
            self._api_cache_key("connectors", "browse", connector_id),
        )
