"""Tests for test_credit_bucket: credit_state.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_6761da26-f90-3/tests/test_credit_bucket.py during modularization.
"""
from __future__ import annotations

from tests._test_credit_bucket_helpers import *  # noqa: F401,F403


def test_credit_state_needs_refresh_above_threshold():
    """Above 10% → no refresh needed."""
    from apps.runtime.credits import CreditState

    s = CreditState(**_make_state(remaining=2000, total=10_000))
    assert not s.needs_refresh


def test_credit_state_needs_refresh_at_threshold():
    """Exactly 10% → refresh needed."""
    from apps.runtime.credits import CreditState

    s = CreditState(**_make_state(remaining=1000, total=10_000))
    assert s.needs_refresh


def test_credit_state_needs_refresh_below_threshold():
    """Below 10% → refresh needed."""
    from apps.runtime.credits import CreditState

    s = CreditState(**_make_state(remaining=500, total=10_000))
    assert s.needs_refresh


def test_credit_state_is_exhausted():
    from apps.runtime.credits import CreditState

    s = CreditState(**_make_state(remaining=0))
    assert s.is_exhausted


def test_credit_state_not_exhausted():
    from apps.runtime.credits import CreditState

    s = CreditState(**_make_state(remaining=1))
    assert not s.is_exhausted


def test_credit_state_is_expired():
    from apps.runtime.credits import CreditState

    s = CreditState(**_make_state(expires_offset=-1))  # expired 1s ago
    assert s.is_expired


def test_credit_state_not_expired():
    from apps.runtime.credits import CreditState

    s = CreditState(**_make_state(expires_offset=3600))
    assert not s.is_expired


def test_credit_state_roundtrip():
    """to_dict / from_dict preserves all fields."""
    from apps.runtime.credits import CreditState

    s = CreditState(**_make_state())
    s2 = CreditState.from_dict(s.to_dict())
    assert s.credits_remaining == s2.credits_remaining
    assert s.credits_total == s2.credits_total
    assert s.billing_period == s2.billing_period


def test_credit_state_from_dict_ignores_extra_keys():
    """Extra keys in JSON don't crash from_dict."""
    from apps.runtime.credits import CreditState

    d = {**_make_state(), "unknown_field": "ignored"}
    s = CreditState.from_dict(d)
    assert s.credits_remaining == 5000


