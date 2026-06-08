from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_adapters.assembly_support import (
    _CONTROL_TRANSFER_OPCODES,
    _DATA_SECTION_TOKENS,
    _INCLUDE_RE,
    _KNOWN_ASSEMBLY_SUFFIXES,
    _LABEL_RE,
    _MACRO_RE,
    _NAME_TOKEN_RE,
    _PROC_RE,
    _SECTION_DIRECTIVE_RE,
    _SEGMENT_REGISTERS,
    _TEXT_SECTION_TOKENS,
    _first_token,
    _is_numeric_token,
    _label_symbol_kind,
    _normalize_repository_relative_path,
    _symbol_name_is_eligible,
    has_assembly_markers,
    is_probable_assembly_source,
    normalize_identifier,
    strip_comments,
)

__all__ = ("is_probable_assembly_source",)

StableIdentifier = Callable[[str, Any], str]
ResolveSuffixMatch = Callable[[dict[str, str], Sequence[str]], str | None]
ResolveImport = Callable[[str, str, dict[str, str]], str | None]
ResolveTarget = Callable[[str, str, dict[str, str]], str | None]


def collect_symbol_entries(
    text: str,
    *,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> list[dict[str, Any]]:
    stripped_text = strip_comments(text)
    path = PurePosixPath(file_path)
    file_alias = normalize_identifier(path.stem)
    final_line = len(stripped_text.splitlines()) if stripped_text else 1
    current_section = ""
    symbol_entries: list[dict[str, Any]] = []
    seen_symbol_keys: set[tuple[str, str, int]] = set()

    for line_no, raw_line in enumerate(stripped_text.splitlines(), start=1):
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        if stripped_line.lower() in _TEXT_SECTION_TOKENS | _DATA_SECTION_TOKENS:
            current_section = stripped_line.lower()
            continue
        section_match = _SECTION_DIRECTIVE_RE.match(stripped_line)
        if section_match is not None:
            current_section = str(section_match.group("name") or "").strip().lower()
            continue

        symbol_name = ""
        symbol_kind = ""
        proc_match = _PROC_RE.match(stripped_line)
        if proc_match is not None:
            symbol_name = normalize_identifier(str(proc_match.group("name") or ""))
            symbol_kind = "function"
        else:
            macro_match = _MACRO_RE.match(stripped_line)
            if macro_match is not None:
                symbol_name = normalize_identifier(str(macro_match.group("name") or ""))
                symbol_kind = "function"
            else:
                label_match = _LABEL_RE.match(stripped_line)
                if label_match is not None:
                    symbol_name = normalize_identifier(str(label_match.group("name") or ""))
                    symbol_kind = _label_symbol_kind(
                        symbol_name=symbol_name,
                        body=str(label_match.group("body") or ""),
                        current_section=current_section,
                    )
        if not _symbol_name_is_eligible(symbol_name):
            continue
        symbol_key = (symbol_kind, symbol_name, line_no)
        if symbol_key in seen_symbol_keys:
            continue
        seen_symbol_keys.add(symbol_key)
        qualified_names = {symbol_name}
        if file_alias and file_alias != symbol_name:
            qualified_names.add(f"{file_alias}.{symbol_name}")
        symbol_entries.append(
            {
                "symbol_id": stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "name": symbol_name,
                        "kind": symbol_kind,
                        "line": line_no,
                    },
                ),
                "symbol_name": symbol_name,
                "symbol_kind": symbol_kind,
                "start_line": line_no,
                "end_line": line_no,
                "signature": stripped_line,
                "qualified_names": tuple(sorted(qualified_names)),
            }
        )
    for index, entry in enumerate(symbol_entries):
        if index + 1 < len(symbol_entries):
            entry["end_line"] = max(
                int(symbol_entries[index + 1]["start_line"]) - 1,
                int(entry["start_line"]),
            )
        else:
            entry["end_line"] = final_line
    return symbol_entries


def _path_aliases(path: PurePosixPath) -> set[str]:
    without_suffix = str(path.with_suffix("")).lower()
    aliases = {
        str(path).lower(),
        without_suffix,
        without_suffix.replace("/", "."),
        path.stem.lower(),
    }
    source_parts = list(path.parts)
    for source_root in ("src", "source", "asm", "assembly", "include", "inc", "lib"):
        if source_root not in source_parts:
            continue
        root_index = source_parts.index(source_root)
        derived_parts = list(source_parts[root_index + 1 :])
        if not derived_parts:
            continue
        derived_parts[-1] = PurePosixPath(derived_parts[-1]).stem
        derived_alias = ".".join(part for part in derived_parts if part).lower()
        if derived_alias:
            aliases.add(derived_alias)
            aliases.add(derived_alias.rsplit(".", 1)[-1])
        break
    return {alias for alias in aliases if alias and alias not in {".", "/"}}


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in _KNOWN_ASSEMBLY_SUFFIXES:
        return set()
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if path.suffix.lower() == ".inc" and text and not has_assembly_markers(text):
        return set()
    aliases = set(_path_aliases(path))
    for symbol_entry in collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    ):
        aliases.update(
            str(alias).lower() for alias in symbol_entry["qualified_names"] if alias
        )
    return {alias for alias in aliases if alias}


def _normalize_import_target(raw_target: str) -> str:
    normalized = str(raw_target or "").strip().strip("<>\"'").replace("\\", "/")
    return _normalize_repository_relative_path(normalized).lower()


def _candidate_import_keys(import_target: str, *, current_file: str) -> tuple[str, ...]:
    normalized_target = _normalize_import_target(import_target)
    if not normalized_target:
        return ()
    current_parent = PurePosixPath(current_file).parent
    raw_candidates = [normalized_target]
    if not PurePosixPath(normalized_target).suffix:
        raw_candidates.extend(
            f"{normalized_target}{suffix}" for suffix in _KNOWN_ASSEMBLY_SUFFIXES
        )
    candidate_keys: list[str] = []
    seen_keys: set[str] = set()
    for raw_candidate in raw_candidates:
        for candidate in (
            raw_candidate,
            _normalize_repository_relative_path(str(current_parent / raw_candidate)),
        ):
            normalized_candidate = candidate.lower()
            if not normalized_candidate or normalized_candidate in seen_keys:
                continue
            seen_keys.add(normalized_candidate)
            candidate_keys.append(normalized_candidate)
    return tuple(candidate_keys)


def _candidate_reference_names(raw_target: str) -> tuple[str, ...]:
    segments = [segment.strip() for segment in str(raw_target or "").split(",") if segment.strip()]
    candidate_names: list[str] = []
    seen_names: set[str] = set()
    for segment in reversed(segments):
        for token in reversed(_NAME_TOKEN_RE.findall(segment)):
            normalized_token = normalize_identifier(token)
            if ":" in normalized_token:
                left, right = normalized_token.split(":", 1)
                if left in _SEGMENT_REGISTERS or _is_numeric_token(left):
                    normalized_token = right
            if "@" in normalized_token and not normalized_token.startswith("@@"):
                normalized_token = normalized_token.split("@", 1)[0]
            if not _symbol_name_is_eligible(normalized_token):
                continue
            if normalized_token not in seen_names:
                seen_names.add(normalized_token)
                candidate_names.append(normalized_token)
            if "." in normalized_token:
                leaf_name = normalized_token.rsplit(".", 1)[-1]
                if _symbol_name_is_eligible(leaf_name) and leaf_name not in seen_names:
                    seen_names.add(leaf_name)
                    candidate_names.append(leaf_name)
        if candidate_names:
            break
    return tuple(candidate_names)


def resolve_import(
    current_file: str,
    import_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    candidate_keys = _candidate_import_keys(import_target, current_file=current_file)
    if not candidate_keys:
        return None
    for candidate_key in candidate_keys:
        direct_match = module_index.get(candidate_key)
        if direct_match is not None:
            return direct_match
    return resolve_suffix_match(module_index=module_index, suffixes=candidate_keys)


def resolve_target(
    current_file: str,
    reference_target: str,
    *,
    module_index: dict[str, str],
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    candidate_names = _candidate_reference_names(reference_target)
    if not candidate_names:
        return None
    suffixes: list[str] = []
    for candidate_name in candidate_names:
        direct_match = module_index.get(candidate_name)
        if direct_match is not None:
            return direct_match
        suffixes.extend(
            [
                candidate_name,
                f"{candidate_name}.asm",
                f"{candidate_name}.s",
                f"src/{candidate_name}.asm",
                f"src/{candidate_name}.s",
                f"asm/{candidate_name}.asm",
                f"asm/{candidate_name}.s",
                f"include/{candidate_name}.inc",
                f"inc/{candidate_name}.inc",
            ]
        )
    return resolve_suffix_match(module_index=module_index, suffixes=suffixes)


def _include_aliases(import_target: str) -> tuple[str, ...]:
    path = PurePosixPath(_normalize_import_target(import_target))
    return tuple(sorted(_path_aliases(path)))


def _extern_targets(text: str) -> tuple[str, ...]:
    targets: list[str] = []
    seen_targets: set[str] = set()
    for raw_line in strip_comments(text).splitlines():
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        first_token = _first_token(stripped_line)
        if first_token not in {"extern", "extrn", "export", "global", "public"}:
            continue
        body = stripped_line.split(None, 1)[1] if " " in stripped_line else ""
        for token in _NAME_TOKEN_RE.findall(body):
            normalized_token = normalize_identifier(token)
            if not _symbol_name_is_eligible(normalized_token) or normalized_token in seen_targets:
                continue
            seen_targets.add(normalized_token)
            targets.append(normalized_token)
    return tuple(targets)


def extract_import_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
    resolve_target: ResolveTarget,
) -> tuple[tuple[dict[str, Any], ...], dict[str, dict[str, Any]]]:
    dependencies: list[dict[str, Any]] = []
    dependency_keys: set[tuple[str | None, str, str]] = set()
    import_bindings: dict[str, dict[str, Any]] = {}

    for import_index, match in enumerate(_INCLUDE_RE.finditer(strip_comments(text))):
        raw_target = (
            match.group("double") or match.group("single") or match.group("angle") or ""
        ).strip()
        normalized_target = _normalize_import_target(raw_target)
        if not normalized_target:
            continue
        target_file = resolve_import(file_path, raw_target, module_index)
        target_symbol = PurePosixPath(normalized_target).stem.lower()
        dependency_key = (target_file, target_symbol, "imports")
        if dependency_key not in dependency_keys:
            dependency_keys.add(dependency_key)
            dependencies.append(
                {
                    "dependency_edge_id": stable_identifier(
                        "dep",
                        {
                            "file_path": file_path,
                            "target": normalized_target,
                            "index": import_index,
                        },
                    ),
                    "source_file": file_path,
                    "target_file": target_file,
                    "target_symbol": target_symbol,
                    "dependency_type": "imports",
                }
            )
        for alias in _include_aliases(normalized_target):
            import_bindings.setdefault(
                alias,
                {
                    "alias": alias,
                    "target_file": target_file,
                    "target_names": tuple(
                        alias_name
                        for alias_name in _include_aliases(normalized_target)
                        if alias_name
                    ),
                },
            )

    for extern_target in _extern_targets(text):
        target_file = resolve_target(file_path, extern_target, module_index)
        import_bindings.setdefault(
            extern_target,
            {
                "alias": extern_target,
                "target_file": target_file,
                "target_names": (extern_target,),
            },
        )
    return tuple(dependencies), import_bindings


def _reference_bindings(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    import_bindings: dict[str, dict[str, Any]],
    resolve_target: ResolveTarget,
) -> tuple[dict[str, Any], ...]:
    bindings: list[dict[str, Any]] = []
    seen_bindings: set[tuple[int, str, tuple[str, ...]]] = set()
    for line_no, raw_line in enumerate(strip_comments(text).splitlines(), start=1):
        stripped_line = raw_line.strip()
        if not stripped_line:
            continue
        label_match = _LABEL_RE.match(stripped_line)
        if label_match is not None:
            stripped_line = str(label_match.group("body") or "").strip()
            if not stripped_line:
                continue
        opcode = _first_token(stripped_line).lstrip(".")
        if opcode not in _CONTROL_TRANSFER_OPCODES and not (
            opcode.startswith("j") and len(opcode) > 1
        ):
            continue
        body = stripped_line.split(None, 1)[1] if " " in stripped_line else ""
        candidate_names = _candidate_reference_names(body)
        if not candidate_names:
            continue
        target_file = None
        target_names = candidate_names
        for candidate_name in candidate_names:
            binding = import_bindings.get(candidate_name)
            if binding is not None and isinstance(binding.get("target_file"), str):
                target_file = str(binding["target_file"])
                target_names = tuple(
                    str(name).lower()
                    for name in binding.get("target_names", ())
                    if str(name).strip()
                ) or candidate_names
                break
            target_file = resolve_target(file_path, candidate_name, module_index)
            if target_file is not None:
                break
        if target_file is None or target_file == file_path:
            continue
        binding_key = (line_no, target_file, tuple(target_names))
        if binding_key in seen_bindings:
            continue
        seen_bindings.add(binding_key)
        bindings.append(
            {
                "line_no": line_no,
                "target_file": target_file,
                "target_names": tuple(target_names),
                "target_symbol": target_names[0].rsplit(".", 1)[-1],
            }
        )
    return tuple(bindings)


def parse_dependencies_only(
    file_path: str,
    text: str,
    module_index: dict[str, str],
    *,
    stable_identifier: StableIdentifier,
    resolve_import: ResolveImport,
    resolve_target: ResolveTarget,
) -> tuple[dict[str, Any], ...]:
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
        resolve_target=resolve_target,
    )
    dependency_entries = list(dependencies)
    dependency_keys = {
        (entry["target_file"], entry["target_symbol"], entry["dependency_type"])
        for entry in dependency_entries
    }
    for binding in _reference_bindings(
        file_path,
        text,
        module_index,
        import_bindings=import_bindings,
        resolve_target=resolve_target,
    ):
        dependency_key = (
            binding["target_file"],
            binding["target_symbol"],
            "references",
        )
        if dependency_key in dependency_keys:
            continue
        dependency_keys.add(dependency_key)
        dependency_entries.append(
            {
                "dependency_edge_id": stable_identifier(
                    "dep",
                    {
                        "file_path": file_path,
                        "target": binding["target_names"],
                        "line": binding["line_no"],
                        "kind": "control_transfer",
                    },
                ),
                "source_file": file_path,
                "target_file": binding["target_file"],
                "target_symbol": binding["target_symbol"],
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
    resolve_import: ResolveImport,
    resolve_target: ResolveTarget,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    symbol_entries = collect_symbol_entries(
        text,
        file_path=file_path,
        stable_identifier=stable_identifier,
    )
    symbols = tuple(
        {
            "symbol_id": str(entry["symbol_id"]),
            "symbol_name": str(entry["symbol_name"]),
            "symbol_kind": str(entry["symbol_kind"]),
            "start_line": int(entry["start_line"]),
            "end_line": int(entry["end_line"]),
            "signature": str(entry["signature"]),
        }
        for entry in symbol_entries
    )
    dependencies, import_bindings = extract_import_bindings(
        file_path,
        text,
        module_index,
        stable_identifier=stable_identifier,
        resolve_import=resolve_import,
        resolve_target=resolve_target,
    )
    dependency_entries = list(
        parse_dependencies_only(
            file_path,
            text,
            module_index,
            stable_identifier=stable_identifier,
            resolve_import=resolve_import,
            resolve_target=resolve_target,
        )
    )
    if not dependencies:
        dependency_entries = list(dependency_entries)

    def _symbol_for_line(line_no: int) -> dict[str, Any] | None:
        for symbol_entry in reversed(symbol_entries):
            if int(symbol_entry["start_line"]) <= line_no <= int(symbol_entry["end_line"]):
                return symbol_entry
        return None

    reference_candidates: dict[str, dict[str, Any]] = {}
    for binding in _reference_bindings(
        file_path,
        text,
        module_index,
        import_bindings=import_bindings,
        resolve_target=resolve_target,
    ):
        source_symbol = _symbol_for_line(int(binding["line_no"]))
        if source_symbol is None:
            continue
        edge_id = stable_identifier(
            "ref",
            {
                "source_symbol_id": source_symbol["symbol_id"],
                "target_file": binding["target_file"],
                "target_names": binding["target_names"],
                "type": "references_symbol",
            },
        )
        reference_candidates.setdefault(
            edge_id,
            {
                "reference_edge_id": edge_id,
                "source_symbol_id": str(source_symbol["symbol_id"]),
                "source_file": file_path,
                "target_symbol_id": None,
                "target_file": str(binding["target_file"]),
                "target_names": tuple(binding["target_names"]),
                "reference_type": "references_symbol",
            },
        )
    return (
        symbols,
        tuple(dependency_entries),
        tuple(reference_candidates[key] for key in sorted(reference_candidates)),
    )
