#!/usr/bin/env python
"""Break-glass operator tooling: suspend / unsuspend / delete a user or org (Wave 2).

Cross-tenant account control needs OPERATOR authority, not a tenant org-admin, and a public admin
endpoint would be attack surface — so this is a CLI run with infra (DB + Redis) access, not an API.
It sets the UserStatus / OrgStatus that the auth gate enforces (get_current_org →
_enforce_account_status) and busts the auth cache so the change takes effect immediately rather than
after the auth cache TTL.

    python scripts/admin_account_control.py --target org  --id <uuid|slug>   --action suspend
    python scripts/admin_account_control.py --target org  --id <uuid|slug>   --action delete
    python scripts/admin_account_control.py --target user --id <uuid|email>  --action unsuspend

Users support suspend/unsuspend (there is no DELETED user status — suspend is the shutdown, and it
preserves the audit trail). Orgs also support delete (a soft DELETED status; data is retained).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import structlog
from sqlalchemy import select

from apps.api_server.config import get_settings
from apps.api_server.models.organization import Organization, OrgStatus
from apps.api_server.models.user import User, UserStatus
from apps.api_server.services.auth_service import (
    invalidate_org_api_key_caches,
    invalidate_user_api_key_caches,
)

logger = structlog.get_logger(__name__)

_USER_ACTIONS = {"suspend": UserStatus.SUSPENDED, "unsuspend": UserStatus.ACTIVE}
_ORG_ACTIONS = {
    "suspend": OrgStatus.SUSPENDED,
    "unsuspend": OrgStatus.ACTIVE,
    "delete": OrgStatus.DELETED,
}


def _maybe_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except (ValueError, AttributeError):
        return None


async def apply_account_action(
    session: object, redis_client: object, *, target: str, identifier: str, action: str
) -> dict:
    """Apply a status change to a user or org + bust its auth cache. Returns a result summary.

    Raises ValueError on an unknown target/action or a not-found subject. Commits the status change,
    then busts the relevant key caches (best-effort) so the auth gate sees it immediately.
    """
    as_uuid = _maybe_uuid(identifier)
    if target == "user":
        if action not in _USER_ACTIONS:
            raise ValueError(f"user supports {sorted(_USER_ACTIONS)} (not {action!r})")
        clause = User.id == as_uuid if as_uuid else User.email == identifier
        user = (await session.execute(select(User).where(clause))).scalar_one_or_none()  # type: ignore[attr-defined]
        if user is None:
            raise ValueError(f"user not found: {identifier}")
        user.status = _USER_ACTIONS[action]
        await session.commit()  # type: ignore[attr-defined]
        busted = await invalidate_user_api_key_caches(session, user.id, redis_client)
        logger.warning(
            "admin_account_action", target="user", action=action, user_id=str(user.id),
            email=user.email, status=user.status.value, keys_invalidated=busted,
        )
        return {"target": "user", "id": str(user.id), "email": user.email,
                "status": user.status.value, "keys_invalidated": busted}

    if target == "org":
        if action not in _ORG_ACTIONS:
            raise ValueError(f"org supports {sorted(_ORG_ACTIONS)} (not {action!r})")
        clause = Organization.id == as_uuid if as_uuid else Organization.slug == identifier
        org = (await session.execute(select(Organization).where(clause))).scalar_one_or_none()  # type: ignore[attr-defined]
        if org is None:
            raise ValueError(f"org not found: {identifier}")
        org.status = _ORG_ACTIONS[action]
        await session.commit()  # type: ignore[attr-defined]
        busted = await invalidate_org_api_key_caches(session, org.id, redis_client)
        logger.warning(
            "admin_account_action", target="org", action=action, org_id=str(org.id),
            slug=org.slug, status=org.status.value, keys_invalidated=busted,
        )
        return {"target": "org", "id": str(org.id), "slug": org.slug,
                "status": org.status.value, "keys_invalidated": busted}

    raise ValueError(f"unknown target: {target!r}")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Operator suspend/unsuspend/delete for a user or org.")
    p.add_argument("--target", required=True, choices=["user", "org"])
    p.add_argument("--id", required=True, help="user uuid/email, or org uuid/slug")
    p.add_argument("--action", required=True, choices=["suspend", "unsuspend", "delete"])
    p.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    return p.parse_args(argv)


async def _amain(args: argparse.Namespace) -> int:
    settings = get_settings()
    if not args.yes:
        confirm = input(f"{args.action} {args.target} {args.id!r}? [y/N] ").strip().lower()
        if confirm != "y":
            print("aborted")
            return 1
    import redis.asyncio as aioredis  # noqa: PLC0415

    from apps.api_server.db.session import AsyncSessionLocal  # noqa: PLC0415

    redis_client = aioredis.from_url(settings.redis_url)
    try:
        async with AsyncSessionLocal() as session:
            await apply_account_action(
                session, redis_client, target=args.target, identifier=args.id, action=args.action
            )
        # Print only from the CLI args — never the ORM-derived result, which CodeQL taints back
        # through the User row's password_hash column (clear-text logging of sensitive data). The
        # full detail (status, busted-cache count) is in the structured audit log inside the action.
        print(f"OK: {args.action} {args.target} {args.id!r} complete")
        return 0
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    finally:
        close = getattr(redis_client, "aclose", None) or getattr(redis_client, "close", None)
        if close:
            await close()


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_amain(_parse_args(argv)))


if __name__ == "__main__":
    raise SystemExit(main())
