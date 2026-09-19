# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import ValidationError as PydanticValidationError

from .client_model_surface_common import _request_model
from .contract_fallback import load_contract_from_openapi
from .exceptions import DecisionEngineError, NotFoundError
from .validation_error_details import build_validation_error_details

if TYPE_CHECKING:
    from .client_facade import DecisionEngineClient


def get_contract(client: DecisionEngineClient):
    try:
        return _request_public_contract_model(
            client,
            "/v1/meta/contract",
            "PlatformContractResult",
            "get_contract",
        )
    except NotFoundError:
        return load_contract_from_openapi(client)


def _request_public_contract_model(
    client: DecisionEngineClient,
    path: str,
    model_name: str,
    method_name: str,
):
    try:
        return _request_model(client, "GET", path, model_name)
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


def _request_runtime_contract_model(
    client: DecisionEngineClient,
    path: str,
    model_name: str,
    method_name: str,
):
    try:
        return _request_model(client, "GET", path, model_name)
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


def get_runtime_manifest(client: DecisionEngineClient):
    return _request_runtime_contract_model(
        client,
        "/v1/runtime/manifest",
        "RuntimeManifestResult",
        "get_runtime_manifest",
    )


def get_runtime_modules(client: DecisionEngineClient):
    return _request_runtime_contract_model(
        client,
        "/v1/admin/runtime/modules",
        "RuntimeAdminModulesResult",
        "get_runtime_modules",
    )


def get_runtime_benchmarks(client: DecisionEngineClient):
    return _request_runtime_contract_model(
        client,
        "/v1/admin/runtime/benchmarks",
        "RuntimeAdminBenchmarksResult",
        "get_runtime_benchmarks",
    )


def get_runtime_release_validation(client: DecisionEngineClient):
    return _request_runtime_contract_model(
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
