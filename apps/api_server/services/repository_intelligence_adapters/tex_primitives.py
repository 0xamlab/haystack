from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from pathlib import Path, PurePosixPath
from typing import Any

from apps.api_server.services.repository_intelligence_contracts import (
    _ImportedSymbolBinding,
    _Symbol,
)

StableIdentifier = Callable[[str, Any], str]
NormalizeRepositoryRelativePath = Callable[[str], str]
ResolveSuffixMatch = Callable[..., str | None]

TEX_SUFFIXES = frozenset({".tex", ".sty", ".cls", ".ltx", ".dtx"})
TEX_CONFIG_BASENAMES = frozenset({".latexmkrc", "latexmkrc", "tectonic.toml", "texmf.cnf"})
_COMMON_MODULE_ROOTS = frozenset(
    {
        "appendix",
        "appendices",
        "chapter",
        "chapters",
        "class",
        "classes",
        "content",
        "cv",
        "doc",
        "docs",
        "document",
        "documents",
        "example",
        "examples",
        "paper",
        "papers",
        "report",
        "reports",
        "resume",
        "resumes",
        "section",
        "sections",
        "src",
        "style",
        "styles",
        "template",
        "templates",
        "tex",
        "thesis",
        "theses",
    }
)
_COMMAND_DECLARATION_RE = re.compile(
    r"\\(?:(?:re)?newcommand|providecommand|DeclareRobustCommand)\*?\s*(?:\{\\(?P<braced>[A-Za-z@]+)\}|\\(?P<bare>[A-Za-z@]+))"
)
_ENV_DECLARATION_RE = re.compile(
    r"\\(?:re)?newenvironment\*?\s*\{(?P<name>[A-Za-z@:_./-]+)\}"
)
_LABEL_RE = re.compile(r"\\label\s*\{(?P<name>[A-Za-z0-9:_./-]+)\}")
_INPUT_RE = re.compile(
    r"\\(?P<kind>input|include|subfile)\s*(?:\{(?P<braced>[^{}\r\n]+)\}|(?P<bare>[^\s%\r\n]+))"
)
_PACKAGE_IMPORT_RE = re.compile(
    r"\\(?P<kind>usepackage|RequirePackage)\s*(?:\[[^\]]*\]\s*)?\{(?P<targets>[^{}\r\n]+)\}"
)
_CLASS_IMPORT_RE = re.compile(
    r"\\(?P<kind>documentclass|LoadClass)\s*(?:\[[^\]]*\]\s*)?\{(?P<targets>[^{}\r\n]+)\}"
)
_PROVIDES_RE = re.compile(r"\\Provides(?:Package|Class)\s*\{(?P<name>[A-Za-z0-9@._-]+)\}")
_LABEL_REF_RE = re.compile(
    r"\\(?:auto|eq|page|name|v|V|c|C)?ref\*?\s*\{(?P<name>[A-Za-z0-9:_./-]+)\}"
)
_COMMAND_USE_RE = re.compile(r"\\(?P<name>[A-Za-z@]+)\b")
_DECLARATION_LINE_RE = re.compile(
    r"\\(?:(?:re)?newcommand|providecommand|DeclareRobustCommand|(?:re)?newenvironment|label)\b"
)
_TEX_COMMAND_SIGNAL_RE = re.compile(r"\\[A-Za-z@]+")
_CONFIG_MARKER_RE = re.compile(
    r"(?m)(?:^latexmk|^TEXINPUTS|^mainfile\s*=|^output\s*=|^root\s*=)"
)
_RESERVED_COMMAND_NAMES = frozenset(
    {
        "author",
        "autoref",
        "begin",
        "bibliography",
        "caption",
        "chapter",
        "cite",
        "cref",
        "Cref",
        "documentclass",
        "emph",
        "end",
        "eqref",
        "footnote",
        "include",
        "input",
        "item",
        "label",
        "LoadClass",
        "nameref",
        "pageref",
        "part",
        "paragraph",
        "providecommand",
        "ref",
        "RequirePackage",
        "section",
        "subfile",
        "subsection",
        "subsubsection",
        "textbf",
        "textit",
        "usepackage",
        "vref",
    }
)


def _line_count(text: str) -> int:
    return max(1, text.count("\n") + 1)


def _line_number(text: str, offset: int) -> int:
    bounded_offset = max(0, min(offset, len(text)))
    return text.count("\n", 0, bounded_offset) + 1


def _ordered_names(*values: str) -> tuple[str, ...]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)


def _looks_binaryish(text: str) -> bool:
    sample = text[:2048]
    control_count = sum(
        1 for character in sample if 0 <= ord(character) < 32 and character not in "\n\r\t"
    )
    return control_count > max(2, len(sample) // 32)


def strip_comments(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines(keepends=True):
        characters: list[str] = []
        index = 0
        while index < len(raw_line):
            character = raw_line[index]
            if character == "%" and (index == 0 or raw_line[index - 1] != "\\"):
                break
            characters.append(character)
            index += 1
        if raw_line.endswith("\n") and (not characters or characters[-1] != "\n"):
            characters.append("\n")
        lines.append("".join(characters))
    return "".join(lines)


def has_tex_path_hints(path: Path | PurePosixPath) -> bool:
    normalized_path = PurePosixPath(path)
    return (
        normalized_path.suffix.lower() in TEX_SUFFIXES
        or normalized_path.name.lower() in TEX_CONFIG_BASENAMES
    )


def is_probable_tex_source(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.suffix.lower() not in TEX_SUFFIXES or not text or _looks_binaryish(text):
        return False
    stripped_text = strip_comments(text)
    if not stripped_text.strip():
        return False
    if normalized_path.suffix.lower() != ".cls":
        return True
    return bool(_TEX_COMMAND_SIGNAL_RE.search(stripped_text))


def is_probable_tex_config(*, path: Path | PurePosixPath, text: str) -> bool:
    normalized_path = PurePosixPath(path)
    if normalized_path.name.lower() not in TEX_CONFIG_BASENAMES or not text:
        return False
    stripped_text = strip_comments(text)
    return bool(stripped_text.strip()) and bool(_CONFIG_MARKER_RE.search(stripped_text))


def normalize_identifier(value: str) -> str:
    return str(value or "").strip().strip('"').strip("'").strip()


def _normalize_repository_relative_path(value: str) -> str:
    raw_parts = PurePosixPath(str(value).replace("\\", "/")).parts
    normalized_parts: list[str] = []
    for part in raw_parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts:
                normalized_parts.pop()
            continue
        normalized_parts.append(part)
    return "/".join(normalized_parts)


def module_name_from_path(file_path: str) -> str:
    normalized_path = PurePosixPath(file_path)
    without_suffix = normalized_path.with_suffix("")
    parts = list(without_suffix.parts)
    while parts and parts[0].lower() in _COMMON_MODULE_ROOTS:
        parts = parts[1:]
    return ".".join(parts) if parts else without_suffix.name


def provided_module_name(text: str) -> str | None:
    stripped_text = strip_comments(text)
    match = _PROVIDES_RE.search(stripped_text)
    if match is None:
        return None
    provided_name = normalize_identifier(str(match.group("name") or ""))
    return provided_name or None


def _normalize_import_target(raw_target: str, *, default_suffix: str) -> str:
    normalized_target = normalize_identifier(raw_target)
    if not normalized_target:
        return ""
    normalized_target = _normalize_repository_relative_path(normalized_target)
    if not normalized_target:
        return ""
    if PurePosixPath(normalized_target).suffix:
        return normalized_target
    return f"{normalized_target}{default_suffix}"


def _split_import_targets(raw_targets: str) -> tuple[str, ...]:
    values = [
        normalize_identifier(target)
        for target in str(raw_targets or "").split(",")
    ]
    return tuple(value for value in values if value)


def iter_import_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _INPUT_RE.finditer(stripped_text):
        raw_target = normalize_identifier(
            str(match.group("braced") or match.group("bare") or "")
        )
        target = _normalize_import_target(raw_target, default_suffix=".tex")
        if not target:
            continue
        item = ("includes", target, _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    for pattern, dependency_type, default_suffix in (
        (_PACKAGE_IMPORT_RE, "imports", ".sty"),
        (_CLASS_IMPORT_RE, "extends", ".cls"),
    ):
        for match in pattern.finditer(stripped_text):
            for raw_target in _split_import_targets(str(match.group("targets") or "")):
                target = _normalize_import_target(raw_target, default_suffix=default_suffix)
                if not target:
                    continue
                item = (dependency_type, target, _line_number(stripped_text, match.start()))
                if item in seen:
                    continue
                seen.add(item)
                entries.append(item)
    return tuple(entries)


def iter_symbol_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _COMMAND_DECLARATION_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(
            str(match.group("braced") or match.group("bare") or "")
        )
        if not symbol_name:
            continue
        item = (symbol_name, "command", _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    for match in _ENV_DECLARATION_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not symbol_name:
            continue
        item = (symbol_name, "environment", _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    for match in _LABEL_RE.finditer(stripped_text):
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not symbol_name:
            continue
        item = (symbol_name, "label", _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def iter_reference_entries(text: str) -> tuple[tuple[str, str, int], ...]:
    stripped_text = strip_comments(text)
    entries: list[tuple[str, str, int]] = []
    seen: set[tuple[str, str, int]] = set()
    for match in _LABEL_REF_RE.finditer(stripped_text):
        target_name = normalize_identifier(str(match.group("name") or ""))
        if not target_name:
            continue
        item = ("label_ref", target_name, _line_number(stripped_text, match.start()))
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    for match in _COMMAND_USE_RE.finditer(stripped_text):
        line_number = _line_number(stripped_text, match.start())
        line_start = stripped_text.rfind("\n", 0, match.start()) + 1
        line_end = stripped_text.find("\n", match.start())
        if line_end < 0:
            line_end = len(stripped_text)
        raw_line = stripped_text[line_start:line_end]
        if _DECLARATION_LINE_RE.search(raw_line):
            continue
        symbol_name = normalize_identifier(str(match.group("name") or ""))
        if not symbol_name or symbol_name in _RESERVED_COMMAND_NAMES:
            continue
        item = ("command_ref", symbol_name, line_number)
        if item in seen:
            continue
        seen.add(item)
        entries.append(item)
    return tuple(entries)


def module_aliases_for_path(
    *,
    root_path: Path,
    file_path: str,
    stable_identifier: StableIdentifier,
) -> set[str]:
    del stable_identifier
    path = PurePosixPath(file_path)
    if path.suffix.lower() not in TEX_SUFFIXES:
        return set()
    aliases = {
        file_path,
        path.name,
        path.stem,
        str(path.with_suffix("")),
        str(path.with_suffix("")).replace("/", "."),
    }
    try:
        text = (root_path / path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        text = ""
    if text and not is_probable_tex_source(path=path, text=text):
        return {alias for alias in aliases if alias}
    module_name = provided_module_name(text) or module_name_from_path(file_path)
    if module_name:
        aliases.add(module_name)
        aliases.add(module_name.replace("/", "."))
    for symbol_name, _symbol_kind, _line_number in iter_symbol_entries(text):
        aliases.add(symbol_name)
        if module_name:
            aliases.add(f"{module_name}.{symbol_name}")
    return {alias for alias in aliases if alias}


def resolve_import(
    *,
    current_file: str,
    import_target: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> str | None:
    normalized_target = normalize_identifier(import_target)
    if not normalized_target:
        return None
    current_dir = normalize_repository_relative_path(str(PurePosixPath(current_file).parent))
    candidate_keys = [normalized_target]
    if current_dir:
        candidate_keys.append(
            normalize_repository_relative_path(str(PurePosixPath(current_dir) / normalized_target))
        )
    for candidate_key in candidate_keys:
        normalized_candidate = normalize_repository_relative_path(candidate_key)
        if not normalized_candidate:
            continue
        resolved = module_index.get(normalized_candidate)
        if resolved is not None and resolved != current_file:
            return resolved
    return resolve_suffix_match(
        module_index=module_index,
        suffixes=tuple(f"/{PurePosixPath(candidate).name}" for candidate in candidate_keys),
    )


def _target_aliases_for_file(
    *,
    target_file: str,
    module_index: dict[str, str],
) -> tuple[str, ...]:
    module_name = module_name_from_path(target_file)
    aliases = list(
        _ordered_names(
            PurePosixPath(target_file).stem,
            module_name,
            module_name.split(".")[-1] if module_name else "",
        )
    )
    for alias, resolved_path in module_index.items():
        if resolved_path != target_file:
            continue
        normalized_alias = normalize_identifier(alias)
        if (
            not normalized_alias
            or "/" in normalized_alias
            or normalized_alias == PurePosixPath(target_file).name
            or normalized_alias == target_file
        ):
            continue
        aliases.extend(_ordered_names(normalized_alias))
    return _ordered_names(*aliases)


def imported_symbol_bindings(
    *,
    current_file: str,
    text: str,
    module_index: dict[str, str],
    normalize_repository_relative_path: NormalizeRepositoryRelativePath,
    resolve_suffix_match: ResolveSuffixMatch,
) -> dict[str, _ImportedSymbolBinding]:
    bindings: dict[str, _ImportedSymbolBinding] = {}
    for _dependency_type, import_target, _line_number in iter_import_entries(text):
        target_file = resolve_import(
            current_file=current_file,
            import_target=import_target,
            module_index=module_index,
            normalize_repository_relative_path=normalize_repository_relative_path,
            resolve_suffix_match=resolve_suffix_match,
        )
        if target_file is None:
            continue
        for alias_name in _target_aliases_for_file(target_file=target_file, module_index=module_index):
            bindings.setdefault(
                alias_name,
                _ImportedSymbolBinding(
                    alias=alias_name,
                    target_file=target_file,
                    target_names=(alias_name,),
                ),
            )
    return bindings


def collect_symbols(
    *,
    file_path: str,
    text: str,
    stable_identifier: StableIdentifier,
) -> tuple[_Symbol, ...]:
    stripped_text = strip_comments(text)
    module_name = provided_module_name(text) or module_name_from_path(file_path) or PurePosixPath(
        file_path
    ).stem
    module_symbol = _Symbol(
        symbol_id=stable_identifier(
            "sym",
            {"file_path": file_path, "symbol_name": module_name, "symbol_kind": "tex"},
        ),
        symbol_name=module_name,
        symbol_kind="tex",
        start_line=1,
        end_line=_line_count(stripped_text),
        parent_symbol_id=None,
        signature=f"tex {module_name}",
    )
    symbols: list[_Symbol] = [module_symbol]
    for symbol_name, symbol_kind, line_number in iter_symbol_entries(text):
        symbols.append(
            _Symbol(
                symbol_id=stable_identifier(
                    "sym",
                    {
                        "file_path": file_path,
                        "symbol_name": symbol_name,
                        "symbol_kind": symbol_kind,
                        "line": line_number,
                    },
                ),
                symbol_name=symbol_name,
                symbol_kind=symbol_kind,
                start_line=line_number,
                end_line=line_number,
                parent_symbol_id=module_symbol.symbol_id,
                signature=f"{symbol_kind} {symbol_name}",
            )
        )
    return tuple(symbols)


def source_symbol_name_for_line(
    symbol_entries: Iterable[tuple[str, str, int]],
    *,
    line_number: int,
) -> str | None:
    active_name: str | None = None
    active_line = -1
    for symbol_name, _symbol_kind, start_line in symbol_entries:
        if start_line <= line_number and start_line >= active_line:
            active_name = symbol_name
            active_line = start_line
    return active_name
