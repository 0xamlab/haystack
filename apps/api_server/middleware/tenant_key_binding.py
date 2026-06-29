"""B10 PR11: API request hook that binds the authenticated org's keys for the request.

A FastAPI yield-dependency: resolve the org's keys from the store (by ``auth["org_id"]``), set the
tenant-key ContextVar, and reset it in ``finally`` so a pooled worker/async task never inherits
another request's keys. Added as a router-level dependency on the routers whose handlers resolve a
provider/engine key in-request (LLM + repositories). Worker / fire-and-forget runs set the override
separately from ``job.org_id`` (they execute outside any request context)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends

from apps.api_server.middleware.auth import get_current_org
from apps.api_server.services.auth_service import AuthContext
from apps.api_server.services.tenant_key_store import resolve_org_keys
from apps.api_server.services.tenant_keys import reset_org_keys_override, set_org_keys_override


async def bind_tenant_keys(
    auth: Annotated[AuthContext, Depends(get_current_org)],
) -> AsyncIterator[None]:
    # Per-device (offline-license) requests resolve provider keys from LOCAL config (the env /
    # self-host tier in tenant_keys), never the tenant_provider_keys table — the fix hot path stays
    # DB-free on a device gone dark.
    if auth.get("email") == "offline_license":
        yield
        return
    # resolve_org_keys reads on its own session, so a key-store error never poisons the request
    # session (the route handler's get_db session stays clean).
    token = set_org_keys_override(await resolve_org_keys(auth["org_id"]))
    try:
        yield
    finally:
        reset_org_keys_override(token)
