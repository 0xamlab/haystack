from __future__ import annotations

import sys
from pathlib import Path

# ruff: noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ALGENTA_CORE = ROOT / "packages" / "algenta-core"
PYTHON_SDK = ROOT / "packages" / "python-sdk"
for path in (str(ALGENTA_CORE), str(PYTHON_SDK), str(ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from algenta import Runtime

from apps.mcp_server.registry import TOOLS, get_tool_specs


def test_python_runtime_primary_surface_is_runtime_first() -> None:
    runtime = Runtime()

    for method_name in (
        "connect",
        "resolve",
        "verify",
        "query",
        "import_preview",
        "import_bundle_preview",
    ):
        method = getattr(runtime, method_name, None)
        assert callable(method), method_name


def test_typescript_runtime_primary_surface_is_runtime_first() -> None:
    ts_runtime = (ROOT / "packages" / "ts-sdk" / "src" / "runtime.ts").read_text(encoding="utf-8")
    ts_index = (ROOT / "packages" / "ts-sdk" / "src" / "index.ts").read_text(encoding="utf-8")

    assert "export class Runtime" in ts_runtime
    assert "connect(" in ts_runtime
    assert "resolve(" in ts_runtime
    assert "verify(" in ts_runtime
    assert "query(" in ts_runtime
    assert "importPreview(" in ts_runtime
    assert "importBundlePreview(" in ts_runtime
    assert 'export {' in ts_index
    assert "Runtime," in ts_index


def test_mcp_registry_keeps_primary_and_secondary_surfaces_available() -> None:
    specs = get_tool_specs()
    spec_names = {spec["name"] for spec in specs}

    assert len(TOOLS) == 30
    assert len(specs) == 30
    assert spec_names == set(TOOLS)
    assert {
        "connect_data",
        "get_data_schema",
        "query_data",
        "simulate",
        "recommend",
        "submit_job",
        "list_runs",
        "log_decision",
        "register_trigger",
    }.issubset(spec_names)


def test_competitor_compatibility_docs_lock_match_and_non_match_decisions() -> None:
    competitor = (ROOT / "apps" / "docs" / "docs" / "competitor-compatibility.md").read_text(
        encoding="utf-8"
    )
    quickstart = (ROOT / "apps" / "docs" / "docs" / "quickstart.md").read_text(encoding="utf-8")
    python_sdk = (ROOT / "apps" / "docs" / "docs" / "sdks" / "python.md").read_text(encoding="utf-8")
    ts_sdk = (ROOT / "apps" / "docs" / "docs" / "sdks" / "typescript.md").read_text(encoding="utf-8")

    assert "Vanna" in competitor
    assert "Cube" in competitor
    assert "LlamaIndex" in competitor
    assert "Must match:" in competitor
    assert "Should match:" in competitor
    assert "Intentional non-match:" in competitor
    assert "LLM-to-SQL as the primary execution path" in competitor
    assert "semantic-model-first product core" in competitor
    assert "probabilistic agent-centric execution" in competitor
    assert "resolve" in quickstart and "query" in quickstart
    assert "from algenta import Runtime" in python_sdk
    assert "plan = rt.resolve" in python_sdk
    assert "result = rt.query(plan)" in python_sdk
    assert 'import { Runtime } from "decision-engine-sdk";' in ts_sdk
    assert "const plan = await rt.resolve" in ts_sdk
    assert "const result = await rt.query(plan);" in ts_sdk


def test_go_live_suite_keeps_live_typescript_runtime_gate() -> None:
    go_live = (ROOT / "tests" / "integration" / "test_go_live_full_real.py").read_text(encoding="utf-8")

    assert "Live TypeScript Runtime integration" in go_live
    assert "tests/integration/test_typescript_runtime_live.py" in go_live


def test_typescript_sdk_package_exports_point_to_real_build_outputs() -> None:
    package_json = (ROOT / "packages" / "ts-sdk" / "package.json").read_text(encoding="utf-8")

    assert '"main": "dist/index.js"' in package_json
    assert '"module": "dist/index.js"' in package_json
    assert '"import": "./dist/index.js"' in package_json
