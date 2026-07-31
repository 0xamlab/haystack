"""`/billing/plans` must price THIS deployment's brand, and refuse to price anyone else's.

Measured against the live host on 2026-07-31: `GET https://api.algenta.ai/billing/plans` returned
`{"app":"codna","plans":[{"plan":"pro","name":"Codna Pro",...}]}` — an Algenta-branded host publicly
advertising Codna's catalogue, unauthenticated. The cause was the signature default
`async def public_plans(app: str = "codna")`. `?app=<brand>` made it worse: the same host also
priced Telys, Cohenta and SQAI on request, including five `*_server` SKUs that are not on the public
pricing card at all.

Two separate defects, so two separate properties are pinned here:
  1. the DEFAULT must be this deployment's own brand (`ALGENTA_PRODUCT`, else the brand that owns the
     `Host` the request arrived on, per the registry's `public_api_base`);
  2. a branded host must REFUSE another brand — not silently answer it. Cross-brand pricing stays
     available only where the request arrived on no brand's host (the shared engine's own address),
     which is where a multi-brand portal belongs.

These are pure-unit: the handler is called directly and the Stripe catalogue is stubbed, so no DB,
no HTTP and no network are involved.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from apps.api_server.routers import billing
from apps.api_server.services import product_registry as pr


class _Settings:
    """Only the field the handler reads; a real Settings would drag in the whole env."""

    def __init__(self, deployment_product: str | None) -> None:
        self.deployment_product = deployment_product


def _request(host: str | None, *, forwarded_host: str | None = None) -> Request:
    headers = [(b"host", host.encode())] if host else []
    if forwarded_host is not None:
        headers.append((b"x-forwarded-host", forwarded_host.encode()))
    return Request({"type": "http", "method": "GET", "headers": headers})


@pytest.fixture(autouse=True)
def _no_stripe(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Record which brand the catalogue was asked for, and never call Stripe."""
    asked: list[str] = []

    async def _fake_list_plans(app: str, **_: Any) -> list[dict[str, Any]]:
        asked.append(app)
        return [{"plan": f"{app}_pro"}]

    monkeypatch.setattr(
        "apps.api_server.services.stripe_catalog.list_plans", _fake_list_plans, raising=True
    )
    return asked


def _call(
    *,
    app: str | None,
    deployment_product: str | None,
    monkeypatch: pytest.MonkeyPatch,
    host: str | None = "engine.internal",
    forwarded_host: str | None = None,
) -> dict[str, Any]:
    monkeypatch.setattr(billing, "_get_settings", lambda: _Settings(deployment_product))
    request = _request(host, forwarded_host=forwarded_host)
    return asyncio.run(billing.public_plans(request, app=app))


# ── The default ────────────────────────────────────────────────────────────────


def test_omitted_brand_resolves_to_this_deployments_product(monkeypatch, _no_stripe):
    """THE REGRESSION. An Algenta deployment must not answer with Codna's catalogue."""
    out = _call(app=None, deployment_product="algenta", monkeypatch=monkeypatch)
    assert out["app"] == "algenta"
    assert _no_stripe == ["algenta"], "the catalogue was priced for the wrong brand"
    assert "codna" not in str(out)


def test_a_brand_host_resolves_its_own_brand_with_no_configuration(monkeypatch, _no_stripe):
    """The fix must not depend on an env var being remembered on every deployment.

    Unconfigured, the live host answered Codna. The `Host` a request arrived on is the one per-request
    signal that says which brand a public, pre-auth caller is talking to, and the registry already
    stores each brand's host as `public_api_base` — so `api.algenta.ai` resolves to `algenta` before
    anyone sets anything.
    """
    out = _call(app=None, deployment_product=None, monkeypatch=monkeypatch, host="api.algenta.ai")
    assert out["app"] == "algenta"
    assert _no_stripe == ["algenta"]


def test_the_host_signal_is_derived_for_every_registered_brand(monkeypatch, _no_stripe):
    """Every brand's own host prices that brand — derived from the registry, not a second host map."""
    for cfg in pr.all_products():
        host = cfg.public_api_base.split("://", 1)[-1]
        out = _call(app=None, deployment_product=None, monkeypatch=monkeypatch, host=host)
        assert out["app"] == cfg.id, f"{host} priced {out['app']}"


def test_an_edge_that_rewrites_host_still_pins_the_brand(monkeypatch, _no_stripe):
    """A proxy that replaces `Host` with an internal origin name would otherwise un-pin the deployment
    and restore the exact wrong answer this fix removes, so the forwarded host is the last resort."""
    out = _call(
        app=None,
        deployment_product=None,
        monkeypatch=monkeypatch,
        host="algenta-api.internal:8080",
        forwarded_host="api.algenta.ai",
    )
    assert out["app"] == "algenta"

    with pytest.raises(HTTPException) as excinfo:
        _call(
            app="codna",
            deployment_product=None,
            monkeypatch=monkeypatch,
            host="algenta-api.internal:8080",
            forwarded_host="api.algenta.ai, api.codna.ai",
        )
    assert excinfo.value.detail["error"]["code"] == "product_not_served"


def test_the_real_host_wins_over_a_forwarded_one(monkeypatch, _no_stripe):
    """`Host` is what the request actually arrived on; the forwarded header only fills a gap."""
    out = _call(
        app=None,
        deployment_product=None,
        monkeypatch=monkeypatch,
        host="api.algenta.ai",
        forwarded_host="api.codna.ai",
    )
    assert out["app"] == "algenta"


def test_configuration_wins_over_the_host_header(monkeypatch, _no_stripe):
    """`Host` is caller-supplied, so an explicitly configured deployment must not be talked out of
    its own edition by a spoofed header."""
    out = _call(
        app=None, deployment_product="algenta", monkeypatch=monkeypatch, host="api.codna.ai"
    )
    assert out["app"] == "algenta"


def test_omitted_brand_on_an_unbranded_unconfigured_host_keeps_the_legacy_default(
    monkeypatch, _no_stripe
):
    """Unset config + a non-brand host must not fail closed on a public pricing page, and must not
    guess a new brand.

    The legacy default is whichever product owns the unprefixed plan namespace — derived, so this
    test cannot pass by agreeing with a second hardcoded copy of the id.
    """
    out = _call(app=None, deployment_product=None, monkeypatch=monkeypatch)
    assert out["app"] == pr.legacy_default_product()
    assert _no_stripe == [pr.legacy_default_product()]


# ── The pin ────────────────────────────────────────────────────────────────────


def test_a_branded_host_refuses_another_brands_catalogue(monkeypatch, _no_stripe):
    """THE LEAK THAT WAS LIVE. `?app=` must not turn the Algenta host into Telys's price list."""
    with pytest.raises(HTTPException) as excinfo:
        _call(app="telys", deployment_product="algenta", monkeypatch=monkeypatch)
    assert excinfo.value.status_code == 404
    assert excinfo.value.detail["error"]["code"] == "product_not_served"
    assert _no_stripe == [], "Stripe must not be called for a brand this host does not serve"


def test_no_registered_brand_can_be_priced_off_the_algenta_host(monkeypatch, _no_stripe):
    """Exhaustive: for a host pinned to Algenta, only Algenta prices. No brand is forgotten as new
    rows are added to the registry."""
    for cfg in pr.all_products():
        if cfg.id == "algenta":
            out = _call(
                app=cfg.id,
                deployment_product=None,
                monkeypatch=monkeypatch,
                host="api.algenta.ai",
            )
            assert out["app"] == "algenta"
            continue
        with pytest.raises(HTTPException) as excinfo:
            _call(
                app=cfg.id,
                deployment_product=None,
                monkeypatch=monkeypatch,
                host="api.algenta.ai",
            )
        assert excinfo.value.status_code == 404, cfg.id
        assert excinfo.value.detail["error"]["code"] == "product_not_served", cfg.id
    assert _no_stripe == ["algenta"]


def test_naming_the_hosts_own_brand_explicitly_still_works(monkeypatch, _no_stripe):
    """Existing callers send `?app=<their brand>`; pinning must not break the correct request."""
    out = _call(app="algenta", deployment_product="algenta", monkeypatch=monkeypatch)
    assert out["app"] == "algenta"
    assert _no_stripe == ["algenta"]


def test_the_shared_accounts_portals_exact_call_pattern_works_for_every_brand(
    monkeypatch, _no_stripe
):
    """The universal account portal is the real consumer, and its pattern must not be broken.

    `accounts.thyn.ai` serves every edition from one codebase. Each brand's config carries its OWN
    engine host (`https://api.${slug}.ai`, derived in the portal's app registry), and the billing
    page fetches `${app.apiUrl}/billing/plans?app=${app.slug}` — so Host and `?app=` always name the
    SAME brand. That is exactly the case the pin admits, which is why the pin is derived from `Host`
    rather than from configuration.

    This test exists because the coupling is across two repositories: the portal derives
    `api.<slug>.ai` and this engine's registry stores `public_api_base` per brand. If either side
    renames a host, the portal's pricing page starts 404-ing with `product_not_served` and the
    failure would look like a billing bug rather than a hostname mismatch.
    """
    for cfg in pr.all_products():
        host = cfg.public_api_base.split("://", 1)[-1]
        out = _call(app=cfg.id, deployment_product=None, monkeypatch=monkeypatch, host=host)
        assert out["app"] == cfg.id, (
            f"the portal's own pattern failed for {cfg.id}: Host {host} with ?app={cfg.id}"
        )


def test_setting_deployment_product_on_a_multi_brand_host_breaks_the_other_brands(
    monkeypatch, _no_stripe
):
    """Pinning by CONFIGURATION on a shared host is wrong, and this records why.

    `ALGENTA_PRODUCT` deliberately wins over `Host`, so that a spoofed header cannot talk a
    single-brand deployment out of its own edition. The consequence is that setting it on a host
    serving SEVERAL brands forces one brand for every request and refuses the rest — which would
    break the portal's pricing page for every other edition.

    Asserted rather than left as a comment because "set ALGENTA_PRODUCT on the api app" reads like
    obvious hardening, and it is the opposite while one Fly app fronts more than one brand alias.
    The Host-derived pin already covers that case correctly.
    """
    others = [c.id for c in pr.all_products() if c.id != "algenta"]
    assert others, "registry should hold more than one brand"
    for brand in others:
        host = pr.get_product(brand).public_api_base.split("://", 1)[-1]
        with pytest.raises(HTTPException) as excinfo:
            _call(app=brand, deployment_product="algenta", monkeypatch=monkeypatch, host=host)
        assert excinfo.value.status_code == 404, brand
        assert excinfo.value.detail["error"]["code"] == "product_not_served", brand
    # ...while the SAME requests succeed with it unset, which is the shipped default.
    for brand in others:
        host = pr.get_product(brand).public_api_base.split("://", 1)[-1]
        out = _call(app=brand, deployment_product=None, monkeypatch=monkeypatch, host=host)
        assert out["app"] == brand


def test_cross_brand_pricing_survives_on_the_shared_engines_own_host(monkeypatch, _no_stripe):
    """One engine deliberately serves several brands. A request that arrived on no brand's host is
    the multi-brand portal case, and must keep working — otherwise the fix breaks the pricing page it
    is meant to correct."""
    for cfg in pr.all_products():
        out = _call(app=cfg.id, deployment_product=None, monkeypatch=monkeypatch)
        assert out["app"] == cfg.id


# ── Unknown / misconfigured brands ─────────────────────────────────────────────


def test_unregistered_brand_is_rejected_not_answered_empty(monkeypatch, _no_stripe):
    """A 200 with `plans: []` reads as "this brand has no paid tiers", not "no such brand".

    It also closed an unbounded-growth path: the brand string was passed straight into the Stripe
    catalogue cache, so every distinct value bought a permanent cache entry and a live Stripe call
    from an unauthenticated endpoint.
    """
    with pytest.raises(HTTPException) as excinfo:
        _call(app="not-a-product", deployment_product="algenta", monkeypatch=monkeypatch)
    assert excinfo.value.status_code == 400
    detail = excinfo.value.detail
    assert detail["error"]["code"] == "invalid_product"
    # The message must name the real options, so a caller can fix the request without the source.
    for cfg in pr.all_products():
        assert cfg.id in detail["error"]["message"]
    assert _no_stripe == [], "Stripe must not be called for an unknown brand"


def test_an_unknown_brand_is_a_typo_not_a_forbidden_brand(monkeypatch, _no_stripe):
    """Order of checks matters: `?app=algentaa` must read as a typo (400 invalid_product), not as
    "this host does not serve that brand" (404), or a caller cannot tell what to fix."""
    with pytest.raises(HTTPException) as excinfo:
        _call(app="algentaa", deployment_product="algenta", monkeypatch=monkeypatch)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail["error"]["code"] == "invalid_product"


def test_a_misconfigured_deployment_product_is_rejected_loudly(monkeypatch, _no_stripe):
    """A typo in ALGENTA_PRODUCT must surface, not silently fall back to another brand's catalogue.

    Falling back would reintroduce exactly the defect this file exists to prevent, only harder to
    see: the operator would believe the host was configured.
    """
    with pytest.raises(HTTPException) as excinfo:
        _call(app=None, deployment_product="algentaa", monkeypatch=monkeypatch)
    assert excinfo.value.status_code == 400
    assert excinfo.value.detail["error"]["code"] == "invalid_product"


def test_brand_matching_is_case_and_space_insensitive(monkeypatch, _no_stripe):
    out = _call(app="  ALGENTA  ", deployment_product=None, monkeypatch=monkeypatch)
    assert out["app"] == "algenta"


def test_host_matching_ignores_port_and_case(monkeypatch, _no_stripe):
    out = _call(
        app=None, deployment_product=None, monkeypatch=monkeypatch, host="API.Algenta.AI:443"
    )
    assert out["app"] == "algenta"


@pytest.mark.parametrize(
    "host",
    ["", "localhost:8000", "127.0.0.1:8000", "[::1]:8000", "algenta-api.fly.dev", "example.com"],
)
def test_non_brand_hosts_pin_nothing(monkeypatch, _no_stripe, host):
    """A non-brand host must resolve to "no brand", never to a brand by accident — an internal name
    that matched a brand would pin the shared engine to one catalogue."""
    assert pr.product_for_public_api_host(host) is None
    out = _call(app="telys", deployment_product=None, monkeypatch=monkeypatch, host=host)
    assert out["app"] == "telys"


def test_the_error_envelope_shape_is_unchanged(monkeypatch, _no_stripe):
    """Clients parse `{"error": {"code", "message"}}`; both new refusals must keep that shape."""
    for app, expected in (("not-a-product", "invalid_product"), ("telys", "product_not_served")):
        with pytest.raises(HTTPException) as excinfo:
            _call(app=app, deployment_product="algenta", monkeypatch=monkeypatch)
        detail = excinfo.value.detail
        assert set(detail) == {"error"}
        assert detail["error"]["code"] == expected
        assert isinstance(detail["error"]["message"], str) and detail["error"]["message"]
