"""
MCP tool registry — full capability inventory.

140 tools across 13 categories:
  Data onboarding    onboard_dataset, list_datasets, get_dataset_status, retrain_dataset
  Data access        connect_data, list_data, get_data_summary,
                     get_data_schema, refresh_data, disconnect_data
  Schema discovery   register_source, list_sources, get_source_schema,
                     list_connectors, create_connector, get_connector,
                     update_connector, test_connector, browse_connector,
                     preview_test_connector, preview_browse_connector,
                     delete_connector
  Query & ingest     query_data, query_batch, query_sql_report, ingest_data
  LLM utilities      list_models, resolve_artifact_bridge, tokenize, count_tokens, chat_completions, responses,
                     embeddings, embedding_similarity, rerank
  Runtime libraries  list_runtime_libraries, execute_runtime_library (API-backed in this
                     standalone package -- the Algenta deployment owns the bundled
                     compute lifecycle)
  Capability plane   list_capability_providers, list_capability_bindings,
                     create_capability_binding, test_capability_binding,
                     discover_capability_binding, list_capabilities, get_capability,
                     route_capabilities, execute_capability, list_skills, enable_skill,
                     disable_skill
  Decisions          plan_decision, product_decision, product_agent_run,
                     product_optimize, product_retrieve, product_forecast,
                     simulate, recommend, score, batch, compare, submit_job,
                     list_jobs, get_job_status, poll_job, get_job_result, cancel_job,
                     test_webhook_delivery
  Agent runtime      create_agent_run, list_agent_runs, get_agent_run, get_agent_run_events,
                     get_agent_run_checkpoints, query_agent_run_checkpoints,
                     get_agent_run_mission_events,
                     query_agent_run_mission_events, get_agent_run_telemetry,
                     query_agent_run_telemetry, resume_agent_run, cancel_agent_run,
                     approve_agent_run
  Control plane      list_deployment_regions, get_deployment, create_deployment,
                     get_deployment_cost, delete_deployment, list_team_members,
                     invite_team_member, update_team_member_role, remove_team_member,
                     list_devices, revoke_device, get_audit_logs,
                     get_execution_policy, update_execution_policy,
                     get_billing_info, create_billing_checkout, create_billing_portal,
                     refresh_credits, ingest_metering_events
  Observability      get_contract, get_runtime_manifest, get_runtime_modules,
                     get_runtime_benchmarks, get_runtime_release_validation,
                     get_me, get_limits, list_distributions, list_templates,
                     list_api_keys, create_api_key,
                     update_me, revoke_api_key, list_runs, get_run, get_analytics, get_usage
  Decision Memory    log_decision, list_decisions, record_outcome
  Triggers           register_trigger, list_triggers, fire_trigger, pause_trigger, delete_trigger

Every tool is available identically via:
  stdio  → Claude Desktop, Cursor, Zed, Windsurf, VS Code
  HTTP   → ChatGPT, OpenWebUI, LibreChat, n8n, custom apps
  /mcp/* → embedded in the main API server
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, TypedDict

from algenta_mcp.tools import (
    account,
    agent_runs,
    analytics,
    capability_plane,
    connectors,
    control_plane,
    data,
    datasets,
    decisions,
    deployments,
    ingest,
    jobs,
    llm,
    meta,
    products,
    query,
    recommend,
    repositories,
    runs,
    runtime_libraries,
    simulate,
    sources,
    triggers,
    usage,
)

ToolSpec = dict[str, Any]


class ToolEntry(TypedDict):
    spec: ToolSpec
    handler: Callable[[dict[str, Any]], Awaitable[str]]


TOOLS: dict[str, ToolEntry] = {
    # ── Data onboarding — schema profiling + semantic training lifecycle ────────
    "onboard_dataset": {"spec": datasets.ONBOARD_SPEC, "handler": datasets.onboard_handler},
    "list_datasets": {"spec": datasets.LIST_SPEC, "handler": datasets.list_handler},
    "get_dataset_status": {"spec": datasets.STATUS_SPEC, "handler": datasets.status_handler},
    "retrain_dataset": {"spec": datasets.RETRAIN_SPEC, "handler": datasets.retrain_handler},
    # ── Data access — high-level connection + dataset flow ────────────────────
    "connect_data": {"spec": data.CONNECT_SPEC, "handler": data.connect_handler},
    "list_data": {"spec": data.LIST_SPEC, "handler": data.list_handler},
    "get_data_summary": {"spec": data.GET_SUMMARY_SPEC, "handler": data.summary_handler},
    "get_data_schema": {"spec": data.GET_SCHEMA_SPEC, "handler": data.schema_handler},
    "refresh_data": {"spec": data.REFRESH_SPEC, "handler": data.refresh_handler},
    "disconnect_data": {"spec": data.DISCONNECT_SPEC, "handler": data.disconnect_handler},
    # ── Schema discovery — column profiling, formula detection, join detection ──
    "register_source": {"spec": sources.REGISTER_SPEC, "handler": sources.register_handler},
    "list_sources": {
        "spec": sources.LIST_SOURCES_SPEC,
        "handler": sources.list_sources_handler,
    },
    "get_source_schema": {
        "spec": sources.GET_SOURCE_SPEC,
        "handler": sources.get_source_handler,
    },
    "list_connectors": {
        "spec": connectors.LIST_CONNECTORS_SPEC,
        "handler": connectors.list_connectors_handler,
    },
    "create_connector": {
        "spec": connectors.CREATE_CONNECTOR_SPEC,
        "handler": connectors.create_connector_handler,
    },
    "get_connector": {
        "spec": connectors.GET_CONNECTOR_SPEC,
        "handler": connectors.get_connector_handler,
    },
    "update_connector": {
        "spec": connectors.UPDATE_CONNECTOR_SPEC,
        "handler": connectors.update_connector_handler,
    },
    "test_connector": {
        "spec": connectors.TEST_CONNECTOR_SPEC,
        "handler": connectors.test_connector_handler,
    },
    "browse_connector": {
        "spec": connectors.BROWSE_CONNECTOR_SPEC,
        "handler": connectors.browse_connector_handler,
    },
    "preview_test_connector": {
        "spec": connectors.PREVIEW_TEST_CONNECTOR_SPEC,
        "handler": connectors.preview_test_connector_handler,
    },
    "preview_browse_connector": {
        "spec": connectors.PREVIEW_BROWSE_CONNECTOR_SPEC,
        "handler": connectors.preview_browse_connector_handler,
    },
    "delete_connector": {
        "spec": connectors.DELETE_CONNECTOR_SPEC,
        "handler": connectors.delete_connector_handler,
    },
    "get_repository_intelligence_capabilities": {
        "spec": repositories.GET_REPOSITORY_INTELLIGENCE_CAPABILITIES_SPEC,
        "handler": repositories.get_repository_intelligence_capabilities_handler,
    },
    "create_repository_snapshot": {
        "spec": repositories.CREATE_REPOSITORY_SNAPSHOT_SPEC,
        "handler": repositories.create_repository_snapshot_handler,
    },
    "get_repository_snapshot": {
        "spec": repositories.GET_REPOSITORY_SNAPSHOT_SPEC,
        "handler": repositories.get_repository_snapshot_handler,
    },
    "triage_repository": {
        "spec": repositories.TRIAGE_REPOSITORY_SPEC,
        "handler": repositories.triage_repository_handler,
    },
    "create_repository_decision_plan": {
        "spec": repositories.CREATE_REPOSITORY_DECISION_PLAN_SPEC,
        "handler": repositories.create_repository_decision_plan_handler,
    },
    "query_repository_graph": {
        "spec": repositories.QUERY_REPOSITORY_GRAPH_SPEC,
        "handler": repositories.query_repository_graph_handler,
    },
    "simulate_repository": {
        "spec": repositories.SIMULATE_REPOSITORY_SPEC,
        "handler": repositories.simulate_repository_handler,
    },
    "run_repository_pipeline": {
        "spec": repositories.RUN_REPOSITORY_PIPELINE_SPEC,
        "handler": repositories.run_repository_pipeline_handler,
    },
    "simulate_repository_patch": {
        "spec": repositories.SIMULATE_REPOSITORY_PATCH_SPEC,
        "handler": repositories.simulate_repository_patch_handler,
    },
    "run_repository_fix": {
        "spec": repositories.RUN_REPOSITORY_FIX_SPEC,
        "handler": repositories.run_repository_fix_handler,
    },
    "apply_repository": {
        "spec": repositories.APPLY_REPOSITORY_SPEC,
        "handler": repositories.apply_repository_handler,
    },
    # ── Query & ingest — LLM converts intent, engine executes ─────────────────
    "query_data": {
        "spec": query.SPEC,
        "handler": query.handler,
    },
    "query_batch": {
        "spec": query.QUERY_BATCH_SPEC,
        "handler": query.query_batch_handler,
    },
    "query_sql_report": {
        "spec": query.QUERY_SQL_REPORT_SPEC,
        "handler": query.query_sql_report_handler,
    },
    "ingest_data": {
        "spec": ingest.SPEC,
        "handler": ingest.handler,
    },
    # ── LLM utilities — deterministic utility-model surface ──────────────────
    "list_models": {"spec": llm.LIST_MODELS_SPEC, "handler": llm.list_models_handler},
    "resolve_artifact_bridge": {
        "spec": llm.RESOLVE_ARTIFACT_BRIDGE_SPEC,
        "handler": llm.resolve_artifact_bridge_handler,
    },
    "tokenize": {"spec": llm.TOKENIZE_SPEC, "handler": llm.tokenize_handler},
    "count_tokens": {"spec": llm.COUNT_TOKENS_SPEC, "handler": llm.count_tokens_handler},
    "chat_completions": {
        "spec": llm.CHAT_COMPLETIONS_SPEC,
        "handler": llm.chat_completions_handler,
    },
    "responses": {"spec": llm.RESPONSES_SPEC, "handler": llm.responses_handler},
    "embeddings": {"spec": llm.EMBEDDINGS_SPEC, "handler": llm.embeddings_handler},
    "embedding_similarity": {
        "spec": llm.EMBEDDING_SIMILARITY_SPEC,
        "handler": llm.embedding_similarity_handler,
    },
    "rerank": {"spec": llm.RERANK_SPEC, "handler": llm.rerank_handler},
    # ── Runtime libraries — API-backed in this standalone package ──
    # (the Algenta deployment owns the bundled compute lifecycle)
    "list_runtime_libraries": {
        "spec": runtime_libraries.LIST_RUNTIME_LIBRARIES_SPEC,
        "handler": runtime_libraries.list_runtime_libraries_handler,
    },
    "execute_runtime_library": {
        "spec": runtime_libraries.EXECUTE_RUNTIME_LIBRARY_SPEC,
        "handler": runtime_libraries.execute_runtime_library_handler,
    },
    # ── Capability plane — unified provider, binding, routing, and skill surfaces ──
    "list_capability_providers": {
        "spec": capability_plane.LIST_CAPABILITY_PROVIDERS_SPEC,
        "handler": capability_plane.list_capability_providers_handler,
    },
    "list_capability_bindings": {
        "spec": capability_plane.LIST_CAPABILITY_BINDINGS_SPEC,
        "handler": capability_plane.list_capability_bindings_handler,
    },
    "create_capability_binding": {
        "spec": capability_plane.CREATE_CAPABILITY_BINDING_SPEC,
        "handler": capability_plane.create_capability_binding_handler,
    },
    "test_capability_binding": {
        "spec": capability_plane.TEST_CAPABILITY_BINDING_SPEC,
        "handler": capability_plane.test_capability_binding_handler,
    },
    "discover_capability_binding": {
        "spec": capability_plane.DISCOVER_CAPABILITY_BINDING_SPEC,
        "handler": capability_plane.discover_capability_binding_handler,
    },
    "list_capabilities": {
        "spec": capability_plane.LIST_CAPABILITIES_SPEC,
        "handler": capability_plane.list_capabilities_handler,
    },
    "get_capability": {
        "spec": capability_plane.GET_CAPABILITY_SPEC,
        "handler": capability_plane.get_capability_handler,
    },
    "route_capabilities": {
        "spec": capability_plane.ROUTE_CAPABILITIES_SPEC,
        "handler": capability_plane.route_capabilities_handler,
    },
    "execute_capability": {
        "spec": capability_plane.EXECUTE_CAPABILITY_SPEC,
        "handler": capability_plane.execute_capability_handler,
    },
    "list_skills": {
        "spec": capability_plane.LIST_SKILLS_SPEC,
        "handler": capability_plane.list_skills_handler,
    },
    "enable_skill": {
        "spec": capability_plane.ENABLE_SKILL_SPEC,
        "handler": capability_plane.enable_skill_handler,
    },
    "disable_skill": {
        "spec": capability_plane.DISABLE_SKILL_SPEC,
        "handler": capability_plane.disable_skill_handler,
    },
    # ── Decisions — Monte Carlo, recommendations, async jobs ──────────────────
    "plan_decision": {
        "spec": decisions.PLAN_DECISION_SPEC,
        "handler": decisions.plan_decision_handler,
    },
    "product_decision": {
        "spec": products.PRODUCT_DECISION_SPEC,
        "handler": products.product_decision_handler,
    },
    "product_agent_run": {
        "spec": products.PRODUCT_AGENT_RUN_SPEC,
        "handler": products.product_agent_run_handler,
    },
    "product_optimize": {
        "spec": products.PRODUCT_OPTIMIZE_SPEC,
        "handler": products.product_optimize_handler,
    },
    "product_retrieve": {
        "spec": products.PRODUCT_RETRIEVE_SPEC,
        "handler": products.product_retrieve_handler,
    },
    "product_forecast": {
        "spec": products.PRODUCT_FORECAST_SPEC,
        "handler": products.product_forecast_handler,
    },
    "simulate": {"spec": simulate.SPEC, "handler": simulate.handler},
    "recommend": {"spec": recommend.SPEC, "handler": recommend.handler},
    "score": {"spec": recommend.SCORE_SPEC, "handler": recommend.score_handler},
    "batch": {"spec": recommend.BATCH_SPEC, "handler": recommend.batch_handler},
    "compare": {"spec": recommend.COMPARE_SPEC, "handler": recommend.compare_handler},
    "submit_job": {
        "spec": jobs.SUBMIT_JOB_SPEC,
        "handler": jobs.submit_job_handler,
    },
    "list_jobs": {
        "spec": jobs.LIST_JOBS_SPEC,
        "handler": jobs.list_jobs_handler,
    },
    "get_job_status": {
        "spec": jobs.GET_JOB_STATUS_SPEC,
        "handler": jobs.get_job_status_handler,
    },
    "poll_job": {
        "spec": jobs.POLL_JOB_SPEC,
        "handler": jobs.poll_job_handler,
    },
    "get_job_result": {
        "spec": jobs.GET_JOB_RESULT_SPEC,
        "handler": jobs.get_job_result_handler,
    },
    "cancel_job": {
        "spec": jobs.CANCEL_JOB_SPEC,
        "handler": jobs.cancel_job_handler,
    },
    "test_webhook_delivery": {
        "spec": jobs.TEST_WEBHOOK_DELIVERY_SPEC,
        "handler": jobs.test_webhook_delivery_handler,
    },
    # ── Agent runtime — persisted run lifecycle + events ─────────────────────
    "create_agent_run": {
        "spec": agent_runs.CREATE_AGENT_RUN_SPEC,
        "handler": agent_runs.create_agent_run_handler,
    },
    "list_agent_runs": {
        "spec": agent_runs.LIST_AGENT_RUNS_SPEC,
        "handler": agent_runs.list_agent_runs_handler,
    },
    "get_agent_run": {
        "spec": agent_runs.GET_AGENT_RUN_SPEC,
        "handler": agent_runs.get_agent_run_handler,
    },
    "get_agent_run_events": {
        "spec": agent_runs.GET_AGENT_RUN_EVENTS_SPEC,
        "handler": agent_runs.get_agent_run_events_handler,
    },
    "get_agent_run_checkpoints": {
        "spec": agent_runs.GET_AGENT_RUN_CHECKPOINTS_SPEC,
        "handler": agent_runs.get_agent_run_checkpoints_handler,
    },
    "query_agent_run_checkpoints": {
        "spec": agent_runs.QUERY_AGENT_RUN_CHECKPOINTS_SPEC,
        "handler": agent_runs.query_agent_run_checkpoints_handler,
    },
    "get_agent_run_mission_events": {
        "spec": agent_runs.GET_AGENT_RUN_MISSION_EVENTS_SPEC,
        "handler": agent_runs.get_agent_run_mission_events_handler,
    },
    "query_agent_run_mission_events": {
        "spec": agent_runs.QUERY_AGENT_RUN_MISSION_EVENTS_SPEC,
        "handler": agent_runs.query_agent_run_mission_events_handler,
    },
    "get_agent_run_telemetry": {
        "spec": agent_runs.GET_AGENT_RUN_TELEMETRY_SPEC,
        "handler": agent_runs.get_agent_run_telemetry_handler,
    },
    "query_agent_run_telemetry": {
        "spec": agent_runs.QUERY_AGENT_RUN_TELEMETRY_SPEC,
        "handler": agent_runs.query_agent_run_telemetry_handler,
    },
    "resume_agent_run": {
        "spec": agent_runs.RESUME_AGENT_RUN_SPEC,
        "handler": agent_runs.resume_agent_run_handler,
    },
    "cancel_agent_run": {
        "spec": agent_runs.CANCEL_AGENT_RUN_SPEC,
        "handler": agent_runs.cancel_agent_run_handler,
    },
    "approve_agent_run": {
        "spec": agent_runs.APPROVE_AGENT_RUN_SPEC,
        "handler": agent_runs.approve_agent_run_handler,
    },
    # ── Control plane — deployment regions + lifecycle ──────────────────────
    "list_deployment_regions": {
        "spec": deployments.LIST_DEPLOYMENT_REGIONS_SPEC,
        "handler": deployments.list_deployment_regions_handler,
    },
    "get_deployment": {
        "spec": deployments.GET_DEPLOYMENT_SPEC,
        "handler": deployments.get_deployment_handler,
    },
    "create_deployment": {
        "spec": deployments.CREATE_DEPLOYMENT_SPEC,
        "handler": deployments.create_deployment_handler,
    },
    "get_deployment_cost": {
        "spec": deployments.GET_DEPLOYMENT_COST_SPEC,
        "handler": deployments.get_deployment_cost_handler,
    },
    "delete_deployment": {
        "spec": deployments.DELETE_DEPLOYMENT_SPEC,
        "handler": deployments.delete_deployment_handler,
    },
    "list_team_members": {
        "spec": control_plane.LIST_TEAM_MEMBERS_SPEC,
        "handler": control_plane.list_team_members_handler,
    },
    "invite_team_member": {
        "spec": control_plane.INVITE_TEAM_MEMBER_SPEC,
        "handler": control_plane.invite_team_member_handler,
    },
    "update_team_member_role": {
        "spec": control_plane.UPDATE_TEAM_MEMBER_ROLE_SPEC,
        "handler": control_plane.update_team_member_role_handler,
    },
    "remove_team_member": {
        "spec": control_plane.REMOVE_TEAM_MEMBER_SPEC,
        "handler": control_plane.remove_team_member_handler,
    },
    "list_devices": {
        "spec": control_plane.LIST_DEVICES_SPEC,
        "handler": control_plane.list_devices_handler,
    },
    "revoke_device": {
        "spec": control_plane.REVOKE_DEVICE_SPEC,
        "handler": control_plane.revoke_device_handler,
    },
    "get_audit_logs": {
        "spec": control_plane.GET_AUDIT_LOGS_SPEC,
        "handler": control_plane.get_audit_logs_handler,
    },
    "get_audit_log_artifacts": {
        "spec": control_plane.GET_AUDIT_LOG_ARTIFACTS_SPEC,
        "handler": control_plane.get_audit_log_artifacts_handler,
    },
    "get_execution_policy": {
        "spec": control_plane.GET_EXECUTION_POLICY_SPEC,
        "handler": control_plane.get_execution_policy_handler,
    },
    "list_execution_policy_snapshots": {
        "spec": control_plane.LIST_EXECUTION_POLICY_SNAPSHOTS_SPEC,
        "handler": control_plane.list_execution_policy_snapshots_handler,
    },
    "get_billing_info": {
        "spec": control_plane.GET_BILLING_INFO_SPEC,
        "handler": control_plane.get_billing_info_handler,
    },
    "create_billing_checkout": {
        "spec": control_plane.CREATE_BILLING_CHECKOUT_SPEC,
        "handler": control_plane.create_billing_checkout_handler,
    },
    "create_billing_portal": {
        "spec": control_plane.CREATE_BILLING_PORTAL_SPEC,
        "handler": control_plane.create_billing_portal_handler,
    },
    "refresh_credits": {
        "spec": control_plane.REFRESH_CREDITS_SPEC,
        "handler": control_plane.refresh_credits_handler,
    },
    "ingest_metering_events": {
        "spec": control_plane.INGEST_METERING_EVENTS_SPEC,
        "handler": control_plane.ingest_metering_events_handler,
    },
    "update_execution_policy": {
        "spec": control_plane.UPDATE_EXECUTION_POLICY_SPEC,
        "handler": control_plane.update_execution_policy_handler,
    },
    # ── Observability — history, analytics, usage ─────────────────────────────
    "get_contract": {"spec": meta.GET_CONTRACT_SPEC, "handler": meta.get_contract_handler},
    "get_runtime_manifest": {
        "spec": meta.GET_RUNTIME_MANIFEST_SPEC,
        "handler": meta.get_runtime_manifest_handler,
    },
    "get_runtime_release_validation": {
        "spec": meta.GET_RUNTIME_RELEASE_VALIDATION_SPEC,
        "handler": meta.get_runtime_release_validation_handler,
    },
    "get_runtime_modules": {
        "spec": meta.GET_RUNTIME_MODULES_SPEC,
        "handler": meta.get_runtime_modules_handler,
    },
    "get_runtime_benchmarks": {
        "spec": meta.GET_RUNTIME_BENCHMARKS_SPEC,
        "handler": meta.get_runtime_benchmarks_handler,
    },
    "get_me": {"spec": account.GET_ME_SPEC, "handler": account.get_me_handler},
    "update_me": {"spec": account.UPDATE_ME_SPEC, "handler": account.update_me_handler},
    "get_limits": {"spec": account.GET_LIMITS_SPEC, "handler": account.get_limits_handler},
    "list_distributions": {
        "spec": account.LIST_DISTRIBUTIONS_SPEC,
        "handler": account.list_distributions_handler,
    },
    "list_templates": {
        "spec": account.LIST_TEMPLATES_SPEC,
        "handler": account.list_templates_handler,
    },
    "list_api_keys": {
        "spec": account.LIST_API_KEYS_SPEC,
        "handler": account.list_api_keys_handler,
    },
    "create_api_key": {
        "spec": account.CREATE_API_KEY_SPEC,
        "handler": account.create_api_key_handler,
    },
    "revoke_api_key": {
        "spec": account.REVOKE_API_KEY_SPEC,
        "handler": account.revoke_api_key_handler,
    },
    "list_runs": {"spec": runs.LIST_RUNS_SPEC, "handler": runs.list_runs_handler},
    "get_run": {"spec": runs.GET_RUN_SPEC, "handler": runs.get_run_handler},
    "get_analytics": {"spec": analytics.SPEC, "handler": analytics.handler},
    "get_usage": {"spec": usage.SPEC, "handler": usage.handler},
    # ── Decision Memory — persist decisions + close the feedback loop ──────────
    "log_decision": {
        "spec": decisions.LOG_DECISION_SPEC,
        "handler": decisions.log_decision_handler,
    },
    "list_decisions": {
        "spec": decisions.LIST_DECISIONS_SPEC,
        "handler": decisions.list_decisions_handler,
    },
    "get_decision": {
        "spec": decisions.GET_DECISION_SPEC,
        "handler": decisions.get_decision_handler,
    },
    "record_outcome": {
        "spec": decisions.RECORD_OUTCOME_SPEC,
        "handler": decisions.record_outcome_handler,
    },
    "execute_decision": {
        "spec": decisions.EXECUTE_DECISION_SPEC,
        "handler": decisions.execute_decision_handler,
    },
    "delete_decision": {
        "spec": decisions.DELETE_DECISION_SPEC,
        "handler": decisions.delete_decision_handler,
    },
    # ── Triggers — real-time threshold detection + auto-simulation ────────────
    "register_trigger": {
        "spec": triggers.REGISTER_TRIGGER_SPEC,
        "handler": triggers.register_trigger_handler,
    },
    "list_triggers": {
        "spec": triggers.LIST_TRIGGERS_SPEC,
        "handler": triggers.list_triggers_handler,
    },
    "fire_trigger": {
        "spec": triggers.FIRE_TRIGGER_SPEC,
        "handler": triggers.fire_trigger_handler,
    },
    "pause_trigger": {
        "spec": triggers.PAUSE_TRIGGER_SPEC,
        "handler": triggers.pause_trigger_handler,
    },
    "delete_trigger": {
        "spec": triggers.DELETE_TRIGGER_SPEC,
        "handler": triggers.delete_trigger_handler,
    },
}


def get_tool_specs(allowed: frozenset[str] | None = None) -> list[ToolSpec]:
    """Return MCP tool spec dicts for the list_tools response.

    ``allowed`` is the caller's visible tool set (product edition ∩ entitlements,
    resolved upstream by the transport/auth layer). ``None`` means no restriction
    (unscoped/trusted key → full registry). An empty set yields no tools — the
    fail-closed result for an unknown/unentitled product.
    """
    if allowed is None:
        return [entry["spec"] for entry in TOOLS.values()]
    return [entry["spec"] for name, entry in TOOLS.items() if name in allowed]


async def call_tool(
    name: str, arguments: dict[str, Any], allowed: frozenset[str] | None = None
) -> str:
    """Dispatch a tool call by name. Raises KeyError for unknown tools.

    When ``allowed`` is provided, a tool outside that visible set is rejected as if
    it did not exist (fail closed) — a product edition is a hard boundary, not a
    hint the caller can bypass.
    """
    if allowed is not None and name not in allowed:
        raise KeyError(name)
    entry = TOOLS[name]
    return await entry["handler"](arguments)
