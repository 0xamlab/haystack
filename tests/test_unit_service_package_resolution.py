from __future__ import annotations

import importlib
from pathlib import Path


def test_unit_service_import_resolves_to_package_init() -> None:
    module = importlib.import_module("apps.api_server.services.unit_service")
    module_path = Path(module.__file__).resolve()

    assert module_path.name == "__init__.py"
    assert module_path.parent.name == "unit_service"


def test_unit_service_package_exports_core_api() -> None:
    from apps.api_server.services import unit_service

    assert callable(unit_service.unit_convert)
    assert callable(unit_service.preprocess_payload)
    assert callable(unit_service.postprocess_results)
    assert unit_service.UnitSpec.__name__ == "UnitSpec"
