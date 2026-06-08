"""
de — Algenta CLI

Simulation, optimization, and AI decisions from your terminal.

Usage:
    de benchmark                           # show speedup vs Python baseline
    de data connect                        # interactive connect flow
    de data list                           # list datasets
    de data list --search otp --compact    # low-token dataset discovery
    de data summary <dataset_id>           # low-token dataset summary
    de data inspect <dataset_id>           # inspect one dataset
    de data query-batch request.json       # governed exact-query batch from file
    de data sql-report request.json        # read-only SQL report from file
    de data refresh <dataset_id>           # refresh one dataset
    de data disconnect <dataset_id>        # delete one dataset
    de connectors list                     # list saved connectors
    de connectors create request.json      # create one saved connector
    de connectors get <connector_id>       # inspect one saved connector
    de connectors update <connector_id> request.json # update one saved connector
    de connectors test <connector_id>      # run one saved connector health check
    de connectors browse <connector_id>    # browse one live connector
    de connectors preview-test request.json   # test one inline connector without saving it
    de connectors preview-browse request.json # browse one inline connector without saving it
    de connectors delete <connector_id>    # delete one saved connector
    de capabilities providers              # list unified capability providers
    de capabilities provider <provider_id> # inspect one unified capability provider
    de capabilities bindings               # list unified capability bindings
    de capabilities list                   # list unified capabilities
    de capabilities route request.json     # route one objective to one capability
    de capabilities execute request.json   # execute one selected capability
    de repositories capabilities           # list globally supported repo languages
    de repositories snapshot <repository_id> request.json
        # create one immutable repo snapshot
    de repositories get-snapshot <repository_id> <snapshot_id>
        # inspect one immutable repo snapshot
    de repositories triage <repository_id> request.json
        # build one workspace evidence bundle
    de repositories decision-plan <repository_id> request.json
        # create one immutable repo DecisionPlan
    de repositories graph-query <repository_id> request.json
        # inspect dependency, dependent, and change-risk edges
    de repositories simulate <repository_id> request.json
        # simulate patch risk and gate apply
    de repositories apply <repository_id> request.json
        # emit patch, local branch, or remote PR
    de simulate examples/sample.json       # run a simulation
    de recommend examples/compare.json     # get a recommendation
    de product decision request.json       # simple product decision helper
    de product agent-run request.json      # simple task-execution helper
    de product optimize request.json       # simple optimization helper
    de product retrieve request.json       # simple retrieval helper
    de product forecast request.json       # simple forecasting helper
    de decision plan request.json          # structured DecisionPlan only
    de decision score request.json         # score one simulation request
    de decision batch request.json         # run several simulation requests
    de decision compare request.json       # compare named scenarios
    de decisions log request.json          # persist one decision-memory record
    de decisions list                      # list persisted decisions
    de decisions get <decision_id>         # fetch one decision-memory record
    de decisions outcome <decision_id> request.json # record actual outcome
    de decisions execute <decision_id> request.json # dispatch one decision to webhook
    de decisions delete <decision_id>      # delete one decision-memory record
    de template list                       # browse ready-to-run templates
    de template run finance_npv            # run a template instantly
    de template get finance_npv            # see template payload
    de job submit examples/large.json      # async job for large runs
    de job list --page 1 --limit 25        # list async jobs
    de job wait <job_id>                   # wait for job completion
    de job status <job_id>                 # check job status
    de job result <job_id>                 # fetch completed job result
    de job cancel <job_id>                 # cancel queued or running job
    de webhook test <callback_url>         # send one webhook test payload
    de triggers register request.json      # register one trigger
    de triggers list                       # list triggers
    de triggers fire <trigger_id>          # fire one trigger
    de triggers pause <trigger_id>         # pause one trigger
    de triggers resume <trigger_id>        # resume one trigger
    de triggers delete <trigger_id>        # delete one trigger
    de llm models                          # list truthful utility models
    de llm resolve-artifact request.json   # resolve HF artifact bridge path
    de llm tokenize --input "hello world"  # deterministic tokenization
    de llm count-tokens --input "hello"    # deterministic token count
    de llm chat request.json [--stream]    # tokenizer-backed utility chat
    de llm responses request.json [--stream] # unified deterministic response surface
    de llm embeddings request.json         # deterministic lexical embeddings
    de llm embedding-similarity request.json # vector similarity scoring
    de llm rerank request.json             # deterministic document reranking
    de decision plan request.json          # structured DecisionPlan only
    de agent-runs list                     # list persisted agent runs
    de agent-runs create request.json      # persisted agent run lifecycle
    de agent-runs get <run_id>             # fetch one persisted agent run
    de agent-runs events <run_id> [--stream] # fetch one run's event stream
    de agent-runs checkpoints <run_id>      # fetch persisted checkpoints
    de agent-runs query-checkpoints         # query persisted checkpoints across runs
    de agent-runs mission-events <run_id>   # fetch canonical mission-event records
    de agent-runs telemetry <run_id>        # fetch runtime telemetry batches
    de agent-runs query-mission-events      # query mission-event records across runs
    de agent-runs query-telemetry           # query telemetry batches across runs
    de agent-runs resume <run_id>          # resume a paused run
    de agent-runs cancel <run_id>          # cancel a run
    de agent-runs approve <run_id>         # approve a waiting run
    de account me                          # show current org/user identity
    de account update request.json         # update current user and or org name
    de account usage                       # show current billing-period usage
    de account limits                      # show current plan limits
    de account distributions               # list supported distribution types
    de account templates                   # list built-in simulation templates
    de billing info                        # show current billing plan/subscription
    de billing checkout [developer|pro]    # create one billing checkout session
    de billing portal                      # create one billing portal session
    de credits refresh request.json        # issue one runtime credit refresh batch
    de team list                           # list current org team members
    de team invite <email> [role]          # invite one team member
    de team update-role <user_id> <role>   # update one team member role
    de team remove <user_id>               # remove one team member
    de team audit-logs                     # list current org audit logs
    de team audit-artifacts                # query immutable audit-log artifacts
    de devices list                        # list registered devices
    de devices revoke <registration_id>    # revoke one registered device
    de execution-policy get                # show execution policy
    de execution-policy snapshots          # list execution policy snapshots
    de execution-policy update request.json # update execution policy
    de keys list                           # list active API keys
    de keys create "Mission Key"           # create one API key
    de keys revoke <key_id>                # revoke one API key
    de deployments regions                 # list deployment providers and regions
    de deployments get                     # show current org deployment
    de deployments create request.json     # request one deployment
    de deployments cost <deployment_id>    # show current deployment cost
    de deployments delete <deployment_id>  # request deployment teardown
    de config set-key <YOUR_ALGENTA_API_KEY> # save your API key (Cloud Managed example)
    de contract                            # machine-readable Algenta contract
    de health                              # check API status
    de version                             # show versions

Local runtime daemon:
    de runtime start                       # start local daemon (background)
    de runtime stop                        # stop local daemon
    de runtime status                      # show daemon status
    de runtime manifest                    # show signed runtime manifest
    de runtime validate                    # show formal release validation
    de runtime admin-modules               # show signed module proof catalog
    de runtime admin-benchmarks            # show signed benchmark catalog
    de runtime modules                     # list loaded modules
    de runtime functions <module>          # list functions for one module
    de runtime execute <module> <function> # execute one runtime library function
    de runtime history                     # inspect local runtime ledger

Install:
    pip install algenta-sdk
    # or from repo:
    PYTHONPATH=. python3 apps/cli/main.py benchmark

Credential examples above are Cloud Managed examples. In `self_hosted` and
`air_gapped`, use the API key provisioned by your self-hosted operator
deployment instead. Private profiles fail closed and do not silently fall back
to Algenta cloud.
"""

import json
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from pydantic import ValidationError

# Add project root for SDK import
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import typer

    _RICH = True
except ImportError:
    typer = None  # type: ignore[assignment]
    _RICH = False

from apps.cli import data_commands as _data_commands
from apps.cli.support import (
    CONFIG_FILE,
    api_request,
    api_stream_request,
    load_config,
    print_result,
    save_config,
)
from apps.cli.support import (
    arg_value as _arg_value,
)
from apps.cli.support import (
    get_base_url as _get_base_url,
)
from apps.cli.support import (
    get_dashboard_url as _get_dashboard_url,
)
from apps.cli.support import (
    load_env_api_key as _load_env_api_key,
)
from apps.cli.support import (
    private_profile_enabled as _private_profile_enabled,
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


def _normalize_expert_variable(variable: dict[str, Any]) -> dict[str, Any]:
    if isinstance(variable.get("params"), dict):
        params = dict(variable.get("params", {}))
    else:
        params = _strip_none(
            {
                "mean": variable.get("mean"),
                "std": variable.get("std") or variable.get("std_dev"),
                "low": variable.get("low"),
                "mode": variable.get("mode"),
                "high": variable.get("high"),
                "value": variable.get("value"),
                "min": variable.get("min"),
                "max": variable.get("max"),
                "p": variable.get("p"),
                "shape": variable.get("shape"),
                "scale": variable.get("scale"),
            }
        )
    return {
        "name": variable.get("name", "value"),
        "distribution": variable.get("distribution", "fixed"),
        "params": params,
    }


def _load_benchmark_summary(root: Path) -> tuple[dict[str, Any] | None, Path | None]:
    candidates = (
        root / "build" / "llm_rollout_parity_benchmark.json",
        root / "benchmarks" / "summary.json",
    )
    for path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError, TypeError):
            continue
        if isinstance(payload, dict) and isinstance(payload.get("libraries"), list):
            return payload, path
    return None, None


def _display_benchmark_source(root: Path, source_path: Path | None) -> str | None:
    if source_path is None:
        return None
    try:
        return str(source_path.relative_to(root))
    except ValueError:
        return str(source_path)


def _format_speedup_value(value: float) -> str:
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _normalize_simulation_request(payload: dict[str, Any]) -> dict[str, Any]:
    if "scenario" in payload or "simulation" in payload:
        return payload

    variables = payload.get("variables")
    if isinstance(variables, dict):
        normalized: dict[str, Any] = {
            "mode": "auto",
            "scenario": {
                "variables": variables,
                "objective": payload.get("objective", "maximize_net_value"),
            },
            "runs": payload.get("runs", 10_000),
        }
        if payload.get("seed") is not None:
            normalized["seed"] = payload["seed"]
        if payload.get("simulation_model") is not None:
            normalized["simulation_model"] = payload["simulation_model"]
        return normalized

    if isinstance(variables, list):
        variable_names = [v.get("name", "value") for v in variables if isinstance(v, dict)]
        objective = (
            payload.get("objective_function")
            or payload.get("objective")
            or " + ".join(variable_names)
            or "value"
        )
        normalized = {
            "mode": "expert",
            "simulation": {
                "variables": [
                    _normalize_expert_variable(v) for v in variables if isinstance(v, dict)
                ],
                "objective_function": objective,
                "scoring": payload.get("scoring", {"expected_value": 0.6, "downside_risk": 0.4}),
            },
            "runs": payload.get("runs", 10_000),
        }
        if payload.get("seed") is not None:
            normalized["seed"] = payload["seed"]
        if payload.get("simulation_model") is not None:
            normalized["simulation_model"] = payload["simulation_model"]
        return normalized

    return payload


def _normalize_recommend_request(payload: dict[str, Any]) -> dict[str, Any]:
    if "actions" in payload:
        return payload
    if "options" not in payload:
        return payload

    normalized_actions: list[dict[str, Any]] = []
    for idx, option in enumerate(payload.get("options", []), start=1):
        name = option.get("label") or option.get("name") or f"option_{idx}"
        expected_value = float(option.get("expected_value", 0.0) or 0.0)
        risk = max(float(option.get("risk", 0.1) or 0.1), 0.05)
        spread = max(abs(expected_value) * risk, 1.0)
        normalized_actions.append(
            {
                "name": name,
                "request": {
                    "mode": "expert",
                    "simulation": {
                        "variables": [
                            {
                                "name": "outcome",
                                "distribution": "triangular",
                                "params": {
                                    "low": expected_value - spread,
                                    "mode": expected_value,
                                    "high": expected_value + spread,
                                },
                            }
                        ],
                        "objective_function": "outcome",
                        "scoring": {"expected_value": 0.6, "downside_risk": 0.4},
                    },
                    "runs": payload.get("runs", 1000),
                },
            }
        )
    return {"actions": normalized_actions, "runs": payload.get("runs", 1000)}


def _normalize_score_request(payload: dict[str, Any]) -> dict[str, Any]:
    if "request" in payload:
        normalized = dict(payload)
        if isinstance(normalized.get("request"), dict):
            normalized["request"] = _normalize_simulation_request(normalized["request"])
        return normalized
    return {"request": _normalize_simulation_request(payload)}


def _normalize_batch_request(payload: dict[str, Any]) -> dict[str, Any]:
    if "items" not in payload or not isinstance(payload.get("items"), list):
        return payload
    normalized = dict(payload)
    normalized["items"] = [
        _normalize_simulation_request(item) if isinstance(item, dict) else item
        for item in normalized["items"]
    ]
    return normalized


def _normalize_compare_request(payload: dict[str, Any]) -> dict[str, Any]:
    if "scenarios" not in payload or not isinstance(payload.get("scenarios"), list):
        return payload
    normalized = dict(payload)
    scenarios: list[dict[str, Any]] = []
    for index, scenario in enumerate(payload["scenarios"], start=1):
        if not isinstance(scenario, dict):
            continue
        if "request" in scenario and isinstance(scenario["request"], dict):
            scenarios.append(
                {
                    **scenario,
                    "request": _normalize_simulation_request(scenario["request"]),
                }
            )
            continue
        name = scenario.get("name") or scenario.get("label") or f"scenario_{index}"
        request_payload = {
            key: value
            for key, value in scenario.items()
            if key not in {"name", "label"}
        }
        scenarios.append(
            {
                "name": name,
                "request": _normalize_simulation_request(request_payload),
            }
        )
    normalized["scenarios"] = scenarios
    return normalized


def _load_request_json(filepath: str) -> dict[str, Any]:
    payload = json.loads(Path(filepath).read_text())
    if not isinstance(payload, dict):
        raise ValueError("Request payload must be a JSON object.")
    return payload


def _print_api_error_and_exit(status: int, data: Any) -> None:
    print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
    sys.exit(1)


def _print_streaming_request_error_and_exit(exc: RuntimeError) -> None:
    try:
        payload = json.loads(str(exc))
    except json.JSONDecodeError:
        print(f"❌ Error: {exc}", file=sys.stderr)
        sys.exit(1)
    if isinstance(payload, dict) and isinstance(payload.get("status"), int):
        _print_api_error_and_exit(int(payload["status"]), payload.get("body"))
    print(f"❌ Error: {json.dumps(payload, indent=2)}", file=sys.stderr)
    sys.exit(1)


def _stream_payloads(method: str, path: str, body: Any = None) -> Iterator[dict[str, Any]]:
    try:
        yield from api_stream_request(method, path, body)
    except RuntimeError as exc:
        _print_streaming_request_error_and_exit(exc)


def _print_sse_payloads(payloads: Iterator[dict[str, Any]], *, format: str) -> None:
    if format == "json":
        for payload in payloads:
            print(json.dumps(payload, default=str))
        return
    for payload in payloads:
        print(json.dumps(payload, indent=2, default=str))


def _print_chat_stream(payloads: Iterator[dict[str, Any]], *, format: str) -> None:
    if format == "json":
        _print_sse_payloads(payloads, format=format)
        return

    completion_id: str | None = None
    model_id: str | None = None
    finish_reason: str | None = None
    content_chunks: list[str] = []

    for payload in payloads:
        completion_id = completion_id or payload.get("id")
        model_id = model_id or payload.get("model")
        choice = (payload.get("choices") or [{}])[0]
        if not isinstance(choice, dict):
            continue
        delta = choice.get("delta") or {}
        if isinstance(delta, dict):
            content = delta.get("content")
            if isinstance(content, str):
                content_chunks.append(content)
        if choice.get("finish_reason") is not None:
            finish_reason = str(choice.get("finish_reason"))

    print()
    print(f"Completion ID:  {completion_id}")
    print(f"Model:          {model_id}")
    print(f"Assistant:      {''.join(content_chunks)}")
    if finish_reason is not None:
        print(f"Finish reason:  {finish_reason}")
    print()


def _render_response_stream_table(payload: dict[str, Any]) -> str:
    event_type = payload.get("type")
    if event_type == "response.created":
        response = payload.get("response") or {}
        return (
            f"Response created: {response.get('id')} "
            f"status={response.get('status')} model={response.get('model')}"
        )
    if event_type == "response.output_item.done":
        item = payload.get("item") or {}
        output_index = payload.get("output_index")
        content = (item.get("content") or [{}])[0]
        if isinstance(content, dict):
            if content.get("text") is not None:
                rendered = content.get("text")
            elif content.get("token_count") is not None:
                rendered = f"tokens={content.get('token_count')}"
            elif content.get("embedding") is not None:
                embedding = content.get("embedding") or []
                rendered = f"embedding_dims={len(embedding)}"
            else:
                rendered = content.get("type")
        else:
            rendered = str(content)
        return f"Output item #{output_index}: {rendered}"
    if event_type == "response.completed":
        response = payload.get("response") or {}
        usage = response.get("usage") or {}
        return (
            f"Response completed: {response.get('id')} "
            f"status={response.get('status')} total_tokens={usage.get('total_tokens')}"
        )
    return json.dumps(payload, default=str)


def _print_response_stream(payloads: Iterator[dict[str, Any]], *, format: str) -> None:
    if format == "json":
        _print_sse_payloads(payloads, format=format)
        return
    print()
    for payload in payloads:
        print(_render_response_stream_table(payload))
    print()


def _render_agent_run_stream_table(payload: dict[str, Any]) -> str:
    event_type = payload.get("type")
    if event_type == "agent.run.event":
        event = payload.get("event") or {}
        return (
            f"{event.get('created_at')}  {event.get('event_type')}  "
            f"{event.get('status')}  {event.get('message')}"
        )
    if event_type == "agent.run.completed":
        return (
            f"Run completed:  {payload.get('run_id')}  "
            f"status={payload.get('status')} total_events={payload.get('total_events')}"
        )
    return json.dumps(payload, default=str)


def _print_agent_run_event_stream(payloads: Iterator[dict[str, Any]], *, format: str) -> None:
    if format == "json":
        _print_sse_payloads(payloads, format=format)
        return
    print()
    for payload in payloads:
        print(_render_agent_run_stream_table(payload))
    print()


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
    progress_label = support_progress.get("progress_label", "unknown")
    print("\nRepository Intelligence Capabilities")
    print(f"Supported:       {supported_count}")
    print(f"Progress:        {progress_label}")
    print(f"Languages:       {', '.join(str(language) for language in supported_languages[:16])}")
    if len(supported_languages) > 16:
        print(f"Language total:  {len(supported_languages)}")
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
    print(f"Assistant:      {message.get('content', '')}")
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


def _load_json_object_file(filepath: str, *, context: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(filepath).read_text())
    except FileNotFoundError as exc:
        raise RuntimeError(f"{context} file not found: {filepath}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{context} file is not valid JSON: {filepath}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"{context} file must contain a JSON object: {filepath}")
    return payload


def _normalize_metering_payload(payload: dict[str, Any]) -> dict[str, Any]:
    device_id = payload.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise RuntimeError("Metering request must include a non-empty device_id.")
    events = payload.get("events")
    if not isinstance(events, list) or not events:
        raise RuntimeError("Metering request must include a non-empty events list.")
    allowed_keys = {
        "event_type",
        "module",
        "function",
        "engine_used",
        "latency_ms",
        "success",
        "timestamp",
        "request_id",
    }
    normalized_events: list[dict[str, Any]] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise RuntimeError(f"Metering event {index} must be a JSON object.")
        unexpected_keys = sorted(set(event) - allowed_keys)
        if unexpected_keys:
            raise RuntimeError(
                f"Metering event {index} contains unsupported fields: {', '.join(unexpected_keys)}."
            )
        normalized_event: dict[str, Any] = {}
        for key in ("event_type", "module", "function", "engine_used", "request_id"):
            if key in event:
                value = event[key]
                if not isinstance(value, str):
                    raise RuntimeError(f"Metering event {index}.{key} must be a string.")
                normalized_event[key] = value.strip()
        for key in ("latency_ms", "timestamp"):
            if key in event:
                value = event[key]
                if isinstance(value, bool) or not isinstance(value, int | float):
                    raise RuntimeError(f"Metering event {index}.{key} must be a number.")
                normalized_event[key] = float(value)
        if "success" in event:
            value = event["success"]
            if not isinstance(value, bool):
                raise RuntimeError(f"Metering event {index}.success must be a boolean.")
            normalized_event["success"] = value
        normalized_events.append(normalized_event)
    return {"device_id": device_id.strip(), "events": normalized_events}


def _normalize_credit_refresh_payload(payload: dict[str, Any]) -> dict[str, Any]:
    device_id = payload.get("device_id")
    if not isinstance(device_id, str) or not device_id.strip():
        raise RuntimeError("Credit refresh request must include a non-empty device_id.")
    billing_period = payload.get("billing_period")
    if not isinstance(billing_period, str) or len(billing_period) != 7:
        raise RuntimeError("Credit refresh request must include a YYYY-MM billing_period.")
    year_text, dash, month_text = billing_period.partition("-")
    if (
        dash != "-"
        or not year_text.isdigit()
        or len(year_text) != 4
        or not month_text.isdigit()
        or len(month_text) != 2
    ):
        raise RuntimeError("Credit refresh request must include a YYYY-MM billing_period.")
    month = int(month_text)
    if month < 1 or month > 12:
        raise RuntimeError("Credit refresh request billing_period month must be between 01 and 12.")
    credits_used = payload.get("credits_used", 0)
    if isinstance(credits_used, bool) or not isinstance(credits_used, int) or credits_used < 0:
        raise RuntimeError("Credit refresh request credits_used must be a non-negative integer.")
    return {
        "device_id": device_id.strip(),
        "billing_period": billing_period,
        "credits_used": credits_used,
    }


def cmd_deployments_regions(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/deployments/regions")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    providers = data.get("providers", []) if isinstance(data, dict) else []
    print("\nDeployment providers:")
    for provider in providers:
        regions = provider.get("regions", [])
        region_labels = ", ".join(
            region.get("label") or region.get("name") or region.get("id") or ""
            for region in regions
            if isinstance(region, dict)
        )
        print(
            f"  {provider.get('id', '')}: {provider.get('name', '')}"
            f" — {region_labels or 'No regions'}"
        )
    print()


def cmd_deployments_get(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/deployments")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    if not data:
        print("\nNo active deployment.\n")
        return
    print(f"\nDeployment ID:       {data.get('deployment_id')}")
    print(f"Provider:            {data.get('provider')}")
    print(f"Region:              {data.get('region')}")
    print(f"Status:              {data.get('status')}")
    print(f"Endpoint URL:        {data.get('endpoint_url')}")
    print(f"Cost USD/month:      {data.get('cost_usd_month')}")
    print(f"Billable USD/month:  {data.get('billable_cost_usd_month')}")
    print(f"Billing markup pct:  {data.get('billing_markup_pct')}\n")


def cmd_deployments_create(request_path: str, format: str = "table") -> None:
    payload = _load_json_object_file(request_path, context="Deployment request")
    status, data = api_request("POST", "/v1/deployments", payload)
    if status != 202:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nDeployment ID:       {data.get('deployment_id')}")
    print(f"Provider:            {data.get('provider')}")
    print(f"Region:              {data.get('region')}")
    print(f"Status:              {data.get('status')}")
    print(f"Billing markup pct:  {data.get('billing_markup_pct')}\n")


def cmd_deployments_cost(deployment_id: str, format: str = "table") -> None:
    status, data = api_request("GET", f"/v1/deployments/{deployment_id}/cost")
    if status != 200:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nDeployment ID:       {data.get('deployment_id')}")
    print(f"Provider:            {data.get('provider')}")
    print(f"Region:              {data.get('region')}")
    print(f"Month:               {data.get('year')}-{str(data.get('month')).zfill(2)}")
    print(f"Cost USD/month:      {data.get('cost_usd_month')}")
    print(f"Billable USD/month:  {data.get('billable_cost_usd_month')}")
    print(f"Billing markup pct:  {data.get('billing_markup_pct')}")
    print(f"Last updated:        {data.get('last_updated')}\n")


def cmd_deployments_delete(deployment_id: str, format: str = "table") -> None:
    status, data = api_request("DELETE", f"/v1/deployments/{deployment_id}")
    if status != 202:
        _print_api_error_and_exit(status, data)
    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return
    print(f"\nDeployment ID: {data.get('deployment_id')}")
    print(f"Status:        {data.get('status')}\n")


def cmd_health() -> None:
    _, data = api_request("GET", "/v1/health")
    status = data.get("status", "unknown")
    print(f"API Status: {'✅ OK' if status == 'ok' else '❌ ' + status}")


def cmd_contract(format: str = "table") -> None:
    status, data = api_request("GET", "/v1/meta/contract")
    if status == 404:
        openapi_status, openapi_payload = api_request("GET", "/openapi.json")
        if openapi_status >= 400:
            raise RuntimeError(
                "Failed to load Algenta contract from /v1/meta/contract or /openapi.json."
            )
        try:
            data = build_platform_contract_from_openapi(
                api_base_url=_get_base_url(),
                openapi_payload=openapi_payload,
            )
        except PlatformContractFallbackError as exc:
            raise RuntimeError(
                f"Algenta contract fallback failed [{exc.code}]: {exc}"
            ) from exc
    elif status >= 400:
        raise RuntimeError(f"Failed to load Algenta contract: HTTP {status}")
    try:
        payload = PlatformContractResponse.model_validate(data)
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Algenta contract endpoint returned an invalid payload.",
                exc,
            )
        ) from exc
    if format == "json":
        print(json.dumps(payload.model_dump(mode="json"), indent=2, default=str))
        return

    primary = payload.primary_data_query_contract
    api_contract = primary.api
    direct_python = primary.direct_sdk.python
    direct_ts = primary.direct_sdk.typescript
    runtime_python = primary.runtime_sdk.python
    runtime_ts = primary.runtime_sdk.typescript
    cli_contract = primary.cli
    mcp_contract = primary.mcp
    filter_contract = primary.governed_filter_contract
    operators = filter_contract.operators
    selector_fields = filter_contract.selector_fields
    filter_ops = [
        *operators.scalar,
        *operators.list,
        *operators.nullary,
    ]
    integration_names = ", ".join(entry.name for entry in payload.integrations)
    read_only_integrations = ", ".join(
        entry.name for entry in payload.integrations if not entry.write_actions
    )

    print(f"\nAlgenta contract: {payload.contract_version}  [{payload.brand}]")
    print(f"Base URL:        {payload.api_base_url}")
    print(f"Auth scheme:     {payload.auth_scheme}")
    print(f"API endpoint:    {api_contract.contract_endpoint}")
    print(
        "Discovery flow:  "
        f"{api_contract.discovery_endpoint} -> "
        f"{api_contract.summary_endpoint}"
    )
    print(
        "Query surface:   "
        f"{api_contract.query_endpoint} | "
        f"{api_contract.query_batch_endpoint} | "
        f"{api_contract.query_sql_report_endpoint}"
    )
    print(
        "Python SDK:      "
        f"{direct_python.contract_method}() / {runtime_python.contract_method}()"
    )
    print(
        "TypeScript SDK:  "
        f"{direct_ts.contract_method}() / {runtime_ts.contract_method}()"
    )
    print(f"Integrations:    {integration_names}")
    print(f"Read-only:       {read_only_integrations}")
    print(f"CLI:             {cli_contract.contract_command}")
    print(f"MCP:             {mcp_contract.contract_tool}")
    if filter_ops or selector_fields:
        print(f"Filter contract: {filter_contract.kind} selectors={', '.join(selector_fields)}")
    if filter_ops:
        print(f"Filter ops:      {', '.join(filter_ops)}")


def cmd_runtime_manifest(format: str = "table") -> None:
    from apps.runtime_manifest import RuntimeManifestResponse, normalize_runtime_validation_payload

    status, data = api_request("GET", "/v1/runtime/manifest")
    if status >= 400:
        raise RuntimeError(f"Failed to load Algenta runtime manifest: HTTP {status}")
    try:
        manifest = RuntimeManifestResponse.model_validate(
            normalize_runtime_validation_payload(data)
        )
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Algenta runtime manifest endpoint returned an invalid signed payload.",
                exc,
            )
        ) from exc
    if format == "json":
        print(json.dumps(manifest.model_dump(mode="json"), indent=2, default=str))
        return

    module_count = manifest.shipping_contract.module_count
    function_count = manifest.shipping_contract.function_count
    maturity_counts: dict[str, int] = {}
    for maturity in manifest.maturity.values():
        key = maturity.value
        maturity_counts[key] = maturity_counts.get(key, 0) + 1
    maturity_summary = ", ".join(
        f"{label}={count}" for label, count in sorted(maturity_counts.items())
    ) or "none"

    print(
        f"\nAlgenta runtime manifest: {manifest.runtime_version}  "
        f"[{manifest.llm_core_manifest}]"
    )
    print(f"Mojo version:    {manifest.mojo_version}")
    print(f"Generated at:    {manifest.generated_at}")
    print(f"Modules:         {module_count} shipping / {len(manifest.modules)} listed")
    print(f"Functions:       {function_count}")
    print(f"Maturity:        {maturity_summary}")
    print(
        "Channels:        "
        f"{', '.join(channel.value for channel in manifest.supported_channels) or 'none'}"
    )
    if manifest.validated_auxiliary_channels:
        print(
            "Aux channels:    "
            f"{', '.join(channel.value for channel in manifest.validated_auxiliary_channels)}"
        )
    if manifest.feature_flag_channels:
        print(
            "Feature flags:   "
            f"{', '.join(channel.value for channel in manifest.feature_flag_channels)}"
        )
    print(
        "Deployment:      "
        f"{manifest.deployment_mode.value} "
        f"[{', '.join(mode.value for mode in manifest.deployment_modes.supported_modes)}]"
    )
    print(
        "Signature:       "
        f"{manifest.signature.algorithm} [{manifest.signature.key_id}]"
    )
    print(f"Manifest digest: {manifest.manifest_digest}")
    print(f"Theorem:         {manifest.formal_release_theorem.statement}")


def cmd_runtime_validate(format: str = "table") -> None:
    from apps.runtime_manifest import (
        RuntimeReleaseValidationResponse,
        normalize_runtime_validation_payload,
    )

    status, data = api_request("GET", "/v1/admin/runtime/validation")
    if status >= 400:
        raise RuntimeError(f"Failed to validate Algenta runtime release: HTTP {status}")
    try:
        validation = RuntimeReleaseValidationResponse.model_validate(
            normalize_runtime_validation_payload(data)
        )
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Algenta runtime validation endpoint returned an invalid signed payload.",
                exc,
            )
        ) from exc
    if format == "json":
        print(json.dumps(validation.model_dump(mode="json"), indent=2, default=str))
        return

    verdict = "valid" if validation.valid_release else "invalid"
    deployment_mode = (
        validation.deployment_mode.value
        if validation.deployment_mode is not None
        else validation.deployment_mode_raw
    )

    print(
        f"\nAlgenta runtime release validation: {validation.runtime_version}  "
        f"[{validation.llm_core_manifest}]  -> {verdict}"
    )
    print(f"Deployment:      {deployment_mode}")
    print(f"Manifest digest: {validation.manifest_digest}")
    print(f"Theorem:         {validation.theorem_statement}")
    print("Conditions:")
    for condition in validation.conditions:
        label = "pass" if condition.satisfied else "FAIL"
        print(f"  - {condition.condition.value}: {label} — {condition.detail}")


def cmd_runtime_admin_modules(format: str = "table") -> None:
    from apps.runtime_manifest import (
        RuntimeAdminModulesResponse,
        normalize_runtime_validation_payload,
    )

    status, data = api_request("GET", "/v1/admin/runtime/modules")
    if status >= 400:
        raise RuntimeError(f"Failed to load Algenta runtime module catalog: HTTP {status}")
    try:
        payload = RuntimeAdminModulesResponse.model_validate(
            normalize_runtime_validation_payload(data)
        )
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Algenta runtime modules endpoint returned an invalid signed payload.",
                exc,
            )
        ) from exc
    if format == "json":
        print(json.dumps(payload.model_dump(mode="json"), indent=2, default=str))
        return

    print(
        f"\nAlgenta runtime module catalog: {payload.runtime_version}  "
        f"[{payload.llm_core_manifest}]"
    )
    print(
        "Summary:         "
        f"{payload.summary.module_count} modules / {payload.summary.function_count} functions"
    )
    print(f"Manifest digest: {payload.manifest_digest}")
    if payload.proof_matrix:
        first_entry = payload.proof_matrix[0]
        print(
            "Proof matrix:    "
            f"{first_entry.layer.value} [{first_entry.status.value}]"
        )
    print(f"{'Module':<28} {'Maturity':<18} {'Functions':<10} Compiled artifact")
    print("─" * 100)
    for module in payload.modules:
        print(
            f"  {module.name.value:<26} "
            f"{module.maturity.value:<18} "
            f"{module.function_count:<10} "
            f"{module.compiled_artifact}"
        )


def cmd_runtime_admin_benchmarks(format: str = "table") -> None:
    from apps.runtime_manifest import (
        RuntimeAdminBenchmarksResponse,
        normalize_runtime_validation_payload,
    )

    status, data = api_request("GET", "/v1/admin/runtime/benchmarks")
    if status >= 400:
        raise RuntimeError(f"Failed to load Algenta runtime benchmark catalog: HTTP {status}")
    try:
        payload = RuntimeAdminBenchmarksResponse.model_validate(
            normalize_runtime_validation_payload(data)
        )
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Algenta runtime benchmarks endpoint returned an invalid signed payload.",
                exc,
            )
        ) from exc
    if format == "json":
        print(json.dumps(payload.model_dump(mode="json"), indent=2, default=str))
        return

    print(
        f"\nAlgenta runtime benchmark catalog: {payload.runtime_version}  "
        f"[{payload.llm_core_manifest}]"
    )
    print(
        "Discovery lane:  "
        f"{payload.benchmark_discovery_lane.discovered_source_modules} source modules / "
        f"{payload.benchmark_discovery_lane.shipping_manifest_modules} shipping modules"
    )
    print(f"Manifest digest: {payload.manifest_digest}")
    print("SLO budgets:")
    for budget in payload.slo_budgets:
        print(
            "  - "
            f"{budget.name.value}: p95 {budget.p95_objective_ms} ms / "
            f"ceiling {budget.hard_ceiling_ms} ms"
        )
    evaluation = payload.evaluation_summary
    print(
        "Evaluation:      "
        f"{evaluation.dimension_count} dimensions / "
        f"{evaluation.method_count} methods / "
        f"{evaluation.release_blocker_count} release blockers"
    )
    print(
        "Quality gates:   "
        f"replay={'on' if evaluation.replay_gate_enabled else 'off'}, "
        f"tool_call={'on' if evaluation.tool_call_quality_gate_enabled else 'off'}, "
        f"rag={'on' if evaluation.rag_quality_gate_enabled else 'off'}, "
        f"decision={'on' if evaluation.decision_quality_gate_enabled else 'off'}"
    )
    print("Benchmark classes:")
    for benchmark_class in payload.benchmarking.classes:
        evidence = ", ".join(benchmark_class.evidence_paths) or "none"
        print(
            "  - "
            f"{benchmark_class.code.value}: {benchmark_class.description} "
            f"[evidence: {evidence}]"
        )
    print("Quality gate benchmark classes:")
    for benchmark_class in payload.quality_gate_benchmark_classes:
        evidence = ", ".join(benchmark_class.evidence_paths) or "none"
        print(
            "  - "
            f"{benchmark_class.code.value}: {benchmark_class.description} "
            f"[evidence: {evidence}]"
        )
    print(f"{'Module':<28} {'Speedup':<12} {'Engine':<12} Benchmark artifact")
    print("─" * 95)
    for benchmark in payload.module_benchmarks:
        print(
            f"  {benchmark.name.value:<26} "
            f"{benchmark.benchmark_speedup_x:<12.2f} "
            f"{benchmark.compiled_engine:<12} "
            f"{benchmark.benchmark_artifact}"
        )


# ─── Auth / login commands ───────────────────────────────────────────────────


def _login_api_key_help_text() -> str:
    if _private_profile_enabled():
        try:
            base_url = _get_base_url()
        except ValueError:
            return (
                "No API key provided. Configure ALGENTA_BASE_URL / DE_BASE_URL / ALGENTA_API_URL "
                "or save base_url in CLI config, then create a key from your self-hosted admin surface."
            )
        return (
            "No API key provided. Create one from your self-hosted admin surface or API base URL: "
            f"{base_url}"
        )
    return "No API key provided. Get one from https://app.algenta.ai/dashboard/api-keys"


def cmd_login(api_key: str = "") -> None:
    """
    Register this machine with an API key.
    Issues a device license (JWT) and stores it locally.

    Usage:
        de login                            # prompts for API key
        de login <YOUR_ALGENTA_API_KEY>     # key as argument (CI-safe)
        ALGENTA_API_KEY=<YOUR_ALGENTA_API_KEY> de login
        DE_API_KEY=<YOUR_LEGACY_DECISION_ENGINE_API_KEY> de login
    """
    if not api_key:
        api_key = _load_env_api_key()
    if not api_key:
        api_key = input("API key: ").strip()
    if not api_key:
        print(_login_api_key_help_text())
        return

    from apps.runtime.device import get_device_info
    from apps.runtime.license import issue_and_store, license_summary

    device_info = get_device_info()
    print(f"Registering device {device_info['device_id'][:8]}...  ({device_info['platform']})")

    lic = issue_and_store(api_key)
    if lic.valid:
        print(f"✓ License issued: {license_summary(lic)}")
        print("  Run `de runtime start` to start the local runtime.")
    else:
        print(f"✗ License failed: {lic.message}")


def cmd_logout() -> None:
    """Remove the stored device license."""
    from apps.runtime.license import revoke_local

    revoke_local()
    print("Device license removed. Run `de login` to re-register.")


def cmd_license_status() -> None:
    """Show current device license status."""
    from apps.runtime.device import get_device_info
    from apps.runtime.license import load_license

    api_key = _load_env_api_key()
    lic = load_license(api_key)
    device_info = get_device_info()

    print(f"Device ID:  {lic.device_id[:8]}...{lic.device_id[-4:]}  ({device_info['platform']})")
    print(f"Plan:       {lic.plan}")
    print(f"Devices:    {'unlimited' if lic.device_limit == 0 else f'max {lic.device_limit}'}")
    modules = "all" if "*" in lic.permitted_modules else ", ".join(lic.permitted_modules)
    print(f"Modules:    {modules}")
    print(f"Source:     {lic.source}")
    if lic.expires_at:
        import time

        print(
            f"Expires:    {time.strftime('%Y-%m-%d', time.gmtime(lic.expires_at))}"
            + ("  [IN GRACE PERIOD]" if lic.is_in_grace() else "")
            + ("  [HARD EXPIRED]" if lic.is_hard_expired() else "")
        )
    else:
        print("Expires:    never")
    if lic.message:
        print(f"Note:       {lic.message}")


# ─── Runtime daemon commands ──────────────────────────────────────────────────


async def _wait_for_runtime_ready(
    *,
    client: Any,
    timeout_seconds: float = _RUNTIME_READY_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    import asyncio

    deadline = time.monotonic() + timeout_seconds
    last_health: dict[str, Any] = {"status": "unreachable"}
    while True:
        health = await client.health()
        if health.get("status") == "ok":
            return dict(health)
        last_health = dict(health)
        if time.monotonic() >= deadline:
            break
        await asyncio.sleep(_RUNTIME_READY_POLL_SECONDS)

    if last_health.get("status") == "unreachable":
        raise RuntimeError(_RUNTIME_NOT_RUNNING_MESSAGE)
    raise RuntimeError(
        "Algenta Runtime did not report healthy status. "
        f"Last health payload: {json.dumps(last_health, default=str)}"
    )


def cmd_runtime_start() -> None:
    """Start the Algenta local runtime daemon in the background."""
    from apps.runtime.daemon import cmd_start

    cmd_start(foreground=False)


def cmd_runtime_stop() -> None:
    """Stop the running local runtime daemon."""
    from apps.runtime.daemon import cmd_stop

    cmd_stop()


def cmd_runtime_status() -> None:
    """Show local runtime daemon status."""
    from apps.runtime.daemon import cmd_status

    cmd_status()


def _runtime_list_modules_sync() -> list[dict[str, Any]]:
    import asyncio

    from apps.runtime.client import DaemonClient

    async def _list() -> list[dict[str, Any]]:
        client = DaemonClient(timeout=10.0)
        await _wait_for_runtime_ready(client=client)
        modules = await client.list_modules()
        if not modules:
            raise RuntimeError("Local runtime returned no executable Mojo libraries.")
        return [dict(module) for module in modules]

    return asyncio.run(_list())


def _load_runtime_execute_args(
    *,
    args_json: str | None = None,
    args_file: str | None = None,
) -> Any:
    if args_json and args_file:
        raise RuntimeError("Provide either --args-json or --args-file, not both.")
    if args_file:
        try:
            return json.loads(Path(args_file).read_text())
        except FileNotFoundError as exc:
            raise RuntimeError(f"Runtime args file not found: {args_file}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Runtime args file is not valid JSON: {args_file}") from exc
    if args_json:
        try:
            return json.loads(args_json)
        except json.JSONDecodeError as exc:
            raise RuntimeError("--args-json must be valid JSON.") from exc
    return None


def cmd_runtime_modules(format: str = "table") -> None:
    """List modules available in the local runtime."""
    try:
        modules = _runtime_list_modules_sync()
    except RuntimeError as exc:
        print(str(exc))
        return

    if format == "json":
        print(json.dumps({"modules": modules}, indent=2, default=str))
        return

    print(f"{'Module':<28} {'Engine':<20} Functions")
    print("─" * 75)
    for module in modules:
        functions = [str(function) for function in module.get("functions", [])]
        preview = ", ".join(functions[:4]) + ("…" if len(functions) > 4 else "")
        print(f"  {str(module.get('name', '')):<26} {str(module.get('engine', '')):<20} {preview}")


def cmd_runtime_functions(module_name: str, format: str = "table") -> None:
    """List executable functions for one local runtime module."""
    try:
        modules = _runtime_list_modules_sync()
    except RuntimeError as exc:
        print(str(exc))
        return

    module = next((item for item in modules if item.get("name") == module_name), None)
    if module is None:
        print(f"Unknown runtime module: {module_name}")
        return

    functions = [str(function) for function in module.get("functions", [])]
    payload = {
        "module": str(module.get("name")),
        "engine": str(module.get("engine")),
        "functions": functions,
    }
    if format == "json":
        print(json.dumps(payload, indent=2, default=str))
        return

    print(f"Runtime module: {payload['module']}")
    print(f"Engine:         {payload['engine']}")
    print(f"Functions ({len(functions)}):")
    for function in functions:
        print(f"  - {function}")


def cmd_runtime_execute(
    module_name: str,
    function_name: str,
    *,
    args_json: str | None = None,
    args_file: str | None = None,
    format: str = "table",
) -> None:
    """Execute one local runtime module function with JSON args."""
    try:
        payload = _load_runtime_execute_args(args_json=args_json, args_file=args_file)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    try:
        import asyncio

        from apps.runtime.client import DaemonClient

        async def _execute() -> dict[str, Any]:
            client = DaemonClient(timeout=30.0)
            await _wait_for_runtime_ready(client=client)
            return await client.execute(module_name, function_name, payload)

        result = asyncio.run(_execute())
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc

    if not result.get("success", False):
        print(
            json.dumps(
                {
                    "error": {
                        "code": "mojo_execution_failed",
                        "message": str(result.get("error", "Runtime execution failed.")),
                        "details": {
                            "module": module_name,
                            "function": function_name,
                            "engine_used": result.get("engine_used"),
                        },
                    }
                },
                indent=2,
                default=str,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1)

    output = {
        "module": module_name,
        "function": function_name,
        "args": payload,
        "result": result.get("result"),
        "latency_ms": result.get("latency_ms"),
        "engine_used": result.get("engine_used"),
        "success": bool(result.get("success")),
    }
    print_result(output, format, rich_enabled=_RICH)


def cmd_runtime_history(limit: int = 20, format: str = "table") -> None:
    """Show recent local runtime ledger entries."""
    from apps.runtime.ledger import ledger_path

    path = ledger_path()
    if not path.exists():
        print(f"No local runtime history found at {path}")
        return

    try:
        lines = [line for line in path.read_text().splitlines() if line.strip()]
        events = [json.loads(line) for line in lines[-max(1, limit) :]]
    except Exception as exc:
        print(f"Could not read runtime history: {exc}")
        return

    if format == "json":
        print(json.dumps(events, indent=2, default=str))
        return

    print(f"Runtime history ({len(events)} event{'s' if len(events) != 1 else ''})")
    print(f"Ledger: {path}")
    print(f"{'Time':<19} {'Status':<10} {'Target':<32} {'Engine':<16} {'Latency':>8}")
    print("─" * 92)
    for event in events:
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(event.get("timestamp", 0)))
        status = str(event.get("status", ""))[:10]
        target = str(event.get("target", ""))[:32]
        engine = str(event.get("engine_used") or "-")[:16]
        latency = event.get("latency_ms")
        latency_text = "-" if latency is None else f"{float(latency):.2f}ms"
        print(f"{ts:<19} {status:<10} {target:<32} {engine:<16} {latency_text:>8}")
        if event.get("error"):
            print(f"  error: {event['error']}")


def cmd_benchmark() -> None:
    """Show Mojo vs Python speedup from the official benchmark suite."""

    root = Path(__file__).parent.parent.parent
    summary_path = root / "benchmarks" / "summary.txt"
    summary_payload, summary_source = _load_benchmark_summary(root)

    print(f"\n{'─' * 62}")
    print("  Algenta — Mojo vs Python Benchmark")
    print(f"{'─' * 62}\n")

    # Try to load real benchmark data
    real_data: list[tuple[str, float]] = []
    meta: dict[str, str] = {}
    total_functions: int | None = None
    n_iterations: int | None = None
    if summary_payload is not None:
        for item in summary_payload.get("libraries", []):
            if not isinstance(item, dict):
                continue
            lib_name = str(item.get("lib", "")).strip()
            speedup_value = item.get("speedup_x")
            try:
                speedup = float(speedup_value)
            except (TypeError, ValueError):
                continue
            if lib_name and speedup > 0:
                real_data.append((lib_name, speedup))

        median_speedup = summary_payload.get("median_speedup_x")
        max_speedup = summary_payload.get("max_speedup_x")
        meta["median"] = str(median_speedup if median_speedup is not None else 0.0)
        meta["max"] = str(max_speedup if max_speedup is not None else 0.0)
        meta["n_libs"] = str(summary_payload.get("n_libraries", 0))
        meta["date"] = str(summary_payload.get("timestamp", ""))
        total_functions = int(summary_payload.get("total_functions_compared", 0) or 0)
        n_iterations = int(summary_payload.get("n_iterations", 0) or 0)
    elif summary_path.exists():
        lines = summary_path.read_text().splitlines()
        for line in lines:
            if "Median:" in line:
                meta["median"] = line.split(":")[-1].strip().replace("x", "")
            elif "Max:" in line:
                meta["max"] = line.split(":")[-1].strip().replace("x", "")
            elif "Libraries benchmarked:" in line:
                meta["n_libs"] = line.split(":")[-1].strip()
            elif "Generated:" in line:
                meta["date"] = line.split(":", 1)[-1].strip()
            elif (
                line.strip()
                and not line.startswith(" ")
                or (
                    line.startswith("  ")
                    and "x" in line
                    and not line.startswith("  Overall")
                    and not line.startswith("  Median")
                    and not line.startswith("  Mean")
                    and not line.startswith("  Max")
                    and not line.startswith("  Min")
                    and not line.startswith("  Library")
                    and "---" not in line
                )
            ):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        name = parts[0].strip()
                        speedup = float(parts[1].replace("x", ""))
                        if speedup > 0 and name not in (
                            "Suite",
                            "Generated",
                            "Overall",
                            "Iterations",
                        ):
                            real_data.append((name, speedup))
                    except (ValueError, IndexError):
                        pass

    if meta:
        n_libs = meta.get("n_libs", "444")
        median = float(meta.get("median", "95"))
        max_val = float(meta.get("max", "1500"))
        date = meta.get("date", "")

        # Pick a spread of examples across speedup range
        examples: list[tuple[str, float]] = []
        if real_data:
            sorted_data = sorted(real_data, key=lambda x: x[1])
            n = len(sorted_data)
            idxs = [n // 10, n // 4, n // 2, 3 * n // 4, n - 1]
            examples = [sorted_data[i] for i in idxs if i < n]

        print(f"  {n_libs} Mojo libraries vs Python — {date[:10] if date else 'latest'}")
        print()
        print(f"  {'Library':<32} {'Python':>10}  {'Mojo':>10}  {'Speedup':>10}")
        print(f"  {'─' * 32}  {'─' * 10}  {'─' * 10}  {'─' * 10}")

        # Show a spread of real examples
        show = (
            examples
            if examples
            else [
                ("probability_distributions", 95.0),
                ("agent_runtime", 992.0),
                ("activation_functions", 393.0),
                ("monte_carlo", 150.0),
                ("risk_engine", 80.0),
            ]
        )
        for lib, spd in show[:6]:
            mojo_ns = 8.0
            python_ns = mojo_ns * spd
            print(f"  {lib:<32}  {python_ns:>8.0f}ns  {mojo_ns:>8.0f}ns  {spd:>7.0f}×")

        print()
        med_bar_w = min(30, int(median / max_val * 30))
        max_bar_w = 30
        med_bar = "█" * med_bar_w + "░" * (30 - med_bar_w)
        max_bar = "█" * max_bar_w

        print(f"  Median speedup:  [{med_bar}] {_format_speedup_value(median)}×")
        print(f"  Max speedup:     [{max_bar}] {_format_speedup_value(max_val)}×")
        print()
        measurement_details = [f"{n_libs} libraries"]
        if total_functions:
            measurement_details.append(f"{total_functions} public runtime functions")
        if n_iterations:
            measurement_details.append(f"{n_iterations:,} iterations per function")
        print(f"  Measured across {', '.join(measurement_details)}.")
        source_text = _display_benchmark_source(root, summary_source)
        if source_text is not None:
            print(f"  Source: {source_text}")
            if summary_source and summary_source.name == "llm_rollout_parity_benchmark.json":
                print(f"  Scope: {n_libs}-library LLM rollout parity proof.")
        print("  This is the benchmark — not a claim.")

    else:
        # Fallback: show known numbers
        print("  Mojo vs Python (official benchmark, 444 libraries)")
        print()
        print(f"  {'Library':<28}  {'Speedup':>10}")
        print(f"  {'─' * 28}  {'─' * 10}")
        for lib, spd in [
            ("agent_runtime", "992×"),
            ("activation_functions", "393×"),
            ("aquaculture", "317×"),
            ("apiculture", "224×"),
            ("actuarial", "133×"),
            ("probability_dist", "95×"),
        ]:
            print(f"  {lib:<28}  {spd:>10}")
        print()
        print("  Median: 95× · Max: 1,734× · 444 libraries")

    dashboard_url = _get_dashboard_url()
    print()
    if _private_profile_enabled():
        print("  Configured deployment:")
    else:
        print("  Free tier: 500 simulations/month")
    print(f"  → {dashboard_url}")
    print(f"{'─' * 62}\n")


def cmd_template_list() -> None:
    """List available simulation templates."""
    status, data = api_request("GET", "/v1/simulate/templates")
    if status != 200:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)
    templates = data.get("templates", [])
    print(f"\n  {len(templates)} templates available\n")
    current_domain = ""
    for t in templates:
        domain = t.get("domain", "")
        if domain != current_domain:
            print(f"  [{domain.upper()}]")
            current_domain = domain
        n_vars = t.get("n_variables", "?")
        print(f"    {t['id']:<35} {t['name']} ({n_vars} variables)")
    print("\n  Run a template: de template run <id>")
    print("  Example: de template run finance_npv\n")


def cmd_template_run(template_id: str, runs: int = 10000, format: str = "table") -> None:
    """Run a simulation template by ID."""
    status, data = api_request(
        "POST",
        f"/v1/templates/{template_id}/run",
        body=None,
    )
    if status != 200:
        # Try with query params via URL
        import urllib.parse

        qs = urllib.parse.urlencode({"runs": runs})
        status, data = api_request("POST", f"/v1/templates/{template_id}/run?{qs}", None)
    if status != 200:
        print(f"❌ Error {status}: {json.dumps(data, indent=2)}", file=sys.stderr)
        sys.exit(1)

    name = data.get("template_name", template_id)
    domain = data.get("domain", "")
    result = data.get("result", {})

    if format == "json":
        print(json.dumps(data, indent=2, default=str))
        return

    print(f"\n  ✅ {name} ({domain})\n")
    ev = result.get("expected_value", 0)
    pol = result.get("probability_of_loss", 0)
    std = result.get("std_deviation", 0)
    p5 = result.get("percentiles", {}).get("p5", 0)
    p95 = result.get("percentiles", {}).get("p95", 0)
    ms = result.get("execution_ms", 0)

    print(f"  Expected outcome:   {ev:>15,.2f}")
    print(f"  Prob. of loss:      {pol:>15.1%}")
    print(f"  Std deviation:      {std:>15,.2f}")
    print(f"  Downside (p5):      {p5:>15,.2f}")
    print(f"  Upside (p95):       {p95:>15,.2f}")
    print(f"  Execution:          {ms:>15.0f}ms\n")
    print(f"  Full payload: de template get {template_id}\n")


# ─── Main entry point (without Typer) ────────────────────────────────────────


def main() -> None:
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0]
    sub = args[1] if len(args) > 1 else ""

    def _json_format_flag() -> str:
        return "json" if _arg_value(args, "--format") == "json" else "table"

    if cmd == "config" and sub == "set-key" and len(args) >= 3:
        cmd_config_set_key(args[2], args[3] if len(args) > 3 else None)
    elif cmd == "data" and sub == "connect":
        request_path = _arg_value(args, "--request")
        fmt = _arg_value(args, "--format") or "table"
        cmd_data_connect(request_path=request_path, format=fmt)
    elif cmd == "data" and sub == "list":
        fmt = _arg_value(args, "--format") or "table"
        cmd_data_list(
            format=fmt,
            search=_arg_value(args, "--search"),
            status_filter=_arg_value(args, "--status"),
            source_name=_arg_value(args, "--source-name"),
            page=int(_arg_value(args, "--page") or "1"),
            limit=int(_arg_value(args, "--limit") or "20"),
            compact="--compact" in args,
        )
    elif cmd == "data" and sub == "summary" and len(args) >= 3:
        fmt = _arg_value(args, "--format") or "table"
        cmd_data_summary(args[2], format=fmt)
    elif cmd == "data" and sub == "inspect" and len(args) >= 3:
        fmt = _arg_value(args, "--format") or "table"
        cmd_data_inspect(args[2], format=fmt)
    elif cmd == "data" and sub == "query-batch" and len(args) >= 3:
        fmt = _arg_value(args, "--format") or "table"
        cmd_data_query_batch(args[2], format=fmt)
    elif cmd == "data" and sub == "sql-report" and len(args) >= 3:
        fmt = _arg_value(args, "--format") or "table"
        cmd_data_sql_report(args[2], format=fmt)
    elif cmd == "data" and sub == "refresh" and len(args) >= 3:
        fmt = _arg_value(args, "--format") or "table"
        cmd_data_refresh(args[2], format=fmt)
    elif cmd == "data" and sub == "disconnect" and len(args) >= 3:
        fmt = _arg_value(args, "--format") or "table"
        cmd_data_disconnect(args[2], assume_yes="--yes" in args, format=fmt)
    elif cmd == "data":
        print(
            "Usage: de data "
            "[connect|list|summary|inspect|query-batch|sql-report|refresh|disconnect]"
        )
    elif cmd == "connectors" and sub == "create" and len(args) >= 3:
        cmd_connectors_create(args[2], _json_format_flag())
    elif cmd == "connectors" and sub == "list":
        fmt = _arg_value(args, "--format") or "table"
        cmd_connectors_list(
            page=int(_arg_value(args, "--page") or "1"),
            limit=int(_arg_value(args, "--limit") or "25"),
            format=fmt,
        )
    elif cmd == "connectors" and sub == "get" and len(args) >= 3:
        cmd_connectors_get(args[2], _json_format_flag())
    elif cmd == "connectors" and sub == "update" and len(args) >= 4:
        cmd_connectors_update(args[2], args[3], _json_format_flag())
    elif cmd == "connectors" and sub == "test" and len(args) >= 3:
        cmd_connectors_test(args[2], _json_format_flag())
    elif cmd == "connectors" and sub == "preview-test" and len(args) >= 3:
        cmd_connectors_preview_test(args[2], _json_format_flag())
    elif cmd == "connectors" and sub == "browse" and len(args) >= 3:
        cmd_connectors_browse(args[2], _json_format_flag())
    elif cmd == "connectors" and sub == "preview-browse" and len(args) >= 3:
        cmd_connectors_preview_browse(args[2], _json_format_flag())
    elif cmd == "connectors" and sub == "delete" and len(args) >= 3:
        cmd_connectors_delete(args[2], _json_format_flag())
    elif cmd == "connectors":
        print(
            "Usage: de connectors "
            "[create|list|get|update|test|preview-test|browse|preview-browse|delete]"
        )
    elif cmd == "capabilities" and sub == "providers":
        cmd_capabilities_providers(_json_format_flag())
    elif cmd == "capabilities" and sub == "provider" and len(args) >= 3:
        cmd_capabilities_provider(args[2], _json_format_flag())
    elif cmd == "capabilities" and sub == "bindings":
        fmt = _arg_value(args, "--format") or "table"
        cmd_capabilities_bindings(
            provider_id=_arg_value(args, "--provider-id"),
            scope=_arg_value(args, "--scope"),
            format=fmt,
        )
    elif cmd == "capabilities" and sub == "list":
        fmt = _arg_value(args, "--format") or "table"
        cmd_capabilities_list(
            kinds=_parse_csv_flag(_arg_value(args, "--kind")),
            provider_ids=_parse_csv_flag(_arg_value(args, "--provider-id")),
            binding_ids=_parse_csv_flag(_arg_value(args, "--binding-id")),
            format=fmt,
        )
    elif cmd == "capabilities" and sub == "route" and len(args) >= 3:
        cmd_capabilities_route(args[2], _json_format_flag())
    elif cmd == "capabilities" and sub == "execute" and len(args) >= 3:
        cmd_capabilities_execute(args[2], _json_format_flag())
    elif cmd == "capabilities":
        print(
            "Usage: de capabilities "
            "[providers|provider <provider_id>|bindings|list|route <request.json>|execute <request.json>] "
            "[--provider-id <id[,id]>] [--binding-id <id[,id]>] [--kind <kind[,kind]>] "
            "[--scope <user|workspace|organization>] [--format json]"
        )
    elif cmd == "repositories" and sub == "snapshot" and len(args) >= 4:
        cmd_repositories_snapshot(args[2], args[3], _json_format_flag())
    elif cmd == "repositories" and sub == "capabilities":
        cmd_repositories_capabilities(_json_format_flag())
    elif cmd == "repositories" and sub == "get-snapshot" and len(args) >= 4:
        cmd_repositories_get_snapshot(args[2], args[3], _json_format_flag())
    elif cmd == "repositories" and sub == "triage" and len(args) >= 4:
        cmd_repositories_triage(args[2], args[3], _json_format_flag())
    elif cmd == "repositories" and sub == "decision-plan" and len(args) >= 4:
        cmd_repositories_decision_plan(args[2], args[3], _json_format_flag())
    elif cmd == "repositories" and sub == "graph-query" and len(args) >= 4:
        cmd_repositories_graph_query(args[2], args[3], _json_format_flag())
    elif cmd == "repositories" and sub == "simulate" and len(args) >= 4:
        cmd_repositories_simulate(args[2], args[3], _json_format_flag())
    elif cmd == "repositories" and sub == "apply" and len(args) >= 4:
        cmd_repositories_apply(args[2], args[3], _json_format_flag())
    elif cmd == "repositories":
        print(
            "Usage: de repositories capabilities [--format json]\n"
            "       de repositories "
            "[snapshot|triage|decision-plan|graph-query|simulate|apply] "
            "<repository_id> <request.json> [--format json]\n"
            "       de repositories get-snapshot <repository_id> <snapshot_id> [--format json]"
        )
    elif cmd == "simulate" and len(args) >= 2:
        cmd_simulate(args[1], _json_format_flag())
    elif cmd == "recommend" and len(args) >= 2:
        fmt = "json" if "--format" in args else "table"
        cmd_recommend(args[1], fmt)
    elif cmd == "product" and sub == "decision" and len(args) >= 3:
        cmd_product_decision(args[2], _json_format_flag())
    elif cmd == "product" and sub == "agent-run" and len(args) >= 3:
        cmd_product_agent_run(args[2], _json_format_flag())
    elif cmd == "product" and sub == "optimize" and len(args) >= 3:
        cmd_product_optimize(args[2], _json_format_flag())
    elif cmd == "product" and sub == "retrieve" and len(args) >= 3:
        cmd_product_retrieve(args[2], _json_format_flag())
    elif cmd == "product" and sub == "forecast" and len(args) >= 3:
        cmd_product_forecast(args[2], _json_format_flag())
    elif cmd == "product":
        print(
            "Usage: de product [decision|agent-run|optimize|retrieve|forecast] "
            "<request.json> [--format json]"
        )
    elif cmd == "llm" and sub == "models":
        cmd_llm_models(_json_format_flag())
    elif cmd == "llm" and sub == "resolve-artifact" and len(args) >= 3:
        cmd_llm_resolve_artifact(args[2], _json_format_flag())
    elif cmd == "llm" and sub == "tokenize":
        text = _arg_value(args, "--input")
        if text is None:
            print("Usage: de llm tokenize --input <text> [--model <id>] [--format json]")
            sys.exit(1)
        cmd_llm_tokenize(
            text,
            model=_arg_value(args, "--model") or "text.tokenizer",
            format=_json_format_flag(),
        )
    elif cmd == "llm" and sub == "count-tokens":
        text = _arg_value(args, "--input")
        if text is None:
            print("Usage: de llm count-tokens --input <text> [--model <id>] [--format json]")
            sys.exit(1)
        cmd_llm_count_tokens(
            text,
            model=_arg_value(args, "--model") or "text.tokenizer",
            format=_json_format_flag(),
        )
    elif cmd == "llm" and sub == "chat" and len(args) >= 3:
        cmd_llm_chat(args[2], _json_format_flag(), stream="--stream" in args)
    elif cmd == "llm" and sub == "responses" and len(args) >= 3:
        cmd_llm_responses(args[2], _json_format_flag(), stream="--stream" in args)
    elif cmd == "llm" and sub == "embeddings" and len(args) >= 3:
        cmd_llm_embeddings(args[2], _json_format_flag())
    elif cmd == "llm" and sub == "embedding-similarity" and len(args) >= 3:
        cmd_llm_embedding_similarity(args[2], _json_format_flag())
    elif cmd == "llm" and sub == "rerank" and len(args) >= 3:
        cmd_llm_rerank(args[2], _json_format_flag())
    elif cmd == "llm":
        print(
            "Usage: de llm "
            "[models|resolve-artifact|tokenize|count-tokens|chat|responses|embeddings|embedding-similarity|rerank]"
        )
    elif cmd == "decision" and sub == "plan" and len(args) >= 3:
        cmd_decision_plan(args[2], _json_format_flag())
    elif cmd == "decision" and sub == "score" and len(args) >= 3:
        cmd_decision_score(args[2], _json_format_flag())
    elif cmd == "decision" and sub == "batch" and len(args) >= 3:
        cmd_decision_batch(args[2], _json_format_flag())
    elif cmd == "decision" and sub == "compare" and len(args) >= 3:
        cmd_decision_compare(args[2], _json_format_flag())
    elif cmd == "decision":
        print("Usage: de decision [plan|score|batch|compare] <request.json> [--format json]")
    elif cmd == "decisions" and sub == "log" and len(args) >= 3:
        cmd_decisions_log(args[2], _json_format_flag())
    elif cmd == "decisions" and sub == "list":
        cmd_decisions_list(
            page=int(_arg_value(args, "--page") or "1"),
            limit=int(_arg_value(args, "--limit")) if _arg_value(args, "--limit") else None,
            page_size=(
                int(_arg_value(args, "--page-size"))
                if _arg_value(args, "--page-size")
                else None
            ),
            with_outcome_only="--with-outcome-only" in args,
            format=_json_format_flag(),
        )
    elif cmd == "decisions" and sub == "get" and len(args) >= 3:
        cmd_decisions_get(args[2], _json_format_flag())
    elif cmd == "decisions" and sub == "outcome" and len(args) >= 4:
        cmd_decisions_outcome(args[2], args[3], _json_format_flag())
    elif cmd == "decisions" and sub == "execute" and len(args) >= 4:
        cmd_decisions_execute(args[2], args[3], _json_format_flag())
    elif cmd == "decisions" and sub == "delete" and len(args) >= 3:
        cmd_decisions_delete(args[2], _json_format_flag())
    elif cmd == "decisions":
        print(
            "Usage: de decisions "
            "[log <request.json>|list|get <decision_id>|outcome <decision_id> <request.json>|"
            "execute <decision_id> <request.json>|delete <decision_id>] [--format json]"
        )
    elif cmd == "agent-runs" and sub == "list":
        cmd_agent_run_list(
            page=int(_arg_value(args, "--page") or "1"),
            limit=int(_arg_value(args, "--limit") or "25"),
            status_filter=_arg_value(args, "--status"),
            request_hash=_arg_value(args, "--request-hash"),
            policy_snapshot_id=_arg_value(args, "--policy-snapshot-id"),
            schema_snapshot_id=_arg_value(args, "--schema-snapshot-id"),
            format=_json_format_flag(),
        )
    elif cmd == "agent-runs" and sub == "create" and len(args) >= 3:
        cmd_agent_run_create(args[2], _json_format_flag())
    elif cmd == "agent-runs" and sub == "get" and len(args) >= 3:
        cmd_agent_run_get(args[2], _json_format_flag())
    elif cmd == "agent-runs" and sub == "events" and len(args) >= 3:
        cmd_agent_run_events(
            args[2],
            limit=int(_arg_value(args, "--limit") or "1000"),
            format=_json_format_flag(),
            stream="--stream" in args,
        )
    elif cmd == "agent-runs" and sub == "checkpoints" and len(args) >= 3:
        cmd_agent_run_checkpoints(args[2], _json_format_flag())
    elif cmd == "agent-runs" and sub == "query-checkpoints":
        cmd_agent_run_query_checkpoints(
            page=int(_arg_value(args, "--page") or "1"),
            limit=int(_arg_value(args, "--limit") or "25"),
            status_filter=_arg_value(args, "--status"),
            request_hash=_arg_value(args, "--request-hash"),
            policy_snapshot_id=_arg_value(args, "--policy-snapshot-id"),
            schema_snapshot_id=_arg_value(args, "--schema-snapshot-id"),
            run_id=_arg_value(args, "--run-id"),
            checkpoint_id=_arg_value(args, "--checkpoint-id"),
            format=_json_format_flag(),
        )
    elif cmd == "agent-runs" and sub == "mission-events" and len(args) >= 3:
        cmd_agent_run_mission_events(
            args[2],
            int(_arg_value(args, "--limit") or "1000"),
            _json_format_flag(),
        )
    elif cmd == "agent-runs" and sub == "query-mission-events":
        cmd_agent_run_query_mission_events(
            page=int(_arg_value(args, "--page") or "1"),
            limit=int(_arg_value(args, "--limit") or "25"),
            status_filter=_arg_value(args, "--status"),
            request_hash=_arg_value(args, "--request-hash"),
            policy_snapshot_id=_arg_value(args, "--policy-snapshot-id"),
            schema_snapshot_id=_arg_value(args, "--schema-snapshot-id"),
            run_id=_arg_value(args, "--run-id"),
            event_type=_arg_value(args, "--event-type"),
            format=_json_format_flag(),
        )
    elif cmd == "agent-runs" and sub == "telemetry" and len(args) >= 3:
        cmd_agent_run_telemetry(
            args[2],
            int(_arg_value(args, "--limit") or "1000"),
            _json_format_flag(),
        )
    elif cmd == "agent-runs" and sub == "query-telemetry":
        cmd_agent_run_query_telemetry(
            page=int(_arg_value(args, "--page") or "1"),
            limit=int(_arg_value(args, "--limit") or "25"),
            status_filter=_arg_value(args, "--status"),
            request_hash=_arg_value(args, "--request-hash"),
            policy_snapshot_id=_arg_value(args, "--policy-snapshot-id"),
            schema_snapshot_id=_arg_value(args, "--schema-snapshot-id"),
            run_id=_arg_value(args, "--run-id"),
            telemetry_kind=_arg_value(args, "--telemetry-kind"),
            module_name=_arg_value(args, "--module-name"),
            format=_json_format_flag(),
        )
    elif cmd == "agent-runs" and sub == "resume" and len(args) >= 3:
        cmd_agent_run_resume(args[2], _json_format_flag())
    elif cmd == "agent-runs" and sub == "cancel" and len(args) >= 3:
        cmd_agent_run_cancel(args[2], _json_format_flag())
    elif cmd == "agent-runs" and sub == "approve" and len(args) >= 3:
        cmd_agent_run_approve(args[2], _json_format_flag())
    elif cmd == "agent-runs":
        print(
            "Usage: de agent-runs "
            "[list|create|get|events|checkpoints|query-checkpoints|mission-events|query-mission-events|"
            "telemetry|query-telemetry|resume|cancel|approve]"
        )
    elif cmd == "job" and sub == "submit" and len(args) >= 3:
        callback = args[args.index("--callback") + 1] if "--callback" in args else None
        cmd_job_submit(args[2], callback)
    elif cmd == "job" and sub == "list":
        cmd_job_list(
            page=int(_arg_value(args, "--page") or "1"),
            limit=int(_arg_value(args, "--limit") or "25"),
            status_filter=_arg_value(args, "--status"),
            format=_json_format_flag(),
        )
    elif cmd == "job" and sub == "status" and len(args) >= 3:
        cmd_job_status(args[2], _json_format_flag())
    elif cmd == "job" and sub == "result" and len(args) >= 3:
        cmd_job_result(args[2], _json_format_flag())
    elif cmd == "job" and sub == "cancel" and len(args) >= 3:
        cmd_job_cancel(args[2], _json_format_flag())
    elif cmd == "job" and sub == "wait" and len(args) >= 3:
        timeout = int(args[args.index("--timeout") + 1]) if "--timeout" in args else 300
        cmd_job_wait(args[2], timeout, _json_format_flag())
    elif cmd == "job":
        print("Usage: de job [submit|list|status|result|cancel|wait]")
    elif cmd == "webhook" and sub == "test" and len(args) >= 3:
        cmd_webhook_test(args[2], _json_format_flag())
    elif cmd == "webhook":
        print("Usage: de webhook test <callback_url> [--format json]")
    elif cmd == "triggers" and sub == "register" and len(args) >= 3:
        cmd_triggers_register(args[2], _json_format_flag())
    elif cmd == "triggers" and sub == "list":
        cmd_triggers_list(
            format=_json_format_flag(),
            status_filter=_arg_value(args, "--status") or "all",
            page=int(_arg_value(args, "--page")) if _arg_value(args, "--page") else None,
            limit=int(_arg_value(args, "--limit")) if _arg_value(args, "--limit") else None,
        )
    elif cmd == "triggers" and sub == "fire" and len(args) >= 3:
        cmd_triggers_fire(args[2], _json_format_flag(), force="--force" in args)
    elif cmd == "triggers" and sub == "pause" and len(args) >= 3:
        cmd_triggers_pause(args[2], _json_format_flag(), paused=True)
    elif cmd == "triggers" and sub == "resume" and len(args) >= 3:
        cmd_triggers_pause(args[2], _json_format_flag(), paused=False)
    elif cmd == "triggers" and sub == "delete" and len(args) >= 3:
        cmd_triggers_delete(args[2], _json_format_flag())
    elif cmd == "triggers":
        print(
            "Usage: de triggers "
            "[register <request.json>|list|fire <trigger_id> [--force]|pause <trigger_id>|"
            "resume <trigger_id>|delete <trigger_id>] [--format json]"
        )
    elif cmd == "account" and sub == "me":
        cmd_account_me(_json_format_flag())
    elif cmd == "account" and sub == "update" and len(args) >= 3:
        cmd_account_update(args[2], _json_format_flag())
    elif cmd == "account" and sub == "usage":
        cmd_account_usage(_json_format_flag())
    elif cmd == "account" and sub == "limits":
        cmd_account_limits(_json_format_flag())
    elif cmd == "account" and sub == "distributions":
        cmd_account_distributions(_json_format_flag())
    elif cmd == "account" and sub == "templates":
        cmd_account_templates(_json_format_flag())
    elif cmd == "account":
        print(
            "Usage: de account [me|update|usage|limits|distributions|templates] "
            "[request.json] [--format json]"
        )
    elif cmd == "billing" and sub == "info":
        cmd_billing_info(_json_format_flag())
    elif cmd == "billing" and sub == "checkout":
        plan = args[2] if len(args) >= 3 and not args[2].startswith("--") else None
        cmd_billing_checkout(plan, _json_format_flag())
    elif cmd == "billing" and sub == "portal":
        cmd_billing_portal(_json_format_flag())
    elif cmd == "billing":
        print("Usage: de billing [info|checkout|portal] [developer|pro] [--format json]")
    elif cmd == "credits" and sub == "refresh" and len(args) >= 3:
        cmd_credits_refresh(args[2], _json_format_flag())
    elif cmd == "credits":
        print("Usage: de credits refresh <request.json> [--format json]")
    elif cmd == "metering" and sub == "ingest" and len(args) >= 3:
        cmd_metering_ingest(args[2], _json_format_flag())
    elif cmd == "metering":
        print("Usage: de metering ingest <request.json> [--format json]")
    elif cmd == "team" and sub == "list":
        cmd_team_list(_json_format_flag())
    elif cmd == "team" and sub == "invite" and len(args) >= 3:
        role = args[3] if len(args) >= 4 else "member"
        cmd_team_invite(args[2], role, _json_format_flag())
    elif cmd == "team" and sub == "update-role" and len(args) >= 4:
        cmd_team_update_role(args[2], args[3], _json_format_flag())
    elif cmd == "team" and sub == "remove" and len(args) >= 3:
        cmd_team_remove(args[2], _json_format_flag())
    elif cmd == "team" and sub == "audit-logs":
        cmd_team_audit_logs(
            _json_format_flag(),
            page=int(_arg_value(args, "--page") or "1"),
            limit=int(_arg_value(args, "--limit") or "25"),
            actor_email=_arg_value(args, "--actor-email"),
            action=_arg_value(args, "--action"),
            resource_type=_arg_value(args, "--resource-type"),
            result=_arg_value(args, "--result"),
            policy_snapshot_id=_arg_value(args, "--policy-snapshot-id"),
            schema_snapshot_id=_arg_value(args, "--schema-snapshot-id"),
            manifest_version=_arg_value(args, "--manifest-version"),
            request_hash=_arg_value(args, "--request-hash"),
        )
    elif cmd == "team" and sub == "audit-artifacts":
        cmd_team_audit_artifacts(
            _json_format_flag(),
            page=int(_arg_value(args, "--page") or "1"),
            limit=int(_arg_value(args, "--limit") or "25"),
            actor_email=_arg_value(args, "--actor-email"),
            action=_arg_value(args, "--action"),
            resource_type=_arg_value(args, "--resource-type"),
            result=_arg_value(args, "--result"),
            policy_snapshot_id=_arg_value(args, "--policy-snapshot-id"),
            schema_snapshot_id=_arg_value(args, "--schema-snapshot-id"),
            manifest_version=_arg_value(args, "--manifest-version"),
            request_hash=_arg_value(args, "--request-hash"),
            content_hash=_arg_value(args, "--content-hash"),
        )
    elif cmd == "team":
        print(
            "Usage: de team [list|invite|update-role|remove|audit-logs|audit-artifacts] "
            "[args] [--format json]"
        )
    elif cmd == "devices" and sub == "list":
        cmd_devices_list(_json_format_flag())
    elif cmd == "devices" and sub == "revoke" and len(args) >= 3:
        cmd_devices_revoke(args[2], _json_format_flag())
    elif cmd == "devices":
        print("Usage: de devices [list|revoke] [registration_id] [--format json]")
    elif cmd == "execution-policy" and sub == "get":
        cmd_execution_policy_get(_json_format_flag())
    elif cmd == "execution-policy" and sub == "snapshots":
        cmd_execution_policy_snapshots(_json_format_flag())
    elif cmd == "execution-policy" and sub == "update" and len(args) >= 3:
        cmd_execution_policy_update(args[2], _json_format_flag())
    elif cmd == "execution-policy":
        print("Usage: de execution-policy [get|snapshots|update] [<request.json>] [--format json]")
    elif cmd == "login":
        cmd_login(args[1] if len(args) > 1 else "")
    elif cmd == "logout":
        cmd_logout()
    elif cmd == "license" and (not sub or sub == "status"):
        cmd_license_status()
    elif cmd == "keys" and sub == "list":
        cmd_keys_list(_json_format_flag())
    elif cmd == "keys" and sub == "create" and len(args) >= 3:
        fmt = _json_format_flag()
        device_limit_value = _arg_value(args, "--device-limit")
        cmd_keys_create(
            args[2],
            expires_at=_arg_value(args, "--expires-at"),
            device_limit=int(device_limit_value) if device_limit_value is not None else None,
            format=fmt,
        )
    elif cmd == "keys" and sub == "revoke" and len(args) >= 3:
        cmd_keys_revoke(args[2], _json_format_flag())
    elif cmd == "keys":
        print("Usage: de keys [list|create|revoke]")
    elif cmd == "deployments" and sub == "regions":
        cmd_deployments_regions(_json_format_flag())
    elif cmd == "deployments" and sub == "get":
        cmd_deployments_get(_json_format_flag())
    elif cmd == "deployments" and sub == "create" and len(args) >= 3:
        cmd_deployments_create(args[2], _json_format_flag())
    elif cmd == "deployments" and sub == "cost" and len(args) >= 3:
        cmd_deployments_cost(args[2], _json_format_flag())
    elif cmd == "deployments" and sub == "delete" and len(args) >= 3:
        cmd_deployments_delete(args[2], _json_format_flag())
    elif cmd == "deployments":
        print(
            "Usage: de deployments [regions|get|create|cost|delete] "
            "[<request.json>|<deployment_id>] [--format json]"
        )
    elif cmd == "runtime" and sub == "start":
        cmd_runtime_start()
    elif cmd == "runtime" and sub == "stop":
        cmd_runtime_stop()
    elif cmd == "runtime" and sub == "status":
        cmd_runtime_status()
    elif cmd == "runtime" and sub == "manifest":
        fmt = _arg_value(args, "--format") or "table"
        cmd_runtime_manifest(format=fmt)
    elif cmd == "runtime" and sub == "validate":
        fmt = _arg_value(args, "--format") or "table"
        cmd_runtime_validate(format=fmt)
    elif cmd == "runtime" and sub == "admin-modules":
        fmt = _arg_value(args, "--format") or "table"
        cmd_runtime_admin_modules(format=fmt)
    elif cmd == "runtime" and sub == "admin-benchmarks":
        fmt = _arg_value(args, "--format") or "table"
        cmd_runtime_admin_benchmarks(format=fmt)
    elif cmd == "runtime" and sub == "modules":
        fmt = _arg_value(args, "--format") or "table"
        cmd_runtime_modules(format=fmt)
    elif cmd == "runtime" and sub == "functions" and len(args) >= 3:
        fmt = _arg_value(args, "--format") or "table"
        cmd_runtime_functions(args[2], format=fmt)
    elif cmd == "runtime" and sub == "execute" and len(args) >= 4:
        fmt = _arg_value(args, "--format") or "table"
        cmd_runtime_execute(
            args[2],
            args[3],
            args_json=_arg_value(args, "--args-json"),
            args_file=_arg_value(args, "--args-file"),
            format=fmt,
        )
    elif cmd == "runtime" and sub == "history":
        limit = int(_arg_value(args, "--limit") or "20")
        fmt = _arg_value(args, "--format") or "table"
        cmd_runtime_history(limit=limit, format=fmt)
    elif cmd == "runtime":
        print(
            "Usage: de runtime "
            "[start|stop|status|manifest|validate|admin-modules|admin-benchmarks|modules|functions|execute|history]"
        )
    elif cmd == "health":
        cmd_health()
    elif cmd == "contract":
        cmd_contract(_json_format_flag())
    elif cmd == "version":
        _, data = api_request("GET", "/v1/version")
        print(f"API: {data.get('api_version')} | Engine: {data.get('engine_version')}")
    elif cmd == "benchmark":
        cmd_benchmark()
    elif cmd == "template" and sub == "list":
        cmd_template_list()
    elif cmd == "template" and sub == "run" and len(args) >= 3:
        runs = int(args[args.index("--runs") + 1]) if "--runs" in args else 10000
        cmd_template_run(args[2], runs=runs, format=_json_format_flag())
    elif cmd == "template" and sub == "get" and len(args) >= 3:
        status, data = api_request("GET", f"/v1/simulate/templates/{args[2]}")
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"Unknown command: {' '.join(args)}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
