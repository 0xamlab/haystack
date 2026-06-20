"""/v1/control-plane — control-plane role marker (P4).

A tiny, dependency-free surface so callers / healthchecks can confirm they reached the hosted
control plane (not the full engine app). Mounted on the control-plane app; harmless elsewhere.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["control-plane"])


@router.get(
    "/v1/control-plane/meta",
    include_in_schema=False,
    summary="Control-plane role marker",
)
async def control_plane_meta() -> dict[str, str]:
    return {"role": "control_plane", "surface": "control-plane"}
