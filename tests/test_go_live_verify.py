from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from tests.go_live_verify import (
    annotate_operational_gaps_with_actions,
    build_gap_action_summary,
    build_gap_connector_summary,
    build_gap_env_summary,
    build_gap_env_resolution_summary,
    build_gap_env_template_summary,
    build_gap_source_summary,
    build_verification_metadata,
    build_go_live_next_actions,
    DEFAULT_REPORT_OUTPUT,
    DEFAULT_SUMMARY_OUTPUT,
    extract_live_connectivity_skips,
    merge_operational_gaps,
    ROOT,
    SCORECARD_PATH,
    VerificationResult,
    build_verification_steps,
    main,
    render_go_live_verify_scorecard_section,
    resolve_python_executable,
    should_sync_go_live_verify_scorecard,
    summarize_verification,
    sync_go_live_verify_scorecard,
    write_go_live_verify_markdown_report,
    write_verification_summary,
)


def test_resolve_python_executable_prefers_repo_venv() -> None:
    resolved = resolve_python_executable()
    expected = ROOT / ".venv" / "bin" / "python"
    if expected.exists():
        assert resolved == str(expected)
    else:
        assert resolved == sys.executable


def test_build_verification_steps_passes_tier_filter_only_to_connectivity() -> None:
    steps = build_verification_steps(
        "python-bin",
        parallel_tasks=4,
        mojo_workers=3,
        mojo_timeout=25,
        include_full_real=True,
        include_pytest=True,
        tiers=("credentialed_example",),
        connectors=("clickhouse",),
    )

    assert "--tiers" in steps[0].command
    assert "--connector" in steps[0].command
    assert steps[0].command[-4:] == (
        "--tiers",
        "credentialed_example",
        "--connector",
        "clickhouse",
    )
    assert "--tiers" not in steps[1].command
    assert "--tiers" not in steps[2].command
    assert "--connector" not in steps[1].command
    assert "--connector" not in steps[2].command


def test_build_verification_steps_keeps_serial_go_live_order() -> None:
    steps = build_verification_steps(
        "python-bin",
        parallel_tasks=4,
        mojo_workers=3,
        mojo_timeout=25,
        include_full_real=True,
        include_pytest=True,
        tiers=None,
        connectors=None,
    )
    assert [step.name for step in steps] == ["connectivity", "full_real", "pytest"]
    assert steps[0].command[-2:] == ("--parallel-tasks", "4")
    assert steps[1].command[-4:] == ("--mojo-workers", "3", "--mojo-timeout", "25")
    assert steps[2].command == ("python-bin", "-m", "pytest", "tests", "-q")


def test_build_verification_steps_supports_connectivity_only_runs() -> None:
    steps = build_verification_steps(
        "python-bin",
        parallel_tasks=4,
        mojo_workers=3,
        mojo_timeout=25,
        include_full_real=False,
        include_pytest=False,
        tiers=("credentialed_example",),
        connectors=("clickhouse",),
    )

    assert [step.name for step in steps] == ["connectivity"]
    assert steps[0].command[-4:] == (
        "--tiers",
        "credentialed_example",
        "--connector",
        "clickhouse",
    )


def test_summarize_verification_reports_completed_and_failed_steps() -> None:
    planned_steps = [
        type("Step", (), {"name": "connectivity", "command": ("python", "connectivity.py")})(),
        type("Step", (), {"name": "full_real", "command": ("python", "full_real.py")})(),
    ]
    summary = summarize_verification(
        {
            "summary": {
                "configured_cases": 5,
                "behavior_ready_cases": 5,
                "total_cases": 15,
            }
        },
        planned_steps,
        [
            type("Result", (), {"name": "connectivity", "returncode": 0, "duration_s": 1.25})(),
            type("Result", (), {"name": "full_real", "returncode": 1, "duration_s": 2.5})(),
        ],
        [{"requirement": "all_configured", "case_id": "snowflake", "reason": "missing env"}],
    )

    assert summary["requirement_failures"][0]["case_id"] == "snowflake"
    assert summary["completed_steps"] == ["connectivity"]
    assert summary["failed_steps"] == ["full_real"]
    assert summary["planned_steps"] == [
        {"name": "connectivity", "command": ["python", "connectivity.py"]},
        {"name": "full_real", "command": ["python", "full_real.py"]},
    ]
    assert summary["step_results"][0]["duration_s"] == 1.25


def test_write_verification_summary_writes_json(tmp_path) -> None:
    output_path = tmp_path / "go_live_verify_summary.json"
    summary = {
        "matrix_summary": {"configured_cases": 8, "behavior_ready_cases": 8, "total_cases": 19},
        "gap_source_summary": {
            "static_gap_count": 0,
            "live_skip_count": 0,
            "merged_gap_count": 0,
            "live_only_case_ids": [],
            "static_only_case_ids": [],
            "merged_case_ids": [],
            "static_gap_counts_by_tier": {},
            "static_gap_counts_by_connector_type": {},
            "live_skip_counts_by_tier": {},
            "live_skip_counts_by_connector_type": {},
            "merged_gap_counts_by_tier": {},
            "merged_gap_counts_by_connector_type": {},
            "merged_gap_counts_by_source": {},
        },
        "gap_action_summary": {
            "mapped_case_count": 0,
            "unmapped_case_ids": [],
            "action_case_counts": {},
            "action_case_ids": {},
            "action_env_names": {},
            "action_env_counts": {},
            "action_connector_types": {},
            "action_connector_counts": {},
            "terminal_action_codes": [],
        },
        "gap_connector_summary": {
            "connector_case_counts": {},
            "connector_case_ids": {},
            "connector_action_codes": {},
            "connector_env_counts": {},
            "connector_env_names": {},
        },
        "gap_env_summary": {
            "env_total_count": 0,
            "shared_env_names": [],
            "tier_env_counts": {},
            "env_case_counts": {},
            "env_case_ids": {},
            "env_connector_types": {},
            "env_connector_counts": {},
            "env_action_codes": {},
            "env_action_counts": {},
            "env_tiers": {},
        },
        "gap_env_resolution_summary": {
            "resolver_supported_count": 0,
            "manual_only_count": 0,
            "resolver_supported_env_names": [],
            "manual_only_env_names": [],
            "env_candidate_names": {},
            "env_group_names": {},
            "group_env_counts": {},
        },
        "gap_env_template_summary": {
            "gap_env_total_count": 0,
            "all_templates_cover_all_gap_envs": True,
            "template_paths": {},
            "template_documented_counts": {},
            "template_missing_counts": {},
            "template_missing_env_names": {},
            "templates_with_missing_envs": [],
            "missing_in_any_template": [],
        },
        "operational_gaps": [],
        "next_actions": [],
        "requirement_failures": [],
        "completed_steps": ["connectivity", "full_real"],
        "failed_steps": [],
        "step_results": [
            {"name": "connectivity", "returncode": 0, "duration_s": 12.5},
            {"name": "full_real", "returncode": 0, "duration_s": 98.7},
        ],
    }

    write_verification_summary(summary, output_path=output_path)

    assert json.loads(output_path.read_text()) == summary


def test_write_go_live_verify_markdown_report_writes_markdown(tmp_path) -> None:
    output_path = tmp_path / "go_live_verify_report.md"
    summary = {
        "generated_at": "2026-05-22T06:24:38Z",
        "python_executable": "python-bin",
        "output_path": "build/go_live_verify_summary.json",
        "filters": {"tiers": [], "connectors": []},
        "options": {
            "include_full_real": True,
            "include_pytest": False,
            "require_all_configured": False,
            "require_all_behavior_ready": False,
            "strict": False,
        },
        "matrix_summary": {
            "total_cases": 19,
            "configured_cases": 8,
            "behavior_ready_cases": 8,
            "tiers": {
                "public_no_auth": {"total": 8, "configured": 7, "behavior_ready": 7},
                "credentialed_example": {"total": 2, "configured": 0, "behavior_ready": 0},
                "customer_credentials_required": {
                    "total": 9,
                    "configured": 1,
                    "behavior_ready": 1,
                },
            },
        },
        "static_operational_gaps": [
            {
                "case_id": "dlt_github_issues",
                "label": "dlt GitHub issues example source registration",
                "tier": "public_no_auth",
                "connector_type": "rest_api",
                "gap_type": "not_configured",
                "reason": "unauthenticated dlt GitHub issues case disabled by default; set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1",
            }
        ],
        "gap_source_summary": {
            "static_gap_count": 1,
            "live_skip_count": 1,
            "merged_gap_count": 1,
            "live_only_case_ids": ["snowflake_customer_connector_test"],
            "static_only_case_ids": ["dlt_github_issues"],
            "merged_case_ids": ["dlt_github_issues"],
            "static_gap_counts_by_tier": {"public_no_auth": 1},
            "static_gap_counts_by_connector_type": {"rest_api": 1},
            "live_skip_counts_by_tier": {"customer_credentials_required": 1},
            "live_skip_counts_by_connector_type": {"snowflake": 1},
            "merged_gap_counts_by_tier": {"public_no_auth": 1},
            "merged_gap_counts_by_connector_type": {"rest_api": 1},
            "merged_gap_counts_by_source": {"static_matrix": 1},
        },
        "operational_gaps": [
            {
                "case_id": "dlt_github_issues",
                "label": "dlt GitHub issues example source registration",
                "tier": "public_no_auth",
                "connector_type": "rest_api",
                "gap_type": "not_configured",
                "reason": "unauthenticated dlt GitHub issues case disabled by default; set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1",
                "source": "static_matrix",
                "sources": ["static_matrix"],
                "static_reason": "unauthenticated dlt GitHub issues case disabled by default; set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1",
                "live_reason": None,
                "action_codes": ["enable_opt_in_public_cases"],
            }
        ],
        "live_connectivity_skips": [
            {
                "case_id": "snowflake_customer_connector_test",
                "label": "Snowflake connector /test",
                "tier": "customer_credentials_required",
                "connector_type": "snowflake",
                "gap_type": "not_behavior_ready",
                "reason": "Snowflake live validation blocked by account network policy; skipping external customer-credential case.",
            }
        ],
        "next_actions": [
            {
                "code": "enable_opt_in_public_cases",
                "message": "Enable the optional public REST cases before rerunning the public connectivity proof.",
                "command": "DE_ENABLE_SLOW_PUBLIC_REST_CASES=1 make test-go-live-connectivity",
                "details": {
                    "case_ids": ["dlt_github_issues"],
                    "env_names": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
                },
            }
        ],
        "gap_action_summary": {
            "mapped_case_count": 1,
            "unmapped_case_ids": [],
            "action_case_counts": {"enable_opt_in_public_cases": 1},
            "action_case_ids": {
                "enable_opt_in_public_cases": ["dlt_github_issues"],
            },
            "action_env_names": {
                "enable_opt_in_public_cases": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
            },
            "action_env_counts": {"enable_opt_in_public_cases": 1},
            "action_connector_types": {
                "enable_opt_in_public_cases": ["rest_api"],
            },
            "action_connector_counts": {"enable_opt_in_public_cases": 1},
            "terminal_action_codes": [],
        },
        "gap_connector_summary": {
            "connector_case_counts": {"rest_api": 1},
            "connector_case_ids": {"rest_api": ["dlt_github_issues"]},
            "connector_action_codes": {"rest_api": ["enable_opt_in_public_cases"]},
            "connector_env_counts": {"rest_api": 1},
            "connector_env_names": {
                "rest_api": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
            },
        },
        "gap_env_summary": {
            "env_total_count": 1,
            "shared_env_names": [],
            "tier_env_counts": {"public_no_auth": 1},
            "env_case_counts": {"DE_ENABLE_SLOW_PUBLIC_REST_CASES": 1},
            "env_case_ids": {
                "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["dlt_github_issues"],
            },
            "env_connector_types": {
                "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["rest_api"],
            },
            "env_connector_counts": {"DE_ENABLE_SLOW_PUBLIC_REST_CASES": 1},
            "env_action_codes": {
                "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["enable_opt_in_public_cases"],
            },
            "env_action_counts": {"DE_ENABLE_SLOW_PUBLIC_REST_CASES": 1},
            "env_tiers": {
                "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["public_no_auth"],
            },
        },
        "gap_env_resolution_summary": {
            "resolver_supported_count": 0,
            "manual_only_count": 1,
            "resolver_supported_env_names": [],
            "manual_only_env_names": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
            "env_candidate_names": {
                "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
            },
            "env_group_names": {},
            "group_env_counts": {},
        },
        "gap_env_template_summary": {
            "gap_env_total_count": 1,
            "all_templates_cover_all_gap_envs": True,
            "template_paths": {
                "go_live_validation_env_example": "tests/integration/go_live_validation.env.example",
                "root_env_example": ".env.example",
            },
            "template_documented_counts": {
                "go_live_validation_env_example": 1,
                "root_env_example": 1,
            },
            "template_missing_counts": {
                "go_live_validation_env_example": 0,
                "root_env_example": 0,
            },
            "template_missing_env_names": {
                "go_live_validation_env_example": [],
                "root_env_example": [],
            },
            "templates_with_missing_envs": [],
            "missing_in_any_template": [],
        },
        "requirement_failures": [],
        "completed_steps": ["connectivity"],
        "failed_steps": [],
        "planned_steps": [
            {"name": "connectivity", "command": ["python-bin", "connectivity.py"]}
        ],
        "step_results": [
            {"name": "connectivity", "returncode": 0, "duration_s": 12.5}
        ],
    }

    write_go_live_verify_markdown_report(summary, output_path=output_path)

    rendered = output_path.read_text(encoding="utf-8")
    assert "# Go-live verifier report" in rendered
    assert "Summary path: `build/go_live_verify_summary.json`" in rendered
    assert "- Duration: `12.50s`" in rendered
    assert "## Operational gaps" in rendered
    assert "dlt_github_issues" in rendered
    assert "[source: static_matrix]" in rendered
    assert "[actions: enable_opt_in_public_cases]" in rendered
    assert "## Live connectivity skips" in rendered
    assert "snowflake_customer_connector_test" in rendered
    assert "## Gap sources" in rendered
    assert "- Static matrix gaps: `1`" in rendered
    assert "- Live connectivity skips: `1`" in rendered
    assert "- Merged operational gaps: `1`" in rendered
    assert "- Static gaps by tier: `public_no_auth 1`" in rendered
    assert "- Static gaps by connector: `rest_api 1`" in rendered
    assert "- Live skips by tier: `customer_credentials_required 1`" in rendered
    assert "- Live skips by connector: `snowflake 1`" in rendered
    assert "- Merged gaps by tier: `public_no_auth 1`" in rendered
    assert "- Merged gaps by connector: `rest_api 1`" in rendered
    assert "- Merged gaps by source: `static_matrix 1`" in rendered
    assert "- Live-only blockers beyond the static matrix: `snowflake_customer_connector_test`" in rendered
    assert "## Next actions" in rendered
    assert "enable_opt_in_public_cases" in rendered
    assert "## Action routing" in rendered
    assert "- Direct remediation coverage: `1/1` cases" in rendered
    assert "- Action case counts: `enable_opt_in_public_cases 1`" in rendered
    assert "- Action env counts: `enable_opt_in_public_cases 1`" in rendered
    assert "- Action connector counts: `enable_opt_in_public_cases 1`" in rendered
    assert "- Terminal actions: `none`" in rendered
    assert "- Unmapped cases: `none`" in rendered
    assert "- `enable_opt_in_public_cases` cases: `dlt_github_issues`" in rendered
    assert "- `enable_opt_in_public_cases` envs: `DE_ENABLE_SLOW_PUBLIC_REST_CASES`" in rendered
    assert "- `enable_opt_in_public_cases` connectors: `rest_api`" in rendered
    assert "## Connector routing" in rendered
    assert "- Connector case counts: `rest_api 1`" in rendered
    assert "- Connector env counts: `rest_api 1`" in rendered
    assert "- `rest_api` cases: `dlt_github_issues`" in rendered
    assert "- `rest_api` actions: `enable_opt_in_public_cases`" in rendered
    assert "- `rest_api` envs: `DE_ENABLE_SLOW_PUBLIC_REST_CASES`" in rendered
    assert "## Env routing" in rendered
    assert "- Total mapped envs: `1`" in rendered
    assert "- Tier env counts: `public_no_auth 1`" in rendered
    assert "- Shared envs: `none`" in rendered
    assert "- `DE_ENABLE_SLOW_PUBLIC_REST_CASES` cases: `dlt_github_issues`" in rendered
    assert "- `DE_ENABLE_SLOW_PUBLIC_REST_CASES` actions: `enable_opt_in_public_cases`" in rendered
    assert "- `DE_ENABLE_SLOW_PUBLIC_REST_CASES` connectors: `rest_api`" in rendered
    assert "- `DE_ENABLE_SLOW_PUBLIC_REST_CASES` tiers: `public_no_auth`" in rendered
    assert "## Env resolution" in rendered
    assert "- Resolver-supported envs: `0`" in rendered
    assert "- Manual-only envs: `1`" in rendered
    assert "- Group env counts: `none`" in rendered
    assert "- Manual-only env names: `DE_ENABLE_SLOW_PUBLIC_REST_CASES`" in rendered
    assert "- `DE_ENABLE_SLOW_PUBLIC_REST_CASES` candidates: `DE_ENABLE_SLOW_PUBLIC_REST_CASES`" in rendered
    assert "## Env template coverage" in rendered
    assert "- Gap env total: `1`" in rendered
    assert "- All templates cover all current gap envs: `yes`" in rendered
    assert "- `root_env_example` (`.env.example`): `1/1` documented, missing `none`" in rendered
    assert (
        "- `go_live_validation_env_example` "
        "(`tests/integration/go_live_validation.env.example`): `1/1` documented, missing `none`"
    ) in rendered


def test_build_go_live_next_actions_groups_operational_gaps() -> None:
    actions = build_go_live_next_actions(
        [
            {
                "case_id": "dlt_github_issues",
                "label": "dlt GitHub issues example source registration",
                "tier": "public_no_auth",
                "connector_type": "rest_api",
                "gap_type": "not_configured",
                "reason": "unauthenticated dlt GitHub issues case disabled by default; set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1",
            },
            {
                "case_id": "fivetran_fred_gnpca",
                "label": "Fivetran FRED example source registration",
                "tier": "credentialed_example",
                "connector_type": "rest_api",
                "gap_type": "not_configured",
                "reason": "required env not provided: DE_TEST_FRED_API_KEY",
            },
            {
                "case_id": "redis_customer_connector_test",
                "label": "Redis connector /test",
                "tier": "customer_credentials_required",
                "connector_type": "redis",
                "gap_type": "not_configured",
                "reason": "required env not provided: DE_TEST_REDIS_URL",
            },
            {
                "case_id": "snowflake_customer_connector_test",
                "label": "Snowflake connector /test",
                "tier": "customer_credentials_required",
                "connector_type": "snowflake",
                "gap_type": "not_configured",
                "reason": "Snowflake live validation blocked by account network policy; skipping external customer-credential case.",
            },
        ]
    )

    assert [action["code"] for action in actions] == [
        "enable_opt_in_public_cases",
        "set_credentialed_example_envs",
        "set_customer_connector_envs",
        "resolve_network_policy_blockers",
        "rerun_strict_go_live_gate",
    ]
    assert actions[1]["details"]["env_names"] == ["DE_TEST_FRED_API_KEY"]
    assert actions[2]["details"]["env_names"] == ["DE_TEST_REDIS_URL"]
    assert actions[3]["command"] == "make go-live-probe-snowflake"


def test_annotate_operational_gaps_with_actions_maps_case_ids_to_action_codes() -> None:
    annotated = annotate_operational_gaps_with_actions(
        [
            {"case_id": "dlt_github_issues"},
            {"case_id": "snowflake_customer_connector_test"},
            {"case_id": "unknown_case"},
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

    assert annotated == [
        {"case_id": "dlt_github_issues", "action_codes": ["enable_opt_in_public_cases"]},
        {
            "case_id": "snowflake_customer_connector_test",
            "action_codes": ["resolve_network_policy_blockers"],
        },
        {"case_id": "unknown_case", "action_codes": []},
    ]


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


def test_extract_live_connectivity_skips_maps_case_labels_and_gap_types() -> None:
    output = """
Skipped checks:
  - Snowflake connector /test: Snowflake live validation blocked by account network policy; skipping external customer-credential case.
  - dlt GitHub issues example source registration: unauthenticated dlt GitHub issues case disabled by default; set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1
Slowest:
"""
    statuses = [
        type(
            "Status",
            (),
            {
                "case_id": "snowflake_customer_connector_test",
                "configured": True,
            },
        )(),
        type(
            "Status",
            (),
            {
                "case_id": "dlt_github_issues",
                "configured": False,
            },
        )(),
    ]

    gaps = extract_live_connectivity_skips(output, statuses)

    assert gaps == [
        {
            "case_id": "snowflake_customer_connector_test",
            "label": "Snowflake connector /test",
            "tier": "customer_credentials_required",
            "connector_type": "snowflake",
            "gap_type": "not_behavior_ready",
            "reason": "Snowflake live validation blocked by account network policy; skipping external customer-credential case.",
        },
        {
            "case_id": "dlt_github_issues",
            "label": "dlt GitHub issues example source registration",
            "tier": "public_no_auth",
            "connector_type": "rest_api",
            "gap_type": "not_configured",
            "reason": "unauthenticated dlt GitHub issues case disabled by default; set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1",
        },
    ]


def test_merge_operational_gaps_prefers_live_reason_for_same_case() -> None:
    merged = merge_operational_gaps(
        [
            {
                "case_id": "snowflake_customer_connector_test",
                "label": "Snowflake connector /test",
                "tier": "customer_credentials_required",
                "connector_type": "snowflake",
                "gap_type": "not_configured",
                "reason": "required env not provided: DE_TEST_SNOWFLAKE_ACCOUNT",
            }
        ],
        [
            {
                "case_id": "snowflake_customer_connector_test",
                "label": "Snowflake connector /test",
                "tier": "customer_credentials_required",
                "connector_type": "snowflake",
                "gap_type": "not_behavior_ready",
                "reason": "Snowflake live validation blocked by account network policy; skipping external customer-credential case.",
            }
        ],
    )

    assert merged == [
        {
            "case_id": "snowflake_customer_connector_test",
            "label": "Snowflake connector /test",
            "tier": "customer_credentials_required",
            "connector_type": "snowflake",
            "gap_type": "not_behavior_ready",
            "reason": "Snowflake live validation blocked by account network policy; skipping external customer-credential case.",
            "source": "static_matrix+live_connectivity",
            "sources": ["static_matrix", "live_connectivity"],
            "static_reason": "required env not provided: DE_TEST_SNOWFLAKE_ACCOUNT",
            "live_reason": "Snowflake live validation blocked by account network policy; skipping external customer-credential case.",
        }
    ]


def test_build_verification_metadata_captures_filters_and_options(monkeypatch, tmp_path) -> None:
    output_path = tmp_path / "go_live_verify_summary.json"
    monkeypatch.setattr("tests.go_live_verify.time.strftime", lambda fmt, now: "2026-05-22T02:20:00Z")

    metadata = build_verification_metadata(
        python_executable="python-bin",
        output_path=output_path,
        selected_tiers=("credentialed_example",),
        selected_connectors=("clickhouse", "snowflake"),
        include_full_real=False,
        include_pytest=True,
        require_all_configured=True,
        require_all_behavior_ready=False,
        strict=False,
    )

    assert metadata == {
        "generated_at": "2026-05-22T02:20:00Z",
        "python_executable": "python-bin",
        "output_path": str(output_path),
        "filters": {
            "tiers": ["credentialed_example"],
            "connectors": ["clickhouse", "snowflake"],
        },
        "options": {
            "include_full_real": False,
            "include_pytest": True,
            "require_all_configured": True,
            "require_all_behavior_ready": False,
            "strict": False,
        },
    }


def test_should_sync_go_live_verify_scorecard_accepts_only_canonical_mode() -> None:
    assert should_sync_go_live_verify_scorecard(
        output_path=DEFAULT_SUMMARY_OUTPUT,
        selected_tiers=None,
        selected_connectors=None,
        include_full_real=True,
        include_pytest=False,
        require_all_configured=False,
        require_all_behavior_ready=False,
        strict=False,
    )
    assert should_sync_go_live_verify_scorecard(
        output_path=DEFAULT_SUMMARY_OUTPUT,
        selected_tiers=None,
        selected_connectors=None,
        include_full_real=True,
        include_pytest=True,
        require_all_configured=False,
        require_all_behavior_ready=False,
        strict=False,
    )
    assert not should_sync_go_live_verify_scorecard(
        output_path=Path("/tmp/go_live_verify_summary.json"),
        selected_tiers=None,
        selected_connectors=None,
        include_full_real=True,
        include_pytest=False,
        require_all_configured=False,
        require_all_behavior_ready=False,
        strict=False,
    )
    assert not should_sync_go_live_verify_scorecard(
        output_path=DEFAULT_SUMMARY_OUTPUT,
        selected_tiers=("credentialed_example",),
        selected_connectors=None,
        include_full_real=True,
        include_pytest=False,
        require_all_configured=False,
        require_all_behavior_ready=False,
        strict=False,
    )


def test_sync_go_live_verify_scorecard_inserts_section_before_llm_rollout(
    tmp_path, monkeypatch
) -> None:
    scorecard_path = tmp_path / "scorecard.md"
    scorecard_path.write_text(
        "# Decision Engine Scorecard\n\n"
        "Updated: 2026-05-22\n\n"
        "## Current measured state\n\n"
        "placeholder\n\n"
        "## LLM rollout proof (2026-05-22)\n\n"
        "existing rollout text\n",
        encoding="utf-8",
    )
    summary = {
        "generated_at": "2026-05-22T06:24:38Z",
        "matrix_summary": {"total_cases": 19, "configured_cases": 8, "behavior_ready_cases": 8},
        "static_operational_gaps": [
            {
                "case_id": "dlt_github_issues",
                "label": "dlt GitHub issues example source registration",
                "tier": "public_no_auth",
                "connector_type": "rest_api",
                "gap_type": "not_configured",
                "reason": "unauthenticated dlt GitHub issues case disabled by default; set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1",
            }
        ],
        "live_connectivity_skips": [
            {
                "case_id": "snowflake_customer_connector_test",
                "label": "Snowflake connector /test",
                "tier": "customer_credentials_required",
                "connector_type": "snowflake",
                "gap_type": "not_behavior_ready",
                "reason": "Snowflake live validation blocked by account network policy; skipping external customer-credential case.",
            }
        ],
        "operational_gaps": [
            {
                "case_id": "dlt_github_issues",
                "label": "dlt GitHub issues example source registration",
                "tier": "public_no_auth",
                "connector_type": "rest_api",
                "gap_type": "not_configured",
                "reason": "unauthenticated dlt GitHub issues case disabled by default; set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1",
                "source": "static_matrix",
                "action_codes": ["enable_opt_in_public_cases"],
            }
        ],
        "gap_source_summary": {
            "static_gap_count": 1,
            "live_skip_count": 1,
            "merged_gap_count": 1,
            "live_only_case_ids": ["snowflake_customer_connector_test"],
            "static_only_case_ids": ["dlt_github_issues"],
            "merged_case_ids": ["dlt_github_issues"],
            "static_gap_counts_by_tier": {"public_no_auth": 1},
            "static_gap_counts_by_connector_type": {"rest_api": 1},
            "live_skip_counts_by_tier": {"customer_credentials_required": 1},
            "live_skip_counts_by_connector_type": {"snowflake": 1},
            "merged_gap_counts_by_tier": {"public_no_auth": 1},
            "merged_gap_counts_by_connector_type": {"rest_api": 1},
            "merged_gap_counts_by_source": {"static_matrix": 1},
        },
        "next_actions": [
            {
                "code": "enable_opt_in_public_cases",
                "message": "Enable the optional public REST cases before rerunning the public connectivity proof.",
                "command": "DE_ENABLE_SLOW_PUBLIC_REST_CASES=1 make test-go-live-connectivity",
                "details": {
                    "case_ids": ["dlt_github_issues"],
                    "env_names": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
                },
            }
        ],
        "gap_action_summary": {
            "mapped_case_count": 1,
            "unmapped_case_ids": [],
            "action_case_counts": {"enable_opt_in_public_cases": 1},
            "action_case_ids": {
                "enable_opt_in_public_cases": ["dlt_github_issues"],
            },
            "action_env_names": {
                "enable_opt_in_public_cases": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
            },
            "action_env_counts": {"enable_opt_in_public_cases": 1},
            "action_connector_types": {
                "enable_opt_in_public_cases": ["rest_api"],
            },
            "action_connector_counts": {"enable_opt_in_public_cases": 1},
            "terminal_action_codes": [],
        },
        "requirement_failures": [],
        "completed_steps": ["connectivity", "full_real"],
        "failed_steps": [],
        "planned_steps": [
            {"name": "connectivity", "command": ["python", "connectivity.py"]},
            {"name": "full_real", "command": ["python", "full_real.py"]},
        ],
        "step_results": [
            {"name": "connectivity", "duration_s": 32.89},
            {"name": "full_real", "duration_s": 339.5},
        ],
        "filters": {"tiers": [], "connectors": []},
        "options": {
            "include_full_real": True,
            "include_pytest": False,
            "require_all_configured": False,
            "require_all_behavior_ready": False,
            "strict": False,
        },
    }
    full_real_summary_path = tmp_path / "go_live_full_real_summary.json"
    full_real_summary_path.write_text(
        json.dumps(
            {
                "passed": 24,
                "failed": 0,
                "total": 24,
                "details": {
                    "status": "complete",
                    "live_suite_count": 13,
                    "local_suite_count": 8,
                    "top_level_suite_count": 3,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("tests.go_live_verify.GO_LIVE_FULL_REAL_SUMMARY_PATH", full_real_summary_path)

    sync_go_live_verify_scorecard(summary, scorecard_path=scorecard_path)

    text = scorecard_path.read_text(encoding="utf-8")
    assert "## Go-live verifier (2026-05-22)" in text
    assert "build/go_live_verify_report.md" in text
    assert "8/19 configured, 8/19 behavior-ready, completed steps connectivity + full_real, 0 failed steps" in text
    assert "Full real suite" in text
    assert "24/24 suites passed; live API-facing 13, local benchmark/regression 8, top-level verifier/bundle/A-Z 3" in text
    assert "connectivity + full_real" in text
    assert "connectivity 32.89s, full_real 339.50s" in text
    assert "unfiltered, non-strict, includes full_real, excludes pytest" in text
    assert "Static matrix operational gaps" in text
    assert "1 cases from the current static matrix status before live connectivity overrides" in text
    assert "Live connectivity skips" in text
    assert "1 skips captured from the latest connectivity run and merged into operational gaps" in text
    assert "Gap source breakdown" in text
    assert (
        "static tiers public_no_auth 1; live tiers customer_credentials_required 1; "
        "merged sources static_matrix 1"
    ) in text
    assert "Gap connector breakdown" in text
    assert "merged connectors rest_api 1" in text
    assert "Outstanding operational gaps" in text
    assert "1 cases outside repo-owned proof: public_no_auth 1" in text
    assert "Operator next actions" in text
    assert "1 action groups ready from current operational gaps" in text
    assert "Gap action routing" in text
    assert "1/1 cases mapped; actions enable_opt_in_public_cases 1; envs enable_opt_in_public_cases 1; connectors enable_opt_in_public_cases 1; terminal none; unmapped none" in text
    assert "Gap connector routing" in text
    assert "cases rest_api 1; envs rest_api 1" in text
    assert "Gap env routing" in text
    assert "1 envs mapped; tiers public_no_auth 1; shared none" in text
    assert "Gap env templates" in text
    assert "## LLM rollout proof (2026-05-22)" in text


def test_render_go_live_verify_scorecard_section_marks_failed_runs_red(tmp_path, monkeypatch) -> None:
    full_real_summary_path = tmp_path / "go_live_full_real_summary.json"
    full_real_summary_path.write_text(
        json.dumps(
            {
                "passed": 24,
                "failed": 0,
                "total": 24,
                "details": {
                    "status": "complete",
                    "live_suite_count": 13,
                    "local_suite_count": 8,
                    "top_level_suite_count": 3,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("tests.go_live_verify.GO_LIVE_FULL_REAL_SUMMARY_PATH", full_real_summary_path)
    rendered = render_go_live_verify_scorecard_section(
        {
            "generated_at": "2026-05-22T06:24:38Z",
            "matrix_summary": {"total_cases": 19, "configured_cases": 8, "behavior_ready_cases": 8},
            "static_operational_gaps": [
                {
                    "case_id": "dlt_github_issues",
                    "label": "dlt GitHub issues example source registration",
                    "tier": "public_no_auth",
                    "connector_type": "rest_api",
                    "gap_type": "not_configured",
                    "reason": "unauthenticated dlt GitHub issues case disabled by default; set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1",
                }
            ],
            "live_connectivity_skips": [
                {
                    "case_id": "snowflake_customer_connector_test",
                    "label": "Snowflake connector /test",
                    "tier": "customer_credentials_required",
                    "connector_type": "snowflake",
                    "gap_type": "not_behavior_ready",
                    "reason": "Snowflake live validation blocked by account network policy; skipping external customer-credential case.",
                }
            ],
            "operational_gaps": [
                {
                    "case_id": "dlt_github_issues",
                    "label": "dlt GitHub issues example source registration",
                    "tier": "public_no_auth",
                    "connector_type": "rest_api",
                    "gap_type": "not_configured",
                    "reason": "unauthenticated dlt GitHub issues case disabled by default; set DE_ENABLE_SLOW_PUBLIC_REST_CASES=1",
                    "source": "static_matrix",
                    "action_codes": ["enable_opt_in_public_cases"],
                }
            ],
            "gap_source_summary": {
                "static_gap_count": 1,
                "live_skip_count": 1,
                "merged_gap_count": 1,
                "live_only_case_ids": ["snowflake_customer_connector_test"],
                "static_only_case_ids": ["dlt_github_issues"],
                "merged_case_ids": ["dlt_github_issues"],
                "static_gap_counts_by_tier": {"public_no_auth": 1},
                "static_gap_counts_by_connector_type": {"rest_api": 1},
                "live_skip_counts_by_tier": {"customer_credentials_required": 1},
                "live_skip_counts_by_connector_type": {"snowflake": 1},
                "merged_gap_counts_by_tier": {"public_no_auth": 1},
                "merged_gap_counts_by_connector_type": {"rest_api": 1},
                "merged_gap_counts_by_source": {"static_matrix": 1},
            },
            "next_actions": [
                {
                    "code": "enable_opt_in_public_cases",
                    "message": "Enable the optional public REST cases before rerunning the public connectivity proof.",
                    "command": "DE_ENABLE_SLOW_PUBLIC_REST_CASES=1 make test-go-live-connectivity",
                    "details": {
                        "case_ids": ["dlt_github_issues"],
                        "env_names": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
                    },
                }
            ],
            "gap_action_summary": {
                "mapped_case_count": 1,
                "unmapped_case_ids": [],
                "action_case_counts": {"enable_opt_in_public_cases": 1},
                "action_case_ids": {
                    "enable_opt_in_public_cases": ["dlt_github_issues"],
                },
                "action_env_names": {
                    "enable_opt_in_public_cases": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
                },
                "action_env_counts": {"enable_opt_in_public_cases": 1},
                "action_connector_types": {
                    "enable_opt_in_public_cases": ["rest_api"],
                },
                "action_connector_counts": {"enable_opt_in_public_cases": 1},
                "terminal_action_codes": [],
            },
            "gap_connector_summary": {
                "connector_case_counts": {"rest_api": 1},
                "connector_case_ids": {"rest_api": ["dlt_github_issues"]},
                "connector_action_codes": {"rest_api": ["enable_opt_in_public_cases"]},
                "connector_env_counts": {"rest_api": 1},
                "connector_env_names": {
                    "rest_api": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
                },
            },
            "gap_env_resolution_summary": {
                "resolver_supported_count": 0,
                "manual_only_count": 1,
                "resolver_supported_env_names": [],
                "manual_only_env_names": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
                "env_candidate_names": {
                    "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
                },
                "env_group_names": {},
                "group_env_counts": {},
            },
            "gap_env_template_summary": {
                "gap_env_total_count": 1,
                "all_templates_cover_all_gap_envs": True,
                "template_paths": {
                    "go_live_validation_env_example": "tests/integration/go_live_validation.env.example",
                    "root_env_example": ".env.example",
                },
                "template_documented_counts": {
                    "go_live_validation_env_example": 1,
                    "root_env_example": 1,
                },
                "template_missing_counts": {
                    "go_live_validation_env_example": 0,
                    "root_env_example": 0,
                },
                "template_missing_env_names": {
                    "go_live_validation_env_example": [],
                    "root_env_example": [],
                },
                "templates_with_missing_envs": [],
                "missing_in_any_template": [],
            },
            "requirement_failures": [],
            "completed_steps": [],
            "failed_steps": ["connectivity"],
            "planned_steps": [
                {"name": "connectivity", "command": ["python", "connectivity.py"]},
                {"name": "full_real", "command": ["python", "full_real.py"]},
            ],
            "step_results": [{"name": "connectivity", "duration_s": 3.744}],
            "filters": {"tiers": [], "connectors": []},
            "options": {
                "include_full_real": True,
                "include_pytest": False,
                "require_all_configured": False,
                "require_all_behavior_ready": False,
                "strict": False,
            },
        }
    )

    assert "| Serial verifier summary | 8/19 configured, 8/19 behavior-ready, completed steps none, 1 failed steps |" in rendered
    assert "`tests/go_live_verify.py`, `tests/test_go_live_verify.py` | Red |" in rendered
    assert (
        "| Full real suite | 24/24 suites passed; live API-facing 13, local benchmark/regression 8, "
        "top-level verifier/bundle/A-Z 3 | "
        "`build/go_live_full_real_summary.json`, `tests/integration/test_go_live_full_real.py` | Green |"
    ) in rendered
    assert "| Latest serial durations | connectivity 3.74s |" in rendered
    assert "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md` | Red |" in rendered
    assert "| Static matrix operational gaps | 1 cases from the current static matrix status before live connectivity overrides |" in rendered
    assert "`build/go_live_verify_summary.json`, `tests/go_live_matrix_status.py` | Amber |" in rendered
    assert "| Live connectivity skips | 1 skips captured from the latest connectivity run and merged into operational gaps |" in rendered
    assert "`tests/integration/test_go_live_connectivity_real.py` | Amber |" in rendered
    assert "| Gap source breakdown | static tiers public_no_auth 1; live tiers customer_credentials_required 1; merged sources static_matrix 1 |" in rendered
    assert "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, `tests/go_live_verify.py` | Amber |" in rendered
    assert "| Gap connector breakdown | merged connectors rest_api 1 |" in rendered
    assert "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, `tests/go_live_verify.py` | Amber |" in rendered
    assert "| Outstanding operational gaps | 1 cases outside repo-owned proof: public_no_auth 1 |" in rendered
    assert "`tests/go_live_matrix_status.py` | Amber |" in rendered
    assert "| Operator next actions | 1 action groups ready from current operational gaps |" in rendered
    assert (
        "| Gap action routing | 1/1 cases mapped; actions enable_opt_in_public_cases 1; envs enable_opt_in_public_cases 1; connectors enable_opt_in_public_cases 1; "
        "terminal none; unmapped none |"
    ) in rendered
    assert "| Gap connector routing | cases rest_api 1; envs rest_api 1 |" in rendered
    assert "| Gap env routing | 1 envs mapped; tiers public_no_auth 1; shared none |" in rendered
    assert (
        "| Gap env resolution | resolver-supported 0; manual-only 1; groups none; "
        "manual DE_ENABLE_SLOW_PUBLIC_REST_CASES |"
    ) in rendered
    assert (
        "| Gap env templates | root_env_example 1/1, go_live_validation_env_example 1/1; "
        "missing none | "
    ) in rendered


def test_main_writes_summary_when_requirements_fail(monkeypatch, tmp_path, capsys) -> None:
    output_path = tmp_path / "go_live_verify_summary.json"
    failure = type(
        "Failure",
        (),
        {
            "requirement": "all_configured",
            "case_id": "snowflake_customer_connector_test",
            "reason": "missing env",
        },
    )()

    monkeypatch.setattr("tests.go_live_verify.collect_matrix_status", lambda: [])
    monkeypatch.setattr("tests.go_live_verify.filter_statuses_by_connectors", lambda statuses, selected: statuses)
    monkeypatch.setattr("tests.go_live_verify.collect_requirement_failures", lambda *args, **kwargs: [failure])
    monkeypatch.setattr(
        "tests.go_live_verify.matrix_status_payload",
        lambda statuses: {
            "summary": {"configured_cases": 8, "behavior_ready_cases": 8, "total_cases": 19},
            "cases": [],
            "operational_gaps": [],
            "requirement_failures": [],
        },
    )
    monkeypatch.setattr("tests.go_live_verify.render_matrix_status", lambda statuses: "matrix")
    monkeypatch.setattr("tests.go_live_verify.render_requirement_failures", lambda failures: "requirements")
    monkeypatch.setattr("tests.go_live_verify.resolve_python_executable", lambda: "python-bin")
    monkeypatch.setattr("tests.go_live_verify.time.strftime", lambda fmt, now: "2026-05-22T02:21:00Z")
    monkeypatch.setattr(
        "tests.go_live_verify.sync_go_live_verify_scorecard",
        lambda summary, *, scorecard_path=SCORECARD_PATH: (_ for _ in ()).throw(
            AssertionError("scorecard should not sync for custom output paths")
        ),
    )
    monkeypatch.setattr(
        "tests.go_live_verify.write_go_live_verify_markdown_report",
        lambda summary, *, output_path=DEFAULT_REPORT_OUTPUT: (_ for _ in ()).throw(
            AssertionError("report should not sync for custom output paths")
        ),
    )

    with pytest.raises(SystemExit, match="1"):
        main(["--output", str(output_path)])

    payload = json.loads(output_path.read_text())
    assert payload["completed_steps"] == []
    assert payload["failed_steps"] == []
    assert payload["static_operational_gaps"] == []
    assert payload["live_connectivity_skips"] == []
    assert payload["operational_gaps"] == []
    assert payload["gap_source_summary"] == {
        "static_gap_count": 0,
        "live_skip_count": 0,
        "merged_gap_count": 0,
        "live_only_case_ids": [],
        "static_only_case_ids": [],
        "merged_case_ids": [],
        "static_gap_counts_by_tier": {},
        "static_gap_counts_by_connector_type": {},
        "live_skip_counts_by_tier": {},
        "live_skip_counts_by_connector_type": {},
        "merged_gap_counts_by_tier": {},
        "merged_gap_counts_by_connector_type": {},
        "merged_gap_counts_by_source": {},
    }
    assert payload["next_actions"] == []
    assert payload["gap_action_summary"] == {
        "mapped_case_count": 0,
        "unmapped_case_ids": [],
        "action_case_counts": {},
        "action_case_ids": {},
        "action_env_names": {},
        "action_env_counts": {},
        "action_connector_types": {},
        "action_connector_counts": {},
        "terminal_action_codes": [],
    }
    assert payload["gap_connector_summary"] == {
        "connector_case_counts": {},
        "connector_case_ids": {},
        "connector_action_codes": {},
        "connector_env_counts": {},
        "connector_env_names": {},
    }
    assert payload["gap_env_summary"] == {
        "env_total_count": 0,
        "shared_env_names": [],
        "tier_env_counts": {},
        "env_case_counts": {},
        "env_case_ids": {},
        "env_connector_types": {},
        "env_connector_counts": {},
        "env_action_codes": {},
        "env_action_counts": {},
        "env_tiers": {},
    }
    assert payload["gap_env_resolution_summary"] == {
        "resolver_supported_count": 0,
        "manual_only_count": 0,
        "resolver_supported_env_names": [],
        "manual_only_env_names": [],
        "env_candidate_names": {},
        "env_group_names": {},
        "group_env_counts": {},
    }
    assert payload["gap_env_template_summary"] == {
        "gap_env_total_count": 0,
        "all_templates_cover_all_gap_envs": True,
        "template_paths": {
            "go_live_validation_env_example": "tests/integration/go_live_validation.env.example",
            "root_env_example": ".env.example",
        },
        "template_documented_counts": {
            "go_live_validation_env_example": 0,
            "root_env_example": 0,
        },
        "template_missing_counts": {
            "go_live_validation_env_example": 0,
            "root_env_example": 0,
        },
        "template_missing_env_names": {
            "go_live_validation_env_example": [],
            "root_env_example": [],
        },
        "templates_with_missing_envs": [],
        "missing_in_any_template": [],
    }
    assert payload["requirement_failures"] == [
        {
            "requirement": "all_configured",
            "case_id": "snowflake_customer_connector_test",
            "reason": "missing env",
        }
    ]
    assert payload["planned_steps"] == [
        {
            "name": "connectivity",
            "command": [
                "python-bin",
                "-u",
                str(ROOT / "tests" / "integration" / "test_go_live_connectivity_real.py"),
                "--parallel-tasks",
                "4",
            ],
        },
        {
            "name": "full_real",
            "command": [
                "python-bin",
                "-u",
                str(ROOT / "tests" / "integration" / "test_go_live_full_real.py"),
                "--parallel-tasks",
                "4",
                "--mojo-workers",
                "4",
                "--mojo-timeout",
                "30",
            ],
        },
        {
            "name": "pytest",
            "command": ["python-bin", "-m", "pytest", "tests", "-q"],
        },
    ]
    assert payload["generated_at"] == "2026-05-22T02:21:00Z"
    assert payload["python_executable"] == "python-bin"
    assert payload["output_path"] == str(output_path)
    assert payload["filters"] == {"tiers": [], "connectors": []}
    assert payload["options"] == {
        "include_full_real": True,
        "include_pytest": True,
        "require_all_configured": False,
        "require_all_behavior_ready": False,
        "strict": False,
    }
    captured = capsys.readouterr().out
    assert str(output_path) in captured


def test_main_writes_summary_when_steps_pass(monkeypatch, tmp_path, capsys) -> None:
    output_path = tmp_path / "go_live_verify_summary.json"

    monkeypatch.setattr("tests.go_live_verify.collect_matrix_status", lambda: [])
    monkeypatch.setattr("tests.go_live_verify.filter_statuses_by_connectors", lambda statuses, selected: statuses)
    monkeypatch.setattr("tests.go_live_verify.collect_requirement_failures", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "tests.go_live_verify.matrix_status_payload",
        lambda statuses: {
            "summary": {"configured_cases": 8, "behavior_ready_cases": 8, "total_cases": 19},
            "cases": [],
            "operational_gaps": [],
            "requirement_failures": [],
        },
    )
    monkeypatch.setattr("tests.go_live_verify.render_matrix_status", lambda statuses: "matrix")
    monkeypatch.setattr("tests.go_live_verify.resolve_python_executable", lambda: "python-bin")
    monkeypatch.setattr("tests.go_live_verify.time.strftime", lambda fmt, now: "2026-05-22T02:22:00Z")
    monkeypatch.setattr(
        "tests.go_live_verify.sync_go_live_verify_scorecard",
        lambda summary, *, scorecard_path=SCORECARD_PATH: (_ for _ in ()).throw(
            AssertionError("scorecard should not sync for custom output paths")
        ),
    )
    monkeypatch.setattr(
        "tests.go_live_verify.write_go_live_verify_markdown_report",
        lambda summary, *, output_path=DEFAULT_REPORT_OUTPUT: (_ for _ in ()).throw(
            AssertionError("report should not sync for custom output paths")
        ),
    )
    monkeypatch.setattr(
        "tests.go_live_verify.run_verification_steps",
        lambda steps: [VerificationResult(name="connectivity", returncode=0, duration_s=12.5)],
    )

    assert main(["--skip-full-real", "--skip-pytest", "--output", str(output_path)]) is None

    payload = json.loads(output_path.read_text())
    assert payload["planned_steps"] == [
        {
            "name": "connectivity",
            "command": [
                "python-bin",
                "-u",
                str(ROOT / "tests" / "integration" / "test_go_live_connectivity_real.py"),
                "--parallel-tasks",
                "4",
            ],
        }
    ]
    assert payload["completed_steps"] == ["connectivity"]
    assert payload["failed_steps"] == []
    assert payload["static_operational_gaps"] == []
    assert payload["live_connectivity_skips"] == []
    assert payload["operational_gaps"] == []
    assert payload["gap_source_summary"] == {
        "static_gap_count": 0,
        "live_skip_count": 0,
        "merged_gap_count": 0,
        "live_only_case_ids": [],
        "static_only_case_ids": [],
        "merged_case_ids": [],
        "static_gap_counts_by_tier": {},
        "static_gap_counts_by_connector_type": {},
        "live_skip_counts_by_tier": {},
        "live_skip_counts_by_connector_type": {},
        "merged_gap_counts_by_tier": {},
        "merged_gap_counts_by_connector_type": {},
        "merged_gap_counts_by_source": {},
    }
    assert payload["next_actions"] == []
    assert payload["gap_action_summary"] == {
        "mapped_case_count": 0,
        "unmapped_case_ids": [],
        "action_case_counts": {},
        "action_case_ids": {},
        "action_env_names": {},
        "action_env_counts": {},
        "action_connector_types": {},
        "action_connector_counts": {},
        "terminal_action_codes": [],
    }
    assert payload["gap_connector_summary"] == {
        "connector_case_counts": {},
        "connector_case_ids": {},
        "connector_action_codes": {},
        "connector_env_counts": {},
        "connector_env_names": {},
    }
    assert payload["gap_env_summary"] == {
        "env_total_count": 0,
        "shared_env_names": [],
        "tier_env_counts": {},
        "env_case_counts": {},
        "env_case_ids": {},
        "env_connector_types": {},
        "env_connector_counts": {},
        "env_action_codes": {},
        "env_action_counts": {},
        "env_tiers": {},
    }
    assert payload["gap_env_resolution_summary"] == {
        "resolver_supported_count": 0,
        "manual_only_count": 0,
        "resolver_supported_env_names": [],
        "manual_only_env_names": [],
        "env_candidate_names": {},
        "env_group_names": {},
        "group_env_counts": {},
    }
    assert payload["gap_env_template_summary"] == {
        "gap_env_total_count": 0,
        "all_templates_cover_all_gap_envs": True,
        "template_paths": {
            "go_live_validation_env_example": "tests/integration/go_live_validation.env.example",
            "root_env_example": ".env.example",
        },
        "template_documented_counts": {
            "go_live_validation_env_example": 0,
            "root_env_example": 0,
        },
        "template_missing_counts": {
            "go_live_validation_env_example": 0,
            "root_env_example": 0,
        },
        "template_missing_env_names": {
            "go_live_validation_env_example": [],
            "root_env_example": [],
        },
        "templates_with_missing_envs": [],
        "missing_in_any_template": [],
    }
    assert payload["step_results"] == [
        {"name": "connectivity", "returncode": 0, "duration_s": 12.5}
    ]
    assert payload["generated_at"] == "2026-05-22T02:22:00Z"
    assert payload["python_executable"] == "python-bin"
    assert payload["output_path"] == str(output_path)
    assert payload["filters"] == {"tiers": [], "connectors": []}
    assert payload["options"] == {
        "include_full_real": False,
        "include_pytest": False,
        "require_all_configured": False,
        "require_all_behavior_ready": False,
        "strict": False,
    }
    captured = capsys.readouterr().out
    assert str(output_path) in captured
    assert str(DEFAULT_SUMMARY_OUTPUT) not in captured


def test_main_syncs_markdown_report_for_canonical_mode(monkeypatch, tmp_path, capsys) -> None:
    summary_output = tmp_path / "go_live_verify_summary.json"
    report_output = tmp_path / "go_live_verify_report.md"
    synced: dict[str, object] = {}

    monkeypatch.setattr("tests.go_live_verify.DEFAULT_SUMMARY_OUTPUT", summary_output)
    monkeypatch.setattr("tests.go_live_verify.DEFAULT_REPORT_OUTPUT", report_output)
    monkeypatch.setattr("tests.go_live_verify.collect_matrix_status", lambda: [])
    monkeypatch.setattr("tests.go_live_verify.filter_statuses_by_connectors", lambda statuses, selected: statuses)
    monkeypatch.setattr("tests.go_live_verify.collect_requirement_failures", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        "tests.go_live_verify.matrix_status_payload",
        lambda statuses: {
            "summary": {"configured_cases": 8, "behavior_ready_cases": 8, "total_cases": 19},
            "cases": [],
            "operational_gaps": [],
            "requirement_failures": [],
        },
    )
    monkeypatch.setattr("tests.go_live_verify.render_matrix_status", lambda statuses: "matrix")
    monkeypatch.setattr("tests.go_live_verify.resolve_python_executable", lambda: "python-bin")
    monkeypatch.setattr("tests.go_live_verify.time.strftime", lambda fmt, now: "2026-05-22T02:23:00Z")
    monkeypatch.setattr(
        "tests.go_live_verify.run_verification_steps",
        lambda steps: [
            VerificationResult(name="connectivity", returncode=0, duration_s=12.5),
            VerificationResult(name="full_real", returncode=0, duration_s=44.0),
        ],
    )

    def _capture_report(summary, *, output_path=DEFAULT_REPORT_OUTPUT):
        synced["report_path"] = output_path
        synced["report_summary"] = summary

    def _capture_scorecard(summary, *, scorecard_path=SCORECARD_PATH):
        synced["scorecard_summary"] = summary
        synced["scorecard_path"] = scorecard_path

    monkeypatch.setattr("tests.go_live_verify.write_go_live_verify_markdown_report", _capture_report)
    monkeypatch.setattr("tests.go_live_verify.sync_go_live_verify_scorecard", _capture_scorecard)

    assert main(["--skip-pytest"]) is None

    assert synced["report_path"] == report_output
    assert synced["scorecard_path"] == SCORECARD_PATH
    captured = capsys.readouterr().out
    assert f"wrote verification report: {report_output}" in captured
    assert f"synced go-live scorecard: {SCORECARD_PATH}" in captured
    assert f"wrote verification summary: {summary_output}" in captured


def test_checked_in_go_live_verify_summary_matches_expected_contract() -> None:
    payload = json.loads(Path("build/go_live_verify_summary.json").read_text())

    assert payload["generated_at"].endswith("Z")
    assert payload["python_executable"]
    assert Path(payload["output_path"]).resolve() == Path("build/go_live_verify_summary.json").resolve()
    assert payload["matrix_summary"] == {
        "total_cases": 19,
        "configured_cases": 8,
        "behavior_ready_cases": 8,
        "tiers": {
            "public_no_auth": {"total": 8, "configured": 7, "behavior_ready": 7},
            "credentialed_example": {"total": 2, "configured": 0, "behavior_ready": 0},
            "customer_credentials_required": {
                "total": 9,
                "configured": 1,
                "behavior_ready": 1,
            },
        },
    }
    assert payload["requirement_failures"] == []
    assert isinstance(payload["static_operational_gaps"], list)
    assert payload["static_operational_gaps"]
    assert payload["gap_source_summary"] == {
        "static_gap_count": 11,
        "live_skip_count": 12,
        "merged_gap_count": 12,
        "live_only_case_ids": ["snowflake_customer_connector_test"],
        "static_only_case_ids": [],
        "merged_case_ids": [
            "bigquery_customer_connector_test",
            "clickhouse_customer_connector_test",
            "customer_azure_blob_source_registration",
            "customer_gcs_source_registration",
            "customer_s3_source_registration",
            "dlt_github_issues",
            "dlt_github_issues_token",
            "elasticsearch_customer_connector_test",
            "fivetran_fred_gnpca",
            "neo4j_customer_connector_test",
            "redis_customer_connector_test",
            "snowflake_customer_connector_test",
        ],
        "static_gap_counts_by_tier": {
            "credentialed_example": 2,
            "customer_credentials_required": 8,
            "public_no_auth": 1,
        },
        "static_gap_counts_by_connector_type": {
            "azure_blob": 1,
            "bigquery": 1,
            "clickhouse": 1,
            "elasticsearch": 1,
            "gcs": 1,
            "neo4j": 1,
            "redis": 1,
            "rest_api": 3,
            "s3": 1,
        },
        "live_skip_counts_by_tier": {
            "credentialed_example": 2,
            "customer_credentials_required": 9,
            "public_no_auth": 1,
        },
        "live_skip_counts_by_connector_type": {
            "azure_blob": 1,
            "bigquery": 1,
            "clickhouse": 1,
            "elasticsearch": 1,
            "gcs": 1,
            "neo4j": 1,
            "redis": 1,
            "rest_api": 3,
            "s3": 1,
            "snowflake": 1,
        },
        "merged_gap_counts_by_tier": {
            "credentialed_example": 2,
            "customer_credentials_required": 9,
            "public_no_auth": 1,
        },
        "merged_gap_counts_by_connector_type": {
            "azure_blob": 1,
            "bigquery": 1,
            "clickhouse": 1,
            "elasticsearch": 1,
            "gcs": 1,
            "neo4j": 1,
            "redis": 1,
            "rest_api": 3,
            "s3": 1,
            "snowflake": 1,
        },
        "merged_gap_counts_by_source": {
            "live_connectivity": 1,
            "static_matrix+live_connectivity": 11,
        },
    }
    assert isinstance(payload["operational_gaps"], list)
    assert payload["operational_gaps"]
    assert isinstance(payload["live_connectivity_skips"], list)
    assert payload["live_connectivity_skips"]
    assert isinstance(payload["next_actions"], list)
    assert payload["next_actions"]
    static_gap_case_ids = [item["case_id"] for item in payload["static_operational_gaps"]]
    assert "snowflake_customer_connector_test" not in static_gap_case_ids
    live_skip_case_ids = [item["case_id"] for item in payload["live_connectivity_skips"]]
    assert "snowflake_customer_connector_test" in live_skip_case_ids
    operational_gap_index = {item["case_id"]: item for item in payload["operational_gaps"]}
    assert operational_gap_index["snowflake_customer_connector_test"]["source"] == "live_connectivity"
    assert operational_gap_index["snowflake_customer_connector_test"]["sources"] == [
        "live_connectivity"
    ]
    assert operational_gap_index["snowflake_customer_connector_test"]["static_reason"] is None
    assert operational_gap_index["snowflake_customer_connector_test"]["live_reason"] == (
        "Snowflake live validation blocked by account network policy; skipping external customer-credential case."
    )
    assert operational_gap_index["snowflake_customer_connector_test"]["action_codes"] == [
        "resolve_network_policy_blockers"
    ]
    assert operational_gap_index["dlt_github_issues"]["source"] == (
        "static_matrix+live_connectivity"
    )
    assert operational_gap_index["dlt_github_issues"]["sources"] == [
        "static_matrix",
        "live_connectivity",
    ]
    assert operational_gap_index["dlt_github_issues"]["action_codes"] == [
        "enable_opt_in_public_cases"
    ]
    next_action_codes = [item["code"] for item in payload["next_actions"]]
    assert next_action_codes == [
        "enable_opt_in_public_cases",
        "set_credentialed_example_envs",
        "set_customer_connector_envs",
        "resolve_network_policy_blockers",
        "rerun_strict_go_live_gate",
    ]
    assert payload["gap_action_summary"] == {
        "mapped_case_count": 12,
        "unmapped_case_ids": [],
        "action_case_counts": {
            "enable_opt_in_public_cases": 1,
            "resolve_network_policy_blockers": 1,
            "set_credentialed_example_envs": 2,
            "set_customer_connector_envs": 8,
        },
        "action_case_ids": {
            "enable_opt_in_public_cases": ["dlt_github_issues"],
            "resolve_network_policy_blockers": ["snowflake_customer_connector_test"],
            "set_credentialed_example_envs": [
                "dlt_github_issues_token",
                "fivetran_fred_gnpca",
            ],
            "set_customer_connector_envs": [
                "bigquery_customer_connector_test",
                "clickhouse_customer_connector_test",
                "customer_azure_blob_source_registration",
                "customer_gcs_source_registration",
                "customer_s3_source_registration",
                "elasticsearch_customer_connector_test",
                "neo4j_customer_connector_test",
                "redis_customer_connector_test",
            ],
        },
        "action_env_names": {
            "enable_opt_in_public_cases": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
            "set_credentialed_example_envs": [
                "DE_TEST_FRED_API_KEY",
                "DE_TEST_GITHUB_TOKEN",
            ],
            "set_customer_connector_envs": [
                "DE_TEST_AZURE_ACCOUNT_URL",
                "DE_TEST_AZURE_BLOB",
                "DE_TEST_AZURE_BLOB_URL",
                "DE_TEST_AZURE_CONNECTION_STRING",
                "DE_TEST_AZURE_CONTAINER",
                "DE_TEST_BIGQUERY_PROJECT_ID",
                "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
                "DE_TEST_CLICKHOUSE_PASSWORD",
                "DE_TEST_CLICKHOUSE_URL",
                "DE_TEST_CLICKHOUSE_USER",
                "DE_TEST_ELASTICSEARCH_API_KEY",
                "DE_TEST_ELASTICSEARCH_URL",
                "DE_TEST_GCS_BLOB",
                "DE_TEST_GCS_BUCKET",
                "DE_TEST_NEO4J_PASSWORD",
                "DE_TEST_NEO4J_URI",
                "DE_TEST_NEO4J_USERNAME",
                "DE_TEST_REDIS_URL",
                "DE_TEST_S3_BUCKET",
                "DE_TEST_S3_KEY",
            ],
        },
        "action_env_counts": {
            "enable_opt_in_public_cases": 1,
            "set_credentialed_example_envs": 2,
            "set_customer_connector_envs": 20,
        },
        "action_connector_types": {
            "enable_opt_in_public_cases": ["rest_api"],
            "resolve_network_policy_blockers": ["snowflake"],
            "set_credentialed_example_envs": ["rest_api"],
            "set_customer_connector_envs": [
                "azure_blob",
                "bigquery",
                "clickhouse",
                "elasticsearch",
                "gcs",
                "neo4j",
                "redis",
                "s3",
            ],
        },
        "action_connector_counts": {
            "enable_opt_in_public_cases": 1,
            "resolve_network_policy_blockers": 1,
            "set_credentialed_example_envs": 1,
            "set_customer_connector_envs": 8,
        },
        "terminal_action_codes": ["rerun_strict_go_live_gate"],
    }
    assert payload["gap_connector_summary"] == {
        "connector_action_codes": {
            "azure_blob": ["set_customer_connector_envs"],
            "bigquery": ["set_customer_connector_envs"],
            "clickhouse": ["set_customer_connector_envs"],
            "elasticsearch": ["set_customer_connector_envs"],
            "gcs": ["set_customer_connector_envs"],
            "neo4j": ["set_customer_connector_envs"],
            "redis": ["set_customer_connector_envs"],
            "rest_api": [
                "enable_opt_in_public_cases",
                "set_credentialed_example_envs",
            ],
            "s3": ["set_customer_connector_envs"],
            "snowflake": ["resolve_network_policy_blockers"],
        },
        "connector_case_counts": {
            "azure_blob": 1,
            "bigquery": 1,
            "clickhouse": 1,
            "elasticsearch": 1,
            "gcs": 1,
            "neo4j": 1,
            "redis": 1,
            "rest_api": 3,
            "s3": 1,
            "snowflake": 1,
        },
        "connector_case_ids": {
            "azure_blob": ["customer_azure_blob_source_registration"],
            "bigquery": ["bigquery_customer_connector_test"],
            "clickhouse": ["clickhouse_customer_connector_test"],
            "elasticsearch": ["elasticsearch_customer_connector_test"],
            "gcs": ["customer_gcs_source_registration"],
            "neo4j": ["neo4j_customer_connector_test"],
            "redis": ["redis_customer_connector_test"],
            "rest_api": [
                "dlt_github_issues",
                "dlt_github_issues_token",
                "fivetran_fred_gnpca",
            ],
            "s3": ["customer_s3_source_registration"],
            "snowflake": ["snowflake_customer_connector_test"],
        },
        "connector_env_counts": {
            "azure_blob": 5,
            "bigquery": 2,
            "clickhouse": 3,
            "elasticsearch": 2,
            "gcs": 2,
            "neo4j": 3,
            "redis": 1,
            "rest_api": 3,
            "s3": 2,
        },
        "connector_env_names": {
            "azure_blob": [
                "DE_TEST_AZURE_ACCOUNT_URL",
                "DE_TEST_AZURE_BLOB",
                "DE_TEST_AZURE_BLOB_URL",
                "DE_TEST_AZURE_CONNECTION_STRING",
                "DE_TEST_AZURE_CONTAINER",
            ],
            "bigquery": [
                "DE_TEST_BIGQUERY_PROJECT_ID",
                "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
            ],
            "clickhouse": [
                "DE_TEST_CLICKHOUSE_PASSWORD",
                "DE_TEST_CLICKHOUSE_URL",
                "DE_TEST_CLICKHOUSE_USER",
            ],
            "elasticsearch": [
                "DE_TEST_ELASTICSEARCH_API_KEY",
                "DE_TEST_ELASTICSEARCH_URL",
            ],
            "gcs": [
                "DE_TEST_GCS_BLOB",
                "DE_TEST_GCS_BUCKET",
            ],
            "neo4j": [
                "DE_TEST_NEO4J_PASSWORD",
                "DE_TEST_NEO4J_URI",
                "DE_TEST_NEO4J_USERNAME",
            ],
            "redis": ["DE_TEST_REDIS_URL"],
            "rest_api": [
                "DE_ENABLE_SLOW_PUBLIC_REST_CASES",
                "DE_TEST_FRED_API_KEY",
                "DE_TEST_GITHUB_TOKEN",
            ],
            "s3": [
                "DE_TEST_S3_BUCKET",
                "DE_TEST_S3_KEY",
            ],
        },
    }
    assert payload["gap_env_summary"] == {
        "env_total_count": 23,
        "shared_env_names": [],
        "tier_env_counts": {
            "credentialed_example": 2,
            "customer_credentials_required": 20,
            "public_no_auth": 1,
        },
        "env_case_counts": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": 1,
            "DE_TEST_AZURE_ACCOUNT_URL": 1,
            "DE_TEST_AZURE_BLOB": 1,
            "DE_TEST_AZURE_BLOB_URL": 1,
            "DE_TEST_AZURE_CONNECTION_STRING": 1,
            "DE_TEST_AZURE_CONTAINER": 1,
            "DE_TEST_BIGQUERY_PROJECT_ID": 1,
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": 1,
            "DE_TEST_CLICKHOUSE_PASSWORD": 1,
            "DE_TEST_CLICKHOUSE_URL": 1,
            "DE_TEST_CLICKHOUSE_USER": 1,
            "DE_TEST_ELASTICSEARCH_API_KEY": 1,
            "DE_TEST_ELASTICSEARCH_URL": 1,
            "DE_TEST_FRED_API_KEY": 1,
            "DE_TEST_GCS_BLOB": 1,
            "DE_TEST_GCS_BUCKET": 1,
            "DE_TEST_GITHUB_TOKEN": 1,
            "DE_TEST_NEO4J_PASSWORD": 1,
            "DE_TEST_NEO4J_URI": 1,
            "DE_TEST_NEO4J_USERNAME": 1,
            "DE_TEST_REDIS_URL": 1,
            "DE_TEST_S3_BUCKET": 1,
            "DE_TEST_S3_KEY": 1,
        },
        "env_case_ids": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["dlt_github_issues"],
            "DE_TEST_AZURE_ACCOUNT_URL": ["customer_azure_blob_source_registration"],
            "DE_TEST_AZURE_BLOB": ["customer_azure_blob_source_registration"],
            "DE_TEST_AZURE_BLOB_URL": ["customer_azure_blob_source_registration"],
            "DE_TEST_AZURE_CONNECTION_STRING": ["customer_azure_blob_source_registration"],
            "DE_TEST_AZURE_CONTAINER": ["customer_azure_blob_source_registration"],
            "DE_TEST_BIGQUERY_PROJECT_ID": ["bigquery_customer_connector_test"],
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": ["bigquery_customer_connector_test"],
            "DE_TEST_CLICKHOUSE_PASSWORD": ["clickhouse_customer_connector_test"],
            "DE_TEST_CLICKHOUSE_URL": ["clickhouse_customer_connector_test"],
            "DE_TEST_CLICKHOUSE_USER": ["clickhouse_customer_connector_test"],
            "DE_TEST_ELASTICSEARCH_API_KEY": ["elasticsearch_customer_connector_test"],
            "DE_TEST_ELASTICSEARCH_URL": ["elasticsearch_customer_connector_test"],
            "DE_TEST_FRED_API_KEY": ["fivetran_fred_gnpca"],
            "DE_TEST_GCS_BLOB": ["customer_gcs_source_registration"],
            "DE_TEST_GCS_BUCKET": ["customer_gcs_source_registration"],
            "DE_TEST_GITHUB_TOKEN": ["dlt_github_issues_token"],
            "DE_TEST_NEO4J_PASSWORD": ["neo4j_customer_connector_test"],
            "DE_TEST_NEO4J_URI": ["neo4j_customer_connector_test"],
            "DE_TEST_NEO4J_USERNAME": ["neo4j_customer_connector_test"],
            "DE_TEST_REDIS_URL": ["redis_customer_connector_test"],
            "DE_TEST_S3_BUCKET": ["customer_s3_source_registration"],
            "DE_TEST_S3_KEY": ["customer_s3_source_registration"],
        },
        "env_connector_types": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["rest_api"],
            "DE_TEST_AZURE_ACCOUNT_URL": ["azure_blob"],
            "DE_TEST_AZURE_BLOB": ["azure_blob"],
            "DE_TEST_AZURE_BLOB_URL": ["azure_blob"],
            "DE_TEST_AZURE_CONNECTION_STRING": ["azure_blob"],
            "DE_TEST_AZURE_CONTAINER": ["azure_blob"],
            "DE_TEST_BIGQUERY_PROJECT_ID": ["bigquery"],
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": ["bigquery"],
            "DE_TEST_CLICKHOUSE_PASSWORD": ["clickhouse"],
            "DE_TEST_CLICKHOUSE_URL": ["clickhouse"],
            "DE_TEST_CLICKHOUSE_USER": ["clickhouse"],
            "DE_TEST_ELASTICSEARCH_API_KEY": ["elasticsearch"],
            "DE_TEST_ELASTICSEARCH_URL": ["elasticsearch"],
            "DE_TEST_FRED_API_KEY": ["rest_api"],
            "DE_TEST_GCS_BLOB": ["gcs"],
            "DE_TEST_GCS_BUCKET": ["gcs"],
            "DE_TEST_GITHUB_TOKEN": ["rest_api"],
            "DE_TEST_NEO4J_PASSWORD": ["neo4j"],
            "DE_TEST_NEO4J_URI": ["neo4j"],
            "DE_TEST_NEO4J_USERNAME": ["neo4j"],
            "DE_TEST_REDIS_URL": ["redis"],
            "DE_TEST_S3_BUCKET": ["s3"],
            "DE_TEST_S3_KEY": ["s3"],
        },
        "env_connector_counts": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": 1,
            "DE_TEST_AZURE_ACCOUNT_URL": 1,
            "DE_TEST_AZURE_BLOB": 1,
            "DE_TEST_AZURE_BLOB_URL": 1,
            "DE_TEST_AZURE_CONNECTION_STRING": 1,
            "DE_TEST_AZURE_CONTAINER": 1,
            "DE_TEST_BIGQUERY_PROJECT_ID": 1,
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": 1,
            "DE_TEST_CLICKHOUSE_PASSWORD": 1,
            "DE_TEST_CLICKHOUSE_URL": 1,
            "DE_TEST_CLICKHOUSE_USER": 1,
            "DE_TEST_ELASTICSEARCH_API_KEY": 1,
            "DE_TEST_ELASTICSEARCH_URL": 1,
            "DE_TEST_FRED_API_KEY": 1,
            "DE_TEST_GCS_BLOB": 1,
            "DE_TEST_GCS_BUCKET": 1,
            "DE_TEST_GITHUB_TOKEN": 1,
            "DE_TEST_NEO4J_PASSWORD": 1,
            "DE_TEST_NEO4J_URI": 1,
            "DE_TEST_NEO4J_USERNAME": 1,
            "DE_TEST_REDIS_URL": 1,
            "DE_TEST_S3_BUCKET": 1,
            "DE_TEST_S3_KEY": 1,
        },
        "env_action_codes": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["enable_opt_in_public_cases"],
            "DE_TEST_AZURE_ACCOUNT_URL": ["set_customer_connector_envs"],
            "DE_TEST_AZURE_BLOB": ["set_customer_connector_envs"],
            "DE_TEST_AZURE_BLOB_URL": ["set_customer_connector_envs"],
            "DE_TEST_AZURE_CONNECTION_STRING": ["set_customer_connector_envs"],
            "DE_TEST_AZURE_CONTAINER": ["set_customer_connector_envs"],
            "DE_TEST_BIGQUERY_PROJECT_ID": ["set_customer_connector_envs"],
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": ["set_customer_connector_envs"],
            "DE_TEST_CLICKHOUSE_PASSWORD": ["set_customer_connector_envs"],
            "DE_TEST_CLICKHOUSE_URL": ["set_customer_connector_envs"],
            "DE_TEST_CLICKHOUSE_USER": ["set_customer_connector_envs"],
            "DE_TEST_ELASTICSEARCH_API_KEY": ["set_customer_connector_envs"],
            "DE_TEST_ELASTICSEARCH_URL": ["set_customer_connector_envs"],
            "DE_TEST_FRED_API_KEY": ["set_credentialed_example_envs"],
            "DE_TEST_GCS_BLOB": ["set_customer_connector_envs"],
            "DE_TEST_GCS_BUCKET": ["set_customer_connector_envs"],
            "DE_TEST_GITHUB_TOKEN": ["set_credentialed_example_envs"],
            "DE_TEST_NEO4J_PASSWORD": ["set_customer_connector_envs"],
            "DE_TEST_NEO4J_URI": ["set_customer_connector_envs"],
            "DE_TEST_NEO4J_USERNAME": ["set_customer_connector_envs"],
            "DE_TEST_REDIS_URL": ["set_customer_connector_envs"],
            "DE_TEST_S3_BUCKET": ["set_customer_connector_envs"],
            "DE_TEST_S3_KEY": ["set_customer_connector_envs"],
        },
        "env_action_counts": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": 1,
            "DE_TEST_AZURE_ACCOUNT_URL": 1,
            "DE_TEST_AZURE_BLOB": 1,
            "DE_TEST_AZURE_BLOB_URL": 1,
            "DE_TEST_AZURE_CONNECTION_STRING": 1,
            "DE_TEST_AZURE_CONTAINER": 1,
            "DE_TEST_BIGQUERY_PROJECT_ID": 1,
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": 1,
            "DE_TEST_CLICKHOUSE_PASSWORD": 1,
            "DE_TEST_CLICKHOUSE_URL": 1,
            "DE_TEST_CLICKHOUSE_USER": 1,
            "DE_TEST_ELASTICSEARCH_API_KEY": 1,
            "DE_TEST_ELASTICSEARCH_URL": 1,
            "DE_TEST_FRED_API_KEY": 1,
            "DE_TEST_GCS_BLOB": 1,
            "DE_TEST_GCS_BUCKET": 1,
            "DE_TEST_GITHUB_TOKEN": 1,
            "DE_TEST_NEO4J_PASSWORD": 1,
            "DE_TEST_NEO4J_URI": 1,
            "DE_TEST_NEO4J_USERNAME": 1,
            "DE_TEST_REDIS_URL": 1,
            "DE_TEST_S3_BUCKET": 1,
            "DE_TEST_S3_KEY": 1,
        },
        "env_tiers": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["public_no_auth"],
            "DE_TEST_AZURE_ACCOUNT_URL": ["customer_credentials_required"],
            "DE_TEST_AZURE_BLOB": ["customer_credentials_required"],
            "DE_TEST_AZURE_BLOB_URL": ["customer_credentials_required"],
            "DE_TEST_AZURE_CONNECTION_STRING": ["customer_credentials_required"],
            "DE_TEST_AZURE_CONTAINER": ["customer_credentials_required"],
            "DE_TEST_BIGQUERY_PROJECT_ID": ["customer_credentials_required"],
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": ["customer_credentials_required"],
            "DE_TEST_CLICKHOUSE_PASSWORD": ["customer_credentials_required"],
            "DE_TEST_CLICKHOUSE_URL": ["customer_credentials_required"],
            "DE_TEST_CLICKHOUSE_USER": ["customer_credentials_required"],
            "DE_TEST_ELASTICSEARCH_API_KEY": ["customer_credentials_required"],
            "DE_TEST_ELASTICSEARCH_URL": ["customer_credentials_required"],
            "DE_TEST_FRED_API_KEY": ["credentialed_example"],
            "DE_TEST_GCS_BLOB": ["customer_credentials_required"],
            "DE_TEST_GCS_BUCKET": ["customer_credentials_required"],
            "DE_TEST_GITHUB_TOKEN": ["credentialed_example"],
            "DE_TEST_NEO4J_PASSWORD": ["customer_credentials_required"],
            "DE_TEST_NEO4J_URI": ["customer_credentials_required"],
            "DE_TEST_NEO4J_USERNAME": ["customer_credentials_required"],
            "DE_TEST_REDIS_URL": ["customer_credentials_required"],
            "DE_TEST_S3_BUCKET": ["customer_credentials_required"],
            "DE_TEST_S3_KEY": ["customer_credentials_required"],
        },
    }
    assert payload["gap_env_resolution_summary"] == {
        "resolver_supported_count": 22,
        "manual_only_count": 1,
        "resolver_supported_env_names": [
            "DE_TEST_AZURE_ACCOUNT_URL",
            "DE_TEST_AZURE_BLOB",
            "DE_TEST_AZURE_BLOB_URL",
            "DE_TEST_AZURE_CONNECTION_STRING",
            "DE_TEST_AZURE_CONTAINER",
            "DE_TEST_BIGQUERY_PROJECT_ID",
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
            "DE_TEST_CLICKHOUSE_PASSWORD",
            "DE_TEST_CLICKHOUSE_URL",
            "DE_TEST_CLICKHOUSE_USER",
            "DE_TEST_ELASTICSEARCH_API_KEY",
            "DE_TEST_ELASTICSEARCH_URL",
            "DE_TEST_FRED_API_KEY",
            "DE_TEST_GCS_BLOB",
            "DE_TEST_GCS_BUCKET",
            "DE_TEST_GITHUB_TOKEN",
            "DE_TEST_NEO4J_PASSWORD",
            "DE_TEST_NEO4J_URI",
            "DE_TEST_NEO4J_USERNAME",
            "DE_TEST_REDIS_URL",
            "DE_TEST_S3_BUCKET",
            "DE_TEST_S3_KEY",
        ],
        "manual_only_env_names": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
        "env_candidate_names": {
            "DE_ENABLE_SLOW_PUBLIC_REST_CASES": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
            "DE_TEST_AZURE_ACCOUNT_URL": [
                "DE_TEST_AZURE_ACCOUNT_URL",
                "AZURE_ACCOUNT_URL",
            ],
            "DE_TEST_AZURE_BLOB": ["DE_TEST_AZURE_BLOB", "AZURE_BLOB"],
            "DE_TEST_AZURE_BLOB_URL": ["DE_TEST_AZURE_BLOB_URL", "AZURE_BLOB_URL"],
            "DE_TEST_AZURE_CONNECTION_STRING": [
                "DE_TEST_AZURE_CONNECTION_STRING",
                "AZURE_CONNECTION_STRING",
            ],
            "DE_TEST_AZURE_CONTAINER": ["DE_TEST_AZURE_CONTAINER", "AZURE_CONTAINER"],
            "DE_TEST_BIGQUERY_PROJECT_ID": [
                "DE_TEST_BIGQUERY_PROJECT_ID",
                "BIGQUERY_PROJECT_ID",
                "GOOGLE_CLOUD_PROJECT",
                "GCP_PROJECT_ID",
            ],
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": [
                "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON",
                "BIGQUERY_SERVICE_ACCOUNT_JSON",
                "GOOGLE_APPLICATION_CREDENTIALS_JSON",
                "GCP_SERVICE_ACCOUNT_JSON",
                "GOOGLE_APPLICATION_CREDENTIALS",
            ],
            "DE_TEST_CLICKHOUSE_PASSWORD": [
                "DE_TEST_CLICKHOUSE_PASSWORD",
                "CLICKHOUSE_PASSWORD",
            ],
            "DE_TEST_CLICKHOUSE_URL": ["DE_TEST_CLICKHOUSE_URL", "CLICKHOUSE_URL"],
            "DE_TEST_CLICKHOUSE_USER": ["DE_TEST_CLICKHOUSE_USER", "CLICKHOUSE_USER"],
            "DE_TEST_ELASTICSEARCH_API_KEY": [
                "DE_TEST_ELASTICSEARCH_API_KEY",
                "ELASTICSEARCH_API_KEY",
                "ELASTIC_API_KEY",
            ],
            "DE_TEST_ELASTICSEARCH_URL": [
                "DE_TEST_ELASTICSEARCH_URL",
                "ELASTICSEARCH_URL",
                "ELASTIC_URL",
            ],
            "DE_TEST_FRED_API_KEY": ["DE_TEST_FRED_API_KEY", "FRED_API_KEY"],
            "DE_TEST_GCS_BLOB": ["DE_TEST_GCS_BLOB", "GCS_BLOB"],
            "DE_TEST_GCS_BUCKET": ["DE_TEST_GCS_BUCKET", "GCS_BUCKET"],
            "DE_TEST_GITHUB_TOKEN": [
                "DE_TEST_GITHUB_TOKEN",
                "GITHUB_TOKEN",
                "GH_TOKEN",
            ],
            "DE_TEST_NEO4J_PASSWORD": ["DE_TEST_NEO4J_PASSWORD", "NEO4J_PASSWORD"],
            "DE_TEST_NEO4J_URI": [
                "DE_TEST_NEO4J_URI",
                "NEO4J_URI",
                "NEO4J_URL",
            ],
            "DE_TEST_NEO4J_USERNAME": [
                "DE_TEST_NEO4J_USERNAME",
                "NEO4J_USERNAME",
                "NEO4J_USER",
            ],
            "DE_TEST_REDIS_URL": ["DE_TEST_REDIS_URL", "REDIS_URL"],
            "DE_TEST_S3_BUCKET": ["DE_TEST_S3_BUCKET", "S3_BUCKET"],
            "DE_TEST_S3_KEY": ["DE_TEST_S3_KEY", "S3_KEY"],
        },
        "env_group_names": {
            "DE_TEST_AZURE_ACCOUNT_URL": "azure_blob",
            "DE_TEST_AZURE_BLOB": "azure_blob",
            "DE_TEST_AZURE_BLOB_URL": "azure_blob",
            "DE_TEST_AZURE_CONNECTION_STRING": "azure_blob",
            "DE_TEST_AZURE_CONTAINER": "azure_blob",
            "DE_TEST_BIGQUERY_PROJECT_ID": "bigquery",
            "DE_TEST_BIGQUERY_SERVICE_ACCOUNT_JSON": "bigquery",
            "DE_TEST_CLICKHOUSE_PASSWORD": "clickhouse",
            "DE_TEST_CLICKHOUSE_URL": "clickhouse",
            "DE_TEST_CLICKHOUSE_USER": "clickhouse",
            "DE_TEST_ELASTICSEARCH_API_KEY": "elasticsearch",
            "DE_TEST_ELASTICSEARCH_URL": "elasticsearch",
            "DE_TEST_GCS_BLOB": "gcs",
            "DE_TEST_GCS_BUCKET": "gcs",
            "DE_TEST_NEO4J_PASSWORD": "neo4j",
            "DE_TEST_NEO4J_URI": "neo4j",
            "DE_TEST_NEO4J_USERNAME": "neo4j",
            "DE_TEST_REDIS_URL": "redis",
            "DE_TEST_S3_BUCKET": "s3",
            "DE_TEST_S3_KEY": "s3",
        },
        "group_env_counts": {
            "azure_blob": 5,
            "bigquery": 2,
            "clickhouse": 3,
            "elasticsearch": 2,
            "gcs": 2,
            "neo4j": 3,
            "redis": 1,
            "s3": 2,
        },
    }
    assert payload["gap_env_template_summary"] == {
        "gap_env_total_count": 23,
        "all_templates_cover_all_gap_envs": True,
        "template_paths": {
            "go_live_validation_env_example": "tests/integration/go_live_validation.env.example",
            "root_env_example": ".env.example",
        },
        "template_documented_counts": {
            "go_live_validation_env_example": 23,
            "root_env_example": 23,
        },
        "template_missing_counts": {
            "go_live_validation_env_example": 0,
            "root_env_example": 0,
        },
        "template_missing_env_names": {
            "go_live_validation_env_example": [],
            "root_env_example": [],
        },
        "templates_with_missing_envs": [],
        "missing_in_any_template": [],
    }
    assert payload["filters"] == {"tiers": [], "connectors": []}
    assert payload["options"] == {
        "include_full_real": True,
        "include_pytest": True,
        "require_all_configured": False,
        "require_all_behavior_ready": False,
        "strict": False,
    }
    planned_names = [item["name"] for item in payload["planned_steps"]]
    executed_names = [item["name"] for item in payload["step_results"]]

    assert planned_names == ["connectivity", "full_real", "pytest"]
    assert payload["planned_steps"][0]["command"][:2] == [payload["python_executable"], "-u"]
    assert executed_names == payload["completed_steps"] + payload["failed_steps"]
    assert executed_names
    assert all(float(item["duration_s"]) > 0.0 for item in payload["step_results"])
    for item in payload["step_results"]:
        if item["name"] in payload["completed_steps"]:
            assert item["returncode"] == 0
        else:
            assert item["name"] in payload["failed_steps"]
            assert item["returncode"] != 0
