"""deployments, health, contract, runtime manifests/admin.

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
from apps.cli.main._cmd_runs_account import *  # noqa: F401, F403
from apps.cli.main._cmd_runs_account import (
    _cmd_agent_run_transition,
)


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
                "Failed to load Codna contract from /v1/meta/contract or /openapi.json."
            )
        try:
            data = build_platform_contract_from_openapi(
                api_base_url=_get_base_url(),
                openapi_payload=openapi_payload,
            )
        except PlatformContractFallbackError as exc:
            raise RuntimeError(
                f"Codna contract fallback failed [{exc.code}]: {exc}"
            ) from exc
    elif status >= 400:
        raise RuntimeError(f"Failed to load Codna contract: HTTP {status}")
    try:
        payload = PlatformContractResponse.model_validate(data)
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Codna contract endpoint returned an invalid payload.",
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

    print(f"\nCodna contract: {payload.contract_version}  [{payload.brand}]")
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
        raise RuntimeError(f"Failed to load Codna runtime manifest: HTTP {status}")
    try:
        manifest = RuntimeManifestResponse.model_validate(
            normalize_runtime_validation_payload(data)
        )
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Codna runtime manifest endpoint returned an invalid signed payload.",
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
        f"\nCodna runtime manifest: {manifest.runtime_version}  "
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
        raise RuntimeError(f"Failed to validate Codna runtime release: HTTP {status}")
    try:
        validation = RuntimeReleaseValidationResponse.model_validate(
            normalize_runtime_validation_payload(data)
        )
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Codna runtime validation endpoint returned an invalid signed payload.",
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
        f"\nCodna runtime release validation: {validation.runtime_version}  "
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
        raise RuntimeError(f"Failed to load Codna runtime module catalog: HTTP {status}")
    try:
        payload = RuntimeAdminModulesResponse.model_validate(
            normalize_runtime_validation_payload(data)
        )
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Codna runtime modules endpoint returned an invalid signed payload.",
                exc,
            )
        ) from exc
    if format == "json":
        print(json.dumps(payload.model_dump(mode="json"), indent=2, default=str))
        return

    print(
        f"\nCodna runtime module catalog: {payload.runtime_version}  "
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
        raise RuntimeError(f"Failed to load Codna runtime benchmark catalog: HTTP {status}")
    try:
        payload = RuntimeAdminBenchmarksResponse.model_validate(
            normalize_runtime_validation_payload(data)
        )
    except ValidationError as exc:
        raise RuntimeError(
            format_validation_error_message(
                "Codna runtime benchmarks endpoint returned an invalid signed payload.",
                exc,
            )
        ) from exc
    if format == "json":
        print(json.dumps(payload.model_dump(mode="json"), indent=2, default=str))
        return

    print(
        f"\nCodna runtime benchmark catalog: {payload.runtime_version}  "
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

