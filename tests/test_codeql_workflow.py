from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "codeql.yml"
CONFIG_PATH = ROOT / ".github" / "codeql" / "codeql-config.yml"
ACTION_SHA = "7211b7c8077ea37d8641b6271f6a365a22a5fbfa"


def _load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_codeql_workflow_scans_all_supported_repository_languages() -> None:
    workflow = _load_yaml(WORKFLOW_PATH)

    assert set(workflow["on"]) == {
        "push",
        "pull_request",
        "schedule",
        "workflow_dispatch",
    }
    assert "pull_request_target" not in workflow["on"]
    assert workflow["permissions"] == {"contents": "read"}

    analyze = workflow["jobs"]["analyze"]
    assert analyze["timeout-minutes"] == 20
    assert analyze["strategy"]["fail-fast"] is False
    assert analyze["strategy"]["matrix"]["language"] == [
        "actions",
        "javascript-typescript",
        "python",
    ]
    assert analyze["permissions"]["security-events"] == "write"


def test_codeql_actions_are_immutable_and_use_no_build_mode() -> None:
    workflow = _load_yaml(WORKFLOW_PATH)
    steps = workflow["jobs"]["analyze"]["steps"]
    action_steps = [step for step in steps if step["uses"].startswith("github/codeql-action/")]

    assert len(action_steps) == 2
    for step in action_steps:
        action, sha = step["uses"].split("@", maxsplit=1)
        assert action in {"github/codeql-action/init", "github/codeql-action/analyze"}
        assert sha == ACTION_SHA
        assert re.fullmatch(r"[0-9a-f]{40}", sha)

    init = next(step for step in action_steps if "/init@" in step["uses"])
    assert init["with"]["build-mode"] == "none"
    assert init["with"]["config-file"] == ".github/codeql/codeql-config.yml"


def test_codeql_scope_excludes_only_noncanonical_duplicate_trees() -> None:
    config = _load_yaml(CONFIG_PATH)

    assert config["paths-ignore"] == [
        "benchmarks/**",
        "tests/**",
        "build/**",
        "packages/python-sdk/build/**",
    ]

    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    config_text = CONFIG_PATH.read_text(encoding="utf-8")
    for production_path in ("apps/**", "packages/**", "scripts/**", ".github/**"):
        assert production_path not in config["paths-ignore"]
    assert "pull_request_target" not in workflow_text
    assert "paths:" not in config_text
