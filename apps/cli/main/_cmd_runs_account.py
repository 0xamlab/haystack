"""agent_runs, account, billing, credits, metering, team, devices, execution, keys.

Extracted from apps/cli/main.py during modularization.
"""
from __future__ import annotations

import json
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from pydantic import ValidationError

from apps.cli import data_commands as _data_commands
from apps.cli.support import (
    CONFIG_FILE,
    load_config,
    print_result,
    save_config,
)
from apps.cli.support import (
    arg_value as _arg_value,
)
from apps.cli.support import (
    store_api_key_secure as _store_api_key_secure,
)
from apps.cli.support import (
    strip_none as _strip_none,
)
from apps.platform_contract import PlatformContractResponse
from apps.platform_contract_fallback import (
    PlatformContractFallbackError,
    build_platform_contract_from_openapi,
)
from apps.validation_error_details import format_validation_error_message

_RUNTIME_READY_TIMEOUT_SECONDS = 3.0
_RUNTIME_READY_POLL_SECONDS = 0.1
_RUNTIME_NOT_RUNNING_MESSAGE = "Codna Runtime is not running. Start with: de runtime start"


# Facade-routed proxies. Tests monkey-patch these on `apps.cli.main` (the
# facade) and expect the submodule call sites to see the patched values.
# Each wrapper does a fresh `from apps.cli import main as _facade` lookup so
# monkeypatch.setattr(cli_main, "X", fake) is honored.
def _load_env_api_key():
    from apps.cli import main as _facade
    return _facade._load_env_api_key()


def _private_profile_enabled():
    from apps.cli import main as _facade
    return _facade._private_profile_enabled()


def _get_base_url():
    from apps.cli import main as _facade
    return _facade._get_base_url()


def _get_dashboard_url():
    from apps.cli import main as _facade
    return _facade._get_dashboard_url()


def api_request(*args, **kwargs):
    from apps.cli import main as _facade
    return _facade.api_request(*args, **kwargs)


def api_stream_request(*args, **kwargs):
    from apps.cli import main as _facade
    return _facade.api_stream_request(*args, **kwargs)


class _RichProxy:
    """Boolean-like proxy that reads `_RICH` from the facade at access time.

    Submodule code uses `_RICH` as a boolean (`if _RICH:` or
    `rich_enabled=_RICH`); when a test monkey-patches `cli_main._RICH = False`,
    bool(_RICH) follows the new value.
    """
    __slots__ = ()

    def __bool__(self) -> bool:
        from apps.cli import main as _facade
        return bool(_facade._RICH)

    def __eq__(self, other: object) -> bool:
        return bool(self) == bool(other)

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __repr__(self) -> str:
        return repr(bool(self))

    def __hash__(self) -> int:
        return hash(bool(self))


_RICH = _RichProxy()

from apps.cli.main._helpers import *  # noqa: F401, F403
from apps.cli.main._helpers import (
    _normalize_expert_variable,
    _load_benchmark_summary,
    _display_benchmark_source,
    _format_speedup_value,
    _normalize_simulation_request,
    _normalize_recommend_request,
    _normalize_score_request,
    _normalize_batch_request,
    _normalize_compare_request,
    _load_request_json,
    _print_api_error_and_exit,
    _print_streaming_request_error_and_exit,
    _stream_payloads,
    _print_sse_payloads,
    _print_chat_stream,
    _render_response_stream_table,
    _print_response_stream,
    _render_agent_run_stream_table,
    _print_agent_run_event_stream,
    _load_json_object_file,
    _normalize_metering_payload,
    _normalize_credit_refresh_payload,
)
from apps.cli.main._cmd_data_repos import *  # noqa: F401, F403
from apps.cli.main._cmd_data_repos import (
    _print_connector_summary,
    _parse_csv_flag,
    _print_capability_provider_summary,
    _print_repository_snapshot_summary,
    _print_repository_triage_summary,
    _print_repository_decision_plan_summary,
    _print_repository_graph_query_summary,
    _print_repository_apply_summary,
    _print_repository_capabilities_summary,
)
from apps.cli.main._cmd_decisions_llm import *  # noqa: F401, F403


def cmd_agent_run_create(request_path: str, format: str = "table") -> None:
    payload = _load_request_json(request_path)
    status, data = api_request("POST", "/v1/agent/runs", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nRun ID:         {data.get('run_id')}")
    print(f"Status:         {data.get('status')}")
    print(f"Task:           {data.get('task')}")
    print(f"Approval mode:  {data.get('approval_mode')}")
    print(f"Pending action: {data.get('pending_action')}\n")


def cmd_agent_run_list(
    *,
    page: int = 1,
    limit: int = 25,
    status_filter: str | None = None,
    request_hash: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    format: str = "table",
) -> None:
    query = [f"page={page}", f"limit={limit}"]
    if status_filter:
        query.append(f"status={status_filter}")
    if request_hash:
        query.append(f"request_hash={request_hash}")
    if policy_snapshot_id:
        query.append(f"policy_snapshot_id={policy_snapshot_id}")
    if schema_snapshot_id:
        query.append(f"schema_snapshot_id={schema_snapshot_id}")
    status, data = api_request("GET", f"/v1/agent/runs?{'&'.join(query)}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nTotal runs:     {data.get('total')}")
    print(f"Page:           {data.get('page')} / {data.get('pages')}")
    print(f"Limit:          {data.get('limit')}")
    for run in data.get("data", []):
        print(
            f"  {run.get('created_at')}  "
            f"{run.get('run_id')}  "
            f"{run.get('status')}  "
            f"{run.get('selected_tool') or '-'}  "
            f"{run.get('policy_snapshot_id') or '-'}"
        )
    print()


def cmd_agent_run_get(run_id: str, format: str = "table") -> None:
    status, data = api_request("GET", f"/v1/agent/runs/{run_id}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nRun ID:         {data.get('run_id')}")
    print(f"Status:         {data.get('status')}")
    print(f"Task:           {data.get('task')}")
    print(f"Selected tool:  {data.get('selected_tool')}")
    print(f"Pending action: {data.get('pending_action')}")
    print(f"Tools used:     {', '.join(data.get('tools_used', []))}\n")


def cmd_agent_run_events(
    run_id: str,
    limit: int = 1000,
    format: str = "table",
    *,
    stream: bool = False,
) -> None:
    path = f"/v1/agent/runs/{run_id}/events?limit={limit}"
    if stream:
        joiner = "&" if "?" in path else "?"
        _print_agent_run_event_stream(
            _stream_payloads("GET", f"{path}{joiner}stream=true"),
            format=format,
        )
        return
    status, data = api_request("GET", path)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nRun ID:        {data.get('run_id')}")
    print(f"Total events:  {data.get('total_events')}")
    for event in data.get("data", []):
        print(
            f"  {event.get('created_at')}  "
            f"{event.get('event_type')}  "
            f"{event.get('status')}  "
            f"{event.get('message')}"
        )
    print()


def cmd_agent_run_checkpoints(run_id: str, format: str = "table") -> None:
    status, data = api_request("GET", f"/v1/agent/runs/{run_id}/checkpoints")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nRun ID:            {data.get('run_id')}")
    print(f"Total checkpoints: {data.get('total_checkpoints')}")
    for checkpoint in data.get("data", []):
        print(
            f"  #{checkpoint.get('checkpoint_index')}  "
            f"{checkpoint.get('checkpoint_id')}  "
            f"{checkpoint.get('status')}  "
            f"events {checkpoint.get('event_start_index')}..{checkpoint.get('event_end_index')}"
        )
    print()


def cmd_agent_run_query_checkpoints(
    *,
    page: int = 1,
    limit: int = 25,
    status_filter: str | None = None,
    request_hash: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    run_id: str | None = None,
    checkpoint_id: str | None = None,
    format: str = "table",
) -> None:
    query = [f"page={page}", f"limit={limit}"]
    if status_filter:
        query.append(f"status={quote(status_filter)}")
    if request_hash:
        query.append(f"request_hash={quote(request_hash)}")
    if policy_snapshot_id:
        query.append(f"policy_snapshot_id={quote(policy_snapshot_id)}")
    if schema_snapshot_id:
        query.append(f"schema_snapshot_id={quote(schema_snapshot_id)}")
    if run_id:
        query.append(f"run_id={quote(run_id)}")
    if checkpoint_id:
        query.append(f"checkpoint_id={quote(checkpoint_id)}")
    status, data = api_request("GET", f"/v1/agent/runs/checkpoints?{'&'.join(query)}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nCheckpoints: {data.get('total')}")
    print(f"Page:        {data.get('page')} / {data.get('pages')}")
    for checkpoint in data.get("data", []):
        print(
            f"  {checkpoint.get('created_at')}  "
            f"{checkpoint.get('run_id')}  "
            f"{checkpoint.get('run_status')}  "
            f"{checkpoint.get('checkpoint_id')}  "
            f"idx={checkpoint.get('checkpoint_index')}"
        )
    print()


def cmd_agent_run_mission_events(run_id: str, limit: int = 1000, format: str = "table") -> None:
    status, data = api_request("GET", f"/v1/agent/runs/{run_id}/mission-events?limit={limit}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nRun ID:        {data.get('run_id')}")
    print(f"Total events:  {data.get('total_events')}")
    for event in data.get("data", []):
        print(
            f"  {event.get('event_ts')}  "
            f"{event.get('event_type')}  "
            f"superstep={event.get('superstep')}  "
            f"checkpoint={event.get('checkpoint_id') or '-'}"
        )
    print()


def cmd_agent_run_telemetry(run_id: str, limit: int = 1000, format: str = "table") -> None:
    status, data = api_request("GET", f"/v1/agent/runs/{run_id}/telemetry?limit={limit}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nRun ID:         {data.get('run_id')}")
    print(f"Total batches:  {data.get('total_batches')}")
    for batch in data.get("data", []):
        print(
            f"  {batch.get('started_at')}..{batch.get('ended_at')}  "
            f"{batch.get('telemetry_kind')}  "
            f"p95={batch.get('latency_ms_p95')}ms  "
            f"success={batch.get('success_count')} failure={batch.get('failure_count')}"
        )
    print()


def cmd_agent_run_query_mission_events(
    *,
    page: int = 1,
    limit: int = 25,
    status_filter: str | None = None,
    request_hash: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    run_id: str | None = None,
    event_type: str | None = None,
    format: str = "table",
) -> None:
    query = [f"page={page}", f"limit={limit}"]
    if status_filter:
        query.append(f"status={quote(status_filter)}")
    if request_hash:
        query.append(f"request_hash={quote(request_hash)}")
    if policy_snapshot_id:
        query.append(f"policy_snapshot_id={quote(policy_snapshot_id)}")
    if schema_snapshot_id:
        query.append(f"schema_snapshot_id={quote(schema_snapshot_id)}")
    if run_id:
        query.append(f"run_id={quote(run_id)}")
    if event_type:
        query.append(f"event_type={quote(event_type)}")
    path = f"/v1/agent/runs/mission-events?{'&'.join(query)}"
    status, data = api_request("GET", path)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nMission events: {data.get('total')}")
    print(f"Page:           {data.get('page')} / {data.get('pages')}")
    for event in data.get("data", []):
        print(
            f"  {event.get('event_ts')}  "
            f"{event.get('run_id')}  "
            f"{event.get('run_status')}  "
            f"{event.get('event_type')}  "
            f"superstep={event.get('superstep')}"
        )
    print()


def cmd_agent_run_query_telemetry(
    *,
    page: int = 1,
    limit: int = 25,
    status_filter: str | None = None,
    request_hash: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    run_id: str | None = None,
    telemetry_kind: str | None = None,
    module_name: str | None = None,
    format: str = "table",
) -> None:
    query = [f"page={page}", f"limit={limit}"]
    if status_filter:
        query.append(f"status={quote(status_filter)}")
    if request_hash:
        query.append(f"request_hash={quote(request_hash)}")
    if policy_snapshot_id:
        query.append(f"policy_snapshot_id={quote(policy_snapshot_id)}")
    if schema_snapshot_id:
        query.append(f"schema_snapshot_id={quote(schema_snapshot_id)}")
    if run_id:
        query.append(f"run_id={quote(run_id)}")
    if telemetry_kind:
        query.append(f"telemetry_kind={quote(telemetry_kind)}")
    if module_name:
        query.append(f"module_name={quote(module_name)}")
    path = f"/v1/agent/runs/telemetry?{'&'.join(query)}"
    status, data = api_request("GET", path)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nTelemetry batches: {data.get('total')}")
    print(f"Page:              {data.get('page')} / {data.get('pages')}")
    for batch in data.get("data", []):
        print(
            f"  {batch.get('started_at')}  "
            f"{batch.get('run_id')}  "
            f"{batch.get('run_status')}  "
            f"{batch.get('telemetry_kind')}  "
            f"p95={batch.get('latency_ms_p95')}ms"
        )
    print()


def _cmd_agent_run_transition(path: str, format: str = "table") -> None:
    status, data = api_request("POST", path, {})
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nRun ID:         {data.get('run_id')}")
    print(f"Status:         {data.get('status')}")
    print(f"Pending action: {data.get('pending_action')}\n")


def cmd_agent_run_resume(run_id: str, format: str = "table") -> None:
    _cmd_agent_run_transition(f"/v1/agent/runs/{run_id}/resume", format=format)


def cmd_agent_run_cancel(run_id: str, format: str = "table") -> None:
    _cmd_agent_run_transition(f"/v1/agent/runs/{run_id}/cancel", format=format)


def cmd_agent_run_approve(run_id: str, format: str = "table") -> None:
    _cmd_agent_run_transition(f"/v1/agent/runs/{run_id}/approve", format=format)


def cmd_account_me(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/me")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nEmail:     {data.get('email') or data.get('user_email') or data.get('user', {}).get('email', '')}")
    print(f"Org ID:    {data.get('org_id') or data.get('organization', {}).get('id', '')}")
    print(f"Org Name:  {data.get('org_name') or data.get('organization', {}).get('name', '')}")
    print(f"Plan:      {data.get('plan') or data.get('organization', {}).get('plan', '')}\n")


def cmd_account_update(request_path: str, format: str = "table") -> None:
    try:
        payload = json.loads(Path(request_path).read_text())
    except FileNotFoundError:
        print(f"Request file not found: {request_path}", file=sys.stderr)
        raise SystemExit(1) from None
    except json.JSONDecodeError as exc:
        print(f"Invalid JSON in request file: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    status, data = api_request("PATCH", "/v1/me", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    user = data.get("user", {}) if isinstance(data, dict) else {}
    org = data.get("org", {}) if isinstance(data, dict) else {}
    print(f"\nName:      {user.get('name', '')}")
    print(f"Email:     {user.get('email', '')}")
    print(f"Org Name:  {org.get('name', '')}")
    print(f"Plan:      {org.get('plan', '')}\n")


def cmd_account_usage(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/usage")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nBilling period:   {data.get('billing_period')}")
    print(f"Simulations run:  {data.get('simulations_run')}")
    print(f"API calls:        {data.get('api_calls')}")
    print(f"Quota limit:      {data.get('quota_limit')}")
    print(f"Quota used:       {data.get('quota_used_pct')}%\n")


def cmd_account_limits(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/limits")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nPlan:              {data.get('plan')}")
    print(f"Simulations/month: {data.get('simulations_per_month')}")
    print(f"Rate limit/minute: {data.get('rate_limit_per_minute')}")
    print(f"Connectors:        {data.get('connectors')}")
    print(f"Jobs enabled:      {data.get('jobs_enabled')}\n")


def cmd_account_distributions(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/distributions")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if isinstance(data, dict):
        distributions = data.get("distributions", [])
    else:
        distributions = data
    if format == "json":
        print(json.dumps({"distributions": distributions}, indent=2, default=str))
        return
    count = len(distributions) if isinstance(distributions, list) else 0
    print(f"\nSupported distributions ({count}):")
    for entry in distributions if isinstance(distributions, list) else []:
        required = ", ".join(entry.get("required_params", []))
        print(f"  {entry.get('name', '')}: {required}")
    print()


def cmd_account_templates(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/templates")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if isinstance(data, dict):
        templates = data.get("templates", [])
    else:
        templates = data
    if format == "json":
        print(json.dumps({"templates": templates}, indent=2, default=str))
        return
    count = len(templates) if isinstance(templates, list) else 0
    print(f"\nBuilt-in templates ({count}):")
    for entry in templates if isinstance(templates, list) else []:
        print(f"  {entry.get('id', '')} [{entry.get('category', '')}] {entry.get('name', '')}")
    print()


def cmd_billing_info(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/billing/info")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nPlan:                 {data.get('plan')}")
    print(f"Stripe customer ID:   {data.get('stripe_customer_id')}")
    print(f"Subscription status:  {data.get('subscription_status')}")
    print(f"Current period end:   {data.get('current_period_end')}\n")


def cmd_billing_checkout(plan: str | None = None, format: str = "table") -> None:
    payload: dict[str, Any] = {}
    if plan is not None:
        if plan not in {"developer", "pro"}:
            raise RuntimeError("Billing checkout plan must be one of: developer, pro.")
        payload["plan"] = plan
    status, data = api_request("POST", "/v1/billing/checkout", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nCheckout URL: {data.get('url')}\n")


def cmd_billing_portal(format: str = "table") -> None:
    status, data = api_request("POST", "/v1/billing/portal", {})
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nPortal URL: {data.get('url')}\n")


def cmd_credits_refresh(request_path: str, format: str = "table") -> None:
    payload = _normalize_credit_refresh_payload(
        _load_json_object_file(request_path, context="Credit refresh request")
    )
    status, data = api_request("POST", "/v1/credits/refresh", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nCredits granted:        {data.get('credits_granted')}")
    print(f"Issued this month:      {data.get('credits_issued_this_month')}")
    print(f"Monthly remaining:      {data.get('monthly_remaining')}")
    print(f"Billing period:         {data.get('billing_period')}")
    print(f"Refresh after:          {data.get('refresh_after')}")
    print(f"Expires at:             {data.get('expires_at')}\n")


def cmd_metering_ingest(request_path: str, format: str = "table") -> None:
    payload = _normalize_metering_payload(
        _load_json_object_file(request_path, context="Metering request")
    )
    status, data = api_request("POST", "/v1/metering", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nAccepted events: {data.get('accepted')}")
    print(f"Billing period:  {data.get('billing_period')}\n")


def cmd_team_list(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/team")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    members = data if isinstance(data, list) else data.get("members", [])
    print(f"\nTeam members ({len(members)}):")
    for member in members:
        print(
            f"  {member.get('email', '')} "
            f"[{member.get('role', '')}] — {member.get('status', '')}"
        )
    print()


def cmd_team_invite(email: str, role: str = "member", format: str = "table") -> None:
    status, data = api_request("POST", "/v1/team/invite", {"email": email, "role": role})
    if status != 201:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nInvitation: {data.get('invite_id')}")
    print(f"Message:    {data.get('message')}\n")


def cmd_team_update_role(user_id: str, role: str, format: str = "table") -> None:
    status, data = api_request("PATCH", f"/v1/team/{user_id}/role", {"role": role})
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nUser ID: {data.get('user_id')}")
    print(f"Message: {data.get('message')}\n")


def cmd_team_remove(user_id: str, format: str = "table") -> None:
    status, data = api_request("DELETE", f"/v1/team/{user_id}")
    if status not in {200, 204}:
        _print_api_error_and_exit(status, data)
    normalized = data if isinstance(data, dict) else {}
    normalized.setdefault("removed", True)
    normalized.setdefault("user_id", user_id)
    if format == "json":
        print(json.dumps(normalized, indent=2, default=str))
        return
    print(f"\nRemoved: {normalized.get('removed')}")
    print(f"User ID: {normalized.get('user_id')}\n")


def cmd_team_audit_logs(
    format: str = "table",
    *,
    page: int = 1,
    limit: int = 25,
    actor_email: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    result: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    manifest_version: str | None = None,
    request_hash: str | None = None,
) -> None:
    import urllib.parse

    query: dict[str, str | int] = {"page": page, "limit": limit}
    optional_filters = {
        "actor_email": actor_email,
        "action": action,
        "resource_type": resource_type,
        "result": result,
        "policy_snapshot_id": policy_snapshot_id,
        "schema_snapshot_id": schema_snapshot_id,
        "manifest_version": manifest_version,
        "request_hash": request_hash,
    }
    for field_name, value in optional_filters.items():
        if value is not None:
            query[field_name] = value
    status, data = api_request("GET", f"/v1/audit-logs?{urllib.parse.urlencode(query)}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    entries = data.get("entries", []) if isinstance(data, dict) else []
    total = data.get("total", len(entries)) if isinstance(data, dict) else len(entries)
    current_page = data.get("page", page) if isinstance(data, dict) else page
    pages = data.get("pages", 1) if isinstance(data, dict) else 1
    print(f"\nAudit log entries ({total} total, page {current_page}/{pages}):")
    for entry in entries:
        metadata = entry.get("metadata")
        metadata_suffix = f" {json.dumps(metadata, sort_keys=True)}" if metadata else ""
        print(
            f"  {entry.get('timestamp', '')} "
            f"{entry.get('action', '')} "
            f"{entry.get('resource_type', '')} "
            f"[{entry.get('result', '')}]"
            f"{metadata_suffix}"
        )
    print()


def cmd_team_audit_artifacts(
    format: str = "table",
    *,
    page: int = 1,
    limit: int = 25,
    actor_email: str | None = None,
    action: str | None = None,
    resource_type: str | None = None,
    result: str | None = None,
    policy_snapshot_id: str | None = None,
    schema_snapshot_id: str | None = None,
    manifest_version: str | None = None,
    request_hash: str | None = None,
    content_hash: str | None = None,
) -> None:
    import urllib.parse

    query: dict[str, str | int] = {"page": page, "limit": limit}
    optional_filters = {
        "actor_email": actor_email,
        "action": action,
        "resource_type": resource_type,
        "result": result,
        "policy_snapshot_id": policy_snapshot_id,
        "schema_snapshot_id": schema_snapshot_id,
        "manifest_version": manifest_version,
        "request_hash": request_hash,
        "content_hash": content_hash,
    }
    for field_name, value in optional_filters.items():
        if value is not None:
            query[field_name] = value
    status, data = api_request("GET", f"/v1/audit-logs/artifacts?{urllib.parse.urlencode(query)}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    entries = data.get("entries", []) if isinstance(data, dict) else []
    total = data.get("total", len(entries)) if isinstance(data, dict) else len(entries)
    current_page = data.get("page", page) if isinstance(data, dict) else page
    pages = data.get("pages", 1) if isinstance(data, dict) else 1
    print(f"\nAudit artifacts ({total} total, page {current_page}/{pages}):")
    for entry in entries:
        metadata = entry.get("metadata")
        metadata_suffix = f" {json.dumps(metadata, sort_keys=True)}" if metadata else ""
        print(
            f"  {entry.get('timestamp', '')} "
            f"{entry.get('action', '')} "
            f"{entry.get('resource_type', '')} "
            f"[{entry.get('result', '')}] "
            f"content_hash={entry.get('content_hash', '')}"
            f"{metadata_suffix}"
        )
    print()


def cmd_devices_list(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/device/list")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    devices = data.get("devices", []) if isinstance(data, dict) else []
    print(f"\nRegistered devices ({len(devices)}):")
    for device in devices:
        print(
            f"  {device.get('device_id', '')} "
            f"[{device.get('status', '')}] "
            f"{device.get('platform', '')} "
            f"{device.get('sdk_version', '')}"
        )
    print()


def cmd_devices_revoke(registration_id: str, format: str = "table") -> None:
    status, data = api_request("DELETE", f"/v1/device/{registration_id}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nRevoked: {data.get('registration_id')}\n")


def cmd_execution_policy_get(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/execution/policy")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nOrg ID:               {data.get('org_id')}")
    print(f"Min confidence:       {data.get('min_confidence')}")
    print(f"Risk floor:           {data.get('risk_floor')}")
    print(f"Require calibration:  {data.get('require_calibration')}")
    print(f"Allow reexecution:    {data.get('allow_reexecution')}")
    print(f"Snapshot ID:          {data.get('snapshot_id')}")
    print(f"Revision:             {data.get('revision')}")
    print(f"Updated at:           {data.get('updated_at')}\n")


def cmd_execution_policy_snapshots(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/execution/policy/snapshots")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    items = data.get("data", []) if isinstance(data, dict) else []
    total = data.get("total_snapshots") if isinstance(data, dict) else len(items)
    print(f"\nExecution Policy Snapshots: {total}")
    for item in items:
        if not isinstance(item, dict):
            continue
        print(
            f"  r{item.get('revision')} "
            f"{item.get('snapshot_id', '')} "
            f"min_conf={item.get('min_confidence')} "
            f"risk_floor={item.get('risk_floor')}"
        )
    print()


def cmd_execution_policy_update(request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Execution policy request")
    status, data = api_request("PATCH", "/v1/execution/policy", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nOrg ID:               {data.get('org_id')}")
    print(f"Min confidence:       {data.get('min_confidence')}")
    print(f"Risk floor:           {data.get('risk_floor')}")
    print(f"Require calibration:  {data.get('require_calibration')}")
    print(f"Allow reexecution:    {data.get('allow_reexecution')}")
    print(f"Snapshot ID:          {data.get('snapshot_id')}")
    print(f"Revision:             {data.get('revision')}")
    print(f"Updated at:           {data.get('updated_at')}\n")


def cmd_keys_list(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/api-keys")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    items = data if isinstance(data, list) else data.get("api_keys", [])
    print(f"\nAPI Keys ({len(items)} active):")
    for key_info in items:
        k: dict[str, Any] = key_info  # type: ignore[assignment]
        print(
            f"  {k.get('key_prefix', '')}... "
            f"[{k.get('label', '')}] — {k.get('status', '')} "
            f"device_limit={k.get('device_limit')}"
        )
    print()


def cmd_keys_create(
    label: str,
    *,
    expires_at: str | None = None,
    device_limit: int | None = None,
    format: str = "table",
) -> None:
    payload: dict[str, Any] = {"label": label}
    if expires_at is not None:
        payload["expires_at"] = expires_at
    if device_limit is not None:
        payload["device_limit"] = device_limit
    status, data = api_request("POST", "/v1/api-keys", payload)
    if status != 201:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nKey ID:        {data.get('id')}")
    print(f"Label:         {data.get('label')}")
    print(f"Key prefix:    {data.get('key_prefix')}")
    print(f"Device limit:  {data.get('device_limit')}")
    print(f"Expires at:    {data.get('expires_at')}")
    print(f"Raw key:       {data.get('raw_key')}\n")


def cmd_keys_revoke(key_id: str, format: str = "table") -> None:
    status, data = api_request("DELETE", f"/v1/api-keys/{key_id}")
    if status != 204:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nRevoked API key: {key_id}\n")

