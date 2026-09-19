# SPDX-License-Identifier: Apache-2.0

"""
Async Algenta API client for use with asyncio.

Usage:
    import asyncio
    import os
    from decision_engine import AsyncAlgentaClient

    async def main():
        api_key = os.environ.get("ALGENTA_API_KEY") or os.environ.get("DE_API_KEY")
        if not api_key:
            raise RuntimeError("Set ALGENTA_API_KEY or DE_API_KEY before running this example.")

        async with AsyncAlgentaClient(api_key=api_key) as client:
            result = await client.simulate(
                mode="auto",
                scenario={
                    "variables": {"revenue": {"low": 80000, "high": 200000}},
                    "objective": "maximize_net_value",
                },
            )
            print(result.recommended_action)

    asyncio.run(main())

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
from decision_engine.lazy_http_client import LazyAsyncHttpClient
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
    return importlib.import_module("decision_engine.async_client_connector_surface")


@cache
def _repository_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_repository_surface")


@cache
def _transport_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_transport")


@cache
def _response_module() -> ModuleType:
    return importlib.import_module("decision_engine.transport_response")


@cache
def _query_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_query_surface")


@cache
def _contract_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_contract_surface")


@cache
def _simulation_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_simulation_surface")


@cache
def _source_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_source_surface")


@cache
def _job_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_job_surface")


@cache
def _product_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_product_surface")


@cache
def _deployment_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_deployment_surface")


@cache
def _account_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_account_surface")


@cache
def _control_plane_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_control_plane_surface")


@cache
def _llm_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_llm_surface")


@cache
def _agent_run_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_agent_run_surface")


@cache
def _decision_plan_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_decision_plan_surface")


@cache
def _decision_memory_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_decision_memory_surface")


@cache
def _trigger_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_trigger_surface")


@cache
def _capability_plane_surface_module() -> ModuleType:
    return importlib.import_module("decision_engine.async_client_capability_plane_surface")



from decision_engine.async_client_facade._mixin_account_control_plane import (  # noqa: E402
    _AsyncAccountControlPlaneMixin,
)
from decision_engine.async_client_facade._mixin_agent_run import _AsyncAgentRunMixin  # noqa: E402
from decision_engine.async_client_facade._mixin_connector_repository import (  # noqa: E402
    _AsyncConnectorRepositoryMixin,
)
from decision_engine.async_client_facade._mixin_contract_capability import (  # noqa: E402
    _AsyncContractCapabilityMixin,
)
from decision_engine.async_client_facade._mixin_job_deployment import (  # noqa: E402
    _AsyncJobDeploymentMixin,
)
from decision_engine.async_client_facade._mixin_llm import _AsyncLLMMixin  # noqa: E402
from decision_engine.async_client_facade._mixin_product_decision import (  # noqa: E402
    _AsyncProductDecisionMixin,
)
from decision_engine.async_client_facade._mixin_simulation_query import (  # noqa: E402
    _AsyncSimulationQueryMixin,
)
from decision_engine.async_client_facade._mixin_trigger_source import (  # noqa: E402
    _AsyncTriggerSourceMixin,
)


class AsyncDecisionEngineClient(
    _AsyncSimulationQueryMixin,
    _AsyncProductDecisionMixin,
    _AsyncTriggerSourceMixin,
    _AsyncLLMMixin,
    _AsyncContractCapabilityMixin,
    _AsyncAgentRunMixin,
    _AsyncConnectorRepositoryMixin,
    _AsyncJobDeploymentMixin,
    _AsyncAccountControlPlaneMixin,
):
    """
    Async HTTP client for the Algenta API.

    `AsyncAlgentaClient` is the preferred public alias.
    `AsyncDecisionEngineClient` remains available for backward compatibility.
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
            component="AsyncDecisionEngineClient",
        )
        resolved_key = (
            api_key or os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
        )
        if not resolved_key:
            raise ValueError(
                "API key required. Pass api_key= or set ALGENTA_API_KEY / DE_API_KEY "
                "environment variables.\n"
                + api_key_help_text(
                    component="AsyncDecisionEngineClient",
                    fallback_base_url=resolved_base_url,
                )
            )
        self._api_key = resolved_key
        self._base_url = resolved_base_url
        self._timeout = timeout
        self._max_retries = max_retries
        self._client = LazyAsyncHttpClient(self._build_http_client)

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
        return httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout,
        )

    def _get_httpx_module(self) -> Any:
        return _get_httpx()

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        return await _transport_module().request_with_retries(self, method, path, **kwargs)

    async def _request_response(self, method: str, path: str, **kwargs: Any) -> tuple[Any, Any]:
        return await _transport_module().request_with_retries_and_response(
            self,
            method,
            path,
            **kwargs,
        )

    def _handle_response(self, response: httpx.Response) -> Any:
        return _response_module().handle_response(response, auth_message="Auth failed")

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

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> AsyncDecisionEngineClient:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.aclose()


class AsyncAlgentaClient(AsyncDecisionEngineClient):
    """Preferred public async client name for the Algenta API."""


AsyncCodnaClient = AsyncAlgentaClient  # back-compat alias
