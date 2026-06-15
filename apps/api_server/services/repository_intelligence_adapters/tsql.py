from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters import (
    sql as sql_adapter,
)

StableIdentifier = Callable[[str, Any], str]
ResolveTarget = sql_adapter.ResolveTarget

_PROJECT_INCLUDE_RE = re.compile(
    r"<(?:Build|Content|None|PostDeploy|PreDeploy)\b[^>]*\bInclude=\"(?P<path>[^\"]+)\"",
    re.IGNORECASE,
)
_PROJECT_FOLDER_RE = re.compile(
    r"<Folder\b[^>]*\bInclude=\"(?P<path>[^\"]+)\"",
    re.IGNORECASE,
)
_TSQL_PROJECT_RE = re.compile(
    r"<Project\b|<DSP>|<SqlCmdVariable\b|<PostDeploy\b|<PreDeploy\b|<Build\b[^>]*\bInclude=",
    re.IGNORECASE,
)
_GO_BATCH_RE = re.compile(r"(?im)^\s*GO(?:\s+\d+)?\s*$")
_DECLARE_VARIABLE_RE = re.compile(
    r"(?i)\bdeclare\s+@[A-Za-z_][A-Za-z0-9_]*\b"
)
_TRY_CATCH_RE = re.compile(r"(?i)\bbegin\s+try\b|\bbegin\s+catch\b|\bend\s+catch\b")
_TSQL_TYPE_RE = re.compile(
    r"(?i)\b(?:nvarchar|nchar|ntext|uniqueidentifier|sysname|datetime2|smalldatetime|money|smallmoney|varbinary)\b"
)
_TSQL_OBJECT_RE = re.compile(r"(?i)\b(?:dbo|sys)\s*\.\s*(?:\[[^\]]+\]|[A-Za-z_][A-Za-z0-9_$]*)")
_TEMP_TABLE_RE = re.compile(r"(?i)(?:\binto\s+|\bfrom\s+|\bjoin\s+)#(?:#)?[A-Za-z_][A-Za-z0-9_]*")
_TSQL_FLOW_RE = re.compile(r"(?i)\b(?:raiserror|throw|set\s+nocount\s+on|sp_executesql)\b")
_EXEC_RE = re.compile(
    r"\bexec(?:ute)?\s+(?P<name>"
    + sql_adapter.COMPOUND_IDENTIFIER_PATTERN
    + r")\b",
    re.IGNORECASE,
)
_PATH_HINT_TOKENS = frozenset(
    {
        "defaults",
        "functions",
        "postdeploy",
        "predeploy",
        "procedures",
        "roles",
        "schemas",
        "security",
        "storedprocedure",
        "storedprocedures",
        "synonyms",
        "tables",
        "triggers",
        "types",
        "users",
        "views",
    }
)
_PREFIX_HINTS = ("fn_", "sp_", "trg_", "ufn_", "usp_", "vw_")


def _normalized_parts(path: PurePosixPath) -> tuple[str, ...]:
    return tuple(
        re.sub(r"[^a-z0-9]+", "", part.lower())
        for part in path.parts
        if part not in {"", "."}
    )


def has_tsql_path_hints(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix in {".sqlproj", ".dbproj"}:
        return True
    normalized_parts = _normalized_parts(PurePosixPath(path))
    if any(part in _PATH_HINT_TOKENS for part in normalized_parts):
        return True
    if suffix != ".sql":
        return False
    return path.stem.lower().startswith(_PREFIX_HINTS)


def is_probable_tsql_project_config(*, path: Path, text: str) -> bool:
    if path.suffix.lower() not in {".sqlproj", ".dbproj"}:
        return False
    if not _TSQL_PROJECT_RE.search(text):
        return False
    return bool(
        _PROJECT_INCLUDE_RE.search(text)
        or re.search(r"(?i)sql\s+server|database\s+schema", text)
    )


def is_probable_tsql_source(*, path: Path, text: str) -> bool:
    suffix = path.suffix.lower()
    if suffix in {".sqlproj", ".dbproj"}:
        return is_probable_tsql_project_config(path=path, text=text)
    if suffix != ".sql":
        return False
    stripped_text = sql_adapter.strip_comments(text)
    has_path_hints = has_tsql_path_hints(path)
    score_threshold = 1 if has_path_hints else 3
    score = 0

    def _matches(pattern: re.Pattern[str]) -> bool:
        nonlocal score
        if pattern.search(stripped_text) is None:
            return False
        score += 2
        return score >= score_threshold

    def _matches_lightweight(pattern: re.Pattern[str]) -> bool:
        nonlocal score
        if pattern.search(stripped_text) is None:
            return False
        score += 1
        return score >= score_threshold

    if _matches(_GO_BATCH_RE):
        return True
    if _matches(_DECLARE_VARIABLE_RE):
        return True
    if _matches(_TRY_CATCH_RE):
        return True
    if _matches(_TSQL_FLOW_RE):
        return True
    if _matches_lightweight(_TSQL_TYPE_RE):
        return True
    if _matches_lightweight(_TSQL_OBJECT_RE):
        return True
    if _matches_lightweight(_TEMP_TABLE_RE):
        return True
    if _matches_lightweight(_EXEC_RE):
        return True
    if has_path_hints:
        return re.search(r"(?i)\[[^\]]+\]", stripped_text) is not None
    if re.search(r"(?i)\[[^\]]+\]", stripped_text):
        return score + 1 >= score_threshold
    return score >= 3


def _normalize_project_relative_path(
    *,
    project_dir: PurePosixPath,
    raw_path: str,
) -> str:
    path_text = str(raw_path or "").replace("\\", "/").strip()
    if not path_text:
        return ""
    combined_path = project_dir / PurePosixPath(path_text)
    normalized_parts: list[str] = []
    for part in combined_path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts:
                normalized_parts.pop()
            continue
        normalized_parts.append(part)
    return "/".join(normalized_parts)


def project_included_paths(*, text: str, project_file_path: str) -> tuple[str, ...]:
    project_dir = PurePosixPath(project_file_path).parent
    included_paths: list[str] = []
    seen: set[str] = set()
    for match in _PROJECT_INCLUDE_RE.finditer(text):
        normalized_path = _normalize_project_relative_path(
            project_dir=project_dir,
            raw_path=str(match.group("path") or ""),
        )
        if not normalized_path or not normalized_path.lower().endswith(".sql"):
            continue
        if normalized_path in seen:
            continue
        seen.add(normalized_path)
        included_paths.append(normalized_path)
    return tuple(included_paths)


def project_folder_paths(*, text: str, project_file_path: str) -> tuple[str, ...]:
    project_dir = PurePosixPath(project_file_path).parent
    folder_paths: list[str] = []
    seen: set[str] = set()
    for match in _PROJECT_FOLDER_RE.finditer(text):
        normalized_path = _normalize_project_relative_path(
            project_dir=project_dir,
            raw_path=str(match.group("path") or ""),
        ).rstrip("/")
        if not normalized_path or normalized_path in seen:
            continue
        seen.add(normalized_path)
        folder_paths.append(normalized_path)
    return tuple(folder_paths)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
    text: str | None = None,
) -> set[str]:
    path = PurePosixPath(file_path)
    suffix = path.suffix.lower()
    if suffix == ".sql":
        return sql_adapter.module_aliases_for_path(
            root_path=root_path,
            file_path=file_path,
            stable_identifier=stable_identifier,
            text=text,
        )
    if suffix not in {".sqlproj", ".dbproj"}:
        return set()
    without_suffix_path = str(path.with_suffix("")).lower()
    aliases = {
        file_path.lower(),
        path.stem.lower(),
        without_suffix_path,
        without_suffix_path.replace("/", "."),
    }
    return {alias for alias in aliases if alias and alias not in {".", "/"}}


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
    stripped_text: str | None = None,
) -> list[dict[str, Any]]:
    if PurePosixPath(file_path).suffix.lower() in {".sqlproj", ".dbproj"}:
        return []
    return sql_adapter.collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )


def iter_reference_targets(
    text: str,
    *,
    stripped_text: str | None = None,
) -> tuple[tuple[int, str, str], ...]:
    stripped_text = stripped_text if stripped_text is not None else sql_adapter.strip_comments(text)
    targets = list(sql_adapter.iter_reference_targets(text, stripped_text=stripped_text))
    for match in _EXEC_RE.finditer(stripped_text):
        target_name = str(match.group("name") or "").strip()
        if not target_name:
            continue
        line_no = sql_adapter._line_number(stripped_text, match.start())
        targets.append((line_no, "execute", target_name))
    return tuple(targets)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_target: ResolveTarget,
    stripped_text: str | None = None,
    reference_targets: tuple[tuple[int, str, str], ...] | None = None,
) -> tuple[dict[str, Any], ...]:
    if PurePosixPath(file_path).suffix.lower() in {".sqlproj", ".dbproj"}:
        return ()
    dependency_entries: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    for line_no, reference_kind, raw_target in (
        reference_targets
        if reference_targets is not None
        else iter_reference_targets(text, stripped_text=stripped_text)
    ):
        normalized_target, leaf_name = sql_adapter.symbol_name_parts(raw_target)
        if (
            not normalized_target
            or not leaf_name
            or leaf_name in sql_adapter.RESERVED_SYMBOL_NAMES
        ):
            continue
        target_file = resolve_target(raw_target, module_index)
        dependency_key = (target_file, leaf_name, "references")
        if (
            target_file is None
            or target_file == file_path
            or dependency_key in dependency_keys
        ):
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": normalized_target,
                        "line": line_no,
                        "kind": reference_kind,
                    },
                ),
                "source_file": file_path,
                "target_file": target_file,
                "target_symbol": leaf_name,
                "dependency_type": "references",
            }
        )
    return tuple(dependency_entries)


def parse_file(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_target: ResolveTarget,
) -> tuple[
    list[dict[str, Any]],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    if PurePosixPath(file_path).suffix.lower() in {".sqlproj", ".dbproj"}:
        return [], (), ()
    stripped_text = sql_adapter.strip_comments(text)
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
        stripped_text=stripped_text,
    )
    reference_candidates: dict[str, dict[str, Any]] = {}
    reference_targets = iter_reference_targets(text, stripped_text=stripped_text)
    for symbol_entry in symbol_entries:
        start_line = int(symbol_entry["start_line"])
        end_line = int(symbol_entry["end_line"])
        symbol_name = str(symbol_entry["symbol_name"]).lower()
        symbol_id = str(symbol_entry["symbol_id"])
        for line_no, reference_kind, raw_target in reference_targets:
            if line_no < start_line or line_no > end_line:
                continue
            normalized_target, leaf_name = sql_adapter.symbol_name_parts(raw_target)
            if (
                not normalized_target
                or not leaf_name
                or leaf_name in sql_adapter.RESERVED_SYMBOL_NAMES
                or leaf_name == symbol_name
            ):
                continue
            target_file = resolve_target(raw_target, module_index)
            if target_file is None or target_file == file_path:
                continue
            edge_id = stable_identifier(
                "ref",
                {
                    "source_symbol_id": symbol_id,
                    "target_file": target_file,
                    "target_names": (leaf_name,),
                    "type": "references_symbol",
                    "kind": reference_kind,
                },
            )
            reference_candidates.setdefault(
                edge_id,
                {
                    "reference_edge_id": edge_id,
                    "source_symbol_id": symbol_id,
                    "source_file": file_path,
                    "target_symbol_id": None,
                    "target_file": target_file,
                    "target_names": (leaf_name,),
                    "reference_type": "references_symbol",
                },
            )
    return (
        symbol_entries,
        parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_target=resolve_target,
            stripped_text=stripped_text,
            reference_targets=reference_targets,
        ),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )


normalize_identifier = sql_adapter.normalize_identifier
resolve_target = sql_adapter.resolve_target
strip_comments = sql_adapter.strip_comments
symbol_name_parts = sql_adapter.symbol_name_parts
