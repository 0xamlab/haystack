from __future__ import annotations

import contextlib
import json
import re
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.cline_proof_common import (
    CLINE_PROOFS_DIR,
    artifact_relative_path,
    build_proof_context,
    create_artifact_provenance,
    read_json,
    repo_root,
    write_json,
)
from apps.api_server.services.cline_runtime_support import (
    agent_core_runtime,
    isolated_cline_runtime_environment,
    request_json,
)


LIVE_RUN_PROOF_PATH = CLINE_PROOFS_DIR / "live_run_proof.json"
PROOF_OWNER = "cline_live_run_proof"
PROOF_PROVIDER_ID = "algenta-proof"
PROOF_MODEL_ID = "algenta/gpt-proof-model"
PROOF_PROVIDER_API_KEY_ENV = "ALGENTA_PROOF_API_KEY"
DEFAULT_TARGET_FILE = "proof-target.txt"


@dataclass(frozen=True)
class EngineRequestRecord:
    path: str
    authorization_present: bool
    payload: dict[str, Any]


class _EngineState:
    def __init__(self) -> None:
        self.requests: list[EngineRequestRecord] = []
        self._lock = threading.Lock()

    def record(self, *, path: str, authorization_present: bool, payload: dict[str, Any]) -> None:
        with self._lock:
            self.requests.append(
                EngineRequestRecord(
                    path=path,
                    authorization_present=authorization_present,
                    payload=payload,
                )
            )

    def count_matching(self, pattern: str) -> int:
        return sum(1 for record in self.requests if re.search(pattern, record.path))

    def all_authorized(self) -> bool:
        return all(record.authorization_present for record in self.requests)

    def to_summary(self) -> dict[str, Any]:
        return {
            "request_count": len(self.requests),
            "triage_calls": self.count_matching(r"/triage$"),
            "graph_query_calls": self.count_matching(r"/graph-query$"),
            "simulate_patch_calls": self.count_matching(r"/simulate-patch$"),
            "all_authorized": self.all_authorized(),
            "requests": [
                {
                    "path": record.path,
                    "authorization_present": record.authorization_present,
                    "payload": record.payload,
                }
                for record in self.requests
            ],
        }


def _json_response(handler: BaseHTTPRequestHandler, status_code: int, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload).encode("utf-8")
    handler.send_response(status_code)
    handler.send_header("content-type", "application/json")
    handler.send_header("content-length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def _requested_target_file(payload: dict[str, Any]) -> str:
    changed_files = payload.get("changed_files")
    if isinstance(changed_files, list):
        for candidate in changed_files:
            if isinstance(candidate, str) and candidate.strip():
                return candidate
    file_path = payload.get("file_path")
    if isinstance(file_path, str) and file_path.strip():
        return file_path
    return DEFAULT_TARGET_FILE


def _build_engine_handler(state: _EngineState) -> type[BaseHTTPRequestHandler]:
    class EngineHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            body = self.rfile.read(int(self.headers.get("content-length", "0")) or 0)
            payload = json.loads(body.decode("utf-8") or "{}")
            if not isinstance(payload, dict):
                _json_response(self, 400, {"error": "payload must be an object"})
                return
            target_file = _requested_target_file(payload)
            state.record(
                path=self.path,
                authorization_present=bool(self.headers.get("authorization")),
                payload=payload,
            )
            if re.fullmatch(r"/v1/repositories/[^/]+/triage", self.path):
                _json_response(
                    self,
                    200,
                    {
                        "suspect_files": [target_file],
                        "suspect_symbols": ["alpha"],
                        "reduction_ratio": 12.5,
                        "evidence_items": [
                            {
                                "file_path": target_file,
                                "snippet": "alpha",
                            }
                        ],
                    },
                )
                return
            if re.fullmatch(r"/v1/repositories/[^/]+/graph-query", self.path):
                _json_response(
                    self,
                    200,
                    {
                        "nodes": [{"id": target_file, "kind": "file"}],
                        "edges": [],
                    },
                )
                return
            if re.fullmatch(r"/v1/repositories/[^/]+/simulate-patch", self.path):
                _json_response(
                    self,
                    200,
                    {
                        "recommended_action": "apply_patch",
                        "confidence": 0.99,
                        "engine_version": "algenta-proof-engine/v1",
                        "execution_ms": 7,
                    },
                )
                return
            _json_response(
                self,
                404,
                {"error": f"unsupported proof engine route: {self.path}"},
            )

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    return EngineHandler


@contextlib.contextmanager
def _proof_engine_server() -> tuple[str, _EngineState]:
    state = _EngineState()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _build_engine_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", state
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _normalize_target_file(target_file: str) -> str:
    if not isinstance(target_file, str) or not target_file.strip():
        raise ValueError("target_file must be a non-empty repo-relative path")
    normalized = str(PurePosixPath(target_file.strip()))
    if normalized in {"", ".", ".."}:
        raise ValueError("target_file must be a non-empty repo-relative path")
    if normalized.startswith("/") or normalized.startswith("../") or "/../" in normalized:
        raise ValueError("target_file must stay within the proof repository")
    return normalized


def _scenario_slug(value: str) -> str:
    sanitized = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return sanitized or "live-run-proof"


@contextlib.contextmanager
def _proof_git_repo(*, target_file: str = DEFAULT_TARGET_FILE, initial_content: str = "alpha\n") -> Path:
    with tempfile.TemporaryDirectory(prefix="algenta-proof-repo-") as temp_dir:
        repo_dir = Path(temp_dir)
        normalized_target_file = _normalize_target_file(target_file)
        subprocess.run(
            ["git", "init", "-b", "main"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "codex@example.com"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Codex"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        target_path = repo_dir / normalized_target_file
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(initial_content, encoding="utf-8")
        subprocess.run(
            ["git", "add", normalized_target_file],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=repo_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        yield repo_dir


def _required_relative_artifact(
    root: Path,
    payload: dict[str, Any],
    field_name: str,
) -> Path:
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("session payload missing artifacts object")
    relative_path = artifacts.get(field_name)
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError(f"session artifacts missing {field_name}")
    return root / relative_path


def _load_run_bundle(root: Path, session_payload: dict[str, Any]) -> dict[str, Any]:
    runtime_manifest_path = _required_relative_artifact(root, session_payload, "runtime_manifest")
    run_dir = runtime_manifest_path.parent
    return {
        "run_dir": artifact_relative_path(root, run_dir),
        "runtime_manifest": read_json(runtime_manifest_path),
        "messages": read_json(_required_relative_artifact(root, session_payload, "messages")),
        "usage": read_json(_required_relative_artifact(root, session_payload, "usage")),
        "tool_calls": read_json(_required_relative_artifact(root, session_payload, "tool_calls")),
        "approvals": read_json(_required_relative_artifact(root, session_payload, "approvals")),
        "gate": read_json(_required_relative_artifact(root, session_payload, "gate")),
    }


def collect_live_run_proof(
    *,
    root: Path | None = None,
    output_path: Path | None = None,
    target_file: str = DEFAULT_TARGET_FILE,
    language: str | None = None,
    scenario_label: str = "live_run_proof",
) -> dict[str, Any]:
    resolved_root = repo_root() if root is None else Path(root).resolve()
    context = build_proof_context(resolved_root)
    owner_header = {"x-session-owner": PROOF_OWNER}
    normalized_target_file = _normalize_target_file(target_file)
    normalized_scenario = _scenario_slug(scenario_label)
    language_label = language.strip() if isinstance(language, str) and language.strip() else None
    prompt_suffix = f"\nTARGET_FILE={normalized_target_file}"
    if language_label is not None:
        prompt_suffix += f"\nLANGUAGE={language_label}"

    with (
        _proof_git_repo(target_file=normalized_target_file) as proof_repo,
        isolated_cline_runtime_environment(prefix="algenta-proof-runtime-") as runtime_env,
        _proof_engine_server() as (engine_url, engine_state),
        agent_core_runtime(
            resolved_root,
            extra_env={
                PROOF_PROVIDER_API_KEY_ENV: "algenta-proof-local-key",
                **runtime_env,
            },
        ) as base_url,
    ):
        create_status, created = request_json(
            "POST",
            f"{base_url}/sessions",
            payload={
                "working_dir": str(proof_repo),
                "prompt": (
                    "Run the Algenta proof sequence and stop after simulate_patch."
                    f"{prompt_suffix}"
                ),
                "repository_scope": "proof_repository",
                "approval_profile": "repository_fix_gated",
                "channel": "test",
                "provider": PROOF_PROVIDER_ID,
                "model": PROOF_MODEL_ID,
                "idempotency_key": f"cline-live-proof-{normalized_scenario}",
                "engine": {
                    "url": engine_url,
                    "repository_id": "proof_repository",
                    "snapshot_id": "snapshot_proof",
                    "api_key": "proof-engine-key",
                    "required_tools": ["simulate_patch"],
                    "expected_calls": ["simulate_patch"],
                    "fail_on_zero_calls": True,
                    "require_govern_hook": True,
                },
                "authorization": {
                    "caller": PROOF_OWNER,
                    "workflow_identity": "local/proof",
                    "repository_allowed": True,
                    "branch_allowed": True,
                },
            },
            headers=owner_header,
            timeout_seconds=60,
        )
        if create_status != 201:
            raise RuntimeError(f"failed to create proof session: {create_status} {created}")
        session_id = created.get("session_id")
        if not isinstance(session_id, str) or not session_id.strip():
            raise RuntimeError("proof session creation did not return a session_id")

        start_status, started = request_json(
            "POST",
            f"{base_url}/sessions/{session_id}/start",
            payload={
                "prompt": (
                    "Run the deterministic Algenta proof plan now."
                    f"{prompt_suffix}"
                )
            },
            headers=owner_header,
            timeout_seconds=120,
        )
        if start_status != 200:
            raise RuntimeError(f"failed to start proof session: {start_status} {started}")

        get_status, session_payload = request_json(
            "GET",
            f"{base_url}/sessions/{session_id}",
            headers=owner_header,
            timeout_seconds=60,
        )
        if get_status != 200:
            raise RuntimeError(f"failed to read proof session: {get_status} {session_payload}")

        run_bundle = _load_run_bundle(resolved_root, session_payload)
        proof_file_text = (proof_repo / normalized_target_file).read_text(encoding="utf-8")

    runtime_manifest = run_bundle["runtime_manifest"]
    tool_calls = run_bundle["tool_calls"]
    gate = run_bundle["gate"]
    approvals = run_bundle["approvals"]
    usage = run_bundle["usage"]
    engine_summary = engine_state.to_summary()
    passed = (
        session_payload.get("terminal_state") == "succeeded"
        and runtime_manifest.get("engine", {}).get("enabled") is True
        and runtime_manifest.get("plugins", {}).get("simulate_patch") == "loaded"
        and {"localize", "graph_query", "simulate_patch"}.issubset(
            set(tool_calls.get("tool_calls_by_name", {}))
        )
        and tool_calls.get("govern_hook", {}).get("status") == "observed"
        and gate.get("terminal_state") == "succeeded"
        and engine_summary["triage_calls"] == 1
        and engine_summary["graph_query_calls"] == 1
        and engine_summary["simulate_patch_calls"] >= 2
        and engine_summary["all_authorized"] is True
        and "beta" in proof_file_text
        and bool(approvals.get("approval_events"))
        and isinstance(usage.get("usage"), dict)
    )

    payload = {
        **create_artifact_provenance(
            context,
            run_id="live_run_proof",
            schema_version="cline-live-run-proof/v1",
        ),
        "status": "passed" if passed else "failed",
        "session_id": session_payload.get("session_id"),
        "agent_run_id": session_payload.get("agent_run_id"),
        "terminal_state": session_payload.get("terminal_state"),
        "language": language_label,
        "scenario_label": normalized_scenario,
        "proof_repository_file": {
            "path": normalized_target_file,
            "content": proof_file_text,
        },
        "runtime_manifest": runtime_manifest,
        "tool_calls": tool_calls,
        "approvals": approvals,
        "gate": gate,
        "usage": usage,
        "engine_requests": engine_summary,
        "run_dir": run_bundle["run_dir"],
    }

    resolved_output_path = (
        resolved_root / LIVE_RUN_PROOF_PATH if output_path is None else Path(output_path)
    )
    write_json(resolved_output_path, payload)
    payload["artifact_path"] = artifact_relative_path(resolved_root, resolved_output_path)
    return payload
