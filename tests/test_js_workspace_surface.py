from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RUN_REPO_PYTHON = ROOT / "scripts" / "run_repo_python.sh"
RUN_JS_TEST_SUITE = ROOT / "scripts" / "run_js_test_suite.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def test_root_package_json_exposes_repo_root_js_commands() -> None:
    payload = json.loads((ROOT / "package.json").read_text())

    assert payload["private"] is True
    assert payload["packageManager"] == "pnpm@10.15.0"
    assert payload["engines"]["node"] == ">=22.0.0"

    scripts = payload["scripts"]
    assert scripts["postinstall"] == (
        "pnpm --dir packages/ts-sdk install --lockfile=false && "
        "pnpm --dir apps/gateway install --lockfile=false"
    )
    assert scripts["test:js"] == "./scripts/run_js_test_suite.sh"
    test_js_script = RUN_JS_TEST_SUITE.read_text(encoding="utf-8")
    assert "unset ALGENTA_API_KEY" in test_js_script
    assert "unset DE_API_KEY" in test_js_script
    assert "unset ALGENTA_BASE_URL" in test_js_script
    assert "unset DE_BASE_URL" in test_js_script
    assert "unset ALGENTA_API_URL" in test_js_script
    assert (
        "pnpm --dir packages/ts-sdk test -- --run "
        "src/libraries.test.ts src/runtime_daemon_client.test.ts src/index.test.ts"
    ) in test_js_script
    assert "pnpm --dir apps/gateway test" in test_js_script
    assert (
        "pnpm --dir apps/gateway exec tsx --test ../../examples/shared/privacyProfile.test.ts"
    ) in test_js_script
    assert "tests/test_js_workspace_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_platform_contract_schema_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_schema_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_runtime_startup_smoke.py" in scripts["test:formal-runtime-foundation"]
    for suffix in (
        "test_algenta_runtime_llm_and_agent_surface_algenta_runtime_a.py",
        "test_algenta_runtime_llm_and_agent_surface_algenta_runtime_b.py",
        "test_algenta_runtime_llm_and_agent_surface_misc.py",
    ):
        assert f"tests/{suffix}" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_algenta_client_plan_surface.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "tests/test_mcp_llm_agent_tools.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_benchmark_inventory_surface.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_scorecard_suite_summaries.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_csv_pipeline_summary.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_benchmark_scorecard_sync.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_go_live_scorecard.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_live_integration_artifacts.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_llm_rollout_live_artifacts.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_llm_rollout_scorecard.py" in scripts["test:formal-runtime-foundation"]
    assert "tests/test_plan_alignment_matrix.py" in scripts["test:formal-runtime-foundation"]
    assert RUN_REPO_PYTHON.exists()
    assert scripts["test:formal-runtime-foundation"].startswith(
        'RUNTIME_WORKER="$PWD/build/go-live-runtime/simulate"; '
        "./scripts/run_repo_python.sh tests/integration/test_csv_pipeline.py && "
        "./scripts/run_repo_python.sh benchmarks/scorecard_suite_summaries.py && "
        'if [ "${DE_SKIP_GO_LIVE_VERIFY:-0}" != "1" ]; then ./scripts/run_repo_python.sh tests/go_live_verify.py --skip-pytest; fi && '
        'if [ -x "$RUNTIME_WORKER" ]; then export ALGENTA_NATIVE_WORKER="$RUNTIME_WORKER" ALGENTA_RUNTIME_WORKER="$RUNTIME_WORKER" ALGENTA_MOJO_BINARY="$RUNTIME_WORKER" MOJO_BINARY_PATH="$RUNTIME_WORKER"; fi && '
        "./scripts/run_repo_python.sh benchmarks/llm_rollout_proof_bundle.py --skip-live && "
        "./scripts/run_repo_python.sh -m pytest -q "
    )
    assert 'DE_SKIP_GO_LIVE_VERIFY:-0' in scripts["test:formal-runtime-foundation"]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_runtime_libraries_http_live.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_cli.py" in scripts["test:formal-runtime-foundation"]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_algenta_client_live.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_typescript_sdk_client_live.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_typescript_runtime_live.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_python_sdk.py" in scripts["test:formal-runtime-foundation"]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_algenta_runtime_live.py" in scripts[
        "test:formal-runtime-foundation"
    ]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_mcp_server.py" in scripts["test:formal-runtime-foundation"]
    assert "&& ./scripts/run_repo_python.sh tests/integration/test_openapi.py" in scripts["test:formal-runtime-foundation"]
    assert scripts["validate:formal-runtime-foundation"] == (
        "./scripts/run_repo_python.sh scripts/validate_runtime_release.py --format table"
    )
    assert scripts["lint"] == "pnpm --dir packages/ts-sdk lint && pnpm --dir apps/gateway lint"
    assert scripts["test"] == "pnpm test:js && pnpm test:formal-runtime-foundation"
    assert scripts["build"] == "pnpm --dir packages/ts-sdk build && pnpm --dir apps/gateway build"
    # The check graph must include every required stage (regression floor), but may add
    # more (e.g. the reliability guard + hardening tests) without churning this contract.
    check_graph = scripts["check"]
    for required_stage in (
        "pnpm lint",
        "pnpm test",
        "pnpm validate:formal-runtime-foundation",
        "pnpm build",
        "pnpm guard:reliability",
        "pnpm test:hardening",
    ):
        assert required_stage in check_graph, f"check graph is missing required stage: {required_stage}"


def test_makefile_exposes_root_js_targets() -> None:
    text = (ROOT / "Makefile").read_text()

    assert "REPO_PYTHON := ./scripts/run_repo_python.sh" in text
    assert "js-install:" in text
    assert "\t" + "pnpm install" in text
    assert "js-lint:" in text
    assert "\t" + "pnpm lint" in text
    assert "js-test:" in text
    assert "\t" + "pnpm test:js" in text
    assert "js-build:" in text
    assert "\t" + "pnpm build" in text
    assert "js-check:" in text
    makefile_after_js_check = text.split("js-check:", 1)[1].split("## Auto-format code", 1)[0]
    assert "\t" + "pnpm lint" in makefile_after_js_check
    assert "\t" + "pnpm test:js" in makefile_after_js_check
    assert "\t" + "pnpm build" in makefile_after_js_check
    assert "pnpm check" not in makefile_after_js_check
    assert "\t" + "pnpm test\n" not in makefile_after_js_check
    assert "test-unit:" in text
    assert "\t$(REPO_PYTHON) -m pytest tests/unit/ -v --tb=short" in text
    assert "test-integration:" in text
    assert "\t$(REPO_PYTHON) -m pytest tests/integration/ -v --tb=short" in text
    assert "test-contract:" in text
    assert "\t$(REPO_PYTHON) -m pytest $(CONTRACT_PYTEST_FILES) -v --tb=short && \\" in text
    assert "\t$(REPO_PYTHON) $(CONTRACT_SCRIPT_FILES)" in text
    assert "test-coverage:" in text
    assert (
        "\t$(REPO_PYTHON) -m pytest tests/unit/ tests/integration/ --cov=apps --cov-report=term-missing --cov-report=html"
        in text
    )
    assert "docs-gitbook-status:" in text
    assert "\t$(REPO_PYTHON) scripts/check_gitbook_v1_docs.py" in text
    assert "docs-gitbook-pack:" in text
    assert "\t$(REPO_PYTHON) scripts/export_gitbook_v1_pack.py" in text
    assert "capability-plane-verify:" in text
    assert "\t$(REPO_PYTHON) -m pytest -q \\" in text
    assert "self-host-status:" in text
    assert "\t$(REPO_PYTHON) -m ruff check \\" in text


def test_run_repo_python_executes_repo_manifest_via_explicit_pixi_home(tmp_path: Path) -> None:
    pixi_home = tmp_path / "pixi-home"
    log_path = tmp_path / "pixi-args.log"
    pixi_bin = pixi_home / "bin" / "pixi"
    pixi_bin.parent.mkdir(parents=True)
    _write_executable(
        pixi_bin,
        """#!/bin/bash
set -euo pipefail
printf '%s\n' "$@" > "$ALGENTA_TEST_PIXI_LOG"
""",
    )

    env = os.environ.copy()
    env["ALGENTA_TEST_PIXI_LOG"] = str(log_path)
    env["HOME"] = str(tmp_path)
    env["PATH"] = "/usr/bin:/bin"
    env["PIXI_HOME"] = str(pixi_home)

    proc = subprocess.run(  # noqa: S603
        [str(RUN_REPO_PYTHON), "-c", "print('pixi')"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert log_path.read_text(encoding="utf-8").splitlines() == [
        "run",
        "--manifest-path",
        str(ROOT / "mojo_env" / "pixi.toml"),
        "python",
        "-c",
        "print('pixi')",
    ]


def test_ts_sdk_package_has_lint_script_for_root_checks() -> None:
    payload = json.loads((ROOT / "packages" / "ts-sdk" / "package.json").read_text())

    assert payload["scripts"]["lint"] == "tsc --noEmit"


def test_sdk_docs_reference_root_js_build_path() -> None:
    ts_sdk_readme = (ROOT / "packages" / "ts-sdk" / "README.md").read_text()
    ts_sdk_docs = (ROOT / "apps" / "docs" / "docs" / "sdks" / "typescript.md").read_text()

    assert len(ts_sdk_readme.splitlines()) <= 180
    assert "https://docs.algenta.ai/sdks/typescript" in ts_sdk_readme
    assert "https://docs.algenta.ai/sdk/typescript" not in ts_sdk_readme
    assert "https://docs.algenta.ai/direct-api-client" not in ts_sdk_readme
    assert "pnpm build" in ts_sdk_readme
    assert "pnpm --dir packages/ts-sdk build" in ts_sdk_readme
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1" in (
        ts_sdk_readme
    )
    assert "planner_model_id" in ts_sdk_readme
    assert "planner_execution_mode" in ts_sdk_readme
    assert "planner_provider_backend" in ts_sdk_readme
    assert "pnpm build" in ts_sdk_docs
    assert "pnpm --dir packages/ts-sdk build" in ts_sdk_docs
    assert "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL=repository.deterministic_local_v1" in (
        ts_sdk_docs
    )
    assert "planner_model_id" in ts_sdk_docs
    assert "planner_execution_mode" in ts_sdk_docs
    assert "planner_provider_backend" in ts_sdk_docs


def test_ci_workflow_runs_root_formal_runtime_check_graph() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")

    assert 'NODE_VERSION: "22"' in text
    assert "Set up Node.js" in text
    assert "actions/setup-node@" in text  # SHA-pinned; tag preserved in trailing comment
    # Self-hosted fleet contract: NO setup-node pnpm cache (its post-job cache-save step errors
    # on the macOS store path) and a per-runner pnpm action dest (a fixed ~/setup-pnpm path
    # races across the concurrent runners sharing this Mac -- ENOTEMPTY).
    assert "package-manager-cache: false" in text
    assert "dest: ${{ runner.temp }}/setup-pnpm" in text
    assert "Enable Corepack" in text
    assert "corepack enable" in text
    assert "Install Pixi" in text
    assert "pixi.sh/install.sh" in text
    assert 'PIXI_HOME="$GITHUB_WORKSPACE/.pixi"' in text
    assert "Install Mojo/Pixi environment" in text
    assert "pixi install --manifest-path mojo_env/pixi.toml" in text
    assert "Build compiled Mojo simulation runtime" in text
    assert "bash scripts/build_mojo_binary.sh" in text
    assert "MOJO_RUNTIME_MODULE_FILTER: vector_kernels.dot" in text
    assert "MOJO_SRC: ${{ runner.temp }}/algenta-ci-runtime/main.mojo" in text
    assert "DISPATCH_OUTPUT_PATH: ${{ runner.temp }}/algenta-ci-runtime/" in text
    assert "BINARY_PATH: ${{ runner.temp }}/algenta-ci-runtime/simulate" in text
    assert 'cp mojo/engine/main.mojo "$MOJO_SRC"' in text
    assert "Verify filtered compiled Mojo worker" in text
    assert "-k vector_dot_runtime_library_request" in text
    assert text.index("Build compiled Mojo simulation runtime") < text.index(
        "Run repo check graph"
    )
    assert "Install JavaScript workspace dependencies" in text
    assert "pnpm install --frozen-lockfile" in text
    assert "Run repo check graph" in text
    assert "pnpm check" in text
    assert "./scripts/run_repo_python.sh -m ruff check apps/ --ignore E501 || true" in text
    assert "pip install -r requirements-dev.txt" not in text
    assert "pytest tests/ -v --tb=short -x" not in text
