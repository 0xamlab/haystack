"""Tests for test_go_live_verify: misc_a.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_ad413055-70e-1/tests/test_go_live_verify.py during modularization.
"""
from __future__ import annotations

from tests._test_go_live_verify_helpers import *  # noqa: F401,F403


def test_resolve_python_executable_prefers_repo_venv() -> None:
    resolved = resolve_python_executable()
    expected = ROOT / ".venv" / "bin" / "python"
    if expected.exists():
        assert resolved == str(expected)
    else:
        assert resolved == sys.executable


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


