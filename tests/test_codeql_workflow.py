from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "codeql.yml"
CONFIG_PATH = ROOT / ".github" / "codeql" / "codeql-config.yml"
TPM_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "tpm.yml"
RUNTIME_WORKFLOW_PATH = ROOT / ".github" / "workflows" / "build-runtime.yml"
ACTION_SHA = "ff2f1c621b7f889edc0d3c761ac2e6a3f8cdb0dd"
CHECKOUT_SHA = "9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0"
SCOPE_SCRIPT = ROOT / "scripts" / "adaptive_codeql_scope.py"


def _load_yaml(path: Path) -> dict[str, object]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _steps_by_name(workflow: dict[str, object]) -> dict[str, dict[str, object]]:
    return {step["name"]: step for step in workflow["jobs"]["analyze"]["steps"]}


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
    action_steps = [step for step in steps if step.get("uses", "").startswith("github/codeql-action/")]

    assert len(action_steps) == 2
    for step in action_steps:
        action, sha = step["uses"].split("@", maxsplit=1)
        assert action in {"github/codeql-action/init", "github/codeql-action/analyze"}
        assert sha == ACTION_SHA
        assert re.fullmatch(r"[0-9a-f]{40}", sha)

    checkout = next(step for step in steps if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["uses"] == f"actions/checkout@{CHECKOUT_SHA}"

    init = next(step for step in action_steps if "/init@" in step["uses"])
    assert init["with"]["build-mode"] == "none"
    # Full scans keep the checked-in config; differential PR scans use the generated scope config.
    assert init["with"]["config-file"] == (
        "${{ steps.scope.outputs.decision == 'differential' && steps.scope.outputs.config_path"
        " || '.github/codeql/codeql-config.yml' }}"
    )


def test_codeql_workflow_scopes_pull_requests_via_codna_blast_radius() -> None:
    workflow = _load_yaml(WORKFLOW_PATH)
    steps = _steps_by_name(workflow)

    scope_step = steps["Compute adaptive scope (blast radius)"]
    assert scope_step["id"] == "scope"
    assert "scripts/adaptive_codeql_scope.py" in scope_step["run"]
    assert '--language "${{ matrix.language }}"' in scope_step["run"]
    assert SCOPE_SCRIPT.is_file()

    # Legs with an empty scope exit early and never run the scanner.
    skip_step = steps["Skip analysis (nothing in scope for this language)"]
    assert skip_step["if"] == "steps.scope.outputs.decision == 'skip'"
    init = steps["Initialize CodeQL"]
    analyze = steps["Perform CodeQL analysis"]
    assert init["if"] == "steps.scope.outputs.decision != 'skip'"
    assert analyze["if"] == "steps.scope.outputs.decision != 'skip'"

    # Differential runs never upload SARIF (no alert churn from partial scope); full runs keep the
    # stable upload contract and category.
    assert analyze["with"]["upload"] == (
        "${{ steps.scope.outputs.decision == 'full' && 'always' || 'never' }}"
    )
    assert analyze["with"]["category"] == "/language:${{ matrix.language }}"

    gate = steps["Gate on alerts inside the differential scope"]
    assert gate["if"] == "steps.scope.outputs.decision == 'differential'"
    assert "suppressions" in gate["run"]
    assert "sys.exit(1)" in gate["run"]


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
    job = workflow["jobs"]["clean-machine-contract"]
    doctor_step = next(
        step for step in job["steps"]
        if step.get("name") == "Clean-machine install + runtime doctor (amd64 container)"
    )
    assert "docker_retry.sh" in doctor_step["run"]
    assert "--platform linux/amd64" in doctor_step["run"]
    assert ".github/scripts/clean_machine_contract_linux_amd64.sh" in doctor_step["run"]

    # The trust-anchor pairing now lives in the container script the job executes; pin the
    # contract there (downloaded wheel's release key becomes the algenta build's anchor).
    contract_script = (
        ROOT / ".github" / "scripts" / "clean_machine_contract_linux_amd64.sh"
    ).read_text(encoding="utf-8")
    assert 'Path("dist-runtime").glob("*.whl")' in contract_script
    assert '"algenta_runtime_native/algenta_release_pub.pem"' in contract_script
    assert '"packages/algenta/algenta/_keys/algenta_release_pub.pem"' in contract_script
    assert "-----BEGIN PUBLIC KEY-----" in contract_script
