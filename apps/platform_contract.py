from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = _ROOT / "apps" / "docs" / "integration_manifest.v1.json"


@dataclass(frozen=True)
class PlatformContract:
    contract_version: str
    brand: str
    api_base_url: str
    mcp_endpoint: str
    mcp_tools_endpoint: str
    auth_scheme: str
    api_key_prefix_live: str
    api_key_prefix_test: str
    legacy_headers: tuple[str, ...]
    legacy_env_vars: tuple[str, ...]
    legacy_domains: tuple[str, ...]
    deprecation_window_days: int
    plan_limits: dict[str, dict[str, Any]]
    integrations: tuple[dict[str, Any], ...]


@lru_cache(maxsize=1)
def load_platform_contract() -> PlatformContract:
    manifest = json.loads(MANIFEST_PATH.read_text())
    compatibility = manifest["compatibility"]
    defaults = manifest["defaults"]
    return PlatformContract(
        contract_version=manifest["contract_version"],
        brand=manifest["brand"],
        api_base_url=manifest["api_base_url"],
        mcp_endpoint=manifest["mcp_endpoint"],
        mcp_tools_endpoint=manifest["mcp_tools_endpoint"],
        auth_scheme=manifest["auth_scheme"],
        api_key_prefix_live=manifest["api_key_prefixes"]["live"],
        api_key_prefix_test=manifest["api_key_prefixes"]["test"],
        legacy_headers=tuple(compatibility["legacy_headers"]),
        legacy_env_vars=tuple(compatibility["legacy_env_vars"]),
        legacy_domains=tuple(compatibility["legacy_domains"]),
        deprecation_window_days=int(compatibility["deprecation_window_days"]),
        plan_limits=dict(defaults["plan_limits"]),
        integrations=tuple(dict(item) for item in manifest["integrations"]),
    )
