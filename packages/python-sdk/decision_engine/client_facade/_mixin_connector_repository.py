"""_ConnectorRepositoryMixin for the DecisionEngineClient class.

Extracted from packages/python-sdk/decision_engine/client_facade.py during modularization.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Any

# Lazy facade-routed wrappers for the @cache surface-module loaders.
# Tests monkey-patch these on the facade module; each call here re-reads
# the attribute from the facade so the patch propagates into mixin bodies.
def _connector_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._connector_surface_module()


def _repository_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._repository_surface_module()


def _query_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._query_surface_module()


def _contract_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._contract_surface_module()


def _simulation_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._simulation_surface_module()


def _source_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._source_surface_module()


def _job_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._job_surface_module()


def _product_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._product_surface_module()


def _deployment_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._deployment_surface_module()


def _account_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._account_surface_module()


def _control_plane_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._control_plane_surface_module()


def _llm_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._llm_surface_module()


def _agent_run_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._agent_run_surface_module()


def _decision_plan_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._decision_plan_surface_module()


def _decision_memory_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._decision_memory_surface_module()


def _trigger_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._trigger_surface_module()


def _capability_plane_surface_module():
    from decision_engine import client_facade as _facade
    return _facade._capability_plane_surface_module()



class _ConnectorRepositoryMixin:
    def create_connector(
        self,
        *,
        name: str,
        connector_type: str,
        config: dict[str, Any] | None = None,
        description: str | None = None,
        visibility: str | None = None,
    ) -> ConnectorInfo:
        return _connector_surface_module().create_connector(
            self,
            name=name,
            connector_type=connector_type,
            config=config,
            description=description,
            visibility=visibility,
        )

    def list_connectors(
        self,
        *,
        page: int = 1,
        limit: int = 200,
    ) -> ConnectorListResult:
        return _connector_surface_module().list_connectors(self, page=page, limit=limit)

    def get_connector(self, connector_id: str) -> ConnectorInfo:
        return _connector_surface_module().get_connector(self, connector_id)

    def update_connector(
        self,
        connector_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        visibility: str | None = None,
        config: dict[str, Any] | None = None,
    ) -> ConnectorInfo:
        return _connector_surface_module().update_connector(
            self,
            connector_id,
            name=name,
            description=description,
            visibility=visibility,
            config=config,
        )

    def iter_connectors(
        self,
        *,
        page: int = 1,
        limit: int = 200,
        max_items: int | None = None,
    ):
        yield from _connector_surface_module().iter_connectors(
            self,
            page=page,
            limit=limit,
            max_items=max_items,
        )

    def test_connector(self, connector_id: str) -> ConnectorTestInfo:
        return _connector_surface_module().test_connector(self, connector_id)

    def preview_test_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any] | None = None,
    ) -> ConnectorTestInfo:
        return _connector_surface_module().preview_test_connector(
            self,
            connector_type=connector_type,
            config=config,
        )

    def browse_connector(self, connector_id: str) -> ConnectorBrowseResult:
        return _connector_surface_module().browse_connector(self, connector_id)

    def preview_browse_connector(
        self,
        *,
        connector_type: str,
        config: dict[str, Any] | None = None,
    ) -> ConnectorBrowseResult:
        return _connector_surface_module().preview_browse_connector(
            self,
            connector_type=connector_type,
            config=config,
        )

    def delete_connector(self, connector_id: str) -> None:
        _connector_surface_module().delete_connector(self, connector_id)

    def create_repository_snapshot(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositorySnapshotResult:
        return _repository_surface_module().create_repository_snapshot(self, repository_id, request)

    def get_repository_intelligence_capabilities(
        self,
    ) -> "RepositoryIntelligenceCapabilitiesResult":
        return _repository_surface_module().get_repository_intelligence_capabilities(self)

    def get_repository_snapshot(
        self,
        repository_id: str,
        snapshot_id: str,
    ) -> RepositorySnapshotResult:
        return _repository_surface_module().get_repository_snapshot(
            self,
            repository_id,
            snapshot_id,
        )

    def triage_repository(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositoryTriageResult:
        return _repository_surface_module().triage_repository(self, repository_id, request)

    def create_repository_decision_plan(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositoryDecisionPlanRevisionResult:
        return _repository_surface_module().create_repository_decision_plan(
            self,
            repository_id,
            request,
        )

    def query_repository_graph(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositoryGraphQueryResult:
        return _repository_surface_module().query_repository_graph(self, repository_id, request)

    def simulate_repository(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> DecisionEnvelope:
        return _repository_surface_module().simulate_repository(self, repository_id, request)

    def apply_repository(
        self,
        repository_id: str,
        request: dict[str, Any],
    ) -> RepositoryApplyResult:
        return _repository_surface_module().apply_repository(self, repository_id, request)

    def connect_data(
        self,
        request: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> DatasetConnectResult:
        return _connector_surface_module().connect_data(self, request, **kwargs)

    def list_datasets(
        self,
        *,
        page: int = 1,
        limit: int = 200,
        search: str | None = None,
        status: str | None = None,
        source_name: str | None = None,
        compact: bool = False,
    ) -> DatasetListResult:
        return _connector_surface_module().list_datasets(
            self,
            page=page,
            limit=limit,
            search=search,
            status=status,
            source_name=source_name,
            compact=compact,
        )

    def iter_datasets(
        self,
        *,
        page: int = 1,
        limit: int = 200,
        max_items: int | None = None,
        search: str | None = None,
        status: str | None = None,
        source_name: str | None = None,
        compact: bool = False,
    ):
        yield from _connector_surface_module().iter_datasets(
            self,
            page=page,
            limit=limit,
            max_items=max_items,
            search=search,
            status=status,
            source_name=source_name,
            compact=compact,
        )

    def get_dataset(self, dataset_id: str) -> DatasetDetailResult:
        return _connector_surface_module().get_dataset(self, dataset_id)

    def get_dataset_summary(self, dataset_id: str) -> DatasetSummaryResult:
        return _connector_surface_module().get_dataset_summary(self, dataset_id)

    def refresh_dataset(self, dataset_id: str) -> DatasetConnectResult:
        return _connector_surface_module().refresh_dataset(self, dataset_id)

    def delete_dataset(self, dataset_id: str) -> DatasetDeleteResult:
        return _connector_surface_module().delete_dataset(self, dataset_id)

