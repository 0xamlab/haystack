"""Tests for test_platform_contract: assert_manifest.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-4/tests/test_platform_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_platform_contract_helpers import *  # noqa: F401,F403


def test_assert_manifest_backed_integrations_rejects_drifted_payload() -> None:
    drifted_integrations = list(MANIFEST_BACKED_INTEGRATIONS)
    drifted_integrations[0] = {
        **drifted_integrations[0],
        "status": "deprecated",
    }

    with pytest.raises(AssertionError):
        assert_manifest_backed_integrations(drifted_integrations)


def test_assert_manifest_backed_integrations_equal_rejects_drifted_payloads() -> None:
    drifted_integrations = list(MANIFEST_BACKED_INTEGRATIONS)
    drifted_integrations[0] = {
        **drifted_integrations[0],
        "status": "deprecated",
    }

    with pytest.raises(AssertionError):
        manifest_helpers.assert_manifest_backed_integrations_equal(
            list(MANIFEST_BACKED_INTEGRATIONS),
            drifted_integrations,
        )


def test_assert_manifest_backed_integrations_equal_accepts_matching_drifted_payloads() -> None:
    left_drifted_integrations = list(MANIFEST_BACKED_INTEGRATIONS)
    left_drifted_integrations[0] = {
        **left_drifted_integrations[0],
        "status": "deprecated",
    }
    right_drifted_integrations = list(left_drifted_integrations)

    manifest_helpers.assert_manifest_backed_integrations_equal(
        left_drifted_integrations,
        right_drifted_integrations,
    )


