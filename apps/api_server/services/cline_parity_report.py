from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from apps.api_server.services.cline_parity_inventory import (
    DEFAULT_PARITY_CAPABILITY_SPECS,
    ParityCapabilitySpec,
)
from apps.api_server.services.cline_agent_run_references import (
    collect_agent_run_references,
)
from apps.api_server.services.cline_proof_common import (
    CHANNEL_PARITY_SOURCE_PATH,
    CLINE_PROOFS_DIR,
    CLINE_RUNS_DIR,
    ClineProofContext,
    artifact_relative_path,
    build_proof_context,
    create_artifact_provenance,
    fetch_live_docs_text,
    read_json,
    read_ndjson,
    repo_root,
    sha256_hex,
    validate_artifact_provenance,
    write_json,
    load_docs_snapshot,
)


CHANNEL_PARITY_REPORT_PATH = CLINE_PROOFS_DIR / "channel_parity_report.json"
PARITY_LEDGER_PATH = CLINE_PROOFS_DIR / "parity_ledger.json"
PARITY_REPORT_PATH = CLINE_PROOFS_DIR / "parity_report.json"
ADAPTER_REGISTRY_PATH = CLINE_PROOFS_DIR / "adapter_registry.json"
LIVE_MATRIX_SELECTION_PATH = CLINE_PROOFS_DIR / "live_matrix_selection.json"

PROOF_LEVEL_RANK = {
    "none": 0,
    "static_proved": 1,
    "contract_proved": 2,
    "integration_proved": 3,
    "live_proved": 4,
}


@dataclass(frozen=True)
class LoadedRunBundle:
    run_dir: Path
    runtime_manifest: dict[str, Any]
    messages: dict[str, Any]
    usage: dict[str, Any]
    events: list[dict[str, Any]]
    tool_calls: dict[str, Any]
    approvals: dict[str, Any]
    gate: dict[str, Any]


def _highest_proof_level(*levels: str) -> str:
    return max(levels, key=lambda level: PROOF_LEVEL_RANK[level])


def _load_runtime_contract_report(
    root: Path,
    context: ClineProofContext,
    *,
    allow_dirty_tree: bool,
) -> tuple[dict[str, Any] | None, list[str]]:
    path = root / CLINE_PROOFS_DIR / "runtime_contract_report.json"
    if not path.exists():
        return None, [f"missing runtime contract report: {path}"]
    payload = read_json(path)
    errors = validate_artifact_provenance(
        payload=payload,
        context=context,
        artifact_path=path,
        allow_dirty_tree=allow_dirty_tree,
    )
    return payload, errors


def _load_json_artifact(
    *,
    root: Path,
    context: ClineProofContext,
    relative_path: Path,
    allow_dirty_tree: bool,
) -> tuple[dict[str, Any] | None, list[str]]:
    path = root / relative_path
    if not path.exists():
        return None, [f"missing proof artifact: {path}"]
    payload = read_json(path)
    errors = validate_artifact_provenance(
        payload=payload,
        context=context,
        artifact_path=path,
        allow_dirty_tree=allow_dirty_tree,
    )
    return payload, errors


def _load_live_matrix_artifacts(
    root: Path,
    context: ClineProofContext,
    *,
    allow_dirty_tree: bool,
) -> tuple[dict[str, dict[str, Any] | None], list[str]]:
    adapter_registry, adapter_errors = _load_json_artifact(
        root=root,
        context=context,
        relative_path=ADAPTER_REGISTRY_PATH,
        allow_dirty_tree=allow_dirty_tree,
    )
    live_matrix_selection, selection_errors = _load_json_artifact(
        root=root,
        context=context,
        relative_path=LIVE_MATRIX_SELECTION_PATH,
        allow_dirty_tree=allow_dirty_tree,
    )
    errors = [*adapter_errors, *selection_errors]
    if adapter_registry is not None:
        if adapter_registry.get("missing_languages"):
            errors.append("adapter_registry.json reported missing runtime languages")
        if adapter_registry.get("supported_language_count") != adapter_registry.get(
            "runtime_covered_language_count"
        ):
            errors.append(
                "adapter_registry.json supported/runtime coverage count mismatch"
            )
    if live_matrix_selection is not None:
        if live_matrix_selection.get("missing_languages"):
            errors.append("live_matrix_selection.json reported missing runtime languages")
        if not isinstance(live_matrix_selection.get("selected_live_languages"), list) or not (
            live_matrix_selection.get("selected_live_languages")
        ):
            errors.append("live_matrix_selection.json is missing selected_live_languages")
    if adapter_registry is not None and live_matrix_selection is not None:
        if adapter_registry.get("supported_language_count") != live_matrix_selection.get(
            "supported_language_count"
        ):
            errors.append(
                "adapter_registry.json and live_matrix_selection.json disagree on supported_language_count"
            )
    return {
        "adapter_registry": adapter_registry,
        "live_matrix_selection": live_matrix_selection,
    }, errors


def _load_latest_run_bundle(
    root: Path,
    context: ClineProofContext,
    *,
    allow_dirty_tree: bool,
) -> tuple[LoadedRunBundle | None, list[str]]:
    runs_dir = root / CLINE_RUNS_DIR
    if not runs_dir.exists():
        return None, [f"missing runs directory: {runs_dir}"]
    candidate_dirs = sorted(
        [path for path in runs_dir.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not candidate_dirs:
        return None, [f"no run artifacts found under {runs_dir}"]
    errors: list[str] = []
    best_bundle: LoadedRunBundle | None = None
    best_score = -1
    for run_dir in candidate_dirs:
        try:
            payloads = {
                "runtime_manifest": read_json(run_dir / "runtime_manifest.json"),
                "messages": read_json(run_dir / "messages.json"),
                "usage": read_json(run_dir / "usage.json"),
                "events": read_ndjson(run_dir / "events.ndjson"),
                "tool_calls": read_json(run_dir / "tool_calls.json"),
                "approvals": read_json(run_dir / "approvals.json"),
                "gate": read_json(run_dir / "gate.json"),
            }
        except FileNotFoundError as exc:
            errors.append(f"incomplete run bundle under {run_dir}: {exc}")
            continue
        bundle_errors: list[str] = []
        for name, payload in payloads.items():
            if name == "events":
                for index, event_payload in enumerate(payload, start=1):
                    bundle_errors.extend(
                        validate_artifact_provenance(
                            payload=event_payload,
                            context=context,
                            artifact_path=run_dir / f"events.ndjson#{index}",
                            allow_dirty_tree=allow_dirty_tree,
                        )
                    )
                continue
            bundle_errors.extend(
                validate_artifact_provenance(
                    payload=payload,
                    context=context,
                    artifact_path=run_dir / f"{name}.json",
                    allow_dirty_tree=allow_dirty_tree,
                )
            )
        if bundle_errors:
            errors.extend(bundle_errors)
            continue
        if payloads["runtime_manifest"].get("offline_contract_only") is True:
            errors.append(f"{run_dir} is offline_contract_only and cannot satisfy parity")
            continue
        bundle = LoadedRunBundle(
            run_dir=run_dir,
            runtime_manifest=payloads["runtime_manifest"],
            messages=payloads["messages"],
            usage=payloads["usage"],
            events=payloads["events"],
            tool_calls=payloads["tool_calls"],
            approvals=payloads["approvals"],
            gate=payloads["gate"],
        )
        score = _run_bundle_score(bundle)
        if score > best_score:
            best_bundle = bundle
            best_score = score
    if best_bundle is not None:
        return best_bundle, []
    return None, errors or [f"no valid run bundles found under {runs_dir}"]


def _run_bundle_score(run_bundle: LoadedRunBundle) -> int:
    score = 0
    if run_bundle.runtime_manifest.get("runtime", {}).get("is_stub") is False:
        score += 1
    if run_bundle.runtime_manifest.get("engine", {}).get("enabled") is True:
        score += 2
    if run_bundle.gate.get("terminal_state") == "succeeded":
        score += 2
    if run_bundle.tool_calls.get("govern_hook", {}).get("status") == "observed":
        score += 2
    score += len(run_bundle.tool_calls.get("tool_calls_by_name", {}))
    return score


def _build_channel_parity_report(
    root: Path,
    context: ClineProofContext,
) -> dict[str, Any]:
    source_path = root / CHANNEL_PARITY_SOURCE_PATH
    if not source_path.exists():
        payload = {
            **create_artifact_provenance(
                context,
                run_id="channel_parity_report",
                schema_version="cline-channel-parity-report/v1",
            ),
            "status": "blocked_missing_source",
            "source_artifact": str(CHANNEL_PARITY_SOURCE_PATH),
            "reason": f"missing repository channel parity source artifact: {source_path}",
            "agent_run_references": [],
        }
        write_json(root / CHANNEL_PARITY_REPORT_PATH, payload)
        return payload

    source_payload = read_json(source_path)
    channels = source_payload.get("channels")
    if not isinstance(channels, list):
        raise ValueError(f"{source_path} channels must be a list")
    agent_run_references = source_payload.get("agent_run_references") or []
    if not isinstance(agent_run_references, list):
        raise ValueError(f"{source_path} agent_run_references must be a list")
    reference_source = "source_summary"
    if not agent_run_references:
        summary_artifacts = [
            channel.get("summary_artifact")
            for channel in channels
            if isinstance(channel, dict) and isinstance(channel.get("summary_artifact"), str)
        ]
        agent_run_references = collect_agent_run_references(
            root=root,
            summary_artifacts=summary_artifacts,
        )
        reference_source = (
            "derived_proof_artifacts" if agent_run_references else "missing"
        )
    source_status = source_payload.get("status")
    if source_status != "passed":
        status = "failed"
        reason = f"source channel parity summary reported status={source_status!r}"
    elif not agent_run_references:
        status = "blocked_missing_agent_run_references"
        reason = "source channel parity summary does not reference proved agent runs"
    else:
        status = "passed"
        reason = None
    payload = {
        **create_artifact_provenance(
            context,
            run_id="channel_parity_report",
            schema_version="cline-channel-parity-report/v1",
        ),
        "status": status,
        "source_artifact": str(CHANNEL_PARITY_SOURCE_PATH),
        "agent_run_references": agent_run_references,
        "agent_run_reference_source": reference_source,
        "channels": channels,
        "reason": reason,
    }
    write_json(root / CHANNEL_PARITY_REPORT_PATH, payload)
    return payload


def _runtime_manifest_level(runtime_contract: dict[str, Any] | None) -> tuple[str, list[str]]:
    if runtime_contract is None:
        return "static_proved", ["runtime contract report missing"]
    manifest = runtime_contract.get("runtime_manifest", {})
    payload = manifest.get("payload", {})
    if (
        manifest.get("status_code") == 200
        and payload.get("runtime", {}).get("kind") == "cline"
        and payload.get("runtime", {}).get("is_stub") is False
        and payload.get("capabilities", {}).get("sessions") is True
    ):
        return "integration_proved", []
    return "static_proved", ["runtime manifest probe did not prove real cline runtime"]


def _session_contract_level(runtime_contract: dict[str, Any] | None) -> tuple[str, list[str]]:
    if runtime_contract is None:
        return "static_proved", ["runtime contract report missing"]
    contract = runtime_contract.get("session_contract", {})
    required_statuses = {
        "create": 201,
        "list": 200,
        "get": 200,
        "messages": 200,
        "usage": 200,
        "events": 200,
        "delete": 200,
    }
    missing = [
        f"{name}={contract.get(name, {}).get('status_code')!r}"
        for name, expected in required_statuses.items()
        if contract.get(name, {}).get("status_code") != expected
    ]
    if not missing:
        return "integration_proved", []
    return "static_proved", [f"session contract incomplete: {', '.join(missing)}"]


def _events_projection_level(runtime_contract: dict[str, Any] | None) -> tuple[str, list[str]]:
    if runtime_contract is None:
        return "static_proved", ["runtime contract report missing"]
    contract = runtime_contract.get("session_contract", {})
    ndjson_status = contract.get("events_ndjson", {}).get("status_code")
    sse_status = contract.get("events_sse", {}).get("status_code")
    if ndjson_status == 200 and sse_status == 200:
        return "integration_proved", []
    return "static_proved", [
        f"events projection status mismatch: ndjson={ndjson_status!r} sse={sse_status!r}"
    ]


def _usage_surface_level(
    runtime_contract: dict[str, Any] | None,
    run_bundle: LoadedRunBundle | None,
) -> tuple[str, list[str]]:
    levels: list[str] = []
    notes: list[str] = []
    if runtime_contract is not None:
        usage_status = runtime_contract.get("session_contract", {}).get("usage", {}).get(
            "status_code"
        )
        if usage_status == 200:
            levels.append("contract_proved")
        else:
            notes.append(f"usage endpoint status={usage_status!r}")
    if run_bundle is not None:
        usage_payload = run_bundle.usage.get("usage", {})
        if isinstance(usage_payload, dict):
            levels.append("integration_proved")
            if any(bool(value) for value in usage_payload.values()):
                levels.append("live_proved")
    if not levels:
        return "static_proved", ["usage artifact or contract evidence missing", *notes]
    return _highest_proof_level(*levels), notes


def _approval_level(run_bundle: LoadedRunBundle | None) -> tuple[str, list[str]]:
    if run_bundle is None:
        return "static_proved", ["run bundle missing"]
    approval_events = run_bundle.approvals.get("approval_events", [])
    if isinstance(approval_events, list):
        return "integration_proved", []
    return "static_proved", ["approvals.json missing approval_events list"]


def _plugin_plane_level(run_bundle: LoadedRunBundle | None) -> tuple[str, list[str]]:
    if run_bundle is None:
        return "static_proved", ["run bundle missing"]
    manifest_plugins = run_bundle.runtime_manifest.get("plugins", {})
    tool_calls = run_bundle.tool_calls.get("tool_calls_by_name", {})
    required_plugins = ("localize", "graph_query", "simulate_patch")
    if all(manifest_plugins.get(name) == "loaded" for name in required_plugins):
        if all(name in tool_calls for name in required_plugins):
            return "live_proved", []
        return "static_proved", ["plugin manifest loaded but tool call evidence missing"]
    return "static_proved", ["runtime manifest does not show loaded plugin plane"]


def _govern_hook_level(run_bundle: LoadedRunBundle | None) -> tuple[str, list[str]]:
    if run_bundle is None:
        return "static_proved", ["run bundle missing"]
    govern_hook = run_bundle.tool_calls.get("govern_hook", {})
    if govern_hook.get("status") == "observed" and govern_hook.get("verdict"):
        return "integration_proved", []
    return "static_proved", ["govern hook evidence missing or unobserved"]


def _engine_gate_level(run_bundle: LoadedRunBundle | None) -> tuple[str, list[str]]:
    if run_bundle is None:
        return "static_proved", ["run bundle missing"]
    terminal_state = run_bundle.gate.get("terminal_state")
    if terminal_state in {"engine_evidence_missing", "succeeded", "apply_blocked"}:
        return "integration_proved", []
    return "static_proved", [f"unexpected gate terminal_state={terminal_state!r}"]


def _run_wrapper_level(runtime_contract: dict[str, Any] | None) -> tuple[str, list[str]]:
    if runtime_contract is None:
        return "static_proved", ["runtime contract report missing"]
    run_contract = runtime_contract.get("session_contract", {}).get("run_compatibility", {})
    if run_contract.get("status_code") == 200 and run_contract.get("final_frame_present") is True:
        return "contract_proved", []
    return "static_proved", ["run compatibility route did not emit a final frame"]


def _language_adapter_registry_level(
    live_matrix_artifacts: dict[str, dict[str, Any] | None],
    live_matrix_artifact_errors: list[str],
) -> tuple[str, list[str]]:
    adapter_registry = live_matrix_artifacts.get("adapter_registry")
    if adapter_registry is None:
        return "none", ["adapter_registry.json missing"]
    if any("adapter_registry" in error for error in live_matrix_artifact_errors):
        return "static_proved", [
            error for error in live_matrix_artifact_errors if "adapter_registry" in error
        ]
    if (
        adapter_registry.get("supported_language_count")
        == adapter_registry.get("runtime_covered_language_count")
        and adapter_registry.get("missing_languages") == []
    ):
        return "integration_proved", []
    return "static_proved", [
        "adapter_registry.json does not prove full runtime language coverage"
    ]


def _language_live_matrix_selection_level(
    live_matrix_artifacts: dict[str, dict[str, Any] | None],
    live_matrix_artifact_errors: list[str],
) -> tuple[str, list[str]]:
    live_matrix_selection = live_matrix_artifacts.get("live_matrix_selection")
    if live_matrix_selection is None:
        return "none", ["live_matrix_selection.json missing"]
    if any("live_matrix_selection" in error for error in live_matrix_artifact_errors):
        return "static_proved", [
            error for error in live_matrix_artifact_errors if "live_matrix_selection" in error
        ]
    selected_languages = live_matrix_selection.get("selected_live_languages")
    top_ranked_entries = [
        entry
        for entry in (selected_languages or [])
        if entry.get("selection_reason") == "top_24"
    ]
    if (
        live_matrix_selection.get("missing_languages") == []
        and isinstance(selected_languages, list)
        and len(top_ranked_entries) == 24
    ):
        return "integration_proved", []
    return "static_proved", [
        "live_matrix_selection.json did not prove ranked matrix selection"
    ]


def _static_exists_level(root: Path, *relative_paths: str) -> tuple[str, list[str]]:
    missing = [path for path in relative_paths if not (root / path).exists()]
    if missing:
        return "none", [f"missing implementation files: {', '.join(missing)}"]
    return "static_proved", []


def _evaluate_row(
    *,
    root: Path,
    spec: ParityCapabilitySpec,
    snapshot_text: str,
    live_docs_text: str,
    runtime_contract: dict[str, Any] | None,
    run_bundle: LoadedRunBundle | None,
    live_matrix_artifacts: dict[str, dict[str, Any] | None],
    live_matrix_artifact_errors: list[str],
    channel_parity_report: dict[str, Any],
) -> dict[str, Any]:
    snapshot_has_markers = all(marker in snapshot_text for marker in spec.docs_markers)
    live_has_markers = all(marker in live_docs_text for marker in spec.docs_markers)
    implementation_exists = (root / spec.implementation_file).exists()
    notes: list[str] = []

    if snapshot_has_markers != live_has_markers:
        status = "blocked_docs_runtime_mismatch"
        achieved_level = "none"
        notes.append("checked-in docs and live docs disagree on required capability markers")
    elif not snapshot_has_markers:
        status = "blocked_docs_runtime_mismatch"
        achieved_level = "none"
        notes.append("checked-in docs snapshot is missing required capability markers")
    elif not implementation_exists:
        status = "missing_implementation"
        achieved_level = "none"
        notes.append(f"missing implementation file: {spec.implementation_file}")
    else:
        if spec.evaluator == "runtime_manifest":
            achieved_level, eval_notes = _runtime_manifest_level(runtime_contract)
        elif spec.evaluator == "session_contract":
            achieved_level, eval_notes = _session_contract_level(runtime_contract)
        elif spec.evaluator == "events_projection":
            achieved_level, eval_notes = _events_projection_level(runtime_contract)
        elif spec.evaluator == "usage_surface":
            achieved_level, eval_notes = _usage_surface_level(runtime_contract, run_bundle)
        elif spec.evaluator == "approval_artifact":
            achieved_level, eval_notes = _approval_level(run_bundle)
        elif spec.evaluator == "plugin_plane":
            achieved_level, eval_notes = _plugin_plane_level(run_bundle)
        elif spec.evaluator == "govern_hook":
            achieved_level, eval_notes = _govern_hook_level(run_bundle)
        elif spec.evaluator == "engine_gate":
            achieved_level, eval_notes = _engine_gate_level(run_bundle)
        elif spec.evaluator == "run_wrapper":
            achieved_level, eval_notes = _run_wrapper_level(runtime_contract)
        elif spec.evaluator == "language_adapter_registry":
            achieved_level, eval_notes = _language_adapter_registry_level(
                live_matrix_artifacts,
                live_matrix_artifact_errors,
            )
        elif spec.evaluator == "language_live_matrix_selection":
            achieved_level, eval_notes = _language_live_matrix_selection_level(
                live_matrix_artifacts,
                live_matrix_artifact_errors,
            )
        elif spec.evaluator == "cli_channel":
            achieved_level, eval_notes = _static_exists_level(
                root,
                "apps/cli/main/_cmd_data_repos.py",
                "apps/cli/main/__init__.py",
            )
            if channel_parity_report.get("status") == "passed":
                achieved_level = _highest_proof_level(achieved_level, "integration_proved")
        elif spec.evaluator == "mcp_channel":
            achieved_level, eval_notes = _static_exists_level(
                root,
                "apps/mcp_server/tools/repositories.py",
                "apps/mcp_server/registry.py",
            )
            if channel_parity_report.get("status") == "passed":
                achieved_level = _highest_proof_level(achieved_level, "integration_proved")
        elif spec.evaluator == "github_channel":
            achieved_level, eval_notes = _static_exists_level(
                root,
                ".github/workflows/repository-intelligence-bot.yml",
                "tests/test_repository_github_workflow.py",
            )
        elif spec.evaluator == "cursor_docs":
            achieved_level, eval_notes = _static_exists_level(root, "apps/mcp_server/README.md")
        elif spec.evaluator == "teams_surface":
            achieved_level, eval_notes = _static_exists_level(
                root,
                "agent-core/vendor/cline/algenta/server/policy.ts",
            )
        elif spec.evaluator == "scheduled_agents_surface":
            achieved_level, eval_notes = _static_exists_level(
                root,
                "agent-core/vendor/cline/algenta/scheduled-agents.ts",
                "tests/test_cline_surface_modules.py",
                "agent-core/vendor/cline/sdk/packages/core/src/cline-core/automation.ts",
            )
        elif spec.evaluator == "acp_editor_surface":
            achieved_level, eval_notes = _static_exists_level(
                root,
                "agent-core/vendor/cline/algenta/acp-editor.ts",
                "tests/test_cline_surface_modules.py",
                "apps/mcp_server/README.md",
            )
        else:
            achieved_level, eval_notes = ("none", ["surface not implemented"])

        notes.extend(eval_notes)
        required_rank = PROOF_LEVEL_RANK[spec.required_level]
        achieved_rank = PROOF_LEVEL_RANK[achieved_level]
        if achieved_rank >= required_rank:
            status = "implemented_and_proved"
        elif achieved_rank > 0:
            status = "implemented_partially_proved"
        else:
            status = "missing_evidence"

    return {
        "capability": spec.capability,
        "cline_source": spec.cline_source,
        "algenta_surface": spec.algenta_surface,
        "implementation_file": spec.implementation_file,
        "proof_type": list(spec.proof_type),
        "proof_artifact": spec.proof_artifact,
        "required_level": spec.required_level,
        "achieved_level": achieved_level,
        "status": status,
        "required": spec.required,
        "notes": notes,
    }


def build_cline_parity_artifacts(
    *,
    root: Path | None = None,
    live_docs_text: str | None = None,
    allow_offline_live_docs: bool = False,
    allow_dirty_tree: bool = False,
    inventory: tuple[ParityCapabilitySpec, ...] = DEFAULT_PARITY_CAPABILITY_SPECS,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    resolved_root = repo_root() if root is None else Path(root).resolve()
    context = build_proof_context(resolved_root)
    snapshot_text, snapshot_hash = load_docs_snapshot(resolved_root)
    live_docs_review_status = "checked"
    if live_docs_text is None:
        if allow_offline_live_docs:
            live_docs_text = snapshot_text
            live_docs_review_status = "offline_skipped"
        else:
            live_docs_text, _ = fetch_live_docs_text()
    live_docs_hash = sha256_hex(live_docs_text)
    runtime_contract, runtime_contract_errors = _load_runtime_contract_report(
        resolved_root,
        context,
        allow_dirty_tree=allow_dirty_tree,
    )
    live_matrix_artifacts, live_matrix_artifact_errors = _load_live_matrix_artifacts(
        resolved_root,
        context,
        allow_dirty_tree=allow_dirty_tree,
    )
    run_bundle, run_bundle_errors = _load_latest_run_bundle(
        resolved_root,
        context,
        allow_dirty_tree=allow_dirty_tree,
    )
    if runtime_contract_errors:
        runtime_contract = None
    if run_bundle_errors:
        run_bundle = None
    channel_parity_report = _build_channel_parity_report(resolved_root, context)

    rows = [
        _evaluate_row(
            root=resolved_root,
            spec=spec,
            snapshot_text=snapshot_text,
            live_docs_text=live_docs_text,
            runtime_contract=runtime_contract,
            run_bundle=run_bundle,
            live_matrix_artifacts=live_matrix_artifacts,
            live_matrix_artifact_errors=live_matrix_artifact_errors,
            channel_parity_report=channel_parity_report,
        )
        for spec in inventory
    ]

    ledger = {
        **create_artifact_provenance(
            context,
            run_id="parity_ledger",
            schema_version="cline-parity-ledger/v1",
        ),
        "live_docs_review_status": live_docs_review_status,
        "checked_in_docs_snapshot_hash": snapshot_hash,
        "live_docs_review_hash": live_docs_hash,
        "runtime_contract_errors": runtime_contract_errors,
        "live_matrix_artifact_errors": live_matrix_artifact_errors,
        "run_bundle_errors": run_bundle_errors,
        "rows": rows,
    }
    write_json(resolved_root / PARITY_LEDGER_PATH, ledger)

    required_rows = [row for row in rows if row["required"]]
    required_proved = [
        row for row in required_rows if row["status"] == "implemented_and_proved"
    ]
    unresolved_required = [
        row["capability"] for row in required_rows if row["status"] != "implemented_and_proved"
    ]
    progress_percent = round(
        (len(required_proved) / len(required_rows) * 100.0) if required_rows else 100.0,
        2,
    )
    report = {
        **create_artifact_provenance(
            context,
            run_id="parity_report",
            schema_version="cline-parity-report/v1",
        ),
        "status": (
            "passed"
            if not unresolved_required and not live_matrix_artifact_errors
            else "failed"
        ),
        "live_docs_review_status": live_docs_review_status,
        "required_row_count": len(required_rows),
        "required_rows_proved": len(required_proved),
        "progress_percent": progress_percent,
        "unresolved_required_capabilities": unresolved_required,
        "live_matrix_artifact_errors": live_matrix_artifact_errors,
        "rows_by_status": {
            "implemented_and_proved": sum(1 for row in rows if row["status"] == "implemented_and_proved"),
            "implemented_partially_proved": sum(
                1 for row in rows if row["status"] == "implemented_partially_proved"
            ),
            "missing_evidence": sum(1 for row in rows if row["status"] == "missing_evidence"),
            "missing_implementation": sum(
                1 for row in rows if row["status"] == "missing_implementation"
            ),
            "blocked_docs_runtime_mismatch": sum(
                1 for row in rows if row["status"] == "blocked_docs_runtime_mismatch"
            ),
        },
        "artifacts": {
            "parity_ledger": artifact_relative_path(resolved_root, resolved_root / PARITY_LEDGER_PATH),
            "channel_parity_report": artifact_relative_path(
                resolved_root,
                resolved_root / CHANNEL_PARITY_REPORT_PATH,
            ),
            "runtime_contract_report": (
                artifact_relative_path(
                    resolved_root,
                    resolved_root / CLINE_PROOFS_DIR / "runtime_contract_report.json",
                )
                if (resolved_root / CLINE_PROOFS_DIR / "runtime_contract_report.json").exists()
                else None
            ),
            "adapter_registry": (
                artifact_relative_path(
                    resolved_root,
                    resolved_root / ADAPTER_REGISTRY_PATH,
                )
                if (resolved_root / ADAPTER_REGISTRY_PATH).exists()
                else None
            ),
            "live_matrix_selection": (
                artifact_relative_path(
                    resolved_root,
                    resolved_root / LIVE_MATRIX_SELECTION_PATH,
                )
                if (resolved_root / LIVE_MATRIX_SELECTION_PATH).exists()
                else None
            ),
            "latest_run_dir": artifact_relative_path(resolved_root, run_bundle.run_dir)
            if run_bundle is not None
            else None,
        },
    }
    write_json(resolved_root / PARITY_REPORT_PATH, report)
    return ledger, report, channel_parity_report
