from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParityCapabilitySpec:
    capability: str
    cline_source: str
    docs_markers: tuple[str, ...]
    algenta_surface: str
    implementation_file: str
    proof_type: tuple[str, ...]
    proof_artifact: str
    required_level: str
    evaluator: str
    required: bool = True


DEFAULT_PARITY_CAPABILITY_SPECS: tuple[ParityCapabilitySpec, ...] = (
    ParityCapabilitySpec(
        capability="runtime.truth.manifest",
        cline_source="docs snapshot: ClineCore, Events, Permission Handling",
        docs_markers=("ClineCore", "Events", "Permission Handling"),
        algenta_surface="/manifest",
        implementation_file="agent-core/vendor/cline/algenta/run-server.ts",
        proof_type=("static", "integration"),
        proof_artifact="build/proofs/cline/runtime_contract_report.json",
        required_level="integration_proved",
        evaluator="runtime_manifest",
    ),
    ParityCapabilitySpec(
        capability="sessions.authoritative_api",
        cline_source="docs snapshot: ClineCore, Events",
        docs_markers=("ClineCore", "Events"),
        algenta_surface="/sessions create/list/get/messages/usage/events/delete",
        implementation_file="agent-core/vendor/cline/algenta/run-server.ts",
        proof_type=("static", "integration"),
        proof_artifact="build/proofs/cline/runtime_contract_report.json",
        required_level="integration_proved",
        evaluator="session_contract",
    ),
    ParityCapabilitySpec(
        capability="events.ndjson_sse_projection",
        cline_source="docs snapshot: Events",
        docs_markers=("Events",),
        algenta_surface="/sessions/:id/events[.ndjson|.sse]",
        implementation_file="agent-core/vendor/cline/algenta/run-server.ts",
        proof_type=("static", "integration"),
        proof_artifact="build/proofs/cline/runtime_contract_report.json",
        required_level="integration_proved",
        evaluator="events_projection",
    ),
    ParityCapabilitySpec(
        capability="usage.accumulated_usage_surface",
        cline_source="docs snapshot: Events",
        docs_markers=("Events",),
        algenta_surface="/sessions/:id/usage + getAccumulatedUsage()",
        implementation_file="agent-core/vendor/cline/algenta/server/execution.ts",
        proof_type=("static", "contract", "integration"),
        proof_artifact="build/proofs/cline/runs/<run_id>/usage.json",
        required_level="contract_proved",
        evaluator="usage_surface",
    ),
    ParityCapabilitySpec(
        capability="approvals.profile_artifact_plane",
        cline_source="docs snapshot: Permission Handling",
        docs_markers=("Permission Handling",),
        algenta_surface="approvals.json",
        implementation_file="agent-core/vendor/cline/algenta/server/artifacts.ts",
        proof_type=("static", "live"),
        proof_artifact="build/proofs/cline/runs/<run_id>/approvals.json",
        required_level="integration_proved",
        evaluator="approval_artifact",
    ),
    ParityCapabilitySpec(
        capability="plugins.algenta_tool_plane",
        cline_source="docs snapshot: Writing Plugins, MCP",
        docs_markers=("Writing Plugins", "MCP"),
        algenta_surface="localize, graph_query, simulate_patch plugin plane",
        implementation_file="agent-core/vendor/cline/algenta/algenta-plugin.ts",
        proof_type=("static", "live"),
        proof_artifact="build/proofs/cline/runs/<run_id>/tool_calls.json",
        required_level="integration_proved",
        evaluator="plugin_plane",
    ),
    ParityCapabilitySpec(
        capability="hooks.govern_hook_verdict",
        cline_source="docs snapshot: Hooks",
        docs_markers=("Hooks",),
        algenta_surface="govern_hook evidence in tool_calls.json",
        implementation_file="agent-core/vendor/cline/algenta/mojo-gate.ts",
        proof_type=("static", "live"),
        proof_artifact="build/proofs/cline/runs/<run_id>/tool_calls.json",
        required_level="integration_proved",
        evaluator="govern_hook",
    ),
    ParityCapabilitySpec(
        capability="engine.required_calls_gate",
        cline_source="docs snapshot: Writing Plugins, Permission Handling",
        docs_markers=("Writing Plugins", "Permission Handling"),
        algenta_surface="gate.json terminal_state engine_evidence_missing",
        implementation_file="agent-core/vendor/cline/algenta/server/artifacts.ts",
        proof_type=("static", "integration"),
        proof_artifact="build/proofs/cline/runs/<run_id>/gate.json",
        required_level="integration_proved",
        evaluator="engine_gate",
    ),
    ParityCapabilitySpec(
        capability="compatibility.run_wrapper",
        cline_source="docs snapshot: ClineCore, Events",
        docs_markers=("ClineCore", "Events"),
        algenta_surface="POST /run",
        implementation_file="agent-core/vendor/cline/algenta/run-server.ts",
        proof_type=("static", "contract"),
        proof_artifact="build/proofs/cline/runtime_contract_report.json",
        required_level="contract_proved",
        evaluator="run_wrapper",
    ),
    ParityCapabilitySpec(
        capability="channels.cli_repository_commands",
        cline_source="docs snapshot: GitHub Actions Integration",
        docs_markers=("GitHub Actions Integration",),
        algenta_surface="de repositories pipeline/simulate-patch/fix",
        implementation_file="apps/cli/main/_cmd_data_repos.py",
        proof_type=("static", "integration"),
        proof_artifact="build/proofs/cline/channel_parity_report.json",
        required_level="static_proved",
        evaluator="cli_channel",
    ),
    ParityCapabilitySpec(
        capability="channels.mcp_repository_tools",
        cline_source="docs snapshot: MCP",
        docs_markers=("MCP",),
        algenta_surface="run_repository_pipeline/simulate_repository_patch/run_repository_fix",
        implementation_file="apps/mcp_server/tools/repositories.py",
        proof_type=("static", "integration"),
        proof_artifact="build/proofs/cline/channel_parity_report.json",
        required_level="static_proved",
        evaluator="mcp_channel",
    ),
    ParityCapabilitySpec(
        capability="channels.github_workflow_split",
        cline_source="docs snapshot: GitHub Actions Integration, GitHub PR Review",
        docs_markers=("GitHub Actions Integration", "GitHub PR Review"),
        algenta_surface=".github/workflows/repository-intelligence-bot.yml",
        implementation_file=".github/workflows/repository-intelligence-bot.yml",
        proof_type=("static", "integration"),
        proof_artifact="build/proofs/cline/channel_parity_report.json",
        required_level="static_proved",
        evaluator="github_channel",
    ),
    ParityCapabilitySpec(
        capability="cursor.mcp_entrypoint",
        cline_source="docs snapshot: MCP, ACP: Editor Integrations",
        docs_markers=("MCP", "ACP: Editor Integrations"),
        algenta_surface="apps/mcp_server/README.md",
        implementation_file="apps/mcp_server/README.md",
        proof_type=("static",),
        proof_artifact="build/proofs/cline/channel_parity_report.json",
        required_level="static_proved",
        evaluator="cursor_docs",
    ),
    ParityCapabilitySpec(
        capability="teams.multi_agent_surface",
        cline_source="docs snapshot: Multi-Agent Teams",
        docs_markers=("Multi-Agent Teams",),
        algenta_surface="enable_agent_teams session policy",
        implementation_file="agent-core/vendor/cline/algenta/server/policy.ts",
        proof_type=("static",),
        proof_artifact="build/proofs/cline/runtime_contract_report.json",
        required_level="static_proved",
        evaluator="teams_surface",
    ),
    ParityCapabilitySpec(
        capability="automation.scheduled_agents_surface",
        cline_source="docs snapshot: Scheduled Agents",
        docs_markers=("Scheduled Agents",),
        algenta_surface=(
            "buildScheduledAgentBlueprint()/buildScheduledAgentSessionPayload()"
        ),
        implementation_file="agent-core/vendor/cline/algenta/scheduled-agents.ts",
        proof_type=("static",),
        proof_artifact="build/proofs/cline/parity_report.json",
        required_level="static_proved",
        evaluator="scheduled_agents_surface",
    ),
    ParityCapabilitySpec(
        capability="editor.acp_surface",
        cline_source="docs snapshot: ACP: Editor Integrations",
        docs_markers=("ACP: Editor Integrations",),
        algenta_surface=(
            "buildEditorIntegrationManifest()/buildCursorMcpConfig()/buildZedContextServerConfig()"
        ),
        implementation_file="agent-core/vendor/cline/algenta/acp-editor.ts",
        proof_type=("static",),
        proof_artifact="build/proofs/cline/parity_report.json",
        required_level="static_proved",
        evaluator="acp_editor_surface",
    ),
    ParityCapabilitySpec(
        capability="languages.static_runtime_coverage",
        cline_source="algenta execution spec: 180-language static proof",
        docs_markers=(),
        algenta_surface="build/proofs/cline/adapter_registry.json",
        implementation_file=(
            "apps/api_server/services/repository_intelligence_runtime_language_support.py"
        ),
        proof_type=("static", "integration"),
        proof_artifact="build/proofs/cline/adapter_registry.json",
        required_level="integration_proved",
        evaluator="language_adapter_registry",
    ),
    ParityCapabilitySpec(
        capability="languages.ranked_live_matrix_selection",
        cline_source="algenta execution spec: ranked live language selector",
        docs_markers=(),
        algenta_surface="build/proofs/cline/live_matrix_selection.json",
        implementation_file="apps/api_server/services/cline_live_matrix_selection.py",
        proof_type=("static", "integration"),
        proof_artifact="build/proofs/cline/live_matrix_selection.json",
        required_level="integration_proved",
        evaluator="language_live_matrix_selection",
    ),
)
