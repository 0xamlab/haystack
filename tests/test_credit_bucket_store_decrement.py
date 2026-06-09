"""Tests for test_credit_bucket: store_decrement.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_6761da26-f90-3/tests/test_credit_bucket.py during modularization.
"""
from __future__ import annotations

from tests._test_credit_bucket_helpers import *  # noqa: F401,F403


def test_store_decrement_reduces_count():
    store = _tmp_store()
    store._write(
        store._read()
        or __import__("apps.runtime.credits", fromlist=["CreditState"]).CreditState(
            **_make_state(remaining=100)
        )
    )
    # Re-write via initialize_sync
    store.initialize_sync(credits_granted=100, billing_period="2026-04")
    permitted = run(store.decrement())
    assert permitted
    state = run(store.get_state())
    assert state.credits_remaining == 99


def test_store_decrement_returns_false_when_exhausted():
    store = _tmp_store()
    store.initialize_sync(credits_granted=0, billing_period="2026-04")
    # Patch: write 0 remaining directly
    from apps.runtime.credits import CreditState

    store._write(CreditState(**_make_state(remaining=0)))
    result = run(store.decrement())
    assert result is False


def test_store_decrement_blocks_when_no_file():
    """No credit file → contract blocks execution unless explicit dev mode is enabled."""
    store = _tmp_store()
    result = run(store.decrement())
    assert result is False


