from __future__ import annotations

import importlib
import sys


def test_dataset_service_import_is_lazy_for_schema_registry() -> None:
    service_name = "apps.api_server.services.dataset_service"
    registry_name = "training.semantic.schema_registry"

    original_service = sys.modules.pop(service_name, None)
    original_registry = sys.modules.pop(registry_name, None)

    try:
        importlib.import_module(service_name)
        assert registry_name not in sys.modules
    finally:
        sys.modules.pop(service_name, None)
        if original_service is not None:
            sys.modules[service_name] = original_service
        if original_registry is not None:
            sys.modules[registry_name] = original_registry
