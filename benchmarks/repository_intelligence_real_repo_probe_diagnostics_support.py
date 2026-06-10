from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from apps.api_server.schemas.repositories import (
    RepositoryDiagnostic,
)


def _probe_module():
    from benchmarks import repository_intelligence_real_repo_probe as probe_module

    return probe_module


def _resolve_diagnostic_base_path(
    repo_path: Path,
    *,
    diagnostic_command: str | None,
    diagnostic_base_path: str | None,
) -> Path:
    probe_module = _probe_module()

    base_value = diagnostic_base_path
    if base_value is None and diagnostic_command:
        match = probe_module._COMMAND_CD_RE.match(diagnostic_command)
        if match:
            base_value = match.group("path").strip()
    if not base_value:
        return repo_path
    candidate = (repo_path / base_value).resolve()
    if candidate == repo_path or repo_path in candidate.parents:
        return candidate
    return repo_path


def _resolve_diagnostic_project_path(
    repo_path: Path,
    *,
    diagnostic_command: str | None,
    diagnostic_base_path: Path,
) -> str | None:
    probe_module = _probe_module()

    if not diagnostic_command:
        return None
    match = probe_module._PROJECT_ARG_RE.search(diagnostic_command)
    if match is None:
        return None
    candidate = (diagnostic_base_path / match.group("path").strip()).resolve()
    if candidate == repo_path or repo_path in candidate.parents:
        return str(candidate.relative_to(repo_path))
    return None


def _normalize_relative_path(
    repo_path: Path,
    raw_path: str,
    *,
    base_path: Path | None = None,
) -> str | None:
    candidate = Path(raw_path.strip())
    if not candidate.is_absolute():
        candidate = ((base_path or repo_path) / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if candidate == repo_path or repo_path in candidate.parents:
        return str(candidate.relative_to(repo_path))
    return None


def parse_repository_diagnostics(
    *,
    repo_path: Path,
    output: str,
    base_path: Path | None = None,
) -> list[RepositoryDiagnostic]:
    probe_module = _probe_module()

    diagnostics: list[RepositoryDiagnostic] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        ts_match = probe_module._TSC_DIAGNOSTIC_RE.match(line)
        if ts_match:
            normalized = _normalize_relative_path(
                repo_path,
                ts_match.group("path"),
                base_path=base_path,
            )
            diagnostics.append(
                RepositoryDiagnostic(
                    path=normalized,
                    line=int(ts_match.group("line")),
                    severity="error",
                    code=ts_match.group("code"),
                    message=ts_match.group("message").strip(),
                )
            )
            continue
        python_match = probe_module._PYTHON_TRACEBACK_FILE_RE.match(raw_line)
        if python_match:
            normalized = _normalize_relative_path(
                repo_path,
                python_match.group("path"),
                base_path=base_path,
            )
            function_name = str(python_match.group("function") or "").strip()
            diagnostics.append(
                RepositoryDiagnostic(
                    path=normalized,
                    line=int(python_match.group("line")),
                    severity="error",
                    code=None,
                    message=(
                        f"Python traceback frame in {function_name}"
                        if function_name
                        else "Python traceback frame"
                    ),
                )
            )
            continue
        node_match = probe_module._NODE_STACK_FRAME_RE.match(raw_line)
        if node_match:
            normalized = _normalize_relative_path(
                repo_path,
                node_match.group("path"),
                base_path=base_path,
            )
            function_name = str(node_match.group("function") or "").strip()
            diagnostics.append(
                RepositoryDiagnostic(
                    path=normalized,
                    line=int(node_match.group("line")),
                    severity="error",
                    code=None,
                    message=(
                        f"JavaScript stack frame in {function_name}"
                        if function_name
                        else "JavaScript stack frame"
                    ),
                )
            )
            continue
        rust_match = probe_module._RUST_SPAN_RE.match(raw_line)
        if rust_match:
            normalized = _normalize_relative_path(
                repo_path,
                rust_match.group("path"),
                base_path=base_path,
            )
            diagnostics.append(
                RepositoryDiagnostic(
                    path=normalized,
                    line=int(rust_match.group("line")),
                    severity="error",
                    code=None,
                    message="Rust compiler span",
                )
            )
            continue
        colon_match = probe_module._COLON_DIAGNOSTIC_RE.match(line)
        if colon_match:
            normalized = _normalize_relative_path(
                repo_path,
                colon_match.group("path"),
                base_path=base_path,
            )
            diagnostics.append(
                RepositoryDiagnostic(
                    path=normalized,
                    line=int(colon_match.group("line")),
                    severity="error",
                    code=None,
                    message=colon_match.group("message").strip(),
                )
            )
    return diagnostics


def _focus_paths_from_diagnostics(
    *,
    repo_path: Path,
    diagnostics: list[RepositoryDiagnostic],
    explicit_focus_paths: list[str],
) -> list[str]:
    focus_paths: list[str] = []
    seen: set[str] = set()

    def _add(value: str | None) -> None:
        if value is None:
            return
        normalized = value.strip().strip("/")
        if not normalized or normalized in seen:
            return
        seen.add(normalized)
        focus_paths.append(normalized)

    for value in explicit_focus_paths:
        _add(value)
    for diagnostic in diagnostics:
        if diagnostic.path:
            _add(diagnostic.path)
            parent = str(Path(diagnostic.path).parent)
            if parent not in {".", ""}:
                _add(parent)
    if not focus_paths:
        for default_path in ("services", "packages", "adapters", "scripts"):
            if (repo_path / default_path).exists():
                _add(default_path)
    return focus_paths


def _effective_focus_paths_for_snapshot(
    *,
    diagnostics: list[RepositoryDiagnostic],
    connected_files: list[str],
    fallback_focus_paths: list[str],
    config_focus_paths: list[str],
) -> list[str]:
    probe_module = _probe_module()

    if connected_files and diagnostics:
        return list(
            dict.fromkeys(
                connected_files
                + [
                    path
                    for path in fallback_focus_paths
                    if probe_module._looks_like_concrete_file_seed(path)
                ]
                + config_focus_paths
            )
        )
    if connected_files:
        return list(
            dict.fromkeys(
                connected_files
                + [
                    path
                    for path in fallback_focus_paths
                    if probe_module._looks_like_concrete_file_seed(path)
                ]
                + config_focus_paths
            )
        )
    return list(
        dict.fromkeys(
            (connected_files if connected_files else fallback_focus_paths)
            + fallback_focus_paths
            + config_focus_paths
        )
    )


def _candidate_config_focus_paths(
    *,
    repo_path: Path,
    focus_paths: list[str],
    diagnostic_base_path: Path,
    diagnostic_project_path: str | None,
) -> list[str]:
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if not resolved.exists() or not resolved.is_file():
            return
        if not (resolved == repo_path or repo_path in resolved.parents):
            return
        relative = str(resolved.relative_to(repo_path)).replace("\\", "/")
        if relative in seen:
            return
        seen.add(relative)
        candidates.append(relative)

    for focus_path in focus_paths:
        focus_candidate = (repo_path / focus_path).resolve()
        if focus_candidate.exists():
            current = focus_candidate if focus_candidate.is_dir() else focus_candidate.parent
            while current == repo_path or repo_path in current.parents:
                for name in (
                    "tsconfig.test.json",
                    "tsconfig.json",
                    "tsconfig.base.json",
                    "tsconfig.eslint.json",
                    "package.json",
                ):
                    _add(current / name)
                if current == repo_path:
                    break
                current = current.parent

    current = diagnostic_base_path
    while current == repo_path or repo_path in current.parents:
        for name in (
            "tsconfig.test.json",
            "tsconfig.json",
            "tsconfig.base.json",
            "tsconfig.eslint.json",
            "package.json",
        ):
            _add(current / name)
        if current == repo_path:
            break
        current = current.parent

    if diagnostic_project_path:
        _add(repo_path / diagnostic_project_path)

    return candidates


def _inventory_repo_surface(
    *,
    repo_path: Path,
    focus_paths: list[str],
    include_patterns: list[str],
    exclude_dirnames: set[str],
    max_file_size_bytes: int,
) -> dict[str, Any]:
    probe_module = _probe_module()

    file_count = 0
    total_bytes = 0
    suffix_counts: Counter[str] = Counter()
    for relative in probe_module._probe_repository_file_paths(
        repo_path=repo_path,
        focus_paths=focus_paths,
        include_patterns=include_patterns,
        exclude_dirnames=exclude_dirnames,
        max_files=None,
    ):
        candidate = repo_path / relative
        try:
            size = candidate.stat().st_size
        except OSError:
            continue
        if size > max_file_size_bytes:
            continue
        file_count += 1
        total_bytes += size
        suffix_counts[candidate.suffix.lower() or "<none>"] += 1
    return {
        "file_count": file_count,
        "total_bytes": total_bytes,
        "total_megabytes": round(total_bytes / 1024 / 1024, 2),
        "top_suffixes": dict(suffix_counts.most_common(12)),
    }
