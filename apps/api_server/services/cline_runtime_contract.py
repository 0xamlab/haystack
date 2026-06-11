from __future__ import annotations
from pathlib import Path
from typing import Any

from apps.api_server.services.cline_proof_common import (
    CLINE_PROOFS_DIR,
    artifact_relative_path,
    build_proof_context,
    create_artifact_provenance,
    repo_root,
    write_json,
)
from apps.api_server.services.cline_runtime_support import (
    agent_core_runtime,
    request_json,
    request_text,
)


RUNTIME_CONTRACT_REPORT_PATH = CLINE_PROOFS_DIR / "runtime_contract_report.json"
SCRUBBED_PROVIDER_ENV = {
    "ANTHROPIC_API_KEY": "",
    "OPENAI_API_KEY": "",
    "GEMINI_API_KEY": "",
    "GOOGLE_API_KEY": "",
    "ALGENTA_PROOF_API_KEY": "",
}


def collect_runtime_contract_report(
    *,
    root: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    resolved_root = repo_root() if root is None else Path(root).resolve()
    context = build_proof_context(resolved_root)
    owner_header = {"x-session-owner": "cline_runtime_contract"}

    # The runtime contract lane proves the surface shape, not a live model turn.
    # Scrub provider credentials so `/start` and `/run` stay deterministic and
    # cheap even when the parent environment contains real keys.
    with agent_core_runtime(resolved_root, extra_env=SCRUBBED_PROVIDER_ENV) as base_url:
        manifest_status, manifest = request_json("GET", f"{base_url}/manifest")
        create_status, created = request_json(
            "POST",
            f"{base_url}/sessions",
            payload={
                "working_dir": str(resolved_root),
                "prompt": "Inspect the repository.",
                "repository_scope": "repository_contract",
                "approval_profile": "repository_fix_gated",
                "channel": "test",
                "idempotency_key": "runtime-contract-probe",
            },
            headers=owner_header,
        )
        session_id = created.get("session_id") if create_status == 201 else None
        list_status, listed = request_json("GET", f"{base_url}/sessions", headers=owner_header)
        get_status, retrieved = request_json(
            "GET",
            f"{base_url}/sessions/{session_id}",
            headers=owner_header,
        )
        messages_status, messages = request_json(
            "GET",
            f"{base_url}/sessions/{session_id}/messages",
            headers=owner_header,
        )
        usage_status, usage = request_json(
            "GET",
            f"{base_url}/sessions/{session_id}/usage",
            headers=owner_header,
        )
        events_status, events = request_json(
            "GET",
            f"{base_url}/sessions/{session_id}/events",
            headers=owner_header,
        )
        ndjson_status, ndjson_body = request_text(
            "GET",
            f"{base_url}/sessions/{session_id}/events/ndjson",
            headers=owner_header,
        )
        sse_status, sse_body = request_text(
            "GET",
            f"{base_url}/sessions/{session_id}/events/sse",
            headers=owner_header,
        )
        start_status, start_payload = request_json(
            "POST",
            f"{base_url}/sessions/{session_id}/start",
            payload={"prompt": "Inspect the repository."},
            headers=owner_header,
        )
        run_status, run_body = request_text(
            "POST",
            f"{base_url}/run",
            payload={
                "working_dir": str(resolved_root),
                "prompt": "Inspect the repository.",
                "repository_scope": "repository_contract",
                "approval_profile": "repository_fix_gated",
                "channel": "test",
            },
            headers=owner_header,
        )
        delete_status, deleted = request_json(
            "DELETE",
            f"{base_url}/sessions/{session_id}",
            headers=owner_header,
        )

    payload = {
        **create_artifact_provenance(
            context,
            run_id="runtime_contract",
            schema_version="cline-runtime-contract-report/v1",
        ),
        "runtime_manifest": {
            "status_code": manifest_status,
            "payload": manifest,
        },
        "session_contract": {
            "create": {"status_code": create_status, "payload": created},
            "list": {"status_code": list_status, "payload": listed},
            "get": {"status_code": get_status, "payload": retrieved},
            "messages": {"status_code": messages_status, "payload": messages},
            "usage": {"status_code": usage_status, "payload": usage},
            "events": {"status_code": events_status, "payload": events},
            "events_ndjson": {
                "status_code": ndjson_status,
                "line_count": len([line for line in ndjson_body.splitlines() if line.strip()]),
            },
            "events_sse": {
                "status_code": sse_status,
                "frame_count": sse_body.count("\n\n"),
            },
            "start": {"status_code": start_status, "payload": start_payload},
            "run_compatibility": {
                "status_code": run_status,
                "final_frame_present": '"type":"final"' in run_body.replace(" ", ""),
            },
            "delete": {"status_code": delete_status, "payload": deleted},
        },
    }

    if output_path is None:
        write_json(resolved_root / RUNTIME_CONTRACT_REPORT_PATH, payload)
    else:
        write_json(Path(output_path), payload)
    payload["artifact_path"] = artifact_relative_path(
        resolved_root,
        (resolved_root / RUNTIME_CONTRACT_REPORT_PATH) if output_path is None else Path(output_path),
    )
    return payload
