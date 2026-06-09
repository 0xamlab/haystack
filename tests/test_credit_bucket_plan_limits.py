"""Tests for test_credit_bucket: plan_limits.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_6761da26-f90-3/tests/test_credit_bucket.py during modularization.
"""
from __future__ import annotations

from tests._test_credit_bucket_helpers import *  # noqa: F401,F403


def test_plan_limits_credit_batch_size_free():
    from apps.api_server.services.plan_limits import credit_batch_size

    assert credit_batch_size("free") == 1_000


def test_plan_limits_credit_batch_size_pro():
    from apps.api_server.services.plan_limits import credit_batch_size

    assert credit_batch_size("pro") == 10_000


def test_plan_limits_credit_batch_size_developer_legacy():
    from apps.api_server.services.plan_limits import credit_batch_size

    assert credit_batch_size("developer") == 10_000  # same as pro


def test_plan_limits_credit_batch_size_team():
    from apps.api_server.services.plan_limits import credit_batch_size

    assert credit_batch_size("team") == 25_000


def test_plan_limits_credit_batch_size_enterprise():
    from apps.api_server.services.plan_limits import credit_batch_size

    assert credit_batch_size("enterprise") == 100_000


def test_plan_limits_batch_much_smaller_than_monthly():
    """Batch should always be << monthly limit to bound overage."""
    from apps.api_server.services.plan_limits import credit_batch_size, execution_quota

    for plan in ("free", "pro", "developer", "team"):
        batch = credit_batch_size(plan)
        monthly = execution_quota(plan)
        assert batch <= monthly * 0.10, f"Plan '{plan}': batch {batch} > 10% of monthly {monthly}"


def test_plan_limits_enterprise_batch_nonzero():
    """Enterprise has unlimited monthly but should still have a finite batch."""
    from apps.api_server.services.plan_limits import credit_batch_size, execution_quota

    assert execution_quota("enterprise") == 0  # unlimited
    assert credit_batch_size("enterprise") > 0  # finite batch


