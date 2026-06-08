from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from typing import Any

from apps.api_server.services.connectors.tester import test_connector_real_detailed
from tests.go_live_secret_resolver import populate_go_live_test_env_from_keys_txt
from tests.integration.connector_validation_catalog import (
    ALL_CONNECTOR_VALIDATION_CASES,
    ConnectorValidationCase,
)

populate_go_live_test_env_from_keys_txt()


def _normalize_connector_type(raw_value: str) -> str:
    return str(raw_value).strip().lower().replace("-", "_")


def _select_probe_case(connector_type: str) -> ConnectorValidationCase:
    normalized = _normalize_connector_type(connector_type)
    candidates = [
        case
        for case in ALL_CONNECTOR_VALIDATION_CASES
        if case.connector_type == normalized and case.validation_mode == "connector_test_only"
    ]
    if len(candidates) == 1:
        return candidates[0]
    if not candidates:
        raise ValueError(f"No connector test probe case is defined for connector '{normalized}'.")
    raise ValueError(
        f"Expected exactly one connector test probe case for '{normalized}', "
        f"found {len(candidates)}."
    )


async def _evaluate_probe(connector_type: str) -> dict[str, Any]:
    case = _select_probe_case(connector_type)
    configured = case.is_configured()
    behavior_skip_reason = case.behavior_skip_reason()
    effective_validation_mode = case.effective_validation_mode()
    effective_behavior_mode = case.effective_behavior_mode()
    payload: dict[str, Any] = {
        "connector_type": case.connector_type,
        "case_id": case.case_id,
        "label": case.label,
        "tier": case.tier,
        "configured": configured,
        "skip_reason": case.skip_reason(),
        "behavior_ready": (
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
        "behavior_skip_reason": behavior_skip_reason,
        "probe": None,
    }
    if not payload["configured"]:
        return payload

    outcome = await test_connector_real_detailed(case.connector_type, case.build_connector_config())
    payload["probe"] = asdict(outcome)
    return payload


def _render_probe(payload: dict[str, Any]) -> str:
    lines = [
        f"Connector probe: {payload['connector_type']}",
        f"  case_id={payload['case_id']}",
        f"  configured={payload['configured']}",
        f"  behavior_ready={payload['behavior_ready']}",
    ]
    skip_reason = str(payload.get("skip_reason") or "").strip()
    if skip_reason:
        lines.append(f"  skip_reason={skip_reason}")
    behavior_skip_reason = str(payload.get("behavior_skip_reason") or "").strip()
    if behavior_skip_reason:
        lines.append(f"  behavior_skip_reason={behavior_skip_reason}")
    probe = payload.get("probe")
    if isinstance(probe, dict):
        lines.extend(
            [
                f"  probe_status={probe['status']}",
                f"  success={probe['success']}",
                f"  latency_ms={probe['latency_ms']}",
            ]
        )
        if probe.get("error_type"):
            lines.append(f"  error_type={probe['error_type']}")
        if probe.get("recoverable") is not None:
            lines.append(f"  recoverable={probe['recoverable']}")
        lines.append(f"  message={probe['message']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a focused live connector probe using the go-live credential wiring."
    )
    parser.add_argument(
        "--connector",
        required=True,
        help="Connector type to probe, for example clickhouse, snowflake, or bigquery.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the probe payload as JSON.",
    )
    args = parser.parse_args(argv)

    payload = asyncio.run(_evaluate_probe(args.connector))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(_render_probe(payload))

    probe = payload.get("probe")
    if not payload["configured"]:
        return 1
    if not isinstance(probe, dict):
        return 1
    return 0 if bool(probe.get("success")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
