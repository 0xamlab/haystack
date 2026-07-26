"""EntitlementSnapshot — a customer resolved against a compiled catalog release.

The immutable bridge between the Stripe-driven :class:`CatalogRelease` and the signed license:
it pins the source IDs, quantity, and resolved license CLAIMS a customer is entitled to. Three
source types, one output shape:

  * ``community_baseline`` — the always-free Community floor. NO Stripe subscription/customer/
    invoice required (the floor is a code invariant); resolved from the free entitlement record.
  * ``stripe_subscription`` — a paid self-serve subscription; quantity = purchased devices
    (device scope) or Compute Units (deployment scope).
  * ``enterprise_contract`` — a negotiated pool; quantity + optional per-org overrides.

All three produce the same ``license_claims`` dict (mergeable into the signed mint payload) via
the single entitlement source of truth (``entitlement_service``). No usage measurement anywhere —
capacity is the PURCHASED quantity, enforced locally as a cap (owner policy: runs on their infra,
no phone-home).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from apps.api_server.services.entitlement_service import resolve_entitlement, to_license_claims
from apps.api_server.services.stripe_catalog_compiler import CompiledSku

SOURCE_COMMUNITY = "community_baseline"
SOURCE_STRIPE = "stripe_subscription"
SOURCE_ENTERPRISE = "enterprise_contract"
_VALID_SOURCES = frozenset({SOURCE_COMMUNITY, SOURCE_STRIPE, SOURCE_ENTERPRISE})


@dataclass(frozen=True)
class EntitlementSnapshot:
    """Immutable resolved entitlement for one customer — the ONLY input the license signer accepts."""

    source_type: str
    org_id: str
    product: str
    edition: str
    sku_key: str
    quantity: int
    license_scope: str  # device | deployment
    license_claims: dict[str, object]
    catalog_release: str = ""
    policy_hash: str = ""
    stripe_product_id: str = ""
    stripe_price_id: str = ""
    stripe_subscription_id: str = ""
    stripe_subscription_item_id: str = ""


def _plan_for_sku(sku: CompiledSku) -> str:
    """Internal entitlement plan name for a compiled SKU. Deployment ⇒ ``<product>_server``
    (the shared server tier); device ⇒ ``<product>_<edition>`` (falls back to the raw edition)."""
    if sku.license_scope == "deployment":
        return f"{sku.product}_server"
    edition = (sku.edition or "").strip().lower()
    return f"{sku.product}_{edition}" if edition else sku.product


def _community_plan(product: str) -> str:
    """The free Community plan name for a product (``<product>_free`` if defined, else ``free``)."""
    from apps.api_server.services.entitlement_service import _TIER_CAPACITY

    candidate = f"{product}_free"
    return candidate if candidate in _TIER_CAPACITY else "free"


def resolve_community_snapshot(
    *, org_id: str, product: str, catalog_release: str = "", policy_hash: str = ""
) -> EntitlementSnapshot:
    """The always-free Community floor — no Stripe objects required. 1 device / 1 unit / 1 worker,
    non-commercial, device scope. This is the terminal state of every lapse and the default for a
    fresh install; it must resolve even if Stripe/the compiler are unavailable."""
    plan = _community_plan(product)
    record = resolve_entitlement(plan)
    return EntitlementSnapshot(
        source_type=SOURCE_COMMUNITY,
        org_id=org_id,
        product=product,
        edition="community",
        sku_key=f"{product}.community",
        quantity=1,
        license_scope="device",
        license_claims=to_license_claims(record),
        catalog_release=catalog_release,
        policy_hash=policy_hash,
    )


def snapshot_from_record(
    *,
    source_type: str,
    org_id: str,
    product: str,
    edition: str,
    record: object,
    catalog_release: str = "",
    policy_hash: str = "",
    stripe_ids: dict[str, str] | None = None,
) -> EntitlementSnapshot:
    """Build a snapshot from an ALREADY-RESOLVED entitlement record (the connected control-plane
    path, where ``org.plan`` + per-org overrides already produced the record — no CompiledSku
    needed). ``record`` is an ``EntitlementRecord``; quantity is its ``max_concurrent_units``."""
    from apps.api_server.services.entitlement_service import to_license_claims

    scope = "deployment" if getattr(record, "is_deployment_scope", lambda: False)() else "device"
    quantity = int(getattr(record, "max_concurrent_units", 0) or 0)
    ids = stripe_ids or {}
    return EntitlementSnapshot(
        source_type=source_type,
        org_id=org_id,
        product=product,
        edition=edition,
        sku_key=f"{product}.{edition}",
        quantity=quantity,
        license_scope=scope,
        license_claims=to_license_claims(record),
        catalog_release=catalog_release,
        policy_hash=policy_hash,
        stripe_product_id=ids.get("product", ""),
        stripe_price_id=ids.get("price", ""),
        stripe_subscription_id=ids.get("subscription", ""),
        stripe_subscription_item_id=ids.get("subscription_item", ""),
    )


def resolve_snapshot(
    *,
    source_type: str,
    org_id: str,
    sku: CompiledSku,
    quantity: int,
    catalog_release: str = "",
    policy_hash: str = "",
    overrides: dict[str, object] | None = None,
    stripe_ids: dict[str, str] | None = None,
) -> EntitlementSnapshot:
    """Resolve a paid (stripe_subscription) or negotiated (enterprise_contract) snapshot.

    Quantity maps to the metric: deployment scope ⇒ ``max_concurrent_units = quantity``
    (Compute-Unit pool ceiling, + the SKU's measurement policy); device scope ⇒ the org device
    ceiling. Enterprise ``overrides`` (negotiated pools) win on top. No usage measurement — the
    quantity IS the licensed cap."""
    if source_type not in {SOURCE_STRIPE, SOURCE_ENTERPRISE}:
        raise ValueError(f"resolve_snapshot is for paid/enterprise sources, not {source_type!r}")
    if quantity < sku.qty_min or quantity > sku.qty_max:
        raise ValueError(
            f"quantity {quantity} outside SKU {sku.sku_key} bounds [{sku.qty_min}, {sku.qty_max}]"
        )

    plan = _plan_for_sku(sku)
    tier_overrides: dict[str, object] = {}
    if sku.license_scope == "deployment":
        tier_overrides["max_concurrent_units"] = quantity
        tier_overrides["vcpu_per_unit"] = sku.vcpu_per_unit
        tier_overrides["measurement_policy_version"] = sku.measurement_policy_version
        tier_overrides["grace_policy_id"] = sku.grace_policy_id
    else:
        # device scope: purchased quantity is the device/node ceiling (mirrors the existing
        # per-device org_node_ceiling behavior in device_service).
        tier_overrides["active_node_limit"] = quantity
    if overrides:  # negotiated enterprise pools win last
        tier_overrides.update(overrides)

    record = resolve_entitlement(plan, overrides=tier_overrides)
    claims = to_license_claims(record)
    ids = stripe_ids or {}
    return EntitlementSnapshot(
        source_type=source_type,
        org_id=org_id,
        product=sku.product,
        edition=sku.edition or "server",
        sku_key=sku.sku_key,
        quantity=quantity,
        license_scope=sku.license_scope,
        license_claims=claims,
        catalog_release=catalog_release,
        policy_hash=policy_hash,
        stripe_product_id=ids.get("product", ""),
        stripe_price_id=ids.get("price", ""),
        stripe_subscription_id=ids.get("subscription", ""),
        stripe_subscription_item_id=ids.get("subscription_item", ""),
    )
