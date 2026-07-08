from __future__ import annotations

import importlib
import sys
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Iterator

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
ALGENTA_CORE = ROOT / "packages" / "algenta"


@contextmanager
def _source_module(package_root: Path, package: str, module_name: str) -> Iterator[ModuleType]:
    original_path = list(sys.path)
    removed_modules = {
        name: module
        for name, module in list(sys.modules.items())
        if name == package or name.startswith(f"{package}.")
    }
    for name in removed_modules:
        sys.modules.pop(name, None)
    sys.path.insert(0, str(package_root))
    try:
        yield importlib.import_module(f"{package}.{module_name}")
    finally:
        for name in list(sys.modules):
            if name == package or name.startswith(f"{package}."):
                sys.modules.pop(name, None)
        sys.path[:] = original_path
        sys.modules.update(removed_modules)


def test_python_sdk_source_client_wrapper_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)

    with _source_module(PYTHON_SDK, "decision_engine", "client") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.DecisionEngineClient(api_key="de_live_test")


def test_python_sdk_source_async_client_wrapper_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)

    with _source_module(PYTHON_SDK, "decision_engine", "async_client") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.AsyncDecisionEngineClient(api_key="de_live_test")


def test_python_sdk_source_package_root_sync_exports_fail_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)

    with _source_module(PYTHON_SDK, "decision_engine", "__init__") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.AlgentaClient(api_key="de_live_test")
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.DecisionEngineClient(api_key="de_live_test")


def test_python_sdk_source_package_root_async_exports_fail_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)

    with _source_module(PYTHON_SDK, "decision_engine", "__init__") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.AsyncAlgentaClient(api_key="de_live_test")
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.AsyncDecisionEngineClient(api_key="de_live_test")


def test_algenta_source_runtime_wrapper_api_mode_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)

    with _source_module(ALGENTA_CORE, "algenta", "runtime") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.Runtime(mode="api", api_key="de_live_test")


def test_algenta_source_package_root_runtime_export_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)

    with _source_module(ALGENTA_CORE, "algenta", "__init__") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.Runtime(mode="api", api_key="de_live_test")


def test_algenta_source_package_root_client_export_fails_closed_without_private_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ALGENTA_DEPLOYMENT_MODE", "self_hosted")
    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)

    with _source_module(ALGENTA_CORE, "algenta", "__init__") as module:
        with pytest.raises(ValueError, match="private profiles cannot target Algenta-owned cloud URLs"):
            module.AlgentaClient(api_key="de_live_test")
