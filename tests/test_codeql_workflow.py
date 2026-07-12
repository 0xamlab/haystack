from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "codeql.yml"
CONFIG_PATH = ROOT / ".github" / "codeql" / "codeql-config.yml"
TPM_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "tpm.yml"
RUNTIME_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "build-runtime.yml"
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


def test_tpm_workflow_is_read_scoped_and_uses_immutable_actions() -> None:
    workflow = _load_yaml(TPM_WORKFLOW_PATH)

    assert workflow["permissions"] == {"contents": "read"}
    action_uses = [step["uses"] for step in workflow["jobs"]["tpm-roundtrip"]["steps"] if "uses" in step]
    assert action_uses
    assert all(re.fullmatch(r"[^@]+@[0-9a-f]{40}", value) for value in action_uses)


def test_runtime_publish_requires_persistent_signing_key() -> None:
    workflow = _load_yaml(RUNTIME_WORKFLOW_PATH)
    steps = workflow["jobs"]["build"]["steps"]
    release_expression = "${{ github.event_name == 'push' || inputs.publish == 'true' }}"
    guarded_steps = {
        step["name"]: step
        for step in steps
        if step.get("name") in {
            "Build + sign runtime manifest",
            "Build + sign Secure Enclave helper (macOS)",
        }
    }

    assert set(guarded_steps) == {
        "Build + sign runtime manifest",
        "Build + sign Secure Enclave helper (macOS)",
    }
    for step in guarded_steps.values():
        assert step["env"]["RUNTIME_RELEASE_PUBLISH"] == release_expression
        assert '[[ "${RUNTIME_RELEASE_PUBLISH:-false}" == "true" ]]' in step["run"]
        assert "exit 1" in step["run"]

    manifest_run = guarded_steps["Build + sign runtime manifest"]["run"]
    assert "ephemeral CI-only signing key" in manifest_run
    assert "non-publishing build" in manifest_run
    assert "packages/algenta/algenta/_keys/algenta_release_pub.pem" in manifest_run
    assert "does not match the embedded runtime release trust anchor" in manifest_run


def test_runtime_clean_machine_pairs_downloaded_release_key() -> None:
    workflow = _load_yaml(RUNTIME_WORKFLOW_PATH)
    steps = workflow["jobs"]["clean-machine-contract"]["steps"]
    pairing_step = next(
        step for step in steps if step.get("name") == "Pair runtime and Algenta trust anchor"
    )
    pairing_run = pairing_step["run"]

    assert 'Path("dist-runtime").glob("*.whl")' in pairing_run
    assert "algenta_runtime_native/algenta_release_pub.pem" in pairing_run
    assert '"packages/algenta/algenta/_keys/algenta_release_pub.pem"' in pairing_run
    assert "-----BEGIN PUBLIC KEY-----" in pairing_run
