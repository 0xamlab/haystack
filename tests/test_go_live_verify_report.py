from __future__ import annotations

import json
from pathlib import Path

from tests.go_live_verify_report import (
    DEFAULT_REPORT_OUTPUT,
    main,
    render_go_live_verify_markdown_report,
)


def _sample_summary() -> dict[str, object]:
    return {
        "generated_at": "2026-05-22T06:24:38Z",
        "python_executable": "/Users/angel/Developer/decision-engine/.venv/bin/python",
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
        "completed_steps": ["connectivity", "full_real"],
        "failed_steps": [],
        "planned_steps": [
            {
                "name": "connectivity",
                "command": [
                    "/Users/angel/Developer/decision-engine/.venv/bin/python",
                    "-u",
                    "/Users/angel/Developer/decision-engine/tests/integration/test_go_live_connectivity_real.py",
                    "--parallel-tasks",
                    "4",
                ],
            },
            {
                "name": "full_real",
                "command": [
                    "/Users/angel/Developer/decision-engine/.venv/bin/python",
                    "-u",
                    "/Users/angel/Developer/decision-engine/tests/integration/test_go_live_full_real.py",
                    "--parallel-tasks",
                    "4",
                    "--mojo-workers",
                    "4",
                    "--mojo-timeout",
                    "30",
                ],
            },
        ],
        "step_results": [
            {"name": "connectivity", "returncode": 0, "duration_s": 32.89},
            {"name": "full_real", "returncode": 0, "duration_s": 339.5},
        ],
    }


def test_render_go_live_verify_markdown_report_includes_matrix_and_commands() -> None:
    rendered = render_go_live_verify_markdown_report(_sample_summary())

    assert "# Go-live verifier report" in rendered
    assert "- Configured: `8/19`" in rendered
    assert "- Behavior-ready: `8/19`" in rendered
    assert "- Completed steps: `connectivity, full_real`" in rendered
    assert "- Planned steps: `connectivity, full_real`" in rendered
    assert "tests/integration/test_go_live_connectivity_real.py" in rendered
    assert "tests/integration/test_go_live_full_real.py" in rendered
    assert "- Duration: `32.89s`" in rendered
    assert "- Duration: `339.50s`" in rendered
    assert "## Requirement failures" in rendered
    assert "- None" in rendered
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
    assert "## Live connectivity skips" in rendered
    assert "snowflake_customer_connector_test" in rendered
    assert "## Operational gaps" in rendered
    assert "dlt_github_issues" in rendered
    assert "[source: static_matrix]" in rendered
    assert "[actions: enable_opt_in_public_cases]" in rendered
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


def test_main_writes_markdown_report_to_file(tmp_path) -> None:
    input_path = tmp_path / "go_live_verify_summary.json"
    output_path = tmp_path / "go_live_verify_report.md"
    input_path.write_text(json.dumps(_sample_summary()), encoding="utf-8")

    assert main(["--input", str(input_path), "--output", str(output_path)]) == 0

    rendered = output_path.read_text(encoding="utf-8")
    assert "# Go-live verifier report" in rendered
    assert "Summary path: `build/go_live_verify_summary.json`" in rendered


def test_makefile_exposes_go_live_report_target() -> None:
    text = Path("Makefile").read_text(encoding="utf-8")

    assert "go-live-report:" in text
    assert "-m tests.go_live_verify_report" in text


def test_checked_in_go_live_verify_report_matches_current_summary_artifact() -> None:
    summary = json.loads(Path("build/go_live_verify_summary.json").read_text(encoding="utf-8"))
    report_path = DEFAULT_REPORT_OUTPUT

    assert report_path.exists()
    assert report_path.read_text(encoding="utf-8") == (
        render_go_live_verify_markdown_report(summary) + "\n"
    )
