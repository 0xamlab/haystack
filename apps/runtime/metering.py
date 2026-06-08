"""
Metering — async, non-blocking usage event queue + 24h device sync.

Two responsibilities:
  1. Usage events — buffered, flushed every 60s to control plane
  2. Device heartbeat — every 24h, sends device_id + usage summary to
     control plane so it can count active machines per API key and
     enforce device limits.

v1: events are logged locally only (no network flush).
v4+: flush to Algenta control plane via POST /v1/metering
     heartbeat to POST /v1/device/heartbeat
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from apps.privacy_policy import policy_from_environment

logger = structlog.get_logger(__name__)

_FLUSH_INTERVAL_S = 60.0
_HEARTBEAT_INTERVAL_S = 86_400.0  # 24h
_MAX_QUEUE = 10_000
_RUNTIME_DIR = Path(os.environ.get("ALGENTA_RUNTIME_DIR", Path.home() / ".algenta" / "runtime"))
_LAST_HEARTBEAT_FILE = _RUNTIME_DIR / "last_heartbeat"


@dataclass
class UsageEvent:
    event_type: str  # "execute_module" | "verify_and_execute" | "health" | etc.
    module: str = ""
    function: str = ""
    engine_used: str = ""
    latency_ms: float = 0.0
    success: bool = True
    timestamp: float = field(default_factory=time.time)
    org_id: str = ""
    request_id: str = ""


class MeteringQueue:
    """Thread-safe event queue with background async flusher + device heartbeat."""

    def __init__(self) -> None:
        self._queue: list[UsageEvent] = []
        self._total_enqueued: int = 0
        self._total_flushed: int = 0
        self._executions_at_last_heartbeat: int = 0  # delta counter for reconciliation
        self._flush_task: asyncio.Task[None] | None = None
        self._heartbeat_task: asyncio.Task[None] | None = None

    def record(self, event: UsageEvent) -> None:
        """Non-blocking: append event to queue. Never raises."""
        try:
            if len(self._queue) >= _MAX_QUEUE:
                self._queue.pop(0)  # drop oldest
            self._queue.append(event)
            self._total_enqueued += 1
        except Exception as exc:
            logger.debug("metering_record_failed", error=str(exc))

    def executions_since_last_heartbeat(self) -> int:
        """Delta executions since the last heartbeat was sent."""
        return self._total_enqueued - self._executions_at_last_heartbeat

    def start_background_flush(self, loop: asyncio.AbstractEventLoop) -> None:
        """Start flush + heartbeat coroutines (call once at daemon startup)."""
        policy = policy_from_environment()
        if policy.metering_mode != "control_plane_sync":
            logger.info(
                "metering_background_sync_disabled",
                metering_mode=policy.metering_mode,
                deployment_mode=policy.deployment_mode,
            )
            return
        self._flush_task = loop.create_task(self._flush_loop())
        if policy.mandatory_heartbeat_enabled:
            self._heartbeat_task = loop.create_task(self._heartbeat_loop())

    async def _flush_loop(self) -> None:
        while True:
            await asyncio.sleep(_FLUSH_INTERVAL_S)
            await self._flush()

    async def _flush(self) -> None:
        if not self._queue:
            return
        batch, self._queue = self._queue[:], []
        self._total_flushed += len(batch)
        logger.debug("metering_flush", count=len(batch), total=self._total_flushed)
        # POST batch to /v1/metering — run blocking urllib in a thread so we
        # don't stall the daemon's event loop.  Exceptions from the thread are
        # swallowed here: the queue was already cleared above, so the events
        # won't be re-queued regardless.
        try:
            await asyncio.to_thread(self._send_metering_batch_sync, batch)
        except Exception as exc:
            logger.debug("metering_flush_thread_error", error=str(exc))

    def _send_metering_batch_sync(self, batch: list[UsageEvent]) -> None:
        """Send metering batch to control plane (blocking; called via asyncio.to_thread)."""
        if policy_from_environment().metering_mode != "control_plane_sync":
            return
        try:
            import json
            import urllib.request

            from apps.runtime.license import _validated_control_plane_url, load_license

            api_key = os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
            lic = load_license(api_key)
            control_plane_url = _validated_control_plane_url(surface="metering_flush")

            payload = {
                "device_id": lic.device_id,
                "events": [
                    {
                        "event_type": e.event_type,
                        "module": e.module,
                        "function": e.function,
                        "engine_used": e.engine_used,
                        "latency_ms": e.latency_ms,
                        "success": e.success,
                        "timestamp": e.timestamp,
                        "request_id": e.request_id,
                    }
                    for e in batch
                ],
            }

            body = json.dumps(payload).encode()
            req = urllib.request.Request(  # noqa: S310
                f"{control_plane_url}/v1/metering",
                data=body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                data = json.loads(resp.read())
                logger.info("metering_flush_sent", accepted=data.get("accepted", len(batch)))
        except Exception as exc:
            # Drop on error — credit bucket is the source of truth for
            # enforcement.  We never re-queue to prevent unbounded growth.
            logger.debug("metering_flush_send_failed", error=str(exc))

    # ── Device heartbeat ──────────────────────────────────────────────────────

    async def _heartbeat_loop(self) -> None:
        """Fire device heartbeat every 24h — tells control plane this machine is active."""
        if not policy_from_environment().mandatory_heartbeat_enabled:
            return
        from apps.runtime.trusted_time import trusted_now_epoch

        # Check if we already sent one recently
        last = self._last_heartbeat_ts()
        if last > 0:
            wait = max(0.0, _HEARTBEAT_INTERVAL_S - (trusted_now_epoch() - last))
        else:
            wait = 5.0  # small delay on first run so daemon is fully up

        await asyncio.sleep(wait)

        while True:
            await self._send_heartbeat()
            await asyncio.sleep(_HEARTBEAT_INTERVAL_S)

    async def _send_heartbeat(self) -> None:
        """
        Send device heartbeat to control plane.

        Payload:
          {
            "device_id": "abc123...",
            "api_key_prefix": "<API_KEY_PREFIX>",
            "sdk_version": "0.1.0",
            "plan": "pro",
            "usage_since_last": { "executions": N, "modules_used": [...] }
          }

        Control plane response:
          {
            "device_count": 3,
            "device_limit": 5,
            "status": "ok" | "approaching_limit" | "over_limit",
            "message": "..."
          }

        v1: writes heartbeat to local file only (no network).
        v4+: POST to ALGENTA_CONTROL_PLANE_URL/v1/device/heartbeat
        """
        if not policy_from_environment().mandatory_heartbeat_enabled:
            return
        try:
            from apps.runtime.device import get_device_info
            from apps.runtime.license import _validated_control_plane_url, load_license

            api_key = os.environ.get("ALGENTA_API_KEY", "") or os.environ.get("DE_API_KEY", "")
            lic = load_license(api_key)
            device_info = get_device_info()

            # Count unique modules used since last heartbeat
            modules_used = list({e.module for e in self._queue if e.module})

            executions_delta = self.executions_since_last_heartbeat()

            heartbeat = {
                "device_id": lic.device_id,
                "api_key_prefix": lic.api_key_prefix,
                "plan": lic.plan,
                "device_limit": lic.device_limit,
                "sdk_version": device_info["sdk_version"],
                "platform": device_info["platform"],
                "executions_queued": self._total_enqueued,
                "executions_since_last_heartbeat": executions_delta,
                "modules_used": modules_used,
                "timestamp": _trusted_now_epoch(),
            }

            logger.info(
                "device_heartbeat",
                **{k: v for k, v in heartbeat.items() if k != "device_id"},
            )
            self._save_heartbeat_ts()
            # Mark delta snapshot — reset after confirmed send below
            heartbeat_baseline = self._total_enqueued

            # Send to control plane (works with local API server or cloud)
            import json as _json
            import urllib.request

            control_plane_url = _validated_control_plane_url(surface="device_heartbeat")
            hb_body = _json.dumps(
                {
                    "device_id": heartbeat["device_id"],
                    "usage": {
                        "executions": heartbeat["executions_queued"],
                        "executions_since_last_heartbeat": executions_delta,
                        "modules_used": heartbeat["modules_used"],
                        "platform": heartbeat["platform"],
                        "sdk_version": heartbeat["sdk_version"],
                    },
                }
            ).encode()
            hb_req = urllib.request.Request(  # noqa: S310
                f"{control_plane_url}/v1/device/heartbeat",
                data=hb_body,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(hb_req, timeout=10) as resp:  # noqa: S310
                    data = _json.loads(resp.read())
                    from apps.runtime.trusted_time import observe_time

                    observe_time(
                        float(data.get("server_time", time.time())),
                        source="control-plane-heartbeat",
                    )
                    if data.get("status") == "over_limit":
                        logger.warning("device_over_limit", message=data.get("message"))
                    elif data.get("status") == "approaching_limit":
                        logger.info("device_approaching_limit", message=data.get("message"))
                    # Advance the delta baseline only on confirmed delivery
                    self._executions_at_last_heartbeat = heartbeat_baseline
            except Exception as exc:
                logger.debug("heartbeat_send_failed", error=str(exc))

        except Exception as exc:
            logger.debug("heartbeat_error", error=str(exc))

    def _last_heartbeat_ts(self) -> float:
        try:
            if _LAST_HEARTBEAT_FILE.exists():
                return float(_LAST_HEARTBEAT_FILE.read_text().strip())
        except Exception as exc:
            logger.debug("heartbeat_timestamp_read_failed", error=str(exc))
        return 0.0

    def _save_heartbeat_ts(self) -> None:
        try:
            from apps.runtime.trusted_time import trusted_now_epoch

            _RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
            _LAST_HEARTBEAT_FILE.write_text(str(trusted_now_epoch()))
        except Exception as exc:
            logger.debug("heartbeat_timestamp_write_failed", error=str(exc))

    def snapshot(self) -> dict[str, int | float]:
        return {
            "queued": len(self._queue),
            "total_enqueued": self._total_enqueued,
            "total_flushed": self._total_flushed,
            "last_heartbeat": self._last_heartbeat_ts(),
        }

    def stop(self) -> None:
        for task in (self._flush_task, self._heartbeat_task):
            if task and not task.done():
                task.cancel()


# Singleton queue — imported by server.py
metering = MeteringQueue()


def _trusted_now_epoch() -> float:
    from apps.runtime.trusted_time import trusted_now_epoch

    return trusted_now_epoch()
