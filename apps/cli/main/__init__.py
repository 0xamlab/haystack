"""
de — Codna CLI

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
    de contract                            # machine-readable Codna contract
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
    PYTHONPATH=. python3 -m apps.cli.main benchmark

Credential examples above are Cloud Managed examples. In `self_hosted` and
`air_gapped`, use the API key provisioned by your self-hosted operator
deployment instead. Private profiles fail closed and do not silently fall back
to Codna cloud.
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
_RUNTIME_NOT_RUNNING_MESSAGE = "Codna Runtime is not running. Start with: de runtime start"

_FACADE_API_REQUEST = api_request
_FACADE_API_STREAM_REQUEST = api_stream_request
_FACADE_LOAD_ENV_API_KEY = _load_env_api_key
_FACADE_PRIVATE_PROFILE_ENABLED = _private_profile_enabled
_FACADE_GET_BASE_URL = _get_base_url
_FACADE_GET_DASHBOARD_URL = _get_dashboard_url
_FACADE_ARG_VALUE = _arg_value
_FACADE_STORE_API_KEY_SECURE = _store_api_key_secure
_FACADE_STRIP_NONE = _strip_none
_FACADE_RICH = _RICH

from apps.cli.main._helpers import *  # noqa: F401, E402, F403
from apps.cli.main._helpers import (  # noqa: F401, E402
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
from apps.cli.main._cmd_data_repos import *  # noqa: F401, E402, F403
from apps.cli.main._cmd_data_repos import (  # noqa: F401, E402
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
from apps.cli.main._cmd_decisions_llm import *  # noqa: F401, E402, F403
from apps.cli.main._cmd_runs_account import *  # noqa: F401, E402, F403
from apps.cli.main._cmd_runs_account import (  # noqa: F401, E402
    _cmd_agent_run_transition,
)
from apps.cli.main._cmd_deployments_runtime import *  # noqa: F401, E402, F403
from apps.cli.main._cmd_auth_daemon_bench import *  # noqa: F401, E402, F403
from apps.cli.main._cmd_auth_daemon_bench import (  # noqa: F401, E402
    _login_api_key_help_text,
    _wait_for_runtime_ready,
    _runtime_list_modules_sync,
    _load_runtime_execute_args,
)

# Keep the package facade as the source of truth. The extracted submodules
# proxy back to `apps.cli.main`, so wildcard imports must not replace these
# facade-bound functions with the proxy wrappers they export.
api_request = _FACADE_API_REQUEST
api_stream_request = _FACADE_API_STREAM_REQUEST
_load_env_api_key = _FACADE_LOAD_ENV_API_KEY
_private_profile_enabled = _FACADE_PRIVATE_PROFILE_ENABLED
_get_base_url = _FACADE_GET_BASE_URL
_get_dashboard_url = _FACADE_GET_DASHBOARD_URL
_arg_value = _FACADE_ARG_VALUE
_store_api_key_secure = _FACADE_STORE_API_KEY_SECURE
_strip_none = _FACADE_STRIP_NONE
_RICH = _FACADE_RICH

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
    elif cmd == "repositories" and sub == "pipeline" and len(args) >= 4:
        cmd_repositories_pipeline(args[2], args[3], _json_format_flag())
    elif cmd == "repositories" and sub == "simulate" and len(args) >= 4:
        cmd_repositories_simulate(args[2], args[3], _json_format_flag())
    elif cmd == "repositories" and sub == "simulate-patch" and len(args) >= 4:
        cmd_repositories_simulate_patch(args[2], args[3], _json_format_flag())
    elif cmd == "repositories" and sub == "fix" and len(args) >= 4:
        cmd_repositories_fix(args[2], args[3], _json_format_flag())
    elif cmd == "repositories" and sub == "apply" and len(args) >= 4:
        cmd_repositories_apply(args[2], args[3], _json_format_flag())
    elif cmd == "repositories":
        print(
            "Usage: de repositories capabilities [--format json]\n"
            "       de repositories "
            "[snapshot|triage|decision-plan|graph-query|pipeline|simulate|simulate-patch|fix|apply] "
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
