"""Tests for test_go_live_verify: build_gap.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_ad413055-70e-1/tests/test_go_live_verify.py during modularization.
"""
from __future__ import annotations

from tests._test_go_live_verify_helpers import *  # noqa: F401,F403


def test_build_gap_action_summary_reports_mapped_and_terminal_actions() -> None:
    summary = build_gap_action_summary(
        [
            {"case_id": "dlt_github_issues"},
            {"case_id": "snowflake_customer_connector_test"},
        ],
        [
            {
                "code": "enable_opt_in_public_cases",
                "details": {"case_ids": ["dlt_github_issues"]},
            },
            {
                "code": "resolve_network_policy_blockers",
                "details": {"case_ids": ["snowflake_customer_connector_test"]},
            },
            {"code": "rerun_strict_go_live_gate"},
        ],
    )

    assert summary == {
        "mapped_case_count": 2,
        "unmapped_case_ids": [],
        "action_case_counts": {
            "enable_opt_in_public_cases": 1,
            "resolve_network_policy_blockers": 1,
        },
        "action_case_ids": {
            "enable_opt_in_public_cases": ["dlt_github_issues"],
            "resolve_network_policy_blockers": ["snowflake_customer_connector_test"],
        },
        "action_env_names": {},
        "action_env_counts": {},
        "action_connector_types": {
            "enable_opt_in_public_cases": ["unknown"],
            "resolve_network_policy_blockers": ["unknown"],
        },
        "action_connector_counts": {
            "enable_opt_in_public_cases": 1,
            "resolve_network_policy_blockers": 1,
        },
        "terminal_action_codes": ["rerun_strict_go_live_gate"],
    }


def test_build_gap_connector_summary_reports_cases_actions_and_envs() -> None:
    summary = build_gap_connector_summary(
        [
            {
                "case_id": "dlt_github_issues",
                "connector_type": "rest_api",
                "reason": "set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1",
                "action_codes": ["enable_opt_in_public_cases"],
            },
            {
                "case_id": "redis_customer_connector_test",
                "connector_type": "redis",
                "reason": "required env not provided: DE_TEST_REDIS_URL",
                "action_codes": ["set_customer_connector_envs"],
            },
        ],
        [
            {
                "code": "enable_opt_in_public_cases",
                "details": {"case_ids": ["dlt_github_issues"]},
            },
            {
                "code": "set_customer_connector_envs",
                "details": {"case_ids": ["redis_customer_connector_test"]},
            },
        ],
    )

    assert summary == {
        "connector_case_counts": {
            "redis": 1,
            "rest_api": 1,
        },
        "connector_case_ids": {
            "redis": ["redis_customer_connector_test"],
            "rest_api": ["dlt_github_issues"],
        },
        "connector_action_codes": {
            "redis": ["set_customer_connector_envs"],
            "rest_api": ["enable_opt_in_public_cases"],
        },
        "connector_env_counts": {
            "redis": 1,
            "rest_api": 1,
        },
        "connector_env_names": {
            "redis": ["DE_TEST_REDIS_URL"],
            "rest_api": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
        },
    }


def test_build_gap_env_summary_reports_cases_actions_connectors_and_tiers() -> None:
    summary = build_gap_env_summary(
        [
            {
                "case_id": "dlt_github_issues",
                "tier": "public_no_auth",
                "connector_type": "rest_api",
                "reason": "set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1",
                "action_codes": ["enable_opt_in_public_cases"],
            },
            {
                "case_id": "redis_customer_connector_test",
                "tier": "customer_credentials_required",
                "connector_type": "redis",
                "reason": "required env not provided: DE_TEST_REDIS_URL",
                "action_codes": ["set_customer_connector_envs"],
            },
        ],
        [
            {
                "code": "enable_opt_in_public_cases",
                "details": {"case_ids": ["dlt_github_issues"]},
            },
            {
                "code": "set_customer_connector_envs",
                "details": {"case_ids": ["redis_customer_connector_test"]},
            },
        ],
    )

    assert summary == {
        "env_total_count": 2,
        "shared_env_names": [],
        "tier_env_counts": {
            "customer_credentials_required": 1,
            "public_no_auth": 1,
        },
        "env_case_counts": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": 1,
            "DE_TEST_REDIS_URL": 1,
        },
        "env_case_ids": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["dlt_github_issues"],
            "DE_TEST_REDIS_URL": ["redis_customer_connector_test"],
        },
        "env_connector_types": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["rest_api"],
            "DE_TEST_REDIS_URL": ["redis"],
        },
        "env_connector_counts": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": 1,
            "DE_TEST_REDIS_URL": 1,
        },
        "env_action_codes": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["enable_opt_in_public_cases"],
            "DE_TEST_REDIS_URL": ["set_customer_connector_envs"],
        },
        "env_action_counts": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": 1,
            "DE_TEST_REDIS_URL": 1,
        },
        "env_tiers": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["public_no_auth"],
            "DE_TEST_REDIS_URL": ["customer_credentials_required"],
        },
    }


def test_build_gap_env_resolution_summary_reports_resolver_supported_and_manual_only() -> None:
    summary = build_gap_env_resolution_summary(
        {
            "env_case_ids": {
                "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["dlt_github_issues"],
                "DE_TEST_REDIS_URL": ["redis_customer_connector_test"],
            }
        }
    )

    assert summary == {
        "resolver_supported_count": 1,
        "manual_only_count": 1,
        "resolver_supported_env_names": ["DE_TEST_REDIS_URL"],
        "manual_only_env_names": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
        "env_candidate_names": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
            "DE_TEST_REDIS_URL": ["DE_TEST_REDIS_URL", "REDIS_URL"],
        },
        "env_group_names": {"DE_TEST_REDIS_URL": "redis"},
        "group_env_counts": {"redis": 1},
    }


def test_build_gap_env_template_summary_reports_template_coverage(tmp_path) -> None:
    root_env_path = tmp_path / ".env.example"
    go_live_env_path = tmp_path / "go_live_validation.env.example"
    root_env_path.write_text(
        "DE_ENABLE_SLOW_PUBLIC_REST_CASES=\nDE_TEST_REDIS_URL=\n",
        encoding="utf-8",
    )
    go_live_env_path.write_text(
        "DE_ENABLE_SLOW_PUBLIC_REST_CASES=\n",
        encoding="utf-8",
    )

    summary = build_gap_env_template_summary(
        {
            "env_case_ids": {
                "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["dlt_github_issues"],
                "DE_TEST_REDIS_URL": ["redis_customer_connector_test"],
            }
        },
        template_paths={
            "root_env_example": root_env_path,
            "go_live_validation_env_example": go_live_env_path,
        },
    )

    assert summary == {
        "gap_env_total_count": 2,
        "all_templates_cover_all_gap_envs": False,
        "template_paths": {
            "go_live_validation_env_example": str(go_live_env_path),
            "root_env_example": str(root_env_path),
        },
        "template_documented_counts": {
            "go_live_validation_env_example": 1,
            "root_env_example": 2,
        },
        "template_missing_counts": {
            "go_live_validation_env_example": 1,
            "root_env_example": 0,
        },
        "template_missing_env_names": {
            "go_live_validation_env_example": ["DE_TEST_REDIS_URL"],
            "root_env_example": [],
        },
        "templates_with_missing_envs": ["go_live_validation_env_example"],
        "missing_in_any_template": ["DE_TEST_REDIS_URL"],
    }


def test_build_gap_source_summary_reports_static_live_and_merged_counts() -> None:
    summary = build_gap_source_summary(
        [
            {
                "case_id": "dlt_github_issues",
                "tier": "public_no_auth",
                "connector_type": "rest_api",
            },
            {
                "case_id": "redis_customer_connector_test",
                "tier": "customer_credentials_required",
                "connector_type": "redis",
            },
        ],
        [
            {
                "case_id": "redis_customer_connector_test",
                "tier": "customer_credentials_required",
                "connector_type": "redis",
            },
            {
                "case_id": "snowflake_customer_connector_test",
                "tier": "customer_credentials_required",
                "connector_type": "snowflake",
            },
        ],
        [
            {
                "case_id": "dlt_github_issues",
                "tier": "public_no_auth",
                "connector_type": "rest_api",
                "source": "static_matrix",
            },
            {
                "case_id": "redis_customer_connector_test",
                "tier": "customer_credentials_required",
                "connector_type": "redis",
                "source": "static_matrix+live_connectivity",
            },
            {
                "case_id": "snowflake_customer_connector_test",
                "tier": "customer_credentials_required",
                "connector_type": "snowflake",
                "source": "live_connectivity",
            },
        ],
    )

    assert summary == {
        "static_gap_count": 2,
        "live_skip_count": 2,
        "merged_gap_count": 3,
        "live_only_case_ids": ["snowflake_customer_connector_test"],
        "static_only_case_ids": ["dlt_github_issues"],
        "merged_case_ids": [
            "dlt_github_issues",
            "redis_customer_connector_test",
            "snowflake_customer_connector_test",
        ],
        "static_gap_counts_by_tier": {
            "customer_credentials_required": 1,
            "public_no_auth": 1,
        },
        "static_gap_counts_by_connector_type": {
            "redis": 1,
            "rest_api": 1,
        },
        "live_skip_counts_by_tier": {"customer_credentials_required": 2},
        "live_skip_counts_by_connector_type": {
            "redis": 1,
            "snowflake": 1,
        },
        "merged_gap_counts_by_tier": {
            "customer_credentials_required": 2,
            "public_no_auth": 1,
        },
        "merged_gap_counts_by_connector_type": {
            "redis": 1,
            "rest_api": 1,
            "snowflake": 1,
        },
        "merged_gap_counts_by_source": {
            "live_connectivity": 1,
            "static_matrix": 1,
            "static_matrix+live_connectivity": 1,
        },
    }


