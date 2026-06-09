"""Tests for test_algenta_runtime_connectors: misc.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_3967a6fe-cb7-2/tests/test_algenta_runtime_connectors.py during modularization.
"""
from __future__ import annotations

from tests._test_algenta_runtime_connectors_helpers import *  # noqa: F401,F403


def test_runtime_self_hosted_requires_explicit_base_url() -> None:
    with pytest.raises(RuntimeConfigurationError, match="base_url"):
        Runtime(mode="self_hosted", api_key="de_live_test")


def test_runtime_local_connector_management_fails_closed() -> None:
    runtime = Runtime(mode="local")

    with pytest.raises(RuntimeConfigurationError, match="not supported"):
        runtime.list_datasets()


def test_runtime_api_connector_methods_use_typed_outputs(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = Runtime(mode="self_hosted", api_key="de_live_test", base_url="http://localhost:8000")

    class _FakeClient:
        def create_connector(self, **kwargs):
            assert kwargs["name"] == "Warehouse Postgres"
            return _connector_payload()

        def list_connectors(self, *, page: int, limit: int):
            assert page == 1
            assert limit == 200
            return SimpleNamespace(connectors=[_connector_payload()])

        def get_connector(self, connector_id: str):
            assert connector_id == "conn_123"
            return _connector_payload()

        def update_connector(
            self,
            connector_id: str,
            *,
            name: str | None = None,
            description: str | None = None,
            visibility: str | None = None,
            config: dict[str, object] | None = None,
        ):
            assert connector_id == "conn_123"
            assert name is None
            assert description == "analytics warehouse"
            assert visibility == "workspace"
            assert config is None
            return {
                **_connector_payload(),
                "description": description,
                "visibility": visibility,
                "status": "untested",
            }

        def test_connector(self, connector_id: str):
            assert connector_id == "conn_123"
            return {
                "success": True,
                "message": "ok",
                "latency_ms": 12,
                "status": "live",
                "error_type": None,
                "recoverable": None,
            }

        def browse_connector(self, connector_id: str):
            assert connector_id == "conn_123"
            return _browse_payload(connector_id)

        def list_datasets(self, *, page: int, limit: int):
            assert page == 1
            assert limit == 200
            return SimpleNamespace(datasets=[_dataset_payload()])

        def get_dataset(self, dataset_id: str):
            assert dataset_id == "ds_123"
            return {
                "dataset": _dataset_payload(dataset_id),
                "schema": {"fields": ["amount"]},
            }

        def refresh_dataset(self, dataset_id: str):
            assert dataset_id == "ds_123"
            return {
                "status": "ready",
                "dataset_id": dataset_id,
                "source_id": dataset_id,
                "dataset_name": "orders_dataset",
                "schema": {"fields": ["amount"]},
            }

        def delete_connector(self, connector_id: str):
            assert connector_id == "conn_123"
            return None

        def delete_dataset(self, dataset_id: str):
            assert dataset_id == "ds_123"
            return {
                "dataset_id": dataset_id,
                "status": "deleted",
                "connection_deleted": True,
            }

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    connector = runtime.create_connector(
        name="Warehouse Postgres",
        connector={"type": "postgres", "host": "localhost", "database": "analytics"},
    )
    connectors = runtime.list_connectors()
    connector_detail = runtime.get_connector("conn_123")
    updated_connector = runtime.update_connector(
        "conn_123",
        description="analytics warehouse",
        visibility="workspace",
    )
    test_result = runtime.test_connector("conn_123")
    browse = runtime.browse_connector("conn_123")
    datasets = runtime.list_datasets()
    dataset_detail = runtime.get_dataset("ds_123")
    refreshed = runtime.refresh_dataset("ds_123")
    deleted = runtime.delete_dataset("ds_123")
    runtime.delete_connector("conn_123")

    assert isinstance(connector, ConnectorMetadata)
    assert connector.id == "conn_123"
    assert isinstance(connectors[0], ConnectorMetadata)
    assert isinstance(connector_detail, ConnectorMetadata)
    assert isinstance(updated_connector, ConnectorMetadata)
    assert updated_connector.visibility == "workspace"
    assert isinstance(test_result, ConnectorTestOutput)
    assert test_result.success is True
    assert isinstance(browse, ConnectorBrowseOutput)
    assert browse.labels["entity_noun"] == "table"
    assert isinstance(datasets[0], DatasetSummary)
    assert datasets[0].dataset_id == "ds_123"
    assert isinstance(dataset_detail, DatasetDetail)
    assert dataset_detail.dataset.dataset_id == "ds_123"
    assert dataset_detail.schema == {"fields": ["amount"]}
    assert isinstance(refreshed, SourceRegistration)
    assert refreshed.dataset_id == "ds_123"
    assert isinstance(deleted, DatasetDeleteOutput)
    assert deleted.dataset_id == "ds_123"
    assert deleted.connection_deleted is True


def test_runtime_dataset_discovery_filters_and_summary_use_typed_outputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    seen: dict[str, object] = {}

    class _FakeClient:
        def list_datasets(
            self,
            *,
            page: int,
            limit: int,
            search: str,
            status: str,
            source_name: str,
            compact: bool,
        ):
            seen["list"] = {
                "page": page,
                "limit": limit,
                "search": search,
                "status": status,
                "source_name": source_name,
                "compact": compact,
            }
            return SimpleNamespace(
                datasets=[_dataset_payload("ds_otp")],
                count=1,
                total=8,
                matched_total=1,
                page=2,
                limit=limit,
                pages=1,
            )

        def get_dataset_summary(self, dataset_id: str):
            seen["summary"] = dataset_id
            return {
                "dataset_id": dataset_id,
                "name": "OTP Monthly",
                "status": "ready",
                "source_names": ["ops_postgres"],
                "row_count": 2048,
                "column_count": 42,
                "registered_at": None,
                "query_hints": [{"hint": "otp_rate"}],
            }

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    datasets = runtime.list_datasets(
        page=2,
        limit=25,
        search="otp",
        status="ready",
        source_name="ops_postgres",
        compact=True,
    )
    summary = runtime.get_dataset_summary("ds_otp")

    assert seen["list"] == {
        "page": 2,
        "limit": 25,
        "search": "otp",
        "status": "ready",
        "source_name": "ops_postgres",
        "compact": True,
    }
    assert isinstance(datasets, DatasetList)
    assert len(datasets) == 1
    assert datasets.matched_total == 1
    assert datasets.datasets[0].name == "Orders Dataset"
    assert datasets[0].status == "ready"
    assert isinstance(summary, DatasetSelectionSummary)
    assert seen["summary"] == "ds_otp"
    assert summary.column_count == 42
    assert summary.query_hints == [{"hint": "otp_rate"}]


def test_runtime_update_connector_requires_changes() -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")

    with pytest.raises(RuntimeValidationError, match="at least one field"):
        runtime.update_connector("conn_123")


def test_runtime_list_connectors_supports_auto_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = Runtime(mode="self_hosted", api_key="de_live_test", base_url="http://localhost:8000")
    pages_seen: list[tuple[int, int]] = []

    class _FakeClient:
        def list_connectors(self, *, page: int, limit: int):
            pages_seen.append((page, limit))
            if page == 1:
                return SimpleNamespace(
                    connectors=[_connector_payload("conn_1"), _connector_payload("conn_2")],
                    page=1,
                    limit=limit,
                    pages=2,
                )
            return SimpleNamespace(
                connectors=[_connector_payload("conn_3")],
                page=2,
                limit=limit,
                pages=2,
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    connectors = runtime.list_connectors(all_pages=True, limit=2)

    assert [connector.id for connector in connectors] == ["conn_1", "conn_2", "conn_3"]
    assert pages_seen == [(1, 2), (2, 2)]


def test_runtime_iter_datasets_supports_max_items(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    pages_seen: list[tuple[int, int]] = []

    class _FakeClient:
        def list_datasets(self, *, page: int, limit: int):
            pages_seen.append((page, limit))
            if page == 1:
                return SimpleNamespace(
                    datasets=[_dataset_payload("ds_1"), _dataset_payload("ds_2")],
                    count=2,
                    total=3,
                    page=1,
                    limit=limit,
                    pages=2,
                )
            return SimpleNamespace(
                datasets=[_dataset_payload("ds_3")],
                count=1,
                total=3,
                page=2,
                limit=limit,
                pages=2,
            )

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    datasets = list(runtime.iter_datasets(limit=2, max_items=2))

    assert [dataset.dataset_id for dataset in datasets] == ["ds_1", "ds_2"]
    assert pages_seen == [(1, 2)]


def test_runtime_saved_reads_reuse_short_ttl_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    calls = {
        "list_connectors": 0,
        "get_connector": 0,
        "browse_connector": 0,
        "list_datasets": 0,
        "get_dataset": 0,
    }

    class _FakeClient:
        def list_connectors(self, *, page: int, limit: int):
            calls["list_connectors"] += 1
            assert page == 1
            assert limit == 200
            return SimpleNamespace(connectors=[_connector_payload()], page=1, limit=limit, pages=1)

        def get_connector(self, connector_id: str):
            calls["get_connector"] += 1
            assert connector_id == "conn_123"
            return _connector_payload(connector_id)

        def browse_connector(self, connector_id: str):
            calls["browse_connector"] += 1
            assert connector_id == "conn_123"
            return _browse_payload(connector_id)

        def list_datasets(self, *, page: int, limit: int):
            calls["list_datasets"] += 1
            assert page == 1
            assert limit == 200
            return SimpleNamespace(datasets=[_dataset_payload()], page=1, limit=limit, pages=1)

        def get_dataset(self, dataset_id: str):
            calls["get_dataset"] += 1
            assert dataset_id == "ds_123"
            return {"dataset": _dataset_payload(dataset_id), "schema": {"fields": ["amount"]}}

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    runtime.list_connectors()
    runtime.list_connectors()
    runtime.get_connector("conn_123")
    runtime.get_connector("conn_123")
    runtime.browse_connector("conn_123")
    runtime.browse_connector("conn_123")
    runtime.list_datasets()
    runtime.list_datasets()
    runtime.get_dataset("ds_123")
    runtime.get_dataset("ds_123")

    assert calls == {
        "list_connectors": 1,
        "get_connector": 1,
        "browse_connector": 1,
        "list_datasets": 1,
        "get_dataset": 1,
    }


def test_runtime_saved_read_cache_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    calls = 0

    class _FakeClient:
        def get_connector(self, connector_id: str):
            nonlocal calls
            calls += 1
            assert connector_id == "conn_123"
            return _connector_payload(connector_id)

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    runtime.get_connector("conn_123")
    cache_key = runtime._api_cache_key("connectors", "get", "conn_123")
    expires_at, payload = runtime._api_surface_cache[cache_key]
    runtime._api_surface_cache[cache_key] = (0.0, payload)
    runtime.get_connector("conn_123")

    assert expires_at > 0.0
    assert calls == 2


def test_runtime_connector_mutations_invalidate_saved_read_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    calls = {"list": 0, "get": 0, "browse": 0, "update": 0, "test": 0, "delete": 0}

    class _FakeClient:
        def list_connectors(self, *, page: int, limit: int):
            calls["list"] += 1
            return SimpleNamespace(
                connectors=[_connector_payload()], page=page, limit=limit, pages=1
            )

        def get_connector(self, connector_id: str):
            calls["get"] += 1
            return _connector_payload(connector_id)

        def browse_connector(self, connector_id: str):
            calls["browse"] += 1
            return _browse_payload(connector_id)

        def update_connector(self, connector_id: str, **_kwargs):
            calls["update"] += 1
            return _connector_payload(connector_id)

        def test_connector(self, connector_id: str):
            calls["test"] += 1
            return {
                "success": True,
                "message": "ok",
                "latency_ms": 12,
                "status": "live",
                "error_type": None,
                "recoverable": None,
            }

        def delete_connector(self, connector_id: str):
            calls["delete"] += 1
            return None

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    runtime.list_connectors()
    runtime.get_connector("conn_123")
    runtime.browse_connector("conn_123")
    runtime.update_connector("conn_123", description="updated")
    runtime.list_connectors()
    runtime.get_connector("conn_123")
    runtime.browse_connector("conn_123")
    runtime.test_connector("conn_123")
    runtime.get_connector("conn_123")
    runtime.browse_connector("conn_123")
    runtime.delete_connector("conn_123")
    runtime.list_connectors()

    assert calls == {
        "list": 3,
        "get": 3,
        "browse": 3,
        "update": 1,
        "test": 1,
        "delete": 1,
    }


def test_runtime_dataset_mutations_invalidate_saved_read_cache(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")
    calls = {"list": 0, "get": 0, "refresh": 0, "delete": 0}

    class _FakeClient:
        def list_datasets(self, *, page: int, limit: int):
            calls["list"] += 1
            return SimpleNamespace(datasets=[_dataset_payload()], page=page, limit=limit, pages=1)

        def get_dataset(self, dataset_id: str):
            calls["get"] += 1
            return {"dataset": _dataset_payload(dataset_id), "schema": {"fields": ["amount"]}}

        def refresh_dataset(self, dataset_id: str):
            calls["refresh"] += 1
            return {
                "status": "ready",
                "dataset_id": dataset_id,
                "source_id": dataset_id,
                "dataset_name": "orders_dataset",
                "schema": {"fields": ["amount"]},
            }

        def delete_dataset(self, dataset_id: str):
            calls["delete"] += 1
            return {
                "dataset_id": dataset_id,
                "status": "deleted",
                "connection_deleted": True,
            }

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    runtime.list_datasets()
    runtime.get_dataset("ds_123")
    runtime.refresh_dataset("ds_123")
    runtime.list_datasets()
    runtime.get_dataset("ds_123")
    runtime.delete_dataset("ds_123")
    runtime.list_datasets()

    assert calls == {
        "list": 3,
        "get": 2,
        "refresh": 1,
        "delete": 1,
    }


def test_runtime_server_side_inline_preview_rate_limit_maps_to_runtime_validation_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")

    class _PreviewRateLimitedError(Exception):
        status_code = 429
        error_code = "inline_preview_rate_limited"
        response_body = {
            "error": {
                "code": "inline_preview_rate_limited",
                "message": "Inline connector previews are rate limited.",
                "details": {"limit": 20, "window_seconds": 60},
            }
        }

        def __str__(self) -> str:
            return "Inline connector previews are rate limited."

    class _FakeClient:
        def preview_test_connector(
            self, *, connector_type: str, config: dict[str, object] | None = None
        ):
            raise _PreviewRateLimitedError()

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="rate limited") as exc_info:
        runtime.test_connector(connector={"type": "redis", "url": "redis://localhost:6379"})

    assert exc_info.value.code == "inline_preview_rate_limited"
    assert exc_info.value.details == {"limit": 20, "window_seconds": 60}


def test_runtime_direct_preview_browse_maps_connector_test_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = Runtime(mode="api", api_key="de_live_test")

    class _PreviewBrowseFailedError(Exception):
        status_code = 409
        error_code = "connector_test_failed"
        response_body = {
            "error": {
                "code": "connector_test_failed",
                "message": "Connection refused",
                "details": {
                    "status": "error",
                    "error_type": "timeout",
                    "recoverable": True,
                },
            }
        }

        def __str__(self) -> str:
            return "Connection refused"

    class _FakeClient:
        def preview_browse_connector(
            self,
            *,
            connector_type: str,
            config: dict[str, object] | None = None,
        ):
            raise _PreviewBrowseFailedError()

    monkeypatch.setattr(runtime, "_client", lambda: _FakeClient())

    with pytest.raises(RuntimeValidationError, match="Connection refused") as exc_info:
        runtime.browse_connector(connector={"type": "redis", "url": "redis://localhost:6379"})

    assert exc_info.value.code == "connector_test_failed"
    assert exc_info.value.details == {
        "status": "error",
        "error_type": "timeout",
        "recoverable": True,
    }


