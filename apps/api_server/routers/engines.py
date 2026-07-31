"""
routers/engines.py — Algenta OS engine catalogue + dispatch endpoints.

GET  /v1/engines              — list all engines (manifest)
GET  /v1/engines/{slug}       — single engine detail
GET  /v1/engines/tiers        — engines grouped by tier

All three require a key. They were reachable unauthenticated only because this file had no
``Depends`` at all — an omission, not a decision: FastAPI derives OpenAPI security from a route's
dependencies, so the published spec advertised them as open. Nothing pre-auth consumes them (no SDK
method, MCP tool, healthcheck, installer or CI probe; the two in-repo callers send a key, and the
catalogue is not advertised in ``/v1/meta/contract``), while the payload is internal build detail —
per-engine ``mojo_libs`` names and, on ``/tiers``, the commercial packaging map. ``/{slug}`` is gated
with them or the gate is bypassed by enumerating the twelve slugs ``/v1/engines`` already listed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from apps.api_server.middleware.auth import AuthContext, get_current_org
from apps.api_server.pagination import paginate_sequence

# Allow running from project root without install
_root = Path(__file__).resolve().parents[3]
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from engines.manifest import ENGINES, ENGINES_BY_SLUG, ENGINES_BY_TIER  # noqa: E402

router = APIRouter(prefix="/v1/engines", tags=["Engines"])


# ── Response models ─────────────────────────────────────────────────────────


class EngineResponse(BaseModel):
    name: str
    slug: str
    description: str
    api_path: str
    mojo_libs: list[str]
    use_cases: list[str]
    tier: str


class EngineListResponse(BaseModel):
    count: int
    total: int
    page: int
    limit: int
    pages: int
    engines: list[EngineResponse]


class EngineTierResponse(BaseModel):
    core: list[EngineResponse]
    advanced: list[EngineResponse]
    platform: list[EngineResponse]


# ── Routes ──────────────────────────────────────────────────────────────────


@router.get("", response_model=EngineListResponse, summary="List all engines")
def list_engines(
    _auth: Annotated[AuthContext, Depends(get_current_org)],
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=200),
) -> EngineListResponse:
    """Return the full Algenta OS engine catalogue."""
    del _auth
    engine_rows = [EngineResponse(**e.__dict__) for e in ENGINES]
    envelope = paginate_sequence(engine_rows, page=page, limit=limit)
    return EngineListResponse(
        count=len(envelope.items),
        total=envelope.total,
        page=envelope.page,
        limit=envelope.limit,
        pages=envelope.pages,
        engines=envelope.items,
    )


@router.get("/tiers", response_model=EngineTierResponse, summary="Engines by tier")
def engines_by_tier(
    _auth: Annotated[AuthContext, Depends(get_current_org)],
) -> EngineTierResponse:
    """Return engines grouped by tier: core / advanced / platform."""
    del _auth

    def _tier(slug: str) -> list[EngineResponse]:
        return [EngineResponse(**e.__dict__) for e in ENGINES_BY_TIER.get(slug, [])]

    return EngineTierResponse(
        core=_tier("core"),
        advanced=_tier("advanced"),
        platform=_tier("platform"),
    )


@router.get("/{slug}", response_model=EngineResponse, summary="Engine detail")
def get_engine(
    slug: str,
    _auth: Annotated[AuthContext, Depends(get_current_org)],
) -> EngineResponse:
    """Return detail for a single engine by slug."""
    del _auth
    engine = ENGINES_BY_SLUG.get(slug)
    if engine is None:
        raise HTTPException(
            status_code=404,
            detail=f"Engine '{slug}' not found. Valid slugs: {sorted(ENGINES_BY_SLUG)}",
        )
    return EngineResponse(**engine.__dict__)
