# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .client_model_surface_common import _request_model
from .model_loader import validate_model as _validate_model
from .query_metadata_helpers import (
    build_query_execution_metadata,
    response_headers_dict,
)
from .request_explain_helpers import _build_explain_result
from .request_query_helpers import _merge_request_payload

if TYPE_CHECKING:
    from .client_facade import DecisionEngineClient


def resolve(
    client: DecisionEngineClient,
    request: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/resolve",
        "ResolveResult",
        json_body=_merge_request_payload(request, kwargs),
    )


def query(
    client: DecisionEngineClient,
    request: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/query",
        "QueryResult",
        json_body=_merge_request_payload(request, kwargs),
    )


def query_with_metadata(
    client: DecisionEngineClient,
    request: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    merged_request = _merge_request_payload(request, kwargs)
    body, response = client._request_response("POST", "/v1/query", json=merged_request)
    return _validate_model(
        "QueryWithMetadataResult",
        {
            "data": body,
            "metadata": build_query_execution_metadata(body, response),
            "headers": response_headers_dict(response),
        },
    )


def query_batch(
    client: DecisionEngineClient,
    request: dict[str, Any],
) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/query/batch",
        "QueryBatchResult",
        json_body=request,
    )


def query_sql_report(
    client: DecisionEngineClient,
    request: dict[str, Any],
) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/query/sql-report",
        "QuerySqlReportResult",
        json_body=request,
    )


def verify(
    client: DecisionEngineClient,
    request: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/verify",
        "VerifyResult",
        json_body=_merge_request_payload(request, kwargs),
    )


def explain(
    client: DecisionEngineClient,
    request: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Any:
    merged_request = _merge_request_payload(request, kwargs)
    result = query(client, merged_request)
    return _build_explain_result(merged_request, result)


__all__ = [
    "explain",
    "query",
    "query_batch",
    "query_sql_report",
    "query_with_metadata",
    "resolve",
    "verify",
]
