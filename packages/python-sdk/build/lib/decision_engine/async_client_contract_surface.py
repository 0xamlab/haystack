from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError as PydanticValidationError

from .async_client_model_surface_common import _request_model
from .contract_fallback import load_contract_from_openapi_async
from .exceptions import DecisionEngineError
from .exceptions import NotFoundError
from .validation_error_details import build_validation_error_details

if TYPE_CHECKING:
    from .async_client_facade import AsyncDecisionEngineClient


async def get_contract(client: AsyncDecisionEngineClient):
    try:
        return await _request_public_contract_model(
            client,
            "/v1/meta/contract",
            "PlatformContractResult",
            "get_contract",
        )
    except NotFoundError:
        return await load_contract_from_openapi_async(client)


async def _request_public_contract_model(
    client: AsyncDecisionEngineClient,
    path: str,
    model_name: str,
    method_name: str,
):
    try:
        return await _request_model(client, "GET", path, model_name)
    except (PydanticValidationError, TypeError, ValueError) as exc:
        raise DecisionEngineError(
            f"{method_name}() returned an invalid payload.",
            response_body={
                "error": {
                    "code": "invalid_contract_payload",
                    "details": build_validation_error_details(exc),
                }
            },
        ) from exc


async def _request_runtime_contract_model(
    client: AsyncDecisionEngineClient,
    path: str,
    model_name: str,
    method_name: str,
):
    try:
        return await _request_model(client, "GET", path, model_name)
    except (PydanticValidationError, TypeError, ValueError) as exc:
        raise DecisionEngineError(
            f"{method_name}() returned an invalid signed payload.",
            response_body={
                "error": {
                    "code": "invalid_runtime_contract_payload",
                    "details": build_validation_error_details(exc),
                }
            },
        ) from exc


async def get_runtime_manifest(client: AsyncDecisionEngineClient):
    return await _request_runtime_contract_model(
        client,
        "/v1/runtime/manifest",
        "RuntimeManifestResult",
        "get_runtime_manifest",
    )


async def get_runtime_modules(client: AsyncDecisionEngineClient):
    return await _request_runtime_contract_model(
        client,
        "/v1/admin/runtime/modules",
        "RuntimeAdminModulesResult",
        "get_runtime_modules",
    )


async def get_runtime_benchmarks(client: AsyncDecisionEngineClient):
    return await _request_runtime_contract_model(
        client,
        "/v1/admin/runtime/benchmarks",
        "RuntimeAdminBenchmarksResult",
        "get_runtime_benchmarks",
    )


async def get_runtime_release_validation(client: AsyncDecisionEngineClient):
    return await _request_runtime_contract_model(
        client,
        "/v1/admin/runtime/validation",
        "RuntimeReleaseValidationResult",
        "get_runtime_release_validation",
    )


__all__ = [
    "get_contract",
    "get_runtime_manifest",
    "get_runtime_modules",
    "get_runtime_benchmarks",
    "get_runtime_release_validation",
]
