# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .client_model_surface_common import _request_model

if TYPE_CHECKING:
    from .client_facade import DecisionEngineClient


def plan_decision(
    client: DecisionEngineClient,
    request: dict[str, Any],
) -> Any:
    return _request_model(
        client,
        "POST",
        "/v1/decisions/plan",
        "DecisionPlanResult",
        json_body=request,
    )


__all__ = ["plan_decision"]
