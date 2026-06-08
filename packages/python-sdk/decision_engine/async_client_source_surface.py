from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .async_client_model_surface_common import _request_model
from .request_source_helpers import _normalize_source_registration_request

if TYPE_CHECKING:
    from .async_client_facade import AsyncDecisionEngineClient


async def register_source(
    client: AsyncDecisionEngineClient,
    source: dict[str, Any] | None = None,
    *,
    description: str | None = None,
    **kwargs: Any,
) -> Any:
    payload = _normalize_source_registration_request(
        source,
        description=description,
        extra=kwargs,
    )
    return await _request_model(
        client,
        "POST",
        "/v1/sources/register",
        "SourceRegistrationResult",
        json_body=payload,
    )


async def refresh_source(client: AsyncDecisionEngineClient, dataset_id: str) -> Any:
    return await _request_model(
        client,
        "POST",
        f"/v1/data/{dataset_id}/refresh",
        "SourceRegistrationResult",
    )


__all__ = ["refresh_source", "register_source"]
