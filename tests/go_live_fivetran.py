from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from tests.go_live_fivetran_inventory import (
    BASELINE_LOCK_PATH,
    INVENTORY_LOCK_PATH,
    SELECTION_LOCK_PATH,
    ensure_inventory_and_selection_locks_are_consistent,
    refresh_inventory_and_selection_locks,
)
from tests.go_live_fivetran_verify import (
    build_connector_manifest_view,
    build_empty_baseline_lock,
    evaluate_fivetran_wave,
    hydrate_manifest_connection_ids_from_live_account,
    inspect_live_fivetran_account,
    refresh_baseline_lock,
    render_fivetran_markdown_report,
    render_fivetran_status,
    sync_example_manifest_from_selection,
)


def _parse_connector_filter(raw_values: list[str]) -> tuple[str, ...] | None:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw_value in raw_values:
        for part in str(raw_value).split(","):
            connector_slug = part.strip()
            if not connector_slug or connector_slug in seen:
                continue
            seen.add(connector_slug)
            normalized.append(connector_slug)
    return tuple(normalized) if normalized else None


def _require_single_connector_slug(connector_slugs: tuple[str, ...] | None) -> str:
    if connector_slugs is None or len(connector_slugs) != 1:
        raise SystemExit("Exactly one connector slug is required for this command.")
    return connector_slugs[0]


def _allowed_prebaseline_blocker(destination: dict[str, object]) -> bool:
    if str(destination.get("state", "")).strip() != "blocked":
        return False
    destination_name = str(destination.get("destination_name", "")).strip()
    reasons = [
        str(reason).strip()
        for reason in destination.get("reasons", [])  # type: ignore[arg-type]
        if str(reason).strip()
    ]
    if not destination_name or not reasons:
        return False
    expected_reason = f"{destination_name} baseline entry is missing."
    return all(reason == expected_reason for reason in reasons)


def _strict_failure_messages(payload: dict[str, object]) -> list[str]:
    failures = list(payload.get("suite_failures", []))  # type: ignore[arg-type]
    summary = payload.get("summary", {})
    if isinstance(summary, dict):
        if int(summary.get("fail", 0) or 0) > 0:
            failures.append(f"{summary['fail']} connector(s) failed.")
        if int(summary.get("blocked", 0) or 0) > 0:
            failures.append(f"{summary['blocked']} connector(s) are blocked.")
    manifest_error = str(payload.get("manifest_error", "") or "").strip()
    if manifest_error:
        failures.append(f"manifest error: {manifest_error}")
    return failures


def _prebaseline_failure_messages(payload: dict[str, object]) -> list[str]:
    failures = list(payload.get("suite_failures", []))  # type: ignore[arg-type]
    manifest_error = str(payload.get("manifest_error", "") or "").strip()
    if manifest_error:
        failures.append(f"manifest error: {manifest_error}")
    summary = payload.get("summary", {})
    if isinstance(summary, dict) and int(summary.get("fail", 0) or 0) > 0:
        failures.append(f"{summary['fail']} connector(s) failed.")
    for connector in payload.get("connector_results", []):  # type: ignore[arg-type]
        connector_slug = str(connector.get("connector_slug", "")).strip()
        for destination in connector.get("destinations", []):
            if _allowed_prebaseline_blocker(destination):
                continue
            state = str(destination.get("state", "")).strip()
            if state == "pass":
                continue
            reasons = [
                str(reason).strip()
                for reason in destination.get("reasons", [])
                if str(reason).strip()
            ]
            reason_text = ", ".join(reasons) if reasons else "unknown pre-baseline blocker"
            failures.append(
                f"{connector_slug}/{destination.get('destination_name')} pre-baseline blocker: {reason_text}"
            )
    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fivetran validation-only go-live operator surface"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    refresh_inventory_parser = subparsers.add_parser(
        "refresh-inventory",
        help="Refresh the frozen Fivetran inventory and top-20 selection locks.",
    )
    refresh_inventory_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the refreshed lock summary as JSON.",
    )

    refresh_baseline_parser = subparsers.add_parser(
        "refresh-baseline",
        help="Refresh the frozen Fivetran warehouse baselines under the strict capture safeguards.",
    )
    refresh_baseline_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the refreshed baseline lock as JSON.",
    )
    refresh_baseline_parser.add_argument(
        "--connector",
        action="append",
        default=[],
        help="Restrict the baseline refresh to one or more connector slugs. Repeat or use comma-separated values.",
    )

    hydrate_manifest_parser = subparsers.add_parser(
        "hydrate-manifest",
        help="Hydrate placeholder Fivetran manifest connection IDs from the live account when matches are unambiguous.",
    )
    hydrate_manifest_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the hydration result as JSON.",
    )
    hydrate_manifest_parser.add_argument(
        "--connector",
        action="append",
        default=[],
        help="Restrict manifest hydration to one or more connector slugs. Repeat or use comma-separated values.",
    )

    account_parser = subparsers.add_parser(
        "account",
        help="Inspect live Fivetran destinations, connections, and connector match candidates.",
    )
    account_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the live account inspection as JSON.",
    )
    account_parser.add_argument(
        "--connector",
        action="append",
        default=[],
        help="Restrict candidate matching to one or more connector slugs. Repeat or use comma-separated values.",
    )

    connector_manifest_parser = subparsers.add_parser(
        "manifest-connector",
        help="Print the exact manifest entry and remaining placeholder fields for one connector.",
    )
    connector_manifest_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the manifest connector view as JSON.",
    )
    connector_manifest_parser.add_argument(
        "--connector",
        action="append",
        default=[],
        help="Exactly one connector slug. Repeat or use comma-separated values is not allowed here.",
    )

    status_parser = subparsers.add_parser(
        "status",
        help="Evaluate the current frozen Fivetran wave and print status without enforcing success.",
    )
    status_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the live status payload as JSON.",
    )
    status_parser.add_argument(
        "--connector",
        action="append",
        default=[],
        help="Restrict status evaluation to one or more connector slugs. Repeat or use comma-separated values.",
    )

    report_parser = subparsers.add_parser(
        "report",
        help="Render the frozen Fivetran wave as a Markdown report without enforcing success.",
    )
    report_parser.add_argument(
        "--output",
        type=Path,
        help="Optional file path to write the Markdown report to instead of stdout.",
    )
    report_parser.add_argument(
        "--connector",
        action="append",
        default=[],
        help="Restrict report rendering to one or more connector slugs. Repeat or use comma-separated values.",
    )

    verify_parser = subparsers.add_parser(
        "verify",
        help="Run the strict Fivetran wave verification and fail on any fail or blocked state.",
    )
    verify_parser.add_argument(
        "--json",
        action="store_true",
        help="Print the live verification payload as JSON.",
    )
    verify_parser.add_argument(
        "--connector",
        action="append",
        default=[],
        help="Restrict verification to one or more connector slugs. Repeat or use comma-separated values.",
    )
    verify_parser.add_argument(
        "--pre-baseline",
        action="store_true",
        help="Allow only missing-baseline blockers; all other blocked or failed states remain fatal.",
    )

    args = parser.parse_args(argv)
    connector_slugs = _parse_connector_filter(getattr(args, "connector", []))

    if args.command == "refresh-inventory":
        inventory_lock, selection_lock = refresh_inventory_and_selection_locks()
        sync_example_manifest_from_selection(selection_lock)
        if not BASELINE_LOCK_PATH.exists():
            BASELINE_LOCK_PATH.write_text(
                json.dumps(build_empty_baseline_lock(), indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        payload = {
            "inventory_path": str(INVENTORY_LOCK_PATH),
            "selection_path": str(SELECTION_LOCK_PATH),
            "baseline_path": str(BASELINE_LOCK_PATH),
            "inventory_version": inventory_lock["inventory_version"],
            "selection_version": selection_lock["selection_version"],
            "selected_count": len(selection_lock["selected_connectors"]),
        }
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(
                "Refreshed Fivetran inventory locks:\n"
                f"  inventory_version={payload['inventory_version']}\n"
                f"  selection_version={payload['selection_version']}\n"
                f"  selected_count={payload['selected_count']}"
            )
        return 0

    if args.command == "refresh-baseline":
        payload = refresh_baseline_lock(connector_slugs=connector_slugs)
        BASELINE_LOCK_PATH.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(
                "Refreshed Fivetran baseline lock:\n"
                f"  baseline_version={payload['baseline_version']}\n"
                f"  entries={len(payload['entries'])}"
            )
        return 0

    if args.command == "hydrate-manifest":
        payload = hydrate_manifest_connection_ids_from_live_account(
            connector_slugs=connector_slugs,
        )
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(
                "Hydrated Fivetran manifest:\n"
                f"  manifest_path={payload['manifest_path']}\n"
                f"  changed={payload['changed']}\n"
                f"  hydrated_paths={len(payload['hydrated_paths'])}\n"
                f"  unresolved_paths={len(payload['unresolved_paths'])}\n"
                f"  remaining_placeholder_fields={len(payload['remaining_placeholder_fields'])}"
            )
        return 0

    if args.command == "manifest-connector":
        connector_slug = _require_single_connector_slug(connector_slugs)
        payload = build_connector_manifest_view(connector_slug=connector_slug)
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(
                "Fivetran manifest connector entry:\n"
                f"  manifest_path={payload['manifest_path']}\n"
                f"  manifest_version={payload['manifest_version']}\n"
                f"  connector_slug={payload['connector_slug']}\n"
                f"  remaining_placeholder_fields={len(payload['remaining_placeholder_fields'])}\n"
                f"  next_commands={len(payload['next_commands'])}\n"
            )
            print(json.dumps(payload["manifest_entry"], indent=2, sort_keys=True))
        return 0

    if args.command == "account":
        payload = inspect_live_fivetran_account(connector_slugs=connector_slugs)
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            summary = payload.get("summary", {})
            print(
                "Fivetran live account inspection:\n"
                f"  destinations={summary.get('destinations', 0)}\n"
                f"  connections={summary.get('connections', 0)}\n"
                f"  matched_pairs={summary.get('matched_pairs', 0)}\n"
                f"  matched_candidates={summary.get('matched_candidates', 0)}\n"
                f"  unmatched_candidates={summary.get('unmatched_candidates', 0)}"
            )
        return 0

    if args.command == "status":
        payload = evaluate_fivetran_wave(
            run_behavior_validation=True,
            connector_slugs=connector_slugs,
        )
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(render_fivetran_status(payload))
        return 0

    if args.command == "report":
        _inventory_lock, selection_lock = ensure_inventory_and_selection_locks_are_consistent()
        payload = evaluate_fivetran_wave(
            run_behavior_validation=True,
            connector_slugs=connector_slugs,
        )
        rendered = render_fivetran_markdown_report(payload, selection_lock=selection_lock)
        output_path: Path | None = args.output
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(rendered + "\n", encoding="utf-8")
        else:
            print(rendered)
        return 0

    if args.command == "verify":
        payload = evaluate_fivetran_wave(
            run_behavior_validation=True,
            connector_slugs=connector_slugs,
        )
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(render_fivetran_status(payload))
        failures = (
            _prebaseline_failure_messages(payload)
            if args.pre_baseline
            else _strict_failure_messages(payload)
        )
        return 1 if failures else 0

    raise AssertionError(f"Unhandled command {args.command}")


if __name__ == "__main__":
    sys.exit(main())
