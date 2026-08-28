from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import secrets
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

# Integrity states reported for the persisted lapse floor:
#   "ok"       — file present, parses, and its HMAC matches the runtime-dir secret key
#   "tampered" — file present but unparsable, unsigned (pre-hardening / forged), or HMAC mismatch
#   "missing"  — no floor file at all (first boot, or the file was deleted out from under us)
_INTEGRITY_OK = "ok"
_INTEGRITY_TAMPERED = "tampered"
_INTEGRITY_MISSING = "missing"


def _runtime_dir() -> Path:
    return Path(os.environ.get("ALGENTA_RUNTIME_DIR", Path.home() / ".algenta" / "runtime"))


def _trusted_time_file() -> Path:
    return _runtime_dir() / "trusted_time.json"


def _time_floor_key_file() -> Path:
    return _runtime_dir() / "time_floor_key"


def _load_or_create_floor_key() -> bytes | None:
    """The HMAC key protecting the lapse floor: the bytes of a 0600 secret file in the runtime
    dir, auto-created on first use. Returns None only when the key can neither be read nor
    created — writes then go out unsigned and reads report "tampered", which the license load
    path resolves fail-closed (Community floor), never into a re-validated lapsed license."""
    key_file = _time_floor_key_file()
    try:
        if key_file.exists():
            key = key_file.read_bytes()
            if key:
                return key
    except Exception as exc:
        logger.debug("time_floor_key_read_failed", error=str(exc))
    try:
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key = secrets.token_bytes(32)
        key_file.write_bytes(key)
        try:
            key_file.chmod(0o600)
        except Exception as chmod_exc:
            logger.debug("time_floor_key_chmod_failed", error=str(chmod_exc))
        return key
    except Exception as exc:
        logger.debug("time_floor_key_create_failed", error=str(exc))
        return None


def _canonical_floor_json(state: TrustedTimeState) -> str:
    """The exact byte string the HMAC covers: canonical JSON of the three floor fields."""
    return json.dumps(
        {
            "version": state.version,
            "trusted_epoch": state.trusted_epoch,
            "source": state.source,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _compute_floor_integrity(state: TrustedTimeState) -> str | None:
    key = _load_or_create_floor_key()
    if key is None:
        return None
    return hmac.new(key, _canonical_floor_json(state).encode("utf-8"), hashlib.sha256).hexdigest()


def floor_integrity() -> str:
    """The current lapse-floor integrity verdict: "ok" | "tampered" | "missing".

    Callers deciding license lapse (apps/runtime/license.py's load path) capture this BEFORE
    ``trusted_now_epoch()`` runs — the first trusted-time read of a session recreates a missing
    floor from the wall clock, which must not launder a deleted floor back into "ok"."""
    _, integrity = _read_state()
    return integrity


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


def _read_state() -> tuple[TrustedTimeState | None, str]:
    """Read the persisted lapse floor: ``(state, integrity)``.

    ``integrity`` is "ok" (parses AND its HMAC verifies against the runtime-dir key), "tampered"
    (present but unparsable, unsigned/pre-hardening, or HMAC mismatch), or "missing" (no file —
    returned with ``state=None``). A tampered read still returns the parsed state so callers can
    log it; using its epoch as a floor is never safe (see observe_time / trusted_now_epoch)."""
    trusted_time_file = _trusted_time_file()
    if not trusted_time_file.exists():
        return None, _INTEGRITY_MISSING
    try:
        payload = json.loads(trusted_time_file.read_text())
    except Exception as exc:
        logger.debug("trusted_time_read_failed", error=str(exc))
        return None, _INTEGRITY_TAMPERED
    if not isinstance(payload, dict):
        return None, _INTEGRITY_TAMPERED
    state = TrustedTimeState.from_dict(payload)
    if state is None:
        return None, _INTEGRITY_TAMPERED
    expected = _compute_floor_integrity(state)
    recorded = payload.get("integrity")
    if (
        expected is None
        or not isinstance(recorded, str)
        or not hmac.compare_digest(expected, recorded)
    ):
        return state, _INTEGRITY_TAMPERED
    return state, _INTEGRITY_OK


def _write_state(state: TrustedTimeState) -> None:
    trusted_time_file = _trusted_time_file()
    try:
        trusted_time_file.parent.mkdir(parents=True, exist_ok=True)
        record = asdict(state)
        integrity = _compute_floor_integrity(state)
        if integrity is not None:
            record["integrity"] = integrity
        tmp_path = trusted_time_file.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(record, indent=2))
        tmp_path.replace(trusted_time_file)
    except Exception as exc:
        logger.debug("trusted_time_write_failed", error=str(exc))


def observe_time(epoch: float, *, source: str) -> float:
    _ensure_session_scope()
    if not math.isfinite(epoch) or epoch <= 0:
        return trusted_now_epoch()
    current, integrity = _read_state()
    # A floor that is not positively intact ("ok") contributes NOTHING: a tampered or deleted
    # floor's epoch is exactly the value an attacker chose, so the floor re-seeds from this
    # observation instead. The license load path captures the integrity verdict BEFORE this and
    # resolves the lapse decision fail-closed regardless of the re-seed.
    current_floor = (
        current.trusted_epoch if current is not None and integrity == _INTEGRITY_OK else 0.0
    )
    trusted_epoch = max(current_floor, float(epoch))
    _reset_session_clock(trusted_epoch)
    if (
        current is None
        or integrity != _INTEGRITY_OK
        or trusted_epoch > current_floor
        or current.source != source
    ):
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
    current, integrity = _read_state()
    current_floor = (
        current.trusted_epoch if current is not None and integrity == _INTEGRITY_OK else 0.0
    )
    trusted_epoch = _session_trusted_epoch(current_floor)
    if trusted_epoch > current_floor + _LOCAL_OBSERVATION_PERSIST_INTERVAL_SECONDS:
        _write_state(
            TrustedTimeState(
                version=_TRUSTED_TIME_VERSION,
                trusted_epoch=trusted_epoch,
                source="local",
            )
        )
    elif (current is None or integrity != _INTEGRITY_OK) and trusted_epoch > 0:
        # Repair an absent or non-intact floor (first boot, or a deleted/tampered/pre-hardening
        # file): re-seed from the wall clock and SIGN it. This re-seed is safe only because the
        # license load path captures floor_integrity() BEFORE this repair and fail-closes the
        # lapse decision on anything but "ok".
        _write_state(
            TrustedTimeState(
                version=_TRUSTED_TIME_VERSION,
                trusted_epoch=trusted_epoch,
                source="local",
            )
        )
    return trusted_epoch
