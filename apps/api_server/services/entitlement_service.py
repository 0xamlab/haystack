"""Entitlement resolution — the single authorized source of an org's commercial capacity.

A license carries *commercial-capacity* claims (named seats, runtime nodes, concurrent
workers, product editions, deployment rights). Those claims are NOT free-form: the
license signer must only sign caps that are **≤ the org's authorized entitlement record**.
This module computes that record from the org's plan tier (+ optional per-org overrides
for negotiated enterprise deals), so issuance, signer-side validation, and billing all
agree on one source of truth.

Enforcement split (see the licensing plan):

* GLOBAL pools (``named_seat_limit``, ``active_node_limit``) — control plane, at
  activation / renewal / reconciliation.
* LOCAL caps (``concurrent_worker_limit``, ``device_allowance_per_seat``, product/feature
  gating) — the runtime broker + MCP edition gating (see ``apps/runtime/worker_broker.py``
  and ``packages/mcp/algenta_mcp/products.py``).

The numbers below encode the commercial model and are intentionally TUNABLE — the
self-service ceiling (≤5 seats / ≤2 nodes / ≤4 workers; above ⇒ enterprise contract) is a
business decision, not a constant of the system. ``to_license_claims()`` emits exactly the
v2 claim subset that ``apps/runtime/license.py`` parses back (round-trip tested).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace

import structlog

# Per-product feature sets are owned by the product registry (single source of truth). Re-exported through
# this import so existing importers/tests (`from entitlement_service import CODNA_FEATURES_FULL`) still work,
# and so the MCP feature→tool map in packages/mcp/algenta_mcp/products.py stays the mirror of codna's keys.
from apps.api_server.services import plan_limits
from apps.api_server.services.product_registry import (
    ALGENTA_FEATURES_FULL,
    CODNA_FEATURES_FULL,
    COHENTA_FEATURES_FULL,
    SQAI_FEATURES_FULL,
    TELYS_FEATURES_FULL,
)

logger = structlog.get_logger(__name__)

# Self-service ceiling (anti-underpayment): at or below this, an org may self-serve;
# above it requires an enterprise contract (negotiated pools via per-org overrides).
SELF_SERVICE_MAX_SEATS = 5
SELF_SERVICE_MAX_NODES = 2
# Top self-serve worker cap = the Team tier's per-device worker cap (pricing: Team = 20/device).
# Above this ⇒ enterprise contract. Kept in sync with plan_limits._WORKER_LIMITS.
SELF_SERVICE_MAX_WORKERS = 20

# ── Compute-Unit (server/enterprise) policy — TUNABLE; the authoritative values are the
# Stripe catalog's; these are the code defaults + safety anchors. Named in the signed license
# so the runtime knows which measurement/grace rules are in force. ──
MEASUREMENT_POLICY_VERSION = "cgroup-v1"  # apps/runtime/capacity.py effective-vCPU rules
GRACE_POLICY_ID = "community-floor-v1"  # lapse → Community floor state machine
DEFAULT_VCPU_PER_UNIT = 4  # 4 effective vCPU = 1 Compute Unit
# Per-ORDER Compute-Unit minimums (NEVER per node/pod — the plan's anti-per-node-minimum rule).
PINNED_SERVER_MIN_UNITS = 4
FLOATING_POOL_MIN_UNITS = 16


@dataclass(frozen=True)
class ProductGrant:
    """A product edition the org is entitled to, and which features within it."""

    tier: str
    features: frozenset[str]


@dataclass(frozen=True)
class EntitlementRecord:
    """The authorized commercial capacity for an org — the cap the signer validates against.

    A limit of ``0`` means *unspecified / negotiated* (enterprise pools the control plane
    reconciles; the local broker treats 0 as uncapped). Concrete self-service tiers carry
    finite caps.
    """

    plan: str
    deployment_class: str = ""  # desktop | server | ci | airgapped | oem
    products: dict[str, ProductGrant] = field(default_factory=dict)
    named_seat_limit: int = 0
    active_node_limit: int = 0
    concurrent_worker_limit: int = 0
    device_allowance_per_seat: int = 0
    commercial_use: bool = False
    redistribution_allowed: bool = False
    offline_grace_days: int = 0
    entitlement_version: int = 0  # monotonic; the signer rejects regressions
    # ── server/enterprise (Compute-Unit) capacity — default = personal-device scope ──
    # license_scope switches the whole enforcement model: "device" (the shipped per-device
    # path — devices/workers) vs "deployment" (org server pool — Compute Units). Only a
    # deployment record carries the unit claims; device records leave them at zero so device
    # tokens are unchanged.
    license_scope: str = "device"  # device | deployment
    max_concurrent_units: int = 0  # Compute-Unit pool ceiling (deployment scope)
    max_effective_vcpu: int = 0  # per-node workstation vCPU ceiling (0 = unspecified)
    vcpu_per_unit: int = 0  # measurement policy (0 = runtime default of 4)
    measurement_policy_version: str = ""  # names the vCPU→unit rules in force
    grace_policy_id: str = ""  # names the lapse/grace/Community-floor policy

    def has_product(self, product: str) -> bool:
        return product in self.products

    def is_deployment_scope(self) -> bool:
        return self.license_scope == "deployment"


def _codna_full(tier: str) -> dict[str, ProductGrant]:
    return {"codna": ProductGrant(tier=tier, features=frozenset(CODNA_FEATURES_FULL))}


def _telys_full(tier: str) -> dict[str, ProductGrant]:
    return {"telys": ProductGrant(tier=tier, features=frozenset(TELYS_FEATURES_FULL))}


def _sqai_full(tier: str) -> dict[str, ProductGrant]:
    return {"sqai": ProductGrant(tier=tier, features=frozenset(SQAI_FEATURES_FULL))}


def _algenta_full(tier: str) -> dict[str, ProductGrant]:
    return {"algenta": ProductGrant(tier=tier, features=frozenset(ALGENTA_FEATURES_FULL))}


def _cohenta_full(tier: str) -> dict[str, ProductGrant]:
    return {"cohenta": ProductGrant(tier=tier, features=frozenset(COHENTA_FEATURES_FULL))}


def _server_record(plan: str, products: dict[str, ProductGrant]) -> EntitlementRecord:
    """Build a DEPLOYMENT-scope (Compute-Unit) server tier — identical across every edition, so
    Algenta/Codna/Telys/SQAI/Cohenta share ONE server-licensing model (only the product grant
    differs). The mint overrides ``max_concurrent_units`` with the org's purchased unit quantity;
    this base is the pinned-server minimum."""
    return EntitlementRecord(
        plan=plan,
        deployment_class="server",
        license_scope="deployment",
        products=products,
        named_seat_limit=0,
        active_node_limit=0,
        concurrent_worker_limit=0,  # derived from units by the runtime broker
        device_allowance_per_seat=0,
        commercial_use=True,
        offline_grace_days=14,
        max_concurrent_units=PINNED_SERVER_MIN_UNITS,
        max_effective_vcpu=0,
        vcpu_per_unit=DEFAULT_VCPU_PER_UNIT,
        measurement_policy_version=MEASUREMENT_POLICY_VERSION,
        grace_policy_id=GRACE_POLICY_ID,
    )



# Per-tier capacity — keyed by the internal plan name (OrgPlan values). ``developer`` and
# ``pro`` are the same commercial tier (see plan_limits). Unknown plans resolve to ``free``.
_TIER_CAPACITY: dict[str, EntitlementRecord] = {
    # Cloud-API only: no local engine license at all (free download stays inert).
    "free": EntitlementRecord(plan="free"),
    # Telys free developer license — account required, NO card; 1 device, local/non-commercial.
    "telys_developer": EntitlementRecord(
        plan="telys_developer",
        deployment_class="desktop",
        products=_telys_full("developer"),
        named_seat_limit=1,
        active_node_limit=1,
        concurrent_worker_limit=1,
        device_allowance_per_seat=1,
        commercial_use=False,
        offline_grace_days=30,
    ),
    "telys_pro": EntitlementRecord(
        plan="telys_pro", deployment_class="desktop",
        products=_telys_full("pro"),
        named_seat_limit=1, active_node_limit=1, concurrent_worker_limit=2,
        device_allowance_per_seat=3, commercial_use=True, offline_grace_days=14,
    ),
    "telys_team": EntitlementRecord(
        plan="telys_team", deployment_class="server",
        products=_telys_full("team"),
        named_seat_limit=SELF_SERVICE_MAX_SEATS, active_node_limit=SELF_SERVICE_MAX_NODES,
        concurrent_worker_limit=SELF_SERVICE_MAX_WORKERS,
        device_allowance_per_seat=3, commercial_use=True, offline_grace_days=14,
    ),
    # SQAI (on-device structured-query runtime) — mirrors the telys developer/pro/team capacities.
    # sqai_developer is the free, no-card, 1-device, local/non-commercial tier `sqai login` lands on.
    "sqai_developer": EntitlementRecord(
        plan="sqai_developer",
        deployment_class="desktop",
        products=_sqai_full("developer"),
        named_seat_limit=1,
        active_node_limit=1,
        concurrent_worker_limit=1,
        device_allowance_per_seat=1,
        commercial_use=False,
        offline_grace_days=30,
    ),
    "sqai_pro": EntitlementRecord(
        plan="sqai_pro", deployment_class="desktop",
        products=_sqai_full("pro"),
        named_seat_limit=1, active_node_limit=1, concurrent_worker_limit=2,
        device_allowance_per_seat=3, commercial_use=True, offline_grace_days=14,
    ),
    "sqai_team": EntitlementRecord(
        plan="sqai_team", deployment_class="server",
        products=_sqai_full("team"),
        named_seat_limit=SELF_SERVICE_MAX_SEATS, active_node_limit=SELF_SERVICE_MAX_NODES,
        concurrent_worker_limit=SELF_SERVICE_MAX_WORKERS,
        device_allowance_per_seat=3, commercial_use=True, offline_grace_days=14,
    ),
    # Algenta (the engine, as a first-class product) — mirrors the telys developer/pro/team shape so the
    # bundled in-process runtime gets products.algenta. algenta_free is the free, no-card, 1-device,
    # local/non-commercial tier a fresh `algenta login` lands on.
    "algenta_free": EntitlementRecord(
        plan="algenta_free",
        deployment_class="desktop",
        products=_algenta_full("developer"),
        named_seat_limit=1,
        active_node_limit=1,
        concurrent_worker_limit=1,
        device_allowance_per_seat=1,
        commercial_use=False,
        offline_grace_days=30,
    ),
    "algenta_pro": EntitlementRecord(
        plan="algenta_pro", deployment_class="desktop",
        products=_algenta_full("pro"),
        named_seat_limit=1, active_node_limit=1, concurrent_worker_limit=5,
        device_allowance_per_seat=3, commercial_use=True, offline_grace_days=14,
    ),
    # Team — self-hosted, per-DEVICE ($499/device). 15 seats (fixed bundle from the pricing card, not
    # the billing unit — devices are). 20 workers/device. Device count = licensed quantity (Part 2 wires
    # the quantity → device cap; active_node_limit here is the self-serve base until then).
    "algenta_team": EntitlementRecord(
        plan="algenta_team", deployment_class="server",
        products=_algenta_full("team"),
        named_seat_limit=15, active_node_limit=1,
        concurrent_worker_limit=SELF_SERVICE_MAX_WORKERS,
        device_allowance_per_seat=3, commercial_use=True, offline_grace_days=14,
    ),
    # Algenta SERVER — organization-DEPLOYMENT scope (Compute Units, not per-device). Same
    # server model as every other edition (_server_record); the mint overrides
    # max_concurrent_units with the org's PURCHASED unit quantity (Stripe qty).
    "algenta_server": _server_record("algenta_server", _algenta_full("enterprise")),
    # Server (DEPLOYMENT scope) tiers for every edition — the SAME Compute-Unit model, one code
    # path (_server_record); only the product grant differs. mint overrides max_concurrent_units.
    "codna_server": _server_record("codna_server", _codna_full("enterprise")),
    "telys_server": _server_record("telys_server", _telys_full("enterprise")),
    "sqai_server": _server_record("sqai_server", _sqai_full("enterprise")),
    "cohenta_server": _server_record("cohenta_server", _cohenta_full("enterprise")),
    # Cohenta (campaign orchestration) — mirrors the telys developer/pro/team shape so the runtime gets
    # products.cohenta. cohenta_free is the free, no-card, 1-device tier; pro_runner is the paid solo
    # tier; team is per-SEAT (Stripe quantity = seats, see team_seats), at the self-service ceiling.
    "cohenta_free": EntitlementRecord(
        plan="cohenta_free",
        deployment_class="desktop",
        products=_cohenta_full("developer"),
        named_seat_limit=1,
        active_node_limit=1,
        concurrent_worker_limit=1,
        device_allowance_per_seat=1,
        commercial_use=False,
        offline_grace_days=30,
    ),
    "cohenta_pro_runner": EntitlementRecord(
        plan="cohenta_pro_runner", deployment_class="desktop",
        products=_cohenta_full("pro"),
        named_seat_limit=1, active_node_limit=1, concurrent_worker_limit=2,
        device_allowance_per_seat=3, commercial_use=True, offline_grace_days=14,
    ),
    "cohenta_team": EntitlementRecord(
        plan="cohenta_team", deployment_class="server",
        products=_cohenta_full("team"),
        named_seat_limit=SELF_SERVICE_MAX_SEATS, active_node_limit=SELF_SERVICE_MAX_NODES,
        concurrent_worker_limit=SELF_SERVICE_MAX_WORKERS,
        device_allowance_per_seat=3, commercial_use=True, offline_grace_days=14,
    ),
    # Individual / small — desktop, within the self-service ceiling.
    "developer": EntitlementRecord(
        plan="developer",
        deployment_class="desktop",
        products=_codna_full("pro"),
        named_seat_limit=1,
        active_node_limit=1,
        concurrent_worker_limit=2,
        device_allowance_per_seat=3,
        commercial_use=True,
        offline_grace_days=3,
    ),
    "pro": EntitlementRecord(
        plan="pro",
        deployment_class="desktop",
        products=_codna_full("pro"),
        named_seat_limit=1,
        active_node_limit=1,
        concurrent_worker_limit=2,
        device_allowance_per_seat=3,
        commercial_use=True,
        offline_grace_days=3,
    ),
    # Team — shared server, at the self-service ceiling.
    "team": EntitlementRecord(
        plan="team",
        deployment_class="server",
        products=_codna_full("team"),
        named_seat_limit=SELF_SERVICE_MAX_SEATS,
        active_node_limit=SELF_SERVICE_MAX_NODES,
        concurrent_worker_limit=SELF_SERVICE_MAX_WORKERS,
        device_allowance_per_seat=3,
        commercial_use=True,
        offline_grace_days=3,
    ),
    # Enterprise — negotiated pools (0 = unspecified; concrete caps come from overrides),
    # paid offline rights.
    "enterprise": EntitlementRecord(
        plan="enterprise",
        deployment_class="server",
        products=_codna_full("enterprise"),
        named_seat_limit=0,
        active_node_limit=0,
        concurrent_worker_limit=0,
        device_allowance_per_seat=5,
        commercial_use=True,
        offline_grace_days=30,
    ),
}


def _coerce_plan(plan: object) -> str:
    """Normalize an OrgPlan enum / string to its internal plan name."""
    value = getattr(plan, "value", plan)
    name = str(value or "").strip().lower()
    return name if name in _TIER_CAPACITY else "free"


def _apply_overrides(record: EntitlementRecord, overrides: Mapping[str, object]) -> EntitlementRecord:
    """Apply admin/negotiated per-org overrides on top of a tier default (overrides win)."""
    changes: dict[str, object] = {}
    for key in (
        "deployment_class",
        "named_seat_limit",
        "active_node_limit",
        "concurrent_worker_limit",
        "device_allowance_per_seat",
        "offline_grace_days",
        "entitlement_version",
        # server/enterprise negotiated pools (Compute Units)
        "license_scope",
        "max_concurrent_units",
        "max_effective_vcpu",
        "vcpu_per_unit",
        "measurement_policy_version",
        "grace_policy_id",
    ):
        if key in overrides and overrides[key] is not None:
            changes[key] = overrides[key]
    for flag in ("commercial_use", "redistribution_allowed"):
        if flag in overrides and overrides[flag] is not None:
            changes[flag] = bool(overrides[flag])
    if overrides.get("products") is not None:
        changes["products"] = _coerce_products(overrides["products"])
    return replace(record, **changes)


def _coerce_products(value: object) -> dict[str, ProductGrant]:
    """Coerce an overrides ``products`` blob ({name: {tier, features}}) to ProductGrants."""
    out: dict[str, ProductGrant] = {}
    if not isinstance(value, Mapping):
        return out
    for name, spec in value.items():
        if not isinstance(spec, Mapping):
            continue
        feats = spec.get("features") or []
        features = (
            frozenset(str(f) for f in feats if str(f).strip())
            if isinstance(feats, list | tuple | set | frozenset)
            else frozenset()
        )
        out[str(name)] = ProductGrant(tier=str(spec.get("tier", "")), features=features)
    return out


def resolve_entitlement(
    plan: object, *, overrides: Mapping[str, object] | None = None
) -> EntitlementRecord:
    """Resolve an org's entitlement record from its plan tier (+ optional overrides).

    ``plan`` may be an OrgPlan enum or a plan-name string. ``overrides`` are admin/negotiated
    per-org adjustments (enterprise pools) applied authoritatively on top of the tier default.
    """
    plan_name = _coerce_plan(plan)
    record = _TIER_CAPACITY[plan_name]
    # concurrent_worker_limit is DYNAMIC — the single source of truth is plan_limits._WORKER_LIMITS,
    # so the per-device worker cap tracks the pricing page (Community 1 / Pro 5 / Team 20) without
    # editing this table. A per-org override (enterprise negotiation) still wins below.
    record = replace(record, concurrent_worker_limit=plan_limits.worker_limit(plan_name))
    if overrides:
        record = _apply_overrides(record, overrides)
    return record


def entitlement_for_org(org: object) -> EntitlementRecord:
    """Resolve the entitlement record for a loaded Organization row.

    Reads ``org.plan`` (and, when present, an ``entitlement_overrides`` mapping — persisted
    overrides storage lands in a later phase; this reads it opportunistically so enterprise
    negotiated pools flow through as soon as the column exists).
    """
    overrides = getattr(org, "entitlement_overrides", None)
    overrides = overrides if isinstance(overrides, Mapping) else None
    return resolve_entitlement(getattr(org, "plan", "free"), overrides=overrides)


def within_self_service_ceiling(record: EntitlementRecord) -> bool:
    """True if the record is sellable self-service; False ⇒ requires an enterprise contract.

    A ``0`` (unspecified / unbounded) cap is treated as *exceeding* the finite ceiling — an
    org with uncapped pools is, by definition, an enterprise/negotiated deal.
    """

    def _ok(value: int, ceiling: int) -> bool:
        return 1 <= value <= ceiling

    return (
        _ok(record.named_seat_limit, SELF_SERVICE_MAX_SEATS)
        and _ok(record.active_node_limit, SELF_SERVICE_MAX_NODES)
        and _ok(record.concurrent_worker_limit, SELF_SERVICE_MAX_WORKERS)
        and not record.redistribution_allowed
    )


def to_license_claims(record: EntitlementRecord) -> dict[str, object]:
    """Emit the v2 license-claim subset for this record.

    Merge into the device/license base payload (device_id, org_id, iss, exp, …) before
    signing. Field names + shapes match what ``apps/runtime/license.py`` parses back
    (``products`` = ``{name: {tier, features:[...]}}``); round-trip tested.
    """
    claims: dict[str, object] = {
        "ver": 2,
        "plan": record.plan,
        "deployment_class": record.deployment_class,
        "products": {
            name: {"tier": grant.tier, "features": sorted(grant.features)}
            for name, grant in record.products.items()
        },
        "named_seat_limit": record.named_seat_limit,
        "active_node_limit": record.active_node_limit,
        "concurrent_worker_limit": record.concurrent_worker_limit,
        "device_allowance_per_seat": record.device_allowance_per_seat,
        "commercial_use": record.commercial_use,
        "redistribution_allowed": record.redistribution_allowed,
        "offline_grace_days": record.offline_grace_days,
        "entitlement_version": record.entitlement_version,
    }
    # Server/Compute-Unit claims are emitted ONLY for a deployment-scope record, so every
    # existing per-device token keeps its exact claim shape (golden-stable). scope="deployment"
    # is the sole switch that activates the server enforcement path in the runtime.
    if record.is_deployment_scope():
        claims["license_scope"] = "deployment"
        claims["max_concurrent_units"] = record.max_concurrent_units
        if record.max_effective_vcpu:
            claims["max_effective_vcpu"] = record.max_effective_vcpu
        if record.vcpu_per_unit:
            claims["vcpu_per_unit"] = record.vcpu_per_unit
        if record.measurement_policy_version:
            claims["measurement_policy_version"] = record.measurement_policy_version
        if record.grace_policy_id:
            claims["grace_policy_id"] = record.grace_policy_id
    elif record.max_effective_vcpu:
        # DEVICE (desktop) scope: a per-node effective-vCPU ceiling lets the runtime refuse a desktop
        # license running on server-class hardware. Emitted ONLY when a positive ceiling is set (from
        # the Stripe SKU's max_effective_vcpu metadata), so every device token for a plan without the
        # key is byte-identical to before — the enforcement stays dark by absence of the claim.
        claims["max_effective_vcpu"] = record.max_effective_vcpu
    return claims
