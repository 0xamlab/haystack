"""Platform contract surface helpers for public and private deployments."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlsplit

from apps.api_server.config import get_settings
from apps.api_server.services.public_url_policy import (
    has_explicit_public_api_base_url_override,
    resolve_api_public_base_url,
)
from apps.platform_contract import PlatformContractResponse, validate_platform_contract_payload
from apps.platform_contract_constants import API_BASE_URL


def _config_attr(config: object, name: str) -> Any:
    if isinstance(config, Mapping):
        return config.get(name)
    return getattr(config, name, None)


def _public_base_url_override_present(env: Mapping[str, str] | None = None) -> bool:
    mapping = os.environ if env is None else env
    return has_explicit_public_api_base_url_override(mapping, env=mapping)


def _should_rebase_surface_urls(
    config: object,
    *,
    env: Mapping[str, str] | None = None,
) -> bool:
    policy = _config_attr(config, "privacy_policy")
    if getattr(policy, "private_profile", False) or getattr(policy, "disable_cloud", False):
        return True
    return _public_base_url_override_present(env)


def _endpoint_suffix(endpoint: str) -> str:
    normalized_default = API_BASE_URL.rstrip("/")
    if endpoint.startswith(normalized_default):
        suffix = endpoint[len(normalized_default) :]
        return suffix or "/"
    parsed = urlsplit(endpoint)
    if parsed.scheme and parsed.netloc:
        suffix = parsed.path or "/"
        if parsed.query:
            suffix = f"{suffix}?{parsed.query}"
        return suffix
    if endpoint.startswith("/"):
        return endpoint
    return f"/{endpoint}"


def _rebase_endpoint(api_base_url: str, endpoint: str) -> str:
    return f"{api_base_url.rstrip('/')}{_endpoint_suffix(endpoint)}"


def build_platform_contract_surface(
    *,
    manifest: PlatformContractResponse,
    settings_obj: object | None = None,
    request_origin: str | None = None,
    env: Mapping[str, str] | None = None,
) -> PlatformContractResponse:
    config = settings_obj or get_settings()
    if not _should_rebase_surface_urls(config, env=env):
        return manifest

    api_base_url = resolve_api_public_base_url(
        settings_obj=config,
        request_origin=request_origin,
    )
    payload = manifest.model_dump(mode="python")
    payload["api_base_url"] = api_base_url
    payload["mcp_endpoint"] = _rebase_endpoint(api_base_url, manifest.mcp_endpoint)
    payload["mcp_tools_endpoint"] = _rebase_endpoint(api_base_url, manifest.mcp_tools_endpoint)
    return validate_platform_contract_payload(payload)
