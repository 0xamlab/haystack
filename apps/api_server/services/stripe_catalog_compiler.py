"""Stripe Catalog Compiler — the commercial desired-state → validated, immutable release.

Stripe is the source of truth for all commercial config (prices, unit size, quantity minimums,
grace/burst, features), but the runtime NEVER trusts raw Stripe metadata: this compiler parses
the ``thyn_license_v1`` metadata against a strict typed schema + hard safety bounds and produces
an immutable :class:`CatalogRelease` (with a ``policy_hash``). Downstream, ``entitlement_snapshot``
resolves a customer against a release and the signer emits signed claims — so a Stripe mistake or
compromise can never weaken a security invariant or reach a runtime unvalidated.

Pure + fetch-injectable: :func:`compile_catalog` takes already-fetched Stripe Product/Price
dicts (as the Stripe REST API returns them), so it is fully unit-testable with fixtures and has
no live-Stripe or network dependency. :func:`fetch_and_compile` is the thin async wrapper that
pulls the objects via the existing ``stripe_service`` request path.

Security invariants are NOT compilable here (RS256-only verify, Community floor, PoP, non-brick
state machine live in code) — this module only shapes commercial values within safe ranges.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field

LICENSE_SCHEMA = "thyn_license_v1"

_VALID_LICENSE_SCOPES = frozenset({"device", "deployment"})
_VALID_LICENSE_MODES = frozenset({"workstation", "pinned", "floating", "ci", "oem"})
_VALID_QTY_METRICS = frozenset({"device", "compute_unit"})
_VALID_DEPLOY_CLASSES = frozenset(
    {"workstation", "production_server", "nonproduction_server", "ci_ephemeral", "oem_embedded"}
)
_KNOWN_PRODUCTS = frozenset({"algenta", "codna", "telys", "sqai", "cohenta"})

# Hard safety bounds — a compiled value outside these is a config error, never silently clamped.
_MAX_VCPU_PER_UNIT = 256
_MAX_UNITS = 1_000_000
_MAX_WORKERS_PER_UNIT = 4_096


class CatalogCompileError(ValueError):
    """The Stripe catalog failed validation — the candidate release is rejected (last-known-good
    is retained by the caller). ``violations`` lists every problem found (fail-safe, all at once)."""

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__("catalog compile rejected:\n  - " + "\n  - ".join(violations))


@dataclass(frozen=True)
class CompiledSku:
    """One validated, purchasable SKU — the commercial policy for a (product, edition), typed."""

    sku_key: str
    product: str
    edition: str
    license_scope: str  # device | deployment
    license_mode: str  # workstation | pinned | floating | ci | oem
    qty_metric: str  # device | compute_unit
    deploy_class: str
    vcpu_per_unit: int
    workers_per_unit: int
    measurement_policy_version: str
    grace_policy_id: str
    qty_min: int
    qty_max: int
    price_amount_cents: int  # native Price.unit_amount (0 = free/quote bookend)
    currency: str
    interval: str  # month | year | "" (one-time / bookend)
    lookup_key: str
    entitlement_features: tuple[str, ...] = ()


@dataclass(frozen=True)
class CatalogRelease:
    """An immutable, validated compilation of the Stripe catalog + its content hash."""

    release: str  # the lic_release tag (from the catalog-control product / product metadata)
    skus: dict[str, CompiledSku]
    policy_hash: str

    def sku(self, sku_key: str) -> CompiledSku | None:
        return self.skus.get(sku_key)


# ── coercion helpers (Stripe metadata is ALWAYS strings) ──────────────────────


def _as_int(value: object, default: int = 0) -> int | None:
    if value is None or value == "":
        return default
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None  # None signals a parse error (distinct from a real 0)


def _as_str(value: object, default: str = "") -> str:
    return str(value).strip() if value is not None else default


def _price_meta(price: dict) -> dict:
    return price.get("metadata") or {}


def _product_of(price: dict) -> dict:
    prod = price.get("product")
    return prod if isinstance(prod, dict) else {}


# ── the compiler ──────────────────────────────────────────────────────────────


def _compile_sku(price: dict, violations: list[str]) -> CompiledSku | None:
    """Compile ONE Stripe price+product into a CompiledSku, appending any violations. Returns None
    when the price is not a licensing SKU (no thyn_license_v1 metadata) — that's not an error."""
    prod = _product_of(price)
    pmeta = prod.get("metadata") or {}
    if pmeta.get("lic_schema") != LICENSE_SCHEMA:
        return None  # not a licensing product — skip silently

    sku_key = _as_str(pmeta.get("sku_key"))
    where = f"product {prod.get('id', '?')} (sku_key={sku_key or '<missing>'})"

    if not sku_key:
        violations.append(f"{where}: missing sku_key")
    product = _as_str(pmeta.get("product_key"))
    if product not in _KNOWN_PRODUCTS:
        violations.append(f"{where}: unknown product_key {product!r} (not in {sorted(_KNOWN_PRODUCTS)})")
    scope = _as_str(pmeta.get("license_scope"), "device")
    if scope not in _VALID_LICENSE_SCOPES:
        violations.append(f"{where}: invalid license_scope {scope!r}")
    mode = _as_str(pmeta.get("license_mode"), "workstation")
    if mode not in _VALID_LICENSE_MODES:
        violations.append(f"{where}: invalid license_mode {mode!r}")
    qty_metric = _as_str(pmeta.get("qty_metric"), "device")
    if qty_metric not in _VALID_QTY_METRICS:
        violations.append(f"{where}: invalid qty_metric {qty_metric!r}")
    deploy_class = _as_str(pmeta.get("deploy_class"), "workstation")
    if deploy_class not in _VALID_DEPLOY_CLASSES:
        violations.append(f"{where}: invalid deploy_class {deploy_class!r}")

    # deployment scope MUST meter compute_units; device scope MUST meter devices — a mismatch
    # is a fleet/pricing hole.
    if scope == "deployment" and qty_metric != "compute_unit":
        violations.append(f"{where}: deployment scope must use qty_metric=compute_unit")
    if scope == "device" and qty_metric != "device":
        violations.append(f"{where}: device scope must use qty_metric=device")

    vcpu_per_unit = _as_int(pmeta.get("vcpu_per_unit"), 4)
    if vcpu_per_unit is None or not (1 <= vcpu_per_unit <= _MAX_VCPU_PER_UNIT):
        violations.append(f"{where}: vcpu_per_unit out of range 1..{_MAX_VCPU_PER_UNIT}: {pmeta.get('vcpu_per_unit')!r}")
        vcpu_per_unit = 4
    workers_per_unit = _as_int(pmeta.get("workers_per_unit"), 0)
    if workers_per_unit is None or not (0 <= workers_per_unit <= _MAX_WORKERS_PER_UNIT):
        violations.append(f"{where}: workers_per_unit out of range: {pmeta.get('workers_per_unit')!r}")
        workers_per_unit = 0

    qty_min = _as_int(_price_meta(price).get("qty_min"), 1)
    qty_max = _as_int(_price_meta(price).get("qty_max"), _MAX_UNITS)
    if qty_min is None or qty_max is None or qty_min < 0 or qty_max < 1 or qty_min > qty_max:
        violations.append(f"{where}: invalid qty_min/qty_max ({_price_meta(price).get('qty_min')!r}/{_price_meta(price).get('qty_max')!r})")
        qty_min, qty_max = 1, _MAX_UNITS

    unit_amount = _as_int(price.get("unit_amount"), 0) or 0
    currency = _as_str(price.get("currency"), "usd").lower()
    recurring = price.get("recurring") or {}
    interval = _as_str(recurring.get("interval")) if isinstance(recurring, dict) else ""
    lookup_key = _as_str(price.get("lookup_key"))

    features = tuple(
        f.strip() for f in _as_str(pmeta.get("entitlement_features")).split(",") if f.strip()
    )

    return CompiledSku(
        sku_key=sku_key,
        product=product,
        edition=_as_str(pmeta.get("edition_key")),
        license_scope=scope,
        license_mode=mode,
        qty_metric=qty_metric,
        deploy_class=deploy_class,
        vcpu_per_unit=vcpu_per_unit,
        workers_per_unit=workers_per_unit,
        measurement_policy_version=_as_str(pmeta.get("measure_policy"), "cgroup-v1"),
        grace_policy_id=_as_str(pmeta.get("grace_policy"), "community-floor-v1"),
        qty_min=qty_min,
        qty_max=qty_max,
        price_amount_cents=unit_amount,
        currency=currency,
        interval=interval,
        lookup_key=lookup_key,
        entitlement_features=features,
    )


def _policy_hash(skus: dict[str, CompiledSku]) -> str:
    canonical = json.dumps(
        {k: asdict(v) for k, v in sorted(skus.items())}, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compile_catalog(prices: list[dict], *, release: str = "") -> CatalogRelease:
    """Compile already-fetched Stripe prices (each with an expanded ``product``) into an immutable
    :class:`CatalogRelease`. Raises :class:`CatalogCompileError` with EVERY violation on any problem
    (so a partial/invalid catalog can never activate). Non-licensing prices are ignored.

    ``prices`` mirrors ``GET /v1/prices?expand[]=data.product`` — the same shape
    ``stripe_service`` already fetches for the display catalog.
    """
    violations: list[str] = []
    skus: dict[str, CompiledSku] = {}
    test_live_mix: set[bool] = set()

    for price in prices:
        if "livemode" in price:
            test_live_mix.add(bool(price.get("livemode")))
        compiled = _compile_sku(price, violations)
        if compiled is None:
            continue
        if compiled.sku_key in skus:
            violations.append(f"duplicate sku_key {compiled.sku_key!r} (two prices/products claim it)")
            continue
        skus[compiled.sku_key] = compiled

    if len(test_live_mix) > 1:
        violations.append("live/test mode mixing: the catalog references both live and test objects")

    if violations:
        raise CatalogCompileError(violations)

    return CatalogRelease(release=release, skus=skus, policy_hash=_policy_hash(skus))


async def fetch_and_compile(*, release: str = "") -> CatalogRelease:
    """Async wrapper: pull active prices (with expanded products) from Stripe and compile them.

    Thin — all logic + validation is in :func:`compile_catalog`. Kept separate so the compiler
    itself stays pure and fully unit-testable without live Stripe."""
    from apps.api_server.services.stripe_service import _stripe_headers, stripe_api_request

    resp = await stripe_api_request(
        method="GET",
        path="/v1/prices?active=true&limit=100&expand[]=data.product",
        surface="catalog_compile",
        headers=_stripe_headers(),
    )
    data = resp.json().get("data", []) if resp.status_code < 400 else []
    return compile_catalog(data, release=release)
