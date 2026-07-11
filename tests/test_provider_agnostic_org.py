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


# ── CLI onboard (`<product> login`, email-keyed org) writes the identity link → website checkout
#    converges on the SAME org (no split-brain, no duplicate) for a non-github provider ─────────────
@pytest.mark.anyio
async def test_cli_onboard_links_org_so_website_resolve_converges() -> None:
    from apps.api_server.services.user_service import activate_product_free_tier

    uid = f"sb-{uuid.uuid4().hex}"
    email = f"conv-{uuid.uuid4().hex}@gmail.com"
    # `algenta login`: activate the free tier (org resolved/created BY EMAIL) + bind the supabase uid —
    # exactly what the onboarding router now does after activate_product_free_tier.
    async with AsyncSessionLocal() as s:
        org, _user = await activate_product_free_tier(s, product="algenta", email=email)
        onboarded_id = org.id
        await byok_org_resolver.ensure_identity_link(s, supabase_uid=uid, org_id=onboarded_id)
        await s.commit()
    # Website billing resolves PROVIDER-AGNOSTICALLY by the supabase uid. Even with auto_provision ON it
    # must return the SAME onboarded org via the link — never mint a second `sb-user-{uid}` org.
    async with AsyncSessionLocal() as s:
        resolved = await byok_org_resolver.resolve_org_for_supabase_user(
            s, supabase_uid=uid, email=email, auto_provision=True
        )
    assert resolved.id == onboarded_id
    async with AsyncSessionLocal() as s:
        dup = (
            await s.execute(select(Organization).where(Organization.slug == f"sb-user-{uid}"))
        ).scalar_one_or_none()
    assert dup is None, "auto_provision minted a duplicate org despite an existing identity link"


# ── A1 (BLOCKER): the identity link is authoritative — a github-linked uid that already has a link
#    resolves to the LINKED org, never hijacked onto its gh-user install org (nor locked out) ────────
@pytest.mark.anyio
async def test_github_identity_with_existing_link_resolves_link_not_install() -> None:
    from apps.api_server.services.user_service import activate_product_free_tier

    gh_id = 800000 + uuid.uuid4().int % 90000
    uid = f"sb-{uuid.uuid4().hex}"
    # A gh-user install org (org B) exists for this github id.
    async with AsyncSessionLocal() as s:
        gh_org = await provision_or_lookup_org_for_installation(
            s, account_id=gh_id, account_login="octo", account_type="user"
        )
        await s.commit()
        gh_org_id = gh_org.id
    # CLI `<product> login` created an email-keyed org A + link uid->A (link-first: no link yet -> email).
    async with AsyncSessionLocal() as s:
        org_a, _ = await activate_product_free_tier(
            s, product="algenta", email=f"a-{uuid.uuid4().hex}@gmail.com", supabase_uid=uid
        )
        await byok_org_resolver.ensure_identity_link(s, supabase_uid=uid, org_id=org_a.id)
        await s.commit()
        org_a_id = org_a.id
    assert org_a_id != gh_org_id
    # Resolving as the GITHUB identity (github_user_id set) must return org A via the link — NOT org B.
    async with AsyncSessionLocal() as s:
        resolved = await byok_org_resolver.resolve_org_for_supabase_user(
            s, supabase_uid=uid, email="x@example.com", github_user_id=gh_id, github_login="octo"
        )
    assert resolved.id == org_a_id


@pytest.mark.anyio
async def test_github_identity_with_link_but_no_install_is_not_locked_out() -> None:
    # A1: github_user_id present + a link + NO install must return the linked org, not no_org 403.
    from apps.api_server.services.user_service import activate_product_free_tier

    uid = f"sb-{uuid.uuid4().hex}"
    gh_id = 700000 + uuid.uuid4().int % 90000
    async with AsyncSessionLocal() as s:
        org, _ = await activate_product_free_tier(
            s, product="algenta", email=f"b-{uuid.uuid4().hex}@gmail.com", supabase_uid=uid
        )
        await byok_org_resolver.ensure_identity_link(s, supabase_uid=uid, org_id=org.id)
        await s.commit()
        org_id = org.id
    async with AsyncSessionLocal() as s:
        resolved = await byok_org_resolver.resolve_org_for_supabase_user(
            s, supabase_uid=uid, github_user_id=gh_id, github_login="ghost"
        )
    assert resolved.id == org_id


# ── A2: ensure_identity_link returns the WINNER on conflict (caller must not strand a duplicate) ────
@pytest.mark.anyio
async def test_ensure_identity_link_returns_existing_winner() -> None:
    uid = f"sb-{uuid.uuid4().hex}"
    async with AsyncSessionLocal() as s:
        a = await provision_org_for_supabase_uid(s, supabase_uid=uid + "-a", email="a@gmail.com")
        b = await provision_org_for_supabase_uid(s, supabase_uid=uid + "-b", email="b@gmail.com")
        await s.commit()
        a_id, b_id = a.id, b.id
    async with AsyncSessionLocal() as s:
        first = await byok_org_resolver.ensure_identity_link(s, supabase_uid=uid, org_id=a_id)
        assert first == a_id
        # A later call with a DIFFERENT org returns the existing winner (A), never re-points to B.
        second = await byok_org_resolver.ensure_identity_link(s, supabase_uid=uid, org_id=b_id)
        assert second == a_id


# ── A3: CLI onboard is link-first — a rotated email (Apple relay) reuses the org, no duplicate ──────
@pytest.mark.anyio
async def test_cli_onboard_link_first_ignores_rotated_email() -> None:
    from apps.api_server.services.user_service import activate_product_free_tier

    uid = f"sb-{uuid.uuid4().hex}"
    async with AsyncSessionLocal() as s:
        org1, _ = await activate_product_free_tier(
            s, product="algenta", email="relay1@privaterelay.appleid.com", supabase_uid=uid
        )
        await byok_org_resolver.ensure_identity_link(s, supabase_uid=uid, org_id=org1.id)
        await s.commit()
        org1_id = org1.id
    # Apple rotates the relay address; the SAME uid onboards again with a DIFFERENT email.
    async with AsyncSessionLocal() as s:
        org2, _ = await activate_product_free_tier(
            s, product="algenta", email="relay2@privaterelay.appleid.com", supabase_uid=uid
        )
        await s.commit()
    assert org2.id == org1_id  # reused via the uid link — not a new email-keyed duplicate


# ── selected_org_id (org picker) still switches + persists via repoint ───────────────────────────────
@pytest.mark.anyio
async def test_repoint_identity_link_moves_link() -> None:
    uid = f"sb-{uuid.uuid4().hex}"
    async with AsyncSessionLocal() as s:
        a = await provision_org_for_supabase_uid(s, supabase_uid=uid + "-a", email="a@gmail.com")
        b = await provision_org_for_supabase_uid(s, supabase_uid=uid + "-b", email="b@gmail.com")
        await s.commit()
        a_id, b_id = a.id, b.id
    async with AsyncSessionLocal() as s:
        await byok_org_resolver.ensure_identity_link(s, supabase_uid=uid, org_id=a_id)
        await byok_org_resolver.repoint_identity_link(s, supabase_uid=uid, org_id=b_id)
        await s.commit()
    async with AsyncSessionLocal() as s:
        linked = await byok_org_resolver._org_for_identity_link(s, uid)
    assert linked is not None and linked.id == b_id
