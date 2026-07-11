#!/usr/bin/env python3
"""Provision (or update) an Entra principal → org/workspace mapping on a self-hosted gateway.

The Decision API's Entra path fails closed: a verified Entra token whose (tenant_id, oid) has no
`active` `entra_principal_mappings` row gets 403 `principal_not_mapped`. There is otherwise NO write
path (no admin API, no other CLI), so this is how an operator ONBOARDS an Entra caller — an employee
(user) or a Foundry / managed-identity (app) — onto the gateway. Idempotent on (tenant_id, oid).

Runs against the gateway's own database (reads `settings.database_url`), like bootstrap_self_host.py —
so run it ON the deployed host / with the gateway's DATABASE_URL. Args are flags (no spaces), so it is
safe to invoke via `az containerapp exec --command "python scripts/provision_entra_principal.py …"`.

Example:
  python scripts/provision_entra_principal.py \
    --tenant 7a0cd533-4d98-450c-bc3a-93cee1495e06 \
    --oid 93b8fe59-80a2-4902-8cf4-573429c0d8d3 \
    --org-slug self-hosted-org --role admin --type app --display-name "Foundry agent"
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Make `apps` importable when run as `python scripts/provision_entra_principal.py` (only the script's
# own dir is on sys.path otherwise). Mirrors scripts/bootstrap_self_host.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apps.api_server.config import get_settings  # noqa: E402
from apps.api_server.models.entra_principal import EntraPrincipalMapping  # noqa: E402
from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus  # noqa: E402

settings = get_settings()
VALID_ROLES = ("owner", "admin", "member", "viewer")
VALID_TYPES = ("user", "app")
VALID_STATUS = ("active", "revoked")


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Provision an Entra principal → org mapping.")
    p.add_argument("--tenant", required=True, help="Entra tenant id (matches the token 'tid')")
    p.add_argument("--oid", required=True, help="principal object id (matches the token 'oid')")
    p.add_argument("--org-slug", default="self-hosted-org", help="org to map into (get-or-create)")
    p.add_argument("--role", default="admin", choices=VALID_ROLES)
    p.add_argument("--type", dest="ptype", default="user", choices=VALID_TYPES)
    p.add_argument("--status", default="active", choices=VALID_STATUS)
    p.add_argument("--display-name", default=None)
    p.add_argument("--email", default=None)
    return p.parse_args()


async def provision(session: AsyncSession, a: argparse.Namespace) -> EntraPrincipalMapping:
    org = (
        await session.execute(select(Organization).where(Organization.slug == a.org_slug))
    ).scalar_one_or_none()
    if org is None:
        org = Organization(
            name=a.org_slug.replace("-", " ").title(),
            slug=a.org_slug,
            plan=OrgPlan.FREE,
            status=OrgStatus.ACTIVE,
        )
        session.add(org)
        await session.flush()
    tid = a.tenant.strip().lower()
    oid = a.oid.strip()
    existing = (
        await session.execute(
            select(EntraPrincipalMapping).where(
                EntraPrincipalMapping.tenant_id == tid,
                EntraPrincipalMapping.principal_oid == oid,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        existing.org_id = org.id
        existing.role = a.role
        existing.principal_type = a.ptype
        existing.status = a.status
        if a.display_name:
            existing.display_name = a.display_name
        if a.email:
            existing.email = a.email
        return existing
    mapping = EntraPrincipalMapping(
        tenant_id=tid,
        principal_oid=oid,
        principal_type=a.ptype,
        role=a.role,
        status=a.status,
        org_id=org.id,
        display_name=a.display_name,
        email=a.email,
    )
    session.add(mapping)
    await session.flush()
    return mapping


async def _main() -> int:
    a = _args()
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        m = await provision(session, a)
        await session.commit()
        print(
            f"ENTRA_MAPPING_ID={m.id}\nENTRA_TENANT={m.tenant_id}\nENTRA_OID={m.principal_oid}\n"
            f"ENTRA_ORG_ID={m.org_id}\nENTRA_ROLE={m.role}\nENTRA_TYPE={m.principal_type}\n"
            f"ENTRA_STATUS={m.status}"
        )
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
