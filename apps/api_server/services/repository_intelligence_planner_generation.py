from __future__ import annotations

import ast
import difflib
import json
import os
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from apps.api_server.services import (
    repository_intelligence_config as repository_config,
)
from apps.api_server.services import (
    repository_intelligence_indexing as repository_indexing,
)
from apps.api_server.services import (
    repository_intelligence_storage as repository_storage,
)
from apps.api_server.services.llm_api_service import (
    create_chat_completion,
    list_llm_model_descriptors,
)
from apps.api_server.services.llm_provider_service import get_configured_provider_model
from apps.api_server.services.repository_intelligence_contracts import (
    RepositoryIntelligenceError,
    _DeterministicConfigPatch,
    _DeterministicLiteralPatch,
)

_RETURN_LITERAL_MISMATCH_RE = re.compile(
    r"""returns\s+(?P<wrong_quote>['"])(?P<wrong>.+?)(?P=wrong_quote)\s+instead\s+of\s+(?P<expected_quote>['"])(?P<expected>.+?)(?P=expected_quote)""",
    re.IGNORECASE,
)
_TSCONFIG_PROJECT_ARG_RE = re.compile(r"(?:^|\s)(?:-p|--project)\s+(?P<path>[^\s]+)")


def _resolve_repository_model(
    explicit_model: str | None,
    *,
    deterministic_local_model_id: str,
    verified_agentic_model_id: str | None = None,
) -> str:
    candidates: list[str] = []
    if explicit_model:
        candidates.append(explicit_model)
    env_model = str(os.environ.get("ALGENTA_REPOSITORY_INTELLIGENCE_MODEL") or "").strip()
    if env_model:
        candidates.append(env_model)
    for descriptor in list_llm_model_descriptors():
        if "chat_completions" in descriptor.capabilities:
            candidates.append(descriptor.model_id)
    seen: set[str] = set()
    for model_id in candidates:
        if model_id in seen:
            continue
        seen.add(model_id)
        if model_id == deterministic_local_model_id:
            return model_id
        if verified_agentic_model_id is not None and model_id == verified_agentic_model_id:
            return model_id
        if get_configured_provider_model(model_id) is not None:
            return model_id
    raise RepositoryIntelligenceError(
        code="repository_model_unavailable",
        message=(
            "Repository decision planning requires either a configured provider-backed "
            "chat model or the explicit bounded local planner model "
            f"'{deterministic_local_model_id}'. Set "
            "ALGENTA_REPOSITORY_INTELLIGENCE_MODEL or configure a provider-backed "
            "/v1/models entry."
        ),
        status_code=503,
    )


def _raise_local_planner_unsupported(
    *,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    raise RepositoryIntelligenceError(
        code="repository_local_planner_unsupported",
        message=message,
        status_code=422,
        details=details,
    )


def _extract_return_literal_mismatch(message: str) -> tuple[str, str] | None:
    match = _RETURN_LITERAL_MISMATCH_RE.search(message)
    if match is None:
        return None
    return match.group("wrong"), match.group("expected")


def _workspace_context_value(workspace_context: Sequence[str], prefix: str) -> str | None:
    normalized_prefix = f"{prefix}:"
    for entry in workspace_context:
        text = str(entry).strip()
        if text.startswith(normalized_prefix):
            value = text[len(normalized_prefix) :].strip()
            if value:
                return value
    return None


def _deterministic_typescript_rootdir_patch(
    *,
    snapshot_manifest: dict[str, Any],
    triage_manifest: dict[str, Any],
    root_path: Path,
) -> _DeterministicConfigPatch:
    files_by_path = {entry["file_path"]: entry for entry in snapshot_manifest["files"]}
    diagnostics = [
        diagnostic
        for diagnostic in triage_manifest.get("signals", {}).get("diagnostics", [])
        if str(diagnostic.get("code") or "") == "TS6059"
    ]
    if not diagnostics:
        _raise_local_planner_unsupported(
            message=(
                "Deterministic local repository planner only supports explicit TS6059 "
                "rootDir diagnostics for TypeScript repositories."
            ),
            details={"snapshot_id": snapshot_manifest["snapshot_id"]},
        )
    workspace_context = tuple(
        str(entry) for entry in triage_manifest.get("signals", {}).get("workspace_context", [])
    )
    project_path = _workspace_context_value(workspace_context, "tsconfig_project")
    diagnostic_base_path = _workspace_context_value(workspace_context, "diagnostic_base_path")
    if project_path is None:
        command_text = _workspace_context_value(workspace_context, "command")
        if command_text:
            project_match = _TSCONFIG_PROJECT_ARG_RE.search(command_text)
            if project_match is not None:
                project_candidate = project_match.group("path").strip()
                base_dir = diagnostic_base_path or ""
                resolved_project = (
                    repository_indexing._normalize_repository_relative_path(
                        str((Path(base_dir) / project_candidate).as_posix())
                    )
                    if base_dir
                    else repository_indexing._normalize_repository_relative_path(
                        project_candidate
                    )
                )
                if resolved_project:
                    project_path = resolved_project
    if project_path is None:
        _raise_local_planner_unsupported(
            message=(
                "Deterministic local repository planner requires explicit tsconfig_project "
                "workspace context for TS6059 diagnostics."
            ),
            details={"workspace_context": list(workspace_context)},
        )
    if project_path not in files_by_path:
        _raise_local_planner_unsupported(
            message=(
                "Deterministic local repository planner requires the tsconfig project file "
                f"'{project_path}' to be included in the snapshot."
            ),
            details={"project_path": project_path, "snapshot_id": snapshot_manifest["snapshot_id"]},
        )

    root_abs = root_path.resolve()
    project_file = (root_abs / project_path).resolve()
    project_text = project_file.read_text(encoding="utf-8")
    project_payload = repository_config._load_jsonc_object(
        file_path=project_path,
        text=project_text,
        unsupported_handler=_raise_local_planner_unsupported,
    )
    project_dir = project_file.parent

    anchor_paths: list[Path] = [project_dir]
    if diagnostic_base_path:
        anchor_paths.append((root_abs / diagnostic_base_path).resolve())
    impacted_paths: list[Path] = []
    for diagnostic in diagnostics:
        diagnostic_path = str(diagnostic.get("path") or "").strip()
        if not diagnostic_path:
            continue
        candidate = (root_abs / diagnostic_path).resolve()
        if candidate.exists():
            impacted_paths.append(candidate)
            anchor_paths.append(candidate)
    if not impacted_paths:
        _raise_local_planner_unsupported(
            message=(
                "Deterministic local repository planner requires at least one TS6059 "
                "diagnostic path present in the snapshot source archive."
            ),
            details={"project_path": project_path, "diagnostic_count": len(diagnostics)},
        )

    required_root_abs = Path(os.path.commonpath([str(path) for path in anchor_paths]))
    recommended_root_dir = repository_config._relative_root_dir(project_dir, required_root_abs)

    extends_value = project_payload.get("extends")
    if isinstance(extends_value, str):
        parent_path = repository_config._resolve_tsconfig_extends_path(
            root_path=root_path,
            project_file_path=project_path,
            extends_value=extends_value,
        )
        if parent_path:
            parent_file = (root_abs / parent_path).resolve()
            if parent_file.exists():
                parent_payload = repository_config._load_jsonc_object(
                    file_path=parent_path,
                    text=parent_file.read_text(encoding="utf-8"),
                    unsupported_handler=_raise_local_planner_unsupported,
                )
                parent_root_dir = repository_config._tsconfig_root_dir_from_payload(
                    parent_payload
                )
                if parent_root_dir:
                    parent_root_abs = (parent_file.parent / parent_root_dir).resolve()
                    if all(
                        candidate == parent_root_abs or parent_root_abs in candidate.parents
                        for candidate in anchor_paths
                    ):
                        recommended_root_dir = repository_config._relative_root_dir(
                            project_dir,
                            parent_root_abs,
                        )

    updated_text, old_root_dir = repository_config._update_tsconfig_root_dir_text(
        file_path=project_path,
        text=project_text,
        new_root_dir=recommended_root_dir,
        unsupported_handler=_raise_local_planner_unsupported,
    )
    patch_diff = "".join(
        difflib.unified_diff(
            project_text.splitlines(keepends=True),
            updated_text.splitlines(keepends=True),
            fromfile=f"a/{project_path}",
            tofile=f"b/{project_path}",
        )
    )
    if not patch_diff.strip():
        _raise_local_planner_unsupported(
            message=(
                "Deterministic local repository planner produced an empty tsconfig patch for "
                f"'{project_path}'."
            ),
            details={"project_path": project_path, "new_root_dir": recommended_root_dir},
        )
    return _DeterministicConfigPatch(
        file_path=project_path,
        old_root_dir=old_root_dir,
        new_root_dir=recommended_root_dir,
        diagnostic_count=len(diagnostics),
        patch_diff=patch_diff,
    )


def _position_to_offset(text: str, *, line: int, column: int) -> int:
    if line < 1 or column < 0:
        raise ValueError("line and column must be positive.")
    offset = 0
    current_line = 1
    for segment in text.splitlines(keepends=True):
        if current_line == line:
            return offset + min(column, len(segment))
        offset += len(segment)
        current_line += 1
    if current_line == line:
        return offset + column
    raise ValueError(f"line {line} is outside the available source range.")


def _python_string_literal(value: str, *, quote: str) -> str:
    escaped = value.replace("\\", "\\\\")
    if quote == "'":
        escaped = escaped.replace("'", "\\'")
    else:
        escaped = escaped.replace('"', '\\"')
    return f"{quote}{escaped}{quote}"


def _deterministic_python_return_literal_patch(
    *,
    file_path: str,
    text: str,
    diagnostic_line: int | None,
    suspect_symbols: Sequence[str],
    current_literal: str,
    expected_literal: str,
) -> _DeterministicLiteralPatch:
    try:
        tree = ast.parse(text, filename=file_path)
    except SyntaxError as exc:
        _raise_local_planner_unsupported(
            message=(
                "Deterministic local repository planner only supports syntactically valid "
                f"Python files; failed to parse '{file_path}'."
            ),
            details={"file_path": file_path, "syntax_error": str(exc)},
        )

    functions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    if suspect_symbols:
        matching_functions = [node for node in functions if node.name in set(suspect_symbols)]
        if matching_functions:
            functions = matching_functions
    if diagnostic_line is not None:
        containing_functions = [
            node
            for node in functions
            if node.lineno <= diagnostic_line <= getattr(node, "end_lineno", node.lineno)
        ]
        if containing_functions:
            functions = containing_functions
    if not functions:
        _raise_local_planner_unsupported(
            message=(
                "Deterministic local repository planner could not localize a unique Python "
                f"function in '{file_path}'."
            ),
            details={
                "file_path": file_path,
                "diagnostic_line": diagnostic_line,
                "suspect_symbols": list(suspect_symbols),
            },
        )

    def _matching_return_nodes(
        target_function: ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> list[ast.Return]:
        matches: list[ast.Return] = []

        class ReturnVisitor(ast.NodeVisitor):
            def visit_Return(self, node: ast.Return) -> Any:
                value = node.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    if value.value == current_literal:
                        matches.append(node)

            def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
                if node is target_function:
                    self.generic_visit(node)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
                if node is target_function:
                    self.generic_visit(node)

            def visit_ClassDef(self, node: ast.ClassDef) -> Any:
                return None

            def visit_Lambda(self, node: ast.Lambda) -> Any:
                return None

        ReturnVisitor().visit(target_function)
        return matches

    candidate_nodes: list[tuple[ast.Return, ast.FunctionDef | ast.AsyncFunctionDef]] = []
    for function_node in functions:
        candidate_nodes.extend(
            (return_node, function_node)
            for return_node in _matching_return_nodes(function_node)
        )

    if diagnostic_line is not None:
        exact_line_matches = [
            (node, function_node)
            for node, function_node in candidate_nodes
            if node.lineno == diagnostic_line
        ]
        if exact_line_matches:
            candidate_nodes = exact_line_matches
        else:
            nearest_distance = min(
                (
                    abs(node.lineno - diagnostic_line)
                    for node, _function_node in candidate_nodes
                ),
                default=None,
            )
            if nearest_distance is not None:
                candidate_nodes = [
                    (node, function_node)
                    for node, function_node in candidate_nodes
                    if abs(node.lineno - diagnostic_line) == nearest_distance
                ]

    if len(candidate_nodes) != 1:
        _raise_local_planner_unsupported(
            message=(
                "Deterministic local repository planner requires exactly one matching "
                f"return literal candidate in '{file_path}'."
            ),
            details={
                "file_path": file_path,
                "diagnostic_line": diagnostic_line,
                "suspect_symbols": list(suspect_symbols),
                "candidate_count": len(candidate_nodes),
                "current_literal": current_literal,
                "expected_literal": expected_literal,
            },
        )

    return_node, function_node = candidate_nodes[0]
    constant_node = return_node.value
    if not isinstance(constant_node, ast.Constant) or not isinstance(constant_node.value, str):
        _raise_local_planner_unsupported(
            message=(
                "Deterministic local repository planner requires a direct string literal "
                f"return in '{file_path}'."
            ),
            details={"file_path": file_path, "diagnostic_line": diagnostic_line},
        )

    source_segment = ast.get_source_segment(text, constant_node) or repr(current_literal)
    quote = '"' if source_segment.startswith('"') else "'"
    replacement_literal = _python_string_literal(expected_literal, quote=quote)
    start_offset = _position_to_offset(
        text,
        line=constant_node.lineno,
        column=constant_node.col_offset,
    )
    end_offset = _position_to_offset(
        text,
        line=getattr(constant_node, "end_lineno", constant_node.lineno),
        column=getattr(constant_node, "end_col_offset", constant_node.col_offset),
    )
    updated_text = f"{text[:start_offset]}{replacement_literal}{text[end_offset:]}"
    patch_diff = "".join(
        difflib.unified_diff(
            text.splitlines(keepends=True),
            updated_text.splitlines(keepends=True),
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )
    )
    if not patch_diff.strip():
        _raise_local_planner_unsupported(
            message=(
                "Deterministic local repository planner produced an empty patch diff for "
                f"'{file_path}'."
            ),
            details={"file_path": file_path, "diagnostic_line": diagnostic_line},
        )
    return _DeterministicLiteralPatch(
        file_path=file_path,
        symbol_name=function_node.name,
        diagnostic_line=diagnostic_line,
        current_literal=current_literal,
        expected_literal=expected_literal,
        patch_diff=patch_diff,
    )


def _generate_deterministic_repository_patch_plan(
    *,
    snapshot_manifest: dict[str, Any],
    triage_manifest: dict[str, Any],
    deterministic_local_model_id: str,
) -> dict[str, Any]:
    files_by_path = {entry["file_path"]: entry for entry in snapshot_manifest["files"]}
    diagnostics = triage_manifest.get("signals", {}).get("diagnostics", [])
    suspect_symbols = tuple(
        str(symbol).strip()
        for symbol in triage_manifest.get("suspect_symbols", [])
        if str(symbol).strip()
    )
    with repository_storage.materialized_snapshot(snapshot_manifest) as root_path:
        ts6059_diagnostics = [
            diagnostic
            for diagnostic in diagnostics
            if str(diagnostic.get("code") or "") == "TS6059"
        ]
        if ts6059_diagnostics:
            patch = _deterministic_typescript_rootdir_patch(
                snapshot_manifest=snapshot_manifest,
                triage_manifest=triage_manifest,
                root_path=root_path,
            )
            return {
                "root_cause": (
                    f"TypeScript project '{patch.file_path}' constrains rootDir to "
                    f"{patch.old_root_dir!r}, which excludes files implicated by "
                    f"{patch.diagnostic_count} TS6059 diagnostics."
                ),
                "planner_model_id": deterministic_local_model_id,
                "planner_execution_mode": "deterministic_local",
                "planner_provider_backend": None,
                "candidate_fixes": [
                    f"Broaden {patch.file_path} rootDir from {patch.old_root_dir!r} "
                    f"to {patch.new_root_dir!r} so the project spans the diagnosed "
                    "workspace boundary."
                ],
                "recommended_action": (
                    f"Set {patch.file_path} compilerOptions.rootDir to "
                    f"{patch.new_root_dir!r}."
                ),
                "rationale": (
                    "Explicit deterministic local repository planning matched TS6059 "
                    "rootDir diagnostics, localized the project tsconfig from workspace "
                    "context, computed the minimal ancestor covering the diagnosed files, "
                    "and produced a single-file config patch."
                ),
                "confidence": 0.94,
                "patch_diff": patch.patch_diff,
            }
        for diagnostic in diagnostics:
            file_path = str(diagnostic.get("path") or "").strip()
            message = str(diagnostic.get("message") or "").strip()
            mismatch = _extract_return_literal_mismatch(message)
            if not file_path or mismatch is None:
                continue
            file_entry = files_by_path.get(file_path)
            if file_entry is None:
                continue
            if str(file_entry.get("language") or "") != "python":
                continue
            current_literal, expected_literal = mismatch
            source_path = root_path / file_path
            if not source_path.exists():
                continue
            patch = _deterministic_python_return_literal_patch(
                file_path=file_path,
                text=source_path.read_text(encoding="utf-8"),
                diagnostic_line=int(diagnostic["line"]) if diagnostic.get("line") else None,
                suspect_symbols=suspect_symbols,
                current_literal=current_literal,
                expected_literal=expected_literal,
            )
            line_ref = (
                f"{patch.file_path}:{patch.diagnostic_line}"
                if patch.diagnostic_line is not None
                else patch.file_path
            )
            symbol_name = patch.symbol_name or "repository target"
            return {
                "root_cause": (
                    f"{symbol_name} returns {patch.current_literal!r} instead of "
                    f"{patch.expected_literal!r} at {line_ref}."
                ),
                "planner_model_id": deterministic_local_model_id,
                "planner_execution_mode": "deterministic_local",
                "planner_provider_backend": None,
                "candidate_fixes": [
                    f"Replace the incorrect return literal in {line_ref} so {symbol_name} "
                    f"returns {patch.expected_literal!r}."
                ],
                "recommended_action": (
                    f"Correct {symbol_name} in {patch.file_path} to return "
                    f"{patch.expected_literal!r}."
                ),
                "rationale": (
                    "Explicit deterministic local repository planning matched one Python "
                    "string-literal return against the bounded diagnostic evidence and "
                    "produced a single-file patch."
                ),
                "confidence": 0.98,
                "patch_diff": patch.patch_diff,
            }
    _raise_local_planner_unsupported(
        message=(
            "Deterministic local repository planner only supports bounded return-literal "
            "mismatch diagnostics for Python repository files."
        ),
        details={
            "snapshot_id": snapshot_manifest["snapshot_id"],
            "suspect_symbols": list(suspect_symbols),
            "diagnostic_count": len(diagnostics),
        },
    )


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        payload = json.loads(stripped)
        if isinstance(payload, dict):
            return payload
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start >= 0 and end > start:
        payload = json.loads(stripped[start : end + 1])
        if isinstance(payload, dict):
            return payload
    raise RepositoryIntelligenceError(
        code="repository_model_invalid_output",
        message="Repository planner model returned invalid JSON.",
        status_code=502,
    )


async def _generate_repository_patch_plan(
    *,
    model_id: str,
    snapshot_manifest: dict[str, Any],
    triage_manifest: dict[str, Any],
    deterministic_local_model_id: str,
    verified_agentic_model_id: str | None = None,
) -> dict[str, Any]:
    if model_id == deterministic_local_model_id:
        return _generate_deterministic_repository_patch_plan(
            snapshot_manifest=snapshot_manifest,
            triage_manifest=triage_manifest,
            deterministic_local_model_id=deterministic_local_model_id,
        )
    if verified_agentic_model_id is not None and model_id == verified_agentic_model_id:
        return await _generate_verified_agentic_repository_patch_plan(
            model_id=model_id,
            snapshot_manifest=snapshot_manifest,
            triage_manifest=triage_manifest,
        )
    evidence_items = triage_manifest["evidence_items"]
    prompt_payload = {
        "snapshot_id": snapshot_manifest["snapshot_id"],
        "resolved_revision": snapshot_manifest["resolved_revision"],
        "signals": triage_manifest["signals"],
        "evidence_items": evidence_items,
        "instructions": {
            "format": "Return JSON only.",
            "required_keys": [
                "root_cause",
                "candidate_fixes",
                "recommended_action",
                "rationale",
                "confidence",
                "patch_diff",
            ],
            "patch_requirements": [
                "Return a unified diff with paths relative to repository root.",
                "Patch must only touch files present in the evidence bundle or directly "
                "related dependencies.",
                "Do not include markdown fences.",
            ],
        },
    }
    _, completion = await create_chat_completion(
        model_id=model_id,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are Algenta Repository Intelligence. Produce one safe repository "
                    "fix plan. Return strict JSON only with the required keys."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(prompt_payload, separators=(",", ":"), ensure_ascii=True),
            },
        ],
    )
    result = _extract_json_object(completion.content)
    provider_config = get_configured_provider_model(model_id)
    result["planner_model_id"] = model_id
    result["planner_execution_mode"] = "provider_backed_chat"
    result["planner_provider_backend"] = (
        provider_config.backend if provider_config is not None else None
    )
    raw_patch_diff = result.get("patch_diff")
    patch_diff = "" if raw_patch_diff is None else str(raw_patch_diff)
    if not patch_diff.strip():
        raise RepositoryIntelligenceError(
            code="repository_model_missing_patch",
            message="Repository planner model did not return a patch_diff.",
            status_code=502,
        )
    return result


# ─── verified_agentic planner tier (forked-Cline agent-core; engine "cline_fork") ──
#
# Instead of a single blind chat completion, this tier runs a headless agent loop
# inside the materialized checkout, with our token-compressed triage evidence +
# (optional) graph blast-radius injected so the agent skips repository exploration.
# Python — not the agent — is the source of truth for the diff: it is recomputed
# from before/after tree state. The Node sidecar is reached through the injected
# ``run_agent`` callable (``_DEFAULT_RUN_AGENT`` until the sidecar is wired), which
# keeps this seam testable without Node or a live model.

_VERIFIED_AGENTIC_MAX_CAPTURE_FILE_BYTES = 1_000_000


def _default_run_agent(
    *,
    working_dir: str,
    task_spec: dict[str, Any],
    injected_context: dict[str, Any],
    limits: dict[str, Any],
) -> dict[str, Any]:
    """Placeholder agent runner — the Node agent-core sidecar is not wired yet.

    Production replaces this with a callable that POSTs to the forked-Cline
    agent-core over the loopback NDJSON contract and mutates files under
    ``working_dir``. Kept monkeypatchable so the Python seam is testable in
    isolation.
    """
    del working_dir, task_spec, injected_context, limits
    raise RepositoryIntelligenceError(
        code="repository_agent_core_unavailable",
        message=(
            "verified_agentic repository planning requires the agent-core sidecar, "
            "which is not configured in this deployment."
        ),
        status_code=503,
    )


_DEFAULT_RUN_AGENT = _default_run_agent
_DEFAULT_GRAPH_QUERY = None


def _capture_repository_tree_state(root_path: Path) -> dict[str, str]:
    """Snapshot the textual contents of every readable file under ``root_path``.

    Binary, oversized, symlinked, and VCS-internal files are skipped. Used to
    compute the authoritative diff in Python (the agent's own ``working_tree_diff``
    is advisory/debug only).
    """
    state: dict[str, str] = {}
    root_abs = root_path.resolve()
    for path in sorted(root_abs.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root_abs).as_posix()
        if relative == ".git" or relative.startswith(".git/"):
            continue
        try:
            if path.stat().st_size > _VERIFIED_AGENTIC_MAX_CAPTURE_FILE_BYTES:
                continue
            state[relative] = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
    return state


def _unified_diff_from_tree_states(
    before: dict[str, str],
    after: dict[str, str],
) -> str:
    """Build a ``git apply``-able unified diff from before/after tree snapshots."""
    segments: list[str] = []
    for relative in sorted(set(before) | set(after)):
        old_text = before.get(relative)
        new_text = after.get(relative)
        if old_text == new_text:
            continue
        from_lines = old_text.splitlines(keepends=True) if old_text is not None else []
        to_lines = new_text.splitlines(keepends=True) if new_text is not None else []
        from_file = "/dev/null" if old_text is None else f"a/{relative}"
        to_file = "/dev/null" if new_text is None else f"b/{relative}"
        segments.append(
            "".join(
                difflib.unified_diff(
                    from_lines,
                    to_lines,
                    fromfile=from_file,
                    tofile=to_file,
                )
            )
        )
    return "".join(segments)


async def _generate_verified_agentic_repository_patch_plan(
    *,
    model_id: str,
    snapshot_manifest: dict[str, Any],
    triage_manifest: dict[str, Any],
    run_agent: Any = None,
    graph_query: Any = None,
) -> dict[str, Any]:
    """Run the forked-Cline agent loop over the materialized checkout.

    Returns the same dict shape as the other planner tiers so all downstream
    decision-plan / simulate / apply code is unchanged. ``planner_engine`` and the
    agent provenance are included for the *internal* audit record only — the
    public ``RepositoryAnalysis`` mapping does not read them (red line #4).
    """
    run_agent = run_agent or _DEFAULT_RUN_AGENT
    if graph_query is None:
        graph_query = _DEFAULT_GRAPH_QUERY

    suspect_files = list(triage_manifest.get("suspect_files", []))
    suspect_symbols = list(triage_manifest.get("suspect_symbols", []))
    signals = triage_manifest.get("signals", {})

    injected_context: dict[str, Any] = {
        "evidence_items": triage_manifest.get("evidence_items", []),
        "suspect_files": suspect_files,
        "suspect_symbols": suspect_symbols,
        "signals": signals,
    }
    if graph_query is not None:
        try:
            injected_context["graph_blast_radius"] = graph_query(
                snapshot_manifest=snapshot_manifest,
                suspect_files=suspect_files,
                suspect_symbols=suspect_symbols,
            )
        except Exception:  # noqa: BLE001 — graph injection is best-effort context
            injected_context["graph_blast_radius"] = None

    task_spec = {
        "snapshot_id": snapshot_manifest["snapshot_id"],
        "resolved_revision": snapshot_manifest.get("resolved_revision"),
        "issue_text": signals.get("issue_text"),
    }
    limits = {"token_budget": 6_000, "max_turns": 8}

    with repository_storage.materialized_snapshot(snapshot_manifest) as root_path:
        root_path = Path(root_path)
        before_state = _capture_repository_tree_state(root_path)
        agent_result = run_agent(
            working_dir=str(root_path),
            task_spec=task_spec,
            injected_context=injected_context,
            limits=limits,
        )
        if not isinstance(agent_result, dict):
            raise RepositoryIntelligenceError(
                code="repository_agent_invalid_result",
                message="verified_agentic agent runner returned a non-object result.",
                status_code=502,
            )
        # Python is the source of truth for the diff; any working_tree_diff the
        # agent returns is advisory/debug only and deliberately ignored here.
        after_state = _capture_repository_tree_state(root_path)

    status = str(agent_result.get("status") or "completed")
    patch_diff = _unified_diff_from_tree_states(before_state, after_state)

    if status in {"failed", "aborted"}:
        raise RepositoryIntelligenceError(
            code=f"repository_agent_{status}",
            message=f"verified_agentic agent run did not complete (status={status}).",
            status_code=502,
            details={"agent_run_id": agent_result.get("agent_run_id")},
        )
    if not patch_diff.strip():
        raise RepositoryIntelligenceError(
            code="repository_agent_no_change",
            message="verified_agentic agent run produced no file changes.",
            status_code=422,
            details={"agent_run_id": agent_result.get("agent_run_id")},
        )

    candidate_fixes = agent_result.get("candidate_fixes")
    if isinstance(candidate_fixes, str):
        candidate_fixes = [candidate_fixes]
    elif not isinstance(candidate_fixes, list):
        candidate_fixes = []

    try:
        confidence = float(agent_result.get("confidence"))
    except (TypeError, ValueError):
        confidence = 0.55
    confidence = min(max(confidence, 0.0), 1.0)

    return {
        "root_cause": str(agent_result.get("root_cause") or "").strip()
        or "Repository issue localized from the injected evidence bundle.",
        "candidate_fixes": candidate_fixes,
        "recommended_action": str(agent_result.get("recommended_action") or "").strip()
        or "Apply the agent-generated repository patch.",
        "rationale": str(agent_result.get("rationale") or "").strip()
        or (
            "Patch generated by the verified agentic planner over the injected "
            "repository evidence bundle and blast-radius."
        ),
        "confidence": confidence,
        "patch_diff": patch_diff,
        "planner_model_id": model_id,
        "planner_execution_mode": "verified_agentic",
        "planner_provider_backend": None,
        # Internal attribution / provenance only — NOT surfaced in the public DecisionPlan.
        "planner_engine": "cline_fork",
        "agent_run_id": agent_result.get("agent_run_id"),
        "transcript_ref": agent_result.get("transcript_ref"),
    }
