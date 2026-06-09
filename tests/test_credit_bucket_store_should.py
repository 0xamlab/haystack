"""Tests for test_credit_bucket: store_should.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_6761da26-f90-3/tests/test_credit_bucket.py during modularization.
"""
from __future__ import annotations

from tests._test_credit_bucket_helpers import *  # noqa: F401,F403


def test_store_should_refresh_true_when_no_file():
    store = _tmp_store()
    assert store.should_refresh() is True


def test_store_should_refresh_true_when_low():
    store = _tmp_store()
    from apps.runtime.credits import CreditState

    store._write(CreditState(**_make_state(remaining=500, total=10_000)))
    assert store.should_refresh() is True


def test_store_should_refresh_false_when_healthy():
    store = _tmp_store()
    from apps.runtime.credits import CreditState

    store._write(CreditState(**_make_state(remaining=5000, total=10_000)))
    assert store.should_refresh() is False


