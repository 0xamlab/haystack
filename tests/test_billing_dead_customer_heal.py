"""Self-heal of a dead Stripe customer (test-mode leftover after the live flip).

The safety-critical invariant: a paid org is downgraded ONLY on a definitive
'customer does not exist' (404 resource_missing) — never on a transient Stripe
error (402/409/429/5xx), which would otherwise wrongly strip a paying customer's
plan during a Stripe outage.
"""

from __future__ import annotations

import pytest

from apps.api_server.services import stripe_service
from apps.api_server.services.stripe_service import (
    StripeCustomerMissingError,
    _is_resource_missing,
    customer_exists,
)


class _Resp:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self._body = body

    def json(self) -> dict:
        return self._body


@pytest.mark.parametrize(
    "resp,expected",
    [
        (_Resp(404, {"error": {"code": "resource_missing", "param": "customer"}}), True),
        (_Resp(404, {"error": {"message": "No such customer: cus_x"}}), True),
        (_Resp(500, {"error": {"code": "api_error"}}), False),
        (_Resp(429, {"error": {"code": "rate_limit"}}), False),
        (_Resp(402, {"error": {"code": "card_declined"}}), False),
        (_Resp(409, {"error": {"code": "resource_already_exists"}}), False),
        (_Resp(200, {"id": "cus_x"}), False),
    ],
)
def test_is_resource_missing_only_on_definitive_404(resp, expected):
    assert _is_resource_missing(resp) is expected


def test_missing_error_carries_customer_id():
    err = StripeCustomerMissingError("cus_abc")
    assert err.customer_id == "cus_abc"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "resp,expected",
    [
        (_Resp(200, {"id": "cus_x"}), True),  # exists
        (_Resp(200, {"id": "cus_x", "deleted": True}), False),  # deleted in dashboard
        (_Resp(404, {"error": {"code": "resource_missing"}}), False),  # gone
        (_Resp(500, {"error": {"code": "api_error"}}), None),  # transient → indeterminate
        (_Resp(429, {"error": {"code": "rate_limit"}}), None),  # throttled → indeterminate
    ],
)
async def test_customer_exists_maps_outcomes(monkeypatch, resp, expected):
    async def _fake_request(**_kwargs):
        return resp

    monkeypatch.setattr(stripe_service, "stripe_api_request", _fake_request)
    assert await customer_exists("cus_x") is expected


@pytest.mark.asyncio
async def test_customer_exists_indeterminate_on_egress_error(monkeypatch):
    async def _boom(**_kwargs):
        raise RuntimeError("egress blocked")

    monkeypatch.setattr(stripe_service, "stripe_api_request", _boom)
    # Never False on an exception — a blocked/errored probe must not trigger a downgrade.
    assert await customer_exists("cus_x") is None
