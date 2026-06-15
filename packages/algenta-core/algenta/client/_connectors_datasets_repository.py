"""_ConnectorsDatasetsRepositoryMixin for the CodnaClient class.

Extracted from packages/algenta-core/algenta/client.py during modularization.
"""
from __future__ import annotations

from typing import Any

from algenta.client._helpers import _sdk_payload_to_plain_data, _cloud_get  # noqa: F401


class _ConnectorsDatasetsRepositoryMixin:
    def list_connectors(
        self,
        *,
        page: int = 1,
        limit: int = 200,
    ) -> Any:
        return self._sdk_client().list_connectors(page=page, limit=limit)

    def create_connector(
        self,
        *,
        name: str,
        connector_type: str,
        config: dict[str, Any] | None = None,
        description: str | None = None,
        visibility: str | None = None,
    ) -> Any:
        return self._sdk_client().create_connector(
            name=name,
            connector_type=connector_type,
            config=config,
            description=description,
            visibility=visibility,
        )

    def get_connector(self, connector_id: str) -> Any:
        return self._sdk_client().get_connector(connector_id)

    def update_connector(
        self,
        connector_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        visibility: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> Any:
        return self._sdk_client().update_connector(
            connector_id,
            name=name,
            description=description,
            visibility=visibility,
            config=config,
        )

    def test_connector(self, connector_id: str) -> Any:
        return self._sdk_client().test_connector(connector_id)

    def preview_test_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any] | None = None,
    ) -> Any:
        return self._sdk_client().preview_test_connector(
            connector_type=connector_type,
            config=config,
        )

    def browse_connector(self, connector_id: str) -> Any:
        return self._sdk_client().browse_connector(connector_id)

    def preview_browse_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any] | None = None,
    ) -> Any:
        return self._sdk_client().preview_browse_connector(
            connector_type=connector_type,
            config=config,
        )

    def delete_connector(self, connector_id: str) -> Any:
        return self._sdk_client().delete_connector(connector_id)

    def create_repository_snapshot(self, repository_id: str, request: dict[str, Any]) -> Any:
        return self._sdk_client().create_repository_snapshot(repository_id, request)

    def get_repository_intelligence_capabilities(self) -> Any:
        return self._sdk_client().get_repository_intelligence_capabilities()

    def get_repository_snapshot(self, repository_id: str, snapshot_id: str) -> Any:
        return self._sdk_client().get_repository_snapshot(repository_id, snapshot_id)

    def triage_repository(self, repository_id: str, request: dict[str, Any]) -> Any:
        return self._sdk_client().triage_repository(repository_id, request)

    def create_repository_decision_plan(self, repository_id: str, request: dict[str, Any]) -> Any:
        return self._sdk_client().create_repository_decision_plan(repository_id, request)

    def query_repository_graph(self, repository_id: str, request: dict[str, Any]) -> Any:
        return self._sdk_client().query_repository_graph(repository_id, request)

    def simulate_repository(self, repository_id: str, request: dict[str, Any]) -> Any:
        return self._sdk_client().simulate_repository(repository_id, request)

    def apply_repository(self, repository_id: str, request: dict[str, Any]) -> Any:
        return self._sdk_client().apply_repository(repository_id, request)

    def connect_data(
        self,
        request: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        return self._sdk_client().connect_data(request, **kwargs)

    def list_datasets(
        self,
        *,
        page: int = 1,
        limit: int = 200,
        search: str | None = None,
        status: str | None = None,
        source_name: str | None = None,
        compact: bool = False,
    ) -> Any:
        return self._sdk_client().list_datasets(
            page=page,
            limit=limit,
            search=search,
            status=status,
            source_name=source_name,
            compact=compact,
        )

    def get_dataset(self, dataset_id: str) -> Any:
        return self._sdk_client().get_dataset(dataset_id)

    def get_dataset_summary(self, dataset_id: str) -> Any:
        return self._sdk_client().get_dataset_summary(dataset_id)

    def refresh_dataset(self, dataset_id: str) -> Any:
        return self._sdk_client().refresh_dataset(dataset_id)

    def delete_dataset(self, dataset_id: str) -> Any:
        return self._sdk_client().delete_dataset(dataset_id)

