from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from algenta import runtime_connector_definitions as _connector_definitions
from algenta.runtime_connector_preview import RuntimeInlinePreviewMixin
from algenta.runtime_connector_saved import RuntimeSavedConnectorMixin
from algenta.runtime_dataset_surface import RuntimeDatasetSurfaceMixin
from algenta.runtime_errors import RuntimeConfigurationError, RuntimeValidationError
from algenta.runtime_surface_cache import RuntimeApiSurfaceCacheMixin

_CANONICAL_FILE_TYPES = _connector_definitions._CANONICAL_FILE_TYPES
_LOCAL_RUNTIME_CONNECTOR_TYPES = _connector_definitions._LOCAL_RUNTIME_CONNECTOR_TYPES
_flatten_connector_envelope = _connector_definitions._flatten_connector_envelope
_is_canonical_connector_envelope = _connector_definitions._is_canonical_connector_envelope
_strip_none_dict = _connector_definitions._strip_none_dict
_normalize_connector_definition = _connector_definitions._normalize_connector_definition

_SHARED_RUNTIME_CONNECTOR_STATE = frozenset(
    {
        "_api_surface_cache",
        "_inline_preview_events",
        "_inline_preview_pending_cleanup",
        "_inline_preview_cache",
        "_inline_preview_capabilities",
    }
)


class RuntimeConnectorSurfaceBaseMixin(RuntimeInlinePreviewMixin, RuntimeApiSurfaceCacheMixin):
    def _iter_api_page_items(
        self,
        *,
        start_page: int,
        limit: int,
        max_items: int | None,
        fetch_page,
    ):
        page = start_page
        emitted = 0

        while True:
            items, pages = fetch_page(page=page, limit=limit)
            for item in items:
                yield item
                emitted += 1
                if max_items is not None and emitted >= max_items:
                    return

            if page >= int(pages) or not items:
                return
            page += 1

    def _uses_api_transport(self) -> bool:
        return self._mode in {"api", "self_hosted"}

    def _require_api_transport(self, method_name: str) -> None:
        if self._uses_api_transport():
            return
        raise RuntimeConfigurationError(
            "local_mode_not_supported",
            (
                f"{method_name}() is not supported for Runtime(mode='local'). "
                "Use Runtime(mode='api', ...) or Runtime(mode='self_hosted', base_url='...')."
            ),
        )

    def _normalize_connector_definition(
        self,
        *,
        connector: Mapping[str, Any] | None,
        connector_type: str | None,
        config: Mapping[str, Any] | None,
    ) -> tuple[str, dict[str, Any]]:
        return _normalize_connector_definition(
            connector=connector,
            connector_type=connector_type,
            config=config,
        )

    def _connect_saved_or_inline_connector_dataset(
        self,
        *,
        connector_id: str | None,
        connector: Mapping[str, Any] | None,
        selection: Mapping[str, Any] | None,
        dataset_name: str | None,
        description: str | None,
        persist: bool,
        visibility: str | None,
        connection_name: str | None,
    ):
        if connector is not None and not persist:
            raise RuntimeValidationError(
                "connector_persistence_required",
                (
                    "connect(connector=...) requires persist=True. Use test_connector() "
                    "or browse_connector() for inline preview flows."
                ),
            )

        payload: dict[str, Any] = {
            "dataset_name": dataset_name,
            "description": description,
            "selection": dict(selection or {}),
            "visibility": visibility,
        }
        if connection_name is not None:
            payload["connection_name"] = connection_name
        if connector_id is not None:
            payload["connection_id"] = connector_id
        elif connector is not None:
            payload["connector"] = dict(connector)

        dataset_name_value = payload.get("dataset_name")
        if not isinstance(dataset_name_value, str) or not dataset_name_value.strip():
            raise RuntimeValidationError(
                "missing_dataset_name",
                (
                    "connect() requires dataset_name= or name= when onboarding "
                    "a connector-backed dataset."
                ),
            )

        result = self._client().connect_data(payload)
        status = result.status
        if status != "ready":
            error_code = (
                "selection_required" if status == "needs_selection" else f"connect_{status}"
            )
            raise RuntimeValidationError(
                error_code,
                result.message or "Connector-backed dataset connection did not complete.",
                {
                    "status": result.status,
                    "choices": result.choices,
                    "labels": result.labels,
                    "discovery": result.discovery,
                    "connection_id": result.connection_id,
                },
            )

        registration = self._source_registration_from_api(result)
        self._remember_api_registration(registration)
        self._invalidate_api_surface_cache("datasets:list:", "datasets:get:")
        return registration


class RuntimeConnectorSurfaceMixin(
    RuntimeConnectorSurfaceBaseMixin,
    RuntimeSavedConnectorMixin,
    RuntimeDatasetSurfaceMixin,
):
    pass


class RuntimeConnectorSurface(RuntimeConnectorSurfaceMixin):
    """Lazy connector surface wrapper bound to a Runtime instance."""

    def __init__(self, runtime: Any) -> None:
        object.__setattr__(self, "_runtime", runtime)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._runtime, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name == "_runtime":
            object.__setattr__(self, name, value)
            return
        if name in _SHARED_RUNTIME_CONNECTOR_STATE:
            setattr(self._runtime, name, value)
            return
        object.__setattr__(self, name, value)
