#!/usr/bin/env python3
"""Provision (or update) a generic-OIDC principal → org/workspace mapping on a self-hosted gateway.

The Decision API's OIDC path fails closed: a verified OIDC token whose (issuer, subject) has no
`active` `oidc_principal_mappings` row gets 403 `principal_not_mapped` (unless auto-provision is
on). There is otherwise NO write path (no admin API, no other CLI), so this is how an operator
ONBOARDS an Okta/Auth0/Keycloak caller — a human user or a client-credentials (machine) client —
onto the gateway. Idempotent on (issuer, subject). Mirrors provision_entra_principal.py exactly,
keyed on (issuer, subject) instead of (tenant_id, oid) since a generic OIDC issuer URL already IS
the tenant/realm identity.

Runs against the gateway's own database (reads `settings.database_url`), like bootstrap_self_host.py —
so run it ON the deployed host / with the gateway's DATABASE_URL. Args are flags (no spaces), so it is
safe to invoke via `az containerapp exec --command "python scripts/provision_oidc_principal.py …"`.

Example:
  python scripts/provision_oidc_principal.py \
    --issuer https://idp.example.com/realms/acme \
    --subject 90b2e441-f049-41bf-b467-9ce85b36a24d \
    --org-slug self-hosted-org --role admin --type app --display-name "CI service account"
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Make `apps` importable when run as `python scripts/provision_oidc_principal.py` (only the script's
# own dir is on sys.path otherwise). Mirrors scripts/bootstrap_self_host.py.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apps.api_server.config import get_settings  # noqa: E402
from apps.api_server.models.oidc_principal import OidcPrincipalMapping  # noqa: E402
from apps.api_server.models.organization import Organization, OrgPlan, OrgStatus  # noqa: E402

settings = get_settings()
VALID_ROLES = ("owner", "admin", "member", "viewer")
VALID_TYPES = ("user", "app")
VALID_STATUS = ("active", "revoked")


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Provision a generic-OIDC principal → org mapping.")
    p.add_argument("--issuer", required=True, help="OIDC issuer (matches the token 'iss')")
    p.add_argument("--subject", required=True, help="principal subject (matches the token 'sub')")
    p.add_argument("--org-slug", default="self-hosted-org", help="org to map into (get-or-create)")
    p.add_argument("--role", default="admin", choices=VALID_ROLES)
    p.add_argument("--type", dest="ptype", default="user", choices=VALID_TYPES)
    p.add_argument("--status", default="active", choices=VALID_STATUS)
    p.add_argument("--display-name", default=None)
    p.add_argument("--email", default=None)
    return p.parse_args()


async def provision(session: AsyncSession, a: argparse.Namespace) -> OidcPrincipalMapping:
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
    # No trailing-slash normalization: verify_oidc_token's issuer check is an EXACT string
    # comparison against the raw ALGENTA_OIDC_ISSUER setting (never rstripped), so the mapping's
    # issuer column must match that raw configured value byte-for-byte or the resolver's lookup
    # will silently miss a genuinely valid, verified principal.
    issuer = a.issuer.strip()
    subject = a.subject.strip()
    existing = (
        await session.execute(
            select(OidcPrincipalMapping).where(
                OidcPrincipalMapping.issuer == issuer,
                OidcPrincipalMapping.subject == subject,
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
    mapping = OidcPrincipalMapping(
        issuer=issuer,
        subject=subject,
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
            f"OIDC_MAPPING_ID={m.id}\nOIDC_ISSUER={m.issuer}\nOIDC_SUBJECT={m.subject}\n"
            f"OIDC_ORG_ID={m.org_id}\nOIDC_ROLE={m.role}\nOIDC_TYPE={m.principal_type}\n"
            f"OIDC_STATUS={m.status}"
        )
    await engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
