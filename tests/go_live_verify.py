from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.go_live_matrix_status import (
    MatrixCaseStatus,
    collect_matrix_status,
    collect_requirement_failures,
    filter_statuses_by_connectors,
    matrix_status_payload,
    parse_selected_connectors,
    parse_selected_tiers,
    render_matrix_status,
    render_requirement_failures,
    summarize_operational_gaps,
)
from tests.go_live_secret_resolver import describe_go_live_env_resolution
from tests.integration.connector_validation_catalog import ALL_CONNECTOR_VALIDATION_CASES

DEFAULT_SUMMARY_OUTPUT = ROOT / "build" / "go_live_verify_summary.json"
DEFAULT_REPORT_OUTPUT = ROOT / "build" / "go_live_verify_report.md"
GO_LIVE_FULL_REAL_SUMMARY_PATH = ROOT / "build" / "go_live_full_real_summary.json"
SCORECARD_PATH = ROOT / "benchmarks" / "scorecard.md"
ROOT_ENV_EXAMPLE_PATH = ROOT / ".env.example"
GO_LIVE_VALIDATION_ENV_EXAMPLE_PATH = (
    ROOT / "tests" / "integration" / "go_live_validation.env.example"
)
_ENV_NAME_PATTERN = re.compile(r"\bDE_[A-Z0-9_]+\b")


@dataclass(frozen=True)
class VerificationStep:
    name: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class VerificationResult:
    name: str
    returncode: int
    duration_s: float
    output: str = ""


def resolve_python_executable() -> str:
    venv_python = ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def build_verification_steps(
    python_executable: str,
    *,
    parallel_tasks: int,
    mojo_workers: int,
    mojo_timeout: int,
    include_full_real: bool,
    include_pytest: bool,
    tiers: tuple[str, ...] | None,
    connectors: tuple[str, ...] | None,
) -> list[VerificationStep]:
    connectivity_command: tuple[str, ...] = (
        python_executable,
        "-u",
        str(ROOT / "tests" / "integration" / "test_go_live_connectivity_real.py"),
        "--parallel-tasks",
        str(parallel_tasks),
    )
    if tiers is not None:
        connectivity_command += ("--tiers", ",".join(tiers))
    if connectors is not None:
        connectivity_command += ("--connector", ",".join(connectors))
    steps = [
        VerificationStep(
            name="connectivity",
            command=connectivity_command,
        ),
    ]
    if include_full_real:
        steps.append(
            VerificationStep(
                name="full_real",
                command=(
                    python_executable,
                    "-u",
                    str(ROOT / "tests" / "integration" / "test_go_live_full_real.py"),
                    "--parallel-tasks",
                    str(parallel_tasks),
                    "--mojo-workers",
                    str(mojo_workers),
                    "--mojo-timeout",
                    str(mojo_timeout),
                ),
            )
        )
    if include_pytest:
        steps.append(
            VerificationStep(
                name="pytest",
                command=(python_executable, "-m", "pytest", "tests", "-q"),
            )
        )
    return steps


def run_verification_steps(steps: list[VerificationStep]) -> list[VerificationResult]:
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    results: list[VerificationResult] = []
    for step in steps:
        print(f"\n=== {step.name} ===")
        start = time.perf_counter()
        proc = subprocess.Popen(
            step.command,
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        output_chunks: list[str] = []
        assert proc.stdout is not None
        for line in proc.stdout:
            print(line, end="")
            output_chunks.append(line)
        proc.stdout.close()
        returncode = proc.wait()
        duration_s = time.perf_counter() - start
        result = VerificationResult(
            name=step.name,
            returncode=returncode,
            duration_s=duration_s,
            output="".join(output_chunks),
        )
        results.append(result)
        if returncode != 0:
            break
    return results


def summarize_verification(
    matrix_payload: dict[str, Any],
    planned_steps: list[VerificationStep],
    results: list[VerificationResult],
    requirement_failures: list[dict[str, Any]],
) -> dict[str, Any]:
    failed_steps = [result.name for result in results if result.returncode != 0]
    completed_steps = [result.name for result in results if result.returncode == 0]
    return {
        "matrix_summary": matrix_payload["summary"],
        "requirement_failures": requirement_failures,
        "completed_steps": completed_steps,
        "failed_steps": failed_steps,
        "planned_steps": [
            {
                "name": step.name,
                "command": list(step.command),
            }
            for step in planned_steps
        ],
        "step_results": [
            {
                "name": result.name,
                "returncode": result.returncode,
                "duration_s": round(result.duration_s, 3),
            }
            for result in results
        ],
    }


def _extract_gap_env_names(reason: str) -> list[str]:
    return sorted(dict.fromkeys(_ENV_NAME_PATTERN.findall(reason)))


_CASE_BY_LABEL = {case.label: case for case in ALL_CONNECTOR_VALIDATION_CASES}


def extract_live_connectivity_skips(
    output: str,
    statuses: list[MatrixCaseStatus],
) -> list[dict[str, Any]]:
    if not output:
        return []

    status_index = {status.case_id: status for status in statuses}
    live_gaps: list[dict[str, Any]] = []
    in_skipped_section = False
    for raw_line in output.splitlines():
        stripped = raw_line.strip()
        if stripped == "Skipped checks:":
            in_skipped_section = True
            continue
        if not in_skipped_section:
            continue
        if not stripped:
            continue
        if stripped == "Slowest:" or stripped.startswith("="):
            break
        if not stripped.startswith("- "):
            continue
        body = stripped[2:]
        if ": " in body:
            label, reason = body.split(": ", 1)
        else:
            label, reason = body, ""
        case = _CASE_BY_LABEL.get(label)
        if case is None:
            continue
        status = status_index.get(case.case_id)
        live_gaps.append(
            {
                "case_id": case.case_id,
                "label": case.label,
                "tier": case.tier,
                "connector_type": case.connector_type,
                "gap_type": (
                    "not_behavior_ready"
                    if status is not None and status.configured
                    else "not_configured"
                ),
                "reason": reason or "live connectivity check skipped",
            }
        )
    return sorted(live_gaps, key=lambda item: (str(item["tier"]), str(item["case_id"])))


def merge_operational_gaps(
    static_gaps: list[dict[str, Any]],
    live_gaps: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    static_index = {str(gap["case_id"]): dict(gap) for gap in static_gaps}
    live_index = {str(gap["case_id"]): dict(gap) for gap in live_gaps}
    merged: list[dict[str, Any]] = []
    for case_id in sorted(
        set(static_index) | set(live_index),
        key=lambda item: (
            str(
                (
                    live_index.get(item)
                    or static_index.get(item)
                    or {}
                ).get("tier", "")
            ),
            item,
        ),
    ):
        static_gap = static_index.get(case_id)
        live_gap = live_index.get(case_id)
        preferred = live_gap or static_gap or {}
        sources: list[str] = []
        if static_gap is not None:
            sources.append("static_matrix")
        if live_gap is not None:
            sources.append("live_connectivity")
        merged.append(
            {
                "case_id": preferred.get("case_id", case_id),
                "label": preferred.get("label", ""),
                "tier": preferred.get("tier", ""),
                "connector_type": preferred.get("connector_type", ""),
                "gap_type": preferred.get("gap_type", "not_configured"),
                "reason": preferred.get("reason", "case is blocked"),
                "source": "+".join(sources),
                "sources": sources,
                "static_reason": None if static_gap is None else static_gap.get("reason"),
                "live_reason": None if live_gap is None else live_gap.get("reason"),
            }
        )
    return merged


def build_gap_source_summary(
    static_gaps: list[dict[str, Any]],
    live_gaps: list[dict[str, Any]],
    merged_gaps: list[dict[str, Any]],
) -> dict[str, Any]:
    def count_by_key(
        gaps: list[dict[str, Any]],
        key: str,
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for gap in gaps:
            value = str(gap.get(key, "") or "unknown")
            counts[value] = counts.get(value, 0) + 1
        return {name: counts[name] for name in sorted(counts)}

    static_gap_case_ids = {str(gap["case_id"]) for gap in static_gaps}
    live_gap_case_ids = {str(gap["case_id"]) for gap in live_gaps}
    merged_gap_case_ids = {str(gap["case_id"]) for gap in merged_gaps}
    live_only_case_ids = sorted(live_gap_case_ids - static_gap_case_ids)
    static_only_case_ids = sorted(static_gap_case_ids - live_gap_case_ids)
    return {
        "static_gap_count": len(static_gaps),
        "live_skip_count": len(live_gaps),
        "merged_gap_count": len(merged_gaps),
        "live_only_case_ids": live_only_case_ids,
        "static_only_case_ids": static_only_case_ids,
        "merged_case_ids": sorted(merged_gap_case_ids),
        "static_gap_counts_by_tier": count_by_key(static_gaps, "tier"),
        "static_gap_counts_by_connector_type": count_by_key(static_gaps, "connector_type"),
        "live_skip_counts_by_tier": count_by_key(live_gaps, "tier"),
        "live_skip_counts_by_connector_type": count_by_key(live_gaps, "connector_type"),
        "merged_gap_counts_by_tier": count_by_key(merged_gaps, "tier"),
        "merged_gap_counts_by_connector_type": count_by_key(merged_gaps, "connector_type"),
        "merged_gap_counts_by_source": count_by_key(merged_gaps, "source"),
    }


def build_go_live_next_actions(operational_gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not operational_gaps:
        return []

    actions: list[dict[str, Any]] = []

    public_opt_in_cases = sorted(
        gap["case_id"]
        for gap in operational_gaps
        if str(gap.get("tier")) == "public_no_auth"
        and "disabled by default" in str(gap.get("reason", "")).lower()
    )
    if public_opt_in_cases:
        actions.append(
            {
                "code": "enable_opt_in_public_cases",
                "message": (
                    "Enable the optional public REST cases before rerunning the public "
                    "connectivity proof."
                ),
                "command": "DE_ENABLE_SLOW_PUBLIC_REST_CASES=1 make test-go-live-connectivity",
                "details": {
                    "case_ids": public_opt_in_cases,
                    "env_names": ["DE_ENABLE_SLOW_PUBLIC_REST_CASES"],
                },
            }
        )

    tier2_gaps = [
        gap for gap in operational_gaps if str(gap.get("tier")) == "credentialed_example"
    ]
    tier2_envs = sorted(
        {
            env
            for gap in tier2_gaps
            for env in _extract_gap_env_names(str(gap.get("reason", "")))
        }
    )
    if tier2_gaps:
        actions.append(
            {
                "code": "set_credentialed_example_envs",
                "message": (
                    "Set the missing Tier 2 credentialed-example environment variables and "
                    "rerun the focused Tier 2 connectivity slice."
                ),
                "command": "make go-live-status-tier2 && make test-go-live-connectivity-tier2",
                "details": {
                    "case_ids": sorted(str(gap["case_id"]) for gap in tier2_gaps),
                    "env_names": tier2_envs,
                },
            }
        )

    tier3_gaps = [
        gap
        for gap in operational_gaps
        if str(gap.get("tier")) == "customer_credentials_required"
    ]
    tier3_envs = sorted(
        {
            env
            for gap in tier3_gaps
            for env in _extract_gap_env_names(str(gap.get("reason", "")))
        }
    )
    tier3_missing_env_cases = sorted(
        str(gap["case_id"])
        for gap in tier3_gaps
        if _extract_gap_env_names(str(gap.get("reason", "")))
    )
    if tier3_missing_env_cases:
        actions.append(
            {
                "code": "set_customer_connector_envs",
                "message": (
                    "Set the missing Tier 3 customer-credential variables and rerun the "
                    "focused customer-connector connectivity slice."
                ),
                "command": "make go-live-status-tier3 && make test-go-live-connectivity-tier3",
                "details": {
                    "case_ids": tier3_missing_env_cases,
                    "env_names": tier3_envs,
                },
            }
        )

    network_policy_cases = sorted(
        str(gap["case_id"])
        for gap in tier3_gaps
        if "network policy" in str(gap.get("reason", "")).lower()
    )
    if network_policy_cases:
        actions.append(
            {
                "code": "resolve_network_policy_blockers",
                "message": (
                    "Resolve the remaining network-policy-gated customer connector probes "
                    "before rerunning the Tier 3 slice."
                ),
                "command": "make go-live-probe-snowflake",
                "details": {"case_ids": network_policy_cases},
            }
        )

    actions.append(
        {
            "code": "rerun_strict_go_live_gate",
            "message": (
                "After the listed operational gaps are cleared, rerun the strict matrix "
                "and the full go-live verifier."
            ),
            "command": "make go-live-status-strict && make go-live-verify-all",
        }
    )
    return actions


def annotate_operational_gaps_with_actions(
    operational_gaps: list[dict[str, Any]],
    next_actions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    case_action_codes: dict[str, list[str]] = {}
    for action in next_actions:
        code = str(action.get("code", "") or "")
        details = action.get("details") or {}
        if not code or not isinstance(details, dict):
            continue
        case_ids = details.get("case_ids") or []
        for case_id in case_ids:
            normalized_case_id = str(case_id)
            case_action_codes.setdefault(normalized_case_id, []).append(code)

    annotated: list[dict[str, Any]] = []
    for gap in operational_gaps:
        normalized_case_id = str(gap.get("case_id", ""))
        action_codes = sorted(set(case_action_codes.get(normalized_case_id, [])))
        annotated.append({**gap, "action_codes": action_codes})
    return annotated


def build_gap_action_summary(
    operational_gaps: list[dict[str, Any]],
    next_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    action_case_counts: dict[str, int] = {}
    action_case_ids: dict[str, list[str]] = {}
    action_env_names: dict[str, list[str]] = {}
    action_connector_types: dict[str, list[str]] = {}
    mapped_case_ids: set[str] = set()
    terminal_action_codes: list[str] = []
    gap_index = {str(gap.get("case_id", "")): gap for gap in operational_gaps}

    for action in next_actions:
        code = str(action.get("code", "") or "")
        details = action.get("details") or {}
        case_ids = []
        env_names = []
        if isinstance(details, dict):
            case_ids = [str(case_id) for case_id in details.get("case_ids") or []]
            env_names = [str(env_name) for env_name in details.get("env_names") or []]
        if case_ids:
            sorted_case_ids = sorted(set(case_ids))
            action_case_counts[code] = len(sorted_case_ids)
            action_case_ids[code] = sorted_case_ids
            mapped_case_ids.update(sorted_case_ids)
            action_connector_types[code] = sorted(
                {
                    str(gap_index[case_id].get("connector_type", "") or "unknown")
                    for case_id in sorted_case_ids
                    if case_id in gap_index
                }
            )
        elif code:
            terminal_action_codes.append(code)
        if code and env_names:
            action_env_names[code] = sorted(set(env_names))

    all_case_ids = {str(gap.get("case_id", "")) for gap in operational_gaps}
    return {
        "mapped_case_count": len(mapped_case_ids),
        "unmapped_case_ids": sorted(all_case_ids - mapped_case_ids),
        "action_case_counts": {
            code: action_case_counts[code] for code in sorted(action_case_counts)
        },
        "action_case_ids": {code: action_case_ids[code] for code in sorted(action_case_ids)},
        "action_env_names": {code: action_env_names[code] for code in sorted(action_env_names)},
        "action_env_counts": {
            code: len(action_env_names[code]) for code in sorted(action_env_names)
        },
        "action_connector_types": {
            code: action_connector_types[code] for code in sorted(action_connector_types)
        },
        "action_connector_counts": {
            code: len(action_connector_types[code]) for code in sorted(action_connector_types)
        },
        "terminal_action_codes": sorted(set(terminal_action_codes)),
    }


def build_gap_connector_summary(
    operational_gaps: list[dict[str, Any]],
    next_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    connector_case_ids: dict[str, list[str]] = {}
    connector_action_codes: dict[str, list[str]] = {}
    connector_env_names: dict[str, list[str]] = {}
    for gap in operational_gaps:
        connector_type = str(gap.get("connector_type", "") or "unknown")
        case_id = str(gap.get("case_id", ""))
        action_codes = [str(code) for code in gap.get("action_codes") or []]
        connector_case_ids.setdefault(connector_type, []).append(case_id)
        connector_action_codes.setdefault(connector_type, []).extend(action_codes)
        env_names = _extract_gap_env_names(str(gap.get("reason", "")))
        connector_env_names.setdefault(connector_type, []).extend(env_names)

    normalized_case_ids = {
        connector_type: sorted(set(case_ids))
        for connector_type, case_ids in connector_case_ids.items()
    }
    normalized_action_codes = {
        connector_type: sorted(set(action_codes))
        for connector_type, action_codes in connector_action_codes.items()
    }
    normalized_env_names = {
        connector_type: sorted(set(env_names))
        for connector_type, env_names in connector_env_names.items()
        if env_names
    }
    return {
        "connector_case_counts": {
            connector_type: len(normalized_case_ids[connector_type])
            for connector_type in sorted(normalized_case_ids)
        },
        "connector_case_ids": {
            connector_type: normalized_case_ids[connector_type]
            for connector_type in sorted(normalized_case_ids)
        },
        "connector_action_codes": {
            connector_type: normalized_action_codes[connector_type]
            for connector_type in sorted(normalized_action_codes)
        },
        "connector_env_counts": {
            connector_type: len(normalized_env_names[connector_type])
            for connector_type in sorted(normalized_env_names)
        },
        "connector_env_names": {
            connector_type: normalized_env_names[connector_type]
            for connector_type in sorted(normalized_env_names)
        },
    }


def build_gap_env_summary(
    operational_gaps: list[dict[str, Any]],
    next_actions: list[dict[str, Any]],
) -> dict[str, Any]:
    case_action_codes: dict[str, list[str]] = {}
    for action in next_actions:
        code = str(action.get("code", "") or "")
        details = action.get("details") or {}
        if not code or not isinstance(details, dict):
            continue
        for case_id in details.get("case_ids") or []:
            normalized_case_id = str(case_id)
            case_action_codes.setdefault(normalized_case_id, []).append(code)

    env_case_ids: dict[str, list[str]] = {}
    env_connector_types: dict[str, list[str]] = {}
    env_action_codes: dict[str, list[str]] = {}
    env_tiers: dict[str, list[str]] = {}
    for gap in operational_gaps:
        case_id = str(gap.get("case_id", ""))
        connector_type = str(gap.get("connector_type", "") or "unknown")
        tier = str(gap.get("tier", "") or "unknown")
        action_codes = [
            str(code) for code in (gap.get("action_codes") or case_action_codes.get(case_id, []))
        ]
        for env_name in _extract_gap_env_names(str(gap.get("reason", ""))):
            env_case_ids.setdefault(env_name, []).append(case_id)
            env_connector_types.setdefault(env_name, []).append(connector_type)
            env_action_codes.setdefault(env_name, []).extend(action_codes)
            env_tiers.setdefault(env_name, []).append(tier)

    normalized_case_ids = {
        env_name: sorted(set(case_ids))
        for env_name, case_ids in env_case_ids.items()
    }
    normalized_connector_types = {
        env_name: sorted(set(connector_types))
        for env_name, connector_types in env_connector_types.items()
    }
    normalized_action_codes = {
        env_name: sorted(set(action_codes))
        for env_name, action_codes in env_action_codes.items()
    }
    normalized_tiers = {
        env_name: sorted(set(tiers))
        for env_name, tiers in env_tiers.items()
    }
    shared_env_names = sorted(
        env_name
        for env_name in normalized_case_ids
        if len(normalized_case_ids[env_name]) > 1
        or len(normalized_connector_types.get(env_name, [])) > 1
        or len(normalized_action_codes.get(env_name, [])) > 1
        or len(normalized_tiers.get(env_name, [])) > 1
    )
    tier_env_counts: dict[str, int] = {}
    for tiers in normalized_tiers.values():
        for tier in tiers:
            tier_env_counts[tier] = tier_env_counts.get(tier, 0) + 1

    return {
        "env_total_count": len(normalized_case_ids),
        "shared_env_names": shared_env_names,
        "tier_env_counts": {
            tier: tier_env_counts[tier] for tier in sorted(tier_env_counts)
        },
        "env_case_counts": {
            env_name: len(normalized_case_ids[env_name])
            for env_name in sorted(normalized_case_ids)
        },
        "env_case_ids": {
            env_name: normalized_case_ids[env_name]
            for env_name in sorted(normalized_case_ids)
        },
        "env_connector_types": {
            env_name: normalized_connector_types[env_name]
            for env_name in sorted(normalized_connector_types)
        },
        "env_connector_counts": {
            env_name: len(normalized_connector_types[env_name])
            for env_name in sorted(normalized_connector_types)
        },
        "env_action_codes": {
            env_name: normalized_action_codes[env_name]
            for env_name in sorted(normalized_action_codes)
            if normalized_action_codes[env_name]
        },
        "env_action_counts": {
            env_name: len(normalized_action_codes[env_name])
            for env_name in sorted(normalized_action_codes)
            if normalized_action_codes[env_name]
        },
        "env_tiers": {
            env_name: normalized_tiers[env_name]
            for env_name in sorted(normalized_tiers)
        },
    }


def build_gap_env_resolution_summary(gap_env_summary: dict[str, Any]) -> dict[str, Any]:
    env_names = sorted((gap_env_summary.get("env_case_ids") or {}).keys())
    resolver_supported_env_names: list[str] = []
    manual_only_env_names: list[str] = []
    env_candidate_names: dict[str, list[str]] = {}
    env_group_names: dict[str, str] = {}
    group_env_counts: dict[str, int] = {}

    for env_name in env_names:
        description = describe_go_live_env_resolution(env_name)
        env_candidate_names[env_name] = [str(name) for name in description["candidate_names"]]
        group_name = description["group_name"]
        if isinstance(group_name, str) and group_name:
            env_group_names[env_name] = group_name
            group_env_counts[group_name] = group_env_counts.get(group_name, 0) + 1
        if bool(description["resolver_supported"]):
            resolver_supported_env_names.append(env_name)
        else:
            manual_only_env_names.append(env_name)

    return {
        "resolver_supported_count": len(resolver_supported_env_names),
        "manual_only_count": len(manual_only_env_names),
        "resolver_supported_env_names": resolver_supported_env_names,
        "manual_only_env_names": manual_only_env_names,
        "env_candidate_names": {
            env_name: env_candidate_names[env_name] for env_name in sorted(env_candidate_names)
        },
        "env_group_names": {
            env_name: env_group_names[env_name] for env_name in sorted(env_group_names)
        },
        "group_env_counts": {
            group_name: group_env_counts[group_name] for group_name in sorted(group_env_counts)
        },
    }


def _extract_env_assignment_names(text: str) -> set[str]:
    return {match.group(1) for match in re.finditer(r"(?m)^([A-Z0-9_]+)=", text)}


def build_gap_env_template_summary(
    gap_env_summary: dict[str, Any],
    *,
    template_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    env_names = sorted((gap_env_summary.get("env_case_ids") or {}).keys())
    resolved_template_paths = template_paths or {
        "root_env_example": ROOT_ENV_EXAMPLE_PATH,
        "go_live_validation_env_example": GO_LIVE_VALIDATION_ENV_EXAMPLE_PATH,
    }
    template_documented_counts: dict[str, int] = {}
    template_missing_counts: dict[str, int] = {}
    template_missing_env_names: dict[str, list[str]] = {}
    normalized_template_paths: dict[str, str] = {}

    for template_name, template_path in sorted(resolved_template_paths.items()):
        normalized_path = (
            str(template_path.relative_to(ROOT))
            if template_path.is_absolute() and ROOT in template_path.parents
            else str(template_path)
        )
        normalized_template_paths[template_name] = normalized_path
        template_env_names = _extract_env_assignment_names(
            template_path.read_text(encoding="utf-8")
        )
        missing_env_names = sorted(set(env_names) - template_env_names)
        template_documented_counts[template_name] = len(env_names) - len(missing_env_names)
        template_missing_counts[template_name] = len(missing_env_names)
        template_missing_env_names[template_name] = missing_env_names

    missing_in_any_template = sorted(
        {
            env_name
            for missing_env_names in template_missing_env_names.values()
            for env_name in missing_env_names
        }
    )
    templates_with_missing_envs = sorted(
        template_name
        for template_name, missing_env_names in template_missing_env_names.items()
        if missing_env_names
    )

    return {
        "gap_env_total_count": len(env_names),
        "all_templates_cover_all_gap_envs": not missing_in_any_template,
        "template_paths": normalized_template_paths,
        "template_documented_counts": {
            template_name: template_documented_counts[template_name]
            for template_name in sorted(template_documented_counts)
        },
        "template_missing_counts": {
            template_name: template_missing_counts[template_name]
            for template_name in sorted(template_missing_counts)
        },
        "template_missing_env_names": {
            template_name: template_missing_env_names[template_name]
            for template_name in sorted(template_missing_env_names)
        },
        "templates_with_missing_envs": templates_with_missing_envs,
        "missing_in_any_template": missing_in_any_template,
    }


def build_gap_action_env_setup_summary(
    gap_action_summary: dict[str, Any],
    gap_env_resolution_summary: dict[str, Any],
    *,
    template_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    action_env_names = {
        str(action_code): [str(env_name) for env_name in env_names]
        for action_code, env_names in (gap_action_summary.get("action_env_names") or {}).items()
    }
    action_case_ids = {
        str(action_code): [str(case_id) for case_id in case_ids]
        for action_code, case_ids in (gap_action_summary.get("action_case_ids") or {}).items()
    }
    action_connector_types = {
        str(action_code): [str(connector_type) for connector_type in connector_types]
        for action_code, connector_types in (
            gap_action_summary.get("action_connector_types") or {}
        ).items()
    }
    terminal_action_codes = [
        str(action_code) for action_code in (gap_action_summary.get("terminal_action_codes") or [])
    ]
    all_action_codes = sorted(
        set(action_env_names)
        | set(action_case_ids)
        | set(action_connector_types)
        | set(terminal_action_codes)
    )
    actions_with_env_requirements = sorted(
        action_code for action_code in all_action_codes if action_env_names.get(action_code)
    )
    actions_without_env_requirements = sorted(
        action_code for action_code in all_action_codes if not action_env_names.get(action_code)
    )

    resolver_supported_env_names = set(
        str(env_name)
        for env_name in (gap_env_resolution_summary.get("resolver_supported_env_names") or [])
    )
    manual_only_env_names = set(
        str(env_name)
        for env_name in (gap_env_resolution_summary.get("manual_only_env_names") or [])
    )
    resolved_template_paths = template_paths or {
        "root_env_example": ROOT_ENV_EXAMPLE_PATH,
        "go_live_validation_env_example": GO_LIVE_VALIDATION_ENV_EXAMPLE_PATH,
    }
    template_env_names_by_name = {
        template_name: _extract_env_assignment_names(template_path.read_text(encoding="utf-8"))
        for template_name, template_path in sorted(resolved_template_paths.items())
    }

    action_env_total_counts: dict[str, int] = {}
    action_resolver_supported_env_counts: dict[str, int] = {}
    action_resolver_supported_env_names: dict[str, list[str]] = {}
    action_manual_only_env_counts: dict[str, int] = {}
    action_manual_only_env_names: dict[str, list[str]] = {}
    action_template_documented_counts: dict[str, dict[str, int]] = {}
    action_template_missing_env_names: dict[str, dict[str, list[str]]] = {}

    for action_code in actions_with_env_requirements:
        env_names = sorted(set(action_env_names.get(action_code, [])))
        action_env_total_counts[action_code] = len(env_names)
        supported = sorted(env_name for env_name in env_names if env_name in resolver_supported_env_names)
        manual = sorted(env_name for env_name in env_names if env_name in manual_only_env_names)
        action_resolver_supported_env_counts[action_code] = len(supported)
        action_resolver_supported_env_names[action_code] = supported
        action_manual_only_env_counts[action_code] = len(manual)
        action_manual_only_env_names[action_code] = manual

        action_template_documented_counts[action_code] = {}
        action_template_missing_env_names[action_code] = {}
        env_name_set = set(env_names)
        for template_name, template_env_names in sorted(template_env_names_by_name.items()):
            missing = sorted(env_name_set - template_env_names)
            action_template_documented_counts[action_code][template_name] = len(env_names) - len(missing)
            action_template_missing_env_names[action_code][template_name] = missing

    return {
        "actions_with_env_requirements": actions_with_env_requirements,
        "actions_without_env_requirements": actions_without_env_requirements,
        "action_env_total_counts": {
            action_code: action_env_total_counts[action_code]
            for action_code in sorted(action_env_total_counts)
        },
        "action_resolver_supported_env_counts": {
            action_code: action_resolver_supported_env_counts[action_code]
            for action_code in sorted(action_resolver_supported_env_counts)
        },
        "action_resolver_supported_env_names": {
            action_code: action_resolver_supported_env_names[action_code]
            for action_code in sorted(action_resolver_supported_env_names)
        },
        "action_manual_only_env_counts": {
            action_code: action_manual_only_env_counts[action_code]
            for action_code in sorted(action_manual_only_env_counts)
        },
        "action_manual_only_env_names": {
            action_code: action_manual_only_env_names[action_code]
            for action_code in sorted(action_manual_only_env_names)
        },
        "action_template_documented_counts": {
            action_code: {
                template_name: action_template_documented_counts[action_code][template_name]
                for template_name in sorted(action_template_documented_counts[action_code])
            }
            for action_code in sorted(action_template_documented_counts)
        },
        "action_template_missing_env_names": {
            action_code: {
                template_name: action_template_missing_env_names[action_code][template_name]
                for template_name in sorted(action_template_missing_env_names[action_code])
            }
            for action_code in sorted(action_template_missing_env_names)
        },
    }


def write_verification_summary(
    summary: dict[str, Any],
    *,
    output_path: Path = DEFAULT_SUMMARY_OUTPUT,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(f"{json.dumps(summary, indent=2)}\n", encoding="utf-8")


def build_verification_metadata(
    *,
    python_executable: str,
    output_path: Path,
    selected_tiers: tuple[str, ...] | None,
    selected_connectors: tuple[str, ...] | None,
    include_full_real: bool,
    include_pytest: bool,
    require_all_configured: bool,
    require_all_behavior_ready: bool,
    strict: bool,
) -> dict[str, Any]:
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "python_executable": python_executable,
        "output_path": str(output_path),
        "filters": {
            "tiers": list(selected_tiers or ()),
            "connectors": list(selected_connectors or ()),
        },
        "options": {
            "include_full_real": include_full_real,
            "include_pytest": include_pytest,
            "require_all_configured": require_all_configured,
            "require_all_behavior_ready": require_all_behavior_ready,
            "strict": strict,
        },
    }


def _join_step_names(step_names: list[str]) -> str:
    if not step_names:
        return "none"
    if len(step_names) == 1:
        return step_names[0]
    return " + ".join(step_names)


def _format_report_duration(value: float) -> str:
    return f"{value:.2f}s"


def _format_count_breakdown(counts: dict[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{name} {value}" for name, value in sorted(counts.items()))


def render_go_live_verify_markdown_report(summary: dict[str, Any]) -> str:
    matrix = summary["matrix_summary"]
    options = summary["options"]
    filters = summary["filters"]
    planned_steps = summary["planned_steps"]
    step_results = summary["step_results"]
    static_operational_gaps = summary.get("static_operational_gaps", [])
    live_connectivity_skips = summary.get("live_connectivity_skips", [])
    operational_gaps = summary.get("operational_gaps", [])
    next_actions = summary.get("next_actions") or build_go_live_next_actions(list(operational_gaps))
    computed_gap_action_summary = build_gap_action_summary(
        list(operational_gaps),
        list(next_actions),
    )
    computed_gap_connector_summary = build_gap_connector_summary(
        list(operational_gaps),
        list(next_actions),
    )
    computed_gap_env_summary = build_gap_env_summary(
        list(operational_gaps),
        list(next_actions),
    )
    computed_gap_env_resolution_summary = build_gap_env_resolution_summary(
        computed_gap_env_summary
    )
    computed_gap_env_template_summary = build_gap_env_template_summary(
        computed_gap_env_summary
    )
    computed_gap_source_summary = build_gap_source_summary(
        list(static_operational_gaps),
        list(live_connectivity_skips),
        list(operational_gaps),
    )
    gap_source_summary = {
        **computed_gap_source_summary,
        **(summary.get("gap_source_summary") or {}),
    }
    gap_action_summary = {
        **computed_gap_action_summary,
        **(summary.get("gap_action_summary") or {}),
    }
    gap_connector_summary = {
        **computed_gap_connector_summary,
        **(summary.get("gap_connector_summary") or {}),
    }
    gap_env_summary = {
        **computed_gap_env_summary,
        **(summary.get("gap_env_summary") or {}),
    }
    gap_env_resolution_summary = {
        **computed_gap_env_resolution_summary,
        **(summary.get("gap_env_resolution_summary") or {}),
    }
    gap_env_template_summary = {
        **computed_gap_env_template_summary,
        **(summary.get("gap_env_template_summary") or {}),
    }

    lines = [
        "# Go-live verifier report",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Python: `{summary['python_executable']}`",
        f"- Summary path: `{summary['output_path']}`",
        "",
        "## Matrix",
        "",
        f"- Configured: `{matrix['configured_cases']}/{matrix['total_cases']}`",
        f"- Behavior-ready: `{matrix['behavior_ready_cases']}/{matrix['total_cases']}`",
        f"- `public_no_auth`: `{matrix['tiers']['public_no_auth']['configured']}/{matrix['tiers']['public_no_auth']['total']}` configured, `{matrix['tiers']['public_no_auth']['behavior_ready']}/{matrix['tiers']['public_no_auth']['total']}` behavior-ready",
        f"- `credentialed_example`: `{matrix['tiers']['credentialed_example']['configured']}/{matrix['tiers']['credentialed_example']['total']}` configured, `{matrix['tiers']['credentialed_example']['behavior_ready']}/{matrix['tiers']['credentialed_example']['total']}` behavior-ready",
        f"- `customer_credentials_required`: `{matrix['tiers']['customer_credentials_required']['configured']}/{matrix['tiers']['customer_credentials_required']['total']}` configured, `{matrix['tiers']['customer_credentials_required']['behavior_ready']}/{matrix['tiers']['customer_credentials_required']['total']}` behavior-ready",
        "",
        "## Execution",
        "",
        f"- Completed steps: `{', '.join(summary['completed_steps']) or 'none'}`",
        f"- Failed steps: `{', '.join(summary['failed_steps']) or 'none'}`",
        f"- Planned steps: `{', '.join(step['name'] for step in planned_steps) or 'none'}`",
        "",
        "## Filters",
        "",
        f"- Tiers: `{', '.join(filters['tiers']) or 'none'}`",
        f"- Connectors: `{', '.join(filters['connectors']) or 'none'}`",
        "",
        "## Options",
        "",
        f"- include_full_real: `{options['include_full_real']}`",
        f"- include_pytest: `{options['include_pytest']}`",
        f"- require_all_configured: `{options['require_all_configured']}`",
        f"- require_all_behavior_ready: `{options['require_all_behavior_ready']}`",
        f"- strict: `{options['strict']}`",
        "",
        "## Step details",
        "",
    ]

    for step in planned_steps:
        lines.append(f"### `{step['name']}`")
        lines.append("")
        lines.append(f"- Command: `{ ' '.join(step['command']) }`")
        matching_result = next(
            (item for item in step_results if item["name"] == step["name"]),
            None,
        )
        if matching_result is None:
            lines.append("- Result: `not run`")
        else:
            lines.append(f"- Return code: `{matching_result['returncode']}`")
            lines.append(
                f"- Duration: `{_format_report_duration(float(matching_result['duration_s']))}`"
            )
        lines.append("")

    requirement_failures = summary["requirement_failures"]
    lines.append("## Requirement failures")
    lines.append("")
    if not requirement_failures:
        lines.append("- None")
    else:
        for failure in requirement_failures:
            lines.append(
                f"- `{failure['requirement']}` -> `{failure['case_id']}`: {failure['reason']}"
            )

    lines.append("")
    lines.append("## Gap sources")
    lines.append("")
    lines.append(f"- Static matrix gaps: `{gap_source_summary['static_gap_count']}`")
    lines.append(f"- Live connectivity skips: `{gap_source_summary['live_skip_count']}`")
    lines.append(f"- Merged operational gaps: `{gap_source_summary['merged_gap_count']}`")
    lines.append(
        f"- Static gaps by tier: `{_format_count_breakdown(gap_source_summary['static_gap_counts_by_tier'])}`"
    )
    lines.append(
        f"- Static gaps by connector: `{_format_count_breakdown(gap_source_summary['static_gap_counts_by_connector_type'])}`"
    )
    lines.append(
        f"- Live skips by tier: `{_format_count_breakdown(gap_source_summary['live_skip_counts_by_tier'])}`"
    )
    lines.append(
        f"- Live skips by connector: `{_format_count_breakdown(gap_source_summary['live_skip_counts_by_connector_type'])}`"
    )
    lines.append(
        f"- Merged gaps by tier: `{_format_count_breakdown(gap_source_summary['merged_gap_counts_by_tier'])}`"
    )
    lines.append(
        f"- Merged gaps by connector: `{_format_count_breakdown(gap_source_summary['merged_gap_counts_by_connector_type'])}`"
    )
    lines.append(
        f"- Merged gaps by source: `{_format_count_breakdown(gap_source_summary['merged_gap_counts_by_source'])}`"
    )
    lines.append(
        f"- Live-only blockers beyond the static matrix: `{', '.join(gap_source_summary['live_only_case_ids']) or 'none'}`"
    )

    lines.append("")
    lines.append("## Live connectivity skips")
    lines.append("")
    if not live_connectivity_skips:
        lines.append("- None")
    else:
        lines.append(
            "- These skips came from the latest real connectivity run and are merged into `operational_gaps`."
        )
        for gap in live_connectivity_skips:
            lines.append(
                f"- `{gap['tier']}` / `{gap['case_id']}` (`{gap['connector_type']}`, `{gap['gap_type']}`): {gap['reason']}"
            )

    lines.append("")
    lines.append("## Operational gaps")
    lines.append("")
    if not operational_gaps:
        lines.append("- None")
    else:
        for gap in operational_gaps:
            source = str(gap.get("source", "") or "")
            source_suffix = f" [source: {source}]" if source else ""
            action_codes = [str(code) for code in gap.get("action_codes") or []]
            action_suffix = (
                f" [actions: {', '.join(action_codes)}]" if action_codes else ""
            )
            lines.append(
                f"- `{gap['tier']}` / `{gap['case_id']}` (`{gap['connector_type']}`, `{gap['gap_type']}`){source_suffix}{action_suffix}: {gap['reason']}"
            )

    lines.append("")
    lines.append("## Next actions")
    lines.append("")
    if not next_actions:
        lines.append("- None")
    else:
        for action in next_actions:
            lines.append(f"- `{action['code']}`: {action['message']}")
            command = str(action.get("command", "") or "").strip()
            if command:
                lines.append(f"  - command: `{command}`")

    lines.append("")
    lines.append("## Action routing")
    lines.append("")
    lines.append(
        f"- Direct remediation coverage: `{gap_action_summary['mapped_case_count']}/{gap_source_summary['merged_gap_count']}` cases"
    )
    lines.append(
        f"- Action case counts: `{_format_count_breakdown(gap_action_summary['action_case_counts'])}`"
    )
    lines.append(
        f"- Action env counts: `{_format_count_breakdown(gap_action_summary['action_env_counts'])}`"
    )
    lines.append(
        f"- Action connector counts: `{_format_count_breakdown(gap_action_summary['action_connector_counts'])}`"
    )
    lines.append(
        f"- Terminal actions: `{', '.join(gap_action_summary['terminal_action_codes']) or 'none'}`"
    )
    lines.append(
        f"- Unmapped cases: `{', '.join(gap_action_summary['unmapped_case_ids']) or 'none'}`"
    )
    if gap_action_summary["action_case_ids"]:
        for action_code in sorted(gap_action_summary["action_case_ids"]):
            lines.append(
                f"- `{action_code}` cases: `{', '.join(gap_action_summary['action_case_ids'][action_code])}`"
            )
    else:
        lines.append("- Action case ids: `none`")
    if gap_action_summary["action_env_names"]:
        for action_code in sorted(gap_action_summary["action_env_names"]):
            lines.append(
                f"- `{action_code}` envs: `{', '.join(gap_action_summary['action_env_names'][action_code])}`"
            )
    else:
        lines.append("- Action env names: `none`")
    if gap_action_summary["action_connector_types"]:
        for action_code in sorted(gap_action_summary["action_connector_types"]):
            lines.append(
                f"- `{action_code}` connectors: `{', '.join(gap_action_summary['action_connector_types'][action_code])}`"
            )
    else:
        lines.append("- Action connector types: `none`")

    lines.append("")
    lines.append("## Connector routing")
    lines.append("")
    lines.append(
        f"- Connector case counts: `{_format_count_breakdown(gap_connector_summary['connector_case_counts'])}`"
    )
    lines.append(
        f"- Connector env counts: `{_format_count_breakdown(gap_connector_summary['connector_env_counts'])}`"
    )
    if gap_connector_summary["connector_case_ids"]:
        for connector_type in sorted(gap_connector_summary["connector_case_ids"]):
            lines.append(
                f"- `{connector_type}` cases: `{', '.join(gap_connector_summary['connector_case_ids'][connector_type])}`"
            )
    else:
        lines.append("- Connector case ids: `none`")
    if gap_connector_summary["connector_action_codes"]:
        for connector_type in sorted(gap_connector_summary["connector_action_codes"]):
            lines.append(
                f"- `{connector_type}` actions: `{', '.join(gap_connector_summary['connector_action_codes'][connector_type])}`"
            )
    else:
        lines.append("- Connector action codes: `none`")
    if gap_connector_summary["connector_env_names"]:
        for connector_type in sorted(gap_connector_summary["connector_env_names"]):
            lines.append(
                f"- `{connector_type}` envs: `{', '.join(gap_connector_summary['connector_env_names'][connector_type])}`"
            )
    else:
        lines.append("- Connector env names: `none`")

    lines.append("")
    lines.append("## Env routing")
    lines.append("")
    lines.append(f"- Total mapped envs: `{gap_env_summary['env_total_count']}`")
    lines.append(
        f"- Tier env counts: `{_format_count_breakdown(gap_env_summary['tier_env_counts'])}`"
    )
    lines.append(
        f"- Shared envs: `{', '.join(gap_env_summary['shared_env_names']) or 'none'}`"
    )
    if gap_env_summary["env_case_ids"]:
        for env_name in sorted(gap_env_summary["env_case_ids"]):
            lines.append(
                f"- `{env_name}` cases: `{', '.join(gap_env_summary['env_case_ids'][env_name])}`"
            )
    else:
        lines.append("- Env case ids: `none`")
    if gap_env_summary["env_action_codes"]:
        for env_name in sorted(gap_env_summary["env_action_codes"]):
            lines.append(
                f"- `{env_name}` actions: `{', '.join(gap_env_summary['env_action_codes'][env_name])}`"
            )
    else:
        lines.append("- Env action codes: `none`")
    if gap_env_summary["env_connector_types"]:
        for env_name in sorted(gap_env_summary["env_connector_types"]):
            lines.append(
                f"- `{env_name}` connectors: `{', '.join(gap_env_summary['env_connector_types'][env_name])}`"
            )
    else:
        lines.append("- Env connector types: `none`")
    if gap_env_summary["env_tiers"]:
        for env_name in sorted(gap_env_summary["env_tiers"]):
            lines.append(
                f"- `{env_name}` tiers: `{', '.join(gap_env_summary['env_tiers'][env_name])}`"
            )
    else:
        lines.append("- Env tiers: `none`")

    lines.append("")
    lines.append("## Env resolution")
    lines.append("")
    lines.append(
        f"- Resolver-supported envs: `{gap_env_resolution_summary['resolver_supported_count']}`"
    )
    lines.append(f"- Manual-only envs: `{gap_env_resolution_summary['manual_only_count']}`")
    lines.append(
        f"- Group env counts: `{_format_count_breakdown(gap_env_resolution_summary['group_env_counts'])}`"
    )
    lines.append(
        f"- Manual-only env names: `{', '.join(gap_env_resolution_summary['manual_only_env_names']) or 'none'}`"
    )
    if gap_env_resolution_summary["env_candidate_names"]:
        for env_name in sorted(gap_env_resolution_summary["env_candidate_names"]):
            lines.append(
                f"- `{env_name}` candidates: `{', '.join(gap_env_resolution_summary['env_candidate_names'][env_name])}`"
            )
    else:
        lines.append("- Env candidate names: `none`")
    if gap_env_resolution_summary["env_group_names"]:
        for env_name in sorted(gap_env_resolution_summary["env_group_names"]):
            lines.append(
                f"- `{env_name}` group: `{gap_env_resolution_summary['env_group_names'][env_name]}`"
            )
    else:
        lines.append("- Env groups: `none`")

    lines.append("")
    lines.append("## Env template coverage")
    lines.append("")
    lines.append(f"- Gap env total: `{gap_env_template_summary['gap_env_total_count']}`")
    lines.append(
        "- All templates cover all current gap envs: "
        f"`{'yes' if gap_env_template_summary['all_templates_cover_all_gap_envs'] else 'no'}`"
    )
    if gap_env_template_summary["template_paths"]:
        for template_name in sorted(gap_env_template_summary["template_paths"]):
            documented_count = gap_env_template_summary["template_documented_counts"][
                template_name
            ]
            missing_names = gap_env_template_summary["template_missing_env_names"][
                template_name
            ]
            lines.append(
                f"- `{template_name}` (`{gap_env_template_summary['template_paths'][template_name]}`): "
                f"`{documented_count}/{gap_env_template_summary['gap_env_total_count']}` documented, "
                f"missing `{', '.join(missing_names) or 'none'}`"
            )
    else:
        lines.append("- Template coverage: `none`")

    return "\n".join(lines)


def write_go_live_verify_markdown_report(
    summary: dict[str, Any],
    *,
    output_path: Path = DEFAULT_REPORT_OUTPUT,
) -> None:
    rendered = render_go_live_verify_markdown_report(summary)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered + "\n", encoding="utf-8")


def render_go_live_verify_scorecard_section(summary: dict[str, Any]) -> str:
    generated_date = str(summary.get("generated_at", ""))[:10]
    matrix_summary = summary["matrix_summary"]
    completed_steps = list(summary["completed_steps"])
    failed_steps = list(summary["failed_steps"])
    planned_steps = list(summary["planned_steps"])
    options = summary["options"]
    static_operational_gaps = list(summary.get("static_operational_gaps", []))
    live_connectivity_skips = list(summary.get("live_connectivity_skips", []))
    operational_gaps = list(summary.get("operational_gaps", []))
    next_actions = list(summary.get("next_actions", []))
    computed_gap_action_summary = build_gap_action_summary(
        list(operational_gaps),
        list(next_actions),
    )
    computed_gap_connector_summary = build_gap_connector_summary(
        list(operational_gaps),
        list(next_actions),
    )
    computed_gap_env_summary = build_gap_env_summary(
        list(operational_gaps),
        list(next_actions),
    )
    computed_gap_env_resolution_summary = build_gap_env_resolution_summary(
        computed_gap_env_summary
    )
    computed_gap_env_template_summary = build_gap_env_template_summary(
        computed_gap_env_summary
    )
    computed_gap_source_summary = build_gap_source_summary(
        list(static_operational_gaps),
        list(live_connectivity_skips),
        list(operational_gaps),
    )
    gap_source_summary = {
        **computed_gap_source_summary,
        **(summary.get("gap_source_summary") or {}),
    }
    gap_action_summary = {
        **computed_gap_action_summary,
        **(summary.get("gap_action_summary") or {}),
    }
    gap_connector_summary = {
        **computed_gap_connector_summary,
        **(summary.get("gap_connector_summary") or {}),
    }
    gap_env_summary = {
        **computed_gap_env_summary,
        **(summary.get("gap_env_summary") or {}),
    }
    gap_env_resolution_summary = {
        **computed_gap_env_resolution_summary,
        **(summary.get("gap_env_resolution_summary") or {}),
    }
    gap_env_template_summary = {
        **computed_gap_env_template_summary,
        **(summary.get("gap_env_template_summary") or {}),
    }
    duration_fragments = ", ".join(
        f"{item['name']} {float(item['duration_s']):.2f}s" for item in summary["step_results"]
    ) or "none"
    verifier_status = "Green"
    if failed_steps or summary["requirement_failures"]:
        verifier_status = "Red"
    static_gap_status = "Green" if not static_operational_gaps else "Amber"
    live_skip_status = "Green" if not live_connectivity_skips else "Amber"
    operational_gap_status = "Green" if not operational_gaps else "Amber"
    operational_gap_counts: dict[str, int] = {}
    for gap in operational_gaps:
        tier = str(gap.get("tier", "unknown"))
        operational_gap_counts[tier] = operational_gap_counts.get(tier, 0) + 1
    if operational_gaps:
        operational_gap_summary = ", ".join(
            f"{tier} {count}" for tier, count in sorted(operational_gap_counts.items())
        )
        operational_gap_current = (
            f"{len(operational_gaps)} cases outside repo-owned proof: {operational_gap_summary}"
        )
    else:
        operational_gap_current = "none"

    canonical_mode = []
    if not summary["filters"]["tiers"] and not summary["filters"]["connectors"]:
        canonical_mode.append("unfiltered")
    else:
        canonical_mode.append("filtered")
    if not options["strict"]:
        canonical_mode.append("non-strict")
    else:
        canonical_mode.append("strict")
    if options["include_full_real"]:
        canonical_mode.append("includes full_real")
    else:
        canonical_mode.append("excludes full_real")
    if options["include_pytest"]:
        canonical_mode.append("includes pytest")
    else:
        canonical_mode.append("excludes pytest")
    env_template_status = (
        "Green" if gap_env_template_summary["all_templates_cover_all_gap_envs"] else "Amber"
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
    full_real_summary = (
        json.loads(GO_LIVE_FULL_REAL_SUMMARY_PATH.read_text(encoding="utf-8"))
        if GO_LIVE_FULL_REAL_SUMMARY_PATH.exists()
        else None
    )
    if full_real_summary is None:
        full_real_current = "artifact missing"
        full_real_status = "Red"
    elif str(full_real_summary.get("details", {}).get("status", "complete")) == "complete":
        full_real_current = (
            f"{int(full_real_summary['passed'])}/{int(full_real_summary['total'])} suites passed; "
            f"live API-facing {int(full_real_summary['details'].get('live_suite_count', 0))}, "
            f"local benchmark/regression {int(full_real_summary['details'].get('local_suite_count', 0))}, "
            f"top-level verifier/bundle/A-Z {int(full_real_summary['details'].get('top_level_suite_count', 0))}"
        )
        full_real_status = "Green" if int(full_real_summary["failed"]) == 0 else "Red"
    else:
        full_real_current = (
            f"{int(full_real_summary['passed'])}/"
            f"{int(full_real_summary['details'].get('expected_suite_count', full_real_summary['total']))} "
            "suites passed so far; "
            f"completed {int(full_real_summary['details'].get('completed_suite_count', full_real_summary['total']))}/"
            f"{int(full_real_summary['details'].get('expected_suite_count', full_real_summary['total']))}"
        )
        full_real_status = "Red"

    lines = [
        f"## Go-live verifier ({generated_date})",
        "",
        "This is the top-level repo-owned operator proof from `tests/go_live_verify.py`. It tracks the serial go-live path separately from the dedicated LLM rollout artifacts.",
        "",
        "| Area | Current | Evidence | Status |",
        "| --- | --- | --- | --- |",
        (
            "| Serial verifier summary | "
            f"{matrix_summary['configured_cases']}/{matrix_summary['total_cases']} configured, "
            f"{matrix_summary['behavior_ready_cases']}/{matrix_summary['total_cases']} behavior-ready, "
            f"completed steps {_join_step_names(completed_steps)}, "
            f"{len(failed_steps)} failed steps | "
            "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
            f"`tests/go_live_verify.py`, `tests/test_go_live_verify.py` | {verifier_status} |"
        ),
        (
            "| Full real suite | "
            f"{full_real_current} | "
            "`build/go_live_full_real_summary.json`, `tests/integration/test_go_live_full_real.py` | "
            f"{full_real_status} |"
        ),
        (
            "| Planned serial steps | "
            f"{_join_step_names([step['name'] for step in planned_steps])} | "
            "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
            "`tests/integration/GO_LIVE_VALIDATION.md` | Green |"
        ),
        (
            "| Latest serial durations | "
            f"{duration_fragments} | "
            f"`build/go_live_verify_summary.json`, `build/go_live_verify_report.md` | {verifier_status} |"
        ),
        (
            "| Canonical verifier mode | "
            f"{', '.join(canonical_mode)} | "
            "`build/go_live_verify_summary.json`, `Makefile`, "
            "`tests/integration/GO_LIVE_VALIDATION.md` | Green |"
        ),
        (
            "| Static matrix operational gaps | "
            f"{gap_source_summary['static_gap_count']} cases from the current static matrix status before live connectivity overrides | "
            "`build/go_live_verify_summary.json`, `tests/go_live_matrix_status.py` | "
            f"{static_gap_status} |"
        ),
        (
            "| Live connectivity skips | "
            f"{gap_source_summary['live_skip_count']} skips captured from the latest connectivity run and merged into operational gaps | "
            "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
            "`tests/integration/test_go_live_connectivity_real.py` | "
            f"{live_skip_status} |"
        ),
        (
            "| Gap source breakdown | "
            f"static tiers {_format_count_breakdown(gap_source_summary['static_gap_counts_by_tier'])}; "
            f"live tiers {_format_count_breakdown(gap_source_summary['live_skip_counts_by_tier'])}; "
            f"merged sources {_format_count_breakdown(gap_source_summary['merged_gap_counts_by_source'])} | "
            "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
            "`tests/go_live_verify.py` | "
            f"{operational_gap_status} |"
        ),
        (
            "| Gap connector breakdown | "
            f"merged connectors {_format_count_breakdown(gap_source_summary['merged_gap_counts_by_connector_type'])} | "
            "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
            "`tests/go_live_verify.py` | "
            f"{operational_gap_status} |"
        ),
        (
            "| Outstanding operational gaps | "
            f"{operational_gap_current} | "
            "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
            "`tests/go_live_matrix_status.py` | "
            f"{operational_gap_status} |"
        ),
        (
            "| Operator next actions | "
            f"{len(next_actions)} action groups ready from current operational gaps | "
            "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
            f"`tests/go_live_verify.py` | {operational_gap_status} |"
        ),
        (
            "| Gap action routing | "
            f"{gap_action_summary['mapped_case_count']}/{gap_source_summary['merged_gap_count']} cases mapped; "
            f"actions {_format_count_breakdown(gap_action_summary['action_case_counts'])}; "
            f"envs {_format_count_breakdown(gap_action_summary['action_env_counts'])}; "
            f"connectors {_format_count_breakdown(gap_action_summary['action_connector_counts'])}; "
            f"terminal {', '.join(gap_action_summary['terminal_action_codes']) or 'none'}; "
            f"unmapped {', '.join(gap_action_summary['unmapped_case_ids']) or 'none'} | "
            "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
            "`tests/go_live_verify.py` | "
            f"{operational_gap_status} |"
        ),
        (
            "| Gap connector routing | "
            f"cases {_format_count_breakdown(gap_connector_summary['connector_case_counts'])}; "
            f"envs {_format_count_breakdown(gap_connector_summary['connector_env_counts'])} | "
            "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
            "`tests/go_live_verify.py` | "
            f"{operational_gap_status} |"
        ),
        (
            "| Gap env routing | "
            f"{gap_env_summary['env_total_count']} envs mapped; "
            f"tiers {_format_count_breakdown(gap_env_summary['tier_env_counts'])}; "
            f"shared {', '.join(gap_env_summary['shared_env_names']) or 'none'} | "
            "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
            "`tests/go_live_verify.py` | "
            f"{operational_gap_status} |"
        ),
        (
            "| Gap env resolution | "
            f"resolver-supported {gap_env_resolution_summary['resolver_supported_count']}; "
            f"manual-only {gap_env_resolution_summary['manual_only_count']}; "
            f"groups {_format_count_breakdown(gap_env_resolution_summary['group_env_counts'])}; "
            f"manual {', '.join(gap_env_resolution_summary['manual_only_env_names']) or 'none'} | "
            "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
            "`tests/go_live_verify.py`, `tests/go_live_secret_resolver.py` | "
            f"{operational_gap_status} |"
        ),
        (
            "| Gap env templates | "
            f"{env_template_current} | "
            "`build/go_live_verify_summary.json`, `build/go_live_verify_report.md`, "
            "`.env.example`, `tests/integration/go_live_validation.env.example`, "
            "`tests/go_live_verify.py` | "
            f"{env_template_status} |"
        ),
        "",
    ]
    return "\n".join(lines)


def sync_go_live_verify_scorecard(
    summary: dict[str, Any],
    *,
    scorecard_path: Path = SCORECARD_PATH,
) -> None:
    text = scorecard_path.read_text(encoding="utf-8")
    start_marker = "## Go-live verifier ("
    end_marker = "\n## LLM rollout proof ("
    replacement = render_go_live_verify_scorecard_section(summary)

    start_index = text.find(start_marker)
    end_index = text.find(end_marker)
    if end_index == -1:
        raise ValueError("scorecard LLM rollout section marker not found")
    if start_index == -1:
        updated = f"{text[:end_index]}{replacement}{text[end_index:]}"
    else:
        updated = f"{text[:start_index]}{replacement}{text[end_index + 1:]}"
    scorecard_path.write_text(updated, encoding="utf-8")


def should_sync_go_live_verify_scorecard(
    *,
    output_path: Path,
    selected_tiers: tuple[str, ...] | None,
    selected_connectors: tuple[str, ...] | None,
    include_full_real: bool,
    include_pytest: bool,
    require_all_configured: bool,
    require_all_behavior_ready: bool,
    strict: bool,
) -> bool:
    normalized_output = Path(output_path)
    if not normalized_output.is_absolute():
        normalized_output = (ROOT / normalized_output).resolve()
    return (
        normalized_output == DEFAULT_SUMMARY_OUTPUT.resolve()
        and not selected_tiers
        and not selected_connectors
        and include_full_real
        and not require_all_configured
        and not require_all_behavior_ready
        and not strict
    )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the full go-live proof serially.")
    parser.add_argument("--parallel-tasks", type=int, default=4)
    parser.add_argument("--mojo-workers", type=int, default=4)
    parser.add_argument("--mojo-timeout", type=int, default=30)
    parser.add_argument("--skip-full-real", action="store_true")
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument(
        "--tiers",
        help="Comma-separated tier filter for matrix status and connectivity validation.",
    )
    parser.add_argument(
        "--connector",
        help="Comma-separated connector filter for matrix status and connectivity validation.",
    )
    parser.add_argument("--require-all-configured", action="store_true")
    parser.add_argument("--require-all-behavior-ready", action="store_true")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_SUMMARY_OUTPUT,
        help=f"Write machine-readable verification summary to this JSON path (default: {DEFAULT_SUMMARY_OUTPUT})",
    )
    args = parser.parse_args(argv)

    selected_tiers = parse_selected_tiers(args.tiers)
    selected_connectors = parse_selected_connectors(args.connector)
    python_executable = resolve_python_executable()
    statuses = collect_matrix_status()
    if selected_tiers is not None:
        statuses = [status for status in statuses if status.tier in selected_tiers]
    statuses = filter_statuses_by_connectors(statuses, selected_connectors)
    require_all_configured = args.require_all_configured or args.strict
    require_all_behavior_ready = args.require_all_behavior_ready or args.strict
    requirement_failures = collect_requirement_failures(
        statuses,
        require_all_configured=require_all_configured,
        require_all_behavior_ready=require_all_behavior_ready,
    )
    matrix_payload = matrix_status_payload(statuses)
    matrix_payload["requirement_failures"] = [
        {
            "requirement": failure.requirement,
            "case_id": failure.case_id,
            "reason": failure.reason,
        }
        for failure in requirement_failures
    ]
    planned_steps = build_verification_steps(
        python_executable,
        parallel_tasks=args.parallel_tasks,
        mojo_workers=args.mojo_workers,
        mojo_timeout=args.mojo_timeout,
        include_full_real=not args.skip_full_real,
        include_pytest=not args.skip_pytest,
        tiers=selected_tiers,
        connectors=selected_connectors,
    )
    print(render_matrix_status(statuses))
    static_operational_gaps = summarize_operational_gaps(statuses)
    if requirement_failures:
        print(render_requirement_failures(requirement_failures))
        summary = summarize_verification(
            matrix_payload,
            planned_steps,
            [],
            matrix_payload["requirement_failures"],
        )
        summary.update(
            build_verification_metadata(
                python_executable=python_executable,
                output_path=args.output,
                selected_tiers=selected_tiers,
                selected_connectors=selected_connectors,
                include_full_real=not args.skip_full_real,
                include_pytest=not args.skip_pytest,
                require_all_configured=require_all_configured,
                require_all_behavior_ready=require_all_behavior_ready,
                strict=args.strict,
            )
        )
        summary["static_operational_gaps"] = static_operational_gaps
        summary["live_connectivity_skips"] = []
        summary["operational_gaps"] = static_operational_gaps
        summary["gap_source_summary"] = build_gap_source_summary(
            summary["static_operational_gaps"],
            summary["live_connectivity_skips"],
            summary["operational_gaps"],
        )
        summary["next_actions"] = build_go_live_next_actions(summary["operational_gaps"])
        summary["operational_gaps"] = annotate_operational_gaps_with_actions(
            summary["operational_gaps"],
            summary["next_actions"],
        )
        summary["gap_action_summary"] = build_gap_action_summary(
            summary["operational_gaps"],
            summary["next_actions"],
        )
        summary["gap_connector_summary"] = build_gap_connector_summary(
            summary["operational_gaps"],
            summary["next_actions"],
        )
        summary["gap_env_summary"] = build_gap_env_summary(
            summary["operational_gaps"],
            summary["next_actions"],
        )
        summary["gap_env_resolution_summary"] = build_gap_env_resolution_summary(
            summary["gap_env_summary"]
        )
        summary["gap_env_template_summary"] = build_gap_env_template_summary(
            summary["gap_env_summary"]
        )
        write_verification_summary(summary, output_path=args.output)
        if should_sync_go_live_verify_scorecard(
            output_path=args.output,
            selected_tiers=selected_tiers,
            selected_connectors=selected_connectors,
            include_full_real=not args.skip_full_real,
            include_pytest=not args.skip_pytest,
            require_all_configured=require_all_configured,
            require_all_behavior_ready=require_all_behavior_ready,
            strict=args.strict,
        ):
            write_go_live_verify_markdown_report(summary, output_path=DEFAULT_REPORT_OUTPUT)
            print(f"wrote verification report: {DEFAULT_REPORT_OUTPUT}")
            sync_go_live_verify_scorecard(summary)
            print(f"synced go-live scorecard: {SCORECARD_PATH}")
        print(f"wrote verification summary: {args.output}")
        raise SystemExit(1)

    results = run_verification_steps(planned_steps)
    summary = summarize_verification(
        matrix_payload,
        planned_steps,
        results,
        matrix_payload["requirement_failures"],
    )
    summary.update(
        build_verification_metadata(
            python_executable=python_executable,
            output_path=args.output,
            selected_tiers=selected_tiers,
            selected_connectors=selected_connectors,
            include_full_real=not args.skip_full_real,
            include_pytest=not args.skip_pytest,
            require_all_configured=require_all_configured,
            require_all_behavior_ready=require_all_behavior_ready,
            strict=args.strict,
        )
    )
    connectivity_result = next((result for result in results if result.name == "connectivity"), None)
    live_connectivity_skips = extract_live_connectivity_skips(
        connectivity_result.output if connectivity_result is not None else "",
        statuses,
    )
    summary["static_operational_gaps"] = static_operational_gaps
    summary["live_connectivity_skips"] = live_connectivity_skips
    summary["operational_gaps"] = merge_operational_gaps(
        static_operational_gaps,
        live_connectivity_skips,
    )
    summary["gap_source_summary"] = build_gap_source_summary(
        summary["static_operational_gaps"],
        summary["live_connectivity_skips"],
        summary["operational_gaps"],
    )
    summary["next_actions"] = build_go_live_next_actions(summary["operational_gaps"])
    summary["operational_gaps"] = annotate_operational_gaps_with_actions(
        summary["operational_gaps"],
        summary["next_actions"],
    )
    summary["gap_action_summary"] = build_gap_action_summary(
        summary["operational_gaps"],
        summary["next_actions"],
    )
    summary["gap_connector_summary"] = build_gap_connector_summary(
        summary["operational_gaps"],
        summary["next_actions"],
    )
    summary["gap_env_summary"] = build_gap_env_summary(
        summary["operational_gaps"],
        summary["next_actions"],
    )
    summary["gap_env_resolution_summary"] = build_gap_env_resolution_summary(
        summary["gap_env_summary"]
    )
    summary["gap_env_template_summary"] = build_gap_env_template_summary(
        summary["gap_env_summary"]
    )
    write_verification_summary(summary, output_path=args.output)
    if should_sync_go_live_verify_scorecard(
        output_path=args.output,
        selected_tiers=selected_tiers,
        selected_connectors=selected_connectors,
        include_full_real=not args.skip_full_real,
        include_pytest=not args.skip_pytest,
        require_all_configured=require_all_configured,
        require_all_behavior_ready=require_all_behavior_ready,
        strict=args.strict,
    ):
        write_go_live_verify_markdown_report(summary, output_path=DEFAULT_REPORT_OUTPUT)
        print(f"wrote verification report: {DEFAULT_REPORT_OUTPUT}")
        sync_go_live_verify_scorecard(summary)
        print(f"synced go-live scorecard: {SCORECARD_PATH}")

    print("\n=== verification summary ===")
    print(
        "configured "
        f"{summary['matrix_summary']['configured_cases']}/{summary['matrix_summary']['total_cases']} "
        "| behavior-ready "
        f"{summary['matrix_summary']['behavior_ready_cases']}/{summary['matrix_summary']['total_cases']}"
    )
    print(f"wrote verification summary: {args.output}")
    if summary["failed_steps"]:
        print(f"failed steps: {', '.join(summary['failed_steps'])}")
        raise SystemExit(1)
    print(f"completed steps: {', '.join(summary['completed_steps'])}")


if __name__ == "__main__":
    main()
