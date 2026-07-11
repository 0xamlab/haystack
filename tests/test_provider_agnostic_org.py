"""Provider-agnostic identity → org resolution.

A verified Supabase JWT resolves to ONE engine org keyed on the stable top-level `sub`, so GitHub /
Google / Apple / Microsoft logins for the same account converge. Existing GitHub users keep their
`gh-user-{id}` org (adopted into an `identity_org_links` row on first agnostic resolve); brand-new
non-GitHub users get an `sb-user-{uid}` org only when `auto_provision` is on (dark by default).
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from apps.api_server.db.session import AsyncSessionLocal
from apps.api_server.models.identity_org_link import IdentityOrgLink
from apps.api_server.models.organization import Organization
from apps.api_server.services import byok_org_resolver, supabase_auth
from apps.api_server.services.github_app_provisioning import (
    provision_or_lookup_org_for_installation,
    provision_org_for_supabase_uid,
)


# ── extract_identity: provider-agnostic, never raises on non-github ─────────────────
def test_extract_identity_google() -> None:
    ident = supabase_auth.extract_identity(
        {
            "sub": "sb-uuid-google-1",
            "email": "a@gmail.com",
            "app_metadata": {"provider": "google", "providers": ["google"]},
            "user_metadata": {},
        }
    )
    assert ident["supabase_uid"] == "sb-uuid-google-1"
    assert ident["email"] == "a@gmail.com"
    assert ident["provider"] == "google"
    assert ident["github_user_id"] is None
    assert ident["github_login"] is None


def test_extract_identity_github_populates_github_fields() -> None:
    ident = supabase_auth.extract_identity(
        {
            "sub": "sb-uuid-gh-2",
            "email": "o@example.com",
            "app_metadata": {"provider": "github", "providers": ["github"]},
            "user_metadata": {"provider_id": "583231", "user_name": "Octocat"},
        }
    )
    assert ident["supabase_uid"] == "sb-uuid-gh-2"
    assert ident["github_user_id"] == 583231
    assert ident["github_login"] == "octocat"
    assert ident["provider"] == "github"


def test_extract_identity_apple_hidden_email() -> None:
    ident = supabase_auth.extract_identity(
        {
            "sub": "sb-uuid-apple-3",
            "app_metadata": {"provider": "apple", "providers": ["apple"]},
            "user_metadata": {},
        }
    )
    assert ident["supabase_uid"] == "sb-uuid-apple-3"
    assert ident["email"] is None
    assert ident["github_user_id"] is None


def test_extract_identity_requires_sub() -> None:
    with pytest.raises(supabase_auth.SupabaseAuthError):
        supabase_auth.extract_identity({"sub": "", "app_metadata": {}})


# ── provision_org_for_supabase_uid: create + idempotent + hidden-email fallback ─────
@pytest.mark.anyio
async def test_provision_supabase_org_creates_and_is_idempotent() -> None:
    uid = f"sb-{uuid.uuid4().hex}"
    async with AsyncSessionLocal() as s:
        org1 = await provision_org_for_supabase_uid(s, supabase_uid=uid, email="x@gmail.com")
        await s.commit()
        id1 = org1.id
    assert org1.slug == f"sb-user-{uid}"
    async with AsyncSessionLocal() as s:
        org2 = await provision_org_for_supabase_uid(s, supabase_uid=uid, email="x@gmail.com")
        await s.commit()
    assert org2.id == id1  # idempotent by uid slug


@pytest.mark.anyio
async def test_provision_supabase_org_hidden_email_uses_noreply_owner() -> None:
    uid = f"sb-{uuid.uuid4().hex}"
    async with AsyncSessionLocal() as s:
        org = await provision_org_for_supabase_uid(s, supabase_uid=uid, email=None)  # Apple hidden
        await s.commit()
        from apps.api_server.models.user import User

        owner = (
            await s.execute(select(User).where(User.org_id == org.id))
        ).scalar_one()
    assert owner.email == f"{uid}@users.noreply.thyn.ai"
    assert owner.email_verified is False


# ── resolver: non-github link / auto_provision / no_org ─────────────────────────────
@pytest.mark.anyio
async def test_resolve_non_github_no_link_no_autoprovision_raises() -> None:
    with pytest.raises(byok_org_resolver.OrgResolutionError) as exc:
        async with AsyncSessionLocal() as s:
            await byok_org_resolver.resolve_org_for_supabase_user(
                s, supabase_uid=f"sb-{uuid.uuid4().hex}", email="n@gmail.com", auto_provision=False
            )
    assert exc.value.code == "no_org"
    assert exc.value.http_status == 403


@pytest.mark.anyio
async def test_resolve_non_github_autoprovision_creates_then_links() -> None:
    uid = f"sb-{uuid.uuid4().hex}"
    async with AsyncSessionLocal() as s:
        org = await byok_org_resolver.resolve_org_for_supabase_user(
            s, supabase_uid=uid, email="g@gmail.com", auto_provision=True
        )
        await s.commit()
        org_id = org.id
        link = (
            await s.execute(select(IdentityOrgLink).where(IdentityOrgLink.supabase_uid == uid))
        ).scalar_one()
    assert link.org_id == org_id
    # Second resolve (even auto_provision off) returns the SAME org via the link.
    async with AsyncSessionLocal() as s:
        again = await byok_org_resolver.resolve_org_for_supabase_user(
            s, supabase_uid=uid, email="g@gmail.com", auto_provision=False
        )
    assert again.id == org_id


# ── adopt-legacy: a GitHub user's gh-user org is adopted; a later non-github login on
#    the SAME Supabase account resolves to that SAME org ──────────────────────────────
@pytest.mark.anyio
async def test_github_org_adopted_then_other_provider_resolves_same_org() -> None:
    gh_id = 900000 + uuid.uuid4().int % 90000
    uid = f"sb-{uuid.uuid4().hex}"
    # A prior GitHub App install minted the gh-user-{id} org.
    async with AsyncSessionLocal() as s:
        gh_org = await provision_or_lookup_org_for_installation(
            s, account_id=gh_id, account_login="octo", account_type="user"
        )
        await s.commit()
        gh_org_id = gh_org.id
    # First agnostic resolve as the GitHub identity → returns gh-user org + creates the uid link.
    async with AsyncSessionLocal() as s:
        resolved = await byok_org_resolver.resolve_org_for_supabase_user(
            s, supabase_uid=uid, email="o@example.com", github_user_id=gh_id, github_login="octo"
        )
        await s.commit()
        assert resolved.id == gh_org_id
        link = (
            await s.execute(select(IdentityOrgLink).where(IdentityOrgLink.supabase_uid == uid))
        ).scalar_one()
        assert link.org_id == gh_org_id  # adopted, not duplicated
    # Later login on the SAME Supabase account via a NON-github provider (no github_user_id) →
    # resolves to the SAME org via the link (no second org minted).
    async with AsyncSessionLocal() as s:
        via_other = await byok_org_resolver.resolve_org_for_supabase_user(
            s, supabase_uid=uid, email="o@example.com", auto_provision=False
        )
    assert via_other.id == gh_org_id
    # And no sb-user-{uid} org was created.
    async with AsyncSessionLocal() as s:
        sb_org = (
            await s.execute(select(Organization).where(Organization.slug == f"sb-user-{uid}"))
        ).scalar_one_or_none()
    assert sb_org is None
