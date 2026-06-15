"""data, connectors, capabilities, repositories, config, simulate, recommend.

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
from apps.api_server.services.repository_intelligence_channel_envelope import (
    build_repository_fix_envelope,
    build_repository_pipeline_envelope,
    build_repository_simulate_patch_envelope,
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


def cmd_data_connect(request_path: str | None = None, format: str = "table") -> None:
    _data_commands.cmd_data_connect(
        request_path=request_path,
        format=format,
        api_request=api_request,
        rich_enabled=_RICH,
    )


def cmd_data_list(
    format: str = "table",
    *,
    search: str | None = None,
    status_filter: str | None = None,
    source_name: str | None = None,
    page: int = 1,
    limit: int = 20,
    compact: bool = False,
) -> None:
    _data_commands.cmd_data_list(
        format=format,
        api_request=api_request,
        rich_enabled=_RICH,
        search=search,
        status_filter=status_filter,
        source_name=source_name,
        page=page,
        limit=limit,
        compact=compact,
    )


def cmd_data_summary(dataset_id: str, format: str = "table") -> None:
    _data_commands.cmd_data_summary(
        dataset_id,
        format=format,
        api_request=api_request,
        rich_enabled=_RICH,
    )


def cmd_data_inspect(dataset_id: str, format: str = "table") -> None:
    _data_commands.cmd_data_inspect(
        dataset_id,
        format=format,
        api_request=api_request,
        rich_enabled=_RICH,
    )


def cmd_data_refresh(dataset_id: str, format: str = "table") -> None:
    _data_commands.cmd_data_refresh(
        dataset_id,
        format=format,
        api_request=api_request,
        rich_enabled=_RICH,
    )


def cmd_data_query_batch(request_path: str, format: str = "table") -> None:
    _data_commands.cmd_data_query_batch(
        request_path,
        format=format,
        api_request=api_request,
        rich_enabled=_RICH,
    )


def cmd_data_sql_report(request_path: str, format: str = "table") -> None:
    _data_commands.cmd_data_sql_report(
        request_path,
        format=format,
        api_request=api_request,
        rich_enabled=_RICH,
    )


def cmd_data_disconnect(
    dataset_id: str,
    *,
    assume_yes: bool = False,
    format: str = "table",
) -> None:
    _data_commands.cmd_data_disconnect(
        dataset_id,
        assume_yes=assume_yes,
        format=format,
        api_request=api_request,
        rich_enabled=_RICH,
    )


def _print_connector_summary(data: dict[str, Any], *, format: str) -> None:
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nConnector ID:     {data.get('id')}")
    print(f"Name:             {data.get('name')}")
    print(f"Type:             {data.get('connector_type')}")
    print(f"Status:           {data.get('status')}")
    print(f"Visibility:       {data.get('visibility')}")
    print(f"Description:      {data.get('description')}")
    print(f"Last tested at:   {data.get('last_tested_at')}")
    print(f"Created at:       {data.get('created_at')}\n")


def cmd_connectors_create(request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Connector create request")
    status, data = api_request("POST", "/v1/connectors", payload)
    if status != 201:
        _print_api_error_and_exit(status, data)
    _print_connector_summary(data, format=format)


def cmd_connectors_list(
    *,
    page: int = 1,
    limit: int = 25,
    format: str = "table",
) -> None:
    status, data = api_request("GET", f"/v1/connectors?{urlencode({'page': page, 'limit': limit})}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    connectors = data if isinstance(data, list) else data.get("connectors", [])
    total = len(connectors) if isinstance(connectors, list) else 0
    if isinstance(data, dict) and isinstance(data.get("total"), int):
        total = data["total"]
    if format == "json":
        print(
            json.dumps(
                {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "connectors": connectors,
                },
                indent=2,
                default=str,
            )
        )
        return
    print(f"\nConnectors ({total} total):")
    for connector in connectors if isinstance(connectors, list) else []:
        print(
            f"  {connector.get('id', '')} "
            f"[{connector.get('connector_type', '')}] "
            f"{connector.get('name', '')} "
            f"status={connector.get('status', '')}"
        )
    print()


def cmd_connectors_get(connector_id: str, format: str = "table") -> None:
    status, data = api_request("GET", f"/v1/connectors/{connector_id}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    _print_connector_summary(data, format=format)


def cmd_connectors_update(connector_id: str, request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Connector update request")
    status, data = api_request("PATCH", f"/v1/connectors/{connector_id}", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    _print_connector_summary(data, format=format)


def cmd_connectors_test(connector_id: str, format: str = "table") -> None:
    status, data = api_request("POST", f"/v1/connectors/{connector_id}/test")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nSuccess:        {data.get('success')}")
    print(f"Status:         {data.get('status')}")
    print(f"Latency ms:     {data.get('latency_ms')}")
    print(f"Recoverable:    {data.get('recoverable')}")
    print(f"Message:        {data.get('message')}\n")


def cmd_connectors_preview_test(request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Connector preview test request")
    status, data = api_request("POST", "/v1/connectors/test", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nSuccess:        {data.get('success')}")
    print(f"Status:         {data.get('status')}")
    print(f"Latency ms:     {data.get('latency_ms')}")
    print(f"Recoverable:    {data.get('recoverable')}")
    print(f"Message:        {data.get('message')}\n")


def cmd_connectors_browse(connector_id: str, format: str = "table") -> None:
    status, data = api_request("GET", f"/v1/connectors/{connector_id}/browse")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nConnector type: {data.get('connector_type')}")
    print(f"Total items:    {data.get('total')}")
    print(f"Message:        {data.get('message')}")
    for item in data.get("items", [])[:10]:
        label = (
            item.get("name")
            or item.get("table_name")
            or item.get("path")
            or item.get("id")
            or json.dumps(item, default=str)
        )
        print(f"  {label}")
    print()


def cmd_connectors_preview_browse(request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Connector preview browse request")
    status, data = api_request("POST", "/v1/connectors/browse", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nConnector type: {data.get('connector_type')}")
    print(f"Total items:    {data.get('total')}")
    print(f"Message:        {data.get('message')}")
    for item in data.get("items", [])[:10]:
        label = (
            item.get("name")
            or item.get("table_name")
            or item.get("path")
            or item.get("id")
            or json.dumps(item, default=str)
        )
        print(f"  {label}")
    print()


def cmd_connectors_delete(connector_id: str, format: str = "table") -> None:
    status, data = api_request("DELETE", f"/v1/connectors/{connector_id}")
    if status != 204:
        _print_api_error_and_exit(status, data)
    payload = {"connector_id": connector_id, "deleted": True}
    if format == "json":
        print(json.dumps(payload, indent=2, default=str))
        return
    print(f"\nConnector deleted: {connector_id}\n")


def _parse_csv_flag(raw_value: str | None) -> list[str]:
    if raw_value is None:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _print_capability_provider_summary(data: dict[str, Any], *, format: str) -> None:
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    profiles = data.get("profiles", [])
    print(f"\nProvider ID:      {data.get('provider_id')}")
    print(f"Type:             {data.get('provider_type')}")
    print(f"Name:             {data.get('name')}")
    print(f"Active:           {data.get('active')}")
    print(f"Execution owners: {', '.join(data.get('supported_execution_owners', []))}")
    print(f"Profiles:         {len(profiles) if isinstance(profiles, list) else 0}")
    print(f"Description:      {data.get('description')}")
    for profile in profiles[:5] if isinstance(profiles, list) else []:
        print(
            f"  {profile.get('profile_id')} "
            f"scope={profile.get('binding_scope_default')} "
            f"auth={profile.get('auth_kind')}"
        )
    print()


def cmd_capabilities_providers(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/capability-providers")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    providers = data if isinstance(data, list) else []
    print(f"\nCapability providers ({len(providers)}):")
    for provider in providers:
        if not isinstance(provider, dict):
            continue
        print(
            f"  {provider.get('provider_id')} "
            f"[{provider.get('provider_type')}] "
            f"{provider.get('name')} active={provider.get('active')}"
        )
    print()


def cmd_capabilities_provider(provider_id: str, format: str = "table") -> None:
    status, data = api_request("GET", f"/v1/capability-providers/{provider_id}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    _print_capability_provider_summary(data, format=format)


def cmd_capabilities_bindings(
    *,
    provider_id: str | None = None,
    scope: str | None = None,
    format: str = "table",
) -> None:
    query = {
        key: value
        for key, value in {"provider_id": provider_id, "scope": scope}.items()
        if value is not None
    }
    path = "/v1/capability-bindings"
    if query:
        path = f"{path}?{urlencode(query)}"
    status, data = api_request("GET", path)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    bindings = data if isinstance(data, list) else []
    print(f"\nCapability bindings ({len(bindings)}):")
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        print(
            f"  {binding.get('binding_id')} "
            f"provider={binding.get('provider_id')} "
            f"scope={binding.get('scope')} "
            f"status={binding.get('status')}"
        )
    print()


def cmd_capabilities_list(
    *,
    kinds: list[str] | None = None,
    provider_ids: list[str] | None = None,
    binding_ids: list[str] | None = None,
    format: str = "table",
) -> None:
    query: list[tuple[str, str]] = []
    for kind in kinds or []:
        query.append(("kinds", kind))
    for provider_id in provider_ids or []:
        query.append(("provider_ids", provider_id))
    for binding_id in binding_ids or []:
        query.append(("binding_ids", binding_id))
    path = "/v1/capabilities"
    if query:
        path = f"{path}?{urlencode(query)}"
    status, data = api_request("GET", path)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    capabilities = data if isinstance(data, list) else []
    print(f"\nCapabilities ({len(capabilities)}):")
    for capability in capabilities:
        if not isinstance(capability, dict):
            continue
        print(
            f"  {capability.get('capability_id')} "
            f"[{capability.get('kind')}] "
            f"{capability.get('name')} "
            f"owner={capability.get('execution_owner')}"
        )
    print()


def cmd_capabilities_route(request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Capability route request")
    status, data = api_request("POST", "/v1/capabilities/route", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nCapability ID:    {data.get('selected_capability_id')}")
    print(f"Provider ID:      {data.get('selected_provider_id')}")
    print(f"Binding ID:       {data.get('selected_binding_id')}")
    print(f"Kind:             {data.get('kind')}")
    print(f"Execution owner:  {data.get('execution_owner')}")
    print(f"Requires approval:{data.get('requires_approval')}")
    print(f"Confidence:       {data.get('confidence')}")
    print(f"Reason:           {data.get('reason')}\n")


def cmd_capabilities_execute(request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Capability execute request")
    status, data = api_request("POST", "/v1/capabilities/execute", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nExecution ID:     {data.get('execution_session_id')}")
    print(f"Capability ID:    {data.get('capability_id')}")
    print(f"Provider ID:      {data.get('provider_id')}")
    print(f"Binding ID:       {data.get('binding_id')}")
    print(f"Execution owner:  {data.get('execution_owner')}")
    print(f"Status:           {data.get('status')}")
    print(f"Started at:       {data.get('started_at')}")
    print(f"Completed at:     {data.get('completed_at')}\n")


def _print_repository_snapshot_summary(data: dict[str, Any], *, format: str) -> None:
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nRepository ID:   {data.get('repository_id')}")
    print(f"Snapshot ID:     {data.get('snapshot_id')}")
    print(f"Connector type:  {data.get('connector_type')}")
    print(f"Revision:        {data.get('resolved_revision')}")
    print(f"Files:           {data.get('file_count')}")
    print(f"Raw tokens:      {data.get('raw_repo_token_estimate')}")
    print(f"Status:          {data.get('status')}\n")


def _print_repository_triage_summary(data: dict[str, Any], *, format: str) -> None:
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nEvidence bundle: {data.get('workspace_evidence_bundle_ref')}")
    print(f"Snapshot ID:     {data.get('snapshot_id')}")
    print(f"Suspect files:   {len(data.get('suspect_files', []))}")
    print(f"Suspect symbols: {len(data.get('suspect_symbols', []))}")
    print(f"Bundle tokens:   {data.get('evidence_bundle_token_count')}")
    print(f"Reduction ratio: {data.get('reduction_ratio')}")
    for file_path in data.get("suspect_files", [])[:8]:
        print(f"  {file_path}")
    print()


def _print_repository_decision_plan_summary(data: dict[str, Any], *, format: str) -> None:
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    plan = data.get("decision_plan", {})
    analysis = plan.get("repository_analysis", {})
    print(f"\nDecision plan:   {data.get('decision_plan_id')}")
    print(f"Snapshot ID:     {data.get('snapshot_id')}")
    print(f"Action:          {plan.get('recommended_action')}")
    print(f"Confidence:      {plan.get('confidence')}")
    print(f"Planner model:   {analysis.get('planner_model_id')}")
    print(f"Planner mode:    {analysis.get('planner_execution_mode')}")
    print(f"Planner backend: {analysis.get('planner_provider_backend')}")
    print(f"Patch ref:       {analysis.get('generated_patch_ref')}")
    print(f"Patch impact:    {analysis.get('patch_impact_report_ref')}")
    print(f"Root cause:      {analysis.get('root_cause')}")
    for candidate in analysis.get("candidate_fixes", [])[:5]:
        print(f"  {candidate}")
    print()


def _print_repository_graph_query_summary(data: dict[str, Any], *, format: str) -> None:
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nSnapshot ID:       {data.get('snapshot_id')}")
    print(f"Seed files:        {len(data.get('seed_file_paths', []))}")
    print(f"Seed symbols:      {len(data.get('seed_symbols', []))}")
    print(f"Direct deps:       {len(data.get('direct_dependencies', []))}")
    print(f"Direct dependents: {len(data.get('direct_dependents', []))}")
    print(f"Impacted files:    {len(data.get('impacted_files', []))}")
    print(f"Impacted symbols:  {len(data.get('impacted_symbols', []))}")
    print(f"Graph nodes:       {len(data.get('graph_nodes', []))}")
    print(f"Graph edges:       {len(data.get('graph_edges', []))}")
    for item in data.get("top_change_risk_files", [])[:8]:
        if not isinstance(item, dict):
            continue
        file_path = item.get("file_path")
        relationship = item.get("relationship")
        risk_score = item.get("risk_score")
        top_symbol = item.get("top_symbol")
        print(f"  {file_path} [{relationship}] risk={risk_score} symbol={top_symbol}")
    print()


def _print_repository_apply_summary(data: dict[str, Any], *, format: str) -> None:
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    apply_gate = data.get("apply_gate", {})
    validation_summary = data.get("validation_summary", {})
    patch_files = validation_summary.get("patch_files", [])
    print(f"\nMode:            {data.get('mode')}")
    print(f"Applied:         {data.get('applied')}")
    print(f"Gate passed:     {apply_gate.get('passed')}")
    print(f"Policy snapshot: {apply_gate.get('policy_snapshot_id')}")
    print(f"Branch:          {data.get('branch_name')}")
    print(f"Commit:          {data.get('commit_sha')}")
    print(f"Pull request:    {data.get('pull_request_url')}")
    print(f"Checkout path:   {data.get('local_checkout_path')}")
    print(f"Patch files:     {len(patch_files)}")
    for file_path in patch_files[:8]:
        print(f"  {file_path}")
    print()


def _print_repository_capabilities_summary(data: dict[str, Any], *, format: str) -> None:
    if format == "json":
        print_result(data, format)
        return

    supported_languages = data.get("supported_languages")
    support_progress = data.get("support_progress")
    if not isinstance(supported_languages, list):
        supported_languages = []
    if not isinstance(support_progress, dict):
        support_progress = {}

    supported_count = support_progress.get(
        "supported_real_language_count",
        len(supported_languages),
    )
    ranked_target_language_count = support_progress.get("ranked_target_language_count")
    requested_ranked_target_language_count = support_progress.get(
        "requested_ranked_target_language_count"
    )
    available_ranked_real_language_count = support_progress.get(
        "available_ranked_real_language_count"
    )
    progress_label = support_progress.get("progress_label", "unknown")
    print("\nRepository Intelligence Capabilities")
    print(f"Supported:       {supported_count}")
    print(f"Progress:        {progress_label}")
    if (
        isinstance(requested_ranked_target_language_count, int)
        and isinstance(ranked_target_language_count, int)
        and requested_ranked_target_language_count != ranked_target_language_count
    ):
        availability_suffix = ""
        if isinstance(available_ranked_real_language_count, int):
            availability_suffix = (
                f", available ranked real languages {available_ranked_real_language_count}"
            )
        print(
            "Requested rank: "
            f"{requested_ranked_target_language_count} "
            f"(effective {ranked_target_language_count}{availability_suffix})"
        )
    print(f"Languages:       {', '.join(str(language) for language in supported_languages[:16])}")
    if len(supported_languages) > 16:
        print(f"Language total:  {len(supported_languages)}")
    print()


def _print_repository_channel_envelope(data: dict[str, Any], *, format: str) -> None:
    if format == "json":
        print_result(data, format)
        return
    repository = data.get("repository", {})
    pipeline = data.get("pipeline", {})
    agent = data.get("agent", {})
    gate = data.get("gate", {})
    print("\nRepository Channel Envelope")
    print(f"Repository:      {repository.get('id')}")
    print(f"Snapshot:        {pipeline.get('snapshot_id')}")
    print(f"Triage:          {pipeline.get('triage_id')}")
    print(f"Plan:            {pipeline.get('plan_id')}")
    print(f"Simulation:      {pipeline.get('simulation_id')}")
    print(f"Apply:           {pipeline.get('apply_id')}")
    print(f"Runtime:         {agent.get('runtime_kind')}")
    print(f"Provider:        {agent.get('provider')}")
    print(f"Model:           {agent.get('model')}")
    print(f"Gate decision:   {gate.get('decision')}")
    reasons = gate.get("reasons") or []
    print(f"Gate reasons:    {', '.join(str(reason) for reason in reasons) or 'none'}")
    print()


def cmd_repositories_snapshot(repository_id: str, request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Repository snapshot request")
    status, data = api_request("POST", f"/v1/repositories/{repository_id}/snapshots", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    _print_repository_snapshot_summary(data, format=format)


def cmd_repositories_capabilities(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/repositories/capabilities")
    if status != 200:
        _print_api_error_and_exit(status, data)
    _print_repository_capabilities_summary(data, format=format)


def cmd_repositories_get_snapshot(
    repository_id: str,
    snapshot_id: str,
    format: str = "table",
) -> None:
    status, data = api_request("GET", f"/v1/repositories/{repository_id}/snapshots/{snapshot_id}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    _print_repository_snapshot_summary(data, format=format)


def cmd_repositories_triage(repository_id: str, request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Repository triage request")
    status, data = api_request("POST", f"/v1/repositories/{repository_id}/triage", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    _print_repository_triage_summary(data, format=format)


def cmd_repositories_decision_plan(
    repository_id: str,
    request_path: str,
    format: str = "table",
) -> None:
    payload = _load_json_object_file(request_path, context="Repository decision plan request")
    status, data = api_request("POST", f"/v1/repositories/{repository_id}/decision-plans", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    _print_repository_decision_plan_summary(data, format=format)


def cmd_repositories_graph_query(
    repository_id: str,
    request_path: str,
    format: str = "table",
) -> None:
    payload = _load_json_object_file(request_path, context="Repository graph query request")
    status, data = api_request("POST", f"/v1/repositories/{repository_id}/graph-query", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    _print_repository_graph_query_summary(data, format=format)


def cmd_repositories_simulate(repository_id: str, request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Repository simulation request")
    status, data = api_request("POST", f"/v1/repositories/{repository_id}/simulate", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    print_result(data, format)


def cmd_repositories_pipeline(repository_id: str, request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Repository pipeline request")
    status, data = api_request("POST", f"/v1/repositories/{repository_id}/pipeline", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    envelope = build_repository_pipeline_envelope(repository_id=repository_id, response=data)
    _print_repository_channel_envelope(envelope, format=format)


def cmd_repositories_simulate_patch(
    repository_id: str,
    request_path: str,
    format: str = "table",
) -> None:
    payload = _load_json_object_file(request_path, context="Repository simulate-patch request")
    status, data = api_request("POST", f"/v1/repositories/{repository_id}/simulate-patch", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    envelope = build_repository_simulate_patch_envelope(
        repository_id=repository_id,
        snapshot_id=payload.get("snapshot_id"),
        response=data,
    )
    _print_repository_channel_envelope(envelope, format=format)


def cmd_repositories_fix(repository_id: str, request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Repository fix request")
    pipeline_payload = payload.get("pipeline") if isinstance(payload.get("pipeline"), dict) else payload
    apply_payload = payload.get("apply") if isinstance(payload.get("apply"), dict) else {}

    status, pipeline_data = api_request(
        "POST", f"/v1/repositories/{repository_id}/pipeline", pipeline_payload
    )
    if status != 200:
        _print_api_error_and_exit(status, pipeline_data)

    pipeline_envelope = build_repository_pipeline_envelope(
        repository_id=repository_id,
        response=pipeline_data,
    )
    snapshot_id = pipeline_envelope["pipeline"]["snapshot_id"]
    decision_plan_id = pipeline_envelope["pipeline"]["plan_id"]
    simulation_id = pipeline_envelope["pipeline"]["simulation_id"]
    if not decision_plan_id or not simulation_id:
        print(
            "❌ Repository pipeline must complete through simulate before fix can apply.",
            file=sys.stderr,
        )
        sys.exit(1)

    resolved_apply_payload = {
        "snapshot_id": snapshot_id,
        "decision_plan_id": decision_plan_id,
        "simulation_id": simulation_id,
        "mode": apply_payload.get("mode", "patch_only"),
        **{
            key: value
            for key, value in apply_payload.items()
            if key
            in {
                "write_permission",
                "branch_name",
                "commit_message",
                "base_branch",
                "pull_request_title",
                "pull_request_body",
            }
        },
    }
    status, apply_data = api_request(
        "POST", f"/v1/repositories/{repository_id}/apply", resolved_apply_payload
    )
    if status != 200:
        _print_api_error_and_exit(status, apply_data)
    envelope = build_repository_fix_envelope(
        repository_id=repository_id,
        pipeline_response=pipeline_data,
        apply_response=apply_data,
    )
    _print_repository_channel_envelope(envelope, format=format)


def cmd_repositories_apply(repository_id: str, request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Repository apply request")
    status, data = api_request("POST", f"/v1/repositories/{repository_id}/apply", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    _print_repository_apply_summary(data, format=format)


# ─── CLI Commands ─────────────────────────────────────────────────────────────


def cmd_config_set_key(api_key: str, base_url: str | None = None) -> None:
    config = load_config()
    _store_api_key_secure(config, api_key)
    if base_url:
        config["base_url"] = base_url
    save_config(config)
    print(f"✅ API key saved to {CONFIG_FILE}")
    print(f"   Key prefix: {api_key[:12]}...")


def cmd_simulate(
    filepath: str,
    format: str = "table",
    runs: int = 10000,
    seed: int | None = None,
) -> None:
    payload = _normalize_simulation_request(json.loads(Path(filepath).read_text()))
    if runs != 10000:
        payload["runs"] = runs
    if seed is not None:
        payload["seed"] = seed
    status, data = api_request("POST", "/v1/simulate", payload)
    if status == 200:
        print_result(data, format)
    else:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)


def cmd_recommend(filepath: str, format: str = "table") -> None:
    payload = _normalize_recommend_request(json.loads(Path(filepath).read_text()))
    status, data = api_request("POST", "/v1/recommend", payload)
    if status == 200:
        if format == "json":
            print(json.dumps(data, indent=2, default=str))
        else:
            print(
                f"\n✅ Recommended: {data.get('recommended_action')} "
                f"(confidence: {data.get('confidence', 0):.0%})"
            )
            print(f"   {data.get('rationale', '')}")
    else:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)
