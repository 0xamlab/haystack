from __future__ import annotations

import json
import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

_TRUSTED_TIME_VERSION = 1
_LOCAL_OBSERVATION_PERSIST_INTERVAL_SECONDS = 60.0
_SESSION_MONOTONIC_BASE: float | None = None
_SESSION_TRUSTED_BASE: float | None = None
_SESSION_RUNTIME_DIR: str | None = None


def _runtime_dir() -> Path:
    return Path(os.environ.get("ALGENTA_RUNTIME_DIR", Path.home() / ".algenta" / "runtime"))


def _trusted_time_file() -> Path:
    return _runtime_dir() / "trusted_time.json"


def _monotonic_now() -> float:
    return float(time.monotonic())


def _ensure_session_scope() -> None:
    global _SESSION_MONOTONIC_BASE, _SESSION_RUNTIME_DIR, _SESSION_TRUSTED_BASE

    runtime_dir = str(_runtime_dir())
    if _SESSION_RUNTIME_DIR == runtime_dir:
        return
    _SESSION_RUNTIME_DIR = runtime_dir
    _SESSION_MONOTONIC_BASE = None
    _SESSION_TRUSTED_BASE = None


def _reset_session_clock(epoch: float, *, monotonic_now: float | None = None) -> float:
    global _SESSION_MONOTONIC_BASE, _SESSION_TRUSTED_BASE

    _SESSION_TRUSTED_BASE = float(epoch)
    _SESSION_MONOTONIC_BASE = _monotonic_now() if monotonic_now is None else float(monotonic_now)
    return _SESSION_TRUSTED_BASE


def _session_trusted_epoch(current_floor: float) -> float:
    _ensure_session_scope()
    mono_now = _monotonic_now()
    local_now = float(time.time())
    seed = max(local_now, current_floor)

    if _SESSION_MONOTONIC_BASE is None or _SESSION_TRUSTED_BASE is None:
        return _reset_session_clock(seed, monotonic_now=mono_now)

    elapsed = max(0.0, mono_now - _SESSION_MONOTONIC_BASE)
    session_epoch = _SESSION_TRUSTED_BASE + elapsed
    if seed > session_epoch:
        return _reset_session_clock(seed, monotonic_now=mono_now)
    return session_epoch


@dataclass
class TrustedTimeState:
    version: int
    trusted_epoch: float
    source: str

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> TrustedTimeState | None:
        trusted_epoch = payload.get("trusted_epoch")
        source = payload.get("source")
        if not isinstance(trusted_epoch, int | float) or not math.isfinite(trusted_epoch):
            return None
        if trusted_epoch <= 0:
            return None
        if not isinstance(source, str) or not source.strip():
            return None
        version = payload.get("version", _TRUSTED_TIME_VERSION)
        if not isinstance(version, int):
            version = _TRUSTED_TIME_VERSION
        return cls(
            version=version,
            trusted_epoch=float(trusted_epoch),
            source=source.strip(),
        )


def _read_state() -> TrustedTimeState | None:
    trusted_time_file = _trusted_time_file()
    if not trusted_time_file.exists():
        return None
    try:
        payload = json.loads(trusted_time_file.read_text())
    except Exception as exc:
        logger.debug("trusted_time_read_failed", error=str(exc))
        return None
    if not isinstance(payload, dict):
        return None
    return TrustedTimeState.from_dict(payload)


def _write_state(state: TrustedTimeState) -> None:
    trusted_time_file = _trusted_time_file()
    try:
        trusted_time_file.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = trusted_time_file.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(asdict(state), indent=2))
        tmp_path.replace(trusted_time_file)
    except Exception as exc:
        logger.debug("trusted_time_write_failed", error=str(exc))


def observe_time(epoch: float, *, source: str) -> float:
    _ensure_session_scope()
    if not math.isfinite(epoch) or epoch <= 0:
        return trusted_now_epoch()
    current = _read_state()
    current_floor = current.trusted_epoch if current is not None else 0.0
    trusted_epoch = max(current_floor, float(epoch))
    _reset_session_clock(trusted_epoch)
    if current is None or trusted_epoch > current_floor or current.source != source:
        _write_state(
            TrustedTimeState(
                version=_TRUSTED_TIME_VERSION,
                trusted_epoch=trusted_epoch,
                source=source,
            )
        )
    return trusted_epoch


def trusted_now_epoch() -> float:
    _ensure_session_scope()
    current = _read_state()
    current_floor = current.trusted_epoch if current is not None else 0.0
    trusted_epoch = _session_trusted_epoch(current_floor)
    if trusted_epoch > current_floor + _LOCAL_OBSERVATION_PERSIST_INTERVAL_SECONDS:
        _write_state(
            TrustedTimeState(
                version=_TRUSTED_TIME_VERSION,
                trusted_epoch=trusted_epoch,
                source="local",
            )
        )
    elif current is None and trusted_epoch > 0:
        _write_state(
            TrustedTimeState(
                version=_TRUSTED_TIME_VERSION,
                trusted_epoch=trusted_epoch,
                source="local",
            )
        )
    return trusted_epoch
