"""
RBAC (Role-Based Access Control) enforcement — FastAPI dependency factory.

Role hierarchy (highest → lowest):
  owner  → admin  → member  → viewer

Usage in routers:
    from apps.api_server.middleware.rbac import require_role

    @router.post("/v1/team/invite")
    async def invite(
        auth: Annotated[AuthContext, Depends(require_role("admin"))],
        ...
    ):
        ...

Sensitive route policy:
  - invite/remove members → admin+
  - change member roles   → admin+
  - view audit logs       → admin+
  - revoke own API keys   → member+ (owner of key only)
  - billing checkout/portal → owner only
  - billing webhook       → no auth (Stripe HMAC)
  - simulate/recommend    → any authenticated key (no role check)
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request

from apps.api_server.error_payloads import access_scope_denied_error
from apps.api_server.middleware.auth import get_current_org
from apps.api_server.services.auth_service import AuthContext

logger = structlog.get_logger(__name__)

# Ordered from lowest to highest privilege
_ROLE_RANK: dict[str, int] = {
    "viewer": 0,
    "member": 1,
    "admin": 2,
    "owner": 3,
}


def _rank(role: str) -> int:
    """Return numeric rank for a role string. Unknown roles get viewer rank."""
    return _ROLE_RANK.get(role.lower(), 0)


def require_role(
    minimum_role: str,
) -> Callable[[Request, AuthContext], Awaitable[AuthContext]]:
    """
    Return a FastAPI dependency that enforces a minimum role.

    :param minimum_role: The lowest role allowed (inclusive).
                         Must be one of: viewer, member, admin, owner.
    :returns: A FastAPI Depends-compatible async callable.

    Example::

        require_role("admin")  # allows admin and owner
        require_role("owner")  # allows only owner
    """
    minimum_rank = _ROLE_RANK.get(minimum_role.lower())
    if minimum_rank is None:
        raise ValueError(f"Unknown role: {minimum_role!r}. Must be one of: {list(_ROLE_RANK)}")

    async def _dependency(
        request: Request,
        auth: Annotated[AuthContext, Depends(get_current_org)],
    ) -> AuthContext:
        actor_role = str(auth.get("role", "owner"))
        actor_rank = _rank(actor_role)

        if actor_rank < minimum_rank:
            logger.warning(
                "rbac_denied",
                org_id=str(auth["org_id"]),
                actor_role=actor_role,
                required_role=minimum_role,
                path=request.url.path,
                method=request.method,
            )
            raise HTTPException(
                status_code=403,
                detail=access_scope_denied_error(
                    (
                        f"This action requires the '{minimum_role}' role or higher. "
                        f"Your current role is '{actor_role}'."
                    ),
                    details=[{"field": "role", "issue": "insufficient_role"}],
                    extra={"required_role": minimum_role, "your_role": actor_role},
                ),
            )

        return auth

    # Give FastAPI a stable name for OpenAPI docs / dependency caching
    _dependency.__name__ = f"require_{minimum_role}_role"
    return _dependency


def forbid_service_key(auth: AuthContext, action: str = "this action") -> None:
    """Deny machine-to-machine SERVICE keys (e.g. the agent's engine-callback key) a privileged
    operation. Service keys are read/simulate-only; they must never perform external writes such as
    `/apply` (git push / open PR). Call this inside a handler whose authorization would otherwise
    rest only on connector visibility — the service-key read allowance must not become a write path.
    """
    if auth.get("is_service"):
        logger.warning("service_key_denied", action=action, org_id=str(auth.get("org_id")))
        raise HTTPException(
            status_code=403,
            detail=access_scope_denied_error(
                f"Service keys cannot perform {action}.",
                details=[{"field": "key", "issue": "service_key_not_permitted"}],
            ),
        )
