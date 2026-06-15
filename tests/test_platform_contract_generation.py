from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

from apps import platform_contract_constants as generated_contract
from apps.platform_contract import load_platform_contract
from apps.platform_contract_fallback import (
    PlatformContractFallbackError,
    build_platform_contract_from_openapi,
)
from tests._manifest_backed_integrations import (
    assert_manifest_backed_integration_texts_equal,
    assert_manifest_backed_integrations,
)

ROOT = Path(__file__).resolve().parents[1]


def _import_from_path(package_root: Path, module_name: str):
    sys.path.insert(0, str(package_root))
    try:
        return importlib.import_module(module_name)
    finally:
        sys.path.pop(0)


def test_generated_python_contract_matches_manifest() -> None:
    contract = load_platform_contract()

    assert generated_contract.CONTRACT_VERSION == contract.contract_version
    assert generated_contract.BRAND == contract.brand
    assert generated_contract.API_BASE_URL == contract.api_base_url
    assert generated_contract.MCP_ENDPOINT == contract.mcp_endpoint
    assert generated_contract.MCP_TOOLS_ENDPOINT == contract.mcp_tools_endpoint
    assert generated_contract.AUTH_SCHEME == contract.auth_scheme
    assert generated_contract.API_KEY_PREFIX_LIVE == contract.api_key_prefix_live
    assert generated_contract.API_KEY_PREFIX_TEST == contract.api_key_prefix_test
    assert generated_contract.LEGACY_ENV_VARS == contract.legacy_env_vars
    assert generated_contract.LEGACY_DOMAINS == contract.legacy_domains
    assert generated_contract.ALGENTA_OWNED_HOSTS == contract.algenta_owned_hosts
    assert generated_contract.ALGENTA_OWNED_SUFFIXES == contract.algenta_owned_suffixes
    assert generated_contract.VENDOR_TELEMETRY_HOSTS == contract.vendor_telemetry_hosts
    assert generated_contract.PRIVATE_HOST_SUFFIXES == contract.private_host_suffixes
    assert generated_contract.DEPRECATION_WINDOW_DAYS == contract.deprecation_window_days
    assert generated_contract.PLAN_LIMITS == contract.plan_limits
    assert generated_contract.PRIMARY_DATA_QUERY_CONTRACT == contract.primary_data_query_contract
    assert generated_contract.CAPABILITY_PLANE_CONTRACT == contract.capability_plane
    assert_manifest_backed_integrations(contract.integrations)
    assert (
        generated_contract.PRIMARY_DATA_QUERY_CONTRACT["api"]["contract_endpoint"]
        == "/v1/meta/contract"
    )
    assert (
        generated_contract.PRIMARY_DATA_QUERY_CONTRACT["governed_filter_contract"]["kind"]
        == "record_predicates"
    )
    assert (
        generated_contract.PRIMARY_DATA_QUERY_CONTRACT["direct_sdk"]["python"]["contract_method"]
        == "get_contract"
    )
    assert (
        generated_contract.PRIMARY_DATA_QUERY_CONTRACT["cli"]["contract_command"] == "de contract"
    )
    assert generated_contract.PRIMARY_DATA_QUERY_CONTRACT["mcp"]["contract_tool"] == "get_contract"


def test_openapi_and_runtime_defaults_use_generated_contract(
    monkeypatch,
    tmp_path: Path,
) -> None:
    main_text = (ROOT / "apps" / "api_server" / "main.py").read_text()
    assert "from apps.api_server.openapi_surface import apply_openapi_surface" in main_text
    assert "CAPABILITY_PLANE_CONTRACT" in main_text
    assert "PRIMARY_DATA_QUERY_CONTRACT" in main_text
    assert "apply_openapi_surface(schema)" in main_text
    assert 'schema["x-primary-data-query-contract"] = PRIMARY_DATA_QUERY_CONTRACT' in main_text
    assert 'schema["x-capability-plane-contract"] = CAPABILITY_PLANE_CONTRACT' in main_text

    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)
    monkeypatch.delenv("ALGENTA_CONTROL_PLANE_URL", raising=False)
    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(tmp_path / "runtime"))

    mcp_config = importlib.reload(importlib.import_module("apps.mcp_server.config"))
    runtime_sdk = importlib.reload(importlib.import_module("apps.runtime.sdk"))
    runtime_license = importlib.reload(importlib.import_module("apps.runtime.license"))

    assert mcp_config.BASE_URL == generated_contract.API_BASE_URL
    assert runtime_sdk._cloud_api_url() == generated_contract.API_BASE_URL
    assert runtime_license._validated_control_plane_url() == generated_contract.API_BASE_URL


def test_generated_sdk_contract_artifacts_match_manifest() -> None:
    contract = load_platform_contract()

    py_sdk_contract = _import_from_path(
        ROOT / "packages" / "python-sdk",
        "decision_engine._contract",
    )
    algenta_contract = _import_from_path(
        ROOT / "packages" / "algenta-core",
        "algenta._contract",
    )

    assert py_sdk_contract.DEFAULT_BASE_URL == contract.api_base_url
    assert py_sdk_contract.CONTRACT_VERSION == contract.contract_version
    assert py_sdk_contract.BRAND == contract.brand
    assert py_sdk_contract.MCP_ENDPOINT == contract.mcp_endpoint
    assert py_sdk_contract.MCP_TOOLS_ENDPOINT == contract.mcp_tools_endpoint
    assert py_sdk_contract.AUTH_SCHEME == contract.auth_scheme
    assert py_sdk_contract.API_KEY_PREFIX_LIVE == contract.api_key_prefix_live
    assert py_sdk_contract.API_KEY_PREFIX_TEST == contract.api_key_prefix_test
    assert py_sdk_contract.LEGACY_HEADERS == contract.legacy_headers
    assert py_sdk_contract.LEGACY_DOMAINS == contract.legacy_domains
    assert py_sdk_contract.ALGENTA_OWNED_HOSTS == contract.algenta_owned_hosts
    assert py_sdk_contract.ALGENTA_OWNED_SUFFIXES == contract.algenta_owned_suffixes
    assert py_sdk_contract.DEPRECATION_WINDOW_DAYS == contract.deprecation_window_days
    assert py_sdk_contract.READ_ONLY_DEFAULT is True
    assert py_sdk_contract.WRITE_CONFIRMATION_REQUIRED is True
    assert py_sdk_contract.PLAN_LIMITS == contract.plan_limits
    assert_manifest_backed_integrations(list(py_sdk_contract.INTEGRATIONS))
    assert py_sdk_contract.PRIMARY_DATA_QUERY_CONTRACT == contract.primary_data_query_contract
    assert py_sdk_contract.CAPABILITY_PLANE_CONTRACT == contract.capability_plane
    assert (
        py_sdk_contract.PRIMARY_DATA_QUERY_CONTRACT["api"]["contract_endpoint"]
        == "/v1/meta/contract"
    )
    assert py_sdk_contract.PRIMARY_DATA_QUERY_CONTRACT["governed_filter_contract"]["operators"][
        "nullary"
    ] == ["is_null", "is_not_null"]
    assert (
        py_sdk_contract.PRIMARY_DATA_QUERY_CONTRACT["direct_sdk"]["python"][
            "preferred_client_class"
        ]
        == "CodnaClient"
    )
    assert (
        py_sdk_contract.PRIMARY_DATA_QUERY_CONTRACT["direct_sdk"]["python"]["contract_method"]
        == "get_contract"
    )
    assert (
        py_sdk_contract.PRIMARY_DATA_QUERY_CONTRACT["runtime_sdk"]["python"]["runtime_class"]
        == "Runtime"
    )

    assert algenta_contract.DEFAULT_BASE_URL == contract.api_base_url
    assert algenta_contract.CONTRACT_VERSION == contract.contract_version
    assert algenta_contract.BRAND == contract.brand
    assert algenta_contract.MCP_ENDPOINT == contract.mcp_endpoint
    assert algenta_contract.MCP_TOOLS_ENDPOINT == contract.mcp_tools_endpoint
    assert algenta_contract.AUTH_SCHEME == contract.auth_scheme
    assert algenta_contract.API_KEY_PREFIX_LIVE == contract.api_key_prefix_live
    assert algenta_contract.API_KEY_PREFIX_TEST == contract.api_key_prefix_test
    assert algenta_contract.LEGACY_HEADERS == contract.legacy_headers
    assert algenta_contract.LEGACY_DOMAINS == contract.legacy_domains
    assert algenta_contract.ALGENTA_OWNED_HOSTS == contract.algenta_owned_hosts
    assert algenta_contract.ALGENTA_OWNED_SUFFIXES == contract.algenta_owned_suffixes
    assert algenta_contract.DEPRECATION_WINDOW_DAYS == contract.deprecation_window_days
    assert algenta_contract.READ_ONLY_DEFAULT is True
    assert algenta_contract.WRITE_CONFIRMATION_REQUIRED is True
    assert algenta_contract.PLAN_LIMITS == contract.plan_limits
    assert_manifest_backed_integrations(list(algenta_contract.INTEGRATIONS))
    assert algenta_contract.PRIMARY_DATA_QUERY_CONTRACT == contract.primary_data_query_contract
    assert algenta_contract.CAPABILITY_PLANE_CONTRACT == contract.capability_plane
    assert (
        algenta_contract.PRIMARY_DATA_QUERY_CONTRACT["governed_filter_contract"][
            "supports_non_sql_backends"
        ]
        is True
    )
    assert (
        algenta_contract.PRIMARY_DATA_QUERY_CONTRACT["runtime_sdk"]["python"]["contract_method"]
        == "get_contract"
    )
    assert (
        algenta_contract.PRIMARY_DATA_QUERY_CONTRACT["runtime_sdk"]["python"][
            "libraries_entrypoint"
        ]
        == "libraries"
    )

    ts_contract = (ROOT / "packages" / "ts-sdk" / "src" / "contract.ts").read_text()
    assert f'export const DEFAULT_BASE_URL = "{contract.api_base_url}";' in ts_contract
    assert f'export const MCP_ENDPOINT = "{contract.mcp_endpoint}";' in ts_contract
    assert "export const LEGACY_HEADERS =" in ts_contract
    assert "export const LEGACY_DOMAINS =" in ts_contract
    assert "export const ALGENTA_OWNED_HOSTS =" in ts_contract
    assert "export const ALGENTA_OWNED_SUFFIXES =" in ts_contract
    assert "export const PRIVATE_HOST_SUFFIXES =" in ts_contract
    assert "export const DEPRECATION_WINDOW_DAYS = 90;" in ts_contract
    assert "export const READ_ONLY_DEFAULT = true;" in ts_contract
    assert "export const WRITE_CONFIRMATION_REQUIRED = true;" in ts_contract
    assert "export const PLAN_LIMITS =" in ts_contract
    assert f'export const AUTH_SCHEME = "{contract.auth_scheme}";' in ts_contract
    assert "export const PRIMARY_DATA_QUERY_CONTRACT =" in ts_contract
    assert "export const CAPABILITY_PLANE_CONTRACT =" in ts_contract
    assert '"contract_endpoint": "/v1/meta/contract"' in ts_contract
    assert '"list_providers_endpoint": "/v1/capability-providers"' in ts_contract
    assert '"governed_filter_contract": {' in ts_contract
    assert '"kind": "record_predicates"' in ts_contract
    assert '"discovery_endpoint": "/v1/data"' in ts_contract
    assert '"preferred_client_class": "CodnaClient"' in ts_contract
    assert '"contract_method": "getContract"' in ts_contract
    assert '"runtime_class": "Runtime"' in ts_contract
    assert '"libraries_entrypoint": "libraries"' in ts_contract

    ts_dist_contract = (ROOT / "packages" / "ts-sdk" / "dist" / "contract.js").read_text()
    assert_manifest_backed_integration_texts_equal(ts_dist_contract, ts_contract)

    gateway_registry = (ROOT / "apps" / "gateway" / "src" / "privacy_registry.ts").read_text()
    assert "export const ALGENTA_OWNED_HOSTS =" in gateway_registry
    assert "export const ALGENTA_OWNED_SUFFIXES =" in gateway_registry
    assert "export const PRIVATE_HOST_SUFFIXES =" in gateway_registry


def test_python_sdk_accepts_canonical_env_api_key(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_API_KEY", "de_test_canonical")
    monkeypatch.delenv("DE_API_KEY", raising=False)
    client_mod = _import_from_path(
        ROOT / "packages" / "python-sdk",
        "decision_engine.client",
    )

    client = client_mod.DecisionEngineClient(api_key=None, base_url="http://localhost")

    assert client._api_key == "de_test_canonical"


def test_platform_contract_fallback_rejects_non_object_payload() -> None:
    with pytest.raises(PlatformContractFallbackError, match="JSON object") as exc:
        build_platform_contract_from_openapi(
            api_base_url="https://example.test/self-host",
            openapi_payload=[],
        )
    assert exc.value.code == "invalid_contract_payload"


def test_platform_contract_fallback_rejects_missing_api_section() -> None:
    with pytest.raises(PlatformContractFallbackError, match="api contract section") as exc:
        build_platform_contract_from_openapi(
            api_base_url="https://example.test/self-host",
            openapi_payload={
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "mcp": {"contract_tool": "get_contract"},
                },
            },
        )
    assert exc.value.code == "invalid_contract_payload"


def test_platform_contract_fallback_rejects_missing_contract_endpoint() -> None:
    with pytest.raises(
        PlatformContractFallbackError,
        match="api.contract_endpoint",
    ) as exc:
        build_platform_contract_from_openapi(
            api_base_url="https://example.test/self-host",
            openapi_payload={
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "api": {"query_batch_endpoint": "/v1/query/batch"},
                    "mcp": {"contract_tool": "get_contract"},
                },
            },
        )
    assert exc.value.code == "invalid_contract_payload"


def test_platform_contract_fallback_rejects_invalid_nested_contract_override() -> None:
    with pytest.raises(
        PlatformContractFallbackError,
        match="runtime_sdk.typescript.runtime_class",
    ) as exc:
        build_platform_contract_from_openapi(
            api_base_url="https://example.test/self-host",
            openapi_payload={
                "openapi": "3.1.0",
                "x-primary-data-query-contract": {
                    "api": {"contract_endpoint": "/v1/meta/contract"},
                    "mcp": {"contract_tool": "get_contract"},
                    "runtime_sdk": {
                        "typescript": {"runtime_class": None},
                    },
                },
            },
        )
    assert exc.value.code == "invalid_contract_payload"


def test_platform_contract_fallback_uses_manifest_integration_inventory() -> None:
    payload = build_platform_contract_from_openapi(
        api_base_url="https://example.test/self-host",
        openapi_payload={
            "openapi": "3.1.0",
            "x-primary-data-query-contract": {
                "api": {"contract_endpoint": "/v1/meta/contract"},
                "mcp": {"contract_tool": "get_contract"},
            },
        },
    )

    assert_manifest_backed_integrations(payload["integrations"])
