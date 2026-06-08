"""Tests for test_platform_contract: contract_integrations.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-4/tests/test_platform_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_platform_contract_helpers import *  # noqa: F401,F403


def test_contract_integrations_match_manifest_fails_closed_for_malformed_input() -> None:
    assert contract_integrations_match_manifest([object()]) is False


def test_contract_integrations_match_manifest_fails_closed_for_empty_sequences() -> None:
    assert contract_integrations_match_manifest([]) is False


def test_contract_integrations_match_manifest_accepts_attribute_backed_fixture_payload() -> None:
    integrations = [
        SimpleNamespace(
            **{
                **integration,
                "capabilities": tuple(integration["capabilities"]),
                "required_scopes": tuple(integration["required_scopes"]),
                "write_actions": tuple(integration["write_actions"]),
                "admin_controls": tuple(integration["admin_controls"]),
                "regions": tuple(integration["regions"]),
            }
        )
        for integration in MANIFEST_BACKED_INTEGRATIONS
    ]

    assert contract_integrations_match_manifest(integrations) is True


def test_contract_integrations_match_manifest_fails_closed_for_drifted_payload() -> None:
    drifted_integrations = list(MANIFEST_BACKED_INTEGRATIONS)
    drifted_integrations[0] = {
        **drifted_integrations[0],
        "status": "deprecated",
    }

    assert contract_integrations_match_manifest(drifted_integrations) is False


