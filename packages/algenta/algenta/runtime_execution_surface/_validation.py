"""contract + runtime API/contract payload validation helpers.

Extracted from packages/algenta/algenta/runtime_execution_surface.py during modularization.
"""
from __future__ import annotations

import asyncio
import re
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from functools import cache
from importlib import import_module
from typing import TYPE_CHECKING, Any

from algenta.runtime_errors import RuntimeConfigurationError, RuntimeValidationError
from algenta.runtime_model_common import coerce_payload_mapping

if TYPE_CHECKING:
    from types import ModuleType


@cache
def _runtime_api_exact_module() -> ModuleType:
    return import_module("algenta.runtime_api_exact")


@cache
def _runtime_api_payloads_module() -> ModuleType:
    return import_module("algenta.runtime_api_payloads")


@cache
def _runtime_intent_module() -> ModuleType:
    return import_module("algenta.runtime_intent")


@cache
def _runtime_local_limits_module() -> ModuleType:
    return import_module("algenta.runtime_local_limits")


@cache
def _runtime_local_query_module() -> ModuleType:
    return import_module("algenta.runtime_local_query")


@cache
def _runtime_local_resolve_module() -> ModuleType:
    return import_module("algenta.runtime_local_resolve")


@cache
def _runtime_model_query_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_query_output")


@cache
def _runtime_model_query_metadata_module() -> ModuleType:
    return import_module("algenta.runtime_model_query_metadata")


@cache
def _runtime_model_resolve_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_resolve_output")


@cache
def _runtime_model_verify_output_module() -> ModuleType:
    return import_module("algenta.runtime_model_verify_output")


@cache
def _runtime_model_decision_plan_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_plan")


@cache
def _runtime_model_decision_envelope_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_envelope")


@cache
def _runtime_model_decision_memory_module() -> ModuleType:
    return import_module("algenta.runtime_model_decision_memory")


@cache
def _runtime_model_repository_intelligence_module() -> ModuleType:
    return import_module("algenta.runtime_model_repository_intelligence")


@cache
def _runtime_model_products_module() -> ModuleType:
    return import_module("algenta.runtime_model_products")


@cache
def _runtime_model_llm_module() -> ModuleType:
    return import_module("algenta.runtime_model_llm")


@cache
def _runtime_model_agent_runs_module() -> ModuleType:
    return import_module("algenta.runtime_model_agent_runs")


@cache
def _runtime_model_account_module() -> ModuleType:
    return import_module("algenta.runtime_model_account")


@cache
def _runtime_model_deployments_module() -> ModuleType:
    return import_module("algenta.runtime_model_deployments")


@cache
def _runtime_model_control_plane_module() -> ModuleType:
    return import_module("algenta.runtime_model_control_plane")


from algenta.runtime_execution_surface._api_client_local import *  # noqa: F401, F403
from algenta.runtime_execution_surface._api_client_local import (
    _run_sync,
)


def contract_runtime_request(runtime: Any) -> Any:
    runtime._require_api_transport("get_contract")
    runtime_model_contract = import_module("algenta.runtime_model_contract")
    payload = _request_runtime_contract_payload(
        runtime,
        client_method_name="get_contract",
        runtime_error_code="invalid_contract_payload",
        message="get_contract() returned an invalid payload.",
        upstream_error_codes=("invalid_contract_payload", "contract_extension_missing"),
    )
    return _validate_contract_payload(
        "get_contract",
        payload,
        runtime_model_contract.PlatformContractOutput,
    )


def _validate_contract_payload(
    method_name: str,
    payload: Any,
    parser: Any,
) -> Any:
    try:
        return parser.from_api(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeValidationError(
            "invalid_contract_payload",
            f"{method_name}() returned an invalid payload.",
            _build_runtime_validation_error_details(exc),
        ) from exc


_RUNTIME_VALIDATION_ERROR_PREFIX = re.compile(
    r"^(?P<path>[A-Za-z0-9_.\[\]-]+)(?::|\s)(?P<message>.+)$"
)


def _build_runtime_validation_error_details(exc: Exception) -> dict[str, Any]:
    message = str(exc)
    match = _RUNTIME_VALIDATION_ERROR_PREFIX.match(message)
    if not match:
        return {"cause": message}
    path = match.group("path")
    detail = match.group("message").strip()
    if not path or not detail:
        return {"cause": message}
    return {
        "cause": path,
        "validation_errors": [
            {
                "path": path,
                "message": detail,
                "type": "value_error",
            }
        ],
    }


def _validate_runtime_proof_payload(
    method_name: str,
    payload: Any,
    parser: Any,
) -> Any:
    try:
        return parser.from_api(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeValidationError(
            "invalid_runtime_contract_payload",
            f"{method_name}() returned an invalid signed payload.",
            _build_runtime_validation_error_details(exc),
        ) from exc


def _validate_runtime_api_payload(
    method_name: str,
    payload: Any,
    parser: Any,
) -> Any:
    try:
        return parser.from_api(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeValidationError(
            "invalid_runtime_api_payload",
            f"{method_name}() returned an invalid payload.",
            _build_runtime_validation_error_details(exc),
        ) from exc


def _validate_runtime_api_mapping_payload(method_name: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise RuntimeValidationError(
            "invalid_runtime_api_payload",
            f"{method_name}() returned an invalid payload.",
            {"cause": "payload", "expected_type": "mapping", "actual_type": type(payload).__name__},
        )
    return dict(payload)


def _validate_runtime_api_structured_mapping_payload(
    method_name: str,
    payload: Any,
    parser: Any,
) -> dict[str, Any]:
    validated = _validate_runtime_api_payload(method_name, payload, parser)
    to_dict = getattr(validated, "to_dict", None)
    if callable(to_dict):
        normalized = to_dict()
        if isinstance(normalized, Mapping):
            return dict(normalized)
    if isinstance(validated, Mapping):
        return dict(validated)
    raise RuntimeValidationError(
        "invalid_runtime_api_payload",
        f"{method_name}() returned an invalid payload.",
        {"cause": "payload", "expected_type": "mapping", "actual_type": type(validated).__name__},
    )


def _validate_runtime_api_mapping_list_payload(
    method_name: str,
    payload: Any,
) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise RuntimeValidationError(
            "invalid_runtime_api_payload",
            f"{method_name}() returned an invalid payload.",
            {"cause": "payload", "expected_type": "list", "actual_type": type(payload).__name__},
        )
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(payload):
        if not isinstance(item, Mapping):
            raise RuntimeValidationError(
                "invalid_runtime_api_payload",
                f"{method_name}() returned an invalid payload.",
                {
                    "cause": f"payload[{index}]",
                    "expected_type": "mapping",
                    "actual_type": type(item).__name__,
                },
            )
        normalized.append(dict(item))
    return normalized


def _validate_runtime_api_stream(
    method_name: str,
    payloads: Any,
    parser: Any,
) -> Any:
    for payload in payloads:
        yield _validate_runtime_api_payload(method_name, payload, parser)


def _validate_runtime_api_payload_list(
    method_name: str,
    payload: Any,
    parser: Any,
) -> list[Any]:
    raw_items = payload
    if isinstance(payload, Mapping):
        raw_items = payload.get("api_keys", payload)
    if not isinstance(raw_items, list):
        raise RuntimeValidationError(
            "invalid_runtime_api_payload",
            f"{method_name}() returned an invalid payload.",
            {"cause": "payload", "expected_type": "list", "actual_type": type(raw_items).__name__},
        )
    return [_validate_runtime_api_payload(method_name, item, parser) for item in raw_items]


def _request_runtime_contract_payload(
    runtime: Any,
    *,
    client_method_name: str,
    runtime_error_code: str,
    message: str,
    upstream_error_codes: tuple[str, ...],
) -> Any:
    try:
        return getattr(runtime._client(), client_method_name)()
    except Exception as exc:
        upstream_error_code = getattr(exc, "error_code", None)
        if upstream_error_code not in upstream_error_codes:
            raise
        details = {
            "cause": str(exc),
            "source_error_code": upstream_error_code,
        }
        upstream_status_code = getattr(exc, "status_code", None)
        if isinstance(upstream_status_code, int):
            details["source_status_code"] = upstream_status_code
        source_error_details = getattr(exc, "details", None)
        if isinstance(source_error_details, dict):
            details["source_error_details"] = source_error_details
        else:
            response_body = getattr(exc, "response_body", None)
            if isinstance(response_body, dict):
                error_payload = response_body.get("error")
                if isinstance(error_payload, dict) and "details" in error_payload:
                    details["source_error_details"] = error_payload["details"]
        raise RuntimeValidationError(
            runtime_error_code,
            message,
            details,
        ) from exc


