"""Tests for test_platform_contract: manifest_export.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_c39b5048-a59-4/tests/test_platform_contract.py during modularization.
"""
from __future__ import annotations

from tests._test_platform_contract_helpers import *  # noqa: F401,F403


def test_manifest_export_text_helper_accepts_matching_esm_and_commonjs_exports() -> None:
    payload = json.dumps(list(MANIFEST_BACKED_INTEGRATIONS))
    esm_text = f"export const INTEGRATIONS = {payload};"
    cjs_text = f"exports.INTEGRATIONS = {payload};"

    assert_manifest_backed_integration_texts_equal(esm_text, cjs_text)


def test_manifest_export_text_helper_accepts_identical_export_texts() -> None:
    payload = json.dumps(list(MANIFEST_BACKED_INTEGRATIONS))
    text = f"export const INTEGRATIONS = {payload};"

    assert_manifest_backed_integration_texts_equal(text, text)


def test_manifest_export_text_helper_rejects_identical_drifted_export_texts() -> None:
    drifted_integrations = list(MANIFEST_BACKED_INTEGRATIONS)
    drifted_integrations[0] = {
        **drifted_integrations[0],
        "status": "deprecated",
    }
    text = f"export const INTEGRATIONS = {json.dumps(drifted_integrations)};"

    with pytest.raises(AssertionError):
        assert_manifest_backed_integration_texts_equal(text, text)


def test_manifest_export_text_helper_rejects_missing_integration_export() -> None:
    payload = json.dumps(list(MANIFEST_BACKED_INTEGRATIONS))

    with pytest.raises(AssertionError, match="missing exported INTEGRATIONS array"):
        assert_manifest_backed_integration_texts_equal(
            f"export const INTEGRATIONS = {payload};",
            "export const CONTRACT_VERSION = '2026.05.0';",
        )


def test_manifest_export_text_helper_rejects_missing_left_hand_integration_export() -> None:
    payload = json.dumps(list(MANIFEST_BACKED_INTEGRATIONS))

    with pytest.raises(AssertionError, match="missing exported INTEGRATIONS array"):
        assert_manifest_backed_integration_texts_equal(
            "export const CONTRACT_VERSION = '2026.05.0';",
            f"exports.INTEGRATIONS = {payload};",
        )


def test_manifest_export_text_helper_rejects_matching_drifted_payloads() -> None:
    left_drifted_integrations = list(MANIFEST_BACKED_INTEGRATIONS)
    left_drifted_integrations[0] = {
        **left_drifted_integrations[0],
        "status": "deprecated",
    }
    right_drifted_integrations = list(left_drifted_integrations)

    with pytest.raises(AssertionError):
        assert_manifest_backed_integration_texts_equal(
            f"export const INTEGRATIONS = {json.dumps(left_drifted_integrations)};",
            f"exports.INTEGRATIONS = {json.dumps(right_drifted_integrations)};",
        )


def test_manifest_export_text_helper_rejects_mismatched_integration_payloads() -> None:
    left_payload = json.dumps(list(MANIFEST_BACKED_INTEGRATIONS))
    mismatched_integrations = list(MANIFEST_BACKED_INTEGRATIONS)
    mismatched_integrations[0] = {
        **mismatched_integrations[0],
        "status": "deprecated",
    }
    right_payload = json.dumps(mismatched_integrations)

    with pytest.raises(AssertionError):
        assert_manifest_backed_integration_texts_equal(
            f"export const INTEGRATIONS = {left_payload};",
            f"exports.INTEGRATIONS = {right_payload};",
        )


