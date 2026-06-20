from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

from tests._manifest_backed_integrations import (
    MANIFEST_BACKED_INTEGRATIONS,
    assert_manifest_backed_integrations,
)

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
if str(PYTHON_SDK) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK))


def test_decision_engine_client_wrapper_loads_facade_once_on_class_access(
    monkeypatch,
) -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "decision_engine.client"
        or module_name == "decision_engine.client_facade"
        or module_name == "decision_engine.client_connector_surface"
        or module_name == "decision_engine.client_service_surface"
        or module_name == "decision_engine.request_helpers"
    }
    for module_name in list(sys.modules):
        if module_name == "decision_engine.client":
            sys.modules.pop(module_name, None)
        elif module_name == "decision_engine.client_facade":
            sys.modules.pop(module_name, None)
        elif module_name == "decision_engine.client_connector_surface":
            sys.modules.pop(module_name, None)
        elif module_name == "decision_engine.client_service_surface":
            sys.modules.pop(module_name, None)
        elif module_name == "decision_engine.request_helpers":
            sys.modules.pop(module_name, None)

    try:
        module = importlib.import_module("decision_engine.client")

        assert "decision_engine.client_facade" not in sys.modules
        assert "decision_engine.client_connector_surface" not in sys.modules
        assert "decision_engine.client_service_surface" not in sys.modules
        assert "decision_engine.request_helpers" not in sys.modules

        load_calls: list[str] = []
        fake_client = type("FakeDecisionEngineClient", (), {})
        fake_algenta_client = type("FakeAlgentaClient", (fake_client,), {})

        def _fake_import(name: str):
            load_calls.append(name)
            if name == "decision_engine.client_facade":
                return SimpleNamespace(
                    DecisionEngineClient=fake_client,
                    AlgentaClient=fake_algenta_client,
                )
            raise AssertionError(f"unexpected lazy import: {name}")

        monkeypatch.setattr(module, "import_module", _fake_import)

        assert module.DecisionEngineClient is fake_client
        assert module.AlgentaClient is fake_algenta_client
        assert module.DecisionEngineClient is fake_client
        assert module.AlgentaClient is fake_algenta_client
        assert load_calls == ["decision_engine.client_facade"]
    finally:
        for module_name in list(sys.modules):
            if module_name == "decision_engine.client":
                sys.modules.pop(module_name, None)
            elif module_name == "decision_engine.client_facade":
                sys.modules.pop(module_name, None)
            elif module_name == "decision_engine.client_connector_surface":
                sys.modules.pop(module_name, None)
            elif module_name == "decision_engine.client_service_surface":
                sys.modules.pop(module_name, None)
            elif module_name == "decision_engine.request_helpers":
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)


def test_async_decision_engine_client_wrapper_loads_facade_once_on_class_access(
    monkeypatch,
) -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "decision_engine.async_client"
        or module_name == "decision_engine.async_client_facade"
        or module_name == "decision_engine.async_client_connector_surface"
        or module_name == "decision_engine.async_client_service_surface"
        or module_name == "decision_engine.request_helpers"
    }
    for module_name in list(sys.modules):
        if module_name == "decision_engine.async_client":
            sys.modules.pop(module_name, None)
        elif module_name == "decision_engine.async_client_facade":
            sys.modules.pop(module_name, None)
        elif module_name == "decision_engine.async_client_connector_surface":
            sys.modules.pop(module_name, None)
        elif module_name == "decision_engine.async_client_service_surface":
            sys.modules.pop(module_name, None)
        elif module_name == "decision_engine.request_helpers":
            sys.modules.pop(module_name, None)

    try:
        module = importlib.import_module("decision_engine.async_client")

        assert "decision_engine.async_client_facade" not in sys.modules
        assert "decision_engine.async_client_connector_surface" not in sys.modules
        assert "decision_engine.async_client_service_surface" not in sys.modules
        assert "decision_engine.request_helpers" not in sys.modules

        load_calls: list[str] = []
        fake_client = type("FakeAsyncDecisionEngineClient", (), {})
        fake_algenta_client = type("FakeAsyncAlgentaClient", (fake_client,), {})

        def _fake_import(name: str):
            load_calls.append(name)
            if name == "decision_engine.async_client_facade":
                return SimpleNamespace(
                    AsyncDecisionEngineClient=fake_client,
                    AsyncAlgentaClient=fake_algenta_client,
                )
            raise AssertionError(f"unexpected lazy import: {name}")

        monkeypatch.setattr(module, "import_module", _fake_import)

        assert module.AsyncDecisionEngineClient is fake_client
        assert module.AsyncAlgentaClient is fake_algenta_client
        assert module.AsyncDecisionEngineClient is fake_client
        assert module.AsyncAlgentaClient is fake_algenta_client
        assert load_calls == ["decision_engine.async_client_facade"]
    finally:
        for module_name in list(sys.modules):
            if module_name == "decision_engine.async_client":
                sys.modules.pop(module_name, None)
            elif module_name == "decision_engine.async_client_facade":
                sys.modules.pop(module_name, None)
            elif module_name == "decision_engine.async_client_connector_surface":
                sys.modules.pop(module_name, None)
            elif module_name == "decision_engine.async_client_service_surface":
                sys.modules.pop(module_name, None)
            elif module_name == "decision_engine.request_helpers":
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)


def test_decision_engine_client_wrapper_loads_default_base_url_without_facade(monkeypatch) -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "decision_engine.client"
        or module_name == "decision_engine.client_facade"
        or module_name == "decision_engine._contract"
    }
    for module_name in list(sys.modules):
        if module_name == "decision_engine.client":
            sys.modules.pop(module_name, None)
        elif module_name == "decision_engine.client_facade":
            sys.modules.pop(module_name, None)
        elif module_name == "decision_engine._contract":
            sys.modules.pop(module_name, None)

    try:
        module = importlib.import_module("decision_engine.client")
        load_calls: list[str] = []

        def _fake_import(name: str):
            load_calls.append(name)
            if name == "decision_engine._contract":
                return SimpleNamespace(
                    DEFAULT_BASE_URL="http://localhost:8000",
                    CONTRACT_VERSION="v1.3",
                    BRAND="Algenta",
                    MCP_ENDPOINT="http://localhost:8000/mcp/sse",
                    MCP_TOOLS_ENDPOINT="http://localhost:8000/mcp/tools",
                    AUTH_SCHEME="bearer_api_key",
                    API_KEY_PREFIX_LIVE="de_live_",
                    API_KEY_PREFIX_TEST="de_test_",
                    LEGACY_HEADERS=("X-API-Key",),
                    LEGACY_ENV_VARS=("DE_API_KEY", "DE_BASE_URL", "ALGENTA_API_URL"),
                    LEGACY_DOMAINS=("api.algenta.io",),
                    VENDOR_TELEMETRY_HOSTS=("telemetry.algenta.ai",),
                    PRIVATE_HOST_SUFFIXES=(".internal", ".corp"),
                    DEPRECATION_WINDOW_DAYS=90,
                    READ_ONLY_DEFAULT=True,
                    WRITE_CONFIRMATION_REQUIRED=True,
                    PLAN_LIMITS={"enterprise": {"simulations_per_month": "unlimited"}},
                    INTEGRATIONS=[dict(entry) for entry in MANIFEST_BACKED_INTEGRATIONS],
                    PRIMARY_DATA_QUERY_CONTRACT={"api": {"contract_endpoint": "/v1/meta/contract"}},
                )
            raise AssertionError(f"unexpected lazy import: {name}")

        monkeypatch.setattr(module, "import_module", _fake_import)

        assert module.DEFAULT_BASE_URL == "http://localhost:8000"
        assert module.CONTRACT_VERSION == "v1.3"
        assert module.MCP_ENDPOINT == "http://localhost:8000/mcp/sse"
        assert module.LEGACY_HEADERS == ("X-API-Key",)
        assert module.READ_ONLY_DEFAULT is True
        assert_manifest_backed_integrations(module.INTEGRATIONS)
        assert module.PRIMARY_DATA_QUERY_CONTRACT["api"]["contract_endpoint"] == "/v1/meta/contract"
        assert load_calls == ["decision_engine._contract"]
    finally:
        for module_name in list(sys.modules):
            if module_name == "decision_engine.client":
                sys.modules.pop(module_name, None)
            elif module_name == "decision_engine.client_facade":
                sys.modules.pop(module_name, None)
            elif module_name == "decision_engine._contract":
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)


def test_async_decision_engine_client_wrapper_loads_default_base_url_without_facade(
    monkeypatch,
) -> None:
    preserved = {
        module_name: module
        for module_name, module in list(sys.modules.items())
        if module_name == "decision_engine.async_client"
        or module_name == "decision_engine.async_client_facade"
        or module_name == "decision_engine._contract"
    }
    for module_name in list(sys.modules):
        if module_name == "decision_engine.async_client":
            sys.modules.pop(module_name, None)
        elif module_name == "decision_engine.async_client_facade":
            sys.modules.pop(module_name, None)
        elif module_name == "decision_engine._contract":
            sys.modules.pop(module_name, None)

    try:
        module = importlib.import_module("decision_engine.async_client")
        load_calls: list[str] = []

        def _fake_import(name: str):
            load_calls.append(name)
            if name == "decision_engine._contract":
                return SimpleNamespace(
                    DEFAULT_BASE_URL="http://localhost:8000",
                    CONTRACT_VERSION="v1.3",
                    BRAND="Algenta",
                    MCP_ENDPOINT="http://localhost:8000/mcp/sse",
                    MCP_TOOLS_ENDPOINT="http://localhost:8000/mcp/tools",
                    AUTH_SCHEME="bearer_api_key",
                    API_KEY_PREFIX_LIVE="de_live_",
                    API_KEY_PREFIX_TEST="de_test_",
                    LEGACY_HEADERS=("X-API-Key",),
                    LEGACY_ENV_VARS=("DE_API_KEY", "DE_BASE_URL", "ALGENTA_API_URL"),
                    LEGACY_DOMAINS=("api.algenta.io",),
                    VENDOR_TELEMETRY_HOSTS=("telemetry.algenta.ai",),
                    PRIVATE_HOST_SUFFIXES=(".internal", ".corp"),
                    DEPRECATION_WINDOW_DAYS=90,
                    READ_ONLY_DEFAULT=True,
                    WRITE_CONFIRMATION_REQUIRED=True,
                    PLAN_LIMITS={"enterprise": {"simulations_per_month": "unlimited"}},
                    INTEGRATIONS=[dict(entry) for entry in MANIFEST_BACKED_INTEGRATIONS],
                    PRIMARY_DATA_QUERY_CONTRACT={"api": {"contract_endpoint": "/v1/meta/contract"}},
                )
            raise AssertionError(f"unexpected lazy import: {name}")

        monkeypatch.setattr(module, "import_module", _fake_import)

        assert module.DEFAULT_BASE_URL == "http://localhost:8000"
        assert module.CONTRACT_VERSION == "v1.3"
        assert module.MCP_TOOLS_ENDPOINT == "http://localhost:8000/mcp/tools"
        assert module.LEGACY_HEADERS == ("X-API-Key",)
        assert module.READ_ONLY_DEFAULT is True
        assert_manifest_backed_integrations(module.INTEGRATIONS)
        assert module.PRIMARY_DATA_QUERY_CONTRACT["api"]["contract_endpoint"] == "/v1/meta/contract"
        assert load_calls == ["decision_engine._contract"]
    finally:
        for module_name in list(sys.modules):
            if module_name == "decision_engine.async_client":
                sys.modules.pop(module_name, None)
            elif module_name == "decision_engine.async_client_facade":
                sys.modules.pop(module_name, None)
            elif module_name == "decision_engine._contract":
                sys.modules.pop(module_name, None)
        sys.modules.update(preserved)
