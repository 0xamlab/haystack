from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
PYTHON_SDK = ROOT / "packages" / "python-sdk"
if str(PYTHON_SDK) not in sys.path:
    sys.path.insert(0, str(PYTHON_SDK))

_SYNC_FACADE_MODULES = (
    "decision_engine.client_facade",
    "decision_engine.client_contract_surface",
    "decision_engine.client_query_surface",
    "decision_engine.client_simulation_surface",
    "decision_engine.client_source_surface",
    "decision_engine.client_job_surface",
    "decision_engine.client_account_surface",
    "decision_engine.client_decision_surface",
    "decision_engine.request_helpers",
)

_ASYNC_FACADE_MODULES = (
    "decision_engine.async_client_facade",
    "decision_engine.async_client_contract_surface",
    "decision_engine.async_client_query_surface",
    "decision_engine.async_client_simulation_surface",
    "decision_engine.async_client_source_surface",
    "decision_engine.async_client_job_surface",
    "decision_engine.async_client_account_surface",
    "decision_engine.async_client_decision_surface",
    "decision_engine.request_helpers",
)


def _preserve_modules(names: tuple[str, ...]) -> dict[str, Any]:
    preserved = {name: module for name, module in list(sys.modules.items()) if name in set(names)}
    for module_name in names:
        sys.modules.pop(module_name, None)
    return preserved


def _restore_modules(names: tuple[str, ...], preserved: dict[str, Any]) -> None:
    for module_name in names:
        sys.modules.pop(module_name, None)
    sys.modules.update(preserved)


def _assert_sync_surfaces_cold() -> None:
    assert "decision_engine.client_contract_surface" not in sys.modules
    assert "decision_engine.client_query_surface" not in sys.modules
    assert "decision_engine.client_simulation_surface" not in sys.modules
    assert "decision_engine.client_source_surface" not in sys.modules
    assert "decision_engine.client_job_surface" not in sys.modules
    assert "decision_engine.client_account_surface" not in sys.modules
    assert "decision_engine.request_helpers" not in sys.modules


def _assert_async_surfaces_cold() -> None:
    assert "decision_engine.async_client_contract_surface" not in sys.modules
    assert "decision_engine.async_client_query_surface" not in sys.modules
    assert "decision_engine.async_client_simulation_surface" not in sys.modules
    assert "decision_engine.async_client_source_surface" not in sys.modules
    assert "decision_engine.async_client_job_surface" not in sys.modules
    assert "decision_engine.async_client_account_surface" not in sys.modules
    assert "decision_engine.request_helpers" not in sys.modules


@pytest.mark.parametrize(
    ("loader_attr", "method_name", "expected_module", "call_args", "call_kwargs", "surface"),
    [
        (
            "_contract_surface_module",
            "get_contract",
            "decision_engine.client_contract_surface",
            (),
            {},
            SimpleNamespace(get_contract=lambda _client: {"contract_version": "v1.3"}),
        ),
        (
            "_contract_surface_module",
            "get_runtime_manifest",
            "decision_engine.client_contract_surface",
            (),
            {},
            SimpleNamespace(get_runtime_manifest=lambda _client: {"runtime_version": "2026.05.0"}),
        ),
        (
            "_contract_surface_module",
            "get_runtime_modules",
            "decision_engine.client_contract_surface",
            (),
            {},
            SimpleNamespace(get_runtime_modules=lambda _client: {"summary": {"module_count": 22}}),
        ),
        (
            "_contract_surface_module",
            "get_runtime_benchmarks",
            "decision_engine.client_contract_surface",
            (),
            {},
            SimpleNamespace(
                get_runtime_benchmarks=lambda _client: {
                    "module_benchmarks": [{"name": "bpe_tokenizer"}]
                }
            ),
        ),
        (
            "_contract_surface_module",
            "get_runtime_release_validation",
            "decision_engine.client_contract_surface",
            (),
            {},
            SimpleNamespace(
                get_runtime_release_validation=lambda _client: {"valid_release": True}
            ),
        ),
        (
            "_query_surface_module",
            "resolve",
            "decision_engine.client_query_surface",
            ({"metric": "revenue"},),
            {"group_by": "region"},
            SimpleNamespace(
                resolve=lambda _client, request=None, **kwargs: {
                    "request": request,
                    "kwargs": kwargs,
                }
            ),
        ),
        (
            "_simulation_surface_module",
            "simulate",
            "decision_engine.client_simulation_surface",
            (),
            {"mode": "auto"},
            SimpleNamespace(simulate=lambda _client, **kwargs: {"kwargs": kwargs}),
        ),
        (
            "_source_surface_module",
            "register_source",
            "decision_engine.client_source_surface",
            ({"type": "file", "path": "orders.csv"},),
            {"description": "Orders"},
            SimpleNamespace(
                register_source=lambda _client, source=None, **kwargs: {
                    "source": source,
                    "kwargs": kwargs,
                }
            ),
        ),
        (
            "_job_surface_module",
            "get_job",
            "decision_engine.client_job_surface",
            ("job_123",),
            {},
            SimpleNamespace(get_job=lambda _client, job_id: {"job_id": job_id}),
        ),
        (
            "_account_surface_module",
            "me",
            "decision_engine.client_account_surface",
            (),
            {},
            SimpleNamespace(me=lambda _client: {"org": "algenta"}),
        ),
        (
            "_account_surface_module",
            "create_api_key",
            "decision_engine.client_account_surface",
            (),
            {"label": "Mission Key"},
            SimpleNamespace(
                create_api_key=lambda _client, label=None, **kwargs: {
                    "label": label,
                    "kwargs": kwargs,
                }
            ),
        ),
        (
            "_account_surface_module",
            "revoke_api_key",
            "decision_engine.client_account_surface",
            ("key_123",),
            {},
            SimpleNamespace(revoke_api_key=lambda _client, key_id: {"key_id": key_id}),
        ),
    ],
)
def test_decision_engine_client_facade_loads_expected_surface(
    monkeypatch: pytest.MonkeyPatch,
    loader_attr: str,
    method_name: str,
    expected_module: str,
    call_args: tuple[Any, ...],
    call_kwargs: dict[str, Any],
    surface: Any,
) -> None:
    preserved = _preserve_modules(_SYNC_FACADE_MODULES)

    try:
        module = importlib.import_module("decision_engine.client_facade")
        _assert_sync_surfaces_cold()

        getattr(module, loader_attr).cache_clear()
        load_calls: list[str] = []

        def _fake_import(name: str):
            load_calls.append(name)
            if name == expected_module:
                return surface
            raise AssertionError(f"unexpected lazy import: {name}")

        monkeypatch.setattr(module.importlib, "import_module", _fake_import)

        client = object.__new__(module.DecisionEngineClient)
        result = getattr(client, method_name)(*call_args, **call_kwargs)

        if method_name == "get_contract":
            assert result == {"contract_version": "v1.3"}
        elif method_name == "get_runtime_manifest":
            assert result == {"runtime_version": "2026.05.0"}
        elif method_name == "get_runtime_modules":
            assert result == {"summary": {"module_count": 22}}
        elif method_name == "get_runtime_benchmarks":
            assert result == {"module_benchmarks": [{"name": "bpe_tokenizer"}]}
        elif method_name == "get_runtime_release_validation":
            assert result == {"valid_release": True}
        elif method_name == "resolve":
            assert result == {"request": {"metric": "revenue"}, "kwargs": {"group_by": "region"}}
        elif method_name == "simulate":
            assert result == {"kwargs": {"mode": "auto"}}
        elif method_name == "register_source":
            assert result == {
                "source": {"type": "file", "path": "orders.csv"},
                "kwargs": {"description": "Orders"},
            }
        elif method_name == "get_job":
            assert result == {"job_id": "job_123"}
        elif method_name == "create_api_key":
            assert result == {"label": "Mission Key", "kwargs": {"name": None, "expires_at": None}}
        elif method_name == "revoke_api_key":
            assert result == {"key_id": "key_123"}
        else:
            assert result == {"org": "algenta"}

        assert load_calls == [expected_module]
    finally:
        _restore_modules(_SYNC_FACADE_MODULES, preserved)


def test_decision_engine_client_facade_forwards_zero_device_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preserved = _preserve_modules(_SYNC_FACADE_MODULES)

    try:
        module = importlib.import_module("decision_engine.client_facade")
        _assert_sync_surfaces_cold()

        module._account_surface_module.cache_clear()
        load_calls: list[str] = []

        surface = SimpleNamespace(
            create_api_key=lambda _client, label=None, **kwargs: {
                "label": label,
                "kwargs": kwargs,
            }
        )

        def _fake_import(name: str):
            load_calls.append(name)
            if name == "decision_engine.client_account_surface":
                return surface
            raise AssertionError(f"unexpected lazy import: {name}")

        monkeypatch.setattr(module.importlib, "import_module", _fake_import)

        client = object.__new__(module.DecisionEngineClient)
        result = client.create_api_key("Mission Key", device_limit=0)

        assert result == {
            "label": "Mission Key",
            "kwargs": {"name": None, "expires_at": None, "device_limit": 0},
        }
        assert load_calls == ["decision_engine.client_account_surface"]
    finally:
        _restore_modules(_SYNC_FACADE_MODULES, preserved)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("loader_attr", "method_name", "expected_module", "call_args", "call_kwargs", "surface"),
    [
        (
            "_contract_surface_module",
            "get_contract",
            "decision_engine.async_client_contract_surface",
            (),
            {},
            SimpleNamespace(
                get_contract=lambda _client: _async_result({"contract_version": "v1.3"})
            ),
        ),
        (
            "_contract_surface_module",
            "get_runtime_manifest",
            "decision_engine.async_client_contract_surface",
            (),
            {},
            SimpleNamespace(
                get_runtime_manifest=lambda _client: _async_result(
                    {"runtime_version": "2026.05.0"}
                )
            ),
        ),
        (
            "_contract_surface_module",
            "get_runtime_modules",
            "decision_engine.async_client_contract_surface",
            (),
            {},
            SimpleNamespace(
                get_runtime_modules=lambda _client: _async_result(
                    {"summary": {"module_count": 22}}
                )
            ),
        ),
        (
            "_contract_surface_module",
            "get_runtime_benchmarks",
            "decision_engine.async_client_contract_surface",
            (),
            {},
            SimpleNamespace(
                get_runtime_benchmarks=lambda _client: _async_result(
                    {"module_benchmarks": [{"name": "bpe_tokenizer"}]}
                )
            ),
        ),
        (
            "_contract_surface_module",
            "get_runtime_release_validation",
            "decision_engine.async_client_contract_surface",
            (),
            {},
            SimpleNamespace(
                get_runtime_release_validation=lambda _client: _async_result(
                    {"valid_release": True}
                )
            ),
        ),
        (
            "_query_surface_module",
            "resolve",
            "decision_engine.async_client_query_surface",
            ({"metric": "revenue"},),
            {"group_by": "region"},
            SimpleNamespace(
                resolve=lambda _client, request=None, **kwargs: _async_result(
                    {"request": request, "kwargs": kwargs}
                )
            ),
        ),
        (
            "_simulation_surface_module",
            "simulate",
            "decision_engine.async_client_simulation_surface",
            (),
            {"mode": "auto"},
            SimpleNamespace(simulate=lambda _client, **kwargs: _async_result({"kwargs": kwargs})),
        ),
        (
            "_source_surface_module",
            "register_source",
            "decision_engine.async_client_source_surface",
            ({"type": "file", "path": "orders.csv"},),
            {"description": "Orders"},
            SimpleNamespace(
                register_source=lambda _client, source=None, **kwargs: _async_result(
                    {"source": source, "kwargs": kwargs}
                )
            ),
        ),
        (
            "_job_surface_module",
            "get_job",
            "decision_engine.async_client_job_surface",
            ("job_123",),
            {},
            SimpleNamespace(get_job=lambda _client, job_id: _async_result({"job_id": job_id})),
        ),
        (
            "_account_surface_module",
            "me",
            "decision_engine.async_client_account_surface",
            (),
            {},
            SimpleNamespace(me=lambda _client: _async_result({"org": "algenta"})),
        ),
        (
            "_account_surface_module",
            "create_api_key",
            "decision_engine.async_client_account_surface",
            (),
            {"label": "Mission Key"},
            SimpleNamespace(
                create_api_key=lambda _client, label=None, **kwargs: _async_result(
                    {"label": label, "kwargs": kwargs}
                )
            ),
        ),
        (
            "_account_surface_module",
            "revoke_api_key",
            "decision_engine.async_client_account_surface",
            ("key_123",),
            {},
            SimpleNamespace(
                revoke_api_key=lambda _client, key_id: _async_result({"key_id": key_id})
            ),
        ),
    ],
)
async def test_async_client_facade_loads_expected_surface(
    monkeypatch: pytest.MonkeyPatch,
    loader_attr: str,
    method_name: str,
    expected_module: str,
    call_args: tuple[Any, ...],
    call_kwargs: dict[str, Any],
    surface: Any,
) -> None:
    preserved = _preserve_modules(_ASYNC_FACADE_MODULES)

    try:
        module = importlib.import_module("decision_engine.async_client_facade")
        _assert_async_surfaces_cold()

        getattr(module, loader_attr).cache_clear()
        load_calls: list[str] = []

        def _fake_import(name: str):
            load_calls.append(name)
            if name == expected_module:
                return surface
            raise AssertionError(f"unexpected lazy import: {name}")

        monkeypatch.setattr(module.importlib, "import_module", _fake_import)

        client = object.__new__(module.AsyncDecisionEngineClient)
        result = await getattr(client, method_name)(*call_args, **call_kwargs)

        if method_name == "get_contract":
            assert result == {"contract_version": "v1.3"}
        elif method_name == "get_runtime_manifest":
            assert result == {"runtime_version": "2026.05.0"}
        elif method_name == "get_runtime_modules":
            assert result == {"summary": {"module_count": 22}}
        elif method_name == "get_runtime_benchmarks":
            assert result == {"module_benchmarks": [{"name": "bpe_tokenizer"}]}
        elif method_name == "get_runtime_release_validation":
            assert result == {"valid_release": True}
        elif method_name == "resolve":
            assert result == {"request": {"metric": "revenue"}, "kwargs": {"group_by": "region"}}
        elif method_name == "simulate":
            assert result == {"kwargs": {"mode": "auto"}}
        elif method_name == "register_source":
            assert result == {
                "source": {"type": "file", "path": "orders.csv"},
                "kwargs": {"description": "Orders"},
            }
        elif method_name == "get_job":
            assert result == {"job_id": "job_123"}
        elif method_name == "create_api_key":
            assert result == {"label": "Mission Key", "kwargs": {"name": None, "expires_at": None}}
        elif method_name == "revoke_api_key":
            assert result == {"key_id": "key_123"}
        else:
            assert result == {"org": "algenta"}

        assert load_calls == [expected_module]
    finally:
        _restore_modules(_ASYNC_FACADE_MODULES, preserved)


@pytest.mark.anyio
async def test_async_client_facade_forwards_zero_device_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preserved = _preserve_modules(_ASYNC_FACADE_MODULES)

    try:
        module = importlib.import_module("decision_engine.async_client_facade")
        _assert_async_surfaces_cold()

        module._account_surface_module.cache_clear()
        load_calls: list[str] = []

        surface = SimpleNamespace(
            create_api_key=lambda _client, label=None, **kwargs: _async_result(
                {"label": label, "kwargs": kwargs}
            )
        )

        def _fake_import(name: str):
            load_calls.append(name)
            if name == "decision_engine.async_client_account_surface":
                return surface
            raise AssertionError(f"unexpected lazy import: {name}")

        monkeypatch.setattr(module.importlib, "import_module", _fake_import)

        client = object.__new__(module.AsyncDecisionEngineClient)
        result = await client.create_api_key("Mission Key", device_limit=0)

        assert result == {
            "label": "Mission Key",
            "kwargs": {"name": None, "expires_at": None, "device_limit": 0},
        }
        assert load_calls == ["decision_engine.async_client_account_surface"]
    finally:
        _restore_modules(_ASYNC_FACADE_MODULES, preserved)


async def _async_result(value: Any) -> Any:
    return value
