"""
Auth endpoints:
  POST /auth/signup           — self-serve sign-up
  POST /auth/login            — login → JWT
  GET  /auth/verify           — verify email address
  POST /auth/forgot-password  — request password reset email
  POST /auth/reset-password   — complete password reset with token
"""
import secrets
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from jose import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.config import get_settings
from apps.api_server.db.session import get_db
from apps.api_server.schemas.auth import (
    LoginRequest,
    SignUpRequest,
    SignUpResponse,
    TokenResponse,
)
from apps.api_server.services.user_service import (
    create_user_and_org,
    get_user_by_email,
    hash_password,
    verify_password,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Auth"], prefix="/auth")
settings = get_settings()


@router.post(
    "/signup",
    response_model=SignUpResponse,
    status_code=201,
    summary="Create a new account",
    description=(
        "Self-serve signup. Creates an organization, user account, and first API key in one step. "
        "The raw API key is shown **once** in the response — store it securely."
    ),
)
async def signup(
    request: Request,
    payload: SignUpRequest,
    db: AsyncSession = Depends(get_db),
) -> SignUpResponse:
    response = await create_user_and_org(payload, db)
    logger.info(
        "signup_completed",
        email=payload.email,
        org_id=str(response.org.id),
        request_id=getattr(request.state, "request_id", None),
    )
    return response


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login and get a session token",
    description=(
        "Returns a JWT bearer token valid for 7 days. "
        "Use as `Authorization: Bearer <token>`."
    ),
)
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    user = await get_user_by_email(str(payload.email), db)

    if user is None or not verify_password(payload.password, user.password_hash):
        logger.warning("login_failed", email=payload.email)
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "invalid_credentials",
                    "message": "Invalid email or password.",
                    "request_id": getattr(request.state, "request_id", None),
                    "docs_url": "https://docs.decisionengine.io/errors/invalid_credentials",
                }
            },
        )

    expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_expire_minutes)
    token_data = {
        "sub": str(user.id),
        "org": str(user.org_id),
        "role": user.role.value,
        "exp": expire,
    }
    access_token = jwt.encode(
        token_data, settings.jwt_secret, algorithm=settings.jwt_algorithm
    )

    logger.info("login_success", user_id=str(user.id), org_id=str(user.org_id))

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",  # noqa: S106
        expires_in=settings.jwt_expire_minutes * 60,
    )


@router.get("/verify", summary="Verify email address via token link")
async def verify_email(
    token: str = Query(..., description="Verification token from email"),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Verify a user's email address. Token sent on signup."""
    from apps.api_server.models.user import User

    result = await db.execute(
        select(User).where(
            User.email_verification_token == token,  # type: ignore[attr-defined]
            User.email_verified == False,  # noqa: E712
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_token",
                    "message": "Invalid or expired verification token.",
                }
            },
        )
    # Check expiry
    expires = getattr(user, "email_verification_expires_at", None)
    if expires and datetime.now(UTC) > expires.replace(tzinfo=UTC):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "token_expired",
                    "message": "Verification link has expired. Request a new one.",
                }
            },
        )

    user.email_verified = True  # type: ignore[assignment]
    user.email_verification_token = None  # type: ignore[assignment]
    user.email_verification_expires_at = None  # type: ignore[assignment]
    await db.commit()

    logger.info("email_verified", user_id=str(user.id))
    return {"message": "Email verified successfully. You can now use the API."}


@router.post("/forgot-password", summary="Request a password reset email")
async def forgot_password(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Send a password reset link to the user's email."""
    from apps.api_server.models.user import User
    from apps.api_server.services.email_service import send_password_reset_email

    body = await request.json()
    email = body.get("email", "").lower().strip()
    if not email:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "missing_email",
                    "message": "Email required.",
                }
            },
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # Always return success (don't reveal if email exists)
    if user is not None:
        token = secrets.token_urlsafe(48)
        expires = datetime.now(UTC) + timedelta(minutes=15)
        user.password_reset_token = token  # type: ignore[assignment]
        user.password_reset_expires_at = expires  # type: ignore[assignment]
        await db.commit()
        try:
            await send_password_reset_email(email, token)
        except Exception as exc:
            logger.warning("password_reset_email_failed", email=email, error=str(exc))

    return {"message": "If an account with that email exists, a reset link has been sent."}


@router.post("/reset-password", summary="Complete password reset with token")
async def reset_password(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reset a user's password using a valid reset token."""
    from apps.api_server.models.user import User

    body = await request.json()
    token = body.get("token", "").strip()
    new_password = body.get("password", "").strip()

    if not token or not new_password:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "missing_fields",
                    "message": "token and password required.",
                }
            },
        )

    if len(new_password) < 8:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "password_too_short",
                    "message": "Password must be at least 8 characters.",
                }
            },
        )

    result = await db.execute(
        select(User).where(User.password_reset_token == token)  # type: ignore[attr-defined]
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_token",
                    "message": "Invalid or expired reset token.",
                }
            },
        )

    expires = getattr(user, "password_reset_expires_at", None)
    if expires and datetime.now(UTC) > expires.replace(tzinfo=UTC):
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "token_expired",
                    "message": "Reset link has expired. Request a new one.",
                }
            },
        )

    user.password_hash = hash_password(new_password)  # type: ignore[assignment]
    user.password_reset_token = None  # type: ignore[assignment]
    user.password_reset_expires_at = None  # type: ignore[assignment]
    await db.commit()

    logger.info("password_reset_completed", user_id=str(user.id))
    return {"message": "Password reset successfully. You can now log in."}
