"""decision, product, job, webhook, triggers, llm, decisions.

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
_RUNTIME_NOT_RUNNING_MESSAGE = "Algenta Runtime is not running. Start with: de runtime start"


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


def cmd_decision_score(request_path: str, format: str = "table") -> None:
    payload = _normalize_score_request(_load_request_json(request_path))
    status, data = api_request("POST", "/v1/score", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    envelope = data.get("envelope", {})
    breakdown = data.get("score_breakdown", {})
    print(f"\nRecommended:    {envelope.get('recommended_action')}")
    print(f"Score:          {data.get('score')}")
    print(f"Expected value: {envelope.get('expected_value')}")
    print(f"Probability of loss: {envelope.get('probability_of_loss')}")
    print(
        "Breakdown:      "
        f"ev={breakdown.get('expected_value_component')} "
        f"risk={breakdown.get('downside_risk_component')}\n"
    )


def cmd_decision_batch(request_path: str, format: str = "table") -> None:
    payload = _normalize_batch_request(_load_request_json(request_path))
    status, data = api_request("POST", "/v1/batch", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nTotal:          {data.get('total')}")
    print(f"Succeeded:      {data.get('succeeded')}")
    print(f"Failed:         {data.get('failed')}")
    for item in data.get("results", []):
        if item.get("success"):
            envelope = item.get("envelope") or {}
            print(
                f"  #{item.get('index')} success "
                f"action={envelope.get('recommended_action')} "
                f"expected_value={envelope.get('expected_value')}"
            )
        else:
            print(f"  #{item.get('index')} failed error={item.get('error')}")
    print()


def cmd_decision_compare(request_path: str, format: str = "table") -> None:
    payload = _normalize_compare_request(_load_request_json(request_path))
    status, data = api_request("POST", "/v1/compare", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    margin = data.get("margin", {})
    print(f"\nWinner:         {data.get('winner')}")
    print(
        "Margin:         "
        f"ev={margin.get('expected_value_delta')} "
        f"pol={margin.get('probability_of_loss_delta')} "
        f"score={margin.get('score_delta')}"
    )
    for scenario in data.get("scenarios", []):
        envelope = scenario.get("envelope") or {}
        delta = scenario.get("delta_vs_best") or {}
        print(
            f"  {scenario.get('name')}: "
            f"action={envelope.get('recommended_action')} "
            f"expected_value={envelope.get('expected_value')} "
            f"pol={envelope.get('probability_of_loss')} "
            f"delta_score={delta.get('score_delta')}"
        )
    print()


def cmd_product_decision(request_path: str, format: str = "table") -> None:
    payload = _load_request_json(request_path)
    status, data = api_request("POST", "/v1/decision", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nDecision ID:       {data.get('decision_id')}")
    print(f"Action:            {data.get('action')}")
    print(f"Confidence:        {data.get('confidence')}")
    print(f"Expected outcome:  {data.get('expected_outcome')}")
    print(f"Probability loss:  {data.get('probability_of_loss')}")
    print(f"Reasoning:         {data.get('reasoning')}\n")


def cmd_product_agent_run(request_path: str, format: str = "table") -> None:
    payload = _load_request_json(request_path)
    status, data = api_request("POST", "/v1/agent/run", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nRun ID:            {data.get('run_id')}")
    print(f"Status:            {data.get('status')}")
    print(f"Tools used:        {', '.join(data.get('tools_used', []))}")
    print(f"Steps:             {len(data.get('steps', []))}")
    print(f"Latency ms:        {data.get('latency_ms')}\n")


def cmd_product_optimize(request_path: str, format: str = "table") -> None:
    payload = _load_request_json(request_path)
    status, data = api_request("POST", "/v1/optimize", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nOptimization ID:   {data.get('optimization_id')}")
    print(f"Status:            {data.get('status')}")
    print(f"Objective value:   {data.get('objective_value')}")
    print(f"Optimal values:    {json.dumps(data.get('optimal_values', {}), default=str)}")
    print(f"Iterations run:    {data.get('iterations_run')}\n")


def cmd_product_retrieve(request_path: str, format: str = "table") -> None:
    payload = _load_request_json(request_path)
    status, data = api_request("POST", "/v1/retrieve", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nRetrieval ID:      {data.get('retrieval_id')}")
    print(f"Query:             {data.get('query')}")
    print(f"Results:           {len(data.get('results', []))}")
    for item in data.get("results", []):
        print(
            f"  #{item.get('rank')} {item.get('document_id')} "
            f"score={item.get('relevance_score')}"
        )
    print()


def cmd_product_forecast(request_path: str, format: str = "table") -> None:
    payload = _load_request_json(request_path)
    status, data = api_request("POST", "/v1/forecast", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nForecast ID:       {data.get('forecast_id')}")
    print(f"Metric:            {data.get('metric')}")
    print(f"Forecast mean:     {data.get('forecast_mean')}")
    print(f"Total change pct:  {data.get('total_change_pct')}")
    print(f"Periods:           {len(data.get('periods', []))}\n")


def cmd_job_submit(filepath: str, callback_url: str | None = None) -> None:
    payload = _normalize_simulation_request(json.loads(Path(filepath).read_text()))
    body: dict[str, Any] = {"request": payload}
    if callback_url:
        body["callback_url"] = callback_url
    status, data = api_request("POST", "/v1/jobs", body)
    if status == 202:
        print(f"✅ Job submitted: {data['job_id']}")
        print(f"   Status: {data['status']}")
        print(f"   Poll: {data['poll_url']}")
        print(f"\nTo wait for completion: de job wait {data['job_id']}")
    else:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)


def cmd_job_status(job_id: str, format: str = "table") -> None:
    status, data = api_request("GET", f"/v1/jobs/{job_id}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"Job ID: {data['job_id']}")
        print(f"Status: {data['status']}")
        if data.get("error_message"):
            print(f"Error:  {data['error_message']}")


def cmd_job_result(job_id: str, format: str = "table") -> None:
    status, data = api_request("GET", f"/v1/jobs/{job_id}/result")
    if status == 200:
        print_result(data, format)
    else:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)


def cmd_job_list(
    page: int = 1,
    limit: int = 25,
    status_filter: str | None = None,
    format: str = "table",
) -> None:
    query_params: dict[str, Any] = {"page": page, "limit": limit}
    if status_filter:
        query_params["status"] = status_filter
    status, data = api_request("GET", f"/v1/jobs/list?{urlencode(query_params)}")
    if status != 200:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    jobs = data.get("jobs", [])
    print(
        f"Jobs ({data.get('total', len(jobs))} total, page {data.get('page', page)}/{data.get('pages', 1)})"
    )
    for job in jobs:
        print(
            "  "
            f"{job.get('job_id')}  "
            f"{job.get('status')}  "
            f"queue={job.get('queue_name')}  "
            f"retries={job.get('retry_count')}"
        )


def cmd_job_cancel(job_id: str, format: str = "table") -> None:
    status, data = api_request("POST", f"/v1/jobs/{job_id}/cancel")
    if status == 200:
        print_result(data, format)
    else:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)


def cmd_job_wait(job_id: str, timeout: int = 300, format: str = "table") -> None:
    print(f"Waiting for job {job_id[:8]}... (timeout: {timeout}s)")
    deadline = time.time() + timeout
    while time.time() < deadline:
        status_code, status_data = api_request("GET", f"/v1/jobs/{job_id}")
        if status_code != 200:
            print()
            _print_api_error_and_exit(status_code, status_data)
        job_status = status_data.get("status", "unknown")
        print(f"  [{time.strftime('%H:%M:%S')}] status: {job_status}", end="\r")
        if job_status == "completed":
            print("\n✅ Job completed!")
            result_status, result = api_request("GET", f"/v1/jobs/{job_id}/result")
            if result_status != 200:
                _print_api_error_and_exit(result_status, result)
            print_result(result, format)
            return
        elif job_status in ("failed", "cancelled"):
            print(f"\n❌ Job {job_status}: {status_data.get('error_message', 'no details')}")
            sys.exit(1)
        time.sleep(2)
    print(f"\n❌ Timeout after {timeout}s")
    sys.exit(1)


def cmd_webhook_test(callback_url: str, format: str = "table") -> None:
    status, data = api_request("POST", "/v1/webhooks/test", {"callback_url": callback_url})
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nSuccess:      {data.get('success')}")
    print(f"Status code:  {data.get('status_code')}")
    print(f"Message:      {data.get('message')}\n")


def cmd_triggers_register(request_path: str, format: str = "table") -> None:
    payload = _load_request_json(request_path)
    status, data = api_request("POST", "/v1/triggers", payload)
    if status != 201:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    condition = data.get("condition") or {}
    print(f"\nTrigger ID:    {data.get('trigger_id')}")
    print(f"Name:          {data.get('name')}")
    print(f"Status:        {data.get('status')}")
    print(f"Condition:     {condition.get('metric_hint')} {condition.get('direction')} {condition.get('threshold')}")
    print(f"Auto execute:  {data.get('auto_execute')}\n")


def cmd_triggers_list(
    format: str = "table",
    *,
    status_filter: str = "all",
    page: int | None = None,
    limit: int | None = None,
) -> None:
    query_params: dict[str, Any] = {}
    if status_filter != "all":
        query_params["status"] = status_filter
    if page is not None:
        query_params["page"] = page
    if limit is not None:
        query_params["limit"] = limit
    path = "/v1/triggers"
    if query_params:
        path = f"{path}?{urlencode(query_params)}"
    status, data = api_request("GET", path)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    triggers = data.get("triggers", [])
    print(
        f"\nTriggers ({data.get('total', len(triggers))} total, page {data.get('page', 1)}/{data.get('pages', 1)})"
    )
    for trigger in triggers:
        condition = trigger.get("condition") or {}
        print(
            f"  - {trigger.get('trigger_id')}  [{trigger.get('status')}] "
            f"{trigger.get('name')}  "
            f"{condition.get('metric_hint')} {condition.get('direction')} {condition.get('threshold')}"
        )
    print()


def cmd_triggers_fire(trigger_id: str, format: str = "table", *, force: bool = False) -> None:
    status, data = api_request("POST", f"/v1/triggers/{trigger_id}/fire", {"force": force})
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nTrigger ID:        {data.get('trigger_id')}")
    print(f"Condition met:     {data.get('condition_met')}")
    print(f"Fired:             {data.get('fired')}")
    print(f"Simulation run ID: {data.get('simulation_run_id')}")
    print(f"Recommended:       {data.get('recommended_action')}")
    print(f"Message:           {data.get('message')}\n")


def cmd_triggers_pause(trigger_id: str, format: str = "table", *, paused: bool = True) -> None:
    paused_value = "true" if paused else "false"
    status, data = api_request("PATCH", f"/v1/triggers/{trigger_id}/pause?paused={paused_value}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nTrigger ID:  {data.get('trigger_id')}")
    print(f"Status:      {data.get('status')}\n")


def cmd_triggers_delete(trigger_id: str, format: str = "table") -> None:
    status, data = api_request("DELETE", f"/v1/triggers/{trigger_id}")
    if status != 204:
        _print_api_error_and_exit(status, data)
    payload = {"trigger_id": trigger_id, "deleted": True}
    if format == "json":
        print(json.dumps(payload, indent=2, default=str))
        return
    print(f"\nTrigger deleted: {trigger_id}\n")


def cmd_llm_models(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/models")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    models = data.get("data", [])
    print(f"\nAlgenta models ({len(models)} available)\n")
    for model in models:
        capabilities = ", ".join(model.get("capabilities", []))
        endpoints = ", ".join(model.get("supported_endpoints", []))
        print(f"  {model.get('id')}  [{model.get('runtime_module')}]")
        print(f"    capabilities: {capabilities}")
        print(f"    endpoints:    {endpoints}")
        provider_backend = model.get("provider_backend")
        if provider_backend:
            print(f"    provider:     {provider_backend}")
            if model.get("routing_targets"):
                print(
                    "    declared:     "
                    + ", ".join(str(item) for item in model.get("routing_targets", []))
                )
            if model.get("resolved_routing_targets"):
                print(
                    "    resolved:     "
                    + ", ".join(
                        str(item) for item in model.get("resolved_routing_targets", [])
                    )
                )
            if model.get("chat_routing_targets"):
                print(
                    "    chat route:   "
                    + ", ".join(str(item) for item in model.get("chat_routing_targets", []))
                )
            if model.get("resolved_chat_routing_targets"):
                print(
                    "    chat leafs:   "
                    + ", ".join(
                        str(item)
                        for item in model.get("resolved_chat_routing_targets", [])
                    )
                )
            if model.get("embedding_routing_targets"):
                print(
                    "    embed route:  "
                    + ", ".join(
                        str(item) for item in model.get("embedding_routing_targets", [])
                    )
                )
            if model.get("resolved_embedding_routing_targets"):
                print(
                    "    embed leafs:  "
                    + ", ".join(
                        str(item)
                        for item in model.get("resolved_embedding_routing_targets", [])
                    )
                )
            if model.get("required_provider_headers"):
                print(
                    "    headers:      "
                    + ", ".join(
                        str(item) for item in model.get("required_provider_headers", [])
                    )
                )
            if model.get("chat_required_provider_headers"):
                print(
                    "    chat headers: "
                    + ", ".join(
                        str(item)
                        for item in model.get("chat_required_provider_headers", [])
                    )
                )
            if model.get("embedding_required_provider_headers"):
                print(
                    "    embed headers:"
                    + " "
                    + ", ".join(
                        str(item)
                        for item in model.get("embedding_required_provider_headers", [])
                    )
                )
            if model.get("provider_auth_env_vars"):
                print(
                    "    auth envs:    "
                    + ", ".join(
                        str(item) for item in model.get("provider_auth_env_vars", [])
                    )
                )
            if model.get("chat_provider_auth_env_vars"):
                print(
                    "    chat envs:    "
                    + ", ".join(
                        str(item)
                        for item in model.get("chat_provider_auth_env_vars", [])
                    )
                )
            if model.get("embedding_provider_auth_env_vars"):
                print(
                    "    embed envs:   "
                    + ", ".join(
                        str(item)
                        for item in model.get("embedding_provider_auth_env_vars", [])
                    )
                )
            if model.get("routing_fallback_policy") is not None:
                print(f"    fallback:     {model.get('routing_fallback_policy')}")
            if model.get("chat_routing_fallback_policy") is not None:
                print(
                    "    chat failover:"
                    f" {model.get('chat_routing_fallback_policy')}"
                )
            if model.get("embedding_routing_fallback_policy") is not None:
                print(
                    "    embed failover:"
                    f" {model.get('embedding_routing_fallback_policy')}"
                )
            if model.get("routing_fallback_on"):
                print(
                    "    on errors:    "
                    + ", ".join(str(item) for item in model.get("routing_fallback_on", []))
                )
            if model.get("chat_routing_fallback_on"):
                print(
                    "    chat on:      "
                    + ", ".join(
                        str(item) for item in model.get("chat_routing_fallback_on", [])
                    )
                )
            if model.get("embedding_routing_fallback_on"):
                print(
                    "    embed on:     "
                    + ", ".join(
                        str(item)
                        for item in model.get("embedding_routing_fallback_on", [])
                    )
                )
            if model.get("routing_max_attempts") is not None:
                print(f"    attempts:     {model.get('routing_max_attempts')}")
            if model.get("chat_routing_max_attempts") is not None:
                print(f"    chat tries:   {model.get('chat_routing_max_attempts')}")
            if model.get("embedding_routing_max_attempts") is not None:
                print(f"    embed tries:  {model.get('embedding_routing_max_attempts')}")
            if model.get("timeout_seconds") is not None:
                print(f"    timeout:      {model.get('timeout_seconds')}s")
            if model.get("chat_timeout_seconds") is not None:
                print(f"    chat timeout: {model.get('chat_timeout_seconds')}s")
            if model.get("embedding_timeout_seconds") is not None:
                print(f"    embed timeout: {model.get('embedding_timeout_seconds')}s")
            print(f"    auth ready:   {bool(model.get('provider_auth_configured', False))}")
            print(f"    chat ready:   {bool(model.get('chat_provider_auth_configured', False))}")
            print(
                f"    embed ready:  {bool(model.get('embedding_provider_auth_configured', False))}"
            )
    print()


def cmd_llm_resolve_artifact(request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Artifact bridge resolve request")
    status, data = api_request("POST", "/v1/artifacts/resolve", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nBackend:         {data.get('backend')}")
    print(f"Artifact backend:{' ' if data.get('artifact_backend') else ''} {data.get('artifact_backend')}")
    print(f"Repo:            {data.get('repo_id')}")
    print(f"Filename:        {data.get('filename')}")
    print(f"Revision:        {data.get('revision') or '(default)'}")
    print(f"Status:          {data.get('status')}")
    print(f"Cache root:      {data.get('cache_root') or '(none)'}")
    print(f"Local only:      {data.get('local_files_only')}")
    print(f"Auth configured: {data.get('auth_configured')}")
    print(f"Auth env used:   {data.get('auth_env_var_used') or '(none)'}")
    print(f"Resolved path:   {data.get('resolved_path') or '(not cached)'}\n")


def cmd_llm_tokenize(text: str, model: str = "text.tokenizer", format: str = "table") -> None:
    status, data = api_request("POST", "/v1/tokenize", {"input": text, "model": model})
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nModel:          {data.get('model')}")
    print(f"Tokenizer kind: {data.get('tokenizer_kind')}")
    print(f"Token count:    {data.get('token_count')}")
    print(f"Tokens:         {', '.join(data.get('tokens', []))}\n")


def cmd_llm_count_tokens(
    text: str,
    model: str = "text.tokenizer",
    format: str = "table",
) -> None:
    status, data = api_request("POST", "/v1/count_tokens", {"input": text, "model": model})
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nModel:          {data.get('model')}")
    print(f"Tokenizer kind: {data.get('tokenizer_kind')}")
    print(f"Token count:    {data.get('token_count')}\n")


def cmd_llm_chat(request_path: str, format: str = "table", *, stream: bool = False) -> None:
    payload = _load_request_json(request_path)
    if stream:
        _print_chat_stream(
            _stream_payloads("POST", "/v1/chat/completions", {**payload, "stream": True}),
            format=format,
        )
        return
    status, data = api_request("POST", "/v1/chat/completions", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    choice = (data.get("choices") or [{}])[0]
    message = choice.get("message", {})
    usage = data.get("usage", {})
    print(f"\nCompletion ID:  {data.get('id')}")
    print(f"Model:          {data.get('model')}")
    print(f"Finish reason:  {choice.get('finish_reason')}")
    print(f"Assistant:      {message.get('content') or ''}")
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        print(f"Tool calls:     {len(tool_calls)}")
        for tool_call in tool_calls:
            function = tool_call.get("function", {})
            print(f"  - {tool_call.get('id')}: {function.get('name')}({function.get('arguments')})")
    print(
        "Usage:          "
        f"prompt={usage.get('prompt_tokens')} "
        f"completion={usage.get('completion_tokens')} "
        f"total={usage.get('total_tokens')}\n"
    )


def cmd_llm_responses(request_path: str, format: str = "table", *, stream: bool = False) -> None:
    payload = _load_request_json(request_path)
    if stream:
        _print_response_stream(
            _stream_payloads("POST", "/v1/responses", {**payload, "stream": True}),
            format=format,
        )
        return
    status, data = api_request("POST", "/v1/responses", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    usage = data.get("usage", {})
    print(f"\nResponse ID:    {data.get('id')}")
    print(f"Model:          {data.get('model')}")
    print(f"Status:         {data.get('status')}")
    print(f"Output items:   {len(data.get('output', []))}")
    print(
        "Usage:          "
        f"prompt={usage.get('prompt_tokens')} total={usage.get('total_tokens')}\n"
    )


def cmd_llm_embeddings(request_path: str, format: str = "table") -> None:
    payload = _load_request_json(request_path)
    status, data = api_request("POST", "/v1/embeddings", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    usage = data.get("usage", {})
    vectors = data.get("data", [])
    print(f"\nModel:          {data.get('model')}")
    print(f"Dimensions:     {data.get('dimensions')}")
    print(f"Vectors:        {len(vectors)}")
    print(
        "Usage:          "
        f"prompt={usage.get('prompt_tokens')} total={usage.get('total_tokens')}\n"
    )


def cmd_llm_embedding_similarity(request_path: str, format: str = "table") -> None:
    payload = _load_request_json(request_path)
    status, data = api_request("POST", "/v1/embeddings/similarity", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nModel:            {data.get('model')}")
    print(f"Similarity metric:{' '}{data.get('similarity_metric')}")
    print(f"Dimension:        {data.get('dimension')}")
    print(f"Score:            {data.get('score')}\n")


def cmd_llm_rerank(request_path: str, format: str = "table") -> None:
    payload = _load_request_json(request_path)
    status, data = api_request("POST", "/v1/rerank", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nModel:             {data.get('model')}")
    print(f"Similarity metric: {data.get('similarity_metric')}")
    print(
        f"Documents:         {data.get('returned_documents')} returned / "
        f"{data.get('total_documents')} total"
    )
    for item in data.get("data", []):
        print(f"  #{item.get('rank')} {item.get('id')} score={item.get('score')}")
    print()


def cmd_decision_plan(request_path: str, format: str = "table") -> None:
    payload = _load_request_json(request_path)
    status, data = api_request("POST", "/v1/decisions/plan", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    risk = data.get("risk", {})
    print(f"\nRecommended:    {data.get('recommended_action')}")
    print(f"Confidence:     {data.get('confidence'):.2f}")
    print(f"Expected value: {data.get('expected_value')}")
    print(
        f"Risk:           p5={risk.get('p5')} "
        f"p95={risk.get('p95')} "
        f"pol={risk.get('probability_of_loss')}"
    )
    print(f"Rationale:      {data.get('rationale')}\n")


def cmd_decisions_log(request_path: str, format: str = "table") -> None:
    payload = _load_request_json(request_path)
    status, data = api_request("POST", "/v1/decisions", payload)
    if status != 201:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nDecision ID:     {data.get('id')}")
    print(f"Chosen action:   {data.get('chosen_action')}")
    print(f"Confidence:      {data.get('confidence')}")
    print(f"Expected value:  {data.get('expected_value')}")
    print(f"Policy snapshot: {data.get('policy_snapshot_id')}")
    print(f"Schema snapshot: {data.get('schema_snapshot_id')}")
    print(f"Manifest:        {data.get('manifest_version')}")
    print(f"Created at:      {data.get('created_at')}\n")


def cmd_decisions_list(
    *,
    page: int = 1,
    limit: int | None = None,
    page_size: int | None = None,
    with_outcome_only: bool = False,
    format: str = "table",
) -> None:
    params: list[str] = [f"page={page}"]
    if limit is not None:
        params.append(f"limit={limit}")
    if page_size is not None:
        params.append(f"page_size={page_size}")
    if with_outcome_only:
        params.append("with_outcome_only=true")
    status, data = api_request("GET", f"/v1/decisions?{'&'.join(params)}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(
        f"\nPage: {data.get('page')} / {data.get('pages')}  "
        f"Total: {data.get('total')}  Limit: {data.get('limit')}"
    )
    for item in data.get("decisions", []):
        print(
            f"  {item.get('id')} action={item.get('chosen_action')} "
            f"expected={item.get('expected_value')} actual={item.get('actual_outcome')} "
            f"delta={item.get('outcome_delta')} "
            f"policy={item.get('policy_snapshot_id')} "
            f"schema={item.get('schema_snapshot_id')}"
        )
    print()


def cmd_decisions_get(decision_id: str, format: str = "table") -> None:
    status, data = api_request("GET", f"/v1/decisions/{decision_id}")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nDecision ID:     {data.get('id')}")
    print(f"Chosen action:   {data.get('chosen_action')}")
    print(f"Context:         {data.get('context')}")
    print(f"Expected value:  {data.get('expected_value')}")
    print(f"Actual outcome:  {data.get('actual_outcome')}")
    print(f"Outcome delta:   {data.get('outcome_delta')}")
    print(f"Execution:       {data.get('execution_status')}\n")
    print(f"Policy snapshot: {data.get('policy_snapshot_id')}")
    print(f"Schema snapshot: {data.get('schema_snapshot_id')}")
    print(f"Manifest:        {data.get('manifest_version')}\n")


def cmd_decisions_outcome(decision_id: str, request_path: str, format: str = "table") -> None:
    payload = _load_request_json(request_path)
    status, data = api_request("PATCH", f"/v1/decisions/{decision_id}/outcome", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nDecision ID:     {data.get('id')}")
    print(f"Actual outcome:  {data.get('actual_outcome')}")
    print(f"Outcome delta:   {data.get('outcome_delta')}")
    print(f"Policy snapshot: {data.get('policy_snapshot_id')}")
    print(f"Schema snapshot: {data.get('schema_snapshot_id')}")
    print(f"Manifest:        {data.get('manifest_version')}")
    print(f"Recorded at:     {data.get('outcome_recorded_at')}\n")


def cmd_decisions_execute(decision_id: str, request_path: str, format: str = "table") -> None:
    payload = _load_request_json(request_path)
    status, data = api_request("POST", f"/v1/decisions/{decision_id}/execute", payload)
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nDecision ID:     {data.get('decision_id')}")
    print(f"Webhook URL:     {data.get('webhook_url')}")
    print(f"Status:          {data.get('execution_status')}")
    print(f"Response code:   {data.get('response_code')}")
    print(f"Executed at:     {data.get('executed_at')}")
    print(f"Policy snapshot: {data.get('policy_snapshot_id')}\n")
    print(f"Schema snapshot: {data.get('schema_snapshot_id')}")
    print(f"Manifest:        {data.get('manifest_version')}\n")


def cmd_decisions_delete(decision_id: str, format: str = "table") -> None:
    status, data = api_request("DELETE", f"/v1/decisions/{decision_id}")
    if status != 204:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps({"decision_id": decision_id, "deleted": True}, indent=2, default=str))
        return
    print(f"\nDecision deleted: {decision_id}\n")

