"""Tests for test_go_live_verify: misc_b.

Extracted from /Users/angel/Developer/decision-engine/.claude/worktrees/wf_ad413055-70e-1/tests/test_go_live_verify.py during modularization.
"""
from __future__ import annotations

from tests._test_go_live_verify_helpers import *  # noqa: F401,F403


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


