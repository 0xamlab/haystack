"""Stateless auth token helpers for email verification and password reset."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import ExpiredSignatureError, JWTError, jwt

from apps.api_server.config import get_settings

EMAIL_VERIFICATION_HOURS = 24
PASSWORD_RESET_MINUTES = 15
EMAIL_VERIFICATION_KIND = "email_verification"
RESET_KIND = "password_reset"


@dataclass(frozen=True)
class AuthTokenClaims:
    subject: str
    email: str


class AuthTokenError(ValueError):
    """Raised when a stateless auth token is invalid or expired."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def issue_email_verification_token(user_id: str, email: str) -> str:
    return _issue_token(
        subject=user_id,
        email=email,
        token_type=EMAIL_VERIFICATION_KIND,
        expires_at=datetime.now(UTC) + timedelta(hours=EMAIL_VERIFICATION_HOURS),
    )


def verify_email_verification_token(token: str) -> AuthTokenClaims:
    return _decode_token(token, expected_type=EMAIL_VERIFICATION_KIND)


def issue_password_reset_token(user_id: str, email: str) -> str:
    return _issue_token(
        subject=user_id,
        email=email,
        token_type=RESET_KIND,
        expires_at=datetime.now(UTC) + timedelta(minutes=PASSWORD_RESET_MINUTES),
    )


def verify_password_reset_token(token: str) -> AuthTokenClaims:
    return _decode_token(token, expected_type=RESET_KIND)


def _issue_token(
    *,
    subject: str,
    email: str,
    token_type: str,
    expires_at: datetime,
) -> str:
    settings = get_settings()
    payload = {
        "sub": subject,
        "email": email.lower(),
        "typ": token_type,
        "exp": expires_at,
    }
    return str(jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm))


def _decode_token(token: str, *, expected_type: str) -> AuthTokenClaims:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except ExpiredSignatureError as exc:
        raise AuthTokenError(
            "token_expired",
            "The token has expired. Request a new link.",
        ) from exc
    except JWTError as exc:
        raise AuthTokenError(
            "invalid_token",
            "Invalid token.",
        ) from exc

    token_type = str(payload.get("typ", ""))
    if token_type != expected_type:
        raise AuthTokenError("invalid_token", "Invalid token.")

    subject = str(payload.get("sub", "")).strip()
    email = str(payload.get("email", "")).strip().lower()
    if not subject or not email:
        raise AuthTokenError("invalid_token", "Invalid token.")

    return AuthTokenClaims(subject=subject, email=email)
