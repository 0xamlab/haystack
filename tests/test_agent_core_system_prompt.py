from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADAPTER_IMPORT = "./agent-core/vendor/cline/algenta/adapter.ts"

pytestmark = pytest.mark.skipif(
    shutil.which("bun") is None,
    reason="bun is required to evaluate the agent-core TypeScript adapter",
)


def _build_system_prompt(args: dict[str, object]) -> str:
    script = (
        f"import {{ buildSystemPrompt }} from {json.dumps(ADAPTER_IMPORT)};\n"
        f"const prompt = buildSystemPrompt({json.dumps(args)});\n"
        "console.log(prompt);\n"
    )
    completed = subprocess.run(
        [shutil.which("bun") or "bun", "--eval", script],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


def test_build_system_prompt_biases_repo_relative_apply_patch_edits() -> None:
    prompt = _build_system_prompt(
        {
            "working_dir": str(ROOT),
            "prompt": "Fix the repository issue.",
            "injected_context": "Suspect files: src/app.ts",
        }
    )

    assert "repository-relative paths only" in prompt
    assert "Never use absolute paths like /src/app.ts." in prompt
    assert "Prefer apply_patch for minimal textual edits." in prompt


def test_build_system_prompt_lists_disabled_tools_and_evidence_guidance() -> None:
    prompt = _build_system_prompt(
        {
            "working_dir": str(ROOT),
            "prompt": "Fix the repository issue.",
            "tool_profile": "no_exploration_no_shell",
            "injected_context": "Suspect files: greet.py",
        }
    )

    assert "Do not call policy-disabled tools:" in prompt
    for tool_name in (
        "read_files",
        "search_codebase",
        "fetch_web_content",
        "ask_question",
        "run_commands",
    ):
        assert tool_name in prompt
    assert "Treat the injected repository evidence bundle as authoritative." in prompt
    assert "[REPOSITORY EVIDENCE BUNDLE" in prompt
