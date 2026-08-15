"""Shared imports + helpers for test_credit_bucket_* sub-modules.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_6761da26-f90-3/tests/test_credit_bucket.py during modularization.
"""
# ruff: noqa: F401

from __future__ import annotations

"""
Credit bucket test suite — 50 checks covering:

  1.  CreditStore: decrement, exhaustion, persistence, atomic write
  2.  CreditStore: apply_refresh merges carry-over correctly
  3.  CreditStore: initialize_sync seeds from scratch
  4.  CreditStore: should_refresh thresholds (>10%, <10%, 0, expired)
  5.  consume_credit: permits when credits available
  6.  consume_credit: blocks when credits exhausted
  7.  consume_credit: blocks when no credit file unless explicit dev mode
  8.  consume_credit: triggers background refresh at <10%
  9.  plan_limits: credit_batch_size per plan
  10. plan_limits: batch sizes relative to monthly limits
  11. /v1/credits/refresh: grants full batch when under quota
  12. /v1/credits/refresh: denies when monthly quota exhausted (HTTP 429)
  13. /v1/credits/refresh: grants partial batch near limit
  14. /v1/credits/refresh: unlimited plan always grants full batch
  15. /v1/credits/refresh: requires valid auth (HTTP 401 without key)
  16. device register: response includes credit fields
  17. device register: STARTER plan blocked (HTTP 402) — no credits issued
  18. heartbeat: executions_since_last_heartbeat written to usage_records
  19. heartbeat: zero executions → no usage_record written
  20. metering: executions_since_last_heartbeat delta tracking
  21. metering: delta resets after confirmed heartbeat
  22. license: credit store seeded on successful registration
  23. CreditState: needs_refresh at exactly 10% boundary
  24. CreditState: expired flag
  25. CreditState: is_exhausted at 0
  26. CreditState: serialization round-trip
  27. credits_issued Redis counter incremented on refresh grant
  28. credits_issued Redis counter incremented on device register
  29. /v1/credits/refresh: device_id truncated in log (privacy)
  30. Full flow: register → execute 9999 credits → trigger refresh → execute
"""

import asyncio

import importlib

import sys

import tempfile

import time

import uuid

from datetime import UTC, datetime

from pathlib import Path

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).parent.parent

sys.path.insert(0, str(ROOT))

def _tmp_store():
    """Return a CreditStore backed by a temp file (cleaned up automatically)."""
    from apps.runtime.credits import CreditStore

    d = tempfile.mkdtemp()
    return CreditStore(Path(d) / "credits.json")

def _seed_key_bound_offline_license(
    monkeypatch: pytest.MonkeyPatch,
    runtime_dir: Path,
    *,
    expires_at: int | None = None,
):
    from apps.api_server.config import get_settings
    from apps.api_server.services.device_service import _issue_license_jwt

    monkeypatch.setenv("ALGENTA_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.delenv("ALGENTA_RUNTIME_DEV_MODE", raising=False)
    monkeypatch.setenv("JWT_SECRET", "jwt-signing-seed")
    # plan="developer" is a Codna-style unprefixed plan, and Codna's runtime is the ONE product
    # that still verifies the legacy HS256 control-plane license by deliberate, already-reviewed
    # design (apps.runtime.license._HS256_LEGACY_PERMITTED_PRODUCTS / product_registry.py's
    # rs256_license=False) — every other product hard-rejects HS256 by default now.
    monkeypatch.setenv("ALGENTA_RUNTIME_PRODUCT", "codna")
    get_settings.cache_clear()
    sys.modules.pop("apps.runtime.license", None)
    license_mod = importlib.import_module("apps.runtime.license")
    token = _issue_license_jwt(
        device_id="device-credit-offline-123",
        api_key_prefix="de_live_test",
        plan="developer",
        device_limit=5,
        org_id="org_credit_test",
        api_key_expires_at=datetime.fromtimestamp(
            float(expires_at or (int(time.time()) + 86_400)),
            UTC,
        ),
    )
    license_mod._save_license(token)
    get_settings.cache_clear()
    return license_mod

def _make_state(remaining=5000, total=10_000, expires_offset=3600, billing="2026-04"):
    """Return a CreditState dict suitable for writing to the store."""
    now = time.time()
    return {
        "credits_remaining": remaining,
        "credits_total": total,
        "issued_at": now,
        "expires_at": now + expires_offset,
        "billing_period": billing,
        "refresh_after": now + expires_offset * 0.9,
    }

def run(coro):
    """Run a coroutine synchronously without touching global event loop state."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

def _make_mock_ctx(plan: str = "pro"):
    return {
        "org_id": uuid.uuid4(),
        "key_id": uuid.uuid4(),
    }

def _mock_api_key_row(plan: str = "pro", org_id=None):
    row = MagicMock()
    row.org_id = org_id or uuid.uuid4()
    row.organization.plan = plan
    return row

def _mock_db_with_row(mock_row):
    """Return an AsyncMock session that yields mock_row from scalar result accessors."""
    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = mock_row
    mock_result.scalar_one_or_none.return_value = mock_row
    mock_db.execute.return_value = mock_result
    return mock_db



__all__ = [
    "annotations",
    "asyncio",
    "importlib",
    "sys",
    "tempfile",
    "time",
    "uuid",
    "UTC",
    "datetime",
    "Path",
    "AsyncMock",
    "MagicMock",
    "patch",
    "pytest",
    "ROOT",
    "_tmp_store",
    "_seed_key_bound_offline_license",
    "_make_state",
    "run",
    "_make_mock_ctx",
    "_mock_api_key_row",
    "_mock_db_with_row",
]
