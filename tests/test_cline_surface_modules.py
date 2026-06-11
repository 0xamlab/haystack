from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCHEDULED_AGENTS_MODULE = (
    ROOT / "agent-core" / "vendor" / "cline" / "algenta" / "scheduled-agents.ts"
)
ACP_EDITOR_MODULE = (
    ROOT / "agent-core" / "vendor" / "cline" / "algenta" / "acp-editor.ts"
)

pytestmark = pytest.mark.skipif(
    shutil.which("bun") is None,
    reason="bun is required for Cline surface module tests",
)


def _bun_json(script: str) -> object:
    result = subprocess.run(
        [shutil.which("bun") or "bun", "-e", script],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"bun execution failed with code {result.returncode}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return json.loads(result.stdout)


def test_scheduled_agents_surface_builds_blueprint_with_deterministic_defaults() -> None:
    payload = _bun_json(
        f"""
const mod = await import({json.dumps(SCHEDULED_AGENTS_MODULE.resolve().as_uri())});
const output = mod.buildScheduledAgentBlueprint({{
  scheduleId: "nightly-repo-fix",
  repositoryScope: "repo_123",
  workingDir: "/tmp/worktree",
  prompt: "Fix the failing integration test.",
  cronSpecsDir: "/tmp/cron",
  engine: {{
    url: "http://127.0.0.1:8000",
    snapshotId: "snap_001",
    requiredTools: ["simulate_patch"],
    expectedCalls: ["simulate_patch"],
    failOnZeroCalls: true,
  }},
  toolPolicies: {{
    simulate_patch: {{ enabled: true, autoApprove: false }},
  }},
}});
console.log(JSON.stringify(output));
"""
    )

    assert payload["manifest"]["approval_profile"] == "ci_controlled_repo_automation"
    assert payload["manifest"]["allowed_write_scope"] == [
        "patch_artifact",
        "bot_branch",
        "pr_comment",
        "check_summary",
    ]
    assert payload["manifest"]["config_extensions"] == ["plugins", "skills"]
    assert (
        payload["requestHeaders"]["x-session-owner"]
        == "scheduled-agent:nightly-repo-fix"
    )
    assert payload["automationOptions"]["cronScope"] == "workspace"
    assert payload["automationOptions"]["autoStart"] is True
    assert payload["sessionCreatePayload"]["task_spec"]["engine"]["snapshot_id"] == "snap_001"
    assert payload["sessionCreatePayload"]["task_spec"]["engine"]["required_tools"] == [
        "simulate_patch"
    ]
    assert payload["sessionCreatePayload"]["idempotency_key"].startswith(
        "scheduled-agent:nightly-repo-fix:"
    )
    assert payload["runtimeBootstrap"]["localRuntime"]["configExtensions"] == [
        "plugins",
        "skills",
    ]


def test_scheduled_agents_surface_fails_closed_on_invalid_write_scope() -> None:
    payload = _bun_json(
        f"""
const mod = await import({json.dumps(SCHEDULED_AGENTS_MODULE.resolve().as_uri())});
try {{
  mod.buildScheduledAgentBlueprint({{
    scheduleId: "review-only",
    repositoryScope: "repo_123",
    workingDir: "/tmp/worktree",
    prompt: "Review this repository.",
    cronSpecsDir: "/tmp/cron",
    approvalProfile: "repository_review",
    allowedWriteScope: ["bot_branch"],
  }});
  console.log(JSON.stringify({{ ok: true }}));
}} catch (error) {{
  console.log(JSON.stringify({{
    ok: false,
    message: error instanceof Error ? error.message : String(error),
  }}));
}}
"""
    )

    assert payload == {
        "ok": False,
        "message": "allowed_write_scope may only reduce profile permissions for repository_review.",
    }


def test_acp_editor_surface_builds_cursor_and_zed_configs() -> None:
    payload = _bun_json(
        f"""
const mod = await import({json.dumps(ACP_EDITOR_MODULE.resolve().as_uri())});
const output = {{
  cursor: mod.buildCursorMcpConfig({{
    serverName: "algenta",
    baseUrl: "http://localhost:8000",
    extraEnv: {{ ALGENTA_REGION: "local" }},
  }}),
  zed: mod.buildZedContextServerConfig({{
    serverName: "algenta",
  }}),
  claude: mod.buildClaudeDesktopMcpConfig({{
    serverName: "algenta",
  }}),
  manifest: mod.buildEditorIntegrationManifest({{
    serverName: "algenta",
  }}),
  rendered: mod.renderEditorConfigJson(mod.buildCursorMcpConfig({{
    serverName: "algenta",
  }})),
}};
console.log(JSON.stringify(output));
"""
    )

    assert payload["cursor"]["mcpServers"]["algenta"]["command"] == "python"
    assert payload["cursor"]["mcpServers"]["algenta"]["env"]["ALGENTA_BASE_URL"] == (
        "http://localhost:8000"
    )
    assert payload["cursor"]["mcpServers"]["algenta"]["env"]["ALGENTA_REGION"] == "local"
    assert payload["zed"]["context_servers"]["algenta"]["command"]["path"] == "python"
    assert payload["claude"]["mcpServers"]["algenta"]["env"]["ALGENTA_BASE_URL"] == (
        "http://localhost:8000"
    )
    assert payload["manifest"][0]["editor"] == "cursor"
    assert payload["manifest"][1]["editor"] == "zed"
    assert payload["manifest"][2]["editor"] == "claude_desktop"
    assert payload["manifest"][0]["entrypoint_tools"] == [
        "run_repository_pipeline",
        "simulate_repository_patch",
        "run_repository_fix",
    ]
    assert "run_repository_fix" in payload["manifest"][0]["example_prompts"][0]
    assert payload["rendered"].endswith("\n")
