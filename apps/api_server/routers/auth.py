"""
Auth endpoints:
  POST /auth/signup           — self-serve sign-up
  POST /auth/login            — login → JWT
  GET  /auth/verify           — verify email address
  POST /auth/forgot-password  — request password reset email
  POST /auth/reset-password   — complete password reset with token
"""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
import jwt  # PyJWT
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_server.config import SettingsProxy, get_settings
from apps.api_server.db.session import get_db
from apps.api_server.middleware.auth import get_redis
from apps.api_server.services.audit_service import get_client_ip
from apps.api_server.services.auth_service import invalidate_user_api_key_caches
from apps.api_server.services.captcha import verify_turnstile
from apps.api_server.services.quota_service import check_named_rate_limit
from apps.api_server.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    ResetPasswordRequest,
    SignUpRequest,
    SignUpResponse,
    TokenResponse,
)
from apps.api_server.services.auth_tokens import (
    AuthTokenError,
    issue_password_reset_token,
    verify_email_verification_token,
    verify_password_reset_token,
)
from apps.api_server.services.user_service import (
    create_user_and_org,
    get_user_by_email,
    hash_password,
    verify_password,
)

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["Auth"], prefix="/auth")
settings = SettingsProxy()


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
async def _enforce_daily_email_signup_cap(email: str, redis: object, settings: object) -> None:
    """Cap org-creations per email per day (multi-account abuse). Best-effort — a Redis hiccup
    falls back to allowing (the per-IP limit + captcha remain the backstop)."""
    limit = int(getattr(settings, "signup_max_per_day_per_email", 0))
    if limit <= 0:
        return
    email_hash = hashlib.sha256(email.strip().lower().encode()).hexdigest()[:32]
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    key = f"signup_email_day:{email_hash}:{day}"
    try:
        count = await redis.incr(key)  # type: ignore[attr-defined]
        if count == 1:
            await redis.expire(key, 86400)  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("signup_daily_cap_unavailable", error=str(exc))
        return
    if count > limit:
        logger.warning("signup_blocked_daily_email_cap", email=email, count=count, limit=limit)
        raise HTTPException(
            status_code=429,
            detail={
                "error": {
                    "code": "signup_limit_exceeded",
                    "message": "This email has reached the daily signup limit. Try again tomorrow.",
                    "retry_after_seconds": 86400,
                }
            },
            headers={"Retry-After": "86400"},
        )


async def signup(
    request: Request,
    payload: SignUpRequest,
    db: AsyncSession = Depends(get_db),
    redis: object = Depends(get_redis),
) -> SignUpResponse:
    settings = get_settings()
    client_ip = get_client_ip(request) or "unknown"

    # 1) Burst protection: per-IP signups/minute (fails open if Redis is down).
    await check_named_rate_limit(
        client_ip,
        redis,
        key_prefix="signup_ip",
        limit_per_minute=settings.signup_rate_limit_per_minute,
        request_state=getattr(request, "state", None),
        error_code="signup_rate_limited",
        error_message="Too many signups from this network. Please try again in a minute.",
        log_context={"ip": client_ip},
    )
    # 2) Multi-account protection: per-email org-creations/day.
    await _enforce_daily_email_signup_cap(payload.email, redis, settings)
    # 3) Bot protection: Cloudflare Turnstile (no-op unless TURNSTILE_SECRET_KEY is configured).
    token = request.headers.get("CF-Turnstile-Response") or request.headers.get("X-Turnstile-Token")
    if not await verify_turnstile(token, client_ip):
        logger.warning("signup_blocked_captcha", ip=client_ip, email=payload.email)
        raise HTTPException(
            status_code=403,
            detail={
                "error": {
                    "code": "captcha_required",
                    "message": "Captcha verification failed. Complete the challenge and retry.",
                }
            },
        )

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
        "Returns a JWT bearer token valid for 7 days. Use as `Authorization: Bearer <token>`."
    ),
)
async def login(
    request: Request,
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
    redis: object = Depends(get_redis),
) -> TokenResponse:
    # Brute-force protection: throttle login attempts per email + client IP (fails open if
    # Redis is down). Keyed on a hashed email so the redis key stays bounded and doesn't leak
    # the address; the IP component uses the same source as the rest of the auth router.
    client_ip = get_client_ip(request) or "unknown"
    email_hash = hashlib.sha256(str(payload.email).strip().lower().encode()).hexdigest()[:32]
    await check_named_rate_limit(
        f"{email_hash}:{client_ip}",
        redis,
        key_prefix="login",
        limit_per_minute=settings.login_rate_limit_per_minute,
        request_state=getattr(request, "state", None),
        error_code="login_rate_limited",
        error_message="Too many login attempts. Please try again in a minute.",
        log_context={"ip": client_ip},
    )

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
                    "docs_url": "https://docs.algenta.ai/errors/invalid_credentials",
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
    access_token = jwt.encode(token_data, settings.jwt_secret, algorithm=settings.jwt_algorithm)

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
    redis: object = Depends(get_redis),
) -> dict[str, str]:
    """Verify a user's email address. Token sent on signup."""
    from apps.api_server.models.user import User

    try:
        claims = verify_email_verification_token(token)
    except AuthTokenError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        ) from exc

    try:
        user_id = uuid.UUID(claims.subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_token",
                    "message": "Invalid token.",
                }
            },
        ) from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or user.email.lower() != claims.email:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_token",
                    "message": "Invalid token.",
                }
            },
        )

    if user.email_verified:
        return {"message": "Email already verified."}

    user.email_verified = True
    await db.commit()
    # Bust cached AuthContexts so the agentic gate (require_verified_email) lets the user in
    # immediately instead of after the auth cache TTL.
    await invalidate_user_api_key_caches(db, user.id, redis)

    logger.info("email_verified", user_id=str(user.id))
    return {"message": "Email verified successfully. You can now use the API."}


@router.post("/forgot-password", summary="Request a password reset email")
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Send a password reset link to the user's email."""
    from apps.api_server.models.user import User
    from apps.api_server.services.email_service import send_password_reset_email

    email = str(payload.email).lower().strip()

    # Email is per-org now (can match multiple orgs); reset the earliest match.
    result = await db.execute(select(User).where(User.email == email).order_by(User.created_at))
    user = result.scalars().first()

    # Always return success (don't reveal if email exists)
    if user is not None:
        token = issue_password_reset_token(str(user.id), email)
        try:
            await send_password_reset_email(email, token)
        except Exception as exc:
            logger.warning("password_reset_email_failed", email=email, error=str(exc))

    return {"message": "If an account with that email exists, a reset link has been sent."}


@router.post("/reset-password", summary="Complete password reset with token")
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Reset a user's password using a valid reset token."""
    from apps.api_server.models.user import User

    token = payload.token.strip()
    new_password = payload.new_password.strip()

    try:
        claims = verify_password_reset_token(token)
    except AuthTokenError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                }
            },
        ) from exc

    try:
        user_id = uuid.UUID(claims.subject)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_token",
                    "message": "Invalid token.",
                }
            },
        ) from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or user.email.lower() != claims.email:
        raise HTTPException(
            status_code=400,
            detail={
                "error": {
                    "code": "invalid_token",
                    "message": "Invalid token.",
                }
            },
        )

    user.password_hash = hash_password(new_password)
    await db.commit()

    logger.info("password_reset_completed", user_id=str(user.id))
    return {"message": "Password reset successfully. You can now log in."}
