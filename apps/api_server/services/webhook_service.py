"""
Webhook delivery service — delivers job completion notifications.

Features:
- HMAC-SHA256 signature on every payload
- Exponential backoff retry (3 attempts: 5s, 30s, 120s)
- Delivery status tracked in DB
"""
import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog

from apps.api_server.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()

_RETRY_DELAYS = [5, 30, 120]  # seconds between retries
_TIMEOUT_SECONDS = 10


def _sign_payload(payload_bytes: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for webhook payload."""
    return hmac.new(
        secret.encode(),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


def build_webhook_payload(
    event: str,
    job_id: uuid.UUID,
    run_id: uuid.UUID,
    org_id: uuid.UUID,
    result: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Build the standard webhook event payload."""
    payload: dict[str, Any] = {
        "event": event,
        "job_id": str(job_id),
        "run_id": str(run_id),
        "org_id": str(org_id),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if result is not None:
        payload["result"] = result
    if error is not None:
        payload["error"] = error
    return payload


async def deliver_webhook(
    callback_url: str,
    payload: dict[str, Any],
    secret: str | None = None,
    max_retries: int = 3,
) -> tuple[bool, int, str]:
    """
    Deliver webhook payload to callback_url with retry logic.

    Returns:
        (success: bool, final_status_code: int, message: str)
    """
    if secret is None:
        secret = settings.webhook_signing_secret

    payload_bytes = json.dumps(payload, default=str).encode()
    signature = _sign_payload(payload_bytes, secret)

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": f"sha256={signature}",
        "X-Webhook-Event": payload.get("event", "unknown"),
        "X-Job-Id": payload.get("job_id", ""),
        "User-Agent": "DecisionEngine-Webhooks/1.0",
    }

    last_status = 0
    last_message = "No attempts made"

    retries = min(max_retries, len(_RETRY_DELAYS))

    for attempt in range(retries + 1):
        if attempt > 0:
            delay = _RETRY_DELAYS[min(attempt - 1, len(_RETRY_DELAYS) - 1)]
            logger.info(
                "webhook_retry_waiting",
                attempt=attempt,
                delay_seconds=delay,
                callback_url=callback_url[:50],
            )
            time.sleep(delay)

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
                response = await client.post(
                    callback_url,
                    content=payload_bytes,
                    headers=headers,
                )
                last_status = response.status_code
                last_message = f"HTTP {response.status_code}"

                if 200 <= response.status_code < 300:
                    logger.info(
                        "webhook_delivered",
                        status_code=response.status_code,
                        attempt=attempt + 1,
                        callback_url=callback_url[:50],
                    )
                    return True, last_status, "delivered"

                logger.warning(
                    "webhook_delivery_failed",
                    status_code=response.status_code,
                    attempt=attempt + 1,
                    callback_url=callback_url[:50],
                )

        except Exception as exc:
            last_status = 0
            last_message = str(exc)
            logger.warning(
                "webhook_delivery_error",
                error=str(exc),
                attempt=attempt + 1,
                callback_url=callback_url[:50],
            )

    logger.error(
        "webhook_all_retries_exhausted",
        attempts=retries + 1,
        last_status=last_status,
        callback_url=callback_url[:50],
    )
    return False, last_status, last_message


def verify_webhook_signature(
    payload_bytes: bytes,
    signature_header: str,
    secret: str,
) -> bool:
    """
    Verify an incoming webhook signature.
    Call this in receiver code to validate authenticity.
    """
    if not signature_header.startswith("sha256="):
        return False
    expected = _sign_payload(payload_bytes, secret)
    received = signature_header[len("sha256="):]
    return hmac.compare_digest(expected, received)
