"""
Execution Policy Service

Per-org configurable safety gates that govern when autonomous execution is allowed.
Policies are persisted under the runtime directory as immutable snapshots plus a
current-state pointer so replayable runtimes can reference stable policy ids.

Gates (evaluated in order):
  1. Idempotency    — already executed → block unless force=True
  2. Confidence     — confidence < min_confidence → block unless override_safety=True
  3. Risk floor     — p5 < -risk_floor → block unless override_safety=True
  4. Calibration    — auto_execute requires is_reliable (when require_calibration=True)

Design principle: default to SAFE
  - min_confidence defaults to 0.5 (reject majority-uncertain decisions)
  - require_calibration defaults to True (no blind autonomous execution)
  - allow_reexecution defaults to False (idempotent by default)
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any, Literal

_POLICY_SCHEMA_REVISION = "execution-policy-v1"
_LOCK = RLock()


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _runtime_dir() -> Path:
    configured = os.environ.get("ALGENTA_RUNTIME_DIR")
    if configured:
        return Path(configured)
    return Path.cwd() / ".algenta-runtime"


def _policy_root() -> Path:
    return _runtime_dir() / "execution_policies"


def _org_policy_dir(org_id: str) -> Path:
    return _policy_root() / org_id


def _snapshot_dir(org_id: str) -> Path:
    return _org_policy_dir(org_id) / "snapshots"


def _current_policy_path(org_id: str) -> Path:
    return _org_policy_dir(org_id) / "current.json"


def _snapshot_json_path(org_id: str, snapshot_id: str) -> Path:
    return _snapshot_dir(org_id) / f"{snapshot_id}.json"


def _snapshot_parquet_path(org_id: str, snapshot_id: str) -> Path:
    return _snapshot_dir(org_id) / f"{snapshot_id}.parquet"


def _ensure_policy_dirs(org_id: str) -> None:
    _snapshot_dir(org_id).mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class ExecutionPolicy:
    """
    Configurable safety policy for an org's autonomous execution.

    All thresholds can be loosened via the PATCH /v1/execution/policy endpoint.
    Set ``override_safety=True`` in an execute request to bypass confidence/risk gates
    for a single call (requires explicit intent signal from caller).
    """

    min_confidence: float = 0.5
    risk_floor: float | None = None
    require_calibration: bool = True
    allow_reexecution: bool = False
    snapshot_id: str = ""
    content_hash: str = ""
    schema_revision: str = _POLICY_SCHEMA_REVISION
    revision: int = 0
    previous_snapshot_id: str | None = None
    created_at: datetime = datetime(2026, 1, 1, tzinfo=UTC)
    updated_at: datetime = datetime(2026, 1, 1, tzinfo=UTC)

    @classmethod
    def defaults(cls) -> ExecutionPolicy:
        return cls()

    def canonical_settings(self) -> dict[str, Any]:
        return {
            "min_confidence": self.min_confidence,
            "risk_floor": self.risk_floor,
            "require_calibration": self.require_calibration,
            "allow_reexecution": self.allow_reexecution,
            "schema_revision": self.schema_revision,
        }

    def snapshot_payload(self, *, org_id: str) -> dict[str, Any]:
        return {
            "org_id": org_id,
            **self.canonical_settings(),
            "snapshot_id": self.snapshot_id,
            "content_hash": self.content_hash,
            "revision": self.revision,
            "previous_snapshot_id": self.previous_snapshot_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.canonical_settings(),
            "snapshot_id": self.snapshot_id,
            "content_hash": self.content_hash,
            "revision": self.revision,
            "previous_snapshot_id": self.previous_snapshot_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


def default_policy_payload() -> dict[str, Any]:
    return ExecutionPolicy.defaults().canonical_settings()


def _hash_policy_settings(settings: dict[str, Any]) -> str:
    return hashlib.sha256(_json_dumps(settings).encode("utf-8")).hexdigest()


def _snapshot_id(*, revision: int, content_hash: str) -> str:
    return f"{_POLICY_SCHEMA_REVISION}-r{revision}:{content_hash[:16]}"


def _coerce_datetime(value: str | datetime, field_name: str) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(f"{field_name} must be timezone-aware.")
        return value.astimezone(UTC)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
    return parsed.astimezone(UTC)


def _policy_from_payload(payload: dict[str, Any]) -> ExecutionPolicy:
    return ExecutionPolicy(
        min_confidence=float(payload["min_confidence"]),
        risk_floor=float(payload["risk_floor"]) if payload.get("risk_floor") is not None else None,
        require_calibration=bool(payload["require_calibration"]),
        allow_reexecution=bool(payload["allow_reexecution"]),
        snapshot_id=str(payload["snapshot_id"]),
        content_hash=str(payload["content_hash"]),
        schema_revision=str(payload.get("schema_revision", _POLICY_SCHEMA_REVISION)),
        revision=int(payload["revision"]),
        previous_snapshot_id=payload.get("previous_snapshot_id"),
        created_at=_coerce_datetime(payload["created_at"], "created_at"),
        updated_at=_coerce_datetime(payload["updated_at"], "updated_at"),
    )


def _policy_record(org_id: str, policy: ExecutionPolicy) -> Any:
    from apps.api_server.services.runtime_internal_contracts import PolicySnapshotRecord

    return PolicySnapshotRecord(
        org_id=org_id,
        snapshot_id=policy.snapshot_id,
        previous_snapshot_id=policy.previous_snapshot_id,
        schema_revision=policy.schema_revision,
        revision=policy.revision,
        min_confidence=policy.min_confidence,
        risk_floor=policy.risk_floor,
        require_calibration=policy.require_calibration,
        allow_reexecution=policy.allow_reexecution,
        content_hash=policy.content_hash,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


def _validate_policy_update(field_name: str, value: Any) -> Any:
    if field_name == "min_confidence":
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("min_confidence must be a number between 0 and 1.")
        normalized = float(value)
        if normalized < 0.0 or normalized > 1.0:
            raise ValueError("min_confidence must be between 0 and 1.")
        return normalized
    if field_name == "risk_floor":
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("risk_floor must be a non-negative number or null.")
        normalized = float(value)
        if normalized < 0.0:
            raise ValueError("risk_floor must be greater than or equal to 0.")
        return normalized
    if field_name in {"require_calibration", "allow_reexecution"}:
        if not isinstance(value, bool):
            raise TypeError(f"{field_name} must be a boolean.")
        return value
    raise ValueError(f"Unsupported execution policy field: {field_name}.")


def _persist_policy_snapshot(org_id: str, policy: ExecutionPolicy) -> None:
    from apps.api_server.services.runtime_internal_contracts import (
        PolicySnapshotRecord,
        parquet_bytes_from_records,
    )

    _ensure_policy_dirs(org_id)
    payload = policy.snapshot_payload(org_id=org_id)
    _snapshot_json_path(org_id, policy.snapshot_id).write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _snapshot_parquet_path(org_id, policy.snapshot_id).write_bytes(
        parquet_bytes_from_records([_policy_record(org_id, policy)], record_type=PolicySnapshotRecord)
    )
    _current_policy_path(org_id).write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _default_policy(org_id: str) -> ExecutionPolicy:
    created_at = _utc_now()
    defaults = default_policy_payload()
    content_hash = _hash_policy_settings(defaults)
    policy = ExecutionPolicy(
        **defaults,
        snapshot_id=_snapshot_id(revision=1, content_hash=content_hash),
        content_hash=content_hash,
        revision=1,
        previous_snapshot_id=None,
        created_at=created_at,
        updated_at=created_at,
    )
    _persist_policy_snapshot(org_id, policy)
    return policy


def _load_current_policy(org_id: str) -> ExecutionPolicy | None:
    path = _current_policy_path(org_id)
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _policy_from_payload(payload)


def get_policy(org_id: str) -> ExecutionPolicy:
    """Return the org's execution policy. Initializes safe defaults when absent."""
    with _LOCK:
        policy = _load_current_policy(org_id)
        if policy is not None:
            return policy
        return _default_policy(org_id)


def get_policy_snapshot(org_id: str, snapshot_id: str) -> ExecutionPolicy:
    with _LOCK:
        path = _snapshot_json_path(org_id, snapshot_id)
        if not path.exists():
            raise KeyError(snapshot_id)
        return _policy_from_payload(json.loads(path.read_text(encoding="utf-8")))


def list_policy_snapshots(org_id: str) -> list[ExecutionPolicy]:
    with _LOCK:
        current = get_policy(org_id)
        paths = sorted(_snapshot_dir(org_id).glob("*.json"))
        if not paths:
            return [current]
        snapshots = [_policy_from_payload(json.loads(path.read_text(encoding="utf-8"))) for path in paths]
        return sorted(
            snapshots,
            key=lambda item: (item.revision, item.created_at.isoformat(), item.snapshot_id),
        )


def set_policy(org_id: str, **kwargs: Any) -> ExecutionPolicy:
    """Update policy fields and persist an immutable snapshot when values change."""
    allowed = {"min_confidence", "risk_floor", "require_calibration", "allow_reexecution"}
    unexpected = sorted(set(kwargs) - allowed)
    if unexpected:
        raise ValueError(f"Unsupported execution policy fields: {', '.join(unexpected)}.")
    with _LOCK:
        current = get_policy(org_id)
        updates = current.canonical_settings()
        changed = False
        for field_name in allowed:
            if field_name not in kwargs:
                continue
            value = _validate_policy_update(field_name, kwargs[field_name])
            if updates[field_name] != value:
                updates[field_name] = value
                changed = True
        if not changed:
            return current
        created_at = _utc_now()
        content_hash = _hash_policy_settings(updates)
        policy = ExecutionPolicy(
            **updates,
            snapshot_id=_snapshot_id(revision=current.revision + 1, content_hash=content_hash),
            content_hash=content_hash,
            revision=current.revision + 1,
            previous_snapshot_id=current.snapshot_id,
            created_at=created_at,
            updated_at=created_at,
        )
        _persist_policy_snapshot(org_id, policy)
        return policy


# ── Gate evaluation ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class PolicyViolation:
    gate: Literal["idempotency", "confidence", "risk_floor"]
    detail: str
    override_hint: str


def check_execution_gates(
    policy: ExecutionPolicy,
    confidence: float | None,
    risk_p5: float | None,
    already_executed: bool,
    force: bool = False,
    override_safety: bool = False,
) -> PolicyViolation | None:
    """
    Evaluate all safety gates in order.

    Returns the first violation, or None if execution is allowed.

    Args:
        force:           bypass the idempotency gate only
        override_safety: bypass confidence + risk_floor gates
    """
    if already_executed and not policy.allow_reexecution and not force:
        return PolicyViolation(
            gate="idempotency",
            detail="This decision was already executed. Pass force=true to re-execute.",
            override_hint="Add force=true to the request body.",
        )

    if not override_safety and confidence is not None:
        if confidence < policy.min_confidence:
            return PolicyViolation(
                gate="confidence",
                detail=(
                    f"confidence {confidence:.2%} is below policy minimum "
                    f"{policy.min_confidence:.2%}."
                ),
                override_hint="Add override_safety=true to bypass this gate.",
            )

    if not override_safety and policy.risk_floor is not None and risk_p5 is not None:
        if risk_p5 < -policy.risk_floor:
            return PolicyViolation(
                gate="risk_floor",
                detail=(
                    f"worst-case outcome p5={risk_p5:,.0f} exceeds risk floor "
                    f"-{policy.risk_floor:,.0f}."
                ),
                override_hint="Add override_safety=true to bypass this gate.",
            )

    return None


def check_auto_execute_allowed(
    policy: ExecutionPolicy,
    calibration_is_reliable: bool,
) -> tuple[bool, str | None]:
    """
    Check whether a trigger's auto_execute should proceed.

    Returns (allowed, reason_if_blocked).
    """
    if policy.require_calibration and not calibration_is_reliable:
        return False, (
            "auto_execute skipped: calibration not yet reliable "
            "(record outcomes via PATCH /v1/decisions/{id}/outcome to enable)"
        )
    return True, None
