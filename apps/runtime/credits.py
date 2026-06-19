"""
Credit bucket — local execution quota enforcement for the Algenta local runtime.

Architecture:
  The server issues a "credit batch" on:
    - Device registration  (initial batch, seeded from RegisterResponse)
    - POST /v1/credits/refresh  (background refresh when running low)

  Each local execution atomically decrements the counter — no network on hot path.
  When credits < 10% of batch: background refresh triggered (non-blocking).
  When credits reach 0: execution is blocked.

  Credits expire after 24h; the daemon auto-refreshes before they run out.
  Offline devices can continue executing until their current batch is exhausted.

Credit file:      ~/.algenta/runtime/credits.json
Refresh endpoint: POST /v1/credits/refresh

Quota enforcement path:
  credits_issued_this_month  (Redis on server)  ← authoritative
  ├── grants denied when issued >= monthly_limit
  └── daemon drains existing credits and then blocks

Heartbeat (separate) is analytics-only — not enforcement.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import UTC
from pathlib import Path
from typing import cast

import structlog

from apps.privacy_policy import policy_from_environment

logger = structlog.get_logger(__name__)

_RUNTIME_DIR = Path(os.environ.get("ALGENTA_RUNTIME_DIR", Path.home() / ".algenta" / "runtime"))
CREDITS_FILE = _RUNTIME_DIR / "credits.json"
_REFRESH_THRESHOLD = 0.10  # trigger refresh when <10% remaining
_CREDIT_TTL = 86_400  # 24h window per batch
_REFRESH_PATH = "/v1/credits/refresh"


# ── Credit state ──────────────────────────────────────────────────────────────


@dataclass
class CreditState:
    credits_remaining: int
    credits_total: int
    issued_at: float
    expires_at: float
    billing_period: str
    refresh_after: float

    @property
    def needs_refresh(self) -> bool:
        if self.credits_total <= 0:
            return True
        pct = self.credits_remaining / self.credits_total
        return pct <= _REFRESH_THRESHOLD or self.is_expired

    @property
    def is_exhausted(self) -> bool:
        return self.credits_remaining <= 0

    @property
    def is_expired(self) -> bool:
        from apps.runtime.trusted_time import trusted_now_epoch

        return trusted_now_epoch() > self.expires_at

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> CreditState:
        data = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(
            credits_remaining=_coerce_credit_int(data.get("credits_remaining"), 0),
            credits_total=_coerce_credit_int(data.get("credits_total"), 0),
            issued_at=_coerce_credit_float(data.get("issued_at"), 0.0),
            expires_at=_coerce_credit_float(data.get("expires_at"), 0.0),
            billing_period=str(data.get("billing_period", "")),
            refresh_after=_coerce_credit_float(data.get("refresh_after"), 0.0),
        )


# ── Persistent store ──────────────────────────────────────────────────────────


class CreditStore:
    """
    Async-safe local credit store backed by a JSON file.
    asyncio.Lock for coroutine safety; atomic tmp-rename writes prevent torn reads.
    """

    def __init__(self, path: Path = CREDITS_FILE) -> None:
        self._path = path
        self._lock = asyncio.Lock()
        self._refreshing = False

    # ── I/O ───────────────────────────────────────────────────────────────────

    def _read(self) -> CreditState | None:
        if not self._path.exists():
            return None
        try:
            payload = json.loads(self._path.read_text())
            if not isinstance(payload, dict):
                return None
            return CreditState.from_dict(cast(dict[str, object], payload))
        except Exception:
            return None

    def _write(self, state: CreditState) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state.to_dict(), indent=2))
        tmp.replace(self._path)

    # ── Public async API ──────────────────────────────────────────────────────

    async def decrement(self) -> bool:
        """
        Consume one execution credit.
        Returns True (permitted) or False (exhausted).
        """
        async with self._lock:
            state = self._read()
            if state is None:
                dev_mode = os.environ.get("ALGENTA_RUNTIME_DEV_MODE", "").strip().lower()
                return dev_mode in {"1", "true", "yes", "on"}
            if state.is_exhausted:
                return False
            self._write(
                CreditState(
                    credits_remaining=state.credits_remaining - 1,
                    credits_total=state.credits_total,
                    issued_at=state.issued_at,
                    expires_at=state.expires_at,
                    billing_period=state.billing_period,
                    refresh_after=state.refresh_after,
                )
            )
            return True

    async def apply_refresh(
        self,
        credits_granted: int,
        expires_at: float,
        billing_period: str,
    ) -> None:
        """Merge a newly granted batch into the local store."""
        async with self._lock:
            existing = self._read()
            carry = existing.credits_remaining if existing else 0
            self._write(
                CreditState(
                    credits_remaining=carry + credits_granted,
                    credits_total=credits_granted,
                    issued_at=_trusted_now_epoch(),
                    expires_at=expires_at,
                    billing_period=billing_period,
                    refresh_after=_trusted_now_epoch() + _CREDIT_TTL * 0.9,
                )
            )
        logger.info(
            "credits_applied", granted=credits_granted, carry=carry, total=carry + credits_granted
        )

    def initialize_sync(
        self,
        credits_granted: int,
        billing_period: str,
        ttl_seconds: int = _CREDIT_TTL,
    ) -> None:
        """
        Seed the credit file synchronously — called from license.py at registration.
        Does NOT require an event loop.
        """
        now = _trusted_now_epoch()
        self._write(
            CreditState(
                credits_remaining=credits_granted,
                credits_total=credits_granted,
                issued_at=now,
                expires_at=now + ttl_seconds,
                billing_period=billing_period,
                refresh_after=now + ttl_seconds * 0.9,
            )
        )
        logger.info("credits_initialized", granted=credits_granted, billing_period=billing_period)

    async def get_state(self) -> CreditState | None:
        return self._read()

    def should_refresh(self) -> bool:
        """Sync check — safe to call from any context."""
        state = self._read()
        return state is None or state.needs_refresh


# ── Global singleton ──────────────────────────────────────────────────────────

_store = CreditStore()


def _current_billing_period() -> str:
    from datetime import datetime

    return datetime.now(UTC).strftime("%Y-%m")


def _trusted_now_epoch() -> float:
    from apps.runtime.trusted_time import trusted_now_epoch

    return trusted_now_epoch()


def _coerce_credit_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _coerce_credit_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def _offline_execution_entitled() -> bool:
    policy = policy_from_environment()
    if policy.deployment_mode == "self_hosted" and not policy.require_local_license:
        return True
    try:
        from apps.runtime.license import load_license, stored_offline_execution_entitlement

        api_key = os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
        if policy.require_local_license:
            return bool(load_license(api_key).valid)
        return stored_offline_execution_entitlement(
            api_key,
            runtime_dir=_store._path.parent,
        )
    except Exception:
        return False


# ── Hot-path helpers ──────────────────────────────────────────────────────────


async def consume_credit(*, allow_background_refresh: bool = True) -> bool:
    """
    Consume one execution credit.
    Optionally triggers a background refresh when the bucket runs low.
    Returns False when exhausted — caller must block execution.
    """
    if _offline_execution_entitled():
        return True

    permitted = await _store.decrement()

    policy = policy_from_environment()
    if (
        allow_background_refresh
        and policy.metering_mode == "control_plane_sync"
        and _store.should_refresh()
        and not _store._refreshing
    ):
        try:
            asyncio.get_running_loop().create_task(_background_refresh())
        except RuntimeError:
            pass  # no event loop — refresh will happen on next startup

    return permitted


async def _background_refresh() -> None:
    """
    Non-blocking credit refresh from the Algenta control plane.
    Called automatically when credits drop below 10% or expire.
    Suppresses all errors — execution is never interrupted by a network failure.
    """
    if _store._refreshing:
        return
    policy = policy_from_environment()
    if policy.metering_mode != "control_plane_sync":
        return
    _store._refreshing = True
    try:
        import urllib.error
        import urllib.request

        from apps.runtime.device import get_device_id
        from apps.runtime.license import _validated_control_plane_url
        from apps.runtime.privacy_guard import runtime_urlopen

        api_key = os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
        if not api_key:
            return  # offline / dev mode
        control_plane_url = _validated_control_plane_url(surface="credits_refresh", record=False)

        state = await _store.get_state()
        billing_period = state.billing_period if state else _current_billing_period()
        credits_used = (state.credits_total - state.credits_remaining) if state else 0

        body = json.dumps(
            {
                "device_id": get_device_id(),
                "billing_period": billing_period,
                "credits_used": credits_used,
            }
        ).encode()

        req = urllib.request.Request(  # noqa: S310
            f"{control_plane_url}{_REFRESH_PATH}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            method="POST",
        )
        # B10: enforce the runtime egress policy at the transport (fail-closed) via the approved
        # wrapper; the control-plane base URL was already validated above.
        with runtime_urlopen(req, surface="credits_refresh", timeout=8) as resp:
            data = json.loads(resp.read())

        from apps.runtime.trusted_time import observe_time

        observe_time(
            float(data.get("server_time", time.time())),
            source="control-plane-credit-refresh",
        )

        granted = data.get("credits_granted", 0)
        if granted > 0:
            await _store.apply_refresh(
                credits_granted=granted,
                expires_at=data["expires_at"],
                billing_period=data["billing_period"],
            )
        else:
            logger.warning(
                "credit_refresh_zero", monthly_remaining=data.get("monthly_remaining", 0)
            )

    except Exception as exc:
        # urllib.error.HTTPError is caught here too
        code = getattr(exc, "code", None)
        if code in (402, 429):
            logger.warning(
                "credit_refresh_quota_exhausted",
                status=code,
                hint=("Monthly quota exhausted; executions will block when credits drain."),
            )
        else:
            logger.debug("credit_refresh_failed", error=str(exc))
    finally:
        _store._refreshing = False


# ── Convenience accessors ─────────────────────────────────────────────────────


def get_store() -> CreditStore:
    return _store
