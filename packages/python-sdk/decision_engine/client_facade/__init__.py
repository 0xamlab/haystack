# SPDX-License-Identifier: Apache-2.0

"""
Synchronous Algenta API client.

Usage:
    import os

    from decision_engine import AlgentaClient

    api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
    if not api_key:
        raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

    client = AlgentaClient(api_key=api_key)
    result = client.simulate(
        mode="auto",
        scenario={
            "variables": {"revenue": {"low": 80000, "high": 200000}},
            "objective": "maximize_net_value",
        },
    )
    print(result.recommended_action, result.confidence)

This example is the Cloud Managed path. In `self_hosted` and `air_gapped`,
pass an explicit self-hosted `base_url` and use the API key provisioned by
your self-hosted operator deployment instead. Private profiles fail closed and
do not silently fall back to Algenta cloud.
"""

from __future__ import annotations

import importlib
import os
from functools import cache
from typing import TYPE_CHECKING, Any

from decision_engine.device_binding import (
    DEVICE_BINDING_TOKEN_HEADER,
    load_device_binding_token,
    store_device_binding_token,
)
from decision_engine.device_headers import DEVICE_ID_HEADER, build_device_headers
from decision_engine.lazy_http_client import LazySyncHttpClient
from decision_engine.privacy_profile import api_key_help_text, resolve_client_base_url
from decision_engine.sdk_defaults import DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT

if TYPE_CHECKING:
    from types import ModuleType

    import httpx

_httpx: Any | None = None
_SDK_USER_AGENT = "algenta-python/1.0.4"
_SDK_VERSION = "algenta-python/1.0.4"


def _get_httpx() -> Any:
    global _httpx
    if _httpx is None:
        _httpx = importlib.import_module("httpx")
    return _httpx


@cache
def _connector_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_connector_surface")


@cache
def _repository_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_repository_surface")


@cache
def _transport_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_transport")


@cache
def _response_module() -> ModuleType:
    return importlib.import_module("decision_engine.transport_response")


@cache
def _query_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_query_surface")


@cache
def _contract_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_contract_surface")


@cache
def _simulation_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_simulation_surface")


@cache
def _source_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_source_surface")


@cache
def _job_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_job_surface")


@cache
def _product_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_product_surface")


@cache
def _deployment_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_deployment_surface")


@cache
def _account_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_account_surface")


@cache
def _control_plane_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_control_plane_surface")


@cache
def _llm_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_llm_surface")


@cache
def _agent_run_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_agent_run_surface")


@cache
def _decision_plan_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_decision_plan_surface")


@cache
def _decision_memory_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_decision_memory_surface")


@cache
def _trigger_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_trigger_surface")


@cache
def _capability_plane_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.client_capability_plane_surface")

from decision_engine.client_facade._mixin_account_control_plane import (  # noqa: E402
    _AccountControlPlaneMixin,
)
from decision_engine.client_facade._mixin_agent_run import _AgentRunMixin  # noqa: E402
from decision_engine.client_facade._mixin_connector_repository import (  # noqa: E402
    _ConnectorRepositoryMixin,
)
from decision_engine.client_facade._mixin_contract_capability import (  # noqa: E402
    _ContractCapabilityMixin,
)
from decision_engine.client_facade._mixin_job_deployment import _JobDeploymentMixin  # noqa: E402
from decision_engine.client_facade._mixin_llm import _LLMMixin  # noqa: E402
from decision_engine.client_facade._mixin_product_decision import (  # noqa: E402
    _ProductDecisionMixin,
)
from decision_engine.client_facade._mixin_simulation_query import (  # noqa: E402
    _SimulationQueryMixin,
)
from decision_engine.client_facade._mixin_trigger_source import _TriggerSourceMixin  # noqa: E402


class DecisionEngineClient(
    _SimulationQueryMixin,
    _ProductDecisionMixin,
    _TriggerSourceMixin,
    _LLMMixin,
    _ContractCapabilityMixin,
    _AgentRunMixin,
    _ConnectorRepositoryMixin,
    _JobDeploymentMixin,
    _AccountControlPlaneMixin,
):
    """
    Synchronous HTTP client for the Algenta API.

    `AlgentaClient` is the preferred public alias.
    `DecisionEngineClient` remains available for backward compatibility.

    Args:
        api_key: Your API key. Prefer `ALGENTA_API_KEY`; legacy `DE_API_KEY`
            remains accepted for compatibility.
                 Falls back to ALGENTA_API_KEY or DE_API_KEY environment variable.
        base_url: API base URL. Override for self-hosted deployments.
        timeout: Request timeout in seconds.
        max_retries: Maximum retries on 429 and 5xx responses.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        resolved_base_url = resolve_client_base_url(
            explicit_base_url=base_url,
            component="DecisionEngineClient",
        )
        resolved_key = (
            api_key or os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
        )
        if not resolved_key:
            raise ValueError(
                "API key required. Pass api_key= or set ALGENTA_API_KEY / DE_API_KEY "
                "environment variables.\n"
                + api_key_help_text(
                    component="DecisionEngineClient",
                    fallback_base_url=resolved_base_url,
                )
            )
        self._api_key = resolved_key
        self._base_url = resolved_base_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = LazySyncHttpClient(self._build_http_client)

    def _build_http_client(self) -> Any:
        httpx = _get_httpx()
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": _SDK_USER_AGENT,
        }
        headers.update(
            build_device_headers(
                sdk_version=_SDK_VERSION,
                user_agent=_SDK_USER_AGENT,
            )
        )
        device_id = headers.get(DEVICE_ID_HEADER, "").strip()
        if device_id:
            binding_token = load_device_binding_token(
                base_url=self._base_url,
                api_key=self._api_key,
                device_id=device_id,
            )
            if binding_token:
                headers[DEVICE_BINDING_TOKEN_HEADER] = binding_token
        return httpx.Client(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
        )

    def _get_httpx_module(self) -> Any:
        return _get_httpx()

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        return _transport_module().request_with_retries(self, method, path, **kwargs)

    def _request_response(self, method: str, path: str, **kwargs: Any) -> tuple[Any, Any]:
        return _transport_module().request_with_retries_and_response(self, method, path, **kwargs)

    def _handle_response(self, response: httpx.Response) -> Any:
        return _response_module().handle_response(
            response,
            auth_message="Authentication failed",
        )

    def _store_device_binding_token(self, response: Any) -> None:
        binding_token = str(response.headers.get(DEVICE_BINDING_TOKEN_HEADER, "")).strip()
        if not binding_token:
            return
        device_id = str(self._client.headers.get(DEVICE_ID_HEADER, "")).strip()
        if not device_id:
            return
        store_device_binding_token(
            base_url=self._base_url,
            api_key=self._api_key,
            device_id=device_id,
            binding_token=binding_token,
        )
        self._client.headers[DEVICE_BINDING_TOKEN_HEADER] = binding_token

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> DecisionEngineClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


class AlgentaClient(DecisionEngineClient):
    """Preferred public sync client name for the Algenta API."""


# Backward-compatible alias for integrations that used the former client name.
CodnaClient = AlgentaClient
