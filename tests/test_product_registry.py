"""Product registry — the single source of truth for what a *product* (brand) is on the shared engine.

These are pure-unit (no DB / no HTTP). They pin the consolidation of the previously-scattered product signals
AND the cross-brand isolation invariants that are launch blockers: adding Algenta must not silently change how
codna/telys resolve, every product's plans must actually exist, and no two brands may collide on the signals
that route auth / billing / licensing.
"""
from __future__ import annotations

from apps.api_server.models.organization import OrgPlan
from apps.api_server.services import plan_limits, product_registry as pr
from apps.api_server.services.entitlement_service import _TIER_CAPACITY, resolve_entitlement, to_license_claims


# ── client_id → product (device-login) ──────────────────────────────────────────
def test_client_id_resolution():
    assert pr.product_for_client_id("algenta-cli") == "algenta"
    assert pr.product_for_client_id("telys-cli") == "telys"
    # codna-cli is now wired for device-login (device_login=True) → resolves to codna.
    assert pr.product_for_client_id("codna-cli") == "codna"
    # cohenta-cli is likewise RESERVED (device_login=False) — billable via the website, no CLI signup yet.
    assert pr.product_for_client_id("cohenta-cli") is None
    assert pr.product_for_client_id("nope") is None
    assert pr.product_for_client_id("") is None
    assert pr.product_for_client_id(None) is None
    # case-insensitive
    assert pr.product_for_client_id("ALGENTA-CLI") == "algenta"


# ── plan-name namespace → product (billing / entitlement / licensing) ───────────
def test_plan_namespace_resolution():
    assert pr.product_for_plan("algenta_free") == "algenta"
    assert pr.product_for_plan("algenta_pro") == "algenta"
    assert pr.product_for_plan("telys_developer") == "telys"
    assert pr.product_for_plan("telys_team") == "telys"
    assert pr.product_for_plan("cohenta_free") == "cohenta"
    assert pr.product_for_plan("cohenta_pro_runner") == "cohenta"
    assert pr.product_for_plan("cohenta_team") == "cohenta"
    # unprefixed / legacy plans are codna (the default), never mis-bucketed
    for legacy in ("free", "developer", "pro", "proplus", "ultra", "team", "enterprise"):
        assert pr.product_for_plan(legacy) == "codna", legacy
    assert pr.product_for_plan("") == "codna"
    assert pr.product_for_plan(None) == "codna"


# ── RS256 signer routing ─────────────────────────────────────────────────────────
def test_legacy_default_product_is_derived_not_written_twice():
    """The unprefixed plan namespace DEFINES the legacy default, so the id must come from it.

    `/billing/plans` used to hardcode `app: str = "codna"`, which meant an Algenta-branded host answered
    `{"app":"codna",...}` — the right catalogue for the codna deployment and the wrong one everywhere
    else. The id is now derived from `plan_namespace == ""`, so it cannot disagree with the namespace it
    is supposed to name, and `product_for_plan` shares the same derivation.
    """
    owner = pr.legacy_default_product()
    unprefixed = [cfg.id for cfg in pr.all_products() if not cfg.plan_namespace]
    assert unprefixed == [owner]
    # The inverse mapping must agree: an unprefixed plan resolves to the same product.
    for unnamespaced_plan in ("pro", "team", "free", "enterprise", "developer"):
        assert pr.product_for_plan(unnamespaced_plan) == owner
    # A namespaced plan must NOT resolve to it, or the namespace would be meaningless.
    assert pr.product_for_plan("algenta_pro") == "algenta"


def test_rs256_products_set():
    # RS256 products: telys, algenta, cohenta, and now sqai. Codna stays OFF (its runtime verifies HS256).
    assert pr.rs256_license_products() == frozenset({"telys", "algenta", "cohenta", "sqai"})
    assert "codna" not in pr.rs256_license_products()


# ── feature flags (default-safe) ────────────────────────────────────────────────
def test_product_flags_default_safe():
    assert pr.product_flag("telys", "device_login") is True
    assert pr.product_flag("codna", "device_login") is True  # codna CLI device-login shipped
    assert pr.product_flag("algenta", "billing") is True  # live (credential gate is the real switch)
    assert pr.product_flag("algenta", "device_login") is True
    assert pr.product_flag("cohenta", "billing") is True  # website checkout is live
    assert pr.product_flag("cohenta", "device_login") is False  # cohenta-cli reserved, not shipped
    # unknown product / unknown flag → the supplied default, never a crash
    assert pr.product_flag("ghost", "device_login") is False
    assert pr.product_flag("algenta", "does_not_exist") is False
    assert pr.product_flag("algenta", "does_not_exist", default=True) is True


# ── cross-brand isolation invariants (LAUNCH BLOCKERS) ──────────────────────────
def test_no_two_products_share_a_client_id():
    ids = [c.accounts_client_id for c in pr.all_products()]
    assert len(ids) == len(set(ids)), f"duplicate client_id: {ids}"


def test_at_most_one_unprefixed_plan_namespace():
    # Exactly one product (codna) may own the empty/unprefixed namespace; a second would make plan→product
    # ambiguous for legacy names.
    empty = [c.id for c in pr.all_products() if c.plan_namespace == ""]
    assert empty == ["codna"], empty
    prefixes = [c.plan_namespace for c in pr.all_products() if c.plan_namespace]
    assert len(prefixes) == len(set(prefixes)), f"duplicate plan_namespace: {prefixes}"


def test_every_product_default_free_tier_actually_exists():
    # A product whose default_free_tier isn't a real plan would 500 the moment someone onboards.
    for c in pr.all_products():
        assert c.default_free_tier in _TIER_CAPACITY, (c.id, c.default_free_tier, "missing from _TIER_CAPACITY")
        assert plan_limits.get(c.default_free_tier) is not plan_limits._DEFAULT or c.default_free_tier == "free", (
            c.id, c.default_free_tier, "missing from plan_limits._PLANS",
        )
        # and it must be a valid OrgPlan enum value (the DB column is a native enum)
        assert OrgPlan(c.default_free_tier)


def test_every_product_features_are_non_empty():
    # The license verifier (telys/verify.py + the engine verifier) REQUIRES a non-empty features list.
    for c in pr.all_products():
        assert c.features_full, c.id


def test_rs256_products_emit_non_empty_products_map_on_their_free_tier():
    # An RS256/offline product's free tier MUST resolve to products.<id> with non-empty features, or the
    # bundled runtime fails closed at first run.
    for c in pr.all_products():
        if not c.rs256_license:
            continue
        claims = to_license_claims(resolve_entitlement(c.default_free_tier))
        assert c.id in claims["products"], (c.id, claims["products"])
        assert claims["products"][c.id]["features"], (c.id, "empty features")


def test_algenta_free_tier_enables_local_runtime():
    # The whole point of `pip install algenta` is the bundled in-process runtime → local_runtime must be ON.
    cfg = pr.get_product("algenta")
    assert cfg is not None
    assert plan_limits.get(cfg.default_free_tier).local_runtime is True
    assert "local_runtime" in cfg.features_full


def test_every_paid_plan_is_dormant_exempt():
    # A paid plan missing from dormant_accounts.PAID_PLANS means a PAYING customer of that plan can be
    # auto-deleted as "dormant". Derive the invariant from plan_limits so it catches every brand, forever.
    from apps.api_server.services.dormant_accounts import PAID_PLANS

    for name, cfg in plan_limits._PLANS.items():
        if cfg.price_usd_month and cfg.price_usd_month > 0:
            assert name in PAID_PLANS, f"paid plan {name!r} not in PAID_PLANS → a payer could be auto-deleted"


def test_every_team_tier_is_multi_seat():
    # A *_team tier that isn't multi-seat caps the org at the owner alone — the paid team plan can't add
    # teammates. Every team-shaped plan (name == 'team' or endswith '_team') must be multi-seat. Uses the
    # public is_multi_seat() so per-DEVICE team plans (algenta_team: fixed 15-seat bundle, billed by
    # device not seat) still count — they're multi-member even though not in the per-seat _MULTI_SEAT set.
    from apps.api_server.services.team_seats import is_multi_seat

    for name in plan_limits._PLANS:
        if name == "team" or name.endswith("_team"):
            assert is_multi_seat(name), f"team plan {name!r} not multi-seat → owner can't add teammates"


def test_platform_license_constants_shared_across_brands():
    # ALL brands share the one issuer/audience/kid (product scoping is via products.<id>) — this is what
    # lets one verifier accept every brand's license. Drift here silently breaks cross-brand verification.
    assert pr.PLATFORM_LICENSE_ISSUER == "https://license.algenta.ai"
    assert pr.PLATFORM_LICENSE_AUDIENCE == "algenta-runtime"
    assert pr.PLATFORM_LICENSE_KID == "algenta-license-2026"
    for c in pr.all_products():
        assert c.license_issuer == pr.PLATFORM_LICENSE_ISSUER, c.id
        assert c.license_audience == pr.PLATFORM_LICENSE_AUDIENCE, c.id
