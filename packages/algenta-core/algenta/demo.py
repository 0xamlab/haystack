"""Interactive deterministic runtime demo for Algenta."""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from algenta.branding import runtime_banner
from algenta.runtime import (
    ImportPreview,
    QueryFilterCondition,
    QueryFilterSpec,
    QueryOutput,
    ResolveOutput,
    Runtime,
    VerifyOutput,
)

_DEMO_DATA = [
    {
        "product_line": "Electronics",
        "revenue": 42193221,
        "region": "United States",
        "channel": "Online",
        "status": "closed",
    },
    {
        "product_line": "Apparel",
        "revenue": 28114992,
        "region": "United States",
        "channel": "Retail",
        "status": "closed",
    },
    {
        "product_line": "Home",
        "revenue": 19852111,
        "region": "United States",
        "channel": "Retail",
        "status": "open",
    },
    {
        "product_line": "Electronics",
        "revenue": 1204000,
        "region": "Canada",
        "channel": "Online",
        "status": "closed",
    },
    {
        "product_line": "Apparel",
        "revenue": 814000,
        "region": "Canada",
        "channel": "Partner",
        "status": "closed",
    },
    {
        "product_line": "Accessories",
        "revenue": 2800000,
        "region": "United Kingdom",
        "channel": "Online",
        "status": "closed",
    },
]
_DEMO_SOURCE_NAME = "demo_orders"


@dataclass(frozen=True)
class DemoScenario:
    key: str
    title: str
    summary: str
    request: dict[str, Any]
    expect_query: bool = True
    takeaway_template: str | None = None


_SCENARIOS = (
    DemoScenario(
        key="product_line",
        title="Executive leaderboard: top product lines",
        summary="Ranks the strongest product lines instead of dumping the whole table.",
        request={
            "source_name": _DEMO_SOURCE_NAME,
            "metric": "revenue",
            "group_by": "product_line",
            "limit": 2,
        },
        takeaway_template="Top line: {group} at {metric}.",
    ),
    DemoScenario(
        key="region",
        title="Executive pulse: regional revenue concentration",
        summary="Shows where revenue is concentrated across the operating footprint.",
        request={
            "source_name": _DEMO_SOURCE_NAME,
            "metric": "revenue",
            "group_by": "region",
        },
        takeaway_template="Largest region: {group} at {metric}.",
    ),
    DemoScenario(
        key="canada_filter",
        title="Recovery drilldown: Canada-only product mix",
        summary="Demonstrates governed filters on a realistic country drilldown.",
        request={
            "source_name": _DEMO_SOURCE_NAME,
            "metric": "revenue",
            "group_by": "product_line",
            "filter": QueryFilterSpec(
                conditions=[
                    QueryFilterCondition(
                        dimension_hint="region",
                        op="eq",
                        value="Canada",
                    )
                ]
            ),
        },
        takeaway_template="Canada leader: {group} at {metric}.",
    ),
    DemoScenario(
        key="guardrail",
        title="Guardrail: reject an unresolvable metric",
        summary="Shows how the runtime blocks a request before it becomes a bad query.",
        request={
            "source_name": _DEMO_SOURCE_NAME,
            "metric": "gross_margin",
            "group_by": "product_line",
        },
        expect_query=False,
    ),
)
_SCENARIOS_BY_KEY = {scenario.key: scenario for scenario in _SCENARIOS}
_MENU_CHOICES = {
    "1": "product_line",
    "2": "region",
    "3": "canada_filter",
    "4": "guardrail",
    "a": "all",
    "all": "all",
    "n": "recipes",
    "r": "recipes",
    "recipes": "recipes",
    "q": "quit",
    "quit": "quit",
}
_MENU_SPLIT_RE = re.compile(r"[\s,]+")


def _render_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no rows)"

    columns = list(rows[0].keys())
    widths = {
        column: max(len(column), *(len(str(row.get(column, ""))) for row in rows))
        for column in columns
    }
    header = "  " + "  ".join(column.upper().ljust(widths[column]) for column in columns)
    divider = "  " + "  ".join("─" * widths[column] for column in columns)
    body = [
        "  " + "  ".join(str(row.get(column, "")).ljust(widths[column]) for column in columns)
        for row in rows
    ]
    return "\n".join([header, divider, *body])


def _render_result(result: QueryOutput) -> str:
    if result.result_type != "table" or not isinstance(result.result, list):
        return str(result.result)
    return _render_table(result.result)


def _emit(message: str = "") -> None:
    sys.stdout.write(f"{message}\n")
    sys.stdout.flush()


def _emit_section(title: str) -> None:
    _emit(title)
    _emit(f"  {'-' * (len(title) - 2)}")


def _emit_key_values(pairs: list[tuple[str, str]]) -> None:
    for key, value in pairs:
        _emit(f"  {key}={value}")


def _emit_json_block(label: str, payload: dict[str, Any]) -> None:
    _emit(f"  {label}")
    rendered = json.dumps(_jsonable(payload), indent=2)
    for line in rendered.splitlines():
        _emit(f"    {line}")


def _jsonable(value: Any) -> Any:
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _jsonable(value.to_dict())
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


def _source_fields(source_schema: dict[str, Any] | None) -> list[str]:
    if not isinstance(source_schema, dict):
        return []
    raw_fields = source_schema.get("fields")
    if not isinstance(raw_fields, list):
        return []
    return [str(field) for field in raw_fields if str(field).strip()]


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="algenta demo",
        description="Interactive deterministic Algenta runtime demo.",
    )
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--scenario",
        choices=sorted(_SCENARIOS_BY_KEY),
        help="Run one named demo scenario and exit.",
    )
    mode_group.add_argument(
        "--all",
        action="store_true",
        help="Run every demo scenario sequentially and exit.",
    )
    mode_group.add_argument(
        "--list",
        action="store_true",
        help="List available demo scenarios and exit.",
    )
    interactive_group = parser.add_mutually_exclusive_group()
    interactive_group.add_argument(
        "--interactive",
        action="store_true",
        help="Force the interactive terminal scenario picker.",
    )
    interactive_group.add_argument(
        "--no-interactive",
        action="store_true",
        help="Disable the interactive picker even in a TTY.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.interactive and (args.scenario or args.all or args.list):
        parser.error("--interactive cannot be combined with --scenario, --all, or --list")
    return args


def _should_use_interactive(args: argparse.Namespace) -> bool:
    if args.no_interactive:
        return False
    if args.interactive:
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            raise SystemExit("Interactive demo requires a TTY on stdin and stdout.")
        return True
    return (
        args.scenario is None
        and not args.all
        and not args.list
        and sys.stdin.isatty()
        and sys.stdout.isatty()
    )


def _emit_demo_banner(*, interactive: bool) -> None:
    banner_lines = [
        "Local mode | register -> resolve -> verify -> query",
        f"Bundled source: {_DEMO_SOURCE_NAME} | algenta-core",
        (
            "Interactive menu | choose a scenario"
            if interactive
            else "No API key required | TTY enables the scenario menu"
        ),
    ]
    _emit(runtime_banner("Algenta Runtime Demo", banner_lines))


def _emit_walkthrough_intro() -> None:
    _emit("Walkthrough")
    _emit("  1. Register bundled rows as a local source.")
    _emit("  2. Choose a business scenario.")
    _emit("  3. Resolve the request against the detected schema.")
    _emit("  4. Verify the plan before execution.")
    _emit("  5. Execute the query or show the guardrail outcome.")
    _emit("  6. Reproduce the same flow on your own data or API runtime.")


def _bootstrap_runtime() -> tuple[Runtime, ImportPreview]:
    runtime = Runtime()
    imported = runtime.import_preview(
        _DEMO_DATA,
        name=_DEMO_SOURCE_NAME,
        source_ref="bundled demo dataset",
    )
    return runtime, imported


def _emit_registration_step(
    imported: ImportPreview,
    *,
    step_label: str = "Step 1/6 - Register bundled source",
) -> None:
    registration = imported.registration
    fields = _source_fields(registration.source_schema)
    _emit_section(step_label)
    _emit_key_values(
        [
            ("source", registration.name or _DEMO_SOURCE_NAME),
            ("origin", "bundled demo dataset"),
            ("status", registration.status),
            ("ingest_mode", registration.ingest_mode or "local"),
            ("rows", str(registration.row_count or len(_DEMO_DATA))),
            ("fields", ", ".join(fields) if fields else "(no schema fields detected)"),
            (
                "schema_revision",
                (registration.planner_schema_revision or "n/a")[:12],
            ),
            ("registration_latency_ms", f"{registration.latency_ms or 0.0:.3f}"),
        ]
    )
    _emit("  sample_rows")
    _emit(_render_table(_DEMO_DATA[:4]))


def _emit_request_step(
    scenario: DemoScenario,
    *,
    step_label: str = "Step 2/6 - Select scenario",
) -> None:
    _emit_section(step_label)
    _emit_key_values(
        [
            ("scenario", scenario.key),
            ("title", scenario.title),
            ("summary", scenario.summary),
        ]
    )
    _emit_json_block("structured_request", scenario.request)


def _emit_plan_step(
    plan: ResolveOutput,
    *,
    step_label: str = "Step 3/6 - Inspect deterministic plan",
) -> None:
    _emit_section(step_label)
    _emit("  planner_actions")
    if plan.plan:
        for item in plan.plan:
            _emit(f"    - {item}")
    else:
        _emit("    - No executable planner actions produced.")
    _emit("  why_this_matched")
    if plan.explanation:
        for item in plan.explanation:
            _emit(f"    - {item}")
    else:
        _emit("    - No explanation provided.")

    metadata = [
        ("confidence", f"{plan.confidence:.3f}"),
        ("decision_path", plan.decision_path),
        ("confidence_source", plan.confidence_source),
        ("deterministic_scope", plan.deterministic_scope),
        ("rejection_reason", plan.rejection_reason or "(none)"),
        ("plan_hash", plan.plan_hash or "n/a"),
        ("planner_latency_ms", f"{plan.latency_ms:.3f}"),
    ]
    if plan.resolved_plan is not None:
        metadata[0:0] = [
            ("source", plan.resolved_plan.source_name),
            ("metric", plan.resolved_plan.metric_column),
            ("group_by", plan.resolved_plan.group_column or "(none)"),
            ("aggregation", plan.resolved_plan.aggregation),
        ]
    else:
        metadata[0:0] = [
            ("source", plan.resolved_source or _DEMO_SOURCE_NAME),
            ("metric", plan.resolved_column or "(unresolved)"),
            ("group_by", "(unresolved)"),
            ("aggregation", "(unresolved)"),
        ]
    _emit("  resolved_metadata")
    _emit_key_values(metadata)

    if plan.candidates:
        top_candidate = plan.candidates[0]
        _emit("  top_candidate")
        _emit_key_values(
            [
                ("source", str(top_candidate.get("source", "(none)"))),
                ("column", str(top_candidate.get("column", "(none)"))),
                ("role", str(top_candidate.get("role", "(none)"))),
                ("confidence", f"{float(top_candidate.get('confidence', 0.0)):.3f}"),
            ]
        )


def _emit_verify_step(
    verification: VerifyOutput,
    *,
    step_label: str = "Step 4/6 - Verify executable plan",
) -> None:
    _emit_section(step_label)
    _emit_key_values(
        [
            ("valid", str(verification.valid).lower()),
            ("verified", str(verification.verified).lower()),
            ("verification_mode", verification.verification_mode),
            ("rejection_reason", verification.rejection_reason or "(none)"),
            ("latency_ms", f"{verification.latency_ms:.3f}"),
        ]
    )
    if verification.resolved:
        _emit_json_block("resolved_bindings", verification.resolved)
    if verification.valid_measures:
        _emit(f"  valid_measures={', '.join(verification.valid_measures)}")
    if verification.valid_dimensions:
        _emit(f"  valid_dimensions={', '.join(verification.valid_dimensions)}")
    if verification.errors:
        _emit("  errors")
        for error in verification.errors:
            _emit(f"    - {error}")
    if verification.suggestions:
        _emit("  suggestions")
        for suggestion in verification.suggestions:
            _emit(f"    - {suggestion}")


def _emit_result_step(
    result: QueryOutput,
    scenario: DemoScenario,
    *,
    step_label: str = "Step 5/6 - Execute deterministic query",
) -> None:
    _emit_section(step_label)
    _emit("  result_table")
    _emit(_render_result(result))
    _emit("  execution_metadata")
    _emit_key_values(
        [
            ("result_type", result.result_type),
            ("rows", str(result.row_count)),
            ("resolved_source", result.resolved_source),
            ("resolved_column", result.resolved_column),
            ("resolved_role", result.resolved_role),
            ("plan_hash", result.plan_hash),
            ("latency_ms", f"{result.latency_ms:.3f}"),
        ]
    )
    insight = _scenario_takeaway(scenario, result)
    if insight is not None:
        _emit("  takeaway")
        _emit(f"    - {insight}")


def _emit_guardrail_step(
    plan: ResolveOutput,
    verification: VerifyOutput,
    *,
    step_label: str = "Step 5/6 - Guardrail outcome",
) -> None:
    _emit_section(step_label)
    _emit("  query_execution=blocked")
    _emit_key_values(
        [
            ("resolve_rejection_reason", plan.rejection_reason or "(none)"),
            ("verify_rejection_reason", verification.rejection_reason or "(none)"),
        ]
    )
    _emit("  Why execution stopped")
    if plan.explanation:
        for item in plan.explanation:
            _emit(f"    - {item}")
    for error in verification.errors:
        _emit(f"    - {error}")
    if verification.suggestions:
        _emit("  What to try next")
        for suggestion in verification.suggestions:
            _emit(f"    - {suggestion}")


def _emit_next_step(*, step_label: str = "Step 6/6 - Reproduce on your own data") -> None:
    _emit_section(step_label)
    _emit("  local_runtime")
    _emit("    from algenta import Runtime")
    _emit("    rt = Runtime()")
    _emit('    rt.connect("orders.csv", name="orders")')
    _emit('    request = {"source_name": "orders", "metric": "revenue"}')
    _emit('    request["group_by"] = "product_line"')
    _emit("    plan = rt.resolve(request)")
    _emit("    verified = rt.verify(plan)")
    _emit("    result = rt.query(plan)")
    _emit("  cli_shortcuts")
    _emit("    algenta import orders.csv --name orders")
    _emit("    algenta demo --list")
    _emit("    algenta demo --scenario canada_filter --no-interactive")
    _emit("  api_runtime")
    _emit("    api_key = os.environ.get('ALGENTA_API_KEY') or os.environ.get('DE_API_KEY')")
    _emit("    if not api_key: raise RuntimeError('Set ALGENTA_API_KEY or DE_API_KEY before running this example.')")
    _emit("    rt = Runtime(mode='api', api_key=api_key)  # Cloud Managed example")
    _emit("    # In self_hosted/air_gapped, pass base_url='http://localhost:8000' or your own self-hosted origin.")
    _emit("    result = rt.query(plan)")


def _emit_scenario_catalog() -> None:
    _emit("Available scenarios")
    for index, scenario in enumerate(_SCENARIOS, start=1):
        _emit(f"  {index}. {scenario.title} [{scenario.key}]")
        _emit(f"     {scenario.summary}")
    _emit("  all. Run every scenario sequentially")
    _emit("  recipes. Show local, CLI, and API integration recipes")
    _emit("  quit. Exit the demo")
    _emit("  Tip: chain choices like 1,recipes or all,quit")


def _format_metric_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:,.1f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


def _scenario_takeaway(scenario: DemoScenario, result: QueryOutput) -> str | None:
    if scenario.takeaway_template is None:
        return None
    if result.result_type != "table" or not isinstance(result.result, list) or not result.result:
        return None
    first_row = result.result[0]
    if not isinstance(first_row, dict):
        return None
    group_value = (
        first_row.get("product_line")
        or first_row.get("region")
        or first_row.get("channel")
    )
    metric_value = first_row.get("revenue") or first_row.get("count")
    if group_value is None or metric_value is None:
        return None
    return scenario.takeaway_template.format(
        group=str(group_value),
        metric=_format_metric_value(metric_value),
    )


def _run_scenario(runtime: Runtime, scenario: DemoScenario) -> None:
    request = copy.deepcopy(scenario.request)
    plan = runtime.resolve(request)
    verification = runtime.verify(plan)

    _emit_request_step(scenario)
    _emit()
    _emit_plan_step(plan)
    _emit()
    _emit_verify_step(verification)
    _emit()
    if scenario.expect_query and plan.resolved_plan is not None and verification.valid:
        result = runtime.query(plan)
        _emit_result_step(result, scenario)
    else:
        _emit_guardrail_step(plan, verification)
    _emit()
    _emit_next_step()


def _run_single_scenario(
    runtime: Runtime,
    imported: ImportPreview,
    scenario: DemoScenario,
    *,
    include_intro: bool,
) -> None:
    if include_intro:
        _emit_walkthrough_intro()
        _emit()
        _emit_registration_step(imported)
        _emit()
    _run_scenario(runtime, scenario)


def _run_all_scenarios(runtime: Runtime, imported: ImportPreview) -> None:
    _emit_walkthrough_intro()
    _emit()
    _emit_registration_step(imported)
    _emit()
    _emit_scenario_catalog()
    for scenario in _SCENARIOS:
        _emit()
        _emit("=" * 62)
        _emit(f"Scenario: {scenario.title}")
        _emit("=" * 62)
        _emit()
        _run_scenario(runtime, scenario)


def _resolve_menu_scenario(choice: str) -> DemoScenario | None:
    normalized = choice.strip().lower()
    key = _MENU_CHOICES.get(normalized, normalized)
    return _SCENARIOS_BY_KEY.get(key)


def _parse_interactive_actions(raw_choice: str) -> list[str]:
    tokens = [token for token in _MENU_SPLIT_RE.split(raw_choice.strip().lower()) if token]
    return [_MENU_CHOICES.get(token, token) for token in tokens]


def _run_interactive(runtime: Runtime, imported: ImportPreview) -> int:
    _emit("Interactive mode")
    _emit(
        "  This session covers registration, resolve, verify, filter-aware queries, "
        "guardrails, and local/API handoff."
    )
    _emit()
    _emit_registration_step(imported, step_label="Session bootstrap - Register bundled source")

    while True:
        _emit()
        _emit_scenario_catalog()
        try:
            choice = input("\nSelect option [1-4, all, recipes, quit]: ").strip().lower()
        except EOFError:
            _emit()
            _emit("Exiting demo.")
            return 0
        except KeyboardInterrupt:
            _emit()
            _emit("Exiting demo.")
            return 0

        if not choice:
            continue

        actions = _parse_interactive_actions(choice)
        if not actions:
            continue
        unknown_actions = [
            action
            for action in actions
            if action not in {"all", "recipes", "quit"} and action not in _SCENARIOS_BY_KEY
        ]
        if unknown_actions:
            _emit()
            _emit(
                "Unknown option. Use 1-4, all, recipes, or quit. "
                "You can chain them with commas."
            )
            continue

        should_exit = False
        for action in actions:
            if action == "quit":
                should_exit = True
                break
            if action == "all":
                _emit()
                _run_all_scenarios(runtime, imported)
                continue
            if action == "recipes":
                _emit()
                _emit_next_step(step_label="Integration recipes")
                continue

            scenario = _SCENARIOS_BY_KEY[action]
            _emit()
            _emit("=" * 62)
            _emit(f"Scenario: {scenario.title}")
            _emit("=" * 62)
            _emit()
            _run_scenario(runtime, scenario)
        if should_exit:
            _emit()
            _emit("Exiting demo.")
            return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.list:
        _emit_scenario_catalog()
        return 0

    interactive = _should_use_interactive(args)
    runtime, imported = _bootstrap_runtime()
    _emit_demo_banner(interactive=interactive)
    _emit()

    if interactive:
        return _run_interactive(runtime, imported)
    if args.all:
        _run_all_scenarios(runtime, imported)
        return 0
    if args.scenario is not None:
        scenario = _SCENARIOS_BY_KEY[args.scenario]
        _run_single_scenario(runtime, imported, scenario, include_intro=True)
        return 0

    _run_single_scenario(runtime, imported, _SCENARIOS_BY_KEY["product_line"], include_intro=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
