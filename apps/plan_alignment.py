from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

AlignmentStatus = Literal["implemented", "partial", "missing"]


@dataclass(frozen=True)
class PlanRouteStatus:
    method: str
    path: str
    status: AlignmentStatus
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class PlanTrancheStatus:
    pr: str
    focus: str
    status: AlignmentStatus
    rationale: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class PlanAlignmentSnapshot:
    public_llm_routes: tuple[PlanRouteStatus, ...]
    immediate_pr_sequence: tuple[PlanTrancheStatus, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "public_llm_routes": [asdict(route) for route in self.public_llm_routes],
            "immediate_pr_sequence": [asdict(pr) for pr in self.immediate_pr_sequence],
        }


PLANNED_PUBLIC_LLM_ROUTES: tuple[tuple[str, str], ...] = (
    ("GET", "/v1/models"),
    ("POST", "/v1/chat/completions"),
    ("POST", "/v1/responses"),
    ("POST", "/v1/embeddings"),
    ("POST", "/v1/rerank"),
    ("POST", "/v1/tokenize"),
    ("POST", "/v1/count_tokens"),
    ("GET", "/v1/agent/runs"),
    ("POST", "/v1/agent/runs"),
    ("GET", "/v1/agent/runs/checkpoints"),
    ("GET", "/v1/agent/runs/mission-events"),
    ("GET", "/v1/agent/runs/telemetry"),
    ("GET", "/v1/agent/runs/{run_id}"),
    ("GET", "/v1/agent/runs/{run_id}/events"),
    ("POST", "/v1/agent/runs/{run_id}/resume"),
    ("POST", "/v1/agent/runs/{run_id}/cancel"),
    ("POST", "/v1/agent/runs/{run_id}/approve"),
    ("POST", "/v1/decisions/plan"),
)

_ROUTE_EVIDENCE: dict[tuple[str, str], tuple[str, ...]] = {
    ("GET", "/v1/models"): ("apps/api_server/routers/llm.py",),
    ("POST", "/v1/chat/completions"): ("apps/api_server/routers/llm.py",),
    ("POST", "/v1/tokenize"): ("apps/api_server/routers/llm.py",),
    ("POST", "/v1/count_tokens"): ("apps/api_server/routers/llm.py",),
    ("POST", "/v1/responses"): ("apps/api_server/routers/llm.py",),
    ("POST", "/v1/embeddings"): ("apps/api_server/routers/llm.py",),
    ("POST", "/v1/rerank"): ("apps/api_server/routers/llm.py",),
    ("GET", "/v1/agent/runs"): ("apps/api_server/routers/agent_runs.py",),
    ("POST", "/v1/agent/runs"): ("apps/api_server/routers/agent_runs.py",),
    ("GET", "/v1/agent/runs/checkpoints"): ("apps/api_server/routers/agent_runs.py",),
    ("GET", "/v1/agent/runs/mission-events"): ("apps/api_server/routers/agent_runs.py",),
    ("GET", "/v1/agent/runs/telemetry"): ("apps/api_server/routers/agent_runs.py",),
    ("GET", "/v1/agent/runs/{run_id}"): ("apps/api_server/routers/agent_runs.py",),
    ("GET", "/v1/agent/runs/{run_id}/events"): ("apps/api_server/routers/agent_runs.py",),
    ("POST", "/v1/agent/runs/{run_id}/resume"): ("apps/api_server/routers/agent_runs.py",),
    ("POST", "/v1/agent/runs/{run_id}/cancel"): ("apps/api_server/routers/agent_runs.py",),
    ("POST", "/v1/agent/runs/{run_id}/approve"): ("apps/api_server/routers/agent_runs.py",),
    ("POST", "/v1/decisions/plan"): ("apps/api_server/routers/decisions.py",),
}


def _route_exists(method: str, path: str) -> bool:
    from apps.api_server.main import app

    method_lower = method.lower()
    for route in app.routes:
        route_path = getattr(route, "path", None)
        route_methods = {item.lower() for item in getattr(route, "methods", set())}
        if route_path == path and method_lower in route_methods:
            return True
    return False


def _route_status(method: str, path: str) -> PlanRouteStatus:
    implemented = _route_exists(method, path)
    return PlanRouteStatus(
        method=method,
        path=path,
        status="implemented" if implemented else "missing",
        evidence=_ROUTE_EVIDENCE.get((method, path), ()),
    )
def _tranche_statuses() -> tuple[PlanTrancheStatus, ...]:
    return (
        PlanTrancheStatus(
            pr="PR 0",
            focus="Runtime truth manifest",
            status="implemented",
            rationale="Signed runtime truth surfaces and admin proof routes are live.",
            evidence=("apps/runtime_manifest.py", "apps/api_server/routers/meta.py"),
        ),
        PlanTrancheStatus(
            pr="PR 1",
            focus="Maturity model and proof matrix",
            status="implemented",
            rationale="Runtime maturity/proof schema and release theorem enforcement are live.",
            evidence=("apps/runtime_manifest.py", "scripts/validate_runtime_release.py"),
        ),
        PlanTrancheStatus(
            pr="PR 2",
            focus="Python compatibility foundation",
            status="implemented",
            rationale="Python SDK sync/async facades and typed runtime models are present.",
            evidence=(
                "packages/python-sdk/decision_engine/client_facade.py",
                "packages/python-sdk/decision_engine/async_client_facade.py",
            ),
        ),
        PlanTrancheStatus(
            pr="PR 3",
            focus="OpenAI-compatible schemas and streaming",
            status="implemented",
            rationale=(
                "OpenAI-compatible utility schemas are live, including SSE streaming semantics "
                "for chat completions, responses, and agent-run event streams."
            ),
            evidence=(
                "apps/api_server/routers/llm.py",
                "apps/api_server/routers/agent_runs.py",
                "apps/api_server/routers/decisions.py",
            ),
        ),
        PlanTrancheStatus(
            pr="PR 4",
            focus="MCP core stabilization",
            status="implemented",
            rationale="Embedded MCP router, tool registry, and transport fallback contracts are live.",
            evidence=("apps/mcp_server/server.py", "apps/mcp_server/registry.py"),
        ),
        PlanTrancheStatus(
            pr="PR 5",
            focus="Provider clients and LiteLLM-style routing",
            status="partial",
            rationale=(
                "Config-driven provider model lanes now cover OpenAI-compatible, OpenAI, "
                "Anthropic, Ollama, Google GenAI, Mistral, Cohere, Groq, and xAI routing plus deterministic ordered "
                "provider-router aliases, nested router execution that preserves inner fallback or timeout policy, "
                "capability-aware route selection that skips incapable targets while still respecting bounded router "
                "fallback policy and capability-aware attempt budgets, resolved route or auth metadata that matches that effective "
                "reachability, and fail-closed config validation that rejects routers whose bounded fallback or "
                "attempt budget would leave a declared capability unreachable at runtime, "
                "provider-backed embeddings, and the unified responses surface, but the "
                "broader multi-provider and LiteLLM-style routing matrix is still not fully landed."
            ),
            evidence=(
                "apps/api_server/services/llm_provider_service.py",
                "apps/api_server/services/llm_api_service.py",
                "apps/api_server/routers/llm.py",
            ),
        ),
        PlanTrancheStatus(
            pr="PR 6",
            focus="Tokenizer and artifact bridge",
            status="implemented",
            rationale=(
                "Tokenizer-backed utility routes are live, the model catalog declares "
                "detected optional tokenizer/artifact bridge backends plus resolved "
                "Hugging Face cache-root and auth-alias state, and the shipped "
                "artifact resolver now provides the missing cache/download/auth bridge "
                "surface across API, SDKs, CLI, MCP, and maintained proofs."
            ),
            evidence=(
                "apps/api_server/routers/llm.py",
                "apps/api_server/services/llm_api_service.py",
                "packages/python-sdk/decision_engine/models_llm.py",
                "packages/algenta-core/algenta/runtime_model_llm.py",
                "packages/ts-sdk/src/types.ts",
                "apps/cli/main.py",
                "apps/mcp_server/tools/llm.py",
            ),
        ),
        PlanTrancheStatus(
            pr="PR 7",
            focus="Rust agent runtime",
            status="missing",
            rationale="No Rust agent runtime crate or agent run lifecycle exists in the repo.",
            evidence=(),
        ),
        PlanTrancheStatus(
            pr="PR 8",
            focus="Decision runtime convergence",
            status="implemented",
            rationale=(
                "Simulation, recommendation, score, batch, compare, and decision plan "
                "surfaces are real across the API, Python, Codna, and TypeScript "
                "client rings, plus the repo CLI and MCP operator surfaces."
            ),
            evidence=(
                "apps/api_server/routers/simulate.py",
                "apps/api_server/routers/recommend.py",
                "apps/api_server/routers/decisions.py",
                "apps/cli/main.py",
                "apps/mcp_server/tools/recommend.py",
                "packages/python-sdk/decision_engine/client_facade.py",
                "packages/algenta-core/algenta/client.py",
                "packages/algenta-core/algenta/runtime_facade.py",
                "packages/ts-sdk/src/client.ts",
                "packages/ts-sdk/src/runtime.ts",
            ),
        ),
        PlanTrancheStatus(
            pr="PR 9",
            focus="Evaluation and RAG quality gates",
            status="implemented",
            rationale=(
                "The signed runtime manifest, benchmark catalog, and release-validation surfaces "
                "now publish evaluation science plus replay, tool-call, RAG, and decision "
                "quality gate summaries across the API, typed client rings, CLI, and maintained "
                "live or OpenAPI proofs."
            ),
            evidence=(
                "apps/runtime_manifest.py",
                "apps/api_server/routers/meta.py",
                "apps/cli/main.py",
                "packages/python-sdk/decision_engine/client_contract_surface.py",
                "packages/algenta-core/algenta/runtime_execution_surface.py",
                "packages/ts-sdk/src/client.ts",
                "tests/integration/test_python_sdk.py",
                "tests/integration/test_algenta_client_live.py",
                "tests/integration/test_openapi.py",
            ),
        ),
        PlanTrancheStatus(
            pr="PR 10",
            focus="Enterprise control plane",
            status="implemented",
            rationale=(
                "Account, team, deployments, devices, audit logs or artifacts, and execution "
                "policy surfaces now span the API, Python, Codna, TypeScript, repo CLI, and "
                "MCP operator channels, with maintained live and lock coverage across those "
                "control-plane bands."
            ),
            evidence=(
                "apps/api_server/routers/account.py",
                "apps/api_server/routers/deployments.py",
                "apps/api_server/routers/team.py",
                "apps/api_server/routers/execution_policy.py",
                "apps/cli/main.py",
                "apps/mcp_server/tools/control_plane.py",
                "apps/mcp_server/tools/deployments.py",
                "packages/python-sdk/decision_engine/client_control_plane_surface.py",
                "packages/algenta-core/algenta/runtime_execution_surface.py",
                "packages/ts-sdk/src/client.ts",
                "packages/ts-sdk/src/runtime.ts",
                "tests/integration/test_python_sdk.py",
                "tests/integration/test_algenta_runtime_live.py",
                "tests/integration/test_typescript_runtime_live.py",
                "tests/integration/test_cli.py",
                "tests/integration/test_mcp_server.py",
            ),
        ),
        PlanTrancheStatus(
            pr="PR 11",
            focus="Billing and quotas",
            status="implemented",
            rationale=(
                "Billing, usage, limits, metering, and credit-refresh surfaces now span the "
                "API, Python, Codna, TypeScript, repo CLI, and MCP channels, with maintained "
                "live and lock coverage across those quota-control bands."
            ),
            evidence=(
                "apps/api_server/routers/billing.py",
                "apps/api_server/routers/metering.py",
                "apps/api_server/services/quota_service.py",
                "apps/api_server/routers/account.py",
                "apps/cli/main.py",
                "apps/mcp_server/tools/control_plane.py",
                "packages/python-sdk/decision_engine/client_control_plane_surface.py",
                "packages/algenta-core/algenta/runtime_execution_surface.py",
                "packages/ts-sdk/src/client.ts",
                "packages/ts-sdk/src/runtime.ts",
                "tests/integration/test_python_sdk.py",
                "tests/integration/test_algenta_client_live.py",
                "tests/integration/test_algenta_runtime_live.py",
                "tests/integration/test_typescript_sdk_client_live.py",
                "tests/integration/test_typescript_runtime_live.py",
                "tests/integration/test_cli.py",
                "tests/integration/test_mcp_server.py",
                "tests/integration/test_openapi.py",
            ),
        ),
        PlanTrancheStatus(
            pr="PR 12",
            focus="Deployment modes",
            status="implemented",
            rationale=(
                "Deployment modes are formalized in the manifest, validated in release output, "
                "and the deployment control surface now spans the API, Python, Codna, "
                "TypeScript, repo CLI, and MCP operator channels."
            ),
            evidence=(
                "apps/runtime_manifest.py",
                "apps/api_server/routers/deployments.py",
                "packages/python-sdk/decision_engine/client_facade.py",
                "packages/algenta-core/algenta/client.py",
                "packages/algenta-core/algenta/runtime_execution_surface.py",
                "packages/ts-sdk/src/client.ts",
                "packages/ts-sdk/src/runtime.ts",
                "apps/cli/main.py",
                "apps/mcp_server/tools/deployments.py",
            ),
        ),
    )


def collect_plan_alignment_snapshot() -> PlanAlignmentSnapshot:
    public_llm_routes = tuple(_route_status(method, path) for method, path in PLANNED_PUBLIC_LLM_ROUTES)
    return PlanAlignmentSnapshot(
        public_llm_routes=public_llm_routes,
        immediate_pr_sequence=_tranche_statuses(),
    )
