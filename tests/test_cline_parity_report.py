from __future__ import annotations

import json
from pathlib import Path

from apps.api_server.services.cline_live_matrix_selection import (
    build_cline_live_matrix_artifacts,
)
from apps.api_server.services.cline_parity_inventory import ParityCapabilitySpec
from apps.api_server.services.cline_parity_report import build_cline_parity_artifacts
from apps.api_server.services.cline_proof_common import (
    CHANNEL_PARITY_SOURCE_PATH,
    CLINE_PROOFS_DIR,
    build_proof_context,
    create_artifact_provenance,
    sha256_hex,
    stable_json_dumps,
    write_json,
)


def _write_docs_snapshot(root: Path, text: str) -> None:
    snapshot_path = root / CLINE_PROOFS_DIR / "cline_docs_snapshot.txt"
    snapshot_hash_path = root / CLINE_PROOFS_DIR / "cline_docs_snapshot.sha256"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(text, encoding="utf-8")
    snapshot_hash_path.write_text(sha256_hex(text), encoding="utf-8")


def _write_run_bundle(root: Path) -> None:
    context = build_proof_context(root)
    run_dir = root / CLINE_PROOFS_DIR / "runs" / "run_001"
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        run_dir / "runtime_manifest.json",
        {
            **create_artifact_provenance(
                context,
                run_id="run_001",
                schema_version="cline-runtime-manifest/v1",
            ),
            "runtime": {"kind": "cline", "is_stub": False},
            "plugins": {
                "localize": "loaded",
                "graph_query": "loaded",
                "simulate_patch": "loaded",
                "govern_hook": "loaded",
            },
        },
    )
    write_json(
        run_dir / "messages.json",
        {
            **create_artifact_provenance(context, run_id="run_001", schema_version="cline-messages/v1"),
            "messages": [],
        },
    )
    write_json(
        run_dir / "usage.json",
        {
            **create_artifact_provenance(context, run_id="run_001", schema_version="cline-usage/v1"),
            "usage": {"inputTokens": 10, "outputTokens": 5},
        },
    )
    (run_dir / "events.ndjson").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        **create_artifact_provenance(
                            context,
                            run_id="run_001",
                            schema_version="cline-session-event-record/v1",
                        ),
                        "record_type": "session_event",
                        "event": {"event_type": "agent.content_end"},
                    }
                )
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_json(
        run_dir / "tool_calls.json",
        {
            **create_artifact_provenance(
                context,
                run_id="run_001",
                schema_version="cline-tool-calls/v1",
            ),
            "tool_calls_by_name": {
                "localize": {"count": 1, "statuses": ["started", "succeeded"]},
                "graph_query": {"count": 1, "statuses": ["started", "succeeded"]},
                "simulate_patch": {"count": 1, "statuses": ["started", "succeeded"]},
            },
            "govern_hook": {"status": "observed", "verdict": "approved"},
        },
    )
    write_json(
        run_dir / "approvals.json",
        {
            **create_artifact_provenance(
                context,
                run_id="run_001",
                schema_version="cline-approvals/v1",
            ),
            "approval_events": [],
        },
    )
    write_json(
        run_dir / "gate.json",
        {
            **create_artifact_provenance(context, run_id="run_001", schema_version="cline-gate/v1"),
            "terminal_state": "succeeded",
        },
    )


def _write_runtime_contract(root: Path) -> None:
    context = build_proof_context(root)
    write_json(
        root / CLINE_PROOFS_DIR / "runtime_contract_report.json",
        {
            **create_artifact_provenance(
                context,
                run_id="runtime_contract",
                schema_version="cline-runtime-contract-report/v1",
            ),
            "runtime_manifest": {
                "status_code": 200,
                "payload": {
                    "runtime": {"kind": "cline", "is_stub": False},
                    "capabilities": {"sessions": True},
                },
            },
            "session_contract": {
                "create": {"status_code": 201},
                "list": {"status_code": 200},
                "get": {"status_code": 200},
                "messages": {"status_code": 200},
                "usage": {"status_code": 200},
                "events": {"status_code": 200},
                "events_ndjson": {"status_code": 200},
                "events_sse": {"status_code": 200},
                "run_compatibility": {"status_code": 200, "final_frame_present": True},
                "delete": {"status_code": 200},
            },
        },
    )


def _write_live_run_proof(root: Path) -> None:
    context = build_proof_context(root)
    write_json(
        root / CLINE_PROOFS_DIR / "live_run_proof.json",
        {
            **create_artifact_provenance(
                context,
                run_id="live_run_proof",
                schema_version="cline-live-run-proof/v1",
            ),
            "status": "passed",
            "run_id": "run_001",
            "agent_run_id": "agent_run_001",
            "session_id": "session_001",
            "run_dir": "build/proofs/cline/runs/run_001",
        },
    )


def _write_live_matrix_artifacts(root: Path) -> None:
    build_cline_live_matrix_artifacts(root=root)


def test_build_cline_parity_artifacts_reports_proved_rows(tmp_path: Path) -> None:
    snapshot_text = "\n".join(
        ["ClineCore", "Events", "Permission Handling", "Writing Plugins", "Hooks", "MCP"]
    )
    _write_docs_snapshot(tmp_path, snapshot_text)
    _write_live_matrix_artifacts(tmp_path)
    _write_runtime_contract(tmp_path)
    _write_run_bundle(tmp_path)
    write_json(
        tmp_path / CHANNEL_PARITY_SOURCE_PATH,
        {
            "status": "passed",
            "channels": [],
            "agent_run_references": ["run_001"],
        },
    )
    for path in (
        "agent-core/vendor/cline/algenta/run-server.ts",
        "agent-core/vendor/cline/algenta/server/execution.ts",
        "agent-core/vendor/cline/algenta/server/artifacts.ts",
        "agent-core/vendor/cline/algenta/algenta-plugin.ts",
        "agent-core/vendor/cline/algenta/mojo-gate.ts",
        "apps/cli/main/_cmd_data_repos.py",
        "apps/cli/main/__init__.py",
        "apps/mcp_server/tools/repositories.py",
        "apps/mcp_server/registry.py",
        "apps/mcp_server/README.md",
    ):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("// present\n", encoding="utf-8")

    inventory = (
        ParityCapabilitySpec(
            capability="runtime.truth.manifest",
            cline_source="docs",
            docs_markers=("ClineCore", "Events", "Permission Handling"),
            algenta_surface="/manifest",
            implementation_file="agent-core/vendor/cline/algenta/run-server.ts",
            proof_type=("static", "integration"),
            proof_artifact="build/proofs/cline/runtime_contract_report.json",
            required_level="integration_proved",
            evaluator="runtime_manifest",
        ),
        ParityCapabilitySpec(
            capability="approvals.profile_artifact_plane",
            cline_source="docs",
            docs_markers=("Permission Handling",),
            algenta_surface="approvals.json",
            implementation_file="agent-core/vendor/cline/algenta/server/artifacts.ts",
            proof_type=("static", "integration"),
            proof_artifact="build/proofs/cline/runs/<run_id>/approvals.json",
            required_level="integration_proved",
            evaluator="approval_artifact",
        ),
        ParityCapabilitySpec(
            capability="plugins.algenta_tool_plane",
            cline_source="docs",
            docs_markers=("Writing Plugins", "MCP"),
            algenta_surface="tool_calls.json",
            implementation_file="agent-core/vendor/cline/algenta/algenta-plugin.ts",
            proof_type=("static", "live"),
            proof_artifact="build/proofs/cline/runs/<run_id>/tool_calls.json",
            required_level="integration_proved",
            evaluator="plugin_plane",
        ),
    )

    ledger, report, channel_report = build_cline_parity_artifacts(
        root=tmp_path,
        live_docs_text=snapshot_text,
        allow_dirty_tree=True,
        inventory=inventory,
    )

    assert report["status"] == "passed"
    assert report["progress_percent"] == 100.0
    assert report["live_matrix_artifact_errors"] == []
    assert all(row["status"] == "implemented_and_proved" for row in ledger["rows"])
    assert channel_report["status"] == "passed"


def test_build_cline_parity_artifacts_fails_closed_on_stale_artifact(tmp_path: Path) -> None:
    snapshot_text = "ClineCore\nEvents\nPermission Handling\n"
    _write_docs_snapshot(tmp_path, snapshot_text)
    _write_live_matrix_artifacts(tmp_path)
    _write_runtime_contract(tmp_path)
    path = tmp_path / CLINE_PROOFS_DIR / "runtime_contract_report.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["git_commit"] = "stale-commit"
    path.write_text(stable_json_dumps(payload), encoding="utf-8")
    target = tmp_path / "agent-core/vendor/cline/algenta/run-server.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("// present\n", encoding="utf-8")

    inventory = (
        ParityCapabilitySpec(
            capability="runtime.truth.manifest",
            cline_source="docs",
            docs_markers=("ClineCore", "Events", "Permission Handling"),
            algenta_surface="/manifest",
            implementation_file="agent-core/vendor/cline/algenta/run-server.ts",
            proof_type=("static", "integration"),
            proof_artifact="build/proofs/cline/runtime_contract_report.json",
            required_level="integration_proved",
            evaluator="runtime_manifest",
        ),
    )

    ledger, report, _ = build_cline_parity_artifacts(
        root=tmp_path,
        live_docs_text=snapshot_text,
        allow_dirty_tree=True,
        inventory=inventory,
    )

    assert report["status"] == "failed"
    assert ledger["runtime_contract_errors"]
    assert ledger["rows"][0]["status"] == "implemented_partially_proved"


def test_build_cline_parity_artifacts_blocks_docs_runtime_mismatch(tmp_path: Path) -> None:
    _write_docs_snapshot(tmp_path, "ClineCore\nEvents\nPermission Handling\n")
    target = tmp_path / "agent-core/vendor/cline/algenta/run-server.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("// present\n", encoding="utf-8")

    inventory = (
        ParityCapabilitySpec(
            capability="runtime.truth.manifest",
            cline_source="docs",
            docs_markers=("ClineCore", "Events", "Permission Handling"),
            algenta_surface="/manifest",
            implementation_file="agent-core/vendor/cline/algenta/run-server.ts",
            proof_type=("static",),
            proof_artifact="build/proofs/cline/runtime_contract_report.json",
            required_level="static_proved",
            evaluator="runtime_manifest",
        ),
    )

    ledger, report, _ = build_cline_parity_artifacts(
        root=tmp_path,
        live_docs_text="ClineCore\nEvents\n",
        allow_dirty_tree=True,
        inventory=inventory,
    )

    assert report["status"] == "failed"
    assert ledger["rows"][0]["status"] == "blocked_docs_runtime_mismatch"


def test_build_cline_parity_artifacts_fails_plugin_and_govern_evidence_missing(tmp_path: Path) -> None:
    snapshot_text = "Writing Plugins\nHooks\nMCP\n"
    _write_docs_snapshot(tmp_path, snapshot_text)
    _write_live_matrix_artifacts(tmp_path)
    context = build_proof_context(tmp_path)
    run_dir = tmp_path / CLINE_PROOFS_DIR / "runs" / "run_002"
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(
        run_dir / "runtime_manifest.json",
        {
            **create_artifact_provenance(
                context,
                run_id="run_002",
                schema_version="cline-runtime-manifest/v1",
            ),
            "runtime": {"kind": "cline", "is_stub": False},
            "plugins": {
                "localize": "loaded",
                "graph_query": "loaded",
                "simulate_patch": "loaded",
                "govern_hook": "loaded",
            },
        },
    )
    for file_name, schema_version, payload in (
        ("messages.json", "cline-messages/v1", {"messages": []}),
        ("usage.json", "cline-usage/v1", {"usage": {}}),
        ("approvals.json", "cline-approvals/v1", {"approval_events": []}),
        ("gate.json", "cline-gate/v1", {"terminal_state": "failed"}),
    ):
        write_json(
            run_dir / file_name,
            {
                **create_artifact_provenance(
                    context,
                    run_id="run_002",
                    schema_version=schema_version,
                ),
                **payload,
            },
        )
    (run_dir / "events.ndjson").write_text(
        json.dumps(
            {
                **create_artifact_provenance(
                    context,
                    run_id="run_002",
                    schema_version="cline-session-event-record/v1",
                ),
                "record_type": "session_event",
                "event": {"event_type": "hook.tool_call"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    write_json(
        run_dir / "tool_calls.json",
        {
            **create_artifact_provenance(
                context,
                run_id="run_002",
                schema_version="cline-tool-calls/v1",
            ),
            "tool_calls_by_name": {
                "localize": {"count": 1, "statuses": ["started", "succeeded"]},
            },
            "govern_hook": {"status": "unobserved"},
        },
    )
    for path in (
        "agent-core/vendor/cline/algenta/algenta-plugin.ts",
        "agent-core/vendor/cline/algenta/mojo-gate.ts",
    ):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("// present\n", encoding="utf-8")

    inventory = (
        ParityCapabilitySpec(
            capability="plugins.algenta_tool_plane",
            cline_source="docs",
            docs_markers=("Writing Plugins", "MCP"),
            algenta_surface="tool_calls.json",
            implementation_file="agent-core/vendor/cline/algenta/algenta-plugin.ts",
            proof_type=("static", "live"),
            proof_artifact="build/proofs/cline/runs/<run_id>/tool_calls.json",
            required_level="integration_proved",
            evaluator="plugin_plane",
        ),
        ParityCapabilitySpec(
            capability="hooks.govern_hook_verdict",
            cline_source="docs",
            docs_markers=("Hooks",),
            algenta_surface="tool_calls.json",
            implementation_file="agent-core/vendor/cline/algenta/mojo-gate.ts",
            proof_type=("static", "live"),
            proof_artifact="build/proofs/cline/runs/<run_id>/tool_calls.json",
            required_level="integration_proved",
            evaluator="govern_hook",
        ),
    )

    ledger, report, _ = build_cline_parity_artifacts(
        root=tmp_path,
        live_docs_text=snapshot_text,
        allow_dirty_tree=True,
        inventory=inventory,
    )

    assert report["status"] == "failed"
    assert ledger["rows"][0]["status"] == "implemented_partially_proved"
    assert "tool call evidence missing" in " ".join(ledger["rows"][0]["notes"]).lower()
    assert ledger["rows"][1]["status"] == "implemented_partially_proved"
    assert "govern hook evidence missing" in " ".join(ledger["rows"][1]["notes"]).lower()


def test_build_cline_parity_artifacts_proves_static_scheduled_and_editor_surfaces(
    tmp_path: Path,
) -> None:
    snapshot_text = "Scheduled Agents\nACP: Editor Integrations\n"
    _write_docs_snapshot(tmp_path, snapshot_text)
    _write_live_matrix_artifacts(tmp_path)
    for path in (
        "agent-core/vendor/cline/algenta/scheduled-agents.ts",
        "agent-core/vendor/cline/algenta/acp-editor.ts",
        "tests/test_cline_surface_modules.py",
        "agent-core/vendor/cline/sdk/packages/core/src/cline-core/automation.ts",
        "apps/mcp_server/README.md",
    ):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("// present\n", encoding="utf-8")

    inventory = (
        ParityCapabilitySpec(
            capability="automation.scheduled_agents_surface",
            cline_source="docs",
            docs_markers=("Scheduled Agents",),
            algenta_surface="buildScheduledAgentBlueprint()",
            implementation_file="agent-core/vendor/cline/algenta/scheduled-agents.ts",
            proof_type=("static",),
            proof_artifact="build/proofs/cline/parity_report.json",
            required_level="static_proved",
            evaluator="scheduled_agents_surface",
        ),
        ParityCapabilitySpec(
            capability="editor.acp_surface",
            cline_source="docs",
            docs_markers=("ACP: Editor Integrations",),
            algenta_surface="buildEditorIntegrationManifest()",
            implementation_file="agent-core/vendor/cline/algenta/acp-editor.ts",
            proof_type=("static",),
            proof_artifact="build/proofs/cline/parity_report.json",
            required_level="static_proved",
            evaluator="acp_editor_surface",
        ),
    )

    ledger, report, _ = build_cline_parity_artifacts(
        root=tmp_path,
        live_docs_text=snapshot_text,
        allow_dirty_tree=True,
        inventory=inventory,
    )

    assert report["status"] == "passed"
    assert report["progress_percent"] == 100.0
    assert report["live_matrix_artifact_errors"] == []
    assert [row["status"] for row in ledger["rows"]] == [
        "implemented_and_proved",
        "implemented_and_proved",
    ]


def test_build_cline_parity_artifacts_fails_when_live_matrix_artifact_is_missing(
    tmp_path: Path,
) -> None:
    snapshot_text = "ClineCore\nEvents\nPermission Handling\n"
    _write_docs_snapshot(tmp_path, snapshot_text)
    _write_runtime_contract(tmp_path)
    _write_run_bundle(tmp_path)
    target = tmp_path / "agent-core/vendor/cline/algenta/run-server.ts"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("// present\n", encoding="utf-8")

    inventory = (
        ParityCapabilitySpec(
            capability="runtime.truth.manifest",
            cline_source="docs",
            docs_markers=("ClineCore", "Events", "Permission Handling"),
            algenta_surface="/manifest",
            implementation_file="agent-core/vendor/cline/algenta/run-server.ts",
            proof_type=("static", "integration"),
            proof_artifact="build/proofs/cline/runtime_contract_report.json",
            required_level="integration_proved",
            evaluator="runtime_manifest",
        ),
    )

    _, report, _ = build_cline_parity_artifacts(
        root=tmp_path,
        live_docs_text=snapshot_text,
        allow_dirty_tree=True,
        inventory=inventory,
    )

    assert report["status"] == "failed"
    assert report["live_matrix_artifact_errors"]
    assert "adapter_registry.json" in " ".join(report["live_matrix_artifact_errors"])


def test_build_cline_parity_artifacts_derives_channel_refs_from_live_run_proof(
    tmp_path: Path,
) -> None:
    snapshot_text = "ClineCore\nEvents\nPermission Handling\n"
    _write_docs_snapshot(tmp_path, snapshot_text)
    _write_live_matrix_artifacts(tmp_path)
    _write_runtime_contract(tmp_path)
    _write_run_bundle(tmp_path)
    _write_live_run_proof(tmp_path)
    target = tmp_path / "apps/cli/main/_cmd_data_repos.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# present\n", encoding="utf-8")
    write_json(
        tmp_path / CHANNEL_PARITY_SOURCE_PATH,
        {
            "status": "passed",
            "channels": [
                {
                    "name": "python_sdk",
                    "summary_artifact": "build/python_sdk_integration_summary.json",
                }
            ],
            "agent_run_references": [],
        },
    )

    _, _, channel_report = build_cline_parity_artifacts(
        root=tmp_path,
        live_docs_text=snapshot_text,
        allow_dirty_tree=True,
        inventory=(
            ParityCapabilitySpec(
                capability="channels.cli",
                cline_source="docs",
                docs_markers=("Events",),
                algenta_surface="CLI",
                implementation_file="apps/cli/main/_cmd_data_repos.py",
                proof_type=("static", "integration"),
                proof_artifact="build/proofs/cline/channel_parity_report.json",
                required_level="integration_proved",
                evaluator="cli_channel",
            ),
        ),
    )

    assert channel_report["status"] == "passed"
    assert channel_report["agent_run_reference_source"] == "derived_proof_artifacts"
    assert channel_report["agent_run_references"] == [
        {
            "source_artifact": str(
                (tmp_path / CLINE_PROOFS_DIR / "live_run_proof.json").resolve()
            ),
            "run_id": "run_001",
            "agent_run_id": "agent_run_001",
            "session_id": "session_001",
            "run_dir": "build/proofs/cline/runs/run_001",
        }
    ]


def test_build_cline_parity_artifacts_proves_language_coverage_and_live_matrix_rows(
    tmp_path: Path,
) -> None:
    _write_docs_snapshot(tmp_path, "ClineCore\n")
    _write_live_matrix_artifacts(tmp_path)
    for path in (
        "apps/api_server/services/repository_intelligence_runtime_language_support.py",
        "apps/api_server/services/cline_live_matrix_selection.py",
    ):
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("# present\n", encoding="utf-8")

    inventory = (
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

    ledger, report, _ = build_cline_parity_artifacts(
        root=tmp_path,
        live_docs_text="ClineCore\n",
        allow_dirty_tree=True,
        inventory=inventory,
    )

    assert report["status"] == "passed"
    assert report["required_row_count"] == 2
    assert report["required_rows_proved"] == 2
    assert [row["status"] for row in ledger["rows"]] == [
        "implemented_and_proved",
        "implemented_and_proved",
    ]
