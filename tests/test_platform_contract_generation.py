from __future__ import annotations

import importlib
import sys
from pathlib import Path

from apps import platform_contract_constants as generated_contract
from apps.platform_contract import load_platform_contract

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
    assert generated_contract.DEPRECATION_WINDOW_DAYS == contract.deprecation_window_days
    assert generated_contract.PLAN_LIMITS == contract.plan_limits


def test_openapi_and_runtime_defaults_use_generated_contract(monkeypatch) -> None:
    main_text = (ROOT / "apps" / "api_server" / "main.py").read_text()
    assert "from apps.platform_contract_constants import API_BASE_URL, MCP_ENDPOINT" in main_text
    assert 'schema["servers"] = [{"url": API_BASE_URL}]' in main_text
    assert 'schema["x-canonical-mcp-endpoint"] = MCP_ENDPOINT' in main_text

    monkeypatch.delenv("ALGENTA_BASE_URL", raising=False)
    monkeypatch.delenv("DE_BASE_URL", raising=False)
    monkeypatch.delenv("ALGENTA_API_URL", raising=False)
    monkeypatch.delenv("ALGENTA_CONTROL_PLANE_URL", raising=False)

    mcp_config = importlib.reload(importlib.import_module("apps.mcp_server.config"))
    runtime_sdk = importlib.reload(importlib.import_module("apps.runtime.sdk"))
    runtime_license = importlib.reload(importlib.import_module("apps.runtime.license"))

    assert mcp_config.BASE_URL == generated_contract.API_BASE_URL
    assert runtime_sdk._CLOUD_API_URL == generated_contract.API_BASE_URL
    assert runtime_license._CONTROL_PLANE_URL == generated_contract.API_BASE_URL


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
    assert py_sdk_contract.AUTH_SCHEME == contract.auth_scheme
    assert py_sdk_contract.API_KEY_PREFIX_LIVE == contract.api_key_prefix_live
    assert py_sdk_contract.API_KEY_PREFIX_TEST == contract.api_key_prefix_test

    assert algenta_contract.DEFAULT_BASE_URL == contract.api_base_url
    assert algenta_contract.AUTH_SCHEME == contract.auth_scheme
    assert algenta_contract.API_KEY_PREFIX_LIVE == contract.api_key_prefix_live
    assert algenta_contract.API_KEY_PREFIX_TEST == contract.api_key_prefix_test

    ts_contract = (ROOT / "packages" / "ts-sdk" / "src" / "contract.ts").read_text()
    assert f'export const DEFAULT_BASE_URL = "{contract.api_base_url}";' in ts_contract
    assert f'export const MCP_ENDPOINT = "{contract.mcp_endpoint}";' in ts_contract
    assert f'export const AUTH_SCHEME = "{contract.auth_scheme}";' in ts_contract


def test_python_sdk_accepts_canonical_env_api_key(monkeypatch) -> None:
    monkeypatch.setenv("ALGENTA_API_KEY", "de_test_canonical")
    monkeypatch.delenv("DE_API_KEY", raising=False)
    client_mod = _import_from_path(
        ROOT / "packages" / "python-sdk",
        "decision_engine.client",
    )

    client = client_mod.DecisionEngineClient(api_key=None, base_url="http://localhost")

    assert client._api_key == "de_test_canonical"
