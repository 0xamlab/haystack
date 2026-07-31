"""Product registry — the ONE source of truth for what a *product* (brand) is on the shared engine.

One deployed engine serves several brands (codna, telys, algenta, …). They are NOT separate infra and
NOT ``if product == "algenta"`` branches — they are *products*: rows in this registry, distinguished only
by identity / entitlement / billing / license *claims*. Every product-aware surface reads product metadata
from here instead of keeping its own private per-brand map. Before this module, "product" was expressed
seven different ways (device-login ``_KNOWN_CLIENTS``, plan-name prefix, entitlement ``products`` map,
Stripe ``metadata.source``, ``_RS256_LICENSE_PRODUCTS``, the MCP ``PRODUCT_*`` dicts, single-brand host
constants); this consolidates the *product-identity* half of that so adding a brand is adding ONE row here
plus its plan tiers + a Stripe price — never scattering another ``if product == …`` across the tree.

Leaf module by design: it imports nothing from ``apps.api_server.services`` so any of those may import it
without a cycle (``entitlement_service`` owns the tier→capacity math and imports the feature sets from here).

Product is resolved from an authoritative *signal*, never a request body:
  * device-login   → ``product_for_client_id(client_id)``   (the CLI's ``client_id``)
  * billing/plans  → ``product_for_plan(plan_name)``         (the plan-name namespace)
  * MCP edition    → ``ALGENTA_PRODUCT`` / ``X-Algenta-Product`` (a routing hint, still ∩ entitlements)
  * license claim  → ``products.<id>``                        (signed; the real authority)
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

# ── Per-product feature sets (owned here; imported by entitlement_service + mirrored by the MCP map) ──────
# A v2 license grants ``products.<id>.features``; the runtime/MCP gate tools on them (telys.verify + the
# engine verifier only require the list be non-empty). Codna's set must match the keys of
# PRODUCT_FEATURE_TOOLS in packages/mcp/algenta_mcp/products.py (invariant-tested there).
CODNA_FEATURES_FULL: tuple[str, ...] = ("repo_graph", "triage", "simulate", "fix", "apply")
# Telys (on-device memory/retrieval runtime) — mirror of telys-sdk telys/verify.py TELYS_FEATURES.
TELYS_FEATURES_FULL: tuple[str, ...] = ("local_runtime", "partitioned_vector", "ivf_partition")
# SQAI (on-device structured-query runtime) — mirrors the telys shape (local runtime + its query surface).
SQAI_FEATURES_FULL: tuple[str, ...] = ("local_runtime", "structured_query")
# Algenta IS the engine (codna is its coding edition), so its product grants the full engine surface:
# the bundled local runtime (``local_runtime``, like telys) plus the repository-intelligence flow
# (the codna feature keys, so the shared feature→tool map applies unchanged).
ALGENTA_FEATURES_FULL: tuple[str, ...] = (
    "local_runtime",
    "repo_graph",
    "triage",
    "simulate",
    "fix",
    "apply",
)
# Cohenta (campaign orchestration) — the campaign lifecycle surface: create/manage campaigns, the
# human approval gate, and confirmed publication. Minimal on purpose (the verifier only requires a
# non-empty list); grow it alongside the Cohenta runtime the way telys/algenta grew theirs.
COHENTA_FEATURES_FULL: tuple[str, ...] = ("campaigns", "approvals", "publishing")

# The SHARED platform license signer (the decision-engine ``license-signer`` Cloudflare Worker + the OEM
# minter). EVERY product's RS256 license carries this issuer + audience + kid; product scoping is via the
# per-product ``products.<id>`` claim, NOT a per-product audience. Keeping these identical across brands is
# exactly what lets one verifier (telys/verify.py, apps/runtime/license.py) accept every brand's license —
# see memory-engine telys_issuer.py / issue_oem_license.py and device_service._PLATFORM_LICENSE_*.
PLATFORM_LICENSE_ISSUER = "https://license.algenta.ai"
PLATFORM_LICENSE_AUDIENCE = "algenta-runtime"
PLATFORM_LICENSE_KID = "algenta-license-2026"


@dataclass(frozen=True)
class ProductConfig:
    """Identity + capability metadata for one brand on the shared engine."""

    id: str  # canonical product id (== the license ``products.<id>`` key + the MCP ``ALGENTA_PRODUCT`` value)
    display_name: str
    accounts_client_id: str  # RFC 8628 device-login client_id that maps to this product (``<id>-cli``)
    accounts_app_slug: str  # ``?app=<slug>`` on accounts.thyn.ai (the portal's per-brand config key)
    plan_namespace: str  # plan-name prefix for this product's tiers ("" = unprefixed legacy default = codna)
    default_free_tier: str  # the plan a fresh onboarding user lands on (must exist in plan_limits + _TIER_CAPACITY)
    features_full: tuple[str, ...]  # the product's full feature set (license ``products.<id>.features``)
    mcp_server_name: str  # public MCP registry name (``io.github.thyn-ai/<id>``)
    public_api_base: str  # the brand's engine host (a DNS alias in front of the one shared engine)
    # Use the RS256 platform signer (shared key → cross-product verifiable) rather than the legacy HS256
    # dev/local path. Telys + Algenta ride RS256; codna stays on its existing path until it cuts over.
    rs256_license: bool = True
    license_audience: str = PLATFORM_LICENSE_AUDIENCE
    license_issuer: str = PLATFORM_LICENSE_ISSUER
    # Per-product launch gates (default-safe): a brand ships dark and flips on independently. Read via
    # ``product_flag`` so an unknown flag is False, never a crash.
    feature_flags: Mapping[str, bool] = field(default_factory=dict)


# The registry. Order is display order (drives "your products" style overviews).
_PRODUCTS: dict[str, ProductConfig] = {
    # Codna — the coding edition; the unprefixed legacy default (developer/pro/team plans have no prefix).
    # CLI device-login is now shipped (codna-cli → /v1/products/codna/onboard), alongside the GitHub App
    # for cloud fixes. The runtime license stays HS256 (rs256_license=False) — decoupled from device_login,
    # which only governs the accounts device-code sign-in, not the license format.
    "codna": ProductConfig(
        id="codna",
        display_name="Codna",
        accounts_client_id="codna-cli",
        accounts_app_slug="codna",
        plan_namespace="",
        default_free_tier="free",
        features_full=CODNA_FEATURES_FULL,
        mcp_server_name="io.github.thyn-ai/codna",
        public_api_base="https://api.codna.ai",
        rs256_license=False,
        feature_flags={"billing": True, "device_login": True},
    ),
    # Telys — on-device memory/retrieval runtime; live, RS256 platform licenses, device-login shipped.
    "telys": ProductConfig(
        id="telys",
        display_name="Telys",
        accounts_client_id="telys-cli",
        accounts_app_slug="telys",
        plan_namespace="telys",
        default_free_tier="telys_developer",
        features_full=TELYS_FEATURES_FULL,
        mcp_server_name="io.github.thyn-ai/telys",
        public_api_base="https://api.telys.ai",
        rs256_license=True,
        feature_flags={"billing": True, "device_login": True},
    ),
    # Algenta — the engine itself, live as a first-class product. Bundled in-process native runtime,
    # RS256 platform license, device-login, self-serve free tier. Billing is ON (per-device Pro/Team are
    # live in Stripe); the effective dark switch is now credential-based — billing_configured() gates on
    # a real (non-placeholder) Stripe key, so a deploy without real keys still refuses checkout. OEM
    # minting is separate infra (not a product flag).
    "algenta": ProductConfig(
        id="algenta",
        display_name="Algenta",
        accounts_client_id="algenta-cli",
        accounts_app_slug="algenta",
        plan_namespace="algenta",
        default_free_tier="algenta_free",
        features_full=ALGENTA_FEATURES_FULL,
        mcp_server_name="io.github.thyn-ai/algenta",
        public_api_base="https://api.algenta.ai",
        rs256_license=True,
        feature_flags={"billing": True, "device_login": True},
    ),
    # Cohenta — campaign orchestration; live for self-serve website billing (accounts.thyn.ai checkout),
    # RS256 platform license. device_login stays OFF (cohenta-cli is reserved, not yet wired) so — like
    # codna — there is no ungated CLI signup until it ships; the accounts portal is the only entry.
    "cohenta": ProductConfig(
        id="cohenta",
        display_name="Cohenta",
        accounts_client_id="cohenta-cli",
        accounts_app_slug="cohenta",
        plan_namespace="cohenta",
        default_free_tier="cohenta_free",
        features_full=COHENTA_FEATURES_FULL,
        mcp_server_name="io.github.thyn-ai/cohenta",
        public_api_base="https://api.cohenta.ai",
        rs256_license=True,
        feature_flags={"billing": True, "device_login": False},
    ),
    # SQAI — on-device structured-query runtime; mirrors the telys shape. RS256 platform license,
    # device-login, self-serve free tier. Billing is ON (Pro/Team live in Stripe under the
    # sqai_<plan>_<cadence> lookup keys); the effective gate is credential-based — billing_configured()
    # refuses checkout unless a real (non-placeholder) Stripe key is present, so a keyless deploy is safe.
    "sqai": ProductConfig(
        id="sqai",
        display_name="SQAI",
        accounts_client_id="sqai-cli",
        accounts_app_slug="sqai",
        plan_namespace="sqai",
        default_free_tier="sqai_developer",
        features_full=SQAI_FEATURES_FULL,
        mcp_server_name="io.github.thyn-ai/sqai",
        public_api_base="https://api.sqai.ai",
        rs256_license=True,
        feature_flags={"billing": True, "device_login": True},
    ),
}


def all_products() -> list[ProductConfig]:
    """Every registered product, in registry order."""
    return list(_PRODUCTS.values())


def get_product(product_id: str | None) -> ProductConfig | None:
    """Resolve a product id to its config, or ``None`` for unknown/blank (callers fail closed)."""
    if not product_id:
        return None
    return _PRODUCTS.get(product_id.strip().lower())


def product_for_client_id(client_id: str | None) -> str | None:
    """Device-login: map a CLI ``client_id`` (e.g. ``algenta-cli``) to its product id, or ``None``.

    Replaces the private ``oauth_device._KNOWN_CLIENTS`` map. A product only participates in device-login
    when its ``device_login`` flag is set (``codna-cli`` is now wired; ``cohenta-cli`` stays reserved/off).
    """
    if not client_id:
        return None
    wanted = client_id.strip().lower()
    for cfg in _PRODUCTS.values():
        if cfg.accounts_client_id == wanted and product_flag(cfg.id, "device_login"):
            return cfg.id
    return None


def product_for_public_api_host(host: str | None) -> str | None:
    """Map the host a request ARRIVED on to the brand that host belongs to, or ``None``.

    Derived from each row's ``public_api_base`` (``https://api.algenta.ai`` → ``algenta``) rather than a
    second per-brand host map, so a new brand cannot be reachable without being resolvable. The brand
    hosts are DNS aliases in front of ONE engine, so the host is the only per-request signal that says
    which brand a caller is actually talking to — which is what makes it the right default for a public,
    pre-auth surface where there is no key, no plan and no license to read the product from.

    A ``Host`` header is caller-supplied and therefore NOT a trust boundary: this answers "which brand is
    this host", never "is the caller allowed". Treat it exactly as authoritative as an explicit
    ``?app=`` — its value is that the honest, common case (a brand's own pricing page hitting its own
    host) resolves correctly with zero configuration.

    Returns ``None`` for a non-brand host (an internal Fly/Kubernetes name, an IP, ``localhost``, a
    preview URL). ``None`` means "this host does not speak for any single brand", so callers fall back
    to configuration — it must never be read as a brand.
    """
    candidate = (host or "").strip().lower()
    if not candidate:
        return None
    # Drop any port; a brand host is the same brand on :443 as on :8000.
    if candidate.startswith("["):  # bracketed IPv6 literal — never a brand host
        return None
    candidate = candidate.split(":", 1)[0].rstrip(".")
    if not candidate:
        return None
    for cfg in _PRODUCTS.values():
        base = cfg.public_api_base.strip().lower()
        # Compare hostnames, not URLs, so scheme/port/trailing-slash differences cannot cause a miss.
        base_host = base.split("://", 1)[-1].split("/", 1)[0].split(":", 1)[0].rstrip(".")
        if base_host and base_host == candidate:
            return cfg.id
    return None


def product_for_plan(plan_name: str | None) -> str:
    """Billing/entitlement: map an internal plan name to its product id via the plan-name namespace.

    ``telys_pro`` → ``telys``; ``algenta_free`` → ``algenta``; an unprefixed/unknown plan (``pro``,
    ``team``, ``free``, ``enterprise``) → ``codna`` (the legacy default). This is the inverse of how a
    brand namespaces its tiers; it never trusts a caller-supplied product string.
    """
    name = (plan_name or "").strip().lower()
    # Longest namespace first so a hypothetical overlapping prefix can't mis-bucket.
    for cfg in sorted(_PRODUCTS.values(), key=lambda c: len(c.plan_namespace), reverse=True):
        if cfg.plan_namespace and name.startswith(f"{cfg.plan_namespace}_"):
            return cfg.id
    return legacy_default_product()


def legacy_default_product() -> str:
    """The product owning the UNPREFIXED plan namespace — i.e. what a nameless plan or brand means.

    Derived from ``plan_namespace == ""`` rather than written as a literal, because that empty namespace
    IS the definition of "the legacy default" and having the id spelled out in a second place is how the
    two drift apart. Exactly one product may claim it; more than one is a registry error, and it is
    raised rather than resolved arbitrarily, because silently picking one would make an unprefixed plan
    resolve to a different brand depending on dict order.
    """
    unprefixed = [cfg.id for cfg in _PRODUCTS.values() if not cfg.plan_namespace]
    if len(unprefixed) != 1:
        raise ValueError(
            "exactly one product must own the unprefixed plan namespace, found: "
            + (", ".join(sorted(unprefixed)) or "none")
        )
    return unprefixed[0]


def rs256_license_products() -> frozenset[str]:
    """Products whose licenses are signed by the RS256 platform signer (vs the legacy HS256 path).

    Replaces the hardcoded ``device_service._RS256_LICENSE_PRODUCTS = {"telys"}`` set; still env-extensible
    at the call site for emergencies.
    """
    return frozenset(cfg.id for cfg in _PRODUCTS.values() if cfg.rs256_license)


def product_flag(product_id: str | None, flag: str, *, default: bool = False) -> bool:
    """Read a per-product launch flag, default-safe (unknown product/flag → ``default``)."""
    cfg = get_product(product_id)
    if cfg is None:
        return default
    value = cfg.feature_flags.get(flag)
    return default if value is None else bool(value)
