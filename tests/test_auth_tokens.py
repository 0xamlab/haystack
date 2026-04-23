from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from jose import jwt

from apps.api_server.config import get_settings
from apps.api_server.services.auth_tokens import (
    AuthTokenError,
    issue_email_verification_token,
    issue_password_reset_token,
    verify_email_verification_token,
    verify_password_reset_token,
)


def test_email_verification_token_roundtrip() -> None:
    token = issue_email_verification_token("user-123", "Person@Example.com")

    claims = verify_email_verification_token(token)

    assert claims.subject == "user-123"
    assert claims.email == "person@example.com"


def test_password_reset_token_roundtrip() -> None:
    token = issue_password_reset_token("user-456", "Reset@Example.com")

    claims = verify_password_reset_token(token)

    assert claims.subject == "user-456"
    assert claims.email == "reset@example.com"


def test_email_verification_rejects_wrong_token_type() -> None:
    token = issue_password_reset_token("user-789", "wrong@example.com")

    with pytest.raises(AuthTokenError, match="Invalid token"):
        verify_email_verification_token(token)


def test_password_reset_rejects_expired_token() -> None:
    settings = get_settings()
    expired = jwt.encode(
        {
            "sub": "user-expired",
            "email": "expired@example.com",
            "typ": "password_reset",
            "exp": datetime.now(UTC) - timedelta(minutes=1),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    with pytest.raises(AuthTokenError, match="expired"):
        verify_password_reset_token(expired)
