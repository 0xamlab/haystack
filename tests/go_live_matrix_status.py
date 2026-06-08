from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any

from tests.integration.connector_validation_catalog import (
    ALL_CONNECTOR_VALIDATION_CASES,
    ConnectorValidationCase,
)

VALIDATION_TIERS = (
    "public_no_auth",
    "credentialed_example",
    "customer_credentials_required",
)

VALIDATION_CONNECTORS = tuple(
    sorted({case.connector_type for case in ALL_CONNECTOR_VALIDATION_CASES})
)

_REPLACEMENT_CASES = {
    "public_s3_source_registration": "customer_s3_source_registration",
    "public_gcs_source_registration": "customer_gcs_source_registration",
    "public_azure_blob_source_registration": "customer_azure_blob_source_registration",
}


@dataclass(frozen=True)
class MatrixCaseStatus:
    case_id: str
    label: str
    tier: str
    connector_type: str
    validation_mode: str
    effective_validation_mode: str
    behavior_mode: str
    effective_behavior_mode: str
    configured: bool
    behavior_ready: bool
    behavior_upgrade_active: bool
    skip_reason: str | None
    behavior_skip_reason: str | None


@dataclass(frozen=True)
class MatrixRequirementFailure:
    requirement: str
    case_id: str
    reason: str


def parse_selected_tiers(raw: str | None) -> tuple[str, ...] | None:
    if raw is None:
        return None
    selected = tuple(tier.strip() for tier in raw.split(",") if tier.strip())
    unknown = sorted(set(selected) - set(VALIDATION_TIERS))
    if unknown:
        raise ValueError(
            f"Unknown validation tiers: {', '.join(unknown)}. "
            f"Expected one of: {', '.join(VALIDATION_TIERS)}"
        )
    return selected or None


def parse_selected_connectors(raw: str | None) -> tuple[str, ...] | None:
    if raw is None:
        return None
    selected = tuple(connector.strip() for connector in raw.split(",") if connector.strip())
    unknown = sorted(set(selected) - set(VALIDATION_CONNECTORS))
    if unknown:
        raise ValueError(
            f"Unknown connector types: {', '.join(unknown)}. "
            f"Expected one of: {', '.join(VALIDATION_CONNECTORS)}"
        )
    return selected or None


def filter_statuses_by_connectors(
    statuses: list[MatrixCaseStatus],
    selected_connectors: tuple[str, ...] | None,
) -> list[MatrixCaseStatus]:
    if selected_connectors is None:
        return list(statuses)
    return [status for status in statuses if status.connector_type in selected_connectors]


def collect_matrix_status(
    cases: tuple[ConnectorValidationCase, ...] = ALL_CONNECTOR_VALIDATION_CASES,
) -> list[MatrixCaseStatus]:
    statuses: list[MatrixCaseStatus] = []
    for case in cases:
        effective_validation_mode = case.effective_validation_mode()
        effective_behavior_mode = case.effective_behavior_mode()
        configured = case.is_configured()
        behavior_skip_reason = case.behavior_skip_reason()
        statuses.append(
            MatrixCaseStatus(
                case_id=case.case_id,
                label=case.label,
                tier=case.tier,
                connector_type=case.connector_type,
                validation_mode=case.validation_mode,
                effective_validation_mode=effective_validation_mode,
                behavior_mode=case.behavior_mode,
                effective_behavior_mode=effective_behavior_mode,
                configured=configured,
                behavior_ready=(
                    configured
                    and (
                        (
                            effective_validation_mode == "register_and_exact_query"
                            and effective_behavior_mode != "connector_test_only"
                        )
                        or (
                            effective_validation_mode == "connector_test_only"
                            and behavior_skip_reason is None
                        )
                    )
                ),
                behavior_upgrade_active=case.supports_behavior_validation(),
                skip_reason=case.skip_reason(),
                behavior_skip_reason=behavior_skip_reason,
            )
        )
    return statuses


def collect_requirement_failures(
    statuses: list[MatrixCaseStatus],
    *,
    require_all_configured: bool = False,
    require_all_behavior_ready: bool = False,
) -> list[MatrixRequirementFailure]:
    status_index = {status.case_id: status for status in statuses}
    failures: list[MatrixRequirementFailure] = []
    if require_all_configured:
        for status in statuses:
            if status.configured:
                continue
            replacement_case_id = _REPLACEMENT_CASES.get(status.case_id)
            replacement_status = (
                status_index.get(replacement_case_id) if replacement_case_id is not None else None
            )
            if replacement_status is not None and replacement_status.configured:
                continue
            failures.append(
                MatrixRequirementFailure(
                    requirement="all_configured",
                    case_id=status.case_id,
                    reason=status.skip_reason or "case is not configured",
                )
            )
    if require_all_behavior_ready:
        for status in statuses:
            if status.behavior_ready:
                continue
            if (
                status.configured
                and status.effective_validation_mode == "connector_test_only"
                and status.behavior_skip_reason is None
            ):
                continue
            replacement_case_id = _REPLACEMENT_CASES.get(status.case_id)
            replacement_status = (
                status_index.get(replacement_case_id) if replacement_case_id is not None else None
            )
            if replacement_status is not None and replacement_status.behavior_ready:
                continue
            failures.append(
                MatrixRequirementFailure(
                    requirement="all_behavior_ready",
                    case_id=status.case_id,
                    reason=(
                        status.behavior_skip_reason
                        or status.skip_reason
                        or "case is not behavior-ready"
                    ),
                )
            )
    return failures


def summarize_matrix_status(statuses: list[MatrixCaseStatus]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "total_cases": len(statuses),
        "configured_cases": sum(1 for status in statuses if status.configured),
        "behavior_ready_cases": sum(1 for status in statuses if status.behavior_ready),
        "tiers": {},
    }
    for tier in VALIDATION_TIERS:
        tier_statuses = [status for status in statuses if status.tier == tier]
        summary["tiers"][tier] = {
            "total": len(tier_statuses),
            "configured": sum(1 for status in tier_statuses if status.configured),
            "behavior_ready": sum(1 for status in tier_statuses if status.behavior_ready),
        }
    return summary


def summarize_operational_gaps(statuses: list[MatrixCaseStatus]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for status in statuses:
        if status.configured and status.behavior_ready:
            continue
        if not status.configured:
            gap_type = "not_configured"
            reason = status.skip_reason or "case is not configured"
        else:
            gap_type = "not_behavior_ready"
            reason = (
                status.behavior_skip_reason
                or status.skip_reason
                or "case is not behavior-ready"
            )
        gaps.append(
            {
                "case_id": status.case_id,
                "label": status.label,
                "tier": status.tier,
                "connector_type": status.connector_type,
                "gap_type": gap_type,
                "reason": reason,
            }
        )
    return sorted(gaps, key=lambda item: (str(item["tier"]), str(item["case_id"])))


def matrix_status_payload(statuses: list[MatrixCaseStatus]) -> dict[str, Any]:
    return {
        "summary": summarize_matrix_status(statuses),
        "cases": [asdict(status) for status in statuses],
        "operational_gaps": summarize_operational_gaps(statuses),
        "requirement_failures": [],
    }


def render_matrix_status(statuses: list[MatrixCaseStatus]) -> str:
    summary = summarize_matrix_status(statuses)
    lines = [
        "Connector validation matrix status",
        (
            f"Configured {summary['configured_cases']}/{summary['total_cases']} "
            f"| behavior-ready {summary['behavior_ready_cases']}/{summary['total_cases']}"
        ),
    ]
    for tier, tier_summary in summary["tiers"].items():
        lines.append(
            f"- {tier}: configured {tier_summary['configured']}/{tier_summary['total']}, "
            f"behavior-ready {tier_summary['behavior_ready']}/{tier_summary['total']}"
        )
    lines.append("")
    for status in statuses:
        readiness = "configured" if status.configured else "skipped"
        behavior = (
            f"behavior={status.effective_validation_mode}"
            if status.behavior_ready
            else f"behavior={status.validation_mode}"
        )
        lines.append(
            f"{status.case_id} | {status.tier} | {status.connector_type} | {readiness} | {behavior}"
        )
        if status.skip_reason:
            lines.append(f"  skip: {status.skip_reason}")
        elif status.behavior_skip_reason:
            lines.append(f"  behavior: {status.behavior_skip_reason}")
    return "\n".join(lines)


def render_requirement_failures(failures: list[MatrixRequirementFailure]) -> str:
    if not failures:
        return ""
    lines = ["", "Matrix requirements not satisfied"]
    for failure in failures:
        lines.append(f"- {failure.requirement}: {failure.case_id} -> {failure.reason}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Render current go-live matrix readiness.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    parser.add_argument(
        "--tiers",
        help="Comma-separated tier filter. Example: credentialed_example or public_no_auth,credentialed_example",
    )
    parser.add_argument(
        "--connector",
        help="Comma-separated connector filter. Example: clickhouse or clickhouse,snowflake",
    )
    parser.add_argument(
        "--require-all-configured",
        action="store_true",
        help="Exit non-zero unless every matrix case is configured.",
    )
    parser.add_argument(
        "--require-all-behavior-ready",
        action="store_true",
        help="Exit non-zero unless every matrix case is behavior-ready.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Require every matrix case to be configured and behavior-ready.",
    )
    args = parser.parse_args(argv)

    selected_tiers = parse_selected_tiers(args.tiers)
    selected_connectors = parse_selected_connectors(args.connector)
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
    payload = matrix_status_payload(statuses)
    payload["requirement_failures"] = [asdict(failure) for failure in requirement_failures]
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
        if requirement_failures:
            raise SystemExit(1)
        return
    print(render_matrix_status(statuses))
    if requirement_failures:
        print(render_requirement_failures(requirement_failures))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
