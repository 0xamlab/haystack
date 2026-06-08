from __future__ import annotations

import importlib
import sys
from types import ModuleType

import pytest


def test_dataset_service_import_is_lazy_for_schema_registry() -> None:
    service_name = "apps.api_server.services.dataset_service"
    registry_name = "training.semantic.schema_registry"
    services_package = importlib.import_module("apps.api_server.services")
    missing = object()

    original_service = sys.modules.pop(service_name, None)
    original_registry = sys.modules.pop(registry_name, None)
    original_package_service = getattr(services_package, "dataset_service", missing)

    try:
        importlib.import_module(service_name)
        assert registry_name not in sys.modules
    finally:
        sys.modules.pop(service_name, None)
        if original_service is not None:
            sys.modules[service_name] = original_service
        if original_package_service is missing:
            if hasattr(services_package, "dataset_service"):
                delattr(services_package, "dataset_service")
        else:
            services_package.dataset_service = original_package_service
        if original_registry is not None:
            sys.modules[registry_name] = original_registry


def test_schema_registry_import_does_not_eager_load_training_runtime() -> None:
    registry_name = "training.semantic.schema_registry"
    pipeline_name = "training.semantic.pipeline"
    train_name = "training.semantic.train_thin_semantic"

    original_registry = sys.modules.pop(registry_name, None)
    original_pipeline = sys.modules.pop(pipeline_name, None)
    original_train = sys.modules.pop(train_name, None)

    try:
        importlib.import_module(registry_name)
        assert pipeline_name in sys.modules
        assert train_name not in sys.modules
    finally:
        sys.modules.pop(registry_name, None)
        sys.modules.pop(pipeline_name, None)
        sys.modules.pop(train_name, None)
        if original_registry is not None:
            sys.modules[registry_name] = original_registry
        if original_pipeline is not None:
            sys.modules[pipeline_name] = original_pipeline
        if original_train is not None:
            sys.modules[train_name] = original_train


@pytest.mark.anyio
async def test_dataset_router_run_onboard_uses_live_dataset_service_loader(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apps.api_server.routers import datasets as router

    calls: list[str] = []
    fake_service = ModuleType("fake_dataset_service")

    def _onboard(**kwargs):  # type: ignore[no-untyped-def]
        calls.append("onboard")
        assert kwargs["org_id"] == "org_test"
        return {
            "dataset_id": "ds_test",
            "name": "Orders",
            "schema_hash": "schema_123",
            "status": "untrained",
            "model_tier": "none",
            "schema": {"Orders": [["amount", "derived_measure"]]},
            "domain_aliases": None,
            "source_names": ["Orders"],
            "column_count": 1,
            "registered_at": "2026-05-18T00:00:00+00:00",
            "updated_at": "2026-05-18T00:00:00+00:00",
        }

    def _suggest_aliases(schema):  # type: ignore[no-untyped-def]
        calls.append("suggest_aliases")
        assert schema == {"Orders": [["amount", "derived_measure"]]}
        return {"amt": ["amount"]}

    def _decision_mode_for_tier(tier: str) -> str:
        calls.append("decision_mode_for_tier")
        assert tier == "none"
        return "deterministic_only"

    fake_service.onboard = _onboard  # type: ignore[attr-defined]
    fake_service.suggest_aliases = _suggest_aliases  # type: ignore[attr-defined]
    fake_service.decision_mode_for_tier = _decision_mode_for_tier  # type: ignore[attr-defined]

    monkeypatch.setattr(router, "_dataset_service", lambda: fake_service)

    response = await router._run_onboard(
        org_id="org_test",
        source=[{"amount": 10.0}],
        name="Orders",
        source_name="Orders",
        domain_aliases=None,
        async_train=True,
        epochs=80,
        batch_size=32,
        t0=0.0,
        log_extra={},
    )

    assert response.dataset_id == "ds_test"
    assert response.suggested_aliases == {"amt": ["amount"]}
    assert response.decision_mode == "deterministic_only"
    assert calls == ["onboard", "suggest_aliases", "decision_mode_for_tier"]
