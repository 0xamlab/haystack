"""Online licenses are short-lived + renewal-gated (anti "pay once and leave").

The online mint (`_issue_license_jwt`) must cap every license at the short rolling renewal window,
so a monthly subscriber who stops paying can't keep a long-lived token — the node must re-mint via
/v1/license/renew, which reflects the current org plan. Air-gapped/offline enterprise mints use a
separate long-lived path and are unaffected.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime, timedelta

from apps.api_server.services.device_service import (
    _GRACE_DAYS,
    _LICENSE_RENEWAL_TTL_DAYS,
    _issue_license_jwt,
)


def _claims(token: str) -> dict:
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def _ttl_days(token: str) -> float:
    c = _claims(token)
    return (c["expires_at"] - c["issued_at"]) / 86400


def test_no_key_expiry_capped_to_rolling_window() -> None:
    # Previously defaulted to 365 days — the pay-once-leave hole.
    token = _issue_license_jwt("dev1", "pfx", "algenta_pro", 1, str(uuid.uuid4()))
    assert abs(_ttl_days(token) - _LICENSE_RENEWAL_TTL_DAYS) < 1
    assert _claims(token)["grace_days"] == _GRACE_DAYS


def test_far_key_expiry_capped_to_rolling_window() -> None:
    token = _issue_license_jwt(
        "dev2", "pfx", "algenta_pro", 1, str(uuid.uuid4()),
        api_key_expires_at=datetime.now(UTC) + timedelta(days=300),
    )
    assert abs(_ttl_days(token) - _LICENSE_RENEWAL_TTL_DAYS) < 1


def test_near_key_expiry_is_honored() -> None:
    # A subscription period end inside the window shortens the license further.
    token = _issue_license_jwt(
        "dev3", "pfx", "algenta_pro", 1, str(uuid.uuid4()),
        api_key_expires_at=datetime.now(UTC) + timedelta(days=10),
    )
    assert abs(_ttl_days(token) - 10) < 1


def test_rolling_window_is_short() -> None:
    # Guardrail: the online window must stay short enough to be renewal-gated (not a de-facto year).
    assert 1 <= _LICENSE_RENEWAL_TTL_DAYS <= 45
