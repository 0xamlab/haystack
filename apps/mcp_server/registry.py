"""
MCP tool registry — full capability inventory.

30 tools across 8 categories:
  Data onboarding    onboard_dataset, list_datasets, get_dataset_status, retrain_dataset
  Data access        connect_data, list_data, get_data_schema, refresh_data, disconnect_data
  Schema discovery   register_source, list_sources, get_source_schema, list_connectors
  Query & ingest     query_data, ingest_data
  Decisions          simulate, recommend, submit_job, get_job_status
  Observability      list_runs, get_run, get_analytics, get_usage
  Decision Memory    log_decision, list_decisions, record_outcome
  Triggers           register_trigger, list_triggers, fire_trigger, delete_trigger

Every tool is available identically via:
  stdio  → Claude Desktop, Cursor, Zed, Windsurf, VS Code
  HTTP   → ChatGPT, OpenWebUI, LibreChat, n8n, custom apps
  /mcp/* → embedded in the main API server
"""
from __future__ import annotations

from typing import Any

from apps.mcp_server.tools import (
    analytics,
    connectors,
    data,
    datasets,
    decisions,
    ingest,
    jobs,
    query,
    recommend,
    runs,
    simulate,
    sources,
    triggers,
    usage,
)

ToolEntry = dict[str, Any]

TOOLS: dict[str, ToolEntry] = {
    # ── Data onboarding — schema profiling + semantic training lifecycle ────────
    "onboard_dataset":    {"spec": datasets.ONBOARD_SPEC,  "handler": datasets.onboard_handler},
    "list_datasets":      {"spec": datasets.LIST_SPEC,     "handler": datasets.list_handler},
    "get_dataset_status": {"spec": datasets.STATUS_SPEC,   "handler": datasets.status_handler},
    "retrain_dataset":    {"spec": datasets.RETRAIN_SPEC,  "handler": datasets.retrain_handler},

    # ── Data access — high-level connection + dataset flow ────────────────────
    "connect_data":       {"spec": data.CONNECT_SPEC,      "handler": data.connect_handler},
    "list_data":          {"spec": data.LIST_SPEC,         "handler": data.list_handler},
    "get_data_schema":    {"spec": data.GET_SCHEMA_SPEC,   "handler": data.schema_handler},
    "refresh_data":       {"spec": data.REFRESH_SPEC,      "handler": data.refresh_handler},
    "disconnect_data":    {"spec": data.DISCONNECT_SPEC,   "handler": data.disconnect_handler},

    # ── Schema discovery — column profiling, formula detection, join detection ──
    "register_source":    {"spec": sources.REGISTER_SPEC,      "handler": sources.register_handler},
    "list_sources": {
        "spec": sources.LIST_SOURCES_SPEC,
        "handler": sources.list_sources_handler,
    },
    "get_source_schema": {
        "spec": sources.GET_SOURCE_SPEC,
        "handler": sources.get_source_handler,
    },
    "list_connectors":    {"spec": connectors.SPEC,             "handler": connectors.handler},

    # ── Query & ingest — LLM converts intent, engine executes ─────────────────
    "query_data":         {"spec": query.SPEC,   "handler": query.handler},
    "ingest_data":        {"spec": ingest.SPEC,  "handler": ingest.handler},

    # ── Decisions — Monte Carlo, recommendations, async jobs ──────────────────
    "simulate":           {"spec": simulate.SPEC,                "handler": simulate.handler},
    "recommend":          {"spec": recommend.SPEC,               "handler": recommend.handler},
    "submit_job": {
        "spec": jobs.SUBMIT_JOB_SPEC,
        "handler": jobs.submit_job_handler,
    },
    "get_job_status": {
        "spec": jobs.GET_JOB_STATUS_SPEC,
        "handler": jobs.get_job_status_handler,
    },

    # ── Observability — history, analytics, usage ─────────────────────────────
    "list_runs":          {"spec": runs.LIST_RUNS_SPEC,  "handler": runs.list_runs_handler},
    "get_run":            {"spec": runs.GET_RUN_SPEC,    "handler": runs.get_run_handler},
    "get_analytics":      {"spec": analytics.SPEC,       "handler": analytics.handler},
    "get_usage":          {"spec": usage.SPEC,           "handler": usage.handler},

    # ── Decision Memory — persist decisions + close the feedback loop ──────────
    "log_decision": {
        "spec": decisions.LOG_DECISION_SPEC,
        "handler": decisions.log_decision_handler,
    },
    "list_decisions": {
        "spec": decisions.LIST_DECISIONS_SPEC,
        "handler": decisions.list_decisions_handler,
    },
    "record_outcome": {
        "spec": decisions.RECORD_OUTCOME_SPEC,
        "handler": decisions.record_outcome_handler,
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
    "delete_trigger": {
        "spec": triggers.DELETE_TRIGGER_SPEC,
        "handler": triggers.delete_trigger_handler,
    },
}


def get_tool_specs() -> list[dict[str, Any]]:
    """Return list of MCP tool spec dicts (for list_tools response)."""
    return [entry["spec"] for entry in TOOLS.values()]


async def call_tool(name: str, arguments: dict[str, Any]) -> str:
    """Dispatch a tool call by name. Raises KeyError for unknown tools."""
    entry = TOOLS[name]
    return await entry["handler"](arguments)
