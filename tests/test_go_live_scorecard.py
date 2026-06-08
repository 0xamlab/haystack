import json
import os
from pathlib import Path

import pytest


def test_go_live_scorecard_matches_current_verifier_artifact() -> None:
    if os.environ.get("DE_SKIP_GO_LIVE_VERIFY") == "1":
        pytest.skip("nested root js-check reuses the outer verifier artifact and skips scorecard parity")

    text = Path("benchmarks/scorecard.md").read_text()
    summary = json.loads(Path("build/go_live_verify_summary.json").read_text())
    full_real_summary = json.loads(Path("build/go_live_full_real_summary.json").read_text())
    full_real_details = full_real_summary.get("details", {})

    matrix = summary["matrix_summary"]
    completed_steps = " + ".join(summary["completed_steps"]) or "none"
    planned_steps = " + ".join(item["name"] for item in summary["planned_steps"])
    durations = {item["name"]: float(item["duration_s"]) for item in summary["step_results"]}
    gap_source_summary = summary["gap_source_summary"]
    verifier_status = "Red" if summary["failed_steps"] or summary["requirement_failures"] else "Green"
    static_operational_gaps = list(summary.get("static_operational_gaps", []))
    static_gap_status = "Green" if not static_operational_gaps else "Amber"
    live_connectivity_skips = list(summary.get("live_connectivity_skips", []))
    live_skip_status = "Green" if not live_connectivity_skips else "Amber"
    operational_gaps = list(summary.get("operational_gaps", []))
    operational_gap_counts: dict[str, int] = {}
    for gap in operational_gaps:
        tier = str(gap["tier"])
        operational_gap_counts[tier] = operational_gap_counts.get(tier, 0) + 1
    operational_gap_status = "Green" if not operational_gaps else "Amber"
    next_actions = list(summary.get("next_actions", []))
    gap_action_summary = summary["gap_action_summary"]
    gap_connector_summary = summary["gap_connector_summary"]
    gap_env_summary = summary["gap_env_summary"]
    gap_env_resolution_summary = summary["gap_env_resolution_summary"]
    gap_env_template_summary = summary["gap_env_template_summary"]
    if operational_gaps:
        operational_gap_summary = ", ".join(
            f"{tier} {count}" for tier, count in sorted(operational_gap_counts.items())
        )
        operational_gap_current = (
            f"{len(operational_gaps)} cases outside repo-owned proof: {operational_gap_summary}"
        )
    else:
        operational_gap_current = "none"
    breakdown_current = (
        "static tiers "
        f"{', '.join(f'{tier} {count}' for tier, count in gap_source_summary['static_gap_counts_by_tier'].items()) or 'none'}; "
        "live tiers "
        f"{', '.join(f'{tier} {count}' for tier, count in gap_source_summary['live_skip_counts_by_tier'].items()) or 'none'}; "
        "merged sources "
        f"{', '.join(f'{source} {count}' for source, count in gap_source_summary['merged_gap_counts_by_source'].items()) or 'none'}"
    )
    connector_breakdown_current = (
        "merged connectors "
        f"{', '.join(f'{connector} {count}' for connector, count in gap_source_summary['merged_gap_counts_by_connector_type'].items()) or 'none'}"
    )
    action_routing_current = (
        f"{gap_action_summary['mapped_case_count']}/{gap_source_summary['merged_gap_count']} cases mapped; "
        f"actions {', '.join(f'{code} {count}' for code, count in gap_action_summary['action_case_counts'].items()) or 'none'}; "
        f"envs {', '.join(f'{code} {count}' for code, count in gap_action_summary['action_env_counts'].items()) or 'none'}; "
        f"connectors {', '.join(f'{code} {count}' for code, count in gap_action_summary['action_connector_counts'].items()) or 'none'}; "
        f"terminal {', '.join(gap_action_summary['terminal_action_codes']) or 'none'}; "
        f"unmapped {', '.join(gap_action_summary['unmapped_case_ids']) or 'none'}"
    )
    connector_routing_current = (
        f"cases {', '.join(f'{connector} {count}' for connector, count in gap_connector_summary['connector_case_counts'].items()) or 'none'}; "
        f"envs {', '.join(f'{connector} {count}' for connector, count in gap_connector_summary['connector_env_counts'].items()) or 'none'}"
    )
    env_routing_current = (
        f"{gap_env_summary['env_total_count']} envs mapped; "
        f"tiers {', '.join(f'{tier} {count}' for tier, count in gap_env_summary['tier_env_counts'].items()) or 'none'}; "
        f"shared {', '.join(gap_env_summary['shared_env_names']) or 'none'}"
    )
    env_resolution_current = (
        f"resolver-supported {gap_env_resolution_summary['resolver_supported_count']}; "
        f"manual-only {gap_env_resolution_summary['manual_only_count']}; "
        f"groups {', '.join(f'{group} {count}' for group, count in gap_env_resolution_summary['group_env_counts'].items()) or 'none'}; "
        f"manual {', '.join(gap_env_resolution_summary['manual_only_env_names']) or 'none'}"
    )
    env_template_current = (
        "root_env_example "
        f"{gap_env_template_summary['template_documented_counts'].get('root_env_example', 0)}/"
        f"{gap_env_template_summary['gap_env_total_count']}, "
        "go_live_validation_env_example "
        f"{gap_env_template_summary['template_documented_counts'].get('go_live_validation_env_example', 0)}/"
        f"{gap_env_template_summary['gap_env_total_count']}; "
        f"missing {', '.join(gap_env_template_summary['missing_in_any_template']) or 'none'}"
    )
    canonical_mode: list[str] = []
    if not summary["filters"]["tiers"] and not summary["filters"]["connectors"]:
        canonical_mode.append("unfiltered")
    else:
        canonical_mode.append("filtered")
    if not summary["options"]["strict"]:
        canonical_mode.append("non-strict")
    if summary["options"]["include_full_real"]:
        canonical_mode.append("includes full_real")
    else:
        canonical_mode.append("excludes full_real")
    if summary["options"]["include_pytest"]:
        canonical_mode.append("includes pytest")
    else:
        canonical_mode.append("excludes pytest")
    if str(full_real_details.get("status", "complete")) == "complete":
        full_real_current = (
            f"{full_real_summary['passed']}/{full_real_summary['total']} suites passed; "
            f"live API-facing {full_real_details['live_suite_count']}, "
            f"local benchmark/regression {full_real_details['local_suite_count']}, "
            f"top-level verifier/bundle/A-Z {full_real_details['top_level_suite_count']}"
        )
    else:
        full_real_current = (
            f"{full_real_summary['passed']}/{full_real_details.get('expected_suite_count', full_real_summary['total'])} "
            "suites passed so far; "
            f"completed {full_real_details.get('completed_suite_count', full_real_summary['total'])}/"
            f"{full_real_details.get('expected_suite_count', full_real_summary['total'])}"
        )
    full_real_status = (
        "Green"
        if int(full_real_summary["failed"]) == 0
        and str(full_real_details.get("status", "complete")) == "complete"
        else "Red"
    )

    assert "## Go-live verifier (" in text
    assert "build/go_live_verify_summary.json" in text
    assert "build/go_live_verify_report.md" in text
    assert "Static matrix operational gaps" in text
    assert "Live connectivity skips" in text
    assert "Gap source breakdown" in text
    assert "Gap connector breakdown" in text
    assert "Outstanding operational gaps" in text
    assert "Operator next actions" in text
    assert "Gap action routing" in text
    assert "Gap connector routing" in text
    assert "Gap env routing" in text
    assert "Gap env resolution" in text
    assert "Gap env templates" in text
    assert "tests/go_live_verify.py" in text
    assert "tests/test_go_live_verify.py" in text
    assert "tests/go_live_matrix_status.py" in text
    assert "tests/integration/GO_LIVE_VALIDATION.md" in text
    assert (
        f"{matrix['configured_cases']}/{matrix['total_cases']} configured, "
        f"{matrix['behavior_ready_cases']}/{matrix['total_cases']} behavior-ready, "
        f"completed steps {completed_steps}, "
        f"{len(summary['failed_steps'])} failed steps"
    ) in text
    assert planned_steps in text
    assert (
        f"connectivity {durations.get('connectivity', 0.0):.2f}s, "
        f"full_real {durations.get('full_real', 0.0):.2f}s"
    ) in text
    assert (
        "| Serial verifier summary | "
        f"{matrix['configured_cases']}/{matrix['total_cases']} configured, "
        f"{matrix['behavior_ready_cases']}/{matrix['total_cases']} behavior-ready, "
        f"completed steps {completed_steps}, "
        f"{len(summary['failed_steps'])} failed steps | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py`, `tests/test_go_live_verify.py` | "
        f"{verifier_status} |"
    ) in text
    assert (
        "| Full real suite | "
        f"{full_real_current} | "
        "`build/go_live_full_real_summary.json`, `tests/integration/test_go_live_full_real.py` | "
        f"{full_real_status} |"
    ) in text
    assert (
        "| Static matrix operational gaps | "
        f"{len(static_operational_gaps)} cases from the current static matrix status before live connectivity overrides | "
        "`build/go_live_verify_summary.json`, `tests/go_live_matrix_status.py` | "
        f"{static_gap_status} |"
    ) in text
    assert (
        "| Live connectivity skips | "
        f"{gap_source_summary['live_skip_count']} skips captured from the latest connectivity run and merged into operational gaps | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/integration/test_go_live_connectivity_real.py` | "
        f"{live_skip_status} |"
    ) in text
    assert (
        "| Gap source breakdown | "
        f"{breakdown_current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py` | "
        f"{operational_gap_status} |"
    ) in text
    assert (
        "| Gap connector breakdown | "
        f"{connector_breakdown_current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py` | "
        f"{operational_gap_status} |"
    ) in text
    assert (
        "| Outstanding operational gaps | "
        f"{operational_gap_current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_matrix_status.py` | "
        f"{operational_gap_status} |"
    ) in text
    assert (
        "| Operator next actions | "
        f"{len(next_actions)} action groups ready from current operational gaps | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py` | "
        f"{operational_gap_status} |"
    ) in text
    assert (
        "| Gap action routing | "
        f"{action_routing_current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py` | "
        f"{operational_gap_status} |"
    ) in text
    assert (
        "| Gap connector routing | "
        f"{connector_routing_current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py` | "
        f"{operational_gap_status} |"
    ) in text
    assert (
        "| Gap env routing | "
        f"{env_routing_current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py` | "
        f"{operational_gap_status} |"
    ) in text
    assert (
        "| Gap env resolution | "
        f"{env_resolution_current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`tests/go_live_verify.py`, `tests/go_live_secret_resolver.py` | "
        f"{operational_gap_status} |"
    ) in text
    assert (
        "| Gap env templates | "
        f"{env_template_current} | "
        "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
        "`.env.example`, `tests/integration/go_live_validation.env.example`, "
        "`tests/go_live_verify.py` | Green |"
    ) in text
    assert ", ".join(canonical_mode) in text
